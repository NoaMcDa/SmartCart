"""Export the catalog as static data for the SEO pages and the methodology page (issue #35, #21).

``smartcart-catalog export-seo --out apps/web/public/seo`` writes three files the Next.js app
reads at build time (``generateStaticParams``), so the site builds without a database:

* ``categories.json``  taxonomy levels 1 and 2 with the number of MVP canonicals under each;
* ``products.json``    every MVP canonical: slug, Hebrew name, taxonomy path, base unit, critical
  attributes, and, when ``effective_prices`` has rows for it, the minimum and median unit price
  per chain and the latest ``price_valid_from``; otherwise ``prices`` is null and
  ``no_prices_yet`` is true;
* ``quality.json``     the public matching-quality metric from the latest ``match_runs`` row of
  kind ``evaluate`` (precision per flexibility level, sample size, run date, synthetic flag).

Page budget (decision D8: 50 to 200 pages). A page exists for every level 1 and level 2 category
that has canonicals, plus the best-ranked canonicals until ``max_pages`` is reached. Every MVP
canonical is still listed in ``products.json`` (``has_page`` says whether it has its own page).

Prices follow the app's logic: the "any brand" row of ``effective_prices`` per store, physical
stores only, promos included unless they need a club (then the row's ``noclub`` option is used,
or the store is left out). The unit is the canonical's base unit (per 100 g, 100 ml, unit, or kg
for weighed goods, which are flagged estimated).

Everything except reading the database is pure, so the same builders also run from the seed files
(``--from-files``): categories and products without prices, no database needed.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from smartcart_catalog.seed import Catalog

MAX_PAGES = 200
MIN_PAGES = 50
PRICE_LEVEL = "any_brand"
CENT = Decimal("0.01")

QUALITY_FILE = "quality.json"
CATEGORIES_FILE = "categories.json"
PRODUCTS_FILE = "products.json"


@dataclass(frozen=True)
class TaxonomyRow:
    id: str
    name_he: str
    name_en: str | None
    sort: int


@dataclass(frozen=True)
class CanonicalRow:
    slug: str
    display_name_he: str
    taxonomy_id: str
    product_type: str
    base_unit: str
    critical_attrs: Mapping[str, Any]
    rank: int | None


@dataclass(frozen=True)
class PriceRow:
    """One store's current any-brand unit price for one canonical, per base unit."""

    canonical_slug: str
    chain_id: str
    chain_name: str
    store_id: int
    unit_price: Decimal
    is_estimated: bool
    price_valid_from: datetime
    computed_at: datetime | None = None


def category_slug(taxonomy_id: str) -> str:
    """``dairy.milk`` -> ``dairy-milk``. Ids are lowercase ASCII segments, so this is reversible."""
    return taxonomy_id.replace(".", "-")


# --- builders (pure) -----------------------------------------------------------------------------


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _money(value: Decimal) -> float:
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))


def _under(taxonomy_id: str, node_id: str) -> bool:
    return taxonomy_id == node_id or taxonomy_id.startswith(node_id + ".")


def build_categories(
    taxonomy: Sequence[TaxonomyRow],
    canonicals: Sequence[CanonicalRow],
    generated_at: datetime,
) -> dict[str, Any]:
    nodes = [n for n in sorted(taxonomy, key=lambda n: n.sort) if n.id.count(".") <= 1]
    names = {n.id: n.name_he for n in nodes}
    out: list[dict[str, Any]] = []
    for node in nodes:
        level = node.id.count(".") + 1
        parent = node.id.rsplit(".", 1)[0] if level == 2 else None
        count = sum(1 for c in canonicals if _under(c.taxonomy_id, node.id))
        out.append(
            {
                "slug": category_slug(node.id),
                "id": node.id,
                "level": level,
                "parent_slug": category_slug(parent) if parent else None,
                "name_he": node.name_he,
                "name_en": node.name_en,
                "canonical_count": count,
                "has_page": count > 0,
                "path": (
                    [{"slug": category_slug(parent), "name_he": names[parent]}] if parent else []
                ),
            }
        )
    return {
        "generated_at": _iso(generated_at),
        "count": len(out),
        "page_count": sum(1 for c in out if c["has_page"]),
        "categories": out,
    }


def aggregate_prices(rows: Iterable[PriceRow]) -> dict[str, dict[str, Any]]:
    """Per canonical slug: ``{"prices": [per chain], "price_valid_from": iso}``.

    Per chain: minimum and median unit price over the chain's stores, the number of stores, the
    latest price date, and whether any store's price is an estimate (weighed goods).
    """
    by_product: dict[str, dict[str, list[PriceRow]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_product[r.canonical_slug][r.chain_id].append(r)
    out: dict[str, dict[str, Any]] = {}
    for slug, chains in by_product.items():
        entries = []
        latest: datetime | None = None
        for chain_id, rs in chains.items():
            prices = [r.unit_price for r in rs]
            newest = max(r.price_valid_from for r in rs)
            latest = newest if latest is None else max(latest, newest)
            entries.append(
                {
                    "chain_id": chain_id,
                    "chain_name": rs[0].chain_name,
                    "min_unit_price": _money(min(prices)),
                    "median_unit_price": _money(Decimal(statistics.median(prices))),
                    "stores": len({r.store_id for r in rs}),
                    "is_estimated": any(r.is_estimated for r in rs),
                    "price_valid_from": _iso(newest),
                }
            )
        entries.sort(key=lambda e: (e["median_unit_price"], e["chain_id"]))
        assert latest is not None
        out[slug] = {"prices": entries, "price_valid_from": _iso(latest)}
    return out


def build_products(
    canonicals: Sequence[CanonicalRow],
    taxonomy: Sequence[TaxonomyRow],
    prices: Mapping[str, dict[str, Any]],
    *,
    categories: Mapping[str, Any],
    generated_at: datetime,
    max_pages: int = MAX_PAGES,
) -> dict[str, Any]:
    names = {n.id: n.name_he for n in taxonomy}
    ordered = sorted(canonicals, key=lambda c: (c.rank is None, c.rank or 0, c.slug))
    category_pages = categories["page_count"]
    budget = max(0, max_pages - category_pages)
    with_page = {c.slug for c in ordered[:budget]}
    products = []
    for c in ordered:
        parts = c.taxonomy_id.split(".")
        path = []
        for i in range(1, len(parts) + 1):
            node_id = ".".join(parts[:i])
            path.append(
                {
                    "id": node_id,
                    "name_he": names.get(node_id, node_id),
                    # only levels 1 and 2 have category pages
                    "slug": category_slug(node_id) if i <= 2 else None,
                }
            )
        priced = prices.get(c.slug)
        products.append(
            {
                "slug": c.slug,
                "name_he": c.display_name_he,
                "taxonomy_id": c.taxonomy_id,
                "path": path,
                "product_type": c.product_type,
                "base_unit": c.base_unit,
                "critical_attrs": dict(c.critical_attrs),
                "rank": c.rank,
                "has_page": c.slug in with_page,
                "no_prices_yet": priced is None,
                "prices": priced["prices"] if priced else None,
                "price_valid_from": priced["price_valid_from"] if priced else None,
            }
        )
    return {
        "generated_at": _iso(generated_at),
        "count": len(products),
        "page_count": len(with_page),
        "priced_count": sum(1 for p in products if not p["no_prices_yet"]),
        "products": products,
    }


def build_quality(row: Mapping[str, Any] | None, generated_at: datetime) -> dict[str, Any]:
    """The public quality metric from the latest ``evaluate`` run (``match_runs`` row).

    ``row`` has ``id``, ``finished_at`` and ``metrics`` (the JSON ``evaluate.run_evaluation``
    stores). With no run the file says so, and the page shows no number rather than inventing one.
    """
    if row is None:
        return {"generated_at": _iso(generated_at), "available": False}
    metrics = row["metrics"]
    support = metrics.get("support", {})
    precision = {
        lvl: metrics["precision"][lvl] for lvl in ("exact", "any_brand", "close")
        if metrics.get("precision", {}).get(lvl) is not None
    }  # fmt: skip
    sample = {lvl: int(support.get(f"predicted_{lvl}", 0)) for lvl in precision}
    return {
        "generated_at": _iso(generated_at),
        "available": True,
        "run_id": row["id"],
        "measured_at": _iso(row["finished_at"]),
        "precision": precision,
        "sample": sample,
        "gold_items": int(support.get("items", 0)),
        "gold_pairs": int(support.get("pairs", 0)),
        "synthetic": bool(metrics.get("synthetic_gold_set", True)),
        "judge": metrics.get("judge"),
        "target_any_brand": 0.98,
    }


# --- readers -------------------------------------------------------------------------------------


def rows_from_catalog(catalog: Catalog) -> tuple[list[TaxonomyRow], list[CanonicalRow]]:
    taxonomy = [TaxonomyRow(n.id, n.name_he, n.name_en, n.sort) for n in catalog.taxonomy.nodes]
    canonicals = [
        CanonicalRow(c.slug, c.display_name_he, c.taxonomy_id, c.product_type, c.base_unit,
                     c.critical_attrs, c.rank)
        for c in catalog.canonicals
        if c.is_mvp
    ]  # fmt: skip
    return taxonomy, canonicals


def read_taxonomy(conn: psycopg.Connection) -> list[TaxonomyRow]:
    return [
        TaxonomyRow(*r)
        for r in conn.execute("SELECT id, name_he, name_en, sort FROM taxonomy ORDER BY sort, id")
    ]


def read_canonicals(conn: psycopg.Connection) -> list[CanonicalRow]:
    return [
        CanonicalRow(*r)
        for r in conn.execute(
            "SELECT slug, display_name_he, taxonomy_id, product_type, base_unit, critical_attrs,"
            " rank FROM canonical_products WHERE is_mvp ORDER BY rank NULLS LAST, slug"
        )
    ]


UNIT_PRICES_SQL = """
SELECT cp.slug, c.id AS chain_id, c.name AS chain_name, s.id AS store_id,
       CASE WHEN ep.club_required THEN (ep.noclub->>'effective_unit_price')::numeric
            ELSE ep.effective_unit_price END AS unit_price,
       CASE WHEN ep.club_required THEN coalesce((ep.noclub->>'is_estimated')::boolean, false)
            ELSE ep.is_estimated END AS is_estimated,
       CASE WHEN ep.club_required
            THEN coalesce((ep.noclub->>'price_valid_from')::timestamptz, ep.price_valid_from)
            ELSE ep.price_valid_from END AS price_valid_from,
       ep.computed_at
FROM effective_prices ep
JOIN canonical_products cp ON cp.id = ep.canonical_id AND cp.is_mvp
JOIN stores s ON s.id = ep.store_id AND s.channel = 'physical'
JOIN chains c ON c.id = s.chain_id
WHERE ep.flex_level = %(level)s
  AND (NOT ep.club_required OR ep.noclub IS NOT NULL)
ORDER BY cp.slug, c.id, s.id
"""


def read_unit_prices(conn: psycopg.Connection, level: str = PRICE_LEVEL) -> list[PriceRow]:
    """Current unit prices per (canonical, store) from ``effective_prices``, club-free."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(UNIT_PRICES_SQL, {"level": level})
        return [
            PriceRow(r["slug"], r["chain_id"], r["chain_name"], r["store_id"], r["unit_price"],
                     bool(r["is_estimated"]), r["price_valid_from"], r["computed_at"])
            for r in cur.fetchall()
        ]  # fmt: skip


def read_latest_evaluation(conn: psycopg.Connection) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, finished_at, metrics FROM match_runs"
            " WHERE kind = 'evaluate' AND finished_at IS NOT NULL"
            " ORDER BY finished_at DESC, id DESC LIMIT 1"
        )
        return cur.fetchone()


# --- writing -------------------------------------------------------------------------------------


def write_json(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class ExportResult:
    categories: dict[str, Any]
    products: dict[str, Any]
    quality: dict[str, Any] | None

    @property
    def pages(self) -> int:
        return self.categories["page_count"] + self.products["page_count"]


def export_seo(
    out: Path,
    taxonomy: Sequence[TaxonomyRow],
    canonicals: Sequence[CanonicalRow],
    prices: Iterable[PriceRow] = (),
    quality_row: Mapping[str, Any] | None = None,
    *,
    write_quality: bool = True,
    max_pages: int = MAX_PAGES,
    now: datetime | None = None,
) -> ExportResult:
    """Build and write the three files. With ``write_quality=False`` quality.json is not touched
    (the seed-file mode has no ``match_runs``)."""
    now = now or datetime.now(UTC)
    categories = build_categories(taxonomy, canonicals, now)
    products = build_products(
        canonicals, taxonomy, aggregate_prices(prices),
        categories=categories, generated_at=now, max_pages=max_pages,
    )  # fmt: skip
    write_json(out / CATEGORIES_FILE, categories)
    write_json(out / PRODUCTS_FILE, products)
    quality = None
    if write_quality:
        quality = build_quality(quality_row, now)
        write_json(out / QUALITY_FILE, quality)
    return ExportResult(categories, products, quality)


def export_from_db(
    conn: psycopg.Connection, out: Path, *, max_pages: int = MAX_PAGES, now: datetime | None = None
) -> ExportResult:
    return export_seo(
        out, read_taxonomy(conn), read_canonicals(conn), read_unit_prices(conn),
        read_latest_evaluation(conn), max_pages=max_pages, now=now,
    )  # fmt: skip


def export_from_files(
    catalog: Catalog, out: Path, *, max_pages: int = MAX_PAGES, now: datetime | None = None
) -> ExportResult:
    taxonomy, canonicals = rows_from_catalog(catalog)
    return export_seo(out, taxonomy, canonicals, write_quality=False, max_pages=max_pages, now=now)
