"""Article/generation request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..ai.schemas import GeneratedArticle
from ..core.config import settings


class GenerateArticleRequest(BaseModel):
    query: str = Field(min_length=3, max_length=settings.max_query_length)

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class RewriteRequest(BaseModel):
    style: str = Field(min_length=1, max_length=30)


class UpdateArticleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SeoInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=400)
    keywords: list[str] = Field(min_length=1, max_length=15)
    og_title: str | None = Field(default=None, max_length=200)
    og_description: str | None = Field(default=None, max_length=400)
    canonical_url: str | None = Field(default=None, max_length=500)
    robots: Literal["index, follow", "noindex, follow"] = "index, follow"

    @field_validator("canonical_url")
    @classmethod
    def validate_canonical_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("canonical_url must be an absolute HTTP(S) URL")
        return value


class SaveArticleRequest(BaseModel):
    base_version: int = Field(ge=1)
    content: GeneratedArticle
    seo: SeoInput

    @model_validator(mode="after")
    def validate_content_size(self) -> SaveArticleRequest:
        if len(self.content.to_markdown()) > settings.max_rewrite_input_length:
            raise ValueError("article content is too long")
        return self


class SeoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    description: str
    keywords: list[str]
    og_title: str | None = None
    og_description: str | None = None
    canonical_url: str | None = None
    robots: str = "index, follow"


class ArticleListItem(BaseModel):
    id: int
    title: str
    query: str
    status: str
    current_version: int
    created_at: datetime
    updated_at: datetime


class ArticleListOut(BaseModel):
    items: list[ArticleListItem]
    next_cursor: str | None = None


class ArticleDetailOut(BaseModel):
    id: int
    title: str
    query: str
    status: str
    current_version: int
    content: GeneratedArticle
    markdown: str
    html: str
    seo: SeoOut | None = None
    created_at: datetime
    updated_at: datetime


class VersionListItem(BaseModel):
    version: int
    change_type: str
    word_count: int
    complete_snapshot: bool
    created_at: datetime


class VersionListOut(BaseModel):
    items: list[VersionListItem]


class VersionDetailOut(BaseModel):
    version: int
    change_type: str
    markdown: str
    created_at: datetime


class RewriteStyleOut(BaseModel):
    key: str
    label: str


class RewriteStylesOut(BaseModel):
    styles: list[RewriteStyleOut]
