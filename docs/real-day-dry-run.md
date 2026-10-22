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
   the stale-date limit of its kind (36 h; 240 h for Stores files since the second run, as in the ingestion
   settings) is loaded with the clock replayed one hour after its publication, as
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

Two runs are described: the **second run** (2026-10-22, current code) first, then the **first run**
(2026-10-21), kept as history because its numbers are what the second run is compared with. The first run's
sections are marked "(first run)"; its findings that no longer hold are marked in the table below.

## Second run (2026-10-22): what changed since the first run

The first run (below, kept as history) ran on a branch that predated the real promo parsing, the per-kind
stale limits, the club rules and the two-group promos. The second ran on the code of 2026-10-22
(`more7/realday2`), to see which findings were gone and to fix the egg gap that stopped the basket index.
Each run is one real day, and **the portals do not return the same files twice** (Shufersal and Mega timed
out at 300 s in the last run; Mega had a single store in the run before), so numbers between runs differ by
what was downloaded, not only by the code. Labels follow `docs/README.md`: the numbers below are **measured**
from the run named; the reading of them is mine.

| Run | Commit | Code | Chains with files / files loaded | Used for |
|---|---|---|---|---|
| [39733359864](https://github.com/NoaMcDa/SmartCart/actions/runs/39733359864) | `2179f3d` | main + the candidate log, no egg rules | 6 / 66 | findings 1 and 2 |
| [39739262262](https://github.com/NoaMcDa/SmartCart/actions/runs/39739262262) | `8541a29` | same + per-kind stale limit, API limiter off | 6 / 66 | the real egg names (before) |
| [39744079077](https://github.com/NoaMcDa/SmartCart/actions/runs/39744079077) | `627a7e3` | egg rules | 7 / 55 | the eggs after, 7 chains |
| [39749768866](https://github.com/NoaMcDa/SmartCart/actions/runs/39749768866) | `01212a7` | final code, per-line basket cost | 5 / 51 | the eggs after, the per-line cost |

(A fifth run, 39683475811, completed but its report existed only in the job summary, which cannot be read from
outside the page. The workflow's `commit_report` input pushes the Markdown and JSON to a
`real-day/report-<run id>` branch; that is how the other four were read.)

### Findings of the first run: which are gone

| # | First run | Second run (measured) |
|---|---|---|
| 1 | Stores files 64 to 71 h old would be quarantined by the 36 h stale gate | **Gone.** The Stores files of Osher Ad, Rami Levy, Tiv Taam and Yohananof were 50 to 59 h old and every one was `loaded` (all four runs; `file_tracking` only `loaded`, 0 alerts, 0 quarantined, 0 failed). The gate has its own 240 h limit for Stores files (`settings.DEFAULT_STALE_STORES_HOURS`); the script no longer replays the clock for them (it used 36 h for every kind, so it would have reported a finding that no longer exists). |
| 2 | 36,722 promos, every one `other`, 0 item links, 0 promo rows in effective prices | **Gone.** Run 39744079077 (7 chains): 29,724 promos, all with item codes, 196,656 `promo_items` rows; reward types `bundle` 14,435, `price` 12,184, `other` 2,867 (9.6 %), `buy_x_get_y` 194, `percent` 44. 1,642 of 5,627 effective-price rows carry a promo (29 %). Per chain in the table below. |
| 3 | `/parse-list` 5 to 27 s | **Not fixed here** (the vector query is another agent's): 3.9, 11.0 and 21.3 s for 6, 17 and 32 lines at 81,595 items; 2.1, 6.0 and 11.1 s at 70,001 items. The bare nearest-neighbour query uses the HNSW index (1 ms); the full statement still scans, as in the first run's plan. |
| 4 | Portal coverage | Same: Hazi Hinam 403, Victory and Machsanei Hashuk time out, Shufersal and Mega list slowly (300 s timeouts in the last run). |
| 5 | No real egg reaches `eggs-l` | **Fixed in matching** (below); not yet in the prices (finding 9). |
| 6 | A negative recommended net saving when no store is complete | Unchanged: 5 of 21 plans in the production variant, 4 of 21 in the stress variant. |
| 7 | Nothing failed in the glue | One thing did: the API's per-client rate limiter (new since the first run) answered 429 to the timing loops (80 recorded failures in run 39733359864). The script now switches it off the way the load tests do (`API_RATE_LIMIT=0`). |

Promos per chain and what reached a price (run 39744079077, reviewed mappings only):

| chain | promos | club-only | linked to items | reward `other` | effective rows | with a promo | club required | of them with a non-club fallback |
|---|---|---|---|---|---|---|---|---|
| Mega | 1,547 | 6 | 947 | 104 | 220 | 82 | 4 | 4 |
| King Store | 602 | 140 | 602 | 1 | 294 | 79 | 19 | 19 |
| Rami Levy | 11,984 | 205 | 11,027 | 2,424 | 1,834 | 648 | 0 | 0 |
| Osher Ad | 3,567 | 0 | 3,230 | 14 | 813 | 265 | 0 | 0 |
| Yohananof | 4,806 | 44 | 4,722 | 247 | 1,121 | 300 | 14 | 14 |
| Tiv Taam | 7,218 | 4,262 | 7,218 | 77 | 1,116 | 268 | 168 | 168 |

**Club promos are gated in the prices (precompute side).** 205 effective-price rows need a club, and every one of
them carries the non-club alternative the API shows to a person who is not a member. Tiv Taam's single rule
`המועדון החדש` covers 4,262 of its 7,218 promos (59 %; in the first run every Tiv Taam promo was club-only); Rami
Levy's biggest rule is a five-club alternative (`מועדון חברתי | מועדון רמי לוי | מועדון לקוחות אשראי | מועדון נטען |
לקוחות ארנק`, 132 promos). The script does not assert club gating at the API (`/compare` is called without a
profile, which is a non-member's view); that is the job of `test_api_clubs_real.py`.

**The MILP now meets real promos.** Run 39744079077: its recommended plan used promo bundles in 9 of 21
production runs and 13 of 21 stress runs, it never fell back to the heuristic, and its net saving equals the
heuristic's in every one of the 42 pairs (difference 0.0); medians 12 ms (heuristic) and 19.5 ms (MILP), the worst
MILP call 37 ms. So the bundle logic ran on real promo data for the first time and added no saving on these
baskets (one day, 5 to 10 stores per place).

### Eggs: the real names and what the catalog does with them

The script now lists, for each basket line that a chain does not price, the real items whose names mention the
product, with the attributes extraction gave them, the mapping they got and the judge's own reason (re-run for
the report, nothing written). Run 39739262262, before any egg rule, for `eggs-l` at the five chains that did not
price it (King Store, Rami Levy, Osher Ad, Yohananof, Tiv Taam): 97 egg items.

| | Same 97 items, old reading | New reading |
|---|---|---|
| names that state one size (L 23, M 28, XL 6) | **0 mapped** (unknown product type, confidence below 0.6, rejected) | all typed `eggs_l`, `eggs_m`, `eggs_xl` |
| free range | 15 mapped to `eggs-free-range-l`, **7 of them served, 4 of those wrong** (`ביצי חופש 12 יח M`, `ביצי חופש 12 יח בינו`, `ביצי חופש 12 יח`, `ביצי חופש`: sizes M, M and none) | free range only with size L; the others are `eggs` and vetoed |
| size missing or ambiguous, organic, omega-3, quail, hard-boiled | 25 unmapped, 8 mapped to the free-range canonical | 33 `eggs`, vetoed by every egg canonical |

What the judge then did with them (run 39749768866, final code, the four chains that still did not price
`eggs-l`, 80 egg items): 16 to `eggs-l` (7 any brand and 8 close in the review queue, 1 close served), 24 to
`eggs-m` (10 and 14, review), 5 to `eggs-xl` (review), 5 to `eggs-free-range-l` (1 served), and 30 `eggs` unmapped.
The same rules in run 39744079077 (7 chains, 86 items): 18 to `eggs-l`, 25 to `eggs-m`, 5 to `eggs-xl`, 6 free range.
**Every item that states one size is now a candidate of its own size canonical and of no other**; the rules and
their reasons are in `matching.md`, "Real items, eggs", and the 80 test cases are the real names
(`services/catalog/tests/test_extract_eggs_real.py`). Rami Levy's 12-pack of L (`ביצים 12 יח גדול L`) is served
at any brand; most of the rest wait in the review queue, because the hash embedder gives a long name a low
similarity (`12 ביצי משק טריות L לסר`: 0.35) and the confidence is `0.4 x similarity + 0.6 x attributes`.
There is no gold set of real egg names: **no precision figure on real items is claimed**. The synthetic gold
sets are unchanged by the change (Hebrew any brand 1.0000 precision, 0.8125 recall; close 1.0000 and 0.7611;
Arabic any brand 1.0000 and 0.9391), as they should be: they carry their own lexicon.

### Basket index (#44), second run

| Variant | Run | Chains pricing all 25 lines | Lines priced per chain | Status |
|---|---|---|---|---|
| Reviewed mappings only | 39744079077 (7 chains) | 0 | Rami Levy 19, Shufersal 14, Yohananof 14, Tiv Taam 13, Mega 12, King Store 8, Osher Ad 8 | draft, `too_few_chains` |
| Reviewed mappings only | 39749768866 (5 chains) | 0 | Rami Levy 19, Yohananof 14, Tiv Taam 13, King Store 8, Osher Ad 8 | draft, `too_few_chains` |
| Stress (unreviewed counted) | 39744079077 | **3** (Rami Levy 908.24, Yohananof 928.27, Tiv Taam 1,421.25) | 21 to 25 | draft, **`implausible_spread` 56.5 % (limit 50 %)** |
| Stress, before the egg rules | 39739262262 | 1 (Mega) | 20 to 25 | draft, `too_few_chains` |

`eggs-l` was priced at no chain in the first run's production variant and is priced at Rami Levy now; in the
stress variant it is priced at every chain (it was missing at five chains before), so `too_few_chains` is gone
there and the egg gap is no longer what stops the index. **The index is still a draft that must not be
published, for a different reason: the totals are not credible.** The new per-line cost table in the report
(`Cost of each line per chain`) shows why. Three causes, none of them in the matching:

8. **Rami Levy's published unit price for weight is per gram, not per 100 g** (ingestion,
   `loader.normalize_unit_price`). In the committed Rami Levy fixture 76 of 200 prices say `UnitOfMeasure = '100 גרם'`
   and the value is the price of one gram: `שקד * קלוי 200 גר` costs 15.10 and publishes 0.08 (15.10 / 200 g = 0.0755
   per gram; per 100 g it is 7.55); `חיטה 1 קג רמי לוי` costs 10.00 and publishes 0.01. The loader reads it as per
   100 g, so Rami Levy's weight unit prices are 100 times too small. Real run: `שמן קנולה אורגני בכב` 27.90 gives 0.03
   per 100 ml, `לחם אחיד אנג'ל 750 ג` 7.36 gives 0.01 per 100 g, against 0.5 to 1.1 at the other chains for the
   same lines; in the table Rami Levy's rice, bread, canola oil, butter, cottage cheese and yogurt lines cost
   ₪0.07 to ₪0.9 where the others cost ₪5 to ₪15. It would make Rami Levy the cheapest chain on every packaged line.
   Not verified with the chain; the reading follows from the 14 sampled rows whose size is in the name.
9. **The pack count in the name does not reach the unit price** (precompute, `precompute._unit_price`, which uses
   the published unit price or the item's `quantity`/`unit` fields, never the catalog's normalization). Where the
   fields say `1 יחידות` and the name says `12 יח` (Rami Levy, Yohananof, Tiv Taam), the tray price is taken as the
   price of one egg: `ביצים 12 יח גדול L` at 14.20 gets 14.20 per unit, while King Store's `ביצים לארג' 12 יח'` has the
   field 12 and gets 1.18; the eggs line then costs ₪170.40 against ₪14.16. The same happens to a pack of 10 pitas
   (9.90 at Yohananof and 16.90 at Tiv Taam per unit against 1.19 to 1.49) and to 24 rolls of toilet paper (₪669.60
   at Rami Levy and ₪789.60 at Tiv Taam against ₪20.88 at King Store). Matching eggs correctly **unmasks** this: Rami
   Levy's 12-pack of L is served now, at 12 times its price. Every `unit`-based canonical whose pack count is only
   in the name is affected, not only eggs. *The eggs, pitas and `32 גלילים` were fixed by the pack counts (precompute);
   a pack whose count no reading states, and the names the normalizer did not read (`32 גליל`, `32גל`), were still
   priced per pack in run 39804455160 (toilet paper at 813.60). Fixed on 2026-10-22: "Unit-price outliers" below.*
10. **Lines that cost ₪0.0** in the table (`toilet-paper`, `sugar-white`, `cucumber` at Osher Ad; `mineral-water` at
    Rami Levy): unit prices that round to nothing. Rami Levy's is cause 8; Osher Ad's was not analysed. (Osher Ad's
    toilet paper is `Quantity 0.00`, a pack of unknown count: see "Unit-price outliers".)

The stress spread check (`implausible_spread`) fired on exactly this, which is what it is for. Nothing in the
index can be trusted until 8 and 9 are fixed and a reviewer has accepted the best-seller mappings (the launch
criterion in `matching.md`).

### What the script now does

`scripts/unblock/real_day.py` (tests: `scripts/unblock/tests/test_real_day.py`): a per-kind stale limit (Stores
240 h, other kinds 36 h) as in the ingestion settings; `API_RATE_LIMIT=0` for the in-process timing loops; the
promo effects per chain (the table above); for every basket line that some chain does not price, and every
line of the egg and dairy hints that some chains price and others do not, the real items behind it (attributes,
mapping, judge reason, and for eggs the size and tray count read from the name); and the per-line cost table of
the basket index with the items behind the lines that two chains price 2x apart or more. The temporary `push`
trigger that was used to run the workflow from the branch (the workflow is not on the default branch) is removed.

## SEO on real prices (2026-10-22)

The workflow's `seo` input (`scripts/unblock/seo_preview.py`, `real_day.py --seo-out`) takes the prices the real day loaded
through `smartcart-catalog export-seo`, `basket-index` and `seo-audit`, builds the static SEO pages from that export with a
placeholder origin (`https://preview.invalid`, `NEXT_PUBLIC_INDEX_UNPRICED=0`), and runs the offline structured-data
validation, the SEO unit tests, a crawl of every generated page and a 390 px browser spec against them. The export is an
artifact (7 days), never committed; the basket index stays a draft. Method, the fixes it led to and the full table are in
`seo.md`, "SEO on real prices". Run 39804455160 (six chains, one day):

| | Production semantics | Stress |
|---|---|---|
| Pages generated | 200 (70 category, 130 product) | 200 |
| Canonicals priced / unpriced | 190 / 55 | 237 / 8 |
| Product pages priced / unpriced | 107 / 23 | 128 / 2 |
| Price rows kept off the pages as implausible | 41 rows (14 chain entries on 8 products) | 37 (14 on 10) |
| Structured-data errors (121 tests, every page's JSON-LD) | 0 | 0 |
| Crawl of all 203 pages | 0 failed of 1,870 checks | 0 of 1,891 |
| Basket index | draft, no chain prices all 25 lines, `line_outlier` x2 | draft, 5 chains rank, spread 226.8%, `line_outlier` x2 |

What the real prices did to the pages: unit prices that cannot be true (toilet paper 24 rolls at 813.60 against 20.93, mineral
water at 6.8 times, garbage bags and paper towels at 9.90 against 1 to 2, sunflower oil 10.90 per 100 ml) reach
`effective_prices` and so would have reached public pages; the export now withholds them (it does not correct them: the
unit-price work is the precompute's) and the basket index names the line (`line_outlier`). Toilet paper (24 rolls) is the pack-count problem of finding 9 again, still present in this run's prices; mineral water is
not analysed here (Osher Ad's unit price is 6 times the others'). **Both were analysed and the unit-price ones fixed
the same day: "Unit-price outliers", below.**

## Unit-price outliers (2026-10-22)

The five outliers of run 39804455160 (the export withheld them; the prices were still in `effective_prices`) were taken
apart on the real rows. The Real day workflow was run from the branch three times (39812688285 to dump the rows,
39819821065 and 39827158427 on the fixed code; GitHub-hosted runner, the same six chains, one day each; the Rami Levy
store the run happened to download differs between runs, so numbers differ a little for reasons that are not the fix).
Every row below is committed verbatim in `services/api/tests/real_unit_rows.py` (48 rows, the file name says the store)
and each case is a test (`services/api/tests/test_unit_outliers_real.py`, 68 tests: the chain's adapter parses the row,
the loader's `resolve_unit_price` stores it, the precompute reads it for its canonical). The loader was **not** the
cause in any of the five: it divides the price by the size the file states, and each file states something the
loader cannot know to be wrong (`adapters.md`, "What the real day's rows showed the loader cannot know").

| Outlier | The real rows (verbatim fields) | Root cause | Fix | Before, after (per unit; the basket line) |
|---|---|---|---|---|
| **Toilet paper**, Shufersal 813.60 against 20.93 | Shufersal `נייר טואלט מולט 32 גליל`: `UnitQty` `מטרים`, `Quantity` 528.00, `UnitOfMeasure` `מטרים`, `ItemPrice` 33.90, `UnitOfMeasurePrice` 0.06 (per metre). Also `…פסטל32גל`, `…"יש" 48גלילים`, Tiv Taam `…סילק  32 גל`, Yohananof `…מולט 30 ג`. King Store (right): `32 גלילים`, `Quantity` 32 `יחידות` | The chain publishes the paper's **length**, so the fields give no count and the loader has no unit price (correct); the count is only in the name, in words `normalize` did not read (singular `גליל`, `32גל`, one-letter `30 ג`). The count was then "unknown" and the shelf price became the price of **one roll**: 24 x 33.90 = 813.60. The same rows at Osher Ad (`Quantity 0.00`, `חתוך הנמל`, no count anywhere) and Yohananof (`עבים במיו`) were priced 16.90 and 19.90 a roll | `normalize` reads `גליל`, `32גל`, `ג` on toilet paper and paper towels (not wet wipes); a per-unit canonical sold in packs (typical 6 or more) gives an item that states no count **no unit price** (`count_unknown`) | Shufersal 33.90 to **1.0594**; Rami Levy 24.90 / 37.90 to 1.1844 or none; Osher Ad 16.90 and Yohananof 19.90 to **none**. The 24-roll line: Shufersal 813.60 to **25.43**, Rami Levy 597.60 to **28.43**, Osher Ad 405.60 and Yohananof 420.00 to **unpriced**, King Store 20.93 and Tiv Taam 24.67 unchanged |
| **Paper towels and garbage bags** at 9.90 against 1 to 2 | Yohananof `מגבות נייר דו שכבתי`: `מטרים` 63.48, 9.90, no count; `מגבות נייר שישיה סוש`: 9.90, `שישיה`. Osher Ad `שקיות אשפה סקיי עם י`: `Quantity 0.00` `יחידה`, 9.90. Rami Levy `שקיות אשפה 75*90 50`: `Quantity 1.00`, 19.00. Tiv Taam `פלי 12 שקיות אשפה ריחניות 35 ל`: `Quantity 1.00` `יחידות`, UoMPrice 9.90 (a roll of 12) | The same: a count that is missing (Osher Ad `0.00`, `מטרים`), written `שישיה` (one yod), or only in the name of a chain that cuts names at 20 characters. The effective rows of the run: Osher Ad `שקיות אשפה סקיי עם י` 9.90, `שקיות אשפה עם ידיות` 9.90 and 10.00, Yohananof `מגבות נייר דו שכבתי` and `ניקול שיש` 9.90, Osher Ad `מגבות נייר סנו סושי` 17.90, each as the price of one roll or bag | `שישיה`, `שישית` read as 6; no count: no unit price. (The Tiv Taam row above was already read as 12 from the name: 0.825; the Tiv Taam 9.90 of the export's withheld list was not found among the rows dumped) | Those seven effective rows to **none**; Yohananof `שישיה סוש` 9.90 to **1.65**; Rami Levy `75*90 50` to **none** (it was 19.00 a bag). Counted bags at the chains: 0.10 to 1.3 a bag, towels 1.5 to 4.0 a roll, unchanged |
| **Mineral water**, Osher Ad 6.8 times | Osher Ad `מארז מים מינרלים מוג`: `Quantity` 1.32 `ליטר`, 14.90, UoMPrice 11.29 (a liter) | **Not a unit-price error.** It is 4 x 330 ml of sparkling water at 14.90: 1.1288 per 100 ml, what the chain itself publishes. The basket line asks for 6 liters of the cheapest mineral water, and in the stores that run downloaded this is the only one Osher Ad has mapped | None in the unit price (nothing is wrong with it). The export still withholds it and the basket index still says `line_outlier` (that is the check doing its job): the fix is in matching (carbonated and bottle size are not critical attributes of `mineral-water`) | unchanged 1.1288 per 100 ml, line 67.73 against 9.94. **Open** |
| **Sunflower oil**, Tiv Taam 10.90 per 100 ml | Tiv Taam `שמן חמניות 1 ליטר`: `UnitQty` `מיליליטר`, **`Quantity` 100.00**, `UnitOfMeasure` `100 מיליליטר`, 10.90, UoMPrice 10.90. The same barcode at Rami Levy and Osher Ad: `Quantity 1.00` `ליטר`, 9.90 | The chain's file says 100 ml for a 1 liter bottle (a decimal slip); the loader computed 10.90 per 100 ml from it and the chain's published 10.90 agrees, so two readings of one wrong number. The old "dearest reading wins" kept it | Chain size 10, 100 or 1000 times smaller than the name's explicit size: the name's size (`measure_name_over_chain`) | **1.09** (the others 0.70 to 1.49 per 100 ml). 8 more such rows in the stress variant, all with the name right: quinoa 1 kg at 3790 per 100 g, oat drink 1 L at 1590, burger 1 kg at 83.90, shower gel, chocolate, fabric softener |
| **Soda water**, Rami Levy 0.03 per 100 ml | Rami Levy `סודה מי עדן 1.5 לי` (cut): `Quantity` **9.00** `ליטר`, 2.70, UoMPrice 0.30 | The file gives a six-pack's 9 liters for one 1.5 liter bottle; 2.70 / 9 L is 0.03 per 100 ml, the chain's own published 0.30 a liter | The name says 1.5 liters (0.18) and `normalize` now reads the cut `לי`; a chain's size 6 times the name's is **ambiguous**: it is also what a name that left out the six-pack looks like (`מי עדן סודה 500מל שי`, 3000 ml, right at 0.46). Two readings far apart that no rule can tell apart give **no unit price** (`measure_unknown`) | 0.03 to **none**. The other soda rows are unchanged (0.19 to 0.64) |

**What changed in the code.** `precompute.read_unit` / `read_unit_price` (new `Unreadable`, `typical_pack`, `MULTIPACK_MIN`
= 6, `CONFLICT_MAX_RATIO` = 3, `_resolve_measure`; docs/optimizer.md "Packs" and matching.md have the rules),
`item_options` and `_chain_rows` pass the canonical's typical pack (the live `/compare` and barcode paths look it up),
`normalize.py` (words listed above; the gold-set evaluation is unchanged: Hebrew any brand 1.0000 precision / 0.8125 recall,
close 1.0000 / 0.7611, exact 1.0000 / 1.0000; Arabic any brand 1.0000 / 0.9391). The loader is unchanged.

**Before and after on the real day** (run 39804455160, commit `32f596f`, against run 39819821065 on the fixed code,
six chains):

| | Before | After |
|---|---|---|
| SEO export, production semantics: price rows withheld as implausible | 41 rows, 14 chain entries on 8 products | **11 rows, 4 entries on 4 products** (`mineral-water`, `salt`, `soup-powder-chicken`, `rice-brown`) |
| SEO export, stress | 37 rows, 14 entries on 10 products | **17 rows, 8 entries on 7 products** |
| Basket index, production semantics | draft, `line_outlier` x2 (`toilet-paper` 38.9x, `mineral-water` 6.8x) | draft, `line_outlier` x1 (`mineral-water`); toilet paper 25.43 / 20.93 / 28.43 / 24.67 |
| Basket index, stress | 5 chains rank, **`implausible_spread` 226.8 %**, `line_outlier` x2 | 3 chains rank (Rami Levy 275.55, Shufersal 343.89, Tiv Taam 346.36), **spread 25.7 %**, `line_outlier` x1 (`chicken-breast-fresh`, 4.5x, already there before and **not analysed**) |
| Precompute, production: items priced / rows | 4,923 / 6,792 | 4,726 / 6,682 |
| Precompute notes, production | `count_from_name` 122, `count_conflict` 2, `measure_conflict` 16 | `count_from_name` 135, `count_conflict` 2, **`count_unknown` 201**, `measure_conflict` 8, `measure_unknown` 5, `measure_name_over_chain` 1 |
| Precompute notes, stress | `count_from_name` 409, `count_conflict` 24, `measure_conflict` 172 | `count_from_name` 427, `count_conflict` 25, **`count_unknown` 400**, `measure_conflict` 93, `measure_unknown` 64, `measure_name_over_chain` 8, `measure_outvoted` 1 |

**What the precision costs** (recall; measured on the stress variant's 18.3 thousand priced items, run 39827158427 dumped
every note): 400 items (2 %; 201 of 4.9 thousand, 4 %, in the production variant) have no unit price because no
reading states a count, by the canonical's typical pack: 98 at 72 (wet wipes), 68 at 30 (garbage bags), 65 at 32 (toilet
paper), 63 at 100 (tea bags, disposable cups), 59 at 6 (paper towels, bread rolls), 29 at 10 (pitas), 19 at 40
(dishwasher tablets). 126 of them have a digit in the name that no rule reads (`XPO32`,
`48XPO`, `L+שרוך100`, `6*72`, `56*4`, bare `10` after `פיתות`); they are candidates for more name rules, one at a
time, each with its real names. 64 items have two sizes that cannot be told apart. By my reading of the names (an estimate,
not verified with the chains) about 50 of those are packs whose name leaves out a word the normalizer does not read
(`רביעיה`, `רבעיית`, `תריסר`, `12 בקבוקים`, `6 פחיות *330 מ"ל`) and the chain's size is right, and about a dozen have the
name right and the chain wrong (`סודה מי עדן 1.5 לי` at 3.20, `מיץ תפוזים סחוט 2 ל`). The 8 decimal slips and the one
two-against-one vote were all right on reading the names. A price of an item that is left out is not a wrong price:
the canonical is priced by the other items of the chain, or at the next store.

**Open.** (1) Osher Ad's mineral water (above): carbonation and bottle size at `mineral-water`, which is matching.
(2) Toilet paper at `close` still holds wet toilet paper (`נייר טואלט לח`, 0.07 per sheet: `toilet-paper` per roll), which
the export does not show but a stress basket at `close` could; matching again. (3) `chicken-breast-fresh` 39.90 against
8.90 per kg in the stress basket index: not analysed. (4) `unit_price_in` (the price-history series) is not given the
canonical's typical pack, so an item with an unknown count shows its shelf price there, as before. (5) The three chains
that never answered the runner (Hazi Hinam, Victory, Machsanei Hashuk) have no rows here; a chain's other quirks (a
size in metres, a quantity of 0.00) are found only on its real files.

## First run (2026-10-21), kept as history

All numbers in the sections from here to "Re-running" are from run
[39668058512](https://github.com/NoaMcDa/SmartCart/actions/runs/39668058512)
(2026-10-21, 20:49 to 21:21 UTC, commit `cc3fa98`), the richest of the runs that completed, unless another run
is named. Its report and JSON are the artifact `real-day-report`; the generated Markdown is the job summary.
Some of what it found is fixed (see "Findings of the first run: which are gone"); read it as it was on that day.

## Stage timings (first run, measured)

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

## Files and gates (first run, measured)

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

## Matching on the real items (first run, measured; precision not measured)

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

## Precompute (first run, measured)

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

## `/compare` and `/optimize` (first run, measured)

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

## Basket index on the real day (first run; #44; a dry run, not publishable)

| Variant | Chains pricing all 25 lines | Lines priced per chain | Status |
|---|---|---|---|
| Reviewed mappings only | 0 | Shufersal 17, Rami Levy 16, Mega 14, Yohananof 14, Tiv Taam 13, King Store 10, Osher Ad 8 | draft, error `too_few_chains` |
| Stress (unreviewed mappings counted) | 1 (Mega) | 20 to 25 | draft, error `too_few_chains` |

Not one ranked chain with the mappings a person would have accepted, and one in the stress variant, where the
index needs two. `eggs-l` is priced at no chain in either variant: the real egg names (for example `ביצים 2*30
יח' בינונ`) have no recognised product type (finding 5). The totals from the stress variant are not reported; they
include mappings nobody has reviewed and estimated weighed-goods prices. The index code, its checks (missing
items, estimated lines, too few chains) and the draft rule all ran on real data and behaved as designed.

## Everything the real data broke or exposed (first run)

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

## Status for the issues after the second run

- **#13 (MILP).** Ran on real prices **and real promos**: 42 solves in run 39744079077, no fallback, net saving
  equal to the heuristic's in all of them, promo bundles in the MILP's plan in 9 of 21 production and 13 of 21
  stress runs, 20 ms median (37 ms worst). The bundle logic is no longer synthetic-only; it found no extra saving
  on these baskets. Its inputs are wrong where findings 8 and 9 apply (Rami Levy's weight prices, pack counts in
  names), so the plans are not evidence about savings.
- **#44 (basket index).** Egg gap closed in matching: `eggs-l` is priced at Rami Levy (production) and at every chain
  (stress), and `too_few_chains` is gone from the stress variant (3 chains complete). Still a draft that cannot be
  published: the production variant has 0 complete chains (Rami Levy, the best, has no served mapping for hummus,
  cucumber, potato, banana, spaghetti and chocolate milk, and nobody has reviewed the egg and dairy candidates), and the stress
  variant fails `implausible_spread` (56.5 %) because of findings 8 and 9.
- **#47 (precompute).** Ran with real promos: 5,627 rows in 0.84 s at 25 stores (7 chains), 1,642 of them with a
  promo, 205 club-only rows all with a non-club fallback; no error. The pack count of a counted good is not read from
  the name (finding 9), and Rami Levy's published weight unit price is per gram (finding 8, the loader's).
  Scale (300 stores) not re-measured.
- **#60 (exit).** Findings 1 and 2, which would each have broken fourteen nightly loads, are gone on real data:
  Stores files of 50 to 59 h and 28,000 to 30,000 real promos load without a quarantine or an alert. Findings 8 and 9
  are new and of the same weight (wrong prices, not failed loads). Still NO-GO.

## Status for the issues after the first run (history)

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
