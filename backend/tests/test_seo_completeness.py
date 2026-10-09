"""Generated SEO retains complete thoughts; manual export remains lossless."""

from __future__ import annotations

import pytest

from app.ai.prompts import render_prompt
from app.ai.renderer import _fallback_seo, render_article_html
from app.ai.schemas import ArticleSection, GeneratedArticle, SeoResult
from app.ai.validation import complete_description, normalize_seo, seo_descriptions_need_repair


def metadata(description: str, **kwargs: str) -> SeoResult:
    return SeoResult(
        title="Claude 3.5 guide", description=description, keywords=["Claude"], **kwargs
    )


def article(introduction: str) -> GeneratedArticle:
    return GeneratedArticle(
        title="Claude 3.5 guide", introduction=introduction,
        sections=[ArticleSection(heading="Overview", paragraphs=["An overview."])],
        conclusion="Read the official documentation.",
    )


def test_valid_generated_metadata_and_publication_fields_are_preserved() -> None:
    description = "Learn how Claude 3.5 works, with an overview of the article's main points."
    source = metadata(description, canonical_url="https://example.com/guide", robots="noindex")
    result = normalize_seo(source)
    assert result.description == description
    assert result.og_description == description
    assert result.canonical_url == source.canonical_url
    assert result.robots == "noindex"
    assert not seo_descriptions_need_repair(source)


def test_long_single_sentence_becomes_a_topic_specific_complete_fallback() -> None:
    source = metadata("Explore " + "its practical capabilities and applications " * 5 + "today.")
    result = normalize_seo(source)
    assert "Claude 3.5 guide" in result.description
    assert result.description == (
        "Read “Claude 3.5 guide” for an overview of the topic and its key points."
    )
    assert len(result.description) <= 160
    assert seo_descriptions_need_repair(source)


def test_first_complete_sentence_is_used_without_cutting_the_following_clause() -> None:
    first = "Claude 3.5 supports several writing workflows."
    result = normalize_seo(metadata(first + " Learn about " + "different tasks " * 14 + "today."))
    assert result.description == first


def test_decimal_model_version_and_domain_are_not_sentence_boundaries() -> None:
    first = "Explore Claude 3.5 and its usage at docs.example.com."
    result = normalize_seo(metadata(first + " Additional context " * 10 + "follows."))
    assert result.description == first


def test_common_abbreviation_does_not_create_an_incomplete_first_sentence() -> None:
    first = "Dr. Rao explains how these models work."
    result = normalize_seo(metadata(first + " Further details " * 13 + "follow."))
    assert result.description == first


@pytest.mark.parametrize("first", [
    "Read Dr. A. Rao's guide to Claude 3.5.",
    'Read "Dr. Rao explains the model."',
    "Learn how models support U.S. teams.",
    "Explore several examples, e.g. drafting and editing.",
])
def test_abbreviations_and_initials_are_retained_in_the_first_complete_sentence(first: str) -> None:
    result = normalize_seo(metadata(first + " Additional details " * 10 + "follow."))
    assert result.description == first


@pytest.mark.parametrize("ending", ["including", "and.", "with...", "for", "…", "Dr.", "e.g."])
def test_obvious_unfinished_endings_are_not_saved_as_complete_descriptions(ending: str) -> None:
    source = metadata("Explore the article's main points " + ending)
    result = normalize_seo(source)
    assert result.description.endswith("key points.")
    assert seo_descriptions_need_repair(source)


@pytest.mark.parametrize("description", [".", "!!!", "3.5."])
def test_punctuation_or_numbers_alone_do_not_count_as_complete_descriptions(
    description: str,
) -> None:
    source = metadata(description)
    assert seo_descriptions_need_repair(source)
    assert normalize_seo(source).description.endswith("key points.")


@pytest.mark.parametrize("description", [
    "इस लेख में मॉडल की मुख्य जानकारी और उपयोग पढ़ें।",
    "この記事ではモデルの概要と使い方を紹介します。",
    "Read the article's main points!",
    'Read the article "Claude 3.5 guide."',
    "Find out what this article is about.",
    "Who is this guide for?",
])
def test_fitting_multilingual_sentence_punctuation_is_preserved(description: str) -> None:
    source = metadata(description)
    assert normalize_seo(source).description == description
    assert not seo_descriptions_need_repair(source)


def test_valid_description_at_the_target_is_preserved() -> None:
    description = "Read " + "a" * 154 + "."
    assert len(description) == 160
    assert normalize_seo(metadata(description)).description == description


def test_short_complete_first_sentence_survives_a_later_incomplete_clause() -> None:
    source = metadata("Read the model overview. Learn about")
    assert seo_descriptions_need_repair(source)
    assert normalize_seo(source).description == "Read the model overview."


def test_long_first_sentence_does_not_select_an_unrelated_later_sentence() -> None:
    description = "Learn " + "about the model " * 11 + "here. Read more."
    result = normalize_seo(metadata(description))
    assert result.description.endswith("key points.")
    assert result.description != "Read more."


def test_generated_titles_and_keyword_lists_follow_product_bounds() -> None:
    source = SeoResult(
        title="Claude model guide " * 6,
        description="Read this complete overview.",
        og_title="Claude model sharing guide " * 6,
        keywords=["Claude", "claude", " Models ", *[f"topic {n}" for n in range(12)]],
    )
    result = normalize_seo(source)
    assert len(result.title) <= 60
    assert result.og_title is not None and len(result.og_title) <= 60
    assert not result.title.endswith("Clau")
    assert result.keywords[:2] == ["claude", "models"]
    assert len(result.keywords) == 12


@pytest.mark.parametrize("title", ["", " ", "x" * 61])
def test_fallback_with_no_fitting_topic_remains_a_complete_sentence(title: str) -> None:
    description = complete_description("An incomplete introduction", fallback_title=title)
    assert description == "Read this article for an overview of its topic and key points."
    assert len(description) <= 160


def test_fallback_uses_the_article_title_instead_of_an_unusable_generated_title() -> None:
    result = normalize_seo(
        metadata("An incomplete description"), fallback_title="The actual article topic"
    )
    assert "The actual article topic" in result.description
    assert "Claude" not in result.description


def test_open_graph_description_is_checked_and_repaired_separately() -> None:
    source = metadata(
        "Read the complete overview.", og_description="Learn about " + "features " * 30
    )
    assert seo_descriptions_need_repair(source)
    result = normalize_seo(source)
    assert result.description == source.description
    assert result.og_description is not None
    assert len(result.og_description) <= 160
    assert result.og_description.endswith("key points.")


def test_renderer_fallback_handles_intro_over_schema_limit_without_clipping() -> None:
    result = _fallback_seo(article("Explore " + "practical model capabilities " * 25 + "today."))
    assert len(result.description) <= 160
    assert "Claude 3.5 guide" in result.description
    assert result.description.endswith("key points.")


def test_manual_seo_export_retains_a_description_above_generation_target() -> None:
    description = "A deliberately detailed description for editors. " * 6
    html = render_article_html(article("An overview."), metadata(description))
    assert len(description) > 160
    assert f'<meta name="description" content="{description}">' in html


def test_seo_prompt_v2_supports_normal_generation_and_one_repair_instruction() -> None:
    variables = {"title": "Claude 3.5 guide", "introduction": "An overview."}
    normal_prompt = render_prompt("seo_generation", "v2", variables)
    assert "at most 60 characters" in normal_prompt
    assert "Rewrite required:" not in normal_prompt
    repair_prompt = render_prompt(
        "seo_generation", "v2", {**variables, "repair": "Write two complete short descriptions."}
    )
    assert "Rewrite required:\nWrite two complete short descriptions." in repair_prompt
