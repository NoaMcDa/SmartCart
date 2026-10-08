"""DB_POOLER_MODE: the API behind the session pooler (default) or the transaction pooler."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from psycopg.conninfo import make_conninfo

from smartcart_api import db as apidb
from smartcart_api.settings import get_settings


@pytest.fixture(autouse=True)
def fresh_pool() -> Iterator[None]:
    apidb.close_pool()
    get_settings.cache_clear()
    yield
    apidb.close_pool()
    get_settings.cache_clear()


def test_mode_defaults_to_session_and_rejects_unknown_values(monkeypatch) -> None:
    monkeypatch.delenv("DB_POOLER_MODE", raising=False)
    assert apidb.pooler_mode() == "session"
    monkeypatch.setenv("DB_POOLER_MODE", "")
    assert apidb.pooler_mode() == "session"
    monkeypatch.setenv("DB_POOLER_MODE", " Transaction ")
    assert apidb.pooler_mode() == "transaction"
    monkeypatch.setenv("DB_POOLER_MODE", "statement")
    with pytest.raises(ValueError, match="DB_POOLER_MODE"):
        apidb.pooler_mode()


@pytest.mark.parametrize(("mode", "prepare", "configured"), [
    ("session", {}, True),
    ("transaction", {"prepare_threshold": None}, False),
])
def test_pool_is_built_for_the_mode(monkeypatch, mode, prepare, configured) -> None:
    seen: dict = {}

    class FakePool:
        def __init__(self, conninfo, **kw) -> None:
            seen.update(kw, conninfo=conninfo)

        def close(self) -> None:
            pass

    monkeypatch.setattr(apidb, "ConnectionPool", FakePool)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/d")
    monkeypatch.setenv("DB_POOLER_MODE", mode)
    get_settings.cache_clear()
    apidb.get_pool()
    assert seen["kwargs"] == prepare
    assert (seen["configure"] is apidb._configure) is configured
    assert (seen["configure"] is None) is (not configured)


def _use(monkeypatch, dsn: str, mode: str) -> None:
    # A server whose own default time zone is not UTC, to see who sets it and for how long.
    monkeypatch.setenv("DATABASE_URL", make_conninfo(dsn, options="-c timezone=Asia/Jerusalem"))
    monkeypatch.setenv("DB_POOLER_MODE", mode)
    monkeypatch.setenv("API_POOL_MIN", "1")
    monkeypatch.setenv("API_POOL_MAX", "1")
    get_settings.cache_clear()


@pytest.mark.db
def test_session_mode_sets_utc_once_per_connection(monkeypatch, api_dsn: str) -> None:
    _use(monkeypatch, api_dsn, "session")
    request = apidb.get_conn()
    conn = next(request)
    assert conn.execute("SHOW TIME ZONE").fetchone()[0] == "UTC"
    request.close()
    with apidb.get_pool().connection() as other:  # the session keeps it between requests
        assert other.execute("SHOW TIME ZONE").fetchone()[0] == "UTC"


@pytest.mark.db
def test_transaction_mode_sets_utc_per_transaction_and_prepares_nothing(monkeypatch, api_dsn: str) -> None:
    _use(monkeypatch, api_dsn, "transaction")
    request = apidb.get_conn()
    conn = next(request)
    assert conn.prepare_threshold is None
    assert conn.execute("SHOW TIME ZONE").fetchone()[0] == "UTC"  # SET LOCAL, for this request
    for i in range(12):  # past the default threshold of 5 that would prepare the statement
        conn.execute("SELECT %s::int + 1", (i,))
    assert conn.execute("SELECT count(*) FROM pg_prepared_statements").fetchone()[0] == 0
    request.close()  # the pool commits; SET LOCAL ends with the transaction
    with apidb.get_pool().connection() as other:
        assert other.execute("SHOW TIME ZONE").fetchone()[0] == "Asia/Jerusalem"


@pytest.mark.db
def test_session_mode_does_prepare_after_the_threshold(monkeypatch, api_dsn: str) -> None:
    """The control for the test above: the default would have prepared the statement."""
    _use(monkeypatch, api_dsn, "session")
    request = apidb.get_conn()
    conn = next(request)
    for i in range(12):
        conn.execute("SELECT %s::int + 1", (i,))
    assert conn.execute("SELECT count(*) FROM pg_prepared_statements").fetchone()[0] >= 1
    request.close()
