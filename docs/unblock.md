# Unblocking through CI runners

Written 2026-10-08 for the unblock round. The build environment cannot reach Hugging Face or the
chain transparency portals, and it has no Anthropic key. GitHub-hosted runners can reach Hugging
Face and the public internet, and repository secrets can hold the keys. So every blocked item that
only needs network access or a single secret is now a `workflow_dispatch` workflow that the owner
or the lead can start from the Actions tab and read in its job summary. A workflow that needs a
secret checks for it first and, when it is absent, says which secret to set and exits 0, so all
four are safe to merge before anything is provisioned.

Labels follow `docs/README.md`: **verified** means shown by a test or a measurement, **estimate**
means a judgement. Every runtime and cost below is an estimate; none of these workflows has run on
GitHub yet (they were linted with actionlint and every script was run locally, see the end).

## The four workflows

| Workflow (Actions tab name) | File | Trigger | Inputs | Secrets | Artifacts | Runtime (estimate) |
|---|---|---|---|---|---|---|
| BGE-M3 evaluation | `bge-eval.yml` | dispatch; Mondays 02:41 UTC | `max_items` (0 = all 857 gold items), `model` (default `BAAI/bge-m3`) | none | `bge-eval-report` (Markdown and JSON, 30 days) | 10 to 20 min the first time (torch wheels and a model of about 2.3 GB), less once the model is cached |
| Portal probe | `portal-probe.yml` | dispatch; daily 07:17 UTC | `chains` (space-separated slugs, empty = all ten), `timeout` (seconds per download, 180), `commit_fixtures` (default off) | none (the commit job uses the workflow token) | `portal-probe-files` (raw files, 7 days), `portal-probe-report` (table and JSON, 30 days), `portal-probe-fixtures` (with `commit_fixtures`, 7 days) | 5 to 30 min, mostly the portals; capped at 90 |
| Extraction pilot | `extraction-pilot.yml` | dispatch | `max_items` (1 to 1000, default 200) | `ANTHROPIC_API_KEY` | `extraction-pilot-report` (30 days) | under 1 min without the key; with it, a few minutes plus the batch (usually well under an hour; the job stops at 2 h) |
| Provision check | `provision-check.yml` | dispatch | `apply_migrations` (default off) | `SUPABASE_DB_URL`; `VPS_SSH_HOST`, `VPS_SSH_KEY` (optional `VPS_SSH_USER`, `VPS_SSH_PORT`, `VPS_SSH_KNOWN_HOSTS`); `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_ENDPOINT_URL` or `S3_REGION` | none | 1 to 3 min |

Every workflow step has a local entry point under `scripts/unblock/`:

| Script | Used by | Run here (no network) |
|---|---|---|
| `bge_eval.py` | BGE-M3 evaluation | `BGE_EVAL_EMBEDDER=hash` on a migrated database: full gold set gave the documented 1.0000 / 0.8125 any-brand and recall@10 0.9988 |
| `portal_probe.py probe` and `gate` | Portal probe | `gate --files services/ingest/tests/fixtures`: all ten chains through the Scheduler path (stale-date quarantines with the real clock, `loaded` with `--now`); `probe` exercised against the unreachable portals; the Cerberus login check against a local FTPS server with a mismatched certificate (passes like upstream, annotated) |
| `portal_probe.py fixtures`, `copy_fixtures.sh` | Portal probe with `commit_fixtures` | synthetic files trimmed to 3 rows, re-parsed by every adapter, copied into temporary `<chain>/real/` folders; the real-fixture tests in `test_adapters.py` then passed (parse and gates), and were removed again |
| `extraction_pilot.py prepare`, `compare`, `check-limit` | Extraction pilot | `prepare`, then `extract --extractor rule --limit 120`, then `compare --model-extractor rule` |
| `provision_check.sh db\|vps\|bucket` | Provision check | db smoke against a local Postgres (pass) and a bare one (fail); every "not set" path; vps against a closed port |
| `supabase_provision.py` | Owner, once (section 9.1 of `infra-provisioning.md`) | `--dry-run` only; the Management API calls are unverified |

Tests: `uv run pytest scripts/unblock/tests -q` (29 tests, no network, no database). The real
fixture tests live in `services/ingest/tests/test_adapters.py` and run in CI once
`fixtures/<chain>/real/` exists.

## Each blocked issue: the minimum owner input now

"Minimum input" is what only the owner can supply. The categories: **one secret** (paste a value
into the repository secrets), **one click** (run a workflow), **person-hours** (a person has to do
or judge something), **time-bound** (it needs calendar time or real users, whatever anyone does).

| Issue | Minimum owner input now | Which workflow does the rest | What remains truly human |
|---|---|---|---|
| #14 Supabase project | **One token plus one secret plus one click.** Run `scripts/unblock/supabase_provision.py` once with a `SUPABASE_ACCESS_TOKEN` and the org id (creates the project, enables the extensions, prints the strings), set `SUPABASE_DB_URL` (session pooler), run Provision check (optionally with `apply_migrations`). | Provision check, job "Supabase database": `db_smoke.sql`, and `smartcart-ingest migrate` on request | Paying for Pro; the restore test record (section 4.4) is **time-bound**: it needs a few thousand real rows. Enabling point-in-time recovery before the first label is a dashboard click. |
| #22 VPS and bucket | **About one person-hour plus secrets plus one click.** Buy the VPS in an Israeli datacenter and the R2 bucket, create the two bucket tokens, run `setup.sh` on the VPS, then set `VPS_SSH_HOST`, `VPS_SSH_KEY` and the `S3_*` secrets and run Provision check. | Provision check, jobs "Israeli-IP VPS" (geolocation and portal download over ssh) and "Object storage" (round trip) | Choosing the provider and paying; checking the host-key fingerprint against the provider console. |
| #60 Phase 0 exit | **Time-bound.** Fourteen consecutive days of nightly loads on the VPS after #14 and #22. | Portal probe runs daily now, so adapter, online-store and schema problems surface before the clock starts. Option for the lead, not built: if the probe shows the non-laibcatalog portals reachable from runners, a scheduled runner job could load eight of the ten chains into Supabase meanwhile; Victory and Machsanei Hashuk would still need the VPS. | The go/no-go decision, the hand check of the promo sample and the checklist in `phase-0-exit-report.md`. |
| #15 Canonical sign-off | **Person-hours.** A domain-aware reviewer goes through the 245 canonicals with the checklist in `catalog.md` section 2 (2 to 4 hours, estimate). | None; the review UI already exists (`smartcart-catalog review`). | The sign-off itself. The measured rank needs real loaded data (after #60). |
| #25 LLM extraction | **One secret plus one click.** Set `ANTHROPIC_API_KEY` and run Extraction pilot (200 items, about 0.40 to 0.60 USD at the repo's estimate). | Extraction pilot: model extraction, rule comparison per attribute, cost per item, disagreement sample | Reading the disagreements and confirming or changing D14 (**person-hours**, about one hour, estimate). The cost run "on the MVP catalog" needs real loaded items (after #22); the Dicta-LM comparison is optional and not automated. |
| #26 Accessibility | **Person-hours.** The Hebrew screen-reader pass with VoiceOver and TalkBack on real devices, and a legal read of the statement. | None (automated coverage is already in `web.yml`). | Both items are human. The other items in the #26 row (195 px overflow, a non-drag split path, a contact detail) are engineering or content work, not owner input; #101 reports every route fitting at 195 px, so the row may be out of date there. |
| #29 BGE-M3 | **One click.** Run BGE-M3 evaluation (no secret). It also runs weekly. | BGE-M3 evaluation: precision and recall per level, recall@10, embed time and model revision on the synthetic gold set, with the hash baseline | Nothing for the synthetic measurement. The real-data number needs real labeled pairs (#38, person-hours), and the `/search` switch (#54) is an engineering change once the vectors exist. |
| #30 Privacy | **Person-hours.** A legal review of the privacy text. `DELETE /me` is implemented (#90). | None | The legal review. |
| #35 SEO pages | **One person-hour plus a decision.** Buy the domain and choose a host, set `NEXT_PUBLIC_SITE_URL`, decide `INDEX_UNPRICED`. | None of these four; a deploy workflow would need the host's credentials (one more secret) and is not part of this round. | Verifying the domain in Search Console and submitting the sitemap. Product pages get offers only after real prices load (**time-bound**, after #60). |
| #40 Closed beta | **Person-hours, then time-bound.** Confirm the thresholds in `beta-plan.md` section 4 (a decision), a legal review of the consent text, then recruit 20 to 50 people. | None | Recruiting and running the beta; it needs real prices first. |
| #52 Active learning | **Time-bound.** Real labeled pairs from the review UI and the beta's rejected substitutions. | None | The labels. |
| #56 Native app decision | **Time-bound.** Retention data from real users after the beta and launch. | None | The decision. |

## Suggested "what remains" text for `docs/phase-2-status.md`

For the lead to copy into the blocker column (this file does not edit that one):

- **#14**: The project does not exist. One token: `scripts/unblock/supabase_provision.py` creates it and enables the extensions (`infra-provisioning.md` section 9.1); then set `SUPABASE_DB_URL` and run "Provision check". The restore test record (section 4.4) waits for real rows.
- **#22**: Owner buys the VPS and bucket (about one person-hour), sets `VPS_SSH_HOST`, `VPS_SSH_KEY` and the `S3_*` secrets, and runs "Provision check", which runs the three smoke scripts against the live services.
- **#60**: Fourteen consecutive nightly loads on the VPS after #14 and #22. "Portal probe" runs daily from a runner meanwhile and shows per chain whether the portal answers, the file parses and the gates pass. Go/no-go stays NO-GO.
- **#15**: Person-hours: a domain-aware reviewer signs off the 245 canonicals (`catalog.md` section 2). The rank is an estimate until real data loads.
- **#25**: One secret: set `ANTHROPIC_API_KEY` and run "Extraction pilot" (default 200 synthetic items, about 0.40 to 0.60 USD, estimate). Then read the comparison and confirm or change D14. The full-catalog cost run waits for loaded items.
- **#26**: Human only: Hebrew screen-reader pass (VoiceOver, TalkBack) and a legal read of the statement. Engineering or content items still listed in the row (non-drag split path, contact detail on the statement page; the 195 px overflow if #101 did not close it) are not owner input.
- **#29**: One click: "BGE-M3 evaluation" (also weekly) measures BGE-M3 on the synthetic gold set. The real-data recall@10 needs real labels (#38); the search switch (#54) follows.
- **#30**: Legal review of the privacy text only (`DELETE /me` is done, #90).
- **#35**: A domain and host (owner), `NEXT_PUBLIC_SITE_URL`, a decision on `INDEX_UNPRICED`, then the sitemap in Search Console. Offers need real prices.
- **#40**: Confirm the thresholds, legal review of the consent text, recruit 20 to 50 people. Needs real prices first.
- **#52**: Real labeled pairs (review UI and the beta's rejections). Time-bound.
- **#56**: Retention data from real users. Time-bound.

## Things the lead should know when triggering

- **Merge before triggering.** `workflow_dispatch` only appears in the Actions tab for workflows on
  the default branch. Schedules also run from the default branch only.
- **BGE-M3 evaluation.** The first run downloads torch with its CUDA wheels (the lock file pins
  the PyPI build) and the model; later runs reuse the model cache (`actions/cache`, key
  `huggingface-Linux-<model>-v1`). Start with `max_items: 100` for a quick check, then 0. The job
  is green whatever the numbers say; read the summary. The gold set is synthetic, and
  `sim_floor`/`sim_ceil` are hash-calibrated, so a precision change can be calibration.
- **Portal probe.** Expect blocked or unreachable rows: the runner is not Israeli, and that is
  part of the measurement. Run it after about 08:00 Israel time (the schedule does). The raw files
  stay 7 days in `portal-probe-files`. The table and one `RESULT {...}` line per file are also in
  the job log, for readers who cannot download artifacts. With `commit_fixtures` the accepted
  files are pushed to a new branch `probe/fixtures-<YYYYMMDD>` (Stores whole, PriceFull trimmed to
  200 rows, `MANIFEST.json` per chain) by a separate job with `contents: write`; open the pull
  request by hand, and CI runs then (a push with the workflow token starts no workflow). Downloads
  are parsed only by the adapters, in the real Scheduler path. A Cerberus login line reading
  `ok (certificate not verified, as upstream ...)` is a pass: the scraper does not verify that
  portal's certificate, which does not match its host name.
- **Extraction pilot.** Without the secret it shows a notice and is green. With it, the spend is
  capped by `max_items` (at most 1000, one batch) and the extractor's limits (1024 output tokens
  per item, low effort). The cost in the summary is the repo's estimate; the console bill is the
  source of truth. If the job hits its 2-hour limit, the batch may still complete and bill.
- **Provision check.** Each service job passes with a "NOT SET" notice until its secrets exist.
  Use the Supabase **session pooler** string for `SUPABASE_DB_URL`: GitHub runners have no IPv6.
  `apply_migrations` writes to the real database (idempotent migrations only); leave it off for a
  pure smoke.
- **Runbook errata found on the way** (in files this round does not own):
  `uv sync --extra embed` in `phase-2-status.md` runbook step 5 fails at the workspace root
  ("Extra `embed` is not defined ... for `smartcart`"); the working command is
  `uv sync --all-packages --extra embed` (the same fix applies to the `matching.md` embedder
  table, corrected in this round). `check_portals.sh` now prints four Cerberus FTP login lines, so the
  expected output in `infra-provisioning.md` section 5.4 is incomplete (section 9.2 says so).
