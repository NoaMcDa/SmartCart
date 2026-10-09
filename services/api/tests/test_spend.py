"""Budget and spend tracking (issue #70): /me/spend, the profile's monthly_budget, RLS."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import psycopg
import pytest
from api_world import World, make_token

pytestmark = [pytest.mark.db, pytest.mark.postgis]


def h(user_id) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


@pytest.fixture
def users(db) -> tuple[uuid.UUID, uuid.UUID]:
    a, b = uuid.uuid4(), uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s), (%s)", (a, b))
    return a, b


def entry(w: World, **over) -> dict:
    return {
        "date": "2026-10-02",
        "store_id": w.stores["home"],
        "store_name": "הבית",
        "total": "312.40",
        "item_count": 18,
        "plan": "single",
        **over,
    }


def test_record_and_read_a_month(client, world: World, users) -> None:
    a, _ = users
    r = client.post("/me/spend", json=entry(world), headers=h(a))
    assert r.status_code == 201, r.text
    first = r.json()
    assert set(first) == {
        "id",
        "date",
        "store_id",
        "store_name",
        "total",
        "item_count",
        "plan",
        "client_id",
    }
    assert (
        first["total"] == "312.40" and first["date"] == "2026-10-02" and first["plan"] == "single"
    )
    client.post(
        "/me/spend",
        json=entry(
            world,
            date="2026-10-20",
            total="150",
            plan="split",
            store_id=world.stores["b"],
            store_name="סניף B",
        ),
        headers=h(a),
    )
    client.post("/me/spend", json=entry(world, date="2026-09-30", total="99.90"), headers=h(a))

    month = client.get("/me/spend", params={"month": "2026-10"}, headers=h(a)).json()
    assert month["month"] == "2026-10" and month["budget"] is None
    assert [e["date"] for e in month["entries"]] == ["2026-10-02", "2026-10-20"]
    assert month["total"] == "462.40"
    sept = client.get("/me/spend", params={"month": "2026-09"}, headers=h(a)).json()
    assert sept["total"] == "99.90" and len(sept["entries"]) == 1
    empty = client.get("/me/spend", params={"month": "2026-12"}, headers=h(a)).json()
    assert empty == {"month": "2026-12", "entries": [], "total": "0.00", "budget": None}
    now = client.get("/me/spend", headers=h(a)).json()
    assert now["month"] == datetime.now(UTC).strftime("%Y-%m")


def test_budget_is_set_kept_and_cleared_through_the_profile(client, world: World, users) -> None:
    a, _ = users
    r = client.put("/me/profile", json={"monthly_budget": "2400.50"}, headers=h(a))
    assert r.status_code == 200 and r.json()["monthly_budget"] == "2400.50"
    # A client that does not know the field keeps the stored budget.
    r = client.put("/me/profile", json={"radius_m": 3000}, headers=h(a))
    assert r.json()["monthly_budget"] == "2400.50" and r.json()["radius_m"] == 3000
    assert (
        client.get("/me/spend", params={"month": "2026-10"}, headers=h(a)).json()["budget"]
        == "2400.50"
    )
    assert client.get("/me/profile", headers=h(a)).json()["monthly_budget"] == "2400.50"
    r = client.put("/me/profile", json={"monthly_budget": None}, headers=h(a))
    assert r.json()["monthly_budget"] is None
    assert client.put("/me/profile", json={"monthly_budget": "-1"}, headers=h(a)).status_code == 422
    assert (
        client.put("/me/profile", json={"monthly_budget": "10.123"}, headers=h(a)).status_code
        == 422
    )
    # A new profile without the field starts with no budget.
    _, b = users
    assert client.put("/me/profile", json={}, headers=h(b)).json()["monthly_budget"] is None


def test_correct_delete_and_export(client, world: World, users) -> None:
    a, _ = users
    eid = client.post("/me/spend", json=entry(world), headers=h(a)).json()["id"]
    r = client.put(f"/me/spend/{eid}", json=entry(world, total="298.10"), headers=h(a))
    assert r.status_code == 200 and r.json()["total"] == "298.10" and r.json()["id"] == eid
    client.put("/me/profile", json={"monthly_budget": "2000"}, headers=h(a))
    other = client.post("/me/spend", json=entry(world, date="2026-08-01"), headers=h(a)).json()[
        "id"
    ]
    export = client.get("/me/spend/export", headers=h(a)).json()
    assert export["budget"] == "2000.00" and [e["id"] for e in export["entries"]] == [other, eid]
    assert client.delete(f"/me/spend/{eid}", headers=h(a)).status_code == 204
    assert client.delete(f"/me/spend/{eid}", headers=h(a)).status_code == 404
    assert [e["id"] for e in client.get("/me/spend/export", headers=h(a)).json()["entries"]] == [
        other
    ]


def test_validation(client, world: World, users) -> None:
    a, _ = users
    for bad in (
        entry(world, plan="three"),
        entry(world, total="-5"),
        entry(world, total="1.234"),
        entry(world, store_name=""),
        entry(world, item_count=-1),
        entry(world, date="2026-13-01"),
        {**entry(world), "user_id": str(a)},
    ):
        assert client.post("/me/spend", json=bad, headers=h(a)).status_code == 422, bad
    r = client.post("/me/spend", json=entry(world, store_id=987654321), headers=h(a))
    assert r.status_code == 422 and "store_id" in r.text
    for month in ("2026-13", "2026-1", "10-2026"):
        assert client.get("/me/spend", params={"month": month}, headers=h(a)).status_code == 422
    assert client.get("/me/spend").status_code == 401
    assert client.post("/me/spend", json=entry(world)).status_code == 401


def test_user_a_cannot_read_or_change_b_spend(client, world: World, users, db) -> None:
    a, b = users
    eid = client.post("/me/spend", json=entry(world), headers=h(b)).json()["id"]
    client.put("/me/profile", json={"monthly_budget": "1500"}, headers=h(b))
    assert client.get("/me/spend", params={"month": "2026-10"}, headers=h(a)).json() == {
        "month": "2026-10",
        "entries": [],
        "total": "0.00",
        "budget": None,
    }
    assert client.get("/me/spend/export", headers=h(a)).json()["entries"] == []
    assert (
        client.put(f"/me/spend/{eid}", json=entry(world, total="1"), headers=h(a)).status_code
        == 404
    )
    assert client.delete(f"/me/spend/{eid}", headers=h(a)).status_code == 404
    got = client.get("/me/spend", params={"month": "2026-10"}, headers=h(b)).json()
    assert got["total"] == "312.40" and got["budget"] == "1500.00"
    assert db.execute("SELECT current_user <> 'smartcart_app'").fetchone()[0]


def test_rls_contract_on_spend_entries(db, world: World, users) -> None:
    """SQL level, through smartcart_app as in test_rls_contract.py."""
    a, b = users

    def as_user(uid):
        db.execute("SET LOCAL ROLE smartcart_app")
        db.execute(
            "SELECT set_config('request.jwt.claim.sub', %s, true)", (str(uid) if uid else "",)
        )

    for uid in (a, b):
        as_user(uid)
        db.execute(
            "INSERT INTO spend_entries (user_id, date, store_id, store_name, total, item_count, plan)"
            " VALUES (%s, '2026-10-01', %s, 'x', 10, 1, 'single')",
            (uid, world.stores["home"]),
        )
    as_user(a)
    assert db.execute("SELECT count(*) FROM spend_entries").fetchone()[0] == 1
    assert db.execute("UPDATE spend_entries SET total = 0 WHERE user_id = %s", (b,)).rowcount == 0
    assert db.execute("DELETE FROM spend_entries WHERE user_id = %s", (b,)).rowcount == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute(
            "INSERT INTO spend_entries (user_id, date, store_id, store_name, total, item_count, plan)"
            " VALUES (%s, '2026-10-01', %s, 'x', 10, 1, 'single')",
            (b, world.stores["home"]),
        )
    as_user(None)
    assert db.execute("SELECT count(*) FROM spend_entries").fetchone()[0] == 0
    db.execute("RESET ROLE")
    assert db.execute("SELECT count(*) FROM spend_entries").fetchone()[0] == 2


def test_spend_never_reaches_events(client, world: World, users, db) -> None:
    a, _ = users
    client.post("/me/spend", json=entry(world), headers=h(a))
    assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
