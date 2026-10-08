"""POST /events: allowlist, user id from the JWT, rate limit, and the beta metric views (issue #40)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from api_world import World, make_token

from smartcart_api import schemas
from smartcart_api.routes import events as events_route
from smartcart_api.routes.events import EVENT_PROPS, EVENTS_PER_SESSION_PER_MINUTE

pytestmark = pytest.mark.db

SESSION = "sess-abcdef12"


def ev(name: str, props: dict | None = None, session: str = SESSION) -> dict:
    return {"name": name, "props": props or {}, "session_id": session}


def post(client, *events: dict, headers: dict | None = None):
    return client.post("/events", json={"events": list(events)}, headers=headers or {})


def stored(db):
    return db.execute(
        "SELECT user_id, session_id, name, props FROM events ORDER BY id"
    ).fetchall()


def test_event_names_in_the_schema_match_the_allowlist() -> None:
    from typing import get_args

    assert set(get_args(schemas.EventName)) == set(EVENT_PROPS)


def test_a_batch_is_stored_with_its_props(client, db) -> None:
    r = post(
        client,
        ev("app_opened", {"surface": "pwa"}),
        ev("list_pasted", {"item_count": 9}),
        ev("results_shown", {"duration_ms": 2400, "item_count": 9, "store_count": 3}),
        ev("split_viewed"),
    )
    assert r.status_code == 200 and r.json() == {"ok": True, "accepted": 4}
    rows = stored(db)
    assert [(u, s, n) for u, s, n, _ in rows] == [(None, SESSION, n) for n in
            ("app_opened", "list_pasted", "results_shown", "split_viewed")]  # fmt: skip
    assert rows[2][3] == {"duration_ms": 2400, "item_count": 9, "store_count": 3}
    assert rows[3][3] == {}


def test_unknown_event_names_and_keys_are_rejected_and_nothing_is_stored(client, db) -> None:
    bad_name = post(client, ev("app_opened"), ev("page_hit", {}))
    assert bad_name.status_code == 422  # not in the schema enum
    bad_key = post(client, ev("app_opened"), ev("list_pasted", {"item_count": 3, "text": "חלב"}))
    assert bad_key.status_code == 422
    assert any("props.text" in p and "not allowed" in p for p in bad_key.json()["detail"])
    assert stored(db) == []


@pytest.mark.parametrize(
    ("name", "props", "reason"),
    [
        ("list_pasted", {"item_count": "9"}, "must be an integer"),
        ("list_pasted", {"item_count": 9.5}, ""),
        ("list_pasted", {"item_count": -1}, "between 0 and 200"),
        ("list_pasted", {"item_count": 10_000}, "between 0 and 200"),
        ("list_pasted", {}, "required"),
        ("results_shown", {"duration_ms": 1.5e9}, ""),
        ("substitutions_shown", {"flex_level": "any_brand"}, "required"),
        ("substitutions_shown", {"flex_level": "דומה", "count": 2}, "must be one of"),
        ("substitution_verdict", {"flex_level": "close", "verdict": "love_it"}, "must be one of"),
        ("page_viewed", {"page_type": "https://example.com/?q=milk"}, "must be one of"),
        ("app_opened", {"email": "a@b.co"}, "not allowed"),
        ("split_viewed", {"anything": 1}, "not allowed"),
    ],
)
def test_props_are_limited_to_allowlisted_keys_with_fixed_values(client, db, name, props, reason) -> None:
    r = post(client, ev(name, props))
    assert r.status_code == 422, r.text
    assert reason in str(r.json()["detail"])
    assert stored(db) == []


PHASE2_EVENTS = [
    ("scan_started", {"engine": "zxing"}),
    ("scan_completed", {"outcome": "found", "duration_ms": 1800, "engine": "native"}),
    ("alert_created", {"flex_level": "any_brand", "source": "product"}),
    ("swap_applied", {"flex_level": "close", "saving_agorot": 450}),
    ("swap_undone", {"flex_level": "any_brand"}),
    ("swap_dismissed", {"flex_level": "exact"}),
    ("list_shared", {"role": "editor"}),
    ("share_accepted", {"role": "viewer"}),
]


def test_phase2_events_are_stored_with_their_props(client, db) -> None:
    assert {n for n, _ in PHASE2_EVENTS} == {
        "scan_started", "scan_completed", "alert_created", "swap_applied", "swap_undone",
        "swap_dismissed", "list_shared", "share_accepted"}
    r = post(client, *(ev(n, p) for n, p in PHASE2_EVENTS))
    assert r.status_code == 200 and r.json()["accepted"] == len(PHASE2_EVENTS), r.text
    assert [(n, p) for _, _, n, p in stored(db)] == PHASE2_EVENTS
    # Every prop is optional except the scan outcome.
    minimal = [ev(n) for n, _ in PHASE2_EVENTS if n != "scan_completed"]
    minimal.append(ev("scan_completed", {"outcome": "cancelled"}))
    assert post(client, *minimal).status_code == 200


@pytest.mark.parametrize(
    ("name", "props", "reason"),
    [
        ("scan_started", {"engine": "camera2"}, "must be one of"),
        ("scan_started", {"barcode": "7290000066318"}, "not allowed"),
        ("scan_completed", {}, "required"),
        ("scan_completed", {"outcome": "found", "duration_ms": 700_000}, "between 0 and 600000"),
        ("scan_completed", {"outcome": "found", "item_id": 12}, "not allowed"),
        ("alert_created", {"source": "email"}, "must be one of"),
        ("alert_created", {"threshold": 5}, "not allowed"),
        ("swap_applied", {"saving_agorot": -1}, "between 0 and 100000"),
        ("swap_applied", {"saving_agorot": "4.50"}, "must be an integer"),
        ("swap_applied", {"price": 450}, "not allowed"),
        ("swap_undone", {"flex_level": "דומה"}, "must be one of"),
        ("swap_undone", {"item_id": 3}, "not allowed"),
        ("swap_dismissed", {"canonical_id": 7}, "not allowed"),
        ("list_shared", {"role": "owner"}, "must be one of"),
        ("list_shared", {"list_id": 4}, "not allowed"),
        ("share_accepted", {"token": "abc"}, "not allowed"),
    ],
)
def test_phase2_events_reject_disallowed_keys_and_values(client, db, name, props, reason) -> None:
    r = post(client, ev(name, props))
    assert r.status_code == 422, r.text
    assert reason in str(r.json()["detail"])
    assert stored(db) == []


def test_free_text_cannot_get_in_through_any_event(client) -> None:
    """Every allowlisted key takes an integer range or a fixed set: no key accepts arbitrary text."""
    for name, keys in EVENT_PROPS.items():
        for key, rule in keys.items():
            assert (rule.choices is not None) ^ (rule.low is not None and rule.high is not None), (
                name, key,
            )  # fmt: skip
            if rule.choices is not None:
                assert all(len(c) <= 20 for c in rule.choices), (name, key)
            assert rule.problem("a free text value that is not allowed") is not None
    assert events_route.Key(0, 5).problem(True) is not None  # booleans are not integers here


def test_session_id_must_be_a_random_looking_token(client, db) -> None:
    for bad in ("short", "has space in it", "x" * 65, "a@b.co-123456", ""):
        assert post(client, ev("app_opened", session=bad)).status_code == 422, bad
    assert post(client, ev("app_opened", session="Abc_123-xyZ")).status_code == 200


def test_empty_and_oversized_batches_are_rejected(client) -> None:
    assert client.post("/events", json={"events": []}).status_code == 422
    assert post(client, *[ev("app_opened")] * 51).status_code == 422
    assert post(client, *[ev("app_opened")] * 50).status_code == 200


def test_user_id_comes_from_a_valid_jwt_only(client, db, world: World) -> None:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id, email) VALUES (%s, 'beta@example.com')", (uid,))
    ok = post(client, ev("app_opened"), headers={"Authorization": f"Bearer {make_token(uid)}"})
    assert ok.status_code == 200
    expired = make_token(uid, exp=int((datetime.now(UTC) - timedelta(hours=1)).timestamp()))
    post(client, ev("app_opened"), headers={"Authorization": f"Bearer {expired}"})
    post(client, ev("app_opened"), headers={"Authorization": "Bearer not.a.jwt"})
    post(client, ev("app_opened"))
    unknown = uuid.uuid4()  # a valid token for an account that does not exist: anonymous, no error
    gone = post(client, ev("app_opened"), headers={"Authorization": f"Bearer {make_token(unknown)}"})
    assert gone.status_code == 200
    assert [u for u, *_ in stored(db)] == [uid, None, None, None, None]


def test_deleting_the_account_keeps_the_event_without_the_user(client, db) -> None:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id, email) VALUES (%s, 'beta@example.com')", (uid,))
    post(client, ev("app_opened"), headers={"Authorization": f"Bearer {make_token(uid)}"})
    db.execute("DELETE FROM auth.users WHERE id = %s", (uid,))
    assert [u for u, *_ in stored(db)] == [None]


def test_rate_limit_is_per_session_and_drops_the_whole_batch(client, db) -> None:
    other = "other-sess-1"
    for _ in range(EVENTS_PER_SESSION_PER_MINUTE // 40):
        assert post(client, *[ev("app_opened")] * 40).status_code == 200
    assert db.execute("SELECT count(*) FROM events").fetchone()[0] == EVENTS_PER_SESSION_PER_MINUTE
    limited = post(client, ev("app_opened"), ev("app_opened", session=other))
    assert limited.status_code == 429 and limited.headers["Retry-After"] == "60"
    assert db.execute("SELECT count(*) FROM events").fetchone()[0] == EVENTS_PER_SESSION_PER_MINUTE
    assert post(client, ev("app_opened", session=other)).status_code == 200  # another session
    # an older minute does not count
    db.execute("UPDATE events SET created_at = now() - interval '2 minutes' WHERE session_id = %s",
               (SESSION,))  # fmt: skip
    assert post(client, ev("app_opened")).status_code == 200


def test_events_table_is_closed_to_the_data_api_roles(db) -> None:
    assert db.execute("SELECT relrowsecurity FROM pg_class WHERE relname = 'events'").fetchone()[0]
    assert db.execute("SELECT count(*) FROM pg_policies WHERE tablename = 'events'").fetchone()[0] == 0
    for role in ("anon", "authenticated"):
        if db.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone():
            assert not db.execute(
                "SELECT has_table_privilege(%s, 'events', 'SELECT') OR has_table_privilege(%s, 'events', 'INSERT')",
                (role, role),
            ).fetchone()[0], role
    with pytest.raises(Exception, match="violates check constraint"):
        db.execute("INSERT INTO events (session_id, name) VALUES ('has space in it', 'app_opened')")


# --- the three beta metrics ----------------------------------------------------------------------------


def put(db, name: str, props: dict, *, session: str, at: str, user=None) -> None:
    import json

    db.execute(
        "INSERT INTO events (user_id, session_id, name, props, created_at)"
        " VALUES (%s, %s, %s, %s::jsonb, %s)",
        (user, session, name, json.dumps(props), at),
    )


def test_rejection_rate_is_not_good_over_substitutions_shown_per_level(client, db) -> None:
    w1, w2 = "2026-10-07T08:00:00+00:00", "2026-10-14T08:00:00+00:00"  # Wednesdays, two weeks
    for at, level, shown, rejected in (
        (w1, "any_brand", 10, 1), (w1, "any_brand", 10, 1), (w1, "close", 5, 2), (w2, "any_brand", 20, 0),
    ):  # fmt: skip
        put(db, "substitutions_shown", {"flex_level": level, "count": shown}, session=SESSION, at=at)
        for _ in range(rejected):
            put(db, "substitution_verdict", {"flex_level": level, "verdict": "not_good"},
                session=SESSION, at=at)  # fmt: skip
    put(db, "substitution_verdict", {"flex_level": "any_brand", "verdict": "accepted"},
        session=SESSION, at=w1)  # accepted answers are not rejections
    rows = db.execute(
        "SELECT week::text, flex_level, shown, rejected, rejection_rate FROM beta_rejection_rate"
    ).fetchall()
    assert [(w, lvl, s, r, float(rate)) for w, lvl, s, r, rate in rows] == [
        ("2026-10-12", "any_brand", 20, 0, 0.0),
        ("2026-10-05", "any_brand", 20, 2, 0.1),
        ("2026-10-05", "close", 5, 2, 0.4),
    ]


def test_paste_to_results_view_gives_median_and_p90(client, db) -> None:
    at = "2026-10-07T08:00:00+00:00"
    for ms in (1000, 2000, 3000, 4000, 10_000):
        put(db, "results_shown", {"duration_ms": ms}, session=SESSION, at=at)
    put(db, "results_shown", {"item_count": 3}, session=SESSION, at=at)  # no duration: ignored
    (week, n, median, p90) = db.execute("SELECT week::text, results_shown, median_ms, p90_ms FROM beta_paste_to_results").fetchone()
    assert (week, n, int(median), int(p90)) == ("2026-10-05", 5, 3000, 7600)


def test_return_visits_use_the_user_else_the_session_as_the_actor(client, db) -> None:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id, email) VALUES (%s, 'beta@example.com')", (uid,))
    # week of 2026-10-05: three actors open the app; week of 2026-10-12: two of them come back
    for day in ("2026-10-05", "2026-10-06"):
        put(db, "app_opened", {}, session="anon-device-1", at=f"{day}T09:00:00+00:00")
    put(db, "app_opened", {}, session="phone-of-user", at="2026-10-06T09:00:00+00:00", user=uid)
    put(db, "app_opened", {}, session="anon-device-2", at="2026-10-07T09:00:00+00:00")
    put(db, "app_opened", {}, session="laptop-of-user", at="2026-10-13T09:00:00+00:00", user=uid)
    put(db, "app_opened", {}, session="anon-device-1", at="2026-10-14T09:00:00+00:00")
    put(db, "app_opened", {}, session="anon-device-3", at="2026-10-14T09:00:00+00:00")  # new
    rows = db.execute(
        "SELECT week::text, active_users, returning_users, returning_share, visit_days_per_user"
        " FROM beta_return_visits"
    ).fetchall()
    assert [(w, a, r, float(s), float(v)) for w, a, r, s, v in rows] == [
        ("2026-10-12", 3, 2, 0.6667, 1.0),
        ("2026-10-05", 3, 0, 0.0, 1.33),
    ]


def test_rejected_substitutions_view_lists_the_context_for_review(client, db, world: World) -> None:
    w = world
    body = {"canonical_id": w.canon["salmon"], "substitute_item_id": w.items["salmon_c2_frozen"],
            "verdict": "not_good"}  # fmt: skip
    assert client.post("/feedback/substitution", json=body).status_code == 200
    ok = {**body, "verdict": "accepted", "substitute_item_id": w.items["milk3_c1_private"],
          "canonical_id": w.canon["milk3"]}  # fmt: skip
    assert client.post("/feedback/substitution", json=ok).status_code == 200
    (row,) = db.execute(
        "SELECT canonical_slug, substitute_item, needs_review, reviewed FROM beta_rejected_substitutions"
    ).fetchall()
    assert row[0] == "t-salmon" and row[2] is True and row[3] is False and row[1]


# --- phase 3: voice list -------------------------------------------------------------------------

VOICE_EVENTS = [
    ("voice_started", {"engine": "web_speech"}),
    ("voice_completed", {"outcome": "parsed", "duration_ms": 5200, "item_count": 7}),
    ("voice_completed", {"outcome": "empty", "duration_ms": 3000, "item_count": 0}),
    ("voice_completed", {"outcome": "cancelled"}),
    ("voice_completed", {"outcome": "error", "duration_ms": 0}),
]


def test_voice_events_are_stored_with_their_props(client, db) -> None:
    r = post(client, *(ev(n, p) for n, p in VOICE_EVENTS), ev("voice_started"))
    assert r.status_code == 200 and r.json()["accepted"] == len(VOICE_EVENTS) + 1, r.text
    assert [(n, p) for _, _, n, p in stored(db)] == [*VOICE_EVENTS, ("voice_started", {})]


@pytest.mark.parametrize(
    ("name", "props", "reason"),
    [
        ("voice_started", {"engine": "siri"}, "must be one of"),
        ("voice_started", {"transcript": "חלב ולחם"}, "not allowed"),
        ("voice_completed", {}, "required"),
        ("voice_completed", {"outcome": "partial"}, "must be one of"),
        ("voice_completed", {"outcome": "parsed", "duration_ms": 700_000}, "between 0 and 600000"),
        ("voice_completed", {"outcome": "parsed", "item_count": 201}, "between 0 and 200"),
        ("voice_completed", {"outcome": "parsed", "item_count": "7"}, "must be an integer"),
        ("voice_completed", {"outcome": "parsed", "text": "חלב"}, "not allowed"),
    ],
)
def test_voice_event_props_are_allowlisted(client, db, name, props, reason) -> None:
    r = post(client, ev(name, props))
    assert r.status_code == 422, r.text
    assert reason in str(r.json()["detail"])
    assert stored(db) == []
