# Cart optimizer: heuristic and MILP, smart-cart swaps

Issues #13 (MILP with cross-item promos and quantity rounding) and #45 (smart cart). Code:
`services/api/smartcart_api/milp.py`, `routes/optimize.py`, `swaps.py`, `routes/swaps.py`.
Tests: `services/api/tests/test_milp.py`, `test_swaps.py`, the phase 1 `test_optimize.py`, and the
randomized `test_api_optimizer_props*.py` (invariants below).
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
| buy X get Y at P % off over products with different prices ("the second at 50 %"; `raw.get_percent` P) | the units' shelf prices minus Y x P % of the cheapest shelf price in the group, rounded toward zero to the agora |
| percent or unit price over products with different prices | each unit at its own promo price |

The buy-X-get-Y rule is conservative: Israeli promos give the cheapest unit free, and counting
the cheapest shelf price of the group never claims more than the store gives. The same holds for
the percentage form: whichever unit of a pair the store discounts, it is at least the cheapest
shelf price of the group, so `Y x P % x cheapest` is a lower bound of the discount. The reward
reading of the plain promo fields is verified on real files (docs/adapters.md). The two-group "buy
one, get one at P % off" shape ("1+1" and "השני ב 50%" in Shufersal, Tiv Taam and Yohananof files)
is read by the adapters from the real layout, with one reservation: **whether a pair may mix
products of the group is not shown by the file**. The adapter links only items that appear in both
groups and lowers the promo's confidence by 0.1 (`mixed_items_unverified`) when there is more
than one. A group of one product is exact in every reading; for mixed pairs the MILP counts only
the lower bound, which would still be too high if a store allowed pairs of the same product only.
That is why the confidence says so.

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
- Weighed goods and fractional shelf-pack counts never join bundles (a counted canonical's
  quantity is rounded up to whole shelf packs first, see "Packs").
- Daily `hours` windows of promos are not applied (as in the precompute).
- Promos restricted to some weekdays (`PromotionDays`) are never applied: the adapters read them as
  unapplied (`weekday_restricted`), so neither the precompute, /compare nor the MILP sees them.
- A "buy one, get one at P % off" promo (`buy_x_get_y` with `raw.get_percent`) folds into the
  precompute as `shelf x (X + Y (1 - P/100)) / (X + Y)` per pack with `X + Y` packs needed (the
  second at 50 %: 75 % of the shelf price, two needed), so `/compare`'s `line_total` (whole packs at
  the effective price, the rest at the shelf price) and the MILP's single-product group need no new
  code; only the MILP's mixed-price group reads `get_percent` (table above). A promo with a
  redemption limit is not applied by the adapter at all (`redemption_limited`).
- Store sets grow as N choose K; the schema caps them at 575.
- The fallback to the heuristic is per request, not per plan.

## Packs: the count in the name, the unit price and whole packs (finding 9 of the second real day)

The first real-day run priced a tray of 12 eggs at 14.20 **per egg**. This section is the rule for
"how many base units are in one shelf item" and how the quantity of a request becomes shelf items.

### How the quantity flows

| Step | Where | What it does |
|---|---|---|
| 1. The chain's fields | `items.quantity`, `items.unit` (`Quantity`, `UnitQty`, `bIsWeighted`, `QtyInPackage`), `prices.unit_price`, `prices.uom` | Rami Levy, Yohananof and Tiv Taam write `Quantity = 1, UnitQty = יחידות` for a tray of 12 eggs and publish the tray's price as the price of "1 unit"; King Store and Osher Ad write the count (`12`, `60`) |
| 2. The catalog's reading | `normalize.normalize` (`services/catalog/smartcart_catalog/normalize.py`) | Parses the name (`12 יח'`, `18יח`, `2*30 יח'` = 60, `6*1.5 ל'` = 9000 ml, `32 גלילים`), weighs it against the fields and returns `quantity x pack_count = total_quantity` in g, ml or units |
| 3. The canonical's base unit | `canonical_products.base_unit` | `unit` for eggs, pitas, toilet paper and the other counted goods; `100g` / `100ml`; `kg` for weighed goods |
| 4. The unit price of an item | `precompute.read_unit_price` | **`shelf price / units in the item`** for a `unit` canonical; per 100 g or 100 ml on the pack's total weight or volume otherwise (rules below) |
| 5. The effective price per canonical and store | `effective_prices.effective_unit_price`, `pack_units` | Ranked by that unit price (D4); `pack_units` is the item's unit count, NULL when the item states none (migration `20261023100000`) |
| 6. The quantity of a request | `BasketItem.quantity` | "Packs": for a counted canonical a pack is the canonical's typical count (`soft_attrs.pack_size`: 12 eggs, 10 pitas, 32 rolls); for every other canonical it counts shelf items |
| 7. The line | `basket.shelf_packs`, `basket.line_total` | `packs = ceil(quantity x typical count / pack_units)` shelf items; promo bundles, the "add N" hint and `line_total` count those shelf items. `PricedItem.packs` and `pack_units` say what was bought |
| 8. The optimizer | `milp._join` | Reads `PricedItem.packs`, not the quantity asked: bundles are made of shelf items |

**The rule for "units in one shelf item"** (`precompute._read_count`, per-unit canonicals only):

1. Three readings: the catalog's (`normalize`: the name, weighed against the fields), the item's own
   fields (`Quantity` with a unit word for units), and the published unit price (`price / unit price`
   when its `uom` is `unit`, rounded to a whole number within 6 %).
2. A reading below 1.5 is a **1**: what the chains write when they do not know the count. It never
   outvotes a stated count. (`Quantity = 1` on `ביצים 12 יח גדול L` is why the old code priced 14.20
   per egg.)
3. If at least one reading states a count above 1, the item holds the **smallest stated count**: the
   larger unit price, the safer one. A unit price is never cheaper than the shelf supports.
4. Readings that differ by more than 12 % are recorded in the precompute's `match_runs` metrics:
   `pack_reads` (`count_from_name`: the name stated it and the fields said 1 or nothing;
   `count_conflict`: two stated counts differed, the smaller was used; `measure_conflict`, below)
   and `pack_samples` (up to 20 of each, with the item id, the name and what each reading said).
5. If no reading states a count the item is compared per pack as before (`pack_units` NULL, the
   quantity counts shelf items). A single loose roll under `toilet-paper` (typical 32) is therefore
   priced as one roll per pack: not detectable without a stated count.

**Per 100 g and per 100 ml** (`precompute._read_measure`): the published unit price, the fields'
unit price and the name's (`price x 100 / normalized total`). When they agree (within 12 %, or one
agora of rounding) the first of published, fields, name is used: a per-100 g item with a consistent
published price is unchanged. When they disagree **the highest unit price wins** and the
disagreement is recorded as `measure_conflict` (a published price a hundred times too small, a
multi-pack whose fields say `1 יחידות`). A multi-pack drink `6*1.5 ל'` at 27.00 is 9000 ml, 0.30 per
100 ml, whatever its fields say. `pack_units` is NULL: the quantity counts shelf items, exactly as
before.

**Whole packs.** The requested amount is `quantity x typical count` units; the line buys the
fewest whole shelf items that cover it (`shelf_packs`). Promo bundles then count shelf items
("2 for 14" on a pack of 6 eggs is reached by one pack of 12 eggs asked: two packs). An exact
barcode and a weight or volume canonical keep counting shelf items; a row with no `pack_units`
(an older run, an item that states no count) too.

| Item (shelf price) | Units | Quantity 1 (12 eggs) | Quantity 2 (24) | Quantity 3 (36) |
|---|---|---|---|---|
| `ביצים 12 יח גדול L` (14.20) | 12 | 1 pack, 14.20 | 2, 28.40 | 3, 42.60 |
| 30-tray (29.90) | 30 | 1 pack, 29.90 | 1, 29.90 | 2, 59.80 |
| `ביצים 18 יח' בינוני` (21.50) | 18 | 1, 21.50 | 2, 43.00 | 2, 43.00 |
| pack of 6 (8.40) | 6 | 2, 16.80 | 4, 33.60 | 6, 50.40 |
| `ביצים 2*30 יח' בינונ` (28.90) | 60 | 1, 28.90 | 1, 28.90 | 1, 28.90 |

The consequences, stated so they are not surprises:

- The nightly pick per (canonical, store, level) is still **by unit price**, which does not know the
  quantity (known limit 4 below). At `close`, a tray of 30 at 1.00 an egg beats a 12-pack at 1.18, and
  the line for 12 eggs is then the whole tray, 29.90. The line is honest; it is not the cheapest
  purchase of 12 eggs. At `any_brand` only the typical pack (12) competes (`matching.md`, "Real items,
  eggs").
- A pack smaller than the typical count costs more packs (toilet paper of 24 rolls for a typical
  32: two packs for quantity 1). The match labels such an item a substitute (`pack_size` differs).
- A fractional quantity of a counted canonical is rounded up to a whole pack (0.5 of a 12-pack of
  eggs is one pack); for other canonicals fractional quantities are priced as before.

Real examples (the second real day, `real-day-dry-run.md` finding 9; shelf prices from that report; the pita line assumes a basket amount of 10, the report does not state it):

| Item | Shelf | Unit price before | Unit price after | 12 eggs / 10 pitas / 24 rolls before (basket index: unit price x amount) | after |
|---|---|---|---|---|---|
| Rami Levy `ביצים 12 יח גדול L` | 14.20 | 14.20 per unit | 1.1833 per egg | 170.40 | 14.20 |
| Yohananof 10 pitas | 9.90 | 9.90 per unit | 0.99 per pita | 99.00 | 9.90 |
| Tiv Taam 10 pitas | 16.90 | 16.90 per unit | 1.69 per pita | 169.00 | 16.90 |
| Rami Levy 24 rolls | 27.90 | 27.90 per unit | 1.1625 per roll | 669.60 | 27.90 |
| Tiv Taam 24 rolls | 32.90 | 32.90 per unit | 1.3708 per roll | 789.60 | 32.90 |

`/compare`'s own `line_total` multiplied the shelf price by the quantity before and does now; what the
old reading broke was the unit price (what the ranking, `/search`, the history chart and the basket
index use) and the choice between a store's items. The new unit prices are in the test data below;
the report is regenerated by the next real-day run.

Tests: `test_api_packs.py` (real names: eggs 12/18/30, `2*30`, pitas, toilet paper, the `6*1.5 ל'` drink;
the reading, `effective_prices`, `/compare` for several quantities, promos, `/optimize`, the history
chart, a per-100 g item unchanged) and the pack features of `test_api_optimizer_props_db.py`.

## Invariants covered by tests

Randomized tests (`test_api_optimizer_props.py`, `test_api_optimizer_props_db.py`; seeded
`random` loops, no `hypothesis` dependency; fixed seeds, so a failure names its seed) compare the
code with references that share nothing with it. The pure half builds small problems (2 to 4
stores, 2 to 4 needs, own and shared bundles, "buy X get Y" and per-unit groups, quantity limits,
travel and extra-stop costs) and checks against an exhaustive search over every store set, every
assignment and every way of putting units into a bundle. The DB half writes a random world to the
tables (2 chains, 3 to 5 stores at distinct distances, 3 to 4 canonicals one of which may be
weighed, store exceptions, products a chain or store does not stock, close-level substitutes, two
sibling milks, items that state a pack count in the name and canonicals with a typical pack,
unit price / percent / 1+1 / "second at P %" / "N for X" promos with and without a minimum quantity,
club-only promos, one promo shared by two products), runs the real precompute and calls the
real routes. `expected()` in that file recomputes every line from the promo definitions.

| Invariant | Where |
|---|---|
| The MILP equals the exhaustive optimum (fewest missing, then cost) for K = 1, 2, 3, with and without shared promos, quantity limits, travel and extra-stop costs; with `min_stores = 2` it equals the heuristic's split (or there is none) | props, 40 seeds |
| The MILP's reported lines add up to its basket total, and that total is what the exhaustive reference charges the plan's own assignment | props |
| The MILP does not depend on the order of the needs or lines, and is deterministic | props, regress |
| The heuristic is never better than the pooled optimum, equals the optimum of pricing every line alone (the D9 claim), equals the pooled optimum when no promo is shared, and the MILP is never worse than the heuristic | props |
| Every subset's plan: the total is the sum of its lines, at most K stores are visited, every need is bought once or listed missing | props, props_db |
| Every line of `/compare` equals the independently recomputed price: bundles and remainders, unit/percent/1+1/"N for X" promos with a minimum quantity, weighed goods per kg, close substitutes, allowed siblings, club gating | props_db |
| A store prices exactly what it stocks and lists the rest as `missing`; `found_count`; stores that supply nothing are not listed | props_db |
| Money is whole agorot everywhere (`line_total`, `total`, travel, every `breakdown` field) and a store's total is the lines' sum rounded once | props_db |
| A club deal is for members only; `club_offer_*` is information only; a member never pays more than a non-member | props_db, regress |
| A substitute is labeled, carries `original_here` exactly when the store sells the original, and an allowed sibling carries a `differs` tag | props_db |
| `/optimize` with the heuristic: `single` is the best one-store plan; with `min_split_saving = 0` the plan shown is the exhaustive optimum (unless the optimum completes a list no single store completes, see "Plans"); a split saves at least `min_split_saving` over `single` | props_db |
| `/optimize` with the MILP equals the pooled exhaustive optimum, including promos two needs share (two products, or two needs that map to the same item) | props_db |
| `breakdown`: `net_saving = basket_saving - travel_cost - extra_stop_cost` exactly; `travel_cost` is the plan's travel minus the home store's, floored at 0; `extra_stop_cost = extra_stop_value x (stores - 1)`; the basket saving is recomputed from the home and plan lines over the canonicals both supply, so a plan never shows a positive net saving the lines do not support; the assignments' `saving_vs_home` add up to `basket_saving`; `minimum_effort` saves exactly 0 | props_db |
| A line of a counted canonical buys whole shelf packs: `packs = ceil(quantity x typical count / pack_units)`, `line_total` and the MILP's bundles are built on `packs`; items with different unit counts, close-level substitutes and promo bundles over packs (random pack counts of 2 to 12 per chain item, typical packs of 1 to 6 per canonical) | props_db |
| `allow: []` equals omitting it; `flex_level` spelled out equals its default; the response does not depend on the order of the list (items and `missing` compared as sets), nor on one quantity split over two entries | props_db |

### Bugs these tests found (each has a regression in `test_api_optimizer_props_regress.py`)

1. A split's per-store `saving_vs_home` covered all the store's lines, not the ones bought there
   (1.10 and -1.40 for a plan saving 3.10). Fixed in `StoreBasket.result` / `saving_vs`.
2. A quantity of 0.0001 packs divided 0.00 by 0.00 (HTTP 500) and 1e30 overflowed `money()`
   (HTTP 500). `BasketItem.quantity` is now 0.01 to 1000 (a 422 outside), and `_unit_paid` no
   longer divides by a zero shelf total.
3. The same canonical asked at two levels was priced by whichever entry came first, and when the
   strictest request had no offer at a store the looser one was priced with only its own share of
   the quantity. Entries are now visited strictest first; a store that cannot meet the strictest
   request lists the canonical as missing.
4. The precompute keeps the offer with the best unit price, which ignores the quantity. For a
   club row a member could pay more than a non-member (a club "4 for 20" against everyone's
   "2 for 16", 2 asked: 20.00 against 16.00), and an allowed sibling could lose to an own offer
   that needed more packs than asked. `price_baskets` now takes the cheapest line for the
   quantity among the offers open to the user (`club_alternatives`, the allowed siblings), the
   own offer first on a tie.
5. The MILP's per-line totals in a shared promo depended on the order of the list (the group's
   total did not): which line paid the loose pack was whatever CP-SAT found first. The units now
   go to the lines by a fixed rule (largest discount, then the lower canonical id,
   `milp._spread_units`).

### Decisions the tests left as they are

- `max_qty` of a promo is applied by the MILP but not by `/compare` or the heuristic (the
  precompute does not carry it: `precompute.py`, "not applied"). For a promo with a limit the
  MILP's line can cost more than `/compare`'s; the heuristic is then not an upper bound of the
  MILP. The randomized comparisons therefore draw no limits for the heuristic.
- A split is shown only when it misses no more items than `single` and saves at least
  `min_split_saving`. When no single store has everything and the cheapest single plan misses an
  item, a split that completes the list costs more and is not shown (the item stays "missing" in
  `single`). The ranking elsewhere is missing-first; this is the documented rule of D9, kept
  because changing which plan is recommended is a product decision.
- `home_store_total` is 0.00 when the home store supplies nothing on the list (documented as "over
  what it supplies"); the web app does not read the field.
- The heuristic prices every line alone. When two needs map to the same item (two siblings
  allowed) a "3 for X" promo is not pooled across them there, only in the MILP: the heuristic is
  never cheaper than the truth, only sometimes dearer.
- Per-unit promo prices in a shared group are `bundle price / N`, rounded to an agora in the
  solver's objective (the reported totals are exact and rounded once). When N does not divide the
  bundle price the objective is off by under an agora per unit, so a plan within an agora of the
  optimum can be preferred. The randomized tests draw whole-agora prices and do not exercise this.
- A non-club row keeps the best deal by unit price: a second, quantity-friendlier non-club promo
  on the same item is not in `effective_prices` and is not considered.

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

### Measured on the scaled synthetic world, 2026-10-08, this machine

End to end through the real route, unlike the solver-only benchmark above:
`scripts/loadtest/run.py` (docs/deploy.md, sizing) writes a world with the adapters' fixture
builders, loads it through the adapters, the quality gates and the loader into a throwaway Postgres,
maps every item through the review step's `accept`, runs the precompute, then calls the API over
HTTP. World: 10 chains, 300 stores (45 % in Gush Dan), 5,000 items mapped to the 245 canonicals,
90 days of price events (207,075 change events from 7,810 files), promotions on about 20 % of each
store's items (19,634 promotions, 15 % club-only), 144,380 effective-price rows. Baskets: 50 of 25
canonicals each (20 % at "close", the rest "any brand"), at points in Gush Dan with a 5 km radius
(median 55 stores in it, at most 79) and a home store; `candidate_stores` 10, `max_stores` 2 (K = 2,
55 store sets). Machine: the build container, 4 vCPU Intel Xeon 2.1 GHz shared with other jobs,
Postgres 16 on the same machine with `fsync` off, Python 3.13, two uvicorn workers; one request at
a time, wall time at the client.

| Route, 50 requests | Run 1 p50 | Run 1 p95 | Run 2 p50 | Run 2 p95 | max |
|---|---|---|---|---|---|
| `/optimize`, `solver = heuristic` | 28 ms | 37 ms | 23 ms | 27 ms | 131 ms |
| `/optimize`, `solver = milp` | 44 ms | 64 ms | 36 ms | 94 ms | 121 ms |
| `/compare` (every store in the radius) | 72 ms | 171 ms | 71 ms | 135 ms | 195 ms |
| `/search`, 50 queries | 46 ms | 61 ms | 56 ms | 92 ms | 117 ms |

| Job | Run 1 | Run 2 |
|---|---|---|
| `smartcart-api precompute`, 144,380 rows | 26.9 s | 33.2 s |
| `smartcart-api alerts-run --dry-run`, 1,000 alerts, 990 fired | 2.5 s | 3.0 s |

- The MILP answered every request itself (no fallback to the heuristic); both solvers found a split
  for the same 37 of the 50 baskets.
- The MILP costs about 15 ms more than the heuristic at the median: the pricing step is shared, and
  the solve itself stays in the tens of milliseconds measured above. The tail is the shared
  machine as much as the solver (run 2's MILP p95 doubled while the heuristic's fell).
- `/compare` is the slowest route because it prices every store in the radius, not the 10 nearest;
  its time grows with store density.
- Under 8 concurrent clients, `/compare` served 17 to 23 requests per second (p50 330 to 443 ms),
  with Postgres competing for the same 4 vCPUs.
- Everything here is **synthetic**: the prices, the promotion mix (unit price 40 %, percent 25 %,
  1+1 / 2+1 20 %, "N for X" 15 %, one or two items each) and the store density are generated, not
  observed. Re-measure on real transparency files.
- `--small` (30 stores, 1,200 items over 60 canonicals, 30 days, 10 baskets of 10) runs the same
  steps in about 20 s; it is meant for CI and not part of any workflow yet.

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
   `BasketItem.allow` is honored like in /compare (#31): the alternatives of an `any_brand` or
   `close` row are priced with that row's allowed attributes, so a sibling canonical that differs
   only in allowed critical attributes (3% milk, `fat_pct` allowed, 1% milk) can be a swap. It is
   labeled with a `differs` tag per attribute that made it a sibling, and a critical difference
   that is not allowed still drops it. An `exact` row ignores `allow`; an empty `allow` is the old
   behavior.
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
