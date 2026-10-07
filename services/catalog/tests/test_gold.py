"""The synthetic gold set under data/gold is well formed and reproducible."""

from __future__ import annotations

import csv
import importlib.util
import sys
from collections import Counter
from pathlib import Path

import yaml

GOLD_DIR = Path(__file__).resolve().parents[3] / "data" / "gold"


def _builder():
    spec = importlib.util.spec_from_file_location("build_gold", GOLD_DIR / "build_gold.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("build_gold", module)
    spec.loader.exec_module(module)
    return module


def _files():
    catalog = yaml.safe_load((GOLD_DIR / "gold_catalog.yaml").read_text(encoding="utf-8"))
    with (GOLD_DIR / "gold_pairs.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return catalog, rows


def test_size_labels_and_categories() -> None:
    catalog, rows = _files()
    assert catalog["synthetic"] is True
    assert 2000 <= len(rows) <= 3000
    labels = Counter(r["label"] for r in rows)
    assert set(labels) == {"exact", "any_brand", "close", "no_match"}
    assert all(labels[k] >= 50 for k in labels)
    assert len({r["category"] for r in rows}) >= 6
    assert len({(r["item_key"], r["canonical_slug"]) for r in rows}) == len(rows)


def test_hard_negatives_are_present() -> None:
    _, rows = _files()

    def has(slug: str, label: str, needle: str) -> bool:
        return any(r["canonical_slug"] == slug and r["label"] == label and needle in r["note"]
                   for r in rows)  # fmt: skip

    assert has("milk-1pct-1l", "no_match", "fat_pct 3 vs 1")  # 3% vs 1%
    assert has("milk-3pct-1l", "no_match", "fat_pct 1 vs 3")
    assert has("salmon-fillet-fresh", "no_match", "state frozen vs fresh")  # fresh vs frozen
    assert has("salmon-fillet-frozen", "no_match", "state fresh vs frozen")
    assert has("almond-drink-1l", "no_match", "soy_drink vs almond_drink")  # soy vs almond
    assert has("soy-drink-1l", "no_match", "almond_drink vs soy_drink")
    assert has("cottage-5pct-250g", "close", "pack size 500 vs 250")  # 250 g vs 500 g
    assert has("cola-1.5l", "no_match", "cola_zero vs cola")
    assert any(r["note"].startswith("orphan") for r in rows)


def test_catalog_is_consistent() -> None:
    catalog, rows = _files()
    tax = {t["id"] for t in catalog["taxonomy"]}
    rules = {r["product_type"] for r in catalog["product_type_rules"]}
    slugs = {c["slug"] for c in catalog["canonicals"]}
    for c in catalog["canonicals"]:
        assert c["taxonomy_id"] in tax and c["product_type"] in rules
        assert c["base_unit"] in {"100g", "100ml", "unit", "kg"}
    assert {r["canonical_slug"] for r in rows} <= slugs
    assert {c["product_type"] for c in catalog["canonicals"]} <= set(
        catalog["lexicon"]["product_types"]
    )
    for t in catalog["taxonomy"]:
        assert t["parent_id"] is None or t["parent_id"] in tax


def test_build_is_deterministic_and_matches_the_committed_files() -> None:
    builder = _builder()
    catalog, rows = builder.build()
    committed_catalog, committed_rows = _files()
    as_text = [{k: str(v) for k, v in r.items()} for r in rows]
    assert as_text == committed_rows, (
        "data/gold is stale: run uv run python data/gold/build_gold.py"
    )
    assert yaml.safe_load(yaml.safe_dump(catalog, allow_unicode=True)) == committed_catalog
