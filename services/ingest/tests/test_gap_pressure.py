"""Report-a-gap as a quality signal (issue #16): the gap_report_pressure() summary and the soft
"gap-report pressure" warning, which never quarantines a file."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from smartcart_ingest import quality
from smartcart_ingest.settings import Settings, Thresholds
from tests.fakes import CHAIN, NOW, encode, item, make_harness, parsed_file, price, statuses

pytestmark = pytest.mark.db

D = Decimal
HOUR = timedelta(hours=1)


def _store(db, code: str, chain: str = CHAIN) -> int:
    db.execute(
        "INSERT INTO chains (id, name, portal) VALUES (%s, %s, 'other') ON CONFLICT DO NOTHING",
        (chain, chain),
    )
    return db.execute(
        "INSERT INTO stores (chain_id, store_code, name) VALUES (%s, %s, %s)"
        " ON CONFLICT (chain_id, store_code) DO UPDATE SET name = EXCLUDED.name RETURNING id",
        (chain, code, f"Store {code}"),
    ).fetchone()[0]


def _user(db) -> uuid.UUID:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    return uid


def _gap(db, store_id, shown, actual, *, ago=HOUR, user=None, item_id=None, note=None) -> None:
    db.execute(
        "INSERT INTO gap_reports (store_id, item_id, shown_price, actual_price, note, user_id,"
        " created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (store_id, item_id, None if shown is None else D(shown),
         None if actual is None else D(actual), note, user, NOW - ago),
    )  # fmt: skip


def _item(db, code: str) -> int:
    return db.execute(
        "INSERT INTO items (chain_id, item_code, raw_name) VALUES (%s, %s, %s) RETURNING id",
        (CHAIN, code, f"Item {code}"),
    ).fetchone()[0]


def _pressure(db, since=NOW - timedelta(days=7), until=NOW) -> dict[str, dict]:
    with db.cursor() as cur:
        cur.execute("SELECT * FROM gap_report_pressure(%s, %s)", (since, until))
        names = [c.name for c in cur.description]
        return {r[2]: dict(zip(names, r, strict=True)) for r in cur.fetchall()}


# --- the summary (SQL) -------------------------------------------------------------------------


def test_gap_report_pressure_counts_confirmed_mismatches_per_store(db) -> None:
    s1, s2 = _store(db, "1"), _store(db, "2")
    a, b = _item(db, "A"), _item(db, "B")
    alice, bob = _user(db), _user(db)
    _gap(db, s1, "5.90", "6.40", user=alice, item_id=a)  # a confirmed mismatch
    _gap(db, s1, "5.90", "6.50", user=alice, item_id=a, ago=2 * HOUR)  # alice again, same item
    _gap(db, s1, "5.90", "6.40", user=bob, item_id=a)  # another reporter: counts
    _gap(db, s1, "3.00", "3.50", user=alice, item_id=b)  # alice, another item: counts
    _gap(db, s1, "4.00", "4.50")  # anonymous: each one counts
    _gap(db, s1, "4.00", "4.50")
    _gap(db, s1, "4.00", "4.00")  # same price: not a mismatch
    _gap(db, s1, "4.00", "4.004")  # under one agora: not a mismatch
    _gap(db, s1, "4.00", None, note="נגמר #reason=wrong_product #shown_at=2026-10-05")
    _gap(db, s1, None, None, note="#reason=promo_wrong")
    _gap(db, s1, "1.00", "9.00", ago=timedelta(days=8))  # outside the window
    _gap(db, s2, "2.00", "2.50", user=bob)
    got = _pressure(db)
    assert set(got) == {"1", "2"}
    one = got["1"]
    assert (one["chain_id"], one["store_id"], one["store_name"]) == (CHAIN, s1, "Store 1")
    assert one["reports"] == 10
    assert one["price_mismatches"] == 5  # alice/A, bob/A, alice/B, two anonymous
    assert (one["wrong_product"], one["promo_wrong"]) == (1, 1)
    assert one["reporters"] == 2 + 6  # alice, bob, and six anonymous reports
    assert one["last_report_at"] == NOW - HOUR
    assert (got["2"]["reports"], got["2"]["price_mismatches"], got["2"]["reporters"]) == (1, 1, 1)
    # The window is [since, until).
    assert _pressure(db, NOW - timedelta(days=9), NOW)["1"]["reports"] == 11
    assert _pressure(db, NOW - HOUR + timedelta(seconds=1), NOW) == {}
    assert _pressure(db, NOW - 3 * HOUR, NOW - HOUR)["1"]["reports"] == 1  # alice's 2-hour-old one


def test_the_7_day_view_uses_the_current_time(db) -> None:
    s1 = _store(db, "1")
    db.execute(
        "INSERT INTO gap_reports (store_id, shown_price, actual_price) VALUES (%s, 5, 6), (%s, 5, 7)",
        (s1, s1),
    )
    db.execute(
        "INSERT INTO gap_reports (store_id, shown_price, actual_price, created_at)"
        " VALUES (%s, 5, 6, now() - interval '8 days')",
        (s1,),
    )
    rows = db.execute(
        "SELECT chain_id, store_code, reports, price_mismatches FROM quality_gap_reports_7d"
    ).fetchall()
    assert rows == [(CHAIN, "1", 2, 2)]


# --- the soft warning ---------------------------------------------------------------------------


def test_warning_needs_a_price_file_with_a_store_and_the_threshold(db) -> None:
    s1 = _store(db, "1")
    for n in range(3):
        _gap(db, s1, "5.00", f"6.0{n}")
    full = parsed_file("price_full", encode(items=[item("A")], prices=[price("A", "1", "5")]))
    w = quality.warn_gap_report_pressure(db, full, 3, NOW)
    assert w is not None and w.warning == "gap_report_pressure" and w.store_code == "1"
    assert "3 confirmed price mismatches" in w.detail and "threshold 3" in w.detail
    assert quality.warn_gap_report_pressure(db, full, 4, NOW) is None
    assert quality.warn_gap_report_pressure(db, full, 0, NOW) is None  # 0 disables
    # Reports older than 7 days do not count.
    assert quality.warn_gap_report_pressure(db, full, 3, NOW + timedelta(days=8)) is None
    other_store = parsed_file(
        "price_full", encode(items=[item("A")], prices=[price("A", "2", "5")]), store_code="2"
    )
    assert quality.warn_gap_report_pressure(db, other_store, 1, NOW) is None
    promo = parsed_file("promo_full", encode())
    assert quality.warn_gap_report_pressure(db, promo, 1, NOW) is None
    assert quality.warnings(db, full, Thresholds(36, 3, 0.5, 3), now=NOW) == [w]


def test_threshold_setting_and_per_chain_override() -> None:
    assert Settings().thresholds_for("x").gap_report_pressure_min == 3
    s = Settings(gap_report_pressure_min=5,
                 quality_overrides={"fake": {"gap_report_pressure_min": 0}})  # fmt: skip
    assert s.thresholds_for("x").gap_report_pressure_min == 5
    assert s.thresholds_for("fake").gap_report_pressure_min == 0
    assert isinstance(s.thresholds_for("fake").gap_report_pressure_min, int)


def _full(h, amount: str, at) -> None:
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", amount, at=at - 2 * HOUR)], salt=str(at)),
        at=at - HOUR,
    )


def test_pressure_warns_once_and_never_quarantines(db, tmp_path) -> None:
    h = make_harness(db, tmp_path)
    s1 = _store(db, "1")
    for n in range(3):
        _gap(db, s1, "5.00", f"6.0{n}")
    _full(h, "5.00", NOW)
    rep = h.scheduler().run_full([CHAIN]).chains[0]
    assert (rep.loaded, rep.quarantined) == (1, 0)
    rows = db.execute(
        "SELECT chain_id, store_code, warning, file_id IS NOT NULL FROM quality_warnings"
    ).fetchall()
    assert rows == [(CHAIN, "1", "gap_report_pressure", True)]
    alerts = [a for a in h.sink.alerts if a.kind == "quality_warning"]
    assert len(alerts) == 1 and alerts[0].details["store_code"] == "1"
    assert "gap_report_pressure" in alerts[0].message
    assert set(statuses(db).values()) == {"loaded"}

    # The next file within 24 hours: loaded, no second warning or alert.
    h.set_now(NOW + 2 * HOUR)
    h.fetcher.clear()
    _full(h, "5.10", NOW + 2 * HOUR)
    assert h.scheduler().run_full([CHAIN]).chains[0].loaded == 1
    assert db.execute("SELECT count(*) FROM quality_warnings").fetchone()[0] == 1
    assert len([a for a in h.sink.alerts if a.kind == "quality_warning"]) == 1


def test_no_warning_below_the_threshold(db, tmp_path) -> None:
    h = make_harness(db, tmp_path, gap_report_pressure_min=4)
    s1 = _store(db, "1")
    for n in range(3):
        _gap(db, s1, "5.00", f"6.0{n}")
    _full(h, "5.00", NOW)
    assert h.scheduler().run_full([CHAIN]).chains[0].loaded == 1
    assert db.execute("SELECT count(*) FROM quality_warnings").fetchone()[0] == 0
    assert not [a for a in h.sink.alerts if a.kind == "quality_warning"]
