"""Article/generation request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    markdown: str
    html: str
    seo: SeoOut | None = None
    created_at: datetime
    updated_at: datetime


class VersionListItem(BaseModel):
    version: int
    change_type: str
    word_count: int
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
