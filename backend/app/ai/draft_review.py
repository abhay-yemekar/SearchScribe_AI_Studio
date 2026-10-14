"""Bounded evidence editing after writing, with server-owned coverage and patches.

This is an AI consistency check against retrieved excerpts, not independent fact
verification. A correction gets one recheck; neither step may silently skip text.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from types import GenericAlias
from typing import Any, Literal, cast

from pydantic import BaseModel, Field, ValidationError, create_model

from ..core.config import settings
from .base import LLMError, LLMProvider, ProviderResponse, SchemaValidationError
from .budget import attempt_budget
from .evidence_review import source_passages
from .factory import _build_provider
from .gemini import GeminiProvider
from .groq import GroqProvider
from .research import ResearchResult
from .research_plan import research_provider
from .schemas import GeneratedArticle, SeoCandidate, SeoResult
from .validation import validate_generated_seo


class BlockReview(BaseModel):
    block_id: str = Field(pattern=r"^D[1-9]\d{0,2}$")
    verdict: Literal["supported", "editorial", "revise"]
    passage_ids: list[str] = Field(max_length=16)
    reason: str = Field(min_length=1, max_length=2000)
    replacement: str = Field(max_length=4000)


class DraftReview(BaseModel):
    blocks: list[BlockReview] = Field(min_length=1, max_length=128)


class RecheckIssue(BaseModel):
    block_id: str = Field(pattern=r"^D[1-9]\d{0,2}$")
    reason: str = Field(min_length=1, max_length=2000)


class DraftRecheck(BaseModel):
    reviewed_block_ids: list[str] = Field(min_length=1, max_length=128)
    issues: list[RecheckIssue] = Field(max_length=128)


@dataclass(frozen=True)
class DraftBlock:
    id: str
    path: tuple[str | int, ...]
    text: str


def draft_blocks(article: GeneratedArticle, seo: SeoResult | None) -> list[DraftBlock]:
    blocks: list[DraftBlock] = []

    def add(path: tuple[str | int, ...], text: str) -> None:
        if text.strip():
            blocks.append(DraftBlock(f"D{len(blocks) + 1}", path, text))

    add(("title",), article.title)
    add(("introduction",), article.introduction)
    for index, section in enumerate(article.sections):
        add(("sections", index, "heading"), section.heading)
        for field in ("paragraphs", "bullets"):
            for item, text in enumerate(getattr(section, field)):
                add(("sections", index, field, item), text)
    add(("conclusion",), article.conclusion)
    if seo is not None:
        for field in ("title", "description", "og_title", "og_description"):
            add(("seo", field), getattr(seo, field) or "")
        for index, keyword in enumerate(seo.keywords):
            add(("seo", "keywords", index), keyword)
    if len(blocks) > 128 or sum(len(block.text) for block in blocks) > 24_000:
        raise SchemaValidationError("Draft exceeds the bounded evidence review input")
    return blocks


def review_draft(
    query: str, article: GeneratedArticle, seo: SeoResult | None,
    research: ResearchResult, provider: LLMProvider,
) -> ProviderResponse[DraftReview]:
    if settings.draft_reviewer_provider == "groq":
        provider = GroqProvider(
            settings.draft_reviewer_model, json_mode="json_object",
            reasoning_effort=settings.draft_reviewer_reasoning_effort,
        )
    elif settings.draft_reviewer_provider:
        provider = _build_provider(settings.draft_reviewer_provider, settings.draft_reviewer_model)
    else:
        provider = research_provider(provider, review=True)
    if isinstance(provider, GeminiProvider):
        provider = GeminiProvider(
            model=provider.model, compact_schema=True, temperature=0.2,
            thinking_budget=settings.draft_reviewer_thinking_budget,
        )
    try:
        blocks = draft_blocks(article, seo)
        passages = source_passages(research)
        if not passages or any(not group for group in passages.values()):
            raise SchemaValidationError("Original excerpts are required for draft review")
        # Publication and retrieval timestamps are deliberately not evidence of
        # event dates. Only original excerpt text is available as factual support.
        references = [
            {"source_id": source.id, "title": source.title, "url": source.url,
             "passages": passages[source.id]}
            for source in research.summary.sources
        ]
        data = {
            "topic": query,
            "draft_blocks": [{"id": block.id, "field": ".".join(map(str, block.path)),
                              "text": block.text} for block in blocks],
            "references": references,
        }
        # Bind the schema shown to the model to this invocation's real IDs.
        # Local ownership/coverage checks remain mandatory for JSON-object mode.
        passage_enum: dict[str, Any] = {"items": {"type": "string", "enum": [
            key for group in passages.values() for key in group
        ]}}
        id_field = (str, Field(json_schema_extra={"enum": [block.id for block in blocks]}))
        supported_schema = create_model(
            "SupportedReviewBlockForDraft", __base__=BlockReview,
            block_id=id_field, verdict=(Literal["supported"], Field()),
            passage_ids=(list[str], Field(min_length=1, max_length=16,
                                          json_schema_extra=passage_enum)),
        )
        other_schema = create_model(
            "EditorialOrRevisionForDraft", __base__=BlockReview,
            block_id=id_field, verdict=(Literal["editorial", "revise"], Field()),
            passage_ids=(list[str], Field(max_length=16, json_schema_extra=passage_enum)),
        )
        response_schema = cast(type[DraftReview], create_model(
            "ReviewForDraft", __base__=DraftReview,
            blocks=(GenericAlias(list, supported_schema | other_schema),
                    Field(min_length=len(blocks), max_length=len(blocks))),
        ))
        with attempt_budget(30):
            response = provider.generate(
                "draft_review", "v1",
                {"review_json": json.dumps(data, ensure_ascii=False).replace(
                    "<", "\\u003c"
                ).replace(">", "\\u003e")}, response_schema,
            )
        response = replace(response, data=DraftReview.model_validate(response.data.model_dump()))
        validate_review(response.data, blocks, research)
        return response
    except LLMError as exc:
        exc.provider, exc.model = provider.name, provider.model
        raise


def validate_review(
    review: DraftReview, blocks: list[DraftBlock], research: ResearchResult,
) -> None:
    expected = {block.id for block in blocks}
    returned = [block.block_id for block in review.blocks]
    if len(returned) != len(set(returned)) or set(returned) != expected:
        raise SchemaValidationError("Draft review must cover each requested block exactly once")
    passages = {key for group in source_passages(research).values() for key in group}
    originals = {block.id: block.text for block in blocks}
    for block in review.blocks:
        if not set(block.passage_ids).issubset(passages):
            raise SchemaValidationError("Draft review cites a nonexistent evidence passage")
        if block.verdict == "supported" and not block.passage_ids:
            raise SchemaValidationError("Supported factual text requires an evidence passage")
        if block.verdict == "revise":
            if not block.reason.strip() or not block.replacement.strip():
                raise SchemaValidationError("A draft correction requires a reason and text")
            if block.replacement.strip() == originals[block.block_id].strip():
                raise SchemaValidationError("A draft correction must address its finding")
        elif block.replacement:
            raise SchemaValidationError("Clean draft blocks cannot carry hidden corrections")
        checked_text = (block.replacement if block.verdict == "revise"
                        else originals[block.block_id])
        cited = {item for bracket in re.findall(r"\[[^\]\n]*\]", checked_text)
                 for item in re.findall(r"\bS\d+\b", bracket)}
        available = {source.id for source in research.summary.sources}
        if not cited.issubset(available):
            raise SchemaValidationError("Reviewed text cites a source that was not retrieved")
        if block.verdict == "supported" and not cited.issubset({
            passage.split("-", 1)[0] for passage in block.passage_ids
        }):
            raise SchemaValidationError("Text citations disagree with assessed evidence")


def recheck_draft(
    query: str, article: GeneratedArticle, seo: SeoResult | None,
    research: ResearchResult, provider: LLMProvider, *, only_ids: set[str],
) -> ProviderResponse[DraftRecheck]:
    """A compact second opinion: check changed text, never generate more patches."""
    provider = research_provider(provider, review=True)
    if isinstance(provider, GroqProvider):
        provider = GroqProvider(provider.model, json_mode="json_object",
                                reasoning_effort="low", max_output_tokens=1536)
    elif isinstance(provider, GeminiProvider):
        provider = GeminiProvider(model=provider.model, compact_schema=True, temperature=0.2,
                                  thinking_budget=settings.draft_reviewer_thinking_budget)
    try:
        blocks = draft_blocks(article, seo)
        if not only_ids or not only_ids.issubset({block.id for block in blocks}):
            raise SchemaValidationError("Recheck references an unknown draft block")
        blocks = [block for block in blocks if block.id in only_ids]
        passages = source_passages(research)
        if not passages or any(not group for group in passages.values()):
            raise SchemaValidationError("Original excerpts are required for draft recheck")
        data = {"topic": query, "draft_blocks": [
            {"id": block.id, "field": ".".join(map(str, block.path)), "text": block.text}
            for block in blocks
        ], "references": [
            {"source_id": source.id, "title": source.title,
             "passages": passages[source.id]} for source in research.summary.sources
        ]}
        with attempt_budget(20):
            response = provider.generate("draft_recheck", "v1", {
                "review_json": json.dumps(data, ensure_ascii=False).replace(
                    "<", "\\u003c"
                ).replace(">", "\\u003e"),
            }, DraftRecheck)
        checked = response.data.reviewed_block_ids
        issues = [issue.block_id for issue in response.data.issues]
        if len(checked) != len(set(checked)) or set(checked) != only_ids:
            raise SchemaValidationError("Draft recheck must cover every changed block exactly once")
        if len(issues) != len(set(issues)) or not set(issues).issubset(only_ids):
            raise SchemaValidationError("Draft recheck issue references an unsupported block")
        return response
    except LLMError as exc:
        exc.provider, exc.model = provider.name, provider.model
        raise


def apply_review(
    article: GeneratedArticle, seo: SeoResult | None, research: ResearchResult,
    review: DraftReview,
) -> tuple[GeneratedArticle, SeoResult | None, set[str]]:
    blocks = draft_blocks(article, seo)
    validate_review(review, blocks, research)
    paths = {block.id: block.path for block in blocks}
    payload = article.model_dump()
    payload["seo"] = seo.model_dump() if seo else None
    changed: set[str] = set()
    for block in review.blocks:
        if block.verdict != "revise":
            continue
        target: Any = payload
        path = paths[block.block_id]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = block.replacement.strip()
        changed.add(block.block_id)
    try:
        corrected = GeneratedArticle.model_validate(payload)
        corrected_seo = seo
        if seo is not None:
            corrected_seo = SeoResult.model_validate(payload["seo"])
            if validate_generated_seo(SeoCandidate.model_validate(payload["seo"])) is None or any(
                len(getattr(corrected_seo, field) or "") > limit
                for field, limit in (("title", 60), ("description", 160),
                                     ("og_title", 60), ("og_description", 160))
            ):
                raise SchemaValidationError("Evidence correction produced incomplete SEO")
    except ValidationError:
        raise SchemaValidationError("Evidence correction produced an invalid draft") from None
    return corrected, corrected_seo, changed
