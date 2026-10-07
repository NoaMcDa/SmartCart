# SmartCart API

The thin FastAPI service of decision D3 (`services/api`, package `smartcart_api`). It serves the
basket routes the web app calls, the signed-in user routes, and the nightly effective-price job.
The contract is `services/api/smartcart_api/schemas.py`; the OpenAPI 3.1 document generated from
it is `apps/web/src/api/openapi.json`, and the web app's TypeScript types are generated from that
(`apps/web/src/api/types.ts`, see [TypeScript client](#typescript-client)).

Every price the API returns comes from the chains' transparency files, carries its update
timestamp, and is subject to "המחיר הקובע הוא בקופה" (`disclaimer_he` on /compare and /optimize).

## Running it locally

```bash
uv sync
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres   # never commit one
uv run python -c "from smartcart_ingest import db; print(db.migrate(db.connect(autocommit=True)))"
uv run smartcart-api precompute            # effective_prices, after an ingestion load
uv run smartcart-api serve --reload        # http://localhost:8000/docs
```

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | none | Postgres (Supabase) connection string, the service connection |
| `API_CORS_ORIGINS` | `http://localhost:3000` | comma-separated allowed origins |
| `SUPABASE_JWT_SECRET` | none | the project's JWT secret (HS256); `/me/*` return 503 without it |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | expected `aud`; empty disables the check |
| `API_DB_USER_ROLE` | `smartcart_app` | role switched to for signed-in requests (RLS) |
| `API_POOL_MIN` / `API_POOL_MAX` | 1 / 10 | psycopg pool size |
| `API_WALK_TRANSIT_COST_PER_STORE` | 11.0 | flat ILS per store for `walk_transit` (estimate: two single bus fares) |

`smartcart-api` commands:

| Command | What it does |
|---|---|
| `smartcart-api serve [--host] [--port] [--reload]` | uvicorn on `smartcart_api.main:app` |
| `smartcart-api precompute [--as-of ISO] [--chain ID ...]` | recompute `effective_prices` and print the run metrics as JSON |

## Routes

| Route | Auth | Purpose |
|---|---|---|
| `GET /health` | none | liveness and API version |
| `GET /search?q=&limit=` | none | hybrid search over canonical products |
| `POST /parse-list` | none | free text to canonical items with quantities and confidence |
| `POST /compare` | none | basket total at every store in the radius |
| `POST /optimize` | none | single store, split, minimum effort, each with a net-saving breakdown |
| `POST /feedback/substitution` | optional | "not good" / kept original / accepted for a substitute |
| `POST /feedback/gap` | optional | report-a-gap: shown versus actual price, or a missing item |
| `GET /me/profile`, `PUT /me/profile` | required | the user's profile (home store, radius, clubs, travel, flex defaults) |
| `GET /me/lists`, `POST /me/lists` | required | saved lists with their items |
| `GET`, `PUT`, `DELETE /me/lists/{list_id}` | required | one list; PUT replaces name, recurrence and items |

Requests reject unknown fields (422). The basket routes take no user identity and store nothing.

### GET /search

Three retrievers over `canonical_products.display_name_he`, merged with reciprocal rank fusion
(`smartcart_api/search.py`, indexes in `supabase/migrations/20261007110200_search_indexes.sql`):

| Retriever | How | Catches |
|---|---|---|
| `trigram` | pg_trgm `word_similarity` of `search_norm(query)` in `search_norm(name)`, threshold 0.3, GIN trigram index | typos ("חלבב", "רסק עגבנייות") |
| `fts` | `to_tsvector('simple', search_norm(name))`, prefix terms, each word also without an attached ו/ה/ב/ל/מ/ש/כ | exact words ("והלחם" finds "לחם") |
| `vector` | pgvector cosine on `canonical_products.embedding` and on `item_embeddings` of items mapped at exact/any_brand, HNSW, minimum 0.25 | meaning, once real embeddings are loaded |

- Postgres has no Hebrew dictionary or stemmer. `simple` only lowercases, so inflection (plural,
  construct state) is left to trigram and vector retrieval. `search_norm()` folds final letters,
  removes niqqud and quote marks (`ק"ג` = `קג`), so "סלמון" and "סלמונ" match.
- pg_trgm and the text-search parser need a UTF-8 `LC_CTYPE` to see Hebrew letters as letters.
  Supabase and the CI image have one; the local throwaway test cluster runs the API tests in a
  sibling database created with `LC_CTYPE C.UTF-8` (`services/api/tests/conftest.py`).
- The query embedder is a deterministic 1024-dimension character n-gram hash
  (`smartcart_api/embedding.py`), a stand-in for BGE-M3 so the pipeline runs without a model. It
  captures spelling, not meaning. When the catalog workstream loads BGE-M3 vectors, the query
  embedder must switch to the same model (one line in `search.py`).
- `score` is the RRF score (`sum 1/(60 + rank)`) divided by its maximum, in [0, 1].
  `matched_by` lists the retrievers that found the hit. `confidence` is the evidence:
  `0.85 x best similarity + 0.15 x share of retrievers that found it`.
- `canonical.category_path_he` is the taxonomy path, root first.
- Latency: a 30-item `/parse-list` (90 retriever queries) took 0.14 s on the test database with
  the test catalog (measured locally). The target on the MVP catalog (a few hundred canonicals) is
  under 50 ms per query; not yet measured on real data.

### POST /parse-list

1. Split on newlines, commas, semicolons and bullets. A `" ו"` ("and") boundary splits only when
   every part resolves at least as well as the whole fragment: "סלמון ולחם" is two rows, "חטיף
   וופל" one.
2. Quantities: leading counts (`2 רסק עגבניות`, `2x`, `x2`, `שני`...), leading weights
   (`1.5 ק"ג עגבניות`, `500 גרם` = 0.5 kg; `unit = "kg"`), trailing counts only with a marker
   (`חלב x3`, `×3`, `*3`, `3x`, `3 יח'`). A bare trailing number stays in the text because it is
   usually part of the product (`ביצים L 12`, `חלב 3%`).
3. Each fragment goes through the hybrid search. The row's `confidence` is the best hit's
   evidence, capped at 0.70 when another canonical is as good (evidence within 0.05 and name
   coverage within 0.1, e.g. 3 % versus 1 % milk for "חלב").
4. `confidence < 0.75`: `needs_confirmation = true` with up to 3 `candidates`. `confidence < 0.35`
   (or no hit): `not_found = true`, `canonical = null`. The parser never guesses silently (D5).
5. `flex_level` is the first match of the canonical's taxonomy node or its ancestors in
   `flex_defaults`, else `any_brand`. `is_weighed` when a weight was given or the canonical is
   sold by the kg.

### POST /compare

- Stores: `stores_within(lon, lat, radius_m)` (PostGIS, GiST); `channel = online` only with
  `include_online`. Stores that supply none of the basket are left out.
- Lines come from `effective_prices` for the requested flexibility level (see
  [Effective prices](#effective-prices-nightly)). Per line:
  - club deals apply only when the user listed that club (`clubs`); otherwise the row's
    `noclub` option is used and no club deal is shown;
  - `flex_level = exact` with `exact_item_id`: that barcode must be sold by the store's chain
    (mapped to the canonical at exact or any_brand) and is priced live with the same promo
    folding; otherwise the canonical counts as missing at that store;
  - by weight (base unit `kg`): `line_total = quantity (kg) x effective price per kg`, estimated;
  - by count: full promo bundles at the promo price, the remainder at the shelf price. When the
    remainder is short of a bundle, `promo_add_qty` and `promo_add_saving` say "add N and save X"
    (`promo_add_saving` = shelf price of quantity + N minus what that quantity costs with the
    promo). `promo_applied` says whether the requested quantity reaches the promo;
  - a line whose item is mapped at `close` is a substitute: `is_substitute`, the mapping
    `confidence`, `tags` comparing the item's extracted attributes with the canonical's critical
    and soft attributes (`matched`, `differs`, `unverified`; kosher and diet flags stay
    unverified unless a human verified them), and `original_item_id`, the store's non-substitute
    item when it has one;
  - `price_valid_from` on every line; `prices_updated_at` per store is the newest of its lines.
- `missing` lists the canonical ids a store cannot supply; `found_count` the others. Never
  dropped, never priced as zero.
- Sorting: fewer missing items first (complete baskets first), then total, then distance.

### Saving semantics (D7)

- The only saving figure is against the user's own store (`home_store_id`), never against the
  most expensive store or chain. A test asserts no response field compares with a maximum.
- `saving_vs_home` (compare) and `basket_saving` (optimize) are computed over the canonicals both
  baskets supply: a store does not look cheaper by not stocking part of the list. Missing items
  are listed separately.
- `home_store_total` is the home store's total over what it supplies; the home store is priced
  even when it is outside the radius.
- Without `home_store_id`, every saving field is null.

### POST /optimize

Phase 1 heuristic (D9), `smartcart_api/routes/optimize.py`:

1. The `candidate_stores` nearest stores in the radius (default N = 10) are priced as in /compare.
2. Every subset of 1 to `max_stores` stores is evaluated: N = 10, K = 2 gives 10 + 45 = 55
   (`subsets_evaluated`). In a subset each canonical goes to the store with the lowest line
   total; the stores that receive an item are visited.
3. Cost = basket total + travel + extra stops:
   - `car`: `2 x distance_km x cost_per_km` per visited store (a round trip to each store from
     the user's location, not a tour);
   - `walk_transit`: a flat `API_WALK_TRANSIT_COST_PER_STORE` per visited store (estimate);
   - `delivery`: no travel; the delivery fee is a placeholder 0 in phase 1;
   - extra stops: `extra_stop_value x (visited stores - 1)`.
4. Subsets rank by missing items, then cost. Without cross-item promos the best subset is the
   exact optimum over all assignments of items to at most K stores; a test compares it with an
   exhaustive reference.
5. `single`: the best one-store subset. `split`: the best subset visiting two or more stores,
   returned only when it misses no more items than `single` and costs at least
   `min_split_saving` less. `minimum_effort`: the home store. `recommended` is true on the split
   when there is one, else on the single.
6. `breakdown` (with a home store): `basket_saving` as above; `travel_cost` = the plan's travel
   minus the home store's travel, floored at 0 (a plan is never credited with a travel saving);
   `extra_stop_cost`; `net_saving = basket_saving - travel_cost - extra_stop_cost`, the hero
   number. `Plan.travel_cost` is the plan's absolute travel cost. `extra_minutes` is an estimate
   (car 30 km/h, walk and transit 12 km/h, 10 minutes per extra stop).

### Effective prices (nightly)

`smartcart-api precompute` (`smartcart_api/precompute.py`, issue #47) fills `effective_prices`,
one row per (canonical, store, flexibility level):

- Candidates: items mapped in `item_canonical` at a level at or below the requested one
  (exact < any_brand < close), not flagged `needs_review`, of the store's chain.
- Price: the store's latest event, else the chain base price (`current_price()` semantics), as
  of `--as-of`. Only rows whose file is `loaded` in `file_tracking` count (rows without a
  `file_id`, written by hand, count too): quarantined or failed files never feed a price.
- Unit price: the published one, normalized by the loader, else derived from the item's pack
  size, converted to the canonical's base unit (kg and 100 g convert; other mismatches are left
  out). An item with no size under a per-unit canonical is compared per pack.
- Promo folding, for promos active at `as_of` for the store or chain-wide, from loaded files.
  The reward mapping follows the adapters' provisional mapping (docs/adapters.md), not yet
  verified against real files:

  | `reward_type` | Reading | Effective price per pack | `promo_min_qty` |
  |---|---|---|---|
  | `price` | `reward_value` is the promo unit price | `reward_value` | `min_qty` or 1 |
  | `percent` | 20 = 20 %, 0.2 = 20 % | `shelf x (1 - rate)` | `min_qty` or 1 |
  | `buy_x_get_y` | buy X = `min_qty` (default 1), get Y = `reward_value` | `shelf x X / (X + Y)` (1+1: half) | X + Y |
  | `bundle` | N = `min_qty` for `reward_value` in total ("3 for 20" = 6.67 each); a value below one shelf price is read per unit | `reward_value / N` | N |
  | `other` | not applied | | |

  A promo that does not lower the price is ignored. `max_qty` and daily `hours` windows are not
  applied (phase 2 MILP, with cross-item promos).
- Ranking: lowest effective unit price, then effective price, then item id.
- Club promos may win; the row then has `club_required`, `club_name` and `noclub`, the best
  option without any club promo, used by /compare for users without that club.
- Idempotent: upsert on the primary key, then rows of the processed chains not produced by the
  run are deleted. A `match_runs` row (kind `precompute`) records counts and duration.
- Measured locally on synthetic data: 3 chains x 250 stores x 300 canonicals x 4 items per
  canonical (675,000 rows) took 52 s. The full run on real data is not measured yet.

### Feedback

- `/feedback/substitution`: inserts `substitution_feedback`; `not_good` also sets
  `item_canonical.needs_review` on that (item, canonical), which takes it out of the next
  precompute until reviewed.
- `/feedback/gap`: inserts `gap_reports` (migration `20261007110000_gap_reports.sql`).
- Both accept anonymous callers and record the user id when a valid token is sent. No location.

## Auth and row-level security (#64)

- The web app signs in with Supabase Auth and sends `Authorization: Bearer <access token>`.
  The API verifies HS256 with `SUPABASE_JWT_SECRET`, requires `exp` and `sub`, checks
  `aud = authenticated`, and rejects `role = anon` tokens (401).
- For `/me/*` the request transaction runs `SET LOCAL ROLE smartcart_app` and sets
  `request.jwt.claim.sub` and `request.jwt.claims`, which `auth.uid()` reads. `smartcart_app`
  (migration `20261007110100_app_role.sql`) is NOLOGIN, not a superuser and has no BYPASSRLS, so
  the RLS policies on `profiles`, `lists`, `list_items` and `preferences` decide which rows exist,
  exactly as for PostgREST. Both settings are transaction-local and reset after the request.
- A neighborhood location is stored only with `consent_location = true` (422 otherwise) and the
  database trigger rounds it to 3 decimals (about 100 m), D11.
- Tests: `services/api/tests/test_rls_contract.py` (SQL level, through `smartcart_app`) and
  `test_me.py` (JWT to RLS: user A cannot read or write B's rows, anonymous and forged, expired
  or wrong-audience tokens are rejected, rounding). CI fails if any of them is skipped.
- The migration also grants the user tables to Supabase's `authenticated` role when it exists,
  for PostgREST.

## TypeScript client

`services/api/scripts/gen_ts_client.sh` regenerates both generated files:

1. `apps/web/src/api/openapi.json` from the FastAPI app
   (`uv run python -m smartcart_api.export_openapi`);
2. `apps/web/src/api/types.ts` with `openapi-typescript` 7.13.0 (pinned in the script, run through
   `npx`; types only, `paths` and `components`, usable with `openapi-fetch` or plain `fetch`).

Both are generated: never edit them by hand. `test_api_contract.py` fails when `openapi.json` is
stale, and the CI step "Generated API client is current" reruns the script and fails on any diff
in either file. Change `schemas.py`, then run the script and commit both files.

## Migrations added with the API

| File | What |
|---|---|
| `20261007110000_gap_reports.sql` | `gap_reports` for report-a-gap |
| `20261007110100_app_role.sql` | `smartcart_app` role and its grants; grants to `authenticated` on Supabase |
| `20261007110200_search_indexes.sql` | `search_norm()`, GIN trigram and FTS indexes on canonical names, HNSW on `item_embeddings` |
| `20261007110300_effective_prices_v2.sql` | `effective_prices.effective_price`, `promo_min_qty`, `is_estimated`, `noclub` |

`20261007100100_user_tables_rls.sql` was also fixed so it applies on Supabase, where the `auth`
schema belongs to `supabase_auth_admin` (it now creates the stand-in `auth.users` only when the
table is absent).
