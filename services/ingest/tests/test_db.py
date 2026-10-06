"""Tests for the migration runner in smartcart_ingest.db."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from smartcart_ingest import db as dbmod

# --- no database needed ------------------------------------------------------------------------


def test_parse_requires_reads_leading_comment_block_only() -> None:
    text = "-- title\n-- requires: postgis, Vector\n\n-- requires: pg_trgm\nSELECT 1;\n-- requires: x\n"
    assert dbmod.parse_requires(text) == {"postgis", "vector", "pg_trgm"}
    assert dbmod.parse_requires("SELECT 1;") == frozenset()


def test_repo_migrations_follow_supabase_naming_and_order() -> None:
    migs = dbmod.list_migrations()
    names = [m.filename for m in migs]
    assert names == sorted(names)
    assert all(dbmod.MIGRATION_NAME.match(n) for n in names)
    by_suffix = {m.filename[15:]: m for m in migs}
    assert names[0].endswith("_extensions.sql")
    assert by_suffix["extensions.sql"].requires == {"postgis", "vector"}
    assert by_suffix["schema_v1.sql"].requires == frozenset()
    assert by_suffix["stores_geog.sql"].requires == {"postgis"}


def test_misnamed_migration_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "001_init.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="YYYYMMDDHHMMSS_name.sql"):
        dbmod.list_migrations(tmp_path)


def test_duplicate_timestamp_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "20260101000000_a.sql").write_text("SELECT 1;")
    (tmp_path / "20260101000000_b.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="same timestamp"):
        dbmod.list_migrations(tmp_path)


def test_connect_needs_a_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        dbmod.connect()


# --- database ----------------------------------------------------------------------------------


@pytest.fixture
def fresh_schema(database) -> Iterator[psycopg.Connection]:
    """An autocommit connection whose search_path starts with a new, empty schema.

    Unqualified migrations then create every object (and schema_migrations) in that schema, which
    gives an empty database for the migration tests without needing CREATE DATABASE rights.
    Extensions stay where the session migration put them, reachable through the rest of the path.
    """
    name = f"migtest_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(database.dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
        conn.execute(
            sql.SQL("SET search_path = {}, public, extensions").format(sql.Identifier(name))
        )
        try:
            yield conn
        finally:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))


def _missing(database) -> set[str]:
    return {"postgis", "vector"} - set(database.extensions)


def _tables(conn: psycopg.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT c.relname FROM pg_class c WHERE c.relnamespace = current_schema()::regnamespace"
        " AND c.relkind IN ('r', 'p') AND NOT c.relispartition"
    ).fetchall()
    return {r[0] for r in rows}


@pytest.mark.db
def test_migrations_apply_to_empty_database_and_rerun_is_noop(fresh_schema, database) -> None:
    conn = fresh_schema
    missing = _missing(database)
    expected = [m.filename for m in dbmod.list_migrations() if not (m.requires & missing)]

    assert dbmod.migrate(conn, skip_requires=missing) == expected
    assert dbmod.applied_migrations(conn) == set(expected)
    assert {
        "chains",
        "stores",
        "items",
        "prices",
        "promos",
        "promo_items",
        "file_tracking",
        "quarantine_events",
        "schema_migrations",
    } <= _tables(conn)

    before = conn.execute("SELECT filename, applied_at FROM schema_migrations").fetchall()
    assert dbmod.migrate(conn, skip_requires=missing) == []
    after = conn.execute("SELECT filename, applied_at FROM schema_migrations").fetchall()
    assert sorted(before) == sorted(after)


@pytest.mark.db
def test_session_database_is_fully_migrated(database) -> None:
    missing = _missing(database)
    expected = {m.filename for m in dbmod.list_migrations() if not (m.requires & missing)}
    with psycopg.connect(database.dsn) as conn:
        assert dbmod.applied_migrations(conn) == expected


@pytest.mark.db
def test_skipped_migrations_are_not_recorded(fresh_schema, tmp_path: Path) -> None:
    (tmp_path / "20260101000000_a.sql").write_text("CREATE TABLE t_a (id int);")
    (tmp_path / "20260101000100_b.sql").write_text(
        "-- requires: no_such_extension\nCREATE EXTENSION no_such_extension;"
    )
    (tmp_path / "20260101000200_c.sql").write_text(
        "CREATE TABLE t_c (id int);\nCREATE TABLE t_c2 (pct text DEFAULT '100%s');"
    )
    conn = fresh_schema
    applied = dbmod.migrate(conn, migrations_dir=tmp_path, skip_requires={"no_such_extension"})
    assert applied == ["20260101000000_a.sql", "20260101000200_c.sql"]
    assert dbmod.applied_migrations(conn) == set(applied)
    assert {"t_a", "t_c", "t_c2"} <= _tables(conn)


@pytest.mark.db
def test_failed_migration_rolls_back_and_is_not_recorded(fresh_schema, tmp_path: Path) -> None:
    (tmp_path / "20260101000000_ok.sql").write_text("CREATE TABLE t_ok (id int);")
    (tmp_path / "20260101000100_bad.sql").write_text(
        "CREATE TABLE t_half (id int);\nSELECT * FROM no_such_table;"
    )
    conn = fresh_schema
    with pytest.raises(psycopg.errors.UndefinedTable):
        dbmod.migrate(conn, migrations_dir=tmp_path)
    assert dbmod.applied_migrations(conn) == {"20260101000000_ok.sql"}
    assert "t_half" not in _tables(conn)


@pytest.mark.db
def test_migrate_refuses_a_connection_inside_a_transaction(database) -> None:
    with psycopg.connect(database.dsn) as conn:
        conn.execute("SELECT 1")  # opens an implicit transaction
        with pytest.raises(RuntimeError, match="idle connection"):
            dbmod.migrate(conn)
