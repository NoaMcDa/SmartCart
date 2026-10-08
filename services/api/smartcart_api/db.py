"""Database access for the API: one psycopg pool per process and the FastAPI dependency.

``get_conn`` yields a pooled connection for the duration of a request; the pool commits when the
request succeeds and rolls back when it raises. Tests override ``get_conn`` with the rolled-back
test connection (``app.dependency_overrides[get_conn]``), so nothing they do is committed.

Poolers. ``DB_POOLER_MODE`` says what sits between the API and Postgres:

* ``session`` (default; a direct connection or the session pooler): a pooled connection keeps its
  session, so the time zone is set once per connection (``SET TIME ZONE 'UTC'``) and psycopg may
  prepare a statement on the server after five executions (``prepare_threshold``).
* ``transaction`` (the transaction pooler, Supabase port 6543): the server connection behind a
  client connection can change between transactions, so nothing may live in the session. Server
  prepared statements are switched off (``prepare_threshold=None``: a statement prepared on one
  server connection does not exist on the next) and the time zone is set per transaction
  (``SET LOCAL TIME ZONE 'UTC'`` at the start of each request). The rest of the code already keeps
  its settings transaction-local (``SET LOCAL ROLE``, ``set_config(..., true)`` for the JWT claims
  and the trigram threshold).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
from fastapi import HTTPException
from psycopg_pool import ConnectionPool

from smartcart_api.settings import get_settings

POOLER_MODE_ENV = "DB_POOLER_MODE"
POOLER_MODES = ("session", "transaction")

_pool: ConnectionPool | None = None


def pooler_mode() -> str:
    """``session`` (default) or ``transaction``, from ``DB_POOLER_MODE``."""
    mode = os.environ.get(POOLER_MODE_ENV, "").strip().lower() or "session"
    if mode not in POOLER_MODES:
        raise ValueError(f"{POOLER_MODE_ENV} must be one of {POOLER_MODES}, got {mode!r}")
    return mode


def _configure(conn: psycopg.Connection) -> None:
    conn.execute("SET TIME ZONE 'UTC'")
    conn.commit()


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        if not settings.database_url:
            raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")
        transaction_mode = pooler_mode() == "transaction"
        _pool = ConnectionPool(
            settings.database_url,
            min_size=settings.pool_min,
            max_size=settings.pool_max,
            # Nothing may live in the session behind a transaction pooler.
            kwargs={"prepare_threshold": None} if transaction_mode else {},
            configure=None if transaction_mode else _configure,
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_conn() -> Iterator[psycopg.Connection]:
    """Routes depend on this with ``scope="function"`` so the pool commits (or rolls back) as
    soon as the endpoint returns, before the response is sent. With the default request scope
    FastAPI runs this exit code after the response, so a client could read its own write too
    early: ``PUT /me/profile`` answered 200 and the next ``POST /me/alerts`` found no location.
    """
    with get_pool().connection() as conn:
        if pooler_mode() == "transaction":
            conn.execute("SET LOCAL TIME ZONE 'UTC'")
        yield conn
