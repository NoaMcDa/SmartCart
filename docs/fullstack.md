# Full-stack demo, smoke test and end-to-end suite

Until this round every layer was tested on its own and the web app had only ever talked to its MSW
mocks. `scripts/demo` runs the whole MVP for real on synthetic data, with one command: Postgres,
the migrations, the catalog seed, the chains' transparency files through the real loader and
quality gates, the matching pipeline, the nightly precompute and the FastAPI service. A smoke test
walks the API over HTTP, and a Playwright suite drives the production build of the web app against
that API. CI runs all three (`.github/workflows/fullstack.yml`).

Labels follow `docs/README.md`. Every price, store choice and saving the demo shows is
**synthetic**: the chain files are the adapters' synthetic fixtures plus a synthetic second day
written for the demo. The counts below are **verified** by running the scripts (2026-10-07, local
Postgres 16 with PostGIS and pgvector); none of them says anything about real data.

## Quickstart

```bash
uv sync
scripts/demo/up.sh                         # about 15 s; re-running is safe
uv run python scripts/demo/smoke.py        # 11 checks over HTTP, exits 1 on a failure

cd apps/web && npm ci
npm run e2e:fullstack                      # builds the app against the demo API, 6 tests
cd ../.. && scripts/demo/down.sh           # stop the API, delete the throwaway database
```

To click through it yourself: `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_MOCK=0 npm run dev` in `apps/web`, then onboarding with the city רמת גן and the
store שופרסל, and paste the demo list (below).

| Script | What it does |
|---|---|
| `scripts/demo/up.sh` | Every step below, then starts the API and writes `$SMARTCART_DEMO_DIR/env` |
| `scripts/demo/down.sh [--keep-db]` | Stops the API; stops and deletes the throwaway cluster unless `--keep-db` or `DATABASE_URL` was given |
| `scripts/demo/pg.py start\|stop\|status` | The throwaway cluster (initdb and pg_ctl, as in `services/ingest/tests/conftest.py`) |
| `scripts/demo/load_fixtures.py` | Replays every chain's fixture files through the ingestion pipeline |
| `scripts/demo/neighborhood.py` | Writes the demo's synthetic second day (three stores, dated yesterday) |
| `scripts/demo/review.py` | The demo's stand-in for the human review step |
| `scripts/demo/demo_user.py` | The demo user in `auth.users` and HS256 tokens for it |
| `scripts/demo/counts.py [--expect FILE]` | Row counts after the pipeline, compared with `expected_counts.json` |
| `scripts/demo/smoke.py` | The HTTP smoke test |

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | unset | Use this database instead of a throwaway cluster (CI points it at the service container) |
| `SMARTCART_DEMO_DIR` | `${TMPDIR:-/tmp}/smartcart-demo` | State: cluster, raw archive, logs, `load.json`, `counts.json`, `env`, API pid. As root, keep it under `/tmp`: the server runs as the `postgres` user |
| `DEMO_PG_PORT` | 54329 | Port of the throwaway cluster |
| `DEMO_API_PORT` | 8000 | API port |
| `DEMO_WEB_ORIGINS` | none | Extra CORS origins (localhost and 127.0.0.1 on 3000 and 3200 are always allowed) |
| `SUPABASE_JWT_SECRET` | the demo secret in `demo_user.py` | Secret the API verifies tokens with; the smoke test and the e2e mint with the same one |
| `DEMO_STRICT_COUNTS` | 0 | 1 fails `up.sh` when a count differs from `scripts/demo/expected_counts.json` |
| `DEMO_API_BASE_URL` | `http://127.0.0.1:8000` | Where `smoke.py` and the Playwright suite find the API |
| `FULLSTACK_WEB_PORT` | 3200 | Port of the web app under test |
| `FULLSTACK_SKIP_BUILD` | unset | 1 reuses `.next` instead of building (only a build made with the same variables) |

## The pipeline, step by step, with the expected counts

Counts are for a fresh database. A re-run of `up.sh` on the same day changes none of them
(verified: the second run's `counts.json` is identical, every file is skipped by hash, no new alert
fires, no item is pending for extraction or embedding, the review queue is empty). A re-run on a
later day adds that day's six second-day files (same prices, so no new price event).

| # | Step | Command | Expected output |
|---|---|---|---|
| 1 | Database | `pg.py start`, or `DATABASE_URL` | Postgres with PostGIS and pgvector; the throwaway cluster has `LC_CTYPE C.UTF-8` so pg_trgm sees Hebrew letters (docs/api.md, search) |
| 2 | Migrations | `smartcart-ingest migrate` | 13 migrations applied (`supabase/migrations`); 0 on a re-run |
| 3 | Catalog seed | `smartcart-catalog seed` | 203 taxonomy nodes, 222 product type rules, 245 canonicals |
| 4 | Ingestion | `load_fixtures.py` | 50 files: 41 loaded, 1 quarantined, 7 failed, 1 held; 8 alerts. 10 chains, 35 stores (24 physical with a location), 79 items, 106 price events, 37 promos, 46 promo items |
| 5 | Normalize | `smartcart-catalog normalize` | 79 items; size from the name 60, weighed 19; base units 100ml 21, 100g 39, kg 19; no issues |
| 6 | Extract | `smartcart-catalog extract --extractor rule` | 79 ok, 0 retry, 0 failed |
| 7 | Embed | `smartcart-catalog embed --target all --embedder hash` | 245 canonicals and 79 items, model `hash-ngram-2-3-4-v1` |
| 8 | Judge | `smartcart-catalog judge --judge rule` | 79 items: 29 accepted, 50 to review, 0 unmapped |
| 9 | Review | `review.py` | 50 queued, 50 accepted from the answer key, 0 left in the queue |
| 10 | Precompute | `smartcart-api precompute --as-of <second day 11:00 Israel, in UTC>` | 162 effective prices (81 any_brand, 81 close, 0 exact); 11 stores priced. With the second day on 2026-10-07: 84 rows with a promo, 16 club-only |
| 11 | Demo user | `demo_user.py ensure` | `auth.users` row `00000000-0000-4000-8000-00000000d3e0` |
| 12 | API | `smartcart-api serve` on 127.0.0.1:8000 | `/health` answers `{"status":"ok","version":"0.3.0"}` |

Step 4 per chain (fixture files plus the demo's second day; `failed` and `quarantined` are the
fixtures' deliberate bad files, which is the gates and adapters doing their job):

| Chain | Files | Loaded | Quarantined | Failed | Held | Why the others did not load |
|---|---|---|---|---|---|---|
| shufersal | 8 | 5 | 1 | 2 | 0 | v2 file of 2026-10-07 with 3 of 8 items: `item_count_drop`; an unknown schema; a truncated gzip |
| ramilevy | 4 | 3 | 0 | 1 | 0 | unknown schema |
| osherad | 5 | 4 | 0 | 1 | 0 | an empty price file the adapter rejects |
| yohananof | 3 | 3 | 0 | 0 | 0 | |
| victory | 4 | 4 | 0 | 0 | 0 | |
| hazihinam | 4 | 3 | 0 | 1 | 0 | a non-numeric price |
| tivtaam | 5 | 5 | 0 | 0 | 0 | |
| mega | 4 | 3 | 0 | 1 | 0 | a promo document named as a price file |
| machsanei_hashuk | 7 | 7 | 0 | 0 | 0 | |
| king_store | 6 | 4 | 0 | 1 | 1 | a truncated file; a promo delta for store 2, whose PromoFull never came (held, as designed) |

`counts.py` prints all of these as one JSON object, and `scripts/demo/expected_counts.json` holds
the values above, except the number of rows with a promo: the fixture chains' promotions end on
2026-10-14, so that number depends on the day the demo runs. `up.sh` warns when they differ (a GitHub warning annotation in CI) and fails only
with `DEMO_STRICT_COUNTS=1`: a change in a pipeline step that changes a count is then visible
without blocking unrelated work. Update the file when the change is intended.

### Three choices the demo makes, and why

**The clock is replayed.** The fixtures are dated 2026-10-06 and 2026-10-07. Loaded with the wall
clock, the stale-date gate (36 hours) would quarantine every one of them once that date is past,
which is the gate working. `load_fixtures.py` therefore serves the portal one file at a time, in
publication order, with the scheduler's clock at one hour after that file's publication. Nothing
else changes: each file goes through `Scheduler`, `download` (hash, tracking, raw archive),
the chain adapter, `quality.check` and `loader.load`, exactly as `tests/test_quality_adapters.py`
does it, so the item-count gate still catches the shufersal file above. The precompute then runs as
of the newest loaded file plus one hour (`as_of_utc` in `load.json`).

**A synthetic second day.** On their own the fixtures are one day of eight items spread over the
country. They cannot show a price change, a close substitute, or two nearby stores that are each
cheaper on part of a list. `neighborhood.py` writes a PriceFull and a PromoFull file for each of
three stores that the fixtures' Stores files already contain, in the chains' own dialects with the
fixture builders (`build_synthetic.py`), and they take the same path through the gates. The second
day is yesterday in Israel (never before 2026-10-07; `load_fixtures.py --day2` overrides it), and
its PromoFull files republish the day-1 promotions (same ids, so the same rows) for a window from six
days before to 13 days after it. So whenever the demo runs, the price change is inside the 90-day
history, and the promotions are active both at the precompute's clock and at the wall clock the
live routes (barcode, history) use. The fixtures' own dates stay fixed.

| Store | Distance from the demo location | Day-2 prices |
|---|---|---|
| Tiv Taam 002, Ramat Gan | 0.7 km | snacks and oil cheap, dairy, bread and produce dear |
| Machsanei Hashuk 003, Bnei Brak | 1.3 km | dairy, bread and produce cheap; also a second milk brand and a 1 kg standard loaf (a "close" substitute: pack size 1000 g against the canonical's 750 g) |
| Shufersal 001, Tel Aviv (the home store) | 3.6 km | slightly up from day 1 (milk 7.12 to 7.45: the price history) |

The two extra items use the made-up brand שדות and made-up barcodes with valid check digits.

**A scripted reviewer.** With the hash embedder (BGE-M3 cannot be downloaded here) the rule judge
sends most mappings to the review queue, and `needs_review` mappings are left out of the
precompute until a person accepts them (docs/matching.md, step E). `review.py` plays that person
with a written answer key: it reads the real queue and calls `review_app.accept`, the function the
review UI calls, only for pairs in the key, as reviewer `demo-answer-key`. It cannot accept a pair
the judge did not propose. Never run it against a real database.

## The demo world

The shopper's rounded neighborhood point is 32.085, 34.820 (Ramat Gan), radius 5 km, home store
Shufersal Tel Aviv, travel by car at ₪1.2 per km and ₪25 for an extra stop (the defaults). The list:

```
3 חלב טרי 3%, 2 קוטג' 5%, לחם אחיד, 2 ק"ג עגבניות שרי, 6 במבה, 2 שמן קנולה, 2 ק"ג בננות, 4 שוקולד מריר
```

What the API answers for it (synthetic, verified on the demo database):

| Plan | Stores | Basket | Net saving versus Shufersal |
|---|---|---|---|
| Split (recommended) | Machsanei Hashuk (5 items) and Tiv Taam (3 items) | ₪84.02 | ₪52.50 = basket saving ₪77.50 − travel ₪0 − extra stop ₪25 |
| Single store | Machsanei Hashuk Bnei Brak | ₪142.34 | ₪19.18 |
| Minimum effort | Shufersal Tel Aviv (the home store) | ₪161.52 | ₪0 |

Travel is ₪0 in the breakdown because both stores are nearer than the home store, and a plan is
never credited with a travel saving (docs/api.md). The MILP solver returns the same split. With
the bread at "close substitute" the 1 kg loaf replaces the 750 g one at Machsanei Hashuk and is
labeled.

## The smoke test

`scripts/demo/smoke.py` (standard library only) asserts, over HTTP:

1. `/health`.
2. `/parse-list` resolves all 8 Hebrew rows without a confirmation, 3 milk, 2 kg tomatoes.
3. `/search?q=קוטג` finds קוטג' 5%.
4. `/stores/nearest` finds the home store.
5. `/compare`: 3 stores, none missing an item, every line with `price_valid_from`, every store with
   `prices_updated_at`, the disclaimer "המחיר הקובע הוא בקופה.", `saving_vs_home` on every store
   and 0 for the home store.
6. `/optimize` with `solver=heuristic` and with `solver=milp`: a split exists and is the one
   recommended plan; on every plan `net_saving = basket_saving − travel_cost − extra_stop_cost`;
   the hero number is positive; the home store saves 0 against itself; every line is timestamped.
7. At "close" for the bread, a substitute line with a confidence, attribute tags and a timestamp.
8. `/items/barcode/7290004131074` at the home store: found, a price here and the cheapest nearby,
   each timestamped; the cheaper substitute, if any, labeled.
9. `/history/{milk}?store_id={home}`: at least two daily points and a price change (7.12, 7.45).
10. `/me/alerts` without a token is 401; with a demo token, `PUT /me/profile` with consent, then
    an alert is created, listed and deleted (RLS through `smartcart_app`).

## The end-to-end suite

`apps/web/playwright.fullstack.config.ts` and `apps/web/tests/fullstack/`. The web server builds the
app with `NEXT_PUBLIC_API_MOCK=0` and `NEXT_PUBLIC_API_BASE_URL` from `DEMO_API_BASE_URL`, then
serves it on port 3200; one worker, because the specs share the database. Numbers come from the
API's own answer to the browser's request, not from constants. The build replaces `.next`: run
`npm run build` again before the mock suite.

| Spec | What it drives and asserts |
|---|---|
| `journey.spec.ts` | Onboarding through its screens (device location rounded to 32.085, 34.82; Shufersal; car), the pasted list (8 rows, weighed produce labeled "מחיר משוער · שקיל", an estimate over 3 stores), the results, the split view (two stores, waterfall, net saving versus Shufersal), then the results with all three plans: the split recommended, "חוסך" with the net saving versus the home store equal to the API's breakdown, the totals, an update time on every plan, the checkout disclaimer, no "most expensive" wording |
| `substitution.spec.ts` | The bread set to "תחליף קרוב" in the flexibility sheet; the split carries one labeled substitute ("תחליף:" in the basket details); the substitution card (Machsanei Hashuk, original and substitute with prices and update times, confidence, tags with icons); "השאירי את המקורי" records `kept_original` at `/feedback/substitution`, the next comparison has no substitute and the row is pinned to "מוצר מדויק" |
| `product.spec.ts` | Product detail: two milk variants, one row per store with its update time, the home store at ₪7.45; the price history at my store with both prices (7.12 and 7.45) in the table, the update time and the disclaimer. Signed out, alerts ask for sign-in (product detail and `/alerts`). Signed in: an alert created on product detail is stored by the API for the demo user, listed on `/alerts` and deleted there |
| `scan.spec.ts` | `/scan` at 390 px: the store picker from `/stores/nearest` with the home store selected; a wrong check digit never reaches the API; the fixture barcode shows the price here (₪7.45), the cheapest nearby (₪4.90, Machsanei Hashuk) and a labeled cheaper substitute (₪4.60), each with its update time, and the disclaimer; a valid unknown code answers "לא ננחש מוצר" |

**Sign-in.** The demo has no Supabase project, so there is no Auth server to send an email code.
The build is configured with a Supabase URL on a dead port (`127.0.0.1:54321`) that the tests
answer, and a signed-in test stores a session in supabase-js storage (`sb-127-auth-token`) whose
access token is minted with the secret `up.sh` gave the API. From there everything is real: the
app reads the session, attaches the token, and the API verifies it and applies row-level
security. The email one-time-code sheet itself is not exercised.

## CI

`.github/workflows/fullstack.yml`, on every push and pull request: the `supabase/postgres:17.11.0.004`
service (as `ci.yml`), uv with Python 3.12, Node 22, `npm ci`, Chromium, then `scripts/demo/up.sh`
with `DATABASE_URL` pointing at the service, `scripts/demo/smoke.py` and `npm run e2e:fullstack`.
On failure it prints the API log and uploads the Playwright report, traces and the demo logs as
`fullstack-report`.

## Known gaps found by the suite

Found by running the real stack on 2026-10-07. Four of the five were fixed in the same completion round;
the fixes are listed so the next run of the suite can tighten its assertions.

1. **Home store after onboarding** (fixed, #101): picking a chain now resolves a concrete store through
   `GET /stores/nearest` and the results screen looks it up when it is missing, so the first results
   page shows the net saving. `journey.spec.ts` still goes through `/split` and records an annotation;
   it can assert the saving on the first results page now.
2. **Links from the results to `/split` and `/product/<id>`** (fixed, #101): the split card links to
   `/split` and each basket line to product detail.
3. **Checkout disclaimer on the substitution card** (fixed, #101): the card carries
   "המחיר הקובע הוא בקופה." like the results page.
4. **Raw attribute tags and units** (fixed): the API folds the pack-size unit into the `pack_size` tag
   ("1000 g") instead of emitting `unit` as a tag of its own (`services/api/smartcart_api/basket.py`,
   `_tags`), and the web renders tag keys, values and units in Hebrew (`apps/web/src/lib/attributes.ts`).
5. **`/scan` takes no code in the URL** (open); the test types the barcode into the manual field, which
   runs the same lookup as the camera.
