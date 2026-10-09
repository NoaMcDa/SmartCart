"""Canonical products and product type rules (issue #15), and idempotent seeding."""

from __future__ import annotations

import copy
from pathlib import Path

import psycopg
import pytest
import yaml

from smartcart_catalog.seed import (
    MAX_CANONICALS,
    MIN_CANONICALS,
    SeedError,
    implied_conflicts,
    load_catalog,
    parse_canonicals,
    parse_rules,
    seed_all,
)
from smartcart_catalog.taxonomy import default_data_dir


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture(scope="module")
def by_slug(catalog):
    return {c.slug: c for c in catalog.canonicals}


def test_count_in_mvp_range(catalog) -> None:
    assert MIN_CANONICALS <= len(catalog.canonicals) <= MAX_CANONICALS


def test_every_canonical_is_complete(catalog) -> None:
    for c in catalog.canonicals:
        assert c.taxonomy_id in catalog.taxonomy
        assert c.display_name_he.strip()
        assert c.base_unit in ("100g", "100ml", "unit", "kg")
        assert c.is_mvp and c.rank is not None
        rule = catalog.rules[c.product_type]
        assert set(c.critical_attrs) == set(rule.critical_keys)


def test_ranks_are_a_permutation(catalog) -> None:
    assert sorted(c.rank for c in catalog.canonicals) == list(range(1, len(catalog.canonicals) + 1))


def test_every_product_type_has_rules_and_keywords(catalog) -> None:
    used = {c.product_type for c in catalog.canonicals}
    assert used == set(catalog.rules)
    for pt, extra in catalog.extras.items():
        assert extra.keywords, f"{pt} has no rule-extractor keywords"


def test_three_and_one_percent_milk_are_distinct(by_slug) -> None:
    m3, m1 = by_slug["milk-fresh-3"], by_slug["milk-fresh-1"]
    assert m3.product_type == m1.product_type == "milk"
    assert m3.critical_attrs["fat_pct"] != m1.critical_attrs["fat_pct"]


def test_fresh_and_frozen_salmon_are_distinct(by_slug) -> None:
    fresh, frozen = by_slug["salmon-fillet-fresh"], by_slug["salmon-fillet-frozen"]
    assert fresh.product_type == frozen.product_type
    assert (fresh.critical_attrs["state"], frozen.critical_attrs["state"]) == ("fresh", "frozen")


def test_plant_drinks_are_separate_product_types(by_slug) -> None:
    types = {by_slug[s].product_type for s in ("soy-drink", "almond-drink", "oat-drink")}
    assert types == {"soy_drink", "almond_drink", "oat_drink"}


def test_plant_drink_base_is_critical(catalog, by_slug) -> None:
    """Issue #102: ``base`` is a critical key of the plant drinks and their canonicals carry it."""
    for slug, base in (("soy-drink", "soy"), ("almond-drink", "almond"), ("oat-drink", "oat")):
        c = by_slug[slug]
        assert "base" in catalog.rules[c.product_type].critical_keys
        assert c.critical_attrs == {"base": base}
        assert catalog.extras[c.product_type].implied.get("base") == base


def test_an_implied_critical_value_no_canonical_carries_is_rejected(catalog) -> None:
    rules = copy.deepcopy(_raw("product_type_rules.yaml"))
    soy = next(r for r in rules["rules"] if r["product_type"] == "soy_drink")
    soy["implied"] = {"base": "almond"}
    parsed, extras = parse_rules(rules)
    assert implied_conflicts(parsed, extras, catalog.canonicals) == [
        "soy_drink: implies base=almond, canonicals have ['soy']"
    ]
    assert implied_conflicts(catalog.rules, catalog.extras, catalog.canonicals) == []


def test_no_two_canonicals_share_type_and_critical_values(catalog) -> None:
    keys = [(c.product_type, tuple(sorted(c.critical_attrs.items()))) for c in catalog.canonicals]
    assert len(keys) == len(set(keys))


# --- validation catches mistakes ------------------------------------------------------------------


def _raw(name: str) -> dict:
    return yaml.safe_load((default_data_dir() / name).read_text(encoding="utf-8"))


def test_duplicate_critical_values_rejected(catalog) -> None:
    doc = copy.deepcopy(_raw("canonicals.yaml"))
    twin = copy.deepcopy(next(c for c in doc["canonicals"] if c["slug"] == "milk-fresh-3"))
    twin.update(slug="milk-fresh-3-copy", rank=len(doc["canonicals"]) + 1)
    doc["canonicals"].append(twin)
    with pytest.raises(SeedError, match="indistinguishable at 'any brand'"):
        parse_canonicals(doc, catalog.taxonomy, catalog.rules)


def test_critical_attrs_must_match_rule(catalog) -> None:
    doc = copy.deepcopy(_raw("canonicals.yaml"))
    milk = next(c for c in doc["canonicals"] if c["slug"] == "milk-fresh-1")
    del milk["critical_attrs"]["state"]
    with pytest.raises(SeedError, match="must be exactly the critical keys of milk"):
        parse_canonicals(doc, catalog.taxonomy, catalog.rules)


def test_unknown_taxonomy_and_bad_value_rejected(catalog) -> None:
    doc = copy.deepcopy(_raw("canonicals.yaml"))
    doc["canonicals"][0]["taxonomy_id"] = "dairy.milk.goat"
    doc["canonicals"][1]["critical_attrs"]["state"] = "raw"
    with pytest.raises(SeedError) as exc:
        parse_canonicals(doc, catalog.taxonomy, catalog.rules)
    assert "dairy.milk.goat does not exist" in str(exc.value)
    assert "bad critical attribute value" in str(exc.value)


def test_reference_barcodes_are_validated(catalog) -> None:
    doc = copy.deepcopy(_raw("canonicals.yaml"))
    doc["canonicals"][0]["reference_barcodes"] = ["7290000000017", "12ab"]
    doc["canonicals"][1]["reference_barcodes"] = [7290000000017]
    with pytest.raises(SeedError) as exc:
        parse_canonicals(doc, catalog.taxonomy, catalog.rules)
    assert "must be 8-14 digits: ['12ab']" in str(exc.value)
    assert "barcode 7290000000017 is also a reference of" in str(exc.value)


def test_rules_reject_unknown_keys() -> None:
    with pytest.raises(SeedError, match="unknown attribute keys"):
        parse_rules({"rules": [{"product_type": "milk", "critical_keys": ["fat"]}]})


# --- seeding ------------------------------------------------------------------------------------------


@pytest.mark.db
@pytest.mark.pgvector
def test_seed_is_idempotent(db: psycopg.Connection, catalog) -> None:
    first = seed_all(db, catalog)
    assert first.taxonomy.inserted == len(catalog.taxonomy)
    assert first.rules.inserted == len(catalog.rules)
    assert first.canonicals.inserted == len(catalog.canonicals)
    stamp = db.execute("SELECT max(updated_at) FROM canonical_products").fetchone()[0]

    second = seed_all(db, catalog)
    for counts in (second.taxonomy, second.rules, second.canonicals):
        assert (counts.inserted, counts.updated) == (0, 0)
        assert counts.not_in_file == []
    assert second.canonicals.unchanged == len(catalog.canonicals)
    assert db.execute("SELECT max(updated_at) FROM canonical_products").fetchone()[0] == stamp

    row = db.execute(
        "SELECT taxonomy_id, product_type, base_unit, critical_attrs, rank FROM canonical_products"
        " WHERE slug = 'milk-fresh-3'"
    ).fetchone()
    assert row == ("dairy.milk.fresh", "milk", "100ml", {"fat_pct": 3, "state": "fresh"}, 1)
    keys = db.execute(
        "SELECT critical_keys, soft_keys FROM product_type_rules WHERE product_type = 'milk'"
    ).fetchone()
    assert keys == (["fat_pct", "state"], ["pack_size", "brand"])


@pytest.mark.db
@pytest.mark.pgvector
def test_seed_updates_changed_rows_only(db: psycopg.Connection, tmp_path: Path) -> None:
    seed_all(db, load_catalog())
    for name in ("taxonomy.yaml", "product_type_rules.yaml", "canonicals.yaml"):
        (tmp_path / name).write_text(
            (default_data_dir() / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    doc = yaml.safe_load((tmp_path / "canonicals.yaml").read_text(encoding="utf-8"))
    doc["canonicals"][0]["display_name_he"] = "חלב טרי 3% (שם חדש)"
    (tmp_path / "canonicals.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8"
    )
    report = seed_all(db, load_catalog(tmp_path))
    assert (report.canonicals.inserted, report.canonicals.updated) == (0, 1)
    assert report.taxonomy.updated == 0


@pytest.mark.db
@pytest.mark.pgvector
def test_seed_loads_reference_barcodes_when_present(db: psycopg.Connection, tmp_path: Path) -> None:
    """``reference_barcodes`` in canonicals.yaml land in the column; an entry without the key
    leaves stored barcodes alone (issue #92)."""
    seed_all(db, load_catalog())
    for name in ("taxonomy.yaml", "product_type_rules.yaml", "canonicals.yaml"):
        (tmp_path / name).write_text(
            (default_data_dir() / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    doc = yaml.safe_load((tmp_path / "canonicals.yaml").read_text(encoding="utf-8"))
    doc["canonicals"][0]["reference_barcodes"] = ["7290004131074"]
    (tmp_path / "canonicals.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8"
    )
    report = seed_all(db, load_catalog(tmp_path))
    assert report.canonicals.updated == 1
    slug = doc["canonicals"][0]["slug"]
    codes = "SELECT reference_barcodes FROM canonical_products WHERE slug = %s"
    assert db.execute(codes, (slug,)).fetchone()[0] == ["7290004131074"]
    assert seed_all(db, load_catalog(tmp_path)).canonicals.updated == 0
    # the shipped file has no barcodes for this canonical: the stored ones stay
    assert seed_all(db, load_catalog()).canonicals.updated == 0
    assert db.execute(codes, (slug,)).fetchone()[0] == ["7290004131074"]
