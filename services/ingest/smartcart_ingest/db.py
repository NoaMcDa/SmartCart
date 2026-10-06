"""Database connection and migration runner.

Plain SQL with psycopg 3, no ORM. Migrations are the files in ``supabase/migrations`` named
``YYYYMMDDHHMMSS_name.sql`` (the Supabase CLI convention). ``migrate`` applies each file once, in
filename order, inside its own transaction, and records it in ``schema_migrations``.

A migration may declare the extensions it needs in its leading comment block::

    -- requires: postgis, vector

Production and CI always apply every file; a missing extension makes the migration fail loudly.
The only way to skip a file is to pass ``skip_requires`` explicitly, which the local test harness
does when the Postgres server has no PostGIS or pgvector installed. Skipped files are not recorded,
so the database is visibly behind and a later full ``migrate`` applies them.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

log = logging.getLogger(__name__)

MIGRATION_NAME = re.compile(r"^(?P<version>\d{14})_(?P<name>[a-z0-9_]+)\.sql$")
_REQUIRES = re.compile(r"^--\s*requires:\s*(?P<exts>.+)$", re.IGNORECASE)

# Any constant works; it only has to be the same for every migrator process.
_MIGRATION_LOCK_KEY = 7_290_027_600_007


@dataclass(frozen=True)
class Migration:
    filename: str
    path: Path
    requires: frozenset[str]

    def read(self) -> str:
        return self.path.read_text(encoding="utf-8")


def default_migrations_dir() -> Path:
    """``$SMARTCART_MIGRATIONS_DIR`` if set, else ``<repo>/supabase/migrations``."""
    env = os.environ.get("SMARTCART_MIGRATIONS_DIR")
    if env:
        return Path(env)
    # services/ingest/smartcart_ingest/db.py -> the repo root is three levels above the package.
    return Path(__file__).resolve().parents[3] / "supabase" / "migrations"


def connect(dsn: str | None = None, **kwargs: Any) -> psycopg.Connection:
    """Open a connection to ``dsn`` or, when omitted, to ``$DATABASE_URL``."""
    dsn = dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("no DSN given and DATABASE_URL is not set")
    return psycopg.connect(dsn, **kwargs)


def parse_requires(text: str) -> frozenset[str]:
    """Collect ``-- requires: a, b`` lines from the leading comment block of a migration."""
    found: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("--"):
            break
        m = _REQUIRES.match(stripped)
        if m:
            found.update(e.strip().lower() for e in m.group("exts").split(",") if e.strip())
    return frozenset(found)


def list_migrations(migrations_dir: Path | None = None) -> list[Migration]:
    """Every ``*.sql`` file in the directory, sorted by filename. Rejects misnamed files."""
    directory = migrations_dir or default_migrations_dir()
    if not directory.is_dir():
        raise FileNotFoundError(f"migrations directory not found: {directory}")
    out: list[Migration] = []
    for path in sorted(directory.glob("*.sql"), key=lambda p: p.name):
        if not MIGRATION_NAME.match(path.name):
            raise ValueError(
                f"bad migration filename {path.name!r}: expected YYYYMMDDHHMMSS_name.sql"
            )
        out.append(Migration(path.name, path, parse_requires(path.read_text(encoding="utf-8"))))
    versions = [m.filename[:14] for m in out]
    if len(versions) != len(set(versions)):
        raise ValueError("two migrations share the same timestamp prefix")
    return out


def available_extensions(conn: psycopg.Connection) -> set[str]:
    """Extensions the server could install (``pg_available_extensions``)."""
    return {r[0] for r in conn.execute("SELECT name FROM pg_available_extensions").fetchall()}


def applied_migrations(conn: psycopg.Connection) -> set[str]:
    """Filenames recorded in ``schema_migrations`` (empty if the table does not exist yet)."""
    row = conn.execute("SELECT to_regclass('schema_migrations') IS NOT NULL").fetchone()
    if not row or not row[0]:
        return set()
    return {r[0] for r in conn.execute("SELECT filename FROM schema_migrations").fetchall()}


def migrate(
    conn: psycopg.Connection,
    *,
    migrations_dir: Path | None = None,
    skip_requires: Iterable[str] = (),
) -> list[str]:
    """Apply pending migrations in filename order and return the filenames applied.

    Each file runs in its own transaction together with its ``schema_migrations`` row, under a
    transaction-scoped advisory lock, so concurrent runners cannot apply a file twice. Running it
    again is a no-op. The connection must be idle (no transaction in progress); an autocommit
    connection is the simplest way to guarantee that.

    ``skip_requires`` names extensions to treat as unavailable: files whose ``-- requires:``
    header mentions one of them are skipped and not recorded. Only the test harness uses it.
    """
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise RuntimeError("migrate() needs an idle connection: commit or roll back first")
    skip = {s.lower() for s in skip_requires}
    migrations = list_migrations(migrations_dir)
    lock = sql.SQL("SELECT pg_advisory_xact_lock({})").format(sql.Literal(_MIGRATION_LOCK_KEY))

    with conn.transaction():
        conn.execute(lock)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " filename text PRIMARY KEY,"
            " applied_at timestamptz NOT NULL DEFAULT now())"
        )

    applied: list[str] = []
    for mig in migrations:
        missing = mig.requires & skip
        if missing:
            log.warning("skipping migration %s: needs %s", mig.filename, ", ".join(sorted(missing)))
            continue
        with conn.transaction():
            conn.execute(lock)
            done = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE filename = %s", (mig.filename,)
            ).fetchone()
            if done:
                continue
            log.info("applying migration %s", mig.filename)
            # No parameters, so psycopg sends the whole file as one multi-statement query and
            # does not interpret % signs in it.
            conn.execute(sql.SQL(mig.read()))  # type: ignore[arg-type]
            conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (mig.filename,))
        applied.append(mig.filename)
    return applied
