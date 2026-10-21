"""BasketItem.allow: soft attributes the person allows to differ reach matching (issue #31).

World: store A (chain c1) sells 1% milk at 0.45 per 100 ml, cheaper than its best 3% milk (0.59);
the home store and chain c2 have no cheaper 1% milk. milk3 and milk1 are siblings (same product
type, taxonomy node and base unit, critical attributes differ in fat_pct only).
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from api_world import World, add_price
from psycopg.types.json import Jsonb

from smartcart_api.precompute import precompute_effective_prices

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
D = Decimal


@pytest.fixture
def w(db, world: World) -> World:
    add_price(
        db, world.items["milk1_c1"], world.stores["a"], "4.50", "0.45", "100ml", world.valid_from
    )
    precompute_effective_prices(db, chains=world.chains)
    return world


def add_milk(
    db, w: World, key: str, critical: dict, soft: dict, price: str, unit_price: str
) -> int:
    """Another canonical of the milk family with one 3%-sibling item, sold at store A only."""
    cid = db.execute(
        "INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type, base_unit,"
        " critical_attrs, soft_attrs, is_mvp, rank)"
        " SELECT taxonomy_id, %s, %s, product_type, base_unit, %s, %s, true, 30"
        " FROM canonical_products WHERE id = %s RETURNING id",
        (f"t-{key}", key, Jsonb(critical), Jsonb(soft), w.canon["milk3"]),
    ).fetchone()[0]
    w.canon[key] = cid
    iid = db.execute(
        "INSERT INTO items (chain_id, item_code, barcode, raw_name, quantity, unit)"
        " VALUES ('t-c1', %s, %s, %s, 1, 'ליטר') RETURNING id",
        (key, f"7291{cid:09d}", f"חלב {key}"),
    ).fetchone()[0]
    w.items[key] = iid
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
        " VALUES (%s, %s, 'any_brand', 0.95, 'rule')",
        (iid, cid),
    )
    db.execute(
        "INSERT INTO item_attributes (item_id, attrs, verified_keys, extractor)"
        " VALUES (%s, %s, '{}', 'rule')",
        (iid, Jsonb(critical)),
    )
    add_price(db, iid, w.stores["a"], price, unit_price, "100ml", w.valid_from)
    precompute_effective_prices(db, chains=w.chains)
    return cid


def milk(w: World, **kw) -> dict:
    return {"canonical_id": w.canon["milk3"], "quantity": 2, **kw}


def compare(client, w: World, item: dict, **kw) -> dict[int, dict]:
    body = {"items": [item], "location": w.location, **kw}
    r = client.post("/compare", json=body)
    assert r.status_code == 200, r.text
    return {s["store_id"]: s for s in r.json()["stores"]}


def only_line(store: dict) -> dict:
    assert len(store["items"]) == 1
    return store["items"][0]


def test_allowed_fat_pct_offers_the_sibling_labeled(client, w: World) -> None:
    stores = compare(client, w, milk(w, allow=["fat_pct"]))
    a = only_line(stores[w.stores["a"]])
    assert a["item_id"] == w.items["milk1_c1"] and a["canonical_id"] == w.canon["milk3"]
    assert a["is_substitute"] and a["confidence"] == pytest.approx(0.99)
    tags = {t["key"]: t for t in a["tags"]}
    assert tags["fat_pct"]["status"] == "differs" and tags["fat_pct"]["value"] == "1"
    assert D(a["line_total"]) == D("9.00")  # 2 x 4.50 instead of 2 x 5.90
    assert a["original_item_id"] == w.items["milk3_c1_tnuva"]
    assert stores[w.stores["a"]]["substituted_count"] == 1
    # Where the sibling is not cheaper, the requested 3% milk stays, unlabeled.
    for key in ("home", "b"):
        line = only_line(stores[w.stores[key]])
        assert not line["is_substitute"] and line["tags"] == []
    assert only_line(stores[w.stores["home"]])["item_id"] == w.items["milk3_c1_private"]


@pytest.mark.parametrize("flex", ["any_brand", "close"])
def test_the_sibling_is_offered_at_both_non_exact_levels(client, w: World, flex: str) -> None:
    a = only_line(compare(client, w, milk(w, flex_level=flex, allow=["fat_pct"]))[w.stores["a"]])
    assert a["item_id"] == w.items["milk1_c1"] and a["is_substitute"]


@pytest.mark.parametrize("allow", [[], ["pack_size"], ["flavor"], ["variety", "packaging"]])
def test_not_allowed_is_never_offered(client, w: World, allow: list[str]) -> None:
    for flex in ("any_brand", "close"):
        a = only_line(compare(client, w, milk(w, flex_level=flex, allow=allow))[w.stores["a"]])
        assert a["item_id"] == w.items["milk3_c1_tnuva"] and not a["is_substitute"]


def test_a_critical_attribute_that_is_not_allowed_still_vetoes(client, db, w: World) -> None:
    # Cheaper than everything, but 1% AND cocoa: it differs from the 3% milk in two critical keys.
    add_milk(db, w, "milk1_cocoa", {"fat_pct": 1, "flavor": "cocoa"}, {}, "1.00", "0.10")
    a = only_line(compare(client, w, milk(w, allow=["fat_pct"]))[w.stores["a"]])
    assert a["item_id"] == w.items["milk1_c1"]  # the plain 1%, not the 0.10 cocoa one
    # Allow both and the cheaper one wins, labeled with both differences.
    a = only_line(compare(client, w, milk(w, allow=["fat_pct", "flavor"]))[w.stores["a"]])
    assert a["item_id"] == w.items["milk1_cocoa"] and a["is_substitute"]
    tags = {t["key"]: t["status"] for t in a["tags"]}
    assert tags["fat_pct"] == "differs"
    # Allowing only the other key does not open the fat difference either.
    a = only_line(compare(client, w, milk(w, allow=["flavor"]))[w.stores["a"]])
    assert a["item_id"] == w.items["milk3_c1_tnuva"] and not a["is_substitute"]


def test_a_sibling_that_differs_in_an_unallowed_soft_attribute_is_vetoed(
    client, db, w: World
) -> None:
    for key, size in (("milk3", 1000), ("milk1", 500)):
        db.execute(
            "UPDATE canonical_products SET soft_attrs = %s WHERE id = %s",
            (Jsonb({"pack_size": size, "unit": "ml"}), w.canon[key]),
        )
    # At "any brand" the 500 ml carton is another pack size the person did not allow...
    a = only_line(compare(client, w, milk(w, allow=["fat_pct"]))[w.stores["a"]])
    assert a["item_id"] == w.items["milk3_c1_tnuva"]
    # ...allowing the pack size too opens it, and at "close" soft differences are the level's own.
    a = only_line(compare(client, w, milk(w, allow=["fat_pct", "pack_size"]))[w.stores["a"]])
    assert a["item_id"] == w.items["milk1_c1"] and a["is_substitute"]
    a = only_line(compare(client, w, milk(w, flex_level="close", allow=["fat_pct"]))[w.stores["a"]])
    assert a["item_id"] == w.items["milk1_c1"]


def test_a_sibling_needs_the_same_taxonomy_node(client, db, w: World) -> None:
    db.execute(
        "UPDATE canonical_products SET taxonomy_id = 't.dairy.cream' WHERE id = %s",
        (w.canon["milk1"],),
    )
    a = only_line(compare(client, w, milk(w, allow=["fat_pct"]))[w.stores["a"]])
    assert a["item_id"] == w.items["milk3_c1_tnuva"]


def test_exact_ignores_allow(client, w: World) -> None:
    for extra in ({}, {"exact_item_id": w.items["milk3_c1_tnuva"]}):
        plain = compare(client, w, milk(w, flex_level="exact", **extra))
        allowed = compare(client, w, milk(w, flex_level="exact", allow=["fat_pct"], **extra))
        assert plain == allowed
        assert not any(only_line(s)["is_substitute"] for s in allowed.values())
    a = only_line(allowed[w.stores["a"]])
    assert a["item_id"] == w.items["milk3_c1_tnuva"]


def test_unknown_or_too_many_keys_are_rejected(client, w: World) -> None:
    for allow in (["color"], ["fat_pct", "brand"], ["fat_pct"] * 6, "fat_pct"):
        for path in ("/compare", "/optimize"):
            body = {"items": [milk(w, allow=allow)], "location": w.location}
            r = client.post(path, json=body)
            assert r.status_code == 422, (path, allow)


def _strip(obj):
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k != "generated_at"}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


def _basket(w: World, **kw) -> list[dict]:
    return [
        {"canonical_id": w.canon["milk3"], "quantity": 2, **kw},
        {"canonical_id": w.canon["paste"], "quantity": 1, **kw},
        {"canonical_id": w.canon["salmon"], "quantity": 1, "flex_level": "close", **kw},
        {"canonical_id": w.canon["bread"], "quantity": 3, **kw},
        {"canonical_id": w.canon["eggs"], "quantity": 1, **kw},
    ]


@pytest.mark.parametrize("path", ["/compare", "/optimize"])
def test_an_empty_allow_changes_nothing(client, w: World, path: str) -> None:
    extra = {"home_store_id": w.stores["home"]}
    if path == "/optimize":
        extra["min_split_saving"] = 1
    omitted = client.post(path, json={"items": _basket(w), "location": w.location, **extra})
    empty = client.post(path, json={"items": _basket(w, allow=[]), "location": w.location, **extra})
    assert omitted.status_code == empty.status_code == 200
    dump = lambda r: json.dumps(_strip(r.json()), sort_keys=True, ensure_ascii=False)  # noqa: E731
    assert dump(omitted) == dump(empty)


def test_optimize_uses_the_sibling_and_labels_it(client, w: World) -> None:
    for solver in ("heuristic", "milp"):
        body = {
            "items": [milk(w, allow=["fat_pct"])],
            "location": w.location,
            "solver": solver,
            "max_stores": 1,
        }
        r = client.post("/optimize", json=body)
        assert r.status_code == 200, r.text
        plan = r.json()["single"]
        assert D(plan["total"]) == D("9.00"), solver
        store = plan["stores"][0]["store"]
        assert store["store_id"] == w.stores["a"]
        line = only_line(store)
        assert line["item_id"] == w.items["milk1_c1"] and line["is_substitute"]
        assert {t["key"]: t["status"] for t in line["tags"]}["fat_pct"] == "differs"
    # Not allowed: the plan buys a 3% milk, unlabeled.
    body = {"items": [milk(w)], "location": w.location, "max_stores": 1}
    plan = client.post("/optimize", json=body).json()["single"]
    line = only_line(plan["stores"][0]["store"])
    assert line["item_id"] in (w.items["milk3_c1_tnuva"], w.items["milk3_c1_private"])
    assert not line["is_substitute"]
