"""One nightly rehearsal of the Phase 0 exit window on a GitHub runner (issue #60).

What ``.github/workflows/exit-window.yml`` runs, once a day. It is the portal probe's download
and the portal probe's Scheduler path, with the real clock, written down as one JSON record per
Israel date (the schema is ``window_record.py``):

1. download one Stores, one PriceFull and one PromoFull file per D13 chain through
   ``portal_probe.probe`` (the pinned upstream scraper, one subprocess per download, only the
   legally mandated transparency portals, never a chain's online store);
2. migrate the throwaway Postgres and load every downloaded file through the real ``Scheduler``
   (download tracking, adapter, quality gates, loader) with ``datetime.now`` as its clock. There is
   no clock replay: a file the chain published more than 36 hours ago (Stores: its own limit) is
   quarantined by the stale-date gate, as on the VPS;
3. read what happened back from ``file_tracking`` and ``quarantine_events``, count what the
   adapters read and what the database holds, and write the record.

Downloaded files are untrusted data: only the chain adapters read them, inside the Scheduler path;
this script never parses a file itself except by calling the adapter. The run is a measurement:
unreachable portals and quarantined files are results, and the exit code is non-zero only when the
script cannot run at all.

    # on a runner (network); DATABASE_URL names an empty throwaway database
    uv run --no-sync python scripts/exit_window/run_day.py --work "$RUNNER_TEMP/exit-window" \\
        --out record.json
    # offline, on the committed real fixtures (they are days old, so the real clock quarantines
    # them: that is the stale gate working); add --now 2026-10-21T12:00 to see them load
    ... run_day.py --work /tmp/ew --out record.json --from-fixtures
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "unblock"))  # portal_probe, real_day, _common

import window_record as wr  # noqa: E402
from _common import run as run_cmd  # noqa: E402
from _common import venv_bin  # noqa: E402

ISRAEL = ZoneInfo("Asia/Jerusalem")


def israel_date(now: datetime) -> str:
    return now.astimezone(ISRAEL).date().isoformat()


def _iso_israel(when: datetime | None) -> str | None:
    return when.astimezone(ISRAEL).isoformat(timespec="minutes") if when else None


def run_info(source: str, clock: str, started: datetime, finished: datetime, country: str,
             download_s: float, load_s: float) -> dict:  # fmt: skip
    """The ``run`` block: where, when and with which code the rehearsal ran (GitHub's variables
    when present)."""
    env = os.environ
    run_id = env.get("GITHUB_RUN_ID")
    url = None
    if run_id and env.get("GITHUB_REPOSITORY"):
        server = env.get("GITHUB_SERVER_URL", "https://github.com")
        url = f"{server}/{env['GITHUB_REPOSITORY']}/actions/runs/{run_id}"
    return {
        "source": source,
        "clock": clock,
        "event": env.get("GITHUB_EVENT_NAME"),
        "ref": env.get("GITHUB_REF_NAME"),
        "commit": (env.get("GITHUB_SHA") or "")[:12] or None,
        "run_id": run_id,
        "run_url": url,
        "started_at": started.isoformat(timespec="seconds"),
        "started_at_israel": started.astimezone(ISRAEL).isoformat(timespec="seconds"),
        "finished_at": finished.isoformat(timespec="seconds"),
        "duration_seconds": round((finished - started).total_seconds(), 1),
        "download_seconds": round(download_s, 1),
        "load_seconds": round(load_s, 1),
        "runner_ip_country": country,
    }


def _count_parse(adapter, path: Path) -> dict:  # noqa: ANN001
    """What the adapter reads from the file (outside the database); an adapter error is a result."""
    data = path.read_bytes()
    try:
        parsed = adapter.parse(adapter.raw_file_for(path.name, data), data)
    except Exception as exc:  # noqa: BLE001 - an adapter failure is a finding
        return {"parse_error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    return {
        "stores": len(parsed.stores),
        "items": len(parsed.items),
        "prices": len(parsed.prices),
        "promos": len(parsed.promos) if parsed.raw.kind in ("promo_full", "promo") else None,
    }


def _tracking_row(conn, data: bytes):  # noqa: ANN001
    row = conn.execute(
        "SELECT id, status, reason, schema_version FROM file_tracking WHERE sha256 = %s",
        (hashlib.sha256(data).hexdigest(),),
    ).fetchone()
    if row is None:
        return None, []
    gates = [
        g
        for (g,) in conn.execute(
            "SELECT gate FROM quarantine_events WHERE file_id = %s ORDER BY id", (row[0],)
        ).fetchall()
    ]
    return row, gates


def _database_stats(conn, slug_of: dict[str, str]) -> tuple[dict, dict]:  # noqa: ANN001
    """Physical stores (and how many have coordinates) and promos by reward type, per slug."""
    stores: dict[str, dict[str, int]] = defaultdict(lambda: {"physical": 0, "with_coordinates": 0})
    has_geog = conn.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()"
        " AND table_name = 'stores' AND column_name = 'geog'"
    ).fetchone()
    coords = "count(*) FILTER (WHERE geog IS NOT NULL)" if has_geog else "0"
    for chain_id, physical, with_coords in conn.execute(
        f"SELECT chain_id, count(*), {coords} FROM stores WHERE channel = 'physical'"
        " GROUP BY chain_id"
    ).fetchall():
        slug = slug_of.get(chain_id)
        if slug:
            stores[slug]["physical"] += physical
            stores[slug]["with_coordinates"] += with_coords
    promos: dict[str, dict[str, int]] = defaultdict(dict)
    for chain_id, reward, n in conn.execute(
        "SELECT chain_id, reward_type, count(*) FROM promos GROUP BY chain_id, reward_type"
    ).fetchall():
        slug = slug_of.get(chain_id)
        if slug:
            promos[slug][reward] = promos[slug].get(reward, 0) + n
    return stores, promos


def build_day(
    files_dir: Path,
    slugs: Sequence[str],
    probe_result: dict | None,
    now: datetime | None,
) -> tuple[dict, list[dict], float]:
    """Load every picked file through the Scheduler. Returns ``(chains, alerts, load_seconds)``
    where ``chains`` maps slug to the chain entry of the record."""
    import portal_probe as pp

    from smartcart_ingest import db as dbmod
    from smartcart_ingest.adapters import REGISTRY
    from smartcart_ingest.alerts import Alerter
    from smartcart_ingest.rawstore import LocalRawStore
    from smartcart_ingest.scheduler import Scheduler
    from smartcart_ingest.settings import load_settings

    pp._logs_to_stderr()
    adapters = {getattr(cls, "slug", None): cls for cls in REGISTRY.values()}
    slug_of: dict[str, str] = {}
    for slug, cls in adapters.items():
        if slug:
            for cid in {cls.chain_id, *cls.accepted_chain_ids()}:
                slug_of[cid] = slug
    clock = (lambda: now) if now else (lambda: datetime.now(tz=ISRAEL))
    fetcher = pp.OneFileFetcher()
    sink = pp._Sink()
    chains: dict[str, dict] = {}
    load_seconds = 0.0
    raw_dir = Path(tempfile.mkdtemp(prefix="exit-window-raw-"))
    try:
        with dbmod.connect(autocommit=True) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            sched = Scheduler(conn, fetcher, LocalRawStore(raw_dir), Alerter([sink]),
                              load_settings(), now=clock, sleep=lambda s: None)  # fmt: skip
            for slug in slugs:
                portal_row = ((probe_result or {}).get("chains") or {}).get(slug) or {}
                downloads = portal_row.get("downloads") or {}
                portal = {
                    "http_status": int(portal_row.get("http_status", 0)),
                    "reachable": str(portal_row.get("reachable", "n/a")),
                    "login": str(portal_row.get("login", "n/a")),
                }
                cls = adapters.get(slug)
                files = {k: wr.empty_file("no adapter registered") for k in wr.KINDS}
                if cls is not None:
                    adapter = cls()
                    picked = pp.pick_files(files_dir, slug, adapter)
                    for kind in wr.KINDS:
                        dl = downloads.get(kind) or {}
                        entry = wr.empty_file(
                            dl.get("error"), wr.download_error_listed(dl.get("error"))
                        )
                        entry["download_seconds"] = dl.get("seconds")
                        path = picked.get(kind)
                        if path is None:
                            if dl.get("file"):
                                entry["download_error"] = "downloaded file not recognised"
                            elif not dl:
                                entry["download_error"] = "no file in the download directory"
                            files[kind] = entry
                            continue
                        started = time.monotonic()
                        entry = _load_one(sched, fetcher, conn, adapter, kind, path, clock, pp)
                        entry["load_seconds"] = round(time.monotonic() - started, 2)
                        load_seconds += entry["load_seconds"]
                        entry["download_seconds"] = dl.get("seconds")
                        entry["listed"] = True
                        if dl.get("parse_error") and not entry["parse_error"]:
                            entry["parse_error"] = str(dl["parse_error"])[:200]
                        files[kind] = entry
                        print(f"  {slug:18} {kind:10} {entry['status']:12} "
                              f"{','.join(entry['gates'])} {entry['reason'] or ''}",
                              file=sys.stderr, flush=True)  # fmt: skip
                chains[slug] = {"portal": portal, "files": files}
            stores, promos = _database_stats(conn, slug_of)
    finally:
        shutil.rmtree(raw_dir, ignore_errors=True)
    done: dict[str, dict] = {}
    for slug in slugs:
        spec = chains[slug]
        cls = adapters.get(slug)
        ids = (
            list(dict.fromkeys([cls.chain_id, *getattr(cls, "accepted_chain_ids", lambda: ())()]))
            if cls
            else ["unknown"]
        )
        done[slug] = wr.finish_chain(
            pp.BY_SLUG[slug].name,
            ids,
            spec["portal"],
            spec["files"],
            dict(stores.get(slug, {"physical": 0, "with_coordinates": 0})),
            dict(promos.get(slug, {})),
        )
    alerts = [
        {"chain_id": a.chain_id, "kind": a.kind, "message": a.message[:300]} for a in sink.alerts
    ]
    return done, alerts, load_seconds


def _load_one(sched, fetcher, conn, adapter, kind, path, clock, pp) -> dict:  # noqa: ANN001
    """One file through ``Scheduler.run_full``; returns its file entry."""
    data = path.read_bytes()
    info = adapter.parse_filename(path.name)
    entry = wr.empty_file()
    entry.update(
        downloaded=True,
        file=path.name,
        bytes=len(data),
        published_at=_iso_israel(info.published_at),
        age_hours=(
            round((clock() - info.published_at).total_seconds() / 3600, 1)
            if info.published_at
            else None
        ),
        status=wr.STATUS_NOT_TRACKED,
    )
    entry.update(_count_parse(adapter, path))
    fetcher.current = pp._OneFile(adapter.chain_id, path.name, kind, data)
    try:
        report = sched.run_full([adapter.chain_id]).chains[0]
    except Exception as exc:  # noqa: BLE001 - a Scheduler crash is a finding, not the run's end
        entry.update(status="failed", failed=True,
                     reason=f"scheduler error: {type(exc).__name__}: {str(exc)[:200]}")  # fmt: skip
        return entry
    finally:
        fetcher.current = None
    row, gates = _tracking_row(conn, data)
    if row is None:
        entry["reason"] = (report.error or "the Scheduler did not track the file")[:300]
        return entry
    _id, status, reason, schema = row
    entry.update(status=status, reason=reason, schema=schema, gates=gates,
                 loaded=status == "loaded", quarantined=status == "quarantined",
                 failed=status == "failed")  # fmt: skip
    return entry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--work", type=Path, required=True, help="scratch directory (outside the repo)")
    ap.add_argument("--out", type=Path, required=True, help="the record (JSON)")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--files", type=Path, help="a directory of <slug>/<portal file>, no network")
    src.add_argument("--from-fixtures", action="store_true",
                     help="the committed real fixtures (tests/fixtures/<slug>/real), no network")  # fmt: skip
    ap.add_argument("--chain", action="append", help="chain slug (repeatable; default: all ten)")
    ap.add_argument("--timeout", type=float, default=180, help="seconds per download")
    ap.add_argument("--date", default=None, help="Israel date of the record (default: today)")
    ap.add_argument("--now", default=None,
                    help="ISO time for the Scheduler's clock (tests only; default: the real clock)")  # fmt: skip
    ap.add_argument("--ip-country", default=os.environ.get("RUNNER_IP_COUNTRY", "unknown"))
    ap.add_argument("--no-migrate", action="store_true", help="the database is already migrated")
    args = ap.parse_args(argv)

    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    import portal_probe as pp

    slugs = args.chain or [p.slug for p in pp.PORTALS]
    unknown = [s for s in slugs if s not in pp.BY_SLUG]
    if unknown:
        print(f"unknown chain(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    now = datetime.fromisoformat(args.now) if args.now else None
    if now is not None and now.tzinfo is None:
        now = now.replace(tzinfo=ISRAEL)

    started = datetime.now(UTC)
    day = args.date or israel_date(now or started)
    if not wr.DATE_RE.match(day):
        print(f"--date must be YYYY-MM-DD, got {day!r}", file=sys.stderr)
        return 2
    args.work.mkdir(parents=True, exist_ok=True)

    # 1. download ------------------------------------------------------------------------------
    t0 = time.monotonic()
    probe_result: dict | None = None
    if args.files:
        files_dir, source = args.files, "files"
    elif args.from_fixtures:
        import real_day

        files_dir, source = real_day.copy_fixtures(args.work, slugs), "fixtures"
    else:
        files_dir, source = args.work / "probe" / "files", "portal"
        probe_result = pp.probe(args.work / "probe", slugs, args.timeout, skip_downloads=False)
    download_s = time.monotonic() - t0

    # 2. migrate and load (the real Scheduler path) -------------------------------------------
    if not args.no_migrate:
        run_cmd([venv_bin("smartcart-ingest"), "migrate"])
    chains, alerts, load_s = build_day(files_dir, slugs, probe_result, now)

    record = {
        "schema_version": wr.SCHEMA_VERSION,
        "kind": wr.RECORD_KIND,
        "date": day,
        "label": wr.LABEL,
        "run": run_info(
            source,
            "fixed" if now else "real",
            started,
            datetime.now(UTC),
            args.ip_country,
            download_s,
            load_s,
        ),  # fmt: skip
        "chains": chains,
        "alerts": alerts,
    }
    wr.validate_record(record)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(wr.render_day_summary(record))
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
