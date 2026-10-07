"""Load the catalog seed files and upsert them into Postgres (issues #10 and #15).

Three files under ``data/``: ``taxonomy.yaml``, ``product_type_rules.yaml`` and
``canonicals.yaml``. Loading validates them against each other (a canonical's taxonomy node and
product type exist, its critical attributes are exactly the type's critical keys, no two
canonicals are indistinguishable at "any brand"). Seeding is idempotent: rows are upserted by
their natural key and a second run with unchanged files changes nothing (``updated_at`` stays).
Rows that disappear from the files are reported, never deleted, because matches may point at them.

A canonical may list ``reference_barcodes`` (issue #92): the barcodes that are exactly this
product, stored in ``canonical_products.reference_barcodes`` and used by the judge's exact rule.
An entry without the key leaves the stored barcodes untouched.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_args

import psycopg
import yaml
from pydantic import ValidationError

from smartcart_catalog.models import (
    AttributeKey,
    Attributes,
    CanonicalProduct,
    ProductTypeRule,
)
from smartcart_catalog.taxonomy import Taxonomy, default_data_dir, load_taxonomy

MIN_CANONICALS, MAX_CANONICALS = 150, 300
ATTRIBUTE_KEYS: frozenset[str] = frozenset(get_args(AttributeKey))
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PRODUCT_TYPE = re.compile(r"^[a-z][a-z0-9_]*$")
_BARCODE = re.compile(r"^\d{8,14}$")


class SeedError(ValueError):
    """A seed file is inconsistent. The message lists every problem found."""


@dataclass(frozen=True)
class RuleExtras:
    """Rule-extractor hints stored next to a product type rule (not in Postgres)."""

    keywords: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    implied: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Catalog:
    taxonomy: Taxonomy
    rules: dict[str, ProductTypeRule]
    extras: dict[str, RuleExtras]
    canonicals: tuple[CanonicalProduct, ...]


# --- loading and validation ----------------------------------------------------------------------


def parse_rules(doc: dict[str, Any]) -> tuple[dict[str, ProductTypeRule], dict[str, RuleExtras]]:
    raw = doc.get("rules") if isinstance(doc, dict) else None
    if not isinstance(raw, list):
        raise SeedError("product_type_rules file must have a 'rules' list")
    problems: list[str] = []
    rules: dict[str, ProductTypeRule] = {}
    extras: dict[str, RuleExtras] = {}
    for entry in raw:
        pt = str(entry.get("product_type", ""))
        if not _PRODUCT_TYPE.match(pt):
            problems.append(f"bad product_type {pt!r}")
            continue
        if pt in rules:
            problems.append(f"{pt}: duplicate product_type")
        crit = tuple(entry.get("critical_keys") or ())
        soft = tuple(entry.get("soft_keys") or ())
        bad = (set(crit) | set(soft)) - ATTRIBUTE_KEYS
        if bad:
            problems.append(f"{pt}: unknown attribute keys {sorted(bad)}")
        both = set(crit) & set(soft)
        if both:
            problems.append(f"{pt}: keys both critical and soft {sorted(both)}")
        if {"product_type", "category_path"} & (set(crit) | set(soft)):
            problems.append(f"{pt}: product_type/category_path are implicit, do not list them")
        unknown = set(entry) - {
            "product_type", "critical_keys", "soft_keys", "keywords", "exclude", "implied"
        }
        if unknown:
            problems.append(f"{pt}: unknown fields {sorted(unknown)}")
        implied = dict(entry.get("implied") or {})
        try:
            Attributes(**implied)
        except ValidationError as exc:
            problems.append(f"{pt}: bad implied attributes: {exc.errors()[0]['msg']}")
        rules[pt] = ProductTypeRule(product_type=pt, critical_keys=crit, soft_keys=soft)
        extras[pt] = RuleExtras(
            keywords=tuple(entry.get("keywords") or ()),
            exclude=tuple(entry.get("exclude") or ()),
            implied=implied,
        )
    if problems:
        raise SeedError("invalid product type rules:\n  " + "\n  ".join(problems))
    return rules, extras


def parse_canonicals(
    doc: dict[str, Any], taxonomy: Taxonomy, rules: dict[str, ProductTypeRule]
) -> tuple[CanonicalProduct, ...]:
    raw = doc.get("canonicals") if isinstance(doc, dict) else None
    if not isinstance(raw, list):
        raise SeedError("canonicals file must have a 'canonicals' list")
    problems: list[str] = []
    out: list[CanonicalProduct] = []
    for entry in raw:
        slug = str(entry.get("slug", ""))
        try:
            cp = CanonicalProduct(**entry)
        except ValidationError as exc:
            problems.append(f"{slug}: {exc.errors()[0]['loc']} {exc.errors()[0]['msg']}")
            continue
        if not _SLUG.match(cp.slug):
            problems.append(f"{slug}: slug must be lowercase words joined by '-'")
        if not cp.display_name_he.strip():
            problems.append(f"{slug}: missing display_name_he")
        if cp.taxonomy_id not in taxonomy:
            problems.append(f"{slug}: taxonomy node {cp.taxonomy_id} does not exist")
        elif taxonomy.get(cp.taxonomy_id).level < 3:
            problems.append(f"{slug}: hangs from {cp.taxonomy_id}; use a product type node (3+)")
        rule = rules.get(cp.product_type)
        if rule is None:
            problems.append(f"{slug}: product_type {cp.product_type} has no rule")
        else:
            if set(cp.critical_attrs) != set(rule.critical_keys):
                problems.append(
                    f"{slug}: critical_attrs {sorted(cp.critical_attrs)} must be exactly the"
                    f" critical keys of {cp.product_type} {sorted(rule.critical_keys)}"
                )
            extra_soft = set(cp.soft_attrs) - set(rule.soft_keys) - {"unit"}
            if extra_soft:
                problems.append(f"{slug}: soft_attrs {sorted(extra_soft)} are not soft keys")
        for label, attrs in (("critical", cp.critical_attrs), ("soft", cp.soft_attrs)):
            try:
                Attributes(**attrs)
            except (ValidationError, TypeError) as exc:
                problems.append(f"{slug}: bad {label} attribute value: {exc}")
        if cp.rank is None:
            problems.append(f"{slug}: missing rank")
        bad_codes = [b for b in cp.reference_barcodes if not _BARCODE.match(b)]
        if bad_codes:
            problems.append(f"{slug}: reference_barcodes must be 8-14 digits: {bad_codes}")
        out.append(cp)

    for slug, n in Counter(c.slug for c in out).items():
        if n > 1:
            problems.append(f"{slug}: duplicate slug")
    owner: dict[str, str] = {}
    for c in out:
        for code in c.reference_barcodes:
            if code in owner and owner[code] != c.slug:
                problems.append(f"{c.slug}: barcode {code} is also a reference of {owner[code]}")
            owner.setdefault(code, c.slug)
    ranks = sorted(c.rank for c in out if c.rank is not None)
    if ranks != list(range(1, len(out) + 1)):
        problems.append("ranks must be 1..N without gaps or duplicates")
    seen: dict[tuple[str, str], str] = {}
    for c in out:
        key = (c.product_type, json.dumps(c.critical_attrs, sort_keys=True, default=str))
        if key in seen:
            problems.append(
                f"{c.slug}: same product_type and critical_attrs as {seen[key]}; they would be"
                " indistinguishable at 'any brand'"
            )
        seen.setdefault(key, c.slug)
    if not MIN_CANONICALS <= len(out) <= MAX_CANONICALS:
        problems.append(f"{len(out)} canonicals; the MVP range is {MIN_CANONICALS}-{MAX_CANONICALS}")
    if problems:
        raise SeedError("invalid canonicals:\n  " + "\n  ".join(problems))
    return tuple(out)


def load_catalog(data_dir: Path | None = None) -> Catalog:
    data_dir = data_dir or default_data_dir()
    taxonomy = load_taxonomy(data_dir / "taxonomy.yaml")
    rules, extras = parse_rules(_read(data_dir / "product_type_rules.yaml"))
    canonicals = parse_canonicals(_read(data_dir / "canonicals.yaml"), taxonomy, rules)
    unused = set(rules) - {c.product_type for c in canonicals}
    if unused:
        raise SeedError(f"product types without a canonical: {sorted(unused)}")
    return Catalog(taxonomy, rules, extras, canonicals)


def _read(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# --- seeding ---------------------------------------------------------------------------------------


@dataclass
class SeedCounts:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    not_in_file: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        s = f"{self.inserted} inserted, {self.updated} updated, {self.unchanged} unchanged"
        if self.not_in_file:
            s += f", {len(self.not_in_file)} in the database but not in the file (kept)"
        return s


@dataclass
class SeedReport:
    taxonomy: SeedCounts
    rules: SeedCounts
    canonicals: SeedCounts


def _tally(counts: SeedCounts, row: tuple[bool] | None) -> None:
    # The upserts below only UPDATE when a column differs (WHERE ... IS DISTINCT FROM), so
    # RETURNING gives no row for unchanged ones; xmax = 0 marks a fresh insert.
    if row is None:
        counts.unchanged += 1
    elif row[0]:
        counts.inserted += 1
    else:
        counts.updated += 1


def seed_taxonomy(conn: psycopg.Connection, taxonomy: Taxonomy) -> SeedCounts:
    counts = SeedCounts()
    for node in sorted(taxonomy.nodes, key=lambda n: (n.level, n.sort)):
        row = conn.execute(
            "INSERT INTO taxonomy AS t (id, parent_id, level, name_he, name_en, sort)"
            " VALUES (%s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (id) DO UPDATE SET parent_id = EXCLUDED.parent_id,"
            "   level = EXCLUDED.level, name_he = EXCLUDED.name_he,"
            "   name_en = EXCLUDED.name_en, sort = EXCLUDED.sort"
            " WHERE (t.parent_id, t.level, t.name_he, t.name_en, t.sort) IS DISTINCT FROM"
            "   (EXCLUDED.parent_id, EXCLUDED.level, EXCLUDED.name_he, EXCLUDED.name_en,"
            "    EXCLUDED.sort)"
            " RETURNING (xmax = 0)",
            (node.id, node.parent_id, node.level, node.name_he, node.name_en, node.sort),
        ).fetchone()
        _tally(counts, row)
    ids = {n.id for n in taxonomy.nodes}
    counts.not_in_file = sorted(
        r[0] for r in conn.execute("SELECT id FROM taxonomy").fetchall() if r[0] not in ids
    )
    return counts


def seed_rules(conn: psycopg.Connection, rules: dict[str, ProductTypeRule]) -> SeedCounts:
    counts = SeedCounts()
    for rule in rules.values():
        row = conn.execute(
            "INSERT INTO product_type_rules AS r (product_type, critical_keys, soft_keys)"
            " VALUES (%s, %s, %s)"
            " ON CONFLICT (product_type) DO UPDATE SET critical_keys = EXCLUDED.critical_keys,"
            "   soft_keys = EXCLUDED.soft_keys"
            " WHERE (r.critical_keys, r.soft_keys) IS DISTINCT FROM"
            "   (EXCLUDED.critical_keys, EXCLUDED.soft_keys)"
            " RETURNING (xmax = 0)",
            (rule.product_type, list(rule.critical_keys), list(rule.soft_keys)),
        ).fetchone()
        _tally(counts, row)
    counts.not_in_file = sorted(
        r[0]
        for r in conn.execute("SELECT product_type FROM product_type_rules").fetchall()
        if r[0] not in rules
    )
    return counts


def _jsonb(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def seed_canonicals(
    conn: psycopg.Connection, canonicals: tuple[CanonicalProduct, ...]
) -> SeedCounts:
    counts = SeedCounts()
    for c in canonicals:
        row = conn.execute(
            "INSERT INTO canonical_products AS c (taxonomy_id, slug, display_name_he,"
            "   product_type, base_unit, critical_attrs, soft_attrs, is_mvp, rank,"
            "   reference_barcodes)"
            " VALUES (%(tax)s, %(slug)s, %(name)s, %(pt)s, %(bu)s, %(crit)s::jsonb,"
            "   %(soft)s::jsonb, %(mvp)s, %(rank)s, %(codes)s)"
            " ON CONFLICT (slug) DO UPDATE SET taxonomy_id = EXCLUDED.taxonomy_id,"
            "   display_name_he = EXCLUDED.display_name_he,"
            "   product_type = EXCLUDED.product_type, base_unit = EXCLUDED.base_unit,"
            "   critical_attrs = EXCLUDED.critical_attrs, soft_attrs = EXCLUDED.soft_attrs,"
            "   is_mvp = EXCLUDED.is_mvp, rank = EXCLUDED.rank,"
            "   reference_barcodes = CASE WHEN %(has_codes)s THEN EXCLUDED.reference_barcodes"
            "                             ELSE c.reference_barcodes END"
            " WHERE (c.taxonomy_id, c.display_name_he, c.product_type, c.base_unit,"
            "        c.critical_attrs, c.soft_attrs, c.is_mvp, c.rank) IS DISTINCT FROM"
            "   (EXCLUDED.taxonomy_id, EXCLUDED.display_name_he, EXCLUDED.product_type,"
            "    EXCLUDED.base_unit, EXCLUDED.critical_attrs, EXCLUDED.soft_attrs,"
            "    EXCLUDED.is_mvp, EXCLUDED.rank)"
            "   OR (%(has_codes)s AND c.reference_barcodes IS DISTINCT FROM"
            "       EXCLUDED.reference_barcodes)"
            " RETURNING (xmax = 0)",
            {
                "tax": c.taxonomy_id, "slug": c.slug, "name": c.display_name_he,
                "pt": c.product_type, "bu": c.base_unit, "crit": _jsonb(c.critical_attrs),
                "soft": _jsonb(c.soft_attrs), "mvp": c.is_mvp, "rank": c.rank,
                "codes": list(c.reference_barcodes),
                # a file entry without the key leaves the stored barcodes as they are
                "has_codes": "reference_barcodes" in c.model_fields_set,
            },
        ).fetchone()
        _tally(counts, row)
    slugs = {c.slug for c in canonicals}
    counts.not_in_file = sorted(
        r[0]
        for r in conn.execute("SELECT slug FROM canonical_products").fetchall()
        if r[0] not in slugs
    )
    return counts


def seed_all(conn: psycopg.Connection, catalog: Catalog) -> SeedReport:
    """Taxonomy, then rules, then canonicals (foreign-key order), in the caller's transaction."""
    return SeedReport(
        taxonomy=seed_taxonomy(conn, catalog.taxonomy),
        rules=seed_rules(conn, catalog.rules),
        canonicals=seed_canonicals(conn, catalog.canonicals),
    )
