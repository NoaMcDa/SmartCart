"""Regressions for the bugs the randomized tests (test_api_optimizer_props*.py) found.

One small test per bug, each with the input that triggered it. docs/optimizer.md, "Invariants
covered by tests", lists what the randomized tests assert in general.
"""

from __future__ import annotations

import random
from decimal import Decimal

import pytest
from api_world import World, add_price, add_promo, add_store

from smartcart_api import milp
from smartcart_api.basket import _Choice, _unit_paid, money
from smartcart_api.embedding import to_pgvector
from smartcart_api.precompute import precompute_effective_prices
from smartcart_api.schemas import BasketItem

D = Decimal


def needs_db(test):
    for mark in (pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector):
        test = mark(test)
    return test


@pytest.fixture
def w(db, world: World) -> World:
    for n, km in enumerate((2.5, 3.0, 3.5, 4.0)):
        world.stores[f"c1_{n}"] = add_store(db, "t-c1", f"X{n}", km)
    for n, km in enumerate((3.2, 3.8, 4.5)):
        world.stores[f"c2_{n}"] = add_store(db, "t-c2", f"Y{n}", km)
    precompute_effective_prices(db, chains=world.chains)
    return world


def post(client, path: str, w: World, items: list[dict], **kw) -> dict:
    r = client.post(path, json={"items": items, "location": w.location, **kw})
    assert r.status_code == 200, r.text
    return r.json()


# --- a store's saving is over the lines bought there ------------------------------------------


@needs_db
@pytest.mark.parametrize("solver", ["heuristic", "milp"])
def test_each_stores_saving_in_a_split_covers_only_the_lines_bought_there(
    client, w: World, solver: str
) -> None:
    """Input: milk x2, paste, bread x3 with the home store, a split over two stores. Each
    assignment's ``saving_vs_home`` was taken over everything the store sells (1.10 and -1.40)
    while its total covered only the lines bought there; the plan's basket_saving is 3.10."""
    items = [
        {"canonical_id": w.canon["milk3"], "quantity": 2},
        {"canonical_id": w.canon["paste"], "quantity": 1},
        {"canonical_id": w.canon["bread"], "quantity": 3},
    ]
    plan = post(
        client,
        "/optimize",
        w,
        items,
        home_store_id=w.stores["home"],
        min_split_saving="0",
        solver=solver,
        travel={"mode": "car", "cost_per_km": "0", "extra_stop_value": "0"},
    )["split"]
    assert plan is not None and len(plan["stores"]) == 2
    savings = [D(a["store"]["saving_vs_home"]) for a in plan["stores"]]
    assert sum(savings) == D(plan["breakdown"]["basket_saving"])
    assert any(s != 0 for s in savings)


# --- quantities that overflow or price to nothing ------------------------------------------------


def test_a_quantity_too_small_to_cost_an_agora_does_not_divide_by_zero() -> None:
    """Input: 0.0001 packs of a 7.00 item on a "3 for 20" promo: the shelf total of the quantity
    rounds to 0.00 and the paid ratio was 0.00 / 0.00 (decimal.InvalidOperation, an HTTP 500)."""
    c = _Choice(1, D("7.00"), D("6.6667"), D("6.6667"), "unit", 5, D(3), False, None, None, False)  # type: ignore[arg-type]
    assert _unit_paid(c, D("0.00"), D("0.0001"), False) == D("6.6667")
    assert money(D("0.0001") * c.shelf_price) == 0


@needs_db
@pytest.mark.parametrize("quantity", ["0.0001", "0.001", "1e30", "1001", "0", "-1"])
def test_quantities_outside_001_to_1000_are_rejected(client, w: World, quantity: str) -> None:
    """Input: quantity 1e30 made ``money()`` overflow (decimal.InvalidOperation, HTTP 500); 0.0001
    made a line cost 0.00. Both are now a 422."""
    body = {
        "items": [{"canonical_id": w.canon["bread"], "quantity": quantity}],
        "location": w.location,
    }
    for path in ("/compare", "/optimize"):
        assert client.post(path, json=body).status_code == 422


@needs_db
@pytest.mark.parametrize("quantity", ["0.01", "1000"])
def test_the_quantity_bounds_are_inclusive(client, w: World, quantity: str) -> None:
    body = {
        "items": [{"canonical_id": w.canon["bread"], "quantity": quantity}],
        "location": w.location,
    }
    assert client.post("/compare", json=body).status_code == 200
    assert BasketItem(canonical_id=1, quantity=D(quantity)).quantity == D(quantity)


# --- the same canonical asked twice ------------------------------------------------------------


@needs_db
def test_a_canonical_asked_at_two_levels_is_priced_by_the_strictest_and_never_loses_quantity(
    client, w: World
) -> None:
    """Input: salmon at any brand x1 and at close x1. Chain c2 sells only a frozen substitute
    (close). The line was whichever entry came first in the list: quantity 1 of the substitute
    (half the list silently dropped) or both. Now the strictest request decides: c2 cannot supply
    the any-brand salmon, so it is missing there; c1 prices both kilos as one line."""
    a = {"canonical_id": w.canon["salmon"], "quantity": 1, "flex_level": "any_brand"}
    b = {"canonical_id": w.canon["salmon"], "quantity": 1, "flex_level": "close"}
    first = post(client, "/compare", w, [a, b])
    second = post(client, "/compare", w, [b, a])
    assert {k: v for k, v in first.items() if k != "generated_at"} == {
        k: v for k, v in second.items() if k != "generated_at"
    }
    c1 = {w.stores[k] for k in ("home", "a", "far")} | {w.stores[f"c1_{n}"] for n in range(4)}
    for st in first["stores"]:
        if st["store_id"] in c1:
            (line,) = st["items"]
            assert D(line["quantity"]) == 2 and not line["is_substitute"]
        else:
            assert st["items"] == [] or all(
                i["canonical_id"] != w.canon["salmon"] for i in st["items"]
            )
    assert all(
        w.canon["salmon"] in st["missing"] for st in first["stores"] if st["store_id"] not in c1
    )


# --- a club never makes a line dearer --------------------------------------------------------------


def _product(db, w: World, key: str, price: str) -> int:
    cid = db.execute(
        "INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type,"
        " base_unit, critical_attrs, soft_attrs, embedding, is_mvp, rank)"
        " VALUES ('t.snacks.wafer', %s, %s, 't_wafer', 'unit', '{}', '{}', %s::vector, true, 30)"
        " RETURNING id",
        (f"t-{key}", key, to_pgvector([1.0] + [0.0] * 1023)),
    ).fetchone()[0]
    iid = db.execute(
        "INSERT INTO items (chain_id, item_code, raw_name, quantity, unit) VALUES ('t-c1', %s, %s,"
        " 1, 'יחידה') RETURNING id",
        (key, key),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
        " VALUES (%s, %s, 'any_brand', 0.97, 'rule')",
        (iid, cid),
    )
    add_price(db, iid, None, price, None, None, w.valid_from)
    w.canon[key], w.items[key] = cid, iid
    return iid


@needs_db
def test_a_club_deal_that_needs_more_packs_than_asked_does_not_beat_a_plain_deal(
    client, db, w: World
) -> None:
    """Input: one item at 10.00; club-a members get 4 for 20.00 (5.00 each), everyone 2 for 16.00
    (8.00 each); 2 packs asked. The row keeps the best deal per unit (the club's, needing 4), so a
    member paid 20.00 (shelf) and a non-member 16.00: marking the club raised the total."""
    iid = _product(db, w, "club-q", "10.00")
    add_promo(
        db,
        "t-c1",
        None,
        "CQ1",
        [iid],
        "bundle",
        "20",
        min_qty="4",
        club_only=True,
        club_name="club-a",
        description="4 ב-20 למועדון",
    )
    add_promo(db, "t-c1", None, "CQ2", [iid], "bundle", "16", min_qty="2", description="2 ב-16")
    precompute_effective_prices(db, chains=w.chains)

    def total(clubs: list[str], quantity: int) -> D:
        body = {"canonical_id": w.canon["club-q"], "quantity": quantity}
        r = post(client, "/compare", w, [body], clubs=clubs)
        return D(next(s for s in r["stores"] if s["store_id"] == w.stores["home"])["total"])

    assert total([], 2) == D("16.00")
    assert total(["club-a"], 2) == D("16.00")  # was 20.00
    assert total([], 4) == D("32.00")
    assert total(["club-a"], 4) == D("20.00")  # the club deal, when the list reaches it
    assert total(["club-a"], 5) == D("30.00")  # 4 for 20 plus one at 10, against 2+2 for 32 + 10


@needs_db
def test_an_allowed_sibling_is_chosen_by_what_the_quantity_costs(client, db, w: World) -> None:
    """Input: 3% milk at store A has 4 for 14.00 (0.35 per 100 ml, better than the 1% milk's 0.45)
    and 2 packs asked with fat_pct allowed. The own offer won on unit price, 11.80 for two,
    though the allowed 1% milk costs 9.00 for two (4.50 each)."""
    add_promo(
        db,
        "t-c1",
        w.stores["a"],
        "MQ",
        [w.items["milk3_c1_tnuva"]],
        "bundle",
        "14",
        min_qty="4",
        description="4 חלב ב-14",
    )
    add_price(db, w.items["milk1_c1"], w.stores["a"], "4.50", "0.45", "100ml", w.valid_from)
    precompute_effective_prices(db, chains=w.chains)

    def line(quantity: int, allow: list[str]) -> dict:
        item = {"canonical_id": w.canon["milk3"], "quantity": quantity, "allow": allow}
        r = post(client, "/compare", w, [item])
        (line,) = next(s for s in r["stores"] if s["store_id"] == w.stores["a"])["items"]
        return line

    two = line(2, ["fat_pct"])
    assert D(two["line_total"]) == D("9.00") and two["is_substitute"]
    assert two["item_id"] == w.items["milk1_c1"]
    four = line(4, ["fat_pct"])  # the bundle: 14.00 against 18.00
    assert D(four["line_total"]) == D("14.00") and not four["is_substitute"]
    own = line(2, [])
    assert D(own["line_total"]) == D("11.80") and not own["is_substitute"]


# --- the MILP's line totals do not depend on the order of the list -------------------------------


def test_milp_line_totals_in_a_shared_promo_do_not_depend_on_the_input_order() -> None:
    """Input: two needs with the same shelf price (5.00, 2 packs each) in one "3 for 12" promo.
    Four packs make one bundle and one pack at the shelf price, and which line paid the loose
    pack was whatever the solver found first: the same basket in another order showed other line
    totals (the group total was the same)."""
    stores = [milp.StoreCost(1, D("1.00"), 0)]
    g = milp.Group("g", 1, "3 ב-12", 3, D(12), {10: D(0), 11: D(0)})
    seen = set()
    rnd = random.Random(5)
    for _ in range(8):
        lines = [
            milp.Line(10, 1, 101, D("10.00"), D("5.00"), 2, "g"),
            milp.Line(11, 1, 111, D("10.00"), D("5.00"), 2, "g"),
        ]
        rnd.shuffle(lines)
        needs = [10, 11]
        rnd.shuffle(needs)
        sol = milp.solve(milp.Problem(needs, stores, lines, {"g": g}), 1)
        assert sol.basket_total == D("17.00")
        seen.add(tuple(sorted(sol.line_totals.items())))
    assert len(seen) == 1
