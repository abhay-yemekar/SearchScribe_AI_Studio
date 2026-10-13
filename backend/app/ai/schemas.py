"""Structured LLM output schemas. All provider answers are validated against these."""

from __future__ import annotations

import ipaddress
import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import Literal
from urllib.parse import quote, urlsplit
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class ResearchSource(BaseModel):
    id: str = Field(pattern=r"^S[1-6]$")
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(max_length=1000)
    published_at: str | None = None

    @field_validator("url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        if any(ord(c) <= 32 or ord(c) == 127 for c in value) or "\\" in value:
            raise ValueError("Source URL contains unsafe characters")
        parsed = urlsplit(value)
        host = (parsed.hostname or "").rstrip(".").lower()
        try:
            port = parsed.port
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError("Source URL must use a public DNS hostname")
        try:
            port = parsed.port
        except ValueError:
            raise ValueError("Source URL has an invalid port") from None
        if (
            parsed.scheme != "https"
            or port not in {None, 443}
            or parsed.username is not None
            or parsed.password is not None
            or "." not in host
            or host.endswith((".localhost", ".local", ".internal", ".lan", ".home", ".test"))
            or not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", host)
            or host.rsplit(".", 1)[-1].isdigit()
            or any(label.startswith("-") or label.endswith("-") for label in host.split("."))
        ):
            raise ValueError("Source must be a public HTTPS URL without credentials")
        return value

    @field_validator("published_at", mode="before")
    @classmethod
    def normalize_reported_date(cls, value: object) -> str | None:
        if not isinstance(value, str) or len(value) > 100:
            return None
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            pass
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                moment = parsedate_to_datetime(value)
            except (ValueError, TypeError, OverflowError):
                return None
        return moment.isoformat() if moment.tzinfo else moment.date().isoformat()


class ResearchSummary(BaseModel):
    status: Literal["unresearched", "sources_retrieved"] = "unresearched"
    retrieved_at: str | None = None
    sources: list[ResearchSource] = Field(default_factory=list, max_length=6)


class ArticleSection(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex, min_length=8, max_length=64)
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
    research: ResearchSummary = Field(default_factory=ResearchSummary)

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
        if self.research.status == "sources_retrieved":
            lines += [
                "",
                "## Sources",
                "",
                f"Sources retrieved: {self.research.retrieved_at}. "
                "Review claims before publishing; retrieved sources "
                "are not a fact-check guarantee.",
            ]
            for source in self.research.sources:
                label = re.sub(r"([\\`*{}\[\]()<>!_])", r"\\\1", source.title)
                target = quote(source.url, safe="/:?#[]@!$&'+,;=%~_-.")
                reported_date = (
                    f" — reported publication/update: {source.published_at} (provider estimate)"
                    if source.published_at else ""
                )
                lines.append(f"- [{source.id}] [{label}]({target}){reported_date}")
        else:
            lines += [
                "",
                "Unresearched draft: no live sources were retrieved. "
                "Verify factual and time-sensitive claims before publishing.",
            ]
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
