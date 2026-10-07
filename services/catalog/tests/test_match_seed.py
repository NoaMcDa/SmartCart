"""Shared seed for the matching database tests (imported by the other test_* modules).

The schema is the contract: a small taxonomy, product type rules and canonicals are inserted
with plain SQL, independent of the catalog seed files.
"""

from __future__ import annotations

import json

import psycopg

from smartcart_catalog.embed import HashEmbedder, embed_canonicals, embed_items

CHAIN = "test-match"
MILK3_BARCODE = "7290000000017"

TAXONOMY = [
    ("dairy", None, 1, "חלב"),
    ("dairy.milk", "dairy", 2, "חלב"),
    ("dairy.plant_drinks", "dairy", 2, "משקאות צמחיים"),
    ("meat_fish", None, 1, "בשר ודגים"),
    ("meat_fish.fish", "meat_fish", 2, "דגים"),
    ("pantry", None, 1, "מזווה"),
    ("pantry.oil", "pantry", 2, "שמן"),
]
RULES = [
    ("milk", ["fat_pct", "state"], ["pack_size", "brand"]),
    ("soy_drink", [], ["pack_size", "flavor", "brand"]),
    ("almond_drink", [], ["pack_size", "flavor", "brand"]),
    ("salmon", ["state"], ["pack_size", "brand"]),
    ("olive_oil", [], ["pack_size", "brand"]),
]
CANONICALS = [
    ("dairy.milk", "t-milk-3", "חלב טרי 3% 1 ליטר", "milk", "100ml",
     {"fat_pct": 3, "state": "fresh"}, {"pack_size": 1, "unit": "l", "barcodes": [MILK3_BARCODE]}),
    ("dairy.milk", "t-milk-1", "חלב טרי 1% 1 ליטר", "milk", "100ml",
     {"fat_pct": 1, "state": "fresh"}, {"pack_size": 1, "unit": "l"}),
    ("dairy.plant_drinks", "t-soy", "משקה סויה 1 ליטר", "soy_drink", "100ml", {},
     {"pack_size": 1, "unit": "l"}),
    ("dairy.plant_drinks", "t-almond", "משקה שקדים 1 ליטר", "almond_drink", "100ml", {},
     {"pack_size": 1, "unit": "l"}),
    ("meat_fish.fish", "t-salmon-fresh", "פילה סלמון טרי", "salmon", "100g",
     {"state": "fresh"}, {}),
    ("meat_fish.fish", "t-salmon-frozen", "פילה סלמון קפוא", "salmon", "100g",
     {"state": "frozen"}, {}),
    ("pantry.oil", "t-olive-oil", "שמן זית כתית מעולה 750 מ\"ל", "olive_oil", "100ml", {},
     {"pack_size": 750, "unit": "ml"}),
]  # fmt: skip

LEXICON = {
    "product_types": {
        "milk": {"keywords": ["חלב", "חלב טרי"], "taxonomy_id": "dairy.milk"},
        "soy_drink": {"keywords": ["משקה סויה", "סויה"], "taxonomy_id": "dairy.plant_drinks"},
        "almond_drink": {"keywords": ["משקה שקדים"], "taxonomy_id": "dairy.plant_drinks"},
        "salmon": {"keywords": ["סלמון", "פילה סלמון"], "taxonomy_id": "meat_fish.fish"},
        "olive_oil": {"keywords": ["שמן זית"], "taxonomy_id": "pantry.oil"},
    }
}


def seed_catalog(db: psycopg.Connection) -> dict[str, int]:
    """Insert the small catalog; returns slug -> canonical id."""
    for tid, parent, level, name in TAXONOMY:
        db.execute(
            "INSERT INTO taxonomy (id, parent_id, level, name_he) VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (id) DO NOTHING",
            (tid, parent, level, name),
        )
    for pt, ck, sk in RULES:
        db.execute(
            "INSERT INTO product_type_rules (product_type, critical_keys, soft_keys)"
            " VALUES (%s, %s, %s) ON CONFLICT (product_type) DO NOTHING",
            (pt, ck, sk),
        )
    ids = {}
    for tax, slug, name, pt, bu, crit, soft in CANONICALS:
        ids[slug] = db.execute(
            "INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type,"
            " base_unit, critical_attrs, soft_attrs, rank) VALUES (%s, %s, %s, %s, %s, %s, %s,"
            " %s) RETURNING id",
            (tax, slug, name, pt, bu, json.dumps(crit), json.dumps(soft, ensure_ascii=False),
             len(ids) + 1),
        ).fetchone()[0]  # fmt: skip
    return ids


def add_item(
    db: psycopg.Connection, name: str, barcode: str | None = None, *, is_weighed: bool = False
) -> int:
    db.execute(
        "INSERT INTO chains (id, name, portal) VALUES (%s, 'Match test chain', 'other')"
        " ON CONFLICT (id) DO NOTHING",
        (CHAIN,),
    )
    n = db.execute("SELECT count(*) FROM items WHERE chain_id = %s", (CHAIN,)).fetchone()[0]
    return db.execute(
        "INSERT INTO items (chain_id, item_code, barcode, raw_name, is_weighed)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (CHAIN, f"m{n + 1:05d}", barcode, name, is_weighed),
    ).fetchone()[0]


def embed_all(db: psycopg.Connection) -> None:
    emb = HashEmbedder()
    embed_canonicals(db, emb)
    embed_items(db, emb)


def test_seed_helpers_are_importable() -> None:
    assert {c[1] for c in CANONICALS} >= {"t-milk-3", "t-milk-1", "t-soy", "t-almond"}
