"""Database fixtures for the ingest test suite.

Where the database comes from:
  * ``DATABASE_URL`` set (CI, docker compose): that database is used and migrated.
  * otherwise: a throwaway Postgres cluster is created with ``initdb``/``pg_ctl`` in a temp dir on
    a free port, migrated, and removed at the end of the session. Binaries are looked up in
    ``$PG_BIN``, then ``/usr/lib/postgresql/<newest>/bin``, then ``$PATH``. If none is found,
    database tests are skipped.

Extensions: when the server lacks PostGIS or pgvector, migrations that declare
``-- requires: postgis`` / ``vector`` are skipped (the schema is then a subset of the real one, never
a different one), and tests marked ``postgis`` / ``pgvector`` are skipped. With
``SMARTCART_REQUIRE_EXTENSIONS=1`` (set in CI) a missing extension fails the run instead.

Each test using ``db`` runs inside a transaction that is rolled back, so tests do not see each
other's rows and an external database is left as it was (apart from being migrated).
"""

from __future__ import annotations

import os
import pwd
import shutil
import socket
import subprocess
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pytest

from smartcart_ingest import db as dbmod

EXTENSION_MARKERS = {"postgis": "postgis", "pgvector": "vector"}


@dataclass(frozen=True)
class Database:
    dsn: str
    extensions: frozenset[str]  # installable extensions among postgis/vector
    applied: tuple[str, ...]  # migrations applied by this session


def _find_pg_bin() -> Path | None:
    env = os.environ.get("PG_BIN")
    if env and (Path(env) / "initdb").exists():
        return Path(env)
    candidates = []
    for d in Path("/usr/lib/postgresql").glob("*/bin"):
        try:
            candidates.append((int(d.parent.name), d))
        except ValueError:
            continue
    for _, d in sorted(candidates, reverse=True):
        if (d / "initdb").exists() and (d / "pg_ctl").exists():
            return d
    initdb = shutil.which("initdb")
    return Path(initdb).parent if initdb else None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _TempCluster:
    """A throwaway Postgres cluster. initdb refuses to run as root, so as root it runs the
    server binaries as the ``postgres`` OS user (or ``nobody``) via runuser."""

    def __init__(self, bindir: Path) -> None:
        self.bindir = bindir
        self.root = Path(tempfile.mkdtemp(prefix="smartcart-pg-"))
        self.data = self.root / "data"
        self.port = _free_port()
        self._prefix: list[str] = []
        if os.geteuid() == 0:
            user = "postgres" if _user_exists("postgres") else "nobody"
            runuser = shutil.which("runuser")
            if not runuser:
                raise RuntimeError("running as root and runuser is not available")
            self._prefix = [runuser, "-u", user, "--"]
            shutil.chown(self.root, user=user)
            self.root.chmod(0o700)

    def _run(self, *args: str) -> None:
        subprocess.run(
            [*self._prefix, *args], check=True, capture_output=True, text=True, cwd=self.root
        )

    def start(self) -> str:
        self._run(
            str(self.bindir / "initdb"),
            "-D", str(self.data),
            "-U", "postgres",
            "--auth=trust",
            "--encoding=UTF8",
            "--no-locale",
        )  # fmt: skip
        opts = (
            f"-p {self.port} -c listen_addresses=127.0.0.1 -k {self.root} "
            "-c fsync=off -c synchronous_commit=off -c full_page_writes=off"
        )
        self._run(
            str(self.bindir / "pg_ctl"),
            "-D", str(self.data),
            "-o", opts,
            "-l", str(self.root / "server.log"),
            "-w", "-t", "60",
            "start",
        )  # fmt: skip
        return f"postgresql://postgres@127.0.0.1:{self.port}/postgres"

    def stop(self) -> None:
        try:
            self._run(str(self.bindir / "pg_ctl"), "-D", str(self.data), "-m", "immediate", "stop")
        except subprocess.CalledProcessError:
            pass
        shutil.rmtree(self.root, ignore_errors=True)


def _user_exists(name: str) -> bool:
    try:
        pwd.getpwnam(name)
    except KeyError:
        return False
    return True


@pytest.fixture(scope="session")
def pg_dsn() -> Iterator[str]:
    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        yield dsn
        return
    bindir = _find_pg_bin()
    if bindir is None:
        pytest.skip("no DATABASE_URL and no Postgres server binaries (initdb, pg_ctl) found")
    cluster = _TempCluster(bindir)
    try:
        try:
            dsn = cluster.start()
        except subprocess.CalledProcessError as exc:
            pytest.fail(f"could not start a temporary Postgres cluster: {exc.stderr}")
        yield dsn
    finally:
        cluster.stop()


@pytest.fixture(scope="session")
def database(pg_dsn: str) -> Database:
    with dbmod.connect(pg_dsn, autocommit=True) as conn:
        installable = dbmod.available_extensions(conn) & set(EXTENSION_MARKERS.values())
        missing = set(EXTENSION_MARKERS.values()) - installable
        if missing and os.environ.get("SMARTCART_REQUIRE_EXTENSIONS") == "1":
            pytest.fail(
                f"SMARTCART_REQUIRE_EXTENSIONS=1 but the server lacks: {', '.join(sorted(missing))}"
            )
        applied = dbmod.migrate(conn, skip_requires=missing)
    return Database(dsn=pg_dsn, extensions=frozenset(installable), applied=tuple(applied))


@pytest.fixture(autouse=True)
def _skip_without_extension(request: pytest.FixtureRequest) -> None:
    """Skip tests marked postgis/pgvector when the server cannot provide the extension."""
    needed = [
        ext for mark, ext in EXTENSION_MARKERS.items() if request.node.get_closest_marker(mark)
    ]
    if not needed:
        return
    database: Database = request.getfixturevalue("database")
    lacking = [e for e in needed if e not in database.extensions]
    if lacking:
        pytest.skip(f"Postgres server has no {', '.join(lacking)} extension (runs in CI)")


@pytest.fixture
def db(database: Database) -> Iterator[psycopg.Connection]:
    """A connection whose work is rolled back after the test."""
    with psycopg.connect(database.dsn) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        try:
            yield conn
        finally:
            conn.rollback()


@dataclass(frozen=True)
class Seed:
    chain_id: str
    store_a: int  # has price exceptions in the schema tests
    store_b: int  # has none
    item_id: int


@pytest.fixture
def seed(db: psycopg.Connection) -> Seed:
    """One chain with two stores and one item, inside the test's rolled-back transaction."""
    db.execute("INSERT INTO chains (id, name, portal) VALUES ('test-chain', 'Test Chain', 'other')")
    store_a, store_b = (
        db.execute(
            "INSERT INTO stores (chain_id, store_code, name, city) VALUES"
            " ('test-chain', %s, %s, 'Tel Aviv') RETURNING id",
            (code, f"Store {code}"),
        ).fetchone()[0]
        for code in ("001", "002")
    )
    item_id = db.execute(
        "INSERT INTO items (chain_id, item_code, barcode, raw_name, quantity, unit)"
        " VALUES ('test-chain', '7290000000001', '7290000000001', 'חלב 3% 1 ליטר', 1, 'liter')"
        " RETURNING id"
    ).fetchone()[0]
    return Seed("test-chain", store_a, store_b, item_id)
