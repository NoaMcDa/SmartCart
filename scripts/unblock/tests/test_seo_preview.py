"""Tests for ``scripts/unblock/seo_preview.py``: the page checks of the real-prices preview.

    uv run pytest scripts/unblock/tests/test_seo_preview.py -q

``crawl`` is run against a tiny local HTTP server that serves hand-made pages, so every check is shown
to pass on a good page and to fail on the page defect it is for. The build, vitest and Playwright steps
need Node and a browser and run in the workflow (``.github/workflows/real-day.yml``).
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import seo_preview  # noqa: E402

ORIGIN = "https://preview.invalid"

PRODUCT = {
    "slug": "eggs-l", "name_he": "ביצים L", "has_page": True, "no_prices_yet": False,
    "price_valid_from": "2026-10-22T05:00:00Z",
    "prices": [{"chain_id": "a", "chain_name": "קינג סטור", "min_unit_price": 1.1,
                "median_unit_price": 1.18, "stores": 3, "is_estimated": False,
                "price_valid_from": "2026-10-22T05:00:00Z"}],
}  # fmt: skip
UNPRICED = {"slug": "milk", "name_he": "חלב", "has_page": True, "no_prices_yet": True, "prices": None,
            "price_valid_from": None}  # fmt: skip


def page(path: str, *, body: str = "", canonical: str | None = None, robots: str = "",
         checkout: bool = True, offers: list | None = None, times: int = 1, h1: int = 1) -> str:  # fmt: skip
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList",
           "itemListElement": [{"@type": "ListItem", "position": 1, "name": "בית", "item": f"{ORIGIN}/"}]}]  # fmt: skip
    if offers is not None:
        ld.append({"@type": "Product", "name": "x", "url": f"{ORIGIN}{path}", "offers": offers})
    return (
        '<html lang="he" dir="rtl"><head><title>כותרת</title>'
        f'<link rel="canonical" href="{canonical or ORIGIN + path}"/>'
        + (f'<meta name="robots" content="{robots}"/>' if robots else "")
        + f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
        "</head><body>"
        + "<h1>שלום</h1>" * h1
        + "".join('<time datetime="2026-10-22">22 באוקטובר 2026</time>' for _ in range(times))
        + (" המחיר הקובע הוא בקופה. " if checkout else "")
        + '<a href="/methodology">איך אנחנו משווים</a>'
        + "קינג סטור "
        + body
        + "</body></html>"
    )


def good_offers() -> list:
    return [
        {
            "@type": "Offer",
            "price": 1.18,
            "priceSpecification": {"@type": "UnitPriceSpecification", "price": 1.18},
        }
    ]


class Site:
    """Serves ``pages`` (path -> html) on localhost; unknown paths are 404."""

    def __init__(self, pages: dict[str, str], robots: str, sitemap: list[str]) -> None:
        pages = dict(pages)
        pages["/robots.txt"] = robots
        pages["/sitemap.xml"] = (
            "<urlset>" + "".join(f"<url><loc>{u}</loc></url>" for u in sitemap) + "</urlset>"
        )

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                body = pages.get(self.path)
                self.send_response(200 if body is not None else 404)
                kind = "text/plain" if self.path == "/robots.txt" else "text/html"
                self.send_header("content-type", kind)  # lower case, as Next.js sends it
                self.end_headers()
                self.wfile.write((body or "").encode("utf-8"))

            def log_message(self, *args):  # silence
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def export_dir(tmp_path: Path, products: list[dict], *, basket_status: str | None = None) -> Path:
    (tmp_path / "products.json").write_text(json.dumps({"products": products}), encoding="utf-8")
    cats = [{"slug": "dairy", "has_page": True}]
    (tmp_path / "categories.json").write_text(json.dumps({"categories": cats}), encoding="utf-8")
    months = [{"month": "2026-10", "status": basket_status}] if basket_status else []
    (tmp_path / "basket-index.json").write_text(json.dumps({"months": months}), encoding="utf-8")
    return tmp_path


def site_for(
    products: list[dict], *, index_unpriced: bool, broken: dict[str, str] | None = None
) -> Site:
    pages = {
        "/methodology": page("/methodology"),
        "/basket-index": page("/basket-index"),
        "/accessibility": page("/accessibility"),
        "/c/dairy": page("/c/dairy"),
    }
    listed = [f"{ORIGIN}/", f"{ORIGIN}/methodology", f"{ORIGIN}/basket-index",
              f"{ORIGIN}/accessibility", f"{ORIGIN}/c/dairy"]  # fmt: skip
    for p in products:
        path = f"/p/{p['slug']}"
        priced = bool(p["prices"])
        pages[path] = page(
            path,
            offers=good_offers() if priced else None,
            robots="" if (priced or index_unpriced) else "noindex, follow",
        )
        if priced or index_unpriced:
            listed.append(f"{ORIGIN}{path}")
    pages.update(broken or {})
    robots = f"User-Agent: *\nDisallow: /compare\nSitemap: {ORIGIN}/sitemap.xml\n"
    return Site(pages, robots, listed)


def run_crawl(
    tmp_path: Path, products: list[dict], *, index_unpriced: bool, broken=None, basket_status=None
):
    seo = export_dir(tmp_path, products, basket_status=basket_status)
    site = site_for(products, index_unpriced=index_unpriced, broken=broken)
    try:
        return seo_preview.crawl(site.base, seo, ORIGIN, index_unpriced)
    finally:
        site.close()


def failed(result: dict) -> set[str]:
    return {f"{f['area']}: {f['check']}" for f in result["failed"]}


# --- crawl: good and broken pages ----------------------------------------------------------------------------------


def test_a_good_export_passes_every_check(tmp_path) -> None:
    result = run_crawl(tmp_path, [PRODUCT, UNPRICED], index_unpriced=False)
    assert result["failed"] == [], result["failed"]
    assert (
        result["pages_fetched"] == 3 + 1 + 2 and result["sitemap_urls"] == 6
    )  # milk is noindex, unlisted


def test_unpriced_pages_are_listed_and_indexable_when_the_setting_says_so(tmp_path) -> None:
    result = run_crawl(tmp_path, [PRODUCT, UNPRICED], index_unpriced=True)
    assert result["failed"] == [], result["failed"]
    assert result["sitemap_urls"] == 7


def test_a_noindex_page_that_the_sitemap_lists_is_a_failure(tmp_path) -> None:
    bad = {"/p/eggs-l": page("/p/eggs-l", offers=good_offers(), robots="noindex")}
    result = run_crawl(tmp_path, [PRODUCT], index_unpriced=False, broken=bad)
    assert "/p/eggs-l: robots meta matches the sitemap" in failed(result)


def test_a_draft_basket_index_must_be_noindex_and_out_of_the_sitemap(tmp_path) -> None:
    # preview build with a draft month: noindex page, not in the sitemap, as the app does
    seo = export_dir(tmp_path, [PRODUCT], basket_status="draft")
    pages = {
        "/methodology": page("/methodology"),
        "/basket-index": page("/basket-index", robots="noindex, nofollow"),
        "/accessibility": page("/accessibility"),
        "/c/dairy": page("/c/dairy"),
        "/p/eggs-l": page("/p/eggs-l", offers=good_offers()),
    }
    listed = [
        f"{ORIGIN}{p}" for p in ("/", "/methodology", "/accessibility", "/c/dairy", "/p/eggs-l")
    ]
    site = Site(pages, f"Disallow: /compare\nSitemap: {ORIGIN}/sitemap.xml\n", listed)
    try:
        result = seo_preview.crawl(site.base, seo, ORIGIN, False)
    finally:
        site.close()
    assert result["failed"] == [], result["failed"]


@pytest.mark.parametrize(
    ("defect", "html", "expected"),
    [
        ("no checkout line", page("/p/eggs-l", offers=good_offers(), checkout=False),
         "says 'המחיר הקובע הוא בקופה' and links the methodology"),
        ("wrong canonical", page("/p/eggs-l", offers=good_offers(), canonical="https://x.example/p/eggs-l"),
         "canonical is this page on the preview origin"),
        ("two h1", page("/p/eggs-l", offers=good_offers(), h1=2), "a <title> and exactly one <h1>"),
        ("no date", page("/p/eggs-l", offers=good_offers(), times=0), "a visible update date (<time datetime>)"),
        ("offer price differs", page("/p/eggs-l", offers=[{"@type": "Offer", "price": 14.2,
                                                           "priceSpecification": {"@type": "UnitPriceSpecification", "price": 14.2}}]),
         "JSON-LD offers equal the exported prices (and exist only with prices)"),
        ("an offer without prices", page("/p/eggs-l", offers=[]), "JSON-LD offers equal the exported prices (and exist only with prices)"),
        ("two offers for one chain", page("/p/eggs-l", offers=good_offers() * 2), "JSON-LD offers equal the exported prices (and exist only with prices)"),
    ],
)  # fmt: skip
def test_each_page_defect_is_caught(tmp_path, defect, html, expected) -> None:
    result = run_crawl(tmp_path, [PRODUCT], index_unpriced=False, broken={"/p/eggs-l": html})
    assert f"/p/eggs-l: {expected}" in failed(result), defect


def test_broken_numbers_and_zero_prices_in_the_visible_text_are_caught(tmp_path) -> None:
    bad = {
        "/p/eggs-l": page("/p/eggs-l", offers=good_offers(), body="מחיר ₪ NaN"),
        "/c/dairy": page("/c/dairy", body="מחיר: ₪ 0.00 ליחידה"),
    }
    result = run_crawl(tmp_path, [PRODUCT], index_unpriced=False, broken=bad)
    names = failed(result)
    assert "all pages: no NaN, undefined, Infinity or null in the visible text" in names
    assert "all pages: no price of 0 shekels in the visible text" in names


def test_a_chain_that_is_not_on_its_page_is_caught(tmp_path) -> None:
    html = page("/p/eggs-l", offers=good_offers()).replace("קינג סטור", "")
    result = run_crawl(tmp_path, [PRODUCT], index_unpriced=False, broken={"/p/eggs-l": html})
    assert "/p/eggs-l: chain קינג סטור is on the page" in failed(result)


def test_a_missing_page_is_a_failure_not_a_crash(tmp_path) -> None:
    seo = export_dir(tmp_path, [PRODUCT])
    site = Site({"/methodology": page("/methodology")}, f"Sitemap: {ORIGIN}/sitemap.xml\n", [])
    try:
        result = seo_preview.crawl(site.base, seo, ORIGIN, False)
    finally:
        site.close()
    assert "/p/eggs-l: status 200" in failed(result)


# --- the parsing helpers --------------------------------------------------------------------------------------------


def test_page_parser_reads_head_tags_json_ld_and_visible_text_only() -> None:
    pg = seo_preview.Page()
    pg.feed(
        '<html lang="he" dir="rtl"><head><title>ת</title><link rel="canonical" href="https://x/p"/>'
        '<meta name="robots" content="noindex"/><script>var NaN = undefined</script>'
        '<script type="application/ld+json">{"a": 1}</script><style>.x{color:red}</style></head>'
        '<body><h1>א</h1><time datetime="2026-10-22">d</time><a href="/m">m</a>גלוי</body></html>'
    )
    assert pg.html["lang"] == "he" and pg.canonical == "https://x/p" and pg.robots == ["noindex"]
    assert pg.h1 == 1 and pg.times == ["2026-10-22"] and pg.links == ["/m"]
    assert pg.jsonld == ['{"a": 1}']
    assert "NaN" not in pg.visible and "color" not in pg.visible and "גלוי" in pg.visible


def test_offer_prices_and_urls_are_found_at_any_depth() -> None:
    node = [
        {"offers": [{"price": 1.5, "seller": {"url": "u1"}, "priceSpecification": {"price": 1.5}}]}
    ]
    assert sorted(seo_preview.offers_in(node, [])) == [1.5, 1.5]
    assert seo_preview.urls_in(node, []) == ["u1"]


def test_text_patterns() -> None:
    for bad in ("₪ NaN", "undefined", "Infinity", "[object Object]", "מחיר null"):
        assert seo_preview.BROKEN_TEXT.search(bad), bad
    for fine in ("nullable", "הבאנו", "₪ 12.90"):
        assert not seo_preview.BROKEN_TEXT.search(fine), fine
    for zero in ("₪ 0.00", "₪ 0", "₪0.0"):
        assert seo_preview.ZERO_PRICE.search(zero), zero
    for fine in ("₪ 0.50", "₪ 10.00", "₪ 0.05"):
        assert not seo_preview.ZERO_PRICE.search(fine), fine


def test_vitest_summary_lists_failures(tmp_path) -> None:
    report = tmp_path / "v.json"
    report.write_text(json.dumps({
        "numTotalTests": 3, "numPassedTests": 2, "numFailedTests": 1, "numTotalTestSuites": 2,
        "testResults": [{"name": "/a/b/x.test.ts", "assertionResults": [
            {"status": "passed", "fullName": "ok"},
            {"status": "failed", "fullName": "it breaks", "failureMessages": ["boom"]},
        ]}],
    }), encoding="utf-8")  # fmt: skip
    out = seo_preview.vitest_summary(report)
    assert (out["total"], out["passed"], out["failed"]) == (3, 2, 1)
    assert out["failures"] == [{"file": "x.test.ts", "test": "it breaks", "message": "boom"}]
    assert "error" in seo_preview.vitest_summary(tmp_path / "missing.json")


def test_render_export_reports_counts_findings_and_the_basket() -> None:
    info = {
        "audit": {
            "pages": {"total": 200, "category": 70, "product": 130}, "priced": 96, "unpriced": 149,
            "product_pages_priced": 60, "product_pages_unpriced": 70, "price_cells": 180,
            "estimated_cells": 40, "chains_per_priced_product": {"1": 30, "2": 40}, "errors": 1,
            "by_code": {"withheld": 2},
            "basket": {"month": "2026-10", "status": "draft", "chains": 5, "ranked": 0, "lines": 25,
                       "spread_pct": None, "lines_priced": {"רמי לוי": 19}, "totals": {},
                       "checks": [{"level": "error", "code": "too_few_chains", "message": "only 0"}]},
        },
        "findings": [{"code": "withheld", "subject": "eggs-l", "detail": "רמי לוי: chain_outlier"}],
    }  # fmt: skip
    text = "\n".join(seo_preview.render_export(info, "production semantics"))
    for needle in (
        "200 (70 category, 130 product)",
        "96 / 149",
        "60 / 70",
        "too_few_chains",
        "eggs-l",
        "19 of 25",
    ):
        assert needle in text, needle
    assert "Failed" in "\n".join(seo_preview.render_export({"error": "audit failed"}, "x"))
    assert seo_preview.render_export(None, "x") == []
