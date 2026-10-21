"""A change to a list's items moves the list's own ``updated_at`` (trigger ``list_items_touch_list``,
migration 20261023090000_list_items_client_id_touch.sql), so ``GET /me/lists`` orders the list that
somebody just worked on first and its "updated" label is right.

The tests run in one transaction, where ``now()`` does not move, so they put the list's
``updated_at`` an hour back first (with the ``lists_set_updated_at`` trigger off for that one
statement) and look at where it goes.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest
from api_world import make_token

pytestmark = pytest.mark.db


def h(user_id) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


@pytest.fixture
def people(db) -> dict[str, uuid.UUID]:
    p = {k: uuid.uuid4() for k in ("owner", "editor")}
    db.execute("INSERT INTO auth.users (id) SELECT unnest(%s::uuid[])", (list(p.values()),))
    return p


def backdate(db: psycopg.Connection, list_id: int, hours: int = 1) -> None:
    db.execute("ALTER TABLE lists DISABLE TRIGGER lists_set_updated_at")
    db.execute(
        "UPDATE lists SET updated_at = now() - make_interval(hours => %s) WHERE id = %s",
        (hours, list_id),
    )
    db.execute("ALTER TABLE lists ENABLE TRIGGER lists_set_updated_at")


def stamp(db: psycopg.Connection, list_id: int):
    return db.execute("SELECT updated_at FROM lists WHERE id = %s", (list_id,)).fetchone()[0]


def hour_ago(db: psycopg.Connection):
    return db.execute("SELECT now() - interval '1 hour'").fetchone()[0]


@pytest.fixture
def shared(client, db, people) -> tuple[int, int]:
    """The owner's list of two items, shared with an editor, and the id of its first item. Its
    ``updated_at`` is an hour old."""
    r = client.post(
        "/me/lists",
        headers=h(people["owner"]),
        json={"name": "משפחה", "items": [{"input_text": "חלב"}, {"input_text": "לחם"}]},
    )
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    token = client.post(
        f"/me/lists/{lid}/share", headers=h(people["owner"]), json={"role": "editor"}
    ).json()["token"]
    assert client.post(f"/lists/accept/{token}", headers=h(people["editor"])).status_code == 200
    backdate(db, lid)
    return lid, r.json()["items"][0]["id"]


@pytest.mark.parametrize("who", ["owner", "editor"])
def test_adding_changing_and_removing_an_item_moves_the_list(
    client, db, people, shared, who
) -> None:
    """An editor may not update the list row itself; the trigger does it for them."""
    lid, first = shared
    me = h(people[who])
    old = hour_ago(db)

    client.post(f"/me/lists/{lid}/items", headers=me, json={"input_text": "גבינה"})
    assert stamp(db, lid) > old
    backdate(db, lid)
    assert stamp(db, lid) == old

    r = client.patch(f"/me/lists/{lid}/items/{first}", headers=me, json={"quantity": 4})
    assert r.status_code == 200
    assert stamp(db, lid) > old
    backdate(db, lid)

    assert client.delete(f"/me/lists/{lid}/items/{first}", headers=me).status_code == 204
    assert stamp(db, lid) > old


def test_a_change_that_changes_nothing_leaves_the_list_alone(client, db, people, shared) -> None:
    lid, first = shared
    me = h(people["owner"])
    before = stamp(db, lid)
    same = client.patch(f"/me/lists/{lid}/items/{first}", headers=me, json={"checked": False})
    assert same.status_code == 200
    assert stamp(db, lid) == before


def test_tick_through_the_checked_flag_moves_the_list(client, db, people, shared) -> None:
    lid, first = shared
    before = stamp(db, lid)
    client.patch(
        f"/me/lists/{lid}/items/{first}", headers=h(people["editor"]), json={"checked": True}
    )
    assert stamp(db, lid) > before


def test_an_item_of_another_list_does_not_move_this_one(client, db, people, shared) -> None:
    lid, _ = shared
    me = h(people["owner"])
    other = client.post("/me/lists", headers=me, json={"name": "אחר", "items": []}).json()["id"]
    backdate(db, other)
    before, other_before = stamp(db, lid), stamp(db, other)
    client.post(f"/me/lists/{other}/items", headers=me, json={"input_text": "חלב"})
    assert stamp(db, lid) == before
    assert stamp(db, other) > other_before


def test_the_list_that_was_just_worked_on_comes_first(client, db, people) -> None:
    me = h(people["owner"])
    a = client.post("/me/lists", headers=me, json={"name": "a", "items": []}).json()["id"]
    b = client.post("/me/lists", headers=me, json={"name": "b", "items": []}).json()["id"]
    backdate(db, a, hours=3)
    backdate(db, b, hours=2)
    names = [x["name"] for x in client.get("/me/lists", headers=me).json()]
    assert names == ["b", "a"]
    client.post(f"/me/lists/{a}/items", headers=me, json={"input_text": "חלב"})
    got = client.get("/me/lists", headers=me).json()
    assert [x["name"] for x in got] == ["a", "b"]
    assert got[0]["updated_at"] > got[1]["updated_at"]


def test_deleting_a_list_with_items_still_works(client, db, people, shared) -> None:
    """The cascade deletes the items, which fires the trigger for a list that is going away."""
    lid, _ = shared
    assert client.delete(f"/me/lists/{lid}", headers=h(people["owner"])).status_code == 204
    assert (
        db.execute("SELECT count(*) FROM list_items WHERE list_id = %s", (lid,)).fetchone()[0] == 0
    )


def test_moving_an_item_between_lists_touches_both(client, db, people, shared) -> None:
    lid, first = shared
    other = client.post(
        "/me/lists", headers=h(people["owner"]), json={"name": "אחר", "items": []}
    ).json()["id"]
    backdate(db, other)
    old = hour_ago(db)
    db.execute("UPDATE list_items SET list_id = %s WHERE id = %s", (other, first))
    assert stamp(db, lid) > old
    assert stamp(db, other) > old


def test_a_list_does_not_go_back_in_time(db, people, client) -> None:
    """The touch never lowers an ``updated_at`` that is already later than now()."""
    lid = client.post(
        "/me/lists", headers=h(people["owner"]), json={"name": "x", "items": []}
    ).json()["id"]
    db.execute("ALTER TABLE lists DISABLE TRIGGER lists_set_updated_at")
    db.execute("UPDATE lists SET updated_at = now() + interval '1 day' WHERE id = %s", (lid,))
    db.execute("ALTER TABLE lists ENABLE TRIGGER lists_set_updated_at")
    future = stamp(db, lid)
    db.execute(
        "INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'x')",
        (lid, people["owner"]),
    )
    assert stamp(db, lid) == future
