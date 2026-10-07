"""Database access for the API: one psycopg pool per process and the FastAPI dependency.

``get_conn`` yields a pooled connection for the duration of a request; the pool commits when the
request succeeds and rolls back when it raises. Tests override ``get_conn`` with the rolled-back
test connection (``app.dependency_overrides[get_conn]``), so nothing they do is committed.
"""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
from fastapi import HTTPException
from psycopg_pool import ConnectionPool

from smartcart_api.settings import get_settings

_pool: ConnectionPool | None = None


def _configure(conn: psycopg.Connection) -> None:
    conn.execute("SET TIME ZONE 'UTC'")
    conn.commit()


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        if not settings.database_url:
            raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")
        _pool = ConnectionPool(
            settings.database_url,
            min_size=settings.pool_min,
            max_size=settings.pool_max,
            configure=_configure,
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_conn() -> Iterator[psycopg.Connection]:
    with get_pool().connection() as conn:
        yield conn
