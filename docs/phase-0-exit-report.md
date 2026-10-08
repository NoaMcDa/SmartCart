# Phase 0 exit report

Status: **template, not yet fillable in full.** This is the report for issue #60. It ends with a go
or no-go for starting phase 1 (`docs/roadmap.md`, Phase 0 exit criteria). Only criterion 4 can be
shown today; the others need the nightly pipeline to run on the VPS for two consecutive weeks.

Evidence labels follow the rest of the repo: **verified** means measured from the database or a
test that ran; **estimate** means anything else. Everything in a table below must be one or the
other, and the evidence sections are pasted from the generator, never typed by hand.

Chains measured: the ten of `docs/decisions.md` D13 (eight if the tie-break rule drops King Store
and Machsanei Hashuk, in which case say so here and run with `--only-chains`).

## Rehearsal on today's files (not evidence)

[phase-0-exit-dry-run.md](phase-0-exit-dry-run.md) is a rehearsal of this report: the real files of
seven chains (one day, 2026-10-08) and the synthetic set, loaded through the production path into
throwaway databases, with the generator's output for each. It shows which criteria can pass today,
which cannot yet (14 days, store coordinates, a checked promo sample) and the exact commands to run
on the VPS. **It is not the exit validation**: nothing in it may be pasted into the sections below,
and the decision stays NO-GO. Regenerate it with `scripts/exit_dry_run/run.sh`.

## How to regenerate

Set the window and the database once. The window is the two weeks (14 days or more, inclusive)
that the report claims.

```bash
export DATABASE_URL=postgresql://...      # the production or staging database, read-only role is enough
export START=2026-10-20 END=2026-11-02    # example dates; use the real window

# Sections 1 to 3 (and 4, if the basket flags are given): writes Markdown to the file.
uv run python -m smartcart_ingest.report --start "$START" --end "$END" \
  --basket-barcodes 7290000000011,7290000000012,7290000000013 \
  --lon 34.7918 --lat 32.0744 --radius-m 3000 \
  --out /tmp/phase-0-evidence.md
```

Real barcodes and the point must be chosen for the real catalog (see criterion 4). Paste the
generated sections into the matching places below, then fill the prose that no query can write
(the plan for each exception, the verdict on each checked promo, the recommendation).

The same generator is used from Python as `smartcart_ingest.report.build_exit_report(conn, start,
end)` returning an `ExitReport`, and rendered with `render_markdown`.

## 1. Two consecutive weeks of nightly loads above 95 percent

Criterion: more than 95 percent success across the chosen chains over two consecutive weeks of
nightly loads.

Definition used by the generator: a (chain, day) succeeds when at least one `price_full` or
`promo_full` file of that chain reached status `loaded` on that day (Israel-time date of
`published_at`, `created_at` when absent). Success rate is successes over chains times days. A
day counts toward the streak when the share of chains that succeeded is strictly above 95 percent,
which with ten chains means every chain. The definition is lenient (a loaded promo file hides a
failed price file), so the generator also lists every full file that did not load.

Regenerate: `uv run python -m smartcart_ingest.report --start "$START" --end "$END" --out ...`
and paste section "1. Nightly loads". The dashboard's file-tracking view is the cross-check.

Status: **blocked on the two-week window.** No nightly loads have run yet
(the VPS setup is in `docs/infra-provisioning.md`), so `file_tracking` has no nightly history. The generator and its
arithmetic are tested on a synthetic fortnight with one failure day
(`services/ingest/tests/test_report.py`: success rate 139 of 140, longest streak 7 days).

| Item | Value |
|---|---|
| Window | _to fill_ |
| Chains measured | _to fill_ |
| Success rate | _to fill_ |
| Longest streak above 95 percent | _to fill_ |
| Failed or quarantined full files, with reasons | _to fill_ |

## 2. Store coordinates

Criterion: every physical store has coordinates, or the exceptions are listed with reasons.

Regenerate: same command; paste section "2. Store coordinates". It counts physical stores
(`channel = 'physical'`) and lists those with `stores.geog IS NULL` with chain, store code, name,
city and address. Online stores are not physical stores and are not counted. Equivalent SQL:

```sql
SELECT chain_id, store_code, name, city, address
FROM stores WHERE channel = 'physical' AND geog IS NULL ORDER BY chain_id, store_code;
```

Status: **blocked on the two-week window** (no stores are loaded from real files before the
nightly pipeline runs). The listing logic is tested, including the case of a database without
PostGIS.

Each exception needs a reason and a plan: geocode from the address, ask the chain, or accept the
store as excluded. The generator states the mechanical reason (`geog` is NULL); the human reason
goes here.

| Chain id | Store | Reason it has no coordinates | Plan |
|---|---|---|---|
| _to fill_ | | | |

## 3. Promo parsing for the top chains

Criterion: promo parsing is demonstrated for the top chains, with a sample of checked promos.

Top chains are the six main chains of D13: Shufersal, Rami Levy, Victory, Yeinot Bitan and
Carrefour, Hazi Hinam, Tiv Taam. Regenerate: same command; paste section "3. Promo parsing, main
chains". For each main chain it gives the count of parsed promos by reward type and a sample of up
to ten promos, spread over reward types and stable between runs, with the raw description next to
the structured fields (reward type and value, min and max quantity, club, dates, hours, item count).

The check is by a person: for every sampled promo, compare each structured field with the raw
description and tick the `Checked` column, or write what is wrong. A promo whose reward type is
`other` is a parsing gap, not a pass. Record the ratio of promos that are `other` per chain.

Status: **blocked on the two-week window** for real promos. The sampler is tested on synthetic
promos.

| Chain | Promos parsed | Sample checked | Fields wrong | `other` share | Notes |
|---|---|---|---|---|---|
| _to fill_ | | | | | |

## 4. Basket price across all stores within a radius

Criterion: a SQL query takes a list of barcodes and a point plus radius and returns a basket total
per store using PostGIS. The query and sample output are in the report. Missing items are reported
as missing, not ignored.

The query is `supabase/queries/basket_radius.sql`; its parameters, assumptions and result columns
are in `supabase/queries/README.md`. In short: stores from `stores_within`, online stores excluded
unless requested, the price of each barcode from `current_price` (latest store price, else latest
base price), one row per store with `basket_total`, `found_count`, `missing_barcodes` and
`is_complete`. A store with missing items keeps its row and lists what is missing.

Status: **met on synthetic data; to be re-run on real data.** The query is proven by
`services/ingest/tests/test_basket_query.py`, which CI runs against PostGIS: per-store totals, the
latest-price rule (a future event ignored, a store price over the base price), the excluded online
store, the excluded far store, the missing-barcode arrays, and complete baskets sorting first. The
sample output below is from that synthetic data, not from real prices.

Regenerate on real data, either with psql:

```bash
sed -E "s/%\(([a-z_]+)\)s/:'\1'/g" supabase/queries/basket_radius.sql \
  | psql "$DATABASE_URL" -X \
      -v "barcodes={7290000000011,7290000000012,7290000000013}" \
      -v lon=34.7918 -v lat=32.0744 -v radius_m=3000 -v include_online=false \
      -f -
```

or through the report generator (`--basket-barcodes`, `--lon`, `--lat`, `--radius-m`, and
`--include-online`), which puts the same table into section 4. Pick a real basket of 10 to 20
common barcodes that exist in several chains (milk, eggs, bread, oil), and a point in a dense area
such as central Tel Aviv with a 3000 m radius. Record the basket, the point and the date.

Sample output (synthetic):

```
 store_id | chain_id |    store_name     | city | channel  | distance_m | basket_total | found_count |       missing_barcodes        | is_complete
----------+----------+-------------------+------+----------+------------+--------------+-------------+-------------------------------+-------------
        1 | chain-a  | Chain A Azrieli   | Test | physical |          0 |        13.50 |           2 | {7290000000013}               | f
        2 | chain-b  | Chain B Dizengoff | Test | physical |        944 |         7.50 |           1 | {7290000000012,7290000000013} | f
(2 rows)
```

Reading it: the Chain B total is lower only because two of three items are missing. Nothing is
silently dropped, so the gap is visible and `is_complete` is false for both rows.

Real-data run: _to fill, with the date, the barcodes and the point._

## 5. Go or no-go for phase 1

**NO-GO until the two-week window is observed.**

Phase 1 (canonical catalog and web app) needs trustworthy data. Three of the four evidence
criteria depend on nightly loads that have not run yet, so the honest answer today is no-go. The
recommendation changes to go only when every box below is ticked, with the evidence pasted in the
sections above.

Checklist to flip the decision:

- [ ] The VPS has run the nightly pipeline for at least 14 consecutive days and the window is
      recorded in section 1.
- [ ] Section 1 shows a success rate above 95 percent over the window across the chosen chains
      (ten, or eight if the tie-break dropped two and that is written down), and any failed or
      quarantined full file has a reason.
- [ ] Section 2 shows every physical store with coordinates, or each exception has a reason and a
      plan, and the exceptions are a small share of stores.
- [ ] Section 3 shows a checked sample for each of the six main chains, with no systematic parsing
      error left open and the `other` share per chain recorded.
- [ ] Section 4 has been re-run on real prices, with the basket, the point and the date, and at
      least one row is complete.
- [ ] Open data-quality items from the window (quarantines, schema `unknown` files, the
      consumer-authority schema change of 2026) are listed with an owner.
- [ ] The decision, its date and the person who made it are written here, and issue #60 is closed.

Decision: **NO-GO** (not yet decided on evidence). Date: _to fill_. Decided by: _to fill_.
