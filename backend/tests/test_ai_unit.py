"""Unit tests for the AI layer: providers, retry, renderer, sanitizer, prompts."""

from __future__ import annotations

import pytest

from app.ai.base import (
    PermanentLLMError,
    ProviderResponse,
    TransientLLMError,
    call_with_retry,
)
from app.ai.factory import get_provider
from app.ai.mock import MockProvider
from app.ai.prompts import UnknownPromptError, render_prompt
from app.ai.renderer import render_article_html
from app.ai.sanitizer import sanitize_html
from app.ai.schemas import ArticleSection, GeneratedArticle, SeoResult
from app.ai.styles import REWRITE_STYLES, get_style
from app.ai.validation import normalize_seo


@pytest.fixture
def provider() -> MockProvider:
    return MockProvider()


def test_mock_provider_generates_validated_article(provider: MockProvider) -> None:
    response = provider.generate(
        "article_generation", "v1", {"topic": "Urban Gardening"}, GeneratedArticle
    )
    article = response.data
    assert isinstance(article, GeneratedArticle)
    assert "Urban Gardening" in article.title
    assert article.sections
    assert response.provider == "mock"
    assert response.input_tokens is not None


def test_mock_provider_generates_seo(provider: MockProvider) -> None:
    response = provider.generate(
        "seo_generation",
        "v1",
        {"title": "Urban Gardening", "introduction": "Grow food in cities."},
        SeoResult,
    )
    assert isinstance(response.data, SeoResult)
    assert response.data.keywords


def test_generated_article_markdown_is_deterministic() -> None:
    article = GeneratedArticle(
        title="T",
        introduction="I",
        sections=[ArticleSection(heading="H", paragraphs=["P1"], bullets=["B1"])],
        conclusion="C",
    )
    md = article.to_markdown()
    assert md.startswith("# T")
    assert "## H" in md
    assert "- B1" in md
    assert "## Conclusion" in md
    assert article.to_markdown() == md


def test_retry_recovers_from_transient_failures(provider: MockProvider) -> None:
    provider.transient_failures_remaining = 2

    result = call_with_retry(
        lambda: provider.generate(
            "article_generation", "v1", {"topic": "X"}, GeneratedArticle
        ),
        max_retries=3,
        base_delay_seconds=0,
    )
    assert isinstance(result, ProviderResponse)


def test_retry_gives_up_after_limit(provider: MockProvider) -> None:
    provider.transient_failures_remaining = 99

    with pytest.raises(TransientLLMError):
        call_with_retry(
            lambda: provider.generate(
                "article_generation", "v1", {"topic": "X"}, GeneratedArticle
            ),
            max_retries=2,
            base_delay_seconds=0,
        )


def test_permanent_errors_are_not_retried(provider: MockProvider) -> None:
    provider.permanent_failure = True
    calls = []

    def call():
        calls.append(1)
        return provider.generate(
            "article_generation", "v1", {"topic": "X"}, GeneratedArticle
        )

    with pytest.raises(PermanentLLMError):
        call_with_retry(call, max_retries=5, base_delay_seconds=0)
    assert len(calls) == 1


def test_schema_rejects_empty_sections() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        GeneratedArticle(
            title="T", introduction="I", sections=[], conclusion="C"
        )


def test_renderer_escapes_malicious_content() -> None:
    article = GeneratedArticle(
        title="Safe <script>alert(1)</script>",
        introduction='Intro with "quotes" & <img src=x onerror=alert(1)>',
        sections=[
            ArticleSection(
                heading="<b>bold</b>",
                paragraphs=["<iframe src='https://evil.example'></iframe>"],
                bullets=["<a href='javascript:alert(1)'>link</a>"],
            )
        ],
        conclusion="done",
    )
    html = render_article_html(article)

    # Malicious markup survives only as escaped text, never as live tags.
    assert "<script>" not in html
    assert "<img" not in html
    assert "<iframe" not in html
    assert "<a href" not in html
    assert "&lt;script&gt;" in html  # escaped, not stripped


def test_renderer_includes_seo_metadata() -> None:
    article = GeneratedArticle(
        title="T", introduction="I",
        sections=[ArticleSection(heading="H", paragraphs=["P"])], conclusion="C",
    )
    seo = SeoResult(
        title="SEO Title", description="SEO description", keywords=["a", "b"]
    )
    html = render_article_html(article, seo)
    assert '<meta name="description" content="SEO description">' in html
    assert 'content="a, b"' in html
    assert "<title>SEO Title</title>" in html


def test_sanitizer_strips_scripts_and_event_handlers() -> None:
    dirty = (
        '<p onclick="alert(1)">hi</p>'
        '<script>alert(2)</script>'
        '<a href="javascript:alert(3)">x</a>'
        '<iframe src="https://evil.example"></iframe>'
    )
    clean = sanitize_html(dirty)
    assert "<script" not in clean
    assert "javascript:" not in clean
    assert "onclick" not in clean
    assert "<iframe" not in clean


def test_sanitizer_keeps_document_and_content_tags() -> None:
    html = render_article_html(
        GeneratedArticle(
            title="T", introduction="I",
            sections=[ArticleSection(heading="H", paragraphs=["P"])], conclusion="C",
        )
    )
    sanitized = sanitize_html(html)
    assert "<article>" in sanitized
    assert "<section>" in sanitized
    assert 'name="description"' in sanitized


def test_prompt_rendering_substitutes_variables() -> None:
    rendered = render_prompt(
        "article_generation", "v1", {"topic": "Night Photography"}
    )
    assert "Night Photography" in rendered
    assert "{{" not in rendered


def test_prompt_rendering_rejects_unknown_variables() -> None:
    from jinja2 import UndefinedError

    with pytest.raises(UndefinedError):
        render_prompt("article_generation", "v1", {})


def test_unknown_prompt_raises() -> None:
    with pytest.raises(UnknownPromptError):
        render_prompt("nonexistent", "v9", {"topic": "x"})


def test_rewrite_styles_registry() -> None:
    assert "genz" in REWRITE_STYLES
    assert "professional" in REWRITE_STYLES
    assert get_style("genz")["label"]
    with pytest.raises(ValueError):
        get_style("nope")


def test_normalize_seo_clamps_lengths_and_dedupes() -> None:
    seo = SeoResult(
        title="A very long title " * 8,   # 144 chars: valid for schema, over SEO limit
        description="word " * 50,          # 250 chars: valid for schema, over SEO limit
        keywords=["SEO", "seo", " Marketing ", "", "a", "b", "c"],
        og_title=None,
        og_description=None,
    )
    result = normalize_seo(seo)
    assert len(result.title) <= 60
    assert len(result.description) <= 160
    assert "seo" in result.keywords
    assert result.keywords.count("seo") == 1
    assert result.og_title is not None


def test_factory_returns_configured_provider() -> None:
    provider = get_provider()
    assert provider.name == "mock"  # tests run with AI_PROVIDER=mock
