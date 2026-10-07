"""Dashboard queries against synthetic rows. All writes happen in the db fixture's transaction,
which is rolled back after each test. geog is left out (no PostGIS needed)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from smartcart_dashboard import queries
from smartcart_dashboard.config import PHASE0_CHAINS

pytestmark = pytest.mark.db

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)

SHUFERSAL = "7290027600007"  # D13, fresh
RAMI_LEVY = "7290058140886"  # D13, last load 25 hours ago
VICTORY_1 = "7290696200003"  # D13 chain with two ids; only the first is present
OTHER = "9999999999999"  # not a D13 chain; nothing ever loaded


def _sha(n: int) -> str:
    return f"{n:064x}"


def _file(db, n, chain, kind, status, *, store=None, ago_h=0.0, reason=None, path=None):
    """Insert a file_tracking row whose updated_at is ago_h hours before NOW."""
    ts = NOW - timedelta(hours=ago_h)
    return db.execute(
        "INSERT INTO file_tracking (sha256, chain_id, store_code, kind, path, published_at,"
        " status, reason, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (_sha(n), chain, store, kind, path, ts - timedelta(minutes=5), status, reason, ts, ts),
    ).fetchone()[0]


@pytest.fixture
def world(db: psycopg.Connection) -> dict:
    db.execute("SELECT ensure_price_partitions('2026-09-01', '2026-11-01')")
    for cid, name in (
        (SHUFERSAL, "Shufersal"),
        (RAMI_LEVY, "Rami Levy"),
        (VICTORY_1, "Victory"),
        (OTHER, "Other"),
    ):
        db.execute("INSERT INTO chains (id, name, portal) VALUES (%s, %s, 'other')", (cid, name))

    # Shufersal: three physical stores plus one online store; price files loaded for 001 and 002.
    for code, channel in (("001", "physical"), ("002", "physical"), ("003", "physical"),
                          ("900", "online")):  # fmt: skip
        db.execute(
            "INSERT INTO stores (chain_id, store_code, name, channel) VALUES (%s, %s, %s, %s)",
            (SHUFERSAL, code, f"Store {code}", channel),
        )
    db.execute(
        "INSERT INTO stores (chain_id, store_code, name) VALUES (%s, '001', 'Rami 001')",
        (RAMI_LEVY,),
    )
    items = [
        db.execute(
            "INSERT INTO items (chain_id, item_code, raw_name) VALUES (%s, %s, %s) RETURNING id",
            (SHUFERSAL, f"i{n}", f"item {n}"),
        ).fetchone()[0]
        for n in range(3)
    ]
    rami_item = db.execute(
        "INSERT INTO items (chain_id, item_code, raw_name) VALUES (%s, 'r1', 'rami item')"
        " RETURNING id",
        (RAMI_LEVY,),
    ).fetchone()[0]

    # Price change events: two effective today, one yesterday (Shufersal); one today (Rami Levy).
    for item, ts in (
        (items[0], NOW.replace(hour=3)),
        (items[1], NOW.replace(hour=0, minute=0)),
        (items[2], NOW - timedelta(days=1)),
    ):
        db.execute(
            "INSERT INTO prices (item_id, price, valid_from) VALUES (%s, 9.9, %s)", (item, ts)
        )
    db.execute(
        "INSERT INTO prices (item_id, price, valid_from) VALUES (%s, 5, %s)",
        (rami_item, NOW.replace(hour=1)),
    )

    # Promos: running, open-ended, and already ended (not counted).
    for pid, starts, ends in (
        ("p-run", NOW - timedelta(days=5), NOW + timedelta(days=4)),
        ("p-open", None, None),
        ("p-ended", NOW - timedelta(days=9), NOW - timedelta(days=1)),
    ):
        db.execute(
            "INSERT INTO promos (chain_id, promo_id, description, starts_at, ends_at)"
            " VALUES (%s, %s, 'promo', %s, %s)",
            (SHUFERSAL, pid, starts, ends),
        )

    # Files. Shufersal is fresh: full 2 h ago, delta 1 h ago. Store 003 only reached 'seen'.
    _file(db, 1, SHUFERSAL, "price_full", "loaded", store="001", ago_h=2)
    _file(db, 2, SHUFERSAL, "price", "loaded", store="002", ago_h=1)
    _file(db, 3, SHUFERSAL, "price_full", "seen", store="003", ago_h=0.5)
    _file(db, 4, SHUFERSAL, "stores", "loaded", ago_h=0.1)
    # Rami Levy: full 30 h ago, delta 25 h ago (stale).
    _file(db, 5, RAMI_LEVY, "promo_full", "loaded", store="001", ago_h=30)
    _file(db, 6, RAMI_LEVY, "price", "loaded", store="001", ago_h=25)
    # Quarantined and failed files.
    q1 = _file(db, 7, SHUFERSAL, "price_full", "quarantined", store="003", ago_h=3,
               reason="2 gates failed", path="raw/shufersal/7.gz")  # fmt: skip
    q2 = _file(db, 8, RAMI_LEVY, "price", "quarantined", store="001", ago_h=4, reason="jump")
    failed = _file(db, 9, OTHER, "promo", "failed", ago_h=5, reason="parse error: bad xml")
    for fid, gate, detail in (
        (q1, "zero_price", "3 rows with price 0"),
        (q1, "price_jump", "item i1 went 4x"),
        (q2, "price_jump", None),
    ):
        db.execute(
            "INSERT INTO quarantine_events (file_id, gate, detail) VALUES (%s, %s, %s)",
            (fid, gate, detail),
        )
    return {"q1": q1, "q2": q2, "failed": failed}


def _by_chain(rows):
    return {r["chain_id"]: r for r in rows}


def test_coverage_per_chain(db, world):
    rows = _by_chain(queries.coverage_per_chain(db, NOW))
    shufersal = rows[SHUFERSAL]
    assert shufersal["name"] == "Shufersal"
    assert shufersal["stores_known"] == 3  # the online store is not counted
    assert shufersal["stores_loaded"] == 2  # 001 (price_full loaded) and 002 (price loaded)
    assert shufersal["items"] == 3
    assert shufersal["prices_today"] == 2  # the event from yesterday is not
    assert shufersal["promos_today"] == 2  # running and open-ended, not the ended one
    rami = rows[RAMI_LEVY]
    assert (rami["stores_known"], rami["stores_loaded"], rami["items"]) == (
        1,
        1,
        1,
    )  # price file loaded for 001
    assert (rami["prices_today"], rami["promos_today"]) == (1, 0)
    # A chain with files and no stores or items is listed with zeros, not omitted.
    assert rows[OTHER]["stores_known"] == 0 and rows[OTHER]["items"] == 0
    assert rows[VICTORY_1]["items"] == 0


def test_coverage_counts_move_with_the_day(db, world):
    tomorrow = queries.coverage_per_chain(db, NOW + timedelta(days=5))
    assert _by_chain(tomorrow)[SHUFERSAL]["prices_today"] == 0
    assert (
        _by_chain(tomorrow)[SHUFERSAL]["promos_today"] == 1
    )  # the running promo has ended, only the open-ended one is left


def test_freshness_and_24_hour_stale_flag(db, world):
    rows = _by_chain(queries.freshness_per_chain(db, NOW))

    shufersal = rows[SHUFERSAL]
    assert shufersal["last_full_load_at"] == NOW - timedelta(hours=2)
    assert shufersal["last_delta_load_at"] == NOW - timedelta(hours=1)
    # The stores file loaded 6 minutes ago and the 'seen' file are not loads.
    assert shufersal["last_load_at"] == NOW - timedelta(hours=1)
    assert shufersal["hours_since_load"] == 1.0
    assert shufersal["stale"] is False

    rami = rows[RAMI_LEVY]
    assert rami["last_full_load_at"] == NOW - timedelta(hours=30)
    assert rami["last_delta_load_at"] == NOW - timedelta(hours=25)
    assert rami["hours_since_load"] == 25.0
    assert rami["stale"] is True

    # Never loaded anything (only a failed file): stale with no age.
    assert rows[OTHER]["last_load_at"] is None
    assert rows[OTHER]["hours_since_load"] is None
    assert rows[OTHER]["stale"] is True
    assert rows[VICTORY_1]["stale"] is True


def test_stale_flag_boundary(db, world):
    just_under = _by_chain(queries.freshness_per_chain(db, NOW + timedelta(hours=22, minutes=59)))
    assert just_under[SHUFERSAL]["stale"] is False  # last load 1 h before NOW: 23 h 59 min old
    just_over = _by_chain(queries.freshness_per_chain(db, NOW + timedelta(hours=23, minutes=1)))
    assert just_over[SHUFERSAL]["stale"] is True  # 24 h 1 min


def test_failed_files_join_gates(db, world):
    rows = queries.failed_files(db)
    assert [r["id"] for r in rows] == [world["q1"], world["q2"], world["failed"]]  # newest first

    q1, q2, failed = rows
    assert q1["sha256"] == _sha(7) and isinstance(q1["sha256"], str) and len(q1["sha256"]) == 64
    assert (q1["chain_id"], q1["kind"], q1["status"]) == (SHUFERSAL, "price_full", "quarantined")
    assert q1["gates"] == ["price_jump", "zero_price"]
    assert q1["gate_details"] == ["zero_price: 3 rows with price 0", "price_jump: item i1 went 4x"]
    assert q1["raw_key"] == "raw/shufersal/7.gz"
    assert q1["published_at"] == NOW - timedelta(hours=3, minutes=5)
    assert q1["reason"] == "2 gates failed"

    assert q2["gates"] == ["price_jump"]
    assert q2["gate_details"] == ["price_jump"]  # no detail text
    assert q2["raw_key"] is None

    assert failed["status"] == "failed" and failed["gates"] == []
    assert failed["reason"] == "parse error: bad xml"
    # Loaded and seen files never appear.
    assert {r["status"] for r in rows} == {"quarantined", "failed"}
    assert len(queries.failed_files(db, limit=2)) == 2


def test_file_by_sha256_full_prefix_and_garbage(db, world):
    full = queries.file_by_sha256(db, _sha(7))
    assert [r["id"] for r in full] == [world["q1"]]
    assert full[0]["gates"] == ["price_jump", "zero_price"]
    # Any status can be looked up, by prefix too ("000...01" is shared by 1 and 10..., so use
    # the long common prefix to match everything).
    assert len(queries.file_by_sha256(db, "0" * 60)) == 9
    assert queries.file_by_sha256(db, _sha(1).upper())[0]["status"] == "loaded"
    assert queries.file_by_sha256(db, "") == []
    assert queries.file_by_sha256(db, "abc") == []  # too short
    assert queries.file_by_sha256(db, "zz" * 10) == []
    assert queries.file_by_sha256(db, "00%") == []  # no LIKE wildcards get through


def test_counts_per_chain_and_status(db, world):
    counts = {(r["chain_id"], r["status"]): r["files"] for r in queries.file_counts(db)}
    assert counts[(SHUFERSAL, "loaded")] == 3  # price_full, price, stores
    assert counts[(SHUFERSAL, "seen")] == 1
    assert counts[(SHUFERSAL, "quarantined")] == 1
    assert counts[(RAMI_LEVY, "loaded")] == 2
    assert counts[(RAMI_LEVY, "quarantined")] == 1
    assert counts[(OTHER, "failed")] == 1
    assert (VICTORY_1, "loaded") not in counts


def test_quarantine_counts_per_chain_and_gate(db, world):
    # A second quarantined Shufersal file that also trips zero_price, twice.
    extra = _file(db, 10, SHUFERSAL, "promo_full", "quarantined", ago_h=6)
    for _ in range(2):
        db.execute(
            "INSERT INTO quarantine_events (file_id, gate) VALUES (%s, 'zero_price')", (extra,)
        )
    rows = {(r["chain_id"], r["gate"]): r for r in queries.quarantine_counts(db)}
    assert set(rows) == {
        (SHUFERSAL, "zero_price"),
        (SHUFERSAL, "price_jump"),
        (RAMI_LEVY, "price_jump"),
    }
    assert (
        rows[(SHUFERSAL, "zero_price")]["events"],
        rows[(SHUFERSAL, "zero_price")]["files"],
    ) == (3, 2)
    assert rows[(SHUFERSAL, "price_jump")]["files"] == 1
    assert rows[(RAMI_LEVY, "price_jump")]["events"] == 1


def test_chain_overview_flags(db, world):
    rows = queries.chain_overview(db, NOW)
    by_id = _by_chain(rows)

    assert by_id[SHUFERSAL]["flag"] == "ok"
    assert by_id[SHUFERSAL]["d13"] and by_id[SHUFERSAL]["main"]
    assert by_id[SHUFERSAL]["hours_since_load"] == 1.0
    assert by_id[RAMI_LEVY]["flag"] == "stale"
    assert by_id[OTHER]["flag"] == "stale" and not by_id[OTHER]["d13"]
    # Victory has two ids in D13; one present means the chain is not missing.
    assert by_id[VICTORY_1]["name"] == "Victory"

    missing = {r["name"] for r in rows if r["flag"] == "missing"}
    expected_missing = {c.name for c in PHASE0_CHAINS} - {"Shufersal", "Rami Levy", "Victory"}
    assert missing == expected_missing
    gone = next(r for r in rows if r["flag"] == "missing" and r["name"] == "Machsanei Hashuk")
    assert gone["chain_id"] == "7290661400001, 7290633800006"
    assert gone["d13"] is True and gone["main"] is False and gone["items"] == 0


def test_chain_overview_empty_database_flags_all_ten(db):
    rows = queries.chain_overview(db, NOW)
    assert len(rows) == 10
    assert {r["flag"] for r in rows} == {"missing"}
    assert sum(r["main"] for r in rows) == 6


def test_naive_now_is_rejected(db):
    with pytest.raises(ValueError):
        queries.freshness_per_chain(db, datetime(2026, 10, 6, 12, 0))


def test_queries_only_select(db, world):
    """Run every query inside a READ ONLY transaction: any write would raise."""
    db.execute("SET LOCAL transaction_read_only = on")
    assert db.execute("SHOW transaction_read_only").fetchone()[0] == "on"

    queries.coverage_per_chain(db, NOW)
    queries.freshness_per_chain(db, NOW)
    queries.failed_files(db)
    queries.file_by_sha256(db, _sha(7))
    queries.file_counts(db)
    queries.quarantine_counts(db)
    queries.chain_overview(db, NOW)
    queries.reported_gaps(db, NOW)
    queries.recent_gap_reports(db, NOW)

    # Sanity check that the guard is real: a write in the same transaction is refused.
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        db.execute("DELETE FROM file_tracking")


def _store_id(db, chain, code):
    return db.execute(
        "SELECT id FROM stores WHERE chain_id = %s AND store_code = %s", (chain, code)
    ).fetchone()[0]


def _gap(db, store_id, shown, actual, ago_h, note=None, item_id=None):
    db.execute(
        "INSERT INTO gap_reports (store_id, item_id, shown_price, actual_price, note, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s)",
        (store_id, item_id, shown, actual, note, NOW - timedelta(hours=ago_h)),
    )


def test_reported_gaps_per_store(db, world):
    s1, s2 = _store_id(db, SHUFERSAL, "001"), _store_id(db, SHUFERSAL, "002")
    rami = _store_id(db, RAMI_LEVY, "001")
    item = db.execute("SELECT id FROM items WHERE item_code = 'i0'").fetchone()[0]
    _gap(db, s1, 5, 6, 1, item_id=item)
    _gap(db, s1, 5, 7, 2)
    _gap(db, s1, 5, 5, 3)  # same price: a report, not a mismatch
    _gap(db, s1, None, None, 4, note="#reason=promo_wrong")
    _gap(db, s2, 4, None, 5, note="נגמר #reason=wrong_product")
    _gap(db, rami, 1, 2, 24 * 8)  # older than 7 days
    db.execute(
        "INSERT INTO quality_warnings (chain_id, store_code, warning, detail, created_at)"
        " VALUES (%s, '001', 'gap_report_pressure', 'x', %s)",
        (SHUFERSAL, NOW - timedelta(hours=1)),
    )
    rows = queries.reported_gaps(db, NOW)
    assert [(r["chain_id"], r["store_code"]) for r in rows] == [
        (SHUFERSAL, "001"),
        (SHUFERSAL, "002"),
    ]
    first = rows[0]
    assert first["chain_name"] == "Shufersal" and first["store_name"] == "Store 001"
    assert (first["reports"], first["price_mismatches"], first["promo_wrong"]) == (4, 2, 1)
    assert first["last_report_at"] == NOW - timedelta(hours=1)
    assert first["last_warning_at"] == NOW - timedelta(hours=1)
    assert (rows[1]["wrong_product"], rows[1]["last_warning_at"]) == (1, None)

    recent = queries.recent_gap_reports(db, NOW)
    assert len(recent) == 5 and recent[0]["product"] == "item 0"
    assert "user_id" not in recent[0]
    assert [r["store_code"] for r in recent] == ["001", "001", "001", "001", "002"]
    assert queries.recent_gap_reports(db, NOW, limit=2)[1]["actual_price"] == 7
