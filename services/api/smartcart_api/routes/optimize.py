"""POST /optimize (issue #62): single store, split, minimum effort (D9 phase 1 heuristic).

1. The ``candidate_stores`` nearest stores in the radius (N = 10 by default; online only with
   ``include_online``) are priced with the same rules as /compare.
2. Every subset of 1 to ``max_stores`` of them is evaluated (N = 10, K = 2: 10 + 45 = 55). In a
   subset each canonical goes to the store with its lowest line total; the stores that get at
   least one item are the ones visited.
3. Cost of a subset = basket total + travel + extra stops, where travel is
   ``2 x distance_km x cost_per_km`` per visited store by car, a flat
   ``API_WALK_TRANSIT_COST_PER_STORE`` per store on foot or by public transport (an estimate,
   11 ILS: two single fares), and 0 for delivery (delivery fees are a placeholder 0 in phase 1);
   extra stops = ``extra_stop_value x (visited stores - 1)``. Subsets are ranked by missing
   items first, then cost. Without cross-item promos the best subset is the exact optimum over
   all assignments (tested against an exhaustive reference).
4. ``single`` is the best one-store subset. ``split`` is the best subset that visits two or more
   stores, returned only when it misses no more items than ``single`` and its cost is lower by at
   least ``min_split_saving``. ``minimum_effort`` is the home store itself.

Savings (D7): only versus the home store, never versus the most expensive store or chain.
``basket_saving`` is the home total minus the plan's total over the canonicals both supply;
``travel_cost`` is the plan's travel minus the home store's travel, floored at 0 (a plan is never
credited with a travel saving); ``net_saving = basket_saving - travel_cost - extra_stop_cost``.
Without a home store ``breakdown`` and ``minimum_effort`` are null.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from itertools import combinations
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends

from smartcart_api import schemas
from smartcart_api.basket import (
    ZERO,
    StoreBasket,
    StoreInfo,
    money,
    price_baskets,
    store_info,
    stores_in_radius,
)
from smartcart_api.db import get_conn
from smartcart_api.settings import get_settings

router = APIRouter()

SPEED_KMH = {"car": 30, "walk_transit": 12, "delivery": None}  # estimates for extra_minutes
MINUTES_PER_EXTRA_STOP = 10  # estimate: parking, checkout


@dataclass
class SubsetEval:
    stores: tuple[int, ...]  # the subset
    assignment: dict[int, int]  # canonical_id -> store_id
    basket_total: Decimal
    missing: list[int]
    travel_cost: Decimal
    extra_stop_cost: Decimal

    @property
    def used(self) -> tuple[int, ...]:
        return tuple(sorted(set(self.assignment.values())))

    @property
    def cost(self) -> Decimal:
        return self.basket_total + self.travel_cost + self.extra_stop_cost

    def key(self) -> tuple:
        return (len(self.missing), self.cost, len(self.used), self.stores)


def travel_cost(info: StoreInfo, travel: schemas.TravelSettings) -> Decimal:
    if travel.mode == "car":
        return money(Decimal(info.distance_m) / 1000 * travel.cost_per_km * 2)
    if travel.mode == "walk_transit":
        return money(get_settings().walk_transit_cost_per_store)
    return ZERO  # delivery: no travel; the delivery fee is a phase 1 placeholder of 0


def _minutes(info: StoreInfo, mode: str) -> float:
    speed = SPEED_KMH.get(mode)
    return 0.0 if not speed else 2 * info.distance_m / 1000 / speed * 60


def evaluate_subsets(
    candidates: list[StoreInfo],
    baskets: dict[int, StoreBasket],
    canonical_ids: list[int],
    max_stores: int,
    travel: schemas.TravelSettings,
) -> list[SubsetEval]:
    """Every subset of 1..max_stores candidates, each with its greedy (per-item cheapest) plan."""
    info = {s.store_id: s for s in candidates}
    trip = {sid: travel_cost(s, travel) for sid, s in info.items()}
    ids = [s.store_id for s in candidates]
    out: list[SubsetEval] = []
    for k in range(1, min(max_stores, len(ids)) + 1):
        for subset in combinations(ids, k):
            assignment: dict[int, int] = {}
            total = ZERO
            missing = []
            for cid in canonical_ids:
                best: tuple[Decimal, int, int] | None = None
                for sid in subset:
                    line = baskets[sid].lines.get(cid)
                    if line is not None:
                        cand = (line.line_total, info[sid].distance_m, sid)
                        if best is None or cand < best:
                            best = cand
                if best is None:
                    missing.append(cid)
                else:
                    assignment[cid] = best[2]
                    total += best[0]
            used = set(assignment.values())
            out.append(
                SubsetEval(
                    stores=subset,
                    assignment=assignment,
                    basket_total=money(total),
                    missing=missing,
                    travel_cost=money(sum((trip[s] for s in used), ZERO)),
                    extra_stop_cost=money(travel.extra_stop_value * max(0, len(used) - 1)),
                )
            )
    return out


def _plan(
    kind: str,
    ev: SubsetEval,
    baskets: dict[int, StoreBasket],
    info: dict[int, StoreInfo],
    home: StoreBasket | None,
    travel: schemas.TravelSettings,
    recommended: bool,
) -> schemas.Plan:
    assignments = []
    for sid in ev.used or ev.stores[:1]:
        cids = {c for c, s in ev.assignment.items() if s == sid}
        result = baskets[sid].result(home, only=cids)
        assignments.append(
            schemas.StoreAssignment(store=result, item_ids=[li.item_id for li in result.items])
        )
    lines = {c: baskets[s].lines[c] for c, s in ev.assignment.items()}
    visited = [info[s] for s in ev.used]
    minutes = sum(_minutes(s, travel.mode) for s in visited)
    breakdown = None
    if home is not None:
        home_trip = travel_cost(home.info, travel)
        common = home.lines.keys() & lines.keys()
        basket_saving = money(
            sum((home.lines[c].line_total - lines[c].line_total for c in common), ZERO)
        )
        rel_travel = max(ZERO, ev.travel_cost - (home_trip if ev.used else ZERO))
        breakdown = schemas.SavingBreakdown(
            basket_saving=basket_saving,
            travel_cost=rel_travel,
            extra_stop_cost=ev.extra_stop_cost,
            net_saving=money(basket_saving - rel_travel - ev.extra_stop_cost),
        )
        minutes -= _minutes(home.info, travel.mode)
    extra_minutes = max(0, round(minutes)) + MINUTES_PER_EXTRA_STOP * max(0, len(ev.used) - 1)
    return schemas.Plan(
        kind=kind,
        stores=assignments,
        total=ev.basket_total,
        travel_cost=ev.travel_cost,
        extra_minutes=extra_minutes,
        breakdown=breakdown,
        recommended=recommended,
        missing=ev.missing,
        substituted_count=sum(1 for li in lines.values() if li.is_substitute),
    )


@router.post("/optimize", response_model=schemas.OptimizeResponse, tags=["basket"])
def optimize(
    body: schemas.OptimizeRequest,
    conn: Annotated[psycopg.Connection, Depends(get_conn)],
) -> schemas.OptimizeResponse:
    candidates = stores_in_radius(conn, body.location, body.include_online, body.candidate_stores)
    home_info = None
    if body.home_store_id is not None:
        home_info = next((s for s in candidates if s.store_id == body.home_store_id), None)
        if home_info is None:
            home_info = store_info(conn, body.home_store_id, body.location)
    priced_stores = candidates + ([home_info] if home_info and home_info not in candidates else [])
    baskets = price_baskets(conn, body.items, priced_stores, body.clubs)
    home = baskets.get(home_info.store_id) if home_info else None
    canonical_ids = list(dict.fromkeys(it.canonical_id for it in body.items))
    info = {s.store_id: s for s in priced_stores}

    evals = evaluate_subsets(candidates, baskets, canonical_ids, body.max_stores, body.travel)
    subsets_evaluated = len(evals)

    singles = [e for e in evals if len(e.stores) == 1]
    best_single = min(singles, key=SubsetEval.key) if singles else None
    splits = [e for e in evals if len(e.used) >= 2]
    best_split = min(splits, key=SubsetEval.key) if splits else None
    if best_split is not None and best_single is not None:
        good_enough = (
            len(best_split.missing) <= len(best_single.missing)
            and best_single.cost - best_split.cost >= body.min_split_saving
        )
        if not good_enough:
            best_split = None

    if best_single is not None:
        single = _plan("single", best_single, baskets, info, home, body.travel, best_split is None)
    else:  # nothing in the radius
        single = schemas.Plan(kind="single", stores=[], total=ZERO, recommended=False,
                              missing=canonical_ids)
    split = (
        _plan("split", best_split, baskets, info, home, body.travel, True) if best_split else None
    )
    minimum_effort = None
    if home is not None:
        home_eval = evaluate_subsets([home.info], {home.info.store_id: home}, canonical_ids, 1,
                                     body.travel)[0]
        minimum_effort = _plan("minimum_effort", home_eval, baskets, info, home, body.travel, False)
    return schemas.OptimizeResponse(
        single=single,
        split=split,
        minimum_effort=minimum_effort,
        subsets_evaluated=subsets_evaluated,
        generated_at=datetime.now(UTC),
    )
