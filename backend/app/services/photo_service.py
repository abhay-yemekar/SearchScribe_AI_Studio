"""Bounded keyless Commons search and short-lived, account-bound selections."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from html import unescape
from urllib.parse import urlsplit, urlunsplit

import httpx
import nh3
from pydantic import ValidationError

from ..core.config import settings
from ..core.exceptions import BadRequestError, ExternalServiceError, ServiceUnavailableError
from ..schemas.media import LICENSES, PhotoAsset, PhotoSearchOut, PhotoSuggestion

_USER_AGENT = "SearchScribeAI/2.0 (https://github.com/abhay-yemekar/SearchScribe_AI_Studio)"


def _plain(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(
        unescape(
            nh3.clean(
                value[:20000], tags=set(), attributes={}, clean_content_tags={"script", "style"}
            )
        ).split()
    )[:limit]


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def selection_token(photo: PhotoAsset, user_id: int, article_id: int) -> str:
    payload = _encode(
        json.dumps(
            {
                "purpose": "article-photo",
                "user": user_id,
                "article": article_id,
                "expires": int(time.time()) + 1800,
                "photo": photo.model_dump(),
            },
            separators=(",", ":"),
        ).encode()
    )
    signature = hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).digest()
    return payload + "." + _encode(signature)


def selected_photo(token: str, user_id: int, article_id: int) -> PhotoAsset:
    try:
        if len(token) > 16000 or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token):
            raise ValueError
        payload, signature = token.split(".")
        expected = hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode(signature)):
            raise ValueError
        data = json.loads(_decode(payload))
        if (
            data["purpose"] != "article-photo"
            or data["user"] != user_id
            or data["article"] != article_id
            or data["expires"] <= time.time()
        ):
            raise ValueError
        return PhotoAsset.model_validate(data["photo"])
    except (ValueError, TypeError, KeyError, ValidationError):
        raise BadRequestError(
            "This photo selection expired or is invalid. "
            "Remove it and choose a fresh search result.",
            code="INVALID_PHOTO_SELECTION",
        ) from None


def _asset(page: object) -> PhotoAsset | None:
    if not isinstance(page, dict):
        return None
    try:
        info = page["imageinfo"][0]
        if info["mime"] not in {"image/jpeg", "image/png", "image/webp"}:
            return None
        metadata = info["extmetadata"]
        license_url = str(metadata["LicenseUrl"]["value"]).strip()
        if license_url.startswith("//"):
            license_url = "https:" + license_url
        license_url = license_url.replace(
            "http://creativecommons.org/", "https://creativecommons.org/"
        )
        license_url = license_url.rstrip("/") + "/"
        license_name = LICENSES.get(license_url)
        if not license_name or info["width"] < 1200 or info["height"] < 600:
            return None
        # Truncated author attributions can drop required credit. Skip instead.
        creator = _plain(metadata["Artist"]["value"], 301)
        if not creator or len(creator) > 300:
            return None
        return PhotoAsset(
            source_id=page["pageid"],
            title=_plain(page["title"].removeprefix("File:"), 300),
            creator=creator,
            source_url=info["descriptionurl"],
            # Commons adds UTM parameters to thumbnails. Retain its public image
            # path, without carrying tracking parameters into saved exports.
            preview_url=urlunsplit(urlsplit(info.get("thumburl", info["url"]))._replace(query="")),
            original_url=urlunsplit(urlsplit(info["url"])._replace(query="")),
            license_name=license_name,
            license_url=license_url,
            width=info["width"],
            height=info["height"],
        )
    except (KeyError, IndexError, TypeError, AttributeError, ValueError, ValidationError):
        return None


def search_photos(query: str, user_id: int, article_id: int) -> PhotoSearchOut:
    if settings.photo_provider == "disabled":
        raise ServiceUnavailableError(
            "Photo search is disabled for this preview.", code="PHOTO_SEARCH_DISABLED"
        )
    query = " ".join(query.split())
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": query + " filetype:bitmap",
        "gsrnamespace": "6",
        "gsrlimit": "12",
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1280",
        "iiextmetadatafilter": "Artist|LicenseUrl",
    }
    try:
        deadline = time.monotonic() + 12
        with (
            httpx.Client(
                timeout=httpx.Timeout(12, connect=3), trust_env=False, follow_redirects=False
            ) as client,
            client.stream(
                "GET",
                "https://commons.wikimedia.org/w/api.php",
                params=params,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            ) as response,
        ):
            if response.status_code != 200 or "application/json" not in response.headers.get(
                "content-type", ""
            ):
                raise ValueError
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 1_000_000 or time.monotonic() > deadline:
                    raise ValueError
        payload = json.loads(body)
        if not isinstance(payload, dict) or "error" in payload:
            raise ValueError
        query_result = payload.get("query", {})
        if not isinstance(query_result, dict):
            raise ValueError
        pages = query_result.get("pages", [])
        if not isinstance(pages, list):
            raise ValueError
    except (httpx.HTTPError, ValueError, TypeError):
        raise ExternalServiceError(
            "Photo search is temporarily unavailable. Your article is saved.",
            code="PHOTO_SEARCH_UNAVAILABLE",
        ) from None
    photos = [photo for page in pages[:12] if (photo := _asset(page)) is not None]
    # Prefer actual 4K originals. Smaller previews keep browsing lightweight.
    photos.sort(
        key=lambda p: (p.width >= 3840 and p.height >= 2160, p.width * p.height), reverse=True
    )
    return PhotoSearchOut(
        query=query,
        photos=[
            PhotoSuggestion(
                **photo.model_dump(), selection_token=selection_token(photo, user_id, article_id)
            )
            for photo in photos[:6]
        ],
    )
