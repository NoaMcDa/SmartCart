# Status of phases 0, 1 and 2, and the owner runbook

Written 2026-10-07 on `phase-2-base` (commit `c36d6b3`), updated the same day on `mvp-complete` after
PR #100 (phases 0 to 2) and the MVP completion round (#101, #102, #16, #12 and the full-stack suite), and
on 2026-10-08 after the unblock round (manual workflows on GitHub runners, deploy packaging, phase 3
features that need no real data; see [unblock.md](unblock.md) and [deploy.md](deploy.md)). It
answers two questions: what is done, and what only the owner can do next. Sources: the status comments on
issues #1 to #7, the bodies of PR #82 (phase 0), PR #100 (phases 0 to 2) and the MVP completion PR, and
the docs named in each row.

Labels follow `docs/README.md`: **verified** means shown by a test or a measurement, **estimate** means a
judgement. Every cost and time figure below is an estimate unless it says otherwise.

## How to read the table

| Status | Meaning |
|---|---|
| **done by tests** | The acceptance criteria are met by tests that run in CI, or by a written decision. Nothing here depends on real data. Where a manual check on a device remains, the note says so. |
| **done with synthetic data** | Built and tested, but only against synthetic fixtures, a synthetic gold set or a mock API. The behavior is real, the numbers are not. It needs the real-data steps in the runbook before any figure from it is quoted. |
| **blocked** | Needs something that only the owner can supply: infrastructure, an API key, real files, a reviewer, a domain, a device or people. The blocker column says which. |
| **open, phase 2** | Engineering work that is not finished and is not waiting on the owner. After the MVP completion round no row carries this label; it stays in the legend for the next round. |

Numbers that appear below are quoted from the status comments: 780 Python tests (2 skipped) and 321 unit,
95 e2e and 131 accessibility web tests were green in CI on `phase-1-base`. All are on synthetic data.

## Phase 0, data foundation (milestone 1)

| Issue | Title | Status | Blocker or what remains |
|---|---|---|---|
| #1 | Epic: data foundation | blocked | Every child is built; #14, #22 and #60 wait on provisioning and two weeks of real nightly loads, and #32, #53, #57 and #81 wait on real files. |
| #9 | Chain list (8 to 10 chains) | done by tests | Decision D13, no code. The chain size tiers are an estimate: replace with a sourced figure before any public coverage claim. |
| #14 | Supabase vs self-hosted, provision the database | blocked | The project does not exist. One token: `scripts/unblock/supabase_provision.py` creates it and enables the extensions (`infra-provisioning.md` section 9.1); then set `SUPABASE_DB_URL` and run the "Provision check" workflow. The restore test record (section 4.4) waits for real rows. |
| #17 | Monorepo scaffold and CI | done by tests | All five items met. The last one, "a failing test turns CI red", was exercised once on the throwaway branch `ci/red-check` (commit `fba9fd7`, never merged): run https://github.com/NoaMcDa/SmartCart/actions/runs/37621263324 ended `failure` in the Test step on Python 3.12 and 3.13, with Lint green. Delete the branch with `git push origin --delete ci/red-check` if it still exists (the build environment could not). |
| #22 | Israeli-IP VPS and object storage | blocked | Owner buys the VPS and bucket (about one person-hour, estimate), sets `VPS_SSH_HOST`, `VPS_SSH_KEY` and the `S3_*` secrets, and runs "Provision check", which runs the three smoke scripts against the live services. The deploy workflow then installs ingestion, the API and its timers (`deploy.md`). |
| #27 | Schema v1 | done by tests | Six of six criteria pass in CI on `supabase/postgres:17.11`. |
| #32 | Adapter framework, one adapter per chain | done with synthetic data | Eight adapters on synthetic fixtures. Real files need the VPS (`fetch_fixtures`). Archiving raw files to the bucket is not wired into the adapters. |
| #37 | Idempotent downloads, full before delta | done by tests | The real portals are unchecked until the VPS runs. |
| #42 | Quality gates and quarantine | done by tests | Thresholds are the defaults from the issue, an estimate. Revisit after real publication delays are seen. |
| #46 | Ingestion dashboard | done by tests | Verify the `smartcart_readonly` role and the numbers on the real project. |
| #49 | Hourly deltas for the main chains | done by tests | Delta polling still has to be watched against the real portals on the VPS. |
| #53 | Online-store record and channel tag | done with synthetic data | Every per-chain rule and the placeholder store codes are provisional until real Stores files confirm them. Osher Ad is listed as having no online record (to confirm). |
| #57 | Dual schema (v1 and v2) | done with synthetic data | `PROVISIONAL_V2_MARKER` is a placeholder. A real file in the authority's new model is needed to confirm it. |
| #60 | Phase 0 exit validation | blocked | Fourteen consecutive nightly loads on the VPS after #14 and #22. Meanwhile "Portal probe" runs daily from a GitHub runner: on 2026-10-08 seven of ten chains (Shufersal, Rami Levy, Mega/Carrefour, Tiv Taam, Osher Ad, Yohananof, King Store) handed over real Stores and PriceFull files; Victory and Machsanei Hashuk timed out and Hazi Hinam answered 403 to the non-Israeli IP. Go/no-go stays NO-GO. |
| #81 | Adapters for Machsanei Hashuk and King Store | done with synthetic data | Both adapters are built on synthetic fixtures (laibcatalog JSON and Bina layouts) and covered by the quality-gate adapter test; all ten D13 chains load in `scripts/demo/up.sh`. Real files need the VPS (`fetch_fixtures`). |

## Phase 1, MVP (milestone 2)

| Issue | Title | Status | Blocker or what remains |
|---|---|---|---|
| #2 | Epic: catalog and matching | blocked | Real data, `ANTHROPIC_API_KEY`, BGE-M3 run, reviewer sign-off (#15, #25, #29, #38). |
| #3 | Epic: backend API | done with synthetic data | Every route is built and tested. Search needs real BGE-M3 vectors for its meaning-only criterion (#54). |
| #4 | Epic: web app | done by tests | Verified against the mock API. Device installs, a visual pass in both themes and the real API remain (see #11, #66, #91). |
| #5 | Epic: trust and compliance | blocked | Screen-reader pass, legal reviews, `DELETE /me` (#26, #30, #90). |
| #6 | Epic: SEO, growth and beta | blocked | A deployed domain, real prices, people (#35, #40, #44). |
| #10 | Taxonomy v1 | done by tests | 203 nodes. The 19 departments are our own list, not Hazol's (the research does not list Hazol's categories). The reviewer should compare. |
| #11 | Next.js PWA scaffold | done by tests | Install on a real Android Chrome and iOS Safari device by hand (steps in `docs/web.md`). |
| #12 | Trust signals | done by tests | Promo confidence is recorded by every adapter (`promos.raw.confidence`, rubric in `docs/adapters.md`) and shown when present. The substitution card carries the checkout disclaimer; every substitute is labeled. |
| #15 | 150 to 300 canonical products | blocked | Person-hours: a domain-aware reviewer signs off the 245 canonicals (`catalog.md` section 2). The rank is an estimate until real data loads. |
| #16 | Report-a-gap button | done by tests | UI and `POST /feedback/gap`; gap reports feed the quality checks (`gap_report_pressure`, the `quality_gap_reports_7d` view, a soft ingest warning that never quarantines, a dashboard panel). The threshold `GAP_REPORT_PRESSURE_MIN=3` is a placeholder. |
| #18 | Onboarding | done by tests | Eye check of dark theme at 390 px. |
| #20 | Rule normalization | done with synthetic data | 50 table cases with realistic, not real, names. Turn the issue list from `smartcart-catalog normalize` on real loads into test cases. |
| #21 | Methodology page and quality metric | done with synthetic data | The published metric comes from the synthetic gold set and is labeled so. Links from results and the substitution card are open (#91). Structured data has not been run through an external validator. |
| #24 | List builder | done by tests | Against the mock API. The estimate's reaction to a flexibility change needs the real API. |
| #25 | LLM attribute extraction | blocked | One secret: set `ANTHROPIC_API_KEY` and run the "Extraction pilot" workflow (default 200 synthetic items, about 0.40 to 0.60 USD, estimate). Then read the comparison and confirm or change D14. The full-catalog cost run waits for loaded items. |
| #26 | Accessibility audit (Israeli standard 5568) | blocked | Human only: the Hebrew screen-reader pass (VoiceOver, TalkBack) and a legal read of the statement. The 195 px overflow is closed (#101); the non-drag split path and a contact detail on the statement page remain as small engineering items. Automated coverage is complete; it is not a conformance claim. |
| #29 | BGE-M3 embeddings, blocking, HNSW | done with synthetic data | BGE-M3 ran on a GitHub runner on 2026-10-08 ("BGE-M3 evaluation" workflow, full synthetic gold set): any-brand precision 1.00, any-brand recall 0.92 (hash embedder: 0.81), retrieval recall@10 0.998. Synthetic numbers; the thresholds are hash-calibrated. The real-data recall needs real labels (#38) and the search switch to `API_QUERY_EMBEDDER=bge-m3` follows the real embed. |
| #30 | Privacy by design | blocked | Legal review of the privacy text only (`DELETE /me` is done, #90). |
| #31 | Flexibility bottom sheet | done by tests | Soft-attribute checkboxes are stored on the row; the API has no field for them yet, so they do not change matching. |
| #33 | Match judge with hard rules | done with synthetic data | The LLM judge is wired and tested but never measured (no key). Compare it with the rule judge on the real gold set. |
| #35 | Static SEO pages | blocked | A domain and host (owner), `NEXT_PUBLIC_SITE_URL`, a decision on `INDEX_UNPRICED`, then the sitemap in Search Console. The web container and the Vercel config are ready (`deploy.md`). Offers need real prices. |
| #36 | Comparison results screen | done by tests | Against the mock API (the mock prices every flexibility level the same). |
| #38 | Review UI, gold set, evaluation harness | done with synthetic data | The CI gate passes at 1.00 any-brand precision on 2,419 synthetic pairs (recall 0.81). Real labels and the human review of the 300 best-sellers are pending. |
| #40 | Closed beta, 20 to 50 users | blocked | Confirm the thresholds, a legal review of the consent text, recruit 20 to 50 people. Needs real prices first. |
| #41 | Cart split view | done by tests | Touch drag onto the other tab is to verify on a device. Keyboard and button paths are in e2e. |
| #43 | Feedback loop | done by tests | Context columns and RLS are in the phase 2 migration; see #92. No rejection rate exists until the beta. |
| #44 | Monthly basket index | done with synthetic data | No month can be published until real prices load. Basket composition and check thresholds are estimates. |
| #47 | Nightly effective-price precompute | done with synthetic data | 675,000 rows in 52 s on the small synthetic world and 144,380 rows in 27 to 33 s on the scaled one (`optimizer.md`), synthetic data only. The VPS timer exists (`infra/vps/smartcart-precompute.timer`, 09:30 Israel time after the full sync). Promo reward semantics are provisional until real promo files are seen. |
| #48 | Substitution card | done by tests | Against the mock API; the original's price at the substitute's store is not in the API response. |
| #50 | Product detail | done by tests | Promo confidence needs the API field (#90). Visual check of RTL, themes and targets. |
| #51 | POST /parse-list | done with synthetic data | Resolves against the synthetic catalog; re-check on the real one. |
| #54 | GET /search | done with synthetic data | Meaning-only criterion needs real BGE-M3 vectors and a one-line switch in `smartcart_api/search.py`. Latency measured on the test catalog only. |
| #55 | Profile and preferences | done by tests | Full account deletion needs `DELETE /me` (#90). |
| #58 | POST /compare | done with synthetic data | Totals and savings are correct by test; real numbers need the pipeline. |
| #59 | Map view | done by tests | Pins use distance plus an approximate bearing until the API returns store coordinates (#90). |
| #62 | POST /optimize (heuristic) | done by tests | Matches an exhaustive reference in 12 combinations. The walk and transit cost per store is an estimate. |
| #63 | Dark mode | done by tests | Syncing the choice to the profile waits on auth wiring (#91). |
| #64 | Supabase Auth, RLS, user tables | done by tests | RLS runs through a non-superuser role in CI. PostgREST itself is not in CI. Pick the Auth provider settings when the project exists. |
| #66 | In-store shopping mode | done by tests | Visual check in both themes; Wake Lock is not testable in CI. |
| #67 | Generated TypeScript client | done by tests | CI fails on drift. |
| #80 | Loader: chain-level base prices | done by tests | The price-jump gate does not compare base records yet. |
| #90 | API follow-ups | done by tests | `DELETE /me`, store coordinates, promo confidence and `GET /stores/nearest` are implemented (PR #100 and the completion round). |
| #91 | Web follow-ups | done by tests | All items landed in PR #100; the remaining loose ends became #101 and are done (below). |
| #92 | Catalog contract follow-ups | done by tests | Columns and the catalog code that reads and writes them landed in PR #100; the remaining items became #102 and are done (below). |

## Phase 2, advanced savings (milestone 3)

All built in PR #100 and finished in the MVP completion round. Only #52 and #56 are blocked, on real data
and real users.

| Issue | Title | Status | Blocker or what remains |
|---|---|---|---|
| #7 | Epic: advanced savings | done with synthetic data | Children below. |
| #13 | MILP cart optimizer | done with synthetic data | OR-Tools CP-SAT with cross-item promos and quantity rounding (`docs/optimizer.md`). Equals the heuristic without bundles and beats it on the bundle case, by test. Solve times were measured on synthetic baskets only; re-measure on real price files. |
| #19 | Club membership filtering | done by tests | Club-only promos apply only when the user's clubs include the club, across `/compare` and `/optimize`. |
| #23 | Price-drop alerts with web push | done with synthetic data | Alerts CRUD, `alerts-run` job, pywebpush sender tested with a fake. Needs the VAPID key pair (runbook step 11) and the real pipeline to fire on real drops. |
| #28 | Price history, 90 days | done with synthetic data | Series from the price change events with promo markers; the chart is a small SVG component. Real history needs weeks of real loads. |
| #34 | Shared family lists in real time | done with synthetic data | Invite link, accept, members, revoke by `share_id`, per-item `checked`, offline queue, Supabase Realtime with a polling fallback. Realtime itself needs the real project. |
| #39 | Barcode scanning in the PWA | done by tests | BarcodeDetector with a ZXing fallback and a manual field; the lookup joins to effective prices in the radius. Device check of the camera flow remains. `/scan` reads no code from the URL yet. |
| #45 | Smart cart: single best swap | done by tests | Swap suggestions, apply, undo and dismiss (dismissal holds until the saving changes by ₪1 and 25%); verdicts stored as catalog feedback with `source=swap`; a dismissal never flags the mapping for review. |
| #52 | Catalog expansion with active learning | blocked | Real labeled pairs (review UI and the beta's rejections). Time-bound. |
| #56 | Native app decision | blocked | Retention data from real users. Time-bound. Not a build task. |

## MVP completion round (2026-10-07)

Four parallel workstreams on `mvp-complete`, merged in one PR to `main`.

| Issue | Title | Status | What landed |
|---|---|---|---|
| #101 | Phase 2 follow-ups, web | done by tests | "שיתוף" entry point; swap undo and dismiss; every route fits at 195 px (`docs/a11y-report.md`); onboarding resolves the home store through `GET /stores/nearest` so the first results page shows the net saving; pending-invite revoke; `checked` flag with an offline queue ("ממתין לסנכרון"); scan, alert, swap and share events; links from results to the split view and product detail; checkout disclaimer on the substitution card; Hebrew labels for attribute tags and units. |
| #102 | Phase 2 follow-ups, API and catalog | done with synthetic data | `GET /me/lists` returns owned then shared lists (`shared`, `role`); `share_id` on members and `DELETE /me/lists/{id}/shares/{share_id}`; `base` is a critical attribute of the plant drinks (three canonicals changed, 104 gold pairs added, precision 1.00 at every level on the synthetic set); SEO snapshot regenerated; query vectors compared only with embeddings of the same model (`API_QUERY_EMBEDDER`); `routes/feedback.py` writes through `record_feedback`; adapters record promo confidence. Optimizer timings on real files remain. |
| — | Full-stack run and suite | done with synthetic data | `scripts/demo/up.sh` builds the whole pipeline on the synthetic fixtures through the real loader and gates, `smoke.py` checks the real API, `npm run e2e:fullstack` drives the real app against the real API, and the "Full stack" workflow runs it in CI. `docs/fullstack.md` lists the counts and the gaps it found. |

## Unblock round (2026-10-08)

Blocked items that only needed network or a secret became manual GitHub workflows (`unblock.md`); the
stack became deployable (`deploy.md`); and the phase 3 features that need no real data were built.

| Issue | Title | Status | What landed |
|---|---|---|---|
| #65 | Voice list input | done by tests | Web Speech API (`he-IL`) with a confirm step before parsing, feature-detected; events `voice_started`, `voice_completed`. The server speech-to-text fallback and the per-device check of `he-IL` on iOS Safari and Android Chrome remain. |
| #70 | Monthly budget and spend tracking | done by tests | `profiles.monthly_budget`, `spend_entries` with RLS, `POST`/`GET`/`PUT`/`DELETE /me/spend`, export; "נותר החודש" on results and split, "סיימתי לקנות" records the plan total; six-month chart on Profile. Correct-a-total and per-entry delete exist in the API, not yet in the UI. |
| #71 | Recipe to list | done with synthetic data | `POST /parse-recipe` with a rule-based Hebrew ingredient parser, JSON-LD recipe extraction for URLs, servings scaling; "ממתכון" in the list builder. Resolved against the synthetic catalog; re-check on the real one. |
| #69 | Promo cycle prediction | done with synthetic data | `GET /promo-cycles/{canonical_id}`, advice only with 3 cycles and confidence 0.6 (`promo-cycles.md`). Synthetic backtest: hit rate 0.88, false alarms 0.02; no real history exists yet. |
| #61, #68 | Receipt and handwritten-list photo | open, phase 3 | Need server-side OCR with Hebrew and real receipts to test on. |
| #72 | Cart transfer to chain online stores | open, phase 3 | Needs the chains' online-store integration; never scraped. |
| #73 | Arabic UI | open, phase 3 | A full second locale; the MVP keeps Hebrew copy as literal text (conventions). |
| — | Deploy packaging | done by tests | API and web containers built and run here, VPS units and timers, `deploy.yml` (images to GHCR always; deploy only when secrets exist), scaled load test (`optimizer.md`, `deploy.md`). |
| — | Manual workflows | done by tests | "BGE-M3 evaluation" (ran: see #29), "Portal probe" (ran: see #60; `commit_fixtures` pushes real regression fixtures), "Extraction pilot" (waits on the key), "Provision check" (waits on secrets). |

## Owner runbook

Do these in order. Each step says where the detail lives. Cost and time figures are estimates from the
research and the docs; none was measured. The whole MVP is 40 to 100 USD per month (estimate,
`architecture.md` section 9).

### 1. Provision (about 1 to 2 days of work, estimate)

Follow `docs/infra-provisioning.md` section 8, in this order. Monthly costs (estimates): Supabase Pro 25 USD
(the price is verified in `architecture.md`), Israeli VPS 10 to 20 USD, object storage about 5 USD.

```bash
# 1. Supabase: create the project, enable the extensions (section 2.2), then from the repo root:
export DATABASE_URL_DIRECT='postgresql://...'      # from your password manager, never in the repo
psql "$DATABASE_URL_DIRECT" -f infra/smoke/db_smoke.sql           # ends with the row: smoke ok

# 2. Roles and connection strings: section 3 (create smartcart_ingest and smartcart_readonly).
# 3. Bucket and the two scoped tokens: section 6.1. Fill /etc/smartcart/ingest.env on the VPS.

# 4. VPS: create it in an Israeli datacenter (section 5.2), then on the VPS:
git clone https://github.com/NoaMcDa/SmartCart.git ~/SmartCart && cd ~/SmartCart
sudo bash infra/vps/setup.sh
bash infra/smoke/check_israeli_ip.sh                  # exit 0, PASS
bash infra/smoke/check_portals.sh                     # run after 08:00 Israel time; download probe: PASS
set -a; . /etc/smartcart/ingest.env; set +a
uv run infra/smoke/bucket_roundtrip.py                # PASS (a refused delete is expected)

# 5. Apply the schema and prove the extensions on the real project:
uv run smartcart-ingest migrate
DATABASE_URL="$DATABASE_URL_DIRECT" SMARTCART_REQUIRE_EXTENSIONS=1 uv run pytest -m "postgis or pgvector"
```

Then tick the items of #14 and #22 with the command output, and fill the restore test record
(`infra-provisioning.md` section 4.4) once a few thousand rows exist. Enable point-in-time recovery before
the first human label or user row is written (section 4.1).

### 2. Fetch real fixtures on the VPS (1 hour, estimate)

```bash
cd ~/SmartCart
uv run python -m smartcart_ingest.adapters.fetch_fixtures
uv run pytest services/ingest -q
```

Real files land in `services/ingest/tests/fixtures/real/` and the test suite parses them automatically
(the one skipped test runs now). Fix every adapter, online-store rule (#53), schema marker (#57) and
placeholder store code that the real files contradict, commit the fixtures, then build the two missing
adapters (#81). Do not load a failed file.

### 3. Run the nightly jobs for two weeks and generate the exit report

```bash
sudoedit /etc/smartcart/ingest.env      # DATABASE_URL, S3_*, optional ALERT_WEBHOOK_URL
sudo systemctl start smartcart-ingest-full.timer smartcart-ingest-delta.timer
systemctl list-timers 'smartcart-*'
uv run smartcart-ingest status          # per chain and status; quarantines per chain
uv run streamlit run services/dashboard/smartcart_dashboard/app.py   # check daily
```

The repo has no timer for `smartcart-api precompute`; schedule it after the full sync (for example a cron
or systemd timer at 09:30 Israel time) so `effective_prices` is current. After 14 or more consecutive days:

```bash
export DATABASE_URL=postgresql://...      # the read-only role is enough
export START=2026-10-20 END=2026-11-02    # example dates; use the real window
uv run python -m smartcart_ingest.report --start "$START" --end "$END" \
  --basket-barcodes 7290000000011,7290000000012,7290000000013 \
  --lon 34.7918 --lat 32.0744 --radius-m 3000 \
  --out /tmp/phase-0-evidence.md
```

Use real barcodes (10 to 20 common items sold in several chains) and a point in a dense area. Paste the
sections into `docs/phase-0-exit-report.md`, check the promo sample by hand, tick the checklist in section
5, record the decision and close #60. Two weeks is the roadmap's exit criterion; the 95 percent success
bar is from the same place.

### 4. Seed the catalog and run the extraction pilot (about 2 to 3 USD, estimate)

```bash
uv run smartcart-catalog seed
uv run smartcart-catalog normalize          # read the issue list; turn it into test cases (#20)
export ANTHROPIC_API_KEY=...                # never commit; put it in your password manager
uv run smartcart-catalog extract --extractor claude --limit 1000 --batch-size 500
uv run smartcart-catalog cost-report
```

`--batch-size` is items per batch (default 500, `EXTRACTION_BATCH_SIZE`), so 1,000 items is two batches.
The cost figure is an estimate: about 0.002 to 0.003 USD per item with prompt caching (D14), which is
roughly 2 to 3 USD for the pilot and about ten times the research's "tens of dollars" for the whole
catalog. The bill is the source of truth. Compare the output with the rule extractor on a labeled sample
(and with Dicta-LM if you want the local option), then confirm or change D14 in `docs/decisions.md`.

### 5. Embed with BGE-M3 and match

```bash
uv sync --all-packages --extra embed
export EMBEDDER=bge-m3                      # EMBEDDING_MODEL defaults to BAAI/bge-m3
uv run smartcart-catalog embed --target all
uv run smartcart-catalog judge --judge rule
```

This needs a machine that can download the model from Hugging Face (not the build sandbox) and enough CPU or
a GPU; the time is not estimated here. Repoint the search route at the BGE-M3 query embedder (#54).

### 6. Rebuild and label the gold set, then evaluate

The committed gold set (`data/gold/`, 2,419 pairs) is synthetic. Replace it with real labeled pairs: sample
real items across the 19 departments and the hard cases (3% vs 1% milk, fresh vs frozen, soy vs almond,
pack sizes), label them in the review UI (every human decision is written to `gold_pairs`), and label the
user-reported pairs from `feedback_gold_candidates`. There is no command that exports a real gold set today;
use `--gold-dir` with a directory in the format of `data/gold/` or evaluate from `gold_pairs` in the database.
Recalibrate `sim_floor` and `sim_ceil` for BGE-M3 on it. Then:

```bash
uv run smartcart-catalog evaluate --fail-below 0.98    # precision at "any brand"; reports every level separately
```

Report precision per flexibility level, never one number. If recall@10 is below 0.95 or any-brand recall is
below 0.80, plan embedder fine-tuning (both thresholds are our planning choices, an estimate; `matching.md`).
Compare the LLM judge (`--judge llm`) with the rule judge on the same set before choosing. The 98 percent is
a target, not a result.

### 7. Review the canonicals and the 300 best-sellers

```bash
uv run smartcart-catalog review --port 8502
```

Have a domain-aware reviewer sign off the 245 canonicals using the checklist in `docs/catalog.md` section 2
(#15). Replace the estimated rank with one measured from loaded data. In the "Best sellers (top 300)" tab,
review every mapped item until all 300 are human-reviewed; that is the launch criterion (#38).

### 8. Deploy the web app and the API

The containers, VPS units, timers and the `deploy.yml` workflow exist now; the step-by-step is in
[deploy.md](deploy.md). What follows is the original outline.

The repo has no deployment config; use the host you choose. Build-time variables (inlined by Next.js, so set
them before `npm run build`):

```bash
cd apps/web
export NEXT_PUBLIC_SITE_URL=https://<your domain>          # canonical URLs, sitemap, JSON-LD
export NEXT_PUBLIC_API_BASE_URL=https://<your api origin>  # `.env.example` still says NEXT_PUBLIC_API_URL; the code reads _BASE_URL
export NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
export NEXT_PUBLIC_SUPABASE_ANON_KEY=...
export NEXT_PUBLIC_BETA_EVENTS=1                           # only for the beta build
export NEXT_PUBLIC_VAPID_PUBLIC_KEY=...                    # web push (#23); confirm the name in .env.example when that work merges
npm ci && npm run build
```

API service (long-lived):

```bash
export DATABASE_URL=... SUPABASE_JWT_SECRET=... API_CORS_ORIGINS=https://<your domain>
export VAPID_PRIVATE_KEY=... VAPID_SUBJECT=mailto:...      # server half of web push; names to confirm as above
uv run smartcart-api serve --host 0.0.0.0 --port 8000
```

Generate the VAPID pair once and keep the private half in the secrets store. The variable names for web
push are not in `.env.example` yet; the phase 2 alerts work should add them in the same change, and this
runbook should then be updated to match. Before launch decide `INDEX_UNPRICED` (`docs/seo.md`), refresh the
SEO data and rebuild:

```bash
uv run smartcart-catalog export-seo        # needs DATABASE_URL; run after the nightly precompute
```

### 9. Submit the sitemap

In Google Search Console verify the domain, then submit `https://<your domain>/sitemap.xml` (204 URLs in the
seed). Record the indexed-page count weekly in the beta report (the last criterion of #35). Run each page
type through the Schema.org validator and Google's Rich Results Test, which was not possible from the build
environment.

### 10. Run the device and screen-reader passes

- Install the PWA on a real Android Chrome and a real iOS Safari device (steps in `docs/web.md`), and test
  the offline shell, store mode and touch drag in the split view (#11, #41, #66).
- Screen-reader pass in Hebrew with VoiceOver (iOS Safari) and TalkBack (Android Chrome) on the screens listed
  in `docs/a11y-report.md`; record findings under "Screen reader pass" there (#26).
- Check text-only scaling at 200 percent, reduced motion and forced colors by hand.
- Get a legal read of the accessibility statement and the privacy text (#26, #30).

### 11. Web push keys (phase 2, #23)

```bash
npx web-push generate-vapid-keys      # the web-push npm package; not run here, any VAPID generator works
```

Put the public key in the web build and the private key in the API's environment (step 8).

### 12. Confirm the beta thresholds, then recruit the beta

Every threshold in `docs/beta-plan.md` section 4 is a proposal. Before the first invitation, accept or edit
the numbers (rejection rate at most 2 percent exact, 5 percent any brand, 15 percent close, each with at
least 100 substitutions shown at that level; median paste-to-results 5 s, p90 10 s; return visits 40
percent), write the final values in that file and in `BETA_THRESHOLDS`
(`services/catalog/smartcart_catalog/cli_seo.py`), and get a legal review of the consent text. Then recruit
20 to 50 people (target 30 to 40) across large families, kosher-conscious shoppers and periphery residents,
at least four home chains and both phone types. Make sure the screens call `trackEvent` first (#91).

```bash
uv run smartcart-catalog beta-report --since <beta start> --out docs/reports/beta-<date>.md   # weekly
uv run smartcart-catalog basket-index --month 2026-11 --reviewed-by "<name>"                   # after prices are real
```

The beta is the first time the product meets real data. Public launch is gated on the rejection-rate gate
or a written decision to change the threshold.

### What stays open after the runbook

The native-app decision (#56) needs retention data from real users. Catalog expansion (#52) needs real
labels. The roadmap's regulatory check on the turnover-threshold bill is due on 2027-01-05 (D13).
