"""``original_here`` on substitute lines of /compare and /optimize (issue #48 follow-up).

The substitution card compares a substitute with the original at the SAME store. The field is
display only: it never moves a total, a ranking or a saving.
"""

from __future__ import annotations

import copy
from datetime import timedelta
from decimal import Decimal

import pytest
from api_world import World, add_price, add_promo

from smartcart_api import basket as basket_mod
from smartcart_api.precompute import precompute_effective_prices

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
D = Decimal


def _add_item(db, w: World, key: str, name: str, canon: str, level: str, price: str, **kw) -> int:
    iid = db.execute(
        "INSERT INTO items (chain_id, item_code, barcode, raw_name, quantity, unit, is_weighed)"
        " VALUES ('t-c2', %s, %s, %s, NULL, %s, %s) RETURNING id",
        (key, f"7291{len(w.items):08d}", name, kw.get("unit"), kw.get("weighed", False)),
    ).fetchone()[0]
    w.items[key] = iid
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
        " VALUES (%s, %s, %s, 0.90, 'rule')",
        (iid, w.canon[canon], level),
    )
    add_price(
        db,
        iid,
        None,
        price,
        kw.get("unit_price"),
        kw.get("uom"),
        kw["at"],
        kw.get("weighed", False),
    )
    return iid


@pytest.fixture
def w(db, world: World) -> World:
    # Chain c2 (store B) already sells the frozen salmon as a close substitute and no fresh salmon.
    # Add, in chain c2 only: a fresh salmon at any_brand (dearer than the frozen one, so the
    # substitute still wins at "close") and a cheaper "close" bread next to bread_c2, whose
    # "3 for 15" promo makes the original dearer per unit than the substitute.
    at = world.valid_from + timedelta(hours=5)
    _add_item(
        db, world, "salmon_c2_fresh", "סלמון טרי במשקל", "salmon", "any_brand", "120.00",
        unit='ק"ג', weighed=True, uom="kg", unit_price="120.00", at=at,
    )  # fmt: skip
    _add_item(
        db, world, "bread_c2_sub", "לחם מלא פרוס", "bread", "close", "4.00", at=world.valid_from
    )
    world.promos["bread_c2_3for15"] = add_promo(
        db, "t-c2", None, "P9", [world.items["bread_c2"]], "bundle", "15", min_qty="3",
        description="3 לחמים ב-15",
    )  # fmt: skip
    precompute_effective_prices(db, chains=world.chains)
    return world


def body(w: World, flex: str = "close", **kw) -> dict:
    items = [
        {"canonical_id": w.canon["salmon"], "quantity": 1, "flex_level": flex},
        {"canonical_id": w.canon["bread"], "quantity": 3, "flex_level": flex},
        {"canonical_id": w.canon["milk3"], "quantity": 2, "flex_level": flex},
    ]
    return {"items": items, "location": w.location, **kw}


def post(client, path: str, payload: dict) -> dict:
    r = client.post(path, json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def line(store: dict, canonical_id: int) -> dict:
    return next(i for i in store["items"] if i["canonical_id"] == canonical_id)


def store_b(resp: dict, w: World) -> dict:
    return next(s for s in resp["stores"] if s["store_id"] == w.stores["b"])


def test_present_when_the_store_sells_the_original(client, w: World) -> None:
    b = store_b(post(client, "/compare", body(w)), w)
    salmon = line(b, w.canon["salmon"])
    assert salmon["is_substitute"] and salmon["item_id"] == w.items["salmon_c2_frozen"]
    here = salmon["original_here"]
    assert here["item_id"] == w.items["salmon_c2_fresh"] == salmon["original_item_id"]
    assert here["display_name_he"] == "סלמון טרי במשקל"
    assert here["canonical_name_ar"] == salmon["canonical_name_ar"]
    assert D(here["shelf_price"]) == D("120.00")
    assert D(here["effective_unit_price"]) == D("120.00") and here["uom"] == "kg"
    assert D(here["line_total"]) == D("120.00") and here["is_estimated"]
    assert not here["promo_applied"] and here["promo_description"] is None
    # The original's own update timestamp, not the substitute's.
    assert here["price_valid_from"] > salmon["price_valid_from"]


def test_original_promo_fields_and_unit_price_at_the_line_quantity(client, w: World) -> None:
    b = store_b(post(client, "/compare", body(w)), w)
    bread = line(b, w.canon["bread"])
    assert bread["is_substitute"] and bread["item_id"] == w.items["bread_c2_sub"]
    assert D(bread["line_total"]) == D("12.00")
    here = bread["original_here"]
    assert here["item_id"] == w.items["bread_c2"] == bread["original_item_id"]
    assert D(here["shelf_price"]) == D("6.00")
    assert here["promo_description"] == "3 לחמים ב-15" and here["promo_applied"]
    assert D(here["promo_min_qty"]) == 3
    assert D(here["line_total"]) == D("15.00")
    assert D(here["effective_unit_price"]) == D("5")  # 3 for 15
    assert here["price_valid_from"]


def test_null_when_the_store_does_not_sell_the_original(client, w: World, db) -> None:
    # Same world without the fresh salmon: store B has only the frozen close substitute.
    db.execute("DELETE FROM prices WHERE item_id = %s", (w.items["salmon_c2_fresh"],))
    db.execute("DELETE FROM item_canonical WHERE item_id = %s", (w.items["salmon_c2_fresh"],))
    precompute_effective_prices(db, chains=w.chains)
    b = store_b(post(client, "/compare", body(w)), w)
    salmon = line(b, w.canon["salmon"])
    assert salmon["is_substitute"]
    assert salmon["original_item_id"] is None and salmon["original_here"] is None


def test_non_substitute_lines_have_no_original_here(client, w: World) -> None:
    resp = post(client, "/compare", body(w))
    for s in resp["stores"]:
        for i in s["items"]:
            if not i["is_substitute"]:
                assert i.get("original_here") is None
    home = next(s for s in resp["stores"] if s["store_id"] == w.stores["home"])
    assert not any(i["is_substitute"] for i in home["items"])
    # An exact barcode request is never a substitute either.
    exact = {
        "items": [
            {
                "canonical_id": w.canon["milk3"],
                "quantity": 1,
                "flex_level": "exact",
                "exact_item_id": w.items["milk3_c1_tnuva"],
            }
        ],
        "location": w.location,
    }
    for s in post(client, "/compare", exact)["stores"]:
        assert all(i.get("original_here") is None for i in s["items"])


def _strip(obj):
    """The response without ``original_here`` anywhere (and without the generation time)."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in ("original_here", "generated_at")}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


def _originals(obj) -> list[dict]:
    if isinstance(obj, dict):
        found = [obj["original_here"]] if obj.get("original_here") else []
        return found + [o for v in obj.values() for o in _originals(v)]
    if isinstance(obj, list):
        return [o for v in obj for o in _originals(v)]
    return []


@pytest.mark.parametrize("path", ["/compare", "/optimize"])
def test_the_field_is_display_only(client, w: World, monkeypatch, path: str) -> None:
    payload = body(w, home_store_id=w.stores["home"])
    if path == "/optimize":  # bread alone: the cheapest plan is store B's close substitute
        payload["items"] = payload["items"][1:2]
    with_field = post(client, path, payload)
    assert _originals(with_field)  # the lines (and the optimizer's plans) really carry it
    # The same request with the field never built: everything else is identical.
    monkeypatch.setattr(basket_mod.schemas, "OriginalOffer", lambda **_kw: None)
    without = post(client, path, copy.deepcopy(payload))
    assert not _originals(without)
    assert _strip(with_field) == _strip(without)
    assert list(with_field) == list(without)
