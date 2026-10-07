"""Monthly basket index (issue #44, decision D8, D10).

A fixed basket of MVP canonical products is priced in every chain and the chain totals are
published, so the press can quote them (Ater and Rigbi found that price transparency reached
consumers through press coverage, not comparison sites: docs/product-and-market.md).

Method (documented for the public on /methodology and /basket-index):

* The basket is versioned (``BASKET_V1``) and does not change inside a version, so months are
  comparable. A line is an amount in the canonical's base unit (2 liters of 3% milk is 20 x
  100 ml), priced at the unit price, so pack sizes do not distort the total (D6).
* A chain's price for a line is the **median** over its physical stores of the app's effective
  unit price at the "any brand" level (``effective_prices``): promos are included unless they
  need a club membership, club-only prices are left out, online stores are left out. Weighed
  goods are per kg and flagged estimated.
* A chain is ranked only when it prices every line (otherwise totals are not comparable); the
  others are listed with their missing items. Delta is the difference from the cheapest ranked
  chain. The index is never presented as a saving versus the most expensive chain (D7).
* ``effective_prices`` holds only the current state, so a month's result is a snapshot taken when
  the command runs and is stored in ``basket-index.json`` and the Markdown report; the stored
  files are the record.

Pre-publication checks (``run_checks``) flag problems before a month goes public. A month is
``published`` only when a reviewer name is given and no error check is open (an error can be
acknowledged by name after a human looked at it); otherwise it is a ``draft`` that the web page
does not show. The thresholds below are proposals, not measured values.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from smartcart_catalog.export_seo import PriceRow

INDEX_FILE = "basket-index.json"
CENT = Decimal("0.01")

MAX_MONTHLY_CHANGE = Decimal("0.15")
"""Proposal: a chain total moving more than 15% against the previous published month is an error."""
MAX_SPREAD = Decimal("0.50")
"""Proposal: cheapest to dearest more than 50% apart is implausible (the verified 67-item gap
between Rami Levy and Tiv Taam was 26%)."""
MAX_PRECOMPUTE_AGE = timedelta(hours=48)
"""Proposal: effective prices older than two days mean the nightly job is not running."""
MIN_CHAINS = 2


@dataclass(frozen=True)
class BasketLine:
    slug: str
    amount: Decimal
    """Quantity in the canonical's base unit (100 ml, 100 g, unit, or kg)."""
    label_he: str
    """What the amount means on a shelf, for readers."""


BASKET_VERSION = 1
BASKET_V1: tuple[BasketLine, ...] = (
    BasketLine("milk-fresh-3", Decimal(20), "2 ליטר"),
    BasketLine("cottage-5", Decimal(5), "2 גביעים של 250 גרם"),
    BasketLine("white-cheese-5", Decimal(5), "500 גרם"),
    BasketLine("yellow-cheese-sliced-28", Decimal(4), "400 גרם"),
    BasketLine("yogurt-plain-3", Decimal(8), "800 גרם"),
    BasketLine("butter", Decimal(2), "200 גרם"),
    BasketLine("eggs-l", Decimal(12), "12 ביצים"),
    BasketLine("chicken-breast-fresh", Decimal(1), "ק״ג אחד"),
    BasketLine("hummus-plain", Decimal(4), "400 גרם"),
    BasketLine("tomato", Decimal("1.5"), "1.5 ק״ג"),
    BasketLine("cucumber", Decimal(1), "ק״ג אחד"),
    BasketLine("onion", Decimal(1), "ק״ג אחד"),
    BasketLine("potato", Decimal(2), "2 ק״ג"),
    BasketLine("banana", Decimal(1), "ק״ג אחד"),
    BasketLine("bread-standard", Decimal("7.5"), "כיכר של 750 גרם"),
    BasketLine("pita", Decimal(10), "10 פיתות"),
    BasketLine("rice-persian", Decimal(10), "ק״ג אחד"),
    BasketLine("pasta-spaghetti", Decimal(5), "500 גרם"),
    BasketLine("sugar-white", Decimal(10), "ק״ג אחד"),
    BasketLine("canola-oil", Decimal(10), "ליטר אחד"),
    BasketLine("tuna-in-oil", Decimal("4.8"), "3 קופסאות של 160 גרם"),
    BasketLine("mineral-water", Decimal(60), "6 ליטר"),
    BasketLine("bamba", Decimal(2), "200 גרם"),
    BasketLine("chocolate-milk", Decimal(10), "ליטר אחד"),
    BasketLine("toilet-paper", Decimal(24), "24 גלילים"),
)
"""25 staples, all among the best-ranked MVP canonicals by the estimated frequency rank
(docs/catalog.md), with amounts for a small household's week. The choice of items and amounts is a judgement (estimate),
not a measured basket; it is fixed for version 1. Change it only by adding BASKET_V2."""


# --- computing -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class ChainResult:
    chain_id: str
    name: str
    total: Decimal | None
    items_priced: int
    missing: tuple[str, ...]
    estimated_items: int
    stores: int
    lines: dict[str, Decimal]
    """slug -> chain median unit price per base unit."""

    @property
    def complete(self) -> bool:
        return not self.missing


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def price_chains(prices: Iterable[PriceRow], basket: Sequence[BasketLine]) -> list[ChainResult]:
    """Chain totals for ``basket``: median store per line, then the weighted sum."""
    wanted = {line.slug for line in basket}
    cells: dict[str, dict[str, list[PriceRow]]] = defaultdict(lambda: defaultdict(list))
    names: dict[str, str] = {}
    stores: dict[str, set[int]] = defaultdict(set)
    for p in prices:
        if p.canonical_slug not in wanted:
            continue
        cells[p.chain_id][p.canonical_slug].append(p)
        names[p.chain_id] = p.chain_name
        stores[p.chain_id].add(p.store_id)
    results = []
    for chain_id in sorted(cells):
        lines: dict[str, Decimal] = {}
        estimated = 0
        total = Decimal(0)
        missing = []
        for line in basket:
            rows = cells[chain_id].get(line.slug)
            if not rows:
                missing.append(line.slug)
                continue
            unit_price = Decimal(statistics.median([r.unit_price for r in rows]))
            lines[line.slug] = unit_price
            total += unit_price * line.amount
            estimated += any(r.is_estimated for r in rows)
        results.append(
            ChainResult(
                chain_id=chain_id,
                name=names[chain_id],
                total=_money(total) if not missing else None,
                items_priced=len(lines),
                missing=tuple(missing),
                estimated_items=estimated,
                stores=len(stores[chain_id]),
                lines=lines,
            )
        )
    return results


def month_document(
    month: str,
    basket: Sequence[BasketLine],
    prices: Sequence[PriceRow],
    *,
    computed_at: datetime,
) -> dict[str, Any]:
    """The month's result as stored in ``basket-index.json`` (before checks and review)."""
    chains = price_chains(prices, basket)
    ranked = sorted((c for c in chains if c.total is not None), key=lambda c: (c.total, c.chain_id))
    cheapest = ranked[0].total if ranked else None
    rows: list[dict[str, Any]] = []
    for c in ranked:
        assert c.total is not None and cheapest is not None
        rows.append(
            {
                "chain_id": c.chain_id,
                "name": c.name,
                "total": float(c.total),
                "delta_vs_cheapest": float(_money(c.total - cheapest)),
                "delta_pct": float(((c.total / cheapest - 1) * 100).quantize(Decimal("0.1"))),
                "items_priced": c.items_priced,
                "estimated_items": c.estimated_items,
                "stores": c.stores,
                "complete": True,
                "missing": [],
            }
        )
    for c in sorted((c for c in chains if c.total is None), key=lambda c: c.chain_id):
        rows.append(
            {
                "chain_id": c.chain_id,
                "name": c.name,
                "total": None,
                "delta_vs_cheapest": None,
                "delta_pct": None,
                "items_priced": c.items_priced,
                "estimated_items": c.estimated_items,
                "stores": c.stores,
                "complete": False,
                "missing": list(c.missing),
            }
        )
    in_basket = {b.slug for b in basket}
    used = [p for p in prices if p.canonical_slug in in_basket]
    dates = [p.price_valid_from for p in used]
    computed = [p.computed_at for p in used if p.computed_at is not None]
    spread = (
        float(((ranked[-1].total / cheapest - 1) * 100).quantize(Decimal("0.1")))
        if len(ranked) >= 2 and cheapest
        else None
    )
    return {
        "month": month,
        "basket_version": BASKET_VERSION,
        "computed_at": _iso(computed_at),
        "price_date": _iso(max(dates)) if dates else None,
        "prices_computed_at": _iso(max(computed)) if computed else None,
        "cheapest_chain_id": ranked[0].chain_id if ranked else None,
        "spread_pct": spread,
        "chains": rows,
        "checks": [],
        "acknowledged": [],
        "reviewed_by": None,
        "status": "draft",
    }


# --- pre-publication checks ----------------------------------------------------------------------


def run_checks(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    *,
    now: datetime,
) -> list[dict[str, str]]:
    """Flags for a human before the month is released.

    ``level`` is ``error`` (blocks publication until acknowledged) or ``warning`` (listed).
    """
    checks: list[dict[str, str]] = []

    def flag(level: str, code: str, message: str, chain: str | None = None) -> None:
        checks.append({"level": level, "code": code, "message": message, "chain_id": chain or ""})

    if not current["chains"]:
        flag("error", "no_prices", "no basket item has a price in any chain")
        return checks
    ranked = [c for c in current["chains"] if c["complete"]]
    for c in current["chains"]:
        if not c["complete"]:
            flag(
                "warning",
                "missing_items",
                f"{c['name']} has no price for {len(c['missing'])} basket items "
                f"({', '.join(c['missing'])}); it is listed but not ranked",
                c["chain_id"],
            )
        if c["estimated_items"]:
            flag(
                "warning",
                "estimated_items",
                f"{c['name']}: {c['estimated_items']} lines use estimated weighed-goods prices",
                c["chain_id"],
            )
    if len(ranked) < MIN_CHAINS:
        flag(
            "error",
            "too_few_chains",
            f"only {len(ranked)} chain(s) price the whole basket; at least {MIN_CHAINS} needed",
        )
    spread = current.get("spread_pct")
    if spread is not None and Decimal(str(spread)) > MAX_SPREAD * 100:
        flag(
            "error",
            "implausible_spread",
            f"cheapest and dearest chain differ by {spread}% (limit {MAX_SPREAD * 100}%)",
        )
    computed = current.get("prices_computed_at")
    if computed is None:
        flag("warning", "no_computed_at", "effective_prices has no computed_at to check freshness")
    else:
        age = now - datetime.fromisoformat(computed.replace("Z", "+00:00"))
        if age > MAX_PRECOMPUTE_AGE:
            flag(
                "error",
                "stale_prices",
                f"effective prices were last computed {computed}, "
                f"{int(age.total_seconds() // 3600)} hours before this run "
                f"(limit {int(MAX_PRECOMPUTE_AGE.total_seconds() // 3600)})",
            )
    if previous is not None:
        before = {c["chain_id"]: c for c in previous["chains"] if c["total"] is not None}
        if previous.get("basket_version") != current["basket_version"]:
            flag(
                "warning",
                "basket_version_changed",
                "the basket version differs from the previous month; totals are not comparable",
            )
        else:
            for c in ranked:
                prev = before.get(c["chain_id"])
                if prev is None:
                    flag("warning", "new_chain", f"{c['name']} was not ranked last month",
                         c["chain_id"])  # fmt: skip
                    continue
                change = Decimal(str(c["total"])) / Decimal(str(prev["total"])) - 1
                if abs(change) > MAX_MONTHLY_CHANGE:
                    flag(
                        "error",
                        "implausible_change",
                        f"{c['name']} total moved {change * 100:+.1f}% against "
                        f"{previous['month']} (limit {MAX_MONTHLY_CHANGE * 100}%)",
                        c["chain_id"],
                    )
            ranked_ids = {c["chain_id"] for c in ranked}
            for chain_id, prev in before.items():
                if chain_id not in ranked_ids:
                    flag("warning", "chain_dropped",
                         f"{prev['name']} was ranked last month and is not ranked now",
                         chain_id)  # fmt: skip
    return checks


def open_errors(doc: dict[str, Any]) -> list[dict[str, str]]:
    ack = set(doc.get("acknowledged", []))
    return [c for c in doc["checks"] if c["level"] == "error" and c["code"] not in ack]


# --- the index document --------------------------------------------------------------------------


def basket_definition(basket: Sequence[BasketLine], names: dict[str, tuple[str, str]]) -> dict:
    """The published basket: slug, Hebrew name, amount and unit. ``names``: slug -> (name, unit)."""
    return {
        "version": BASKET_VERSION,
        "item_count": len(basket),
        "items": [
            {
                "slug": line.slug,
                "name_he": names[line.slug][0],
                "amount": float(line.amount),
                "base_unit": names[line.slug][1],
                "label_he": line.label_he,
            }
            for line in basket
        ],
    }


def empty_index(definition: dict[str, Any], now: datetime) -> dict[str, Any]:
    return {"generated_at": _iso(now), "basket": definition, "months": []}


def ensure_index(out: Path, canonicals: Iterable[Any], now: datetime) -> dict[str, Any]:
    """Write ``basket-index.json`` with the current basket definition, keeping stored months.

    Called by ``export-seo`` so the site always has the published definition, also before the
    first month exists. ``canonicals`` are ``CanonicalRow``s (slug, display_name_he, base_unit).
    """
    names = {c.slug: (c.display_name_he, c.base_unit) for c in canonicals}
    definition = basket_definition(BASKET_V1, names)
    path = out / INDEX_FILE
    existing = load_index(path)
    if existing is None:
        index = empty_index(definition, now)
    elif existing["basket"] == definition:
        return existing
    else:
        index = {**existing, "basket": definition, "generated_at": _iso(now)}
    from smartcart_catalog.export_seo import write_json

    write_json(path, index)
    return index


def load_index(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def merge_month(index: dict[str, Any], month_doc: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Replace (or add) the month, newest first."""
    months = [m for m in index["months"] if m["month"] != month_doc["month"]]
    months.append(month_doc)
    months.sort(key=lambda m: m["month"], reverse=True)
    return {**index, "generated_at": _iso(now), "months": months}


def previous_published(index: dict[str, Any], month: str) -> dict[str, Any] | None:
    older = [m for m in index["months"] if m["month"] < month and m["status"] == "published"]
    return max(older, key=lambda m: m["month"]) if older else None


@dataclass(frozen=True)
class MonthOutcome:
    doc: dict[str, Any]
    blocked: list[dict[str, str]]


def evaluate_month(
    index: dict[str, Any],
    month: str,
    basket: Sequence[BasketLine],
    prices: Sequence[PriceRow],
    *,
    now: datetime,
    reviewed_by: str | None = None,
    acknowledge: Sequence[str] = (),
) -> MonthOutcome:
    """Compute the month, run the checks and set its status.

    ``published`` needs ``reviewed_by`` and no unacknowledged error; otherwise ``draft``.
    ``blocked`` lists the errors that stopped a requested publication.
    """
    doc = month_document(month, basket, prices, computed_at=now)
    doc["checks"] = run_checks(doc, previous_published(index, month), now=now)
    doc["acknowledged"] = sorted(set(acknowledge))
    errors = open_errors(doc)
    if reviewed_by and not errors:
        doc["status"] = "published"
        doc["reviewed_by"] = reviewed_by
    return MonthOutcome(doc, errors if reviewed_by else [])


# --- the press report ----------------------------------------------------------------------------

_MONTHS_HE = (
    "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
    "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
)  # fmt: skip


def month_label_he(month: str) -> str:
    year, mm = month.split("-")
    return f"{_MONTHS_HE[int(mm) - 1]} {year}"


def render_report(month_doc: dict[str, Any], basket: dict[str, Any]) -> str:
    """One page of Markdown, in Hebrew, that a journalist can quote."""
    m = month_doc
    label = month_label_he(m["month"])
    ranked = [c for c in m["chains"] if c["complete"]]
    lines = [f"# מדד הסל החודשי של SmartCart, {label}", ""]
    if m["status"] != "published":
        lines += ["> **טיוטה.** המדד טרם עבר בדיקה ופרסום, אין לצטט אותו.", ""]
    if ranked:
        top, bottom = ranked[0], ranked[-1]
        lines += [
            f"סל קבוע של {basket['item_count']} מוצרי יסוד (גרסה {basket['version']}) עלה "
            f"ב{top['name']} ₪{top['total']:.2f}, הזול ביותר מבין {len(ranked)} רשתות שבהן "
            f"נמצאו מחירים לכל הסל. ב{bottom['name']} אותו סל עלה ₪{bottom['total']:.2f}, "
            f"פער של {m['spread_pct']}% בין הרשת הזולה ליקרה.",
            "",
            "| רשת | סך הסל (₪) | הפרש מהזולה (₪) | הפרש מהזולה (%) |",
            "|---|---:|---:|---:|",
        ]
        for c in ranked:
            lines.append(
                f"| {c['name']} | {c['total']:.2f} | {c['delta_vs_cheapest']:.2f}"
                f" | {c['delta_pct']:.1f} |"
            )
        lines.append("")
    skipped = [c for c in m["chains"] if not c["complete"]]
    if skipped:
        names = ", ".join(f"{c['name']} ({len(c['missing'])} פריטים חסרים)" for c in skipped)
        lines += [f"רשתות שלא דורגו כי חסרו להן מחירים לחלק מהסל: {names}.", ""]
    lines += [
        "## איך חושב",
        "",
        "- הסל קבוע בכל חודש בגרסתו, והרכבו מפורסם בעמוד המדד באתר.",
        "- מחיר רשת לכל מוצר הוא החציוני בין סניפיה (חנויות פיזיות בלבד), ליחידת מידה "
        "(ל-100 גרם, ל-100 מ״ל, ליחידה או לק״ג), כפול הכמות בסל.",
        "- מבצעים כלולים, מלבד מבצעי מועדון. מחירי ירקות ופירות במשקל הם הערכה.",
        "- המחירים מקבצי השקיפות הממשלתיים של הרשתות. המחיר הקובע הוא בקופה.",
        "- הסל וכמויותיו נבחרו בשיקול דעת (הערכה) ואינם סל צריכה שנמדד.",
        f"- נתוני המחירים נכונים ל-{(m['price_date'] or '')[:10]}, החישוב בוצע ב-{m['computed_at'][:10]}.",
        "",
        "מתודולוגיה מלאה: /methodology",
        "",
    ]
    if m["checks"]:
        lines += ["## בדיקות לפני פרסום", ""]
        for c in m["checks"]:
            ack = " (אושר ידנית)" if c["code"] in m["acknowledged"] else ""
            lines.append(f"- {c['level']}: {c['code']}: {c['message']}{ack}")
        lines.append("")
    if m["reviewed_by"]:
        lines += [f"נבדק ואושר לפרסום על ידי: {m['reviewed_by']}", ""]
    return "\n".join(lines)
