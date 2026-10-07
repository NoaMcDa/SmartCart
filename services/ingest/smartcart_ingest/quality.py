"""Quality gates, run on every parsed file before it is loaded (issue #42).

Gates (thresholds per chain from :meth:`Settings.thresholds_for`):

* ``zero_price``       any price record with a price of zero or less.
* ``price_jump``       a price more than ``price_jump_factor`` times the latest known price for
                       the same item and store: the store's own event, else the chain base price
                       (``store_id NULL``) when the store has no history for the item, or is not
                       loaded yet. A chain-level record (``store_code`` None, issue #80) is
                       compared with the latest base price.
* ``item_count_drop``  a full file (PriceFull, PromoFull, Stores) with fewer records than
                       ``item_count_drop_ratio`` times the previous loaded file of the same kind
                       for the same chain and store.
* ``stale_date``       ``published_at`` older than ``stale_file_max_age_hours``.

Every gate runs, so one file can fail several. A failing file gets one ``quarantine_events`` row
per failed gate, status ``quarantined`` with the reasons, and none of its rows reach the data
tables. Deltas pass through the same gates (no special path), except the item-count gate, which
only means something for complete files.

Soft warnings (issue #16) never quarantine: the file is loaded, the warning is recorded in
``quality_warnings`` and sent as a ``quality_warning`` alert.

* ``gap_report_pressure``  a price file (full or delta) for a store that users reported at
                           least ``gap_report_pressure_min`` confirmed price mismatches for in
                           the last ``GAP_PRESSURE_DAYS`` days (``gap_report_pressure()`` in
                           migration 20261009100000_mvp_followups.sql: the report carries the
                           price we showed and the shelf price, and they differ; counted once per
                           reporter and product). The prices shown for that store may be wrong
                           or late. Recorded at most once per store per ``WARNING_REPEAT_HOURS``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

import psycopg

from smartcart_ingest import tracking
from smartcart_ingest.loader import record_count
from smartcart_ingest.models import ParsedFile
from smartcart_ingest.settings import Thresholds

COUNTED_KINDS = frozenset({"price_full", "promo_full", "stores"})
_EXAMPLES = 5


@dataclass(frozen=True)
class GateFailure:
    gate: str
    detail: str


@dataclass(frozen=True)
class GateWarning:
    """A soft finding: recorded and alerted, the file is still loaded."""

    warning: str
    detail: str
    store_code: str | None = None


GAP_PRESSURE_DAYS = 7
WARNING_REPEAT_HOURS = 24
PRICE_KINDS = frozenset({"price_full", "price"})


def _examples(values: list[str]) -> str:
    shown = ", ".join(values[:_EXAMPLES])
    return shown + (", ..." if len(values) > _EXAMPLES else "")


def gate_zero_price(parsed: ParsedFile) -> GateFailure | None:
    bad = [f"{p.item_code}@{p.store_code}={p.price}" for p in parsed.prices if p.price <= 0]
    if not bad:
        return None
    return GateFailure("zero_price", f"{len(bad)} prices <= 0: {_examples(bad)}")


def latest_known_prices(
    conn: psycopg.Connection, chain_id: str, pairs: set[tuple[str, str | None]]
) -> dict[tuple[str, str | None], Decimal]:
    """(item_code, store_code) -> latest price in force: the store's own latest event, else the
    latest chain base price (``store_id NULL``). The base is used when the store has no event
    for the item and when the store is not in ``stores`` yet (a new store's first file). A
    ``store_code`` of None (a chain-level record) is compared with the base price only."""
    if not pairs:
        return {}
    item_codes = [i for i, _ in pairs]
    store_codes = [s for _, s in pairs]
    rows = conn.execute(
        "SELECT r.item_code, r.store_code, lp.price"
        " FROM unnest(%s::text[], %s::text[]) AS r(item_code, store_code)"
        " JOIN items AS i ON i.chain_id = %s AND i.item_code = r.item_code"
        " LEFT JOIN stores AS s ON s.chain_id = %s AND s.store_code = r.store_code"
        " JOIN LATERAL ("
        "   SELECT p.price FROM prices AS p"
        "   WHERE p.item_id = i.id"
        "     AND (p.store_id IS NULL OR (s.id IS NOT NULL AND p.store_id = s.id))"
        "   ORDER BY (p.store_id IS NOT NULL) DESC, p.valid_from DESC LIMIT 1"
        " ) AS lp ON true",
        (item_codes, store_codes, chain_id, chain_id),
    ).fetchall()
    return {(r[0], r[1]): r[2] for r in rows}


def gate_price_jump(
    conn: psycopg.Connection, parsed: ParsedFile, factor: float
) -> GateFailure | None:
    by_chain: dict[str, set[tuple[str, str | None]]] = defaultdict(set)
    for p in parsed.prices:
        by_chain[p.chain_id].add((p.item_code, p.store_code))
    limit = Decimal(str(factor))
    bad: list[str] = []
    for chain_id, pairs in by_chain.items():
        known = latest_known_prices(conn, chain_id, pairs)
        for p in parsed.prices:
            if p.chain_id != chain_id:
                continue
            prev = known.get((p.item_code, p.store_code))
            if prev is not None and prev > 0 and p.price > prev * limit:
                bad.append(f"{p.item_code}@{p.store_code or 'base'} {prev}->{p.price}")
    if not bad:
        return None
    return GateFailure(
        "price_jump", f"{len(bad)} prices above {factor}x the previous price: {_examples(bad)}"
    )


def gate_item_count_drop(
    conn: psycopg.Connection, parsed: ParsedFile, ratio: float, file_id: int | None = None
) -> GateFailure | None:
    raw = parsed.raw
    if raw.kind not in COUNTED_KINDS:
        return None
    previous = tracking.previous_full_count(
        conn, raw.chain_id, raw.store_code, raw.kind, raw.published_at, exclude_id=file_id
    )
    if not previous:
        return None
    count = record_count(parsed)
    if count < ratio * previous:
        return GateFailure(
            "item_count_drop",
            f"{count} records versus {previous} in the previous {raw.kind} file"
            f" (below {ratio:.0%})",
        )
    return None


def gate_stale_date(parsed: ParsedFile, max_age_hours: float, now: datetime) -> GateFailure | None:
    age = now - parsed.raw.published_at
    if age > timedelta(hours=max_age_hours):
        hours = age.total_seconds() / 3600
        return GateFailure(
            "stale_date",
            f"published {parsed.raw.published_at.isoformat()}, {hours:.1f} h old"
            f" (limit {max_age_hours:g} h)",
        )
    return None


def check(
    conn: psycopg.Connection,
    parsed: ParsedFile,
    thresholds: Thresholds,
    *,
    now: datetime,
    file_id: int | None = None,
) -> list[GateFailure]:
    """Run every gate; an empty list means the file may be loaded."""
    results = [
        gate_zero_price(parsed),
        gate_price_jump(conn, parsed, thresholds.price_jump_factor),
        gate_item_count_drop(conn, parsed, thresholds.item_count_drop_ratio, file_id),
        gate_stale_date(parsed, thresholds.stale_file_max_age_hours, now),
    ]
    return [r for r in results if r is not None]


def warn_gap_report_pressure(
    conn: psycopg.Connection, parsed: ParsedFile, min_mismatches: int, now: datetime
) -> GateWarning | None:
    """``gap_report_pressure`` for the file's store, or None (see the module doc).

    ``min_mismatches`` 0 disables the check. Chain-level files (no store code), files other than
    price files, and a database without ``gap_report_pressure()`` are not checked."""
    raw = parsed.raw
    if min_mismatches <= 0 or raw.kind not in PRICE_KINDS or raw.store_code is None:
        return None
    if not _has_function(conn, "gap_report_pressure"):
        return None
    row = conn.execute(
        "SELECT price_mismatches, reports, reporters, last_report_at"
        " FROM gap_report_pressure(%s, %s) WHERE chain_id = %s AND store_code = %s",
        (now - timedelta(days=GAP_PRESSURE_DAYS), now, raw.chain_id, raw.store_code),
    ).fetchone()
    if row is None or row[0] < min_mismatches:
        return None
    mismatches, reports, reporters, last = row
    return GateWarning(
        "gap_report_pressure",
        f"{mismatches} confirmed price mismatches reported for store {raw.store_code} in the last"
        f" {GAP_PRESSURE_DAYS} days ({reports} reports from {reporters} reporters, latest"
        f" {last.isoformat()}; threshold {min_mismatches})",
        raw.store_code,
    )


def warnings(
    conn: psycopg.Connection, parsed: ParsedFile, thresholds: Thresholds, *, now: datetime
) -> list[GateWarning]:
    """Every soft check. The file is loaded whatever this returns."""
    results = [warn_gap_report_pressure(conn, parsed, thresholds.gap_report_pressure_min, now)]
    return [r for r in results if r is not None]


def record_warnings(
    conn: psycopg.Connection,
    chain_id: str,
    file_id: int | None,
    found: list[GateWarning],
    *,
    now: datetime,
) -> list[GateWarning]:
    """Insert each warning into ``quality_warnings`` unless the same warning was recorded for the
    same store in the last ``WARNING_REPEAT_HOURS`` hours; return the ones inserted (the ones to
    alert on)."""
    new: list[GateWarning] = []
    for w in found:
        seen = conn.execute(
            "SELECT 1 FROM quality_warnings WHERE chain_id = %s"
            " AND store_code IS NOT DISTINCT FROM %s AND warning = %s AND created_at > %s LIMIT 1",
            (chain_id, w.store_code, w.warning, now - timedelta(hours=WARNING_REPEAT_HOURS)),
        ).fetchone()
        if seen:
            continue
        conn.execute(
            "INSERT INTO quality_warnings (file_id, chain_id, store_code, warning, detail,"
            " created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (file_id, chain_id, w.store_code, w.warning, w.detail, now),
        )
        new.append(w)
    return new


def _has_function(conn: psycopg.Connection, name: str) -> bool:
    return bool(conn.execute("SELECT to_regproc(%s) IS NOT NULL", (name,)).fetchone()[0])


def quarantine(
    conn: psycopg.Connection,
    file_id: int,
    failures: list[GateFailure],
    schema_version: str | None = None,
) -> tracking.TrackedFile:
    """Write the quarantine events and set the file quarantined (one transaction)."""
    return tracking.record_quarantine(
        conn, file_id, [(f.gate, f.detail) for f in failures], schema_version
    )
