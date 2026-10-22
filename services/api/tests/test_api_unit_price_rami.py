"""A Rami Levy weight/volume line, from the real file to /compare (docs/real-day-dry-run.md,
finding 8).

The real PriceFull of 2026-10-21 is loaded by the ingest loader. Three of its soft drinks are
mapped to one "any brand" canonical (base unit 100 ml):

* ``קולה 2 ליטר בודד``: 8.60 for 2 l, published 4.30 per liter (labelled "ליטר"): 0.43 per 100 ml;
* ``טמפו סודה 500 מ"ל``: 2.90 for 500 ml, published **0.01** labelled "100 מיליליטר" (it is the price
  of one milliliter): 0.58 per 100 ml;
* ``מיץ לימונענע 400 מ"ל``: 7.90 for 400 ml, published 0.02 the same way: 1.975 per 100 ml.

Read as labelled, the 500 ml soda (0.01) beat the 2 l cola (0.43) by a factor of 43 and the
precompute picked it; the cola is the cheapest per 100 ml. The test follows the value through
``precompute`` into ``effective_prices`` and ``/compare``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from api_world import World, add_store
from psycopg.types.json import Jsonb

from smartcart_api.embedding import query_embedder, to_pgvector
from smartcart_api.precompute import precompute_effective_prices
from smartcart_ingest import tracking
from smartcart_ingest.loader import load
from tests.test_adapters import FIXTURES, chain_adapters, parse_fixture

D = Decimal
RAMI = "7290058140886"
COLA, SODA, JUICE = "7290110119508", "7290000135342", "7290001045633"

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]


@pytest.fixture
def rami(db, world: World):
    """The real Rami Levy PriceFull loaded, its store placed 1 km from the origin, and the three
    soft drinks mapped to one canonical. Returns (item ids by code, canonical id)."""
    adapter = chain_adapters()["ramilevy"]()
    parsed = parse_fixture(adapter, next((FIXTURES / "ramilevy" / "real").glob("PriceFull*")))
    row, _ = tracking.register(db, parsed.raw)
    tracking.mark_downloaded(db, row.id, parsed.raw.path)
    load(db, parsed, adapter)
    placed = add_store(db, "t-c1", "tmp", 1.0)
    db.execute(
        "UPDATE stores SET geog = (SELECT geog FROM stores WHERE id = %s) WHERE chain_id = %s",
        (placed, RAMI),
    )
    emb = query_embedder()
    canon = db.execute(
        "INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type,"
        " base_unit, critical_attrs, soft_attrs, embedding, embedding_model, is_mvp, rank)"
        " VALUES ('t.snacks.wafer', 't-soft-drink', 'משקה קל', 't_wafer', '100ml', %s, %s,"
        " %s::vector, %s, true, 30) RETURNING id",
        (Jsonb({}), Jsonb({}), to_pgvector(emb.embed_one("משקה קל")), emb.model_name),
    ).fetchone()[0]
    ids: dict[str, int] = {}
    for code in (COLA, SODA, JUICE):
        iid = db.execute(
            "SELECT id FROM items WHERE chain_id = %s AND item_code = %s", (RAMI, code)
        ).fetchone()[0]
        ids[code] = iid
        db.execute(
            "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
            " VALUES (%s, %s, 'any_brand', 0.95, 'rule')",
            (iid, canon),
        )
        db.execute(
            "INSERT INTO item_attributes (item_id, attrs, verified_keys, extractor)"
            " VALUES (%s, %s, '{}', 'rule')",
            (iid, Jsonb({})),
        )
    return ids, canon


def test_the_loaded_unit_prices_are_per_100ml(db, rami) -> None:
    ids, _ = rami
    got = dict(
        db.execute(
            "SELECT item_id, unit_price FROM prices WHERE item_id = ANY(%s)", (list(ids.values()),)
        ).fetchall()
    )
    assert got == {ids[COLA]: D("0.43"), ids[SODA]: D("0.58"), ids[JUICE]: D("1.975")}


def test_the_precompute_picks_the_cheapest_per_100ml_not_the_100x_one(db, rami) -> None:
    ids, canon = rami
    precompute_effective_prices(db, chains=[RAMI])
    rows = db.execute(
        "SELECT item_id, shelf_price, effective_unit_price, uom FROM effective_prices"
        " WHERE canonical_id = %s AND flex_level = 'any_brand'",
        (canon,),
    ).fetchall()
    assert len(rows) == 1
    item_id, shelf, unit, uom = rows[0]
    assert item_id == ids[COLA]  # 0.43 per 100 ml, not the 500 ml soda that read as 0.01
    assert (shelf, unit, uom) == (D("8.60"), D("0.4300"), "100ml")


def test_compare_prices_the_line_with_the_corrected_item(client, db, rami) -> None:
    ids, canon = rami
    precompute_effective_prices(db, chains=[RAMI])
    store_id = db.execute("SELECT id FROM stores WHERE chain_id = %s", (RAMI,)).fetchone()[0]
    body = {
        "items": [{"canonical_id": canon, "quantity": 1, "flex_level": "any_brand"}],
        "location": {"lon": 34.78, "lat": 32.08, "radius_m": 5000},
    }
    r = client.post("/compare", json=body)
    assert r.status_code == 200, r.text
    stores = {s["store_id"]: s for s in r.json()["stores"]}
    line = stores[store_id]["items"][0]
    assert line["item_id"] == ids[COLA]
    assert (D(line["shelf_price"]), D(line["effective_unit_price"]), line["uom"]) == (
        D("8.60"),
        D("0.43"),
        "100ml",
    )
    assert D(line["line_total"]) == D("8.60")
