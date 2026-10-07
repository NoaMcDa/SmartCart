"""POST /optimize (issue #62)."""

from __future__ import annotations

from decimal import Decimal
from itertools import product

import pytest
from api_world import World, add_store

from smartcart_api import schemas
from smartcart_api.basket import money, price_baskets, stores_in_radius
from smartcart_api.precompute import precompute_effective_prices
from smartcart_api.routes.optimize import evaluate_subsets, travel_cost

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
D = Decimal


@pytest.fixture
def w(db, world: World) -> World:
    # Seven more stores within 5 km (they inherit their chain's base prices): 10 candidates.
    for n, km in enumerate((2.5, 3.0, 3.5, 4.0)):
        world.stores[f"c1_{n}"] = add_store(db, "t-c1", f"X{n}", km)
    for n, km in enumerate((3.2, 3.8, 4.5)):
        world.stores[f"c2_{n}"] = add_store(db, "t-c2", f"Y{n}", km)
    precompute_effective_prices(db, chains=world.chains)
    return world


def items(w: World) -> list[dict]:
    return [
        {"canonical_id": w.canon["milk3"], "quantity": 2},
        {"canonical_id": w.canon["paste"], "quantity": 1},
        {"canonical_id": w.canon["salmon"], "quantity": 1},
        {"canonical_id": w.canon["bread"], "quantity": 3},
        {"canonical_id": w.canon["eggs"], "quantity": 1},
    ]


def post(client, w: World, **kw) -> dict:
    r = client.post("/optimize", json={"items": items(w), "location": w.location, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_ten_stores_two_per_plan_is_55_subsets(client, w: World) -> None:
    resp = post(client, w, max_stores=2, candidate_stores=10)
    assert resp["subsets_evaluated"] == 55  # 10 singles + 45 pairs
    assert post(client, w, max_stores=1)["subsets_evaluated"] == 10
    assert post(client, w, max_stores=3)["subsets_evaluated"] == 10 + 45 + 120


def test_three_alternatives_and_the_net_saving_identity(client, w: World) -> None:
    resp = post(client, w, home_store_id=w.stores["home"], min_split_saving=1,
                travel={"mode": "car", "cost_per_km": 0, "extra_stop_value": 0})
    for kind in ("single", "split", "minimum_effort"):
        plan = resp[kind]
        assert plan is not None and plan["kind"] == kind
        b = plan["breakdown"]
        assert D(b["net_saving"]) == D(b["basket_saving"]) - D(b["travel_cost"]) - D(b["extra_stop_cost"])
    # Without travel cost the cheapest single store is A (137.60 versus 138.70 at home)...
    assert resp["single"]["stores"][0]["store"]["store_id"] == w.stores["a"]
    assert D(resp["single"]["breakdown"]["net_saving"]) == D("1.10")
    # ...and the split takes the bread from chain c2 (18.00 instead of 20.00).
    split = resp["split"]
    assert split["recommended"] and not resp["single"]["recommended"]
    assert D(split["total"]) == D("135.60") and D(split["breakdown"]["basket_saving"]) == D("3.10")
    by_store = {a["store"]["chain_id"]: a for a in split["stores"]}
    assert by_store["t-c2"]["item_ids"] == [w.items["bread_c2"]]
    # The minimum-effort plan is the home store itself.
    me = resp["minimum_effort"]
    assert [a["store"]["store_id"] for a in me["stores"]] == [w.stores["home"]]
    assert D(me["breakdown"]["net_saving"]) == 0 and D(me["total"]) == D("138.70")


def test_split_only_above_the_minimum_saving(client, w: World) -> None:
    # Default extra-stop value (25 ILS) makes the 2.00 bread saving not worth a second stop.
    resp = post(client, w, home_store_id=w.stores["home"])
    assert resp["split"] is None and resp["single"]["recommended"]
    resp = post(client, w, home_store_id=w.stores["home"], min_split_saving=5,
                travel={"cost_per_km": 0, "extra_stop_value": 0})
    assert resp["split"] is None  # saves 2.00 < 5


def test_travel_cost_by_car_is_charged_relative_to_home(client, w: World) -> None:
    resp = post(client, w, home_store_id=w.stores["home"])
    single = resp["single"]
    # With 1.2 ILS/km, A (2 km) costs 2.40 more travel than home (1 km) and saves only 1.10.
    assert single["stores"][0]["store"]["store_id"] == w.stores["home"]
    home = single["stores"][0]["store"]
    assert D(single["travel_cost"]) == money(D(home["distance_m"]) / 1000 * D("1.2") * 2)
    assert D(single["breakdown"]["travel_cost"]) == 0


def test_walk_transit_and_delivery(client, w: World) -> None:
    resp = post(client, w, travel={"mode": "walk_transit", "extra_stop_value": 0}, min_split_saving=0)
    assert D(resp["single"]["travel_cost"]) == D("11.00")
    resp = post(client, w, travel={"mode": "delivery", "extra_stop_value": 0}, min_split_saving=1)
    assert D(resp["single"]["travel_cost"]) == 0
    assert resp["split"] is not None and D(resp["split"]["travel_cost"]) == 0


def test_no_home_store_means_no_saving_figures(client, w: World) -> None:
    resp = post(client, w)
    assert resp["minimum_effort"] is None and resp["single"]["breakdown"] is None


def test_missing_items_are_kept(client, w: World) -> None:
    body_items = items(w) + [{"canonical_id": w.canon["wafer"], "quantity": 1}]
    resp = client.post("/optimize", json={"items": body_items, "location": w.location}).json()
    assert resp["single"]["missing"] == [w.canon["wafer"]]


def test_empty_radius(client, w: World) -> None:
    resp = client.post("/optimize", json={
        "items": items(w), "location": {"lon": 35.5, "lat": 33.2, "radius_m": 1000},
    }).json()
    assert resp["subsets_evaluated"] == 0 and resp["single"]["stores"] == []
    assert len(resp["single"]["missing"]) == 5


@pytest.mark.parametrize("max_stores", [1, 2, 3])
@pytest.mark.parametrize(
    "travel",
    [
        {"mode": "car", "cost_per_km": "1.2", "extra_stop_value": "25"},
        {"mode": "car", "cost_per_km": "0", "extra_stop_value": "0"},
        {"mode": "car", "cost_per_km": "0.3", "extra_stop_value": "1"},
        {"mode": "walk_transit", "extra_stop_value": "0"},
    ],
)
def test_matches_an_exhaustive_reference(db, w: World, max_stores: int, travel: dict) -> None:
    """Without cross-item promos the best subset equals the best of all assignments of items to
    at most K of the N stores (precision of the D9 claim)."""
    req_items = [schemas.BasketItem(**i) for i in items(w)] + [
        schemas.BasketItem(canonical_id=w.canon["salmon"], quantity=1, flex_level="close")
    ]
    loc = schemas.Location(**w.location)
    t = schemas.TravelSettings(**travel)
    cands = stores_in_radius(db, loc, False, 10)
    assert len(cands) == 10
    baskets = price_baskets(db, req_items, cands, [])
    cids = list(dict.fromkeys(i.canonical_id for i in req_items))
    evals = evaluate_subsets(cands, baskets, cids, max_stores, t)
    best = min(evals, key=lambda e: (len(e.missing), e.cost))

    trip = {s.store_id: travel_cost(s, t) for s in cands}
    options = []
    for cid in cids:
        have = [s.store_id for s in cands if cid in baskets[s.store_id].lines]
        options.append(have or [None])
    ref = None
    for choice in product(*options):
        used = {s for s in choice if s is not None}
        if len(used) > max_stores:
            continue
        basket_total = sum(
            (baskets[s].lines[c].line_total for c, s in zip(cids, choice, strict=True) if s is not None),
            D(0),
        )
        cost = basket_total + sum((trip[s] for s in used), D(0)) + t.extra_stop_value * max(0, len(used) - 1)
        key = (sum(1 for s in choice if s is None), money(cost))
        ref = key if ref is None or key < ref else ref
    assert (len(best.missing), money(best.cost)) == ref
