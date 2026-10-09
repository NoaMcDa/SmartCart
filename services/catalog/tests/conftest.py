"""Reuse the ingest suite's database fixtures (``db``, ``database``, ``pg_dsn``).

They live in services/ingest/tests/conftest.py (DATABASE_URL, or a throwaway Postgres cluster
migrated with the repo's migrations). That file is loaded by path and its fixtures are
re-exported here, so the catalog tests get the same database without importing across test
packages. This directory has no ``__init__.py`` on purpose: services/ingest/tests is already the
top-level package ``tests``.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from smartcart_ingest import db as dbmod

_PATH = Path(__file__).resolve().parents[2] / "ingest" / "tests" / "conftest.py"
_spec = importlib.util.spec_from_file_location("_ingest_test_fixtures", _PATH)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module  # dataclasses looks the module up by name
_spec.loader.exec_module(_module)

pg_dsn = _module.pg_dsn
database = _module.database
db = _module.db
_skip_without_extension = _module._skip_without_extension

UTF8_TEST_DB = "smartcart_catalog_test"


@pytest.fixture(scope="session")
def utf8_dsn(pg_dsn: str) -> str:
    """A database whose LC_CTYPE is UTF-8, for tests that use pg_trgm on Hebrew.

    pg_trgm classifies characters with the database's LC_CTYPE; under ``C`` (the throwaway local
    cluster is created with --no-locale) Hebrew letters are not alphanumeric and similarity finds
    nothing. Supabase and the CI image use a UTF-8 ctype and are used as they are; otherwise a
    sibling database is created with LC_CTYPE C.UTF-8 (the same approach as the API tests).
    """
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        ctype = conn.execute(
            "SELECT datctype FROM pg_database WHERE datname = current_database()"
        ).fetchone()[0]
        if ctype not in ("C", "POSIX"):
            return pg_dsn
        conn.execute(f"DROP DATABASE IF EXISTS {UTF8_TEST_DB}")
        conn.execute(
            f"CREATE DATABASE {UTF8_TEST_DB} TEMPLATE template0 ENCODING 'UTF8'"
            " LC_COLLATE 'C' LC_CTYPE 'C.UTF-8'"
        )
    params = conninfo_to_dict(pg_dsn)
    params["dbname"] = UTF8_TEST_DB
    return make_conninfo(**params)


@pytest.fixture(scope="session")
def utf8_database(utf8_dsn: str, pg_dsn: str, database) -> str:
    if utf8_dsn != pg_dsn:
        missing = set(_module.EXTENSION_MARKERS.values()) - set(database.extensions)
        with dbmod.connect(utf8_dsn, autocommit=True) as conn:
            if missing and os.environ.get("SMARTCART_REQUIRE_EXTENSIONS") == "1":
                pytest.fail(
                    f"SMARTCART_REQUIRE_EXTENSIONS=1 but the server lacks: {sorted(missing)}"
                )
            dbmod.migrate(conn, skip_requires=missing)
    return utf8_dsn


@pytest.fixture
def db_utf8(utf8_database: str) -> Iterator[psycopg.Connection]:
    """Like ``db``, on a database where pg_trgm understands Hebrew."""
    with psycopg.connect(utf8_database) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        try:
            yield conn
        finally:
            conn.rollback()
