# Deploy: from secrets pasted to smoke green

The go-live runbook. Once the owner has provisioned (`infra-provisioning.md`: Supabase, the Israeli
VPS, the bucket), going live is one command, `git tag v0.1.0 && git push origin v0.1.0`, and the
`Deploy` workflow does the rest. This page says what runs where, every variable, the order of the
first deploy, rollback, sizing from the load test, and the costs.

Evidence labels follow `docs/README.md`: **verified** (shown by a test or a measurement here),
**estimate** (a judgement), **unverified** (a vendor fact this document could not check; confirm it
in the vendor's dashboard). Nothing here has run against live services: there are none yet. What
was run is listed in [How this was validated](#how-this-was-validated).

## What runs where

| Where | What | Started by |
|---|---|---|
| **VPS** (Israeli IP, `infra/vps`) | Ingestion: `smartcart-ingest-full.timer` (06:00 and 08:30 Israel time), `smartcart-ingest-delta.timer` (hourly at :20) | `setup.sh` |
| **VPS** | The API: `smartcart-api.service`, uvicorn on 127.0.0.1:8000 (`WEB_CONCURRENCY` workers, default 2), behind Caddy on 443 with automatic TLS when `SMARTCART_API_DOMAIN` is set | `setup.sh` |
| **VPS** | `smartcart-precompute.timer`: nightly `smartcart-api precompute` at 09:30 Israel time, after the second full sync; it waits on the ingestion lock | `setup.sh` |
| **VPS** | `smartcart-alerts.timer`: hourly `smartcart-api alerts-run` at :45 | `setup.sh` |
| **Vercel** (or the web image on any container host) | The PWA and the static SEO pages (`apps/web`) | `deploy.yml` |
| **Supabase** | Postgres 17 with PostGIS, pgvector, pg_trgm; Auth; Realtime (shared lists) | the owner, once |
| **Cloudflare R2** | The raw archive of transparency files | the owner, once |
| **GHCR** | `ghcr.io/<owner>/smartcart-api` and `smartcart-web`, one tag per release | `deploy.yml` |

Why the API is on the VPS: the box already exists for ingestion, the API is light (see
[Sizing](#sizing-from-the-load-test)), and a second host is a second bill and a second place to
keep secrets. `architecture.md` section 9 budgeted 10 to 30 USD a month for a separate FastAPI
container (estimate); this layout spends nothing on it. The API image is the portable unit if that
changes: it runs as is on Fly.io, Railway, Render or Cloud Run (it honours `$PORT`), and the API
needs no Israeli IP, only the ingestion does.

## Files

| File | What it is |
|---|---|
| `services/api/Dockerfile` (+ `Dockerfile.dockerignore`) | API image: Python 3.12 slim, uv, non-root (uid 10001), `/health` healthcheck, OR-Tools wheels. Build from the repo root. Also runs `smartcart-api precompute`, `alerts-run` and `smartcart-ingest migrate` |
| `apps/web/Dockerfile` (+ `Dockerfile.dockerignore`) | Web image: Node 22, `next build` with `output: "standalone"` (switched on by `NEXT_OUTPUT=standalone`, one line in `next.config.ts`), non-root, `node server.js` on `$PORT` (3000) |
| `apps/web/vercel.json` | Vercel config, the zero-ops alternative: framework Next.js, `npm ci`, region `fra1`, Git auto-deploys off (deploys come from the workflow) |
| `infra/vps/smartcart-api.service` | The API unit |
| `infra/vps/smartcart-precompute.{service,timer}`, `smartcart-alerts.{service,timer}` | The batch jobs |
| `infra/vps/setup.sh` | Idempotent VPS setup; now also syncs `smartcart-api`, installs the API units, creates `/etc/smartcart/api.env` and `jobs.env`, restarts the API and fails unless `/health` answers within 30 s; with `SMARTCART_API_DOMAIN`, Caddy and ports 80/443 |
| `infra/docker-compose.yml` | Profile `app`: `migrate`, `api`, `web` from the two images; profile `jobs`: `precompute`, `alerts`. A plain `up -d` still starts only the database |
| `.github/workflows/deploy.yml` | On a `v*` tag or by hand: images to GHCR, API to the VPS, web to Vercel, smoke |
| `scripts/loadtest/` | The scaled synthetic load test behind the sizing below |

## The environment contract

Names are catalogued in `.env.example`. Never commit a value.

### API, at run time

On the VPS the API unit reads `/etc/smartcart/ingest.env`, then `/etc/smartcart/api.env`; a name in
`api.env` wins. In a container, pass them with `-e`.

| Variable | Required | Meaning |
|---|---|---|
| `DATABASE_URL` | yes | The API's connection, as the least-privilege role `smartcart_api` (see "Which role" below), through the **session** pooler (port 5432 on the pooler host), the **transaction** pooler (port 6543, with `DB_POOLER_MODE=transaction`) or the direct host |
| `DB_POOLER_MODE` | no (`session`) | `transaction` when `DATABASE_URL` goes through the transaction pooler: no server-side prepared statements (`prepare_threshold=None`) and the time zone set per transaction (`SET LOCAL TIME ZONE 'UTC'`) instead of per connection. Any other value than `session` or `transaction` stops the API when it first opens the pool |
| `SUPABASE_JWT_SECRET` | yes | The project's JWT secret; `/me/*` answers 503 without it |
| `API_CORS_ORIGINS` | yes | `https://<your domain>` (comma separated; add the Vercel preview origin only if you use previews) |
| `API_PUBLIC_WEB_URL` | yes | `https://<your domain>`: the origin of list-invite links |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | for `DELETE /me` | Supabase Admin API (docs/api.md, account deletion) |
| `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_SUBJECT` | for web push | Without them alerts are recorded, not pushed |
| `API_QUERY_EMBEDDER` | no (`hash`) | `bge-m3` once BGE-M3 vectors are loaded (docs/api.md, search) |
| `WEB_CONCURRENCY` | no (2 in the unit) | uvicorn worker processes |
| `API_POOL_MAX` | no (10) | connections per worker; total = workers x this |
| `SMARTCART_API_PORT` | no (8000) | loopback port of the unit; set the same in `setup.sh`'s environment |

**Which connection: session or transaction pooler.** Both work. `infra-provisioning.md` section 3.2
planned the transaction pooler (port 6543) for the API: many short requests. Two things in
`smartcart_api/db.py` made that unsafe, and `DB_POOLER_MODE=transaction` fixes both. The time zone
was set once per pooled connection (`SET TIME ZONE 'UTC'`), session state that a transaction pooler
does not keep; in transaction mode it is `SET LOCAL TIME ZONE 'UTC'` at the start of each request's
transaction. psycopg prepares a statement on the server after five executions
(`prepare_threshold`), and a statement prepared on one server connection does not exist on the next;
transaction mode sets `prepare_threshold=None`. Everything else the API keeps in the session is
already transaction-local (`SET LOCAL ROLE`, `set_config(..., true)` for the JWT claims and the
trigram threshold). Proven against a local Postgres by `services/api/tests/test_api_db_pooler.py`
(the time zone ends with the request, no statement is ever prepared); **not yet run against
Supavisor itself**, so after switching, watch the first requests' log for prepared-statement errors
and fall back to the session pooler if any appear. The session pooler stays the default and the
documented choice until then: `WEB_CONCURRENCY=2` and `API_POOL_MAX=5` (10 connections; the Pro
plan's connection limits are unverified, check the dashboard). With the transaction pooler the
pool can be larger, since the server connection is held for one transaction only.

**Which role.** The API connects as `smartcart_api`, a login role created by migration
`20261011100500_api_role.sql` with exactly what the API does and nothing else:

- read the catalog and price tables (`chains`, `stores`, `items`, `prices`, `promos`,
  `effective_prices`, `canonical_products`, `taxonomy`, `item_canonical`, `file_tracking`, ...);
- write `events`, `search_misses`, `gap_reports` and `substitution_feedback`, and set
  `item_canonical.needs_review` (that column only) when a substitute is reported;
- reach the user tables (`profiles`, `lists`, `list_items`, `preferences`, `price_alerts`,
  `push_subscriptions`, `spend_entries`, `list_shares`) only through `SET LOCAL ROLE smartcart_app`
  as every `/me` route already does, so row-level security decides the rows. The role is
  `NOINHERIT`, so a route that forgot the switch cannot read them;
- three statements run on the service connection by design and have column-limited grants and
  policies: taking over a push endpoint registered to another account, reading and accepting an
  invite by the hash of its token, and the cleanup of a deleted account's shares and items;
- no DDL and no write to the catalog or the price tables. The nightly precompute and the alerts
  job write `effective_prices` and read every user's alerts: they keep the owner connection in
  `jobs.env` (below). `DELETE /me` needs `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`; the stand-in
  `auth.users` delete used on the demo database is something this role cannot do (the API logs a
  warning and the account's rows are removed regardless).

The role exists only if a password is supplied; otherwise the migration prints a NOTICE and creates
the function `smartcart_grant_api_role(role)` that holds the grants. Two ways, both from the laptop
and the **direct** connection (the pooler may reject the `options` startup parameter; unverified):

```bash
# 1. with the first migration: the password reaches the migration through libpq, never a file
export SMARTCART_API_PASSWORD="$(openssl rand -base64 24)"      # keep it in the password manager
PGOPTIONS="-c smartcart.api_password=$SMARTCART_API_PASSWORD" \
  DATABASE_URL="$DATABASE_URL_DIRECT" uv run smartcart-ingest migrate

# 2. after the migration has run without it (the file is recorded; it does not run twice)
psql "$DATABASE_URL_DIRECT" -c "create role smartcart_api login noinherit" -c "\password smartcart_api"
psql "$DATABASE_URL_DIRECT" -c "select smartcart_grant_api_role('smartcart_api')"
```

`smartcart_grant_api_role` is idempotent: run it again after a migration adds a table the API
uses. If it prints "auth schema grants ... left to a role that may grant on it", the migrating role
may not grant on Supabase's `auth` schema; run these three as `supabase_admin` in the SQL editor
(unverified which role owns the schema): `grant usage on schema auth to smartcart_api; grant select
(id) on auth.users to smartcart_api; grant execute on function auth.uid() to smartcart_api;`. The
API needs them to check that a token's account exists before storing an event and for the
policies' `auth.uid()`. The pooler user name of a role carries the project reference (`role.projectref`,
unverified): take the string from the Connect panel and put `smartcart_api` in front of it.
The grants are tested on a throwaway role by `services/api/tests/test_api_role.py`, and the whole API suite
passes as that role with `SMARTCART_TEST_AS_API_ROLE=1 uv run pytest services/api/tests`
(one stand-in `auth.users` delete test differs on purpose). Treat `api.env` as a secret of the
restricted role, no longer as the owner password; the owner password lives in `jobs.env` and on the
laptop.

### Batch jobs, at run time

`smartcart-precompute.service` and `smartcart-alerts.service` read `ingest.env`, `api.env`, then
`/etc/smartcart/jobs.env`, the last one winning. Put a `DATABASE_URL` in `jobs.env` that may delete
`effective_prices` rows (the precompute replaces them) and read every user's alerts (the alerts job
bypasses RLS): the owner (`postgres`) over the session pooler or the direct host, not
`smartcart_api`. `SMARTCART_PRECOMPUTE_ARGS`
and `SMARTCART_ALERTS_ARGS` add flags (`--chain ID`, `--dry-run`).

### Web, at build time

`NEXT_PUBLIC_*` values are inlined into the JavaScript by `next build`, so they are fixed per build:
on Vercel they are project environment variables (Production), for the image they are build
arguments (`deploy.yml` reads them from GitHub repository **variables**). All of them reach every
browser: nothing secret belongs here.

| Variable | Required | Meaning |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | yes | `https://api.<your domain>`, the API origin |
| `NEXT_PUBLIC_SITE_URL` | yes | `https://<your domain>`: canonical URLs, sitemap, JSON-LD |
| `NEXT_PUBLIC_SUPABASE_URL` | yes | `https://<project>.supabase.co`; without it the app stays signed out |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | yes | the project's anon (public) key |
| `NEXT_PUBLIC_VAPID_PUBLIC_KEY` | for web push | the public half of the VAPID pair |
| `NEXT_PUBLIC_BETA_EVENTS` | beta build only | `1` turns on the consented beta events (docs/web.md) |
| `NEXT_PUBLIC_CONTACT_EMAIL` | no | contact address on the accessibility statement |
| `NEXT_PUBLIC_CONTACT_NAME` | no | the accessibility coordinator's name on the statement |
| `NEXT_PUBLIC_INDEX_UNPRICED` | no | `0` keeps product pages without a price out of the index (`noindex`, not in the sitemap); default on (docs/seo.md) |
| `SEO_STRICT_SITE_URL` | build only | `1` fails the build unless `NEXT_PUBLIC_SITE_URL` is an absolute https URL; `deploy.yml` sets it whenever the site URL variable is set |
| `NEXT_PUBLIC_API_MOCK`, `NEXT_PUBLIC_DISABLE_SW` | never in production | test switches (mock API, no service worker) |

The web image's runtime takes only `PORT` (3000) and `HOSTNAME` (0.0.0.0).

### GitHub: secrets and variables for `deploy.yml`

Settings, Secrets and variables, Actions. Put the secrets in an environment named `production`
(the workflow's jobs use it) and add required reviewers there if you want a human gate before each
deploy (recommended: the VPS key is root-equivalent, below).

| Name | Kind | For |
|---|---|---|
| `VPS_SSH_HOST` | secret | API deploy: the VPS host name or IP |
| `VPS_SSH_KEY` | secret | API deploy: private key of the deploy user (ed25519, no passphrase) |
| `VPS_SSH_USER` | secret, optional | default `deploy` |
| `VPS_SSH_PORT` | secret, optional | default 22 |
| `VPS_SSH_KNOWN_HOSTS` | secret, recommended | `ssh-keyscan -H <host>` output; without it the host key is trusted on first use, with a warning |
| `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | secrets | web deploy (Vercel account settings, Tokens; the two ids are in `.vercel/project.json` after `vercel link`) |
| `SUPABASE_JWT_SECRET` | secret, optional | only for the demo smoke (`DEPLOY_SMOKE_DEMO=1`) |
| `NEXT_PUBLIC_*` (the table above) | variables | the web image's build arguments |
| `SMARTCART_API_DOMAIN` | variable | passed to `setup.sh`: Caddy and TLS for this host name |
| `DEPLOY_API_URL`, `DEPLOY_WEB_URL` | variables | smoke targets after the deploy |
| `DEPLOY_SMOKE_DEMO` | variable | `1` only for a deployment that holds the synthetic demo data: also runs `scripts/demo/smoke.py` |

A missing secret never fails the workflow: the job prints which one to set (a notice and a line in
the run summary) and ends green. The images are always built and pushed (`GITHUB_TOKEN` is enough).

## First deploy, in order

Prerequisite: `infra-provisioning.md` sections 2 to 6 done (Supabase project with the extensions,
roles, bucket, VPS with `setup.sh` run once and the smoke scripts passing), a domain, and the owner's
laptop with `uv`, `psql` and the repo.

**1. Schema.** From the laptop, with the owner's direct connection (never committed):

```bash
export DATABASE_URL_DIRECT='postgresql://postgres:...@db.<project>.supabase.co:5432/postgres?sslmode=require'
DATABASE_URL="$DATABASE_URL_DIRECT" uv run smartcart-ingest migrate     # "applied ..." lines, then nothing on a re-run
DATABASE_URL="$DATABASE_URL_DIRECT" uv run smartcart-catalog seed       # 203 taxonomy nodes, 222 rules, 245 canonicals
```

(The same from the image: `docker run --rm -e DATABASE_URL="$DATABASE_URL_DIRECT"
ghcr.io/<owner>/smartcart-api:<tag> smartcart-ingest migrate`.) Run `migrate` before every release
that adds a file under `supabase/migrations`; the workflow does not migrate.

**2. DNS.** `api.<domain>` A record to the VPS. `<domain>` to Vercel (Vercel shows the record to
create when you add the domain to the project; unverified which record type it asks for).

**3. VPS environment.** On the VPS, as root:

```bash
sudoedit /etc/smartcart/api.env     # DATABASE_URL (pooler, smartcart_api), DB_POOLER_MODE, SUPABASE_JWT_SECRET,
                                    # API_CORS_ORIGINS=https://<domain>, API_PUBLIC_WEB_URL=https://<domain>,
                                    # SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, VAPID_* (runbook step 11)
sudoedit /etc/smartcart/jobs.env    # DATABASE_URL for precompute and alerts (postgres)
sudo SMARTCART_API_DOMAIN=api.<domain> bash /opt/smartcart/infra/vps/setup.sh
# ... ==> API healthy: {"status":"ok","version":"0.3.0"}
curl -fsS https://api.<domain>/health
```

**4. Deploy user for the workflow.** On the VPS:

```bash
sudo adduser --disabled-password --gecos "" deploy
sudo install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
# on the laptop: ssh-keygen -t ed25519 -f smartcart-deploy -N '' ; paste smartcart-deploy.pub:
sudo tee /home/deploy/.ssh/authorized_keys <<<'ssh-ed25519 AAAA... smartcart-deploy'
sudo chown deploy:deploy /home/deploy/.ssh/authorized_keys && sudo chmod 600 /home/deploy/.ssh/authorized_keys
echo 'deploy ALL=(root) NOPASSWD:SETENV: /usr/bin/bash /opt/smartcart/infra/vps/setup.sh' \
  | sudo tee /etc/sudoers.d/smartcart-deploy && sudo chmod 440 /etc/sudoers.d/smartcart-deploy
sudo visudo -c
```

The workflow runs `sudo -n SMARTCART_REPO_REF=<tag> [SMARTCART_API_DOMAIN=...] /usr/bin/bash
/opt/smartcart/infra/vps/setup.sh` (twice, so a release's own `setup.sh` applies it; see the comment
in `deploy.yml`). `SETENV` lets that one command take those variables, and `setup.sh` runs as root
code from the repository at that ref, so the deploy key is root-equivalent on the VPS: keep it only
in the `production` environment. Then paste the private key as `VPS_SSH_KEY`, the host as
`VPS_SSH_HOST`, and `ssh-keyscan -H <host>` as `VPS_SSH_KNOWN_HOSTS`. If the repository is private,
the VPS clones with the read-only deploy key of `infra-provisioning.md` section 5.2.

**5. Vercel.** Create the project from the repository with Root Directory `apps/web` (framework
Next.js is detected; `vercel.json` sets the rest). In Project Settings, Environment Variables,
Production: the web table above. Add the domain. Create a token (Account Settings, Tokens) and run
`npx vercel link` once in the repo to read the org and project ids from `.vercel/project.json`
(do not commit `.vercel/`). Paste `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`. Git
auto-deploys are off in `vercel.json` so that a deploy is always a tag; turn them back on in the
project if you want preview deployments of pull requests.

**6. GitHub variables.** `NEXT_PUBLIC_*` (for the web image), `SMARTCART_API_DOMAIN`,
`DEPLOY_API_URL=https://api.<domain>`, `DEPLOY_WEB_URL=https://<domain>`.

**7. Go.**

```bash
git tag v0.1.0 && git push origin v0.1.0
```

The run: images (about 5 to 10 minutes cold, estimate), then the API and the web deploys in
parallel, then the smoke job. Green smoke means: `/health` ok, `/search` and `/parse-list` answer,
`/compare` answers, `/me/alerts` is 401 without a token, the API's CORS allows the site origin, and
the site serves `/`, `/sw.js` (with `Cache-Control: no-cache`), `/manifest.webmanifest`,
`/sitemap.xml`, `/robots.txt` and `/methodology`. The smoke is data-independent on purpose:
`scripts/demo/smoke.py` asserts the synthetic demo's prices and only runs with `DEPLOY_SMOKE_DEMO=1`.

**8. After the first nightly cycle.** The next morning: `systemctl list-timers 'smartcart-*'`,
`tail /var/log/smartcart/precompute.log` (a JSON line with `rows_written`), then
`uv run smartcart-catalog export-seo` and a new tag so the SEO pages carry real data
(`phase-2-status.md`, runbook step 8).

## Every later release

`git tag vX.Y.Z && git push origin vX.Y.Z`. Before it, if the release adds a migration, step 1's
`migrate`. To deploy a branch or commit by hand: Actions, Deploy, Run workflow, `ref`.

## Rollback

Every release is a tag and an image pair, so rolling back is deploying the previous tag.

- **Everything:** Actions, Deploy, Run workflow, `ref = v<previous>`. It re-runs `setup.sh` at that
  tag on the VPS (code, units, restart, health check) and redeploys that tag's web build.
- **API only, from the VPS:** `sudo SMARTCART_REPO_REF=v<previous> bash
  /opt/smartcart/infra/vps/setup.sh` (twice if `setup.sh` itself changed between the versions).
- **Web only, on Vercel:** Deployments, the previous production deployment, Promote to Production
  (instant; no rebuild; unverified that the button keeps this name).
- **Web or API from images:** `docker run ... ghcr.io/<owner>/smartcart-web:v<previous>` (or
  `smartcart-api`); every tag and `sha-<commit>` stays in GHCR.
- **Schema:** migrations are forward-only. A release whose migration must be undone needs a new
  migration; restore from backup only for data loss (`infra-provisioning.md` section 4). Code of
  the previous tag runs on a newer schema as long as migrations only add, which has held so far.

Stop everything without uninstalling: `sudo systemctl disable --now smartcart-api
smartcart-precompute.timer smartcart-alerts.timer smartcart-ingest-full.timer
smartcart-ingest-delta.timer`.

## Sizing from the load test

`scripts/loadtest/run.py` builds a scaled synthetic world with the adapters' fixture builders,
loads it through the real adapters, gates and loader into a throwaway Postgres, and times the jobs
and the routes (docs/optimizer.md has the full table). Measured on 2026-10-08 in this build
container (4 vCPU Intel Xeon 2.1 GHz shared with other jobs, load average 3 to 7; Postgres 16 on the
same machine with `fsync` off; Python 3.13), on 300 stores, 5,000 items mapped to 245 canonicals,
207,000 price events over 90 days, 19,600 promotions and 144,000 effective-price rows. All of it
**synthetic**: it sizes the machine, it says nothing about real data.

Two runs of the same world, one after the other (load average 7.1 falling to 2.7 in the first,
2.1 rising to 8.6 in the second); routes over HTTP, one request at a time unless stated, two API
workers:

| Measure | Run 1 | Run 2 |
|---|---|---|
| Load 7,810 files, 1.8 million price records, through adapters, gates and loader (4 chains in parallel) | 139 s | 163 s |
| `smartcart-api precompute`, 144,380 rows | 26.9 s | 33.2 s |
| `smartcart-api alerts-run --dry-run`, 1,000 alerts (990 fired) | 2.5 s | 3.0 s |
| `/search`, 50 queries, p50 / p95 | 46 / 61 ms | 56 / 92 ms |
| `/compare`, 50 baskets of 25 items, 5 km (median 55 stores in the radius), p50 / p95 | 72 / 171 ms | 71 / 135 ms |
| `/optimize` heuristic, K = 2, same baskets, p50 / p95 | 28 / 37 ms | 23 / 27 ms |
| `/optimize` MILP, K = 2, same baskets, p50 / p95 | 44 / 64 ms | 36 / 94 ms |
| `/compare` from 8 clients at once: throughput, p50 | 23.4 req/s, 330 ms | 17.4 req/s, 443 ms |
| API memory, peak RSS (2 workers + supervisor) | | about 560 MB (250 MB per worker) |
| The whole test | 250 s | 283 s |

What follows from it (estimates):

- **The API fits the planned VPS** (2 vCPU, 4 GB, `infra-provisioning.md` section 5.1). A route is
  tens of milliseconds of CPU, mostly in Python; the database work is on Supabase, not on the VPS.
  Two workers use about 560 MB of memory together, which leaves room for an ingestion run in 4 GB.
- **Throughput:** with Postgres on the same 4 vCPUs, 8 concurrent clients got 17 to 23
  `/compare` requests per second. A beta of 20 to 50 people (`beta-plan.md`) makes a few requests a
  minute; the headroom is two orders of magnitude. Add workers (`WEB_CONCURRENCY`, one per vCPU)
  before adding machines, and keep `workers x API_POOL_MAX` under the pooler's limit.
- **The nightly precompute** took 27 to 33 s for 144,000 rows. The earlier synthetic
  measurement (675,000 rows in 52 s, `docs/api.md`) scales the same way; on the real catalog
  expect minutes, not hours. The 09:30 timer leaves the whole morning.
- **The alerts job** evaluated 1,000 alerts in 2 to 3 s; hourly is cheap.
- **Ingestion** (the replay) loaded 1.8 million price records in 139 to 163 s with four chains in
  parallel, on a database with `fsync` off: a real daily full sync is I/O and portal bound, not
  CPU bound, and the 2-hour lock timeout in the units is ample.
- **Watch** the `/compare` tail: it prices every store in the radius (median 55 in this world's
  Gush Dan), so it grows with store density, while `/optimize` prices only the 10 nearest.

## Costs (estimates)

| Item | Monthly | Label |
|---|---|---|
| Supabase Pro | 25 USD, includes 10 USD compute credit | verified (`architecture.md` section 9) |
| Israeli VPS (ingestion and API) | 10 to 20 USD | estimate (research) |
| Object storage (R2) | about 5 USD | estimate (research) |
| Separate API container | 0 (the API runs on the VPS); 10 to 30 USD if moved to Fly.io or Railway | estimate (`architecture.md`) |
| Vercel | Hobby is free but for non-commercial use; Pro is per seat | unverified (check vercel.com/pricing); the web image on the VPS or any container host is the alternative |
| GHCR | free for public images; private images count against the account's package storage | unverified |
| Domain | about 10 to 20 USD a year | estimate |
| TLS (Caddy, Let's Encrypt) | 0 | unverified that nothing changes |
| **Total** | about 40 to 100 USD at MVP scale | estimate (`architecture.md` section 9), unchanged by this layout |

## How this was validated

On 2026-10-08, in the build container, with Docker 29 available:

- Both images built (`docker build`, BuildKit) and linted with hadolint 2.12 (clean; DL3006 is
  ignored on the `FROM ${ARG}` lines because the default is pinned). `deploy.yml` passes actionlint
  1.7.7 with shellcheck; `setup.sh` passes shellcheck 0.10; the five new units pass
  `systemd-analyze verify`.
- The API image: healthy by its own healthcheck, runs as uid 10001, OR-Tools imports, `alerts-run`
  and `smartcart-ingest migrate` run from the image; `scripts/demo/smoke.py` (11 checks) passed
  against the container on the demo database.
- The web image (standalone): `npm run e2e:fullstack` (6 tests) passed against the web container
  and the API container together (Playwright reuses a server already listening on its port outside
  CI), and the PWA specs of the mock suite (`tests/e2e/pwa.spec.ts`: manifest, Heebo offline,
  service worker precache and offline shell, 3 tests) passed against a container built with the
  service worker on. `/`, `/sw.js` (no-cache), `/manifest.webmanifest`, `/p/milk-fresh-3` (with
  JSON-LD), `/c/dairy`, `/methodology`, `/sitemap.xml`, `/robots.txt`, fonts and icons answered 200.
  The final container run used ports no other job on the machine used (API 8001, web 3231), and the
  API container's log shows it served the suite's `/optimize` calls.
- After all changes, the native suite (`scripts/demo/up.sh`, `smoke.py`, `npm run e2e:fullstack`
  with a fresh, non-standalone build) passed: 11 checks and 6 tests.
- The compose stack (`--profile app`): `migrate`, `api` and `web` healthy on the Supabase image,
  the demo data loaded into it with `scripts/demo/up.sh`, then the smoke test and the 6 fullstack
  tests passed against it, and `--profile jobs run --rm alerts` ran.
- Not run: `deploy.yml` itself (it needs GitHub), `setup.sh` on a real Ubuntu host with systemd,
  Caddy, Vercel. Base images had to come through a CA-trusting local variant of the same pinned
  images (`--build-arg PYTHON_IMAGE=...`, `NODE_IMAGE=...`) because this container reaches the
  network through a TLS-inspecting proxy; the Dockerfiles are unchanged by that.

- Finish round (2026-10-08): the API image rebuilt without Streamlit (sizes in the note below);
  from it `import smartcart_api.main` loads neither Streamlit nor pyarrow, `smartcart-api`,
  `smartcart-ingest` and `smartcart-catalog` start, and `smartcart-catalog review` prints the hint for
  the missing extra. The API role, the pooler mode, the idempotent spend entry and the search misses
  are covered by tests on a local Postgres (`test_api_role.py`, `test_api_db_pooler.py`,
  `test_api_spend_idempotency.py`, `test_api_search_misses.py`); **not run**: the role migration on
  Supabase itself (the `auth` schema grants are the part most likely to need the manual step above),
  and the transaction pooler against Supavisor.

Known image notes: the API image was about 1.39 GB on disk (326 MB compressed) because the catalog
package depended on Streamlit and with it pyarrow, altair and pydeck for its review UI. Streamlit is
now the `review` extra of `smartcart-catalog`, which the API does not install (the build fails if
`import streamlit` works in the image): **1.05 GB on disk, 248 MB compressed** (measured 2026-10-08
with `docker image inspect`, the same base image, before and after; 25% and 24% less). The rest is dominated by Playwright (140 MB, pulled by the upstream scraper package through
`smartcart-ingest`, which the image carries only for `smartcart-ingest migrate`), OR-Tools (80 MB),
pandas (75 MB, a hard dependency of both OR-Tools and the upstream parser) and numpy (70 MB with its
libraries), botocore (31 MB). Splitting a migrate-only extra out of `smartcart-ingest` would remove
roughly 200 MB more (estimate, from those sizes); it is not done. `@zxing/library` 0.23 declares Node 24 in
`engines` (a warning on Node 22, which CI uses too).
