"""Monthly basket index: pricing, checks, publication gate, files (issue #44)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import typer
from test_export_seo import NOW, PriceWorld, _NoCommit
from typer.testing import CliRunner

from smartcart_catalog import basket_index as bi
from smartcart_catalog import cli_seo
from smartcart_catalog.export_seo import PriceRow, read_unit_prices
from smartcart_catalog.seed import load_catalog
from smartcart_catalog.taxonomy import default_data_dir

SMALL = (
    bi.BasketLine("milk-fresh-3", Decimal(20), "2 ליטר"),
    bi.BasketLine("eggs-l", Decimal(12), "12 ביצים"),
    bi.BasketLine("tomato", Decimal("1.5"), "1.5 ק״ג"),
)


@pytest.fixture
def prices(db) -> PriceWorld:
    return PriceWorld(db)


def fill(p: PriceWorld, milk: str, eggs: str, tomato: str, *, store: str, **kw) -> None:
    p.put("milk-fresh-3", store, milk, **kw)
    p.put("eggs-l", store, eggs, **kw)
    p.put("tomato", store, tomato, estimated=True, **kw)


# --- the basket definition ---------------------------------------------------------------------------


def test_basket_v1_is_a_documented_list_of_about_25_mvp_canonicals() -> None:
    catalog = load_catalog(default_data_dir())
    by_slug = {c.slug: c for c in catalog.canonicals if c.is_mvp}
    slugs = [line.slug for line in bi.BASKET_V1]
    assert len(slugs) == len(set(slugs)) == 25
    assert set(slugs) <= set(by_slug)
    assert all(line.amount > 0 and line.label_he for line in bi.BASKET_V1)
    # a staples basket: every item is among the best-ranked 60 of the estimated ranking
    assert max(by_slug[s].rank for s in slugs) <= 60
    definition = bi.basket_definition(
        bi.BASKET_V1, {s: (c.display_name_he, c.base_unit) for s, c in by_slug.items()}
    )
    assert definition["version"] == 1 and definition["item_count"] == 25
    assert definition["items"][0] == {
        "slug": "milk-fresh-3", "name_he": "חלב טרי 3%", "amount": 20.0,
        "base_unit": "100ml", "label_he": "2 ליטר",
    }  # fmt: skip


def test_ensure_index_writes_the_definition_and_keeps_stored_months(tmp_path) -> None:
    from smartcart_catalog.export_seo import rows_from_catalog

    canonicals = rows_from_catalog(load_catalog(default_data_dir()))[1]
    first = bi.ensure_index(tmp_path, canonicals, NOW)
    assert first["months"] == [] and first["basket"]["item_count"] == 25
    stored = bi.merge_month(first, bi.month_document("2026-10", SMALL, good_rows(), computed_at=NOW), NOW)
    (tmp_path / bi.INDEX_FILE).write_text(json.dumps(stored), encoding="utf-8")
    again = bi.ensure_index(tmp_path, canonicals, NOW + timedelta(days=1))
    assert [m["month"] for m in again["months"]] == ["2026-10"]  # untouched when the basket is the same


def test_committed_basket_definition_matches_the_code() -> None:
    from test_export_seo import SNAPSHOT_DIR

    from smartcart_catalog.export_seo import rows_from_catalog

    canonicals = rows_from_catalog(load_catalog(default_data_dir()))[1]
    names = {c.slug: (c.display_name_he, c.base_unit) for c in canonicals}
    committed = json.loads((SNAPSHOT_DIR / bi.INDEX_FILE).read_text(encoding="utf-8"))
    assert committed["basket"] == bi.basket_definition(bi.BASKET_V1, names)


# --- pricing ---------------------------------------------------------------------------------------------


def test_chain_total_is_the_median_store_times_the_amount() -> None:
    def row(slug, chain, store, price):
        return PriceRow(slug, chain, chain.upper(), store, Decimal(price), False, NOW, NOW)

    rows = [
        row("milk-fresh-3", "a", 1, "0.50"), row("milk-fresh-3", "a", 2, "0.70"),
        row("milk-fresh-3", "a", 3, "9.00"),  # an outlier store does not move the median
        row("eggs-l", "a", 1, "1.00"), row("eggs-l", "a", 2, "1.20"),
        row("tomato", "a", 1, "6.00"),
        row("milk-fresh-3", "b", 4, "0.60"), row("eggs-l", "b", 4, "1.10"),
        row("tomato", "b", 4, "7.00"),
        row("cottage-5", "b", 4, "2.00"),  # not in this basket: ignored
    ]  # fmt: skip
    a, b = bi.price_chains(rows, SMALL)
    # a: 20 x 0.70 + 12 x 1.10 + 1.5 x 6.00 = 14 + 13.2 + 9 = 36.20
    assert (a.chain_id, a.total, a.stores, a.complete) == ("a", Decimal("36.20"), 3, True)
    # b: 20 x 0.60 + 12 x 1.10 + 1.5 x 7.00 = 12 + 13.2 + 10.5 = 35.70
    assert b.total == Decimal("35.70") and b.items_priced == 3


def test_a_chain_missing_items_has_no_total_and_is_not_ranked() -> None:
    rows = [PriceRow("milk-fresh-3", "a", "A", 1, Decimal("0.5"), False, NOW)]
    (a,) = bi.price_chains(rows, SMALL)
    assert a.total is None and a.missing == ("eggs-l", "tomato") and not a.complete
    doc = bi.month_document("2026-10", SMALL, rows, computed_at=NOW)
    assert doc["cheapest_chain_id"] is None and doc["spread_pct"] is None
    assert doc["chains"][0]["complete"] is False and doc["chains"][0]["missing"] == ["eggs-l", "tomato"]


@pytest.mark.db
def test_month_from_seeded_effective_prices(db, prices: PriceWorld) -> None:
    p = prices
    fill(p, "0.50", "1.00", "6.00", store="a1")
    fill(p, "0.70", "1.20", "6.00", store="a2")
    fill(p, "0.60", "1.10", "7.00", store="b1")
    fill(p, "0.10", "0.10", "0.10", store="c_online")  # online: excluded
    p.put("milk-fresh-3", "c1", "0.55")  # c has only milk: missing eggs and tomato
    doc = bi.month_document("2026-10", SMALL, read_unit_prices(db), computed_at=NOW)
    ranked = [c for c in doc["chains"] if c["complete"]]
    # a: milk median(0.50, 0.70) = 0.60 -> 12; eggs median(1.00, 1.20) = 1.10 -> 13.2; tomato 9.0
    #    = 34.20.  b: 12 + 13.2 + 10.5 = 35.70
    assert [(c["chain_id"], c["total"]) for c in ranked] == [("a", 34.2), ("b", 35.7)]
    assert ranked[0]["delta_vs_cheapest"] == 0 and ranked[1]["delta_vs_cheapest"] == 1.5
    assert ranked[1]["delta_pct"] == 4.4 and doc["spread_pct"] == 4.4
    assert doc["cheapest_chain_id"] == "a" and ranked[0]["stores"] == 2
    assert ranked[0]["estimated_items"] == 1
    c = doc["chains"][-1]
    assert c["chain_id"] == "c" and c["total"] is None and c["missing"] == ["eggs-l", "tomato"]
    assert doc["price_date"] == "2026-10-07T06:00:00Z"


# --- pre-publication checks -------------------------------------------------------------------------------


def _doc(totals: dict[str, float | None], **kw) -> dict:
    rows = [PriceRow("milk-fresh-3", c, c.upper(), 1, Decimal("1"), False, NOW, NOW) for c in totals]
    doc = bi.month_document("2026-10", SMALL, rows, computed_at=NOW)
    ranked = sorted((c, t) for c, t in totals.items() if t is not None)
    doc["chains"] = [
        {"chain_id": c, "name": c.upper(), "total": t, "delta_vs_cheapest": 0.0, "delta_pct": 0.0,
         "items_priced": 3 if t else 1, "estimated_items": 0, "stores": 1, "complete": t is not None,
         "missing": [] if t is not None else ["eggs-l"]}
        for c, t in totals.items()
    ]  # fmt: skip
    doc["spread_pct"] = (
        round((max(t for _, t in ranked) / min(t for _, t in ranked) - 1) * 100, 1)
        if len(ranked) > 1 else None
    )  # fmt: skip
    doc.update(kw)
    return doc


def codes(checks: list[dict], level: str | None = None) -> set[str]:
    return {c["code"] for c in checks if level is None or c["level"] == level}


def test_checks_flag_missing_items_and_too_few_chains() -> None:
    doc = _doc({"a": 100.0, "b": None})
    checks = bi.run_checks(doc, None, now=NOW)
    assert "missing_items" in codes(checks, "warning")
    assert "too_few_chains" in codes(checks, "error")
    assert codes(bi.run_checks(_doc({"a": 100.0, "b": 110.0}), None, now=NOW), "error") == set()


def test_checks_flag_an_implausible_spread() -> None:
    assert "implausible_spread" in codes(bi.run_checks(_doc({"a": 100.0, "b": 160.0}), None, now=NOW))
    assert "implausible_spread" not in codes(
        bi.run_checks(_doc({"a": 100.0, "b": 126.0}), None, now=NOW)  # the verified 26% gap
    )


def test_checks_flag_an_implausible_month_over_month_change() -> None:
    prev = _doc({"a": 100.0, "b": 110.0})
    prev.update(month="2026-09", status="published")
    cur = _doc({"a": 118.0, "b": 111.0})
    checks = bi.run_checks(cur, prev, now=NOW)
    bad = [c for c in checks if c["code"] == "implausible_change"]
    assert [c["chain_id"] for c in bad] == ["a"] and "+18.0%" in bad[0]["message"]
    within = bi.run_checks(_doc({"a": 114.0, "b": 111.0}), prev, now=NOW)
    assert "implausible_change" not in codes(within)
    dropped = bi.run_checks(_doc({"a": 101.0, "c": 105.0}), prev, now=NOW)
    assert {"chain_dropped", "new_chain"} <= codes(dropped, "warning")
    other_version = {**prev, "basket_version": 2}
    assert "basket_version_changed" in codes(bi.run_checks(cur, other_version, now=NOW), "warning")
    assert "implausible_change" not in codes(bi.run_checks(cur, other_version, now=NOW))


def test_checks_flag_stale_effective_prices() -> None:
    fresh = _doc({"a": 100.0, "b": 105.0}, prices_computed_at=bi._iso(NOW - timedelta(hours=5)))
    stale = _doc({"a": 100.0, "b": 105.0}, prices_computed_at=bi._iso(NOW - timedelta(hours=72)))
    assert "stale_prices" not in codes(bi.run_checks(fresh, None, now=NOW))
    assert "stale_prices" in codes(bi.run_checks(stale, None, now=NOW), "error")


def test_no_prices_at_all_is_an_error() -> None:
    doc = bi.month_document("2026-10", SMALL, [], computed_at=NOW)
    assert codes(bi.run_checks(doc, None, now=NOW), "error") == {"no_prices"}


# --- publication gate ------------------------------------------------------------------------------------------


def good_rows() -> list[PriceRow]:
    out = []
    for chain, store, (m, e, t) in (("a", 1, ("0.5", "1.0", "6")), ("b", 2, ("0.6", "1.1", "7"))):
        for slug, price in zip(("milk-fresh-3", "eggs-l", "tomato"), (m, e, t), strict=True):
            out.append(PriceRow(slug, chain, chain.upper(), store, Decimal(price), slug == "tomato",
                                NOW, NOW))  # fmt: skip
    return out


def test_a_month_is_a_draft_until_a_reviewer_signs_and_no_error_is_open() -> None:
    index = bi.empty_index({"version": 1, "item_count": 3, "items": []}, NOW)
    draft = bi.evaluate_month(index, "2026-10", SMALL, good_rows(), now=NOW)
    assert draft.doc["status"] == "draft" and draft.blocked == []
    ok = bi.evaluate_month(index, "2026-10", SMALL, good_rows(), now=NOW, reviewed_by="נועה")
    assert ok.doc["status"] == "published" and ok.doc["reviewed_by"] == "נועה" and not ok.blocked

    rows = [r for r in good_rows() if r.chain_id == "a"]  # only one chain: too_few_chains
    blocked = bi.evaluate_month(index, "2026-10", SMALL, rows, now=NOW, reviewed_by="נועה")
    assert blocked.doc["status"] == "draft" and blocked.doc["reviewed_by"] is None
    assert [c["code"] for c in blocked.blocked] == ["too_few_chains"]
    acked = bi.evaluate_month(index, "2026-10", SMALL, rows, now=NOW, reviewed_by="נועה",
                              acknowledge=["too_few_chains"])  # fmt: skip
    assert acked.doc["status"] == "published" and acked.doc["acknowledged"] == ["too_few_chains"]


def test_merge_keeps_months_newest_first_and_replaces_a_rerun() -> None:
    index = bi.empty_index({"version": 1, "item_count": 3, "items": []}, NOW)
    for month in ("2026-09", "2026-10", "2026-08", "2026-10"):
        doc = bi.month_document(month, SMALL, good_rows(), computed_at=NOW)
        index = bi.merge_month(index, doc, NOW)
    assert [m["month"] for m in index["months"]] == ["2026-10", "2026-09", "2026-08"]


# --- report and command ------------------------------------------------------------------------------------------


def test_report_is_a_one_page_hebrew_summary_with_the_method_and_checks() -> None:
    index = bi.empty_index({"version": 1, "item_count": 3, "items": []}, NOW)
    out = bi.evaluate_month(index, "2026-10", SMALL, good_rows(), now=NOW, reviewed_by="נועה")
    text = bi.render_report(out.doc, {"version": 1, "item_count": 3})
    assert text.startswith("# מדד הסל החודשי של SmartCart, אוקטובר 2026")
    assert "| A | 31.00 | 0.00 | 0.0 |" in text and "| B | 35.70 | 4.70 | 15.2 |" in text
    assert "פער של 15.2%" in text and "/methodology" in text and "המחיר הקובע הוא בקופה" in text
    assert "נבדק ואושר לפרסום על ידי: נועה" in text and "טיוטה" not in text
    assert "estimated_items" in text  # warnings are listed
    draft = bi.render_report(bi.month_document("2026-10", SMALL, good_rows(), computed_at=NOW),
                             {"version": 1, "item_count": 3})  # fmt: skip
    assert "טיוטה" in draft


@pytest.mark.db
def test_cli_writes_the_index_and_the_report_and_refuses_to_publish_on_errors(
    db, prices: PriceWorld, monkeypatch, tmp_path
) -> None:
    @contextmanager
    def fake_connect():
        yield _NoCommit(db)

    monkeypatch.setattr(cli_seo, "_connect", fake_connect)
    monkeypatch.setattr(bi, "BASKET_V1", SMALL)
    app = typer.Typer()
    cli_seo.register(app)
    out_dir, reports = tmp_path / "seo", tmp_path / "reports"

    def args(month: str, *extra: str) -> list[str]:
        return ["basket-index", "--month", month, "--out", str(out_dir), "--reports", str(reports),
                *extra]  # fmt: skip

    now = datetime.now(UTC)
    for store, (m, e, t) in (("a1", ("0.5", "1.0", "6")), ("b1", ("0.6", "1.1", "7"))):
        fill(prices, m, e, t, store=store, valid_from=now, computed_at=now)

    draft = CliRunner().invoke(app, args("2026-10"))
    assert draft.exit_code == 0, draft.output
    assert "2 chains ranked, status draft" in draft.output and "draft: run again" in draft.output
    index = json.loads((out_dir / bi.INDEX_FILE).read_text(encoding="utf-8"))
    assert index["basket"]["version"] == 1 and index["months"][0]["status"] == "draft"
    assert (reports / "basket-index-2026-10.md").read_text(encoding="utf-8").startswith("# מדד")
    assert not (out_dir / "reports").exists()  # a draft has no public press copy

    published = CliRunner().invoke(app, args("2026-10", "--reviewed-by", "נועה"))
    assert published.exit_code == 0, published.output
    month = json.loads((out_dir / bi.INDEX_FILE).read_text(encoding="utf-8"))["months"][0]
    assert month["status"] == "published" and month["reviewed_by"] == "נועה"
    public = out_dir / "reports" / "basket-index-2026-10.md"
    assert public.read_text(encoding="utf-8") == (reports / public.name).read_text(encoding="utf-8")

    # next month: chain a jumps 40%, which blocks publication but still writes the draft
    db.execute("UPDATE effective_prices SET effective_unit_price = effective_unit_price * 1.4"
               " WHERE store_id = %s", (prices.stores["a1"],))  # fmt: skip
    blocked = CliRunner().invoke(app, args("2026-11", "--reviewed-by", "נועה"))
    assert blocked.exit_code == 1 and "implausible_change" in blocked.output
    months = json.loads((out_dir / bi.INDEX_FILE).read_text(encoding="utf-8"))["months"]
    assert [(m["month"], m["status"]) for m in months] == [("2026-11", "draft"), ("2026-10", "published")]
    accepted = CliRunner().invoke(
        app, args("2026-11", "--reviewed-by", "נועה", "--acknowledge", "implausible_change")
    )
    assert accepted.exit_code == 0, accepted.output
