"""Load every chain's synthetic transparency fixtures through the real ingestion pipeline.

The fixtures are the adapters' regression files under ``services/ingest/tests/fixtures/<slug>``
(written by ``build_synthetic.py``; synthetic until the VPS fetches real files). Each file takes
the production path, exactly like ``tests/test_quality_adapters.py`` does it: the ``Scheduler``
lists it from a fetcher, ``download`` hashes, tracks and archives it, the chain adapter parses it,
the quality gates run, and only then does ``loader.load`` write it, in one transaction. Nothing is
inserted around the gates: a file that fails a gate is quarantined, a file the adapter rejects is
marked failed, and both stay out of the data tables.

The portal is replayed in publication order, one file at a time, with the scheduler's clock set to
one hour after that file was published. The fixtures are dated 2026-10-06; with the wall clock the
stale-date gate (36 hours) would quarantine all of them once that date is past, which is the gate
doing its job, not a demo. Replaying the timeline keeps every other gate meaningful: the shufersal
v2 file of the next day still trips the item-count gate against the day before.

After the fixtures come the demo's second-day files for three stores near Tel Aviv
(``neighborhood.py``, written to ``$SMARTCART_DEMO_DIR/neighborhood``), through the same path.

Re-running is idempotent: a file whose hash is already loaded or quarantined is skipped, and a
failed file is retried and fails again with the same reason (no second alert). The second day is
dated yesterday, so a re-run on a later day adds that day's files (same prices, no new events).

    DATABASE_URL=... uv run python scripts/demo/load_fixtures.py [--day2 YYYY-MM-DD]
        [--no-neighborhood] [--raw-dir DIR] [--chain ID ...]

Prints one JSON line per file outcome to stderr and a JSON summary on stdout (file outcomes per
chain, row counts, the clock to precompute at, and the alerts raised).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import psycopg
import structlog

from smartcart_ingest import db as dbmod
from smartcart_ingest.adapters import REGISTRY, get_adapter
from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.adapters.base import AdapterError
from smartcart_ingest.alerts import Alert, Alerter
from smartcart_ingest.download import RemoteFile
from smartcart_ingest.models import FileKind
from smartcart_ingest.rawstore import LocalRawStore
from smartcart_ingest.scheduler import DELTA_KINDS, Scheduler
from smartcart_ingest.settings import load_settings

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "services" / "ingest" / "tests" / "fixtures"
KIND_ORDER: dict[str, int] = {"stores": 0, "price_full": 1, "promo_full": 2, "price": 3, "promo": 4}


@dataclass(frozen=True)
class FixtureFile:
    chain_id: str
    slug: str
    path: Path
    kind: FileKind
    published_at: datetime


@dataclass
class OneFileFetcher:
    """A portal listing exactly one file: the replay serves the fixtures one at a time."""

    current: FixtureFile | None = None
    served: list[str] = field(default_factory=list)

    def list_files(
        self,
        chain_id: str,
        kinds: Sequence[FileKind] | None = None,
        since: datetime | None = None,
    ) -> list[RemoteFile]:
        f = self.current
        if f is None or f.chain_id != chain_id or (kinds and f.kind not in kinds):
            return []
        return [RemoteFile(chain_id=chain_id, name=f.path.name, kind=f.kind)]

    def fetch(self, remote: RemoteFile) -> bytes:
        assert self.current is not None and remote.name == self.current.path.name
        self.served.append(remote.name)
        return self.current.path.read_bytes()


class CollectSink:
    def __init__(self) -> None:
        self.alerts: list[Alert] = []

    def send(self, alert: Alert) -> None:
        self.alerts.append(alert)


def chain_adapters(only: Sequence[str] | None = None) -> list[RegulationAdapter]:
    """Every registered regulation adapter that has a fixture folder, by slug."""
    classes = {
        cls
        for cls in REGISTRY.values()
        if isinstance(cls, type)
        and issubclass(cls, RegulationAdapter)
        and (FIXTURES / cls.slug).is_dir()
    }
    adapters = [get_adapter(cls.chain_id) for cls in sorted(classes, key=lambda c: c.slug)]
    if only:
        adapters = [a for a in adapters if a.chain_id in only]
    return adapters  # type: ignore[return-value]


def fixture_files(
    adapter: RegulationAdapter, extra_roots: Sequence[Path] = ()
) -> tuple[list[FixtureFile], list[str]]:
    """The chain's fixture files (and any under ``<extra_root>/<slug>``) in portal order
    (publication time, then kind), plus the names the adapter does not recognise as its own
    (listed, never loaded)."""
    out, unrecognized = [], []
    folders = [FIXTURES / adapter.slug, *(root / adapter.slug for root in extra_roots)]
    paths = sorted(p for d in folders if d.is_dir() for p in d.iterdir())
    for path in paths:
        if not path.is_file() or path.name == "expected.json":
            continue
        try:
            info = adapter.parse_filename(path.name)
        except AdapterError:
            unrecognized.append(path.name)
            continue
        if info.published_at is None:
            unrecognized.append(path.name)
            continue
        out.append(FixtureFile(adapter.chain_id, adapter.slug, path, info.kind, info.published_at))
    out.sort(key=lambda f: (f.published_at, KIND_ORDER[f.kind], f.path.name))
    return out, unrecognized


def _quiet_logs() -> None:
    logging.basicConfig(level=logging.ERROR, stream=sys.stderr, format="%(message)s")
    structlog.configure(
        processors=[structlog.processors.add_log_level, structlog.processors.KeyValueRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR),
        logger_factory=lambda *a: structlog.PrintLogger(file=sys.stderr),
    )


COUNT_SQL = {
    "chains": "SELECT count(*) FROM chains",
    "stores": "SELECT count(*) FROM stores",
    "stores_physical_with_location": (
        "SELECT count(*) FROM stores WHERE channel = 'physical' AND geog IS NOT NULL"
    ),
    "items": "SELECT count(*) FROM items",
    "price_events": "SELECT count(*) FROM prices",
    "promos": "SELECT count(*) FROM promos",
    "promo_items": "SELECT count(*) FROM promo_items",
}


def table_counts(conn: psycopg.Connection) -> dict[str, int]:
    out = {}
    for name, sql in COUNT_SQL.items():
        try:
            out[name] = conn.execute(sql).fetchone()[0]
        except psycopg.Error:
            out[name] = -1
    return out


def tracking_counts(conn: psycopg.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, count(*) FROM file_tracking GROUP BY 1 ORDER BY 1"
    ).fetchall()
    return {status: n for status, n in rows}


def chain_status(conn: psycopg.Connection, chain_id: str) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, count(*) FROM file_tracking WHERE chain_id = %s GROUP BY 1 ORDER BY 1",
        (chain_id,),
    ).fetchall()
    return {status: n for status, n in rows}


def newest_loaded(conn: psycopg.Connection) -> datetime | None:
    return conn.execute(
        "SELECT max(published_at) FROM file_tracking WHERE status = 'loaded'"
    ).fetchone()[0]


def run(
    dsn: str, raw_dir: Path, only: Sequence[str] | None = None, extra_roots: Sequence[Path] = ()
) -> dict:
    settings = load_settings()
    sink = CollectSink()
    alerter = Alerter([sink])
    fetcher = OneFileFetcher()
    clock: dict[str, datetime] = {}
    per_chain: dict[str, dict[str, int]] = {}

    with dbmod.connect(dsn, autocommit=True) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        sched = Scheduler(
            conn,
            fetcher,
            LocalRawStore(raw_dir),
            alerter,
            settings,
            adapter_for=get_adapter,
            now=lambda: clock["now"],
            sleep=lambda s: None,
        )
        for adapter in chain_adapters(only):
            files, unrecognized = fixture_files(adapter, extra_roots)
            run_totals = {"files": len(files), "unrecognized": len(unrecognized),
                          "downloaded": 0, "skipped": 0}  # fmt: skip
            for f in files:
                fetcher.current = f
                clock["now"] = f.published_at + timedelta(hours=1)
                if f.kind in DELTA_KINDS:
                    report = sched.run_delta([f.chain_id])
                else:
                    report = sched.run_full([f.chain_id])
                rep = report.chains[0]
                run_totals["downloaded"] += rep.downloaded
                run_totals["skipped"] += rep.skipped
                print(
                    json.dumps(
                        {"chain": adapter.slug, "file": f.path.name, "kind": f.kind,
                         **{k: v for k, v in rep.as_dict().items() if v and k != "chain_id"}},
                        ensure_ascii=False,
                    ),
                    file=sys.stderr,
                )  # fmt: skip
            # Outcomes are read back from file_tracking, so a re-run reports the same state.
            per_chain[adapter.slug] = {**run_totals, **chain_status(conn, adapter.chain_id)}
        fetcher.current = None

        status = tracking_counts(conn)
        counts = table_counts(conn)
        newest = newest_loaded(conn)

    as_of = (newest + timedelta(hours=1)) if newest else None
    return {
        "chains": per_chain,
        "file_tracking": status,
        "rows": counts,
        # Naive UTC, the format `smartcart-api precompute --as-of` takes.
        "as_of_utc": (
            as_of.astimezone(UTC).replace(tzinfo=None).isoformat(timespec="seconds")
            if as_of
            else None
        ),
        "alerts": [
            {"chain_id": a.chain_id, "kind": a.kind, "message": a.message[:200]}
            for a in sink.alerts
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--raw-dir", type=Path, default=None,
                        help="local raw archive (default $SMARTCART_DEMO_DIR/raw)")  # fmt: skip
    parser.add_argument("--chain", action="append", help="only this chain id (repeatable)")
    parser.add_argument("--day2", type=date.fromisoformat, default=None,
                        help="the demo's second day (default: yesterday in Israel)")  # fmt: skip
    parser.add_argument("--no-neighborhood", action="store_true",
                        help="only the adapters' fixtures, without the demo's second day")  # fmt: skip
    args = parser.parse_args(argv)
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    demo_dir = Path(
        os.environ.get("SMARTCART_DEMO_DIR") or Path(tempfile.gettempdir()) / "smartcart-demo"
    )
    raw_dir = args.raw_dir or demo_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    extra: list[Path] = []
    if not args.no_neighborhood:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import neighborhood

        neighborhood.build(demo_dir / "neighborhood", args.day2)
        extra.append(demo_dir / "neighborhood")
    _quiet_logs()
    summary = run(dsn, raw_dir, args.chain, extra)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["file_tracking"].get("loaded"):
        print("no file loaded", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
