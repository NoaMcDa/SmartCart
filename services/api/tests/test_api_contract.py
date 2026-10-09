import json
from pathlib import Path

from fastapi.testclient import TestClient

from smartcart_api.db import get_conn
from smartcart_api.export_openapi import DEFAULT
from smartcart_api.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_routes_declared() -> None:
    paths = set(app.openapi()["paths"])
    assert {
        "/parse-list",
        "/search",
        "/compare",
        "/optimize",
        "/feedback/substitution",
        "/feedback/gap",
        "/me/profile",
        "/me/lists",
        "/me/lists/{list_id}",
    } <= paths


def test_openapi_snapshot_is_current() -> None:
    """apps/web/src/api/openapi.json must match the app. Regenerate with
    `uv run python -m smartcart_api.export_openapi` when the schemas change."""
    assert DEFAULT.exists(), "run uv run python -m smartcart_api.export_openapi"
    on_disk = json.loads(Path(DEFAULT).read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(app.openapi(), sort_keys=True))


def test_validation_rejects_unknown_fields() -> None:
    app.dependency_overrides[get_conn] = lambda: None  # no database needed to reject a request
    try:
        r = client.post("/compare", json={"items": [], "location": {"lon": 35, "lat": 32}, "x": 1})
    finally:
        app.dependency_overrides.pop(get_conn, None)
    assert r.status_code == 422


def test_generated_typescript_types_cover_the_basket_routes() -> None:
    """apps/web/src/api/types.ts is generated from openapi.json by
    services/api/scripts/gen_ts_client.sh (CI fails when it is stale)."""
    types = DEFAULT.parent / "types.ts"
    assert types.exists(), "run services/api/scripts/gen_ts_client.sh"
    text = types.read_text(encoding="utf-8")
    for path in ("/parse-list", "/search", "/compare", "/optimize"):
        assert f'"{path}"' in text, path
