"""Per-item writes on a shared list: ``POST /me/lists/{id}/items``, ``PATCH`` and ``DELETE`` on
``/me/lists/{id}/items/{item_id}``, the item version (``list_items.updated_at``, kept by a trigger),
the 409 precondition, and the id-stable ``PUT /me/lists/{id}``.

Roles as in test_shares.py: the owner and an accepted editor write, a viewer reads, a stranger sees
nothing. Everything runs on ``smartcart_app`` under row-level security, as in production.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import psycopg
import pytest
from api_world import make_token

from smartcart_api.routes.shares import token_hash

pytestmark = pytest.mark.db

API_PATH = "/me/lists/{}/items"


def h(user_id) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


@pytest.fixture
def people(db) -> dict[str, uuid.UUID]:
    p = {k: uuid.uuid4() for k in ("owner", "editor", "viewer", "stranger")}
    db.execute("INSERT INTO auth.users (id) SELECT unnest(%s::uuid[])", (list(p.values()),))
    return p


@pytest.fixture
def shared(client, db, people) -> int:
    """The owner's list of three items ("חלב", "לחם", "ביצים"), shared with an editor and a viewer."""
    body = {
        "name": "משפחה",
        "items": [
            {"input_text": "חלב", "quantity": 2},
            {"input_text": "לחם"},
            {"input_text": "ביצים"},
        ],
    }
    r = client.post("/me/lists", headers=h(people["owner"]), json=body)
    assert r.status_code == 201, r.text
    list_id = r.json()["id"]
    for role in ("editor", "viewer"):
        token = client.post(
            f"/me/lists/{list_id}/share", headers=h(people["owner"]), json={"role": role}
        ).json()["token"]
        assert client.post(f"/lists/accept/{token}", headers=h(people[role])).status_code == 200
    return list_id


def items_of(client, who, list_id) -> list[dict]:
    return client.get(f"/me/lists/{list_id}", headers=h(who)).json()["items"]


def by_text(client, who, list_id) -> dict[str, dict]:
    return {i["input_text"]: i for i in items_of(client, who, list_id)}


# --- who may write -----------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["owner", "editor"])
def test_owner_and_editor_add_change_and_delete_single_items(client, people, shared, who) -> None:
    me = people[who]
    base = API_PATH.format(shared)
    r = client.post(base, headers=h(me), json={"input_text": "גבינה", "quantity": 3})
    assert r.status_code == 201, r.text
    new = r.json()
    assert (new["input_text"], new["quantity"], new["checked"], new["sort"]) == (
        "גבינה",
        "3",
        False,
        3,
    )
    assert new["updated_at"] and new["flex_level"] == "any_brand" and new["confirmed"] is True

    r = client.patch(f"{base}/{new['id']}", headers=h(me), json={"checked": True, "quantity": 5})
    assert r.status_code == 200, r.text
    assert (r.json()["checked"], r.json()["quantity"]) == (True, "5")
    assert r.json()["id"] == new["id"] and r.json()["input_text"] == "גבינה"

    # Everyone with access sees the change, under the same id.
    for viewer in ("owner", "editor", "viewer"):
        row = by_text(client, people[viewer], shared)["גבינה"]
        assert (row["id"], row["checked"], row["quantity"]) == (new["id"], True, "5")

    assert client.delete(f"{base}/{new['id']}", headers=h(me)).status_code == 204
    assert "גבינה" not in by_text(client, people["owner"], shared)
    assert client.delete(f"{base}/{new['id']}", headers=h(me)).status_code == 404


def test_the_author_of_an_item_is_who_added_it(client, db, people, shared) -> None:
    r = client.post(API_PATH.format(shared), headers=h(people["editor"]), json={"input_text": "x"})
    row = db.execute("SELECT user_id FROM list_items WHERE id = %s", (r.json()["id"],)).fetchone()
    assert row[0] == people["editor"]
    # ... and a later change by the owner does not take the item over.
    client.patch(
        f"{API_PATH.format(shared)}/{r.json()['id']}",
        headers=h(people["owner"]),
        json={"checked": True},
    )
    row = db.execute("SELECT user_id FROM list_items WHERE id = %s", (r.json()["id"],)).fetchone()
    assert row[0] == people["editor"]


def test_a_viewer_reads_but_cannot_write(client, db, people, shared) -> None:
    viewer = h(people["viewer"])
    base = API_PATH.format(shared)
    item = by_text(client, people["viewer"], shared)["חלב"]
    assert client.post(base, headers=viewer, json={"input_text": "x"}).status_code == 403
    assert (
        client.patch(f"{base}/{item['id']}", headers=viewer, json={"checked": True}).status_code
        == 403
    )
    assert client.delete(f"{base}/{item['id']}", headers=viewer).status_code == 403
    assert by_text(client, people["owner"], shared)["חלב"] == item  # nothing moved
    assert (
        db.execute("SELECT count(*) FROM list_items WHERE list_id = %s", (shared,)).fetchone()[0]
        == 3
    )


def test_a_stranger_gets_404_and_changes_nothing(client, db, people, shared) -> None:
    stranger = h(people["stranger"])
    base = API_PATH.format(shared)
    item = by_text(client, people["owner"], shared)["חלב"]
    assert client.post(base, headers=stranger, json={"input_text": "x"}).status_code == 404
    assert (
        client.patch(f"{base}/{item['id']}", headers=stranger, json={"checked": True}).status_code
        == 404
    )
    assert client.delete(f"{base}/{item['id']}", headers=stranger).status_code == 404
    assert client.post(API_PATH.format(987654321), headers=stranger, json={}).status_code == 404
    assert by_text(client, people["owner"], shared)["חלב"] == item


def test_a_pending_or_revoked_member_cannot_write(client, people, shared) -> None:
    owner = h(people["owner"])
    pending = client.post(
        f"/me/lists/{shared}/share", headers=owner, json={"role": "editor"}
    ).json()
    assert pending["token"]  # an invite nobody accepted gives the stranger nothing
    assert (
        client.post(API_PATH.format(shared), headers=h(people["stranger"]), json={}).status_code
        == 404
    )
    # The editor is removed: access ends with the next request.
    assert (
        client.delete(f"/me/lists/{shared}/members/{people['editor']}", headers=owner).status_code
        == 204
    )
    item = by_text(client, people["owner"], shared)["חלב"]
    editor = h(people["editor"])
    assert client.post(API_PATH.format(shared), headers=editor, json={}).status_code == 404
    path = f"{API_PATH.format(shared)}/{item['id']}"
    assert client.patch(path, headers=editor, json={"checked": True}).status_code == 404
    assert client.delete(path, headers=editor).status_code == 404


def test_authentication_is_required(client, people, shared) -> None:
    item = by_text(client, people["owner"], shared)["חלב"]
    path = f"{API_PATH.format(shared)}/{item['id']}"
    assert client.post(API_PATH.format(shared), json={}).status_code == 401
    assert client.patch(path, json={"checked": True}).status_code == 401
    assert client.delete(path).status_code == 401


def test_an_item_of_another_list_is_never_reached_through_this_one(client, people, shared) -> None:
    """The list in the path must be the item's list: a member of list A who knows the id of an item
    of list B (ids are sequential) can neither read nor change it by naming list A."""
    outsider = people["stranger"]
    other = client.post(
        "/me/lists", headers=h(outsider), json={"name": "פרטי", "items": [{"input_text": "סוד"}]}
    ).json()
    secret = other["items"][0]
    editor = h(people["editor"])
    base = API_PATH.format(shared)
    r = client.patch(f"{base}/{secret['id']}", headers=editor, json={"input_text": "פרוץ"})
    assert r.status_code == 404
    assert client.delete(f"{base}/{secret['id']}", headers=editor).status_code == 404
    # Nor through the other list's own path: the editor has no access to it.
    base_other = API_PATH.format(other["id"])
    assert client.patch(f"{base_other}/{secret['id']}", headers=editor, json={}).status_code == 404
    assert client.delete(f"{base_other}/{secret['id']}", headers=editor).status_code == 404
    assert items_of(client, outsider, other["id"])[0]["input_text"] == "סוד"
    assert secret["id"] not in [i["id"] for i in items_of(client, people["owner"], shared)]


# --- what a change may be ----------------------------------------------------------------------


def test_patch_changes_only_the_named_fields_and_can_clear_the_nullable_ones(
    client, people, shared
) -> None:
    owner = h(people["owner"])
    base = API_PATH.format(shared)
    milk = by_text(client, people["owner"], shared)["חלב"]
    r = client.patch(f"{base}/{milk['id']}", headers=owner, json={"flex_level": "close"})
    assert r.json() | {"updated_at": 0, "flex_level": 0} == milk | {
        "updated_at": 0,
        "flex_level": 0,
    }
    assert r.json()["flex_level"] == "close"
    r = client.patch(f"{base}/{milk['id']}", headers=owner, json={"input_text": None})
    assert r.status_code == 200 and r.json()["input_text"] is None
    r = client.patch(
        f"{base}/{milk['id']}", headers=owner, json={"canonical_id": None, "confirmed": False}
    )
    assert r.status_code == 200 and r.json()["confirmed"] is False
    # Not nullable, out of range, unknown field, not an item field.
    for body in (
        {"quantity": None},
        {"checked": None},
        {"flex_level": None},
        {"quantity": 0},
        {"quantity": 1001},
        {"flex_level": "any"},
        {"input_text": "x" * 201},
        {"sort": 5},
        {"user_id": str(people["editor"])},
        {"list_id": 1},
        {"id": 7},
        {"updated_at": "2030-01-01T00:00:00Z"},
        {"expected_updated_at": "2026-10-21T10:00:00"},  # no offset: ambiguous
    ):
        r = client.patch(f"{base}/{milk['id']}", headers=owner, json=body)
        assert r.status_code == 422, (body, r.text)
    assert (
        client.patch(f"{base}/{milk['id']}", headers=owner, json={"checked": True}).status_code
        == 200
    )


def test_post_validates_like_a_list_item_and_ignores_the_id(client, people, shared) -> None:
    owner = h(people["owner"])
    base = API_PATH.format(shared)
    for body in (
        {"quantity": 0},
        {"quantity": 1001},
        {"flex_level": "x"},
        {"input_text": "x" * 201},
        {"sort": 1},
    ):
        assert client.post(base, headers=owner, json=body).status_code == 422, body
    existing = by_text(client, people["owner"], shared)["חלב"]
    r = client.post(base, headers=owner, json={"id": existing["id"], "input_text": "חדש"})
    assert r.status_code == 201 and r.json()["id"] != existing["id"]
    assert by_text(client, people["owner"], shared)["חלב"] == existing


def test_items_are_appended_in_order_and_a_list_holds_at_most_200(
    client, db, people, shared
) -> None:
    owner = h(people["owner"])
    base = API_PATH.format(shared)
    a = client.post(base, headers=owner, json={"input_text": "a"}).json()
    b = client.post(base, headers=h(people["editor"]), json={"input_text": "b"}).json()
    assert (a["sort"], b["sort"]) == (3, 4)
    # An item deleted from the middle leaves the others where they are; the next one goes last.
    first = items_of(client, people["owner"], shared)[0]
    client.delete(f"{base}/{first['id']}", headers=owner)
    c = client.post(base, headers=owner, json={"input_text": "c"}).json()
    assert c["sort"] == 5
    assert [i["input_text"] for i in items_of(client, people["owner"], shared)][-3:] == [
        "a",
        "b",
        "c",
    ]
    db.execute(
        "INSERT INTO list_items (list_id, user_id, input_text, sort)"
        " SELECT %s, %s, 'x', 100 + n FROM generate_series(1, 200) AS n"
        " WHERE (SELECT count(*) FROM list_items WHERE list_id = %s) + n <= 200",
        (shared, people["owner"], shared),
    )
    count = db.execute("SELECT count(*) FROM list_items WHERE list_id = %s", (shared,)).fetchone()[
        0
    ]
    assert count == 200
    for who in ("owner", "editor"):
        r = client.post(base, headers=h(people[who]), json={"input_text": "one too many"})
        assert r.status_code == 403 and "200" in r.json()["detail"]
    # The cap is about adding; the items there can still be changed and removed.
    r = client.delete(f"{base}/{c['id']}", headers=owner)
    assert r.status_code == 204
    assert client.post(base, headers=owner, json={"input_text": "fits"}).status_code == 201


def test_huge_and_unknown_ids_are_refused_cleanly(client, people, shared) -> None:
    owner = h(people["owner"])
    base = API_PATH.format(shared)
    assert (
        client.patch(f"{base}/987654321", headers=owner, json={"checked": True}).status_code == 404
    )
    assert client.delete(f"{base}/987654321", headers=owner).status_code == 404
    assert client.patch(f"{base}/abc", headers=owner, json={}).status_code == 422
    for path in (f"{base}/{2**70}", API_PATH.format(2**70) + "/1"):
        assert client.patch(path, headers=owner, json={"checked": True}).status_code in (404, 422)
        assert client.delete(path, headers=owner).status_code in (404, 422)


# --- the version (updated_at) and the 409 precondition ----------------------------------------


def test_a_change_moves_the_version_and_a_no_op_does_not(client, people, shared) -> None:
    owner = h(people["owner"])
    base = API_PATH.format(shared)
    milk = by_text(client, people["owner"], shared)["חלב"]
    same = client.patch(
        f"{base}/{milk['id']}", headers=owner, json={"quantity": 2, "checked": False}
    )
    assert same.json()["updated_at"] == milk["updated_at"]
    changed = client.patch(f"{base}/{milk['id']}", headers=owner, json={"checked": True})
    assert datetime.fromisoformat(changed.json()["updated_at"]) > datetime.fromisoformat(
        milk["updated_at"]
    )
    # The list read carries the same version.
    assert (
        by_text(client, people["owner"], shared)["חלב"]["updated_at"]
        == changed.json()["updated_at"]
    )
    # Other items keep theirs.
    assert (
        by_text(client, people["owner"], shared)["לחם"]["updated_at"]
        != changed.json()["updated_at"]
    )


def test_patch_with_a_stale_version_is_a_409_with_the_current_row(client, people, shared) -> None:
    owner, editor = h(people["owner"]), h(people["editor"])
    base = API_PATH.format(shared)
    seen = by_text(client, people["owner"], shared)["לחם"]
    # The editor changes the item after the owner read it.
    theirs = client.patch(f"{base}/{seen['id']}", headers=editor, json={"quantity": 4}).json()
    r = client.patch(
        f"{base}/{seen['id']}",
        headers=owner,
        json={"checked": True, "expected_updated_at": seen["updated_at"]},
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert set(body) == {"detail", "current"}
    assert body["current"] == theirs  # the editor's row, in full, with its new version
    # Nothing of the owner's change was applied.
    assert by_text(client, people["owner"], shared)["לחם"] == theirs
    # Retry with the version from the 409: it goes through.
    r = client.patch(
        f"{base}/{seen['id']}",
        headers=owner,
        json={"checked": True, "expected_updated_at": body["current"]["updated_at"]},
    )
    assert r.status_code == 200 and (r.json()["checked"], r.json()["quantity"]) == (True, "4")
    # Without a precondition the change is applied whatever the version.
    assert (
        client.patch(f"{base}/{seen['id']}", headers=owner, json={"checked": False}).status_code
        == 200
    )


def test_the_version_matches_to_the_millisecond(client, people, shared) -> None:
    """A browser keeps `new Date(...)` values to the millisecond; the version it sends back must
    still match, and one that is really older must not."""
    owner = h(people["owner"])
    base = API_PATH.format(shared)
    item = by_text(client, people["owner"], shared)["חלב"]
    stamp = datetime.fromisoformat(item["updated_at"])
    ms = stamp.replace(microsecond=stamp.microsecond // 1000 * 1000).isoformat()
    r = client.patch(
        f"{base}/{item['id']}", headers=owner, json={"checked": True, "expected_updated_at": ms}
    )
    assert r.status_code == 200, r.text
    r = client.patch(
        f"{base}/{item['id']}",
        headers=owner,
        json={"checked": False, "expected_updated_at": item["updated_at"]},  # the old version
    )
    assert r.status_code == 409


def test_a_no_op_by_someone_else_does_not_break_my_version(client, people, shared) -> None:
    owner, editor = h(people["owner"]), h(people["editor"])
    base = API_PATH.format(shared)
    item = by_text(client, people["owner"], shared)["חלב"]
    assert (
        client.patch(f"{base}/{item['id']}", headers=editor, json={"quantity": 2}).status_code
        == 200
    )
    r = client.patch(
        f"{base}/{item['id']}",
        headers=owner,
        json={"checked": True, "expected_updated_at": item["updated_at"]},
    )
    assert r.status_code == 200


def test_delete_with_a_stale_version_is_a_409_and_with_the_current_one_deletes(
    client, people, shared
) -> None:
    owner, editor = h(people["owner"]), h(people["editor"])
    base = API_PATH.format(shared)
    seen = by_text(client, people["owner"], shared)["ביצים"]
    theirs = client.patch(f"{base}/{seen['id']}", headers=editor, json={"checked": True}).json()
    r = client.delete(
        f"{base}/{seen['id']}", headers=owner, params={"expected_updated_at": seen["updated_at"]}
    )
    assert r.status_code == 409 and r.json()["current"] == theirs
    assert "ביצים" in by_text(client, people["owner"], shared)
    r = client.delete(
        f"{base}/{seen['id']}", headers=owner, params={"expected_updated_at": theirs["updated_at"]}
    )
    assert r.status_code == 204
    assert "ביצים" not in by_text(client, people["owner"], shared)
    # An item somebody else already removed is a 404, with or without a version.
    assert (
        client.delete(
            f"{base}/{seen['id']}",
            headers=owner,
            params={"expected_updated_at": theirs["updated_at"]},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"{base}/{seen['id']}",
            headers=owner,
            json={"checked": True, "expected_updated_at": theirs["updated_at"]},
        ).status_code
        == 404
    )


def test_the_precondition_is_checked_for_the_viewer_and_stranger_last(
    client, people, shared
) -> None:
    """A 409 body is the item's content: only members who may write get it."""
    item = by_text(client, people["owner"], shared)["חלב"]
    path = f"{API_PATH.format(shared)}/{item['id']}"
    stale = "2020-01-01T00:00:00+00:00"
    for who, status in (("viewer", 403), ("stranger", 404)):
        r = client.patch(
            path, headers=h(people[who]), json={"checked": True, "expected_updated_at": stale}
        )
        assert r.status_code == status and "current" not in r.text
        r = client.delete(path, headers=h(people[who]), params={"expected_updated_at": stale})
        assert r.status_code == status and "current" not in r.text


# --- the trigger -------------------------------------------------------------------------------


def test_updated_at_is_written_by_the_trigger_only(db, people) -> None:
    owner = people["owner"]
    lid = db.execute(
        "INSERT INTO lists (user_id, name) VALUES (%s, 'x') RETURNING id", (owner,)
    ).fetchone()[0]
    forged = "2000-01-01T00:00:00+00:00"
    iid, born = db.execute(
        "INSERT INTO list_items (list_id, user_id, input_text, updated_at)"
        " VALUES (%s, %s, 'חלב', %s) RETURNING id, updated_at",
        (lid, owner, forged),
    ).fetchone()
    assert born.year >= 2026  # an INSERT cannot back-date a row

    def version() -> datetime:
        return db.execute("SELECT updated_at FROM list_items WHERE id = %s", (iid,)).fetchone()[0]

    # An UPDATE that changes nothing keeps the version, whatever the statement says.
    db.execute("UPDATE list_items SET quantity = quantity WHERE id = %s", (iid,))
    assert version() == born
    db.execute("UPDATE list_items SET updated_at = %s WHERE id = %s", (forged, iid))
    assert version() == born
    # A real change moves it forward, and a forged value next to it is ignored.
    db.execute("UPDATE list_items SET checked = true, updated_at = %s WHERE id = %s", (forged, iid))
    second = version()
    assert second > born
    db.execute("UPDATE list_items SET checked = false WHERE id = %s", (iid,))
    third = version()
    assert third > second
    # Even a forged future value is replaced by the real time.
    db.execute(
        "UPDATE list_items SET quantity = 3, updated_at = now() + interval '1 day' WHERE id = %s",
        (iid,),
    )
    assert version() < db.execute("SELECT now() + interval '1 hour'").fetchone()[0]


# --- PUT keeps ids -----------------------------------------------------------------------------


def put_body(items: list[dict], name: str = "משפחה") -> dict:
    return {"name": name, "is_recurring": False, "items": items}


def test_put_keeps_the_ids_of_the_items_it_names_and_only_touches_what_changed(
    client, people, shared
) -> None:
    owner = h(people["owner"])
    before = items_of(client, people["owner"], shared)
    milk, bread, eggs = before
    body = put_body(
        [
            {"id": milk["id"], "input_text": "חלב", "quantity": 2},  # unchanged
            {"id": bread["id"], "input_text": "לחם", "quantity": 1, "checked": True},  # ticked
            {"input_text": "גבינה"},  # new
        ]
    )
    r = client.put(f"/me/lists/{shared}", headers=owner, json=body)
    assert r.status_code == 200, r.text
    after = r.json()["items"]
    assert [i["input_text"] for i in after] == ["חלב", "לחם", "גבינה"]
    assert [i["id"] for i in after][:2] == [milk["id"], bread["id"]]  # same rows, same ids
    assert after[2]["id"] not in {milk["id"], bread["id"], eggs["id"]}  # a new row, a new id
    assert after[0]["updated_at"] == milk["updated_at"]  # nothing changed: not touched
    assert after[1]["updated_at"] != bread["updated_at"] and after[1]["checked"] is True
    assert eggs["id"] not in [i["id"] for i in after]  # not named: deleted
    assert [i["sort"] for i in after] == [0, 1, 2]


def test_put_reorders_without_changing_ids_and_a_repeat_is_a_no_op(client, people, shared) -> None:
    owner = h(people["owner"])
    milk, bread, eggs = items_of(client, people["owner"], shared)

    def full(it: dict) -> dict:
        return {"id": it["id"], "input_text": it["input_text"], "quantity": float(it["quantity"])}

    r = client.put(
        f"/me/lists/{shared}", headers=owner, json=put_body([full(eggs), full(milk), full(bread)])
    )
    after = r.json()["items"]
    assert [i["id"] for i in after] == [eggs["id"], milk["id"], bread["id"]]
    again = client.put(
        f"/me/lists/{shared}", headers=owner, json=put_body([full(eggs), full(milk), full(bread)])
    ).json()["items"]
    assert again == after  # versions included: the second PUT wrote nothing


def test_put_with_an_id_this_list_does_not_have_adds_an_item_and_touches_no_other_list(
    client, db, people, shared
) -> None:
    other = client.post(
        "/me/lists",
        headers=h(people["stranger"]),
        json={"name": "פרטי", "items": [{"input_text": "סוד"}]},
    ).json()
    secret = other["items"][0]
    r = client.put(
        f"/me/lists/{shared}",
        headers=h(people["owner"]),
        json=put_body(
            [{"id": secret["id"], "input_text": "נחטף", "quantity": 9}, {"id": 987654321}]
        ),
    )
    assert r.status_code == 200, r.text
    ids = [i["id"] for i in r.json()["items"]]
    assert secret["id"] not in ids and 987654321 not in ids and len(ids) == 2
    assert items_of(client, people["stranger"], other["id"]) == [secret]  # untouched, same version
    row = db.execute("SELECT list_id FROM list_items WHERE id = %s", (secret["id"],)).fetchone()
    assert row[0] == other["id"]


def test_put_refuses_the_same_id_twice_and_changes_nothing(client, people, shared) -> None:
    before = items_of(client, people["owner"], shared)
    r = client.put(
        f"/me/lists/{shared}",
        headers=h(people["owner"]),
        json=put_body([{"id": before[0]["id"]}, {"id": before[0]["id"], "input_text": "x"}]),
    )
    assert r.status_code == 422
    assert items_of(client, people["owner"], shared) == before


def test_put_stays_owner_only_and_keeps_an_editors_items_author(client, db, people, shared) -> None:
    added = client.post(
        API_PATH.format(shared), headers=h(people["editor"]), json={"input_text": "מהעורך"}
    ).json()
    for who, status in (("editor", 404), ("viewer", 404), ("stranger", 404)):
        r = client.put(f"/me/lists/{shared}", headers=h(people[who]), json=put_body([]))
        assert r.status_code == status
    assert len(items_of(client, people["owner"], shared)) == 4
    items = [
        {"id": i["id"], "input_text": i["input_text"], "quantity": float(i["quantity"])}
        for i in items_of(client, people["owner"], shared)
    ]
    assert (
        client.put(
            f"/me/lists/{shared}", headers=h(people["owner"]), json=put_body(items)
        ).status_code
        == 200
    )
    row = db.execute("SELECT user_id FROM list_items WHERE id = %s", (added["id"],)).fetchone()
    assert row[0] == people["editor"]  # the owner's PUT did not take the item over


def test_put_and_create_accept_what_the_api_sends_back(client, people, shared) -> None:
    """A client that echoes the items it read (with ids) is fine; `updated_at` and `sort` are not
    inputs."""
    owner = h(people["owner"])
    items = items_of(client, people["owner"], shared)
    echoed = [{k: v for k, v in i.items() if k not in ("sort", "updated_at")} for i in items]
    assert (
        client.put(f"/me/lists/{shared}", headers=owner, json=put_body(echoed)).status_code == 200
    )
    r = client.post("/me/lists", headers=owner, json=put_body(echoed, name="עותק"))
    assert r.status_code == 201
    assert {i["id"] for i in r.json()["items"]}.isdisjoint({i["id"] for i in items})
    with_version = [{**echoed[0], "updated_at": items[0]["updated_at"]}]
    assert (
        client.put(f"/me/lists/{shared}", headers=owner, json=put_body(with_version)).status_code
        == 422
    )


def test_two_editors_changing_different_items_both_win(client, people, shared) -> None:
    """The bug this exists for: A ticks milk and B ticks bread from the same stale view. With a
    whole-list PUT the second save undid the first; with per-item writes both stay."""
    base = API_PATH.format(shared)
    stale = items_of(client, people["owner"], shared)  # both people hold this view
    milk, bread = stale[0], stale[1]
    assert (
        client.patch(
            f"{base}/{milk['id']}",
            headers=h(people["owner"]),
            json={"checked": True, "expected_updated_at": milk["updated_at"]},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"{base}/{bread['id']}",
            headers=h(people["editor"]),
            json={"checked": True, "expected_updated_at": bread["updated_at"]},
        ).status_code
        == 200
    )
    now = by_text(client, people["owner"], shared)
    assert (now["חלב"]["checked"], now["לחם"]["checked"], now["ביצים"]["checked"]) == (
        True,
        True,
        False,
    )


def test_rls_still_blocks_a_direct_write_by_a_viewer_after_the_new_column(db, people) -> None:
    """The version column did not open anything: a viewer's UPDATE through the app role matches no
    row (see also test_api_security_rls.py)."""
    lid = db.execute(
        "INSERT INTO lists (user_id, name) VALUES (%s, 'x') RETURNING id", (people["owner"],)
    ).fetchone()[0]
    db.execute("INSERT INTO list_items (list_id, user_id) VALUES (%s, %s)", (lid, people["owner"]))
    db.execute(
        "INSERT INTO list_shares (list_id, owner_id, member_id, role, invite_token, accepted_at)"
        " VALUES (%s, %s, %s, 'viewer', %s, now())",
        (lid, people["owner"], people["viewer"], token_hash("v")),
    )
    db.execute("SET LOCAL ROLE smartcart_app")
    db.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(people["viewer"]),))
    assert db.execute("UPDATE list_items SET updated_at = now(), checked = true").rowcount == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute(
            "INSERT INTO list_items (list_id, user_id) VALUES (%s, %s)", (lid, people["viewer"])
        )


# The test transaction is one for the whole test, so a statement the database refuses (a foreign
# key) has to be the last one: in production each request has its own transaction.


def test_patch_with_a_canonical_id_that_does_not_exist_is_a_422(client, people, shared) -> None:
    milk = by_text(client, people["owner"], shared)["חלב"]
    r = client.patch(
        f"{API_PATH.format(shared)}/{milk['id']}",
        headers=h(people["owner"]),
        json={"canonical_id": 987654321},
    )
    assert r.status_code == 422 and "foreign" not in r.text and "list_items" not in r.text


def test_post_with_a_canonical_id_that_does_not_exist_is_a_422(client, people, shared) -> None:
    r = client.post(
        API_PATH.format(shared), headers=h(people["owner"]), json={"canonical_id": 987654321}
    )
    assert r.status_code == 422 and "foreign" not in r.text and "list_items" not in r.text
