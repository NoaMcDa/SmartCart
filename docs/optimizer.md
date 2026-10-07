# Cart optimizer: heuristic and MILP, smart-cart swaps

Issues #13 (MILP with cross-item promos and quantity rounding) and #45 (smart cart). Code:
`services/api/smartcart_api/milp.py`, `routes/optimize.py`, `swaps.py`, `routes/swaps.py`.
Tests: `services/api/tests/test_milp.py`, `test_swaps.py`, and the phase 1 `test_optimize.py`.
Background: `docs/architecture.md` sections 4 and 5, decisions D7 and D9.

## Which solver runs

`POST /optimize` takes `solver: "heuristic" | "milp"` (default `heuristic`).

| `solver` | What runs | `OptimizeResponse.solver` |
|---|---|---|
| `heuristic` (default) | the phase 1 subset enumeration, unchanged | `heuristic` |
| `milp` | the MILP below | `milp` |
| `milp`, OR-Tools missing or no answer within the time limit | the heuristic, with a warning in the log | `heuristic` |

The response says which one produced the plans, so a fallback is never hidden. Both share the
same pricing step (`_price` in `routes/optimize.py`: candidates, home store, `price_baskets`).
The heuristic path is the phase 1 code moved into `_optimize_heuristic` without changes; its tests
are untouched. The web app keeps the default until the MILP has run on real data.

## Inputs

Exactly what the heuristic uses:

- the `candidate_stores` nearest stores in the radius, in distance order, and the home store;
- per store, one priced line per canonical from `basket.price_baskets` (the product chosen at the
  requested flexibility level, club deals already gated there; the MILP never re-reads clubs);
- travel cost per store (`travel_cost`: car round trip, flat walk/transit fare, delivery 0; the
  delivery fee is still a placeholder 0) and `extra_stop_value`;
- `max_stores` (K) and `min_split_saving`.

The one extra read is the promo row behind each line's promo, to know which lines share it
(`milp.priced_lines`). A line joins a promo group when its promo needs several units
(`promo_min_qty > 1`), it is counted in whole packs (not by weight, integer quantity), and a promo
row with the same item, store or chain-wide scope, description, club flag and quantity is active
and comes from a loaded file. Lines of one store with the same promo row form one group. The
bundle price is read back from basket.py's own line total, so a line alone costs exactly what
/compare charges for it.

## Formulation as implemented

All money is in integer agorot.

**Store sets.** `w[T]` binary for every set `T` of 1 to K candidates, enumerated in the
heuristic's order (size, then distance): N = 10, K = 2 gives 55 sets, the API maximum (N = 15,
K = 3) gives 575. Exactly one is chosen. `y[s] = sum of w[T] over T containing s`.

**Needs outside shared promos** (most needs) are bought at the cheapest store of the chosen set
(ties: nearer store). Their cost for each set is a constant computed before the solve (the sum
of per-need minimums), so they need no variables. For them this is the heuristic's assignment.
A need with a promo of its own (1+1 on that product only) is in this class: its cost is whole
bundles at the bundle price plus the rest at the shelf price, with the promo's `max_qty` applied.

**Needs that can share a promo** with another line of the same store get:

- `x[i,p,s]` binary: buy product `p` for need `i` at store `s` (`p` is the line basket.py
  priced, so there is one `p` per need and store);
- `b[k]` integer: bundles of promo `k` at its store;
- `u[k,i]` integer: units of need `i` counted into those bundles.

**Objective.** Minimize `M x missing + W x cost + tie-breaks`, where

```
cost = sum over sets T  w[T] x (cheapest lines of the plain needs in T
                                + sum of travel and delivery fee over s in T
                                + extra_stop_value x (|T| - 1))
     + sum x[i,p,s] x shelf price x quantity
     + sum over promos k ( b[k] x bundle fixed price + sum_i u[k,i] x (unit price in bundle - shelf price) )
```

- `M` exceeds any basket, so fewer missing needs always win, as in the heuristic's ranking.
  Missing needs are counted, never dropped and never priced as zero.
- Tie-breaks: a substitution penalty (an exact or any-brand match wins a tie over a close
  substitute), then the heuristic's set order. Together they stay below one agora (`W`).

**Constraints.**

- exactly one store set;
- `x[i,p,s] <= y[s]` (buy only at visited stores);
- a shared-promo need is bought exactly once when a store of the set sells it, and not at all
  otherwise (so the set fixes the missing count);
- it goes to its cheapest visited store unless it joins a promo bundle there (`sum of x over the
  stores at least as cheap + x where it can join a bundle >= y[s]`): a store is never visited
  just to make up a split, the same plans the heuristic considers;
- `sum_i u[k,i] = N_k x b[k]`, `u[k,i] <= q_i x x[i,p,s]` (bundles only from what is bought, in
  whole units);
- `sum_i u[k,i] <= max_qty_k` when the promo row has a positive `max_qty`;
- with `min_stores >= 2` every store of the chosen set sells something (only used when a tie
  with the single-store plan must still produce a split, see below);
- club promos only for members: gated upstream in `price_baskets`, so a line the user cannot get
  never carries a club promo and never joins its group.

Quantities are never increased: the user's quantities are hard constraints. "Add N and save X"
is a suggestion only (below).

### Bundle prices in a shared group

| Group | A bundle costs |
|---|---|
| every line has the same bundle price (one product; or "3 for 20" / a unit price over several products) | that price, for any N units |
| buy X get Y over products with different prices | the units' shelf prices minus Y x the cheapest shelf price in the group |
| percent or unit price over products with different prices | each unit at its own promo price |

The buy-X-get-Y rule is conservative: Israeli promos give the cheapest unit free, and counting
the cheapest shelf price of the group never claims more than the store gives. The reward reading
of the promo fields is still the adapters' provisional mapping (docs/adapters.md), not yet
verified on real files.

### Why the store-set form

The textbook form (`y[s]` free, every need with `x[i,p,s]`, big-M for missing) is the same
model, but its LP relaxation is weak here (fractional stores, and the missing-item big-M), and
CP-SAT needed thousands of branches: 150 to 400 ms per solve on the 40 x 10 benchmark, up to the
time limit at K = 3. Enumerating the store sets (at most 575, bounded by the request schema) makes
the plain needs constants and leaves the solver only the coupled part. On the same benchmark the
median dropped to about 25 ms at K = 2. With N or K above the schema's limits the number of sets
grows as N choose K and this form would need revisiting.

## Plans

The MILP solves at most three problems, each with the heuristic's best plan as a hint:

1. `single`: one store (`K = 1`);
2. the best plan with up to `max_stores` stores. When it visits two or more stores it is the
   `split`. When it visits one, every split costs at least as much, so a split can only tie;
   only with `min_split_saving = 0` is a third solve made with "at least two stores" (the
   heuristic returns such a tie too);
3. `minimum_effort`: the home store alone.

Selection is the heuristic's: the split is returned only when it misses no more items than
`single` and costs at least `min_split_saving` less; `recommended` is on the split when there
is one. `subsets_evaluated` keeps its meaning: the number of store sets the plans are chosen
from.

**Savings (D7).** The breakdown is built by the same code as the heuristic's, against the home
store, and the home store is priced by the same model (its own shared promos included), so a
plan never claims a bundle as a saving against a home store that offers the same deal. The hero
number is still `net_saving = basket_saving - travel_cost - extra_stop_cost`.

**Lines.** A line outside shared promos keeps basket.py's line exactly. In a shared group each
line pays the shelf price for its units outside bundles, its promo unit price inside, and its
share of the bundles' fixed price; the rounding remainder goes to one line, so the lines add up to
the group's cost. Such a line has `promo_applied = true` when it has units in a bundle, and its
per-line `promo_add_qty`/`promo_add_saving` are cleared (they describe the line alone).

**`Plan.promo_bundles`.**

- Applied bundles (`add_qty = null`): every promo applied in whole bundles in the plan, single
  product or shared, with `bundle_count` and `saving` (shelf price of the units in the bundles
  minus what the bundles cost).
- Suggestions (`add_qty` set, not applied): for each promo group in the plan, the smallest
  addition to one of its lines that lowers the group's total cost, the extra units' price
  included. `saving` is that net drop, `bundle_count` the bundles after adding. A suggestion is
  returned only when the saving is strictly positive: "3 for 9" at 5.00 each with 2 in the list
  (10.00, or 9.00 for 3) gives "add 1, save 1.00"; a 1+1 with one in the list (5.00 or 5.00 for
  2) gives nothing. The check holds the plan's stores fixed, so the true saving after
  re-optimizing can only be larger.

## Solver choice and settings

OR-Tools CP-SAT (`ortools==9.15.6755`, pinned in `services/api/pyproject.toml`; the wheel
installs on Python 3.12 and 3.13 on Linux x86-64):

- exact integer arithmetic in agorot, no floating-point tolerance on money;
- a pip wheel with no system dependency, available in CI and on the VPS;
- `num_workers = 1`, `random_seed = 0`: deterministic answers for the same input;
- `linearization_level = 2` (full LP relaxation; several times faster proofs here);
- `max_time_in_seconds = 2`: when the limit is hit with a solution, it is used and logged with
  `status = feasible`; with no solution, the request falls back to the heuristic;
- `absolute_gap_limit` set so that the search stops once the cost is proven optimal to the
  agora; only the tie-break order may then be unproven.

HiGHS through PuLP (the other option in D9) was not needed: CP-SAT installs here and handles the
integer bundle variables natively. It stays the fallback if a platform lacks the OR-Tools wheel;
`milp.py` imports OR-Tools lazily so the API still starts (heuristic only) without it.

## Limits

- One product per need and store: the line basket.py chose (the lowest effective unit price at
  that level). The MILP does not consider a dearer product of the same store that would fill a
  shared promo; the swap suggestions below cover product changes.
- A shared promo is found only when it is the promo basket.py chose for each line. A product
  whose best deal is another promo does not join the group.
- Weighed goods and fractional quantities never join bundles.
- Daily `hours` windows of promos are not applied (as in the precompute).
- Store sets grow as N choose K; the schema caps them at 575.
- The fallback to the heuristic is per request, not per plan.

## Performance (measured)

Benchmark harness: `uv run python -m smartcart_api.milp` and
`test_milp.py::test_benchmark_40_items_10_stores` (prints its timings in the pytest output and
fails above 1 s per solve). It times the two solves `/optimize` makes over the candidates (one
store, then up to K) on synthetic baskets of 40 needs over 10 stores, with no hint. The data is
synthetic (`milp.synthetic_problem`): four chains with a chain price level per product within
15 %, 10 % store exceptions, 5 % of products not stocked by a chain and 2 % missing at a store,
10 % substitutes, a "3 for 20" shared by every seventh need at every store and a 1+1 on every fifth
need. `random` draws every store's prices independently (no chain structure).

Measured on 2026-10-07 in a shared 4-vCPU container with a load average of 6 to 10 (other jobs
running), wall time per solve, 20 solves per row:

| Case | K | median | max |
|---|---|---|---|
| chains | 2 | 29 ms | 212 ms |
| chains | 3 | 62 ms | 594 ms |
| random | 2 | 26 ms | 55 ms |
| random | 3 | 57 ms | 124 ms |
| no shared promo (every need's promo is its own) | 2 | 4 ms | 5 ms |
| no shared promo | 3 | 8 ms | 10 ms |
| a third of the needs in one shared promo at every store (stress) | 3 | 92 ms | 2 s (time limit, best solution kept) |

So the research's "40 items and 10 stores in tens of milliseconds" (an expectation, not a
measurement on our data) holds for the median at the default K = 2 in these runs; the tail
depends on how many needs share a promo. The CI runner's numbers are in the PR. None of this is
measured on real transparency files yet. The route adds the pricing queries (the same as the
heuristic's) and one promo lookup.

## Smart-cart swaps (#45)

`POST /optimize/swaps?store_id=` with the /compare body (`smartcart_api/swaps.py`):

1. The list is priced at the store as in /compare (the current lines).
2. For each canonical the store sells at the chosen level, the alternatives are the store's
   lines at that level or a looser one: `exact` with a barcode: the cheapest other exact match,
   `any_brand`, `close`; `exact` without a barcode or `any_brand`: the looser levels; `close`:
   none. They are priced by the same `price_baskets` (one call per level), so they contain only
   mappings the matching layer accepted at that level and not flagged `needs_review`, with the
   same club gating and promo folding.
3. A candidate is dropped when one of the canonical's critical attributes is known on the item
   and differs (D4 fixes critical attributes at `any_brand` and `close`; D5). Its tags are the
   same `matched`/`differs`/`unverified` tags /compare shows for substitutes, plus `confidence`.
4. `saving` = current line total minus the alternative's, for the requested quantity (promos and
   weight included); only positive savings. One swap per canonical, the largest (ties keep the
   stricter level).
5. `swaps` sorted by saving, `top_swap` the first, `total_saving` their sum. The swaps touch
   different canonicals and each line is priced on its own, so the total is exactly the basket
   difference after applying all of them; a test checks it against re-pricing the list, and that
   no combination of level changes saves more.

Nothing is applied and the user's level is not changed. A canonical the store does not sell at
the chosen level is a gap, not a swap. Not in this endpoint yet (issue #45 items that need the
web app or storage): dismissing a swap until prices change materially, undo, and recording
dismissals as catalog feedback (`/feedback/substitution` exists for the "not a good substitute"
signal); "add one more" suggestions are in `Plan.promo_bundles` instead. The saving is per store,
so it does not include a travel effect; the store's travel is unchanged by a swap.
