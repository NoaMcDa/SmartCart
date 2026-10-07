"""Shared lists (issue #34): invite, accept, members, revoke; row-level security through
``smartcart_app`` (SET LOCAL ROLE, as in test_rls_contract.py) and through the API."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from api_world import make_token

from smartcart_api.routes.shares import token_hash

pytestmark = pytest.mark.db

APP_ROLE = "smartcart_app"


def h(user_id) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


def as_user(conn: psycopg.Connection, user_id: uuid.UUID | None) -> None:
    conn.execute(f"SET LOCAL ROLE {APP_ROLE}")
    conn.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(user_id) if user_id else "",))


def as_owner(conn: psycopg.Connection) -> None:
    conn.execute("RESET ROLE")


@pytest.fixture
def people(db) -> dict[str, uuid.UUID]:
    p = {k: uuid.uuid4() for k in ("owner", "editor", "viewer", "stranger")}
    db.execute("INSERT INTO auth.users (id) SELECT unnest(%s::uuid[])", (list(p.values()),))
    return p


@pytest.fixture
def shared(db, people) -> int:
    """The owner's list with one item, shared with an editor and a viewer (accepted)."""
    as_user(db, people["owner"])
    list_id = db.execute(
        "INSERT INTO lists (user_id, name) VALUES (%s, 'משפחה') RETURNING id", (people["owner"],)
    ).fetchone()[0]
    db.execute("INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'חלב')",
               (list_id, people["owner"]))
    for role in ("editor", "viewer"):
        db.execute(
            "INSERT INTO list_shares (list_id, owner_id, role, invite_token) VALUES (%s, %s, %s, %s)",
            (list_id, people["owner"], role, token_hash(role)),
        )
    as_owner(db)  # accepting runs on the service connection
    for role in ("editor", "viewer"):
        db.execute("UPDATE list_shares SET member_id = %s, accepted_at = now() WHERE invite_token = %s",
                   (people[role], token_hash(role)))
    return list_id


def items(db) -> list[str]:
    return [r[0] for r in db.execute("SELECT input_text FROM list_items ORDER BY id").fetchall()]


# --- row-level security (SQL, through smartcart_app) ------------------------------------------


def test_members_read_the_list_and_its_items(db, people, shared) -> None:
    for who in ("owner", "editor", "viewer"):
        as_user(db, people[who])
        assert [r[0] for r in db.execute("SELECT id FROM lists").fetchall()] == [shared], who
        assert items(db) == ["חלב"], who


def test_editor_adds_and_edits_items_and_the_owner_sees_them(db, people, shared) -> None:
    as_user(db, people["editor"])
    db.execute("INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'לחם')",
               (shared, people["editor"]))
    assert db.execute("UPDATE list_items SET quantity = 2 WHERE input_text = 'חלב'").rowcount == 1
    # An editor still cannot forge another user as the author of a row.
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute("INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'x')",
                   (shared, people["owner"]))
    as_user(db, people["owner"])
    assert items(db) == ["חלב", "לחם"]
    # The editor cannot rename or delete the list itself (owner-only).
    as_user(db, people["editor"])
    assert db.execute("UPDATE lists SET name = 'x' WHERE id = %s", (shared,)).rowcount == 0
    assert db.execute("DELETE FROM lists WHERE id = %s", (shared,)).rowcount == 0


def test_viewer_cannot_write(db, people, shared) -> None:
    as_user(db, people["viewer"])
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute("INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'x')",
                   (shared, people["viewer"]))
    assert db.execute("UPDATE list_items SET quantity = 5").rowcount == 0
    assert db.execute("DELETE FROM list_items").rowcount == 0
    as_user(db, people["owner"])
    assert items(db) == ["חלב"]


def test_stranger_sees_and_writes_nothing(db, people, shared) -> None:
    as_user(db, people["stranger"])
    assert db.execute("SELECT count(*) FROM lists").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM list_items").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM list_shares").fetchone()[0] == 0
    # The phase 1 policy let anyone add a row to any list under their own user id; no longer.
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute("INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'x')",
                   (shared, people["stranger"]))
    # A stranger cannot join by writing a share row for themselves.
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute(
            "INSERT INTO list_shares (list_id, owner_id, member_id, role, invite_token, accepted_at)"
            " VALUES (%s, %s, %s, 'editor', 'forged', now())",
            (shared, people["owner"], people["stranger"]),
        )
    assert db.execute("UPDATE list_shares SET member_id = %s", (people["stranger"],)).rowcount == 0


def test_member_sees_only_their_own_share_row(db, people, shared) -> None:
    as_user(db, people["viewer"])
    rows = db.execute("SELECT member_id FROM list_shares").fetchall()
    assert rows == [(people["viewer"],)]
    as_user(db, people["owner"])
    assert db.execute("SELECT count(*) FROM list_shares").fetchone()[0] == 2


def test_owner_revokes_and_access_ends_immediately(db, people, shared) -> None:
    as_user(db, people["owner"])
    assert db.execute("DELETE FROM list_shares WHERE member_id = %s", (people["editor"],)).rowcount == 1
    as_user(db, people["editor"])
    assert db.execute("SELECT count(*) FROM lists").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM list_items").fetchone()[0] == 0
    # Members cannot revoke others or themselves out of someone else's share rows.
    as_user(db, people["viewer"])
    assert db.execute("DELETE FROM list_shares").rowcount == 0


def test_members_never_see_each_others_profile_or_preferences(db, people, shared) -> None:
    as_user(db, people["owner"])
    db.execute("INSERT INTO profiles (user_id, neighborhood_lat, neighborhood_lon, consent_location)"
               " VALUES (%s, 32.08, 34.78, true)", (people["owner"],))
    db.execute("INSERT INTO preferences (user_id, data) VALUES (%s, '{\"x\": 1}')", (people["owner"],))
    for who in ("editor", "viewer"):
        as_user(db, people[who])
        assert db.execute("SELECT count(*) FROM profiles").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM preferences").fetchone()[0] == 0


# --- the API flow ------------------------------------------------------------------------------


def make_list(client, owner) -> int:
    r = client.post("/me/lists", headers=h(owner), json={"name": "בית", "items": [{"input_text": "חלב"}]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_invite_accept_members_and_revoke(client, db, people, monkeypatch) -> None:
    monkeypatch.setenv("API_PUBLIC_WEB_URL", "https://smartcart.example/")
    owner, editor, stranger = people["owner"], people["editor"], people["stranger"]
    list_id = make_list(client, owner)
    r = client.post(f"/me/lists/{list_id}/share", headers=h(owner), json={"role": "editor"})
    assert r.status_code == 201, r.text
    invite = r.json()
    token = invite["token"]
    assert len(token) >= 40 and invite["role"] == "editor"
    assert invite["url"] == f"https://smartcart.example/lists/accept/{token}"
    # Only the hash is stored.
    assert db.execute("SELECT count(*) FROM list_shares WHERE invite_token = %s", (token,)).fetchone()[0] == 0
    share_id = db.execute("SELECT id FROM list_shares WHERE invite_token = %s",
                          (token_hash(token),)).fetchone()[0]
    pending = client.get(f"/me/lists/{list_id}/members", headers=h(owner)).json()
    assert pending[0]["is_owner"] and pending[0]["share_id"] is None
    assert pending[1] == {
        "user_id": None, "role": "editor", "accepted_at": None, "is_owner": False,
        "share_id": share_id}
    # Not shared yet: the editor cannot see it.
    assert client.get(f"/me/lists/{list_id}/members", headers=h(editor)).status_code == 404

    r = client.post(f"/lists/accept/{token}", headers=h(editor))
    assert r.status_code == 200, r.text
    assert r.json()["id"] == list_id and [i["input_text"] for i in r.json()["items"]] == ["חלב"]
    assert client.post(f"/lists/accept/{token}", headers=h(editor)).status_code == 200  # idempotent
    assert client.post(f"/lists/accept/{token}", headers=h(stranger)).status_code == 409  # single use
    shared = client.get("/me/shared-lists", headers=h(editor)).json()
    assert [s["id"] for s in shared] == [list_id]
    assert client.get("/me/shared-lists", headers=h(stranger)).json() == []
    members = client.get(f"/me/lists/{list_id}/members", headers=h(editor)).json()
    assert [(m["user_id"], m["is_owner"], m["share_id"]) for m in members] == [
        (str(owner), True, None), (str(editor), False, share_id)]
    # Only the owner revokes; then the editor loses access at once.
    assert client.delete(f"/me/lists/{list_id}/share/{token}", headers=h(editor)).status_code == 404
    assert client.delete(f"/me/lists/{list_id}/share/{token}", headers=h(owner)).status_code == 204
    assert client.get("/me/shared-lists", headers=h(editor)).json() == []
    assert client.post(f"/lists/accept/{token}", headers=h(editor)).status_code == 404  # revoked


def test_remove_member_and_owner_only_invites(client, people) -> None:
    owner, viewer, stranger = people["owner"], people["viewer"], people["stranger"]
    list_id = make_list(client, owner)
    assert client.post(f"/me/lists/{list_id}/share", headers=h(stranger), json={}).status_code == 404
    token = client.post(f"/me/lists/{list_id}/share", headers=h(owner), json={"role": "viewer"}).json()["token"]
    assert client.post(f"/lists/accept/{token}", headers=h(viewer)).status_code == 200
    assert client.delete(f"/me/lists/{list_id}/members/{viewer}", headers=h(viewer)).status_code == 404
    assert client.delete(f"/me/lists/{list_id}/members/{viewer}", headers=h(owner)).status_code == 204
    assert client.get("/me/shared-lists", headers=h(viewer)).json() == []


def test_expired_invite_cannot_be_used(client, db, people) -> None:
    owner, editor = people["owner"], people["editor"]
    list_id = make_list(client, owner)
    token = client.post(f"/me/lists/{list_id}/share", headers=h(owner), json={}).json()["token"]
    db.execute("UPDATE list_shares SET expires_at = %s WHERE invite_token = %s",
               (datetime.now(UTC) - timedelta(minutes=1), token_hash(token)))
    assert client.post(f"/lists/accept/{token}", headers=h(editor)).status_code == 410
    assert client.post("/lists/accept/not-a-token", headers=h(editor)).status_code == 404
    assert client.post(f"/lists/accept/{token}").status_code == 401


def test_sharing_flag_gates_invites(client, people, monkeypatch) -> None:
    list_id = make_list(client, people["owner"])
    monkeypatch.setenv("API_FAMILY_SHARING", "0")
    assert client.post(f"/me/lists/{list_id}/share", headers=h(people["owner"]), json={}).status_code == 403


def test_revoke_a_pending_invite_and_remove_a_member_by_share_id(client, db, people) -> None:
    owner, editor, viewer, stranger = (people[k] for k in ("owner", "editor", "viewer", "stranger"))
    list_id = make_list(client, owner)
    other_list = make_list(client, stranger)
    pending_token = client.post(f"/me/lists/{list_id}/share", headers=h(owner),
                                json={"role": "editor"}).json()["token"]
    member_token = client.post(f"/me/lists/{list_id}/share", headers=h(owner),
                               json={"role": "viewer"}).json()["token"]
    assert client.post(f"/lists/accept/{member_token}", headers=h(viewer)).status_code == 200
    members = client.get(f"/me/lists/{list_id}/members", headers=h(owner)).json()
    ids = {m["user_id"]: m["share_id"] for m in members if not m["is_owner"]}
    want = dict(db.execute(
        "SELECT invite_token, id FROM list_shares WHERE list_id = %s", (list_id,)).fetchall())
    assert ids == {None: want[token_hash(pending_token)], str(viewer): want[token_hash(member_token)]}
    pending_id, member_id = ids[None], ids[str(viewer)]

    # Owner only, and only within the list named in the path.
    for who in (editor, viewer, stranger):
        assert client.delete(f"/me/lists/{list_id}/shares/{pending_id}", headers=h(who)).status_code == 404
    assert client.delete(f"/me/lists/{other_list}/shares/{pending_id}", headers=h(stranger)).status_code == 404
    assert client.delete(f"/me/lists/{list_id}/shares/999999999", headers=h(owner)).status_code == 404
    assert client.delete(f"/me/lists/{list_id}/shares/{pending_id}").status_code == 401

    # The pending invite: revoked, and its link no longer works.
    assert client.delete(f"/me/lists/{list_id}/shares/{pending_id}", headers=h(owner)).status_code == 204
    assert client.delete(f"/me/lists/{list_id}/shares/{pending_id}", headers=h(owner)).status_code == 404
    assert client.post(f"/lists/accept/{pending_token}", headers=h(editor)).status_code == 404
    # The member: removed, access ends at once.
    assert [s["id"] for s in client.get("/me/shared-lists", headers=h(viewer)).json()] == [list_id]
    assert client.delete(f"/me/lists/{list_id}/shares/{member_id}", headers=h(owner)).status_code == 204
    assert client.get("/me/shared-lists", headers=h(viewer)).json() == []
    assert client.get(f"/me/lists/{list_id}", headers=h(viewer)).status_code == 404
    members = client.get(f"/me/lists/{list_id}/members", headers=h(owner)).json()
    assert [m["is_owner"] for m in members] == [True]


def test_me_lists_includes_accepted_shared_lists(client, people) -> None:
    owner, editor, viewer, stranger = (people[k] for k in ("owner", "editor", "viewer", "stranger"))
    family = make_list(client, owner)
    mine = make_list(client, editor)
    for who, role in ((editor, "editor"), (viewer, "viewer")):
        token = client.post(f"/me/lists/{family}/share", headers=h(owner),
                            json={"role": role}).json()["token"]
        assert client.post(f"/lists/accept/{token}", headers=h(who)).status_code == 200
    # A pending invite shows the list to nobody else.
    client.post(f"/me/lists/{family}/share", headers=h(owner), json={"role": "editor"})

    def summary(who):
        return [(x["id"], x["shared"], x["role"], [i["input_text"] for i in x["items"]])
                for x in client.get("/me/lists", headers=h(who)).json()]

    assert summary(owner) == [(family, False, "owner", ["חלב"])]
    # Owned lists first, then the shared ones.
    assert summary(editor) == [(mine, False, "owner", ["חלב"]), (family, True, "editor", ["חלב"])]
    assert summary(viewer) == [(family, True, "viewer", ["חלב"])]
    assert summary(stranger) == []
    # One shared list by id; a member cannot replace or delete it (owner only).
    got = client.get(f"/me/lists/{family}", headers=h(viewer)).json()
    assert (got["shared"], got["role"]) == (True, "viewer")
    assert client.put(f"/me/lists/{family}", headers=h(editor), json={"name": "x"}).status_code == 404
    assert client.delete(f"/me/lists/{family}", headers=h(editor)).status_code == 404
    # /me/shared-lists keeps working: the shared ones only, with the same fields.
    shared = client.get("/me/shared-lists", headers=h(editor)).json()
    assert [(x["id"], x["shared"], x["role"]) for x in shared] == [(family, True, "editor")]
    assert client.get("/me/shared-lists", headers=h(owner)).json() == []


def test_checked_flag_round_trips_and_editors_may_tick_items(client, db, people) -> None:
    owner, editor, viewer = people["owner"], people["editor"], people["viewer"]
    body = {"name": "בית", "items": [{"input_text": "חלב", "checked": True}, {"input_text": "לחם"}]}
    r = client.post("/me/lists", headers=h(owner), json=body)
    assert r.status_code == 201, r.text
    list_id = r.json()["id"]
    assert [(i["input_text"], i["checked"]) for i in r.json()["items"]] == [("חלב", True), ("לחם", False)]
    body["items"] = [{"input_text": "חלב", "checked": False}, {"input_text": "לחם", "checked": True}]
    r = client.put(f"/me/lists/{list_id}", headers=h(owner), json=body)
    assert [(i["input_text"], i["checked"]) for i in r.json()["items"]] == [("חלב", False), ("לחם", True)]
    got = client.get(f"/me/lists/{list_id}", headers=h(owner)).json()
    assert [i["checked"] for i in got["items"]] == [False, True]
    assert db.execute("SELECT count(*) FROM list_items WHERE list_id = %s AND checked",
                      (list_id,)).fetchone()[0] == 1
    for who, role in ((editor, "editor"), (viewer, "viewer")):
        token = client.post(f"/me/lists/{list_id}/share", headers=h(owner),
                            json={"role": role}).json()["token"]
        assert client.post(f"/lists/accept/{token}", headers=h(who)).status_code == 200
    # Row-level security, as PostgREST runs it: an editor ticks an item, a viewer cannot.
    as_user(db, editor)
    assert db.execute("UPDATE list_items SET checked = true WHERE list_id = %s AND NOT checked",
                      (list_id,)).rowcount == 1
    as_user(db, viewer)
    assert db.execute("UPDATE list_items SET checked = false WHERE list_id = %s",
                      (list_id,)).rowcount == 0
    as_owner(db)
    got = client.get(f"/me/lists/{list_id}", headers=h(viewer)).json()
    assert [i["checked"] for i in got["items"]] == [True, True]
