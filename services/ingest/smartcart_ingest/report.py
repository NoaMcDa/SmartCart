"""Phase 0 exit report (issue #60): evidence for the exit criteria, computed from the database.

``build_exit_report(conn, start, end)`` reads ``file_tracking``, ``stores`` and ``promos`` and
returns an ``ExitReport``; ``render_markdown`` turns it into the text of
``docs/phase-0-exit-report.md``. Run it without the CLI::

    python -m smartcart_ingest.report --start 2026-10-20 --end 2026-11-02 --out report.md

What it measures, and the choices behind it:

* A (chain, day) is a success when at least one file of kind ``price_full`` or ``promo_full`` of
  that chain reached status ``loaded`` on that day. This is deliberately the issue's definition,
  and it is lenient (a loaded promo file hides a failed price file); the failed-files table below
  the matrix lists every full file that did not load, so a masked failure is still visible.
* The day of a file is the Israel-time date of ``published_at`` (``created_at`` when the source
  gave no publish time).
* The success rate is successes over (chains x days). A day is "above threshold" when the share
  of chains that succeeded that day is strictly above the threshold (95 percent by default; with
  the ten D13 chains that means every chain). The longest streak counts consecutive such days.
* Stores: physical stores with no coordinates are listed as exceptions. When the ``stores.geog``
  column does not exist (a database without PostGIS) no store can have coordinates, so every
  physical store is listed.
* Promos: up to ten parsed promos per main chain, spread over reward types, with the structured
  fields next to the raw description so a human can tick each one as checked.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

SUCCESS_THRESHOLD = 0.95
REQUIRED_WINDOW_DAYS = 14
PROMO_SAMPLE_SIZE = 10
FULL_KINDS = ("price_full", "promo_full")
LOCAL_TZ = "Asia/Jerusalem"
MAX_LISTED_STORES = 50
MAX_LISTED_FAILURES = 50

BASKET_QUERY_PATH = (
    Path(__file__).resolve().parents[3] / "supabase" / "queries" / "basket_radius.sql"
)


@dataclass(frozen=True)
class ChainSpec:
    """A chain of the Phase 0 list (docs/decisions.md D13). ``chain_ids`` has more than one entry
    when the chain publishes under several chain ids."""

    name: str
    chain_ids: tuple[str, ...]
    main: bool  # one of the six main chains (hourly deltas, promo spot-check)


D13_CHAINS: tuple[ChainSpec, ...] = (
    ChainSpec("Shufersal", ("7290027600007",), True),
    ChainSpec("Rami Levy", ("7290058140886",), True),
    ChainSpec("Victory", ("7290696200003", "7290058103393"), True),
    ChainSpec("Yeinot Bitan and Carrefour", ("7290055700007",), True),
    ChainSpec("Hazi Hinam", ("7290700100008",), True),
    ChainSpec("Tiv Taam", ("7290873255550",), True),
    ChainSpec("Osher Ad", ("7290103152017",), False),
    ChainSpec("Yohananof", ("7290803800003",), False),
    ChainSpec("Machsanei Hashuk", ("7290661400001", "7290633800006"), False),
    ChainSpec("King Store", ("7290058108879",), False),
)


@dataclass(frozen=True)
class DaySummary:
    day: date
    succeeded: int  # chains with a loaded full file that day
    total: int  # chains measured
    rate: float
    above_threshold: bool


@dataclass(frozen=True)
class ChainLoads:
    chain: ChainSpec
    days: dict[date, bool]  # day -> a full load succeeded

    @property
    def successes(self) -> int:
        return sum(self.days.values())

    @property
    def rate(self) -> float:
        return self.successes / len(self.days) if self.days else 0.0


@dataclass(frozen=True)
class FailedFile:
    chain_id: str
    day: date
    kind: str
    status: str
    reason: str | None


@dataclass(frozen=True)
class StoreException:
    id: int
    chain_id: str
    store_code: str
    name: str
    city: str | None
    address: str | None
    reason: str


@dataclass(frozen=True)
class PromoSample:
    chain: str
    chain_id: str
    store_code: str | None  # None: chain-wide promo
    promo_id: str
    description: str
    starts_at: datetime | None
    ends_at: datetime | None
    hours: str | None
    club_only: bool
    club_name: str | None
    min_qty: Any
    max_qty: Any
    reward_type: str
    reward_value: Any
    item_count: int


@dataclass(frozen=True)
class PromoStats:
    chain: str
    total: int
    by_reward_type: dict[str, int]


@dataclass
class ExitReport:
    start: date
    end: date
    generated_at: datetime
    threshold: float
    chains: list[ChainLoads]
    days: list[DaySummary]
    success_rate: float
    longest_streak: int
    streak_start: date | None
    streak_end: date | None
    failed_files: list[FailedFile]
    physical_stores: int
    stores_with_coordinates: int
    store_exceptions: list[StoreException]
    promo_samples: dict[str, list[PromoSample]]
    promo_stats: list[PromoStats]
    basket_params: dict[str, Any] | None = None
    basket_rows: list[dict[str, Any]] | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def window_days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def meets_success_rate(self) -> bool:
        """More than ``threshold`` success over a window of at least two weeks."""
        return self.window_days >= REQUIRED_WINDOW_DAYS and self.success_rate > self.threshold

    @property
    def stores_missing_coordinates(self) -> int:
        return self.physical_stores - self.stores_with_coordinates


# --- computation -------------------------------------------------------------------------------


def _date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=n) for n in range((end - start).days + 1)]


def longest_streak(days: Sequence[DaySummary]) -> tuple[int, date | None, date | None]:
    """Longest run of consecutive above-threshold days: (length, first day, last day)."""
    best = (0, None, None)
    run = 0
    run_start: date | None = None
    for d in days:
        if d.above_threshold:
            if run == 0:
                run_start = d.day
            run += 1
            if run > best[0]:
                best = (run, run_start, d.day)
        else:
            run = 0
    return best


def _file_tracking_section(
    conn: psycopg.Connection, start: date, end: date, chains: Sequence[ChainSpec], threshold: float
) -> tuple[list[ChainLoads], list[DaySummary], float, list[FailedFile]]:
    day_expr = f"(COALESCE(published_at, created_at) AT TIME ZONE '{LOCAL_TZ}')::date"
    all_ids = [cid for c in chains for cid in c.chain_ids]
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT DISTINCT chain_id, {day_expr} AS day FROM file_tracking"
            " WHERE chain_id = ANY(%s) AND status = 'loaded' AND kind = ANY(%s)"
            f" AND {day_expr} BETWEEN %s AND %s",
            (all_ids, list(FULL_KINDS), start, end),
        )
        loaded = {(cid, day) for cid, day in cur.fetchall()}
        cur.execute(
            f"SELECT chain_id, {day_expr} AS day, kind, status, reason FROM file_tracking"
            " WHERE chain_id = ANY(%s) AND status <> 'loaded' AND kind = ANY(%s)"
            f" AND {day_expr} BETWEEN %s AND %s"
            " ORDER BY day, chain_id, id",
            (all_ids, list(FULL_KINDS), start, end),
        )
        failed = [FailedFile(*row) for row in cur.fetchall()]

    window = _date_range(start, end)
    chain_loads = [
        ChainLoads(c, {d: any((cid, d) in loaded for cid in c.chain_ids) for d in window})
        for c in chains
    ]
    day_summaries = []
    for d in window:
        ok = sum(cl.days[d] for cl in chain_loads)
        rate = ok / len(chains) if chains else 0.0
        day_summaries.append(DaySummary(d, ok, len(chains), rate, rate > threshold))
    cells = len(chains) * len(window)
    success_rate = sum(cl.successes for cl in chain_loads) / cells if cells else 0.0
    return chain_loads, day_summaries, success_rate, failed


def _has_geog(conn: psycopg.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM information_schema.columns"
        " WHERE table_schema = current_schema() AND table_name = 'stores'"
        " AND column_name = 'geog'"
    ).fetchone()
    return row is not None


def _stores_section(conn: psycopg.Connection) -> tuple[int, int, list[StoreException]]:
    if _has_geog(conn):
        reason = (
            "no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet"
        )
        with_coords_sql = "count(*) FILTER (WHERE geog IS NOT NULL)"
        missing_filter = "AND geog IS NULL"
    else:
        reason = "no coordinates: the database has no stores.geog column (no PostGIS)"
        with_coords_sql = "0"
        missing_filter = ""
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*), {with_coords_sql} FROM stores WHERE channel = 'physical'")
        total, with_coords = cur.fetchone()
        cur.execute(
            "SELECT id, chain_id, store_code, name, city, address FROM stores"
            f" WHERE channel = 'physical' {missing_filter} ORDER BY chain_id, store_code"
        )
        exceptions = [StoreException(*row, reason) for row in cur.fetchall()]
    return total, with_coords, exceptions


def _promos_section(
    conn: psycopg.Connection, chains: Sequence[ChainSpec], sample_size: int
) -> tuple[dict[str, list[PromoSample]], list[PromoStats]]:
    samples: dict[str, list[PromoSample]] = {}
    stats: list[PromoStats] = []
    with conn.cursor(row_factory=dict_row) as cur:
        for chain in (c for c in chains if c.main):
            ids = list(chain.chain_ids)
            cur.execute(
                "SELECT reward_type, count(*) AS n FROM promos WHERE chain_id = ANY(%s)"
                " GROUP BY reward_type ORDER BY reward_type",
                (ids,),
            )
            by_type = {r["reward_type"]: r["n"] for r in cur.fetchall()}
            stats.append(PromoStats(chain.name, sum(by_type.values()), by_type))
            # Spread the sample over reward types (first of each type, then second of each, ...),
            # with a stable hash order inside a type so a rerun picks the same promos.
            cur.execute(
                "SELECT * FROM ("
                "  SELECT q.*, row_number() OVER (ORDER BY q.type_rank, q.h, q.id) AS rn FROM ("
                "    SELECT p.id, p.chain_id, s.store_code, p.promo_id, p.description,"
                "           p.starts_at, p.ends_at, p.hours, p.club_only, p.club_name,"
                "           p.min_qty, p.max_qty, p.reward_type, p.reward_value,"
                "           (SELECT count(*) FROM promo_items AS pi WHERE pi.promo_id = p.id)"
                "             AS item_count,"
                "           md5(p.chain_id || ':' || p.promo_id) AS h,"
                "           row_number() OVER (PARTITION BY p.reward_type"
                "                              ORDER BY md5(p.chain_id || ':' || p.promo_id), p.id)"
                "             AS type_rank"
                "    FROM promos AS p LEFT JOIN stores AS s ON s.id = p.store_id"
                "    WHERE p.chain_id = ANY(%s)"
                "  ) AS q"
                ") AS r WHERE rn <= %s ORDER BY rn",
                (ids, sample_size),
            )
            samples[chain.name] = [
                PromoSample(
                    chain=chain.name,
                    chain_id=r["chain_id"],
                    store_code=r["store_code"],
                    promo_id=r["promo_id"],
                    description=r["description"],
                    starts_at=r["starts_at"],
                    ends_at=r["ends_at"],
                    hours=r["hours"],
                    club_only=r["club_only"],
                    club_name=r["club_name"],
                    min_qty=r["min_qty"],
                    max_qty=r["max_qty"],
                    reward_type=r["reward_type"],
                    reward_value=r["reward_value"],
                    item_count=r["item_count"],
                )
                for r in cur.fetchall()
            ]
    return samples, stats


def build_exit_report(
    conn: psycopg.Connection,
    start_date: date,
    end_date: date,
    *,
    chains: Sequence[ChainSpec] = D13_CHAINS,
    threshold: float = SUCCESS_THRESHOLD,
    promo_sample_size: int = PROMO_SAMPLE_SIZE,
) -> ExitReport:
    """Compute the exit-report evidence for the window ``start_date`` to ``end_date`` inclusive."""
    if end_date < start_date:
        raise ValueError("end_date is before start_date")
    chain_loads, days, rate, failed = _file_tracking_section(
        conn, start_date, end_date, chains, threshold
    )
    streak, streak_start, streak_end = longest_streak(days)
    physical, with_coords, exceptions = _stores_section(conn)
    samples, stats = _promos_section(conn, chains, promo_sample_size)
    return ExitReport(
        start=start_date,
        end=end_date,
        generated_at=datetime.now(UTC),
        threshold=threshold,
        chains=chain_loads,
        days=days,
        success_rate=rate,
        longest_streak=streak,
        streak_start=streak_start,
        streak_end=streak_end,
        failed_files=failed,
        physical_stores=physical,
        stores_with_coordinates=with_coords,
        store_exceptions=exceptions,
        promo_samples=samples,
        promo_stats=stats,
    )


def run_basket_query(
    conn: psycopg.Connection,
    barcodes: Iterable[str],
    lon: float,
    lat: float,
    radius_m: float,
    include_online: bool = False,
) -> list[dict[str, Any]]:
    """Run ``supabase/queries/basket_radius.sql``: one dict per store in the radius."""
    params = {
        "barcodes": list(barcodes),
        "lon": lon,
        "lat": lat,
        "radius_m": radius_m,
        "include_online": include_online,
    }
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(BASKET_QUERY_PATH.read_text(encoding="utf-8"), params)
        return cur.fetchall()


# --- Markdown ----------------------------------------------------------------------------------


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _cell(text: Any) -> str:
    """Escape a value for a Markdown table cell."""
    if text is None:
        return ""
    return str(text).replace("|", "\\|").replace("\n", " ")


def _table(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return out


def render_markdown(report: ExitReport) -> str:
    """The evidence sections of the exit report, in the order of the issue's acceptance list."""
    r = report
    lines: list[str] = []
    add = lines.append
    add(f"# Phase 0 exit evidence, {r.start.isoformat()} to {r.end.isoformat()}")
    add("")
    add(f"Generated {r.generated_at:%Y-%m-%d %H:%M} UTC by `python -m smartcart_ingest.report`.")
    add("")

    # 1. Nightly loads
    add("## 1. Nightly loads")
    add("")
    verdict = "met" if r.meets_success_rate else "not met"
    add(
        f"- Window: {r.window_days} days ({r.start.isoformat()} to {r.end.isoformat()}), "
        f"{len(r.chains)} chains."
    )
    add(
        f"- Success rate: **{_pct(r.success_rate)}** "
        f"({sum(c.successes for c in r.chains)} of {len(r.chains) * r.window_days} chain-days "
        f"with a loaded full file). Criterion: above {_pct(r.threshold)} over at least "
        f"{REQUIRED_WINDOW_DAYS} days: **{verdict}**."
    )
    if r.longest_streak:
        add(
            f"- Longest streak of days above {_pct(r.threshold)}: **{r.longest_streak}** "
            f"({r.streak_start.isoformat()} to {r.streak_end.isoformat()})."
        )
    else:
        add(f"- Longest streak of days above {_pct(r.threshold)}: **0**.")
    add("")
    add("Per chain and day (`ok` = a `price_full` or `promo_full` file reached `loaded`):")
    add("")
    days = [d.day for d in r.days]
    header = ["Chain", "Rate", *(d.strftime("%m-%d") for d in days)]
    rows = [
        [c.chain.name, _pct(c.rate), *("ok" if c.days[d] else "FAIL" for d in days)]
        for c in r.chains
    ]
    rows.append(["**All chains**", _pct(r.success_rate), *(_pct(s.rate) for s in r.days)])
    lines += _table(header, rows)
    add("")
    if r.failed_files:
        add("Full files that did not load:")
        add("")
        shown = r.failed_files[:MAX_LISTED_FAILURES]
        lines += _table(
            ["Day", "Chain id", "Kind", "Status", "Reason"],
            [(f.day.isoformat(), f.chain_id, f.kind, f.status, f.reason) for f in shown],
        )
        if len(r.failed_files) > len(shown):
            add("")
            add(f"({len(r.failed_files) - len(shown)} more not shown.)")
        add("")

    # 2. Store coordinates
    add("## 2. Store coordinates")
    add("")
    add(
        f"- Physical stores: {r.physical_stores}; with coordinates: {r.stores_with_coordinates}; "
        f"without: **{r.stores_missing_coordinates}**."
    )
    if r.store_exceptions:
        add("")
        shown_stores = r.store_exceptions[:MAX_LISTED_STORES]
        lines += _table(
            ["Chain id", "Store", "Name", "City", "Address", "Reason"],
            [(s.chain_id, s.store_code, s.name, s.city, s.address, s.reason) for s in shown_stores],
        )
        if len(r.store_exceptions) > len(shown_stores):
            add("")
            add(f"({len(r.store_exceptions) - len(shown_stores)} more not shown.)")
        add("")
        add(
            "Each exception needs a plan before go: geocode from the address, ask the chain, or "
            "accept it with a stated reason."
        )
    else:
        add("- No exceptions: every physical store has coordinates.")
    add("")

    # 3. Promo parsing
    add("## 3. Promo parsing, main chains")
    add("")
    stats_rows = [
        (s.chain, s.total, ", ".join(f"{k}: {v}" for k, v in s.by_reward_type.items()) or "none")
        for s in r.promo_stats
    ]
    lines += _table(["Chain", "Promos parsed", "By reward type"], stats_rows)
    add("")
    for chain, sample in r.promo_samples.items():
        add(f"### {chain}")
        add("")
        if not sample:
            add("No promos in the database for this chain.")
            add("")
            continue
        lines += _table(
            [
                "Promo",
                "Store",
                "Raw description",
                "Reward",
                "Value",
                "Min qty",
                "Max qty",
                "Club",
                "Dates",
                "Hours",
                "Items",
                "Checked",
            ],  # fmt: skip
            [
                (
                    p.promo_id,
                    p.store_code or "chain-wide",
                    p.description,
                    p.reward_type,
                    p.reward_value,
                    p.min_qty,
                    p.max_qty,
                    (p.club_name or "club") if p.club_only else "no",
                    f"{p.starts_at:%Y-%m-%d} to {p.ends_at:%Y-%m-%d}"
                    if p.starts_at and p.ends_at
                    else "",
                    p.hours,
                    p.item_count,
                    "[ ]",
                )
                for p in sample
            ],
        )
        add("")
    add("Tick `Checked` by comparing each structured field with the raw description.")
    add("")

    # 4. Basket query
    add("## 4. Basket price across stores in a radius")
    add("")
    if r.basket_rows is None:
        add("Not run in this report. See `supabase/queries/README.md` to run the query.")
    else:
        p = r.basket_params or {}
        add(
            f"Barcodes: {', '.join(p.get('barcodes', []))}. Point: {p.get('lon')}, {p.get('lat')}; "
            f"radius {p.get('radius_m')} m; online stores "
            f"{'included' if p.get('include_online') else 'excluded'}."
        )
        add("")
        lines += _table(
            ["Store", "Chain id", "Name", "Distance (m)", "Total", "Found", "Missing", "Complete"],
            [
                (
                    b["store_id"],
                    b["chain_id"],
                    b["store_name"],
                    b["distance_m"],
                    b["basket_total"],
                    b["found_count"],
                    ", ".join(b["missing_barcodes"]) or "none",
                    "yes" if b["is_complete"] else "no",
                )
                for b in r.basket_rows
            ],
        )
    add("")
    for note in r.notes:
        add(f"> {note}")
        add("")
    return "\n".join(lines).rstrip() + "\n"


# --- entry point -------------------------------------------------------------------------------


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m smartcart_ingest.report",
        description="Compute the Phase 0 exit evidence from the database and write it as Markdown.",
    )
    p.add_argument("--start", required=True, type=date.fromisoformat, help="first day, YYYY-MM-DD")
    p.add_argument("--end", required=True, type=date.fromisoformat, help="last day, YYYY-MM-DD")
    p.add_argument("--out", type=Path, help="output file (default: stdout)")
    p.add_argument("--dsn", help="Postgres connection string (default: $DATABASE_URL)")
    p.add_argument(
        "--only-chains",
        help="comma-separated chain names to measure, e.g. after the D13 tie-break drops two",
    )
    basket = p.add_argument_group("optional basket section")
    basket.add_argument("--basket-barcodes", help="comma-separated barcodes")
    basket.add_argument("--lon", type=float)
    basket.add_argument("--lat", type=float)
    basket.add_argument("--radius-m", type=float)
    basket.add_argument("--include-online", action="store_true")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    chains: Sequence[ChainSpec] = D13_CHAINS
    if args.only_chains:
        wanted = {n.strip().lower() for n in args.only_chains.split(",") if n.strip()}
        chains = tuple(c for c in D13_CHAINS if c.name.lower() in wanted)
        unknown = wanted - {c.name.lower() for c in chains}
        if unknown:
            print(f"unknown chain names: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
    dsn = args.dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        print("no --dsn given and DATABASE_URL is not set", file=sys.stderr)
        return 2
    with psycopg.connect(dsn) as conn:
        report = build_exit_report(conn, args.start, args.end, chains=chains)
        if args.basket_barcodes:
            if args.lon is None or args.lat is None or args.radius_m is None:
                print("--basket-barcodes needs --lon, --lat and --radius-m", file=sys.stderr)
                return 2
            barcodes = [b.strip() for b in args.basket_barcodes.split(",") if b.strip()]
            report.basket_params = {
                "barcodes": barcodes,
                "lon": args.lon,
                "lat": args.lat,
                "radius_m": args.radius_m,
                "include_online": args.include_online,
            }
            report.basket_rows = run_basket_query(
                conn, barcodes, args.lon, args.lat, args.radius_m, args.include_online
            )
    text = render_markdown(report)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
