"""The shared (Postgres) rate limit backend (docs/security-review.md R3).

``API_RATE_LIMIT_BACKEND=postgres`` counts in ``api_rate_limits`` so that every worker and replica
shares the limit. This file checks: two limiters on two connections share one count (what two
processes do), the count is atomic under threads, windows roll over (on a controlled clock), old
windows are cleaned up (and only by one process at a time), one statement carries every limit of a
request, the API role has exactly the grants the limiter runs on, an outage of the table degrades
to per-process counting (or, on the routes that guard guessing, to a 503), and the default backend
never touches the database. The in-memory limiter's own tests are test_api_security_ratelimit.py.
"""

from __future__ import annotations

import logging
import threading
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import psycopg
import pytest
from api_world import make_token

from smartcart_api import ratelimit
from smartcart_api.ratelimit import SharedLimiter, limiter, use_shared_limiter
from smartcart_api.settings import Settings, get_settings

pytestmark = pytest.mark.db

T0 = 1_000_020  # a multiple of 60 (and not of 3600): the start of a minute window


def h(uid) -> dict:
    return {"Authorization": f"Bearer {make_token(uid)}"}


@pytest.fixture
def dsn(database) -> str:
    return database.dsn


def _wipe(dsn: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DELETE FROM api_rate_limits")


def _rows(dsn: str) -> list[tuple]:
    with psycopg.connect(dsn, autocommit=True) as conn:
        return conn.execute(
            "SELECT bucket, client_key, window_seconds, window_start, hits"
            " FROM api_rate_limits ORDER BY 1, 2, 3, 4"
        ).fetchall()


@pytest.fixture(autouse=True)
def shared_backend(monkeypatch: pytest.MonkeyPatch, dsn: str):
    """Limits on, the Postgres backend selected, counters committed to the test database (so they
    are visible to a second connection, as another process would see them) and wiped around."""
    monkeypatch.setenv("API_RATE_LIMIT", "1")
    monkeypatch.setenv("API_RATE_LIMIT_BACKEND", "postgres")
    get_settings.cache_clear()
    limiter.reset()
    use_shared_limiter(make_limiter(dsn))
    _wipe(dsn)
    yield
    use_shared_limiter(None)
    ratelimit.close_pool()
    limiter.reset()
    _wipe(dsn)
    get_settings.cache_clear()


def make_limiter(dsn: str, **kw) -> SharedLimiter:
    """One 'process': its own connection per call, like a pool of its own. The windows are cut from
    a fixed instant unless a clock is given (``clock=lambda: None`` is the database's own), so that
    a test that sends many requests cannot straddle a real minute boundary and fail at random."""
    kw.setdefault("clock", lambda: T0)

    @contextmanager
    def connect():
        with psycopg.connect(dsn, autocommit=True) as conn:
            yield conn

    return SharedLimiter(connect, **kw)


class Counting:
    """A connection that counts the statements the limiter runs on it."""

    def __init__(self, dsn: str, counter: list[str]) -> None:
        self.dsn, self.counter = dsn, counter

    @contextmanager
    def __call__(self):
        with psycopg.connect(self.dsn, autocommit=True) as conn:
            counter = self.counter

            class Proxy:
                def execute(self, query, params=None):
                    counter.append(" ".join(str(query).split())[:40])
                    return conn.execute(query, params)

            yield Proxy()


# --- one count for every process ----------------------------------------------------------------------


def test_two_processes_share_the_limit(client, catalog, dsn) -> None:
    """/parse-list allows 30 a minute. Two limiters on two connections take turns (what two
    workers do), and each one's own in-memory counters are wiped between requests, so only the
    database can be what stops the 31st."""
    a, b = make_limiter(dsn), make_limiter(dsn)
    codes = []
    for n in range(33):
        use_shared_limiter(a if n % 2 == 0 else b)
        limiter.reset()
        codes.append(client.post("/parse-list", json={"text": "חלב"}).status_code)
    assert codes[:30] == [200] * 30 and set(codes[30:]) == {429}


def test_the_memory_backend_would_have_let_each_process_have_its_own(
    client, catalog, monkeypatch
) -> None:
    """The contrast: the same two 'processes' on the default backend each get the full limit."""
    monkeypatch.setenv("API_RATE_LIMIT_BACKEND", "memory")
    get_settings.cache_clear()
    codes = []
    for n in range(60):
        if n % 30 == 0:
            limiter.reset()  # a second process starts with empty counters
        codes.append(client.post("/parse-list", json={"text": "חלב"}).status_code)
    assert set(codes) == {200}


def test_the_default_backend_is_memory_and_never_touches_the_database(
    client, catalog, monkeypatch
) -> None:
    monkeypatch.delenv("API_RATE_LIMIT_BACKEND")
    get_settings.cache_clear()
    assert get_settings().rate_limit_backend == "memory"

    def boom():
        raise AssertionError("the memory backend must not open a connection")

    use_shared_limiter(SharedLimiter(boom))
    codes = [client.post("/parse-list", json={"text": "חלב"}).status_code for _ in range(32)]
    assert codes[:30] == [200] * 30 and codes[30:] == [429, 429]


def test_the_backend_setting_is_validated_and_case_insensitive(monkeypatch) -> None:
    assert Settings(API_RATE_LIMIT_BACKEND=" Postgres ").rate_limit_backend == "postgres"
    with pytest.raises(ValueError):
        Settings(API_RATE_LIMIT_BACKEND="redis")


def test_the_limit_is_atomic_under_threads(dsn) -> None:
    """Eight threads on four 'processes' send 240 hits at a limit of 30: exactly 30 pass."""
    procs = [make_limiter(dsn) for _ in range(4)]
    allowed: list[bool] = []
    guard = threading.Lock()

    def work(i: int) -> None:
        for _ in range(30):
            wait = procs[i % 4].hit([("t:principal", "ip:1.2.3.4", 60, 30)])
            with guard:
                allowed.append(wait is None)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(allowed) == 240 and sum(allowed) == 30
    assert _rows(dsn)[0][4] == 240  # a refused request counts too


def test_clients_and_routes_do_not_share_a_count(dsn) -> None:
    rl = make_limiter(dsn)
    rows = lambda key, bucket="b:principal": [(bucket, key, 60, 2)]  # noqa: E731
    assert [rl.hit(rows("u:1")) for _ in range(2)] == [None, None]
    assert rl.hit(rows("u:1")) is not None
    assert rl.hit(rows("u:2")) is None  # another client
    assert rl.hit(rows("u:1", "other:principal")) is None  # another route
    assert rl.hit(rows("u:1", "b:ip")) is None  # the same route keyed by address


def test_a_signed_in_user_is_counted_apart_from_the_address(client, catalog, db) -> None:
    uid, other = uuid.uuid4(), uuid.uuid4()
    codes = [
        client.post("/parse-list", json={"text": "חלב"}, headers=h(uid)).status_code
        for _ in range(32)
    ]
    assert codes[:30] == [200] * 30 and codes[30:] == [429, 429]
    # another account and the same address, signed out: neither is counted with the first
    assert client.post("/parse-list", json={"text": "חלב"}, headers=h(other)).status_code == 200
    assert client.post("/parse-list", json={"text": "חלב"}).status_code == 200


def test_a_forged_token_is_counted_by_address(client, catalog, dsn) -> None:
    forged = {"Authorization": f"Bearer {make_token(uuid.uuid4(), secret='x' * 40)}"}
    for _ in range(3):
        client.post("/parse-list", json={"text": "חלב"}, headers=forged)
    keys = {r[1] for r in _rows(dsn)}
    assert keys == {"ip:testclient"}


def test_429_carries_retry_after_and_cors(client, catalog) -> None:
    for _ in range(30):
        client.post("/parse-list", json={"text": "חלב"})
    r = client.post(
        "/parse-list", json={"text": "חלב"}, headers={"Origin": get_settings().cors_origins[0]}
    )
    assert r.status_code == 429
    assert 1 <= int(r.headers["retry-after"]) <= 60
    assert r.headers["access-control-allow-origin"] == get_settings().cors_origins[0]


def test_code_guessing_is_limited_across_accounts_by_address(client, db) -> None:
    codes = []
    for _ in range(24):
        uid = uuid.uuid4()
        db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
        codes.append(
            client.post("/beta/join", json={"code": "WRONG-CODE"}, headers=h(uid)).status_code
        )
    assert codes[:20] == [404] * 20 and set(codes[20:]) == {429}


# --- windows ------------------------------------------------------------------------------------------


def test_a_window_rolls_over_and_the_hour_still_counts(dsn) -> None:
    now = [T0]
    rl = make_limiter(dsn, clock=lambda: now[0])
    key = [("w:principal", "u:1", 60, 3), ("w:principal", "u:1", 3600, 5)]
    assert [rl.hit(key) for _ in range(3)] == [None] * 3
    now[0] = T0 + 5
    wait = rl.hit(key)  # the fourth in the minute
    assert wait == 55  # until the minute window ends
    now[0] = T0 + 60  # the next minute: the minute count starts again
    assert rl.hit(key) is None  # hour count is now 5 (the refused one counted): still within
    assert rl.hit(key) is not None  # the sixth of the hour
    now[0] = T0 + 120
    wait = rl.hit(key)
    assert wait == (T0 // 3600 + 1) * 3600 - (T0 + 120)  # the hour is the window that is full
    now[0] = (T0 // 3600 + 1) * 3600 + 60  # the next hour
    assert rl.hit(key) is None


def test_the_windows_are_cut_from_one_clock_not_from_the_caller(dsn) -> None:
    """Two processes whose own clocks differ still land in the same window: the database's."""
    a, b = make_limiter(dsn, clock=lambda: None), make_limiter(dsn, clock=lambda: None)
    a.hit([("c:principal", "u:1", 3600, 100)])
    b.hit([("c:principal", "u:1", 3600, 100)])
    rows = _rows(dsn)
    assert len(rows) == 1 and rows[0][4] == 2 and rows[0][3] % 3600 == 0


# --- cleanup ----------------------------------------------------------------------------------------------


def test_expired_windows_are_deleted_and_live_ones_kept(dsn) -> None:
    now = [T0]
    rl = make_limiter(dsn, clock=lambda: now[0])
    for key in ("u:1", "u:2", "u:3"):
        rl.hit([("x:principal", key, 60, 5), ("x:principal", key, 3600, 50)])
    assert len(_rows(dsn)) == 6
    assert rl.cleanup() == 0  # nothing has ended
    now[0] = T0 + 60 + 59  # the minute windows ended 59 s ago: inside the one-minute grace
    assert rl.cleanup() == 0
    now[0] = T0 + 60 + 61
    assert rl.cleanup() == 3  # the minute windows are gone, the hour windows are live
    assert {r[2] for r in _rows(dsn)} == {3600}
    now[0] = (T0 // 3600 + 1) * 3600 + 61
    assert rl.cleanup() == 3 and _rows(dsn) == []


def test_the_cleanup_runs_by_itself_without_blocking_a_request(dsn) -> None:
    now = [T0]
    rl = make_limiter(dsn, clock=lambda: now[0], cleanup_every_s=0)  # every hit may clean up
    rl.hit([("y:principal", "u:old", 60, 5)])
    now[0] = T0 + 600
    assert rl.hit([("y:principal", "u:new", 60, 5)]) is None
    assert [r[1] for r in _rows(dsn)] == ["u:new"]
    # a limiter that has not waited long enough does not clean up at all
    slow = make_limiter(dsn, clock=lambda: now[0], cleanup_every_s=3600)
    now[0] = T0 + 1200
    slow.hit([("y:principal", "u:newer", 60, 5)])
    assert sorted(r[1] for r in _rows(dsn)) == ["u:new", "u:newer"]


def test_only_one_process_cleans_at_a_time(dsn) -> None:
    now = [T0]
    rl = make_limiter(dsn, clock=lambda: now[0])
    rl.hit([("z:principal", "u:1", 60, 5)])
    now[0] = T0 + 1000
    with psycopg.connect(dsn, autocommit=True) as other:
        other.execute("SELECT pg_advisory_lock(hashtext('smartcart.api_rate_limits.cleanup'))")
        assert rl.cleanup() == 0  # somebody else holds it: this one skips
        other.execute("SELECT pg_advisory_unlock_all()")
    assert rl.cleanup() == 1


def test_a_failing_cleanup_never_fails_the_request(dsn, caplog) -> None:
    class Flaky:
        def __init__(self, conn):
            self.conn = conn

        def execute(self, query, params=None):
            if "DELETE" in str(query):
                raise psycopg.OperationalError("boom")
            return self.conn.execute(query, params)

    @contextmanager
    def connect():
        with psycopg.connect(dsn, autocommit=True) as conn:
            yield Flaky(conn)

    rl = SharedLimiter(connect, cleanup_every_s=0)
    with caplog.at_level(logging.WARNING, logger="smartcart_api.ratelimit"):
        assert rl.hit([("f:principal", "u:1", 60, 5)]) is None
    assert "cleanup failed" in caplog.text


# --- one fast statement ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "statements", "rows"),
    [
        ("GET", "/search", {"params": {"q": "חלב"}}, 1, 2),  # search: a minute and an hour window
        ("POST", "/compare", {"json": {}}, 1, 1),  # a minute window
        ("GET", "/health", {}, 0, 0),  # only the in-process ceiling: no statement at all
    ],
)
def test_a_hot_route_costs_at_most_one_statement(
    client, catalog, dsn, method, path, kwargs, statements, rows
) -> None:
    ran: list[str] = []
    use_shared_limiter(SharedLimiter(Counting(dsn, ran), clock=lambda: T0, cleanup_every_s=3600))
    client.request(method, path, **kwargs)
    assert len(ran) == statements, ran
    assert len(_rows(dsn)) == rows


def test_the_ceiling_is_counted_in_the_process_not_in_the_database(
    client, dsn, monkeypatch
) -> None:
    assert "all" in ratelimit.LOCAL_ONLY_BUCKETS
    ran: list[str] = []
    use_shared_limiter(SharedLimiter(Counting(dsn, ran)))
    for _ in range(3):
        client.get("/health")
    assert ran == [] and _rows(dsn) == []
    assert ratelimit.limiter._hits[("all:principal", "ip:testclient")]  # counted here


def test_a_signed_in_route_with_two_buckets_counts_each_in_one_statement(client, db, dsn) -> None:
    ran: list[str] = []
    use_shared_limiter(SharedLimiter(Counting(dsn, ran), clock=lambda: T0, cleanup_every_s=3600))
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    client.post("/beta/join", json={"code": "WRONG-CODE"}, headers=h(uid))
    assert len(ran) == 2  # by account, and by address
    assert {(r[0], r[2]) for r in _rows(dsn)} == {
        ("beta-join:principal", 60),
        ("beta-join:principal", 3600),
        ("beta-join:ip", 60),
        ("beta-join:ip", 3600),
    }


def test_the_statement_is_an_upsert_with_no_read_first() -> None:
    sql = " ".join(ratelimit._HIT_SQL.split())
    assert sql.count("INSERT INTO api_rate_limits") == 1
    assert "ON CONFLICT (bucket, client_key, window_seconds, window_start) DO UPDATE" in sql
    assert "SELECT * FROM api_rate_limits" not in sql


def test_the_real_pool_is_autocommit_and_counts(client, catalog, dsn, monkeypatch) -> None:
    """The default connection path: the limiter's own pool on DATABASE_URL."""
    monkeypatch.setenv("DATABASE_URL", dsn)
    get_settings.cache_clear()
    use_shared_limiter(None)
    for _ in range(3):
        assert client.post("/parse-list", json={"text": "חלב"}).status_code == 200
    by_bucket = {r[0]: r[4] for r in _rows(dsn) if r[2] == 60}
    assert by_bucket == {"parse-list:principal": 3}


# --- the API role's grants ------------------------------------------------------------------------------

ROLE = "zz_limiter_probe"


@pytest.fixture
def api_login_role(db: psycopg.Connection) -> str:
    db.execute(f"CREATE ROLE {ROLE} NOLOGIN NOINHERIT")
    if db.info.server_version >= 160000:
        db.execute(f"GRANT {ROLE} TO CURRENT_USER WITH SET TRUE")
    db.execute("SELECT smartcart_grant_api_role(%s)", (ROLE,))
    return ROLE


def test_the_api_role_runs_the_limiter_and_can_do_nothing_else_to_the_table(
    db: psycopg.Connection, api_login_role: str
) -> None:
    def priv(kind: str, what: str, how: str) -> bool:
        if kind == "table":
            q = "SELECT has_table_privilege(%s, 'api_rate_limits', %s)"
            return db.execute(q, (what, how)).fetchone()[0]
        q = "SELECT has_column_privilege(%s, 'api_rate_limits', %s, 'UPDATE')"
        return db.execute(q, (api_login_role, what)).fetchone()[0]

    assert priv("table", api_login_role, "SELECT") and priv("table", api_login_role, "INSERT")
    assert priv("table", api_login_role, "DELETE")
    assert priv("column", "hits", "UPDATE")
    for column in ("bucket", "client_key", "window_seconds", "window_start", "window_end"):
        assert not priv("column", column, "UPDATE"), column
    for how in ("TRUNCATE", "REFERENCES", "TRIGGER"):
        assert not priv("table", api_login_role, how), how
    assert db.execute(
        "SELECT count(*) FROM pg_policies WHERE tablename = 'api_rate_limits' AND %s = ANY(roles)",
        (api_login_role,),
    ).fetchone() == (1,)

    @contextmanager
    def connect():
        yield db

    rl = SharedLimiter(connect, clock=lambda: T0, cleanup_every_s=3600)
    db.execute(f"SET LOCAL ROLE {api_login_role}")
    assert [rl.hit([("g:principal", "u:1", 60, 2)]) for _ in range(3)] == [None, None, 60.0]
    assert rl.hit([("g:principal", "u:1", 3600, 9)]) is None
    rl2 = SharedLimiter(connect, clock=lambda: T0 + 10_000)
    assert rl2.cleanup() == 2  # the cleanup is a plain DELETE under the role
    for stmt in (
        "UPDATE api_rate_limits SET window_start = 0",
        "TRUNCATE api_rate_limits",
        "ALTER TABLE api_rate_limits DISABLE ROW LEVEL SECURITY",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.transaction():
                db.execute(stmt)


def test_nobody_else_can_reach_the_table(db: psycopg.Connection, api_login_role: str) -> None:
    roles = [
        r
        for r in ("anon", "authenticated", "smartcart_app", "public")
        if r == "public" or db.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (r,)).fetchone()
    ]
    for role in roles:
        for how in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert not db.execute(
                "SELECT has_table_privilege(%s, 'api_rate_limits', %s)", (role, how)
            ).fetchone()[0], (role, how)
    assert db.execute(
        "SELECT relrowsecurity FROM pg_class WHERE relname = 'api_rate_limits'"
        " AND relnamespace = current_schema()::regnamespace"
    ).fetchone() == (True,)


def test_granting_twice_keeps_one_policy(db: psycopg.Connection, api_login_role: str) -> None:
    db.execute("SELECT smartcart_grant_api_role(%s)", (api_login_role,))
    assert db.execute(
        "SELECT count(*) FROM pg_policies WHERE tablename = 'api_rate_limits'"
    ).fetchone() == (1,)


# --- the database is not there --------------------------------------------------------------------------


@contextmanager
def _unavailable():
    raise psycopg.OperationalError("connection refused")
    yield  # pragma: no cover


class Unavailable:
    calls = 0

    def __call__(self):
        Unavailable.calls += 1
        return _unavailable()


def test_an_outage_degrades_to_per_process_counting_with_a_warning(client, catalog, caplog) -> None:
    Unavailable.calls = 0
    use_shared_limiter(SharedLimiter(Unavailable()))
    with caplog.at_level(logging.WARNING, logger="smartcart_api.ratelimit"):
        codes = [client.get("/search", params={"q": "חלב"}).status_code for _ in range(122)]
    assert "shared rate limiter unavailable" in caplog.text
    assert codes[:120] == [200] * 120 and codes[120:] == [429, 429]  # /search: 120 a minute, here
    # the breaker: the database was asked once, not 122 times
    assert Unavailable.calls == 1


def test_the_warning_is_not_repeated_for_every_request(client, catalog, caplog) -> None:
    use_shared_limiter(SharedLimiter(Unavailable()))
    with caplog.at_level(logging.WARNING, logger="smartcart_api.ratelimit"):
        for _ in range(10):
            client.get("/search", params={"q": "חלב"})
    assert caplog.text.count("shared rate limiter unavailable") == 1


def test_the_database_comes_back_and_the_shared_counts_resume(client, catalog, dsn):
    use_shared_limiter(SharedLimiter(Unavailable()))
    assert client.get("/search", params={"q": "חלב"}).status_code == 200
    assert _rows(dsn) == []
    use_shared_limiter(make_limiter(dsn))  # a healthy database, and the breaker cleared
    assert client.get("/search", params={"q": "חלב"}).status_code == 200
    assert {r[0] for r in _rows(dsn)} == {"search:principal"}  # counted in the table again


def test_the_breaker_lets_the_database_back_in_after_a_few_seconds(
    client, catalog, dsn, monkeypatch
):
    ticks = [1000.0]
    monkeypatch.setattr(ratelimit, "time", SimpleNamespace(monotonic=lambda: ticks[0]))
    Unavailable.calls = 0
    use_shared_limiter(SharedLimiter(Unavailable()))
    for _ in range(3):
        client.get("/search", params={"q": "חלב"})
    assert Unavailable.calls == 1  # the breaker is open
    ticks[0] += ratelimit.BREAKER_S + 0.1
    client.get("/search", params={"q": "חלב"})
    assert Unavailable.calls == 2  # asked again


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("POST", "/beta/join", {"json": {"code": "ANY-CODE"}}),
        ("POST", "/lists/accept/some-token", {}),
    ],
)
def test_the_routes_that_stop_guessing_fail_closed(client, db, method, path, kwargs) -> None:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    use_shared_limiter(SharedLimiter(Unavailable()))
    r = client.request(method, path, headers=h(uid), **kwargs)
    assert r.status_code == 503
    assert int(r.headers["retry-after"]) >= 1
    assert "connection refused" not in r.text  # no detail of the failure


def test_a_missing_table_is_an_outage_not_a_500(client, catalog, dsn) -> None:
    """The migration not applied yet (deploying the code first): the table is missing, the
    statement fails, the request is served."""
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("ALTER TABLE api_rate_limits RENAME TO api_rate_limits_moved")
    try:
        use_shared_limiter(make_limiter(dsn))
        assert client.post("/parse-list", json={"text": "חלב"}).status_code == 200
    finally:
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("ALTER TABLE api_rate_limits_moved RENAME TO api_rate_limits")
