"""Club filtering (issue #19), store coordinates and promo confidence (issue #90).

The world's eggs carry a chain-wide club deal in chain t-c1 ("מועדון לקוחות", 9.90 instead of
12.90). The fixture adds, for eggs:
  * in t-c1, a credit-card deal ("כרטיס אשראי", 8.50) that beats the customer-club deal;
  * in t-c2, a deal of chain two's own club (7.00, shelf 13.50), so store B becomes the cheapest
    store only for members of that club;
  * in t-c2, two club deals whose restriction could not be parsed (no name, and "אחר") at 5.00:
    they must never apply.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from api_world import KM_LAT, ORIGIN, World, add_promo

from smartcart_api.basket import club_member, promo_confidence
from smartcart_api.precompute import precompute_effective_prices

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
D = Decimal
CHAIN1, CHAIN2 = "רשת אחת", "רשת שתיים"


@pytest.fixture
def w(db, world: World) -> World:
    world.promos["eggs_card"] = add_promo(
        db,
        "t-c1",
        None,
        "P4",
        [world.items["eggs_c1"]],
        "price",
        "8.50",
        club_only=True,
        club_name="כרטיס אשראי",
        description="ביצים בכרטיס",
    )
    world.promos["eggs_c2_club"] = add_promo(
        db,
        "t-c2",
        None,
        "P5",
        [world.items["eggs_c2"]],
        "price",
        "7.00",
        club_only=True,
        club_name="מועדון לקוחות",
        description="ביצים למועדון שתיים",
    )
    add_promo(
        db,
        "t-c2",
        None,
        "P6",
        [world.items["eggs_c2"]],
        "price",
        "5.00",
        club_only=True,
        club_name=None,
        description="מבצע מועדון לא מפוענח",
    )
    add_promo(
        db,
        "t-c2",
        None,
        "P7",
        [world.items["eggs_c2"]],
        "price",
        "5.00",
        club_only=True,
        club_name="אחר",
        description="מבצע אחר",
    )
    db.execute(
        "UPDATE promos SET raw = '{\"confidence\": 0.8}' WHERE id = %s",
        (world.promos["bread_3for20"],),
    )
    precompute_effective_prices(db, chains=world.chains)
    return world


def eggs_body(w: World, clubs: list[str], **kw) -> dict:
    return {
        "items": [{"canonical_id": w.canon["eggs"], "quantity": 1}],
        "location": w.location,
        "clubs": clubs,
        **kw,
    }


def compare(client, body: dict) -> dict[int, dict]:
    r = client.post("/compare", json=body)
    assert r.status_code == 200, r.text
    return {s["store_id"]: s for s in r.json()["stores"]}


# --- the matching rule ---------------------------------------------------------------------------


def test_club_name_matches_case_insensitive_and_trimmed() -> None:
    assert club_member("Shufersal Club", ["  shufersal   club "])
    assert club_member("כרטיס אשראי", ["כרטיס אשראי"])
    assert not club_member("Shufersal Club", ["Rami Levy Club"])
    assert not club_member("Shufersal Club", [])


def test_marking_the_chain_covers_its_own_customer_club() -> None:
    assert club_member("מועדון לקוחות", ["רמי לוי"], chain_name="רמי לוי")
    assert club_member("מועדון לקוחות", ["מועדון רמי לוי"], chain_name="רמי לוי")
    assert club_member("מועדון לקוחות", ["רמי לוי"], chain_name="רמי לוי שיווק השקמה")
    assert club_member("Yellow", ["רמי לוי"], chain_name="רמי לוי", chain_club_names=["Yellow"])
    # The chain's name does not unlock a credit-card deal, nor another chain's club.
    assert not club_member("כרטיס אשראי", ["רמי לוי"], chain_name="רמי לוי")
    assert not club_member("מועדון לקוחות", ["שופרסל"], chain_name="רמי לוי")


def test_unparseable_restriction_stays_restricted() -> None:
    everything = ["אחר", "club 7", "רמי לוי", "מועדון לקוחות"]
    assert not club_member(None, everything, chain_name="רמי לוי")
    assert not club_member("", everything, chain_name="רמי לוי")
    assert not club_member("אחר", everything, chain_name="רמי לוי")
    assert not club_member("club 7", everything, chain_name="רמי לוי")


def test_promo_confidence_parsing() -> None:
    assert promo_confidence("0.8") == pytest.approx(0.8)
    assert promo_confidence("85") == pytest.approx(0.85)
    assert promo_confidence(None) is None
    assert promo_confidence("high") is None
    assert promo_confidence("-1") is None


def test_precompute_keeps_every_clubs_deal(db, w: World) -> None:
    club_required, club_name, noclub = db.execute(
        "SELECT club_required, club_name, noclub FROM effective_prices"
        " WHERE canonical_id = %s AND store_id = %s AND flex_level = 'any_brand'",
        (w.canon["eggs"], w.stores["home"]),
    ).fetchone()
    assert club_required and club_name == "כרטיס אשראי"
    assert noclub["effective_price"] == "12.90" and noclub["promo_id"] is None
    assert {k: D(v["effective_price"]) for k, v in noclub["clubs"].items()} == {
        "כרטיס אשראי": D("8.50"),
        "מועדון לקוחות": D("9.90"),
    }
    # At B the deal without a club name is not kept; "אחר" is kept as data, and club_member
    # never matches it (test_unparseable_club_deal_never_applies).
    b = db.execute(
        "SELECT noclub FROM effective_prices WHERE canonical_id = %s AND store_id = %s"
        " AND flex_level = 'any_brand'",
        (w.canon["eggs"], w.stores["b"]),
    ).fetchone()[0]
    assert set(b["clubs"]) == {"מועדון לקוחות", "אחר"}


# --- /compare --------------------------------------------------------------------------------------


def test_non_member_pays_the_shelf_price_and_sees_the_offer_apart(client, w: World) -> None:
    home = compare(client, eggs_body(w, []))[w.stores["home"]]
    egg = home["items"][0]
    assert D(egg["line_total"]) == D("12.90") and D(home["total"]) == D("12.90")
    assert not egg["club_required"] and egg["club_name"] is None and not egg["promo_applied"]
    # Information only: the best club deal they did not mark and what it would take off.
    assert egg["club_offer_name"] == "כרטיס אשראי" and D(egg["club_offer_discount"]) == D("4.40")


def test_member_pays_the_club_price_tagged_with_the_club(client, w: World) -> None:
    egg = compare(client, eggs_body(w, [CHAIN1]))[w.stores["home"]]["items"][0]
    # A member of chain one's club gets 9.90 although the card deal (8.50) won the row.
    assert D(egg["line_total"]) == D("9.90")
    assert egg["club_required"] and egg["club_name"] == "מועדון לקוחות"
    assert egg["club_offer_name"] == "כרטיס אשראי" and D(egg["club_offer_discount"]) == D("1.40")
    card = compare(client, eggs_body(w, [CHAIN1, " כרטיס  אשראי "]))[w.stores["home"]]["items"][0]
    assert D(card["line_total"]) == D("8.50") and card["club_name"] == "כרטיס אשראי"
    assert card["club_offer_name"] is None and card["club_offer_discount"] is None


def test_cheapest_store_depends_on_membership(client, w: World) -> None:
    def first(clubs: list[str]) -> dict:
        r = client.post("/compare", json=eggs_body(w, clubs))
        assert r.status_code == 200, r.text
        return r.json()["stores"][0]

    assert first([])["store_id"] == w.stores["home"]  # 12.90 beats 13.50
    best = first([CHAIN2])
    assert best["store_id"] == w.stores["b"] and D(best["total"]) == D("7.00")
    assert best["items"][0]["club_name"] == "מועדון לקוחות"


def test_unparseable_club_deal_never_applies(client, w: World) -> None:
    for clubs in ([], [CHAIN2], ["אחר", "club 1", CHAIN2, "מועדון לקוחות"]):
        b = compare(client, eggs_body(w, clubs))[w.stores["b"]]
        assert D(b["total"]) >= D("7.00"), clubs  # never the unparsed 5.00
    b = compare(client, eggs_body(w, ["מועדון לקוחות"]))[w.stores["b"]]
    assert D(b["total"]) == D("7.00")  # the literal club name of the parsed deal matches


def test_promo_confidence_and_coordinates(client, w: World) -> None:
    body = {"items": [{"canonical_id": w.canon["bread"], "quantity": 3}], "location": w.location}
    stores = compare(client, body)
    bread = stores[w.stores["home"]]["items"][0]
    assert bread["promo_applied"] and bread["promo_confidence"] == pytest.approx(0.8)
    b_bread = stores[w.stores["b"]]["items"][0]
    assert b_bread["promo_confidence"] is None
    home = stores[w.stores["home"]]
    assert home["lat"] == pytest.approx(ORIGIN[1] + 1.0 * KM_LAT)
    assert home["lon"] == pytest.approx(ORIGIN[0])


# --- /optimize ---------------------------------------------------------------------------------


def optimize(client, w: World, clubs: list[str], **kw) -> dict:
    r = client.post("/optimize", json=eggs_body(w, clubs, max_stores=1, **kw))
    assert r.status_code == 200, r.text
    return r.json()


def test_optimize_single_store_depends_on_membership(client, w: World) -> None:
    plain = optimize(client, w, [])["single"]
    assert plain["stores"][0]["store"]["store_id"] == w.stores["home"]
    assert D(plain["total"]) == D("12.90")
    member = optimize(client, w, [CHAIN2])["single"]
    assert member["stores"][0]["store"]["store_id"] == w.stores["b"]
    assert D(member["total"]) == D("7.00")
    store = member["stores"][0]["store"]
    assert store["lat"] == pytest.approx(ORIGIN[1] + 3.0 * KM_LAT)


def test_headline_saving_never_counts_unmarked_clubs(client, w: World) -> None:
    travel = {"mode": "car", "cost_per_km": 0, "extra_stop_value": 0}
    resp = optimize(client, w, [], home_store_id=w.stores["b"], travel=travel)
    b = resp["single"]["breakdown"]
    # Home B at 13.50 against home store H at 12.90: 0.60, not the club deals' 13.50 - 8.50.
    assert D(b["basket_saving"]) == D("0.60") and D(b["net_saving"]) == D("0.60")
    resp = optimize(client, w, [CHAIN1], home_store_id=w.stores["b"], travel=travel)
    assert D(resp["single"]["breakdown"]["net_saving"]) == D("3.60")  # 13.50 - 9.90
