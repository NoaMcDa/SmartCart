"""POST /compare (issue #58). Totals are computed by hand from api_world's prices."""

from __future__ import annotations

from decimal import Decimal

import pytest
from api_world import World

from smartcart_api.precompute import precompute_effective_prices

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
D = Decimal


@pytest.fixture
def w(db, world: World) -> World:
    precompute_effective_prices(db, chains=world.chains)
    return world


def basket(w: World, flex: str = "any_brand") -> list[dict]:
    return [
        {"canonical_id": w.canon["milk3"], "quantity": 2, "flex_level": flex},
        {"canonical_id": w.canon["paste"], "quantity": 1, "flex_level": flex},
        {"canonical_id": w.canon["salmon"], "quantity": 1, "flex_level": flex},
        {"canonical_id": w.canon["bread"], "quantity": 3, "flex_level": flex},
        {"canonical_id": w.canon["eggs"], "quantity": 1, "flex_level": flex},
    ]


def post(client, w: World, **kw) -> dict:
    body = {"items": basket(w), "location": w.location, **kw}
    r = client.post("/compare", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def by_store(resp: dict) -> dict[int, dict]:
    return {s["store_id"]: s for s in resp["stores"]}


def line(store: dict, canonical_id: int) -> dict:
    return next(i for i in store["items"] if i["canonical_id"] == canonical_id)


def test_totals_sorting_and_radius(client, w: World) -> None:
    resp = post(client, w, home_store_id=w.stores["home"])
    stores = by_store(resp)
    # Only physical stores within 5 km: not the online store, not the far one.
    assert set(stores) == {w.stores["home"], w.stores["a"], w.stores["b"]}
    # home: 6.20x2 + 3.50 + 89.90 + 20.00 (3 for 20) + 12.90 (no club) = 138.70
    # A:    5.90x2 + 3.00 + 89.90 + 20.00 + 12.90 = 137.60
    # B:    6.40x2 + 6.50 + (salmon missing) + 6.00x3 + 13.50 = 50.80
    assert D(stores[w.stores["home"]]["total"]) == D("138.70")
    assert D(stores[w.stores["a"]]["total"]) == D("137.60")
    assert D(stores[w.stores["b"]]["total"]) == D("50.80")
    # Complete baskets first, then by total: B is cheapest but incomplete, so it is last.
    assert [s["store_id"] for s in resp["stores"]] == [
        w.stores["a"],
        w.stores["home"],
        w.stores["b"],
    ]
    assert D(resp["home_store_total"]) == D("138.70")
    assert resp["disclaimer_he"] == "המחיר הקובע הוא בקופה."


def test_store_lacking_items_lists_them(client, w: World) -> None:
    b = by_store(post(client, w))[w.stores["b"]]
    assert b["missing"] == [w.canon["salmon"]] and b["found_count"] == 4
    assert w.canon["salmon"] not in [i["canonical_id"] for i in b["items"]]


def test_saving_only_versus_home_and_never_counts_missing_items(client, w: World) -> None:
    resp = post(client, w, home_store_id=w.stores["home"])
    stores = by_store(resp)
    assert D(stores[w.stores["a"]]["saving_vs_home"]) == D("1.10")
    assert D(stores[w.stores["home"]]["saving_vs_home"]) == 0
    # B is 87.90 cheaper in total only because it lacks the salmon. Over the items both stores
    # supply it is 2.00 dearer: 12.40 + 3.50 + 20.00 + 12.90 - 50.80.
    assert D(stores[w.stores["b"]]["saving_vs_home"]) == D("-2.00")
    # Without a home store there is no saving figure at all.
    no_home = post(client, w)
    assert no_home["home_store_total"] is None
    assert all(s["saving_vs_home"] is None for s in no_home["stores"])


def test_no_field_compares_against_the_most_expensive_store(client, w: World) -> None:
    resp = post(client, w, home_store_id=w.stores["home"])

    def keys(obj) -> set[str]:
        if isinstance(obj, dict):
            return set(obj) | {k for v in obj.values() for k in keys(v)}
        if isinstance(obj, list):
            return {k for v in obj for k in keys(v)}
        return set()

    names = keys(resp)
    assert not {k for k in names if "expensive" in k or "max" in k or "worst" in k}
    assert {k for k in names if "saving" in k} <= {"saving_vs_home", "promo_add_saving"}
    schema = client.get("/openapi.json").json()["components"]["schemas"]
    for model in ("CompareResponse", "StoreResult", "PricedItem"):
        assert not [p for p in schema[model]["properties"] if "expensive" in p or "max" in p]


def test_promo_lines_and_add_one_more(client, w: World) -> None:
    stores = by_store(post(client, w))
    paste_a = line(stores[w.stores["a"]], w.canon["paste"])
    # 1+1 needs 2; one jar is paid at the shelf price and the response offers the second.
    assert D(paste_a["line_total"]) == D("3.00") and not paste_a["promo_applied"]
    assert D(paste_a["promo_min_qty"]) == 2 and D(paste_a["promo_add_qty"]) == 1
    assert D(paste_a["promo_add_saving"]) == D("3.00")
    assert paste_a["promo_description"] == "רסק 1+1"
    bread = line(stores[w.stores["home"]], w.canon["bread"])
    assert D(bread["line_total"]) == D("20.00") and bread["promo_applied"]
    assert D(bread["effective_unit_price"]) == D("6.6667")
    assert bread["promo_add_qty"] is None


def test_two_jars_get_the_one_plus_one(client, w: World) -> None:
    body = {"items": [{"canonical_id": w.canon["paste"], "quantity": 2}], "location": w.location}
    a = by_store(client.post("/compare", json=body).json())[w.stores["a"]]
    assert D(a["total"]) == D("3.00") and a["items"][0]["promo_applied"]


def test_club_deals_only_for_members(client, w: World) -> None:
    eggs = line(by_store(post(client, w))[w.stores["home"]], w.canon["eggs"])
    assert D(eggs["line_total"]) == D("12.90") and not eggs["club_required"]
    eggs = line(
        by_store(post(client, w, clubs=["מועדון לקוחות"]))[w.stores["home"]], w.canon["eggs"]
    )
    assert D(eggs["line_total"]) == D("9.90")
    assert eggs["club_required"] and eggs["club_name"] == "מועדון לקוחות"


def test_substitution_with_tags_and_confidence(client, w: World) -> None:
    body = {"items": basket(w, "close"), "location": w.location}
    b = by_store(client.post("/compare", json=body).json())[w.stores["b"]]
    assert b["missing"] == [] and b["substituted_count"] == 1
    salmon = line(b, w.canon["salmon"])
    assert salmon["is_substitute"] and salmon["item_id"] == w.items["salmon_c2_frozen"]
    assert salmon["confidence"] == pytest.approx(0.81)
    # 1 kg at 39.90 per 400 g = 99.75, estimated (sold by weight)
    assert D(salmon["line_total"]) == D("99.75") and salmon["is_estimated"]
    tags = {t["key"]: t for t in salmon["tags"]}
    assert tags["state"]["status"] == "differs" and tags["state"]["value"] == "frozen"
    assert tags["product_type"]["status"] == "matched"
    # Not substitutes: the any-brand milk and the exact salmon of chain c1.
    home = by_store(client.post("/compare", json=body).json())[w.stores["home"]]
    assert not any(i["is_substitute"] for i in home["items"])


def test_every_price_has_a_timestamp(client, w: World) -> None:
    for s in post(client, w)["stores"]:
        assert s["prices_updated_at"]
        assert all(i["price_valid_from"] for i in s["items"])
        assert s["prices_updated_at"] == max(i["price_valid_from"] for i in s["items"])


def test_exact_barcode(client, w: World) -> None:
    body = {
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
    stores = by_store(client.post("/compare", json=body).json())
    assert D(stores[w.stores["home"]]["total"]) == D("6.90")  # not the cheaper private label
    assert D(stores[w.stores["a"]]["total"]) == D("5.90")
    assert w.stores["b"] not in stores  # chain c2 does not sell that barcode


def test_online_stores_on_request(client, w: World) -> None:
    db_online = by_store(post(client, w, include_online=True))
    assert w.stores["online"] in db_online
    assert db_online[w.stores["online"]]["channel"] == "online"


def test_empty_radius(client, w: World) -> None:
    body = {
        "items": basket(w),
        "location": {"lon": 35.5, "lat": 33.2, "radius_m": 1000},
        "home_store_id": w.stores["home"],
    }
    resp = client.post("/compare", json=body).json()
    assert resp["stores"] == []
    # The home store is still priced so the user sees what their usual basket costs.
    assert D(resp["home_store_total"]) == D("138.70")


def test_priced_items_carry_the_canonicals_arabic_name(client, db, w: World) -> None:
    db.execute(
        "UPDATE canonical_products SET names_ar = %s WHERE id = %s",
        (["بيض", "بيض طازج"], w.canon["eggs"]),
    )
    home = by_store(post(client, w))[w.stores["home"]]
    eggs = line(home, w.canon["eggs"])
    assert eggs["canonical_name_ar"] == "بيض"
    assert eggs["display_name_he"]  # the chain's item name, still Hebrew
    assert line(home, w.canon["salmon"])["canonical_name_ar"] is None
