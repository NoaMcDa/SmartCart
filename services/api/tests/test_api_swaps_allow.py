"""POST /optimize/swaps honors BasketItem.allow like /compare does (issue #31).

World (api_world, plus the milk family of test_api_allow): store A sells 3% milk at 0.59 per
100 ml and a 1% milk (a sibling canonical: same product type, taxonomy node and base unit, only
fat_pct differs) at 0.45. The canonicals' typical pack sizes differ (1000 ml and 500 ml), so at
"any brand" the 1% milk is another pack size the person did not allow; "close" lets the pack size
differ, which is what makes it a swap there.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from api_world import World, add_price
from psycopg.types.json import Jsonb
from test_api_allow import add_milk

from smartcart_api.precompute import precompute_effective_prices

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
D = Decimal


@pytest.fixture
def w(db, world: World) -> World:
    add_price(
        db, world.items["milk1_c1"], world.stores["a"], "4.50", "0.45", "100ml", world.valid_from
    )
    for key, size in (("milk3", 1000), ("milk1", 500)):
        db.execute(
            "UPDATE canonical_products SET soft_attrs = %s WHERE id = %s",
            (Jsonb({"pack_size": size, "unit": "ml"}), world.canon[key]),
        )
    precompute_effective_prices(db, chains=world.chains)
    return world


def milk(w: World, **kw) -> dict:
    return {"canonical_id": w.canon["milk3"], "quantity": 2, **kw}


def swaps(client, w: World, store: str, items: list[dict]) -> dict:
    r = client.post(
        f"/optimize/swaps?store_id={w.stores[store]}", json={"items": items, "location": w.location}
    )
    assert r.status_code == 200, r.text
    out = r.json()
    out.pop("generated_at")
    return out


def milk_swap(resp: dict, w: World) -> dict | None:
    return next((s for s in resp["swaps"] if s["canonical_id"] == w.canon["milk3"]), None)


def test_an_empty_allow_changes_nothing(client, w: World) -> None:
    base = [milk(w), {"canonical_id": w.canon["bread"], "quantity": 3}]
    for store in ("home", "a", "b"):
        old = swaps(client, w, store, base)
        assert swaps(client, w, store, [{**i, "allow": []} for i in base]) == old
        # Allowing attributes that open no sibling is the same as not allowing any.
        no_sibling = [{**i, "allow": ["pack_size", "flavor", "variety", "packaging"]} for i in base]
        assert swaps(client, w, store, no_sibling) == old


def test_an_allowed_fat_pct_offers_the_sibling_labeled(client, w: World) -> None:
    # Without it nothing is offered at store A: the 1% milk is never suggested for a 3% milk.
    assert milk_swap(swaps(client, w, "a", [milk(w)]), w) is None
    resp = swaps(client, w, "a", [milk(w, allow=["fat_pct"])])
    s = milk_swap(resp, w)
    assert s is not None
    assert s["to_item_id"] == w.items["milk1_c1"] and s["from_item_id"] == w.items["milk3_c1_tnuva"]
    assert s["flex_level"] == "close" and D(s["saving"]) == D("2.80")  # 2 x (5.90 - 4.50)
    tags = {t["key"]: t for t in s["tags"]}
    assert tags["fat_pct"]["status"] == "differs" and tags["fat_pct"]["value"] == "1"
    assert resp["top_swap"] == s and D(resp["total_saving"]) == D("2.80")


def test_a_sibling_the_basket_already_uses_is_not_a_swap(client, w: World) -> None:
    # With the pack size allowed too the 1% milk is already the line at store A (as in /compare).
    resp = swaps(client, w, "a", [milk(w, allow=["fat_pct", "pack_size"])])
    assert milk_swap(resp, w) is None
    r = client.post(
        "/compare",
        json={"items": [milk(w, allow=["fat_pct", "pack_size"])], "location": w.location},
    )
    line = next(s for s in r.json()["stores"] if s["store_id"] == w.stores["a"])["items"][0]
    assert line["item_id"] == w.items["milk1_c1"] and line["is_substitute"]


@pytest.mark.parametrize("allow", [[], ["pack_size"], ["flavor"], ["variety", "packaging"]])
def test_not_allowed_is_never_offered(client, w: World, allow: list[str]) -> None:
    for store in ("home", "a", "b"):
        for flex in ("any_brand", "close"):
            resp = swaps(client, w, store, [milk(w, flex_level=flex, allow=allow)])
            assert all(s["to_item_id"] != w.items["milk1_c1"] for s in resp["swaps"])


def test_exact_ignores_allow(client, w: World) -> None:
    item = milk(w, flex_level="exact", exact_item_id=w.items["milk3_c1_tnuva"])
    for store in ("home", "a"):
        plain = swaps(client, w, store, [item])
        assert swaps(client, w, store, [{**item, "allow": ["fat_pct", "pack_size"]}]) == plain
        assert all(s["to_item_id"] != w.items["milk1_c1"] for s in plain["swaps"])


def test_a_critical_attribute_that_is_not_allowed_still_vetoes(client, db, w: World) -> None:
    # Cheaper than everything, but 1% AND cocoa: two critical keys differ from the 3% milk.
    add_milk(
        db,
        w,
        "milk1_cocoa",
        {"fat_pct": 1, "flavor": "cocoa"},
        {"pack_size": 500, "unit": "ml"},
        "1.00",
        "0.10",
    )
    s = milk_swap(swaps(client, w, "a", [milk(w, allow=["fat_pct"])]), w)
    assert s is not None and s["to_item_id"] == w.items["milk1_c1"]  # not the 0.10 cocoa milk
    s = milk_swap(swaps(client, w, "a", [milk(w, allow=["fat_pct", "flavor"])]), w)
    assert s is not None and s["to_item_id"] == w.items["milk1_cocoa"]
    tags = {t["key"]: t["status"] for t in s["tags"]}
    assert tags["fat_pct"] == "differs" and tags["flavor"] == "differs"
    assert milk_swap(swaps(client, w, "a", [milk(w, allow=["flavor"])]), w) is None
