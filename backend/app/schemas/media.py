"""Server-owned photo metadata, kept out of every model output schema."""

from __future__ import annotations

import re
from urllib.parse import quote, unquote, urlsplit
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from ..ai.schemas import GeneratedArticle

LICENSES = {
    **{
        f"https://creativecommons.org/licenses/{kind}/{version}/": f"CC {kind.upper()} {version}"
        for kind in ("by", "by-sa")
        for version in ("2.0", "2.5", "3.0", "4.0")
    },
    "https://creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
    "https://creativecommons.org/publicdomain/mark/1.0/": "Public domain",
}


def media_url(value: str, host: str, prefix: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != host
        or not parsed.path.startswith(prefix)
        or parsed.query
        or parsed.fragment
        or "\\" in value
        or any(ord(c) <= 32 or ord(c) == 127 for c in value)
        or ".." in unquote(parsed.path).split("/")
    ):
        raise ValueError("Unsupported photo URL")
    return value


def markdown_label(value: str) -> str:
    return re.sub(r"([\\`*{}\[\]()<>!_])", r"\\\1", value)


class PhotoAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(default="commons", pattern="^commons$")
    source_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=300)
    creator: str = Field(min_length=1, max_length=300)
    source_url: str = Field(max_length=2000)
    preview_url: str = Field(max_length=2000)
    original_url: str = Field(max_length=2000)
    license_name: str = Field(max_length=80)
    license_url: str = Field(max_length=120)
    width: int = Field(ge=1, le=100000)
    height: int = Field(ge=1, le=100000)

    @field_validator("source_url")
    @classmethod
    def source_link(cls, value: str) -> str:
        return media_url(value, "commons.wikimedia.org", "/wiki/File:")

    @field_validator("preview_url", "original_url")
    @classmethod
    def image_link(cls, value: str, info: ValidationInfo) -> str:
        host = "upload.wikimedia.org"
        if info.field_name == "preview_url" and urlsplit(value).netloc == "thumb.wikimedia.org":
            host = "thumb.wikimedia.org"
        value = media_url(value, host, "/wikipedia/commons/")
        if not urlsplit(value).path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            raise ValueError("Only raster photo URLs are supported")
        return value

    @model_validator(mode="after")
    def known_license(self) -> PhotoAsset:
        if LICENSES.get(self.license_url) != self.license_name:
            raise ValueError("Unsupported or mismatched photo license")
        return self


class PhotoSuggestion(PhotoAsset):
    selection_token: str


class ArticlePhoto(PhotoAsset):
    id: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[a-f0-9]{32}$")
    section_id: str | None = Field(default=None, min_length=8, max_length=64)
    alt: str = Field(min_length=1, max_length=300)

    @field_validator("alt")
    @classmethod
    def clean_alt(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Describe the photo for readers who cannot see it")
        return value


class ArticleDocument(GeneratedArticle):
    photos: list[ArticlePhoto] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def photo_placements(self) -> ArticleDocument:
        sections = {section.id for section in self.sections}
        slots = [photo.section_id for photo in self.photos]
        if len(set(slots)) != len(slots) or len({p.id for p in self.photos}) != len(self.photos):
            raise ValueError("Use one photo per position")
        if any(slot is not None and slot not in sections for slot in slots):
            raise ValueError("Photo section no longer exists")
        return self

    def _image_markdown(self, section_id: str | None) -> list[str]:
        lines: list[str] = []
        for photo in self.photos:
            if photo.section_id != section_id:
                continue
            target = quote(photo.preview_url, safe="/:@!$&'+,;=%~_-.")
            source = quote(photo.source_url, safe="/:@!$&'+,;=%~_-.")
            lines += [
                f"![{markdown_label(photo.alt)}]({target})",
                "",
                f"Photo: {markdown_label(photo.title)} — "
                f"[{markdown_label(photo.creator)}]({source}), "
                f"[{photo.license_name}]({photo.license_url}). Wikimedia Commons.",
                "",
            ]
        return lines


class PhotoChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    selection_token: str | None = Field(default=None, max_length=16000)
    section_id: str | None = Field(default=None, min_length=8, max_length=64)
    alt: str = Field(min_length=1, max_length=300)

    @field_validator("alt")
    @classmethod
    def clean_alt(cls, value: str) -> str:
        return ArticlePhoto.clean_alt(value)

    @model_validator(mode="after")
    def one_origin(self) -> PhotoChoice:
        if bool(self.id) == bool(self.selection_token):
            raise ValueError("Choose an existing photo or a search result")
        return self


class SavePhotosRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_version: int = Field(ge=1)
    photos: list[PhotoChoice] = Field(max_length=4)


class PhotoSearchOut(BaseModel):
    query: str
    photos: list[PhotoSuggestion]
