"""``POST /me/lists/{id}/items`` is idempotent per (list, client_id): the offline queue of the shared
list can send an add again after a lost response without adding the item twice
(``list_items.client_id``, migration 20261023090000_list_items_client_id_touch.sql). Same contract
as ``POST /me/spend`` (``test_api_spend_idempotency.py``).
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
    p = {k: uuid.uuid4() for k in ("owner", "editor", "viewer")}
    db.execute("INSERT INTO auth.users (id) SELECT unnest(%s::uuid[])", (list(p.values()),))
    return p


def new_list(client, owner, name="משפחה", items=()) -> int:
    r = client.post(
        "/me/lists",
        headers=h(owner),
        json={"name": name, "items": [{"input_text": t} for t in items]},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def share(client, people, list_id: int) -> None:
    for role in ("editor", "viewer"):
        token = client.post(
            f"/me/lists/{list_id}/share", headers=h(people["owner"]), json={"role": role}
        ).json()["token"]
        assert client.post(f"/lists/accept/{token}", headers=h(people[role])).status_code == 200


def count(db, list_id: int) -> int:
    row = db.execute("SELECT count(*) FROM list_items WHERE list_id = %s", (list_id,)).fetchone()
    return row[0]


def test_a_replay_returns_the_stored_item_and_inserts_nothing(client, people, db) -> None:
    lid = new_list(client, people["owner"], items=["חלב"])
    cid = str(uuid.uuid4())
    body = {"input_text": "גבינה", "quantity": 2, "client_id": cid}
    first = client.post(f"/me/lists/{lid}/items", headers=h(people["owner"]), json=body)
    assert first.status_code == 201, first.text
    assert first.json()["client_id"] == cid
    again = client.post(f"/me/lists/{lid}/items", headers=h(people["owner"]), json=body)
    assert again.status_code == 200, again.text
    assert again.json() == first.json()
    assert count(db, lid) == 2


def test_the_stored_item_wins_when_the_replay_differs_or_the_item_moved_on(
    client, people, db
) -> None:
    """The replay is "the same add": it answers with the item as it is now, not with its own body."""
    me = h(people["owner"])
    lid = new_list(client, people["owner"])
    cid = str(uuid.uuid4())
    first = client.post(
        f"/me/lists/{lid}/items", headers=me, json={"input_text": "חלב", "client_id": cid}
    ).json()
    ticked = client.patch(
        f"/me/lists/{lid}/items/{first['id']}", headers=me, json={"checked": True}
    )
    assert ticked.status_code == 200
    again = client.post(
        f"/me/lists/{lid}/items",
        headers=me,
        json={"input_text": "something else", "quantity": 9, "client_id": cid},
    )
    assert again.status_code == 200
    got = again.json()
    assert (got["input_text"], got["quantity"], got["checked"]) == ("חלב", "1", True)
    assert count(db, lid) == 1


def test_without_a_client_id_every_post_inserts(client, people, db) -> None:
    me = h(people["owner"])
    lid = new_list(client, people["owner"])
    for _ in range(2):
        r = client.post(f"/me/lists/{lid}/items", headers=me, json={"input_text": "חלב"})
        assert r.status_code == 201
        assert r.json()["client_id"] is None
    assert count(db, lid) == 2


def test_the_same_client_id_in_another_list_is_a_new_item(client, people, db) -> None:
    me = h(people["owner"])
    a, b = new_list(client, people["owner"], "a"), new_list(client, people["owner"], "b")
    cid = str(uuid.uuid4())
    for lid in (a, b):
        r = client.post(
            f"/me/lists/{lid}/items", headers=me, json={"input_text": "חלב", "client_id": cid}
        )
        assert r.status_code == 201, r.text
    assert (count(db, a), count(db, b)) == (1, 1)


def test_an_editor_replay_gets_the_stored_item(client, people, db) -> None:
    lid = new_list(client, people["owner"])
    share(client, people, lid)
    body = {"input_text": "חלב", "client_id": str(uuid.uuid4())}
    first = client.post(f"/me/lists/{lid}/items", headers=h(people["editor"]), json=body)
    again = client.post(f"/me/lists/{lid}/items", headers=h(people["editor"]), json=body)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["id"] == first.json()["id"]
    assert count(db, lid) == 1


def test_a_viewer_cannot_use_a_replay_to_read_an_item(client, people, db) -> None:
    lid = new_list(client, people["owner"])
    share(client, people, lid)
    body = {"input_text": "חלב", "client_id": str(uuid.uuid4())}
    owner_post = client.post(f"/me/lists/{lid}/items", headers=h(people["owner"]), json=body)
    assert owner_post.status_code == 201
    viewer_post = client.post(f"/me/lists/{lid}/items", headers=h(people["viewer"]), json=body)
    assert viewer_post.status_code == 403


def test_a_replay_on_a_full_list_is_still_a_replay(client, people, db) -> None:
    """The size cap refuses a new item; a replay of an item that is in the list is not one."""
    me = h(people["owner"])
    lid = new_list(client, people["owner"])
    body = {"input_text": "חלב", "client_id": str(uuid.uuid4())}
    assert client.post(f"/me/lists/{lid}/items", headers=me, json=body).status_code == 201
    db.execute(
        "INSERT INTO list_items (list_id, user_id, input_text, sort)"
        " SELECT %s, %s, 'x', 1 + g FROM generate_series(1, 199) AS g",
        (lid, people["owner"]),
    )
    assert count(db, lid) == 200
    assert client.post(f"/me/lists/{lid}/items", headers=me, json=body).status_code == 200
    full = client.post(f"/me/lists/{lid}/items", headers=me, json={"input_text": "new"})
    assert full.status_code == 403


def test_a_deleted_item_can_be_added_again_with_its_key(client, people, db) -> None:
    """The key identifies a live item: after a delete the add is a new add."""
    me = h(people["owner"])
    lid = new_list(client, people["owner"])
    body = {"input_text": "חלב", "client_id": str(uuid.uuid4())}
    first = client.post(f"/me/lists/{lid}/items", headers=me, json=body).json()
    assert client.delete(f"/me/lists/{lid}/items/{first['id']}", headers=me).status_code == 204
    again = client.post(f"/me/lists/{lid}/items", headers=me, json=body)
    assert again.status_code == 201
    assert again.json()["id"] != first["id"]


def test_a_malformed_client_id_is_422(client, people) -> None:
    lid = new_list(client, people["owner"])
    r = client.post(
        f"/me/lists/{lid}/items", headers=h(people["owner"]), json={"client_id": "not-a-uuid"}
    )
    assert r.status_code == 422


def test_the_key_is_unique_per_list_in_the_table(client, people, db) -> None:
    """The database refuses a second row, whatever path wrote it (PostgREST, a race)."""
    lid = new_list(client, people["owner"])
    cid = uuid.uuid4()
    insert = (
        "INSERT INTO list_items (list_id, user_id, input_text, client_id) VALUES (%s, %s, 'x', %s)"
    )
    db.execute(insert, (lid, people["owner"], cid))
    with pytest.raises(psycopg.errors.UniqueViolation):
        with db.transaction():
            db.execute(insert, (lid, people["owner"], cid))
    for _ in range(2):  # rows without a key never collide
        db.execute(insert, (lid, people["owner"], None))


def test_put_keeps_the_key_of_a_kept_item_and_ignores_one_in_the_body(client, people, db) -> None:
    me = h(people["owner"])
    lid = new_list(client, people["owner"])
    cid = str(uuid.uuid4())
    item = client.post(
        f"/me/lists/{lid}/items", headers=me, json={"input_text": "חלב", "client_id": cid}
    ).json()
    echoed = {k: v for k, v in item.items() if k not in ("sort", "updated_at")}
    body = {
        "name": "משפחה",
        "items": [{**echoed, "client_id": str(uuid.uuid4()), "quantity": "3"}],
    }
    r = client.put(f"/me/lists/{lid}", headers=me, json=body)
    assert r.status_code == 200, r.text
    got = r.json()["items"][0]
    assert (got["quantity"], got["client_id"]) == ("3", cid)
