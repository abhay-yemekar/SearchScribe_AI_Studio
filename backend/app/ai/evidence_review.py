"""Select immutable source passages before writing; an AI review is not verification."""

from __future__ import annotations

import json
from dataclasses import replace
from types import GenericAlias
from typing import Annotated, Literal, cast

from pydantic import BaseModel, Field, create_model

from ..core.config import settings
from .base import LLMError, LLMProvider, ProviderResponse, SchemaValidationError
from .budget import attempt_budget
from .research import ResearchResult
from .research_plan import ResearchPlan, research_provider
from .schemas import ResearchSummary


class EvidenceSelection(BaseModel):
    source_id: str = Field(pattern=r"^S[1-6]$")
    role: Literal["primary", "secondary", "uncertain"]
    passage_ids: list[str] = Field(min_length=1, max_length=16)


class EvidenceConflict(BaseModel):
    source_ids: list[str] = Field(min_length=2, max_length=5)
    description: str = Field(max_length=350)


class EvidenceReview(BaseModel):
    selections: list[EvidenceSelection] = Field(max_length=5)
    conflicts: list[EvidenceConflict] = Field(max_length=3)
    limitations: list[Annotated[str, Field(min_length=1, max_length=350)]] = Field(max_length=3)


def source_passages(research: ResearchResult) -> dict[str, dict[str, str]]:
    """Stable bounded text blocks; only the server copies original evidence."""
    passages: dict[str, dict[str, str]] = {}
    for source in research.summary.sources:
        remaining = research.excerpts.get(source.id, "")
        chunks: dict[str, str] = {}
        while remaining:
            end = len(remaining) if len(remaining) <= 750 else remaining.rfind(" ", 0, 751)
            if end <= 0:
                end = min(750, len(remaining))
            chunks[f"{source.id}-P{len(chunks) + 1}"] = remaining[:end]
            remaining = remaining[end:].lstrip()
        passages[source.id] = chunks
    return passages


def review_evidence(
    query: str, research: ResearchResult, plan: ResearchPlan, provider: LLMProvider,
) -> ProviderResponse[EvidenceReview]:
    provider = research_provider(provider, review=True)
    passages = source_passages(research)
    references = [
        {**source.model_dump(), "passages": passages[source.id]}
        for source in research.summary.sources
    ]
    variables = {
        "topic_json": json.dumps(query, ensure_ascii=False),
        "plan_json": plan.model_dump_json(),
        "research_context": research.context.split("\n", 1)[0] + "\n" + json.dumps(
            references, ensure_ascii=False,
        ),
    }
    variables = {key: value.replace("<", "\\u003c").replace(">", "\\u003e")
                 for key, value in variables.items()}
    # Bind the request schema to actual server-assigned IDs. The writer/reviewer
    # cannot choose a plausible but nonexistent spelling; ownership is checked
    # again locally. No publisher names or domains are encoded in this schema.
    selection_schema = create_model(
        "EvidenceSelectionForSources", __base__=EvidenceSelection,
        source_id=(str, Field(json_schema_extra={"enum": list(passages)})),
        passage_ids=(list[str], Field(min_length=1, max_length=16, json_schema_extra={
            "items": {"type": "string", "enum": [
                key for group in passages.values() for key in group
            ]},
        })),
    )
    response_schema = cast(type[EvidenceReview], create_model(
        "EvidenceReviewForSources", __base__=EvidenceReview,
        selections=(GenericAlias(list, selection_schema), Field(max_length=5)),
    ))
    try:
        with attempt_budget(20):
            response = provider.generate("evidence_review", "v1", variables, response_schema)
            return replace(response, data=EvidenceReview.model_validate(response.data.model_dump()))
    except LLMError as exc:
        exc.provider, exc.model = provider.name, provider.model
        raise


def select_evidence(
    research: ResearchResult, review: EvidenceReview, *, primary_only: bool,
) -> ResearchResult:
    sources = {source.id: source for source in research.summary.sources}
    passages = source_passages(research)
    selected = []
    records = []
    selected_excerpts: dict[str, str] = {}
    used_ids: set[str] = set()
    # Duplicate rows are a recoverable formatting variation, not new evidence.
    # Merge valid passage references; conflicting role assessments lose trust.
    merged: dict[str, EvidenceSelection] = {}
    for selection in review.selections:
        if selection.source_id not in merged:
            merged[selection.source_id] = selection.model_copy(deep=True)
        else:
            existing = merged[selection.source_id]
            existing.passage_ids.extend(selection.passage_ids)
            if existing.role != selection.role:
                existing.role = "uncertain"
    selections = list(merged.values())
    requested_ids = {selection.source_id for selection in selections}
    for conflict in review.conflicts:
        if not set(conflict.source_ids).issubset(sources) or len(set(conflict.source_ids)) < 2:
            raise SchemaValidationError("Evidence conflict references unsupported sources")
        # A conflict cannot silently lose its other side because the model omitted
        # that source from selections. Keep original text, labelled uncertain.
        if not primary_only:
            for source_id in conflict.source_ids:
                if source_id not in requested_ids:
                    selections.append(EvidenceSelection(
                        source_id=source_id, role="uncertain",
                        passage_ids=list(passages[source_id]),
                    ))
                    requested_ids.add(source_id)
    for selection in selections:
        source_id = selection.source_id
        if source_id not in sources or source_id in used_ids:
            raise SchemaValidationError("Evidence selection references an unsupported source")
        used_ids.add(source_id)
        if any(
            passage_id not in passages[source_id] for passage_id in selection.passage_ids
        ):
            raise SchemaValidationError("Evidence selection references an unsupported passage")
        if primary_only and selection.role != "primary":
            continue
        selected.append(sources[source_id])
        selected_excerpts[source_id] = " [...] ".join(
            text for passage_id, text in passages[source_id].items()
            if passage_id in selection.passage_ids
        )
        records.append({**sources[source_id].model_dump(), "excerpt": selected_excerpts[source_id],
                        "model_assessed_role": selection.role})
    if not selected:
        message = (
            "The retrieved excerpts did not establish usable first-party evidence. "
            "Try a more specific topic or the publisher's documentation title."
            if primary_only else "The retrieved excerpts did not establish relevant evidence. "
            "Try a more specific topic."
        )
        return ResearchResult(ResearchSummary(), message, "no_evidence", message)
    selected_ids = {source.id for source in selected}
    conflicts = []
    for conflict in review.conflicts:
        if set(conflict.source_ids).issubset(selected_ids):
            conflicts.append(conflict.model_dump())
    if any(not text.strip() or len(text) > 350 for text in review.limitations):
        raise SchemaValidationError("Evidence limitations exceed their bounds")
    # Passages retain their real IDs and original URLs. Non-selected raw excerpts
    # never reach the writer, including secondary material in official-only tasks.
    notice = research.context.split("\n", 1)[0]
    notes = json.dumps({"conflicts_to_attribute": conflicts,
                        "coverage_gaps_to_explain": review.limitations}, ensure_ascii=False)
    context = notice + "\nAI-selected source passages; selection is not fact-checking. " + notes
    for record in records:
        context += "\n" + json.dumps(record, ensure_ascii=False)
    context = context.replace("<", "\\u003c").replace(">", "\\u003e")
    if len(context) > settings.research_max_context_chars:
        raise SchemaValidationError("Selected evidence exceeds the research context budget")
    return ResearchResult(
        research.summary.model_copy(update={"sources": selected}), context,
        excerpts=selected_excerpts,
    )
