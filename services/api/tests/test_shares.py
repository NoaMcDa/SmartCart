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
    pending = client.get(f"/me/lists/{list_id}/members", headers=h(owner)).json()
    assert pending[0]["is_owner"] and pending[1] == {
        "user_id": None, "role": "editor", "accepted_at": None, "is_owner": False}
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
    assert [(m["user_id"], m["is_owner"]) for m in members] == [(str(owner), True), (str(editor), False)]
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
