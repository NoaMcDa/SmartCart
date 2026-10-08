# Ingestion pipeline

How transparency files get from a chain portal into Postgres: download, tracking, quality gates,
the loader, the schedule and alerts. Covers issues #37 (idempotent downloads, full before delta),
#42 (quality gates, quarantine, alerts) and #49 (hourly deltas for the main chains). Adapters (one
per chain, issue #32) are documented with their code in `services/ingest/smartcart_ingest/adapters`.

Code: `services/ingest/smartcart_ingest/` — `download.py`, `rawstore.py`, `tracking.py`,
`quality.py`, `loader.py`, `scheduler.py`, `alerts.py`, `settings.py`, `cli.py`.

## One file, end to end

```
portal listing ──> fetch bytes ──> sha256 ──(hash loaded or quarantined?)──> skip, log
                                     │
                                     ├─> file_tracking: seen ──> raw archive ──> downloaded
                                     │
     delta (Price/Promo) and no loaded full file of the same kind for that store and day?
                                     ├─> held (retried on later runs, never dropped)
                                     │
                                     ├─> loading ──> adapter.parse ──(AdapterError)──> failed + alert
                                     │                     │
                                     │              quality gates ──(any fails)──> quarantined + alert
                                     │                     │
                                     │              loader.load, one transaction ──(error)──> failed + alert
                                     │                     │
                                     └────────────────────────────────> loaded
```

Every file takes this path, deltas included. There is no special path around the gates.

## Commands

The systemd units in `infra/vps` are the production trigger and call these exact commands.

| Command | What it does |
|---|---|
| `smartcart-ingest migrate` | Apply pending migrations from `supabase/migrations`. |
| `smartcart-ingest run --mode full [--chain ID ...]` | Creates price partitions two months ahead, then for each chain today's Stores, PriceFull and PromoFull, then the chain's held deltas. Default chains: the ten D13 chains that have a registered adapter. |
| `smartcart-ingest run --mode delta [--chain ID ...]` | Held deltas first, then today's Price and Promo files. Default chains: the main chains whose interval is due. An explicit `--chain` runs regardless of interval. |
| `smartcart-ingest status` | `file_tracking` counts by chain and status, and quarantined files per chain. |

`run` prints one JSON line per chain (listed, downloaded, skipped, loaded, held, quarantined,
failed, error) and exits 1 when a chain could not run (portal down after the backoff cap, no
adapter) or a file failed to parse or load. A quarantine is not an error exit; it alerts.

## Schedule (issue #49)

Timers (Israel time, from `infra/vps/*.timer`; do not change them here):

- **Full sync** at 06:00 and 08:30. The second pass exists because the laibcatalog listing (Victory,
  Machsanei Hashuk) is empty between midnight and about 08:00 (D13, verified upstream source). It
  is cheap: files already loaded are skipped by hash.
- **Delta poll** every hour at :20. Each tick polls the main chains whose interval is due.

Main chains (D13 chains 1 to 6) and their default delta interval:

| Chain | Chain id | Portal | Delta interval |
|---|---|---|---|
| Shufersal | 7290027600007 | own portal | 60 min |
| Rami Levy | 7290058140886 | Cerberus | 60 min |
| Victory | 7290696200003 | laibcatalog | 60 min (overnight listing gap, see above) |
| Yeinot Bitan and Carrefour | 7290055700007 | own portal (PublishPrice) | 60 min |
| Hazi Hinam | 7290700100008 | own portal | 60 min |
| Tiv Taam | 7290873255550 | Cerberus | 60 min |
| Osher Ad, Yohananof, Machsanei Hashuk, King Store | | | daily full only |

- **Per-chain intervals** are configurable with `DELTA_INTERVAL_MINUTES` (JSON, minutes). The
  timer ticks hourly, so 60 or less means every tick and 120 means every second tick (by hour
  count since the epoch). A value of 0 turns deltas off for that chain; a value for a non-main
  chain turns them on. A 30-minute cadence would need a second `OnCalendar` line in the delta timer.
- **Spreading the Cerberus chains.** Chains are polled one after another, never in parallel, and
  the order interleaves chains that share a portal engine, so Rami Levy and Tiv Taam (both on
  publishedprices.co.il) are never polled back to back.
- **Concurrency.** The two units share one `flock`, so a delta tick never overlaps a full sync. The
  application still refuses to apply a delta before its full file (next section).

## Idempotency and ordering (issue #37)

- **Key.** A file is its content: `file_tracking.sha256` is unique. A hash already `loaded` or
  `quarantined` is skipped and logged (`skipped: hash already processed`), whatever its filename,
  so re-runs, overlapping polls and the 08:30 pass never load anything twice.
- **State machine** (`tracking.py`, every change is a guarded `UPDATE ... WHERE status = ANY(...)`):

  | To | Allowed from |
  |---|---|
  | `downloaded` | `seen`, `failed` (a failed file seen again is retried) |
  | `held` | `downloaded`, `held`, `failed` |
  | `loading` | `downloaded`, `held`, `failed` |
  | `loaded` | `loading` |
  | `quarantined` | `loading` |
  | `failed` | any non-terminal status |

  `loaded` and `quarantined` are terminal. A row left in `loading` by a killed process is set to
  `failed` ("interrupted") at the start of the next run for that chain and then retried.
- **Full before delta.** A Price delta needs that store's PriceFull, and a Promo delta that store's
  PromoFull, published the same calendar day in Israel time and `loaded`. Otherwise the delta is
  `held` with the reason (`waiting for price_full of store 12 for 2026-10-06`) and retried on every
  later run, full or delta, until the full loads. If the day's full is quarantined or never
  published, its deltas stay held, visible in `status`.
- **Order inside a run.** Listing order from a portal is arbitrary, so files are processed as
  Stores, PriceFull, PromoFull, Price, Promo, each group by publication time.
- **Store codes in tracking** come from the adapter's `parse_filename` when it has one (the
  regulation adapters do), else from a generic parser of `PriceFull<chain>-<store>-<yyyymmddhhmm>`,
  with leading zeros stripped either way, so a full and its deltas compare the same way. The
  fetcher may supply the store code and publication time instead.

## Raw archive

Every downloaded file is archived before parsing, under
`raw/<chain_id>/<yyyy>/<mm>/<dd>/<original filename>` (publication day in Israel time). If a chain
republishes different content under the same filename on the same day, it goes to
`raw/<chain_id>/<yyyy>/<mm>/<dd>/dup-<sha256[:12]>/<filename>`. `file_tracking.path` is the key.
`S3_BUCKET` set selects R2/S3 (`S3_*` variables); otherwise `RAW_STORE_PATH` is a local directory.

## Loader (one transaction per file)

In order, inside one transaction: chains, stores (channel from `smartcart_ingest.channel.tag_channel`:
source declaration, the adapter's `online_store_rule`, then the shared heuristic; `geog` from
lat/lon when the column exists, else from `data/geo`, see Store coordinates), items, `ensure_price_partition`
for every month of the price events, price events, promos and promo items, and the `loaded` status
with the record count. Any error rolls all of it back and sets the file `failed` with the reason.

- **Price events.** Change events only, per store: a row is written when price, unit price, unit or
  the estimate flag differs from the latest event for that item and store (a return to an earlier
  price is a change). An observation older than the latest event is skipped. Upsert on
  `prices_event_key`.
- **Chain base prices** (`store_id IS NULL`) are not written in phase 0: the internal model has no
  way for an adapter to say a file is chain-level. Every event is a store event, which
  `current_price()` handles. Deriving base prices (for example the modal price across a chain's
  stores) is a phase 1 compaction job.
- **Unit prices** are normalized to `100g`, `100ml`, `unit` or `kg`: per gram and per 100 g to
  `100g`, per kg to `100g` (divide by 10) unless the item is weighed, per ml, per 100 ml and per
  liter to `100ml`, units to `unit`. Weighed produce is `kg` with `is_estimated = true`; if it has
  no unit price, its shelf price (published per kg) is used. An unknown unit stores the shelf price
  with no unit price.
- **Stores not yet in a Stores file** get a placeholder row (name = store code) so a price file can
  load; the next Stores file fills in name, address and city.
- **Promos** upsert on `promos_source_key`; rows with the same promotion id in one file are merged.
  The promo's item list is replaced by the file's list. Item codes the chain has never published a
  price for are skipped and counted (`promo_items_unknown` in the log).
- A price for an item code that is neither in the file nor in the database fails the file.

## Store coordinates

The real Stores files carry a CBS locality code (`City`) and an address, no coordinates (0 of 827
real physical stores at the phase 0 dry run). The loader fills `stores.geog` after the upsert, per
Stores file, in this order: coordinates the chain published (`geo_precision` `address`, source
`chain`); a row of `data/geo/store_geocodes.csv` for the (chain, store code) (`address`, `street`
or `locality`); the centroid of the store's locality from `data/geo/localities.csv` (`locality`);
otherwise NULL, and the store is listed by the view `stores_missing_geo` with a reason. A worse
source never replaces a better one, online stores are not looked up, and a missing data file is an
empty table, never a load failure. `LoadResult.stores_located` counts what a file placed, by
precision. The two CSVs are built by `scripts/geo/fetch_localities.py` and
`scripts/geo/geocode_stores.py`, run by the manual workflow **Geocode stores** (open internet
needed: data.gov.il and OpenStreetMap Nominatim). Method, Nominatim's usage policy, the OSM
attribution (ODbL) and the follow-up for the API and web (locality-precision stores are
approximate) are in `docs/geocoding.md`.

## Quality gates (issue #42)

Run on the parsed file before the load, with database context. All gates run, so a file can fail
several; each failure is one `quarantine_events` row, and the file becomes `quarantined` with the
reasons in `file_tracking.reason`. No row of a quarantined file reaches the data tables, and the
raw file stays in the archive.

| Gate (`quarantine_events.gate`) | Fails when | Default |
|---|---|---|
| `zero_price` | any price is zero or negative | |
| `price_jump` | a price is more than the factor times the latest known price for the same item and store (the store's own event, else the chain base) | `PRICE_JUMP_FACTOR=3` |
| `item_count_drop` | a full file (PriceFull, PromoFull, Stores) has fewer records than the ratio times the previous loaded file of the same kind, chain and store | `ITEM_COUNT_DROP_RATIO=0.5` |
| `stale_date` | the file was published longer ago than the limit | `STALE_FILE_MAX_AGE_HOURS=36` |

Thresholds can be set per chain with `QUALITY_OVERRIDES`, e.g.
`{"7290027600007": {"price_jump_factor": 4}}`. The stale default of 36 hours tolerates one missed
daily full sync; the regulation requires updates within one hour of a change at the register
(verified, research, `product-and-market.md`), so a tighter limit for deltas is an option once real
publication delays are measured. The thresholds themselves are the issue's defaults, not measured
values (estimate).

The item-count gate needs the previous file's record count. Schema v1 has no column for it, so
`mark_loaded` stores it in `file_tracking.reason` as `items=<n>` on loaded rows. If a migration adds
`file_tracking.item_count integer`, the code writes and reads that column instead, with no other
change.

### Soft warning: gap-report pressure (issue #16)

Users' report-a-gap answers (`POST /feedback/gap`, table `gap_reports`) are a quality signal.
`gap_report_pressure(since, until)` (migration `20261009100000_mvp_followups.sql`) summarises
them per (chain, store); the view `quality_gap_reports_7d` is the last 7 days.

| Column | Meaning |
|---|---|
| `reports` | every report in the window |
| `price_mismatches` | confirmed price mismatches: the report carries the price we showed and the shelf price, and they differ by at least one agora. Counted once per reporter and product (one user reporting the same product twice counts once; each anonymous report counts) |
| `wrong_product`, `promo_wrong` | reports tagged `#reason=wrong_product` / `#reason=promo_wrong` in the note (the web app appends the reason there) |
| `reporters` | distinct signed-in reporters plus one per anonymous report |
| `last_report_at` | newest report |

Before a price file (full or delta) of a store is loaded, `quality.warnings` checks it: when the
store has at least `GAP_REPORT_PRESSURE_MIN` (default 3, per chain in `QUALITY_OVERRIDES` as
`gap_report_pressure_min`; 0 disables) confirmed price mismatches in the last 7 days, a
`gap_report_pressure` warning is written to `quality_warnings` (file, chain, store, detail) and a
`quality_warning` alert fires. **The file is still loaded**: a warning never quarantines, because
the reports may be about the shelf, not the file, and a newer file is the likeliest fix. The same
store is warned at most once per 24 hours. Chain-level files and promo or stores files are not
checked. The threshold of 3 is a placeholder (estimate), not a measured value; revisit it once the
beta has real report volumes.

### Quarantine counts for the dashboard

```sql
SELECT ft.chain_id,
       count(*)                                                          AS quarantined_files,
       count(*) FILTER (WHERE ft.updated_at >= now() - interval '1 day') AS last_24h,
       max(ft.updated_at)                                                AS last_quarantined_at
FROM file_tracking AS ft
WHERE ft.status = 'quarantined'
GROUP BY ft.chain_id
ORDER BY ft.chain_id;
```

Per gate: `SELECT ft.chain_id, qe.gate, count(*) FROM quarantine_events qe JOIN file_tracking ft
ON ft.id = qe.file_id GROUP BY 1, 2`. The same per-chain query is `tracking.QUARANTINE_COUNTS_SQL`
and `smartcart-ingest status` prints it.

## Alerts

`alerts.Alert(chain_id, kind, message, details)` always goes to the structlog logger (level error,
event `alert`). With `ALERT_WEBHOOK_URL` set it is also POSTed as JSON with a `text` field (shown
as-is by Slack or Discord incoming webhooks) plus the structured fields. A failing webhook is
logged and never stops ingestion.

| Kind | Fires when |
|---|---|
| `parse_failure` | the adapter raised `AdapterError` (or crashed) on a file |
| `unknown_schema` | the adapter raised `UnknownSchemaError`; the file is not loaded |
| `quarantine` | a file failed a gate; names chain, store, file and gates |
| `load_failure` | the load raised and was rolled back |
| `portal_failure` | listing or fetching kept failing after the backoff cap |
| `quality_warning` | a soft warning (`gap_report_pressure`); the file was still loaded; once per store per 24 hours |

A file that fails again with the same reason on a later run is not alerted again.

## Portal backoff

Listing and fetching are retried on `PortalError`, `OSError` and timeouts with exponential backoff
and full jitter: before retry *n* the worker waits a random time in
`[0, min(PORTAL_BACKOFF_CAP_SECONDS, PORTAL_BACKOFF_BASE_SECONDS * 2^(n-1))]`. After
`PORTAL_MAX_ATTEMPTS` calls the chain is skipped for this tick and a `portal_failure` alert fires;
the next tick starts again.

## Environment variables

`DATABASE_URL` and `S3_*` are in `.env.example`. The others are new and should be added there.

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | | Postgres connection (ingest role). |
| `RAW_STORE_PATH` | | Local raw archive directory, used when `S3_BUCKET` is empty. |
| `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | | R2/S3 raw archive. |
| `ALERT_WEBHOOK_URL` | | Optional webhook for alerts. |
| `STALE_FILE_MAX_AGE_HOURS` | 36 | Stale-date gate. |
| `PRICE_JUMP_FACTOR` | 3 | Price-jump gate. |
| `ITEM_COUNT_DROP_RATIO` | 0.5 | Item-count gate. |
| `GAP_REPORT_PRESSURE_MIN` | 3 | Confirmed price mismatches per store in 7 days before a `gap_report_pressure` warning; 0 disables. |
| `QUALITY_OVERRIDES` | `{}` | Per-chain thresholds, JSON. |
| `DELTA_INTERVAL_MINUTES` | `{}` | Per-chain delta interval overrides, JSON. |
| `PORTAL_MAX_ATTEMPTS` | 5 | Portal calls before giving up for this tick. |
| `PORTAL_BACKOFF_BASE_SECONDS` | 2 | First backoff ceiling. |
| `PORTAL_BACKOFF_CAP_SECONDS` | 120 | Largest backoff ceiling. |

## The upstream scraper

`download.ScraperFetcher` lists and fetches through `il_supermarket_scarper` (1.0.15). Per the
adapter contract the import itself lives in `adapters/_scraper.py`, and `download.load_upstream()`
installs stderr handlers on the upstream loggers first (upstream otherwise opens `logging.log` in
the working directory, which is read-only on the VPS). The scraper name comes from the adapter's
`upstream_scraper` when it declares one, else from the D13 table in `download.py`. Upstream
couples listing and downloading, so `list_files` runs a scrape for the requested file types and
day into a fresh staging directory (gzip extraction off, so the archive holds the portal's bytes)
and `fetch` reads and deletes the staged file. A scrape that saved nothing but reported download
errors raises `PortalError`. Upstream logs and swallows listing exceptions, so a portal that is
down may look like an empty listing; the run logs `portal listed no files` in that case.

## Portal probe from GitHub runners

`.github/workflows/portal-probe.yml` ("Portal probe", issues #32, #53, #57 and preparation for
#60) runs on `workflow_dispatch` and daily at 07:17 UTC (after the laibcatalog listing fills, D13).
A GitHub-hosted runner is **not** an Israeli IP, so the run doubles as a measurement of which
portals block cloud ranges (laibcatalog is reported to, verified in the research, section 2.3);
the VPS (#22) remains the production path whatever it shows. Steps:

1. `infra/smoke/check_portals.sh` with `MARKDOWN_OUT=$GITHUB_STEP_SUMMARY`: HTTP reachability of
   the portal hosts, the Cerberus FTP-over-TLS login for Rami Levy, Tiv Taam, Osher Ad and
   Yohananof (added for this workflow; it also runs on the VPS), and the laibcatalog download
   probe. Its exit code is printed, not enforced.
2. `scripts/unblock/portal_probe.py probe`: per D13 chain, the portal's HTTP status, the Cerberus
   login, and one Stores and one PriceFull file through `smartcart_ingest.adapters.fetch_fixtures`
   (`--kind stores --kind price_full --timeout`, the pinned upstream scraper, one subprocess per
   download so a hung portal is killed). Files land in `$RUNNER_TEMP/portal-probe/files/<slug>/`,
   outside the checkout. Only transparency portals are contacted, never an online store.
3. `smartcart-ingest migrate` on the throwaway Supabase Postgres, then `portal_probe.py gate`:
   every downloaded file goes through `Scheduler.run_full` with a one-file fetcher and the real
   clock, which is the production path (download tracking, adapter, quality gates, loader; no
   bypass). The outcome is read back from `file_tracking` and `quarantine_events`.

The job summary is one table: chain, portal reachable (HTTP status), login (Cerberus only), the
Stores and PriceFull file (name, size, publication time), what the adapter parsed (stores and
online stores; items and prices), the gate result (`loaded`, `quarantined (<gates>)`, `failed
(<reason>)`) and the schema the adapter detected (v1 or v2; v2 depends on the provisional marker,
#57). Download errors and alerts follow in collapsed sections. The same table is also printed to
the job log, and the gate step logs one untruncated `RESULT {...}` JSON line per file (chain,
kind, file, size, publication time, schema, stores, items, prices, parse error, status, gates,
reason), so the outcome can be read without downloading an artifact. Artifacts:
`portal-probe-files` (the raw files, 7 days) and `portal-probe-report` (table and JSON, 30 days).
Inputs: `chains` (space-separated slugs, default all ten), `timeout` (seconds per download,
default 180) and `commit_fixtures` (below). The job only fails if the script itself breaks;
unreachable portals are a result.

The Cerberus login (Rami Levy, Tiv Taam, Osher Ad, Yohananof) is checked the way the upstream
scraper connects: `ftplib.FTP_TLS(host, user, "")` on `url.retail.publishedprices.co.il` with no
SSL context, which in ftplib means an unverified one (no CA and no host-name check). The portal's
certificate does not match that host name (seen from a runner on 2026-10-08), so a verifying login
fails while the scraper downloads normally; the result then reads `ok (certificate not verified,
as upstream; ...)`. This is the upstream package's behaviour for public price data, recorded here,
not changed.

**Committing real fixtures (`commit_fixtures`, #32).** With the input set, the probe job runs
`portal_probe.py fixtures` after the gates: every file the adapter accepted is written to
`<chain>/real/`, Stores whole and PriceFull trimmed to its first 200 rows by
`fetch_fixtures.trim_price_file` (decoded and parsed with the adapters' own `xmlutil`, no entity
resolution; header, XML declaration, encoding, BOM and outer gzip or zip kept; a numeric `Count`
on the container updated), then re-parsed through the adapter. Each chain gets a `MANIFEST.json`:
source file name, sha256 and size of the original and of the committed file, publication and
fetch times, rows before and after trimming, what the adapter parsed, the schema and the gate
result seen on the runner. A separate job, the only one with `contents: write`, copies the
artifact into `services/ingest/tests/fixtures/<chain>/real/` (`scripts/unblock/copy_fixtures.sh`
accepts only `<known chain>/real/<plain file name>`), commits as `github-actions[bot]` and pushes
the branch `probe/fixtures-<YYYYMMDD>` (with the run id appended if that branch exists). No pull
request is opened, and a push with the workflow token does not start other workflows, so CI runs
when the pull request is opened. `tests/test_adapters.py` then picks the files up: each must parse
through its adapter with a schema, a publication time and (PriceFull) a store code, items, prices
with a store code and every price above zero; and per chain the files go through the Scheduler
path with the clock one hour after the newest file and must load, or be quarantined only by the quality
gates above that their `MANIFEST.json` recorded. The synthetic fixtures are unchanged
and stay the regression set for the edge cases. In one fresh
database a PriceFull has no earlier file, so the item-count and price-jump gates cannot trip;
stale date and zero price can.

Run it locally without portal access on a migrated database:
`uv run --no-sync python scripts/unblock/portal_probe.py gate --files services/ingest/tests/fixtures`
(the synthetic fixtures are past the 36-hour stale limit, so they show `quarantined
(stale_date)`; add `--now 2026-10-06T12:00` to see them load).

## Not done yet, and what to verify on the VPS

- `ScraperFetcher` against the real portals (unreachable from development machines). Check that each
  of the ten chains lists and downloads today's files, and that published times and store codes
  parse from the real filenames.
- Chain base prices and per-store exceptions (needs a model change, see Loader).
- Ending promos that disappear from the day's PromoFull (they keep their `ends_at`).
- Held deltas never expire; a day whose full file never loads keeps its deltas held.
- `tests/test_quality_adapters.py` runs every registered chain adapter's fixtures through the
  whole pipeline (gates included) and checks the gates catch a zero price, a price jump and a stale
  date on that chain's PriceFull. The fixtures are synthetic until the VPS fetches real ones.
