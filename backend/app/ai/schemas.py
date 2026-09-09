"""Structured LLM output schemas. All provider answers are validated against these."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ArticleSection(BaseModel):
    heading: str = Field(min_length=1, max_length=300)
    paragraphs: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)

    @field_validator("heading")
    @classmethod
    def strip_heading(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("heading cannot be blank")
        return value


class GeneratedArticle(BaseModel):
    """Canonical article representation.

    Markdown and HTML are derived deterministically from this structure —
    the LLM never produces raw HTML.
    """

    title: str = Field(min_length=1, max_length=200)
    introduction: str = Field(min_length=1)
    sections: list[ArticleSection] = Field(min_length=1, max_length=12)
    conclusion: str = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title cannot be blank")
        return value

    def to_markdown(self) -> str:
        """Deterministic Markdown rendering (used for storage and display)."""
        lines: list[str] = [f"# {self.title}", "", self.introduction, ""]
        for section in self.sections:
            lines += [f"## {section.heading}", ""]
            lines += [paragraph + "\n" for paragraph in section.paragraphs]
            if section.bullets:
                lines += [f"- {bullet}" for bullet in section.bullets]
                lines.append("")
        lines += ["## Conclusion", "", self.conclusion]
        return "\n".join(lines).strip()

    @property
    def word_count(self) -> int:
        parts = [self.introduction, self.conclusion]
        for section in self.sections:
            parts.append(section.heading)
            parts.extend(section.paragraphs)
            parts.extend(section.bullets)
        return sum(len(p.split()) for p in parts)


class SeoResult(BaseModel):
    """SEO metadata for an article. Normalized by validate_seo() before use."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=400)
    keywords: list[str] = Field(min_length=1, max_length=15)
    og_title: str | None = None
    og_description: str | None = None
    canonical_url: str | None = None
    robots: str = "index, follow"

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, value: list[str]) -> list[str]:
        cleaned = [k.strip() for k in value if k and k.strip()]
        if not cleaned:
            raise ValueError("at least one keyword required")
        return cleaned
