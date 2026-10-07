# supabase

SQL for the SmartCart database: Supabase-hosted Postgres with PostGIS and pgvector (decision D3).
Plain SQL, no ORM.

## Migrations

Files in `migrations/` are named `YYYYMMDDHHMMSS_name.sql`, the Supabase CLI convention, and are
applied in filename order, each exactly once, by `smartcart_ingest.db.migrate`:

```bash
export DATABASE_URL=postgresql://...      # never commit a real one
uv run python -c "from smartcart_ingest import db; print(db.migrate(db.connect(autocommit=True)))"
```

`migrate` runs each file in its own transaction together with a row in
`schema_migrations(filename, applied_at)`, under an advisory lock, so a second run (or a
concurrent one) is a no-op. Never edit a migration that has been applied anywhere; add a new one.

A migration that needs an extension says so in its leading comments:

```sql
-- requires: postgis
```

Every real environment applies every file, and a missing extension fails loudly. Only the local
test harness skips such files, when the server has no PostGIS or pgvector (see
`docs/dev-setup.md`).

Use either this runner or `supabase db push` on a given database, not both: the CLI records
applied versions in `supabase_migrations.schema_migrations`, this runner in
`public.schema_migrations`.

| File | What it does |
|---|---|
| `20261006120000_extensions.sql` | `postgis`, `vector`, `pg_trgm` |
| `20261006120100_schema_v1.sql` | chains, stores, items, prices (partitioned), promos, promo_items, file_tracking, quarantine_events, and the price functions |
| `20261006120200_stores_geog.sql` | `stores.geog geography(Point,4326)`, its GiST index, `stores_within()` |

`stores.geog` lives in its own migration only so developers without PostGIS can run the
plain-SQL tests. The resulting schema is the same in CI, on Supabase and in docker compose.

## Schema v1 (issue #27)

| Table | Key | Notes |
|---|---|---|
| `chains` | `id text` | name, portal, `club_names text[]` |
| `stores` | `id bigserial`, unique `(chain_id, store_code)` | name, address, city, `channel` physical/online (default physical), `geog` |
| `items` | `id bigserial`, unique `(chain_id, item_code)` | chain-scoped; barcode (may be chain-internal, so not unique), raw name, manufacturer, quantity, unit, `is_weighed`, `raw_attributes jsonb` |
| `prices` | unique `(item_id, store_id, valid_from)` NULLS NOT DISTINCT | change events, partitioned by month on `valid_from` |
| `promos` | `id bigserial`, unique `(chain_id, store_id, promo_id)` NULLS NOT DISTINCT | structured: dates, hours, club, min/max qty, reward type and value, plus `raw jsonb` |
| `promo_items` | `(promo_id, item_id)` | which items a promo covers |
| `file_tracking` | `id bigserial`, unique `sha256` | chain, store, kind, published_at, schema_version, status, reason |
| `quarantine_events` | `id bigserial` | one row per failed quality gate, references `file_tracking` |

Columns use the vocabulary of `services/ingest/smartcart_ingest/models.py` (file kinds, schema
versions, channels, portals, reward types), enforced with CHECK constraints.

`file_tracking.chain_id` deliberately has no foreign key: the audit trail must record a file
from a chain that is not yet in `chains` instead of failing to record it. `prices.file_id` and
`promos.file_id` point back at the file that produced a row.

### Prices: base price per chain plus per-store exceptions

- A row with `store_id IS NULL` is the chain base price; a row with a `store_id` is that store's
  exception. Only changes are stored.
- `current_price(item_id, store_id [, at])` returns the latest store-specific event if the store
  has one, otherwise the latest base price, with `is_store_price` saying which. An exception
  stays in force until a newer event for that store supersedes it, so **the loader writes a store
  event whenever a store's price changes, including when it returns to the base price.**
- `latest_prices` is a view of the latest event per (item, store-or-base) as of now.
- Unit prices are per 100 g, 100 ml or unit (`uom` = `100g`, `100ml`, `unit`); weighed produce is
  per kg (`kg`) with `is_estimated = true`.

### Monthly partitions

`prices` has no default partition, on purpose: a row for a month without a partition fails with
"no partition of relation prices found for row" instead of landing somewhere it is hard to move
from. Partitions are `prices_YYYY_MM`, with UTC month boundaries.

- `ensure_price_partition(month date)` creates the partition containing that date if missing and
  returns its name. It is idempotent and safe to call concurrently. **The loader calls it for the
  month of every `valid_from` it is about to insert** (once per distinct month per file).
- `ensure_price_partitions(from date, to date)` does a range. The schema migration creates last
  month through two months ahead. A nightly job (the ingestion scheduler, or `pg_cron` on
  Supabase) should run `SELECT ensure_price_partitions(now()::date, (now() + interval '2 months')::date)`
  so partitions always exist ahead of time.

### Indexes and the queries they serve (docs/architecture.md section 4)

| Index | Query |
|---|---|
| `stores_geog_gist` | stores within a radius (`ST_DWithin`, `stores_within()`) |
| `prices_event_key` (item, store, valid_from) | latest price for an item at a store, and the base price (`store_id IS NULL`) |
| `prices_store_item_idx` (store, item, valid_from desc) | every price in a set of stores, for basket totals |
| `items_barcode_idx` | the same barcode across chains |
| `promos_store_active_idx`, `promos_chain_active_idx` | active promos for a store, and chain-wide ones |
| `promo_items_item_idx` | promos that cover an item |
| `file_tracking_latest_idx`, `file_tracking_open_idx` | latest file per (chain, store, kind); files still in flight |

Out of scope for v1 (phase 1): `canonical_products`, `item_canonical`, `effective_prices`,
`gold_pairs`, user tables and RLS policies.
