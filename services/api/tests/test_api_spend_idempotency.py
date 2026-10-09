"""POST /me/spend is idempotent per (user, client_id)."""

from __future__ import annotations

import uuid

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


def count(db, user_id=None) -> int:
    if user_id is None:
        return db.execute("SELECT count(*) FROM spend_entries").fetchone()[0]
    return db.execute(
        "SELECT count(*) FROM spend_entries WHERE user_id = %s", (user_id,)
    ).fetchone()[0]


def test_a_replay_returns_the_stored_entry_and_inserts_nothing(
    client, world: World, users, db
) -> None:
    a, _ = users
    cid = str(uuid.uuid4())
    first = client.post("/me/spend", json=entry(world, client_id=cid), headers=h(a))
    assert first.status_code == 201, first.text
    assert first.json()["client_id"] == cid
    again = client.post("/me/spend", json=entry(world, client_id=cid), headers=h(a))
    assert again.status_code == 200, again.text
    assert again.json() == first.json()
    assert count(db, a) == 1


def test_the_stored_row_wins_when_the_replay_differs(client, world: World, users, db) -> None:
    a, _ = users
    cid = str(uuid.uuid4())
    first = client.post("/me/spend", json=entry(world, client_id=cid), headers=h(a)).json()
    again = client.post(
        "/me/spend",
        json=entry(world, client_id=cid, total="1.00", item_count=1, plan="split"),
        headers=h(a),
    )
    assert again.status_code == 200
    assert again.json() == first and again.json()["total"] == "312.40"
    assert count(db, a) == 1
    # a correction goes through PUT, and the replay then returns the corrected row
    put = client.put(
        f"/me/spend/{first['id']}", json=entry(world, client_id=cid, total="298.10"), headers=h(a)
    )
    assert put.status_code == 200 and put.json()["client_id"] == cid
    assert (
        client.post("/me/spend", json=entry(world, client_id=cid), headers=h(a)).json()["total"]
        == "298.10"
    )


def test_without_a_client_id_every_post_inserts(client, world: World, users, db) -> None:
    a, _ = users
    r1 = client.post("/me/spend", json=entry(world), headers=h(a))
    r2 = client.post("/me/spend", json=entry(world), headers=h(a))
    assert (r1.status_code, r2.status_code) == (201, 201)
    assert r1.json()["client_id"] is None and r1.json()["id"] != r2.json()["id"]
    assert count(db, a) == 2


def test_two_ids_are_two_entries(client, world: World, users, db) -> None:
    a, _ = users
    codes = [
        client.post(
            "/me/spend", json=entry(world, client_id=str(uuid.uuid4())), headers=h(a)
        ).status_code
        for _ in range(2)
    ]
    assert codes == [201, 201] and count(db, a) == 2


def test_the_same_client_id_of_another_user_is_a_new_entry(client, world: World, users, db) -> None:
    a, b = users
    cid = str(uuid.uuid4())
    ra = client.post("/me/spend", json=entry(world, client_id=cid, total="10"), headers=h(a))
    rb = client.post("/me/spend", json=entry(world, client_id=cid, total="20"), headers=h(b))
    assert (ra.status_code, rb.status_code) == (201, 201)
    assert ra.json()["id"] != rb.json()["id"]
    assert rb.json()["total"] == "20.00" and count(db) == 2
    # a replay by A still returns A's row, never B's
    assert (
        client.post("/me/spend", json=entry(world, client_id=cid), headers=h(a)).json()["id"]
        == ra.json()["id"]
    )


def test_a_replay_with_an_unknown_store_is_still_the_stored_entry(
    client, world: World, users, db
) -> None:
    a, _ = users
    cid = str(uuid.uuid4())
    first = client.post("/me/spend", json=entry(world, client_id=cid), headers=h(a)).json()
    # An unknown store on a fresh id is rejected; on a known id the conflict is found before the
    # foreign key is checked, so the stored entry comes back.
    assert (
        client.post("/me/spend", json=entry(world, store_id=987654321), headers=h(a)).status_code
        == 422
    )
    again = client.post(
        "/me/spend", json=entry(world, client_id=cid, store_id=987654321), headers=h(a)
    )
    assert again.status_code == 200 and again.json() == first
    assert count(db, a) == 1


def test_client_id_must_be_a_uuid(client, world: World, users) -> None:
    a, _ = users
    for bad in ("not-a-uuid", "1234", 7):
        assert (
            client.post("/me/spend", json=entry(world, client_id=bad), headers=h(a)).status_code
            == 422
        )


def test_client_id_is_listed_and_exported(client, world: World, users) -> None:
    a, _ = users
    cid = str(uuid.uuid4())
    client.post("/me/spend", json=entry(world, client_id=cid), headers=h(a))
    month = client.get("/me/spend", params={"month": "2026-10"}, headers=h(a)).json()
    assert [e["client_id"] for e in month["entries"]] == [cid]
    assert [
        e["client_id"] for e in client.get("/me/spend/export", headers=h(a)).json()["entries"]
    ] == [cid]


def test_the_database_enforces_it_and_rls_is_unchanged(db, world: World, users) -> None:
    a, b = users
    cid = uuid.uuid4()
    sql = (
        "INSERT INTO spend_entries (user_id, client_id, date, store_id, store_name, total,"
        " item_count, plan) VALUES (%s, %s, '2026-10-01', %s, 'x', 10, 1, 'single')"
    )
    db.execute(sql, (a, cid, world.stores["home"]))
    with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
        db.execute(sql, (a, cid, world.stores["home"]))
    db.execute(sql, (b, cid, world.stores["home"]))  # another user: fine
    for _ in range(2):  # no id: no constraint
        db.execute(sql, (a, None, world.stores["home"]))
    # row-level security as before: user A cannot see B's entry
    db.execute("SET LOCAL ROLE smartcart_app")
    db.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(a),))
    assert (
        db.execute("SELECT count(*) FROM spend_entries WHERE client_id = %s", (cid,)).fetchone()[0]
        == 1
    )
    assert (
        db.execute("SELECT count(*) FROM spend_entries WHERE user_id = %s", (b,)).fetchone()[0] == 0
    )
    db.execute("RESET ROLE")
