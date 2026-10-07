"""Fixtures for the API tests.

Database fixtures (``db``, ``database``, ``pg_dsn``) are reused from the ingest suite: they live
in services/ingest/tests/conftest.py (DATABASE_URL, or a throwaway Postgres cluster migrated with
the repo's migrations). That file is loaded by path and its fixtures are re-exported here, so the
api tests get the same database without importing across test packages. This directory has no
``__init__.py`` on purpose: services/ingest/tests is already the top-level package ``tests``.

``world`` seeds a small catalog (taxonomy, canonical products with hash embeddings, items mapped
at every flexibility level, attributes), two chains with stores around a point in Tel Aviv,
prices (chain base prices plus store exceptions) and promos, inside the test's rolled-back
transaction (see api_world.py). It does not depend on the catalog workstream's code.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from api_world import JWT_SECRET, World, seed_catalog, seed_world
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from smartcart_api.db import get_conn
from smartcart_api.main import app
from smartcart_api.settings import get_settings
from smartcart_ingest import db as dbmod

_PATH = Path(__file__).resolve().parents[2] / "ingest" / "tests" / "conftest.py"
_spec = importlib.util.spec_from_file_location("_ingest_test_fixtures", _PATH)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module  # dataclasses looks the module up by name
_spec.loader.exec_module(_module)

pg_dsn = _module.pg_dsn
db = _module.db
_skip_without_extension = _module._skip_without_extension

API_TEST_DB = "smartcart_api_test"


@pytest.fixture(scope="session")
def api_dsn(pg_dsn: str) -> str:
    """The database the API tests use.

    pg_trgm and the text-search parser classify characters with the database's LC_CTYPE; under
    ``C`` (the throwaway local cluster is created with --no-locale) Hebrew letters are not
    alphanumeric and trigram search finds nothing. Supabase and the CI image use a UTF-8 ctype.
    So when the server database has a C ctype, the API tests run in a sibling database created
    with LC_CTYPE C.UTF-8 (collation stays C).
    """
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        ctype = conn.execute(
            "SELECT datctype FROM pg_database WHERE datname = current_database()"
        ).fetchone()[0]
        if ctype not in ("C", "POSIX"):
            return pg_dsn
        conn.execute(f"DROP DATABASE IF EXISTS {API_TEST_DB}")
        conn.execute(
            f"CREATE DATABASE {API_TEST_DB} TEMPLATE template0 ENCODING 'UTF8'"
            " LC_COLLATE 'C' LC_CTYPE 'C.UTF-8'"
        )
    params = conninfo_to_dict(pg_dsn)
    params["dbname"] = API_TEST_DB
    return make_conninfo(**params)


@pytest.fixture(scope="session")
def database(api_dsn: str):
    """Same as the ingest suite's ``database`` fixture, on ``api_dsn``."""
    with dbmod.connect(api_dsn, autocommit=True) as conn:
        installable = dbmod.available_extensions(conn) & set(_module.EXTENSION_MARKERS.values())
        missing = set(_module.EXTENSION_MARKERS.values()) - installable
        if missing and os.environ.get("SMARTCART_REQUIRE_EXTENSIONS") == "1":
            pytest.fail(f"SMARTCART_REQUIRE_EXTENSIONS=1 but the server lacks: {sorted(missing)}")
        applied = dbmod.migrate(conn, skip_requires=missing)
    return _module.Database(dsn=api_dsn, extensions=frozenset(installable), applied=tuple(applied))


@pytest.fixture
def client(db: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A TestClient whose requests run on the test's rolled-back connection."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    get_settings.cache_clear()

    def _conn() -> Iterator[psycopg.Connection]:
        yield db

    app.dependency_overrides[get_conn] = _conn
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_conn, None)
        get_settings.cache_clear()


@pytest.fixture
def world(db: psycopg.Connection) -> World:
    return seed_world(db)


@pytest.fixture
def catalog(db: psycopg.Connection) -> World:
    """Only the catalog (taxonomy, rules, canonical products with embeddings)."""
    w = World()
    seed_catalog(db, w)
    return w
