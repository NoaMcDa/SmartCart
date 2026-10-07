"""Read-only queries behind the dashboard. Every function takes an open psycopg connection and
returns a list of dicts, so none of this needs Streamlit and all of it is testable against a
test database. Nothing here writes: every statement is a SELECT.

Time handling: ``now`` is a parameter (default: the current time) so the 24-hour stale flag and
the "today" counts are deterministic in tests. "Today" is the UTC calendar day of ``now``.

What a "load" is: a ``file_tracking`` row with ``status = 'loaded'`` and kind ``price_full``,
``price``, ``promo_full`` or ``promo``. The load time is the row's ``updated_at``, the moment it
reached ``loaded``. Stores files are left out on purpose: a chain whose stores file loads while
every price file fails must still show as stale.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import PHASE0_CHAINS, STALE_AFTER_HOURS

Row = dict[str, Any]

FULL_KINDS = ("price_full", "promo_full")
DELTA_KINDS = ("price", "promo")
LOAD_KINDS = FULL_KINDS + DELTA_KINDS

_HEX_PREFIX = re.compile(r"^[0-9a-f]{4,64}$")


def _fetch(conn: psycopg.Connection, sql: str, params: dict[str, Any] | None = None) -> list[Row]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params or {})
        return list(cur.fetchall())


def _utc(now: datetime | None) -> datetime:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(UTC)


def _day_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


# --------------------------------------------------------------------------------------------
# Coverage
# --------------------------------------------------------------------------------------------

_COVERAGE_SQL = """
WITH chain_ids AS (
  SELECT id AS chain_id FROM chains
  UNION
  SELECT chain_id FROM file_tracking
),
stores_known AS (
  SELECT chain_id, count(*) AS n FROM stores WHERE channel = 'physical' GROUP BY chain_id
),
stores_loaded AS (
  SELECT s.chain_id, count(*) AS n
  FROM stores AS s
  WHERE s.channel = 'physical'
    AND EXISTS (
      SELECT 1 FROM file_tracking AS f
      WHERE f.chain_id = s.chain_id AND f.store_code = s.store_code
        AND f.status = 'loaded' AND f.kind IN ('price_full', 'price')
    )
  GROUP BY s.chain_id
),
items_n AS (
  SELECT chain_id, count(*) AS n FROM items GROUP BY chain_id
),
prices_today AS (
  SELECT i.chain_id, count(*) AS n
  FROM prices AS p JOIN items AS i ON i.id = p.item_id
  WHERE p.valid_from >= %(day_start)s AND p.valid_from < %(day_end)s
  GROUP BY i.chain_id
),
promos_today AS (
  SELECT chain_id, count(*) AS n
  FROM promos
  WHERE (starts_at IS NULL OR starts_at < %(day_end)s)
    AND (ends_at IS NULL OR ends_at >= %(day_start)s)
  GROUP BY chain_id
)
SELECT c.chain_id,
       ch.name,
       coalesce(sk.n, 0)  AS stores_known,
       coalesce(sl.n, 0)  AS stores_loaded,
       coalesce(i.n, 0)   AS items,
       coalesce(pt.n, 0)  AS prices_today,
       coalesce(pr.n, 0)  AS promos_today
FROM chain_ids AS c
LEFT JOIN chains AS ch ON ch.id = c.chain_id
LEFT JOIN stores_known AS sk ON sk.chain_id = c.chain_id
LEFT JOIN stores_loaded AS sl ON sl.chain_id = c.chain_id
LEFT JOIN items_n AS i ON i.chain_id = c.chain_id
LEFT JOIN prices_today AS pt ON pt.chain_id = c.chain_id
LEFT JOIN promos_today AS pr ON pr.chain_id = c.chain_id
ORDER BY c.chain_id
"""


def coverage_per_chain(conn: psycopg.Connection, now: datetime | None = None) -> list[Row]:
    """Per chain: physical stores known, stores with a loaded price file, item count, price
    change events effective today, and promos in effect at some point today."""
    day_start, day_end = _day_bounds(_utc(now))
    return _fetch(conn, _COVERAGE_SQL, {"day_start": day_start, "day_end": day_end})


# --------------------------------------------------------------------------------------------
# Freshness
# --------------------------------------------------------------------------------------------

_FRESHNESS_SQL = """
WITH chain_ids AS (
  SELECT id AS chain_id FROM chains
  UNION
  SELECT chain_id FROM file_tracking
)
SELECT c.chain_id,
       max(f.updated_at) FILTER (
         WHERE f.status = 'loaded' AND f.kind = ANY(%(full)s)) AS last_full_load_at,
       max(f.updated_at) FILTER (
         WHERE f.status = 'loaded' AND f.kind = ANY(%(delta)s)) AS last_delta_load_at,
       max(f.updated_at) FILTER (
         WHERE f.status = 'loaded' AND f.kind = ANY(%(all)s)) AS last_load_at,
       max(f.published_at) FILTER (
         WHERE f.status = 'loaded' AND f.kind = ANY(%(all)s)) AS last_published_at
FROM chain_ids AS c
LEFT JOIN file_tracking AS f ON f.chain_id = c.chain_id
GROUP BY c.chain_id
ORDER BY c.chain_id
"""


def freshness_per_chain(conn: psycopg.Connection, now: datetime | None = None) -> list[Row]:
    """Per chain: last successful full load, last successful delta, hours since the latest of
    the two, and ``stale`` (true when there is no load at all or the last one is more than
    24 hours old)."""
    now = _utc(now)
    rows = _fetch(
        conn,
        _FRESHNESS_SQL,
        {"full": list(FULL_KINDS), "delta": list(DELTA_KINDS), "all": list(LOAD_KINDS)},
    )
    for row in rows:
        last = row["last_load_at"]
        if last is None:
            row["hours_since_load"] = None
            row["stale"] = True
        else:
            hours = (now - last).total_seconds() / 3600
            row["hours_since_load"] = round(hours, 1)
            row["stale"] = hours > STALE_AFTER_HOURS
    return rows


# --------------------------------------------------------------------------------------------
# Failed and quarantined files
# --------------------------------------------------------------------------------------------

_FILES_SQL = """
SELECT f.id,
       f.chain_id,
       f.store_code,
       f.kind,
       f.published_at,
       f.sha256::text AS sha256,
       f.status,
       f.reason,
       f.path AS raw_key,
       f.updated_at,
       coalesce(array_agg(DISTINCT q.gate) FILTER (WHERE q.gate IS NOT NULL), '{}') AS gates,
       coalesce(
         array_agg(q.gate || coalesce(': ' || q.detail, '') ORDER BY q.id)
           FILTER (WHERE q.gate IS NOT NULL),
         '{}') AS gate_details
FROM file_tracking AS f
LEFT JOIN quarantine_events AS q ON q.file_id = f.id
WHERE @@WHERE@@
GROUP BY f.id
ORDER BY f.updated_at DESC, f.id DESC
LIMIT %(limit)s
"""


def failed_files(conn: psycopg.Connection, limit: int = 200) -> list[Row]:
    """Files with status ``failed`` or ``quarantined``, newest first, with the failing gate(s)
    joined from ``quarantine_events`` (``gates`` is a sorted list of distinct gate names,
    ``gate_details`` the matching "gate: detail" strings) and ``raw_key``, the raw file's
    location in object storage when the loader recorded one."""
    sql = _FILES_SQL.replace("@@WHERE@@", "f.status IN ('failed', 'quarantined')")
    return _fetch(conn, sql, {"limit": limit})


def file_by_sha256(conn: psycopg.Connection, sha256: str, limit: int = 20) -> list[Row]:
    """Look up files (any status) by full sha256 or a hex prefix of at least 4 characters. Same
    columns as ``failed_files``. Anything that is not lowercase hex returns an empty list."""
    needle = sha256.strip().lower()
    if not _HEX_PREFIX.match(needle):
        return []
    sql = _FILES_SQL.replace("@@WHERE@@", "f.sha256 LIKE %(prefix)s")
    return _fetch(conn, sql, {"prefix": needle + "%", "limit": limit})


# --------------------------------------------------------------------------------------------
# Counts
# --------------------------------------------------------------------------------------------


def file_counts(conn: psycopg.Connection) -> list[Row]:
    """Files per chain and status, from file_tracking."""
    return _fetch(
        conn,
        "SELECT chain_id, status, count(*) AS files FROM file_tracking"
        " GROUP BY chain_id, status ORDER BY chain_id, status",
    )


def quarantine_counts(conn: psycopg.Connection) -> list[Row]:
    """Per chain and gate: quarantine events and the distinct files they belong to."""
    return _fetch(
        conn,
        "SELECT f.chain_id, q.gate, count(*) AS events, count(DISTINCT f.id) AS files"
        " FROM quarantine_events AS q JOIN file_tracking AS f ON f.id = q.file_id"
        " GROUP BY f.chain_id, q.gate ORDER BY f.chain_id, q.gate",
    )


# --------------------------------------------------------------------------------------------
# Reported gaps (issue #16)
# --------------------------------------------------------------------------------------------

GAP_DAYS = 7


def reported_gaps(
    conn: psycopg.Connection, now: datetime | None = None, days: int = GAP_DAYS
) -> list[Row]:
    """Report-a-gap per store over the last ``days`` days, from ``gap_report_pressure()``
    (migration 20261009100000_mvp_followups.sql), with the chain name and the latest soft
    ``gap_report_pressure`` warning ingestion recorded for the store. Stores with the most
    confirmed price mismatches first. Empty when the function does not exist yet."""
    now = _utc(now)
    if not conn.execute("SELECT to_regproc('gap_report_pressure') IS NOT NULL").fetchone()[0]:
        return []
    return _fetch(
        conn,
        "SELECT g.chain_id, c.name AS chain_name, g.store_code, g.store_name, g.reports,"
        "  g.price_mismatches, g.wrong_product, g.promo_wrong, g.reporters, g.last_report_at,"
        "  w.created_at AS last_warning_at"
        " FROM gap_report_pressure(%(since)s, %(until)s) AS g"
        " LEFT JOIN chains AS c ON c.id = g.chain_id"
        " LEFT JOIN LATERAL ("
        "   SELECT q.created_at FROM quality_warnings AS q"
        "   WHERE q.chain_id = g.chain_id AND q.store_code = g.store_code"
        "     AND q.warning = 'gap_report_pressure'"
        "   ORDER BY q.created_at DESC LIMIT 1) AS w ON true"
        " ORDER BY g.price_mismatches DESC, g.reports DESC, g.chain_id, g.store_code",
        {"since": now - timedelta(days=days), "until": now},
    )


def recent_gap_reports(
    conn: psycopg.Connection, now: datetime | None = None, days: int = GAP_DAYS, limit: int = 100
) -> list[Row]:
    """The newest gap reports of the last ``days`` days, without the reporter (no user id, no
    location is shown)."""
    now = _utc(now)
    return _fetch(
        conn,
        "SELECT g.created_at, s.chain_id, s.store_code, s.name AS store_name,"
        "  coalesce(i.raw_name, cp.display_name_he) AS product, g.shown_price, g.actual_price,"
        "  g.note"
        " FROM gap_reports AS g"
        " JOIN stores AS s ON s.id = g.store_id"
        " LEFT JOIN items AS i ON i.id = g.item_id"
        " LEFT JOIN canonical_products AS cp ON cp.id = g.canonical_id"
        " WHERE g.created_at >= %(since)s AND g.created_at < %(until)s"
        " ORDER BY g.created_at DESC, g.id DESC LIMIT %(limit)s",
        {"since": now - timedelta(days=days), "until": now, "limit": limit},
    )


# --------------------------------------------------------------------------------------------
# The chain table
# --------------------------------------------------------------------------------------------


def chain_overview(conn: psycopg.Connection, now: datetime | None = None) -> list[Row]:
    """One row per known chain id (coverage and freshness merged), plus one row for each D13
    chain that appears nowhere (not in ``chains`` and not in ``file_tracking``).

    ``flag`` is ``missing`` (D13 chain with no data at all), ``stale`` (no load in 24 hours) or
    ``ok``. ``d13`` marks the ten phase 0 chains and ``main`` the six with hourly deltas.
    """
    now = _utc(now)
    coverage = {r["chain_id"]: r for r in coverage_per_chain(conn, now)}
    freshness = {r["chain_id"]: r for r in freshness_per_chain(conn, now)}
    by_id = {cid: (c.name, c.main) for c in PHASE0_CHAINS for cid in c.chain_ids}

    rows: list[Row] = []
    for chain_id, cov in coverage.items():
        fresh = freshness[chain_id]
        d13_name, main = by_id.get(chain_id, (None, False))
        rows.append(
            {
                "chain_id": chain_id,
                "name": cov["name"] or d13_name,
                "d13": chain_id in by_id,
                "main": main,
                "stores_known": cov["stores_known"],
                "stores_loaded": cov["stores_loaded"],
                "items": cov["items"],
                "prices_today": cov["prices_today"],
                "promos_today": cov["promos_today"],
                "last_full_load_at": fresh["last_full_load_at"],
                "last_delta_load_at": fresh["last_delta_load_at"],
                "hours_since_load": fresh["hours_since_load"],
                "flag": "stale" if fresh["stale"] else "ok",
            }
        )

    for chain in PHASE0_CHAINS:
        if any(cid in coverage for cid in chain.chain_ids):
            continue
        rows.append(
            {
                "chain_id": ", ".join(chain.chain_ids),
                "name": chain.name,
                "d13": True,
                "main": chain.main,
                "stores_known": 0,
                "stores_loaded": 0,
                "items": 0,
                "prices_today": 0,
                "promos_today": 0,
                "last_full_load_at": None,
                "last_delta_load_at": None,
                "hours_since_load": None,
                "flag": "missing",
            }
        )
    return rows
