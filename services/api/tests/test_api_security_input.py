"""Input limits: body size, list lengths, string lengths, numeric ranges, text that cannot be stored.

Each limit has a test on both sides of the line (the largest accepted value, the smallest refused
one), and the refusal is a 4xx with no database error in the body.
"""

from __future__ import annotations

import json
import time
import uuid

import pytest
from api_world import World, make_token

from smartcart_api.routes.image import MAX_BODY as IMAGE_MAX_BODY
from smartcart_api.security import PATH_LIMITS
from smartcart_api.settings import get_settings

pytestmark = pytest.mark.db


def h(uid) -> dict:
    return {"Authorization": f"Bearer {make_token(uid)}"}


@pytest.fixture
def user(db) -> uuid.UUID:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    return uid


def post_json(client, path: str, raw: bytes, headers: dict | None = None):
    return client.post(
        path, content=raw, headers={"Content-Type": "application/json", **(headers or {})}
    )


# --- body size -------------------------------------------------------------------------------------


def test_a_body_over_the_limit_is_413_before_any_route_reads_it(client, catalog) -> None:
    limit = get_settings().max_body_bytes
    big = json.dumps({"text": "חלב", "flex_defaults": {}, "pad": "x" * (limit + 10)}).encode()
    r = post_json(client, "/parse-list", big)
    assert r.status_code == 413 and "larger than" in r.json()["detail"]


def test_a_chunked_body_without_content_length_is_counted_as_it_streams(client, catalog) -> None:
    limit = get_settings().max_body_bytes

    def chunks():
        yield b'{"text": "'
        for _ in range(limit // 4096 + 5):
            yield b"x" * 4096
        yield b'"}'

    r = client.post("/parse-list", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_a_body_at_the_limit_gets_to_the_route(client, catalog) -> None:
    r = post_json(client, "/parse-list", json.dumps({"text": "חלב"}).encode())
    assert r.status_code == 200


def test_the_limit_applies_to_authenticated_routes_too(client, user) -> None:
    limit = get_settings().max_body_bytes
    big = json.dumps({"name": "x", "items": [], "pad": "y" * (limit + 10)}).encode()
    assert post_json(client, "/me/lists", big, h(user)).status_code == 413


def test_the_photo_route_keeps_its_own_larger_limit() -> None:
    assert PATH_LIMITS["/parse-image"] == IMAGE_MAX_BODY > get_settings().max_body_bytes


def test_a_413_still_carries_cors_headers(client) -> None:
    limit = get_settings().max_body_bytes
    origin = get_settings().cors_origins[0]
    r = post_json(client, "/parse-list", b"x" * (limit + 1), {"Origin": origin})
    assert r.status_code == 413 and r.headers["access-control-allow-origin"] == origin


# --- text that cannot be stored ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad", ["חלב\u0000", "\u0000", "a\u0000b", "\\ud800", "\\udfff", "x\\ud83dy"]
)
def test_nul_and_lone_surrogates_are_422_not_500(client, catalog, bad) -> None:
    # `bad` is spliced into raw JSON: "\\ud800" is the JSON escape of a lone surrogate
    escaped = bad.replace("\u0000", "\\u0000")
    r = post_json(client, "/parse-list", f'{{"text": "{escaped}"}}'.encode())
    assert r.status_code == 422, (bad, r.status_code, r.text[:200])
    assert "psycopg" not in r.text and "codec" not in r.text


def test_nul_is_refused_in_every_string_of_a_request(client, user) -> None:
    for path, method, body in (
        ("/me/lists", "POST", {"name": "a\u0000", "items": []}),
        ("/me/lists", "POST", {"name": "ok", "items": [{"input_text": "a\u0000"}]}),
        ("/me/profile", "PUT", {"clubs": ["a\u0000"]}),
        ("/me/profile", "PUT", {"flex_defaults": {"a\u0000": "exact"}}),
        ("/me/profile", "PUT", {"kosher_level": "\u0000"}),
        ("/feedback/gap", "POST", {"store_id": 1, "note": "n\u0000"}),
    ):
        r = client.request(method, path, json=body, headers=h(user))
        assert r.status_code == 422, (path, body, r.status_code, r.text[:200])


def test_nul_in_a_query_string_is_422(client, catalog) -> None:
    assert client.get("/search", params={"q": "חלב\u0000"}).status_code == 422
    assert client.get("/search?q=%00").status_code == 422
    assert client.get("/search", params={"q": "חלב"}).status_code == 200


@pytest.mark.parametrize(
    "text",
    [
        "‏‮חלב‬",  # bidi controls
        "חֲלָב",  # nikud
        "حَلِيب ٣ لتر",  # Arabic with diacritics and Arabic-Indic digits
        "ـ" * 500,  # tatweel
        "́" * 3000,  # combining marks with nothing to combine with
        "א" * 4000,  # one very long word
        "🥛" * 1000,  # astral characters
        "﻿￾￿",
        "　   \t",  # exotic white space
        "חלב " * 800,
        "1" * 4000,
        "x2 " * 1300,
        "\r\n" * 1999 + "חלב",
        "—" * 3000,
    ],
)
def test_odd_unicode_in_a_list_never_breaks_the_parser(client, catalog, text) -> None:
    started = time.monotonic()
    r = post_json(client, "/parse-list", json.dumps({"text": text[:4000]}).encode())
    assert r.status_code in (200, 422), (text[:20], r.status_code, r.text[:200])
    assert time.monotonic() - started < 10


def test_a_list_has_at_most_200_items(client, catalog) -> None:
    ok = client.post("/parse-list", json={"text": ",".join(["חלב"] * 200)})
    assert ok.status_code == 200 and len(ok.json()["rows"]) == 200
    too_many = client.post("/parse-list", json={"text": ",".join(["חלב"] * 201)})
    assert too_many.status_code == 422 and "200" in too_many.json()["detail"]
    # 4000 characters of separators is the worst case the text limit allows
    assert client.post("/parse-list", json={"text": "a," * 2000}).status_code == 422


def test_parse_list_text_limits(client, catalog) -> None:
    assert client.post("/parse-list", json={"text": ""}).status_code == 422
    assert client.post("/parse-list", json={"text": "ח" * 4001}).status_code == 422
    assert (
        client.post(
            "/parse-list", json={"text": "חלב", "flex_defaults": {"x" * 61: "exact"}}
        ).status_code
        == 422
    )
    big = {f"t{i}": "exact" for i in range(1001)}
    assert client.post("/parse-list", json={"text": "חלב", "flex_defaults": big}).status_code == 422


# --- numbers ----------------------------------------------------------------------------------------

LOC = {"lon": 34.78, "lat": 32.08, "radius_m": 5000}


def compare_body(world: World, **over) -> dict:
    item = {"canonical_id": world.canon["milk3"], "quantity": 1}
    return {
        "items": [{**item, **over.pop("item", {})}],
        "location": {**LOC, **over.pop("loc", {})},
        **over,
    }


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        "0.001",
        -1,
        1000.5,
        10**6,
        1e30,
        "1e30",
        "NaN",
        "Infinity",
        "-Infinity",
        "1" * 400,
        "0.1" + "1" * 30,
    ],
)
def test_basket_quantities_are_bounded(client, world: World, quantity) -> None:
    for path in ("/compare", "/optimize"):
        r = client.post(path, json=compare_body(world, item={"quantity": quantity}))
        assert r.status_code == 422, (path, quantity, r.status_code)


def test_basket_quantity_extremes_that_are_fine(client, world: World) -> None:
    # 0.01 is the floor: below it a quantity prices to 0.00 (test_api_optimizer_props_regress.py).
    for quantity in (1000, "0.01", 0.30000000000000004, "2.5"):
        r = client.post("/compare", json=compare_body(world, item={"quantity": quantity}))
        assert r.status_code == 200, (quantity, r.text[:200])


@pytest.mark.parametrize(
    "loc",
    [
        {"radius_m": 499},
        {"radius_m": 15001},
        {"radius_m": 10**12},
        {"radius_m": -1},
        {"lat": 91},
        {"lat": -90.0001},
        {"lon": 181},
        {"lat": "NaN"},
        {"lon": "Infinity"},
        {"lat": None},
    ],
)
def test_location_ranges(client, world: World, loc) -> None:
    assert client.post("/compare", json=compare_body(world, loc=loc)).status_code == 422


def test_nan_and_infinity_tokens_in_raw_json_are_422(client, world: World) -> None:
    raw = b'{"items": [{"canonical_id": 1, "quantity": NaN}], "location": {"lon": 1, "lat": Infinity}}'
    assert post_json(client, "/compare", raw).status_code == 422


@pytest.mark.parametrize(
    "extra",
    [
        {"max_stores": 0},
        {"max_stores": 4},
        {"candidate_stores": 0},
        {"candidate_stores": 16},
        {"min_split_saving": -1},
        {"min_split_saving": 10**9},
        {"travel": {"cost_per_km": -1}},
        {"travel": {"cost_per_km": 101}},
        {"travel": {"cost_per_km": 10**30}},
        {"travel": {"extra_stop_value": 51}},
        {"travel": {"mode": "teleport"}},
        {"solver": "evil"},
    ],
)
def test_optimizer_settings_are_bounded(client, world: World, extra) -> None:
    assert client.post("/optimize", json=compare_body(world, **extra)).status_code == 422


def test_a_basket_has_between_1_and_200_items_and_bounded_clubs(client, world: World) -> None:
    item = {"canonical_id": world.canon["milk3"], "quantity": 1}
    assert client.post("/compare", json={"items": [], "location": LOC}).status_code == 422
    assert client.post("/compare", json={"items": [item] * 201, "location": LOC}).status_code == 422
    assert client.post("/compare", json={"items": [item] * 200, "location": LOC}).status_code == 200
    for clubs in (["c"] * 31, ["x" * 61], [1]):
        assert (
            client.post(
                "/compare", json={"items": [item], "location": LOC, "clubs": clubs}
            ).status_code
            == 422
        )


def test_allow_list_is_bounded(client, world: World) -> None:
    item = {"canonical_id": 1, "quantity": 1, "allow": ["pack_size"] * 6}
    assert client.post("/compare", json={"items": [item], "location": LOC}).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"cost_per_km": 101},
        {"cost_per_km": -1},
        {"extra_stop_value": 51},
        {"radius_m": 499},
        {"radius_m": 15001},
        {"max_stores": 4},
        {"monthly_budget": -1},
        {"monthly_budget": "123456789012.00"},
        {"monthly_budget": "1.001"},
        {"clubs": ["c"] * 31},
        {"diet_flags": ["d"] * 31},
        {"kosher_level": "k" * 61},
        {"theme": "neon"},
        {"neighborhood_lat": 100, "consent_location": True},
        {"neighborhood_lon": -181, "consent_location": True},
    ],
)
def test_profile_ranges(client, user, body) -> None:
    assert client.put("/me/profile", json=body, headers=h(user)).status_code == 422


def test_a_location_without_consent_is_refused_and_the_stored_one_is_rounded(
    client, user, db
) -> None:
    r = client.put(
        "/me/profile",
        json={"neighborhood_lat": 32.0712345, "neighborhood_lon": 34.7812345},
        headers=h(user),
    )
    assert r.status_code == 422
    r = client.put(
        "/me/profile",
        json={
            "neighborhood_lat": 32.0712345,
            "neighborhood_lon": 34.7812345,
            "consent_location": True,
        },
        headers=h(user),
    )
    assert r.status_code == 200 and r.json()["neighborhood_lat"] == 32.071
    row = db.execute(
        "SELECT neighborhood_lat::text, neighborhood_lon::text FROM profiles"
    ).fetchone()
    assert row == ("32.071", "34.781")


@pytest.mark.parametrize(
    "item",
    [
        {"quantity": 0},
        {"quantity": 1001},
        {"quantity": "NaN"},
        {"input_text": "x" * 201},
        {"flex_level": "any"},
        {"canonical_id": "abc"},
    ],
)
def test_list_item_bounds(client, user, item) -> None:
    r = client.post("/me/lists", json={"name": "n", "items": [item]}, headers=h(user))
    assert r.status_code == 422


def test_list_name_and_length_bounds(client, user) -> None:
    assert (
        client.post("/me/lists", json={"name": "", "items": []}, headers=h(user)).status_code == 422
    )
    assert (
        client.post("/me/lists", json={"name": "n" * 101, "items": []}, headers=h(user)).status_code
        == 422
    )
    items = [{"input_text": "a"}] * 201
    assert (
        client.post("/me/lists", json={"name": "n", "items": items}, headers=h(user)).status_code
        == 422
    )
    ok = client.post("/me/lists", json={"name": "ח" * 100, "items": items[:200]}, headers=h(user))
    assert ok.status_code == 201 and len(ok.json()["items"]) == 200


@pytest.mark.parametrize(
    "body",
    [
        {"total": "-1"},
        {"total": "100000000.00"},
        {"total": "1.234"},
        {"total": "NaN"},
        {"item_count": -1},
        {"item_count": 1001},
        {"store_name": ""},
        {"store_name": "s" * 201},
        {"plan": "triple"},
        {"date": "2026-13-01"},
        {"date": "not-a-date"},
        {"client_id": "not-a-uuid"},
    ],
)
def test_spend_bounds(client, world: World, user, body) -> None:
    entry = {
        "date": "2026-10-05",
        "store_id": next(iter(world.stores.values())),
        "store_name": "x",
        "total": "10",
        "item_count": 1,
        "plan": "single",
        **body,
    }
    assert client.post("/me/spend", json=entry, headers=h(user)).status_code == 422


@pytest.mark.parametrize(
    "month", ["2026-13", "2026-00", "26-10", "2026-1", "2026-10-01", "x", "9999-99"]
)
def test_spend_month_pattern(client, user, month) -> None:
    assert client.get("/me/spend", params={"month": month}, headers=h(user)).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"threshold_unit_price": 0},
        {"threshold_unit_price": -1},
        {"threshold_unit_price": 10**9},
        {"threshold_unit_price": "NaN"},
        {"radius_m": 10},
        {"flex_level": "x"},
    ],
)
def test_alert_bounds(client, world: World, user, body) -> None:
    alert = {"canonical_id": world.canon["milk3"], "threshold_unit_price": "5", **body}
    assert client.post("/me/alerts", json=alert, headers=h(user)).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"shown_price": -1},
        {"actual_price": -0.01},
        {"shown_price": 10**9},
        {"actual_price": "NaN"},
        {"note": "n" * 501},
    ],
)
def test_gap_report_bounds(client, world: World, body) -> None:
    gap = {"store_id": next(iter(world.stores.values())), **body}
    assert client.post("/feedback/gap", json=gap).status_code == 422


def test_beta_and_events_bounds(client, user) -> None:
    for code in ("A" * 5, "A" * 33, "AB CD EF", "ABCDEF;--", "ABCDEF\u0000", ""):
        assert client.post("/beta/join", json={"code": code}, headers=h(user)).status_code == 422, (
            code
        )
    for rating in (0, 6, -1, 99, "x", None):
        r = client.post("/beta/feedback", json={"rating": rating, "text": "x"}, headers=h(user))
        assert r.status_code == 422
    r = client.post("/beta/feedback", json={"rating": 3, "text": "t" * 1001}, headers=h(user))
    assert r.status_code == 422
    event = {"name": "split_viewed", "props": {}, "session_id": "session-sec-0001"}
    assert client.post("/events", json={"events": [event] * 51}).status_code == 422
    assert client.post("/events", json={"events": []}).status_code == 422
    for sid in ("short", "x" * 65, "has space 123", "a" * 8 + "\u0000"):
        assert (
            client.post("/events", json={"events": [{**event, "session_id": sid}]}).status_code
            == 422
        )
    huge = {**event, "props": {"k" * 10: "v" * 100_000}}
    assert client.post("/events", json={"events": [huge]}).status_code in (413, 422)


def test_push_subscription_field_bounds(client, user) -> None:
    sub = {"endpoint": "https://push.example.com/x", "p256dh": "k", "auth": "a"}
    assert client.post("/me/push-subscriptions", json=sub, headers=h(user)).status_code == 201
    for over in (
        {"p256dh": ""},
        {"p256dh": "k" * 201},
        {"auth": "a" * 101},
        {"user_agent": "u" * 301},
        {"endpoint": "https://push.example.com/" + "x" * 2000},
    ):
        r = client.post("/me/push-subscriptions", json={**sub, **over}, headers=h(user))
        assert r.status_code == 422, over


# --- control and bidi-override characters ---------------------------------------------------------


def test_terminal_escapes_and_bidi_overrides_are_stripped_from_free_text(client, user, db) -> None:
    """Feedback is printed in the maintainer's terminal (`smartcart-catalog beta-feedback`) and list
    names are shown to the people a list is shared with."""
    db.execute(
        "INSERT INTO beta_invites (code, segment, max_uses) VALUES ('CLEAN-TEXT-1', 'general', 1)"
    )
    joined = client.post("/beta/join", json={"code": "CLEAN-TEXT-1"}, headers=h(user))
    assert joined.status_code == 200
    nasty = "great\x1b[2J\x1b]0;pwned\x07 app\r\nline2‮evil⁦x⁩ ‏שלום‎"
    r = client.post("/beta/feedback", json={"rating": 5, "text": nasty}, headers=h(user))
    assert r.status_code == 201
    (stored,) = db.execute("SELECT body FROM beta_feedback").fetchone()
    assert stored == "great[2J]0;pwned app\nline2evilx ‏שלום‎"  # RLM and LRM are kept
    assert not any(ord(c) < 32 and c not in "\n\t" for c in stored)
    body = {"name": "רשימה‮משפחה", "items": [{"input_text": "חלב\x1b[31m"}]}
    made = client.post("/me/lists", json=body, headers=h(user)).json()
    assert made["name"] == "רשימהמשפחה" and made["items"][0]["input_text"] == "חלב[31m"
