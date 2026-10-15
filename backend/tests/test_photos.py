"""Photo ownership, bounded external input, snapshots, and export integrity."""

from __future__ import annotations

import copy
import json
from html.parser import HTMLParser

import httpx
import pytest
from conftest import auth_headers, generate_article, register_user
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai.schemas import GeneratedArticle, GeneratedArticleWithSeo
from app.core.config import settings
from app.core.exceptions import BadRequestError, ExternalServiceError
from app.schemas.media import PhotoAsset
from app.services import photo_service


@pytest.fixture
def asset() -> PhotoAsset:
    return PhotoAsset(
        source_id=123,
        title="Backwaters.jpg",
        creator="Photo Author",
        source_url="https://commons.wikimedia.org/wiki/File:Backwaters.jpg",
        preview_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Backwaters.jpg/1280px-Backwaters.jpg",
        original_url="https://upload.wikimedia.org/wikipedia/commons/a/ab/Backwaters.jpg",
        license_name="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        width=4032,
        height=2688,
    )


def add_photo(client, owner, detail, asset, *, section_id=None):
    token = photo_service.selection_token(asset, owner["user"]["id"], detail["id"])
    response = client.put(
        f"/api/v1/articles/{detail['id']}/photos",
        headers=auth_headers(owner["access_token"]),
        json={
            "base_version": detail["current_version"],
            "photos": [
                {
                    "selection_token": token,
                    "alt": "A quiet canal & palm trees",
                    "section_id": section_id,
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_photo_snapshot_exports_duplicate_restore_and_remove(client: TestClient, asset):
    owner = register_user(client, email="photos@example.com")
    headers = auth_headers(owner["access_token"])
    original = generate_article(client, owner["access_token"])
    detail = add_photo(client, owner, original, asset)
    assert detail["current_version"] == 2
    versions = client.get(f"/api/v1/articles/{detail['id']}/versions", headers=headers).json()
    assert len({version["word_count"] for version in versions["items"]}) == 1
    assert detail["seo"] == original["seo"]
    photo = detail["content"]["photos"][0]
    assert photo["creator"] == asset.creator
    assert photo["width"] == 4032
    assert "![A quiet canal & palm trees]" in detail["markdown"]
    assert asset.source_url in detail["markdown"] and asset.license_url in detail["markdown"]
    assert '<img src="' + asset.preview_url in detail["html"]
    assert "<figcaption>" in detail["html"] and "CC BY 4.0" in detail["html"]
    assert "A quiet canal &amp; palm trees" in detail["html"]
    duplicate = client.post(f"/api/v1/articles/{detail['id']}/duplicate", headers=headers).json()
    assert duplicate["content"]["photos"] == [photo]
    removed = client.put(
        f"/api/v1/articles/{detail['id']}/photos",
        headers=headers,
        json={"base_version": 2, "photos": []},
    ).json()
    assert removed["content"]["photos"] == []
    restored = client.post(
        f"/api/v1/articles/{detail['id']}/versions/2/restore", headers=headers
    ).json()
    assert restored["content"]["photos"] == [photo]
    old = client.get(f"/api/v1/articles/{detail['id']}/versions/2", headers=headers).json()
    assert asset.license_url in old["markdown"]


def test_photo_selection_is_bound_to_owner_article_expiry_and_signature(asset, monkeypatch):
    token = photo_service.selection_token(asset, 3, 7)
    assert photo_service.selected_photo(token, 3, 7) == asset
    for user, article, value in ((4, 7, token), (3, 8, token), (3, 7, token + "tamper")):
        with pytest.raises(BadRequestError):
            photo_service.selected_photo(value, user, article)
    original_time = photo_service.time.time()
    monkeypatch.setattr(photo_service.time, "time", lambda: original_time + 1801)
    with pytest.raises(BadRequestError):
        photo_service.selected_photo(token, 3, 7)


def test_photo_api_checks_ownership_before_search_and_cannot_reuse_selection(
    client, asset, monkeypatch
):
    owner = register_user(client, email="photo-owner@example.com")
    other = register_user(client, email="photo-other@example.com")
    detail = generate_article(client, owner["access_token"])

    def unexpected(*args):
        raise AssertionError("External search must not run for another user's article")

    monkeypatch.setattr("app.api.v1.articles.search_photos", unexpected)
    headers = auth_headers(other["access_token"])
    assert (
        client.get(
            f"/api/v1/articles/{detail['id']}/photos?query=canal", headers=headers
        ).status_code
        == 404
    )
    token = photo_service.selection_token(asset, other["user"]["id"], detail["id"])
    response = client.put(
        f"/api/v1/articles/{detail['id']}/photos",
        headers=auth_headers(owner["access_token"]),
        json={"base_version": 1, "photos": [{"selection_token": token, "alt": "Canal"}]},
    )
    assert response.status_code == 400
    assert (
        client.get(
            f"/api/v1/articles/{detail['id']}", headers=auth_headers(owner["access_token"])
        ).json()["current_version"]
        == 1
    )


def test_legacy_text_edits_preserve_server_owned_media(client, asset):
    owner = register_user(client, email="photo-edit@example.com")
    headers = auth_headers(owner["access_token"])
    detail = add_photo(client, owner, generate_article(client, owner["access_token"]), asset)
    content = copy.deepcopy(detail["content"])
    content["photos"] = []  # Old or modified clients cannot drop server-owned credits.
    content["introduction"] = "An edited introduction."
    response = client.put(
        f"/api/v1/articles/{detail['id']}/content",
        headers=headers,
        json={"base_version": 2, "content": content, "seo": detail["seo"]},
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["content"]["photos"] == detail["content"]["photos"]
    stale = client.put(
        f"/api/v1/articles/{detail['id']}/photos",
        headers=headers,
        json={"base_version": 2, "photos": []},
    )
    assert stale.status_code == 409


def test_alt_edit_placement_and_rewrite_retain_credits(client, asset):
    owner = register_user(client, email="photo-rewrite@example.com")
    headers = auth_headers(owner["access_token"])
    original = generate_article(client, owner["access_token"])
    section_id = original["content"]["sections"][0]["id"]
    detail = add_photo(client, owner, original, asset, section_id=section_id)
    photo = detail["content"]["photos"][0]
    edit = client.put(
        f"/api/v1/articles/{detail['id']}/photos",
        headers=headers,
        json={
            "base_version": 2,
            "photos": [
                {
                    "id": photo["id"],
                    "alt": "Canal <script>alert(1)</script>",
                    "section_id": section_id,
                }
            ],
        },
    )
    assert edit.status_code == 200

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags: list[str] = []

        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)
            if tag == "img":
                assert "onerror" not in dict(attrs)
                assert dict(attrs)["alt"] == "Canal <script>alert(1)</script>"

    parsed = Elements()
    parsed.feed(edit.json()["html"])
    assert "script" not in parsed.tags
    rewritten = client.post(
        f"/api/v1/articles/{detail['id']}/rewrite", headers=headers, json={"style": "genz"}
    )
    assert rewritten.status_code == 200, rewritten.text
    assert rewritten.json()["content"]["photos"] == edit.json()["content"]["photos"]


def test_invalid_position_and_whitespace_alt_do_not_write_version(client, asset):
    owner = register_user(client, email="photo-invalid@example.com")
    detail = generate_article(client, owner["access_token"])
    headers = auth_headers(owner["access_token"])
    token = photo_service.selection_token(asset, owner["user"]["id"], detail["id"])
    for entry, status in (
        ({"selection_token": token, "alt": "   "}, 422),
        ({"selection_token": token, "alt": "Canal", "section_id": "missingsection"}, 400),
    ):
        response = client.put(
            f"/api/v1/articles/{detail['id']}/photos",
            headers=headers,
            json={"base_version": 1, "photos": [entry]},
        )
        assert response.status_code == status, response.text
    assert (
        client.get(f"/api/v1/articles/{detail['id']}", headers=headers).json()["current_version"]
        == 1
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("preview_url", "https://evil.example/photo.jpg"),
        ("original_url", "https://upload.wikimedia.org/wikipedia/commons/x.svg"),
        ("source_url", "javascript:alert(1)"),
        ("license_name", "No attribution required"),
    ],
)
def test_untrusted_media_urls_and_forged_licenses_rejected(asset, field, value):
    with pytest.raises(ValidationError):
        PhotoAsset.model_validate({**asset.model_dump(), field: value})


def test_model_wire_schemas_cannot_generate_photos():
    for schema in (GeneratedArticle, GeneratedArticleWithSeo):
        assert "photos" not in schema.model_json_schema()["properties"]
        assert "PhotoAsset" not in json.dumps(schema.model_json_schema())


def test_commons_search_sanitizes_metadata_and_skips_unknown_license(asset, monkeypatch):
    page = {
        "pageid": 123,
        "title": "File:Backwaters.jpg",
        "imageinfo": [
            {
                "mime": "image/jpeg",
                "width": 4032,
                "height": 2688,
            "url": asset.original_url + "?utm_content=original",
                "thumburl": asset.preview_url.replace("upload.wikimedia.org", "thumb.wikimedia.org")
                + "?utm_source=commons.wikimedia.org",
                "descriptionurl": asset.source_url,
                "extmetadata": {
                    "Artist": {
                        "value": '<a href="javascript:x">Author &amp; Co</a><script>bad()</script>'
                    },
                    "LicenseUrl": {"value": asset.license_url.rstrip("/")},
                },
            }
        ],
    }
    invalid = copy.deepcopy(page)
    invalid["imageinfo"][0]["extmetadata"]["LicenseUrl"]["value"] = "https://evil.example/license"
    original_client = httpx.Client
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == "commons.wikimedia.org"
        assert request.url.params["gsrnamespace"] == "6"
        assert request.url.params["gsrsearch"] == "Kerala canals filetype:bitmap"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"query": {"pages": [invalid, page, {"imageinfo": None}]}})

    monkeypatch.setattr(
        photo_service.httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(settings, "photo_provider", "commons")
    result = photo_service.search_photos("Kerala canals", 5, 8)
    assert len(calls) == 1 and len(result.photos) == 1
    assert result.photos[0].creator == "Author & Co"
    assert result.photos[0].preview_url.startswith("https://thumb.wikimedia.org/")
    assert "?" not in result.photos[0].preview_url
    assert "?" not in result.photos[0].original_url
    assert photo_service.selected_photo(result.photos[0].selection_token, 5, 8).source_id == 123


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"location": "https://evil.example"}),
        httpx.Response(200, json={"query": {"pages": "malformed"}}),
        httpx.Response(200, content=b"x" * 1_000_001, headers={"content-type": "application/json"}),
    ],
)
def test_provider_redirects_malformed_and_oversized_results_fail_closed(response, monkeypatch):
    original_client = httpx.Client
    monkeypatch.setattr(
        photo_service.httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(lambda request: response), **kwargs
        ),
    )
    monkeypatch.setattr(settings, "photo_provider", "commons")
    with pytest.raises(ExternalServiceError):
        photo_service.search_photos("canal", 1, 2)
