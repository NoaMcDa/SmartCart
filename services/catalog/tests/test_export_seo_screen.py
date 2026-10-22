"""export-seo on real-shaped prices: what is kept off the pages, and the audit (issue #35, real day 2026-10-22).

The rows are shaped like the first real day's ``effective_prices``: a tray of twelve eggs read as one egg
(14.20 where the others say 1.18), a unit price that rounds to nothing (Rami Levy 0.01 per 100 g), a chain
alone with its single store, weighed goods per kg, chain names with quotes and brackets.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from test_export_seo import NOW, PriceWorld

from smartcart_catalog.export_seo import (
    PRODUCTS_FILE,
    PriceRow,
    aggregate_prices,
    aggregate_withheld,
    export_from_db,
    export_from_files,
    screen_prices,
)
from smartcart_catalog.seed import load_catalog
from smartcart_catalog.seo_audit import audit_dir, audit_products, render_audit
from smartcart_catalog.taxonomy import default_data_dir

UNITS = {
    "eggs-l": "unit",
    "milk-fresh-3": "100ml",
    "chicken-breast-fresh": "kg",
    "rice-persian": "100g",
}


def row(slug: str, chain: str, store: int, price: str, **kw) -> PriceRow:
    return PriceRow(slug, chain, kw.pop("name", chain.upper()), store, Decimal(price),
                    kw.pop("estimated", False), kw.pop("when", NOW), NOW)  # fmt: skip


def reasons(held) -> set[tuple[str, str, str]]:
    return {(w.canonical_slug, w.chain_id, w.reason) for w in held}


# --- screen_prices -----------------------------------------------------------------------------------------------


def test_a_tray_read_as_one_egg_is_withheld_when_other_chains_disagree() -> None:
    rows = [
        row("eggs-l", "kingstore", 1, "1.18"),
        row("eggs-l", "shufersal", 2, "1.35"),
        row("eggs-l", "yohananof", 3, "1.29"),
        row(
            "eggs-l", "ramilevy", 4, "14.20"
        ),  # a tray of twelve read as a unit: 12 times its price
    ]
    kept, held = screen_prices(rows, UNITS)
    assert {r.chain_id for r in kept} == {"kingstore", "shufersal", "yohananof"}
    assert reasons(held) == {("eggs-l", "ramilevy", "chain_outlier")}
    assert "14.20 against" in held[0].detail


def test_two_chains_that_differ_four_times_or_more_are_both_withheld() -> None:
    """With two chains nobody can tell which is right, so neither is shown."""
    kept, held = screen_prices(
        [row("eggs-l", "a", 1, "1.18"), row("eggs-l", "b", 2, "14.20")], UNITS
    )
    assert kept == []
    assert reasons(held) == {("eggs-l", "a", "chains_disagree"), ("eggs-l", "b", "chains_disagree")}
    # an ordinary gap stays: 3.9 times is shelf competition, not a data error
    kept, held = screen_prices(
        [row("eggs-l", "a", 1, "1.00"), row("eggs-l", "b", 2, "3.90")], UNITS
    )
    assert len(kept) == 2 and held == []


def test_a_price_that_rounds_to_nothing_or_is_negative_is_never_shown() -> None:
    rows = [
        row("rice-persian", "ramilevy", 1, "0.001"),
        row("rice-persian", "ramilevy", 2, "0"),
        row("rice-persian", "ramilevy", 3, "-1"),
        row("rice-persian", "shufersal", 4, "0.89"),
        row("rice-persian", "osherad", 5, "0.95"),
    ]
    kept, held = screen_prices(rows, UNITS)
    assert {r.chain_id for r in kept} == {"shufersal", "osherad"}
    assert {w.reason for w in held} == {"bad_price"} and len(held) == 3


def test_a_price_above_the_cap_of_its_unit_is_withheld() -> None:
    rows = [
        row("rice-persian", "a", 1, "151"),
        row("rice-persian", "b", 2, "1.1"),
        row("rice-persian", "c", 3, "1.2"),
    ]
    kept, held = screen_prices(rows, UNITS)
    assert {r.chain_id for r in kept} == {"b", "c"}
    assert reasons(held) == {("rice-persian", "a", "above_cap")}
    # a canonical with an unknown unit has no cap, only the relative checks
    kept, _ = screen_prices([row("mystery", "a", 1, "5000")], UNITS)
    assert len(kept) == 1


def test_one_store_far_from_its_own_chain_is_dropped_only_with_three_or_more_stores() -> None:
    three = [row("milk-fresh-3", "a", i, p) for i, p in enumerate(("0.60", "0.62", "0.05"), 1)]
    kept, held = screen_prices(three, UNITS)
    assert [r.unit_price for r in kept] == [Decimal("0.60"), Decimal("0.62")]
    assert reasons(held) == {("milk-fresh-3", "a", "store_outlier")}
    two = [row("milk-fresh-3", "a", i, p) for i, p in enumerate(("0.60", "0.05"), 1)]
    kept, held = screen_prices(two, UNITS)
    assert len(kept) == 2 and held == []


def test_a_single_chain_with_a_single_store_is_shown_as_it_is() -> None:
    kept, held = screen_prices(
        [row("chicken-breast-fresh", "osherad", 7, "29.90", estimated=True)], UNITS
    )
    assert len(kept) == 1 and held == []


def test_aggregate_withheld_counts_rows_per_chain_and_reason() -> None:
    _, held = screen_prices(
        [
            row("rice-persian", "a", 1, "0"),
            row("rice-persian", "a", 2, "0"),
            row("rice-persian", "b", 3, "1"),
        ],
        UNITS,
    )
    (entry,) = aggregate_withheld(held)["rice-persian"]
    assert entry["chain_id"] == "a" and entry["reason"] == "bad_price" and entry["rows"] == 2


def test_screened_rows_do_not_reach_the_aggregate() -> None:
    kept, _ = screen_prices(
        [
            row("eggs-l", "a", 1, "1.18"),
            row("eggs-l", "b", 2, "1.30"),
            row("eggs-l", "c", 3, "14.20"),
        ],
        UNITS,
    )
    out = aggregate_prices(kept)["eggs-l"]
    assert [p["chain_id"] for p in out["prices"]] == ["a", "b"]
    assert max(p["median_unit_price"] for p in out["prices"]) < 2


# --- the export, in the database --------------------------------------------------------------------------------


@pytest.mark.db
def test_db_export_withholds_and_says_so(db, tmp_path) -> None:
    world = PriceWorld(db)
    world.put("eggs-l", "a1", "1.18")
    world.put("eggs-l", "b1", "1.30")
    world.put("eggs-l", "c1", "14.20")  # the tray read as an egg
    world.put("milk-fresh-3", "a1", "0.60")
    world.put("milk-fresh-3", "a2", "0.00")  # a zero is not a price
    result = export_from_db(db, tmp_path, now=NOW)
    products = {p["slug"]: p for p in result.products["products"]}
    eggs = products["eggs-l"]
    assert [c["chain_id"] for c in eggs["prices"]] == ["a", "b"]
    assert eggs["withheld"] == [
        {"chain_id": "c", "chain_name": "יוחננוף", "reason": "chain_outlier",
         "detail": eggs["withheld"][0]["detail"], "rows": 1}
    ]  # fmt: skip
    milk = products["milk-fresh-3"]
    assert [c["median_unit_price"] for c in milk["prices"]] == [0.6]
    assert milk["withheld"][0]["reason"] == "bad_price"
    assert "withheld" not in products["tomato"]
    assert result.products["withheld_count"] == 2
    assert len(result.withheld) == 2
    audit = audit_dir(tmp_path)
    assert audit["by_code"]["withheld"] == 2 and audit["errors"] == 0


def test_a_clean_export_adds_no_withheld_keys(tmp_path) -> None:
    """The committed snapshot has no prices, so it stays byte-for-byte what it was."""
    export_from_files(load_catalog(default_data_dir()), tmp_path, now=NOW)
    text = (tmp_path / PRODUCTS_FILE).read_text(encoding="utf-8")
    assert "withheld" not in text


# --- the audit -----------------------------------------------------------------------------------------------------


def product(**kw) -> dict:
    base = {
        "slug": "eggs-l", "name_he": "ביצים L", "taxonomy_id": "dairy.eggs", "path": [{"id": "dairy"}],
        "base_unit": "unit", "has_page": True, "no_prices_yet": False,
        "price_valid_from": "2026-10-22T05:00:00Z",
        "prices": [
            {"chain_id": "a", "chain_name": "קינג סטור", "min_unit_price": 1.1, "median_unit_price": 1.18,
             "stores": 3, "is_estimated": False, "price_valid_from": "2026-10-22T05:00:00Z"},
        ],
    }  # fmt: skip
    return {**base, **kw}


def codes(findings) -> list[str]:
    return sorted(f["code"] for f in findings)


def audit(*products: dict) -> list[dict]:
    return audit_products({"generated_at": "2026-10-22T06:00:00Z", "products": list(products)})


def test_audit_is_quiet_on_a_good_product() -> None:
    assert audit(product()) == []


def test_audit_names_each_kind_of_implausible_number() -> None:
    p = product()
    p["prices"] = [
        {**p["prices"][0], "chain_id": "a", "median_unit_price": 0.0, "min_unit_price": 0.0},
        {**p["prices"][0], "chain_id": "b", "median_unit_price": 14.2, "min_unit_price": 1.0},
        {**p["prices"][0], "chain_id": "c", "median_unit_price": 1.3, "stores": 0},
        {
            **p["prices"][0],
            "chain_id": "d",
            "median_unit_price": 1.2,
            "price_valid_from": "2026-12-01T00:00:00Z",
        },
        {
            **p["prices"][0],
            "chain_id": "e",
            "median_unit_price": 1.25,
            "price_valid_from": "2026-07-01T00:00:00Z",
        },
    ]
    found = codes(audit(p))
    assert found.count("bad_price") == 1
    assert (
        "chain_outlier" in found and "store_spread" in found
    )  # b against the others, 14.2 against its 1.0
    assert "no_stores" in found and "bad_date" in found and "old_price" in found
    assert "above_cap" not in found  # 14.2 per unit is under the 300 cap


def test_audit_catches_missing_fields_bad_names_and_a_flag_that_disagrees() -> None:
    p = product(name_he="", base_unit="")
    p["prices"][0].pop("chain_name")
    p2 = product(slug="x", name_he="ב" * 90, no_prices_yet=True)  # flagged unpriced, has prices
    p3 = product(slug="y", name_he="חלב\u0000")
    found = codes(audit(p, p2, p3))
    assert found.count("missing_field") >= 4
    assert found.count("bad_name") >= 3


def test_audit_counts_pages_priced_and_unpriced_in_a_real_shaped_export(tmp_path) -> None:
    unpriced = product(
        slug="u", has_page=True, no_prices_yet=True, prices=None, price_valid_from=None
    )
    rows = [product(), product(slug="m", has_page=False), unpriced]
    (tmp_path / "products.json").write_text(
        json.dumps({"generated_at": "2026-10-22T06:00:00Z", "page_count": 2, "products": rows}),
        encoding="utf-8",
    )
    (tmp_path / "categories.json").write_text(
        json.dumps({"generated_at": "2026-10-22T06:00:00Z", "page_count": 3, "categories": []}),
        encoding="utf-8",
    )
    result = audit_dir(tmp_path)
    assert result["pages"] == {"category": 3, "product": 2, "total": 5}
    assert (result["canonicals"], result["priced"], result["unpriced"]) == (3, 2, 1)
    assert (result["product_pages_priced"], result["product_pages_unpriced"]) == (1, 1)
    assert result["chains_per_priced_product"] == {"1": 2}
    assert "Pages generated | 5" in render_audit(result)


def test_audit_reads_the_draft_basket_month_and_its_line_outliers(tmp_path) -> None:
    (tmp_path / "products.json").write_text(
        json.dumps({"generated_at": "2026-10-22T06:00:00Z", "products": []})
    )
    (tmp_path / "categories.json").write_text(json.dumps({"categories": []}))
    chain = {"complete": True, "items_priced": 25, "missing": [], "estimated_items": 0, "stores": 3}
    month = {
        "month": "2026-10", "status": "draft", "spread_pct": 56.5, "checks": [],
        "chains": [
            {**chain, "chain_id": "a", "name": "A", "total": 900.0, "line_costs": {"eggs-l": 14.16}},
            {**chain, "chain_id": "b", "name": "B", "total": 1400.0, "line_costs": {"eggs-l": 170.4}},
        ],
    }  # fmt: skip
    (tmp_path / "basket-index.json").write_text(
        json.dumps({"basket": {"item_count": 25}, "months": [month]}), encoding="utf-8"
    )
    result = audit_dir(tmp_path)
    assert result["basket"]["status"] == "draft" and result["basket"]["ranked"] == 2
    assert result["by_code"] == {"basket_line": 1}
    assert result["findings"][0]["subject"] == "eggs-l"


def test_the_clock_of_the_audit_is_the_export_time() -> None:
    old = product()
    old["prices"][0]["price_valid_from"] = (
        datetime(2026, 10, 22, tzinfo=UTC) - timedelta(days=46)
    ).isoformat()
    assert codes(audit(old)) == ["old_price"]
