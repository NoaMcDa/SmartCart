"""GET /history/{canonical_id} (issue #28): a daily series rebuilt from price change events.

Events are placed at 12:00 UTC on past days (n days ago), across at least two monthly partitions
(ensure_price_partition for each), for Tnuva 3% milk (exact-mapped to milk3 in chain t-c1):

  n=50  base 7.00   n=40  base 6.50   n=20  home store exception 5.90   n=10  base 6.80
  (and the world's own base 6.90 from yesterday, and a quarantined base 1.00 at n=30)
"""

from __future__ import annotations

import time as clock
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
from api_world import World, add_price, add_promo

from smartcart_api.precompute import precompute_effective_prices
from smartcart_api.routes.history import daily_series

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
D = Decimal


def noon(n: int) -> datetime:
    return datetime.combine(datetime.now(UTC).date() - timedelta(days=n), time(12), tzinfo=UTC)


def day(n: int) -> str:
    return (datetime.now(UTC).date() - timedelta(days=n)).isoformat()


@pytest.fixture
def w(db, world: World) -> World:
    item = world.items["milk3_c1_tnuva"]
    for n in (50, 40, 30, 20, 10, 200):
        db.execute("SELECT ensure_price_partition(%s::date)", (noon(n).date(),))
    add_price(db, item, None, "7.00", "0.70", "100ml", noon(50))
    add_price(db, item, None, "6.50", "0.65", "100ml", noon(40))
    add_price(db, item, world.stores["home"], "5.90", "0.59", "100ml", noon(20))
    add_price(db, item, None, "6.80", "0.68", "100ml", noon(10))
    fid = db.execute(
        "INSERT INTO file_tracking (sha256, chain_id, kind, status) VALUES (%s, 't-c1', 'price',"
        " 'quarantined') RETURNING id", ("a" * 64,),
    ).fetchone()[0]
    add_price(db, item, None, "1.00", "0.10", "100ml", noon(30), file_id=fid)
    world.promos["milk_sale"] = add_promo(
        db, "t-c1", None, "H1", [item], "price", "5.50", description="חלב במבצע",
        starts_at=noon(30), ends_at=noon(25))
    db.execute("UPDATE promos SET raw = '{\"confidence\": 0.6}' WHERE id = %s", (world.promos["milk_sale"],))
    world.promos["milk_club"] = add_promo(
        db, "t-c1", world.stores["home"], "H2", [item], "price", "5.00", club_only=True,
        club_name="מועדון לקוחות", description="חלב למועדון", starts_at=noon(15), ends_at=noon(12))
    add_promo(db, "t-c1", None, "H3", [item], "price", "5.00", description="ישן",
              starts_at=noon(200), ends_at=noon(190))
    precompute_effective_prices(db, chains=world.chains)
    return world


def get(client, w: World, **params) -> dict:
    r = client.get(f"/history/{w.canon['milk3']}", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_store_series_with_exception_over_base(client, w: World) -> None:
    resp = get(client, w, store_id=w.stores["home"])
    assert resp["item_id"] == w.items["milk3_c1_tnuva"] and resp["days"] == 90
    pts = {p["date"][:10]: p for p in resp["points"]}
    dates = [p["date"] for p in resp["points"]]
    assert dates == sorted(dates)
    # Nothing before the first event: a gap, never a line drawn backwards.
    assert min(pts) == day(50) and len(pts) == 51
    assert D(pts[day(50)]["unit_price"]) == D("0.7000") and pts[day(50)]["store_id"] is None
    assert D(pts[day(41)]["shelf_price"]) == D("7.00")
    assert D(pts[day(40)]["shelf_price"]) == D("6.50")
    assert D(pts[day(30)]["shelf_price"]) == D("6.50")  # the quarantined 1.00 never counts
    # From the exception on, the store's price governs, also after newer base prices.
    for n in (20, 10, 5, 1, 0):
        assert D(pts[day(n)]["shelf_price"]) == D("5.90"), n
        assert pts[day(n)]["store_id"] == w.stores["home"]


def test_chain_base_series_and_promo_windows(client, w: World) -> None:
    resp = get(client, w)  # no store: the best any-brand item's chain base price
    assert resp["store_id"] is None and resp["item_id"] == w.items["milk3_c1_tnuva"]
    pts = {p["date"][:10]: p for p in resp["points"]}
    assert all(p["store_id"] is None for p in resp["points"])
    assert D(pts[day(10)]["shelf_price"]) == D("6.80") and D(pts[day(0)]["shelf_price"]) == D("6.90")
    # Only the chain-wide promo inside the range (not the store's club promo, not the old one).
    assert [p["description"] for p in resp["promos"]] == ["חלב במבצע"]
    sale = resp["promos"][0]
    assert sale["starts_at"][:10] == day(30) and sale["ends_at"][:10] == day(25)
    assert sale["promo_type"] == "price" and not sale["club_only"]
    assert sale["confidence"] == pytest.approx(0.6)
    assert pts[day(28)]["promo_description"] == "חלב במבצע"
    assert pts[day(35)]["promo_description"] is None


def test_store_series_marks_club_promos(client, w: World) -> None:
    resp = get(client, w, store_id=w.stores["home"])
    club = next(p for p in resp["promos"] if p["club_only"])
    assert club["club_name"] == "מועדון לקוחות" and club["description"] == "חלב למועדון"
    pts = {p["date"][:10]: p for p in resp["points"]}
    assert pts[day(13)]["promo_description"] == "חלב למועדון (מועדון: מועדון לקוחות)"


def test_range_limits_and_errors(client, w: World) -> None:
    short = get(client, w, days=30)
    assert len(short["points"]) == 30 and short["points"][0]["date"][:10] == day(29)
    assert len(get(client, w, days=365)["promos"]) == 2  # the old promo is inside a year
    cid = w.canon["milk3"]
    assert client.get(f"/history/{cid}", params={"days": 0}).status_code == 422
    assert client.get(f"/history/{cid}", params={"days": 366}).status_code == 422
    assert client.get("/history/999999").status_code == 404
    assert client.get(f"/history/{cid}", params={"store_id": 999999}).status_code == 404
    empty = client.get(f"/history/{w.canon['wafer']}").json()  # no item at all
    assert empty["points"] == [] and empty["item_id"] is None


def test_daily_series_unit() -> None:
    """A known sequence of events, including a store exception over the chain base price."""
    start = datetime(2026, 9, 1, tzinfo=UTC)
    now = datetime(2026, 9, 8, 9, tzinfo=UTC)
    ev = [
        (None, D("10"), None, None, datetime(2026, 9, 2, 8, tzinfo=UTC)),
        (None, D("9"), None, None, datetime(2026, 9, 4, 23, 59, tzinfo=UTC)),
        (7, D("8"), None, None, datetime(2026, 9, 5, 10, tzinfo=UTC)),
        (None, D("11"), None, None, datetime(2026, 9, 7, 1, tzinfo=UTC)),
        (None, D("1"), None, None, datetime(2026, 9, 8, 10, tzinfo=UTC)),  # after now
    ]
    pts = daily_series(ev, start, now, lambda e: e[1])
    got = [(p.date.date(), p.shelf_price, p.store_id) for p in pts]
    assert got == [
        (date(2026, 9, 2), D("10"), None),
        (date(2026, 9, 3), D("10"), None),
        (date(2026, 9, 4), D("9"), None),
        (date(2026, 9, 5), D("8"), 7),
        (date(2026, 9, 6), D("8"), 7),
        (date(2026, 9, 7), D("8"), 7),
        (date(2026, 9, 8), D("8"), 7),
    ]


def test_ninety_days_response_time(client, w: World) -> None:
    started = clock.perf_counter()
    get(client, w, store_id=w.stores["home"])
    elapsed = clock.perf_counter() - started
    print(f"history 90 days: {elapsed * 1000:.1f} ms")
    assert elapsed < 2.0
