"""Deterministic SEO validation and normalization.

LLM-generated SEO is clamped into search-engine-friendly bounds before it is
stored: titles truncated to 60 characters, descriptions to 160, keyword lists
deduplicated and capped. These rules are testable and provider-independent.
"""

from __future__ import annotations

from .schemas import SeoResult

TITLE_MAX = 60
DESCRIPTION_MAX = 160
KEYWORDS_MAX = 12


def _truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Avoid mid-word cuts; fall back to hard cut for single long words.
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:-")


def normalize_seo(seo: SeoResult) -> SeoResult:
    """Clamp an LLM-produced SeoResult into deterministic bounds."""
    keywords: list[str] = []
    for keyword in seo.keywords:
        normalized = " ".join(keyword.split()).lower()
        if normalized and normalized not in keywords:
            keywords.append(normalized)
    keywords = keywords[:KEYWORDS_MAX]
    if not keywords:
        keywords = ["article"]

    return SeoResult(
        title=_truncate(seo.title, TITLE_MAX) or "Untitled",
        description=_truncate(seo.description, DESCRIPTION_MAX) or "-",
        keywords=keywords,
        og_title=_truncate(seo.og_title or seo.title, TITLE_MAX) or None,
        og_description=_truncate(
            seo.og_description or seo.description, DESCRIPTION_MAX
        ) or None,
    )
