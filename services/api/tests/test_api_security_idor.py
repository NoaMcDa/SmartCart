"""Cross-user access through the API: every route that takes an id scopes to the caller.

For each resource user B owns something and users A (a stranger) and M (a member of one of B's
lists) try to read, change, delete, revoke or re-use it by id, by token and by an id they made up.
The answer is always a 404 (never a 200 with B's data, never a 403 that confirms the id exists) and
B's data is unchanged afterwards. The database-level matrix is in ``test_api_security_rls.py``.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from api_world import World, make_token

pytestmark = pytest.mark.db


def h(uid) -> dict:
    return {"Authorization": f"Bearer {make_token(uid)}"}


@pytest.fixture
def people(db) -> dict[str, uuid.UUID]:
    p = {k: uuid.uuid4() for k in ("a", "b", "m")}  # stranger, owner, member
    db.execute("INSERT INTO auth.users (id) SELECT unnest(%s::uuid[])", (list(p.values()),))
    return p


LIST = {"name": "הרשימה של B", "items": [{"input_text": "חלב", "quantity": 2}]}
SPEND_BODY = {
    "date": "2026-10-01",
    "store_id": 1,
    "store_name": "x",
    "total": "1",
    "item_count": 1,
    "plan": "single",
}


# --- lists ----------------------------------------------------------------------------------------


def test_lists_are_invisible_and_immutable_to_a_stranger(client, people) -> None:
    a, b = people["a"], people["b"]
    lid = client.post("/me/lists", json=LIST, headers=h(b)).json()["id"]
    assert client.get(f"/me/lists/{lid}", headers=h(a)).status_code == 404
    taken = {"name": "taken", "items": []}
    assert client.put(f"/me/lists/{lid}", json=taken, headers=h(a)).status_code == 404
    assert client.delete(f"/me/lists/{lid}", headers=h(a)).status_code == 404
    assert client.get("/me/lists", headers=h(a)).json() == []
    assert client.get("/me/shared-lists", headers=h(a)).json() == []
    mine = client.get(f"/me/lists/{lid}", headers=h(b)).json()
    assert mine["name"] == LIST["name"] and len(mine["items"]) == 1


ID_ROUTES = [
    ("GET", "/me/lists/{i}", None),
    ("PUT", "/me/lists/{i}", {"name": "x", "items": []}),
    ("DELETE", "/me/lists/{i}", None),
    ("GET", "/me/lists/{i}/members", None),
    ("POST", "/me/lists/{i}/share", {"role": "viewer"}),
    ("DELETE", "/me/lists/{i}/shares/{i}", None),
    ("PUT", "/me/spend/{i}", SPEND_BODY),
    ("DELETE", "/me/spend/{i}", None),
    ("PUT", "/me/alerts/{i}", {"canonical_id": 1, "threshold_unit_price": "1"}),
    ("DELETE", "/me/alerts/{i}", None),
]


@pytest.mark.parametrize("bad_id", ["0", "-1", "99999999999999999999", "9" * 40])
@pytest.mark.parametrize(("method", "path", "body"), ID_ROUTES)
def test_made_up_ids_are_404_or_422_never_500(client, people, method, path, body, bad_id) -> None:
    # one request per test: a refused value aborts the (shared, test-wide) transaction, which in
    # production is the one request's own
    r = client.request(method, path.format(i=bad_id), json=body, headers=h(people["a"]))
    assert r.status_code in (404, 422), (method, path, r.status_code, r.text)
    assert "psycopg" not in r.text and "SELECT" not in r.text


# --- shares, members, share_id --------------------------------------------------------------------


@pytest.fixture
def shared(client, people):
    """B's list, shared with M (accepted), plus a second pending invite and a second list."""
    b, m = people["b"], people["m"]
    lid = client.post("/me/lists", json=LIST, headers=h(b)).json()["id"]
    invite = client.post(f"/me/lists/{lid}/share", json={"role": "editor"}, headers=h(b)).json()
    assert client.post(f"/lists/accept/{invite['token']}", headers=h(m)).status_code == 200
    pending = client.post(f"/me/lists/{lid}/share", json={"role": "viewer"}, headers=h(b)).json()
    other = client.post("/me/lists", json={"name": "second", "items": []}, headers=h(b)).json()
    return {"list": lid, "other": other["id"], "invite": invite, "pending": pending}


def _members(client, uid, lid):
    return client.get(f"/me/lists/{lid}/members", headers=h(uid))


def test_a_stranger_cannot_share_or_read_members_of_another_users_list(
    client, people, shared
) -> None:
    a, lid = people["a"], shared["list"]
    r = client.post(f"/me/lists/{lid}/share", json={"role": "editor"}, headers=h(a))
    assert r.status_code == 404
    assert _members(client, a, lid).status_code == 404


def test_a_member_cannot_share_manage_or_see_other_invites(client, people, shared) -> None:
    m, b, lid = people["m"], people["b"], shared["list"]
    r = client.post(f"/me/lists/{lid}/share", json={"role": "editor"}, headers=h(m))
    assert r.status_code == 404
    seen = _members(client, m, lid).json()
    # the owner and the member themselves; the pending invite (somebody else's link) is not listed
    assert {x["user_id"] for x in seen} == {str(b), str(m)}
    assert len(seen) == 2
    # a member cannot rename or delete the list either
    rename = {"name": "mine", "items": []}
    assert client.put(f"/me/lists/{lid}", json=rename, headers=h(m)).status_code == 404
    assert client.delete(f"/me/lists/{lid}", headers=h(m)).status_code == 404
    assert client.get(f"/me/lists/{lid}", headers=h(m)).json()["name"] == LIST["name"]


def test_share_id_revocation_is_owner_and_list_scoped(client, db, people, shared) -> None:
    a, b, m = people["a"], people["b"], people["m"]
    lid, other = shared["list"], shared["other"]
    shares = [x for x in _members(client, b, lid).json() if x["share_id"] is not None]
    sid = next(x["share_id"] for x in shares if x["user_id"] == str(m))
    pending_sid = next(x["share_id"] for x in shares if x["user_id"] is None)

    def rows() -> int:
        return db.execute("SELECT count(*) FROM list_shares").fetchone()[0]

    before = rows()
    # a stranger, with the right list id and with their own list's id
    assert client.delete(f"/me/lists/{lid}/shares/{sid}", headers=h(a)).status_code == 404
    mine = client.post("/me/lists", json={"name": "mine", "items": []}, headers=h(a)).json()["id"]
    assert client.delete(f"/me/lists/{mine}/shares/{sid}", headers=h(a)).status_code == 404
    # the member cannot remove themselves through the owner endpoint, nor the pending invite
    assert client.delete(f"/me/lists/{lid}/shares/{sid}", headers=h(m)).status_code == 404
    assert client.delete(f"/me/lists/{lid}/shares/{pending_sid}", headers=h(m)).status_code == 404
    # the owner with the wrong list id (a list of theirs the share does not belong to)
    assert client.delete(f"/me/lists/{other}/shares/{sid}", headers=h(b)).status_code == 404
    assert rows() == before
    # by token and by member id as a stranger / member
    token = shared["pending"]["token"]
    for who in (a, m):
        assert client.delete(f"/me/lists/{lid}/share/{token}", headers=h(who)).status_code == 404
        assert client.delete(f"/me/lists/{lid}/members/{m}", headers=h(who)).status_code == 404
    assert rows() == before
    # the owner can
    assert client.delete(f"/me/lists/{lid}/shares/{sid}", headers=h(b)).status_code == 204
    assert client.get(f"/me/lists/{lid}", headers=h(m)).status_code == 404  # access ended with it


def test_invite_tokens_are_single_use_hashed_and_not_guessable(client, db, people, shared) -> None:
    a = people["a"]
    token = shared["invite"]["token"]
    assert len(token) >= 40
    stored = [r[0] for r in db.execute("SELECT invite_token FROM list_shares").fetchall()]
    assert token not in stored and shared["pending"]["token"] not in stored
    assert all(len(s) == 64 for s in stored)  # a SHA-256 hex digest
    # M already accepted it: a stranger holding the same link is refused
    assert client.post(f"/lists/accept/{token}", headers=h(a)).status_code == 409
    # a guess is a 404, whatever it looks like
    for guess in (token[:-1], token + "x", "x" * 43, "1", "..", "%00"):
        assert client.post(f"/lists/accept/{guess}", headers=h(a)).status_code in (404, 422), guess
    # the stranger got nothing from the failures
    assert client.get("/me/shared-lists", headers=h(a)).json() == []


def test_an_expired_and_a_revoked_invite_do_not_work(client, db, people, shared) -> None:
    a, b, lid = people["a"], people["b"], shared["list"]
    token = shared["pending"]["token"]
    db.execute(
        "UPDATE list_shares SET expires_at = now() - interval '1 minute' WHERE member_id IS NULL"
    )
    assert client.post(f"/lists/accept/{token}", headers=h(a)).status_code == 410
    fresh = client.post(f"/me/lists/{lid}/share", json={"role": "viewer"}, headers=h(b)).json()
    assert client.delete(f"/me/lists/{lid}/share/{fresh['token']}", headers=h(b)).status_code == 204
    assert client.post(f"/lists/accept/{fresh['token']}", headers=h(a)).status_code == 404


def test_a_viewer_invite_never_gives_write_access(client, people, shared) -> None:
    a, lid = people["a"], shared["list"]
    got = client.post(f"/lists/accept/{shared['pending']['token']}", headers=h(a)).json()
    assert got["role"] == "viewer" and got["shared"] is True
    rename = {"name": "x", "items": []}
    assert client.put(f"/me/lists/{lid}", json=rename, headers=h(a)).status_code == 404


def test_a_list_has_a_ceiling_on_invites(client, people, shared, monkeypatch) -> None:
    from smartcart_api.routes import shares

    monkeypatch.setattr(shares, "MAX_SHARES_PER_LIST", 3)  # two rows exist already
    b, lid = people["b"], shared["list"]
    assert client.post(f"/me/lists/{lid}/share", json={}, headers=h(b)).status_code == 201
    assert client.post(f"/me/lists/{lid}/share", json={}, headers=h(b)).status_code == 403


# --- spend ----------------------------------------------------------------------------------------


def _spend(world: World, **over) -> dict:
    return {
        "date": date(2026, 10, 5).isoformat(),
        "store_id": next(iter(world.stores.values())),
        "store_name": "סניף",
        "total": "120.50",
        "item_count": 12,
        "plan": "single",
        **over,
    }


def test_spend_entries_are_private(client, world: World, people) -> None:
    a, b = people["a"], people["b"]
    cid = str(uuid.uuid4())
    entry = client.post("/me/spend", json=_spend(world, client_id=cid), headers=h(b)).json()
    eid = entry["id"]
    assert client.get("/me/spend?month=2026-10", headers=h(a)).json()["entries"] == []
    assert client.get("/me/spend/export", headers=h(a)).json()["entries"] == []
    put = client.put(f"/me/spend/{eid}", json=_spend(world, total="1"), headers=h(a))
    assert put.status_code == 404
    assert client.delete(f"/me/spend/{eid}", headers=h(a)).status_code == 404
    # re-using B's client_id is not a way to read B's entry: A gets A's own new row
    mine = client.post("/me/spend", json=_spend(world, client_id=cid, total="5"), headers=h(a))
    assert mine.status_code == 201 and mine.json()["id"] != eid and mine.json()["total"] == "5.00"
    again = client.post("/me/spend", json=_spend(world, client_id=cid, total="999"), headers=h(b))
    assert again.status_code == 200 and again.json()["id"] == eid
    assert again.json()["total"] == "120.50"
    assert client.get("/me/spend?month=2026-10", headers=h(b)).json()["total"] == "120.50"


def test_spend_has_a_ceiling_per_user(client, world: World, people, monkeypatch) -> None:
    from smartcart_api.routes import spend

    monkeypatch.setattr(spend, "MAX_SPEND_ENTRIES", 2)
    a = people["a"]
    assert client.post("/me/spend", json=_spend(world), headers=h(a)).status_code == 201
    assert client.post("/me/spend", json=_spend(world), headers=h(a)).status_code == 201
    assert client.post("/me/spend", json=_spend(world), headers=h(a)).status_code == 403


# --- alerts and push ------------------------------------------------------------------------------


def test_alerts_are_private_and_use_the_callers_own_location(client, world: World, people) -> None:
    a, b = people["a"], people["b"]
    for uid, lat in ((a, 31.1), (b, 32.2)):
        client.put(
            "/me/profile",
            json={"neighborhood_lat": lat, "neighborhood_lon": 34.8, "consent_location": True},
            headers=h(uid),
        )
    body = {"canonical_id": world.canon["milk3"], "threshold_unit_price": "5"}
    alert = client.post("/me/alerts", json=body, headers=h(b)).json()
    assert client.get("/me/alerts", headers=h(a)).json() == []
    cheap = {**body, "threshold_unit_price": "0.01"}
    assert client.put(f"/me/alerts/{alert['id']}", json=cheap, headers=h(a)).status_code == 404
    assert client.delete(f"/me/alerts/{alert['id']}", headers=h(a)).status_code == 404
    mine = client.post("/me/alerts", json=body, headers=h(a)).json()
    assert mine["id"] != alert["id"]
    assert client.get("/me/alerts", headers=h(b)).json()[0]["threshold_unit_price"] == "5"


def test_a_push_subscription_cannot_be_removed_by_another_user(client, db, people) -> None:
    a, b = people["a"], people["b"]
    endpoint = "https://push.example.com/sub/" + "q" * 40
    sub = {"endpoint": endpoint, "p256dh": "k" * 20, "auth": "a" * 10}
    assert client.post("/me/push-subscriptions", json=sub, headers=h(b)).status_code == 201
    r = client.delete("/me/push-subscriptions", params={"endpoint": endpoint}, headers=h(a))
    assert r.status_code == 204
    owner = db.execute("SELECT user_id FROM push_subscriptions WHERE endpoint = %s", (endpoint,))
    assert owner.fetchone()[0] == b


# --- profile and body-supplied identities ---------------------------------------------------------


def test_a_body_cannot_name_another_user(client, people, db) -> None:
    a, b = people["a"], people["b"]
    for path, method, body in (
        ("/me/profile", "PUT", {"user_id": str(b), "radius_m": 1000}),
        ("/me/lists", "POST", {"name": "x", "items": [], "user_id": str(b)}),
        ("/me/lists", "POST", {"name": "x", "items": [{"input_text": "y", "user_id": str(b)}]}),
        ("/me/alerts", "POST", {"canonical_id": 1, "threshold_unit_price": "1", "user_id": str(b)}),
        ("/me/spend", "POST", {"user_id": str(b)}),
    ):
        r = client.request(method, path, json=body, headers=h(a))
        assert r.status_code == 422, (path, r.text)
    assert db.execute("SELECT count(*) FROM profiles WHERE user_id = %s", (b,)).fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM lists WHERE user_id = %s", (b,)).fetchone()[0] == 0


def test_profiles_are_private(client, people) -> None:
    a, b = people["a"], people["b"]
    client.put("/me/profile", json={"radius_m": 1234, "clubs": ["x"]}, headers=h(b))
    got = client.get("/me/profile", headers=h(a)).json()
    assert got["exists"] is False and got["user_id"] == str(a) and got["clubs"] == []


def test_a_user_has_a_ceiling_on_lists_and_devices(client, people, monkeypatch) -> None:
    from smartcart_api.routes import alerts, me

    monkeypatch.setattr(me, "MAX_LISTS_PER_USER", 2)
    monkeypatch.setattr(alerts, "MAX_PUSH_SUBSCRIPTIONS", 2)
    a = people["a"]
    new = {"name": "x", "items": []}
    assert client.post("/me/lists", json=new, headers=h(a)).status_code == 201
    assert client.post("/me/lists", json=new, headers=h(a)).status_code == 201
    assert client.post("/me/lists", json=new, headers=h(a)).status_code == 403
    for n in range(2):
        sub = {"endpoint": f"https://push.example.com/{n}", "p256dh": "k", "auth": "a"}
        assert client.post("/me/push-subscriptions", json=sub, headers=h(a)).status_code == 201
    third = {"endpoint": "https://push.example.com/3", "p256dh": "k", "auth": "a"}
    assert client.post("/me/push-subscriptions", json=third, headers=h(a)).status_code == 403
    # re-registering a device that is already registered is an update, not a new device
    again = {"endpoint": "https://push.example.com/0", "p256dh": "k2", "auth": "a"}
    assert client.post("/me/push-subscriptions", json=again, headers=h(a)).status_code == 201


# --- beta -----------------------------------------------------------------------------------------


def test_beta_membership_feedback_and_leaving_are_per_user(client, db, people) -> None:
    a, b = people["a"], people["b"]
    db.execute(
        "INSERT INTO beta_invites (code, segment, max_uses) VALUES ('IDOR-TEST-1', 'kosher', 3)"
    )
    assert client.post("/beta/join", json={"code": "IDOR-TEST-1"}, headers=h(b)).status_code == 200
    assert client.get("/me/beta", headers=h(a)).json() == {"member": False, "segment": None}
    # not a member: no feedback, and leaving does nothing to B
    nope = client.post("/beta/feedback", json={"rating": 1, "text": "x"}, headers=h(a))
    assert nope.status_code == 403
    assert client.delete("/me/beta", headers=h(a)).status_code == 200
    assert client.get("/me/beta", headers=h(b)).json()["member"] is True
    # feedback is stored with the segment only: nothing ties it to B
    ok = client.post("/beta/feedback", json={"rating": 5, "text": "great"}, headers=h(b))
    assert ok.status_code == 201
    cols = {
        r[0]
        for r in db.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'beta_feedback'"
        ).fetchall()
    }
    assert not {"user_id", "member_id", "owner_id"} & cols
    assert db.execute("SELECT segment, body FROM beta_feedback").fetchall() == [("kosher", "great")]


def test_a_used_up_code_does_not_reveal_who_used_it(client, db, people) -> None:
    a, b = people["a"], people["b"]
    db.execute(
        "INSERT INTO beta_invites (code, segment, max_uses) VALUES ('IDOR-TEST-2', 'general', 1)"
    )
    assert client.post("/beta/join", json={"code": "IDOR-TEST-2"}, headers=h(b)).status_code == 200
    r = client.post("/beta/join", json={"code": "IDOR-TEST-2"}, headers=h(a))
    assert r.status_code == 410 and str(b) not in r.text and "general" not in r.text


# --- feedback: the caller is the token, not the body ----------------------------------------------


def test_feedback_records_the_token_user_only(client, db, world: World, people) -> None:
    a, b = people["a"], people["b"]
    gap = {"store_id": next(iter(world.stores.values())), "note": "x"}
    forged = client.post("/feedback/gap", json={**gap, "user_id": str(b)}, headers=h(a))
    assert forged.status_code == 422
    assert client.post("/feedback/gap", json=gap, headers=h(a)).status_code == 200
    assert db.execute("SELECT user_id FROM gap_reports").fetchone()[0] == a
