"""Two-group "buy one, get one at P % off" promotions ("1+1", "the second at 50 %") through the
precompute, /compare and the MILP (docs/adapters.md "Promotions in real files", docs/optimizer.md).

The promotion is read by the real adapter from a small inline file in the real grouped layout, and
its fields (reward type, quantities, ``raw.get_percent``) are written to ``promos`` exactly as the
loader would, so a change in how the adapter encodes the shape breaks these tests. Expected numbers
are computed by hand.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from api_world import World, add_promo
from test_milp import _add_product

from smartcart_api import milp, schemas
from smartcart_api.basket import price_baskets, stores_in_radius
from smartcart_api.precompute import PromoTerms, fold_promo, precompute_effective_prices
from smartcart_ingest.adapters.shufersal import ShufersalAdapter

D = Decimal
pair_marks = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
FILE = "PromoFull7290027600007-001-116-20261021-043100.xml"


# --- the adapter's reading of an inline file ------------------------------------------------------


def _item(code: str, reward: str, price: str, rate: str = "") -> str:
    return (
        f"<PromotionItem><ItemCode>{code}</ItemCode><ItemType>1</ItemType>"
        f"<RewardType>{reward}</RewardType><MinQty>1.00</MinQty><MaxQty/>"
        f"<DiscountRate>{rate}</DiscountRate><DiscountedPrice>{price}</DiscountedPrice>"
        "<DiscountedPricePerMida/><bIsWeighted>0</bIsWeighted></PromotionItem>"
    )


def read_pair(desc: str, shelf: dict[str, str], rate: str, promo_id: str = "77"):
    """The adapter's PromoRecord for a trigger group at the shelf prices and a reward group at
    ``rate`` % off (rate 100: free), over the items in ``shelf``."""
    trig = "".join(_item(c, "0", p) for c, p in shelf.items())
    rew = "".join(
        _item(c, "1" if rate == "100" else "10", f"{D(p) * (100 - D(rate)) / 100:.2f}", rate)
        for c, p in shelf.items()
    )
    group = "<Group><GroupID>{}</GroupID><MinPurchaseAmount/><DiscountType/><PromotionItems>{}</PromotionItems></Group>"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?><Root><ChainID>7290027600007</ChainID>'
        "<SubChainID>001</SubChainID><StoreID>116</StoreID><BikoretNo>0</BikoretNo><Promotions>"
        f"<Promotion><PromotionID>{promo_id}</PromotionID>"
        f"<PromotionDescription>{desc}</PromotionDescription>"
        "<PromotionStartDateTime>2026-10-20T00:00:00.000</PromotionStartDateTime>"
        "<PromotionEndDateTime>2031-01-01T02:59:00.000</PromotionEndDateTime>"
        "<PromotionDays>1,2,3,4,5,6,7</PromotionDays><RedemptionLimit>0</RedemptionLimit>"
        "<ClubID>0 - כלל הלקוחות</ClubID><AdditionalIsCoupon>0</AdditionalIsCoupon>"
        f"<Groups>{group.format(1, trig)}{group.format(2, rew)}</Groups></Promotion>"
        "</Promotions></Root>"
    ).encode()
    adapter = ShufersalAdapter()
    (promo,) = adapter.parse(adapter.raw_file_for(FILE, xml), xml).promos
    return promo


def add_read(db, promo, chain: str, items: list[int], store_id: int | None = None) -> int:
    """Write what the loader writes for ``promo`` (reward type, quantity, value, raw)."""
    assert promo.reward_type == "buy_x_get_y", promo.raw["unapplied"]
    pid = add_promo(
        db,
        chain,
        store_id,
        promo.promo_id,
        items,
        promo.reward_type,
        str(promo.reward_value),
        min_qty=str(promo.min_qty),
        description=promo.description,
        get_percent=promo.raw["get_percent"],
    )
    db.execute(
        "UPDATE promos SET raw = raw || jsonb_build_object('confidence', %s::float) WHERE id = %s",
        (promo.raw["confidence"], pid),
    )
    return pid


# --- the fold, no database ---------------------------------------------------------------------


def _terms(value: str = "1", min_qty: str | None = "1", get_percent: str | None = None):
    return PromoTerms(
        1, None, "", False, None, D(min_qty) if min_qty else None, "buy_x_get_y", D(value),
        D(get_percent) if get_percent else None,
    )  # fmt: skip


@pytest.mark.parametrize(
    ("shelf", "get_percent", "eff"),
    [
        ("20.00", "50", "15.0000"),  # pay 20 + 10 for two: 15 each
        ("20.00", "100", "10.0000"),  # 1+1: pay 20 for two
        ("20.00", None, "10.0000"),  # no percentage: free, as before
        ("9.90", "25", "8.6625"),  # 9.90 x (1 + 0.75) / 2
        ("20.00", "30", "17.0000"),
    ],
)
def test_fold_the_second_at_a_percentage(shelf: str, get_percent: str | None, eff: str) -> None:
    assert fold_promo(D(shelf), _terms(get_percent=get_percent)) == (D(eff), D(2))


@pytest.mark.parametrize("get_percent", ["0", "-5", "101"])
def test_fold_ignores_a_percentage_that_is_not_a_discount(get_percent: str) -> None:
    assert fold_promo(D("20.00"), _terms(get_percent=get_percent)) is None


def test_fold_keeps_buy_two_get_one_at_a_percentage() -> None:
    # Buy 2, the third 50 % off: 9 x (2 + 0.5) / 3 each, three needed.
    assert fold_promo(D("9.00"), _terms(min_qty="2", get_percent="50")) == (D("7.5000"), D(3))


# --- precompute and /compare ----------------------------------------------------------------------


@pytest.fixture
def seconds(db, world: World) -> World:
    """Home store of chain c1: milk 3 % (private label, 6.20) on "the second at 50 %", read by the
    adapter from a real-shaped file; paste at store A keeps its 1+1 of the shared world."""
    w = world
    promo = read_pair("חלב השני ב 50%", {"7290000000001": "6.20"}, "50")
    assert promo.raw["get_percent"] == "50" and promo.raw["confidence"] == 1.0
    w.promos["milk_second_half"] = add_read(
        db, promo, "t-c1", [w.items["milk3_c1_private"]], w.stores["home"]
    )
    precompute_effective_prices(db, chains=w.chains)
    return w


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_precompute_row_of_the_second_at_fifty_percent(db, seconds: World) -> None:
    w = seconds
    row = db.execute(
        "SELECT item_id, shelf_price, effective_price, effective_unit_price, promo_id,"
        " promo_min_qty FROM effective_prices WHERE canonical_id = %s AND store_id = %s"
        " AND flex_level = 'any_brand'",
        (w.canon["milk3"], w.stores["home"]),
    ).fetchone()
    # 6.20 + 3.10 for two packs: 4.65 each, two needed; 0.62 per 100 ml times 0.75.
    assert row == (
        w.items["milk3_c1_private"], D("6.20"), D("4.6500"), D("0.4650"),
        w.promos["milk_second_half"], D(2),
    )  # fmt: skip


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
@pytest.mark.parametrize(
    ("quantity", "total", "applied", "add_qty", "add_saving"),
    [
        (1, "6.20", False, "1", "3.10"),  # one pack: no pair, the response offers the second
        (2, "9.30", True, None, None),  # 6.20 + 3.10
        (
            3,
            "15.50",
            True,
            "1",
            "6.20",
        ),  # a pair and a loose pack; a fourth makes two pairs (saves 6.20)
        (4, "18.60", True, None, None),  # two pairs
    ],
)
def test_compare_totals_of_the_second_at_fifty_percent(
    client, seconds: World, quantity: int, total: str, applied: bool, add_qty, add_saving
) -> None:
    w = seconds
    body = {
        "items": [{"canonical_id": w.canon["milk3"], "quantity": quantity}],
        "location": w.location,
    }
    r = client.post("/compare", json=body)
    assert r.status_code == 200, r.text
    home = next(s for s in r.json()["stores"] if s["store_id"] == w.stores["home"])
    line = home["items"][0]
    assert D(line["line_total"]) == D(total) and D(home["total"]) == D(total)
    assert line["promo_applied"] is applied and line["promo_description"] == "חלב השני ב 50%"
    assert line["promo_confidence"] == pytest.approx(1.0)  # the adapter's number, unchanged
    if add_qty is None:
        assert line["promo_add_qty"] is None
    else:
        assert (D(line["promo_add_qty"]), D(line["promo_add_saving"])) == (
            D(add_qty),
            D(add_saving),
        )


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_one_plus_one_read_from_the_grouped_layout_is_a_free_second_unit(client, db, world):
    """The "1+1" shape (rate 100, reward price 0) on the shared world's bread (7.00 at store A,
    where the chain-wide "3 for 20" also applies): at two loaves the pair beats it, unit for unit."""
    w = world
    promo = read_pair("לחם 1+1", {"7290000000002": "7.00"}, "100")
    assert (promo.raw["get_percent"], promo.raw["confidence"]) == ("100", 1.0)
    add_read(db, promo, "t-c1", [w.items["bread_c1"]], w.stores["a"])
    precompute_effective_prices(db, chains=w.chains)
    totals = {}
    for quantity in (1, 2, 3):
        body = {"items": [{"canonical_id": w.canon["bread"], "quantity": quantity}],
                "location": w.location}  # fmt: skip
        r = client.post("/compare", json=body)
        a = next(s for s in r.json()["stores"] if s["store_id"] == w.stores["a"])
        totals[quantity] = (D(a["total"]), a["items"][0]["promo_applied"])
    # 3.50 a loaf (pairs), against 6.67 for the "3 for 20": a pair for 7.00, the third at the shelf.
    assert totals == {1: (D("7.00"), False), 2: (D("7.00"), True), 3: (D("14.00"), True)}


# --- the MILP: one promotion over several products ---------------------------------------------


@pytest.fixture
def hummus(db, world: World) -> World:
    """Chain c1: two hummus at 8.00 and 6.00 in one "the second at 50 %" (both items in both
    groups of the file), and two yogurts at 5.00 in one "1+1"."""
    w = world
    h1 = _add_product(db, w, "hum_a", "חומוס א", "t-c1", "8.00")
    h2 = _add_product(db, w, "hum_b", "חומוס ב", "t-c1", "6.00")
    ys = _add_product(db, w, "yog_s", "יוגורט תות", "t-c1", "5.00")
    yv = _add_product(db, w, "yog_v", "יוגורט וניל", "t-c1", "5.00")
    halves = read_pair("חומוס השני ב 50%", {"7290000000011": "8.00", "7290000000012": "6.00"}, "50")
    assert halves.raw["confidence"] == 0.9 and halves.raw["confidence_reasons"] == [
        "mixed_items_unverified"
    ]
    add_read(db, halves, "t-c1", [h1, h2])
    ones = read_pair("יוגורט 1+1", {"7290000000021": "5.00", "7290000000022": "5.00"}, "100", "78")
    add_read(db, ones, "t-c1", [ys, yv])
    precompute_effective_prices(db, chains=w.chains)
    return w


def optimize(client, w: World, items: list[dict], **kw) -> dict:
    body = {"items": items, "location": w.location, "travel": {"cost_per_km": "0",
            "extra_stop_value": "0"}, **kw}  # fmt: skip
    r = client.post("/optimize", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_the_milp_pairs_units_of_two_products_at_the_cheapest_discount(client, hummus: World):
    w = hummus
    items = [
        {"canonical_id": w.canon["hum_a"], "quantity": 1},
        {"canonical_id": w.canon["hum_b"], "quantity": 1},
    ]
    h = optimize(client, w, items, home_store_id=w.stores["home"])
    m = optimize(client, w, items, home_store_id=w.stores["home"], solver="milp")
    # One of each: no line reaches a pair alone (8 + 6), the heuristic cannot pair them.
    assert D(h["single"]["total"]) == D("14.00")
    # Together they are a pair: the store gives the second at 50 %. The model counts the cheapest
    # unit of the group (6.00) at 50 %, which never overstates it: 14.00 - 3.00.
    assert D(m["single"]["total"]) == D("11.00")
    assert m["single"]["promo_bundles"] == [
        {"promo_description": "חומוס השני ב 50%", "bundle_count": 1, "saving": "3.00",
         "add_qty": None}
    ]  # fmt: skip
    lines = m["single"]["stores"][0]["store"]["items"]
    assert sum(D(i["line_total"]) for i in lines) == D("11.00")
    assert all(i["promo_applied"] for i in lines)


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_the_milp_pairs_two_yogurts_for_the_price_of_one(client, hummus: World):
    w = hummus
    items = [
        {"canonical_id": w.canon["yog_s"], "quantity": 1},
        {"canonical_id": w.canon["yog_v"], "quantity": 1},
    ]
    h = optimize(client, w, items)
    m = optimize(client, w, items, solver="milp")
    assert D(h["single"]["total"]) == D("10.00")
    assert D(m["single"]["total"]) == D("5.00")  # equal prices: the second one is free
    assert m["single"]["promo_bundles"][0]["bundle_count"] == 1
    assert D(m["single"]["promo_bundles"][0]["saving"]) == D("5.00")


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_the_milp_group_of_a_percentage_pair_is_never_better_than_the_store_gives(db, hummus):
    """The group the MILP builds from the promo row: a pair of 8.00 and 6.00 products at 50 %."""
    w = hummus
    req = [
        schemas.BasketItem(canonical_id=w.canon["hum_a"], quantity=1),
        schemas.BasketItem(canonical_id=w.canon["hum_b"], quantity=1),
    ]
    cands = stores_in_radius(db, schemas.Location(**w.location), False, 10)
    baskets = price_baskets(db, req, cands, [])
    _, groups = milp.priced_lines(db, baskets)
    (g,) = [g for g in groups.values() if g.description == "חומוס השני ב 50%"][:1]
    assert (g.size, g.fixed) == (2, D("-3.00"))  # 50 % of the cheapest shelf price, per pair
    cost, bundles = milp.group_cost(g, {w.canon["hum_a"]: 1, w.canon["hum_b"]: 1},
                                    {w.canon["hum_a"]: D("8.00"), w.canon["hum_b"]: D("6.00")})  # fmt: skip
    assert (cost, bundles) == (1100, 1)
    # The store gives the cheaper unit at 50 % (3.00 off) or the second-scanned one (4.00 off at
    # most): 11.00 is never below what the store charges.
