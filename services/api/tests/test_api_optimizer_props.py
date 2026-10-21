"""Randomized correctness tests for the optimizer, with no database (docs/optimizer.md, Invariants).

Small random worlds (2-4 stores, 2-4 needs, bundles, shared promos, quantity limits, travel and
extra-stop costs) are solved by the MILP and by the phase 1 heuristic and compared with an
exhaustive reference that shares no code with either: every store set, every assignment of needs
to stores, and for each promo group every way of putting units into bundles. Seeds are fixed, so a
failure names its seed and reproduces. ``hypothesis`` is not a dependency; this is a plain seeded
``random`` loop.

The DB-backed half (prices through the real tables, /compare and /optimize through the API) is in
test_api_optimizer_props_db.py.
"""

from __future__ import annotations

import random
from decimal import Decimal
from itertools import product

import pytest

from smartcart_api import milp, schemas
from smartcart_api.basket import StoreBasket, StoreInfo, money
from smartcart_api.routes.optimize import evaluate_subsets, travel_cost

D = Decimal
SEEDS = range(40)


# --- an exhaustive reference ---------------------------------------------------------------------


def _a(d: Decimal) -> int:
    """Exact agorot of a price that is a whole number of agorot."""
    x = d * 100
    assert x == x.to_integral_value(), d
    return int(x)


def brute_group(g: milp.Group, qty: dict[int, int], shelf: dict[int, Decimal]) -> int:
    """The cheapest cost in agorot of ``qty`` units under promo group ``g``: every way of putting
    u_i of need i into bundles (sum u = size x bundles, within the quantity limit)."""
    ids = sorted(qty)
    best: int | None = None
    for u in product(*(range(qty[c] + 1) for c in ids)):
        inside = sum(u)
        if inside % g.size or (g.max_units is not None and inside > g.max_units):
            continue
        cost = _a(g.fixed) * (inside // g.size)
        for c, uc in zip(ids, u, strict=True):
            cost += _a(shelf[c]) * (qty[c] - uc) + _a(g.unit[c]) * uc
        best = cost if best is None else min(best, cost)
    assert best is not None
    return best


def plan_cost(p: milp.Problem, choice: dict[int, int]) -> int:
    """Agorot of the goods in ``choice`` (need -> store), promo groups pooled per store."""
    by = {(li.canonical_id, li.store_id): li for li in p.lines}
    pools: dict[str, dict[int, int]] = {}
    total = 0
    for c, s in choice.items():
        li = by[(c, s)]
        if li.group is None:
            total += _a(li.line_total)
        else:
            pools.setdefault(li.group, {})[c] = li.quantity or 0
    for key, qty in pools.items():
        shelf = {c: by[(c, p.groups[key].store_id)].shelf_price for c in qty}
        total += brute_group(p.groups[key], qty, shelf)
    return total


def exhaustive(
    p: milp.Problem, max_stores: int, min_stores: int = 1, pool: bool = True
) -> tuple[int, int] | None:
    """(missing, cost in agorot) of the best plan over at most ``max_stores`` stores: every
    assignment of needs to stores (or to missing), ranked fewest missing first. With
    ``pool=False`` every line is priced on its own (what the heuristic does)."""
    by = {(li.canonical_id, li.store_id): li for li in p.lines}
    ids = [s.store_id for s in p.stores]
    trips = {s.store_id: _a(s.trip) for s in p.stores}
    extra = _a(p.extra_stop_value)
    best: tuple[int, int] | None = None
    options = [[s for s in ids if (c, s) in by] + [None] for c in p.canonical_ids]
    for pick in product(*options):
        choice = {c: s for c, s in zip(p.canonical_ids, pick, strict=True) if s is not None}
        used = set(choice.values())
        if len(used) > max_stores or len(used) < min_stores:
            continue
        if pool:
            goods = plan_cost(p, choice)
        else:
            goods = sum(_a(by[(c, s)].line_total) for c, s in choice.items())
        cost = goods + sum(trips[s] for s in used) + extra * max(0, len(used) - 1)
        key = (len(p.canonical_ids) - len(choice), cost)
        best = key if best is None or key < best else best
    return best


# --- random worlds -----------------------------------------------------------------------------


def random_problem(seed: int, shared: bool = True, limits: bool = True) -> milp.Problem:
    rnd = random.Random(seed)
    n_stores, n_needs = rnd.randint(2, 4), rnd.randint(2, 4)
    stores = [
        milp.StoreCost(s, D(rnd.randint(0, 900)) / 100, n)
        for n, s in enumerate(range(1, n_stores + 1))
    ]
    needs = list(range(10, 10 + n_needs))
    extra = rnd.choice([D(0), D("0.50"), D(3), D(10)])
    lines: list[milp.Line] = []
    groups: dict[str, milp.Group] = {}
    for s in stores:
        kind = rnd.choice(["none", "fixed", "fixed", "bogo", "unit"]) if shared else "none"
        size = rnd.randint(2, 3)
        limit = rnd.choice([None, None, size, 2 * size]) if limits else None
        shelves: dict[int, Decimal] = {}
        qtys: dict[int, int] = {}
        members: list[int] = []
        for c in needs:
            if rnd.random() < 0.2:
                continue  # not stocked here
            shelves[c] = D(rnd.randint(150, 1200)) / 100
            qtys[c] = rnd.randint(1, 4)
            if kind != "none" and rnd.random() < 0.7:
                members.append(c)
        key = f"g{s.store_id}"
        if members:
            cheapest = min(shelves[c] for c in members)
            if kind == "fixed":
                total = sum(shelves[c] for c in members) / len(members) * size
                g = milp.Group(
                    key,
                    s.store_id,
                    "N ב-X",
                    size,
                    money(total * D("0.8")),
                    dict.fromkeys(members, D(0)),
                    limit,
                )
            elif kind == "bogo":
                g = milp.Group(
                    key, s.store_id, "1+1", size, -cheapest, {c: shelves[c] for c in members}, limit
                )
            else:
                g = milp.Group(
                    key,
                    s.store_id,
                    "מחיר ליחידה",
                    size,
                    D(0),
                    {c: money(shelves[c] * D("0.8")) for c in members},
                    limit,
                )
            groups[key] = g
        # Some needs have a promo of their own (a group of one), the rest are plain.
        for c, shelf in shelves.items():
            q = qtys[c]
            gkey = key if c in members else None
            if gkey is None and shared and rnd.random() < 0.25:
                gkey = f"own{c}@{s.store_id}"
                groups[gkey] = milp.Group(gkey, s.store_id, "1+1", 2, shelf, {c: D(0)}, None)
            if gkey is None:
                lines.append(
                    milp.Line(
                        c,
                        s.store_id,
                        c * 100 + s.store_id,
                        shelf * q,
                        shelf,
                        None,
                        None,
                        rnd.random() < 0.15,
                    )
                )
            else:
                total = D(brute_group(groups[gkey], {c: q}, {c: shelf})) / 100
                lines.append(
                    milp.Line(
                        c,
                        s.store_id,
                        c * 100 + s.store_id,
                        total,
                        shelf,
                        q,
                        gkey,
                        rnd.random() < 0.15,
                    )
                )
    return milp.Problem(needs, stores, lines, groups, extra)


def has_shared(p: milp.Problem) -> bool:
    n: dict[str, int] = {}
    for li in p.lines:
        if li.group:
            n[li.group] = n.get(li.group, 0) + 1
    return any(v >= 2 for v in n.values())


# --- the MILP equals the exhaustive optimum ----------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_milp_equals_the_exhaustive_optimum(seed: int) -> None:
    p = random_problem(seed)
    for k in (1, 2, 3):
        ref = exhaustive(p, k)
        sol = milp.solve(p, k)
        assert sol is not None and ref is not None, (seed, k)
        assert (len(sol.missing), _a(sol.cost)) == ref, (seed, k)
        # What it reports is what it charges: the lines add up, and the plan costs what the
        # reference says its own assignment costs.
        assert sum(sol.line_totals.values(), D(0)) == sol.basket_total, (seed, k)
        assert _a(sol.basket_total) == plan_cost(p, sol.assignment), (seed, k)
        assert len(sol.used) <= k


@pytest.mark.parametrize("seed", SEEDS[:20])
def test_milp_is_deterministic(seed: int) -> None:
    p = random_problem(seed)
    a, b = milp.solve(p, 2), milp.solve(p, 2)
    assert (a.assignment, a.line_totals, a.bundles) == (b.assignment, b.line_totals, b.bundles)


@pytest.mark.parametrize("seed", SEEDS[:20])
def test_milp_does_not_depend_on_the_order_of_the_needs(seed: int) -> None:
    p = random_problem(seed)
    rnd = random.Random(seed)
    needs = list(p.canonical_ids)
    rnd.shuffle(needs)
    q = milp.Problem(
        needs, p.stores, rnd.sample(p.lines, len(p.lines)), p.groups, p.extra_stop_value
    )
    for k in (1, 2):
        a, b = milp.solve(p, k), milp.solve(q, k)
        assert (len(a.missing), a.cost) == (len(b.missing), b.cost), (seed, k)
        assert sorted(a.missing) == sorted(b.missing)


# --- the heuristic --------------------------------------------------------------------------------

CAR = schemas.TravelSettings(mode="car", cost_per_km=D(1), extra_stop_value=D(0))


def heuristic_world(p: milp.Problem) -> tuple[list[StoreInfo], dict[int, StoreBasket]]:
    """The Problem's lines as the priced baskets the heuristic reads. Distances make
    ``travel_cost`` (car, 1 ILS/km, round trip) equal the problem's trips."""
    from datetime import UTC, datetime

    infos = [
        StoreInfo(
            s.store_id,
            "c",
            "chain",
            f"s{s.store_id}",
            None,
            "physical",
            int(s.trip * 500),
            None,
            None,
            "address",
        )
        for s in p.stores
    ]
    now = datetime.now(UTC)
    baskets = {i.store_id: StoreBasket(info=i) for i in infos}
    for li in p.lines:
        baskets[li.store_id].lines[li.canonical_id] = schemas.PricedItem(
            canonical_id=li.canonical_id,
            item_id=li.item_id,
            display_name_he="x",
            quantity=D(li.quantity or 1),
            shelf_price=li.shelf_price,
            effective_unit_price=li.shelf_price,
            uom="unit",
            line_total=li.line_total,
            is_substitute=li.is_substitute,
            price_valid_from=now,
        )
    for s in infos:
        baskets[s.store_id].missing = [
            c for c in p.canonical_ids if c not in baskets[s.store_id].lines
        ]
    return infos, baskets


@pytest.mark.parametrize("seed", SEEDS)
def test_heuristic_is_never_better_than_the_optimum_and_equal_without_shared_promos(
    seed: int,
) -> None:
    for shared in (True, False):
        p = random_problem(seed, shared=shared, limits=False)
        infos, baskets = heuristic_world(p)
        for k in (1, 2, 3):
            travel = schemas.TravelSettings(
                mode="car", cost_per_km=D(1), extra_stop_value=p.extra_stop_value
            )
            for s, i in zip(p.stores, infos, strict=True):
                assert travel_cost(i, travel) == s.trip  # the helper really reproduces the trips
            evals = evaluate_subsets(infos, baskets, p.canonical_ids, k, travel)
            best = min(evals, key=lambda e: (len(e.missing), e.cost))
            h = (len(best.missing), _a(best.cost))
            opt = exhaustive(p, k)
            alone = exhaustive(p, k, pool=False)
            # Never better than the pooled optimum; exactly the optimum of every-line-alone
            # pricing (the D9 claim), which is the pooled one when no promo is shared.
            assert h >= opt, (seed, shared, k)
            assert h == alone, (seed, shared, k)
            if not has_shared(p):
                assert h == opt, (seed, shared, k)
            # The MILP is never worse than the heuristic.
            sol = milp.solve(p, k)
            assert (len(sol.missing), _a(sol.cost)) <= h, (seed, shared, k)
            # Each subset's plan: lines add up, the stores visited are the ones that get items.
            for e in evals:
                assert e.basket_total == money(
                    sum((baskets[s].lines[c].line_total for c, s in e.assignment.items()), D(0))
                )
                assert set(e.assignment.values()) <= set(e.stores)
                assert len(e.used) <= k
                assert sorted([*e.assignment, *e.missing]) == sorted(p.canonical_ids)


@pytest.mark.parametrize("seed", SEEDS)
def test_milp_split_is_the_heuristics_split_when_no_promo_is_shared(seed: int) -> None:
    """``min_stores = 2`` asks for the best plan that really visits two or more stores, in the
    heuristic's sense (every need at its cheapest store of the set): the same plan, or none."""
    p = random_problem(seed, shared=False, limits=False)
    infos, baskets = heuristic_world(p)
    travel = schemas.TravelSettings(
        mode="car", cost_per_km=D(1), extra_stop_value=p.extra_stop_value
    )
    evals = evaluate_subsets(infos, baskets, p.canonical_ids, 3, travel)
    splits = [e for e in evals if len(e.used) >= 2]
    sol = milp.solve(p, 3, min_stores=2)
    if not splits:
        assert sol is None, seed
    else:
        best = min(splits, key=lambda e: (len(e.missing), e.cost))
        assert sol is not None, seed
        assert (len(sol.missing), _a(sol.cost)) == (len(best.missing), _a(best.cost)), seed
        assert len(sol.used) >= 2
