"""Replay transparency files through the production ingestion path, with the clock replayed.

Same method as ``scripts/demo/load_fixtures.py`` (and ``scripts/unblock/portal_probe.py gate``):
a fake portal lists exactly one file, the real ``Scheduler`` downloads, tracks, archives, parses,
gates and loads it, and the scheduler's clock is set to one hour after the file was published, so
the stale-date gate (36 hours) judges the file against its own day and not against today. Nothing
is inserted around the gates. Two file sets:

* ``real``: ``services/ingest/tests/fixtures/<chain>/real/`` (7 chains, one Stores file and one
  PriceFull file each, trimmed to 200 rows, fetched from the portals on 2026-10-08);
* ``synthetic``: ``services/ingest/tests/fixtures/<chain>/`` (10 chains, written by
  ``build_synthetic.py``), the set the full-stack demo loads.

Importable (``replay(...)``) and runnable for one database::

    DATABASE_URL=... uv run --no-sync python scripts/exit_dry_run/replay.py real
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import os
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import structlog

from smartcart_ingest import db as dbmod
from smartcart_ingest.adapters import REGISTRY, get_adapter
from smartcart_ingest.adapters.base import AdapterError
from smartcart_ingest.alerts import Alerter
from smartcart_ingest.rawstore import LocalRawStore
from smartcart_ingest.scheduler import DELTA_KINDS, Scheduler
from smartcart_ingest.settings import load_settings

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "services" / "ingest" / "tests" / "fixtures"

# The demo's fake portal and fixture ordering are reused as they are (loaded by path: scripts/
# is not a package).
_spec = importlib.util.spec_from_file_location(
    "_demo_load_fixtures", REPO / "scripts" / "demo" / "load_fixtures.py"
)
assert _spec and _spec.loader
_demo = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _demo  # dataclasses looks the module up by name
_spec.loader.exec_module(_demo)
KIND_ORDER = _demo.KIND_ORDER
CollectSink = _demo.CollectSink
FixtureFile = _demo.FixtureFile
OneFileFetcher = _demo.OneFileFetcher


@dataclass
class FileOutcome:
    chain: str
    chain_id: str
    file: str
    kind: str
    bytes: int
    published_at: datetime
    status: str
    reason: str | None
    schema: str | None
    gates: list[str] = field(default_factory=list)


def fixture_set(name: str) -> list[FixtureFile]:
    """The files of one set, in portal order (publication time, then kind)."""
    if name not in ("real", "synthetic"):
        raise ValueError("set must be 'real' or 'synthetic'")
    files: list[FixtureFile] = []
    classes = {cls for cls in REGISTRY.values() if isinstance(cls, type) and hasattr(cls, "slug")}
    for cls in sorted(classes, key=lambda c: c.slug):
        folder = FIXTURES / cls.slug / ("real" if name == "real" else "")
        if not folder.is_dir():
            continue
        adapter = get_adapter(cls.chain_id)
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name in ("expected.json", "MANIFEST.json"):
                continue
            try:
                info = adapter.parse_filename(path.name)
            except AdapterError:
                continue
            if info.published_at is None:
                continue
            files.append(FixtureFile(cls.chain_id, cls.slug, path, info.kind, info.published_at))
    files.sort(key=lambda f: (f.published_at, KIND_ORDER[f.kind], f.path.name))
    return files


def quiet_logs() -> None:
    logging.basicConfig(level=logging.ERROR, stream=sys.stderr, format="%(message)s")
    structlog.configure(
        processors=[structlog.processors.add_log_level, structlog.processors.KeyValueRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR),
        logger_factory=lambda *a: structlog.PrintLogger(file=sys.stderr),
    )


def replay(dsn: str, files: list[FixtureFile]) -> tuple[list[FileOutcome], list[dict]]:
    """Run ``files`` (already in portal order) through the Scheduler; return what happened to
    each file, read back from ``file_tracking``, and the alerts raised."""
    settings = load_settings()
    sink = CollectSink()
    fetcher = OneFileFetcher()
    clock: dict[str, datetime] = {}
    outcomes: list[FileOutcome] = []
    with tempfile.TemporaryDirectory(prefix="exit-dry-run-raw-") as raw_dir:
        with dbmod.connect(dsn, autocommit=True) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            sched = Scheduler(
                conn, fetcher, LocalRawStore(Path(raw_dir)), Alerter([sink]), settings,
                adapter_for=get_adapter, now=lambda: clock["now"], sleep=lambda s: None,
            )  # fmt: skip
            for f in files:
                fetcher.current = f
                clock["now"] = f.published_at + timedelta(hours=1)
                if f.kind in DELTA_KINDS:
                    sched.run_delta([f.chain_id])
                else:
                    sched.run_full([f.chain_id])
                data = f.path.read_bytes()
                row = conn.execute(
                    "SELECT id, status, reason, schema_version FROM file_tracking WHERE sha256 = %s",
                    (hashlib.sha256(data).hexdigest(),),
                ).fetchone()
                gates: list[str] = []
                if row:
                    gates = [g for (g,) in conn.execute(
                        "SELECT gate FROM quarantine_events WHERE file_id = %s ORDER BY id",
                        (row[0],)).fetchall()]  # fmt: skip
                outcomes.append(
                    FileOutcome(
                        chain=get_adapter(f.chain_id).display_name, chain_id=f.chain_id,
                        file=f.path.name, kind=f.kind, bytes=len(data),
                        published_at=f.published_at,
                        status=row[1] if row else "not tracked", reason=row[2] if row else None,
                        schema=row[3] if row else None, gates=gates,
                    )
                )  # fmt: skip
            fetcher.current = None
    alerts = [{"chain_id": a.chain_id, "kind": a.kind, "message": a.message[:300]}
              for a in sink.alerts]  # fmt: skip
    return outcomes, alerts


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    which = args[0] if args else "real"
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    quiet_logs()
    outcomes, alerts = replay(dsn, fixture_set(which))
    print(json.dumps({"files": [o.__dict__ for o in outcomes], "alerts": alerts},
                     ensure_ascii=False, indent=2, default=str))  # fmt: skip
    return 0 if all(o.status == "loaded" for o in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
