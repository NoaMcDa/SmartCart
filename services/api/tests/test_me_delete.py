"""DELETE /me (issue #90): every row of the user, then the auth user."""

from __future__ import annotations

import uuid

import httpx
import pytest
from api_world import World, make_token
from fastapi import HTTPException

from smartcart_api.routes import me_delete

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]


def h(user_id) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


@pytest.fixture
def users(db, monkeypatch) -> tuple[uuid.UUID, uuid.UUID]:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    a, b = uuid.uuid4(), uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s), (%s)", (a, b))
    return a, b


def seed_user(client, db, w: World, uid: uuid.UUID) -> int:
    """Profile with a budget, a list with items, an alert, a push subscription, feedback, a spend
    entry; returns the list id."""
    assert (
        client.put(
            "/me/profile",
            headers=h(uid),
            json={
                "neighborhood_lat": 32.08,
                "neighborhood_lon": 34.78,
                "consent_location": True,
                "clubs": ["רשת אחת"],
                "monthly_budget": "2400.00",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/me/spend",
            headers=h(uid),
            json={
                "date": "2026-10-02",
                "store_id": w.stores["home"],
                "store_name": "הבית",
                "total": "312.40",
                "item_count": 18,
                "plan": "single",
            },
        ).status_code
        == 201
    )
    lst = client.post(
        "/me/lists",
        headers=h(uid),
        json={
            "name": "שבועי",
            "items": [{"input_text": "חלב"}, {"input_text": "לחם"}],
        },
    )
    assert lst.status_code == 201, lst.text
    assert (
        client.post(
            "/me/alerts",
            headers=h(uid),
            json={
                "canonical_id": w.canon["eggs"],
                "threshold_unit_price": "1.00",
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/me/push-subscriptions",
            headers=h(uid),
            json={
                "endpoint": f"https://push.example/{uid}",
                "p256dh": "k",
                "auth": "a",
            },
        ).status_code
        == 201
    )
    assert client.post(
        "/feedback/substitution",
        headers=h(uid),
        json={
            "canonical_id": w.canon["salmon"],
            "substitute_item_id": w.items["salmon_c2_frozen"],
            "verdict": "accepted",
        },
    ).status_code in (200, 201)
    db.execute(
        "INSERT INTO gap_reports (store_id, canonical_id, note, user_id) VALUES (%s, %s, 'x', %s)",
        (w.stores["home"], w.canon["eggs"], uid),
    )
    return lst.json()["id"]


COUNTS = {
    "profiles": "SELECT count(*) FROM profiles WHERE user_id = %s",
    "lists": "SELECT count(*) FROM lists WHERE user_id = %s",
    "list_items": "SELECT count(*) FROM list_items WHERE user_id = %s",
    "price_alerts": "SELECT count(*) FROM price_alerts WHERE user_id = %s",
    "push_subscriptions": "SELECT count(*) FROM push_subscriptions WHERE user_id = %s",
    "substitution_feedback": "SELECT count(*) FROM substitution_feedback WHERE user_id = %s",
    "list_shares": "SELECT count(*) FROM list_shares WHERE owner_id = %s OR member_id = %s",
    "gap_reports": "SELECT count(*) FROM gap_reports WHERE user_id = %s",
    "spend_entries": "SELECT count(*) FROM spend_entries WHERE user_id = %s",
    "auth.users": "SELECT count(*) FROM auth.users WHERE id = %s",
}


def counts(db, uid) -> dict[str, int]:
    return {k: db.execute(q, (uid,) * q.count("%s")).fetchone()[0] for k, q in COUNTS.items()}


def test_delete_me_removes_everything_of_the_user_only(client, db, world: World, users) -> None:
    a, b = users
    list_a = seed_user(client, db, world, a)
    seed_user(client, db, world, b)
    # A shares a list with B, and B shares one with A (A is then a member who added an item).
    tok = client.post(f"/me/lists/{list_a}/share", headers=h(a), json={}).json()["token"]
    assert client.post(f"/lists/accept/{tok}", headers=h(b)).status_code == 200
    list_b = client.get("/me/lists", headers=h(b)).json()[0]["id"]
    tok_b = client.post(f"/me/lists/{list_b}/share", headers=h(b), json={}).json()["token"]
    assert client.post(f"/lists/accept/{tok_b}", headers=h(a)).status_code == 200
    db.execute(
        "INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'ביצים')",
        (list_b, a),
    )
    before_b = counts(db, b)
    assert all(v >= 1 for v in counts(db, a).values())

    r = client.delete("/me", headers=h(a))
    assert r.status_code == 200 and r.json()["ok"]
    assert counts(db, a) == dict.fromkeys(COUNTS, 0)
    after_b = counts(db, b)
    # B keeps everything except the shares that involved A.
    assert after_b == {**before_b, "list_shares": 0}
    assert (
        db.execute("SELECT count(*) FROM list_items WHERE list_id = %s", (list_b,)).fetchone()[0]
        == 2
    )
    assert db.execute("SELECT count(*) FROM gap_reports WHERE user_id IS NULL").fetchone()[0] >= 1
    # The token no longer works.
    assert client.get("/me/profile", headers=h(a)).json()["exists"] is False


def test_delete_me_needs_sign_in(client, users) -> None:
    assert client.delete("/me").status_code == 401


def test_admin_api_is_called_first_when_configured(
    client, db, world: World, users, monkeypatch
) -> None:
    a, _ = users
    calls: list[tuple] = []
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co/")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    monkeypatch.setattr(
        me_delete, "delete_auth_user", lambda uid, url, key: calls.append((uid, url, key))
    )
    assert client.delete("/me", headers=h(a)).status_code == 200
    assert calls == [(a, "https://proj.supabase.co", "service-key")]
    # The hosted cascade removes auth.users; the stand-in row is left to it.
    assert db.execute("SELECT count(*) FROM auth.users WHERE id = %s", (a,)).fetchone()[0] == 1


def test_admin_delete_request_and_errors() -> None:
    seen: list[httpx.Request] = []

    def handler(status: int):
        def _h(req: httpx.Request) -> httpx.Response:
            seen.append(req)
            return httpx.Response(status)

        return _h

    uid = uuid.uuid4()
    with httpx.Client(transport=httpx.MockTransport(handler(200))) as c:
        me_delete.delete_auth_user(uid, "https://p.supabase.co", "k", client=c)
    req = seen[-1]
    assert (
        req.method == "DELETE"
        and str(req.url) == f"https://p.supabase.co/auth/v1/admin/users/{uid}"
    )
    assert req.headers["apikey"] == "k" and req.headers["authorization"] == "Bearer k"
    with httpx.Client(transport=httpx.MockTransport(handler(404))) as c:
        me_delete.delete_auth_user(uid, "https://p.supabase.co", "k", client=c)  # already gone
    with (
        httpx.Client(transport=httpx.MockTransport(handler(500))) as c,
        pytest.raises(HTTPException) as e,
    ):
        me_delete.delete_auth_user(uid, "https://p.supabase.co", "k", client=c)
    assert e.value.status_code == 502
