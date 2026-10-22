"""The MILP never returns a plan that costs more than the heuristic's (docs/optimizer.md, "Decisions
the tests left as they are").

The solver's objective is in whole agorot, and the unit price a shared promo gives a product is the
bundle price over its size, rounded to an agora. A percent promo "33 % off, 3 packs" on two products
makes such prices: 3.99 -> 2.6733 a pack, which the objective counts as 2.67. The solver can then
prefer a plan that is really an agora dearer.
That was seen on the real day (net saving 132.83 against the heuristic's 132.86).

Here: a world where it happens (the nearer chain's promo, really 26.77 for 5 + 4 packs; the
farther chain's shelf prices, 26.76), the raw solver's choice, and the route's answer, which keeps
the heuristic's plan whenever it is strictly cheaper.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from api_world import World, add_promo
from test_api_packs import add_counted_canonical, add_pack_item

from smartcart_api.precompute import precompute_effective_prices
from smartcart_api.routes import optimize as optimize_route

D = Decimal
pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]


@pytest.fixture
def flip(db, world: World) -> World:
    for key in ("pa", "pb"):
        add_counted_canonical(db, world, key, 1)
    near_a = add_pack_item(db, world, "near_a", "pa", "t-c1", "מוצר א", "1", "יחידה", "3.99")
    near_b = add_pack_item(db, world, "near_b", "pb", "t-c1", "מוצר ב", "1", "יחידה", "5.00")
    add_promo(
        db, "t-c1", None, "PR", [near_a, near_b], "percent", "33", min_qty="3",
        description="33% הנחה ב-3",
    )  # fmt: skip
    add_pack_item(db, world, "far_a", "pa", "t-c2", "מוצר א", "1", "יחידה", "2.48")
    add_pack_item(db, world, "far_b", "pb", "t-c2", "מוצר ב", "1", "יחידה", "3.59")
    precompute_effective_prices(db, chains=world.chains)
    return world


def body(w: World, solver: str) -> dict:
    return {
        "items": [
            {"canonical_id": w.canon["pa"], "quantity": 5},
            {"canonical_id": w.canon["pb"], "quantity": 4},
        ],
        "location": w.location,
        "solver": solver,
        "max_stores": 1,
        "travel": {"mode": "delivery", "extra_stop_value": "0"},
    }


def single(client, w: World, solver: str) -> tuple[int, Decimal]:
    r = client.post("/optimize", json=body(w, solver))
    assert r.status_code == 200, r.text
    assert r.json()["solver"] == solver
    plan = r.json()["single"]
    assert plan["missing"] == []
    return plan["stores"][0]["store"]["store_id"], D(plan["total"])


def test_the_heuristic_buys_at_the_cheaper_far_store(client, flip: World) -> None:
    assert single(client, flip, "heuristic") == (flip.stores["b"], D("26.76"))


def test_the_raw_solver_takes_the_plan_that_is_an_agora_dearer(
    client, flip: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cause, kept visible: without the comparison the MILP's plan is the nearer store's,
    26.77, an agora dearer than the heuristic's 26.76. If a later change makes the objective exact this
    test says so, and the comparison can stay as a guard."""
    monkeypatch.setattr(optimize_route, "_no_worse", lambda sol, ev, baskets: sol)
    assert single(client, flip, "milp") == (flip.stores["home"], D("26.77"))


def test_the_route_never_returns_a_plan_dearer_than_the_heuristics(client, flip: World) -> None:
    store, total = single(client, flip, "milp")
    assert (store, total) == (flip.stores["b"], D("26.76"))
    # the plan is a whole plan: lines, totals and the saving breakdown are those of that store
    r = client.post("/optimize", json={**body(flip, "milp"), "home_store_id": flip.stores["home"]})
    plan = r.json()["single"]
    assert [i["canonical_id"] for i in plan["stores"][0]["store"]["items"]] != []
    assert D(plan["total"]) == D(plan["stores"][0]["store"]["total"]) == D("26.76")
    assert plan["breakdown"] is not None


def test_a_milp_plan_that_ties_the_heuristic_is_kept(client, db, world: World) -> None:
    """With whole-agora prices nothing is rounded and the MILP's plan, which knows the bundles,
    stays: the comparison replaces a plan only when the heuristic's is strictly cheaper."""
    for key in ("pa", "pb"):
        add_counted_canonical(db, world, key, 1)
    a = add_pack_item(db, world, "near_a", "pa", "t-c1", "מוצר א", "1", "יחידה", "4.00")
    b = add_pack_item(db, world, "near_b", "pb", "t-c1", "מוצר ב", "1", "יחידה", "5.00")
    add_promo(db, "t-c1", None, "PR", [a, b], "bundle", "9.00", min_qty="3", description="3 ב-9")
    precompute_effective_prices(db, chains=world.chains)
    r = client.post("/optimize", json=body(world, "milp"))
    assert r.status_code == 200, r.text
    plan = r.json()["single"]
    assert plan["stores"][0]["store"]["store_id"] == world.stores["home"]
    assert plan["promo_bundles"]  # the bundles of the shared promo are reported
