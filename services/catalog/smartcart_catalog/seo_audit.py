"""Audit an SEO export (``categories.json``, ``products.json``, ``basket-index.json``) before it is built.

``smartcart-catalog seo-audit --dir DIR`` reads what ``export-seo`` and ``basket-index`` wrote and
reports what a reader of the pages would see: page counts, priced against unpriced, and every
number that looks implausible. It reads only the files, so it runs on the committed snapshot, on a
real-day export and in tests on real-shaped rows. It changes nothing and does not decide what is
published: ``export_seo.screen_prices`` is what keeps a bad row off a page, this reports what is
left that still looks wrong (and what was held back).

Thresholds are proposals (constants below), not measured values. Codes:

====================  =====================================================================
``bad_price``         a unit price that is zero, negative, not a number, or not finite
``above_cap``         a unit price above the sanity cap for its unit (``UNIT_CAPS``)
``chain_outlier``     a chain's median is ``CHAIN_RATIO`` times (or 1/times) the median of the
                      other chains' medians; with two chains, they differ by that much
``store_spread``      a chain's median is ``STORE_RATIO`` times its own cheapest store
``missing_field``     a product, price or category lacks a field the page reads
``bad_name``          an empty name, a very long one, or control characters
``bad_date``          a price date that does not parse, or lies after the export
``old_price``         a price date older than ``OLD_PRICE_DAYS`` (listed, not an error)
``no_stores``         a price row that says it comes from no store
``withheld``          a price the export held back (``products[].withheld``), by reason
``basket_line``       a basket line that costs ``MAX_LINE_RATIO`` times more at one chain
====================  =====================================================================
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from smartcart_catalog.export_seo import CHAIN_RATIO as _CHAIN_RATIO
from smartcart_catalog.export_seo import STORE_RATIO as _STORE_RATIO
from smartcart_catalog.export_seo import UNIT_CAPS as _UNIT_CAPS

UNIT_CAPS: dict[str, float] = {unit: float(cap) for unit, cap in _UNIT_CAPS.items()}
CHAIN_RATIO = float(_CHAIN_RATIO)
STORE_RATIO = float(_STORE_RATIO)
"""The same thresholds the export screens with: after the screen, none of them should fire."""
OLD_PRICE_DAYS = 45
NAME_MAX = 80
SEVERE = ("bad_price", "above_cap", "chain_outlier", "missing_field", "bad_date", "bad_name")
"""Codes that count as errors; the rest are listed as notes."""


def _finding(code: str, subject: str, detail: str) -> dict[str, str]:
    return {"code": code, "subject": subject, "detail": detail}


def _parse(moment: Any) -> datetime | None:
    if not isinstance(moment, str):
        return None
    try:
        parsed = datetime.fromisoformat(moment.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _name_problem(name: Any) -> str | None:
    if not isinstance(name, str) or not name.strip():
        return "empty"
    if len(name) > NAME_MAX:
        return f"{len(name)} characters"
    if any(ord(ch) < 32 or 0x7F <= ord(ch) < 0xA0 for ch in name):
        return "control characters"
    return None


def audit_products(
    products: Mapping[str, Any], *, now: datetime | None = None
) -> list[dict[str, str]]:
    """Findings for every product row of ``products.json``."""
    now = now or _parse(products.get("generated_at")) or datetime.now(UTC)
    found: list[dict[str, str]] = []
    seen: Counter[str] = Counter()
    for p in products.get("products", []):
        slug = p.get("slug") or "?"
        seen[slug] += 1
        for key in ("slug", "name_he", "base_unit", "taxonomy_id", "path"):
            if not p.get(key):
                found.append(_finding("missing_field", slug, f"product has no {key}"))
        bad = _name_problem(p.get("name_he"))
        if bad:
            found.append(_finding("bad_name", slug, f"product name: {bad}"))
        unit = p.get("base_unit")
        prices = p.get("prices") or []
        if p.get("no_prices_yet") != (not prices):
            found.append(_finding("missing_field", slug, "no_prices_yet disagrees with prices"))
        if prices and not p.get("price_valid_from"):
            found.append(_finding("missing_field", slug, "prices without price_valid_from"))
        for w in p.get("withheld") or []:
            found.append(_finding("withheld", slug, f"{w.get('chain_name') or w.get('chain_id')}: "
                                  f"{w.get('reason')} ({w.get('detail', '')})".strip()))  # fmt: skip
        medians: dict[str, float] = {}
        for c in prices:
            where = f"{slug} / {c.get('chain_name') or c.get('chain_id') or '?'}"
            for key in ("chain_id", "chain_name", "price_valid_from"):
                if not c.get(key):
                    found.append(_finding("missing_field", where, f"price has no {key}"))
            bad = _name_problem(c.get("chain_name"))
            if bad:
                found.append(_finding("bad_name", where, f"chain name: {bad}"))
            median, low = c.get("median_unit_price"), c.get("min_unit_price")
            if not (_is_number(median) and _is_number(low)) or median <= 0 or low <= 0:
                found.append(_finding("bad_price", where, f"median {median!r}, cheapest {low!r}"))
                continue
            medians[c.get("chain_id") or where] = float(median)
            cap = UNIT_CAPS.get(unit)
            if cap is not None and median > cap:
                found.append(_finding("above_cap", where, f"{median:.2f} per {unit} (cap {cap:g})"))
            if median / low >= STORE_RATIO:
                found.append(_finding("store_spread", where,
                                      f"median {median:.2f} is {median / low:.1f} times the "
                                      f"cheapest store {low:.2f}"))  # fmt: skip
            if not c.get("stores"):
                found.append(_finding("no_stores", where, "stores is 0"))
            when = _parse(c.get("price_valid_from"))
            if when is None:
                found.append(_finding("bad_date", where, f"{c.get('price_valid_from')!r}"))
            elif when > now:
                found.append(
                    _finding("bad_date", where, f"{c['price_valid_from']} is after the export")
                )
            elif (now - when).days > OLD_PRICE_DAYS:
                found.append(_finding("old_price", where, f"{(now - when).days} days old"))
        if len(medians) >= 2:
            for chain, value in medians.items():
                others = [v for k, v in medians.items() if k != chain]
                ref = statistics.median(others)
                ratio = max(value / ref, ref / value)
                if ratio >= CHAIN_RATIO:
                    found.append(_finding("chain_outlier", f"{slug} / {chain}",
                                          f"{value:.2f} per {unit} against {ref:.2f} at the "
                                          f"other chain(s): {ratio:.1f} times"))  # fmt: skip
    for slug, n in seen.items():
        if n > 1:
            found.append(_finding("missing_field", slug, f"slug appears {n} times"))
    return found


def audit_categories(categories: Mapping[str, Any]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for c in categories.get("categories", []):
        slug = c.get("slug") or "?"
        for key in ("slug", "name_he"):
            if not c.get(key):
                found.append(_finding("missing_field", slug, f"category has no {key}"))
        bad = _name_problem(c.get("name_he"))
        if bad:
            found.append(_finding("bad_name", slug, f"category name: {bad}"))
    return found


def audit_basket(index: Mapping[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Findings and a summary for the newest month of ``basket-index.json`` (draft or published)."""
    from smartcart_catalog.basket_index import line_outliers

    months = index.get("months") or []
    if not months:
        return [], {"month": None}
    m = months[0]
    found = [
        _finding("basket_line", f"{slug}", f"{high[1]} {high[0]:.2f} against {low[1]} {low[0]:.2f}")
        for slug, low, high in line_outliers(m.get("chains", []))
    ]
    ranked = [c for c in m.get("chains", []) if c.get("complete")]
    summary = {
        "month": m.get("month"),
        "status": m.get("status"),
        "chains": len(m.get("chains", [])),
        "ranked": len(ranked),
        "lines": (index.get("basket") or {}).get("item_count"),
        "lines_priced": {c.get("name"): c.get("items_priced") for c in m.get("chains", [])},
        "spread_pct": m.get("spread_pct"),
        "totals": {c.get("name"): c.get("total") for c in ranked},
        "checks": [
            {k: c.get(k) for k in ("level", "code", "message")} for c in m.get("checks", [])
        ],
    }
    return found, summary


def audit_dir(directory: Path) -> dict[str, Any]:
    """The full audit of an export directory: counts, findings by code, the findings themselves."""
    load = lambda name: json.loads((directory / name).read_text(encoding="utf-8"))  # noqa: E731
    products = load("products.json")
    categories = load("categories.json")
    basket = load("basket-index.json") if (directory / "basket-index.json").exists() else {}
    rows = products.get("products", [])
    priced = [p for p in rows if p.get("prices")]
    page_rows = [p for p in rows if p.get("has_page")]
    findings = audit_products(products) + audit_categories(categories)
    basket_findings, basket_summary = audit_basket(basket)
    findings += basket_findings
    by_code = Counter(f["code"] for f in findings)
    chains_per_product = Counter(len(p["prices"]) for p in priced)
    return {
        "generated_at": products.get("generated_at"),
        "pages": {
            "category": categories.get("page_count", 0),
            "product": products.get("page_count", 0),
            "total": categories.get("page_count", 0) + products.get("page_count", 0),
        },
        "canonicals": len(rows),
        "priced": len(priced),
        "unpriced": len(rows) - len(priced),
        "product_pages_priced": sum(1 for p in page_rows if p.get("prices")),
        "product_pages_unpriced": sum(1 for p in page_rows if not p.get("prices")),
        "chains_per_priced_product": {str(k): v for k, v in sorted(chains_per_product.items())},
        "price_cells": sum(len(p["prices"]) for p in priced),
        "estimated_cells": sum(1 for p in priced for c in p["prices"] if c.get("is_estimated")),
        "basket": basket_summary,
        "errors": sum(n for code, n in by_code.items() if code in SEVERE),
        "by_code": dict(sorted(by_code.items())),
        "findings": findings,
    }


def render_audit(audit: Mapping[str, Any], limit: int = 60) -> str:
    pages = audit["pages"]
    lines = [
        "| | |",
        "|---|---|",
        f"| Pages generated | {pages['total']} ({pages['category']} category, {pages['product']} product) |",
        f"| Canonicals priced / unpriced | {audit['priced']} / {audit['unpriced']} |",
        f"| Product pages priced / unpriced | {audit['product_pages_priced']} / {audit['product_pages_unpriced']} |",
        f"| Price cells (chain x product) | {audit['price_cells']} ({audit['estimated_cells']} estimated) |",
        f"| Chains per priced product | {', '.join(f'{k}: {v}' for k, v in audit['chains_per_priced_product'].items()) or '-'} |",
        f"| Findings that count as errors | {audit['errors']} |",
        f"| Findings by code | {', '.join(f'{k} {v}' for k, v in audit['by_code'].items()) or 'none'} |",
        "",
    ]
    findings = audit["findings"]
    if findings:
        lines += ["| Code | Subject | Detail |", "|---|---|---|"]
        for f in findings[:limit]:
            lines.append(f"| {f['code']} | {f['subject']} | {f['detail']} |")
        if len(findings) > limit:
            lines.append(f"| ... | {len(findings) - limit} more | in the JSON |")
        lines.append("")
    return "\n".join(lines)


def severe(findings: Sequence[Mapping[str, str]]) -> list[Mapping[str, str]]:
    return [f for f in findings if f["code"] in SEVERE]
