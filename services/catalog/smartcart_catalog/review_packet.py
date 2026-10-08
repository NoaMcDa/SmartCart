"""Canonical review packet and sign-off import (issue #15).

``smartcart-catalog review-packet --out dist/review/`` writes two files for the domain-aware
reviewer who has to sign off ``data/canonicals.yaml`` (``docs/catalog.md`` section 2, "Open:
domain-aware reviewer sign-off"):

* ``canonicals-review.html``: one self-contained page (right to left, system fonts, no script, no
  external asset, printable) with the canonicals grouped by taxonomy and, per canonical, its name,
  base unit, rank (an estimate), critical and soft attributes, the product type rule, up to five
  example items and an "OK / change / remove" box.
* ``canonicals-review.csv``: the same rows with empty ``decision`` and ``comment`` columns (and
  optional ``proposed_*`` columns), for a reviewer who prefers a spreadsheet.

``smartcart-catalog review-import FILLED.csv --reviewer NAME`` validates the filled CSV, writes
``data/signoff/canonicals-<date>.yaml`` and prints the diff the decisions imply for
``data/canonicals.yaml``. It never edits ``data/canonicals.yaml``.

Where the examples come from. Each example is an item name run through the repository's own rule
pipeline: ``normalize`` -> ``RuleExtractor`` -> block (department and base unit) -> top-10 by
cosine similarity of the hash embedder -> ``RuleJudge``. That is the same chain
``smartcart-catalog normalize / extract / embed / judge`` runs over a database, done in memory so
the packet needs no database (``tests/test_review_packet.py`` checks that both give the same
decisions). Three sources, always labeled on the page and in the CSV:

* ``real``: the 200-row price files of seven chains committed as regression fixtures
  (``services/ingest/tests/fixtures/<chain>/real``), parsed by the chain adapters;
* ``gold``: the synthetic gold set (``data/gold``), used to fill canonicals the real fixtures do
  not reach. Synthetic, written by us, not chain data;
* ``db``: rows of ``item_canonical`` in the database ``$DATABASE_URL`` points at (after real data
  is loaded and matched).

An example is a machine decision, not a verified match: the page says so.
"""

from __future__ import annotations

import csv
import difflib
import hashlib
import html
import io
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from smartcart_catalog.block import base_unit_for, block_prefix
from smartcart_catalog.embed import HashEmbedder
from smartcart_catalog.extract.rule import RuleExtractor
from smartcart_catalog.judge import RuleJudge
from smartcart_catalog.match import parse_quantity
from smartcart_catalog.models import (
    Attributes,
    Candidate,
    CanonicalProduct,
    ExtractionError,
    NormalizedItem,
)
from smartcart_catalog.normalize import normalize
from smartcart_catalog.seed import (
    ATTRIBUTE_KEYS,
    Catalog,
    SeedError,
    implied_conflicts,
    load_catalog,
    parse_canonicals,
)

REPO = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO / "services" / "ingest" / "tests" / "fixtures"
GOLD_DIR = REPO / "data" / "gold"

HTML_NAME = "canonicals-review.html"
CSV_NAME = "canonicals-review.csv"

PER_CANONICAL = 5
TOP_K = 10

# docs/catalog.md section 2: five frequency tiers of 24, 54, 77, 75 and 15 products. The ranks are
# an estimate; the tiers are only shown while the list still has exactly that many canonicals.
TIER_SIZES = (24, 54, 77, 75, 15)

DECISIONS = ("ok", "change", "remove", "add")
_DECISION_WORDS: dict[str, str] = {
    "ok": "ok", "o.k.": "ok", "okay": "ok", "yes": "ok", "y": "ok", "approve": "ok",
    "approved": "ok", "✓": "ok", "v": "ok",
    "תקין": "ok", "אישור": "ok", "מאושר": "ok", "כן": "ok", "בסדר": "ok",
    "change": "change", "edit": "change", "fix": "change",
    "שינוי": "change", "לשנות": "change", "תיקון": "change", "לתקן": "change",
    "remove": "remove", "delete": "remove", "drop": "remove",
    "הסרה": "remove", "להסיר": "remove", "מחיקה": "remove", "למחוק": "remove", "הסר": "remove",
    "add": "add", "new": "add", "הוספה": "add", "להוסיף": "add", "הוסף": "add",
}  # fmt: skip

# --- Hebrew labels for the page -------------------------------------------------------------------

KEY_HE: dict[str, str] = {
    "fat_pct": "אחוז שומן",
    "state": "מצב (טרי/קפוא)",
    "flavor": "טעם",
    "base": "בסיס (סויה/שקדים/שיבולת)",
    "variety": "זן",
    "pack_size": "גודל אריזה",
    "brand": "מותג",
    "is_private_label": "מותג פרטי",
    "unit": "יחידה",
    "kosher": "כשרות",
    "diet_flags": "תזונה",
}
STATE_HE = {"fresh": "טרי", "frozen": "קפוא", "chilled": "מצונן", "canned": "משומר", "dry": "יבש"}
BASE_UNIT_HE = {"100g": "ל-100 גרם", "100ml": "ל-100 מ״ל", "unit": "ליחידה", "kg": "לק״ג"}
LEVEL_HE = {"exact": "זהה (ברקוד)", "any_brand": "כל מותג", "close": "תחליף קרוב"}
SOURCE_HE = {
    "real": "קובץ אמיתי של רשת",
    "gold": "סינתטי (סט הזהב)",
    "db": "מסד הנתונים",
}
SOURCE_RANK = {"db": 0, "real": 1, "gold": 2}
LEVEL_RANK = {"exact": 0, "any_brand": 1, "close": 2}


# --- source items ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceItem:
    """One chain item (or gold item) that can serve as an example."""

    key: str
    chain_id: str
    chain_name: str
    raw_name: str
    source: str  # real | gold | db
    barcode: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    is_weighed: bool = False
    manufacturer: str | None = None
    item_code: str | None = None
    """The chain's own code: normalization reads it (a short numeric code marks a weighed item)."""


@dataclass(frozen=True)
class Example:
    """An item that the rule pipeline maps to a canonical."""

    name: str
    chain: str
    source: str
    level: str
    confidence: float
    needs_review: bool

    def as_text(self) -> str:
        level = LEVEL_HE.get(self.level, self.level)
        review = ", לבדיקה" if self.needs_review else ""
        return f"{self.name} [{self.chain}; {level}{review}; {SOURCE_HE[self.source]}]"


def load_real_items(fixtures_dir: Path = FIXTURES_DIR) -> list[SourceItem]:
    """Items of every ``<chain>/real/PriceFull*`` fixture, parsed by the chain's adapter.

    Fixtures that are not there (a checkout without them) simply give no items."""
    from smartcart_ingest.adapters import REGISTRY

    out: list[SourceItem] = []
    by_slug = {getattr(c, "slug", None): c for c in REGISTRY.values()}
    for slug in sorted(s for s in by_slug if s):
        folder = fixtures_dir / slug / "real"
        if not folder.is_dir():
            continue
        adapter = by_slug[slug]()
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name == "MANIFEST.json":
                continue
            try:
                info = adapter.parse_filename(path.name)
            except Exception:  # noqa: BLE001 - not a portal file name
                continue
            if info.kind != "price_full":
                continue
            data = path.read_bytes()
            parsed = adapter.parse(adapter.raw_file_for(path.name, data), data)
            seen: set[str] = set()
            for rec in parsed.items:
                if rec.item_code in seen:
                    continue
                seen.add(rec.item_code)
                out.append(
                    SourceItem(
                        key=f"{slug}:{rec.item_code}",
                        chain_id=rec.chain_id,
                        chain_name=adapter.display_name,
                        raw_name=rec.raw_name,
                        source="real",
                        barcode=rec.barcode,
                        quantity=rec.quantity,
                        unit=rec.unit,
                        is_weighed=rec.is_weighed,
                        manufacturer=rec.manufacturer,
                        item_code=rec.item_code,
                    )
                )
    return out


def load_gold_items(gold_dir: Path = GOLD_DIR) -> list[SourceItem]:
    """The synthetic gold set's items (``data/gold/gold_pairs.csv``)."""
    path = gold_dir / "gold_pairs.csv"
    if not path.exists():
        return []
    items: dict[str, SourceItem] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            key = row["item_key"]
            if key not in items:
                items[key] = SourceItem(
                    key=f"gold:{key}",
                    chain_id="gold",
                    chain_name="סט הזהב (סינתטי)",
                    raw_name=row["item_text"],
                    source="gold",
                    barcode=row.get("barcode") or None,
                    is_weighed=row.get("is_weighed") == "True",
                    item_code=key,
                )
    return list(items.values())


# --- the rule pipeline, in memory -----------------------------------------------------------------


@dataclass(frozen=True)
class ItemMatch:
    item: SourceItem
    canonical_slug: str | None
    level: str | None
    confidence: float
    needs_review: bool
    reason: str = ""


def _sparse(vec: Sequence[float]) -> dict[int, float]:
    return {i: v for i, v in enumerate(vec) if v}


def _dot(a: Mapping[int, float], b: Mapping[int, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(i, 0.0) for i, v in a.items())


def match_items(
    catalog: Catalog, items: Sequence[SourceItem], *, k: int = TOP_K
) -> list[ItemMatch]:
    """Run ``items`` through normalize, the rule extractor, blocking, hash-embedding retrieval
    and the rule judge, as ``smartcart-catalog normalize / extract / embed / judge`` do."""
    extractor = RuleExtractor(catalog)
    judge = RuleJudge()
    embedder = HashEmbedder()
    canon_vecs = [_sparse(v) for v in embedder.embed([c.display_name_he for c in catalog.canonicals])]
    # canonical ids are positions in the catalog (1-based), like database ids in file order
    canon_ids = {c.slug: i for i, c in enumerate(catalog.canonicals, start=1)}
    item_vecs = [_sparse(v) for v in embedder.embed([i.raw_name for i in items])]

    normalized: list[NormalizedItem] = []
    for n, it in enumerate(items, start=1):
        row = {
            "id": n, "chain_id": it.chain_id, "chain_name": it.chain_name,
            "item_code": it.item_code, "barcode": it.barcode, "raw_name": it.raw_name, "manufacturer": it.manufacturer,
            "quantity": it.quantity, "unit": it.unit, "is_weighed": it.is_weighed,
        }  # fmt: skip
        normalized.append(normalize(row, item_id=n))
    extracted = extractor.extract(normalized)

    out: list[ItemMatch] = []
    for n, (it, attrs, ivec) in enumerate(zip(items, extracted, item_vecs, strict=True), start=1):
        if isinstance(attrs, ExtractionError):
            out.append(ItemMatch(it, None, None, 0.0, False, attrs.reason))
            continue
        judged = _judge_view(it, attrs, n)
        prefix = block_prefix(attrs.category_path)
        scored: list[tuple[float, int, CanonicalProduct]] = []
        for c, cvec in zip(catalog.canonicals, canon_vecs, strict=True):
            if judged.base_unit is not None and c.base_unit != judged.base_unit:
                continue
            if prefix is not None and not (
                c.taxonomy_id == prefix or c.taxonomy_id.startswith(prefix + ".")
            ):
                continue
            scored.append((_dot(ivec, cvec), canon_ids[c.slug], c))
        scored.sort(key=lambda t: (-t[0], t[1]))
        candidates = [
            Candidate(canonical_id=cid, similarity=sim, canonical=c.model_copy(update={"id": cid}))
            for sim, cid, c in scored[:k]
        ]
        decision = judge.judge(judged, attrs, candidates, catalog.rules)
        slug = None
        if decision.canonical_id is not None:
            slug = catalog.canonicals[decision.canonical_id - 1].slug
        out.append(ItemMatch(it, slug, decision.flex_level, decision.confidence,
                             decision.needs_review, decision.reason))  # fmt: skip
    return out


def _judge_view(it: SourceItem, attrs: Attributes, item_id: int) -> NormalizedItem:
    """The item as ``match.load_items`` hands it to the judge: size from the file's quantity and
    unit, else from the name; ``clean_name`` is the raw name."""
    qty, unit = it.quantity, it.unit
    if qty is None or not unit:
        q2, u2, count = parse_quantity(it.raw_name)
        qty = q2 * count if q2 is not None else None
        unit = u2
    return NormalizedItem(
        item_id=item_id,
        clean_name=it.raw_name,
        quantity=qty,
        unit=unit,
        total_quantity=qty,
        base_unit=base_unit_for(attrs.unit or unit, is_weighed=it.is_weighed),
        is_weighed=it.is_weighed,
        chain_id=it.chain_id,
        manufacturer=it.manufacturer,
        barcode=it.barcode,
        raw_name=it.raw_name,
    )


def examples_from_matches(
    matches: Iterable[ItemMatch], per_canonical: int = PER_CANONICAL
) -> dict[str, list[Example]]:
    """Up to ``per_canonical`` examples per canonical: real before synthetic, accepted before
    to-review, tighter level first, and different chains before a second item of one chain."""
    pool: dict[str, list[Example]] = defaultdict(list)
    for m in matches:
        if m.canonical_slug is None or m.level is None:
            continue
        pool[m.canonical_slug].append(
            Example(m.item.raw_name.strip(), m.item.chain_name, m.item.source, m.level,
                    m.confidence, m.needs_review)  # fmt: skip
        )
    return {slug: pick_examples(found, per_canonical) for slug, found in pool.items()}


def _quality(e: Example) -> tuple[Any, ...]:
    return (e.needs_review, LEVEL_RANK.get(e.level, 9), -e.confidence, e.chain, e.name)


def pick_examples(found: Sequence[Example], limit: int) -> list[Example]:
    """Sources in order (database, real, synthetic), each used up before the next; inside a
    source one item per chain first, then the rest, best quality first."""
    chosen: list[Example] = []
    names: set[str] = set()
    for source in sorted({e.source for e in found}, key=lambda s: SOURCE_RANK.get(s, 9)):
        group = sorted((e for e in found if e.source == source), key=_quality)
        chains: set[str] = set()
        for second_pass in (False, True):
            for e in group:
                if len(chosen) == limit:
                    break
                if e.name in names or (not second_pass and e.chain in chains):
                    continue
                chosen.append(e)
                names.add(e.name)
                chains.add(e.chain)
    chosen.sort(key=lambda e: (SOURCE_RANK.get(e.source, 9), *_quality(e)))
    return chosen


def examples_from_db(conn: Any, per_canonical: int = PER_CANONICAL) -> dict[str, list[Example]]:
    """Examples from ``item_canonical`` rows (machine or human mappings) of a loaded database."""
    rows = conn.execute(
        "SELECT cp.slug, i.raw_name, COALESCE(c.name, i.chain_id), ic.flex_level,"
        "       COALESCE(ic.confidence, 0), ic.needs_review"
        " FROM item_canonical ic"
        " JOIN items i ON i.id = ic.item_id"
        " JOIN canonical_products cp ON cp.id = ic.canonical_id"
        " LEFT JOIN chains c ON c.id = i.chain_id"
        " WHERE NOT ic.human_rejected AND i.chain_id <> 'gold'"
    ).fetchall()
    pool: dict[str, list[Example]] = defaultdict(list)
    for slug, name, chain, level, conf, review in rows:
        pool[slug].append(Example(name.strip(), chain, "db", level, float(conf), bool(review)))
    return {slug: pick_examples(found, per_canonical) for slug, found in pool.items()}


@dataclass
class ExamplesReport:
    by_slug: dict[str, list[Example]] = field(default_factory=dict)
    sources_used: list[str] = field(default_factory=list)
    items_seen: dict[str, int] = field(default_factory=dict)
    items_mapped: dict[str, int] = field(default_factory=dict)


def collect_examples(
    catalog: Catalog,
    sources: Sequence[str],
    *,
    per_canonical: int = PER_CANONICAL,
    fixtures_dir: Path = FIXTURES_DIR,
    gold_dir: Path = GOLD_DIR,
    conn: Any = None,
) -> ExamplesReport:
    """Examples from the sources in order; a later source only fills what earlier ones left
    short of ``per_canonical``. Each example carries its own source label."""
    report = ExamplesReport()
    merged: dict[str, list[Example]] = defaultdict(list)
    for source in sources:
        if source == "none":
            continue
        if source == "db":
            if conn is None:
                raise ValueError("the db source needs a database connection")
            found = examples_from_db(conn, per_canonical)
            report.items_seen["db"] = sum(len(v) for v in found.values())
            report.items_mapped["db"] = report.items_seen["db"]
        elif source in ("real", "gold"):
            items = (load_real_items(fixtures_dir) if source == "real"
                     else load_gold_items(gold_dir))  # fmt: skip
            matches = match_items(catalog, items) if items else []
            report.items_seen[source] = len(items)
            report.items_mapped[source] = sum(1 for m in matches if m.canonical_slug)
            found = examples_from_matches(matches, per_canonical)
        else:
            raise ValueError(f"unknown examples source {source!r}; use real, gold, db or none")
        if report.items_seen.get(source):
            report.sources_used.append(source)
        for slug, exs in found.items():
            have = merged[slug]
            for e in exs:
                if len(have) < per_canonical:
                    have.append(e)
    report.by_slug = {slug: pick_examples(v, per_canonical) for slug, v in merged.items()}
    return report


# --- rows -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PacketRow:
    rank: int
    tier: int | None
    slug: str
    name_he: str
    department: str
    category: str
    taxonomy_id: str
    taxonomy_path_he: str
    product_type: str
    base_unit: str
    critical_attrs: dict[str, Any]
    soft_attrs: dict[str, Any]
    critical_keys: tuple[str, ...]
    soft_keys: tuple[str, ...]
    keywords: tuple[str, ...]
    reference_barcodes: tuple[str, ...]
    examples: tuple[Example, ...]
    row_hash: str


def tier_of(rank: int, total: int) -> int | None:
    if total != sum(TIER_SIZES):
        return None
    upper = 0
    for tier, size in enumerate(TIER_SIZES, start=1):
        upper += size
        if rank <= upper:
            return tier
    return None


def entry_hash(entry: Mapping[str, Any]) -> str:
    """A short fingerprint of the fields a reviewer sees, to notice a stale packet at import."""
    fields = {
        k: entry.get(k)
        for k in ("slug", "display_name_he", "taxonomy_id", "product_type", "base_unit",
                  "critical_attrs", "soft_attrs", "rank")
    }  # fmt: skip
    blob = json.dumps(fields, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:10]


def raw_entries(data_dir: Path) -> list[dict[str, Any]]:
    doc = yaml.safe_load((data_dir / "canonicals.yaml").read_text(encoding="utf-8"))
    return [dict(e) for e in doc["canonicals"]]


def build_rows(
    catalog: Catalog,
    entries: Sequence[Mapping[str, Any]],
    examples: Mapping[str, Sequence[Example]],
) -> list[PacketRow]:
    by_slug = {e["slug"]: e for e in entries}
    total = len(catalog.canonicals)
    rows: list[PacketRow] = []
    for c in sorted(catalog.canonicals, key=lambda c: c.rank or 0):
        rule = catalog.rules[c.product_type]
        parts = c.taxonomy_id.split(".")
        dept = catalog.taxonomy.get(parts[0]).name_he
        cat = catalog.taxonomy.get(".".join(parts[:2])).name_he if len(parts) > 1 else dept
        rows.append(
            PacketRow(
                rank=c.rank or 0,
                tier=tier_of(c.rank or 0, total),
                slug=c.slug,
                name_he=c.display_name_he,
                department=dept,
                category=cat,
                taxonomy_id=c.taxonomy_id,
                taxonomy_path_he=catalog.taxonomy.path_he(c.taxonomy_id),
                product_type=c.product_type,
                base_unit=c.base_unit,
                critical_attrs=dict(c.critical_attrs),
                soft_attrs=dict(c.soft_attrs),
                critical_keys=rule.critical_keys,
                soft_keys=rule.soft_keys,
                keywords=tuple(catalog.extras[c.product_type].keywords),
                reference_barcodes=c.reference_barcodes,
                examples=tuple(examples.get(c.slug, ())),
                row_hash=entry_hash(by_slug[c.slug]),
            )
        )
    return rows


# --- attribute text -------------------------------------------------------------------------------


def _value_text(key: str, value: Any) -> str:
    if key == "state":
        return STATE_HE.get(str(value), str(value))
    if isinstance(value, float) and value == int(value):
        value = int(value)
    return str(value)


def attrs_text(attrs: Mapping[str, Any]) -> str:
    """``fat_pct=3; state=fresh`` (the CSV form, and the form ``proposed_*`` columns use)."""
    return "; ".join(f"{k}={v}" for k, v in attrs.items()) if attrs else "(none)"


def parse_attrs_cell(text: str) -> dict[str, Any]:
    """Parse ``key=value; key=value`` (values read as YAML scalars). ``{}`` or ``none`` is an empty
    mapping. Raises ``ValueError`` with a reviewer-readable message."""
    text = text.strip()
    if text.lower() in ("{}", "none", "(none)", "-", "ללא"):
        return {}
    out: dict[str, Any] = {}
    for part in re.split(r"[;\n]", text):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"expected key=value, got {part!r}")
        key, _, value = part.partition("=")
        key = key.strip()
        if key not in ATTRIBUTE_KEYS:
            raise ValueError(f"unknown attribute {key!r}; known: {', '.join(sorted(ATTRIBUTE_KEYS))}")
        value = value.strip()
        try:
            parsed = yaml.safe_load(value) if value else None
        except yaml.YAMLError as exc:
            raise ValueError(f"cannot read the value of {key}: {value!r}") from exc
        if parsed is None:
            raise ValueError(f"{key} has no value")
        out[key] = parsed
    return out


# --- CSV ------------------------------------------------------------------------------------------

CSV_FIELDS = (
    "rank_estimate", "tier_estimate", "slug", "display_name_he", "department", "category",
    "taxonomy_id", "product_type", "base_unit",
    "critical_keys", "critical_attrs", "soft_keys", "soft_attrs",
    "examples", "row_hash",
    "decision", "comment",
    "proposed_display_name_he", "proposed_base_unit", "proposed_critical_attrs",
    "proposed_soft_attrs", "proposed_rank",
)  # fmt: skip


def render_csv(rows: Sequence[PacketRow]) -> str:
    """The packet as CSV text (write it as ``utf-8-sig`` so Excel reads the Hebrew)."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\r\n")
    w.writeheader()
    for r in rows:
        w.writerow({
            "rank_estimate": r.rank,
            "tier_estimate": r.tier or "",
            "slug": r.slug,
            "display_name_he": r.name_he,
            "department": r.department,
            "category": r.category,
            "taxonomy_id": r.taxonomy_id,
            "product_type": r.product_type,
            "base_unit": r.base_unit,
            "critical_keys": ", ".join(r.critical_keys),
            "critical_attrs": attrs_text(r.critical_attrs),
            "soft_keys": ", ".join(r.soft_keys),
            "soft_attrs": attrs_text(r.soft_attrs),
            "examples": " | ".join(e.as_text() for e in r.examples),
            "row_hash": r.row_hash,
            "decision": "", "comment": "", "proposed_display_name_he": "",
            "proposed_base_unit": "", "proposed_critical_attrs": "", "proposed_soft_attrs": "",
            "proposed_rank": "",
        })  # fmt: skip
    return buf.getvalue()


# --- HTML -----------------------------------------------------------------------------------------

_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; padding: 16px; background: #fff; color: #1a1a1a; line-height: 1.45;
  font-family: system-ui, -apple-system, "Segoe UI", "Arial Hebrew", Arial, sans-serif; font-size: 15px; }
main { max-width: 1280px; margin: 0 auto; }
h1 { font-size: 26px; margin: 0 0 4px; }
h2 { font-size: 21px; margin: 28px 0 6px; padding-bottom: 4px; border-bottom: 2px solid #1a1a1a; }
h3 { font-size: 16px; margin: 16px 0 6px; color: #333; }
.meta, .muted { color: #555; font-size: 13px; }
.box { border: 1px solid #999; border-radius: 6px; padding: 10px 14px; margin: 12px 0; background: #fafafa; }
.warn { border-color: #b36b00; background: #fff6e6; }
.box ul, .box ol { margin: 4px 0; padding-inline-start: 22px; }
nav.toc ul { columns: 3 220px; list-style: none; padding: 0; margin: 6px 0; }
nav.toc li { padding: 2px 0; }
table { width: 100%; border-collapse: collapse; margin: 6px 0 14px; }
th, td { border: 1px solid #aaa; padding: 6px 8px; vertical-align: top; text-align: start; }
thead th { background: #eee; font-size: 13px; }
td.num { white-space: nowrap; text-align: center; width: 54px; }
.name { font-weight: 700; font-size: 16px; }
.slug, code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; color: #444; direction: ltr; unicode-bidi: isolate; }
.tag { display: inline-block; border: 1px solid #888; border-radius: 10px; padding: 0 7px; font-size: 12px; margin-inline-end: 4px; background: #fff; }
.tag.est { border-style: dashed; }
.kv { display: block; margin: 1px 0; }
.kv b { font-weight: 600; }
.none { color: #777; }
ul.ex { margin: 0; padding: 0; list-style: none; font-size: 13px; }
ul.ex li { margin: 0 0 4px; padding-bottom: 3px; border-bottom: 1px dotted #ccc; }
ul.ex li:last-child { border-bottom: 0; }
.src-real { border-color: #1a6b2f; color: #14531f; }
.src-gold { border-color: #8a5a00; color: #6a4500; border-style: dashed; }
.src-db { border-color: #1a4a8a; color: #12366a; }
.review { border-color: #b00020; color: #8a0019; }
td.decision { width: 150px; font-size: 14px; }
td.decision .opt { display: block; margin: 3px 0; white-space: nowrap; }
td.decision .line { display: block; border-bottom: 1px solid #777; height: 22px; margin-top: 6px; }
.rule { font-size: 13px; }
.rule .kw { color: #555; }
@media (max-width: 760px) { body { padding: 8px; } table, thead, tbody, tr, th, td { display: block; width: auto; }
  thead { display: none; } td.num { text-align: start; } tr { border: 2px solid #777; margin: 10px 0; } }
@media print {
  @page { size: A4 landscape; margin: 10mm; }
  body { padding: 0; font-size: 11px; }
  h2 { page-break-after: avoid; }
  thead { display: table-header-group; }
  tr { page-break-inside: avoid; }
  nav.toc { display: none; }
  .box { background: #fff; }
  a { color: inherit; text-decoration: none; }
}
"""


def _e(text: Any) -> str:
    return html.escape(str(text), quote=True)


def _attr_cells(attrs: Mapping[str, Any]) -> str:
    """Attributes as lines: the Hebrew label, the value, and the key name for engineers. A pack
    size and its unit are one line."""
    if not attrs:
        return '<span class="none">אין (רק סוג המוצר)</span>'
    lines = []
    for k, v in attrs.items():
        if k == "unit" and "pack_size" in attrs:
            continue
        value = _value_text(k, v)
        key = k
        if k == "pack_size" and "unit" in attrs:
            value = f"{value} {attrs['unit']}"
            key = "pack_size, unit"
        lines.append(
            f'<span class="kv"><b>{_e(KEY_HE.get(k, k))}:</b> <bdi>{_e(value)}</bdi>'
            f' <code>{_e(key)}</code></span>'
        )
    return "".join(lines)


def _keys_text(keys: Sequence[str]) -> str:
    if not keys:
        return '<span class="none">אין</span>'
    return ", ".join(f"{_e(KEY_HE.get(k, k))} (<code>{_e(k)}</code>)" for k in keys)


def _examples_cell(r: PacketRow) -> str:
    if not r.examples:
        return '<span class="none">אין דוגמה בקבצים שנבדקו</span>'
    items = []
    for e in r.examples:
        review = '<span class="tag review">לבדיקה</span>' if e.needs_review else ""
        items.append(
            f'<li><span dir="auto">{_e(e.name)}</span><br>'
            f'<span class="tag">{_e(e.chain)}</span>'
            f'<span class="tag">{_e(LEVEL_HE.get(e.level, e.level))}</span>{review}'
            f'<span class="tag src-{_e(e.source)}">{_e(SOURCE_HE.get(e.source, e.source))}</span></li>'
        )
    return f'<ul class="ex">{"".join(items)}</ul>'


def _row_html(r: PacketRow) -> str:
    tier = f' <span class="tag est">שכבה {r.tier} (הערכה)</span>' if r.tier else ""
    barcodes = (
        f'<br><span class="muted">ברקודים: <code>{_e(", ".join(r.reference_barcodes))}</code></span>'
        if r.reference_barcodes else ""
    )
    kw = ", ".join(r.keywords[:6]) + (" …" if len(r.keywords) > 6 else "")
    return (
        f'<tr id="c-{_e(r.slug)}">'
        f'<td class="num"><b>{r.rank}</b><br><span class="tag est">הערכה</span></td>'
        f'<td><span class="name">{_e(r.name_he)}</span><br><span class="slug">{_e(r.slug)}</span>'
        f'{tier}<br><span class="muted">{_e(r.taxonomy_path_he)}</span>{barcodes}</td>'
        f'<td>{_e(BASE_UNIT_HE.get(r.base_unit, r.base_unit))}<br><code>{_e(r.base_unit)}</code></td>'
        f"<td>{_attr_cells(r.critical_attrs)}</td>"
        f"<td>{_attr_cells(r.soft_attrs)}</td>"
        f'<td class="rule"><code>{_e(r.product_type)}</code><br>'
        f"<b>קריטי:</b> {_keys_text(r.critical_keys)}<br>"
        f"<b>רך:</b> {_keys_text(r.soft_keys)}<br>"
        f'<span class="kw">מילות זיהוי: <span dir="auto">{_e(kw)}</span></span></td>'
        f"<td>{_examples_cell(r)}</td>"
        '<td class="decision"><span class="opt">☐ תקין (OK)</span>'
        '<span class="opt">☐ שינוי (change)</span><span class="opt">☐ הסרה (remove)</span>'
        '<span class="line"></span><span class="line"></span></td>'
        "</tr>"
    )


@dataclass(frozen=True)
class PacketMeta:
    generated_on: str
    canonicals_sha: str
    examples_sources: tuple[str, ...]
    items_seen: Mapping[str, int]
    items_mapped: Mapping[str, int]
    product_types: int
    departments: int


def packet_summary(rows: Sequence[PacketRow]) -> dict[str, int]:
    """Counts the page shows at the top: canonicals with a real, a synthetic-only and no example."""
    real = sum(1 for r in rows if any(e.source in ("real", "db") for e in r.examples))
    synth = sum(
        1 for r in rows
        if r.examples and not any(e.source in ("real", "db") for e in r.examples)
    )  # fmt: skip
    return {"total": len(rows), "with_real": real, "synthetic_only": synth,
            "without": len(rows) - real - synth}  # fmt: skip


def render_html(rows: Sequence[PacketRow], meta: PacketMeta, dept_order: Sequence[str]) -> str:
    summary = packet_summary(rows)
    groups: dict[str, dict[str, list[PacketRow]]] = {}
    for r in rows:
        groups.setdefault(r.department, {}).setdefault(r.category, []).append(r)
    ordered = [d for d in dept_order if d in groups] + [d for d in groups if d not in dept_order]

    toc = "".join(
        f'<li><a href="#d{i}">{_e(d)}</a> '
        f'<span class="muted">({sum(len(v) for v in groups[d].values())})</span></li>'
        for i, d in enumerate(ordered)
    )
    sections = []
    for i, dept in enumerate(ordered):
        parts = [f'<section><h2 id="d{i}">{_e(dept)}</h2>']
        for cat, rs in groups[dept].items():
            if cat != dept:
                parts.append(f"<h3>{_e(cat)}</h3>")
            parts.append(
                "<table><thead><tr>"
                '<th>דירוג<br>(הערכה)</th><th>מוצר</th><th>יחידת בסיס</th>'
                "<th>מאפיינים קריטיים<br>(לא משתנים ב״כל מותג״)</th>"
                "<th>מאפיינים רכים<br>(נפתחים ב״תחליף קרוב״)</th>"
                "<th>כלל סוג המוצר</th><th>עד 5 דוגמאות</th><th>החלטה</th></tr></thead><tbody>"
            )
            parts.extend(_row_html(r) for r in rs)
            parts.append("</tbody></table>")
        parts.append("</section>")
        sections.append("".join(parts))

    seen = meta.items_seen
    sources_line = ", ".join(
        f"{SOURCE_HE.get(s, s)}: {seen.get(s, 0)} פריטים נבדקו, {meta.items_mapped.get(s, 0)} שויכו"
        for s in meta.examples_sources
    ) or "אין דוגמאות (הופעל --examples none)"
    return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>סקירת מוצרים קנוניים · SmartCart</title>
<style>{_CSS}</style>
</head>
<body>
<main>
<header>
<h1>סקירת המוצרים הקנוניים של SmartCart</h1>
<p class="meta">נוצר ב-{_e(meta.generated_on)} מתוך <code>data/canonicals.yaml</code>
(טביעת אצבע <code>{_e(meta.canonicals_sha)}</code>) · {summary["total"]} מוצרים קנוניים ·
{meta.product_types} סוגי מוצר · {meta.departments} מחלקות · מזהה #15</p>
</header>

<div class="box">
<h3>מה מבקשים ממך</h3>
<p>לכל שורה לסמן אחת משלוש: <b>תקין</b>, <b>שינוי</b> (לכתוב מה לשנות) או <b>הסרה</b>.
אם חסר מוצר חשוב, לכתוב אותו בסוף העמוד או בקובץ ה-CSV. מה בודקים, לפי הרשימה ב-<code>docs/catalog.md</code>:</p>
<ol>
<li>אחוזי השומן תואמים מוצרים נפוצים בישראל (למשל חלב ללא לקטוז 2%, גבינה צהובה 28% ו-9%, בולגרית 5% ו-24%, שמנת מתוקה 32% ו-38%).</li>
<li>שום דבר חשוב לא חסר בשכבות 1 ו-2 (המוצרים השכיחים ביותר).</li>
<li>המאפיינים הקריטיים נכונים לכל סוג מוצר (למשל: האם &quot;פרוס&quot; צריך לפצל גבינה צהובה).</li>
<li>הדירוג נראה סביר. <b>הדירוג הוא הערכה</b>, לא מדידה.</li>
</ol>
</div>

<div class="box">
<h3>איך לקרוא את הדף</h3>
<ul>
<li><b>מאפיין קריטי</b> חייב להיות זהה ברמת &quot;כל מותג&quot;: חלב 3% לא יוחלף בחלב 1%. <b>מאפיין רך</b> (גודל אריזה, מותג) יכול להשתנות ברמת &quot;תחליף קרוב&quot;. סוג המוצר תמיד קריטי.</li>
<li><b>הדירוג והשכבות הם הערכה</b> מתוך ידע כללי ומחקר השוק, לא נמדדו בנתוני קנייה. שכבה 1 היא המוצרים השכיחים ביותר.</li>
<li><b>דוגמאות</b> הן שמות פריטים שהכללים האוטומטיים שלנו שייכו למוצר. הן הצעה של מכונה, לא התאמה מאומתת, וייתכנו בהן טעויות. {_e(sources_line)}.
פריט שהתיוג שלו &quot;לבדיקה&quot; לא היה מוצג למשתמשת. תיוג &quot;סינתטי&quot; פירושו שם שנכתב על ידינו, לא נתון של רשת. בקבצי חמש מתוך שבע הרשתות שם הפריט נחתך בכ-20 עד 24 תווים (נמדד על קבצי הדוגמה), ולכן חלק מהשמות האמיתיים קטועים.</li>
<li>כיסוי הדוגמאות: {summary["with_real"]} מוצרים עם דוגמה אמיתית, {summary["synthetic_only"]} עם דוגמה סינתטית בלבד, {summary["without"]} בלי דוגמה. מוצר בלי דוגמה אינו בהכרח שגוי: הקבצים האמיתיים הם 200 שורות לכל רשת.</li>
</ul>
</div>

<nav class="toc" aria-label="מחלקות"><h3>מחלקות</h3><ul>{toc}</ul></nav>

{"".join(sections)}

<section class="box">
<h3>מוצרים שחסרים</h3>
<p>רשמי כאן (או בשורות חדשות בקובץ ה-CSV עם <code>decision = add</code>) מוצרים חשובים שאינם ברשימה.</p>
<span class="line" style="display:block;border-bottom:1px solid #777;height:26px"></span>
<span class="line" style="display:block;border-bottom:1px solid #777;height:26px"></span>
<span class="line" style="display:block;border-bottom:1px solid #777;height:26px"></span>
<p class="muted" style="margin-top:14px">שם הסוקרת/ת: ______________________ &nbsp; תאריך: ______________ &nbsp; חתימה: ______________</p>
</section>
</main>
</body>
</html>
"""


# --- writing the packet ---------------------------------------------------------------------------


def sha_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def build_packet(
    data_dir: Path,
    out_dir: Path,
    *,
    sources: Sequence[str] = ("real", "gold"),
    per_canonical: int = PER_CANONICAL,
    generated_on: date | None = None,
    fixtures_dir: Path = FIXTURES_DIR,
    gold_dir: Path = GOLD_DIR,
    conn: Any = None,
) -> dict[str, Any]:
    """Write the HTML and the CSV into ``out_dir`` and return what was written and counted."""
    catalog = load_catalog(data_dir)
    entries = raw_entries(data_dir)
    report = collect_examples(catalog, sources, per_canonical=per_canonical,
                              fixtures_dir=fixtures_dir, gold_dir=gold_dir, conn=conn)  # fmt: skip
    rows = build_rows(catalog, entries, report.by_slug)
    meta = PacketMeta(
        generated_on=(generated_on or date.today()).isoformat(),
        canonicals_sha=sha_of_file(data_dir / "canonicals.yaml"),
        examples_sources=tuple(report.sources_used),
        items_seen=report.items_seen,
        items_mapped=report.items_mapped,
        product_types=len(catalog.rules),
        departments=len({r.department for r in rows}),
    )
    dept_order = [n.name_he for n in catalog.taxonomy.departments()]
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / HTML_NAME
    csv_path = out_dir / CSV_NAME
    html_path.write_text(render_html(rows, meta, dept_order), encoding="utf-8")
    csv_path.write_text(render_csv(rows), encoding="utf-8-sig", newline="")
    # The packet is a generated artifact, not source: keep a default `dist/` out of git without
    # touching the repository's .gitignore.
    guard = out_dir / ".gitignore"
    if not guard.exists():
        guard.write_text("*\n", encoding="utf-8")
    return {
        "html": html_path, "csv": csv_path, "rows": len(rows), "summary": packet_summary(rows),
        "sources": list(report.sources_used), "items_seen": dict(report.items_seen),
        "items_mapped": dict(report.items_mapped),
    }  # fmt: skip


# --- importing a filled CSV -----------------------------------------------------------------------


class ReviewImportError(ValueError):
    """The filled CSV cannot be turned into a sign-off. The message lists every problem."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


@dataclass
class Decision:
    slug: str
    decision: str
    comment: str = ""
    row_hash: str = ""
    proposed: dict[str, Any] = field(default_factory=dict)
    line: int = 0


@dataclass
class ImportResult:
    decisions: list[Decision]
    additions: list[Decision]
    pending: list[str]
    stale: list[str]
    warnings: list[str]
    encoding: str

    @property
    def counts(self) -> dict[str, int]:
        c = Counter(d.decision for d in self.decisions)
        return {"ok": c["ok"], "change": c["change"], "remove": c["remove"],
                "add": len(self.additions), "pending": len(self.pending)}  # fmt: skip


def read_csv_text(path: Path) -> tuple[str, str]:
    """The CSV as text and the encoding that worked. Excel's plain "CSV" on a Hebrew Windows saves
    Windows-1255, "CSV UTF-8" saves UTF-8 with a BOM; both are accepted."""
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1255"), "windows-1255"


def _sniff_delimiter(text: str) -> str:
    header = text.splitlines()[0] if text.splitlines() else ""
    counts = {d: header.count(d) for d in (",", ";", "\t")}
    return max(counts, key=lambda d: counts[d]) if any(counts.values()) else ","


def normalize_decision(word: str) -> str | None:
    key = word.strip().lower().rstrip(".")
    key = re.sub(r"[☐☑☒\[\]()]", "", key).strip()
    return _DECISION_WORDS.get(key)


def parse_filled_csv(
    path: Path,
    entries: Sequence[Mapping[str, Any]],
    *,
    allow_partial: bool = False,
    allow_stale: bool = False,
) -> ImportResult:
    """Validate a filled review CSV against the current ``canonicals.yaml`` entries.

    Errors (raised together as ``ReviewImportError``): missing columns, an unknown or duplicated
    slug, an unreadable decision, a ``change`` or ``remove`` without a comment or a proposal, a
    bad ``proposed_*`` cell, undecided canonicals (unless ``allow_partial``) and rows whose
    ``row_hash`` no longer matches the file (unless ``allow_stale``)."""
    text, encoding = read_csv_text(path)
    delimiter = _sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)
    fields = [f.strip() for f in (reader.fieldnames or [])]
    reader.fieldnames = fields
    problems: list[str] = []
    missing = [f for f in ("slug", "decision", "comment") if f not in fields]
    if missing:
        raise ReviewImportError([f"missing column(s): {', '.join(missing)} (found: {fields})"])

    current = {e["slug"]: e for e in entries}
    seen: dict[str, int] = {}
    decisions: list[Decision] = []
    additions: list[Decision] = []
    stale: list[str] = []
    warnings: list[str] = []
    if encoding != "utf-8":
        warnings.append("the file was not UTF-8; read as Windows-1255 (Hebrew Excel 'CSV')")
    if delimiter != ",":
        warnings.append(f"the delimiter is {delimiter!r}, not a comma (read as is)")

    for line, row in enumerate(reader, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        slug, word = row.get("slug", ""), row.get("decision", "")
        if not slug and not word and not row.get("comment") and not row.get("display_name_he"):
            continue  # a blank line
        decision = normalize_decision(word) if word else None
        if word and decision is None:
            problems.append(f"line {line} ({slug or 'no slug'}): unknown decision {word!r};"
                            f" use OK, change, remove or add")  # fmt: skip
            continue
        if decision == "add" or (not slug and decision):
            if decision != "add":
                problems.append(f"line {line}: a row without a slug can only be 'add'")
                continue
            name = row.get("display_name_he", "")
            if not name or not row.get("comment"):
                problems.append(f"line {line}: an 'add' row needs display_name_he and a comment")
                continue
            additions.append(Decision("", "add", row["comment"], "", {"display_name_he": name,
                             **{k: row[k] for k in ("taxonomy_id", "product_type", "base_unit")
                                if row.get(k)}}, line))  # fmt: skip
            continue
        if not slug:
            problems.append(f"line {line}: a decision without a slug")
            continue
        if slug not in current:
            problems.append(f"line {line}: slug {slug!r} is not in data/canonicals.yaml")
            continue
        if slug in seen:
            problems.append(f"line {line}: {slug} appears twice (first on line {seen[slug]})")
            continue
        seen[slug] = line
        if decision is None:
            # undecided: counted as pending below, but a note without a decision is a mistake
            if row.get("comment") or any(row.get(f"proposed_{c}") for c in _PROPOSED):
                problems.append(f"line {line} ({slug}): a comment or proposal but no decision")
            continue
        d = Decision(slug, decision, row.get("comment", ""), row.get("row_hash", ""), {}, line)
        proposed = _read_proposed(row, line, slug, problems)
        d.proposed = proposed
        if decision in ("change", "remove") and not (d.comment or proposed):
            problems.append(f"line {line} ({slug}): '{decision}' needs a comment or a proposed_*"
                            f" value saying why/what")  # fmt: skip
        if decision in ("ok", "remove") and proposed:
            problems.append(f"line {line} ({slug}): proposed_* values only go with 'change'")
        if d.row_hash and d.row_hash != entry_hash(current[slug]):
            stale.append(slug)
        decisions.append(d)

    pending = [s for s in current if s not in {d.slug for d in decisions}]
    if stale and not allow_stale:
        problems.append(
            f"{len(stale)} row(s) changed in data/canonicals.yaml since the packet was made"
            f" (first: {', '.join(stale[:5])}); make a new packet, or pass --allow-stale"
        )
    if pending and not allow_partial:
        shown = ", ".join(pending[:10]) + (" …" if len(pending) > 10 else "")
        problems.append(f"{len(pending)} canonical(s) have no decision: {shown}."
                        " Decide them, or pass --allow-partial to record a partial sign-off")  # fmt: skip
    if problems:
        raise ReviewImportError(problems)
    return ImportResult(decisions, additions, pending, stale, warnings, encoding)


_PROPOSED = ("display_name_he", "base_unit", "critical_attrs", "soft_attrs", "rank")


def _read_proposed(row: Mapping[str, str], line: int, slug: str, problems: list[str]) -> dict[str, Any]:
    proposed: dict[str, Any] = {}
    where = f"line {line} ({slug})"
    if row.get("proposed_display_name_he"):
        proposed["display_name_he"] = row["proposed_display_name_he"]
    if row.get("proposed_base_unit"):
        unit = row["proposed_base_unit"].strip()
        if unit not in ("100g", "100ml", "unit", "kg"):
            problems.append(f"{where}: proposed_base_unit {unit!r} must be 100g, 100ml, unit or kg")
        else:
            proposed["base_unit"] = unit
    for col in ("critical_attrs", "soft_attrs"):
        cell = row.get(f"proposed_{col}", "")
        if cell:
            try:
                proposed[col] = parse_attrs_cell(cell)
            except ValueError as exc:
                problems.append(f"{where}: proposed_{col}: {exc}")
    if row.get("proposed_rank"):
        try:
            proposed["rank"] = int(row["proposed_rank"])
            if proposed["rank"] < 1:
                raise ValueError
        except ValueError:
            problems.append(f"{where}: proposed_rank must be a whole number from 1")
    return proposed


# --- applying decisions (in memory) and the diff --------------------------------------------------


def apply_decisions(
    entries: Sequence[Mapping[str, Any]], decisions: Sequence[Decision]
) -> list[dict[str, Any]]:
    """The entries after removals, field changes and rank moves, ranks renumbered 1..N.

    A rank move puts the canonical at that position of the list left after removals (applied in
    ascending order of the proposed position). Nothing here touches a file."""
    removed = {d.slug for d in decisions if d.decision == "remove"}
    changes = {d.slug: d.proposed for d in decisions if d.decision == "change" and d.proposed}
    out: list[dict[str, Any]] = []
    for e in sorted(entries, key=lambda e: e["rank"]):
        if e["slug"] in removed:
            continue
        new = dict(e)
        for key, value in changes.get(e["slug"], {}).items():
            if key != "rank":
                new[key] = value
        out.append(new)
    moves = sorted((p["rank"], slug) for slug, p in changes.items() if "rank" in p)
    for position, slug in moves:
        idx = next((i for i, e in enumerate(out) if e["slug"] == slug), None)
        if idx is None:
            continue
        entry = out.pop(idx)
        out.insert(min(position, len(out) + 1) - 1, entry)
    for n, e in enumerate(out, start=1):
        e["rank"] = n
    return out


def _scalar(value: Any) -> str:
    text = yaml.safe_dump(value, allow_unicode=True, default_flow_style=True, width=10**6)
    return text.strip().removesuffix("...").strip()


def _flow(mapping: Mapping[str, Any]) -> str:
    return "{" + ", ".join(f"{k}: {_scalar(v)}" for k, v in mapping.items()) + "}"


_ENTRY_ORDER = ("slug", "display_name_he", "taxonomy_id", "product_type", "base_unit",
                "critical_attrs", "soft_attrs", "rank", "is_mvp", "reference_barcodes")  # fmt: skip


def render_entries(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    """``canonicals:`` entries as lines in the file's style (flow-style attribute maps, no YAML
    anchors), the same renderer for before and after so the diff only shows real changes."""
    lines: list[str] = []
    for e in sorted(entries, key=lambda e: e["rank"]):
        keys = [k for k in _ENTRY_ORDER if k in e] + [k for k in e if k not in _ENTRY_ORDER]
        for i, key in enumerate(keys):
            value = e[key]
            if key in ("critical_attrs", "soft_attrs"):
                text = _flow(value)
            elif isinstance(value, list | tuple):
                text = "[" + ", ".join(_scalar(v) for v in value) + "]"
            else:
                text = _scalar(value)
            lines.append(("- " if i == 0 else "  ") + f"{key}: {text}")
    return lines


def validate_entries(catalog: Catalog, entries: Sequence[Mapping[str, Any]]) -> list[str]:
    """What ``smartcart-catalog seed`` would object to in the proposed entries (empty if none)."""
    try:
        canonicals = parse_canonicals({"canonicals": list(entries)}, catalog.taxonomy, catalog.rules)
    except SeedError as exc:
        return [line.strip() for line in str(exc).splitlines()[1:]] or [str(exc)]
    problems: list[str] = []
    unused = set(catalog.rules) - {c.product_type for c in canonicals}
    if unused:
        problems.append(f"product types left without a canonical: {sorted(unused)}")
    problems.extend(implied_conflicts(catalog.rules, catalog.extras, canonicals))
    return problems


@dataclass
class DiffReport:
    diff: str
    follow_ups: list[str]
    problems: list[str]
    changed_entries: int


def implied_diff(
    catalog: Catalog, entries: Sequence[Mapping[str, Any]], result: ImportResult
) -> DiffReport:
    after = apply_decisions(entries, result.decisions)
    diff = "".join(
        difflib.unified_diff(
            [line + "\n" for line in render_entries(entries)],
            [line + "\n" for line in render_entries(after)],
            fromfile="data/canonicals.yaml (as is, normalized rendering)",
            tofile="data/canonicals.yaml (with the sign-off decisions)",
            n=1,
        )
    )
    follow: list[str] = []
    for d in result.decisions:
        if d.decision == "change" and not d.proposed:
            follow.append(f"change {d.slug}: needs a manual edit - {d.comment}")
        elif d.decision == "change" and d.comment:
            follow.append(f"change {d.slug}: note - {d.comment}")
        elif d.decision == "remove" and d.comment:
            follow.append(f"remove {d.slug}: reason - {d.comment}")
    for d in result.additions:
        follow.append(f"add (not applied, needs taxonomy, type and attributes): "
                      f"{d.proposed.get('display_name_he')} - {d.comment}")  # fmt: skip
    changed = sum(1 for d in result.decisions if d.decision in ("change", "remove"))
    problems = validate_entries(catalog, after) if (diff or result.decisions) else []
    return DiffReport(diff, follow, problems, changed)


def signoff_document(
    result: ImportResult,
    *,
    reviewer: str,
    reviewed_on: str,
    note: str,
    canonicals_path: Path,
    total: int,
    csv_name: str,
) -> dict[str, Any]:
    status = "complete" if not result.pending else "partial"
    doc: dict[str, Any] = {
        "version": 1,
        "kind": "canonical-signoff",
        "issue": 15,
        "status": status,
        "reviewer": reviewer,
        "reviewed_on": reviewed_on,
        "note": note,
        "source": {
            "canonicals_file": "data/canonicals.yaml",
            "canonicals_sha256_12": sha_of_file(canonicals_path),
            "canonicals_total": total,
            "review_csv": csv_name,
            "csv_encoding": result.encoding,
        },
        "summary": result.counts,
        "decisions": [],
        "additions": [],
        "pending": list(result.pending),
    }
    for d in sorted(result.decisions, key=lambda d: d.line):
        item: dict[str, Any] = {"slug": d.slug, "decision": d.decision}
        if d.comment:
            item["comment"] = d.comment
        if d.proposed:
            item["proposed"] = d.proposed
        doc["decisions"].append(item)
    for d in result.additions:
        doc["additions"].append({"display_name_he": d.proposed.get("display_name_he"),
                                 "comment": d.comment,
                                 **{k: v for k, v in d.proposed.items() if k != "display_name_he"}})  # fmt: skip
    return doc


def write_signoff(doc: dict[str, Any], out_dir: Path, *, force: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"canonicals-{doc['reviewed_on']}.yaml"
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; pass --force to overwrite it")
    header = (
        "# Canonical sign-off (issue #15). Written by `smartcart-catalog review-import`;\n"
        "# the format is described in data/signoff/FORMAT.md. Nothing here changes\n"
        "# data/canonicals.yaml by itself: an engineer applies the decisions.\n"
    )
    body = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100)
    path.write_text(header + body, encoding="utf-8")
    return path


# --- command line ---------------------------------------------------------------------------------

app = typer.Typer(add_completion=False, help="Canonical review packet and sign-off.")


def review_packet(
    out: Annotated[Path, typer.Option(help="Output folder (created).")] = Path("dist/review"),
    examples: Annotated[
        str,
        typer.Option(help="Example sources in order: real, gold, db or none (comma separated)."),
    ] = "real,gold",
    per_canonical: Annotated[int, typer.Option(min=0, max=10, help="Examples per canonical.")] = PER_CANONICAL,
) -> None:
    """Write the HTML and CSV packet for the canonical sign-off (issue #15)."""
    from smartcart_catalog.settings import load_settings

    sources = [s.strip() for s in examples.split(",") if s.strip()] or ["none"]
    settings = load_settings()
    try:
        if "db" in sources:
            from smartcart_catalog import cli

            with cli.open_connection(settings) as conn:
                result = build_packet(settings.catalog_data_dir, out, sources=sources,
                                      per_canonical=per_canonical, conn=conn)  # fmt: skip
        else:
            result = build_packet(settings.catalog_data_dir, out, sources=sources,
                                  per_canonical=per_canonical)  # fmt: skip
    except (ValueError, SeedError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    s = result["summary"]
    typer.echo(f"{result['rows']} canonicals written")
    typer.echo(f"  {result['html']}")
    typer.echo(f"  {result['csv']}")
    for src in result["sources"]:
        typer.echo(f"  examples from {src}: {result['items_seen'].get(src, 0)} items,"
                   f" {result['items_mapped'].get(src, 0)} mapped")  # fmt: skip
    typer.echo(f"  with a real example: {s['with_real']}; synthetic only: {s['synthetic_only']};"
               f" none: {s['without']}")  # fmt: skip


def review_import(
    csv_file: Annotated[Path, typer.Argument(help="The filled review CSV.", exists=True, dir_okay=False)],
    reviewer: Annotated[str, typer.Option(help="Reviewer's name, recorded in the sign-off.")],
    reviewed_on: Annotated[str | None, typer.Option("--date", help="YYYY-MM-DD (default: today).")] = None,
    note: Annotated[str, typer.Option(help="Free text for the record (role, scope).")] = "",
    out_dir: Annotated[Path | None, typer.Option(help="Default: <data dir>/signoff.")] = None,
    allow_partial: Annotated[bool, typer.Option(help="Accept canonicals without a decision.")] = False,
    allow_stale: Annotated[bool, typer.Option(help="Accept rows changed since the packet.")] = False,
    force: Annotated[bool, typer.Option(help="Overwrite an existing sign-off file.")] = False,
    patch_out: Annotated[Path | None, typer.Option(help="Also save the diff to this file.")] = None,
) -> None:
    """Validate a filled CSV, write data/signoff/canonicals-<date>.yaml, print the implied diff.

    data/canonicals.yaml is never modified."""
    from smartcart_catalog.settings import load_settings

    if not reviewer.strip():
        raise typer.BadParameter("--reviewer must not be empty")
    day = reviewed_on or date.today().isoformat()
    try:
        date.fromisoformat(day)
    except ValueError as exc:
        raise typer.BadParameter("--date must be YYYY-MM-DD") from exc
    settings = load_settings()
    data_dir = settings.catalog_data_dir
    catalog = load_catalog(data_dir)
    entries = raw_entries(data_dir)
    try:
        result = parse_filled_csv(csv_file, entries, allow_partial=allow_partial,
                                  allow_stale=allow_stale)  # fmt: skip
    except ReviewImportError as exc:
        typer.echo(f"{csv_file}: {len(exc.problems)} problem(s), nothing written", err=True)
        for p in exc.problems:
            typer.echo(f"  - {p}", err=True)
        raise typer.Exit(1) from exc
    doc = signoff_document(result, reviewer=reviewer.strip(), reviewed_on=day, note=note,
                           canonicals_path=data_dir / "canonicals.yaml",
                           total=len(entries), csv_name=csv_file.name)  # fmt: skip
    try:
        path = write_signoff(doc, out_dir or data_dir / "signoff", force=force)
    except FileExistsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    report = implied_diff(catalog, entries, result)
    for w in result.warnings:
        typer.echo(f"warning: {w}", err=True)
    c = result.counts
    typer.echo(f"sign-off written: {path} ({doc['status']}: {c['ok']} ok, {c['change']} change,"
               f" {c['remove']} remove, {c['add']} add, {c['pending']} pending)")  # fmt: skip
    typer.echo("\nDiff implied for data/canonicals.yaml (NOT applied):")
    typer.echo(report.diff.rstrip() or "  (no change to the file)")
    if patch_out:
        patch_out.write_text(report.diff, encoding="utf-8")
        typer.echo(f"\ndiff saved to {patch_out}")
    if report.follow_ups:
        typer.echo("\nFor an engineer (not in the diff):")
        for line in report.follow_ups:
            typer.echo(f"  - {line}")
    if report.problems:
        typer.echo("\nThe proposed file would NOT pass `smartcart-catalog seed --check`:")
        for p in report.problems:
            typer.echo(f"  - {p}")
    else:
        typer.echo("\nThe proposed file passes the seed validation.")


def register(parent: typer.Typer) -> None:
    """Add ``review-packet`` and ``review-import`` to the catalog CLI."""
    parent.command("review-packet")(review_packet)
    parent.command("review-import")(review_import)


register(app)

if __name__ == "__main__":
    app()
