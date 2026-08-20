"""Health, middleware, and error-envelope behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_ready() -> None:
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_every_response_carries_request_id() -> None:
    response = client.get("/api/v1/health")
    assert response.headers.get("X-Request-ID")


def test_security_headers_present() -> None:
    response = client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_unknown_route_returns_error_envelope() -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"]
    assert body["error"]["request_id"]


def test_validation_error_returns_field_details() -> None:
    response = client.post("/api/v1/health", json={"unexpected": True})
    assert response.status_code in (405, 422)
    if response.status_code == 422:
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
