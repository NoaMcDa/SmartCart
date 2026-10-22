"""Every real PriceFull row, recomputed: the unit price is price / pack size and agrees with what
the chain published, to the rounding of a two-decimal price, under the chain's measured reading.

Fourteen files: the committed real PriceFull of each of the seven chains of 2026-10-21
(``fixtures/<chain>/real/``) and the second day, 2026-10-08 (``data/audit/real-2026-10-08/``),
200 rows each. ``AS_LABELLED`` is the measurement that docs/adapters.md ("Unit prices in real
files") tabulates: how the published value relates to ``price / quantity`` when it is read as its
``UnitOfMeasure`` label says. ``agree`` is the label being right; ``off_x100_low`` is a value
100 times smaller than the label implies (a price per gram under "100 גרם"); ``off_x100_high``
100 times bigger. ``W`` marks weighed items. The numbers are literal: they change only when the
files or the reading rules do.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

from smartcart_ingest.unitprice import (
    PUBLISHED_SCALE,
    check_published,
    parse_label,
    resolve_unit_price,
)
from tests.test_adapters import FIXTURES, chain_adapters, parse_fixture

D = Decimal
AUDIT = Path(__file__).resolve().parents[3] / "data" / "audit" / "real-2026-10-08"
DAYS = {"2026-10-21": FIXTURES, "2026-10-08": AUDIT}
SLUGS = ["king_store", "mega", "osherad", "ramilevy", "shufersal", "tivtaam", "yohananof"]

# (chain, day) -> (rows, price records by source, ``check_as_labelled`` classes, ``check`` classes)
MEASURED: dict[tuple[str, str], tuple[int, dict, dict, dict]] = {
    ("king_store", "2026-10-21"): (
        200, {"computed": 114, "weighed": 86},
        {"agree": 113, "Wagree": 86}, {"agree": 113, "Wagree": 86},
    ),
    ("mega", "2026-10-21"): (
        200, {"computed": 195, "none": 4, "weighed": 1},
        {"agree": 190, "off_x100_high": 5, "Wagree": 1}, {"agree": 195, "Wagree": 1},
    ),
    ("osherad", "2026-10-21"): (
        200, {"computed": 146, "none": 26, "weighed": 28},
        {"agree": 131, "off_x100_low": 15}, {"agree": 146},
    ),
    ("ramilevy", "2026-10-21"): (
        200, {"computed": 197, "weighed": 3},
        {"agree": 87, "off_x100_low": 108, "Wagree": 3, "other": 2},
        {"agree": 195, "Wagree": 3, "other": 2},
    ),
    ("shufersal", "2026-10-21"): (
        200, {"computed": 199, "none": 1}, {"agree": 199}, {"agree": 199},
    ),
    ("tivtaam", "2026-10-21"): (
        200, {"computed": 109, "weighed": 91},
        {"agree": 109, "Wagree": 91}, {"agree": 109, "Wagree": 91},
    ),
    ("yohananof", "2026-10-21"): (
        200, {"computed": 119, "weighed": 81},
        {"agree": 119, "Wagree": 81}, {"agree": 119, "Wagree": 81},
    ),
    ("king_store", "2026-10-08"): (
        200, {"computed": 109, "weighed": 91},
        {"agree": 108, "Wagree": 91}, {"agree": 108, "Wagree": 91},
    ),
    ("mega", "2026-10-08"): (
        200, {"computed": 178, "none": 11, "weighed": 11},
        {"agree": 171, "off_x100_high": 7, "Wagree": 11}, {"agree": 178, "Wagree": 11},
    ),
    ("osherad", "2026-10-08"): (
        200, {"computed": 148, "weighed": 28, "none": 24},
        {"agree": 130, "off_x100_low": 18}, {"agree": 148},
    ),
    ("ramilevy", "2026-10-08"): (
        200, {"computed": 198, "weighed": 2},
        {"agree": 91, "off_x100_low": 107, "Wagree": 2}, {"agree": 198, "Wagree": 2},
    ),
    ("shufersal", "2026-10-08"): (
        200, {"none": 1, "computed": 199}, {"agree": 199}, {"agree": 199},
    ),
    ("tivtaam", "2026-10-08"): (
        200, {"weighed": 92, "computed": 108},
        {"agree": 108, "Wagree": 92}, {"agree": 108, "Wagree": 92},
    ),
    ("yohananof", "2026-10-08"): (
        200, {"weighed": 49, "computed": 151},
        {"agree": 151, "Wagree": 49}, {"agree": 151, "Wagree": 49},
    ),
}  # fmt: skip


def real_file(slug: str, day: str) -> Path:
    return next((DAYS[day] / slug / "real").glob("PriceFull*"))


def resolved_rows(slug: str, day: str):
    """``(price record, weighed, UnitPrice)`` for every row of the chain's real PriceFull."""
    adapter = chain_adapters()[slug]()
    parsed = parse_fixture(adapter, real_file(slug, day))
    weighed = {i.item_code: i.is_weighed for i in parsed.items}
    return [
        (
            r,
            weighed[r.item_code],
            resolve_unit_price(
                r.price,
                r.unit_price,
                r.unit_of_measure,
                weighed[r.item_code],
                r.quantity,
                r.quantity_unit,
                adapter.chain_id,
            ),
        )
        for r in parsed.prices
    ]


# Rami Levy's "בושם לכביסה 240 מל": 38.90 for 20 units, labelled "2   יחידות", published 1.94
# (per unit). On 2026-10-08 the same file does not carry that label.
TWO_UNITS = {"7290108358773", "7290108358797"}
CASES = [(slug, day) for day in DAYS for slug in SLUGS]


@pytest.mark.parametrize(("slug", "day"), CASES)
def test_each_real_file_matches_the_measurement_documented_in_adapters_md(slug, day) -> None:
    rows = resolved_rows(slug, day)
    n, sources, as_labelled, ruled = MEASURED[(slug, day)]
    assert len(rows) == n
    assert dict(Counter(u.source for _, _, u in rows)) == sources
    flag = lambda w, c: ("W" if w else "") + c  # noqa: E731
    got_labelled = Counter(flag(w, u.check_as_labelled) for _, w, u in rows if u.check_as_labelled)
    got_ruled = Counter(flag(w, u.check) for _, w, u in rows if u.check)
    assert dict(got_labelled) == as_labelled
    assert dict(got_ruled) == ruled


@pytest.mark.parametrize(("slug", "day"), CASES)
def test_every_unit_price_agrees_with_price_over_quantity_within_rounding(slug, day) -> None:
    """The recomputed value, expressed in the published unit, is the published value to the
    rounding of two decimals (or 2 %), for every computed row except the two Rami Levy rows
    whose label says "2 units" for a per-unit price."""
    for record, weighed, u in resolved_rows(slug, day):
        if u.source == "weighed":
            assert (u.value, u.uom, u.is_estimated) == (record.price, "kg", True)
            continue
        assert not weighed or u.source != "computed"
        if u.source == "none":
            assert u.value is None and u.uom is None
            continue
        assert u.source == "computed" and u.uom in {"100g", "100ml", "unit"}
        assert u.value is not None and u.value > 0 and not u.is_estimated
        if record.unit_price is None:
            continue
        label = parse_label(record.unit_of_measure)
        per = D(100) if u.uom != "unit" else D(1)
        expected_in_label = u.value / per * label.size  # price / pack, in the label's unit
        scale = PUBLISHED_SCALE.get(record.chain_id, {}).get((label.dim, label.size), D(1))
        verdict = check_published(record.unit_price, expected_in_label / scale)
        if day == "2026-10-21" and record.item_code in TWO_UNITS:
            assert verdict == "other"
        else:
            assert verdict == "agree", (record.item_code, record.price, record.unit_price)


@pytest.mark.parametrize(("slug", "day"), CASES)
def test_without_the_pack_size_the_scaled_published_value_is_the_same_price(slug, day) -> None:
    """Drop ``Quantity`` from every row: the fallback (label x the chain's measured scale) is
    either refused or equals the computed value to the rounding of the published price."""
    adapter = chain_adapters()[slug]()
    refused = checked = 0
    for record, weighed, u in resolved_rows(slug, day):
        if weighed or u.source != "computed" or record.unit_price is None:
            continue
        if day == "2026-10-21" and record.item_code in TWO_UNITS:
            fallback = resolve_unit_price(
                record.price, record.unit_price, record.unit_of_measure, False, None, None, "x"
            )
            assert fallback.value is None  # a count label other than 1 is not read
            continue
        fallback = resolve_unit_price(
            record.price,
            record.unit_price,
            record.unit_of_measure,
            weighed,
            None,
            None,
            adapter.chain_id,
        )
        if fallback.value is None:
            refused += 1
            continue
        checked += 1
        assert fallback.uom == u.uom
        label = parse_label(record.unit_of_measure)
        scale = PUBLISHED_SCALE.get(record.chain_id, {}).get((label.dim, label.size), D(1))
        per = D(100) if u.uom != "unit" else D(1)
        slack = D("0.0051") * scale * per / label.size  # half a cent of the published price
        assert abs(fallback.value - u.value) <= slack + u.value * D("0.02"), record.item_code
    assert checked > 0
    assert refused <= 4  # a published 0.00 or an unknown label (Rami Levy: none; Mega: 0)


def test_the_chain_scales_are_what_the_files_measure() -> None:
    """Re-derive ``PUBLISHED_SCALE`` from the 2 x 7 files: per chain and label, the class of at
    least 90 % of the computed rows (5 or more) as labelled decides the factor."""
    groups: dict[tuple[str, str, int], Counter] = defaultdict(Counter)
    ids = {slug: chain_adapters()[slug].chain_id for slug in SLUGS}
    for slug, day in CASES:
        for record, weighed, u in resolved_rows(slug, day):
            if weighed or u.source != "computed" or not u.check_as_labelled:
                continue
            label = parse_label(record.unit_of_measure)
            groups[(ids[slug], label.dim, int(label.size))][u.check_as_labelled] += 1
    derived: dict[str, dict[tuple[str, D], D]] = defaultdict(dict)
    for (chain, dim, size), classes in groups.items():
        total = sum(classes.values())
        if total < 5:
            continue
        cls, count = classes.most_common(1)[0]
        if count / total < 0.9:
            continue  # a mixed label (Rami Levy's "2 units"): never a rule
        factor = {"agree": D(1), "off_x100_low": D(100), "off_x100_high": D("0.01")}.get(cls)
        assert factor is not None, (chain, dim, size, dict(classes))
        if factor != 1:
            derived[chain][(dim, D(size))] = factor
    assert dict(derived) == PUBLISHED_SCALE
