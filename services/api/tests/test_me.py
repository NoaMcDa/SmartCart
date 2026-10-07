"""Signed-in routes (issue #64): Supabase JWT -> SET LOCAL ROLE smartcart_app -> RLS."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from api_world import JWT_SECRET, make_token

pytestmark = pytest.mark.db


@pytest.fixture
def users(db) -> tuple[uuid.UUID, uuid.UUID]:
    a, b = uuid.uuid4(), uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s), (%s)", (a, b))
    return a, b


def h(user_id) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


LIST = {
    "name": "הקנייה השבועית",
    "is_recurring": True,
    "items": [
        {"input_text": "חלב", "quantity": 2, "flex_level": "any_brand"},
        {"input_text": "סלמון", "quantity": "0.5", "flex_level": "close", "confirmed": False},
    ],
}


def test_anonymous_and_bad_tokens_are_rejected(client, users) -> None:
    a, _ = users
    assert client.get("/me/lists").status_code == 401
    assert client.get("/me/lists", headers={"Authorization": "Basic abc"}).status_code == 401
    forged = make_token(a, secret="another-secret-that-is-also-32-bytes-long")
    assert client.get("/me/lists", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    expired = jwt.encode(
        {"sub": str(a), "aud": "authenticated", "exp": datetime.now(UTC) - timedelta(minutes=1)},
        JWT_SECRET, algorithm="HS256",
    )
    assert client.get("/me/lists", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    wrong_aud = make_token(a, aud="anon")
    assert client.get("/me/lists", headers={"Authorization": f"Bearer {wrong_aud}"}).status_code == 401


def test_list_crud_under_rls(client, users) -> None:
    a, _ = users
    r = client.post("/me/lists", json=LIST, headers=h(a))
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["name"] == LIST["name"] and [i["input_text"] for i in created["items"]] == ["חלב", "סלמון"]
    lid = created["id"]
    assert [x["id"] for x in client.get("/me/lists", headers=h(a)).json()] == [lid]
    upd = {**LIST, "name": "שבועי", "items": LIST["items"][:1]}
    r = client.put(f"/me/lists/{lid}", json=upd, headers=h(a))
    assert r.status_code == 200 and r.json()["name"] == "שבועי" and len(r.json()["items"]) == 1
    assert client.get(f"/me/lists/{lid}", headers=h(a)).json()["name"] == "שבועי"
    assert client.delete(f"/me/lists/{lid}", headers=h(a)).status_code == 204
    assert client.get("/me/lists", headers=h(a)).json() == []


def test_user_a_cannot_read_or_write_b_lists(client, users, db) -> None:
    a, b = users
    lid = client.post("/me/lists", json=LIST, headers=h(b)).json()["id"]
    assert client.get("/me/lists", headers=h(a)).json() == []
    assert client.get(f"/me/lists/{lid}", headers=h(a)).status_code == 404
    assert client.put(f"/me/lists/{lid}", json=LIST, headers=h(a)).status_code == 404
    assert client.delete(f"/me/lists/{lid}", headers=h(a)).status_code == 404
    # B's list is untouched.
    got = client.get(f"/me/lists/{lid}", headers=h(b)).json()
    assert got["name"] == LIST["name"] and len(got["items"]) == 2
    # And the request role was reset: the test connection is the owner again.
    assert db.execute("SELECT current_user <> 'smartcart_app'").fetchone()[0]


def test_profile_defaults_update_and_rounding(client, users) -> None:
    a, b = users
    r = client.get("/me/profile", headers=h(a))
    assert r.status_code == 200 and r.json()["exists"] is False and r.json()["radius_m"] == 5000
    body = {"radius_m": 3000, "neighborhood_lat": 32.0712345, "neighborhood_lon": 34.7812345,
            "consent_location": True, "clubs": ["מועדון לקוחות"], "travel_mode": "walk_transit",
            "flex_defaults": {"t.fish": "close"}}
    r = client.put("/me/profile", json=body, headers=h(a))
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["exists"] and p["neighborhood_lat"] == 32.071 and p["neighborhood_lon"] == 34.781
    assert p["clubs"] == ["מועדון לקוחות"] and p["flex_defaults"] == {"t.fish": "close"}
    # B sees only its own (absent) profile.
    assert client.get("/me/profile", headers=h(b)).json()["exists"] is False


def test_location_needs_consent(client, users) -> None:
    a, _ = users
    r = client.put("/me/profile", json={"neighborhood_lat": 32.07, "neighborhood_lon": 34.78},
                   headers=h(a))
    assert r.status_code == 422


def test_user_routes_without_a_configured_secret(client, users, monkeypatch) -> None:
    from smartcart_api.settings import get_settings

    monkeypatch.delenv("SUPABASE_JWT_SECRET")
    get_settings.cache_clear()
    assert client.get("/me/profile", headers=h(users[0])).status_code == 503
