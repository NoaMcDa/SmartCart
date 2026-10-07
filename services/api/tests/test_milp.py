"""MILP cart optimizer (issue #13): smartcart_api/milp.py and POST /optimize with solver=milp."""

from __future__ import annotations

import time
from decimal import Decimal
from itertools import combinations, product

import pytest
from api_world import EMB, World, add_price, add_promo, add_store

from smartcart_api import milp, schemas
from smartcart_api.basket import money, price_baskets, stores_in_radius
from smartcart_api.embedding import to_pgvector
from smartcart_api.precompute import precompute_effective_prices
from smartcart_api.routes.optimize import evaluate_subsets, travel_cost

D = Decimal
db_marks = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]


# --- a brute-force reference over every store set and every assignment -------------------------


def reference(p: milp.Problem, max_stores: int, min_stores: int = 1) -> tuple[int, Decimal]:
    """(missing, cost) of the best plan, by enumeration: every store set, every assignment of the
    needs that share a promo, the others at their cheapest store of the set."""
    by = {(li.canonical_id, li.store_id): li for li in p.lines}
    trips = {s.store_id: s.trip for s in p.stores}
    ids = [s.store_id for s in p.stores]
    shared = {li.group for li in p.lines if li.group} & {
        g for g in p.groups if sum(1 for li in p.lines if li.group == g) >= 2
    }
    best: tuple[int, Decimal] | None = None
    for k in range(max(1, min_stores), min(max_stores, len(ids)) + 1):
        for t in combinations(ids, k):
            options = []
            for c in p.canonical_ids:
                sellers = [s for s in t if (c, s) in by]
                options.append(sellers or [None])
            for choice in product(*options):
                used = {s for s in choice if s is not None}
                if len(used) < min_stores:
                    continue
                total = D(0)
                pools: dict[str, dict[int, int]] = {}
                for c, s in zip(p.canonical_ids, choice, strict=True):
                    if s is None:
                        continue
                    li = by[(c, s)]
                    if li.group in shared:
                        pools.setdefault(li.group, {})[c] = li.quantity
                    elif li.group is not None:
                        g = p.groups[li.group]
                        total += D(milp.group_cost(g, {c: li.quantity}, {c: li.shelf_price})[0]) / 100
                    else:
                        total += li.line_total
                for key, qty in pools.items():
                    shelf = {c: by[(c, p.groups[key].store_id)].shelf_price for c in qty}
                    total += D(milp.group_cost(p.groups[key], qty, shelf)[0]) / 100
                cost = money(total + sum((trips[s] for s in used), D(0))
                             + p.extra_stop_value * max(0, len(used) - 1))
                key = (sum(1 for s in choice if s is None), cost)
                best = key if best is None or key < best else best
    assert best is not None
    return best


def mixed_problem() -> milp.Problem:
    """Three stores; two needs share "3 for 12" at stores 1 and 2, one need has a 1+1."""
    stores = [milp.StoreCost(1, D("2.00"), 0), milp.StoreCost(2, D("3.00"), 1),
              milp.StoreCost(3, D("1.00"), 2)]
    groups = {
        "p@1": milp.Group("p@1", 1, "3 ב-12", 3, D(12), {10: D(0), 11: D(0)}),
        "p@2": milp.Group("p@2", 2, "3 ב-12", 3, D(12), {10: D(0), 11: D(0)}),
        "one@3": milp.Group("one@3", 3, "1+1", 2, D("7.00"), {12: D(0)}),
    }
    L = milp.Line
    lines = [
        L(10, 1, 101, D("10.00"), D("5.00"), 2, "p@1"), L(11, 1, 111, D("5.00"), D("5.00"), 1, "p@1"),
        L(10, 2, 102, D("9.80"), D("4.90"), 2, "p@2"), L(11, 2, 112, D("5.50"), D("5.50"), 1, "p@2"),
        L(10, 3, 103, D("9.00"), D("4.50"), None), L(11, 3, 113, D("4.60"), D("4.60"), None),
        L(12, 1, 121, D("16.00"), D("8.00"), None), L(12, 3, 123, D("7.00"), D("7.00"), 2, "one@3"),
        L(13, 2, 132, D("3.00"), D("3.00"), None, None, True),
    ]
    return milp.Problem([10, 11, 12, 13], stores, lines, groups, D(5))


@pytest.mark.parametrize("max_stores", [1, 2, 3])
def test_matches_brute_force_with_shared_promos(max_stores: int) -> None:
    p = mixed_problem()
    sol = milp.solve(p, max_stores)
    assert sol is not None and sol.status == "optimal"
    assert (len(sol.missing), sol.cost) == reference(p, max_stores)


@pytest.mark.parametrize("seed", range(4))
def test_matches_brute_force_on_random_small_baskets(seed: int) -> None:
    p = milp.synthetic_problem(n_items=7, n_stores=4, seed=seed, shared_every=3)  # 3, 6 share
    for k in (1, 2, 3):
        sol = milp.solve(p, k)
        assert (len(sol.missing), sol.cost) == reference(p, k), (seed, k)
    sol = milp.solve(p, 3, min_stores=2)
    if sol is not None:
        assert (len(sol.missing), sol.cost) == reference(p, 3, min_stores=2)


def test_shared_bundle_is_reported_and_lines_add_up() -> None:
    p = mixed_problem()
    for k in (1, 2, 3):
        sol = milp.solve(p, k)
        assert sum(sol.line_totals.values()) == sol.basket_total
        assert all(b.count >= 1 and b.saving > 0 and b.add_qty is None for b in sol.bundles)
    sol = milp.solve(milp.Problem(p.canonical_ids, p.stores[:1], p.lines, p.groups), 1)
    # Store 1 alone: 2 + 1 yogurts fill one "3 for 12" (15.00 at shelf); 13 is not sold there.
    assert sol.missing == [13] and sol.bundles[0].count == 1 and sol.bundles[0].saving == D(3)
    assert sol.line_totals[10] + sol.line_totals[11] == D(12)


def test_add_one_more_only_when_it_lowers_the_total() -> None:
    g9 = milp.Group("g", 1, "3 ב-9", 3, D(9), {1: D(0)})
    line = milp.Line(1, 1, 11, D("10.00"), D("5.00"), 2, "g")
    out = milp.suggest_additions({"g": g9}, {1: line})
    assert [(u.add_qty, u.saving, u.count) for u in out] == [(1, D("1.00"), 1)]  # 10.00 -> 9.00
    g12 = milp.Group("g", 1, "3 ב-12", 3, D(12), {1: D(0)})
    assert milp.suggest_additions({"g": g12}, {1: line}) == []  # 10.00 -> 12.00: not a saving
    g1p1 = milp.Group("g", 1, "1+1", 2, D(5), {1: D(0)})
    one = milp.Line(1, 1, 11, D("5.00"), D("5.00"), 1, "g")
    assert milp.suggest_additions({"g": g1p1}, {1: one}) == []  # 5.00 -> 5.00: zero is not positive


def test_group_cost_respects_the_quantity_limit() -> None:
    g = milp.Group("g", 1, "1+1", 2, D(5), {1: D(0)}, max_units=2)
    assert milp.group_cost(g, {1: 4}, {1: D(5)}) == (500 + 1000, 1)  # one bundle, two at shelf


@pytest.mark.parametrize("max_stores", [2, 3])
def test_benchmark_40_items_10_stores(max_stores: int, capsys: pytest.CaptureFixture) -> None:
    """Issue #13 benchmark: 40 needs x 10 stores, the two solves /optimize makes. The research's
    "tens of milliseconds" is an expectation; the measured numbers go to docs/optimizer.md."""
    times = []
    for seed in range(5):
        p = milp.synthetic_problem(40, 10, seed=seed)
        for k in (1, max_stores):
            t = time.perf_counter()
            sol = milp.solve(p, k)
            times.append(time.perf_counter() - t)
            assert sol is not None and sol.status == "optimal"
    times.sort()
    with capsys.disabled():
        print(f"\n[milp bench] 40x10 K={max_stores}: median {times[len(times) // 2] * 1000:.0f} ms,"
              f" max {times[-1] * 1000:.0f} ms")
    assert times[-1] < 1.0


def test_without_shared_promos_equals_the_heuristic_enumeration() -> None:
    """No line shares a promo: the MILP is the heuristic (cheapest store of the best set)."""
    p = milp.synthetic_problem(40, 10, seed=3)
    plain = milp.Problem(p.canonical_ids, p.stores,
                         [milp.Line(li.canonical_id, li.store_id, li.item_id, li.line_total,
                                    li.shelf_price, None, None, li.is_substitute) for li in p.lines],
                         {}, p.extra_stop_value)
    for k in (1, 2, 3):
        sol = milp.solve(plain, k)
        best = None
        for t in milp.store_sets([s.store_id for s in plain.stores], k):
            total, missing, used = D(0), 0, set()
            for c in plain.canonical_ids:
                cands = [li for li in plain.lines if li.canonical_id == c and li.store_id in t]
                if not cands:
                    missing += 1
                    continue
                li = min(cands, key=lambda li: li.line_total)
                total += li.line_total
                used.add(li.store_id)
            trips = sum((s.trip for s in plain.stores if s.store_id in used), D(0))
            key = (missing, money(total + trips + plain.extra_stop_value * max(0, len(used) - 1)))
            best = key if best is None or key < best else best
        assert (len(sol.missing), sol.cost) == best


# --- through the API, on the seeded world ------------------------------------------------------


@pytest.fixture
def w(db, world: World) -> World:
    for n, km in enumerate((2.5, 3.0, 3.5, 4.0)):
        world.stores[f"c1_{n}"] = add_store(db, "t-c1", f"X{n}", km)
    for n, km in enumerate((3.2, 3.8, 4.5)):
        world.stores[f"c2_{n}"] = add_store(db, "t-c2", f"Y{n}", km)
    precompute_effective_prices(db, chains=world.chains)
    return world


def basket(w: World) -> list[dict]:
    return [
        {"canonical_id": w.canon["milk3"], "quantity": 2},
        {"canonical_id": w.canon["paste"], "quantity": 1},
        {"canonical_id": w.canon["salmon"], "quantity": 1},
        {"canonical_id": w.canon["bread"], "quantity": 3},
        {"canonical_id": w.canon["eggs"], "quantity": 1},
    ]


def post(client, w: World, items: list[dict] | None = None, **kw) -> dict:
    r = client.post("/optimize", json={"items": items or basket(w), "location": w.location, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def _key(plan: dict | None) -> tuple | None:
    if plan is None:
        return None
    return (D(plan["total"]), D(plan["travel_cost"]), sorted(a["store"]["store_id"] for a in plan["stores"]),
            plan["missing"], plan["recommended"])


TRAVELS = [
    {"mode": "car", "cost_per_km": "1.2", "extra_stop_value": "25"},
    {"mode": "car", "cost_per_km": "0", "extra_stop_value": "0"},
    {"mode": "car", "cost_per_km": "0.3", "extra_stop_value": "1"},
    {"mode": "walk_transit", "extra_stop_value": "0"},
    {"mode": "delivery", "extra_stop_value": "0"},
]


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
@pytest.mark.parametrize("max_stores", [1, 2, 3])
@pytest.mark.parametrize("travel", TRAVELS)
@pytest.mark.parametrize("min_split_saving", ["0", "1", "25"])
def test_db_api_equals_the_heuristic_without_shared_promos(
    client, w: World, max_stores: int, travel: dict, min_split_saving: str
) -> None:
    """Acceptance (#13): no cross-item promo in the world, so the MILP's plans are the
    heuristic's: same totals, same stores, same breakdown."""
    kw = {"home_store_id": w.stores["home"], "max_stores": max_stores, "travel": travel,
          "min_split_saving": min_split_saving}
    h = post(client, w, **kw)
    m = post(client, w, solver="milp", **kw)
    assert h["solver"] == "heuristic" and m["solver"] == "milp"
    for kind in ("single", "split", "minimum_effort"):
        assert _key(m[kind]) == _key(h[kind]), kind
        if h[kind] is not None:
            assert m[kind]["breakdown"] == h[kind]["breakdown"], kind
    assert m["subsets_evaluated"] == h["subsets_evaluated"]


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
@pytest.mark.parametrize("max_stores", [1, 2, 3])
@pytest.mark.parametrize("travel", TRAVELS[:4])
def test_db_milp_equals_an_exhaustive_reference(db, w: World, max_stores: int, travel: dict) -> None:
    """The existing exhaustive reference (test_optimize.py) applied to the MILP's best plan."""
    req = [schemas.BasketItem(**i) for i in basket(w)] + [
        schemas.BasketItem(canonical_id=w.canon["salmon"], quantity=1, flex_level="close")
    ]
    t = schemas.TravelSettings(**travel)
    cands = stores_in_radius(db, schemas.Location(**w.location), False, 10)
    baskets = price_baskets(db, req, cands, [])
    cids = list(dict.fromkeys(i.canonical_id for i in req))
    lines, groups = milp.priced_lines(db, baskets)
    p = milp.Problem(cids, [milp.StoreCost(s.store_id, travel_cost(s, t), n) for n, s in enumerate(cands)],
                     [li for s in cands for li in lines[s.store_id]], groups, t.extra_stop_value)
    sol = milp.solve(p, max_stores)
    evals = evaluate_subsets(cands, baskets, cids, max_stores, t)
    best = min(evals, key=lambda e: (len(e.missing), e.cost))
    assert (len(sol.missing), money(sol.cost)) == (len(best.missing), money(best.cost))


# --- crafted cross-item promos -----------------------------------------------------------------


def _add_product(db, w: World, key: str, name: str, chain: str, price: str) -> int:
    if key not in w.canon:
        w.canon[key] = db.execute(
            "INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type,"
            " base_unit, critical_attrs, soft_attrs, embedding, is_mvp, rank)"
            " VALUES ('t.snacks.wafer', %s, %s, 't_wafer', 'unit', '{}', '{}', %s::vector, true, 30)"
            " RETURNING id",
            (f"t-{key}", name, to_pgvector(EMB.embed_one(name))),
        ).fetchone()[0]
    iid = db.execute(
        "INSERT INTO items (chain_id, item_code, raw_name, quantity, unit) VALUES (%s, %s, %s, 1,"
        " 'יחידה') RETURNING id",
        (chain, f"{key}-{chain}", name),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
        " VALUES (%s, %s, 'any_brand', 0.97, 'rule')",
        (iid, w.canon[key]),
    )
    add_price(db, iid, None, price, None, None, w.valid_from)
    w.items[f"{key}_{chain}"] = iid
    return iid


@pytest.fixture
def promos(db, world: World) -> World:
    """Chain c1 only: two yogurts at 5.00 in a mix-and-match "3 for 12", and two hummus at 8.00
    and 6.00 in a "buy 2 get 1" across both."""
    w = world
    ys = _add_product(db, w, "yog_s", "יוגורט תות", "t-c1", "5.00")
    yv = _add_product(db, w, "yog_v", "יוגורט וניל", "t-c1", "5.00")
    h1 = _add_product(db, w, "hum_a", "חומוס א", "t-c1", "8.00")
    h2 = _add_product(db, w, "hum_b", "חומוס ב", "t-c1", "6.00")
    add_promo(db, "t-c1", None, "MIX", [ys, yv], "bundle", "12", min_qty="3",
              description="3 יוגורטים ב-12")
    add_promo(db, "t-c1", None, "B2G1", [h1, h2], "buy_x_get_y", "1", min_qty="2",
              description="קנה 2 קבל 1 חינם")
    precompute_effective_prices(db, chains=w.chains)
    return w


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_db_three_for_twelve_across_two_products(client, promos: World) -> None:
    w = promos
    items = [{"canonical_id": w.canon["yog_s"], "quantity": 2},
             {"canonical_id": w.canon["yog_v"], "quantity": 1}]
    kw = {"items": items, "travel": {"cost_per_km": "0", "extra_stop_value": "0"}}
    h = post(client, w, **kw)
    m = post(client, w, solver="milp", **kw)
    # Line by line, neither yogurt reaches 3: 2 x 5.00 + 5.00. Together they fill one bundle.
    assert D(h["single"]["total"]) == D("15.00")
    assert D(m["single"]["total"]) == D("12.00")
    assert h["single"]["promo_bundles"] == []
    assert m["single"]["promo_bundles"] == [
        {"promo_description": "3 יוגורטים ב-12", "bundle_count": 1, "saving": "3.00", "add_qty": None}
    ]
    store_items = m["single"]["stores"][0]["store"]["items"]
    assert sum(D(i["line_total"]) for i in store_items) == D("12.00")
    assert all(i["promo_applied"] for i in store_items)


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_db_buy_two_get_one_across_two_products(client, promos: World) -> None:
    w = promos
    items = [{"canonical_id": w.canon["hum_a"], "quantity": 2},
             {"canonical_id": w.canon["hum_b"], "quantity": 1}]
    kw = {"items": items, "home_store_id": w.stores["home"],
          "travel": {"cost_per_km": "0", "extra_stop_value": "0"}}
    h = post(client, w, **kw)
    m = post(client, w, solver="milp", **kw)
    assert D(h["single"]["total"]) == D("22.00")
    # The cheapest unit (6.00) is free: 8 + 8 + 6 - 6. With mixed prices the model counts the
    # cheapest unit of the group, which never overstates the discount.
    assert D(m["single"]["total"]) == D("16.00")
    assert m["single"]["promo_bundles"][0]["bundle_count"] == 1
    assert D(m["single"]["promo_bundles"][0]["saving"]) == D("6.00")
    # D7: the home store is priced by the same model, so the plan does not claim the bundle as a
    # saving against a home store that offers the same deal.
    assert D(m["single"]["breakdown"]["basket_saving"]) == 0
    assert D(m["minimum_effort"]["total"]) == D("16.00")


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_db_add_one_more_is_a_suggestion(client, db, world: World) -> None:
    w = world
    ys = _add_product(db, w, "yog_s", "יוגורט תות", "t-c1", "5.00")
    add_promo(db, "t-c1", None, "Y9", [ys], "bundle", "9", min_qty="3", description="3 ב-9")
    precompute_effective_prices(db, chains=w.chains)
    items = [{"canonical_id": w.canon["yog_s"], "quantity": 2}]
    m = post(client, w, items=items, solver="milp")
    single = m["single"]
    assert D(single["total"]) == D("10.00")  # never silently buys a third
    assert single["promo_bundles"] == [
        {"promo_description": "3 ב-9", "bundle_count": 1, "saving": "1.00", "add_qty": "1"}
    ]
    assert single["stores"][0]["store"]["items"][0]["quantity"] == "2"


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_db_max_stores_and_min_split_saving(client, w: World) -> None:
    free = {"cost_per_km": "0", "extra_stop_value": "0"}
    one = post(client, w, solver="milp", max_stores=1, travel=free, min_split_saving="0")
    assert one["split"] is None and len(one["single"]["stores"]) == 1
    two = post(client, w, solver="milp", travel=free, min_split_saving="1",
               home_store_id=w.stores["home"])
    assert two["split"] is not None and len(two["split"]["stores"]) == 2
    saving = D(two["single"]["total"]) - D(two["split"]["total"])
    assert saving == D("2.00")
    assert post(client, w, solver="milp", travel=free, min_split_saving="2.01")["split"] is None
    three = post(client, w, solver="milp", max_stores=3, travel=free, min_split_saving="0")
    assert 2 <= len(three["split"]["stores"]) <= 3


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_db_solver_flag_round_trips(client, w: World) -> None:
    assert post(client, w)["solver"] == "heuristic"
    assert post(client, w, solver="heuristic")["solver"] == "heuristic"
    assert post(client, w, solver="milp")["solver"] == "milp"
    assert client.post("/optimize", json={"items": basket(w), "location": w.location,
                                          "solver": "cplex"}).status_code == 422


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_db_falls_back_to_the_heuristic(client, w: World, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a, **_k):
        raise milp.SolverUnavailable("no solver")

    monkeypatch.setattr(milp, "solve", boom)
    assert post(client, w, solver="milp")["solver"] == "heuristic"


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_db_missing_items_and_empty_radius(client, w: World) -> None:
    items = basket(w) + [{"canonical_id": w.canon["wafer"], "quantity": 1}]
    assert post(client, w, items=items, solver="milp")["single"]["missing"] == [w.canon["wafer"]]
    r = client.post("/optimize", json={"items": basket(w), "solver": "milp",
                                       "location": {"lon": 35.5, "lat": 33.2, "radius_m": 1000}})
    resp = r.json()
    assert resp["single"]["stores"] == [] and len(resp["single"]["missing"]) == 5
