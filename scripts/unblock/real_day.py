"""One real day through the whole pipeline, on one machine (what ``.github/workflows/real-day.yml`` runs).

Everything downstream of ingestion had only run on synthetic data. This script takes the real
transparency files of one day and walks them through every stage, timing each:

1. download: the portal probe's own download functions (``portal_probe.probe``: one Stores and
   one PriceFull per reachable chain), then, once the Stores files are loaded and the stores have
   coordinates, the PriceFull (and PromoFull) files of the stores nearest to a few city centres,
   through the same pinned upstream scraper with a file-name filter (a hidden ``_scrape`` step
   in a subprocess, so a hung portal is killed);
2. migrate, then every file through the real ``Scheduler`` path (adapter, quality gates, loader),
   Stores first; store coordinates are set by the loader from ``data/geo`` (docs/geocoding.md);
3. the catalog: ``smartcart-catalog seed, normalize, extract, embed, judge`` on the real items;
4. the nightly effective-price precompute (``smartcart-api precompute``);
5. ``/parse-list``, ``/compare`` and ``/optimize`` (heuristic and MILP) through the FastAPI test
   client for hand-made Hebrew baskets and for baskets drawn from what was priced, at a few real
   store locations;
6. the monthly basket index on the real day (a dry run: never publishable);
7. a stress variant (``--stress``): the unreviewed machine mappings are marked accepted, the
   precompute runs again and the optimizer is timed on the larger priced set. This is a
   performance measurement only; precision of those mappings is unknown.

Only the legally mandated transparency portals are contacted, through the pinned upstream scraper,
never a chain's online store. Downloaded files are untrusted data: the chain adapters are the only
code that reads them. The run is a measurement: a stage that fails is recorded as a finding and
the next stage still runs; the exit code is non-zero only when the script cannot run at all.

    # on a runner (network) -- the workflow does this
    DATABASE_URL=... uv run --no-sync python scripts/unblock/real_day.py run --work $RUNNER_TEMP/rd
    # offline, on the committed real fixtures (one store per chain; no extra download)
    DATABASE_URL=... uv run --no-sync python scripts/unblock/real_day.py run --work /tmp/rd \\
        --from-fixtures
    # offline, on any directory laid out <slug>/<portal filename>
    ... run --work /tmp/rd --files DIR
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
import traceback
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from _common import REPO, git_sha, last_json_document, md_escape, venv_bin, write_text
from _common import run as run_cmd

ISRAEL = ZoneInfo("Asia/Jerusalem")
STALE_HOURS = 36.0  # the stale-date gate's limit (smartcart_ingest.settings)
KINDS_ORDER = {"stores": 0, "price_full": 1, "promo_full": 2}
KIND_FILTERS = {
    "stores": "STORE_FILE",
    "price_full": "PRICE_FULL_FILE",
    "promo_full": "PROMO_FULL_FILE",
}
FIXTURES = REPO / "services" / "ingest" / "tests" / "fixtures"

# City centres the extra downloads and the API locations are drawn from. Coordinates are the
# usual centre points (estimates, to about a kilometre); only the stores' own coordinates matter.
ANCHOR_CATALOG: tuple[tuple[str, float, float], ...] = (
    ("Tel Aviv centre", 32.0780, 34.7740),
    ("Ramat Gan", 32.0830, 34.8120),
    ("Jerusalem centre", 31.7810, 35.2170),
    ("Haifa centre", 32.8000, 34.9900),
    ("Petah Tikva", 32.0880, 34.8880),
    ("Rishon LeZion", 31.9700, 34.7900),
    ("Beer Sheva", 31.2520, 34.7870),
    ("Netanya", 32.3300, 34.8570),
    ("Ashdod", 31.8040, 34.6550),
    ("Holon", 32.0150, 34.7740),
)

# Hand-made Hebrew shopping lists, the way a person pastes one (docs/fullstack.md has the demo's).
HAND_BASKETS: dict[str, str] = {
    "small (6 lines)": ('3 חלב טרי 3%, 2 קוטג\' 5%, לחם אחיד, 2 ק"ג עגבניות, 6 במבה, 2 ק"ג בננות'),
    "weekly (17 lines)": (
        "חלב טרי 3%, קוטג' 5%, גבינה צהובה פרוסה, ביצים L, חזה עוף טרי, 2 ק\"ג עגבניות, "
        '1 ק"ג מלפפונים, 2 ק"ג תפוחי אדמה, בצל, בננות, לחם אחיד, אורז פרסי, ספגטי, שמן קנולה, '
        "סוכר, קפה נמס, נייר טואלט"
    ),
    "large (32 lines)": (
        "חלב טרי 3%, חלב טרי 1%, קוטג' 5%, גבינה לבנה 5%, יוגורט טבעי, חמאה, ביצים L, "
        'חזה עוף טרי, שוקיים עוף, בשר בקר טחון, 2 ק"ג עגבניות, 1 ק"ג מלפפונים, '
        '2 ק"ג תפוחי אדמה, בצל, גזר, פלפל אדום, לימונים, אבוקדו, תפוחי עץ, בננות, לחם אחיד, '
        "פיתות, אורז פרסי, ספגטי, קמח, שמן קנולה, טחינה, קטשופ, קפה נמס, קולה, מים מינרליים, "
        "נייר טואלט, נוזל כלים"
    ),
}
COVERED_SIZES = (5, 10, 20, 40)


# --- pure helpers (tested in scripts/unblock/tests/test_real_day.py) -----------------------------------


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km (spherical earth; fine at city scale)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def rank_anchors(
    stores: Sequence[dict],
    catalog: Sequence[tuple[str, float, float]],
    radius_km: float,
    count: int,
    min_separation_km: float = 6.0,
) -> list[dict]:
    """The ``count`` anchors with the most distinct chains (then the most stores) among the
    ``stores`` (dicts with ``chain_id``, ``lat``, ``lon``) within ``radius_km``. Anchors closer
    than ``min_separation_km`` to a better one are skipped, so the locations differ."""
    scored = []
    for name, lat, lon in catalog:
        near = [s for s in stores if haversine_km(lat, lon, s["lat"], s["lon"]) <= radius_km]
        chains = {s["chain_id"] for s in near}
        scored.append({"name": name, "lat": lat, "lon": lon, "chains": len(chains),
                       "stores": len(near)})  # fmt: skip
    scored.sort(key=lambda a: (-a["chains"], -a["stores"], a["name"]))
    chosen: list[dict] = []
    for a in scored:
        if a["stores"] == 0:
            continue
        if all(haversine_km(a["lat"], a["lon"], c["lat"], c["lon"]) >= min_separation_km
               for c in chosen):  # fmt: skip
            chosen.append(a)
        if len(chosen) == count:
            break
    return chosen


def select_stores(
    stores: Sequence[dict], anchor: dict, radius_km: float, per_chain: int
) -> dict[str, list[str]]:
    """``{chain_id: [store_code, ...]}``: for each chain the ``per_chain`` stores nearest to the
    anchor within ``radius_km`` (each store once, nearest first)."""
    by_chain: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for s in stores:
        d = haversine_km(anchor["lat"], anchor["lon"], s["lat"], s["lon"])
        if d <= radius_km:
            by_chain[s["chain_id"]].append((d, str(s["store_code"])))
    return {c: [code for _, code in sorted(v)[:per_chain]] for c, v in sorted(by_chain.items())}


def store_file_regex(kind: str, codes: Sequence[str]) -> str:
    """A ``file_name_regex`` for the upstream scraper: files of ``kind`` (``price_full`` or
    ``promo_full``) of these store codes, i.e. ``<Kind><chain>-<sub>-<store>-<date>`` with the
    store number in any zero padding. A hint only: every file is checked again with the
    adapter's own filename parser."""
    prefix = {"price_full": "PriceFull", "promo_full": "PromoFull"}[kind]
    alternatives = "|".join(re.escape(str(c).lstrip("0") or "0") for c in codes)
    return rf"{prefix}\d+-\d+-0*(?:{alternatives})-\d{{8}}"


def stale_clock(
    published_at: datetime | None, now: datetime, limit_hours: float = STALE_HOURS
) -> tuple[datetime, bool]:
    """``(clock for the gates, stale on the real clock)``. A file older than the stale-date
    limit is loaded with the clock replayed one hour after its publication (as
    ``scripts/demo/load_fixtures.py`` does), so the stale-date gate cannot hide every later
    stage; the flag is reported as a finding."""
    if published_at is None:
        return now, False
    if now - published_at > timedelta(hours=limit_hours):
        return published_at + timedelta(hours=1), True
    return now, False


def summarize_ms(values: Sequence[float]) -> dict:
    """n, median, p95 (nearest rank) and max of a list of milliseconds."""
    if not values:
        return {"n": 0, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    rank = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {"n": len(ordered), "median": round(statistics.median(ordered), 1),
            "p95": round(ordered[rank], 1), "max": round(ordered[-1], 1)}  # fmt: skip


def covered_baskets(
    priced: dict[int, int], sizes: Sequence[int], seed: int, min_stores: int = 2
) -> dict[int, list[dict]]:
    """Baskets drawn from what was priced: ``priced`` is ``{canonical_id: stores that price it}``
    near one location. Each size gets that many canonicals priced in at least ``min_stores``
    stores (the whole pool when it is smaller; a size the pool cannot fill is reported at the
    pool's size), quantity 1 to 3, level any_brand. Deterministic in ``seed``."""
    pool = sorted(c for c, n in priced.items() if n >= min_stores)
    out: dict[int, list[dict]] = {}
    for size in sizes:
        rng = random.Random(f"{seed}:{size}")
        pick = sorted(rng.sample(pool, min(size, len(pool)))) if pool else []
        qty_rng = random.Random(f"{seed}:{size}:q")
        out[size] = [{"canonical_id": c, "quantity": qty_rng.randint(1, 3),
                      "flex_level": "any_brand"} for c in pick]  # fmt: skip
    return out


def newest_per_store(names: Sequence[str], parse_name) -> dict[str, str]:
    """``{store_code: newest file name}`` over ``names`` (``parse_name`` is an adapter's
    ``parse_filename``; names it rejects are skipped)."""
    best: dict[str, tuple[datetime, str]] = {}
    for name in names:
        try:
            info = parse_name(name)
        except Exception:  # noqa: BLE001 - not a portal file
            continue
        if info.store_code is None:
            continue
        when = info.published_at or datetime.min.replace(tzinfo=ISRAEL)
        if info.store_code not in best or when > best[info.store_code][0]:
            best[info.store_code] = (when, name)
    return {code: v[1] for code, v in best.items()}


# --- stage bookkeeping ---------------------------------------------------------------------------------


class Run:
    """Stage timings and findings. A stage that raises is recorded and the run goes on."""

    def __init__(self) -> None:
        self.stages: list[dict] = []
        self.failures: list[dict] = []

    @contextmanager
    def stage(self, name: str) -> Iterator[dict]:
        rec: dict = {"name": name, "ok": True}
        print(f"\n==> {name}", file=sys.stderr, flush=True)
        t0 = time.perf_counter()
        try:
            yield rec
        except Exception as exc:  # noqa: BLE001 - a failing stage is a finding, not a crash
            rec["ok"] = False
            rec["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            self.fail(name, rec["error"], traceback.format_exc()[-1200:])
        finally:
            rec["seconds"] = round(time.perf_counter() - t0, 2)
            self.stages.append(rec)
            print(f"    {name}: {rec['seconds']} s{'' if rec['ok'] else ' FAILED'}",
                  file=sys.stderr, flush=True)  # fmt: skip

    def fail(self, stage: str, what: str, detail: str = "") -> None:
        self.failures.append({"stage": stage, "what": what, "detail": detail})
        print(f"::warning title=real-day {stage}::{what[:200]}", flush=True)


def _logs_to_stderr() -> None:
    import logging

    import structlog

    structlog.configure(
        processors=[structlog.processors.add_log_level, structlog.processors.KeyValueRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        logger_factory=lambda *a: structlog.PrintLogger(file=sys.stderr),
    )


# --- 1. download ---------------------------------------------------------------------------------------


def adapter_tables() -> tuple[dict[str, type], dict[str, str]]:
    """``({slug: adapter class}, {chain_id: slug})`` for the chains that have an upstream scraper."""
    from smartcart_ingest.adapters.fetch_fixtures import adapters_by_slug

    by_slug = adapters_by_slug()
    return by_slug, {cls.chain_id: slug for slug, cls in by_slug.items()}


def scrape_subprocess(slug: str, kind: str, regex: str, limit: int, out: Path, timeout: float):
    """Fetch up to ``limit`` files of ``kind`` matching ``regex`` into ``out/<slug>/`` through the
    pinned upstream scraper, in a subprocess that is killed after ``timeout`` seconds. Returns
    ``(file names, error or None)``."""
    shutil.rmtree(out / "_stage", ignore_errors=True)
    cmd = [sys.executable, str(Path(__file__).resolve()), "_scrape", slug, kind,
           "--regex", regex, "--limit", str(limit), "--out", str(out / "_stage")]  # fmt: skip
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=REPO)
    except subprocess.TimeoutExpired:
        return [], f"timed out after {timeout:.0f}s"
    if res.stderr.strip():
        sys.stderr.write(res.stderr[-1500:])
    names: list[str] = []
    dest = out / slug
    dest.mkdir(parents=True, exist_ok=True)
    stage = out / "_stage"
    for path in sorted(stage.rglob("*")) if stage.is_dir() else []:
        if path.is_file():
            shutil.move(str(path), dest / path.name)
            names.append(path.name)
    shutil.rmtree(stage, ignore_errors=True)
    err = None
    if res.returncode != 0:
        err = f"scrape exited {res.returncode}: {(res.stderr or res.stdout)[-200:]}"
    elif not names:
        err = "no file matched"
    return names, err


def _scrape_main(args: argparse.Namespace) -> int:
    """Hidden subcommand ``_scrape``: the upstream scrape with a name filter and a limit (what
    ``fetch_fixtures._download`` does for one file, for several)."""
    from smartcart_ingest.adapters.fetch_fixtures import adapters_by_slug
    from smartcart_ingest.download import quiet_upstream_loggers

    quiet_upstream_loggers()
    from il_supermarket_scarper import FileTypesFilters, ScraperFactory
    from il_supermarket_scarper.utils import DiskFileOutput

    name = adapters_by_slug()[args.slug].upstream_scraper
    scraper_cls = ScraperFactory[name].value
    scraper = scraper_cls(file_output=DiskFileOutput(str(args.out), extract_gz=False))
    file_type = FileTypesFilters[KIND_FILTERS[args.kind]].name

    async def go() -> None:
        async for _result in scraper.scrape(
            limit=args.limit, files_types=[file_type], file_name_regex=args.regex
        ):
            pass

    asyncio.run(go())
    return 0


def download_probe(work: Path, slugs: Sequence[str], timeout: float) -> tuple[Path, dict]:
    """The portal probe, unchanged: reachability, login, one Stores and one PriceFull per chain."""
    import portal_probe

    out = work / "probe"
    result = portal_probe.probe(out, slugs, timeout, skip_downloads=False)
    return out / "files", result


def copy_fixtures(work: Path, slugs: Sequence[str]) -> Path:
    """The committed real fixtures (``tests/fixtures/<slug>/real``) as a files directory."""
    files = work / "fixtures-files"
    for slug in slugs:
        src = FIXTURES / slug / "real"
        if not src.is_dir():
            continue
        (files / slug).mkdir(parents=True, exist_ok=True)
        for path in src.iterdir():
            if path.is_file() and path.name != "MANIFEST.json":
                shutil.copy(path, files / slug / path.name)
    return files


# --- 2. ingestion: the real Scheduler path ----------------------------------------------------------------


class Ingest:
    """One Scheduler over one connection; ``load`` runs a single file through it."""

    def __init__(self, conn, raw_dir: Path) -> None:
        import portal_probe

        from smartcart_ingest.adapters import REGISTRY
        from smartcart_ingest.alerts import Alerter
        from smartcart_ingest.rawstore import LocalRawStore
        from smartcart_ingest.scheduler import Scheduler
        from smartcart_ingest.settings import load_settings

        self.conn = conn
        self.probe = portal_probe
        self.sink = portal_probe._Sink()
        self.fetcher = portal_probe.OneFileFetcher()
        self.adapters = {getattr(cls, "slug", None): cls for cls in REGISTRY.values()}
        self.clock = {"now": datetime.now(tz=ISRAEL)}
        self.sched = Scheduler(conn, self.fetcher, LocalRawStore(raw_dir), Alerter([self.sink]),
                               load_settings(), now=lambda: self.clock["now"],
                               sleep=lambda s: None)  # fmt: skip
        self.records: list[dict] = []

    def load(self, slug: str, path: Path, kind_hint: str | None = None) -> dict:
        import hashlib

        cls = self.adapters.get(slug)
        entry: dict = {"chain": slug, "file": path.name, "bytes": path.stat().st_size}
        if cls is None:
            entry["gate"] = {"status": "no adapter"}
            self.records.append(entry)
            return entry
        adapter = cls()
        try:
            info = adapter.parse_filename(path.name)
        except Exception as exc:  # noqa: BLE001
            entry["gate"] = {"status": "unrecognized", "reason": str(exc)[:200]}
            self.records.append(entry)
            return entry
        entry["kind"] = info.kind
        entry["published_at"] = (info.published_at.isoformat(timespec="minutes")
                                 if info.published_at else None)  # fmt: skip
        real_now = datetime.now(tz=ISRAEL)
        clock, stale = stale_clock(info.published_at, real_now)
        self.clock["now"] = clock
        entry["stale_on_real_clock"] = stale
        if info.published_at:
            entry["age_hours"] = round((real_now - info.published_at).total_seconds() / 3600, 1)
        data = path.read_bytes()
        entry["parse"] = self.probe.parse_summary(adapter, path)
        sha = hashlib.sha256(data).hexdigest()
        self.fetcher.current = self.probe._OneFile(adapter.chain_id, path.name, info.kind, data)
        t0 = time.perf_counter()
        try:
            report = self.sched.run_full([adapter.chain_id]).chains[0]
        finally:
            self.fetcher.current = None
        entry["seconds"] = round(time.perf_counter() - t0, 2)
        row = self.conn.execute(
            "SELECT id, status, reason, schema_version FROM file_tracking WHERE sha256 = %s",
            (sha,),
        ).fetchone()
        if row is None:
            entry["gate"] = {"status": "not tracked", "error": report.error}
        else:
            gates = [g for (g,) in self.conn.execute(
                "SELECT gate FROM quarantine_events WHERE file_id = %s ORDER BY id", (row[0],)
            ).fetchall()]  # fmt: skip
            entry["file_id"] = row[0]
            entry["gate"] = {"status": row[1], "reason": row[2], "gates": gates, "schema": row[3]}
        print(self.probe.result_line(slug, info.kind, entry), file=sys.stderr, flush=True)
        self.records.append(entry)
        return entry


def list_files(files: Path, slug: str, adapter_cls) -> list[tuple[str, Path]]:
    """Every portal-named file under ``files/<slug>``, Stores first, then by publication time."""
    folder = files / slug
    if not folder.is_dir():
        return []
    adapter = adapter_cls()
    out = []
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        try:
            info = adapter.parse_filename(path.name)
        except Exception:  # noqa: BLE001
            continue
        if info.kind in KINDS_ORDER:
            when = info.published_at or datetime.min.replace(tzinfo=ISRAEL)
            out.append((KINDS_ORDER[info.kind], when, path))
    out.sort(key=lambda t: (t[0], t[1], t[2].name))
    return [(slug, p) for _, _, p in out]


def located_stores(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT s.chain_id, s.store_code, s.name, s.city, ST_Y(s.geog::geometry),"
        " ST_X(s.geog::geometry), s.geo_precision"
        " FROM stores AS s WHERE s.channel = 'physical' AND s.geog IS NOT NULL"
    ).fetchall()
    return [{"chain_id": r[0], "store_code": r[1], "name": r[2], "city": r[3], "lat": r[4],
             "lon": r[5], "precision": r[6]} for r in rows]  # fmt: skip


# --- DB measurements ---------------------------------------------------------------------------------------


def chain_tables(conn, slug_by_chain: dict[str, str]) -> dict[str, dict]:
    """Rows per chain after ingestion."""
    out: dict[str, dict] = {}

    def put(sql: str, key: str) -> None:
        for chain_id, n in conn.execute(sql).fetchall():
            out.setdefault(chain_id, {})[key] = n

    put("SELECT chain_id, count(*) FROM stores WHERE channel = 'physical' GROUP BY 1", "physical")
    put("SELECT chain_id, count(*) FROM stores WHERE channel = 'online' GROUP BY 1", "online")
    put("SELECT chain_id, count(*) FROM stores WHERE geog IS NOT NULL AND channel = 'physical'"
        " GROUP BY 1", "located")  # fmt: skip
    put("SELECT chain_id, count(*) FROM items GROUP BY 1", "items")
    put("SELECT i.chain_id, count(*) FROM prices p JOIN items i ON i.id = p.item_id GROUP BY 1",
        "price_events")  # fmt: skip
    put("SELECT i.chain_id, count(DISTINCT p.store_id) FROM prices p JOIN items i ON i.id = p.item_id"
        " WHERE p.store_id IS NOT NULL GROUP BY 1", "priced_stores")  # fmt: skip
    put("SELECT chain_id, count(*) FROM promos GROUP BY 1", "promos")
    put("SELECT p.chain_id, count(*) FROM promo_items pi JOIN promos p ON p.id = pi.promo_id"
        " GROUP BY 1", "promo_items")  # fmt: skip
    for chain_id in out:
        out[chain_id]["slug"] = slug_by_chain.get(chain_id, chain_id)
    return out


def rows_per_file(conn, records: list[dict]) -> None:
    prices = dict(conn.execute("SELECT file_id, count(*) FROM prices GROUP BY 1").fetchall())
    promos = dict(conn.execute("SELECT file_id, count(*) FROM promos GROUP BY 1").fetchall())
    for r in records:
        fid = r.get("file_id")
        if fid is not None:
            r["price_rows"] = prices.get(fid, 0)
            r["promo_rows"] = promos.get(fid, 0)


def matching_counts(conn) -> dict:
    """Mapped items per flexibility level, served (no review flag) and in the review queue."""
    items = conn.execute("SELECT count(*) FROM items").fetchone()[0]
    by_level = {}
    for level, review, n, _distinct in conn.execute(
        "SELECT flex_level, needs_review, count(*), count(DISTINCT item_id)"
        " FROM item_canonical WHERE NOT human_rejected GROUP BY 1, 2"
    ).fetchall():
        by_level.setdefault(level, {})["review" if review else "served"] = n
    mapped_items = conn.execute(
        "SELECT count(DISTINCT item_id) FROM item_canonical WHERE NOT human_rejected"
    ).fetchone()[0]
    served_items = conn.execute(
        "SELECT count(DISTINCT item_id) FROM item_canonical"
        " WHERE NOT human_rejected AND NOT needs_review"
    ).fetchone()[0]
    served_canonicals = conn.execute(
        "SELECT count(DISTINCT canonical_id) FROM item_canonical"
        " WHERE NOT human_rejected AND NOT needs_review"
    ).fetchone()[0]
    per_chain = {
        c: {"items": n, "mapped": m, "served": s}
        for c, n, m, s in conn.execute(
            "SELECT i.chain_id, count(DISTINCT i.id),"
            " count(DISTINCT ic.item_id) FILTER (WHERE ic.item_id IS NOT NULL),"
            " count(DISTINCT ic.item_id) FILTER (WHERE NOT ic.needs_review)"
            " FROM items i LEFT JOIN item_canonical ic"
            "   ON ic.item_id = i.id AND NOT ic.human_rejected GROUP BY 1"
        ).fetchall()
    }
    return {"items": items, "mapped_items": mapped_items, "served_items": served_items,
            "served_canonicals": served_canonicals, "by_level": by_level,
            "per_chain": per_chain}  # fmt: skip


def effective_counts(conn) -> dict:
    rows = conn.execute(
        "SELECT flex_level, count(*), count(DISTINCT canonical_id), count(DISTINCT store_id)"
        " FROM effective_prices GROUP BY 1 ORDER BY 1"
    ).fetchall()
    by_flex = {lv: {"rows": n, "canonicals": c, "stores": s} for lv, n, c, s in rows}
    total = conn.execute(
        "SELECT count(*), count(DISTINCT canonical_id), count(DISTINCT store_id)"
        " FROM effective_prices"
    ).fetchone()
    multi = conn.execute(
        "SELECT count(*) FROM (SELECT canonical_id FROM effective_prices"
        " WHERE flex_level = 'any_brand' GROUP BY 1 HAVING count(DISTINCT store_id) >= 2) t"
    ).fetchone()[0]
    return {"by_flex": by_flex, "rows": total[0], "canonicals": total[1], "stores": total[2],
            "canonicals_in_2plus_stores_any_brand": multi}  # fmt: skip


# --- 5. the API ---------------------------------------------------------------------------------------------


def money(value) -> float:
    return float(value)


def plan_summary(plan: dict | None) -> dict | None:
    if not plan:
        return None
    b = plan.get("breakdown") or {}
    return {
        "kind": plan["kind"],
        "recommended": plan["recommended"],
        "stores": [
            f"{a['store']['chain_name']} {a['store']['store_name']}" for a in plan["stores"]
        ],
        "items_per_store": [len(a["item_ids"]) for a in plan["stores"]],
        "total": money(plan["total"]),
        "travel_cost": money(plan["travel_cost"]),
        "missing": len(plan.get("missing") or []),
        "net_saving": money(b["net_saving"]) if b else None,
        "basket_saving": money(b["basket_saving"]) if b else None,
        "promo_bundles": len(plan.get("promo_bundles") or []),
    }


def check_trust(cmp_json: dict, label: str, problems: list[str]) -> None:
    """Trust signals the product promises on every response: timestamps, the disclaimer."""
    if cmp_json.get("disclaimer_he") != "המחיר הקובע הוא בקופה.":
        problems.append(f"{label}: disclaimer missing")
    for s in cmp_json["stores"]:
        if not s.get("prices_updated_at"):
            problems.append(f"{label}: store {s['store_id']} has no prices_updated_at")
        for line in s["items"]:
            if not line.get("price_valid_from"):
                problems.append(f"{label}: line {line['item_id']} has no price_valid_from")
            if line.get("is_substitute") and not line.get("tags"):
                problems.append(f"{label}: substitute line {line['item_id']} has no tags")


def check_plan(plan: dict | None, label: str, problems: list[str]) -> None:
    if not plan or not plan.get("breakdown"):
        return
    b = plan["breakdown"]
    net = money(b["basket_saving"]) - money(b["travel_cost"]) - money(b["extra_stop_cost"])
    if abs(net - money(b["net_saving"])) > 0.005:
        problems.append(f"{label}: net_saving {b['net_saving']} != basket - travel - extra stop")
    for a in plan["stores"]:
        for line in a["store"]["items"]:
            if not line.get("price_valid_from"):
                problems.append(f"{label}: line without a timestamp")
                break


def api_stage(
    db_url: str,
    locations: Sequence[dict],
    repeats: int,
    seed: int,
    run: Run,
    tag: str,
) -> dict:
    """/parse-list, /compare and /optimize through the FastAPI test client."""
    import psycopg
    from fastapi.testclient import TestClient

    os.environ["DATABASE_URL"] = db_url
    from smartcart_api.main import app

    out: dict = {"tag": tag, "parse": {}, "runs": [], "problems": []}
    problems: list[str] = out["problems"]

    def timed(fn):
        t0 = time.perf_counter()
        res = fn()
        return res, (time.perf_counter() - t0) * 1000

    with TestClient(app) as client, psycopg.connect(db_url) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        hand: dict[str, list[dict]] = {}
        for name, text in HAND_BASKETS.items():
            res, ms = timed(lambda text=text: client.post("/parse-list", json={"text": text}))
            if res.status_code != 200:
                run.fail("api", f"/parse-list {name}: HTTP {res.status_code} {res.text[:160]}")
                continue
            rows = res.json()["rows"]
            resolved = [r for r in rows if r["canonical"] and not r["not_found"]]
            out["parse"][name] = {
                "rows": len(rows), "resolved": len(resolved), "ms": round(ms, 1),
                "needs_confirmation": sum(1 for r in rows if r["needs_confirmation"]),
                "not_found": [r["input_text"] for r in rows if r["not_found"]],
            }  # fmt: skip
            hand[name] = [{"canonical_id": r["canonical"]["canonical_id"], "quantity": r["quantity"],
                           "flex_level": r["flex_level"]} for r in resolved]  # fmt: skip

        for loc in locations:
            lon, lat, radius = loc["lon"], loc["lat"], loc.get("radius_m", 5000)
            priced = {
                cid: n
                for cid, n in conn.execute(
                    "SELECT ep.canonical_id, count(DISTINCT ep.store_id)"
                    " FROM effective_prices ep JOIN stores_within(%s, %s, %s) sw"
                    "   ON sw.store_id = ep.store_id WHERE ep.flex_level = 'any_brand'"
                    " GROUP BY 1",
                    (lon, lat, radius),
                ).fetchall()
            }
            home = conn.execute(
                "SELECT sw.store_id FROM stores_within(%s, %s, %s) sw"
                " WHERE sw.channel = 'physical' AND EXISTS"
                "  (SELECT 1 FROM effective_prices ep WHERE ep.store_id = sw.store_id)"
                " ORDER BY sw.distance_m LIMIT 1",
                (lon, lat, radius),
            ).fetchone()
            home_id = home[0] if home else None
            baskets: list[tuple[str, str, list[dict]]] = [
                (f"hand: {n}", "hand", items) for n, items in hand.items() if items
            ]
            for size, items in covered_baskets(priced, COVERED_SIZES, seed).items():
                if items:
                    label = f"drawn: {size}" + (
                        "" if len(items) == size else f" (pool {len(items)})"
                    )
                    baskets.append((label, "drawn", items))
            for bname, kind, items in baskets:
                body = {"items": items, "location": {"lat": lat, "lon": lon, "radius_m": radius},
                        "home_store_id": home_id}  # fmt: skip
                rec: dict = {"location": loc["name"], "basket": bname, "source": kind,
                             "lines": len(items), "home_store_id": home_id}  # fmt: skip
                cmp_ms: list[float] = []
                cmp_json = None
                for _ in range(repeats):
                    res, ms = timed(lambda body=body: client.post("/compare", json=body))
                    cmp_ms.append(ms)
                    if res.status_code != 200:
                        run.fail("api", f"/compare {loc['name']} {bname}: HTTP {res.status_code} "
                                 f"{res.text[:160]}")  # fmt: skip
                        break
                    cmp_json = res.json()
                rec["compare_ms"] = summarize_ms(cmp_ms)
                if cmp_json is None:
                    out["runs"].append(rec)
                    continue
                check_trust(cmp_json, f"{loc['name']} {bname} /compare", problems)
                stores = cmp_json["stores"]
                rec["stores_in_radius"] = len(stores)
                rec["complete_stores"] = sum(1 for s in stores if not s["missing"])
                rec["median_found"] = (statistics.median(s["found_count"] for s in stores)
                                       if stores else 0)  # fmt: skip
                rec["substituted_lines"] = sum(s["substituted_count"] for s in stores)
                best = next((s for s in stores if not s["missing"]), None)
                rec["cheapest_complete"] = (
                    {"store": f"{best['chain_name']} {best['store_name']}",
                     "total": money(best["total"])} if best else None)  # fmt: skip
                for solver in ("heuristic", "milp"):
                    req = {**body, "solver": solver,
                           "travel": {"mode": "car", "cost_per_km": 1.2, "extra_stop_value": 25}}  # fmt: skip
                    ms_list: list[float] = []
                    opt = None
                    for _ in range(repeats):
                        res, ms = timed(lambda req=req: client.post("/optimize", json=req))
                        ms_list.append(ms)
                        if res.status_code != 200:
                            run.fail("api", f"/optimize {solver} {loc['name']} {bname}: HTTP "
                                     f"{res.status_code} {res.text[:200]}")  # fmt: skip
                            opt = None
                            break
                        opt = res.json()
                    entry: dict = {"ms": summarize_ms(ms_list)}
                    if opt is not None:
                        label = f"{loc['name']} {bname} {solver}"
                        for key in ("single", "split", "minimum_effort"):
                            check_plan(opt.get(key), f"{label} {key}", problems)
                        recommended = [
                            p for p in (opt["single"], opt["split"]) if p and p["recommended"]
                        ]
                        entry.update({
                            "ran": opt["solver"], "subsets_evaluated": opt["subsets_evaluated"],
                            "single": plan_summary(opt["single"]), "split": plan_summary(opt["split"]),
                            "recommended": plan_summary(recommended[0]) if recommended else None,
                        })  # fmt: skip
                        if solver == "milp" and opt["solver"] != "milp":
                            problems.append(f"{label}: the MILP fell back to the heuristic")
                    rec[solver] = entry
                h, m = (
                    rec.get("heuristic", {}).get("recommended"),
                    rec.get("milp", {}).get("recommended"),
                )
                if h and m and h["net_saving"] is not None and m["net_saving"] is not None:
                    if m["net_saving"] + 0.005 < h["net_saving"]:
                        problems.append(f"{loc['name']} {bname}: MILP net saving {m['net_saving']} "
                                        f"is below the heuristic's {h['net_saving']}")  # fmt: skip
                    rec["milp_vs_heuristic_net"] = round(m["net_saving"] - h["net_saving"], 2)
                out["runs"].append(rec)
                print(f"  {loc['name']} | {bname}: compare {rec['compare_ms']['median']} ms, "
                      f"heuristic {rec['heuristic']['ms']['median']} ms, milp "
                      f"{rec.get('milp', {}).get('ms', {}).get('median')} ms", file=sys.stderr,
                      flush=True)  # fmt: skip
    return out


def pick_locations(conn, count: int, radius_m: int = 5000) -> list[dict]:
    """API locations: city centres and the places of priced stores, ranked by how many priced
    stores (then chains) lie within the radius; distinct by at least 6 km."""
    rows = conn.execute(
        "SELECT s.chain_id, s.store_code, s.name, ST_Y(s.geog::geometry), ST_X(s.geog::geometry)"
        " FROM stores s WHERE s.channel = 'physical' AND s.geog IS NOT NULL AND EXISTS"
        " (SELECT 1 FROM effective_prices ep WHERE ep.store_id = s.id)"
    ).fetchall()
    priced = [{"chain_id": r[0], "store_code": r[1], "name": r[2], "lat": r[3], "lon": r[4]}
              for r in rows]  # fmt: skip
    candidates = list(ANCHOR_CATALOG) + [(f"near {p['name']}", p["lat"], p["lon"]) for p in priced]
    picks = rank_anchors(priced, candidates, radius_m / 1000, count)
    return [{"name": p["name"], "lat": p["lat"], "lon": p["lon"], "radius_m": radius_m,
             "priced_chains": p["chains"], "priced_stores": p["stores"]} for p in picks]  # fmt: skip


# --- 6. basket index -----------------------------------------------------------------------------------------


def basket_index_dry_run(work: Path, env: dict, tag: str) -> dict:
    """``smartcart-catalog basket-index`` into a scratch directory: a draft, never published."""
    out_dir = work / f"seo-{tag}"
    reports = work / f"reports-{tag}"
    month = datetime.now(UTC).strftime("%Y-%m")
    res = run_cmd([venv_bin("smartcart-catalog"), "basket-index", "--month", month,
                   "--out", str(out_dir), "--reports", str(reports)], env=env, check=False)  # fmt: skip
    info: dict = {"month": month, "exit": res.returncode, "seconds": round(res.seconds, 2),
                  "stdout": res.stdout[-1500:]}  # fmt: skip
    index_path = out_dir / "basket-index.json"
    if index_path.exists():
        doc = json.loads(index_path.read_text(encoding="utf-8"))
        months = doc.get("months") or []
        entry = next((m for m in months if m.get("month") == month), None)
        if entry:
            info["status"] = entry.get("status")
            info["checks"] = [{k: c.get(k) for k in ("level", "code", "message")}
                              for c in entry.get("checks", [])]  # fmt: skip
            info["chains"] = [
                {"chain": c.get("name"), "total": c.get("total"),
                 "items_priced": c.get("items_priced"), "missing": len(c.get("missing") or []),
                 "estimated_items": c.get("estimated_items"), "stores": c.get("stores"),
                 "complete": c.get("complete")}
                for c in entry.get("chains", [])
            ]  # fmt: skip
            info["price_date"] = entry.get("price_date")
        info["basket_lines"] = (doc.get("basket") or {}).get("item_count")
    return info


# --- the run -------------------------------------------------------------------------------------------------


def run_all(args: argparse.Namespace) -> dict:
    import psycopg

    from smartcart_ingest import db as dbmod

    db_url = os.environ["DATABASE_URL"]
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    run = Run()
    by_slug, slug_by_chain = adapter_tables()
    slugs = list(args.chain) if args.chain else sorted(by_slug)
    env = {"DATABASE_URL": db_url}
    result: dict = {
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": git_sha(),
        "runner": os.environ.get("RUNNER_NAME") or os.uname().nodename,
        "cpus": os.cpu_count(),
        "python": sys.version.split()[0],
        "mode": "fixtures" if args.from_fixtures else ("files" if args.files else "portal"),
        "chains_requested": slugs,
        "options": {
            k: getattr(args, k)
            for k in (
                "anchors",
                "per_chain",
                "radius_km",
                "max_files",
                "with_promos",
                "stress",
                "repeats",
                "seed",
            )
        },  # fmt: skip
    }
    _logs_to_stderr()

    # 1. download (probe) --------------------------------------------------------------------------
    files_dir: Path | None = None
    probe_result: dict | None = None
    with run.stage("download: portal probe (one Stores and one PriceFull per chain)") as st:
        if args.files:
            files_dir = args.files
            st["note"] = f"files from {args.files}"
        elif args.from_fixtures:
            files_dir = copy_fixtures(work, slugs)
            st["note"] = "the committed real fixtures (trimmed to 200 rows, one store per chain)"
        else:
            files_dir, probe_result = download_probe(work, slugs, args.timeout)
        result["probe"] = probe_result
    if files_dir is None:
        raise SystemExit("no files to load")

    # 2. migrate ------------------------------------------------------------------------------------
    with run.stage("migrate") as st:
        res = run_cmd([venv_bin("smartcart-ingest"), "migrate"], env=env, check=False)
        st["note"] = (
            f"{sum(1 for ln in res.stdout.splitlines() if ln.startswith('applied '))} applied"
        )
        if res.returncode != 0:
            raise RuntimeError("smartcart-ingest migrate failed")

    # 3. ingestion ----------------------------------------------------------------------------------
    raw_dir = work / "raw"
    raw_dir.mkdir(exist_ok=True)
    ingest: Ingest | None = None
    conn = dbmod.connect(db_url, autocommit=True)
    conn.execute("SET TIME ZONE 'UTC'")
    try:
        ingest = Ingest(conn, raw_dir)
        stores_first = []
        for slug in slugs:
            cls = by_slug.get(slug)
            if cls is not None:
                stores_first += [(s, p) for s, p in list_files(files_dir, slug, cls)
                                 if p.name.startswith("Stores")]  # fmt: skip
        with run.stage(
            "ingest: Stores files (Scheduler, adapters, gates, loader, store coordinates)"
        ) as st:
            for slug, path in stores_first:
                ingest.load(slug, path)
            st["note"] = f"{len(stores_first)} files"

        # 3b. extra downloads: the stores nearest to a few city centres ------------------------------
        located = located_stores(conn)
        result["stores_located"] = len(located)
        extra_dir = work / "extra"
        extra: dict = {"anchors": [], "downloads": []}
        if not args.files and not args.from_fixtures and args.anchors > 0:
            with run.stage(
                "download: PriceFull and PromoFull of the stores nearest to city centres"
            ) as st:
                anchors = rank_anchors(located, ANCHOR_CATALOG, args.radius_km, args.anchors)
                budget = args.max_files
                for a in anchors:
                    chosen = select_stores(located, a, args.radius_km, args.per_chain)
                    a["selected"] = {slug_by_chain.get(c, c): codes for c, codes in chosen.items()}
                    extra["anchors"].append(a)
                wanted: dict[str, set[str]] = defaultdict(set)
                for a in extra["anchors"]:
                    for slug, codes in a["selected"].items():
                        wanted[slug] |= set(codes)
                for slug in slugs:
                    codes = sorted(wanted.get(slug, ()))
                    cls = by_slug.get(slug)
                    if not codes or cls is None or budget <= 0:
                        continue
                    codes = codes[:budget]
                    kinds = ["price_full"] + (["promo_full"] if args.with_promos else [])
                    for kind in kinds:
                        names, err = scrape_subprocess(
                            extra_dir, slug, kind, store_file_regex(kind, codes),
                            limit=len(codes) * 3, timeout=args.timeout)  # fmt: skip
                        newest = newest_per_store(names, cls().parse_filename)
                        keep = set(newest.values())
                        for name in names:  # one file per store: the newest
                            if name not in keep:
                                (extra_dir / slug / name).unlink(missing_ok=True)
                        extra["downloads"].append({"chain": slug, "kind": kind, "stores_asked": codes,
                                                   "files": sorted(keep), "error": err})  # fmt: skip
                        if kind == "price_full":
                            budget -= len(keep)
                        if err and not keep:
                            run.fail("download", f"{slug} {kind}: {err}")
                st["note"] = (f"{sum(len(d['files']) for d in extra['downloads'])} files, "
                              f"anchors: {', '.join(a['name'] for a in extra['anchors'])}")  # fmt: skip
        result["extra_download"] = extra

        # 3c. every price and promo file ------------------------------------------------------------
        with run.stage(
            "ingest: PriceFull and PromoFull files (Scheduler, adapters, gates, loader)"
        ) as st:
            n = 0
            for root in (files_dir, extra_dir):
                for slug in slugs:
                    cls = by_slug.get(slug)
                    if cls is None:
                        continue
                    for s, path in list_files(root, slug, cls):
                        if path.name.startswith("Stores"):
                            continue
                        ingest.load(s, path)
                        n += 1
            st["note"] = f"{n} files"
        rows_per_file(conn, ingest.records)
        result["files"] = ingest.records
        result["alerts"] = [{"chain_id": a.chain_id, "kind": a.kind, "message": a.message[:240]}
                            for a in ingest.sink.alerts]  # fmt: skip
        result["chains"] = chain_tables(conn, slug_by_chain)
        result["file_tracking"] = dict(conn.execute(
            "SELECT status, count(*) FROM file_tracking GROUP BY 1 ORDER BY 1").fetchall())  # fmt: skip
        for r in ingest.records:
            if r.get("gate", {}).get("status") in ("failed", "not tracked", "unrecognized"):
                run.fail("ingest", f"{r['chain']} {r.get('kind')} {r['file']}: "
                         f"{r['gate'].get('status')} {r['gate'].get('reason') or r['gate'].get('error') or ''}"[:300])  # fmt: skip
    finally:
        conn.close()

    # 4. catalog ------------------------------------------------------------------------------------
    cat = venv_bin("smartcart-catalog")
    catalog: dict = {}
    for label, cmd in (
        ("seed", [cat, "seed"]),
        ("normalize", [cat, "normalize", "--show", "0"]),
        ("extract (rule)", [cat, "extract", "--extractor", "rule"]),
        ("embed (hash)", [cat, "embed", "--target", "all", "--embedder", "hash"]),
        ("judge (rule)", [cat, "judge", "--judge", "rule"]),
    ):
        with run.stage(f"catalog: {label}") as st:
            res = run_cmd(cmd, env=env, check=False)
            catalog[label] = {"seconds": round(res.seconds, 2), "exit": res.returncode,
                              "stdout_tail": res.stdout[-600:]}  # fmt: skip
            if res.returncode != 0:
                raise RuntimeError(f"{label} exited {res.returncode}: {res.stderr[-300:]}")
    result["catalog"] = catalog
    with psycopg.connect(db_url) as c:
        result["matching"] = matching_counts(c)

    # 5. precompute + API -----------------------------------------------------------------------------
    def precompute(tag: str) -> dict:
        with run.stage(f"precompute effective prices ({tag})") as st:
            res = run_cmd([venv_bin("smartcart-api"), "precompute"],
                          env={**env, "PGTZ": "UTC"}, check=False)  # fmt: skip
            if res.returncode != 0:
                raise RuntimeError(f"precompute exited {res.returncode}: {res.stderr[-300:]}")
            metrics = last_json_document(res.stdout)
            metrics["wall_seconds"] = round(res.seconds, 2)
            with psycopg.connect(db_url) as c:
                metrics["table"] = effective_counts(c)
            st["note"] = f"{metrics.get('rows_written')} rows"
            return metrics

    def api_run(tag: str) -> dict:
        with psycopg.connect(db_url) as c:
            locs = pick_locations(c, args.locations)
        with run.stage(f"API: parse-list, compare, optimize ({tag})") as st:
            api = api_stage(db_url, locs, args.repeats, args.seed, run, tag)
            api["locations"] = locs
            st["note"] = f"{len(api['runs'])} basket runs at {len(locs)} locations"
            for p in api["problems"]:
                run.fail("api", p)
            return api

    result["precompute"] = precompute("production semantics: reviewed mappings only")
    result["api"] = api_run("production")
    with run.stage("basket index dry run (production semantics)") as st:
        result["basket_index"] = basket_index_dry_run(work, env, "production")
        st["note"] = f"status {result['basket_index'].get('status')}"

    # 7. stress ----------------------------------------------------------------------------------------
    if args.stress:
        with run.stage("stress: mark the machine suggestions accepted (performance only)") as st:
            with psycopg.connect(db_url) as c:
                n = c.execute(
                    "UPDATE item_canonical SET needs_review = false"
                    " WHERE needs_review AND NOT human_rejected"
                ).rowcount
                c.commit()
            st["note"] = f"{n} mappings"
        result["precompute_stress"] = precompute("stress: unreviewed mappings included")
        result["api_stress"] = api_run("stress")
        with run.stage("basket index dry run (stress)") as st:
            result["basket_index_stress"] = basket_index_dry_run(work, env, "stress")
            st["note"] = f"status {result['basket_index_stress'].get('status')}"

    with psycopg.connect(db_url) as c:
        result["pg_version"] = c.execute("SHOW server_version").fetchone()[0]
    result["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    result["stages"] = run.stages
    result["failures"] = run.failures
    return result


# --- report -------------------------------------------------------------------------------------------------


def _n(value) -> str:
    return "-" if value is None else f"{value:,}" if isinstance(value, int) else str(value)


def _ms(summary: dict | None) -> str:
    if not summary or summary.get("median") is None:
        return "-"
    return f"{summary['median']:g}"


def render_report(res: dict) -> str:
    """The Markdown report (job summary, artifact, and the generated tables of the doc)."""
    L: list[str] = []
    a = L.append
    a("## One real day through the pipeline (dry run)")
    a("")
    a(
        f"Mode `{res['mode']}`, commit `{res['commit']}`, runner `{res['runner']}` "
        f"({res.get('cpus')} CPUs, Python {res.get('python')}, Postgres {res.get('pg_version', '?')}), "
        f"{res['started_at']} to {res.get('finished_at', '?')} UTC. Measurements on one real day with "
        "hand-made baskets; the prices are real, the baskets and locations are not a sample of "
        "anything. **Not publishable.**"
    )
    a("")
    a("### Stages")
    a("")
    a("| stage | seconds | result |")
    a("|---|---|---|")
    for s in res["stages"]:
        a(
            f"| {md_escape(s['name'])} | {s['seconds']:g} | "
            f"{md_escape(s.get('note') or ('ok' if s['ok'] else s.get('error', 'failed')))} |"
        )
    a("")

    probe = res.get("probe")
    if probe:
        a("### Portals (the portal probe's own reachability and downloads)")
        a("")
        a("| chain | reachable | login | Stores download | PriceFull download |")
        a("|---|---|---|---|---|")
        for slug, c in probe["chains"].items():
            d = c.get("downloads", {})

            def cell(e):
                if not e:
                    return "-"
                return (
                    md_escape(e["file"])
                    if "file" in e
                    else "no: " + md_escape(str(e.get("error"))[:80])
                )

            a(
                f"| {slug} | {c['reachable']} ({c['http_status']}) | {md_escape(c['login'][:40])} | "
                f"{cell(d.get('stores'))} | {cell(d.get('price_full'))} |"
            )
        a("")

    files = res.get("files", [])
    a("### Files, gates and rows per chain")
    a("")
    a(
        "| chain | kind | file | published (Israel) | age h | schema | gate result | rows | seconds |"
    )
    a("|---|---|---|---|---|---|---|---|---|")
    for f in files:
        g = f.get("gate", {})
        gates = f"quarantined ({', '.join(g['gates'])})" if g.get("gates") else g.get("status")
        if g.get("status") == "failed":
            gates = f"failed: {md_escape(str(g.get('reason'))[:80])}"
        rows = f.get("price_rows") or f.get("promo_rows") or f.get("parse", {}).get("stores")
        a(
            f"| {f['chain']} | {f.get('kind', '?')} | `{md_escape(f['file'])}` | "
            f"{f.get('published_at') or '?'} | {_n(f.get('age_hours'))}"
            f"{' (stale on the real clock)' if f.get('stale_on_real_clock') else ''} | "
            f"{f.get('parse', {}).get('schema') or g.get('schema') or '?'} | {gates} | {_n(rows)} | "
            f"{_n(f.get('seconds'))} |"
        )
    a("")
    a(
        f"`file_tracking` after the run: {res.get('file_tracking')}. Alerts raised: {len(res.get('alerts', []))}."
    )
    for al in res.get("alerts", [])[:12]:
        a(f"- `{al['chain_id']}` {al['kind']}: {md_escape(al['message'])}")
    a("")
    chains = res.get("chains", {})
    a(
        "| chain | physical stores | located | online | items | price events | stores with prices | promos | promo items |"
    )
    a("|---|---|---|---|---|---|---|---|---|")
    for _cid, c in sorted(chains.items(), key=lambda kv: kv[1].get("slug", "")):
        a(
            f"| {c.get('slug')} | {_n(c.get('physical'))} | {_n(c.get('located'))} | {_n(c.get('online'))} | "
            f"{_n(c.get('items'))} | {_n(c.get('price_events'))} | {_n(c.get('priced_stores'))} | "
            f"{_n(c.get('promos'))} | {_n(c.get('promo_items'))} |"
        )
    a("")
    ex = res.get("extra_download") or {}
    if ex.get("anchors"):
        a("Extra downloads (the stores nearest to these city centres, for the optimizer):")
        a("")
        for an in ex["anchors"]:
            sel = ", ".join(f"{s} {','.join(c)}" for s, c in an["selected"].items())
            a(
                f"- {an['name']}: {an['chains']} chains and {an['stores']} located stores within "
                f"{res['options']['radius_km']:g} km; asked for {sel}"
            )
        for d in ex["downloads"]:
            if d.get("error"):
                a(f"- download `{d['chain']}` {d['kind']}: {md_escape(d['error'])}")
        a("")

    m = res.get("matching")
    if m:
        a("### Matching on the real items")
        a("")
        a(
            f"{_n(m['items'])} items; {_n(m['mapped_items'])} mapped to a canonical (any level, "
            f"including the review queue); {_n(m['served_items'])} served (no review flag), onto "
            f"{_n(m['served_canonicals'])} canonicals."
        )
        a("")
        a("| level | mappings served | mappings in the review queue |")
        a("|---|---|---|")
        for lv in ("exact", "any_brand", "close"):
            d = m["by_level"].get(lv, {})
            a(f"| {lv} | {_n(d.get('served', 0))} | {_n(d.get('review', 0))} |")
        a("")
        a("| chain | items | mapped | served |")
        a("|---|---|---|---|")
        for cid, d in sorted(m["per_chain"].items()):
            a(
                f"| {chains.get(cid, {}).get('slug', cid)} | {_n(d['items'])} | {_n(d['mapped'])} | {_n(d['served'])} |"
            )
        a("")
        for label, d in res.get("catalog", {}).items():
            a(f"- {label}: {d['seconds']:g} s")
        a("")

    for key, title in (("precompute", "production semantics"), ("precompute_stress", "stress")):
        p = res.get(key)
        if not p:
            continue
        t = p.get("table", {})
        a(f"### Precompute ({title})")
        a("")
        a(
            f"{_n(p.get('rows_written'))} rows written in {p.get('seconds')} s of job time "
            f"({p.get('wall_seconds')} s wall including start-up); {_n(p.get('items_priced'))} items "
            f"priced at {_n(t.get('stores'))} stores ({_n(p.get('stores'))} stores of "
            f"{_n(p.get('chains'))} chains considered); "
            f"{_n(p.get('rows_with_promo'))} rows with a promo, {_n(p.get('rows_club_required'))} "
            f"club-only. Canonicals with a real price: {_n(t.get('canonicals'))}, of them "
            f"{_n(t.get('canonicals_in_2plus_stores_any_brand'))} at two or more stores (any brand)."
        )
        a("")
        a("| level | rows | canonicals priced | stores |")
        a("|---|---|---|---|")
        for lv, d in sorted(t.get("by_flex", {}).items()):
            a(f"| {lv} | {_n(d['rows'])} | {_n(d['canonicals'])} | {_n(d['stores'])} |")
        a("")

    for key, title in (
        ("api", "production semantics"),
        ("api_stress", "stress: unreviewed mappings included, performance only"),
    ):
        api = res.get(key)
        if not api:
            continue
        a(f"### /parse-list, /compare and /optimize ({title})")
        a("")
        a(
            "Locations: "
            + "; ".join(
                f"{loc['name']} ({loc['priced_stores']} priced stores, "
                f"{loc['priced_chains']} chains within {loc['radius_m'] / 1000:g} km)"
                for loc in api.get("locations", [])
            )
            + "."
        )
        a("")
        if api["parse"]:
            a("| hand-made list | rows | resolved | need confirmation | not found | ms |")
            a("|---|---|---|---|---|---|")
            for name, p in api["parse"].items():
                a(
                    f"| {name} | {p['rows']} | {p['resolved']} | {p['needs_confirmation']} | "
                    f"{len(p['not_found'])} | {p['ms']:g} |"
                )
            a("")
        a(
            "Times are the median over the repeats, in ms, through the in-process test client (no network)."
        )
        a("")
        a(
            "| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | "
            "subsets | recommended (MILP) | net saving heuristic / MILP |"
        )
        a("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in api["runs"]:
            h, mm = r.get("heuristic", {}), r.get("milp", {})
            rec = mm.get("recommended") or {}
            plan = f"{rec.get('kind')}: {', '.join(rec.get('stores', []))}" if rec else "-"
            nets = (
                f"{_n((h.get('recommended') or {}).get('net_saving'))} / "
                f"{_n(rec.get('net_saving'))}"
            )
            a(
                f"| {md_escape(r['location'])} | {md_escape(r['basket'])} | {r['lines']} | "
                f"{_n(r.get('stores_in_radius'))} | {_n(r.get('complete_stores'))} | "
                f"{_ms(r.get('compare_ms'))} | {_ms(h.get('ms'))} | {_ms(mm.get('ms'))} | "
                f"{_n(h.get('subsets_evaluated'))} | {md_escape(plan)} | {nets} |"
            )
        a("")
        by_size: dict[tuple[str, str], list[float]] = defaultdict(list)
        for r in api["runs"]:
            for solver in ("heuristic", "milp"):
                med = r.get(solver, {}).get("ms", {}).get("median")
                if med is not None:
                    by_size[(r["basket"], solver)].append(med)
            cm = r.get("compare_ms", {}).get("median")
            if cm is not None:
                by_size[(r["basket"], "compare")].append(cm)
        if by_size:
            a("Median of the per-location medians, by basket:")
            a("")
            a("| basket | /compare ms | heuristic ms | MILP ms |")
            a("|---|---|---|---|")
            for basket in dict.fromkeys(r["basket"] for r in api["runs"]):

                def med(kind: str, basket=basket, by_size=by_size) -> str:
                    v = by_size.get((basket, kind))
                    return f"{statistics.median(v):.1f}" if v else "-"

                a(
                    f"| {md_escape(basket)} | {med('compare')} | {med('heuristic')} | {med('milp')} |"
                )
            a("")
        if api["problems"]:
            a(f"Invariant violations seen on responses ({len(api['problems'])}):")
            for p in api["problems"][:15]:
                a(f"- {md_escape(p)}")
            a("")

    for key, title in (("basket_index", "production semantics"), ("basket_index_stress", "stress")):
        b = res.get(key)
        if not b:
            continue
        a(f"### Basket index on the real day (#44, dry run, {title})")
        a("")
        a(
            f"`smartcart-catalog basket-index` into a scratch directory (month {b['month']}, status "
            f"`{b.get('status')}`, exit {b['exit']}): **a dry run on one day, never publishable.**"
        )
        a("")
        for c in b.get("checks", []):
            a(f"- {c['level']}: `{c['code']}` {md_escape(c['message'])}")
        if b.get("chains"):
            a("")
            a(f"Basket of {b.get('basket_lines')} lines; price date {b.get('price_date')}.")
            a("")
            a("| chain | total (ILS) | lines priced | lines missing | stores | ranked |")
            a("|---|---|---|---|---|---|")
            for c in b["chains"]:
                a(
                    f"| {md_escape(c['chain'])} | {_n(c['total'])} | {_n(c['items_priced'])} | "
                    f"{_n(c['missing'])} | {_n(c['stores'])} | {'yes' if c['complete'] else 'no'} |"
                )
        a("")

    fails = res.get("failures", [])
    a(f"### Failures and findings the run recorded ({len(fails)})")
    a("")
    for f in fails:
        a(f"- **{f['stage']}**: {md_escape(f['what'])}")
    if not fails:
        a("None recorded by the script itself.")
    a("")
    return "\n".join(L) + "\n"


# --- main ----------------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="download (or read files), load, match, precompute, optimize")
    r.add_argument("--work", type=Path, required=True, help="scratch directory (outside the repo)")
    src = r.add_mutually_exclusive_group()
    src.add_argument("--files", type=Path, help="a directory of <slug>/<portal file>, no network")
    src.add_argument("--from-fixtures", action="store_true",
                     help="the committed real fixtures under tests/fixtures/<slug>/real, no network")  # fmt: skip
    r.add_argument("--chain", action="append", help="chain slug (repeatable; default: every chain)")
    r.add_argument("--timeout", type=float, default=240, help="seconds per portal download")
    r.add_argument("--anchors", type=int, default=3, help="city centres for the extra downloads")
    r.add_argument("--per-chain", type=int, default=2, help="stores per chain per city centre")
    r.add_argument("--radius-km", type=float, default=4.0, help="radius of a city centre")
    r.add_argument("--max-files", type=int, default=40, help="cap on extra PriceFull files")
    r.add_argument("--no-promos", dest="with_promos", action="store_false",
                   help="do not download PromoFull files for the extra stores")  # fmt: skip
    r.add_argument("--no-stress", dest="stress", action="store_false",
                   help="skip the stress variant (unreviewed mappings included)")  # fmt: skip
    r.add_argument("--locations", type=int, default=3, help="API locations")
    r.add_argument("--repeats", type=int, default=5, help="repeats per timed request")
    r.add_argument("--seed", type=int, default=20261021, help="seed of the drawn baskets")
    r.add_argument("--out", type=Path, default=None, help="Markdown report (default stdout)")
    r.add_argument("--json-out", type=Path, default=None)
    s = sub.add_parser("_scrape", help=argparse.SUPPRESS)
    s.add_argument("slug")
    s.add_argument("kind", choices=["price_full", "promo_full", "stores"])
    s.add_argument("--regex", default=None)
    s.add_argument("--limit", type=int, required=True)
    s.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    if args.cmd == "_scrape":
        return _scrape_main(args)
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    res = run_all(args)
    write_text(args.out, render_report(res))
    if args.json_out:
        write_text(args.json_out, json.dumps(res, ensure_ascii=False, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
