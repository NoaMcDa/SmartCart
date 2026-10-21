"""Tests for the pure parts of ``scripts/unblock/real_day.py`` (no network, no database).

    uv run pytest scripts/unblock/tests/test_real_day.py -q

The stages that need a database or the portals are exercised by running the script itself:
offline with ``--from-fixtures`` against a throwaway Postgres (docs/real-day-dry-run.md), and on a
runner by ``.github/workflows/real-day.yml``.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import real_day  # noqa: E402

ISRAEL = ZoneInfo("Asia/Jerusalem")


def _store(chain: str, code: str, lat: float, lon: float) -> dict:
    return {"chain_id": chain, "store_code": code, "lat": lat, "lon": lon}


def test_haversine_known_distance() -> None:
    # Tel Aviv to Jerusalem centre is about 54 km in a straight line.
    d = real_day.haversine_km(32.0780, 34.7740, 31.7810, 35.2170)
    assert 52 < d < 56
    assert real_day.haversine_km(32.0, 34.8, 32.0, 34.8) == 0


def test_rank_anchors_prefers_more_chains_and_separates_them() -> None:
    stores = [
        _store("a", "1", 32.078, 34.774),
        _store("b", "1", 32.080, 34.776),
        _store("c", "1", 32.075, 34.770),
        _store("a", "2", 32.083, 34.812),  # Ramat Gan, 3.7 km from the first: too close
        _store("a", "3", 31.781, 35.217),
        _store("b", "3", 31.783, 35.219),
        _store("a", "4", 32.800, 34.990),  # one chain only
    ]
    catalog = [
        ("Tel Aviv", 32.078, 34.774),
        ("Ramat Gan", 32.083, 34.812),
        ("Jerusalem", 31.781, 35.217),
        ("Haifa", 32.800, 34.990),
        ("Eilat", 29.55, 34.95),  # no store at all
    ]
    picked = real_day.rank_anchors(stores, catalog, radius_km=4, count=3)
    assert [p["name"] for p in picked] == ["Tel Aviv", "Jerusalem", "Haifa"]
    assert picked[0]["chains"] == 3
    assert all(p["stores"] > 0 for p in picked)


def test_select_stores_nearest_per_chain_within_radius() -> None:
    anchor = {"lat": 32.078, "lon": 34.774}
    stores = [
        _store("a", "10", 32.079, 34.775),
        _store("a", "11", 32.090, 34.780),
        _store("a", "12", 32.100, 34.790),
        _store("b", "7", 32.077, 34.773),
        _store("b", "8", 31.5, 35.0),  # far away
    ]
    chosen = real_day.select_stores(stores, anchor, radius_km=4, per_chain=2)
    assert chosen == {"a": ["10", "11"], "b": ["7"]}


def test_store_file_regex_matches_portal_names_with_any_padding() -> None:
    rx = re.compile(real_day.store_file_regex("price_full", ["164", "001", "7"]))
    assert rx.search("PriceFull7290027600007-001-164-20261008-030000.gz")
    assert rx.search("PriceFull7290058140886-001-001-20261008-001000.gz")
    assert rx.search("PriceFull7290058108879-000-007-20261008-043451.gz")
    assert not rx.search("PriceFull7290027600007-001-165-20261008-030000.gz")
    assert not rx.search("PriceFull7290027600007-001-1640-20261008-030000.gz")
    assert not rx.search("PromoFull7290027600007-001-164-20261008-030000.gz")
    promo = re.compile(real_day.store_file_regex("promo_full", ["2"]))
    assert promo.search("PromoFull7290055700007-001-002-20261008-051017.gz")
    assert not promo.search("PriceFull7290055700007-001-002-20261008-051017.gz")


def test_stale_clock_replays_only_old_files() -> None:
    now = datetime(2026, 10, 21, 12, 0, tzinfo=ISRAEL)
    fresh = now - timedelta(hours=5)
    assert real_day.stale_clock(fresh, now) == (now, False)
    old = now - timedelta(hours=40)
    clock, stale = real_day.stale_clock(old, now)
    assert stale and clock == old + timedelta(hours=1)
    assert real_day.stale_clock(None, now) == (now, False)
    # Exactly at the limit is not stale (the gate says "older than").
    edge = now - timedelta(hours=real_day.STALE_HOURS)
    assert real_day.stale_clock(edge, now) == (now, False)


def test_summarize_ms() -> None:
    assert real_day.summarize_ms([]) == {"n": 0, "median": None, "p95": None, "max": None}
    s = real_day.summarize_ms([10, 30, 20, 40, 50])
    assert s == {"n": 5, "median": 30, "p95": 50, "max": 50}


def test_covered_baskets_are_deterministic_and_priced_in_two_stores() -> None:
    priced = {c: (1 if c % 5 == 0 else 3) for c in range(1, 61)}
    a = real_day.covered_baskets(priced, (5, 10, 40), seed=1)
    b = real_day.covered_baskets(priced, (5, 10, 40), seed=1)
    assert a == b
    assert real_day.covered_baskets(priced, (5,), seed=2) != {5: a[5]}
    for size, items in a.items():
        assert len(items) == min(size, 48)  # 48 canonicals are priced in two or more stores
        assert all(priced[i["canonical_id"]] >= 2 for i in items)
        assert len({i["canonical_id"] for i in items}) == len(items)
        assert all(1 <= i["quantity"] <= 3 and i["flex_level"] == "any_brand" for i in items)
    assert real_day.covered_baskets({1: 1}, (5,), seed=1) == {5: []}


def test_newest_per_store_keeps_the_latest_file() -> None:
    def parser(name: str):
        if name == "bad":
            raise ValueError(name)
        store, stamp = name.split("_")
        return SimpleNamespace(
            store_code=None if store == "x" else store,
            published_at=datetime.strptime(stamp, "%Y%m%d%H%M").replace(tzinfo=ISRAEL),
        )

    names = ["1_202610200100", "1_202610210100", "2_202610200900", "x_202610210900", "bad"]
    assert real_day.newest_per_store(names, parser) == {
        "1": "1_202610210100",
        "2": "2_202610200900",
    }


def test_report_renders_without_optional_sections() -> None:
    res = {
        "mode": "files",
        "commit": "abc",
        "runner": "r",
        "started_at": "t0",
        "stages": [
            {"name": "migrate", "seconds": 1.5, "ok": True, "note": "25 applied"},
            {"name": "catalog: judge", "seconds": 2, "ok": False, "error": "boom"},
        ],
        "files": [
            {
                "chain": "shufersal",
                "kind": "price_full",
                "file": "PriceFull1.gz",
                "published_at": "2026-10-21T03:00+03:00",
                "age_hours": 5.0,
                "parse": {"schema": "v1"},
                "gate": {"status": "loaded"},
                "price_rows": 12000,
                "seconds": 3.2,
            }
        ],
        "options": {"radius_km": 4.0},
        "failures": [{"stage": "api", "what": "milp fell back", "detail": ""}],
    }
    text = real_day.render_report(res)
    assert "| migrate | 1.5 | 25 applied |" in text
    assert "| catalog: judge | 2 | boom |" in text
    assert "12,000" in text
    assert "**api**: milp fell back" in text
    assert "not publishable" in text.lower()
