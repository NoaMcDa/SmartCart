# supabase/queries

Reusable read queries, kept apart from the migrations because they change nothing. Each file is
one parameterized statement using psycopg named placeholders (`%(name)s`).

| File | What it answers |
|---|---|
| `basket_radius.sql` | What does this basket of barcodes cost at every store within a radius of a point, and what is missing at each store? (Phase 0 exit criterion, issue #60.) |
| `catalog_backlog.sql` | What should the catalog learn next? Missed queries (clustered) and uncovered products in the price files, ranked. Run by `smartcart-catalog backlog`; documented in `docs/catalog.md` section 9 (issue #52). |

## basket_radius.sql

Prices a list of barcodes at every store within a radius, with PostGIS, and reports the gaps.
It is the Layer 4 step of `docs/architecture.md` section 4 in its simplest form: every item has
quantity 1, the item is picked by exact barcode, and no promos are applied. It is proven by
`services/ingest/tests/test_basket_query.py`, which CI runs against PostGIS on synthetic data.

### Parameters

| Name | Type | Meaning |
|---|---|---|
| `barcodes` | `text[]` | The basket. Duplicates are collapsed and NULL entries ignored. |
| `lon`, `lat` | `float8` | Search point, WGS 84 degrees (longitude first, as in `stores_within`). |
| `radius_m` | `float8` | Radius in meters. |
| `include_online` | `boolean` | Count stores with `channel = 'online'` too. NULL is treated as false, which is the default for callers that can omit it. |

### Result

One row per store in the radius. Complete baskets come first, then fewer missing items, then
lower total, then distance.

| Column | Meaning |
|---|---|
| `store_id`, `chain_id`, `store_name`, `city`, `channel` | the store |
| `distance_m` | straight-line distance from the point, rounded to meters |
| `basket_total` | sum of the current price of the barcodes that were found; **partial when something is missing**, 0 when nothing was found |
| `found_count` | barcodes with a current price at this store |
| `missing_barcodes` | `text[]` of the requested barcodes with no current price at this store, empty when none |
| `is_complete` | true when `missing_barcodes` is empty |

A store with missing items is never dropped and its gap is never hidden. Compare `basket_total`
only between rows where `is_complete` is true; a partial total is not a cheaper basket, it is a
smaller one (`docs/architecture.md` section 4: "a store cannot look cheap by not stocking half the
list"). A product surface must show the missing list next to the total.

### Assumptions

- **Store selection.** `stores_within(lon, lat, radius_m)` (uses the `stores_geog_gist` index).
  Stores whose `geog` is NULL are not found, which is why the exit report lists them separately.
  Online-channel stores are excluded unless `include_online` is true.
- **A barcode is found at a store** when an item of that store's chain has that barcode and
  `current_price(item, store)` returns a row. Barcodes are matched on `items.barcode`; items are
  chain-scoped, so a chain never supplies prices to another chain's stores. An item that exists
  but has no price event for that store counts as missing.
- **Which price.** `current_price` returns the latest store-specific event if the store has one,
  otherwise the latest chain base price, and ignores events with `valid_from` in the future. The
  query uses `now()`; there is no as-of parameter yet.
- **Several items, one barcode, one chain.** Barcodes can be chain-internal codes, so a chain
  can hold two items with the same barcode. The lowest current price at that store is used and
  the barcode counts once.
- **Promos, quantities and units are out of scope.** The total is shelf price times one. Matching
  by canonical product and effective prices belong to phase 1.
- An empty `barcodes` array returns no rows.

### Running it from Python

```python
from smartcart_ingest import db, report

with db.connect() as conn:                      # $DATABASE_URL
    rows = report.run_basket_query(
        conn,
        ["7290000000011", "7290000000012", "7290000000013"],
        lon=34.7918, lat=32.0744, radius_m=3000,
        include_online=False,
    )
```

The same call is available from the exit report as `--basket-barcodes ... --lon ... --lat ...
--radius-m ...` (see `docs/phase-0-exit-report.md`).

### Running it with psql

psql does not understand `%(name)s`, so rewrite the placeholders into psql variables on the fly.
All five variables are required in psql (there is no default for `include_online`; say `false`):

```bash
sed -E "s/%\(([a-z_]+)\)s/:'\1'/g" supabase/queries/basket_radius.sql \
  | psql "$DATABASE_URL" -X \
      -v "barcodes={7290000000011,7290000000012,7290000000013}" \
      -v lon=34.7918 -v lat=32.0744 -v radius_m=3000 -v include_online=false \
      -f -
```

The query file contains no other `%` character, so the rewrite is safe. The array is passed in
Postgres array-literal form.

### Sample output

Synthetic data from the CI test, run through psql with the command above. Chain A prices milk
(7290000000011) at 9.00 and bread (7290000000012) at 5.00, with a store price of 4.50 for bread at
its Azrieli store. Chain B prices milk at 7.50 and does not price bread. Nobody sells salt
(7290000000013). A third Chain A store in Jerusalem is outside the radius and an online store at the
same point is excluded:

```
 store_id | chain_id |    store_name     | city | channel  | distance_m | basket_total | found_count |       missing_barcodes        | is_complete
----------+----------+-------------------+------+----------+------------+--------------+-------------+-------------------------------+-------------
        1 | chain-a  | Chain A Azrieli   | Test | physical |          0 |        13.50 |           2 | {7290000000013}               | f
        2 | chain-b  | Chain B Dizengoff | Test | physical |        944 |         7.50 |           1 | {7290000000012,7290000000013} | f
(2 rows)
```

Chain B's 7.50 is the smaller total only because it is missing two of three items; its
`is_complete` is false and so is Chain A's, because nobody sells salt. Asking for the first two
barcodes only makes Chain A the single complete row, ahead of Chain B.

## catalog_backlog.sql

Parameters: `days` (30), `min_similarity` (0.5), `min_misses` (1), `item_days` (60), `top` (20). With
psql, give all five (same rewrite as above; the file has no other `%` character):

```bash
sed -E "s/%\(([a-z_]+)\)s/:'\1'/g" supabase/queries/catalog_backlog.sql \
  | psql "$DATABASE_URL" -X -v days=30 -v min_similarity=0.5 -v min_misses=1 \
      -v item_days=60 -v top=20 -f -
```

The result has `kind` (`missed_query` or `unmapped_item`), `position` within its kind, `label`,
`demand` (misses, or stores carrying the product), `secondary` (spellings, or chains),
`examples` and `last_seen`. The two kinds are ranked separately because their units differ.
