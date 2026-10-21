"""Per-client request limits for the routes that cost something (docs/security-review.md).

A sliding window per (bucket, client). The client is the signed-in user when the request carries a
token that verifies (a person on a shared mobile address is not throttled by their neighbours), else
the peer address. ``request.client`` is the TCP peer, or the address from ``X-Forwarded-For`` when
the peer is one of uvicorn's ``FORWARDED_ALLOW_IPS`` (default 127.0.0.1: the Caddy on the same
host, ``infra/vps``). An attacker cannot choose their own key: a forged token fails verification
and falls back to the address.

The counters live in the process. With ``WEB_CONCURRENCY`` workers the effective limit is the
configured one times the worker count; that is deliberate (no new moving part before the beta) and
the numbers below are chosen with it in mind. ``POST /events`` additionally has a per-session limit
in the database (routes/events.py), and ``POST /parse-image`` the monthly cap (ocr/usage.py).

Over the limit: 429 with ``Retry-After``. ``API_RATE_LIMIT=0`` switches all of it off (load tests).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from smartcart_api.auth import User, optional_user
from smartcart_api.settings import get_settings

_MAX_KEYS = 50_000  # a flood of distinct addresses cannot grow the table without bound


class RateLimiter:
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


def limit(
    bucket: str,
    per_minute: int,
    *,
    per_hour: int | None = None,
    by: str = "principal",
    methods: tuple[str, ...] | None = None,
) -> Callable[..., None]:
    """A FastAPI dependency: at most ``per_minute`` (and ``per_hour``) requests per client.

    ``by="ip"`` always keys on the address (for a limit that must hold across accounts, such as
    invite-code guessing). ``methods`` restricts the limit to those HTTP methods."""
    windows: tuple[tuple[int, float], ...] = ((per_minute, 60.0),)
    if per_hour is not None:
        windows += ((per_hour, 3600.0),)

    def dependency(
        request: Request,
        user: Annotated[User | None, Depends(_principal)],
    ) -> None:
        if not get_settings().rate_limit_enabled:
            return
        if methods is not None and request.method not in methods:
            return
        key = client_key(request, None if by == "ip" else user)
        wait = limiter.check(f"{bucket}:{by}", key, windows)
        if wait is not None:
            raise HTTPException(
                status_code=429,
                detail="too many requests, try again shortly",
                headers={"Retry-After": str(int(wait + 0.999))},
            )

    return dependency


WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")
