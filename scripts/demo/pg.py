"""A throwaway Postgres cluster for the full-stack demo (``scripts/demo/up.sh``).

Same approach as ``services/ingest/tests/conftest.py``: ``initdb`` and ``pg_ctl`` in a state
directory, trust auth on 127.0.0.1, and as root the server runs as the ``postgres`` OS user through
``runuser`` because ``initdb`` refuses to run as root. One difference: the cluster is created with
``LC_CTYPE C.UTF-8`` (collation stays ``C``), because pg_trgm and the text-search parser only see
Hebrew letters as letters under a UTF-8 ctype (``docs/api.md``, search). Supabase and the CI image
already have one.

    python scripts/demo/pg.py start    # prints the DSN; reuses a running cluster
    python scripts/demo/pg.py stop     # stops it and deletes the state directory
    python scripts/demo/pg.py status   # prints the DSN when running, exits 1 otherwise

The state directory is ``$SMARTCART_DEMO_DIR/pg`` (default ``$TMPDIR/smartcart-demo/pg``) and the
port is ``$DEMO_PG_PORT`` (default 54329).
"""

from __future__ import annotations

import os
import pwd
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def state_root() -> Path:
    base = os.environ.get("SMARTCART_DEMO_DIR") or str(
        Path(tempfile.gettempdir()) / "smartcart-demo"
    )
    return Path(base) / "pg"


def find_pg_bin() -> Path | None:
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


def _user_exists(name: str) -> bool:
    try:
        pwd.getpwnam(name)
    except KeyError:
        return False
    return True


def _prefix() -> list[str]:
    if os.geteuid() != 0:
        return []
    user = "postgres" if _user_exists("postgres") else "nobody"
    runuser = shutil.which("runuser")
    if not runuser:
        raise SystemExit("running as root and runuser is not available")
    return [runuser, "-u", user, "--"]


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    res = subprocess.run([*_prefix(), *args], capture_output=True, text=True, cwd=cwd)
    if res.returncode != 0:
        raise SystemExit(f"{Path(args[0]).name} failed ({res.returncode}): {res.stderr.strip()}")
    return res


def _dsn(port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/postgres"


def _running(bindir: Path, root: Path) -> bool:
    data = root / "data"
    if not (data / "PG_VERSION").exists():
        return False
    res = subprocess.run(
        [*_prefix(), str(bindir / "pg_ctl"), "-D", str(data), "status"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    return res.returncode == 0


def start() -> str:
    bindir = find_pg_bin()
    if bindir is None:
        raise SystemExit(
            "no Postgres server binaries (initdb, pg_ctl) found: set PG_BIN, install Postgres with"
            " PostGIS and pgvector, or export DATABASE_URL"
        )
    root = state_root()
    port_file = root / "port"
    if _running(bindir, root) and port_file.exists():
        return _dsn(int(port_file.read_text()))

    port = int(os.environ.get("DEMO_PG_PORT", "54329"))
    root.mkdir(parents=True, exist_ok=True)
    prefix = _prefix()
    if prefix:
        shutil.chown(root, user=prefix[2])
        # The server user must be able to reach the directory: the state dir itself is opened
        # up, and every ancestor must already be traversable (o+x), as /tmp is.
        root.parent.chmod(0o755)
        for parent in root.parent.parents:
            if not parent.stat().st_mode & 0o001:
                raise SystemExit(
                    f"{parent} is not traversable by the {prefix[2]} user that runs Postgres;"
                    " set SMARTCART_DEMO_DIR under /tmp"
                )
    root.chmod(0o700)
    data = root / "data"
    if not (data / "PG_VERSION").exists():
        _run(
            str(bindir / "initdb"),
            "-D", str(data),
            "-U", "postgres",
            "--auth=trust",
            "--encoding=UTF8",
            "--lc-collate=C",
            "--lc-ctype=C.UTF-8",
            "--lc-messages=C",
            cwd=root,
        )  # fmt: skip
    opts = (
        f"-p {port} -c listen_addresses=127.0.0.1 -k {root} "
        "-c fsync=off -c synchronous_commit=off -c full_page_writes=off"
    )
    try:
        _run(
            str(bindir / "pg_ctl"),
            "-D", str(data),
            "-o", opts,
            "-l", str(root / "server.log"),
            "-w", "-t", "60",
            "start",
            cwd=root,
        )  # fmt: skip
    except subprocess.CalledProcessError as exc:
        log = root / "server.log"
        tail = log.read_text(errors="replace")[-2000:] if log.exists() else ""
        raise SystemExit(f"pg_ctl start failed: {exc.stderr}\n{tail}") from exc
    port_file.write_text(str(port))
    return _dsn(port)


def stop() -> None:
    root = state_root()
    bindir = find_pg_bin()
    if bindir is not None and (root / "data" / "PG_VERSION").exists():
        subprocess.run(
            [*_prefix(), str(bindir / "pg_ctl"), "-D", str(root / "data"), "-m", "fast", "stop"],
            capture_output=True,
            text=True,
            cwd=root,
        )
    shutil.rmtree(root, ignore_errors=True)


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "start":
        print(start())
        return 0
    if cmd == "stop":
        stop()
        return 0
    if cmd == "status":
        bindir = find_pg_bin()
        root = state_root()
        if bindir and _running(bindir, root) and (root / "port").exists():
            print(_dsn(int((root / "port").read_text())))
            return 0
        return 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
