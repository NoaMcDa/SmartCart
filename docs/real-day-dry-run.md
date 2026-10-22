# One real day through the whole pipeline (dry run)

> **A dry run on one day, with hand-made baskets.** It is not the phase 0 exit (`phase-0-exit-report.md`
> stays NO-GO), not a price survey, and nothing here may be published: the basket index it computes is a
> draft the pipeline itself refuses to publish. The prices are real; the baskets, the three locations and
> the stores the optimizer saw are not a sample of anything.

Until now everything downstream of ingestion had run on synthetic data only (`optimizer.md`, `fullstack.md`,
`phase-2-status.md`: "re-measure on real price files"). The workflow **Real day**
(`.github/workflows/real-day.yml`, script `scripts/unblock/real_day.py`) takes one real day of transparency
files through every stage on a GitHub-hosted runner and times each stage. Labels follow `docs/README.md`:
**measured** is read from a run, **derived** is reasoning from a measured value, **estimate** is a judgement.

## What the run does

On `ubuntu-latest` (4 vCPUs, not an Israeli IP) with the same `supabase/postgres:17.11.0.004` service as CI:

1. **Download.** The portal probe's own function (`portal_probe.probe`, unchanged: reachability, Cerberus
   login, one Stores and one PriceFull per chain through the pinned upstream scraper, never a chain's online
   store). One PriceFull is one store, which is too thin for a split, so once the Stores files are loaded and
   the stores have coordinates (`docs/geocoding.md`) the script ranks ten city centres by how many chains have
   a located store within 4 km, takes the three best, and downloads the PriceFull and PromoFull files of the
   two nearest stores of each chain (the same scraper with a file-name filter, in a subprocess that a hung
   portal cannot block).
2. **Ingest.** Every file through the real `Scheduler` path (adapter, quality gates, loader). A file older than
   the stale-date limit (36 h) is loaded with the clock replayed one hour after its publication, as
   `scripts/demo/load_fixtures.py` does, and reported as a finding; every other file is judged at the real time.
   Store coordinates are set by the loader from `data/geo` (769 of 827 physical stores, `geocoding.md`).
3. **Catalog.** `smartcart-catalog seed, normalize, extract (rule), embed (hash), judge (rule)` on the real
   items (the hash embedder: BGE-M3 on 100,000 items is hours on a runner CPU and was not run).
4. **Precompute.** `smartcart-api precompute`.
5. **API.** `/parse-list` on three hand-made Hebrew lists (6, 17 and 32 lines), `/compare` and `/optimize`
   (heuristic and MILP) through the FastAPI test client at three locations, for those lists and for baskets
   of 5, 10, 20 and 40 canonicals drawn at random (seeded) from what was priced at two or more stores near the
   location. Every request is repeated five times (median reported). A **relaxed** variant (an extra stop
   worth 0, `min_split_saving` 0) forces splits, which is the MILP's heavy path.
6. **Basket index** (`smartcart-catalog basket-index`) into a scratch directory.
7. **Stress variant.** The unreviewed machine suggestions are marked accepted, and steps 4 to 6 run again.
   This measures the optimizer on a priced set about twice as large; it is **not product behaviour** and says
   nothing about the precision of those mappings.

All numbers below are from run [39668058512](https://github.com/NoaMcDa/SmartCart/actions/runs/39668058512)
(2026-10-21, 20:49 to 21:21 UTC, commit `cc3fa98`), the richest of the runs that completed, unless another run
is named. Its report and JSON are the artifact `real-day-report`; the generated Markdown is the job summary.

## Stage timings (measured)

| Stage | Seconds | Notes |
|---|---|---|
| Portal probe: reachability, login, one Stores and one PriceFull per chain | 539 | the portals are the time; Victory and Machsanei Hashuk each wait out the 60 s timeout twice |
| Migrations | 1.2 | 25 applied |
| Load the 7 Stores files | 0.6 | |
| Download 60 PriceFull and PromoFull files of the stores near 3 city centres | 504 | Shufersal and Mega list slowly |
| Load 67 PriceFull and PromoFull files | 109 (loader 73) | 291,387 price rows and 36,722 promos; 23.7 MB of gz and xml for all 74 files |
| `catalog seed` | 1.1 | |
| `catalog normalize` | 9.4 | 99,612 items |
| `catalog extract` (rule) | 90 | |
| `catalog embed` (hash) | 332 | 99,612 item vectors and 245 canonical vectors |
| `catalog judge` (rule) | 233 | |
| `precompute` | 1.3 (job 0.91) | 8,221 rows |
| API stage: 21 basket runs x 5 repeats x 5 requests | 55 | includes three `/parse-list` calls that took 5 to 27 s each, see below |
| Basket index | 0.5 | |

Whole job: about 32 minutes of which 17 are portals.

## Files and gates (measured)

7 of the 10 D13 chains gave files; **74 files, all 74 reached `loaded`, 0 alerts, 0 quarantined, 0 failed**
(`file_tracking`). Hazi Hinam (HTTP 403 and no file from the scraper) and Victory and Machsanei Hashuk (the
laibcatalog host does not answer, 61 s timeout each) gave nothing from the runner.

| Chain | Stores | PriceFull (stores) | PromoFull | Price events | Items | Promos | Physical stores (located) |
|---|---|---|---|---|---|---|---|
| Shufersal | 1 | 7 | 6 | 36,447 | 13,650 | 5,445 | 416 (411) |
| Rami Levy | 1 | 7 | 6 | 69,710 | 18,422 | 10,804 | 98 (96) |
| Carrefour (Mega) | 1 | 7 | 6 | 49,342 | 13,519 | 8,828 | 147 (144) |
| Osher Ad | 1 | 5 | 4 | 32,754 | 8,715 | 2,905 | 24 (24) |
| Tiv Taam | 1 | 5 | 4 | 58,521 | 24,986 | 5,508 | 47 (47) |
| Yohananof | 1 | 3 | 2 | 33,816 | 13,572 | 2,489 | 50 (19) |
| King Store | 1 | 3 | 2 | 10,797 | 6,748 | 743 | 48 (28) |
| **Total** | 7 | 37 | 30 | 291,387 | 99,612 (distinct per chain) | 36,722 | 830 (769) |

- **Gate results.** A file's row count is its price rows or promos; the per-file table (published time, age,
  schema, gate, rows, load time) is in the report. Every file was schema v1. Loading ran at about 4,000 price
  rows per second. The stale-date gate fired on **no** price or promo file (the oldest was 23.9 h) but see finding 1 for the
  Stores files. The price-jump and item-count-drop gates **could not be exercised**: each store was loaded for
  the first time, so there was no earlier day to compare with. That needs the second day.
- **Stores with coordinates.** 769 of 830 physical stores, as `geocoding.md` predicted (Yohananof 19 of 50 and
  King Store 28 of 48 are the weak chains: many of their stores have city code 0).
- **Stores with prices: 37**, in 7 chains. That, not the 830 listed, is what every later stage sees.
- Run-to-run, the portals do not return the same set: the same job loaded 68 files (run 2), 74 (runs 4 and 6),
  and 60 (run 7, where the Mega portal answered "no file matched" for six stores it had listed an hour earlier).

## Matching on the real items (measured; precision not measured)

| | Count |
|---|---|
| Real items | 99,612 |
| Mapped to a canonical (any level, including the review queue) | 21,520 (21.6 %) |
| Served: mapped and not flagged for review | 5,923 (5.9 %), onto 210 of the 245 canonicals |
| `exact` | 0 served, 0 in review (no real barcode equals a canonical's reference barcode) |
| `any_brand` | 3,609 served, 6,481 in the review queue |
| `close` | 2,314 served, 9,116 in the review queue |

Served by chain: Shufersal 944 of 13,650 items, Rami Levy 1,350 of 18,422, Mega 1,010 of 13,519, Osher Ad 690 of
8,715, Yohananof 916 of 13,572, King Store 324 of 6,748, Tiv Taam 689 of 24,986. The 5.9 % matches the 6.6 % the
1,400-item audit found (`matching.md`, "Real items, first audit"), so the 245 canonicals cover a small part of a
supermarket and the review queue (15,597 mappings) is what a human would have to clear. There is no gold set for
these items, so **no precision figure** is claimed; the audit's 1.000 was one reader on a subset.

## Precompute (measured)

8,221 rows (3,612 `any_brand`, 4,609 `close`, 0 `exact`) for 5,706 items at **37 stores** of 7 chains, in 0.91 s
of job time (1.3 s with start-up). **209 canonicals have a real price** (193 at `any_brand`), 191 of them at two or
more stores. **0 rows carry a promo** (finding 2). Stress variant: 13,609 rows, 241 canonicals, 2.3 s.

| | Rows | Job seconds | Seconds per 1,000 rows |
|---|---|---|---|
| Real day, reviewed mappings only | 8,221 | 0.91 | 0.11 |
| Real day, stress | 13,609 | 2.28 | 0.17 |
| Synthetic scaled world (`optimizer.md`) | 144,380 | 26.9 to 33.2 | 0.19 to 0.23 |

The per-row cost is the same order, but 8,221 rows at 37 stores is a different scale from 300 stores and 144,380
rows: this does **not** re-measure the job at its target size. It shows the SQL runs on real names, prices,
units and weighed goods without error.

## `/compare` and `/optimize` (measured)

Locations (by the number of priced stores within 5 km): Jerusalem centre (10 stores, 6 chains), a Tiv Taam in Ono
near Petah Tikva (9 stores, 5 chains), Haifa centre (8 stores, 5 chains). Each location has 8 to 10 priced
stores, so every call considers 8 to 10 candidates and **55 store sets** (the K = 2 case of the optimizer's
N = 10). Times are the median over five repeats, in ms, through the in-process test client (no network, no
uvicorn), Postgres on the same 4-vCPU machine.

| Basket | `/compare` | heuristic | MILP | MILP, relaxed |
|---|---|---|---|---|
| hand-made, 6 lines | 8.7 | 7.4 | 13.1 | 13.3 |
| hand-made, 17 lines | 12.8 | 8.9 | 15.5 | 15.6 |
| hand-made, 32 lines | 16.0 | 10.8 | 17.8 | 18.2 |
| drawn, 5 canonicals | 8.9 | 8.0 | 13.0 | 14.6 |
| drawn, 10 | 10.3 | 7.8 | 13.8 | 14.1 |
| drawn, 20 | 12.6 | 8.9 | 15.1 | 15.3 |
| drawn, 40 | 19.4 | 11.2 | 17.8 | 18.2 |

Across the 21 basket-location pairs the median is 8.9 ms (heuristic), 15.2 ms (MILP) and 11.9 ms (`/compare`);
the slowest single call was 87 ms (heuristic) and 25 ms (MILP) in the production variant. In the stress variant
(66 percent more precompute rows, 13,609 against 8,221) the medians were 9.2, 15.5 and 13.8 ms with one MILP call
at 90 ms and one relaxed call at 98 ms.

Next to `optimizer.md` (synthetic, scaled world, over HTTP with two uvicorn workers, 50 baskets of 25 canonicals,
55 stores in a radius): heuristic p50 23 to 28 ms, MILP p50 36 to 44 ms, `/compare` p50 71 to 72 ms. The
real-data medians are lower by roughly a factor of 3, but the two are not comparable: the synthetic run
included the HTTP stack and a `/compare` over 55 to 79 stores in the radius, the real one 8 to 10. What the real
run does show is that **the optimizer's cost is flat in basket size over 5 to 40 lines on real data (heuristic
7 to 11 ms, MILP 13 to 18 ms)** and that the MILP costs about 6 ms more than the heuristic here (about 15 ms
more in the synthetic run, which included the HTTP stack).

What the plans looked like:

- **No split was recommended** with the default settings (extra stop worth 25, `min_split_saving` 25) in any of
  the 21 production runs or the 21 stress runs. With the relaxed settings a split appeared in 4 of 21 production
  runs and 11 of 21 stress runs. On this day, at these three places, for these baskets, a second stop did not
  pay at ₪25 per stop: this is one day and nine to ten stores, so it says little about the product.
- **The MILP never fell back to the heuristic, never produced a worse net saving, and equalled the heuristic's net
  saving in every one of the 84 pairs** (production, stress, default and relaxed). That is expected and not
  evidence of anything: with 0 promos reaching a price (finding 2) the MILP's difference (shared promo bundles)
  is never used, so on this data the two are the same problem. **The MILP's reason to exist has not been
  tested on real data**; it needs promos that link to items.
- **3 of 21 recommended plans have a negative net saving** (for example Haifa, 17 lines: -₪11.87). The
  optimizer ranks by missing items first (`routes/optimize.py`), and no store had every line: 19 of 21 production
  basket runs had no complete store at all (the hand-made lists and the drawn baskets of 10 or more). The plan with
  fewer missing lines can cost more than the home store. By design, but a negative "hero number" must be handled
  by the UI.
- Trust fields: the script checks every `/compare` and `/optimize` response for `price_valid_from` on each line,
  `prices_updated_at` on each store, the disclaimer, labeled substitutes and
  `net_saving = basket saving - travel - extra stop`; it recorded **no violation** in the 42 basket runs.

`/parse-list` resolved all 6, 17 and 33 lines of the hand-made lists (2 and 5 of them flagged "needs
confirmation" in the longer ones), but took **5 s, 14 s and 27 s** (finding 3).

## Basket index on the real day (#44; a dry run, not publishable)

| Variant | Chains pricing all 25 lines | Lines priced per chain | Status |
|---|---|---|---|
| Reviewed mappings only | 0 | Shufersal 17, Rami Levy 16, Mega 14, Yohananof 14, Tiv Taam 13, King Store 10, Osher Ad 8 | draft, error `too_few_chains` |
| Stress (unreviewed mappings counted) | 1 (Mega) | 20 to 25 | draft, error `too_few_chains` |

Not one ranked chain with the mappings a person would have accepted, and one in the stress variant, where the
index needs two. `eggs-l` is priced at no chain in either variant: the real egg names (for example `ביצים 2*30
יח' בינונ`) have no recognised product type (finding 5). The totals from the stress variant are not reported; they
include mappings nobody has reviewed and estimated weighed-goods prices. The index code, its checks (missing
items, estimated lines, too few chains) and the draft rule all ran on real data and behaved as designed.

## Everything the real data broke or exposed

Each item says where it lives so the lead can route it. I changed none of them; the glue I own (the script and
the workflow) needed one fix of its own (the call of the extra download).

1. **Stores files go stale under the stale-date gate** (ingestion core, `smartcart_ingest/quality.py`
   `gate_stale_date`, applied to kind `stores`). The Cerberus chains publish their Stores file every few days:
   on 2026-10-21 the files of Osher Ad, Rami Levy, Tiv Taam and Yohananof were dated 2026-10-19, 64 to 71 hours
   old, against the 36-hour limit. On the real clock the gate would quarantine them, and with no Stores file no
   store of those four chains loads and no PriceFull can be priced. The script replays the clock for those files
   (and flags them in the report). The committed real fixtures show the same pattern (Stores files two days
   older than the price files, `phase-0-exit-dry-run.md`), which the replayed clock of that dry run hid.
2. **Real PromoFull files load with no items, no reward and no quantity** (adapters, promos:
   `smartcart_ingest/adapters/_common.py`, the promo parser, all chains). 36,722 promos from 30 files in seven
   chains: **every one has `item_codes = []`, `reward_type = 'other'`, `min_qty = None`**, so `promo_items` has 0
   rows, `effective_prices` has 0 rows with a promo and no promo can reach a price. The adapter's `raw` keys
   (`promotionid, promotiondescription, promotionstartdatetime, promotionenddatetime, clubid, minnoofitemoffered,
   ...`) hold no item list, so the item list sits in an element the adapter does not read; the reward is only in
   the description (`צלעות עגל טרי 1 קג ב 49.9`). Also every promo of the Shufersal, Tiv Taam and Yohananof files
   is `club_only` (1,379 of 1,379 in one Shufersal file), against 0 to 3 percent for Osher Ad, Mega and Rami Levy,
   which looks like a field mapping, not a market fact (**not verified**). This is what keeps #13's shared-promo
   MILP and #47's promo folding untested on real data.
3. **`/parse-list` and `/search` take 0.5 to 0.9 s per line at 99,612 items** (API,
   `smartcart_api/search.py` `_vector`). One call with 6 lines: 4.9 s, of which 4.9 s inside six executions of the
   vector statement (max 848 ms each); the other 31 statements cost about 50 ms in all. `EXPLAIN (ANALYZE, BUFFERS)` of
   the slowest (run 39673601986, `plan` below) shows the `near_items` part reading **all 96,966 rows of
   `item_embeddings` with a sequential scan** and a top-N sort (775,000 buffer hits, 66,500 reads, 675 ms)
   instead of using `item_embeddings_hnsw`. The same `ORDER BY embedding <=> q LIMIT 40` on its own, in the
   diagnostic, used the index and took 1 to 5 ms, so it is the statement as built (`LIMIT 80` = k x 4 with the
   query vector in a CTE joined to the table, followed by the join to `item_canonical`) that the planner turns
   into a scan. At 1,400 items, as in the demo and the tests, it is invisible (283 ms for 6 lines in my offline
   run on the committed fixtures). A pasted list
   of 30 lines would wait about half a minute. Suggestion, not tested: the query vector as a bind parameter, or
   `SET LOCAL enable_seqscan = off` for the statement, and `hnsw.iterative_scan`.
4. **Portal coverage and the probe's reachability column.** From the runner Hazi Hinam answers 403 and the scraper
   returns no file; Victory and Machsanei Hashuk (laibcatalog) time out; King Store's root answers 403 yet the
   scraper downloads its files. The probe's table says `UNREACHABLE (0)` for the four Cerberus chains although the
   FTP login passes and the files download: `portal_probe.http_status` tests an HTTPS root that is not how that
   portal is used (the probe's owner). The Mega portal listed the six stores' files in runs 2, 3, 4 and 6 and "no
   file matched" in run 7, an hour later. Shufersal's filtered listing needed more than 240 s twice (the script
   now allows 600 s).
5. **Matching covers 5.9 % of real items.** Eggs are the sharp case: no real egg item reaches `eggs-l`,
   `eggs-m` or `eggs-xl` (`data/audit/real-2026-10-08.csv`: `ביצים 2*30 יח' בינונ` has confidence 0.43,
   "critical unknown product_type"), which alone stops the basket index. 15,597 mappings sit in the review queue,
   9,116 of them at `close`. Matching and normalization owner.
6. **A negative recommended net saving** (3 of 21 plans) when no store is complete: see above (optimizer and API,
   `routes/optimize.py`; by design, a question for the UI).
7. **Nothing failed in the pipeline glue itself.** No adapter error, no loader error, no gate failure, no timeout
   in a stage after the downloads. That is a result: 74 real files from 7 chains, 291,387 price rows and 36,722
   promos loaded cleanly; the faults above are about what was *not* read or *not* chosen, not about files being
   rejected.

## Plan of the slow statement (run 39673601986, measured)

```
->  Limit  (actual rows=80)   Buffers: shared hit=774952 read=66443
      ->  Sort  (top-N heapsort, Sort Key: e.embedding <=> qv.v)
            ->  Nested Loop  (actual rows=96966)
                  ->  CTE Scan on qv
                  ->  Seq Scan on item_embeddings e  (actual rows=96966)
                        Filter: (model = 'hash-ngram-2-3-4-v1')     Buffers: shared read=1000
->  Index Scan using item_canonical_pkey on item_canonical ic  (loops=80)
Execution Time: 675 ms
```

## Status for the issues

- **#13 (MILP).** Ran on real prices: 84 solves, no fallback, never worse than the heuristic, 13 to 18 ms median
  (98 ms worst) for 5 to 40 lines and 8 to 10 stores. Not tested on what makes it different, because no real
  promo reaches a price (finding 2); equal to the heuristic everywhere. Stays "done with synthetic data" for the
  bundle logic.
- **#44 (basket index).** Computed on a real day for the first time: draft, 0 chains complete (1 in the stress
  variant), `too_few_chains`. Needs egg and dairy matching and a reviewed catalog before any month can be
  published.
- **#47 (precompute).** Ran on real items, units and prices: 8,221 rows in 0.9 s at 37 stores, no error. Promo
  folding got no real input. Scale (300 stores) not re-measured.
- **#60 (exit).** Evidence for the dry run, not for the exit: 74 real files in 7 chains load through the gates;
  finding 1 (stale Stores files) and finding 2 (promos) would each break fourteen nightly loads of the VPS and
  should be fixed before the clock starts. Still NO-GO.

## Re-running

`Actions` tab, **Real day** (or `uv run --no-sync python scripts/unblock/real_day.py run --work DIR
[--from-fixtures | --files DIR]`; offline, on the committed 200-row fixtures, it takes about 35 s and was how the
script was developed). Inputs: `chains`, `timeout`, `anchors`, `per_chain`, `max_files`, `with_promos`, `stress`,
`commit_report` (pushes the Markdown and JSON, never the raw files, to `real-day/report-<run id>`). Tests of the
script's pure parts: `uv run pytest scripts/unblock/tests/test_real_day.py -q`. The raw files stay 7 days in the
`real-day-files` artifact.
