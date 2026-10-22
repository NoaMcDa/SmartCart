# Exit window on GitHub runners (#60 rehearsal)

> **This is a runner rehearsal, not the VPS window.** The Phase 0 exit needs fourteen consecutive
> nightly loads on the Israeli-IP VPS, which does not exist yet (`infra-provisioning.md`). Nothing
> this workflow produces may be pasted into `phase-0-exit-report.md` as evidence, and that report
> stays **NO-GO**. What the rehearsal does give, starting now, is real reliability data: which chains
> a runner reaches, which files pass the adapters and the quality gates with the **real clock**, when
> each chain publishes, and how long a night takes.

Labels follow `docs/README.md`: **measured** is read from a run's own database or logs, **derived**
is reasoning from a measured value, **estimate** is a judgement.

## What runs each day

`.github/workflows/exit-window.yml` ("Exit window"): daily at 06:47 UTC (08:47 Israel winter time,
09:47 summer; the laibcatalog listing is empty until about 08:00, D13), and on `workflow_dispatch`
(inputs `chains`, `timeout`, `replace`). The default branch holds only docs and workflow copies, so a
scheduled run checks out `main`, the same pattern and comment as `portal-probe.yml`; a manual run
uses the chosen ref.

Job `rehearsal` (read-only token):

1. A throwaway Postgres 17 service (`supabase/postgres:17.11.0.004`, as in `ci.yml`), `uv sync --locked`,
   the runner's public IP country (ipinfo.io) into the record.
2. `scripts/exit_window/run_day.py`:
   - **Download.** `portal_probe.probe`, unchanged: per D13 chain the portal's HTTP status, the Cerberus
     login where there is one, and one Stores, one PriceFull and one PromoFull file through the pinned
     upstream scraper (one subprocess per download so a hung portal is killed). Only the legally mandated
     transparency portals are contacted, never a chain's online store. The files land in `$RUNNER_TEMP`,
     outside the checkout, and only the chain adapters read them.
   - **Load.** `smartcart-ingest migrate`, then every downloaded file through the real `Scheduler.run_full`
     (download tracking, adapter, quality gates, loader) with `datetime.now` as the clock. There is **no
     clock replay**, unlike `scripts/exit_dry_run` and `real_day.py`: a file the chain published more than
     36 hours ago (Stores: its own limit) is quarantined by the stale-date gate, as on the VPS. Order:
     Stores first, then PriceFull, then PromoFull, per chain.
   - **Read back.** Each file's outcome from `file_tracking` and `quarantine_events`, what the adapter
     read (stores, items, prices, promos), the physical stores and how many have coordinates, and the
     promos by reward type, all written to one JSON record.
3. The record goes to the job summary and to the artifact `exit-window-record` (30 days); the downloaded
   files are kept 7 days as `exit-window-files`.

Job `persist` (the only one with `contents: write`) takes the record and appends it to the branch
`exit-window/data`, then writes the report of the window so far to the job summary and the artifact
`exit-window-report` (90 days). It runs even when the rehearsal job failed late, as long as a record exists.

The workflow is a measurement. An unreachable portal, a quarantined file or a failed load is a result and
does not fail the job; the job fails only when the script itself breaks. A night on which no record is
written counts in the report as a failure of every chain ("no record").

## The record (`scripts/exit_window/window_record.py`)

One JSON file per Israel date, `records/<YYYY-MM-DD>.json`, schema version 1, validated on write and on
read (a malformed or hand-edited file is listed as unusable by the report and cannot hide the rest).

| Block | Content |
|---|---|
| `date`, `label` | The Israel date of the run, and "runner rehearsal, not the VPS window" |
| `run` | source (`portal`, `fixtures`, `files`), clock (`real`, or `fixed` for tests), event, ref, commit, run id and URL, start and finish times (UTC and Israel), duration, download seconds, load seconds, **runner IP country** |
| `chains.<slug>.portal` | HTTP status, reachability class (`OK`, `BLOCKED?`, `UNREACHABLE`, ...), Cerberus login result |
| `chains.<slug>.files.<kind>` | For Stores, PriceFull and PromoFull: `listed`, `downloaded`, `loaded`, `quarantined`, `failed`, `status` (the `file_tracking` status, or `not_downloaded`), the **gate reasons** (`gates`, `reason`), schema, file name and size, **publication time (Israel)**, age at load, rows the adapter read (`stores`, `items`, `prices`, `promos`), download and load seconds, the **download failure** text |
| `chains.<slug>` | counters over the three kinds (`listed`, `downloaded`, `loaded`, `quarantined`, `failed`), `full_loaded` (a PriceFull or PromoFull reached `loaded`: the criterion's success), `failure` (why not, in words), physical stores and with coordinates, promos by reward type |
| `alerts` | The alerts the Scheduler raised (chain, kind, message) |

`listed` is exact only when a file came back: the pinned upstream scraper does not separate "nothing was
listed" from "listed but not downloadable" (`no file downloaded` covers both, recorded as `false`), and a
timeout or exception says nothing about the listing (recorded as `null`, unknown).

## The data branch and idempotency (`window_store.py`)

`exit-window/data` is an orphan branch (no shared history with the code) holding a README and
`records/<date>.json`. It is created by the first run, as `probe/fixtures-<date>` is by the probe's
commit job, with the workflow token (no pull request, and a push with that token starts no workflow).

- **One file per day, never rewritten.** A second record for a date that already has one (a manual dispatch
  after the scheduled run, a re-run) is reported as `exists` and nothing is written or committed. The first
  record of a day stands. `replace` (a dispatch input) is the one explicit overwrite; it is still a new
  commit, so history keeps the old file.
- **Atomic write**: a temporary file in the same folder and a rename, so an interrupted write never leaves
  a half record that a later run would call `exists`.
- **No force push.** The commit is pushed with a plain push; a rejected push (another run committed first)
  fetches, rebases (different dates touch different files) and retries up to four times.
- A record is validated before it is written; an invalid one writes nothing and fails the job loudly.

## The report (`scripts/exit_window/report.py`)

```bash
git worktree add /tmp/exit-window-data origin/exit-window/data    # or any checkout of the branch
uv run python scripts/exit_window/report.py --data /tmp/exit-window-data --out exit-window-report.md
```

It reuses the exit report code of `smartcart_ingest.report` (the D13 chain list, `ChainLoads`,
`DaySummary`, `FailedFile`, `longest_streak`, the 95 percent and 14 day constants, the table helpers) but
takes the **records as input instead of a database**: the nightly database is a throwaway, so what it held
is in the record. Replaying counts into a database would have been a second schema for the same numbers.

How criterion 1 is evaluated, and where it differs from the VPS report:

- A (chain, day) succeeds when that day's rehearsal loaded a `price_full` or `promo_full` file of the
  chain. The VPS report attributes a file to the Israel date of its `published_at`; here the day is the date
  of the run, so a file published late the evening before and loaded this morning counts for this morning.
- **Every D13 chain counts.** A chain a runner cannot reach, or one a record does not contain, is a
  failure with its reason, never dropped from the denominator. A day between the first and last record
  with no record fails every chain.
- **Met** means some 14 consecutive days (all with a record) with a success rate above 95 percent,
  which is the existing `meets_success_rate` rule applied to the best 14-day window; the longest streak of
  days above 95 percent (with ten chains, every chain) is reported next to it. Fewer than 14 days reads
  "not met: N of 14 days so far".
- Because Victory, Machsanei Hashuk and Hazi Hinam were unreachable from runners in every probe so far, the
  criterion cannot be met on a runner. The report therefore also gives, as **information only**, the rate
  over the chains that produced a full file at least once; it is not the criterion.
- Criteria 2 to 4 are not claimed: the report shows the store and promo counts the records carry (from the
  Stores and PromoFull files of the day) and says they are not evaluable here (the hand check of a promo
  sample, every store of a chain, the basket SQL on a loaded database).

Sections: the criteria table; 1. nightly loads (rate, streak, chain by day matrix, per-chain reach,
downloads, loads, quarantines, publication hours in Israel time and median age at load, the causes of
every full file that did not load with numbers masked so equal causes group, and the failed-file table
by day); 2. the latest record (portal, the three files' outcomes, rows, publication times, chains with no
file and why, alerts); 3. promo counts by reward type (with the `other` share, a parsing gap) and store
coordinates; records that could not be used.

## Run the whole logic locally, offline

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ew   # an empty database
uv run python scripts/exit_window/run_day.py --work /tmp/ew --out /tmp/ew/record.json --from-fixtures
uv run python scripts/exit_window/window_store.py append --data /tmp/ew-data --record /tmp/ew/record.json
uv run python scripts/exit_window/report.py --data /tmp/ew-data
```

`--from-fixtures` takes the committed real files (`tests/fixtures/<chain>/real`, seven chains). They are
days old, so with the real clock the stale-date gate quarantines most of them, which is the point; add
`--now 2026-10-22T01:40+03:00` to see them load. `--files DIR` takes any `<slug>/<portal file>` directory.
Use an empty database each time: a file whose hash is already loaded is skipped, as in production.

Tests (`uv run pytest scripts/exit_window/tests -q`): the record schema, the idempotent append and the
generator on fixture records run offline; the end-to-end test (fixtures through the real Scheduler,
fixed and real clock, record, store and report) needs a Postgres with PostGIS, pgvector and pg_trgm.
The workflow's shell steps for the data branch were also run against a local bare repository (first run
creates the orphan branch, a repeat prints `exists` and commits nothing, a new date adds one commit).

## Limits, so the numbers are read correctly

- **Runner IP, not Israeli.** Three D13 chains (Victory and Machsanei Hashuk on laibcatalog, Hazi
  Hinam) were not reachable from a runner in the probe runs of 2026-10-08 and 2026-10-21; others (Mega, King Store)
  answer the home page with 403 but the scraper still gets the files. Reachability can change; each record
  holds the answer of that day.
- **One store per chain.** A real PriceFull is one store's prices. The rehearsal loads one file per kind
  per chain (the probe's choice: the largest of ten PromoFull files, and that store's PriceFull), not a
  night's thousand files. It says nothing about the size of a real night or about its time budgets.
- **A fresh database every night.** `price_jump` and `item_count_drop` have no previous load to compare
  with, so they cannot fire; only `zero_price` and `stale_date` (and the loader's own errors) are exercised.
  The VPS window, with a persistent database, is the first test of the other two.
- **The portal HTTP status is the home page, not the download.** The record keeps the probe's reachability class
  (`OK`, `BLOCKED?`, `UNREACHABLE`), but on 2026-10-22 four Cerberus chains read `UNREACHABLE (0)` and still
  delivered all three files, and King Store read 403 and delivered too. Whether a chain's files arrived is the
  measure; the class is context for the chains that delivered nothing.
- **Stores files are published rarely** on the Cerberus portals (57 to 65 hours old on 2026-10-22). They
  loaded: the stale limit for a Stores file is its own, much longer one (`stale_stores_max_age_hours`), not the
  36 hours of the full files.
- **GitHub's schedule is best effort**: a run can start late or be skipped under load, and scheduled
  workflows are paused after 60 days without repository activity. A skipped night is a day with no
  record, counted as a failure.
- The schedule and `workflow_dispatch` appear only for workflows on the default branch (see `unblock.md`,
  "Things the lead should know when triggering"); merge before expecting nightly runs.

## Day one: run 39795071797, 2026-10-22 (measured)

A verification run on a runner from the branch `phase/exit-window` (event `push`, commit `9262c029171c`;
the push trigger was temporary), started 17:22 Israel time, so the chains' files of the day were all out
and some of the intraday promo files too. [Run](https://github.com/NoaMcDa/SmartCart/actions/runs/39795071797);
its record is `records/2026-10-22.json` on `exit-window/data`. Runner IP country: US.

- **6 of 10 chains loaded a full file**: Shufersal, Rami Levy, Tiv Taam, Osher Ad, Yohananof, King Store
  (all three files each, all `loaded`, no quarantine, no failure, no Scheduler alert).
- **Not reached**: Victory and Machsanei Hashuk (laibcatalog: unreachable, `no file downloaded` for all
  three kinds), Hazi Hinam (HTTP 403, `no file downloaded`), and **Yeinot Bitan and Carrefour (Mega), which
  timed out after 240 s on each of the three downloads**. Mega delivered all three files in the probe
  runs of 2026-10-21 (docs/ingestion.md). One run does not say whether this is a bad hour or a block that
  has started; the next records will.
- **Criterion 1 on this record**: 60.0 percent for the day, "not met: 1 of 14 days so far". Over the six
  chains that delivered, 100 percent (information only).
- **Time**: 1916 s in all, 1891 s downloading (the three unreachable laibcatalog and Hazi Hinam chains and
  Mega's timeouts account for most of it: 61 to 127 s per kind for the first three, 3 x 240 s for Mega) and
  24 s loading 6 chains x 3 files through the Scheduler.
- **Rows the adapters read** (PriceFull items / PromoFull promotions): Shufersal 7494 / 1383, Rami Levy
  14853 / 2663, Tiv Taam 23274 / 2349, Osher Ad 6741 / 809, Yohananof 11656 / 1241, King Store 5991 / 507.
  Promos of reward type `other` (a parsing gap): Shufersal 9.1 percent, Rami Levy 18.3, Yohananof 5.0, the
  other three below 1 percent.
- **Publication (Israel time)**: Rami Levy's PriceFull 00:10 and its PromoFull 12:01, Osher Ad's PriceFull 08:00
  and PromoFull 14:05: a chain publishes promo files during the day, so a morning run takes the previous
  day's one (up to about 30 hours old, inside the 36-hour limit). Tiv Taam and Yohananof 00:40, Shufersal 03:00,
  King Store 05:10.
- **Coordinates** (criterion 2 input, not the criterion): 625 of 683 physical stores in the six Stores files
  have coordinates.

The persist job ran on the runner too: it created the orphan branch `exit-window/data` with the README
and the record and wrote the report to the job summary. Re-running the same day is covered below.
