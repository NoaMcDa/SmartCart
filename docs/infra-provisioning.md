# Infrastructure provisioning (phase 0)

Step by step for the owner. Written 2026-10-06 for issues #14 (Supabase database) and #22 (Israeli-IP
VPS and object storage). The decisions behind it are D3 (Supabase-hosted Postgres) and D13 (chain
list) in `decisions.md`; the cost table is `architecture.md` section 9.

**Nothing described here has been provisioned.** The Supabase project, the VPS and the bucket do not
exist yet, and the author of this document could not create them. Everything below is a procedure
plus scripts that were written without being run against live services. Where a step depends on the
current behavior of a vendor product, the text says so and tells you what to confirm.

Evidence labels follow the research: **verified** (stated in the research or in the project docs, with
the source), **estimate** (the author's or the research's estimate), **unverified** (a vendor fact from
general knowledge that this document could not check; confirm it in the vendor's dashboard or docs
before relying on it).

## 0. What is done and what only you can do

Everything in the repo is ready to run once the environment variables from `.env.example` exist. The
acceptance items below can be ticked only after you run the listed command against the real service.

| Issue | Acceptance item | State | How it gets ticked |
|---|---|---|---|
| #14 | D3 confirmed or overridden in `decisions.md`, with the reason | Met in this change | Nothing to run |
| #14 | Supabase project exists with `postgis` and `vector` enabled, shown by `select extname from pg_extension` | Blocked on provisioning | Section 2, then `psql "$DATABASE_URL_DIRECT" -f infra/smoke/db_smoke.sql` |
| #14 | Smoke test runs a PostGIS distance query and a pgvector similarity query | Blocked on provisioning | Same command; it ends with the row `smoke ok` |
| #14 | Connection and role policy documented, no credentials committed | Met in this change (sections 3 and 7) | Nothing to run; the roles themselves are created in section 3 |
| #14 | Backup policy documented, including a restore test result | Policy met in this change (section 4); **restore test result blocked** | Run the restore test in section 4.3 and paste the record into section 4.4 |
| #22 | VPS has an Israeli IP, verified by a geolocation check | Blocked on provisioning | On the VPS: `bash infra/smoke/check_israeli_ip.sh` exits 0 |
| #22 | Test download from a portal known to block cloud IPs succeeds from the VPS | Blocked on provisioning | On the VPS: `bash infra/smoke/check_portals.sh` prints `download probe: PASS` (laibcatalog, verified in the research to block cloud IPs) |
| #22 | Raw file uploaded to and read back from the bucket with least-privilege credentials | Blocked on provisioning | With the ingest token in the environment: `uv run infra/smoke/bucket_roundtrip.py` prints `PASS` |
| #22 | No secrets in the repository; secrets approach documented | Met in this change (section 7, `.env.example`) | Nothing to run |
| #22 | Deployment and access instructions written down | Met in this change (section 5) | Nothing to run |
| #22 | Baseline hardening (non-root user, SSH keys only, firewall, automatic updates) | Script written; applied only when you run it | `sudo bash infra/vps/setup.sh`, then the checks in section 5.5 |

## 1. Before you start

- A GitHub account with access to `NoaMcDa/SmartCart` (the VPS clones it).
- A password manager for the secrets in section 7.
- Accounts: Supabase (Pro plan, 25 USD per month, verified in `architecture.md` section 9), a VPS provider, and Cloudflare (R2) or AWS (S3).
- On your laptop: `psql` (PostgreSQL client 16 or newer) and `uv`.
- Optional: Terraform 1.6 or newer for the skeleton in `infra/terraform/`. The skeleton covers the Supabase project, the R2 bucket and one VPS. It has never been validated against the live providers, so the manual steps below are the supported path; use Terraform only if you want the project recorded as code.

Expected monthly cost, all **estimates** from the research and `architecture.md`: Supabase Pro 25 USD
(verified price), Israeli VPS 10 to 20 USD, object storage about 5 USD. The whole MVP is 40 to 100 USD
per month and this section is the first third of it.

## 2. Supabase project

### 2.1 Create it

1. Sign in at supabase.com, create an organization if you have none, and upgrade it to Pro (daily backups, section 4, need it).
2. New project. Name `smartcart`. Choose the database password with the password manager (32 or more random characters) and keep it there. Region: **there is no Israeli region** (unverified); the nearest European region is the working choice, `eu-central-1` Frankfurt as the **estimate**. Measure before committing: from the VPS (section 5), run `psql "$DATABASE_URL_DIRECT" -c 'select 1' -c '\timing on'` a few times; the target is a round trip well under 100 ms (estimate). Regions cannot be changed later without a migration, so test before loading data.
3. Postgres version: the issue asks for Postgres 16. The dashboard shows the version under Settings, Infrastructure. Confirm it is 16 or newer (unverified that new projects default to 16).
4. Copy the three connection strings from the Connect panel into the password manager (see section 3.2 for which is which). Do not paste them into chat, issues or the repo.

### 2.2 Enable the extensions

In the SQL editor, or with `psql "$DATABASE_URL_DIRECT"` as the `postgres` user:

```sql
create extension if not exists postgis  with schema extensions;
create extension if not exists vector   with schema extensions;
create extension if not exists pg_trgm  with schema extensions;  -- needed later for hybrid search
```

`pg_trgm` is not needed in phase 0; it is enabled now because `architecture.md` section 6 (search)
uses it and enabling it later is the same one line. Putting the extensions in the `extensions` schema
is the Supabase convention (unverified); the smoke script sets `search_path = public, extensions` so
it works either way. The schema migrations (a separate issue) must set the same search path, or
qualify the types, so that `geography` and `vector` columns resolve.

### 2.3 Run the smoke test

From the repo root, with the direct connection string of the `postgres` user:

```bash
export DATABASE_URL_DIRECT='postgresql://...'   # from your password manager, not from a file in the repo
psql "$DATABASE_URL_DIRECT" -f infra/smoke/db_smoke.sql
```

Expected output, in order (versions and the other extension rows will differ):

```
   extname    | extversion
--------------+------------
 pg_trgm      | 1.6
 pgcrypto     | 1.3
 plpgsql      | 1.0
 postgis      | 3.x.x
 vector       | 0.x.x
 ...
 distance_m
------------
      53888          <- about 54,000 m, Tel Aviv to Jerusalem
 cosine_distance
-----------------
 0.0085399...        <- vectors [1,2,3] and [1,2,4]
 result
----------
 smoke ok
```

The script also asserts that both extensions are enabled and that the two numbers fall in a sane
range (50,000 to 58,000 m; 0.0080 to 0.0090). If an assertion fails, `psql` stops with an error and
no `smoke ok` row is printed. Save the full output to attach to issue #14: that, with the Supabase
dashboard showing the project, is the evidence for the two database acceptance items.

## 3. Roles, connections and RLS

### 3.1 Roles

Three roles, least privilege. The tables do not exist yet (the schema is a separate issue, #27), so
grants are applied in the schema migration; the statements below create the roles and the default
privileges, and the schema issue adds explicit grants for each table it creates.

| Role | Used by | Rights | When |
|---|---|---|---|
| `postgres` | Owner only: migrations, enabling extensions, creating roles | Superuser-like on Supabase (unverified); never given to a worker | Now |
| `smartcart_ingest` | `smartcart-ingest` on the VPS, and later the catalog workers | Connect; usage on the schemas it writes; select, insert, update on the ingest tables (`chains`, `stores`, `items`, `prices`, `promos`, `file_tracking`, quarantine tables); **no DDL, no delete, no access to user tables** | Now |
| `smartcart_readonly` | The internal Streamlit dashboard (issue #46) | Select on ingest tables and views only | Now |
| `smartcart_api` | The FastAPI service | Select on catalog and effective-price tables; limited writes to its own tables | Phase 1, Track B (#64). The app role works with Supabase Auth and RLS; do not create it before the schema and policies exist |

Create the first two (the password prompt keeps the password out of shell history and the repo):

```sql
create role smartcart_ingest   login noinherit;
create role smartcart_readonly login noinherit;
\password smartcart_ingest
\password smartcart_readonly

grant usage on schema public to smartcart_ingest, smartcart_readonly;
alter default privileges in schema public
  grant select, insert, update on tables to smartcart_ingest;
alter default privileges in schema public
  grant usage, select on sequences to smartcart_ingest;
alter default privileges in schema public
  grant select on tables to smartcart_readonly;
```

Notes:
- Default privileges apply to tables created later by the role that ran `alter default privileges` (`postgres`). Run the migrations as `postgres` so they apply.
- Partitioned tables (`prices` by month): grants on the parent do not always cascade to partitions created later. The schema issue must either create partitions as `postgres` after the default privileges exist, or grant on each partition. Test this with an insert as `smartcart_ingest` in the schema issue's acceptance.
- `smartcart_ingest` gets no delete right by design: a bug in a worker cannot erase price history. Quarantined files are marked, not deleted.

### 3.2 Which connection for what (the pooler question)

Supabase offers a direct connection and a pooler (Supavisor) in session mode and in transaction mode.
The port numbers, host names and the IPv4 situation below are from general knowledge of the product
and are **unverified**: the Connect panel in the dashboard shows the current strings, and it wins.

| Use | Connection | Why |
|---|---|---|
| Migrations, `db_smoke.sql`, one-off admin work | Direct, as `postgres` | DDL and `\copy` want a stable session. The direct host may be IPv6 only unless the IPv4 add-on is bought (unverified); if your laptop or VPS has no IPv6, use the session pooler instead. |
| `smartcart-ingest` on the VPS | Session pooler (port 5432 on the pooler host), or direct if the VPS has IPv6 | The worker is a few long-lived processes that use `COPY`, long transactions and possibly prepared statements. Session mode keeps them working and works over IPv4. Cap the worker at 4 connections. |
| FastAPI, later | Transaction pooler (port 6543) | Many short requests. Prepared statements need care in transaction mode; decide in the API issue. |
| Dashboard | Session pooler or direct, as `smartcart_readonly` | Low volume. |

Rules:
- TLS always: `sslmode=require` in every URL (use `verify-full` with the Supabase CA certificate once you have downloaded it from the dashboard).
- Pooler user names carry the project reference (the form is `role.projectref`, unverified); take the exact string from the Connect panel and substitute the role name.
- One variable per purpose, never reused: `DATABASE_URL` (ingest role, pooled), `DATABASE_URL_DIRECT` (migrations and smoke), `DATABASE_URL_READONLY` (dashboard). Names are in `.env.example`.

### 3.3 Where `DATABASE_URL` lives

- On the VPS: `/etc/smartcart/ingest.env`, mode 0640, owner root, group `smartcart` (created empty by `setup.sh`). The systemd units read it through `EnvironmentFile=`. Not in the unit files, not in the repo, not in shell history.
- In CI: GitHub Actions secrets (repository settings, Secrets and variables, Actions), named exactly as in `.env.example`. Tests that need a database run against a throwaway Postgres container with PostGIS and pgvector in CI, not against the production project.
- On your laptop: a git-ignored `.env`, or your password manager's CLI. The `.gitignore` already excludes `.env` and `.env.*` except `.env.example`.
- Never in: issues, PR descriptions, chat, screenshots of the Connect panel.

### 3.4 RLS note

Supabase exposes the `public` schema through its REST API using the `anon` and `authenticated` roles
(unverified in detail, true as the default as far as the author knows). A table in `public` without
row-level security is therefore readable through the project's public API key. Phase 0 has no user
data, but the price tables are not meant to be served that way either, so one of these must hold
before the first table is created, and the schema issue (#27) chooses:
1. Create the ingest tables in a schema that is **not** in the exposed-schemas list (Settings, API), for example `ingest`; or
2. Enable RLS on every table and revoke access from `anon` and `authenticated`. Note that an enabled RLS table with no policy returns no rows to roles that do not bypass RLS, so `smartcart_ingest` and `smartcart_readonly` then need the `bypassrls` attribute or explicit policies.

Option 1 is the simpler fit for ingest data. If it is chosen, change `public` in the grants above to
that schema. Auth, user tables and their RLS policies are phase 1 (#64) and out of scope here.

## 4. Backups

### 4.1 Policy

| Item | Policy | State |
|---|---|---|
| Automatic backups | Supabase daily backups, included in Pro. Retention is 7 days on Pro (unverified; confirm in Database, Backups) | Starts when the Pro project exists |
| Point-in-time recovery (PITR) | **Not enabled in phase 0.** It is a paid add-on (price unverified) | Revisit before the first human-labeled data lands |
| Independent copy | The raw archive in the bucket (section 6) is the second copy of everything the database ingests, because loads are idempotent by file hash and can be replayed | Exists once the bucket and workers run |
| Restore test | Once now, then once per quarter and before any schema change that rewrites data | Not yet done |

Why PITR is off in phase 0: everything in the database during phase 0 is derived from public files
that can be re-downloaded (the source keeps files for 3 months, verified, research section 2.1) and
from the raw archive we keep ourselves, so the worst case is a replay, not a loss. That reasoning
stops being true when the catalog starts holding things no file can recreate: human review decisions,
gold-set labels (`gold_pairs`), and later user data. The trigger to enable PITR is therefore: before
the first label or user row is written (phase 1, Track A and Track B), whichever comes first. Record
that date in `decisions.md` under D3 when it happens.

Do not rely on one mechanism. Until PITR is on, add a weekly logical dump from the VPS to the bucket
under a separate `backups/` prefix (a `pg_dump` with the direct connection; the schema issue or an
ops issue should add the script, it is not part of this change).

### 4.2 Check the backup is happening

Dashboard, Database, Backups: confirm a daily backup row exists the day after the project is created.
Take a screenshot or copy the timestamp for the record in 4.4.

### 4.3 Restore test procedure

Do this once the schema exists and at least a few thousand rows are loaded, so the test means
something. A test on an empty database proves nothing. Never restore on top of the production project.

1. Pick the backup to test (the most recent daily backup) and note its timestamp. Note the production row counts at the moment you choose it, for the tables that exist: `select 'prices', count(*) from prices union all select 'items', count(*) from items;` (adapt to the schema).
2. Restore to a new, separate project. Preferred: the dashboard's restore-to-new-project action for a backup (unverified that this is available for daily backups on your plan; check). Fallback that always works: `pg_dump --format=custom` from production over the direct connection, create a scratch project (or a local container with PostGIS and pgvector), and `pg_restore` into it.
3. In the restored database run `psql "$RESTORED_URL" -f infra/smoke/db_smoke.sql` and the same row-count query. Row counts must equal the counts at the backup timestamp (equal to the production counts minus whatever loaded after it).
4. Run one real query the product depends on, for example the radius query over `stores` once it exists. It must return rows.
5. Delete the scratch project. Record the result in 4.4 and attach it to issue #14.

What to record: date of the test, who ran it, which backup (its timestamp) and the method, restore
duration from start to a passing smoke test, row counts before and after per table, the smoke
output, anything that surprised you, and the verdict. The recovery time observed is the number that
goes into any future "how long are we down" answer.

### 4.4 Restore test record

To be filled in by the owner. Acceptance item "backup policy documented, including a restore test result" stays open until this table has a row.

| Date | Run by | Backup used (timestamp) | Method | Duration | Row counts (prod / restored) | Smoke result | Verdict and notes |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## 5. Israeli-IP VPS

### 5.1 Why and which provider

At least one portal family (laibcatalog, used by Victory and Machsanei Hashuk) blocks cloud IP ranges
(verified, research section 2.3, citing Segalil). D13 makes those two chains part of phase 0, so the
worker must run from an IP that the portals treat as Israeli and non-cloud. Whether a given provider's
range is blocked is exactly what `check_portals.sh` measures; the table below is a starting list and
every provider fact in it is **unverified**.

| Option | Israeli IP | Notes |
|---|---|---|
| Kamatera | Operates Israeli datacenters (unverified) | Israeli company, hourly or monthly billing, has a Terraform provider. The skeleton in `infra/terraform/` uses it. First choice to try. |
| Local Israeli VPS or hosting providers | Yes | Often the lowest risk of range blocking; monthly plans in the 10 to 20 USD range match the research estimate. Compare current offers. |
| AWS (il-central-1, Tel Aviv), Google Cloud (me-west1), Azure (Israel Central) | Region is in Israel (unverified for each) | These are the big cloud ranges a "block cloud IPs" rule is most likely to target; only use after `check_portals.sh` passes, and expect the cost to be above the 10 to 20 USD estimate. |
| Hetzner and most European providers | **No Israeli location as far as the author knows** (unverified) | The IP would geolocate to Europe and fail `check_israeli_ip.sh`. Not an option for this purpose. |

Size, from the ingest workload (I/O bound, no ML): 2 vCPU, 4 GB RAM, 40 GB disk, Ubuntu 24.04 LTS
(estimate). Cost 10 to 20 USD per month (estimate, research). Buy a plan you can cancel after a short
period: the acceptance checks below decide whether the provider works, and discovering that after a
year is the expensive way to learn it.

### 5.2 Create the server

1. Create the server (Ubuntu 24.04, the size above, an Israeli datacenter) with your SSH public key. Do not enable password login.
2. Create a non-root admin user with sudo and your key, then confirm you can log in with it. `setup.sh` only disables root and password login when it can see a key for a login user, so it cannot lock you out; still, do this first:
   ```bash
   adduser --disabled-password --gecos "" admin
   usermod -aG sudo admin
   install -d -m 700 -o admin -g admin /home/admin/.ssh
   install -m 600 -o admin -g admin /root/.ssh/authorized_keys /home/admin/.ssh/authorized_keys
   ```
   Then log out and log in as `admin`.
3. If the repo is private, create a read-only deploy key: `ssh-keygen -t ed25519 -f deploy_key -N ''` on your laptop, add `deploy_key.pub` in the repo's Settings, Deploy keys (read-only), and place the private key at `/var/lib/smartcart/.ssh/id_ed25519` (mode 0600, owner `smartcart`) after the first `setup.sh` run creates the user; then use an `ssh` URL in `SMARTCART_REPO_URL` and run `setup.sh` again.

### 5.3 Run the setup script

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/NoaMcDa/SmartCart.git ~/SmartCart   # or your ssh URL
cd ~/SmartCart
sudo bash infra/vps/setup.sh
```

The script is idempotent: run it again after any repo update (it fetches `SMARTCART_REPO_REF`,
default `main`, and re-syncs the environment). It:

- installs system packages, `uv`, and Python 3.12 (system-wide under `/opt/uv-python`);
- creates the `smartcart` user (no login shell), `/opt/smartcart` (the checkout and `.venv`), `/var/lib/smartcart`, `/var/log/smartcart`, and an empty `/etc/smartcart/ingest.env`;
- runs `uv sync --package smartcart-ingest` so `smartcart-ingest` is at `/opt/smartcart/.venv/bin/smartcart-ingest`;
- installs four systemd units: `smartcart-ingest-full.timer` (daily at 06:00 and 08:30 Israel time, the second pass because the laibcatalog listing is empty until about 08:00, D13) and `smartcart-ingest-delta.timer` (hourly at minute 20), both calling `smartcart-ingest` through a shared lock so a delta never runs while the full sync is running;
- rotates `/var/log/smartcart/*.log` daily for 14 days and caps the journal at 500 MB;
- hardens: firewall with only SSH inbound, key-only SSH, root login off when an admin key exists, automatic security updates.

The unit files call `smartcart-ingest run --mode full` and `... --mode delta` by default. The CLI does
not exist yet (it arrives with issues #32, #37 and #49), so those argument names are a placeholder.
When the real names are decided, set `SMARTCART_INGEST_FULL_ARGS` and `SMARTCART_INGEST_DELTA_ARGS` in
`/etc/smartcart/ingest.env`, or edit the unit files, then `sudo systemctl daemon-reload`. Until the CLI
exists and `DATABASE_URL` is set, the timers are enabled but not started.

Fill the environment file, as root (copy the names from `.env.example`; values from your password manager):

```bash
sudoedit /etc/smartcart/ingest.env      # DATABASE_URL=..., S3_ENDPOINT_URL=..., S3_BUCKET=..., S3_ACCESS_KEY_ID=..., ...
sudo systemctl start smartcart-ingest-full.timer smartcart-ingest-delta.timer
```

### 5.4 Run the two smoke scripts

Both run on the VPS, from the repo checkout.

```bash
bash infra/smoke/check_israeli_ip.sh
```

Expected, and the exit code is 0:

```
public ip:        <the VPS address>
service 1 (https://ipinfo.io/country): IL
service 2 (https://ifconfig.co/country-iso): IL
PASS: both services report IL.
```

Exit 1 means a service places the IP outside Israel: the provider's range is not Israeli, so change
provider (do not try to work around it). Exit 2 means a service did not answer; wait and re-run.

```bash
bash infra/smoke/check_portals.sh
```

Expected, with exit code 0 (status codes and wording of rows will vary; what matters is no row says
`UNREACHABLE`, `BLOCKED?` or `ERROR`):

```
PORTAL                                       HTTP   RESULT
publishedprices (Cerberus, task host)        200    OK
publishedprices (Cerberus, upstream host)    200    OK
Shufersal                                    200    OK
laibcatalog (Victory, Machsanei Hashuk)      200    OK
matrixcatalog                                200    OK
Carrefour / Yeinot Bitan                     200    OK
Hazi Hinam                                   200    OK
King Store (Bina)                            200    OK

download probe: laibcatalog chain 7290696200003
  downloading Stores7290696200003-....gz
  ok: 12345 bytes, archive magic 1f8b

reachability failures: 0
download probe:        PASS
```

Exit 2 with `INCONCLUSIVE` means the laibcatalog listing was empty (it is, between midnight and about
08:00 Israel time, D13): run it again in the morning. An optional comparison proves the block is real:
run the same script from a non-Israeli cloud machine and expect the laibcatalog row or the download
probe to fail there. The `PASS` of the download probe is the evidence for the #22 item "a test
download from a portal known to block cloud IPs succeeds from the VPS". The other portal hosts in the
list come from the upstream scraper source, and the first row uses the host name given in the issue;
if one is retired the row fails, which is useful information for the adapter issues.

### 5.5 Check the hardening and operate the timers

```bash
sudo ufw status verbose                      # default deny incoming, only the SSH port allowed
sudo sshd -T | grep -Ei 'passwordauth|permitroot'   # passwordauthentication no
systemctl list-timers 'smartcart-*'          # next run for both timers
journalctl -u smartcart-ingest-full -n 50    # unit status lines; worker output is in the log files
tail -n 100 /var/log/smartcart/ingest-full.log
sudo systemctl start smartcart-ingest-full.service   # run a full sync now (waits for the lock)
```

Deploy an update: `cd ~/SmartCart && sudo bash infra/vps/setup.sh` (use `SMARTCART_REPO_REF=<tag or
branch>` to pin). Roll back: run it again with the previous tag. Stop all ingestion: `sudo systemctl
disable --now smartcart-ingest-full.timer smartcart-ingest-delta.timer`.

## 6. Object storage for the raw archive

### 6.1 Create the bucket (Cloudflare R2)

1. Cloudflare dashboard, R2, create bucket `smartcart-raw-archive`, location hint Eastern Europe (the closest to the VPS, estimate). Keep it private: no public bucket URL, no custom domain.
2. R2, Manage API tokens, create two tokens, each scoped to this bucket only, never account-wide:
   - **ingest-writer**: Object Read and Write, applied to the one bucket. This goes on the VPS. It can write and read the archive; the smoke script's delete step is then expected to be refused, which is fine (see below).
   - **archive-admin**: Admin Read and Write on the one bucket, for cleanup, lifecycle changes and removing smoke objects. Keep it in the password manager, **not on the VPS**.
3. Copy the endpoint (`https://<account id>.r2.cloudflarestorage.com`), the access key id and the secret into the password manager; the secret is shown only once.
4. Lifecycle rules (dashboard, bucket settings): expire objects under `smoke/` after 1 day. The retention rule for `raw/` is the open question below.

If you choose AWS S3 instead, create a private bucket with all public access blocked, versioning off,
and an IAM user for the worker with this policy. S3 can scope to a key prefix, which is stricter than
R2's bucket-level tokens (unverified that R2 cannot scope by prefix; check):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": ["arn:aws:s3:::BUCKET/raw/*", "arn:aws:s3:::BUCKET/smoke/*"] },
    { "Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::BUCKET" }
  ]
}
```

(Replace `BUCKET`. For S3 leave `S3_ENDPOINT_URL` empty and set `S3_REGION`.)

### 6.2 Key layout and retention

Layout: `raw/{chain_id}/{yyyy-mm-dd}/{file_type}/{sha256}.xml.gz`, where `chain_id` is the chain
identifier from D13 (the 13-digit id), `yyyy-mm-dd` is the publication date in Israel time,
`file_type` is one of `stores`, `price`, `pricefull`, `promo`, `promofull`, and `sha256` is the hash of
the file's bytes. The hash in the name makes uploads idempotent: the same file always maps to the same
key. The original file name goes in the object's metadata. Test objects live under `smoke/`. Database
backups, when added, live under `backups/`.

Retention: the source keeps files for only 3 months (verified, research section 2.1), so the archive
is the only long-term copy. Proposed policy (a policy proposal, not a measured need): keep `raw/` for
13 months, then expire, so a year-over-year comparison is possible; revisit after two weeks of real
loads, when the monthly volume is known. The bucket's size is not known today and no figure is
asserted here. The 5 USD per month storage figure is the research's estimate.

### 6.3 Run the round trip

On the VPS, or anywhere with the ingest-writer token in the environment (never pasted on the command
line):

```bash
set -a; . /etc/smartcart/ingest.env; set +a      # or export the five S3_* variables from your manager
uv run infra/smoke/bucket_roundtrip.py
```

`uv` reads the inline dependency block (boto3) so nothing is installed into the project. Expected:

```
bucket=smartcart-raw-archive endpoint=https://<account id>.r2.cloudflarestorage.com key=smoke/20261006T101500Z-1a2b3c4d.txt
upload:   ok
read-back: ok (sha256 matches)
delete:   denied or failed (An error occurred (AccessDenied) ...).
WARN: remove s3://smartcart-raw-archive/smoke/20261006T101500Z-1a2b3c4d.txt with an admin credential.
PASS
```

`PASS` with the delete warning is the intended result for a write-once ingest token; the object
expires by the 1-day lifecycle rule or with the admin token. Set `SMOKE_REQUIRE_DELETE=1` with the
admin token to test delete too. Exit 1 is a failure (wrong endpoint, region, or token scope); exit 2 is
missing variables.

## 7. Secrets approach

Rules: no secret is ever committed; `.env.example` lists every variable name, with empty values, and
is the catalog; a new variable is added to `.env.example` in the same change that starts using it.

| Secret | Lives in | Read by | Rotation |
|---|---|---|---|
| `postgres` password (owner) | Password manager only | You, for migrations | Change in the dashboard (Database settings) when anyone who knew it leaves, or yearly; update the manager entry |
| `DATABASE_URL` (ingest role) | `/etc/smartcart/ingest.env` on the VPS; GitHub Actions secret if CI needs it | `smartcart-ingest` | `alter role smartcart_ingest password ...` via `\password`, update the env file, `sudo systemctl restart` the timers; overlap is not needed because jobs are short |
| `DATABASE_URL_READONLY` | Dashboard host's environment | Streamlit dashboard | Same, per role |
| `S3_*` ingest token | `/etc/smartcart/ingest.env` | `smartcart-ingest` | Create a new R2 token, update the env file, run the round trip, then revoke the old one |
| `archive-admin` token | Password manager | You | Create on demand, delete after use if you can |
| SSH keys | Your laptop; the public half in `authorized_keys` | You | Add the new key, test it, remove the old one |
| Deploy key (private repo only) | `/var/lib/smartcart/.ssh/` on the VPS | `setup.sh` git fetch | Regenerate, replace in repo settings |
| Terraform tokens | `TF_VAR_*` in your shell session | Terraform | Per vendor |

GitHub Actions: repository settings, Secrets and variables, Actions. Use secret names identical to the
variable names in `.env.example`. Prefer environment-scoped secrets with required reviewers for any
workflow that touches the production database. Pull requests from forks do not receive secrets, which
is the behavior we want.

If a secret leaks (pasted into an issue, a log, a commit): rotate it first, then clean up. Rewriting
git history does not un-leak it.

## 8. Order of operations

1. Section 2: Supabase project, extensions, `db_smoke.sql`. Tick the two database items of #14.
2. Section 3: roles, record the connection strings in the password manager.
3. Section 6: bucket and both tokens.
4. Section 5: VPS, `setup.sh`, the two smoke scripts, the bucket round trip from the VPS. Tick the first three items of #22.
5. Wait for the schema (#27) and some real loads, then run the restore test (section 4.3) and fill 4.4. Tick the last item of #14.
