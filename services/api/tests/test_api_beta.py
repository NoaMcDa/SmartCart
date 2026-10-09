"""Closed beta: invite codes, membership, feedback and their row-level security (issue #40)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from api_world import make_token

pytestmark = pytest.mark.db


def h(user_id) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


def make_users(db, n: int) -> list[uuid.UUID]:
    ids = [uuid.uuid4() for _ in range(n)]
    for i in ids:
        db.execute("INSERT INTO auth.users (id) VALUES (%s)", (i,))
    return ids


def invite(db, code="KOSH-12345", segment="kosher", max_uses=1, expires_at=None) -> str:
    db.execute(
        "INSERT INTO beta_invites (code, segment, max_uses, expires_at) VALUES (%s, %s, %s, %s)",
        (code, segment, max_uses, expires_at),
    )
    return code


def uses(db, code) -> int:
    return db.execute("SELECT uses FROM beta_invites WHERE code = %s", (code,)).fetchone()[0]


# --- join ------------------------------------------------------------------------------------


def test_joining_creates_a_member_with_the_codes_segment_and_counts_the_use(client, db) -> None:
    (a,) = make_users(db, 1)
    code = invite(db, segment="periphery", max_uses=3)
    assert client.get("/me/beta", headers=h(a)).json() == {"member": False, "segment": None}
    r = client.post("/beta/join", json={"code": code}, headers=h(a))
    assert r.status_code == 200 and r.json() == {"member": True, "segment": "periphery"}
    assert client.get("/me/beta", headers=h(a)).json() == {"member": True, "segment": "periphery"}
    assert uses(db, code) == 1
    row = db.execute("SELECT user_id, code, segment FROM beta_members").fetchone()
    assert row == (a, code, "periphery")


def test_the_code_is_case_and_space_insensitive(client, db) -> None:
    (a,) = make_users(db, 1)
    invite(db, code="GEN-ABCDE")
    r = client.post("/beta/join", json={"code": "gen-abcde"}, headers=h(a))
    assert r.status_code == 200 and r.json()["segment"] == "kosher"


def test_a_code_with_one_place_admits_exactly_one_person(client, db) -> None:
    a, b = make_users(db, 2)
    code = invite(db, max_uses=1)
    assert client.post("/beta/join", json={"code": code}, headers=h(a)).status_code == 200
    r = client.post("/beta/join", json={"code": code}, headers=h(b))
    assert r.status_code == 410 and "used up" in r.json()["detail"]
    assert uses(db, code) == 1
    assert client.get("/me/beta", headers=h(b)).json()["member"] is False


def test_a_code_with_several_places_stops_at_max_uses(client, db) -> None:
    users = make_users(db, 4)
    code = invite(db, max_uses=3)
    statuses = [
        client.post("/beta/join", json={"code": code}, headers=h(u)).status_code for u in users
    ]
    assert statuses == [200, 200, 200, 410]
    assert uses(db, code) == 3
    assert db.execute("SELECT count(*) FROM beta_members").fetchone()[0] == 3


def test_unknown_expired_and_malformed_codes(client, db) -> None:
    (a,) = make_users(db, 1)
    assert client.post("/beta/join", json={"code": "NOPE-00000"}, headers=h(a)).status_code == 404
    old = invite(db, code="OLD-12345", expires_at=datetime.now(UTC) - timedelta(minutes=1))
    r = client.post("/beta/join", json={"code": old}, headers=h(a))
    assert r.status_code == 410 and "expired" in r.json()["detail"]
    assert uses(db, old) == 0
    future = invite(db, code="NEW-12345", expires_at=datetime.now(UTC) + timedelta(days=1))
    assert client.post("/beta/join", json={"code": future}, headers=h(a)).status_code == 200
    assert client.post("/beta/join", json={"code": "ab"}, headers=h(a)).status_code == 422
    assert client.post("/beta/join", json={"code": "a b c d e f"}, headers=h(a)).status_code == 422


def test_joining_again_returns_the_membership_and_uses_no_place(client, db) -> None:
    a, b = make_users(db, 2)
    code = invite(db, max_uses=2)
    other = invite(db, code="GEN-77777", segment="general")
    assert client.post("/beta/join", json={"code": code}, headers=h(a)).status_code == 200
    for c in (code, other):  # even with a different code: one membership per person
        r = client.post("/beta/join", json={"code": c}, headers=h(a))
        assert r.status_code == 200 and r.json()["segment"] == "kosher"
    assert uses(db, code) == 1 and uses(db, other) == 0
    assert client.post("/beta/join", json={"code": code}, headers=h(b)).status_code == 200


def test_joining_needs_a_signed_in_user(client, db) -> None:
    code = invite(db)
    assert client.post("/beta/join", json={"code": code}).status_code == 401
    anon = {"Authorization": f"Bearer {make_token(uuid.uuid4(), role='anon')}"}
    assert client.post("/beta/join", json={"code": code}, headers=anon).status_code == 401
    assert uses(db, code) == 0


def test_a_token_for_a_deleted_account_does_not_take_a_place(client, db) -> None:
    code = invite(db)
    r = client.post("/beta/join", json={"code": code}, headers=h(uuid.uuid4()))
    assert r.status_code == 401
    assert uses(db, code) == 0


# --- leaving and row-level security -----------------------------------------------------------


def test_leaving_deletes_the_member_row_and_is_idempotent(client, db) -> None:
    a, b = make_users(db, 2)
    code = invite(db, max_uses=2)
    client.post("/beta/join", json={"code": code}, headers=h(a))
    client.post("/beta/join", json={"code": code}, headers=h(b))
    assert client.delete("/me/beta", headers=h(a)).json() == {"ok": True, "id": None}
    assert client.get("/me/beta", headers=h(a)).json()["member"] is False
    assert client.get("/me/beta", headers=h(b)).json()["member"] is True  # b is untouched
    assert client.delete("/me/beta", headers=h(a)).status_code == 200
    assert client.delete("/me/beta").status_code == 401
    # the place stays used: a left member does not free the code
    assert uses(db, code) == 2


def test_deleting_the_account_removes_the_membership(client, db) -> None:
    (a,) = make_users(db, 1)
    client.post("/beta/join", json={"code": invite(db)}, headers=h(a))
    db.execute("DELETE FROM auth.users WHERE id = %s", (a,))
    assert db.execute("SELECT count(*) FROM beta_members").fetchone()[0] == 0


def _as_app(db, user_id) -> None:
    db.execute("SET LOCAL ROLE smartcart_app")
    db.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(user_id),))


def test_rls_a_member_reads_only_their_own_row_and_nobody_reads_invites(client, db) -> None:
    a, b = make_users(db, 2)
    code = invite(db, max_uses=2)
    client.post("/beta/join", json={"code": code}, headers=h(a))
    client.post("/beta/join", json={"code": code}, headers=h(b))
    _as_app(db, a)
    assert [r[0] for r in db.execute("SELECT user_id FROM beta_members").fetchall()] == [a]
    for table in ("beta_invites", "beta_feedback"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.transaction():
                db.execute(f"SELECT * FROM {table}")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):  # no way to add oneself
        with db.transaction():
            db.execute(
                "INSERT INTO beta_members (user_id, code, segment) VALUES (%s, %s, 'general')",
                (a, code),
            )
    # deleting someone else's row matches nothing
    assert db.execute("DELETE FROM beta_members WHERE user_id = %s", (b,)).rowcount == 0
    db.execute("RESET ROLE")
    assert db.execute("SELECT count(*) FROM beta_members").fetchone()[0] == 2


def test_rls_no_policy_for_a_caller_without_an_identity(client, db) -> None:
    (a,) = make_users(db, 1)
    client.post("/beta/join", json={"code": invite(db)}, headers=h(a))
    db.execute("SET LOCAL ROLE smartcart_app")
    db.execute("SELECT set_config('request.jwt.claim.sub', '', true)")
    assert db.execute("SELECT count(*) FROM beta_members").fetchone()[0] == 0


# --- feedback --------------------------------------------------------------------------------


def test_members_send_feedback_stored_with_the_segment_and_no_user(client, db) -> None:
    (a,) = make_users(db, 1)
    client.post("/beta/join", json={"code": invite(db, segment="large_family")}, headers=h(a))
    r = client.post(
        "/beta/feedback", json={"rating": 4, "text": "  התחליף לגבינה היה מצוין  "}, headers=h(a)
    )
    assert r.status_code == 201 and r.json()["ok"] is True
    assert client.post("/beta/feedback", json={"rating": 2}, headers=h(a)).status_code == 201
    cols = [c.name for c in db.execute("SELECT * FROM beta_feedback").description]
    assert cols == ["id", "segment", "rating", "body", "created_at"]  # no user, no session
    rows = db.execute("SELECT segment, rating, body FROM beta_feedback ORDER BY id").fetchall()
    assert rows == [("large_family", 4, "התחליף לגבינה היה מצוין"), ("large_family", 2, "")]


def test_feedback_is_for_members_and_is_validated(client, db) -> None:
    a, b = make_users(db, 2)
    client.post("/beta/join", json={"code": invite(db)}, headers=h(a))
    assert client.post("/beta/feedback", json={"rating": 5}, headers=h(b)).status_code == 403
    assert client.post("/beta/feedback", json={"rating": 5}).status_code == 401
    for bad in (
        {"rating": 0},
        {"rating": 6},
        {"rating": 3, "text": "א" * 1001},
        {"rating": 3, "email": "a@b.co"},
        {"text": "no rating"},
    ):
        assert client.post("/beta/feedback", json=bad, headers=h(a)).status_code == 422, bad
    assert (
        client.post(
            "/beta/feedback", json={"rating": 3, "text": "א" * 1000}, headers=h(a)
        ).status_code
        == 201
    )
    assert db.execute("SELECT count(*) FROM beta_feedback").fetchone()[0] == 1


def test_feedback_survives_leaving_without_a_link_back_to_the_person(client, db) -> None:
    (a,) = make_users(db, 1)
    client.post("/beta/join", json={"code": invite(db)}, headers=h(a))
    client.post("/beta/feedback", json={"rating": 5, "text": "ok"}, headers=h(a))
    client.delete("/me/beta", headers=h(a))
    assert client.post("/beta/feedback", json={"rating": 5}, headers=h(a)).status_code == 403
    assert db.execute("SELECT count(*) FROM beta_feedback").fetchone()[0] == 1


# --- the by-segment views ----------------------------------------------------------------------


def test_segment_views_join_events_to_the_members_segment(client, db) -> None:
    a, b, c = make_users(db, 3)
    kosher, periphery = (
        invite(db, segment="kosher", max_uses=2),
        invite(db, "PER-12345", "periphery"),
    )
    client.post("/beta/join", json={"code": kosher}, headers=h(a))
    client.post("/beta/join", json={"code": periphery}, headers=h(b))

    def ev(user, name, props):
        import json as _json

        db.execute(
            "INSERT INTO events (user_id, session_id, name, props) VALUES (%s, 'sess-abcdef12', %s, %s::jsonb)",
            (user, name, _json.dumps(props)),
        )

    ev(a, "substitutions_shown", {"flex_level": "close", "count": 10})
    ev(a, "substitution_verdict", {"flex_level": "close", "verdict": "not_good"})
    ev(b, "substitutions_shown", {"flex_level": "close", "count": 4})
    ev(c, "substitutions_shown", {"flex_level": "close", "count": 99})  # not a member: no segment
    ev(a, "results_shown", {"duration_ms": 3000})
    ev(a, "results_shown", {"duration_ms": 5000})
    rows = db.execute(
        "SELECT segment, flex_level, shown, users, rejected, rejection_rate"
        " FROM beta_rejection_rate_by_segment ORDER BY segment"
    ).fetchall()
    assert [(s, f, sh, u, rj) for s, f, sh, u, rj, _ in rows] == [
        ("kosher", "close", 10, 1, 1),
        ("periphery", "close", 4, 1, 0),
    ]
    assert float(rows[0][5]) == 0.1
    seg = db.execute(
        "SELECT segment, results_shown, users, median_ms FROM beta_paste_to_results_by_segment"
    ).fetchall()
    assert seg == [("kosher", 2, 1, 4000)]
    overview = db.execute(
        "SELECT segment, codes, places, uses, members FROM beta_segment_overview ORDER BY segment"
    ).fetchall()
    assert overview == [("kosher", 1, 2, 1, 1), ("periphery", 1, 1, 1, 1)]


def test_the_beta_routes_are_in_the_openapi_contract(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths["/beta/join"]) == {"post"}
    assert set(paths["/me/beta"]) == {"get", "delete"}
    assert set(paths["/beta/feedback"]) == {"post"}
