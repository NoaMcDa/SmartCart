"""Smart-cart swap suggestions (issue #45): POST /optimize/swaps."""

from __future__ import annotations

from decimal import Decimal
from itertools import product

import pytest
from api_world import EMB, World, add_price
from psycopg.types.json import Jsonb

from smartcart_api import schemas
from smartcart_api.basket import price_baskets, store_info
from smartcart_api.embedding import to_pgvector
from smartcart_api.precompute import precompute_effective_prices
from smartcart_api.swaps import _candidate_levels

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
D = Decimal


def add_item(db, w: World, key: str, chain: str, raw: str, canon: str, level: str, price: str,
             qty: str, unit: str, attrs: dict, conf: str = "0.95") -> int:
    iid = db.execute(
        "INSERT INTO items (chain_id, item_code, raw_name, quantity, unit) VALUES (%s, %s, %s, %s,"
        " %s) RETURNING id",
        (chain, key, raw, D(qty), unit),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
        " VALUES (%s, %s, %s, %s, 'rule')",
        (iid, w.canon[canon], level, D(conf)),
    )
    db.execute("INSERT INTO item_attributes (item_id, attrs, verified_keys, extractor)"
               " VALUES (%s, %s, '{}', 'rule')", (iid, Jsonb(attrs)))
    db.execute("INSERT INTO item_embeddings (item_id, embedding, model) VALUES (%s, %s::vector, %s)",
               (iid, to_pgvector(EMB.embed_one(raw)), EMB.model_name))
    add_price(db, iid, None, price, None, None, w.valid_from)
    w.items[key] = iid
    return iid


@pytest.fixture
def w(db, world: World) -> World:
    # A frozen salmon in chain c1, a close substitute for fresh salmon at 49.90 per kg.
    add_item(db, world, "salmon_c1_frozen", "t-c1", "סלמון קפוא 1 קילו", "salmon", "close",
             "49.90", "1", 'ק"ג', {"product_type": "סלמון", "state": "frozen"}, conf="0.82")
    precompute_effective_prices(db, chains=world.chains)
    return world


def basket(w: World) -> list[dict]:
    return [
        {"canonical_id": w.canon["milk3"], "quantity": 2, "flex_level": "exact",
         "exact_item_id": w.items["milk3_c1_tnuva"]},
        {"canonical_id": w.canon["salmon"], "quantity": 1},
        {"canonical_id": w.canon["paste"], "quantity": 1},
        {"canonical_id": w.canon["bread"], "quantity": 3},
    ]


def post(client, w: World, store: str, items: list[dict] | None = None, **kw) -> dict:
    r = client.post(f"/optimize/swaps?store_id={w.stores[store]}",
                    json={"items": items or basket(w), "location": w.location, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_swaps_are_sorted_and_explained(client, w: World) -> None:
    resp = post(client, w, "home")
    assert resp["store_id"] == w.stores["home"]
    got = [(s["canonical_id"], s["flex_level"], D(s["saving"])) for s in resp["swaps"]]
    # Fresh salmon 89.90/kg -> frozen 49.90/kg (close); Tnuva 6.90 -> house brand 6.20, x2.
    assert got == [(w.canon["salmon"], "close", D("40.00")), (w.canon["milk3"], "any_brand", D("1.40"))]
    top = resp["top_swap"]
    assert top == resp["swaps"][0]
    assert top["from_item_id"] == w.items["salmon_c1"]
    assert top["to_item_id"] == w.items["salmon_c1_frozen"]
    assert top["to_display_name_he"] == "סלמון קפוא 1 קילו"
    assert top["confidence"] == pytest.approx(0.82)
    tags = {t["key"]: t["status"] for t in top["tags"]}
    assert tags == {"product_type": "matched", "state": "differs"}  # the soft difference is shown
    assert D(resp["total_saving"]) == D("41.40")


def _total(db, w: World, levels: dict[int, str], store: str) -> Decimal:
    items = []
    for it in basket(w):
        lvl = levels.get(it["canonical_id"], it.get("flex_level", "any_brand"))
        ex = it.get("exact_item_id") if lvl == "exact" and it.get("flex_level") == "exact" else None
        items.append(schemas.BasketItem(canonical_id=it["canonical_id"], quantity=it["quantity"],
                                        flex_level=lvl, exact_item_id=ex))
    s = store_info(db, w.stores[store], schemas.Location(**w.location))
    return price_baskets(db, items, [s], [])[s.store_id].total


def test_top_swap_and_total_match_a_brute_force(client, db, w: World) -> None:
    """Acceptance (#45): the top swap is the largest valid single change, and the aggregate equals
    the real basket difference after applying every swap (no double counting)."""
    resp = post(client, w, "home")
    base = _total(db, w, {}, "home")
    reqs = {it["canonical_id"]: it for it in basket(w)}
    options = {
        cid: [None, *_candidate_levels(it.get("flex_level", "any_brand"), it.get("exact_item_id"))]
        for cid, it in reqs.items()
    }
    best_single = D(0)
    for cid, levels in options.items():
        for lvl in levels[1:]:
            best_single = max(best_single, base - _total(db, w, {cid: lvl}, "home"))
    assert D(resp["top_swap"]["saving"]) == best_single
    applied = {s["canonical_id"]: s["flex_level"] for s in resp["swaps"]}
    assert base - _total(db, w, applied, "home") == D(resp["total_saving"])
    # And no combination of level changes saves more than the swaps together.
    cids = list(options)
    best_any = max(
        base - _total(db, w, {c: lv for c, lv in zip(cids, combo, strict=True) if lv}, "home")
        for combo in product(*(options[c] for c in cids))
    )
    assert best_any == D(resp["total_saving"])


def test_no_swap_available(client, w: World) -> None:
    # Store A sells Tnuva 3% at 5.90, below the house brand's 6.20: nothing to gain.
    items = [{"canonical_id": w.canon["milk3"], "quantity": 2, "flex_level": "exact",
              "exact_item_id": w.items["milk3_c1_tnuva"]}]
    resp = post(client, w, "a", items=items)
    assert resp["swaps"] == [] and resp["top_swap"] is None and D(resp["total_saving"]) == 0


def test_close_level_has_nothing_looser(client, w: World) -> None:
    items = [{"canonical_id": w.canon["salmon"], "quantity": 1, "flex_level": "close"}]
    resp = post(client, w, "home", items=items)
    assert resp["swaps"] == []


def test_never_a_critical_attribute_mismatch(client, db, w: World) -> None:
    # A wrong mapping: 1% milk mapped to the 3% canonical at any_brand, and cheapest.
    bad = add_item(db, w, "milk1_bad", "t-c1", "חלב 1% מבצע", "milk3", "any_brand", "4.00", "1",
                   "ליטר", {"fat_pct": 1})
    precompute_effective_prices(db, chains=w.chains)
    resp = post(client, w, "home")
    assert all(s["to_item_id"] != bad for s in resp["swaps"])
    assert w.canon["milk3"] not in {s["canonical_id"] for s in resp["swaps"]}


def test_needs_review_mappings_are_not_offered(client, db, w: World) -> None:
    db.execute("UPDATE item_canonical SET needs_review = true WHERE item_id = %s",
               (w.items["milk3_c1_private"],))
    precompute_effective_prices(db, chains=w.chains)
    resp = post(client, w, "home")
    assert w.canon["milk3"] not in {s["canonical_id"] for s in resp["swaps"]}


def test_store_in_another_chain_and_missing_items(client, w: World) -> None:
    # Store B (chain c2) has no fresh salmon at any_brand: a gap, not a swap.
    resp = post(client, w, "b")
    assert w.canon["salmon"] not in {s["canonical_id"] for s in resp["swaps"]}
    assert all(D(s["saving"]) > 0 for s in resp["swaps"])


def test_unknown_store(client, w: World) -> None:
    r = client.post("/optimize/swaps?store_id=999999999",
                    json={"items": basket(w), "location": w.location})
    assert r.status_code == 404


def test_swap_carries_the_canonicals_arabic_name(client, db, w: World) -> None:
    db.execute("UPDATE canonical_products SET names_ar = %s WHERE id = %s",
               (["سلمون طازج", "سمك سلمون"], w.canon["salmon"]))
    swaps = {s["canonical_id"]: s for s in post(client, w, "home")["swaps"]}
    assert swaps[w.canon["salmon"]]["canonical_name_ar"] == "سلمون طازج"
    assert swaps[w.canon["salmon"]]["to_display_name_he"] == "סלמון קפוא 1 קילו"  # Hebrew unchanged
    assert swaps[w.canon["milk3"]]["canonical_name_ar"] is None  # no Arabic name: null
