"""A browser on another origin can send the image-consent header (#61, #68)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from smartcart_api.main import app
from smartcart_api.settings import get_settings


def test_preflight_allows_the_image_consent_header() -> None:
    origins = get_settings().cors_origins
    assert origins, "the API configures at least one CORS origin"
    r = TestClient(app).options(
        "/parse-image",
        headers={
            "Origin": origins[0],
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-image-consent",
        },
    )
    assert r.status_code == 200, r.text
    assert "x-image-consent" in r.headers["access-control-allow-headers"].lower()
