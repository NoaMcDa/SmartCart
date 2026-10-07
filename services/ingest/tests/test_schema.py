"""Schema v1 tests that need no extension (issue #27)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pytest
from psycopg import errors

pytestmark = pytest.mark.db


def _columns(db: psycopg.Connection, table: str) -> dict[str, str]:
    rows = db.execute(
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod) FROM pg_attribute a"
        " WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped",
        (table,),
    ).fetchall()
    return dict(rows)


def _add_price(db, item_id, store_id, price, valid_from) -> None:
    db.execute(
        "INSERT INTO prices (item_id, store_id, price, unit_price, uom, valid_from)"
        " VALUES (%s, %s, %s, %s, '100ml', %s)",
        (item_id, store_id, price, Decimal(price) / 10, valid_from),
    )


def _ts(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


# --- tables and columns ------------------------------------------------------------------------


def test_core_tables_have_the_planned_columns(db) -> None:
    expected = {
        "chains": {"id", "name", "portal", "club_names"},
        "stores": {"id", "chain_id", "store_code", "name", "address", "city", "channel"},
        "items": {
            "id", "chain_id", "item_code", "barcode", "raw_name", "manufacturer",
            "quantity", "unit", "is_weighed", "raw_attributes",
        },
        "prices": {"item_id", "store_id", "price", "unit_price", "uom", "valid_from"},
        "promo_items": {"promo_id", "item_id"},
        "file_tracking": {
            "id", "sha256", "chain_id", "store_code", "kind", "published_at",
            "schema_version", "status", "reason", "created_at", "updated_at",
        },
        "quarantine_events": {"id", "file_id", "gate", "detail", "created_at"},
    }  # fmt: skip
    for table, cols in expected.items():
        assert cols <= set(_columns(db, table)), table


def test_store_channel_defaults_to_physical_and_is_checked(db, seed) -> None:
    channel = db.execute("SELECT channel FROM stores WHERE id = %s", (seed.store_a,)).fetchone()[0]
    assert channel == "physical"
    with pytest.raises(errors.CheckViolation), db.transaction():
        db.execute("UPDATE stores SET channel = 'kiosk' WHERE id = %s", (seed.store_a,))


def test_store_code_is_unique_per_chain(db, seed) -> None:
    with pytest.raises(errors.UniqueViolation), db.transaction():
        db.execute(
            "INSERT INTO stores (chain_id, store_code, name) VALUES ('test-chain', '001', 'dup')"
        )


def test_item_code_is_unique_per_chain(db, seed) -> None:
    with pytest.raises(errors.UniqueViolation), db.transaction():
        db.execute(
            "INSERT INTO items (chain_id, item_code, raw_name)"
            " VALUES ('test-chain', '7290000000001', 'dup')"
        )


def test_updated_at_is_maintained(db, seed) -> None:
    db.execute("UPDATE items SET updated_at = '2000-01-01' WHERE id = %s", (seed.item_id,))
    db.execute("UPDATE items SET manufacturer = 'Tnuva' WHERE id = %s", (seed.item_id,))
    year = db.execute(
        "SELECT extract(year FROM updated_at) FROM items WHERE id = %s", (seed.item_id,)
    ).fetchone()[0]
    assert year > 2000


# --- prices: partitions ------------------------------------------------------------------------


def test_prices_is_range_partitioned_on_valid_from(db) -> None:
    row = db.execute(
        "SELECT pt.partstrat, a.attname FROM pg_partitioned_table pt"
        " JOIN pg_attribute a ON a.attrelid = pt.partrelid AND a.attnum = pt.partattrs[0]"
        " WHERE pt.partrelid = 'prices'::regclass"
    ).fetchone()
    assert row == ("r", "valid_from")


def test_migration_created_partitions_around_now(db) -> None:
    current = db.execute(
        "SELECT 'prices_' || to_char(now() AT TIME ZONE 'UTC', 'YYYY_MM')"
    ).fetchone()[0]
    assert db.execute("SELECT to_regclass(%s)", (current,)).fetchone()[0] is not None


def test_ensure_price_partition_is_idempotent(db) -> None:
    first = db.execute("SELECT ensure_price_partition('2031-02-17')").fetchone()[0]
    second = db.execute("SELECT ensure_price_partition('2031-02-01')").fetchone()[0]
    assert first == second == "prices_2031_02"
    names = db.execute("SELECT ensure_price_partitions('2031-01-31', '2031-04-01')").fetchall()
    assert [n[0] for n in names] == ["prices_2031_01", "prices_2031_02", "prices_2031_03",
                                     "prices_2031_04"]  # fmt: skip


def test_two_months_land_in_two_partitions(db, seed) -> None:
    db.execute("SELECT ensure_price_partitions('2030-09-01', '2030-10-01')")
    _add_price(db, seed.item_id, None, "6.90", _ts(2030, 9, 15))
    _add_price(db, seed.item_id, None, "7.20", _ts(2030, 10, 15))
    rows = db.execute(
        "SELECT tableoid::regclass::text, price FROM prices WHERE item_id = %s ORDER BY valid_from",
        (seed.item_id,),
    ).fetchall()
    assert rows == [("prices_2030_09", Decimal("6.90")), ("prices_2030_10", Decimal("7.20"))]


def test_partition_months_are_utc(db, seed) -> None:
    db.execute("SELECT ensure_price_partitions('2030-09-01', '2030-10-01')")
    # 01:00 Israel time on Oct 1 is still Sep 30 in UTC.
    db.execute(
        "INSERT INTO prices (item_id, price, valid_from)"
        " VALUES (%s, 1, '2030-10-01 01:00:00+03'), (%s, 2, '2030-10-01 00:00:00+00')",
        (seed.item_id, seed.item_id),
    )
    rows = db.execute(
        "SELECT price, tableoid::regclass::text FROM prices WHERE item_id = %s ORDER BY price",
        (seed.item_id,),
    ).fetchall()
    assert rows == [(Decimal(1), "prices_2030_09"), (Decimal(2), "prices_2030_10")]


def test_insert_without_partition_fails_loudly(db, seed) -> None:
    with pytest.raises(errors.CheckViolation), db.transaction():
        _add_price(db, seed.item_id, None, "1.00", _ts(2099, 1, 1))


def test_duplicate_price_event_is_rejected_for_base_and_store(db, seed) -> None:
    db.execute("SELECT ensure_price_partition('2030-09-01')")
    for store in (None, seed.store_a):
        _add_price(db, seed.item_id, store, "6.90", _ts(2030, 9, 15))
        with pytest.raises(errors.UniqueViolation), db.transaction():
            _add_price(db, seed.item_id, store, "6.90", _ts(2030, 9, 15))


def test_negative_price_is_rejected(db, seed) -> None:
    db.execute("SELECT ensure_price_partition('2030-09-01')")
    with pytest.raises(errors.CheckViolation), db.transaction():
        _add_price(db, seed.item_id, None, "-1", _ts(2030, 9, 15))


# --- prices: base price plus store exceptions ---------------------------------------------------


def _current(db, item_id, store_id, at=None):
    if at is None:
        return db.execute(
            "SELECT price, is_store_price FROM current_price(%s, %s)", (item_id, store_id)
        ).fetchone()
    return db.execute(
        "SELECT price, is_store_price FROM current_price(%s, %s, %s)", (item_id, store_id, at)
    ).fetchone()


def test_store_exception_overrides_chain_base_price(db, seed) -> None:
    db.execute("SELECT ensure_price_partitions('2030-08-01', '2030-10-01')")
    _add_price(db, seed.item_id, None, "6.90", _ts(2030, 8, 1))  # chain base
    _add_price(db, seed.item_id, seed.store_a, "5.90", _ts(2030, 9, 1))  # store A exception

    at = _ts(2030, 9, 20)
    assert _current(db, seed.item_id, seed.store_a, at) == (Decimal("5.90"), True)
    # Store B has no exception and falls back to the chain base price.
    assert _current(db, seed.item_id, seed.store_b, at) == (Decimal("6.90"), False)
    # Before the exception started, store A also had the base price.
    assert _current(db, seed.item_id, seed.store_a, _ts(2030, 8, 15)) == (Decimal("6.90"), False)


def test_latest_event_wins_within_each_level(db, seed) -> None:
    db.execute("SELECT ensure_price_partitions('2030-08-01', '2030-10-01')")
    _add_price(db, seed.item_id, None, "6.90", _ts(2030, 8, 1))
    _add_price(db, seed.item_id, None, "7.40", _ts(2030, 10, 1))  # base price change
    _add_price(db, seed.item_id, seed.store_a, "5.90", _ts(2030, 9, 1))
    _add_price(db, seed.item_id, seed.store_a, "6.10", _ts(2030, 10, 2))  # exception change

    at = _ts(2030, 10, 20)
    assert _current(db, seed.item_id, seed.store_b, at) == (Decimal("7.40"), False)
    assert _current(db, seed.item_id, seed.store_a, at) == (Decimal("6.10"), True)


def test_current_price_is_empty_without_any_price(db, seed) -> None:
    assert _current(db, seed.item_id, seed.store_a) is None


def test_latest_prices_view_returns_one_row_per_level(db, seed) -> None:
    # The view is "as of now", so this test uses past dates.
    db.execute("SELECT ensure_price_partitions('2025-08-01', '2025-10-01')")
    _add_price(db, seed.item_id, None, "6.90", _ts(2025, 8, 1))
    _add_price(db, seed.item_id, None, "7.40", _ts(2025, 10, 1))
    _add_price(db, seed.item_id, seed.store_a, "5.90", _ts(2025, 9, 1))
    rows = db.execute(
        "SELECT store_id, price FROM latest_prices WHERE item_id = %s"
        " ORDER BY store_id NULLS FIRST",
        (seed.item_id,),
    ).fetchall()
    assert rows == [(None, Decimal("7.40")), (seed.store_a, Decimal("5.90"))]


def test_latest_price_lookup_can_use_an_index(db, seed) -> None:
    db.execute("SET LOCAL enable_seqscan = off")
    plan = "\n".join(
        r[0]
        for r in db.execute(
            "EXPLAIN SELECT price FROM prices WHERE item_id = 1 AND store_id = 2"
            " ORDER BY valid_from DESC LIMIT 1"
        ).fetchall()
    )
    assert "Index" in plan, plan


# --- promos ------------------------------------------------------------------------------------


def test_promos_have_structured_columns(db) -> None:
    cols = _columns(db, "promos")
    assert {
        "chain_id": "text",
        "store_id": "bigint",
        "promo_id": "text",
        "description": "text",
        "starts_at": "timestamp with time zone",
        "ends_at": "timestamp with time zone",
        "hours": "text",
        "club_only": "boolean",
        "club_name": "text",
        "min_qty": "numeric",
        "max_qty": "numeric",
        "reward_type": "text",
        "reward_value": "numeric",
        "raw": "jsonb",
    }.items() <= cols.items()


def test_structured_promo_round_trip(db, seed) -> None:
    promo = db.execute(
        "INSERT INTO promos (chain_id, store_id, promo_id, description, starts_at, ends_at,"
        " hours, club_only, club_name, min_qty, max_qty, reward_type, reward_value, raw)"
        " VALUES ('test-chain', %s, 'P1', '3 ב-20', '2030-09-01', '2030-09-30', '08:00-14:00',"
        " true, 'Club', 3, 6, 'bundle', 20, '{\"RewardType\": \"1\"}') RETURNING id",
        (seed.store_a,),
    ).fetchone()[0]
    db.execute("INSERT INTO promo_items (promo_id, item_id) VALUES (%s, %s)", (promo, seed.item_id))
    row = db.execute(
        "SELECT p.min_qty, p.max_qty, p.reward_type, p.club_only, p.raw->>'RewardType'"
        " FROM promos p JOIN promo_items pi ON pi.promo_id = p.id WHERE pi.item_id = %s",
        (seed.item_id,),
    ).fetchone()
    assert row == (Decimal(3), Decimal(6), "bundle", True, "1")


def test_promo_reward_type_is_checked(db, seed) -> None:
    with pytest.raises(errors.CheckViolation), db.transaction():
        db.execute(
            "INSERT INTO promos (chain_id, promo_id, description, reward_type)"
            " VALUES ('test-chain', 'P2', 'x', 'free_lunch')"
        )


def test_chain_wide_promo_id_is_unique(db, seed) -> None:
    sql = "INSERT INTO promos (chain_id, promo_id, description) VALUES ('test-chain', 'P3', 'x')"
    db.execute(sql)
    with pytest.raises(errors.UniqueViolation), db.transaction():
        db.execute(sql)
    # The same promo id at a specific store is a different row.
    db.execute(
        "INSERT INTO promos (chain_id, store_id, promo_id, description)"
        " VALUES ('test-chain', %s, 'P3', 'x')",
        (seed.store_a,),
    )


# --- file tracking -----------------------------------------------------------------------------


def _track(db, sha: str, **cols) -> int:
    cols = {"chain_id": "test-chain", "kind": "price_full", **cols}
    names = ", ".join(["sha256", *cols])
    marks = ", ".join(["%s"] * (len(cols) + 1))
    return db.execute(
        f"INSERT INTO file_tracking ({names}) VALUES ({marks}) RETURNING id",
        (sha, *cols.values()),
    ).fetchone()[0]


def test_file_tracking_sha256_is_unique(db) -> None:
    _track(db, "a" * 64)
    with pytest.raises(errors.UniqueViolation), db.transaction():
        _track(db, "a" * 64, kind="promo_full")


def test_file_tracking_validates_hash_kind_status_and_schema(db) -> None:
    for bad in ({"kind": "pricefull"}, {"status": "done"}, {"schema_version": "v3"}):
        with pytest.raises(errors.CheckViolation), db.transaction():
            _track(db, "b" * 64, **bad)
    with pytest.raises(errors.CheckViolation), db.transaction():
        _track(db, "Z" * 64)
    row_id = _track(db, "c" * 64)
    row = db.execute(
        "SELECT status, schema_version FROM file_tracking WHERE id = %s", (row_id,)
    ).fetchone()
    assert row == ("seen", "unknown")


def test_quarantine_events_reference_files(db) -> None:
    file_id = _track(db, "d" * 64, status="quarantined", reason="zero price")
    db.execute(
        "INSERT INTO quarantine_events (file_id, gate, detail) VALUES (%s, 'zero_price', '3 rows')",
        (file_id,),
    )
    with pytest.raises(errors.ForeignKeyViolation), db.transaction():
        db.execute("INSERT INTO quarantine_events (file_id, gate) VALUES (-1, 'zero_price')")
