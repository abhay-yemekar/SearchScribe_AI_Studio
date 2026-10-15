"""Evaluator isolation and scoring; fake transports do not measure model accuracy."""

import json
import subprocess
import sys

import pytest

from app.ai.base import ProviderResponse, TransientLLMError
from app.ai.draft_review import BlockReview, DraftRecheck, DraftReview, draft_blocks
from app.core.config import settings
from scripts import evaluate_evidence as evaluation


def test_corpus_contains_unsupported_and_clean_controls():
    cases = evaluation.load_cases()
    assert len(cases) == 12 and len({case["id"] for case in cases}) == 12
    assert {case["expected"] for case in cases} == {"revise", "supported", "editorial"}
    assert any("नील" in case["claim"] for case in cases)


@pytest.mark.parametrize("fault", ["duplicate", "oversized", "invalid-label"])
def test_invalid_corpus_refused(tmp_path, fault):
    cases = evaluation.load_cases()[:1]
    if fault == "duplicate":
        cases *= 2
    elif fault == "oversized":
        cases[0]["passage"] = "x" * 4001
    else:
        cases[0]["expected"] = "probably-true"
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"version": 1, "cases": cases}), encoding="utf-8")
    with pytest.raises(ValueError):
        evaluation.load_cases(path)


@pytest.mark.parametrize("mode", ["correct", "missed", "false-positive", "failure", "rejected"])
def test_real_scoring_and_recheck_with_no_database_or_search(monkeypatch, mode):
    import app.ai.draft_review as editor
    import app.ai.factory as factory

    cases = evaluation.load_cases()
    case = cases[8] if mode == "false-positive" else cases[0]
    initial_model = settings.draft_reviewer_model
    calls = []

    def review(query, article, seo, research, provider):
        calls.append("review")
        assert settings.database_url == "sqlite://" and not settings.ai_fallback_provider
        assert settings.draft_reviewer_model == "fixture-model"
        if mode == "failure":
            raise TransientLLMError("private provider body must never appear")
        blocks = [BlockReview(
            block_id=block.id, verdict="editorial", passage_ids=[],
            reason="Neutral fixture label.", replacement="",
        ) for block in draft_blocks(article, None)]
        target = blocks[1]
        target.verdict = "supported" if mode == "missed" else "revise"
        target.passage_ids = ["S1-P1"]
        if target.verdict == "revise":
            target.replacement = "North Studio announced a research hub. [S1]"
        return ProviderResponse(DraftReview(blocks=blocks), "groq", "fixture-model",
                                1, 1, 1, "draft_review", "v2")

    def recheck(*args, **kwargs):
        calls.append("recheck")
        return ProviderResponse(DraftRecheck(
            reviewed_block_ids=sorted(kwargs["only_ids"]), issues=(
                [{"block_id": "D2", "reason": "Still unsupported."}] if mode == "rejected" else []
            ),
        ), "groq", "fixture-model", 1, 1, 1, "draft_recheck", "v2")

    def forbidden(*args, **kwargs):
        pytest.fail("The isolated evidence evaluator opened a database or performed search")

    monkeypatch.setattr("sqlalchemy.create_engine", forbidden)
    monkeypatch.setattr("app.ai.research.retrieve_sources", forbidden)
    monkeypatch.setattr(factory, "_build_provider", lambda *args: object())
    monkeypatch.setattr(editor, "review_draft", review)
    monkeypatch.setattr(editor, "recheck_draft", recheck)
    result = evaluation.run_evaluation([case], provider="groq", model="fixture-model")
    assert result["all_cases_passed"] is (mode == "correct")
    assert not result["database_access"] and result["search_calls"] == 0
    assert settings.draft_reviewer_model == initial_model
    assert "private provider body" not in json.dumps(result)
    if mode in {"correct", "false-positive", "rejected"}:
        assert calls == ["review", "recheck"]
    else:
        assert calls == ["review"]
    if mode == "rejected":
        assert result["label_matches"] == 1 and result["status_counts"] == {"recheck_rejected": 1}


def test_dry_run_does_not_import_app_or_require_secrets():
    code = (
        "import sys; from scripts.evaluate_evidence import main; "
        "main(['--ids', 'model-specific-controls']); "
        "assert not any(x == 'app' or x.startswith('app.') for x in sys.modules)"
    )
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], cwd=evaluation.BACKEND_ROOT,
        capture_output=True, text=True, timeout=15, check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["dry_run"] and payload["external_calls"] == 0
    assert len(payload["cases"]) == 1
