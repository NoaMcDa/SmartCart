import json
from pathlib import Path

from fastapi.testclient import TestClient

from smartcart_api.export_openapi import DEFAULT
from smartcart_api.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_routes_declared() -> None:
    paths = set(app.openapi()["paths"])
    assert {"/parse-list", "/search", "/compare", "/optimize", "/feedback/substitution", "/feedback/gap"} <= paths


def test_openapi_snapshot_is_current() -> None:
    """apps/web/src/api/openapi.json must match the app. Regenerate with
    `uv run python -m smartcart_api.export_openapi` when the schemas change."""
    assert DEFAULT.exists(), "run uv run python -m smartcart_api.export_openapi"
    on_disk = json.loads(Path(DEFAULT).read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(app.openapi(), sort_keys=True))


def test_validation_rejects_unknown_fields() -> None:
    r = client.post("/compare", json={"items": [], "location": {"lon": 35, "lat": 32}, "x": 1})
    assert r.status_code == 422
