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
| `API_QUERY_EMBEDDER` | `hash` | query embedder for vector search, the catalog's `hash` or `bge-m3` (must match the stored vectors, see [GET /search](#get-search)) |

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
| `GET /me/lists`, `POST /me/lists` | required | saved lists with their items; GET also returns the lists shared with the user (`shared`, `role`) |
| `GET`, `PUT`, `DELETE /me/lists/{list_id}` | required | one list (GET: owned or shared); PUT (owner only) replaces name, recurrence and items |

Requests reject unknown fields (422). The basket routes take no user identity and store nothing.

### GET /search

Three retrievers over `canonical_products.display_name_he`, merged with reciprocal rank fusion
(`smartcart_api/search.py`, indexes in `supabase/migrations/20261007110200_search_indexes.sql`):

| Retriever | How | Catches |
|---|---|---|
| `trigram` | pg_trgm `word_similarity` of `search_norm(query)` in `search_norm(name)`, threshold 0.3, GIN trigram index | typos ("חלבב", "רסק עגבנייות") |
| `fts` | `to_tsvector('simple', search_norm(name))`, prefix terms, each word also without an attached ו/ה/ב/ל/מ/ש/כ | exact words ("והלחם" finds "לחם") |
| `vector` | pgvector cosine on `canonical_products.embedding` and on `item_embeddings` of items mapped at exact/any_brand, HNSW, minimum 0.25; only vectors of the query embedder's model | meaning, once real embeddings are loaded |

- Postgres has no Hebrew dictionary or stemmer. `simple` only lowercases, so inflection (plural,
  construct state) is left to trigram and vector retrieval. `search_norm()` folds final letters,
  removes niqqud and quote marks (`ק"ג` = `קג`), so "סלמון" and "סלמונ" match.
- pg_trgm and the text-search parser need a UTF-8 `LC_CTYPE` to see Hebrew letters as letters.
  Supabase and the CI image have one; the local throwaway test cluster runs the API tests in a
  sibling database created with `LC_CTYPE C.UTF-8` (`services/api/tests/conftest.py`).
- The query embedder is the catalog's (`smartcart_catalog.embed.get_embedder`, through
  `smartcart_api/embedding.py`), chosen by `API_QUERY_EMBEDDER`: `hash` (default), the
  deterministic 1024-dimension character n-gram `HashEmbedder` (`hash-ngram-2-3-4-v1`), a stand-in
  for BGE-M3 that captures spelling, not meaning; or `bge-m3` (needs the catalog's `embed` extra in
  the API's environment; the model loads on the first query). Vectors of two models are not
  comparable, so the vector retriever only compares canonicals whose
  `canonical_products.embedding_model`, and items whose `item_embeddings.model`, equal the query
  embedder's `model_name`. A canonical with a NULL `embedding_model` is skipped (its model is
  unknown); the catalog's `embed` job fills the column. When BGE-M3 vectors are loaded, set
  `API_QUERY_EMBEDDER=bge-m3` in the same deploy, or vector search finds nothing (trigram and
  full text keep working).
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

- `/feedback/substitution`: written through the catalog's `record_feedback`
  (`smartcart_catalog.feedback`), with `list_item_id`, `flex_level` and `match_confidence` when
  given, and `source` (`substitution_feedback.source`): `substitution_card` (default) or `swap`,
  the smart-cart swap, where apply = `accepted`, undo = `kept_original` and dismiss = `not_good`.
  `not_good` (from either source) also sets `item_canonical.needs_review` on that (item,
  canonical) unless a human already rejected it, which takes it out of the next precompute until
  reviewed. Swap verdicts count in the catalog's `rejection_rates` and in
  `beta_rejected_substitutions` like the card's.
- `/feedback/gap`: inserts `gap_reports` (migration `20261007110000_gap_reports.sql`). The reports
  feed data quality: `gap_report_pressure()` and a soft ingest warning (docs/ingestion.md,
  "Soft warning: gap-report pressure") and the dashboard's "Reported gaps" panel.
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

## Phase 2: account deletion, stores, clubs, history, shared lists, alerts, barcode (P2-A)

Issues #90, #19, #28, #34, #23 and #39. The contract additions are optional fields with
defaults, so older clients keep working; `openapi.json` and `types.ts` are regenerated.

| Route | Auth | Purpose |
|---|---|---|
| `DELETE /me` | required | delete every row of the user and the auth user (#90) |
| `GET /stores/nearest?chain_id=&lon=&lat=` | none | the nearest physical store of a chain, for "my chain" in onboarding (#90) |
| `GET /history/{canonical_id}?store_id=&days=` | none | daily price series from change events, with promo windows (#28) |
| `GET`, `POST /me/alerts`; `PUT`, `DELETE /me/alerts/{id}` | required | price-drop alerts; `active = false` pauses (#23) |
| `POST`, `DELETE /me/push-subscriptions` | required | web push subscription of this device, upsert by endpoint (#23) |
| `POST /me/lists/{id}/share` | required, owner | create an invite link with a role (#34) |
| `GET /me/lists/{id}/members` | required, owner or member | owner, invites and members (a member sees the owner and themselves) |
| `DELETE /me/lists/{id}/shares/{share_id}` | required, owner | revoke a pending invite or remove a member by the share's id (204, else 404) |
| `DELETE /me/lists/{id}/share/{token}` | required, owner | revoke an invite, and the membership it created |
| `DELETE /me/lists/{id}/members/{user_id}` | required, owner | remove a member |
| `POST /lists/accept/{token}` | required | join a shared list; returns the list |
| `GET /me/shared-lists` | required | lists shared with the user (also part of `GET /me/lists`) |
| `GET /items/barcode/{barcode}?lon=&lat=&radius_m=&store_id=&clubs=` | none | scanned product: price here, cheapest nearby, cheaper substitute (#39) |

New environment variables (never commit real values):

| Variable | Default | Meaning |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | none | Supabase Admin API for `DELETE /me`; without them see [Account deletion](#account-deletion-delete-me) |
| `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_SUBJECT` | none | web push keys (`smartcart_api/push.py`); without them alerts are recorded, not pushed |
| `API_ALERTS_FREE_LIMIT` | 10 | alerts per user in the free tier (D12; the number is a placeholder, not a decision) |
| `API_SHARE_INVITE_DAYS` | 7 | days an unaccepted invite link stays valid |
| `API_FAMILY_SHARING` | on | paid-tier flag for creating invites (D12); `0` answers 403 |
| `API_PUBLIC_WEB_URL` | first CORS origin | origin of the invite links |

| Command | What it does |
|---|---|
| `smartcart-api alerts-run [--dry-run]` | evaluate alerts against `effective_prices`, send pushes, print metrics as JSON; run after `precompute` |

### Club filtering (#19)

The rule lives in `basket.club_member` and `basket.gate_club`, used by /compare, /optimize (and
so the MILP, through `price_baskets`), the barcode lookup and the alerts job. A club-only promo
(`promos.club_only`) applies only when:

1. one of the request's `clubs` equals the promo's `club_name`, compared trimmed, with inner
   whitespace collapsed and case-folded. Credit-card deals follow the same rule (the user marks
   the card's name); or
2. the promo's club is the chain's own customer club (`מועדון לקוחות`, the adapters' name for
   regulation club code 1, or a name in `chains.club_names`) and the user marked the chain
   itself: its name (what the web app sends), `מועדון <chain name>`, or a prefix of the chain's
   name followed by a space.

A restriction that could not be parsed (no club name, `אחר`, `club <n>`) never applies, for
anyone: the safe default. The club codes are the adapters' provisional mapping, not verified
against real files.

The precompute keeps, next to the best row, `noclub` (the best price without any club deal)
and `noclub.clubs` (each club's own best deal that beats `noclub`), so a member of club A gets
A's deal even when club B's deal won the row. For a user who is not a member, the line is priced
at the best of `noclub` and the deals of the clubs they did mark: `club_required` and `club_name`
then describe that price (true only when the user's own club deal is applied), and
`club_offer_name` / `club_offer_discount` report the deal they did not mark, as information. It
never enters a total, a store ranking, an "add one more" suggestion or a saving (the D7 hero
number). Tests: `test_clubs.py` (a basket whose cheapest store changes with membership, in
/compare and /optimize, and the unparseable default).

`PricedItem.promo_confidence` is `promos.raw->>'confidence'` when the adapter recorded one
(0 to 1, or a percentage), else null. `StoreResult.lat` / `lon` come from `stores.geog`.

### Account deletion, DELETE /me

1. With `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`: `DELETE {SUPABASE_URL}/auth/v1/admin/users/{id}`
   first, before the request transaction touches a row (every user table cascades from
   `auth.users`, and holding row locks while Supabase cascades would block both). A failure
   answers 502 and nothing is deleted; 404 counts as already deleted.
2. Under RLS as the user: push subscriptions, alerts (deliveries cascade), shares they own,
   lists (items and shares cascade), profile, preferences, substitution feedback.
3. Service connection: their memberships in other lists and the items they added there;
   `gap_reports.user_id` and `events.user_id` set to NULL (kept as anonymous statistics).
4. Without the Admin API settings, the stand-in `auth.users` row is deleted (local, CI). On
   hosted Supabase the log line `auth user not deleted` means the user must be removed by hand:
   Supabase dashboard, Authentication, Users, delete. The hosted path has not been run against a
   real project yet.

### GET /stores/nearest

PostGIS KNN (`ORDER BY geog <-> point`) over the chain's physical stores with a location; 404
when there is none. Returns a `StoreRef` with `distance_m`, `lat`, `lon`.

### GET /history/{canonical_id}

- Item: with `store_id`, the item of that store's chain mapped `exact` when there is one, else
  the store's best `any_brand` item in `effective_prices`; without `store_id`, the best
  `any_brand` item over all stores, as its chain's base price. Fallback: the most confident
  mapped item with prices. `item_id` and `display_name_he` say which.
- Series: one point per day of the last `days` (default 90, 1 to 365), the price in force at the
  end of the day with `current_price()` semantics: the store's latest event overrides the chain
  base price, `store_id` on the point says which applied (null = chain base). Only loaded files
  count. Days before the first known event are absent: a gap, not a flat line.
- `unit_price` is the shelf unit price in the canonical's base unit (D6); promos are reported
  separately: `promos` lists the promo windows (chain-wide, plus the store's with `store_id`)
  overlapping the range, with `promo_type`, `club_only`, `club_name` and `confidence`; each
  point's `promo_description` names the promo active that day (a club one is suffixed with its
  club).
- Plan: both event queries filter `item_id`, `store_id` and a `valid_from` range, so they prune
  to the range's monthly partitions and use `prices_event_key`; the price in force at the start
  is one backward index scan with `LIMIT 1`.
- Measured locally on the test world: 90 days for one store in about 20 ms (one run, small
  data; not measured on real data). The paid-tier history limit (D12) is not implemented yet.

### Shared lists (#34)

- Invite: `secrets.token_urlsafe(32)`; only its SHA-256 is stored in `list_shares.invite_token`.
  Link `{API_PUBLIC_WEB_URL}/lists/accept/{token}`, valid `API_SHARE_INVITE_DAYS` days
  (`list_shares.expires_at`). Single use: accepted by another user 409, revoked 404, expired 410.
- Accepting runs on the service connection (a pending invite is invisible to the invitee under
  RLS), then the list is read back under RLS as the member.
- Members list: every invite and membership row has `share_id` (`list_shares.id`, an identity
  column; null for the owner's row). The owner revokes a pending invite, whose token only the
  invitee has, or removes a member with `DELETE /me/lists/{id}/shares/{share_id}`; the path's
  list must match, others get 404. The token and member-id routes stay.
- `GET /me/lists` returns the user's own lists first, then the accepted shared lists, each group
  newest first. `ShoppingList.shared` is true for a list someone else owns and `role` is `owner`,
  `editor` or `viewer`. `GET /me/lists/{id}` reads a shared list too; PUT and DELETE stay
  owner-only (404 for members). Pending invites show nothing.
- `ListItem.checked` (`list_items.checked`, default false) is ticked off in the store. The API
  persists it on create, replace and read; members tick items through PostgREST under the
  unchanged `list_items` policies (owner and editors update, viewers cannot).
- RLS (migration `20261008100100_shared_lists_rls.sql`): list items follow their list. The
  owner (`owns_list()`) and accepted members (`is_list_member()`) read; the owner and editors
  insert, update and delete; a new row must carry the writer's own `user_id`; viewers cannot
  write; strangers see nothing. This replaces the phase 1 `list_items_own` policy, which let
  anyone add rows to any list under their own user id and hid members' items from the owner.
  Only the owner changes or deletes the list itself and manages `list_shares`; a member sees
  their own share row only. Profiles and preferences stay owner-only, so members never see each
  other's location or preferences (tested).
- Members edit items through Supabase PostgREST and get changes through Realtime (the phase 2
  migration adds `lists` and `list_items` to `supabase_realtime`); the conflict rule and offline
  merge are the web workstream's.

### Alerts and web push (#23)

- An alert takes the profile's neighborhood (consent required, else 422) and is stored rounded
  to 3 decimals. `PUT` re-arms it (`last_fired_at` reset) when the product, level or threshold
  changes.
- `alerts_job.evaluate_alerts(conn, sender)`: for each active alert, `effective_prices` rows of
  its canonical at its flexibility level at physical stores within `radius_m` (PostGIS
  `ST_DWithin`), gated by the user's profile clubs as above; fires on the lowest effective unit
  price at or below the threshold. De-duplication: at most once per 24 hours, and never again for
  the same item and store unless the price went lower. A firing inserts `alert_deliveries`
  (`push`, or `log` without keys or subscriptions), sets `last_fired_at` and pushes to each
  subscription; 404 or 410 deletes the subscription.
- The push payload: product, store, price with `₪` and a non-breaking space, update time,
  "המחיר הקובע הוא בקופה", deep link `/product/{canonical_id}`, tag `alert-{id}`.
- The job reads every user's alerts, so it needs a connection that bypasses RLS (the Supabase
  `postgres` or service role). Push delivery to real devices (Android Chrome, iOS 16.4+ PWA) is
  not verified yet: it needs real VAPID keys.

### GET /items/barcode/{barcode}

- Lookup: `items.barcode` in any chain (also without leading zeros and padded to EAN-13), then
  `item_canonical` at `exact` or `any_brand`, not `needs_review` or `human_rejected`. Unknown or
  unmapped codes answer `found = false` (with the item's name when known), never a guess (D5).
  A code in `canonical_products.reference_barcodes` resolves to that canonical without prices.
- `here` and `cheapest_nearby` price the scanned product itself, live (precompute rules, club
  rule with `clubs`), at `store_id` and at the physical stores in the radius.
- `cheaper_substitute`: the lowest `any_brand` effective unit price nearby for another barcode,
  only when it beats the scanned product's unit price (`here`, else `cheapest_nearby`); labeled
  `is_substitute` with its mapping `confidence` and `tags` comparing its attributes with the
  canonical's critical attributes and the scanned product's soft ones (brand, pack size).
- The scan is logged (found, time to answer), never with the location.

### Migration

| File | What |
|---|---|
| `20261008100100_shared_lists_rls.sql` | `owns_list()`, list item policies by list (owner, editor, viewer), `list_shares.expires_at` |
| `20261009100000_mvp_followups.sql` | `list_shares.id` (identity, unique), `list_items.checked`, `substitution_feedback.source`, `gap_report_pressure()` and the `quality_gap_reports_7d` view, `quality_warnings` |

## Events: phase 2 surfaces (#101, #102)

`POST /events` accepts eight more names (`EVENT_PROPS` in `routes/events.py`, the `EventName`
enum in `schemas.py`). Like the others they carry counts and fixed values only: no barcode, item
id, price, list id or token. Every prop is optional except `scan_completed.outcome`.

| Event | Props |
|---|---|
| `scan_started` | `engine`: `native`, `zxing`, `manual` |
| `scan_completed` | `outcome` (required): `found`, `not_found`, `no_price`, `cancelled`, `error`; `duration_ms` 0 to 600000; `engine` |
| `alert_created` | `flex_level`; `source`: `product`, `alerts` |
| `swap_applied` | `flex_level`; `saving_agorot` 0 to 100000 |
| `swap_undone`, `swap_dismissed` | `flex_level` |
| `list_shared`, `share_accepted` | `role`: `editor`, `viewer` |

Tests: `test_api_events.py` stores each with its props and rejects other keys and values.

## Phase 3: recipe to list, budget and spend, promo cycles, voice events (#71, #70, #69)

Built on synthetic data and the seeded catalog only; nothing here has run against real files.
The contract additions are new routes and optional fields, so older clients keep working;
`openapi.json` and `types.ts` are regenerated.

| Route | Auth | Purpose |
|---|---|---|
| `POST /parse-recipe` | none | a Hebrew recipe (pasted text or one page) to basket rows (#71) |
| `GET /me/spend?month=YYYY-MM` | required | the month's spend entries, their total and the budget (#70) |
| `POST /me/spend` | required | record a shopping trip; 201 with the entry and its `id` |
| `PUT`, `DELETE /me/spend/{id}` | required | correct an entry (the actual checkout total replaces the estimate), or remove it (204) |
| `GET /me/spend/export` | required | every spend entry and the budget: the user's copy of their spend data |
| `GET /promo-cycles/{canonical_id}?clubs=` | none | when a promo is likely to return, per chain (#69) |

`PUT /me/profile` gains `monthly_budget` (ILS, 2 decimals, at least 0). It is written only when
the request names it: a client that omits the field keeps the stored budget (the existing
onboarding and settings screens PUT the profile without it), an explicit `null` clears it.
`GET /me/profile` returns it.

### POST /parse-recipe

Request `{text?, url?, servings?}`, exactly one of `text` and `url` (else 422); `servings` 1 to
100. Response `{title, servings, items: ParsedRow[], unresolved: string[]}`. Code:
`routes/recipe.py`, `recipe_fetch.py`, and the catalog's parser `smartcart_catalog/recipe.py`
(rules and tables in [catalog.md](catalog.md#7-recipe-parser-71)).

1. **Read.** Text goes to the rule parser. A `url` is fetched (below) and read from its JSON-LD
   `Recipe` (`recipeIngredient`, `recipeYield`, `name`), else from the visible text under an
   ingredients header ("מצרכים"); a page without either yields no items. No LLM is used or needed.
2. **Merge and scale.** The same ingredient twice is one row (`input_text` joins the lines with
   ` + `). With `servings` and a known recipe yield the amounts are scaled; `servings` in the
   response is the number the quantities are for, the recipe's own yield when none was asked, or
   null when the yield is unknown (then nothing was scaled).
3. **Resolve.** Each ingredient goes through the `/parse-list` matcher (`routes.search.resolve`,
   the same retrievers, ambiguity cap, candidates and flexibility defaults). The floor is stricter
   than /parse-list: a best hit under **0.70** goes to `unresolved` with its line, not to a
   confirmation prompt, because recipe words are not written for our catalog ("יין לבן" shares a
   word with "קמח לבן", "סודה לשתייה" with soda water). Two equally good canonicals ("חלב", 3 % or
   1 %) are capped at exactly 0.70 by the matcher and stay as a row with `needs_confirmation` and
   candidates. The 0.70 floor is an estimate from the ten-recipe fixture, not a measured precision.
4. **Quantity.** `quantity` follows /parse-list: kilograms with `unit = "kg"` for canonicals sold
   by weight (rounded up to 50 g), else whole packs of the canonical's typical pack size
   (`canonical_products.soft_attrs.pack_size`), rounded up. "200 גרם גבינה" with a 250 g pack is
   1; 600 g of spaghetti in 500 g packs is 2. The original amount stays visible in `input_text`.
   An amount the tables cannot convert (no density, no piece weight, no pack size, slices of a
   packaged product) keeps one pack or one kilogram and sets `needs_confirmation`.
5. **Unresolved.** Lines left to the user, in order: what the parser set aside (tap water, ice,
   "to taste" or "as needed" without an amount such as "מלח לפי הטעם", optional ingredients),
   then ingredients the matcher did not find. Nothing is dropped silently and nothing is guessed.

Every row has a canonical; `confidence >= 0.70`; `is_weighed` exactly when `unit = "kg"`.
Pantry staples are not filtered by default: salt with an amount is a row, salt "to taste" is
unresolved. A pantry toggle (issue #71) is a client-side filter on the rows.

**Fetching a URL** (`recipe_fetch.py`): http or https on the default ports, no credentials in the
URL, and the host must resolve to public addresses only (loopback, private, link-local,
multicast, reserved and unspecified are refused with 422 before any request). Only the given
page is fetched: no links are followed, at most 3 redirects, each checked like the first URL.
5 s timeout per phase and in total, 2 MB body cap, HTML or plain text only. A site error or
timeout answers 502. The fetcher is a FastAPI dependency (`get_fetcher`), so the tests use a
fake and never touch the network. Known limit: the address is checked before httpx connects,
so DNS rebinding is not caught in the process; deploy the API with egress limited to the public
internet.

Tests: `test_recipe.py`, ten Hebrew recipes (`tests/fixtures/recipes.json`: headers or not,
fractions, ranges, word amounts, pack units, cloves, weights in parentheses, amounts after the
name, JSON-LD and plain-HTML pages, scaling up and down) against the seeded MVP catalog with
hash embeddings, plus the fetch rules with an `httpx.MockTransport`.

### POST /parse-image (#61, #68)

A photo of a receipt or a handwritten list to rows. `multipart/form-data` with `kind`
(`receipt` or `list`) and `image` (JPEG, PNG or WebP, at most 8 MB). Required header:
`X-Image-Consent: 1` (the user agreed to photo processing; it is not in `openapi.json`).
Response `{kind, provider, items: ParsedRow[], unresolved: string[], receipt, deleted: true}`;
`receipt` is `{chain_hint, store_hint, total, lines: [{text, quantity, price}]}` for a receipt and
null for a list. Full design, privacy guarantee, caps and evaluation: [ocr.md](ocr.md). Code:
`routes/image.py`, `ocr/`, and the catalog's `receipt.py`.

| Status | When |
|---|---|
| 200 | read; `items` resolved like `/parse-list` (low confidence carries `needs_confirmation`), `unresolved` are lines read but not matched (best hit under 0.70, never guessed) |
| 403 | no `X-Image-Consent: 1`; the body is not read |
| 413 | body over 8 MB, or an image over 25 megapixels |
| 415 | not JPEG, PNG or WebP (by magic bytes, not the client's content type) |
| 422 | the image cannot be decoded, is empty, or `kind` is invalid |
| 429 | the monthly cap was reached (`OCR_MONTHLY_IMAGE_CAP`, default 2000, or `OCR_MONTHLY_USD_CAP`, default 20, estimated) |
| 502 | the OCR provider failed or declined |
| 503 | no OCR provider configured (`OCR_PROVIDER`: `auto`, `fake`, `tesseract`, `claude`) |

The photo is rotated by its EXIF orientation and downscaled to 2400 px on the long side, read in
memory, and never written to disk, logged or stored; `deleted: true` states it. Only a monthly
count and cost estimate are kept (`ocr_usage`, no user id). Receipts: quantity is the printed one
(`unit = "kg"` for weighed goods), repeated products merge, and a till's brand and pack size are
tried with and without (the catalog is "any brand"). List photos read by Tesseract mark every row
`needs_confirmation`. The web client sends the consent header only after the user's consent
screen and shows what was read next to the photo.

| Variable | Default | Meaning |
|---|---|---|
| `OCR_PROVIDER` | `auto` | `auto` (claude when `ANTHROPIC_API_KEY` is set, else tesseract when installed with the `heb` data, else 503), `fake`, `tesseract`, `claude` |
| `OCR_MONTHLY_IMAGE_CAP` | 2000 | images per calendar month (UTC) |
| `OCR_MONTHLY_USD_CAP` | 20 | estimated dollars per month |
| `OCR_CLAUDE_MODEL` | `claude-sonnet-5-5` | model of the vision provider |
| `ANTHROPIC_API_KEY` | none | enables the Claude provider |

Migration: `20261011100000_ocr_usage.sql` (`ocr_usage(month, provider, images, est_cost_usd)`, RLS
on with no policy). Tests: `test_api_image.py` (consent, round trips, cap), `test_api_image_limits.py`,
`test_api_image_privacy.py`, `test_api_image_providers.py`, `test_api_image_eval.py`, and the
catalog's `test_receipt_structuring.py`.

### Budget and spend (/me/spend)

- Entry: `{id, date, store_id, store_name, total, item_count, plan: "single" | "split"}`. `total`
  is what the client sends: the app's estimate when a list is marked as purchased, or the actual
  checkout total the user typed, which replaces it (`PUT`). The estimate label and the net-saving
  explanation (D7) are the screen's; the API stores the number. An unknown `store_id` is 422.
- Month: `{month, entries (oldest first), total, budget}`; `month` defaults to the current UTC
  month; `budget` is `profiles.monthly_budget` or null. Decimals are strings in JSON.
- RLS: `spend_entries` has `spend_entries_own` (`user_id = auth.uid()`, forced), so the routes
  run on `user_conn` like the other `/me` routes. Tests (`test_spend.py`): user A cannot read,
  change or delete B's entries over the API, and at SQL level through `smartcart_app` (including
  an insert with another user's id, refused by the policy).
- Privacy (D10, D11): spend data never enters `events` and is never sent anywhere. `DELETE /me`
  deletes the user's `spend_entries` under RLS and the profile (with the budget);
  `test_me_delete.py` checks both. The auth cascade removes them on Supabase too.

### GET /promo-cycles/{canonical_id}

`{canonical_id, chains: [{chain_id, chain_name, cycles_seen, median_gap_days, confidence,
last_promo_ends, next_expected_from, next_expected_to, advice}]}`, one entry per chain with promo
history for the canonical, by chain id; 404 for an unknown canonical. Dates are Israel-local days
(`YYYY-MM-DD`). The method, the thresholds (estimates) and the limits are in
[promo-cycles.md](promo-cycles.md). In short: below 3 cycles or a confidence of 0.6 the window is
null and `advice = "unknown"`; `wait` means the next window opens within 14 days; `buy_now`
means a promo is running or none is expected soon. Club-only promos count only for clubs passed
in `clubs` (repeatable), with the /compare club rule (`basket.club_member`). It reads `promos` per
request and is not on the compare or optimize path.

### Events: voice list

`POST /events` accepts two more names. No transcript, no audio, no item text.

| Event | Props |
|---|---|
| `voice_started` | `engine`: `web_speech`, `server`, `manual` |
| `voice_completed` | `outcome` (required): `parsed`, `empty`, `cancelled`, `error`; `duration_ms` 0 to 600000; `item_count` 0 to 200 |

### Migration

| File | What |
|---|---|
| `20261010100000_phase3.sql` | `profiles.monthly_budget numeric(10,2)`; `spend_entries` with own-rows RLS (forced), grants to `smartcart_app` and, on Supabase, `authenticated` |

## Cart handoff to chain online stores (#72)

### GET /chains/online

One row per chain: `chain_id`, `chain_name`, `online_url`, `search_url_template`, `enabled`,
`referral` (the `ChainOnline` schema). Public (no auth) and sent with
`Cache-Control: public, max-age=3600`.

- `enabled` is the per-chain feature flag: the chain id is in `CART_HANDOFF_CHAINS` (comma separated
  env var, default empty, so every row is disabled) **and** the chain has an `online_url`.
- `online_url` and `search_url_template` come from `chains` (https only; the template must contain
  `{q}`, checked by the database). They are links for the user's browser to open. The API never
  requests them (CLAUDE.md: no scraping of chain online stores). `referral` is `chains.online_referral`.
- Ranking never reads any of this: `/compare` and `/optimize` are byte-identical with the flag and the
  referral flags on or off (`tests/test_api_handoff_independence.py`).

See [cart-transfer.md](cart-transfer.md) for the seeded addresses (all unverified), why this is not
scraping and what an official cart-prefill integration needs.

| Variable | Default | Meaning |
|---|---|---|
| `CART_HANDOFF_CHAINS` | empty | chain ids whose handoff is on |

### Migration

| File | What |
|---|---|
| `20261011100100_chain_online.sql` | `chains.online_url`, `chains.search_url_template` (CHECK: https and `{q}`), `chains.online_referral boolean NOT NULL DEFAULT false`; `chain_online_seed` and a `BEFORE INSERT` trigger on `chains` that fills seeded addresses into rows the ingest loader creates later |

Tests: `test_api_chains.py`, `test_api_handoff_independence.py`.
