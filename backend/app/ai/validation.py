"""Deterministic SEO validation and normalization.

Generated metadata follows product length targets, not search-engine hard limits.
Descriptions retain complete sentences or use an honest topic-based fallback;
they are never shortened by cutting off a clause. Manual SEO has separate bounds.
"""

from __future__ import annotations

import re

from .schemas import SeoCandidate, SeoResult

TITLE_MAX = 60
DESCRIPTION_MAX = 160
KEYWORDS_MAX = 12
_SENTENCE_ENDINGS = ".!?。！？।॥"  # noqa: RUF001 - multilingual sentence punctuation
_CLOSING_PUNCTUATION = '\"\'”’»)]}'  # noqa: RUF001 - supported closing quotation marks
_ABBREVIATIONS = {
    "a.m.", "co.", "dr.", "e.g.", "etc.", "fig.", "i.e.", "inc.", "jr.", "ltd.",
    "mr.", "mrs.", "ms.", "no.", "p.m.", "ph.d.", "prof.", "sr.", "st.", "u.k.",
    "u.s.", "vs.",
}
_DANGLING_WORDS = {
    "about", "and", "as", "because", "for", "from", "if", "including", "of", "or",
    "than", "that", "to", "whether", "which", "while", "with",
}
_RELATIVE_PREPOSITIONS = {"about", "as", "for", "from", "of", "to", "with"}


def _ends_with_abbreviation(text: str) -> bool:
    """A period in an abbreviation or initial does not establish a sentence end."""
    match = re.search(r"[A-Za-z]+(?:\.[A-Za-z]+)*\.$", text.rstrip(_CLOSING_PUNCTUATION))
    if match is None:
        return False
    last_word = match.group().lower()
    return last_word in _ABBREVIATIONS or re.fullmatch(r"[a-z]\.", last_word) is not None


def _truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Avoid mid-word cuts; fall back to hard cut for single long words.
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:-")


def _has_complete_ending(text: str) -> bool:
    """Reject obvious unfinished endings; this is not a grammar or fact checker."""
    stripped = text.rstrip(_CLOSING_PUNCTUATION)
    if not stripped or stripped.endswith(("...", "…")):
        return False
    if stripped[-1] not in _SENTENCE_ENDINGS:
        return False
    if not any(character.isalpha() for character in stripped):
        return False
    if _ends_with_abbreviation(stripped):
        return False
    words = re.findall(r"[A-Za-z]+", stripped.rstrip(_SENTENCE_ENDINGS))
    if not words or words[-1].lower() not in _DANGLING_WORDS:
        return True
    # A relative clause may legitimately end in a preposition: "what it is for."
    return words[-1].lower() in _RELATIVE_PREPOSITIONS and any(
        word.lower() in {"what", "who", "whom", "where", "which", "how"}
        for word in words[:-1]
    )


def seo_descriptions_need_repair(seo: SeoResult) -> bool:
    """Check both generated descriptions for one bounded provider rewrite.

    Missing Open Graph text inherits the main description. This check flags
    overlength text and obvious unfinished endings; it is not a grammar checker.
    """
    return any(
        len(cleaned := " ".join(text.split())) > DESCRIPTION_MAX
        or not _has_complete_ending(cleaned)
        for text in (seo.description, seo.og_description or seo.description)
    )


def validate_generated_seo(candidate: SeoCandidate | None) -> SeoResult | None:
    """Accept complete generated text without clipping or silently inventing it.

    These deterministic checks cannot establish factual accuracy or good prose.
    A rejected answer gets one provider repair, then a visible review state.
    """
    if candidate is None:
        return None
    title = " ".join((candidate.title or "").split())
    description = " ".join((candidate.description or "").split())
    og_title = " ".join((candidate.og_title or title).split())
    og_description = " ".join((candidate.og_description or description).split())
    keywords = list(dict.fromkeys(" ".join(k.split()).lower() for k in candidate.keywords))
    if (
        not title or len(title) > TITLE_MAX
        or not og_title or len(og_title) > TITLE_MAX
        or not description or len(description) > DESCRIPTION_MAX
        or not _has_complete_ending(description)
        or not og_description or len(og_description) > DESCRIPTION_MAX
        or not _has_complete_ending(og_description)
        or not 5 <= len(keywords) <= KEYWORDS_MAX
        or any(not keyword or len(keyword) > 80 for keyword in keywords)
    ):
        return None
    return SeoResult(
        title=title, description=description, keywords=keywords,
        og_title=og_title, og_description=og_description, review_status="generated",
    )


def fitting_first_sentence(text: str) -> str | None:
    """Return an exact complete first sentence, or nothing; never manufacture prose."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= DESCRIPTION_MAX and _has_complete_ending(cleaned):
        return cleaned
    for match in re.finditer(r'[.!?。！？।॥]+["\'”’)\]}]*', cleaned):  # noqa: RUF001
        end = match.end()
        punctuation = match.group().rstrip(_CLOSING_PUNCTUATION)
        if punctuation[0] in ".!?" and end < len(cleaned) and not cleaned[end].isspace():
            continue
        candidate = cleaned[:end]
        if _ends_with_abbreviation(candidate):
            continue
        return candidate if len(candidate) <= DESCRIPTION_MAX and _has_complete_ending(
            candidate
        ) else None
    return None


def complete_description(text: str, *, fallback_title: str) -> str:
    """Keep a fitting sentence, take its first complete sentence, or use a fallback.

    Terminal punctuation is a conservative completeness signal. It cannot prove
    grammar, language quality, or factual accuracy; those remain model/review work.
    """
    cleaned = " ".join(text.split())
    if len(cleaned) <= DESCRIPTION_MAX and _has_complete_ending(cleaned):
        return cleaned

    # ASCII sentence endings need a following space/end, so Claude 3.5 and
    # searchscribe.ai are not split. CJK/Indic endings may join without spaces.
    for match in re.finditer(r'[.!?。！？।॥]+["\'”’»)\]}]*', cleaned):  # noqa: RUF001
        end = match.end()
        punctuation = match.group().rstrip(_CLOSING_PUNCTUATION)
        if punctuation[0] in ".!?" and end < len(cleaned) and not cleaned[end].isspace():
            continue
        candidate = cleaned[:end]
        if _ends_with_abbreviation(candidate):
            continue
        if len(candidate) <= DESCRIPTION_MAX and _has_complete_ending(candidate):
            return candidate
        break

    topic = _truncate(fallback_title, TITLE_MAX).strip('"\'“”‘’')  # noqa: RUF001
    title_words = fallback_title.split()
    if not topic or not title_words or len(title_words[0]) > TITLE_MAX:
        return "Read this article for an overview of its topic and key points."
    return f"Read “{topic}” for an overview of the topic and its key points."


def normalize_seo(seo: SeoResult, *, fallback_title: str | None = None) -> SeoResult:
    """Normalize generated metadata without turning descriptions into fragments."""
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
        description=complete_description(
            seo.description, fallback_title=fallback_title or seo.title
        ),
        keywords=keywords,
        og_title=_truncate(seo.og_title or seo.title, TITLE_MAX) or None,
        og_description=complete_description(
            seo.og_description or seo.description,
            fallback_title=fallback_title or seo.og_title or seo.title,
        ),
        canonical_url=seo.canonical_url,
        robots=seo.robots,
        review_status=seo.review_status,
    )
