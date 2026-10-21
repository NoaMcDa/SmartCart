"""Per-client request limits for the routes that cost something (docs/security-review.md).

A window per (bucket, client). The client is the signed-in user when the request carries a token
that verifies (a person on a shared mobile address is not throttled by their neighbours), else the
peer address. ``request.client`` is the TCP peer, or the address from ``X-Forwarded-For`` when the
peer is one of uvicorn's ``FORWARDED_ALLOW_IPS`` (default 127.0.0.1: the Caddy on the same host,
``infra/vps``). An attacker cannot choose their own key: a forged token fails verification and falls
back to the address.

Two backends (``API_RATE_LIMIT_BACKEND``):

* ``memory`` (default): the counters live in the process, a sliding window per (bucket, client).
  With ``WEB_CONCURRENCY`` workers the effective limit is the configured one times the workers.
  Nothing else is needed: laptops, CI, a single worker.
* ``postgres``: the counters live in ``api_rate_limits`` (migration 20261022120000), a fixed window
  per (bucket, client, window length), so every worker and replica shares them. One atomic upsert
  per limit carries its windows, so a hot read route pays one fast statement, on a small pool of
  its own and an autocommit connection, not on the request's transaction. The coarse ceiling on
  every route (``all``) stays in the process: no statement at all for a route with no limit of its own. A refused request still counts, and the
  edge of a fixed window can pass up to twice the limit across the boundary: both are accepted for a
  guard whose numbers are proposals (docs/security-review.md). If the database cannot answer, the
  request falls back to the in-memory counters (logged, retried after a few seconds), except on the
  routes that guard guessing (``fail_closed=True``: invite and share codes), which answer 503.

``POST /events`` additionally has a per-session limit in the database (routes/events.py), and
``POST /parse-image`` the monthly cap (ocr/usage.py).

Over the limit: 429 with ``Retry-After``. ``API_RATE_LIMIT=0`` switches all of it off (load tests).
"""

from __future__ import annotations

import atexit
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Annotated

import psycopg
from fastapi import Depends, Header, HTTPException, Request
from psycopg_pool import ConnectionPool

from smartcart_api.auth import User, optional_user
from smartcart_api.settings import get_settings

log = logging.getLogger("smartcart_api.ratelimit")

# The coarse ceiling on every route stays in the process even with the shared counters: counting it
# in the database would cost a statement on every request, including the routes that have no limit
# of their own, and its job is to stop a flood, for which "times the workers" is close enough. Every
# route class with a tighter limit is counted in the database.
LOCAL_ONLY_BUCKETS = frozenset({"all"})

# The route classes whose limit is what stops guessing a secret (a beta code, a share link): with
# the shared counters down they answer 503 rather than count per process (a guesser who can reach
# N workers would get N times the tries). Everything else degrades to the per-process counters.
FAIL_CLOSED_BUCKETS = frozenset({"beta-join", "accept-share"})

_MAX_KEYS = 50_000  # a flood of distinct addresses cannot grow the table without bound


class RateLimiter:
    """The in-memory sliding-window counters (the ``memory`` backend and the fallback)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: dict[tuple[str, str], deque[float]] = {}

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def check(self, bucket: str, key: str, windows: tuple[tuple[int, float], ...]) -> float | None:
        """Count one hit; the seconds to wait when a window (``(limit, seconds)``) is full."""
        now = self._clock()
        longest = max(seconds for _, seconds in windows)
        with self._lock:
            if len(self._hits) >= _MAX_KEYS:
                self._purge(now)
            q = self._hits.setdefault((bucket, key), deque())
            while q and q[0] <= now - longest:
                q.popleft()
            for limit, seconds in windows:
                inside = [t for t in q if t > now - seconds]
                if len(inside) >= limit:
                    return max(1.0, inside[0] + seconds - now)
            q.append(now)
            return None

    def _purge(self, now: float) -> None:
        for k in [k for k, q in self._hits.items() if not q or q[-1] <= now - 3600]:
            del self._hits[k]
        if len(self._hits) >= _MAX_KEYS:  # still full of live keys: start over rather than grow
            self._hits.clear()


limiter = RateLimiter()


def client_key(request: Request, user: User | None) -> str:
    if user is not None:
        return f"u:{user.id}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def _principal(
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    """The verified user, or None for no token or a token that does not verify (that request is
    then limited by address, and the route's own auth answers 401)."""
    try:
        return optional_user(authorization)
    except HTTPException:
        return None


# --- the shared (Postgres) counters ---------------------------------------------------------------

# One statement: cut the windows from the database's clock, count one hit in each (inserting the
# row for a new window), and return the counts. ORDER BY gives concurrent requests of one client the
# same lock order. ``now`` is NULL in production (the database's clock) and a fixed epoch in tests.
_HIT_SQL = """
WITH t AS (
  SELECT coalesce(%(now)s::bigint, floor(extract(epoch FROM clock_timestamp()))::bigint) AS now
), q AS (
  SELECT * FROM unnest(%(buckets)s::text[], %(keys)s::text[], %(wins)s::integer[])
    AS u(bucket, client_key, win)
)
INSERT INTO api_rate_limits AS r (bucket, client_key, window_seconds, window_start, window_end, hits)
SELECT q.bucket, q.client_key, q.win,
       (t.now / q.win) * q.win, (t.now / q.win) * q.win + q.win, 1
FROM q CROSS JOIN t
ORDER BY q.bucket, q.client_key, q.win
ON CONFLICT (bucket, client_key, window_seconds, window_start)
DO UPDATE SET hits = r.hits + 1
RETURNING r.bucket, r.client_key, r.window_seconds, r.hits, r.window_end, (SELECT now FROM t)
"""

# Delete the windows that ended more than a minute ago. The advisory lock lets one process at a time
# do it; the others get zero rows and carry on.
_CLEANUP_SQL = """
WITH t AS (
  SELECT coalesce(%(now)s::bigint, floor(extract(epoch FROM clock_timestamp()))::bigint) AS now
), l AS (
  SELECT pg_try_advisory_xact_lock(hashtext('smartcart.api_rate_limits.cleanup')) AS ok
)
DELETE FROM api_rate_limits
WHERE (SELECT ok FROM l) AND window_end < (SELECT now FROM t) - 60
"""

CLEANUP_EVERY_S = 300.0
BREAKER_S = (
    5.0  # after a failure, use the local counters this long before asking the database again
)
POOL_TIMEOUT_S = 0.5  # wait for a limiter connection at most this long
_WARN_EVERY_S = 30.0

# (bucket, client key, window seconds, limit)
Row = tuple[str, str, int, int]


class SharedLimiter:
    """Fixed-window counters in ``api_rate_limits``. ``connect`` yields an autocommit connection;
    ``clock`` gives the epoch second to cut windows from, or None for the database's own clock."""

    def __init__(
        self,
        connect: Callable[[], AbstractContextManager[psycopg.Connection]],
        *,
        clock: Callable[[], int | None] = lambda: None,
        cleanup_every_s: float = CLEANUP_EVERY_S,
    ) -> None:
        self._connect = connect
        self._clock = clock
        self._cleanup_every_s = cleanup_every_s
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def hit(self, rows: list[Row]) -> float | None:
        """Count one hit in each window; the seconds to wait when any is over its limit.

        Raises whatever the database raises (the caller decides what a failure means)."""
        limits: dict[tuple[str, str, int], int] = {}
        for bucket, key, window, limit in rows:
            k = (bucket, key, window)
            limits[k] = min(limit, limits.get(k, limit))  # the same window twice: the tighter one
        if not limits:
            return None
        ks = sorted(limits)
        params = {
            "now": self._clock(),
            "buckets": [k[0] for k in ks],
            "keys": [k[1] for k in ks],
            "wins": [k[2] for k in ks],
        }
        with self._connect() as conn:
            result = conn.execute(_HIT_SQL, params).fetchall()
            self._maybe_cleanup(conn)
        wait: float | None = None
        for bucket, key, window, hits, window_end, now in result:
            if hits > limits[(bucket, key, window)]:
                wait = max(wait or 1.0, float(window_end - now))
        return wait

    def cleanup(self) -> int:
        """Delete the windows that ended; the number of rows removed."""
        with self._connect() as conn:
            return self._cleanup(conn)

    def _cleanup(self, conn: psycopg.Connection) -> int:
        return conn.execute(_CLEANUP_SQL, {"now": self._clock()}).rowcount

    def _maybe_cleanup(self, conn: psycopg.Connection) -> None:
        with self._lock:
            if time.monotonic() - self._last_cleanup < self._cleanup_every_s:
                return
            self._last_cleanup = time.monotonic()  # claimed: one thread per process tries
        try:
            self._cleanup(conn)
        except Exception as exc:  # noqa: BLE001 - never fail a request over housekeeping
            log.warning("rate limit cleanup failed: %s", type(exc).__name__)


_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def _limiter_pool() -> ConnectionPool:
    """The limiter's own small pool: autocommit, so the statement is one round trip and is never
    part of (or rolled back with) a request's transaction, and it cannot starve the request pool."""
    global _pool
    with _pool_lock:
        if _pool is None:
            from smartcart_api.db import pooler_mode

            settings = get_settings()
            if not settings.database_url:
                raise RuntimeError("DATABASE_URL is not configured")
            kwargs: dict = {"autocommit": True, "connect_timeout": 2}
            if pooler_mode() == "transaction":
                kwargs["prepare_threshold"] = None
            _pool = ConnectionPool(
                settings.database_url,
                min_size=1,
                max_size=settings.rate_limit_pool_max,
                kwargs=kwargs,
                open=True,
            )
            atexit.register(close_pool)
        return _pool


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None


@contextmanager
def _pool_connection():
    with _limiter_pool().connection(timeout=POOL_TIMEOUT_S) as conn:
        yield conn


_shared: SharedLimiter | None = None
_breaker_until = 0.0
_last_warning = float("-inf")


def shared_limiter() -> SharedLimiter:
    global _shared
    if _shared is None:
        _shared = SharedLimiter(_pool_connection)
    return _shared


def use_shared_limiter(shared: SharedLimiter | None) -> None:
    """Replace (or, with None, drop) the process's shared limiter, and clear the failure
    breaker: for tests."""
    global _shared, _breaker_until, _last_warning
    _shared = shared
    _breaker_until = 0.0
    _last_warning = float("-inf")


# --- the dependency -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class LimitSpec:
    bucket: str
    windows: tuple[tuple[int, float], ...]  # (limit, seconds)
    by: str = "principal"
    methods: tuple[str, ...] | None = None
    fail_closed: bool = False

    @property
    def name(self) -> str:
        return f"{self.bucket}:{self.by}"


def _too_many(wait: float) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail="too many requests, try again shortly",
        headers={"Retry-After": str(int(wait + 0.999))},
    )


def _applies(spec: LimitSpec, request: Request) -> bool:
    return spec.methods is None or request.method in spec.methods


def _enforce_local(request: Request, user: User | None, specs: list[LimitSpec]) -> None:
    for spec in specs:
        if not _applies(spec, request):
            continue
        key = client_key(request, None if spec.by == "ip" else user)
        wait = limiter.check(spec.name, key, spec.windows)
        if wait is not None:
            raise _too_many(wait)


def _warn_unavailable(exc: Exception) -> None:
    global _last_warning
    now = time.monotonic()
    if now - _last_warning >= _WARN_EVERY_S:
        _last_warning = now
        log.warning(
            "shared rate limiter unavailable (%s): counting per process for now", type(exc).__name__
        )


def _enforce_shared(request: Request, user: User | None, spec: LimitSpec) -> None:
    """Count this limit in the database: one statement, carrying every window of the limit."""
    global _breaker_until
    if not _applies(spec, request):
        return
    if spec.bucket in LOCAL_ONLY_BUCKETS:
        _enforce_local(request, user, [spec])
        return
    if time.monotonic() < _breaker_until:
        failure: Exception = RuntimeError("recently failed")
    else:
        key = client_key(request, None if spec.by == "ip" else user)
        rows: list[Row] = [(spec.name, key, int(secs), n) for n, secs in spec.windows]
        try:
            wait = shared_limiter().hit(rows)
        except Exception as exc:  # noqa: BLE001 - a limiter outage is not the caller's problem
            failure = exc
            _breaker_until = time.monotonic() + BREAKER_S
            _warn_unavailable(exc)
        else:
            if wait is not None:
                raise _too_many(wait)
            return
    # The database could not count. Routes that guard guessing refuse; the rest count here.
    if spec.fail_closed:
        raise HTTPException(
            status_code=503,
            detail="temporarily unavailable, try again shortly",
            headers={"Retry-After": str(int(BREAKER_S))},
        ) from failure
    _enforce_local(request, user, [spec])


def limit(
    bucket: str,
    per_minute: int,
    *,
    per_hour: int | None = None,
    by: str = "principal",
    methods: tuple[str, ...] | None = None,
    fail_closed: bool = False,
) -> Callable[..., None]:
    """A FastAPI dependency: at most ``per_minute`` (and ``per_hour``) requests per client.

    ``by="ip"`` always keys on the address (for a limit that must hold across accounts, such as
    invite-code guessing). ``methods`` restricts the limit to those HTTP methods. ``fail_closed``
    answers 503 instead of counting per process when the shared counters are unavailable: for the
    routes whose limit is what stops guessing (docs/security-review.md, R3)."""
    windows: tuple[tuple[int, float], ...] = ((per_minute, 60.0),)
    if per_hour is not None:
        windows += ((per_hour, 3600.0),)
    spec = LimitSpec(bucket, windows, by, methods, fail_closed or bucket in FAIL_CLOSED_BUCKETS)

    def dependency(
        request: Request,
        user: Annotated[User | None, Depends(_principal)],
    ) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        if settings.rate_limit_backend == "postgres":
            _enforce_shared(request, user, spec)
        else:
            _enforce_local(request, user, [spec])

    return dependency


WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")
