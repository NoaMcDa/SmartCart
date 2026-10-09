"""MILP cart optimizer (issue #13, docs/architecture.md section 5, decision D9 phase 2).

The phase 1 heuristic (routes/optimize.py) prices every line on its own, so a promo can only be
completed with units of that same line. This model buys the same lines but lets units of several
lines at one store fill the bundles of one promo ("any 3 for 20", "buy 2 get 1" over a group of
items), and it counts bundles in whole units (quantity rounding). See docs/optimizer.md.

Inputs are exactly what the heuristic uses: the candidate stores, the per-store priced lines from
``basket.price_baskets`` (one product per need and store, club deals already gated there), the
travel cost per store and the value of an extra stop. The only extra read is the promo row behind
a line's promo (to know which lines share it), identified from the line itself.

Formulation, in integer agorot (docs/optimizer.md has the full statement):

* ``w[T]`` binary: the visited store set is ``T`` (every set of 1 to K of the N candidates, in
  the heuristic's order; N = 10, K = 2 gives 55). ``y[s] = sum of w[T] over T containing s``.
* Needs that cannot share a promo with another line of the same store are bought at the cheapest
  store of the set (ties: nearer). Their cost for each set is a constant, so they need no
  variables: this is the heuristic's assignment, exact for them.
* Needs that can share a promo keep ``x[i,p,s]`` binary (buy product ``p`` for need ``i`` at
  ``s``; ``p`` is the line basket.py priced), with ``b[k]`` integer bundles of promo ``k`` at its
  store and ``u[k,i]`` integer units of need ``i`` counted into them.
* Minimize ``W x cost + M x missing + tie-breaks``: cost = set constant (cheapest lines, travel
  and delivery fee per store, extra-stop value per store beyond the first) + sum line cost x
  ``x`` + sum (bundle price x ``b`` - shelf price x ``u``). ``M`` outweighs any basket, so fewer
  missing needs always win (the heuristic's ranking). The tie-breaks (fewer substitutes, then
  the heuristic's set order) stay below one agora.
* Constraints: exactly one set; ``x <= y``; a need with ``x`` is bought exactly when a store of
  the set sells it (never ignored, never double-bought); it goes to its cheapest visited store
  unless it joins a promo there; ``sum_i u[k,i] = N_k x b[k]``; ``u[k,i] <= q_i x x[i,p,s]``;
  ``sum_i u[k,i] <= max_qty_k`` when the promo has a quantity limit; with ``min_stores >= 2``
  every visited store sells something.

The solver is OR-Tools CP-SAT (exact integer arithmetic, a 2 s limit, a fixed seed and one
worker, so the answer is deterministic). The heuristic's plan is passed as a hint.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from itertools import combinations

import psycopg

from smartcart_api import schemas
from smartcart_api.basket import ZERO, StoreBasket, StoreInfo, money
from smartcart_api.precompute import PromoTerms, fold_promo

try:  # the API must still start (heuristic only) if the wheel is missing on a platform
    from ortools.sat.python import cp_model
except ImportError:  # pragma: no cover
    cp_model = None

TIME_LIMIT_S = 2.0
SEED = 0
WORKERS = 1  # deterministic; the models are small (measured in docs/optimizer.md)


class SolverUnavailable(RuntimeError):
    """OR-Tools is not installed, or the solver returned no answer within the time limit."""


def agorot(d: Decimal) -> int:
    return int((d * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _ils(a: int) -> Decimal:
    return money(Decimal(a) / 100)


# --- the model's data ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    """One priced (need, product, store): basket.py's line for that canonical at that store."""

    canonical_id: int
    store_id: int
    item_id: int
    line_total: Decimal  # basket.py's total for the requested quantity (its own promo folded in)
    shelf_price: Decimal
    quantity: int | None  # whole packs when the line can join promo bundles, else None
    group: str | None = None  # promo group key when the line can join bundles
    is_substitute: bool = False


@dataclass(frozen=True)
class Group:
    """One promo at one store. A bundle of ``size`` units costs ``fixed`` + sum ``unit`` of its
    units; units outside bundles pay the shelf price."""

    key: str
    store_id: int
    description: str
    size: int
    fixed: Decimal
    unit: dict[int, Decimal]  # canonical_id -> cost of one unit inside a bundle (besides fixed)
    max_units: int | None = None


@dataclass(frozen=True)
class StoreCost:
    store_id: int
    trip: Decimal  # travel + delivery fee for visiting the store
    rank: int  # distance order, 0 = nearest (tie-break only)


@dataclass
class Problem:
    canonical_ids: list[int]
    stores: list[StoreCost]
    lines: list[Line]  # lines of these stores only
    groups: dict[str, Group]
    extra_stop_value: Decimal = ZERO


@dataclass
class BundleUse:
    key: str
    description: str
    count: int
    saving: Decimal  # shelf price of the units in the bundles minus what the bundles cost
    add_qty: int | None = None  # set on a suggestion, which is never applied


@dataclass
class Solution:
    status: str  # "optimal" or "feasible" (time limit reached with a solution)
    assignment: dict[int, int]  # canonical_id -> store_id
    missing: list[int]
    line_totals: dict[int, Decimal]  # canonical_id -> line total in this plan
    units_in_bundles: dict[int, int]  # canonical_id -> units counted into bundles
    bundles: list[BundleUse]
    suggestions: list[BundleUse]
    basket_total: Decimal
    travel_cost: Decimal
    extra_stop_cost: Decimal
    seconds: float
    objective: int = 0
    store_set: tuple[int, ...] = ()  # the chosen store set (y = 1)

    @property
    def used(self) -> tuple[int, ...]:
        return tuple(sorted(set(self.assignment.values())))

    @property
    def cost(self) -> Decimal:
        return self.basket_total + self.travel_cost + self.extra_stop_cost


# --- reading the lines and their promos --------------------------------------------------------

_PROMOS_SQL = """
SELECT p.id, p.store_id, p.description, p.club_only, p.club_name, p.min_qty, p.reward_type,
       p.reward_value, p.max_qty, p.chain_id, pi.item_id
FROM promos AS p
JOIN promo_items AS pi ON pi.promo_id = p.id
LEFT JOIN file_tracking AS f ON f.id = p.file_id
WHERE pi.item_id = ANY(%(items)s)
  AND (p.starts_at IS NULL OR p.starts_at <= %(as_of)s)
  AND (p.ends_at IS NULL OR p.ends_at > %(as_of)s)
  AND (p.file_id IS NULL OR f.status = 'loaded')
ORDER BY p.id
"""


@dataclass(frozen=True)
class _PromoRow:
    terms: PromoTerms
    max_qty: Decimal | None
    chain_id: str


def _bundle_price(li: schemas.PricedItem, n: int, q: int) -> Decimal | None:
    """The price of one full bundle, read back from basket.py's line (so the MILP charges exactly
    what /compare charges for a line on its own)."""
    full = q // n
    rest = q - full * n
    if full > 0:
        return (li.line_total - rest * li.shelf_price) / full
    if li.promo_add_saving is not None:  # q < n: basket.py priced q + add = n units
        return n * li.shelf_price - li.promo_add_saving
    return None


def priced_lines(
    conn: psycopg.Connection,
    baskets: dict[int, StoreBasket],
    as_of: datetime | None = None,
) -> tuple[dict[int, list[Line]], dict[str, Group]]:
    """store_id -> lines, and the promo groups those lines can fill.

    A line joins a group when its promo needs several units (``promo_min_qty > 1``), it is
    counted in whole packs, and the promo row behind it is found (same item, store or chain-wide,
    active, from a loaded file, same description, same club flag, same quantity). Lines at one
    store with the same promo share the group. Everything else keeps basket.py's line total.
    """
    as_of = as_of or datetime.now(UTC)
    kg = _weighed(conn, {cid for b in baskets.values() for cid in b.lines})
    want = [
        li.item_id
        for b in baskets.values()
        for li in b.lines.values()
        if li.promo_min_qty is not None and li.promo_min_qty > 1 and li.promo_description
    ]
    rows: dict[int, list[_PromoRow]] = defaultdict(list)
    if want:
        for r in conn.execute(_PROMOS_SQL, {"items": sorted(set(want)), "as_of": as_of}):
            rows[r[10]].append(_PromoRow(PromoTerms(*r[:8]), r[8], r[9]))

    out: dict[int, list[Line]] = {}
    members: dict[str, list[tuple[Line, Decimal, _PromoRow | None]]] = defaultdict(list)
    names: dict[str, str] = {}
    for sid, basket in baskets.items():
        lines = []
        for cid, li in basket.lines.items():
            line = Line(
                cid, sid, li.item_id, li.line_total, li.shelf_price, None, None, li.is_substitute
            )
            joined = _join(li, cid in kg, basket.info, rows.get(li.item_id, []))
            if joined is not None:
                n, q, price, row = joined
                key = f"{row.terms.id if row else 'item' + str(li.item_id)}@{sid}/{n}"
                line = Line(
                    cid, sid, li.item_id, li.line_total, li.shelf_price, q, key, li.is_substitute
                )
                members[key].append((line, price, row))
                names.setdefault(key, li.promo_description or "")
            lines.append(line)
        out[sid] = lines

    groups: dict[str, Group] = {}
    for key, mem in members.items():
        n = int(key.rsplit("/", 1)[1])
        row = mem[0][2]
        prices = {line.canonical_id: price for line, price, _ in mem}
        if len(set(prices.values())) == 1:
            fixed, unit = next(iter(prices.values())), dict.fromkeys(prices, ZERO)
        elif row is not None and row.terms.reward_type == "buy_x_get_y":
            # Mixed prices: the store gives the cheapest units free. Counting the cheapest shelf
            # price of the group never overstates the discount.
            y = (
                row.terms.reward_value
                if row.terms.reward_value and row.terms.reward_value > 0
                else 1
            )
            cheapest = min(line.shelf_price for line, _, _ in mem)
            fixed = -(Decimal(y) * cheapest)
            unit = {line.canonical_id: line.shelf_price for line, _, _ in mem}
        else:  # per-unit promo prices (percent, a price per unit): each unit at its own price
            fixed, unit = ZERO, {c: p / n for c, p in prices.items()}
        max_units = None
        if row is not None and row.max_qty is not None and row.max_qty > 0:
            max_units = int(row.max_qty)
        groups[key] = Group(key, mem[0][0].store_id, names[key], n, fixed, unit, max_units)
    return out, groups


def _join(
    li: schemas.PricedItem, by_weight: bool, store: StoreInfo, rows: list[_PromoRow]
) -> tuple[int, int, Decimal, _PromoRow | None] | None:
    need = li.promo_min_qty
    if by_weight or need is None or need <= 1 or need != need.to_integral_value():
        return None
    if li.quantity != li.quantity.to_integral_value():
        return None
    n, q = int(need), int(li.quantity)
    price = _bundle_price(li, n, q)
    if price is None or price >= n * li.shelf_price:
        return None
    for row in rows:
        t = row.terms
        if row.chain_id != store.chain_id or (
            t.store_id is not None and t.store_id != store.store_id
        ):
            continue
        if t.description != li.promo_description or t.club_only != li.club_required:
            continue
        if t.club_only and t.club_name != li.club_name:
            continue
        folded = fold_promo(li.shelf_price, t)
        if folded is not None and folded[1] == need:
            return n, q, price, row
    return n, q, price, None  # promo row not found: the line still rounds to whole bundles alone


def _weighed(conn: psycopg.Connection, canonical_ids: set[int]) -> set[int]:
    if not canonical_ids:
        return set()
    return {
        r[0]
        for r in conn.execute(
            "SELECT id FROM canonical_products WHERE id = ANY(%s) AND base_unit = 'kg'",
            (sorted(canonical_ids),),
        )
    }


# --- group cost, exact ---------------------------------------------------------------------------


def group_cost(
    group: Group, quantities: dict[int, int], shelf: dict[int, Decimal]
) -> tuple[int, int]:
    """(cost in agorot, bundles) of buying ``quantities`` (canonical_id -> units) under ``group``
    at its best: for b bundles the N x b units with the largest discount go in."""
    gain: list[int] = []
    base = 0
    for cid, q in quantities.items():
        s = agorot(shelf[cid])
        base += s * q
        gain += [s - agorot(group.unit[cid])] * q
    gain.sort(reverse=True)
    best, best_b, acc = base, 0, 0
    fixed = agorot(group.fixed)
    for b in range(1, len(gain) // group.size + 1):
        if group.max_units is not None and b * group.size > group.max_units:
            break
        acc += sum(gain[(b - 1) * group.size : b * group.size])
        cost = base - acc + fixed * b
        if cost < best:
            best, best_b = cost, b
    return best, best_b


# --- the solver ----------------------------------------------------------------------------------


def store_sets(store_ids: list[int], max_stores: int, min_stores: int = 1) -> list[tuple[int, ...]]:
    """Every set of ``min_stores`` to ``max_stores`` stores, in the heuristic's order (size, then
    distance rank): N = 10, K = 2 gives 55 sets; the API's limits (N = 15, K = 3) give 575."""
    out: list[tuple[int, ...]] = []
    for k in range(max(1, min_stores), min(max_stores, len(store_ids)) + 1):
        out += combinations(store_ids, k)
    return out


def solve(
    problem: Problem,
    max_stores: int,
    min_stores: int = 1,
    hint: dict[int, int] | None = None,
    time_limit: float = TIME_LIMIT_S,
    seed: int = SEED,
) -> Solution | None:
    """The cheapest plan visiting ``min_stores`` to ``max_stores`` stores (fewest missing needs
    first, then cost), or None when there is no such plan. Raises SolverUnavailable when the
    solver is missing or finds no answer in time."""
    if cp_model is None:
        raise SolverUnavailable("ortools is not installed")
    started = time.perf_counter()
    store_ids = [s.store_id for s in problem.stores]
    sets = store_sets(store_ids, max_stores, min_stores)
    if not sets:
        return None
    lines = [li for li in problem.lines if li.store_id in set(store_ids)]
    needs = list(problem.canonical_ids)

    # A promo that only one line of the store can fill is that line's own business: its cost is
    # fixed (whole bundles, then shelf price). Groups of two or more lines get b and u variables.
    size: dict[str, int] = defaultdict(int)
    for li in lines:
        if li.group is not None:
            size[li.group] += 1
    modelled = {key for key, n in size.items() if n >= 2}
    line_of = {(li.canonical_id, li.item_id, li.store_id): li for li in lines}
    own: dict[tuple[int, int, int], int] = {}
    for k, li in line_of.items():
        if li.group in modelled:
            own[k] = agorot(li.shelf_price) * (li.quantity or 0)  # bundles are counted apart
        elif li.group is not None:
            own[k] = group_cost(
                problem.groups[li.group], {k[0]: li.quantity or 0}, {k[0]: li.shelf_price}
            )[0]
        else:
            own[k] = agorot(li.line_total)

    # Objective weights. Tie-breaks (fewer substitutes, then the heuristic's set order) together
    # stay below one agora; one missing need outweighs any cost.
    sub_pen = len(sets) + 1
    tie_max = sub_pen * len(needs) + len(sets)  # every tie-break term together stays below this
    weight = 2 * (tie_max + 1)
    worst: dict[int, int] = defaultdict(int)
    for k, c in own.items():
        worst[k[0]] = max(worst[k[0]], c)
    trips = {s.store_id: s.trip for s in problem.stores}
    big_m = weight * (
        sum(worst.values())
        + sum(agorot(t) for t in trips.values())
        + agorot(problem.extra_stop_value) * max_stores
        + 1
    )
    rank = {s.store_id: s.rank for s in problem.stores}
    coef = {k: weight * own[k] + (sub_pen if line_of[k].is_substitute else 0) for k in line_of}
    per_need: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
    for k in line_of:
        per_need[k[0]].append(k)
    for ks in per_need.values():
        ks.sort(key=lambda k: (coef[k], rank[k[2]], k[2]))
    x_set = {c for c in needs if any(line_of[k].group in modelled for k in per_need.get(c, []))}
    x_needs = [c for c in needs if c in x_set]
    z_needs = [c for c in needs if c not in x_set]

    # Needs outside shared promos go to the cheapest store of the chosen set (ties: nearer), so
    # their cost for a store set is a constant, the sum of the per-need minimum. The low 6 bits
    # carry the distance rank so that min() also breaks ties the heuristic's way.
    inf = 1 << 62
    col = {s: [inf] * len(z_needs) for s in store_ids}
    for j, c in enumerate(z_needs):
        for k in per_need.get(c, []):
            col[k[2]][j] = (coef[k] << 6) + min(rank[k[2]], 63)
    stocks: dict[int, set[int]] = defaultdict(set)
    for k in line_of:
        stocks[k[2]].add(k[0])

    m = cp_model.CpModel()
    w = [m.new_bool_var(f"w_{n}") for n in range(len(sets))]
    m.add_exactly_one(w)
    terms: list = []
    coefs: list[int] = []
    unused_by_z: dict[int, list] = defaultdict(list)  # store -> sets in which no z-need goes there
    for n, t in enumerate(sets):
        best = list(map(min, *(col[s] for s in t))) if len(t) > 1 else col[t[0]]
        found = [v for v in best if v < inf]
        covered = set().union(*(stocks[s] for s in t))
        missing = len(z_needs) - len(found) + sum(1 for c in x_needs if c not in covered)
        set_cost = (
            sum(v >> 6 for v in found)
            + weight
            * (sum(agorot(trips[s]) for s in t) + agorot(problem.extra_stop_value) * (len(t) - 1))
            + big_m * missing
            + n  # the heuristic's order among equal sets
        )
        terms.append(w[n])
        coefs.append(set_cost)
        if min_stores >= 2:
            used = {_argmin_store(t, col, j) for j, v in enumerate(best) if v < inf}
            for s in t:
                if s not in used:
                    unused_by_z[s].append(w[n])

    y = {}
    for s in store_ids:
        v = m.new_bool_var(f"y_{s}")
        m.add(v == sum(w[n] for n, t in enumerate(sets) if s in t))
        y[s] = v

    # Needs that can share a promo bundle: x[i,p,s].
    x: dict[tuple[int, int, int], cp_model.IntVar] = {}
    by_store: dict[int, list] = defaultdict(list)
    for c in x_needs:
        ks = per_need[c]
        xs = []
        for k in ks:
            v = m.new_bool_var(f"x_{k[0]}_{k[1]}_{k[2]}")
            x[k] = v
            xs.append(v)
            by_store[k[2]].append(v)
            m.add_implication(v, y[k[2]])
            terms.append(v)
            coefs.append(coef[k])
        # Bought exactly when a store of the set sells it (the set fixes which needs are missing).
        sellers = {k[2] for k in ks}
        m.add(sum(xs) == sum(w[n] for n, t in enumerate(sets) if sellers & set(t)))
        # Cheapest visited store, unless the need joins a shared promo there.
        in_group = [x[k] for k in ks if line_of[k].group in modelled]
        plain = [k for k in ks if line_of[k].group not in modelled]
        for j, k in enumerate(plain):
            m.add(sum(x[q] for q in plain[: j + 1]) + sum(in_group) >= y[k[2]])
    if min_stores >= 2:  # visiting a store means buying something there
        for s, ws in unused_by_z.items():
            m.add(sum(ws) <= sum(by_store.get(s, [])))

    # Promo bundles.
    b_var: dict[str, cp_model.IntVar] = {}
    u_var: dict[tuple[str, tuple[int, int, int]], cp_model.IntVar] = {}
    grouped: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    for k in x:
        if line_of[k].group in modelled:
            grouped[line_of[k].group].append(k)
    for key, ks in grouped.items():
        g = problem.groups[key]
        total = sum(line_of[k].quantity or 0 for k in ks)
        cap = total if g.max_units is None else min(total, g.max_units)
        b = m.new_int_var(0, cap // g.size, f"b_{key}")
        b_var[key] = b
        us = []
        for k in ks:
            li = line_of[k]
            u = m.new_int_var(0, li.quantity or 0, f"u_{key}_{k[0]}")
            m.add(u <= (li.quantity or 0) * x[k])
            u_var[(key, k)] = u
            us.append(u)
            terms.append(u)
            coefs.append(weight * (agorot(g.unit[li.canonical_id]) - agorot(li.shelf_price)))
        m.add(sum(us) == g.size * b)
        if g.max_units is not None:
            m.add(sum(us) <= g.max_units)
        terms.append(b)
        coefs.append(weight * agorot(g.fixed))
    m.minimize(cp_model.LinearExpr.weighted_sum(terms, coefs))

    if hint:
        target = tuple(s for s in store_ids if s in set(hint.values()))
        for n, t in enumerate(sets):
            m.add_hint(w[n], t == target)
        for (c, _i, s), v in x.items():
            m.add_hint(v, hint.get(c) == s)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.random_seed = seed
    solver.parameters.num_workers = WORKERS
    solver.parameters.linearization_level = 2  # full LP relaxation: much faster proofs here
    # Stop once the cost is proven optimal to the agora; only the tie-break may remain unproven.
    solver.parameters.absolute_gap_limit = weight - tie_max - 1
    status = solver.solve(m)
    if status == cp_model.INFEASIBLE:
        return None
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise SolverUnavailable(f"CP-SAT status {solver.status_name(status)}")

    chosen_set = next(t for n, t in enumerate(sets) if solver.boolean_value(w[n]))
    assignment: dict[int, int] = {}
    chosen: dict[int, Line] = {}
    for k, v in x.items():
        if solver.boolean_value(v):
            assignment[k[0]], chosen[k[0]] = k[2], line_of[k]
    for j, c in enumerate(z_needs):
        if min(col[s][j] for s in chosen_set) < inf:
            s = _argmin_store(chosen_set, col, j)
            k = next(k for k in per_need[c] if k[2] == s)
            assignment[c], chosen[c] = s, line_of[k]
    units = {
        k[0]: int(solver.value(u)) for (_key, k), u in u_var.items() if assignment.get(k[0]) == k[2]
    }
    counts = {key: int(solver.value(b)) for key, b in b_var.items()}
    for cid, li in chosen.items():
        if li.group is not None and li.group not in modelled:
            g = problem.groups[li.group]
            _cost, n = group_cost(g, {cid: li.quantity or 0}, {cid: li.shelf_price})
            units[cid], counts[li.group] = n * g.size, n
    line_totals, bundles = _report(problem.groups, chosen, units, counts)
    used = sorted(set(assignment.values()))
    return Solution(
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
        assignment=assignment,
        missing=[c for c in needs if c not in assignment],
        line_totals=line_totals,
        units_in_bundles=units,
        bundles=bundles,
        suggestions=suggest_additions(problem.groups, chosen),
        basket_total=money(sum(line_totals.values(), ZERO)),
        travel_cost=money(sum((trips[s] for s in used), ZERO)),
        extra_stop_cost=money(problem.extra_stop_value * max(0, len(used) - 1)),
        seconds=time.perf_counter() - started,
        objective=int(solver.objective_value),
        store_set=chosen_set,
    )


def _argmin_store(t: tuple[int, ...], col: dict[int, list[int]], j: int) -> int:
    return min(t, key=lambda s: (col[s][j], s))


def _report(
    groups: dict[str, Group], chosen: dict[int, Line], units: dict[int, int], b: dict[str, int]
) -> tuple[dict[int, Decimal], list[BundleUse]]:
    """Line totals and applied bundles of a solution, in exact ILS.

    A line outside any group keeps basket.py's total. Inside a group each line pays the shelf
    price for its units outside bundles, its own unit cost for units inside, and its share of the
    bundles' fixed price; the rounding remainder goes to the group's last line, so the lines of a
    group add up to the group's cost.
    """
    totals: dict[int, Decimal] = {}
    members: dict[str, list[Line]] = defaultdict(list)
    for cid, li in chosen.items():
        if li.group is None:
            totals[cid] = li.line_total
        else:
            members[li.group].append(li)
    used: list[BundleUse] = []
    for key, mem in members.items():
        g = groups[key]
        count = b.get(key, 0)
        exact = g.fixed * count
        shelf_value = ZERO
        for li in mem:
            u = units.get(li.canonical_id, 0)
            q = li.quantity or 0
            share = li.shelf_price * (q - u) + g.unit[li.canonical_id] * u + g.fixed * u / g.size
            totals[li.canonical_id] = money(share)
            exact += li.shelf_price * (q - u) + g.unit[li.canonical_id] * u
            shelf_value += li.shelf_price * u
        last = max(
            (li for li in mem if units.get(li.canonical_id, 0)),
            default=mem[-1],
            key=lambda li: li.canonical_id,
        )
        totals[last.canonical_id] += money(exact) - sum(
            (totals[li.canonical_id] for li in mem), ZERO
        )
        if count:
            in_bundles = g.fixed * count + sum(
                (g.unit[li.canonical_id] * units.get(li.canonical_id, 0) for li in mem), ZERO
            )
            used.append(BundleUse(key, g.description, count, money(shelf_value - in_bundles)))
    used.sort(key=lambda u: (-u.saving, u.key))
    return totals, used


def suggest_additions(groups: dict[str, Group], chosen: dict[int, Line]) -> list[BundleUse]:
    """ "Add N and save X": for each promo group in the plan, the smallest addition to one of its
    lines that lowers the group's total cost (the extra units' price included). Only strictly
    positive savings are returned; the plan itself never changes."""
    members: dict[str, list[Line]] = defaultdict(list)
    for li in chosen.values():
        if li.group is not None:
            members[li.group].append(li)
    out = []
    for key, mem in members.items():
        g = groups[key]
        qty = {li.canonical_id: li.quantity or 0 for li in mem}
        shelf = {li.canonical_id: li.shelf_price for li in mem}
        now, _ = group_cost(g, qty, shelf)
        best: tuple[int, int, int] | None = None  # (-saving, add, bundles after)
        for li in mem:
            for add in range(1, g.size):
                more = dict(qty)
                more[li.canonical_id] += add
                cost, count = group_cost(g, more, shelf)
                if now - cost > 0 and count > 0:
                    cand = (-(now - cost), add, count)
                    if best is None or cand < best:
                        best = cand
                    break
        if best is not None:
            out.append(BundleUse(key, g.description, best[2], _ils(-best[0]), add_qty=best[1]))
    out.sort(key=lambda u: (-u.saving, u.key))
    return out


def promo_bundles(sol: Solution) -> list[schemas.PromoBundle]:
    """Applied bundles first (``add_qty`` null), then suggestions (``add_qty`` set, not applied)."""
    out = [
        schemas.PromoBundle(promo_description=u.description, bundle_count=u.count, saving=u.saving)
        for u in sol.bundles
        if u.count >= 1
    ]
    out += [
        schemas.PromoBundle(
            promo_description=u.description,
            bundle_count=u.count,
            saving=u.saving,
            add_qty=Decimal(u.add_qty),
        )
        for u in sol.suggestions
    ]
    return out


# --- benchmark -----------------------------------------------------------------------------------


@dataclass
class BenchResult:
    items: int
    stores: int
    seconds: list[float] = field(default_factory=list)


def synthetic_problem(
    n_items: int = 40,
    n_stores: int = 10,
    seed: int = 7,
    dispersion: str = "chains",
    shared_every: int = 7,
) -> Problem:
    """A random basket over ``n_stores`` stores for the benchmark and tests.

    ``dispersion="chains"`` (the default) looks like the transparency files: four chains, a base
    price per product, a chain price level per product within +-15 %, store exceptions on 10 % of
    lines, 5 % of products not stocked by a chain and 2 % missing at a store. ``"random"`` draws
    every store's price independently between 3 and 25 ILS, a stress case with no structure.
    Every ``shared_every``-th need joins a "3 for 20" promo shared by several products, every
    fifth a 1+1 of its own.
    """
    import random

    rnd = random.Random(seed)
    n_chains = 4
    stores = [StoreCost(s, Decimal(rnd.randint(100, 900)) / 100, s) for s in range(n_stores)]
    base = {c: rnd.randint(300, 2500) for c in range(1, n_items + 1)}
    qty = {c: rnd.choice((1, 1, 1, 2, 2, 3)) for c in base}
    level = {(ch, c): rnd.uniform(0.85, 1.15) for ch in range(n_chains) for c in base}
    stocked = {(ch, c): rnd.random() >= 0.05 for ch in range(n_chains) for c in base}
    sub = {(ch, c): rnd.random() < 0.1 for ch in range(n_chains) for c in base}
    lines: list[Line] = []
    groups: dict[str, Group] = {}
    for s in stores:
        ch = s.store_id % n_chains
        mix = f"mix@{s.store_id}"
        groups[mix] = Group(mix, s.store_id, "3 ב-20", 3, Decimal(20), {}, None)
        for c in base:
            if dispersion == "random":
                if rnd.random() < 0.05:
                    continue
                agora = rnd.randint(300, 2500)
            else:
                if not stocked[(ch, c)] or rnd.random() < 0.02:
                    continue
                agora = base[c] * level[(ch, c)]
                if rnd.random() < 0.1:
                    agora *= rnd.uniform(0.9, 1.1)
            shelf = Decimal(round(agora)) / 100
            q = qty[c]
            key = None
            if c % shared_every == 0:
                key = mix
                groups[mix].unit[c] = ZERO
            elif c % 5 == 0:
                key = f"one{c}@{s.store_id}"
                groups[key] = Group(key, s.store_id, "1+1", 2, shelf, {c: ZERO}, None)
            total = shelf * q
            if key is not None:
                total = _ils(group_cost(groups[key], {c: q}, {c: shelf})[0])
            lines.append(
                Line(
                    c,
                    s.store_id,
                    c * 1000 + s.store_id,
                    money(total),
                    shelf,
                    q if key else None,
                    key,
                    sub[(ch, c)],
                )
            )
    return Problem(list(base), stores, lines, groups, Decimal(10))


def bench(
    runs: int = 10,
    n_items: int = 40,
    n_stores: int = 10,
    max_stores: int = 2,
    dispersion: str = "chains",
) -> BenchResult:
    """Time the two solves /optimize makes over the candidates: one store, then up to K."""
    res = BenchResult(n_items, n_stores)
    for r in range(runs):
        p = synthetic_problem(n_items, n_stores, seed=r, dispersion=dispersion)
        for k in (1, max_stores):
            t = time.perf_counter()
            solve(p, k)
            res.seconds.append(time.perf_counter() - t)
    return res


if __name__ == "__main__":  # uv run python -m smartcart_api.milp
    for disp in ("chains", "random"):
        for k in (2, 3):
            r = bench(max_stores=k, dispersion=disp)
            t = sorted(r.seconds)
            print(
                f"{r.items} items x {r.stores} stores, K={k}, {disp}: {len(t)} solves,"
                f" median {t[len(t) // 2] * 1000:.1f} ms, max {t[-1] * 1000:.1f} ms"
            )
