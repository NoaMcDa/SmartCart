"""Per-client request limits on the routes that cost something (smartcart_api/ratelimit.py).

The suite switches them off (conftest ``_rate_limits_off``); this file switches them on, resets the
counters, and checks: the numbers, who is counted (the verified user, else the peer address; a
forged token or a spoofed ``X-Forwarded-For`` buys nothing), the 429 with ``Retry-After`` (and CORS
headers), the sliding window, and that nothing leaks between clients.
"""

from __future__ import annotations

import uuid

import pytest
from api_world import make_token

from smartcart_api import ratelimit
from smartcart_api.ratelimit import RateLimiter, limiter
from smartcart_api.settings import get_settings

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def limits_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_RATE_LIMIT", "1")
    get_settings.cache_clear()
    limiter.reset()
    yield
    limiter.reset()
    get_settings.cache_clear()


def h(uid) -> dict:
    return {"Authorization": f"Bearer {make_token(uid)}"}


def hammer(client, n: int, method: str, path: str, **kw) -> list[int]:
    return [client.request(method, path, **kw).status_code for _ in range(n)]


# --- the limiter itself ----------------------------------------------------------------------------


def test_a_sliding_window_per_bucket_and_key() -> None:
    now = [0.0]
    rl = RateLimiter(clock=lambda: now[0])
    windows = ((3, 60.0), (5, 3600.0))
    assert [rl.check("b", "k", windows) for _ in range(3)] == [None, None, None]
    wait = rl.check("b", "k", windows)
    assert wait is not None and 1 <= wait <= 60
    assert rl.check("b", "other-key", windows) is None  # another client
    assert rl.check("other-bucket", "k", windows) is None  # another route
    now[0] = 61.0  # the minute window has slid past the first three hits
    assert [rl.check("b", "k", windows) for _ in range(2)] == [None, None]  # hour: 5 used
    assert rl.check("b", "k", windows) is not None  # the hour window is now the one that is full
    now[0] = 3700.0
    assert rl.check("b", "k", windows) is None


def test_the_table_cannot_grow_without_bound(monkeypatch) -> None:
    monkeypatch.setattr(ratelimit, "_MAX_KEYS", 100)
    now = [0.0]
    rl = RateLimiter(clock=lambda: now[0])
    for n in range(5000):  # a flood of distinct addresses
        rl.check("b", f"ip:{n}", ((1, 60.0),))
        now[0] += 0.001
    assert len(rl._hits) <= 100


# --- who is counted ----------------------------------------------------------------------------------


def test_parse_list_is_limited_per_client_with_retry_after_and_cors(client, catalog) -> None:
    codes = hammer(client, 33, "POST", "/parse-list", json={"text": "חלב"})
    assert codes[:30] == [200] * 30 and set(codes[30:]) == {429}
    r = client.post(
        "/parse-list", json={"text": "חלב"}, headers={"Origin": get_settings().cors_origins[0]}
    )
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1
    assert r.headers["access-control-allow-origin"] == get_settings().cors_origins[0]
    assert r.json() == {"detail": "too many requests, try again shortly"}


def test_a_signed_in_user_is_counted_apart_from_the_address(client, catalog) -> None:
    anon = hammer(client, 31, "POST", "/parse-list", json={"text": "חלב"})
    assert anon[-1] == 429
    uid = uuid.uuid4()
    assert client.post("/parse-list", json={"text": "חלב"}, headers=h(uid)).status_code == 200
    # and the user has their own budget, separate from every other user's
    other = uuid.uuid4()
    codes = hammer(client, 30, "POST", "/parse-list", json={"text": "חלב"}, headers=h(other))
    assert codes == [200] * 30
    assert client.post("/parse-list", json={"text": "חלב"}, headers=h(other)).status_code == 429
    assert client.post("/parse-list", json={"text": "חלב"}, headers=h(uid)).status_code == 200


def test_a_forged_or_garbage_token_does_not_buy_a_fresh_budget(client, catalog) -> None:
    assert hammer(client, 30, "POST", "/parse-list", json={"text": "חלב"})[-1] == 200
    for token in (
        "garbage",
        make_token(uuid.uuid4(), secret="another-secret-that-is-also-32-bytes-long"),
    ):
        r = client.post(
            "/parse-list", json={"text": "חלב"}, headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 429, "counted by address, like an anonymous call"


def test_x_forwarded_for_is_not_trusted_by_the_application(client, catalog) -> None:
    """The address comes from the connection (uvicorn rewrites it only for FORWARDED_ALLOW_IPS)."""
    hammer(client, 30, "POST", "/parse-list", json={"text": "חלב"})
    r = client.post(
        "/parse-list",
        json={"text": "חלב"},
        headers={"X-Forwarded-For": "203.0.113.77", "X-Real-IP": "203.0.113.78"},
    )
    assert r.status_code == 429


def test_the_switch_turns_the_limits_off(client, catalog, monkeypatch) -> None:
    monkeypatch.setenv("API_RATE_LIMIT", "0")
    get_settings.cache_clear()
    assert set(hammer(client, 40, "POST", "/parse-list", json={"text": "חלב"})) == {200}


# --- the individual routes ------------------------------------------------------------------------


def test_search_optimize_compare_and_feedback_have_limits(client, catalog) -> None:
    assert hammer(client, 121, "GET", "/search", params={"q": "חלב"})[-1] == 429
    assert hammer(client, 21, "POST", "/optimize", json={})[-1] == 429  # 422s count too
    assert hammer(client, 61, "POST", "/compare", json={})[-1] == 429
    assert hammer(client, 31, "POST", "/feedback/gap", json={})[-1] == 429
    # the buckets are separate: one exhausted route does not close the others
    assert client.get("/health").status_code == 200


def test_the_recipe_url_fetch_is_limited_hard(client) -> None:
    codes = hammer(client, 10, "POST", "/parse-recipe", json={"url": "http://127.0.0.1/r"})
    assert codes[:8] == [422] * 8 and codes[8:] == [429, 429]


def test_the_photo_route_is_limited_per_client(client) -> None:
    codes = hammer(
        client,
        8,
        "POST",
        "/parse-image",
        data={"kind": "list"},
        files={"image": ("x", b"not an image", "image/png")},
        headers={"X-Image-Consent": "1"},
    )
    assert codes[6:] == [429, 429] and 429 not in codes[:6]


def test_events_are_limited_per_address_even_with_a_new_session_id_each_time(client, db) -> None:
    def batch(n: int) -> dict:
        return {"events": [{"name": "split_viewed", "props": {}, "session_id": f"session-{n:08d}"}]}

    codes = [client.post("/events", json=batch(n)).status_code for n in range(33)]
    assert codes[:30] == [200] * 30 and set(codes[30:]) == {429}
    assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 30


def test_beta_code_guessing_is_limited_per_account_and_across_accounts(client, db) -> None:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    codes = hammer(client, 8, "POST", "/beta/join", json={"code": "WRONG-CODE"}, headers=h(uid))
    assert codes[:6] == [404] * 6 and codes[6:] == [429, 429]
    # many accounts from one address: the address bucket
    results = []
    for _ in range(24):
        results.append(
            client.post(
                "/beta/join", json={"code": "WRONG-CODE"}, headers=h(uuid.uuid4())
            ).status_code
        )
    # the address has seen 6 guesses already (the refused ones were stopped by the account bucket)
    assert results[:14] == [404] * 14 and set(results[14:]) == {429}


def test_sharing_and_accepting_are_limited(client, db) -> None:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    lid = client.post("/me/lists", json={"name": "x", "items": []}, headers=h(uid)).json()["id"]
    codes = hammer(client, 12, "POST", f"/me/lists/{lid}/share", json={}, headers=h(uid))
    assert codes[:10] == [201] * 10 and codes[10:] == [429, 429]
    codes = hammer(client, 12, "POST", "/lists/accept/nope", headers=h(uid))
    assert codes[:10] == [404] * 10 and codes[10:] == [429, 429]


def test_the_user_routes_have_a_ceiling(client, db) -> None:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    codes = hammer(client, 243, "GET", "/me/profile", headers=h(uid))
    assert codes[:240] == [200] * 240 and set(codes[240:]) == {429}
