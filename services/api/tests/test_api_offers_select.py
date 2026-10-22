"""The choice of the offers kept per (canonical, store, level), with no database
(``smartcart_api/offers.py``; the tables and the routes are in ``test_api_offers.py``)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from smartcart_api import offers
from smartcart_api.precompute import Option

D = Decimal
NOW = datetime(2026, 10, 22, tzinfo=UTC)


def opt(
    item: int,
    shelf: str,
    eff: str | None = None,
    need: int | None = None,
    promo: int | None = None,
    units: int | None = None,
    club: str | None = None,
    amount: str | None = None,
) -> Option:
    effective = D(eff) if eff else D(shelf)
    unit = (effective / units) if units else effective
    return Option(
        item, D(shelf), effective, unit, "unit", NOW, False, promo, D(need) if need else None,
        None, club is not None, club, D(units) if units else None, D(amount) if amount else None,
    )  # fmt: skip


def pick(offers_: list[tuple[Option, bool]], stored: list[Option], per=None):
    return offers.choose_extras(offers_, stored, D(per) if per else None)


def test_the_best_unit_price_alone_needs_no_extra_row() -> None:
    a = opt(1, "10", "7", 4, 1)  # 4 for 28: best unit price, and the cheapest at 4
    b = opt(2, "10")  # a plain item at the same shelf price: never cheaper
    assert pick([(a, False), (b, False)], [a]) == []


def test_probe_quantities_reach_the_end_of_each_shelf_item() -> None:
    tray, dozen = opt(1, "29.90", units=30), opt(2, "14.20", units=12)
    qs = offers.probe_quantities([tray, dozen], D(12))
    assert D("2.5") in qs and D(1) in qs and D(6) in qs and D(15) in qs
    assert qs == sorted(set(qs))
    # An item whose k-th shelf item ends at a repeating decimal is probed just inside the step.
    q = offers.probe_quantities([opt(3, "5", units=10)], D(12))
    third = D(10) / D(12) * 3
    assert any(abs(x - third) < D("0.00001") and x <= third for x in q)


def test_eggs_selection_without_a_database() -> None:
    tray, dozen = opt(1, "29.90", units=30), opt(2, "14.20", units=12)
    got = pick([(tray, True), (dozen, False)], [tray], per=12)
    assert got == [dozen]


def test_the_extras_are_bounded() -> None:
    """Eight items of different counts, each the cheapest for some quantity: at most four kept."""
    per = D(1)
    stored = opt(0, "100", units=1000)  # the best unit price, dear for any real quantity
    prices = {2: "3", 3: "4.1", 5: "6.0", 8: "9.0", 13: "13.5", 21: "21.5", 34: "34.2"}
    many = [(opt(n, p, units=n), False) for n, p in prices.items()]
    got = offers.choose_extras([(stored, False), *many], [stored], per)
    assert 0 < len(got) <= offers.MAX_EXTRA_OFFERS
    assert stored not in got and len({o.item_id for o in got}) == len(got)


def test_a_substitute_loses_a_tie_to_an_item_of_the_level() -> None:
    sub = opt(1, "10.00")
    real = opt(2, "10.00")
    assert pick([(sub, True), (real, False)], [sub]) == [real]


def test_each_club_audience_keeps_its_own_cheapest() -> None:
    nonclub = opt(1, "10", "8.5", 2, 11)  # 2 for 17
    best = opt(1, "10", "5", 4, 12, club="club-a")  # 4 for 20, club a
    other = opt(1, "10", "6", 3, 13, club="club-b")  # 3 for 18, club b
    got = pick([(nonclub, False), (best, False), (other, False)], [best])
    assert {o.promo_id for o in got} == {11, 13}  # everyone's deal, and club b's for its members


def test_an_unnamed_club_deal_is_never_a_candidate() -> None:
    unnamed = opt(1, "10", "4", 4, 12)
    unnamed = replace(unnamed, club_required=True, club_name=None)
    plain = opt(1, "10")
    assert pick([(unnamed, False), (plain, False)], [plain]) == []


def test_only_items_of_one_size_are_compared() -> None:
    big = opt(1, "8.60", amount="20")
    small = opt(2, "2.90", amount="5")
    assert offers.comparable(small, big) is False
    assert offers.comparable(opt(3, "8.00", amount="20.5"), big) is True
    assert offers.comparable(opt(4, "8.00", units=6), opt(5, "9.00", units=12)) is True
    assert offers.comparable(opt(4, "8.00", units=6), opt(5, "9.00")) is False
    assert pick([(big, False), (small, False)], [big]) == []
