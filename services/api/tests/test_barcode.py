"""GET /items/barcode/{barcode} (issue #39).

The world's barcodes are 7290000 + the item's index (api_world.ITEMS): Tnuva 3% milk in t-c1 is
7290000000000. The fixture adds the same Tnuva product in chain t-c2 (same barcode, 6.70), so
the scanned product is priced at the home store (6.90 = 0.69 per 100 ml), store A (exception
5.90 = 0.59) and store B (0.67). Any-brand alternatives: the private label at home and A (0.62),
Tera at B (0.64).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from api_world import ITEMS, ORIGIN, World, add_price

from smartcart_api.precompute import precompute_effective_prices
from smartcart_api.routes.barcode import barcode_variants

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
D = Decimal


def code(key: str) -> str:
    n = next(i for i, it in enumerate(ITEMS) if it[0] == key)
    return f"7290000{n:06d}"


@pytest.fixture
def w(db, world: World) -> World:
    iid = db.execute(
        "INSERT INTO items (chain_id, item_code, barcode, raw_name, quantity, unit)"
        " VALUES ('t-c2', 'tnuva-c2', %s, %s, 1, 'ליטר') RETURNING id",
        (code("milk3_c1_tnuva"), "חלב תנובה 3% 1 ליטר"),
    ).fetchone()[0]
    world.items["milk3_c2_tnuva"] = iid
    db.execute("INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
               " VALUES (%s, %s, 'exact', 0.99, 'rule')", (iid, world.canon["milk3"]))
    db.execute("INSERT INTO item_attributes (item_id, attrs, verified_keys, extractor)"
               " VALUES (%s, '{\"fat_pct\": 3, \"brand\": \"תנובה\"}', '{}', 'rule')", (iid,))
    add_price(db, iid, None, "6.70", "0.67", "100ml", world.valid_from)
    # A product nobody mapped, and a UPC-A code published without the leading zero.
    db.execute("INSERT INTO items (chain_id, item_code, barcode, raw_name)"
               " VALUES ('t-c1', 'mystery', '7290011111111', 'מוצר לא ממופה')")
    db.execute("UPDATE items SET barcode = '123456789012' WHERE id = %s", (world.items["bread_c1"],))
    db.execute("UPDATE canonical_products SET reference_barcodes = '{7290099999999}' WHERE id = %s",
               (world.canon["cream"],))
    precompute_effective_prices(db, chains=world.chains)
    return world


def scan(client, barcode: str, **params) -> dict:
    r = client.get(f"/items/barcode/{barcode}",
                   params={"lon": ORIGIN[0], "lat": ORIGIN[1], **params})
    assert r.status_code == 200, r.text
    return r.json()


def test_here_cheapest_nearby_and_a_labeled_substitute(client, w: World) -> None:
    resp = scan(client, code("milk3_c1_tnuva"), store_id=w.stores["home"])
    assert resp["found"] and resp["canonical"]["canonical_id"] == w.canon["milk3"]
    assert resp["canonical"]["category_path_he"] == ["מוצרי חלב", "חלב"]
    assert resp["display_name_he"] == "חלב תנובה 3% 1 ליטר"
    here = resp["here"]
    assert here["store"]["store_id"] == w.stores["home"] and here["item_id"] == w.items["milk3_c1_tnuva"]
    assert D(here["shelf_price"]) == D("6.90") and D(here["unit_price"]) == D("0.6900")
    assert here["price_valid_from"] and not here["is_substitute"]
    near = resp["cheapest_nearby"]
    assert near["store"]["store_id"] == w.stores["a"] and D(near["unit_price"]) == D("0.5900")
    assert near["store"]["lat"] is not None and near["store"]["distance_m"] > 0
    sub = resp["cheaper_substitute"]
    assert sub["is_substitute"] and sub["item_id"] == w.items["milk3_c1_private"]
    assert sub["store"]["store_id"] == w.stores["home"] and D(sub["unit_price"]) == D("0.6200")
    assert sub["confidence"] == pytest.approx(0.95)
    tags = {t["key"]: t for t in sub["tags"]}
    assert tags["brand"]["status"] == "differs" and tags["brand"]["value"] == "מותג הבית"
    assert tags["fat_pct"]["status"] == "matched"
    assert resp["disclaimer_he"] == "המחיר הקובע הוא בקופה."


def test_without_a_store_the_reference_is_the_cheapest_nearby(client, w: World) -> None:
    resp = scan(client, code("milk3_c1_tnuva"))
    assert resp["here"] is None
    assert resp["cheapest_nearby"]["store"]["store_id"] == w.stores["a"]
    assert resp["cheaper_substitute"] is None  # nothing beats 0.59 per 100 ml nearby


def test_same_barcode_in_another_chain_is_the_same_product(client, w: World) -> None:
    resp = scan(client, code("milk3_c1_tnuva"), store_id=w.stores["b"])
    assert resp["here"]["item_id"] == w.items["milk3_c2_tnuva"]
    assert D(resp["here"]["unit_price"]) == D("0.6700")
    # Tera at B (0.64) is cheaper than the scanned 0.67, but the private label at home is cheaper still.
    assert resp["cheaper_substitute"]["item_id"] == w.items["milk3_c1_private"]


def test_unknown_unmapped_and_close_only_codes_are_not_found(client, w: World) -> None:
    for barcode in ("7290000999999", "abc", "12"):
        resp = scan(client, barcode)
        assert resp["found"] is False and resp["canonical"] is None and resp["here"] is None
    mystery = scan(client, "7290011111111")
    assert mystery["found"] is False and mystery["display_name_he"] == "מוצר לא ממופה"
    frozen = scan(client, code("salmon_c2_frozen"))  # mapped only as a close substitute
    assert frozen["found"] is False and frozen["canonical"] is None


def test_reference_barcode_and_leading_zero(client, w: World) -> None:
    cream = scan(client, "7290099999999")
    assert cream["found"] and cream["canonical"]["canonical_id"] == w.canon["cream"]
    assert cream["cheapest_nearby"] is None
    bread = scan(client, "0123456789012", store_id=w.stores["home"])
    assert bread["found"] and bread["here"]["item_id"] == w.items["bread_c1"]
    assert barcode_variants("0123456789012") == ["0123456789012", "123456789012"]
    assert barcode_variants("12345678") == ["12345678", "0000012345678"]


def test_club_deals_only_for_members(client, w: World) -> None:
    eggs = code("eggs_c1")
    plain = scan(client, eggs, store_id=w.stores["home"])["here"]
    assert D(plain["shelf_price"]) == D("12.90") and not plain["club_required"]
    assert D(plain["unit_price"]) == D("1.0750")
    member = scan(client, eggs, store_id=w.stores["home"], clubs=["רשת אחת"])["here"]
    assert member["club_required"] and member["club_name"] == "מועדון לקוחות"
    assert D(member["unit_price"]) == D("0.8250") and member["promo_description"] == "ביצים למועדון"


def test_rejected_mappings_are_never_used(client, db, w: World) -> None:
    """A reviewer's rejection (human_rejected, as the catalog writes it) hides the mapping from
    the barcode lookup and from the live exact-barcode path of /compare."""
    db.execute(
        "UPDATE item_canonical SET human_rejected = true, needs_review = true, confidence = 0"
        " WHERE item_id = ANY(%s) AND canonical_id = %s",
        ([w.items["milk3_c1_tnuva"], w.items["milk3_c2_tnuva"]], w.canon["milk3"]),
    )
    assert scan(client, code("milk3_c1_tnuva"))["found"] is False
    body = {"items": [{"canonical_id": w.canon["milk3"], "quantity": 1, "flex_level": "exact",
                       "exact_item_id": w.items["milk3_c1_tnuva"]}],
            "location": {"lon": ORIGIN[0], "lat": ORIGIN[1], "radius_m": 5000}}
    r = client.post("/compare", json=body)
    assert r.status_code == 200 and r.json()["stores"] == []


def test_parameters_are_validated(client, w: World) -> None:
    r = client.get(f"/items/barcode/{code('eggs_c1')}", params={"lon": ORIGIN[0], "lat": 100})
    assert r.status_code == 422
    r = client.get(f"/items/barcode/{code('eggs_c1')}",
                   params={"lon": ORIGIN[0], "lat": ORIGIN[1], "radius_m": 100})
    assert r.status_code == 422


def test_barcode_canonical_carries_the_arabic_name(client, db, w: World) -> None:
    code_ = code("milk3_c1_tnuva")
    assert scan(client, code_)["canonical"]["display_name_ar"] is None
    db.execute("UPDATE canonical_products SET names_ar = %s WHERE id = %s",
               (["حليب 3%", "حليب طازج 3%"], w.canon["milk3"]))
    resp = scan(client, code_)
    assert resp["canonical"]["display_name_ar"] == "حليب 3%"
    assert resp["canonical"]["display_name_he"] and resp["display_name_he"] == "חלב תנובה 3% 1 ליטר"
