# Ingestion dashboard

An internal, read-only Streamlit page that shows whether ingestion is healthy: which chains are
covered, how fresh they are, and which files failed. It is for the team only (issue #46). It is
not a public status page and it cannot edit or release quarantined files.

Code: `services/dashboard/` (workspace member `smartcart-dashboard`). The queries are in
`smartcart_dashboard/queries.py` and need no Streamlit; `app.py` only renders them.

## Run it

From the repository root:

```bash
export DATABASE_URL_READONLY=postgresql://smartcart_readonly:...@host:5432/postgres?sslmode=require
uv run streamlit run services/dashboard/smartcart_dashboard/app.py
```

`uv run` installs the workspace first, so there is no other setup. The page opens on
`http://localhost:8501`. To keep it team-only on a server, add `--server.address localhost` and reach it through an SSH
tunnel (`ssh -L 8501:localhost:8501 <vps>`); do not expose the port publicly.

## Connection and the read-only role

| Variable | Meaning |
|---|---|
| `DATABASE_URL_READONLY` | Connection string for the `smartcart_readonly` role. Used first. |
| `DATABASE_URL` | Fallback when the variable above is empty. The page then shows a warning, because that URL normally belongs to the ingest role, which can write. |

The dashboard never writes. Two layers back this up: it opens the connection read-only (the
server rejects any write on it), and a test runs every query inside a `READ ONLY` transaction.
Neither replaces the role: the credentials themselves should not be able to write.

The reported-gaps panel also needs `EXECUTE` on `gap_report_pressure(timestamptz, timestamptz)`
and `SELECT` on `gap_reports` and `quality_warnings`; the migration grants them to
`smartcart_readonly` when the role exists, so create the role before running it, or grant them by
hand afterwards.

Create the role as in `docs/infra-provisioning.md` section 3.1 (`create role smartcart_readonly
login noinherit`, `grant usage on schema public`, default privileges `grant select on tables`).
Tables created before the default privileges existed, and monthly `prices` partitions created
later, may need an explicit `grant select`; that file has the details. Names for the variables are
in `.env.example`.

## Panels

Times are UTC. A "load" is a `file_tracking` row with status `loaded` and kind `price_full`,
`price`, `promo_full` or `promo`. Its time is the row's `updated_at`, when it reached `loaded`.
Stores files do not count, so a chain whose stores file loads while its price files fail still
shows as stale. Counts are cached for 60 seconds; the Refresh button clears the cache.

**Banners (top).** Red when a phase 0 chain has no data at all, and red when a chain has no
load in 24 hours. Green when neither applies.

**Chains.** One row per chain id seen in `chains` or `file_tracking`, plus one row for every
phase 0 chain (D13, `docs/decisions.md`) that appears in neither. Flagged rows are red and sort
first.

| Column | Meaning |
|---|---|
| flag | `ok`; `STALE` when the last load is more than 24 hours old or there is none; `MISSING` for a phase 0 chain with no data at all. A chain with two ids (Victory, Machsanei Hashuk) is missing only if neither id is present. |
| name, chain_id | From `chains`, or the D13 name when the chain is not in `chains` yet. |
| phase 0 | `main` for the six chains with hourly deltas, `yes` for the other four, blank for chains outside D13. |
| stores loaded / known | Known: physical stores in `stores`. Loaded: of those, stores with a loaded `price_full` or `price` file in `file_tracking` (matched on chain and store code). |
| items | Rows in `items` for the chain. |
| prices_today | Price change events in `prices` whose `valid_from` is today. Prices are change events, so this is how many prices changed or started today, not the size of the price list. |
| promos_today | Promos in effect at some point today (started before the end of today and not ended before the start of today; a missing date counts as open). |
| last_full_load_at, last_delta_load_at | Latest loaded full file (`price_full` or `promo_full`) and latest loaded delta (`price` or `promo`). |
| hours_since_load | Hours since the later of the two. |

**Failed and quarantined files.** Files with status `failed` or `quarantined`, newest first
(200 at most). `gates` are the failing quality gates joined from `quarantine_events`, with the
detail text in `gate details`; `reason` is the free text on the file row. The `sha256` is shown
as text (there is no file browser yet). `raw key` is the raw file's location in object storage and
appears only once the loader records it in `file_tracking.path`.

**Files per chain and status** and **Quarantined files per chain and gate.** Counts from
`file_tracking` and `quarantine_events`. A file that fails two gates counts once under each.

**Reported gaps (last 7 days)** (issue #16). Report-a-gap answers per store, from
`gap_report_pressure()` (migration `20261009100000_mvp_followups.sql`; see
`docs/ingestion.md`, "Soft warning: gap-report pressure"). Stores with the most confirmed price
mismatches first.

| Column | Meaning |
|---|---|
| chain, store_code, store_name | The reported store (chain name from `chains`). |
| price_mismatches | Reports with both the shown and the shelf price, differing by at least one agora; once per reporter and product. |
| reports | Every report in the 7 days. |
| wrong_product, promo_wrong | Reports tagged with that reason in their note. |
| reporters | Distinct signed-in reporters plus one per anonymous report. |
| last_report_at | Newest report. |
| warned | When ingestion last recorded a `gap_report_pressure` warning for the store (`quality_warnings`); blank when it never did. The store's files are loaded either way. |

"Newest reports" (collapsed) lists the last 100 reports with store, product, shown and shelf
price and the note. No user id or location is shown.

**Look up a file by sha256.** Paste a full hash or a prefix of at least four hex characters to see
the file in any status, with its gates. The lookup is also a link: add `?sha256=<hash>` to the
dashboard URL.

## Tests

```bash
uv run pytest services/dashboard
```

Database tests (marked `db`) use the ingest suite's fixtures, so they need `DATABASE_URL` or local
Postgres binaries, as in `docs/dev-setup.md`.
