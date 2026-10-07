# Status of phases 0, 1 and 2, and the owner runbook

Written 2026-10-07 on `phase-2-base` (commit `c36d6b3`). It answers two questions: what is done, and what
only the owner can do next. Sources: the status comments on issues #1 to #6, the bodies of PR #82
(phase 0, merged) and PR #93 (phase 1, open), and the docs named in each row.

Labels follow `docs/README.md`: **verified** means shown by a test or a measurement, **estimate** means a
judgement. Every cost and time figure below is an estimate unless it says otherwise.

## How to read the table

| Status | Meaning |
|---|---|
| **done by tests** | The acceptance criteria are met by tests that run in CI, or by a written decision. Nothing here depends on real data. Where a manual check on a device remains, the note says so. |
| **done with synthetic data** | Built and tested, but only against synthetic fixtures, a synthetic gold set or a mock API. The behavior is real, the numbers are not. It needs the real-data steps in the runbook before any figure from it is quoted. |
| **blocked** | Needs something that only the owner can supply: infrastructure, an API key, real files, a reviewer, a domain, a device or people. The blocker column says which. |
| **open, phase 2** | Engineering work that is not finished and is not waiting on the owner. For the milestone 3 issues the repo has only the shared contract (migration `20261008100000_phase2.sql`, API schemas, stub routes, MSW handlers); the implementations are separate phase 2 workstreams. Update this table as each one merges. |

Numbers that appear below are quoted from the status comments: 780 Python tests (2 skipped) and 321 unit,
95 e2e and 131 accessibility web tests were green in CI on `phase-1-base`. All are on synthetic data.

## Phase 0, data foundation (milestone 1)

| Issue | Title | Status | Blocker or what remains |
|---|---|---|---|
| #1 | Epic: data foundation | blocked | Children #14, #22, #60 and #81 are open; #32, #53 and #57 wait for real files. |
| #9 | Chain list (8 to 10 chains) | done by tests | Decision D13, no code. The chain size tiers are an estimate: replace with a sourced figure before any public coverage claim. |
| #14 | Supabase vs self-hosted, provision the database | blocked | The project does not exist. Owner creates it (`docs/infra-provisioning.md` section 2). The PostGIS and pgvector smoke tests already pass in CI on the Supabase image. The restore test record (section 4.4) is also the owner's. |
| #17 | Monorepo scaffold and CI | done by tests | All five items met. The last one, "a failing test turns CI red", was exercised once on the throwaway branch `ci/red-check` (commit `fba9fd7`, never merged): run https://github.com/NoaMcDa/SmartCart/actions/runs/37621263324 ended `failure` in the Test step on Python 3.12 and 3.13, with Lint green. Delete the branch with `git push origin --delete ci/red-check` if it still exists (the build environment could not). |
| #22 | Israeli-IP VPS and object storage | blocked | Owner provisions the VPS and bucket, then runs the three smoke scripts. Scripts and Terraform are written but were never run against a live service. |
| #27 | Schema v1 | done by tests | Six of six criteria pass in CI on `supabase/postgres:17.11`. |
| #32 | Adapter framework, one adapter per chain | done with synthetic data | Eight adapters on synthetic fixtures. Real files need the VPS (`fetch_fixtures`). Archiving raw files to the bucket is not wired into the adapters. |
| #37 | Idempotent downloads, full before delta | done by tests | The real portals are unchecked until the VPS runs. |
| #42 | Quality gates and quarantine | done by tests | Thresholds are the defaults from the issue, an estimate. Revisit after real publication delays are seen. |
| #46 | Ingestion dashboard | done by tests | Verify the `smartcart_readonly` role and the numbers on the real project. |
| #49 | Hourly deltas for the main chains | done by tests | Delta polling still has to be watched against the real portals on the VPS. |
| #53 | Online-store record and channel tag | done with synthetic data | Every per-chain rule and the placeholder store codes are provisional until real Stores files confirm them. Osher Ad is listed as having no online record (to confirm). |
| #57 | Dual schema (v1 and v2) | done with synthetic data | `PROVISIONAL_V2_MARKER` is a placeholder. A real file in the authority's new model is needed to confirm it. |
| #60 | Phase 0 exit validation | blocked | Two weeks of nightly loads on the VPS. The report generator and basket query are tested on synthetic data; go/no-go stays NO-GO (`docs/phase-0-exit-report.md`). |
| #81 | Adapters for Machsanei Hashuk and King Store | blocked | Not built: only eight of the ten D13 chains have adapters. Needs the code (synthetic fixtures first) and the VPS for real laibcatalog files. If the schedule slips, D13 drops King Store first, then Machsanei Hashuk. |

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
| #12 | Trust signals | done by tests | Promo confidence needs an API field (#90). Timestamps on product detail and the split view were left to the secondary screens. |
| #15 | 150 to 300 canonical products | blocked | 245 canonicals are committed. A domain-aware reviewer must sign them off (checklist in `docs/catalog.md` section 2). The rank is an estimate: replace with a measured one. |
| #16 | Report-a-gap button | open, phase 2 | UI and `POST /feedback/gap` are done and tested. Feeding gap reports into the quality checks is the remaining half. |
| #18 | Onboarding | done by tests | Eye check of dark theme at 390 px. |
| #20 | Rule normalization | done with synthetic data | 50 table cases with realistic, not real, names. Turn the issue list from `smartcart-catalog normalize` on real loads into test cases. |
| #21 | Methodology page and quality metric | done with synthetic data | The published metric comes from the synthetic gold set and is labeled so. Links from results and the substitution card are open (#91). Structured data has not been run through an external validator. |
| #24 | List builder | done by tests | Against the mock API. The estimate's reaction to a flexibility change needs the real API. |
| #25 | LLM attribute extraction | blocked | `ANTHROPIC_API_KEY` and loaded items for the model comparison and the first cost run. The extractor runs on hand-written fixtures. |
| #26 | Accessibility audit (Israeli standard 5568) | blocked | The screen-reader pass in Hebrew (VoiceOver, TalkBack) needs a person. Also open: top bar overflow by 7 px at 195 px, no non-drag path in the split view yet, a legal read of the statement, and a contact detail on the statement page. Automated coverage is complete; it is not a conformance claim. |
| #29 | BGE-M3 embeddings, blocking, HNSW | blocked | BGE-M3 has not run (Hugging Face was unreachable from the build environment). The 0.9988 recall@10 is on the synthetic gold set with a hash embedder. |
| #30 | Privacy by design | blocked | `DELETE /me` (#90) and a legal review of the privacy text. |
| #31 | Flexibility bottom sheet | done by tests | Soft-attribute checkboxes are stored on the row; the API has no field for them yet, so they do not change matching. |
| #33 | Match judge with hard rules | done with synthetic data | The LLM judge is wired and tested but never measured (no key). Compare it with the rule judge on the real gold set. |
| #35 | Static SEO pages | blocked | A deployed domain, `NEXT_PUBLIC_SITE_URL`, real prices (product pages have no offers yet), and a decision on `INDEX_UNPRICED`. Then submit the sitemap. |
| #36 | Comparison results screen | done by tests | Against the mock API (the mock prices every flexibility level the same). |
| #38 | Review UI, gold set, evaluation harness | done with synthetic data | The CI gate passes at 1.00 any-brand precision on 2,419 synthetic pairs (recall 0.81). Real labels and the human review of the 300 best-sellers are pending. |
| #40 | Closed beta, 20 to 50 users | blocked | People to recruit; the owner's confirmation of the proposed thresholds; consent screen; the screens must call `trackEvent` (#91). |
| #41 | Cart split view | done by tests | Touch drag onto the other tab is to verify on a device. Keyboard and button paths are in e2e. |
| #43 | Feedback loop | done by tests | Context columns and RLS are in the phase 2 migration; see #92. No rejection rate exists until the beta. |
| #44 | Monthly basket index | done with synthetic data | No month can be published until real prices load. Basket composition and check thresholds are estimates. |
| #47 | Nightly effective-price precompute | done with synthetic data | 675,000 rows in 52 s was measured on synthetic data only. Scheduling it on the VPS is still open (the repo ships no timer for it). Promo reward semantics are provisional until real promo files are seen. |
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
| #90 | API follow-ups | open, phase 2 | `DELETE /me`, store coordinates, promo confidence, nearest store of a chain. The phase 2 base has schemas and stub routes for them. |
| #91 | Web follow-ups | open, phase 2 | `AuthProvider` in the root layout, event tracking and consent, methodology links, design-system page, top bar at 200% zoom. |
| #92 | Catalog contract follow-ups | open, phase 2 | The columns are in the phase 2 migration (`item_canonical.reason`, `human_rejected`, `canonical_products.embedding_model`, `reference_barcodes`, feedback context and RLS). The catalog code that reads and writes them is still to do. |

## Phase 2, advanced savings (milestone 3)

At the base commit these have a shared contract and nothing else. None is blocked on the owner except #52
and #56, which need real data and real users.

| Issue | Title | Status | Blocker or what remains |
|---|---|---|---|
| #7 | Epic: advanced savings | open, phase 2 | Children below. |
| #13 | MILP cart optimizer | open, phase 2 | The API schema has solver selection and promo bundles. Design in `docs/optimizer.md` (being written). Compare against the phase 1 heuristic on real baskets. |
| #19 | Club membership filtering | open, phase 2 | Club flags and the `noclub` fallback already exist in the precompute (#47). |
| #23 | Price-drop alerts with web push | open, phase 2 | Tables for alerts, push subscriptions and deliveries are in the phase 2 migration. Web push needs a VAPID key pair, which the owner generates (runbook step 11). |
| #28 | Price history, 90 days | open, phase 2 | Schema and API contract exist. Real history needs weeks of real loads; until then charts show synthetic data. |
| #34 | Shared family lists in real time | open, phase 2 | `list_shares`, member policies and the Realtime publication are in the migration. Realtime needs the real Supabase project. |
| #39 | Barcode scanning in the PWA | open, phase 2 | Barcode lookup contract exists. Needs a device check, and barcodes in the catalog from real loads. |
| #45 | Smart cart: single best swap | open, phase 2 | Swap-suggestion contract exists. Depends on the real catalog for meaningful swaps. |
| #52 | Catalog expansion with active learning | blocked | Needs real labeled pairs from the review UI and the beta's rejected substitutions. |
| #56 | Native app decision | blocked | Needs retention data from real users (after the beta and launch). Not a build task. |

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
uv sync --extra embed
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
