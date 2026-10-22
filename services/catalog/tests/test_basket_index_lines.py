"""Basket index: the cost of each line and the line-outlier check (real day, 2026-10-22, issue #44).

The first real day priced a tray of twelve eggs as one egg (14.20 an egg, 170.40 for the line, against
14.16 at King Store). The totals' spread check caught it only as a 56% spread; this check names the line.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from smartcart_catalog import basket_index as bi
from smartcart_catalog.export_seo import PriceRow

NOW = datetime(2026, 10, 22, 6, 0, tzinfo=UTC)
SMALL = (
    bi.BasketLine("milk-fresh-3", Decimal(20), "2 ליטר"),
    bi.BasketLine("eggs-l", Decimal(12), "12 ביצים"),
    bi.BasketLine("tomato", Decimal("1.5"), "1.5 ק״ג"),
)


def rows(overrides: dict[tuple[str, str], str] | None = None) -> list[PriceRow]:
    base = {
        "a": (1, {"milk-fresh-3": "0.5", "eggs-l": "1.0", "tomato": "6"}),
        "b": (2, {"milk-fresh-3": "0.6", "eggs-l": "1.1", "tomato": "7"}),
    }
    out = []
    for chain, (store, prices) in base.items():
        for slug, price in prices.items():
            price = (overrides or {}).get((slug, chain), price)
            out.append(
                PriceRow(
                    slug, chain, chain.upper(), store, Decimal(price), slug == "tomato", NOW, NOW
                )
            )
    return out


def test_month_rows_carry_the_cost_of_each_line() -> None:
    doc = bi.month_document("2026-10", SMALL, rows(), computed_at=NOW)
    a = next(c for c in doc["chains"] if c["chain_id"] == "a")
    # 20 x 0.5, 12 x 1.0, 1.5 x 6
    assert a["line_costs"] == {"milk-fresh-3": 10.0, "eggs-l": 12.0, "tomato": 9.0}


def test_a_pack_read_as_one_unit_is_a_line_outlier_error_that_blocks_publication() -> None:
    data = rows({("eggs-l", "b"): "14.20"})
    doc = bi.month_document("2026-10", SMALL, data, computed_at=NOW)
    flagged = bi.line_outliers(doc["chains"])
    assert [(slug, low[1], high[1]) for slug, low, high in flagged] == [("eggs-l", "A", "B")]
    (check,) = [c for c in bi.run_checks(doc, None, now=NOW) if c["code"] == "line_outlier"]
    assert check["level"] == "error" and check["chain_id"] == "b"
    assert "170.40 against 12.00" in check["message"]
    index = bi.empty_index({"version": 1, "item_count": 3, "items": []}, NOW)
    outcome = bi.evaluate_month(index, "2026-10", SMALL, data, now=NOW, reviewed_by="reviewer")
    assert outcome.doc["status"] == "draft"
    assert "line_outlier" in {c["code"] for c in outcome.blocked}


def test_a_line_that_costs_nothing_is_flagged_against_the_chain_that_prices_it() -> None:
    doc = bi.month_document(
        "2026-10", SMALL, rows({("milk-fresh-3", "a"): "0.0001"}), computed_at=NOW
    )
    (check,) = [c for c in bi.run_checks(doc, None, now=NOW) if c["code"] == "line_outlier"]
    assert "an unpriced line" in check["message"] and check["chain_id"] == "b"


def test_ordinary_price_gaps_are_not_line_outliers() -> None:
    # real shelf gaps are tens of percent: 0.5 against 0.6, 1.0 against 1.1, 6 against 7
    doc = bi.month_document("2026-10", SMALL, rows(), computed_at=NOW)
    assert bi.line_outliers(doc["chains"]) == []
    # just under the limit is allowed, the limit itself is not
    under = bi.month_document("2026-10", SMALL, rows({("eggs-l", "b"): "3.9"}), computed_at=NOW)
    assert bi.line_outliers(under["chains"]) == []
    at = bi.month_document("2026-10", SMALL, rows({("eggs-l", "b"): "4.0"}), computed_at=NOW)
    assert [s for s, *_ in bi.line_outliers(at["chains"])] == ["eggs-l"]


def test_a_stored_month_from_before_line_costs_existed_is_skipped() -> None:
    old = [{"chain_id": "a", "name": "A"}, {"chain_id": "b", "name": "B"}]
    assert bi.line_outliers(old) == []
