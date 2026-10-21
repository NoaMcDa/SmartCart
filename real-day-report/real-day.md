## One real day through the pipeline (dry run)

Mode `portal`, commit `986b913779d7`, runner `GitHub Actions 1000004733` (4 CPUs, Python 3.12.3, Postgres 17.11), 2026-10-21T17:44:40+00:00 to 2026-10-21T18:20:22+00:00 UTC. Measurements on one real day with hand-made baskets; the prices are real, the baskets and locations are not a sample of anything. **Not publishable.**

### Stages

| stage | seconds | result |
|---|---|---|
| download: portal probe (one Stores and one PriceFull per chain) | 583.15 | ok |
| migrate | 1.23 | 25 applied |
| ingest: Stores files (Scheduler, adapters, gates, loader, store coordinates) | 0.59 | 7 files |
| download: PriceFull and PromoFull of the stores nearest to city centres | 679.6 | 54 files, anchors: Haifa centre, Jerusalem centre, Petah Tikva |
| ingest: PriceFull and PromoFull files (Scheduler, adapters, gates, loader) | 97.81 | 61 files |
| catalog: seed | 1.1 | ok |
| catalog: normalize | 9.42 | ok |
| catalog: extract (rule) | 98.42 | ok |
| catalog: embed (hash) | 326.39 | ok |
| catalog: judge (rule) | 240.6 | ok |
| precompute effective prices (production semantics: reviewed mappings only) | 1.31 | 8220 rows |
| API: parse-list, compare, optimize (production) | 50.04 | 21 basket runs at 3 locations |
| basket index dry run (production semantics) | 0.44 | status draft |
| stress: mark the machine suggestions accepted (performance only) | 0.26 | 15588 mappings |
| precompute effective prices (stress: unreviewed mappings included) | 2.54 | 13602 rows |
| API: parse-list, compare, optimize (stress) | 47.49 | 21 basket runs at 3 locations |
| basket index dry run (stress) | 0.43 | status draft |

### Portals (the portal probe's own reachability and downloads)

| chain | reachable | login | Stores download | PriceFull download |
|---|---|---|---|---|
| hazihinam | BLOCKED? (403) | n/a | no: no file downloaded | no: no file downloaded |
| king_store | BLOCKED? (403) | n/a | Stores7290058108879-000-20261021-040448.gz | PriceFull7290058108879-000-340-20261021-040448.gz |
| machsanei_hashuk | UNREACHABLE (0) | n/a | no: no file downloaded | no: no file downloaded |
| mega | OK (200) | n/a | Stores7290055700007-000-20261021-000100.xml | PriceFull7290055700007-001-002-20261021-051019.gz |
| osherad | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290103152017-000-20261019-080501.xml | PriceFull7290103152017-001-001-20261021-080011.gz |
| ramilevy | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290058140886-000-20261019-050500.xml | PriceFull7290058140886-001-001-20261021-001002.gz |
| shufersal | OK (200) | n/a | Stores7290027600007-000-20261021-020.gz | PriceFull7290027600007-001-036-20261021-043100.gz |
| tivtaam | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290873255550-000-20261019-050501.xml | PriceFull7290873255550-000-002-20261021-004004.gz |
| victory | UNREACHABLE (0) | n/a | no: no file downloaded | no: no file downloaded |
| yohananof | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290803800003-000-20261019-010000.xml | PriceFull7290803800003-000-001-20261021-004031.gz |

### Files, gates and rows per chain

| chain | kind | file | published (Israel) | age h | schema | gate result | rows | seconds |
|---|---|---|---|---|---|---|---|---|
| king_store | stores | `Stores7290058108879-000-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 16.8 | v1 | loaded | 48 | 0.07 |
| mega | stores | `Stores7290055700007-000-20261021-000100.xml` | 2026-10-21T00:01+03:00 | 20.9 | v1 | loaded | 147 | 0.08 |
| osherad | stores | `Stores7290103152017-000-20261019-080501.xml` | 2026-10-19T08:05+03:00 | 60.8 (stale on the real clock) | v1 | loaded | 24 | 0.05 |
| ramilevy | stores | `Stores7290058140886-000-20261019-050500.xml` | 2026-10-19T05:05+03:00 | 63.8 (stale on the real clock) | v1 | loaded | 99 | 0.06 |
| shufersal | stores | `Stores7290027600007-000-20261021-020.gz` | 2026-10-21T02:00+03:00 | 18.9 | v1 | loaded | 417 | 0.21 |
| tivtaam | stores | `Stores7290873255550-000-20261019-050501.xml` | 2026-10-19T05:05+03:00 | 63.8 (stale on the real clock) | v1 | loaded | 54 | 0.04 |
| yohananof | stores | `Stores7290803800003-000-20261019-010000.xml` | 2026-10-19T01:00+03:00 | 67.9 (stale on the real clock) | v1 | loaded | 51 | 0.03 |
| king_store | price_full | `PriceFull7290058108879-000-340-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 17.0 | v1 | loaded | 2,336 | 0.47 |
| mega | price_full | `PriceFull7290055700007-001-002-20261021-051019.gz` | 2026-10-21T05:10+03:00 | 15.9 | v1 | loaded | 5,899 | 1.33 |
| osherad | price_full | `PriceFull7290103152017-001-001-20261021-080011.gz` | 2026-10-21T08:00+03:00 | 13.1 | v1 | loaded | 6,508 | 1.25 |
| ramilevy | price_full | `PriceFull7290058140886-001-001-20261021-001002.gz` | 2026-10-21T00:10+03:00 | 20.9 | v1 | loaded | 12,976 | 2.53 |
| shufersal | price_full | `PriceFull7290027600007-001-036-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 16.6 | v1 | loaded | 5,808 | 1.1 |
| tivtaam | price_full | `PriceFull7290873255550-000-002-20261021-004004.gz` | 2026-10-21T00:40+03:00 | 20.4 | v1 | loaded | 21,598 | 4.62 |
| yohananof | price_full | `PriceFull7290803800003-000-001-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 20.4 | v1 | loaded | 10,732 | 2.4 |
| king_store | price_full | `PriceFull7290058108879-000-014-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 17.0 | v1 | loaded | 4,833 | 1.02 |
| king_store | price_full | `PriceFull7290058108879-000-200-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 17.0 | v1 | loaded | 3,628 | 0.81 |
| king_store | promo_full | `PromoFull7290058108879-000-014-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 17.0 | v1 | loaded | 430 | 0.13 |
| king_store | promo_full | `PromoFull7290058108879-000-200-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 17.0 | v1 | loaded | 313 | 0.09 |
| mega | price_full | `PriceFull7290055700007-001-091-20261021-051007.gz` | 2026-10-21T05:10+03:00 | 15.9 | v1 | loaded | 6,825 | 1.49 |
| mega | price_full | `PriceFull7290055700007-001-418-20261021-051008.gz` | 2026-10-21T05:10+03:00 | 15.9 | v1 | loaded | 5,782 | 1.16 |
| mega | price_full | `PriceFull7290055700007-001-452-20261021-051010.gz` | 2026-10-21T05:10+03:00 | 15.9 | v1 | loaded | 8,176 | 1.63 |
| mega | price_full | `PriceFull7290055700007-001-457-20261021-051015.gz` | 2026-10-21T05:10+03:00 | 15.9 | v1 | loaded | 9,248 | 1.84 |
| mega | price_full | `PriceFull7290055700007-001-407-20261021-051019.gz` | 2026-10-21T05:10+03:00 | 15.9 | v1 | loaded | 8,576 | 1.77 |
| mega | price_full | `PriceFull7290055700007-001-470-20261021-064437.gz` | 2026-10-21T06:44+03:00 | 14.4 | v1 | loaded | 4,836 | 0.99 |
| mega | promo_full | `PromoFull7290055700007-001-418-20261021-051058.gz` | 2026-10-21T05:10+03:00 | 15.9 | v1 | loaded | 1,445 | 0.47 |
| mega | promo_full | `PromoFull7290055700007-001-091-20261021-051103.gz` | 2026-10-21T05:11+03:00 | 15.9 | v1 | loaded | 1,530 | 0.51 |
| mega | promo_full | `PromoFull7290055700007-001-452-20261021-051116.gz` | 2026-10-21T05:11+03:00 | 15.9 | v1 | loaded | 1,518 | 0.49 |
| mega | promo_full | `PromoFull7290055700007-001-407-20261021-051125.gz` | 2026-10-21T05:11+03:00 | 15.9 | v1 | loaded | 1,465 | 0.44 |
| mega | promo_full | `PromoFull7290055700007-001-457-20261021-051126.gz` | 2026-10-21T05:11+03:00 | 15.9 | v1 | loaded | 1,437 | 0.44 |
| mega | promo_full | `PromoFull7290055700007-001-470-20261021-064509.gz` | 2026-10-21T06:45+03:00 | 14.4 | v1 | loaded | 1,433 | 0.5 |
| osherad | price_full | `PriceFull7290103152017-001-026-20261021-140501.gz` | 2026-10-21T14:05+03:00 | 7.0 | v1 | loaded | 6,836 | 1.36 |
| osherad | price_full | `PriceFull7290103152017-001-030-20261021-140501.gz` | 2026-10-21T14:05+03:00 | 7.0 | v1 | loaded | 6,465 | 1.3 |
| osherad | price_full | `PriceFull7290103152017-001-010-20261021-140502.gz` | 2026-10-21T14:05+03:00 | 7.0 | v1 | loaded | 6,699 | 1.41 |
| osherad | price_full | `PriceFull7290103152017-001-028-20261021-140502.gz` | 2026-10-21T14:05+03:00 | 7.0 | v1 | loaded | 6,246 | 1.25 |
| osherad | promo_full | `PromoFull7290103152017-001-028-20261021-140522.gz` | 2026-10-21T14:05+03:00 | 7.0 | v1 | loaded | 716 | 0.21 |
| osherad | promo_full | `PromoFull7290103152017-001-026-20261021-140527.gz` | 2026-10-21T14:05+03:00 | 7.0 | v1 | loaded | 734 | 0.22 |
| osherad | promo_full | `PromoFull7290103152017-001-030-20261021-140545.gz` | 2026-10-21T14:05+03:00 | 7.0 | v1 | loaded | 750 | 0.24 |
| osherad | promo_full | `PromoFull7290103152017-001-010-20261021-140558.gz` | 2026-10-21T14:05+03:00 | 7.0 | v1 | loaded | 705 | 0.24 |
| ramilevy | price_full | `PriceFull7290058140886-001-062-20261021-120007.gz` | 2026-10-21T12:00+03:00 | 9.1 | v1 | loaded | 14,121 | 2.88 |
| ramilevy | price_full | `PriceFull7290058140886-001-703-20261021-120007.gz` | 2026-10-21T12:00+03:00 | 9.1 | v1 | loaded | 4,955 | 0.99 |
| ramilevy | price_full | `PriceFull7290058140886-001-048-20261021-120011.gz` | 2026-10-21T12:00+03:00 | 9.1 | v1 | loaded | 14,448 | 2.9 |
| ramilevy | price_full | `PriceFull7290058140886-001-057-20261021-121509.gz` | 2026-10-21T12:15+03:00 | 8.9 | v1 | loaded | 13,927 | 2.84 |
| ramilevy | price_full | `PriceFull7290058140886-001-724-20261021-180005.gz` | 2026-10-21T18:00+03:00 | 3.1 | v1 | loaded | 5,164 | 1.04 |
| ramilevy | price_full | `PriceFull7290058140886-001-725-20261021-180015.gz` | 2026-10-21T18:00+03:00 | 3.1 | v1 | loaded | 4,119 | 0.84 |
| ramilevy | promo_full | `PromoFull7290058140886-001-703-20261021-120038.gz` | 2026-10-21T12:00+03:00 | 9.1 | v1 | loaded | 1,108 | 0.37 |
| ramilevy | promo_full | `PromoFull7290058140886-001-048-20261021-120055.gz` | 2026-10-21T12:00+03:00 | 9.1 | v1 | loaded | 2,525 | 0.94 |
| ramilevy | promo_full | `PromoFull7290058140886-001-062-20261021-120113.gz` | 2026-10-21T12:01+03:00 | 9.1 | v1 | loaded | 2,532 | 1.03 |
| ramilevy | promo_full | `PromoFull7290058140886-001-057-20261021-121655.gz` | 2026-10-21T12:16+03:00 | 8.8 | v1 | loaded | 2,532 | 0.94 |
| ramilevy | promo_full | `PromoFull7290058140886-001-724-20261021-180029.gz` | 2026-10-21T18:00+03:00 | 3.1 | v1 | loaded | 1,060 | 0.34 |
| ramilevy | promo_full | `PromoFull7290058140886-001-725-20261021-180038.gz` | 2026-10-21T18:00+03:00 | 3.1 | v1 | loaded | 1,047 | 0.35 |
| shufersal | price_full | `PriceFull7290027600007-001-002-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 16.6 | v1 | loaded | 7,488 | 1.47 |
| shufersal | price_full | `PriceFull7290027600007-001-302-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 16.6 | v1 | loaded | 6,534 | 1.28 |
| shufersal | price_full | `PriceFull7290027600007-006-300-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 16.6 | v1 | loaded | 7,723 | 1.57 |
| shufersal | price_full | `PriceFull7290027600007-007-285-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 16.6 | v1 | loaded | 3,328 | 0.72 |
| shufersal | price_full | `PriceFull7290027600007-007-353-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 16.6 | v1 | loaded | 2,271 | 0.49 |
| shufersal | price_full | `PriceFull7290027600007-018-753-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 16.6 | v1 | loaded | 3,547 | 0.72 |
| tivtaam | price_full | `PriceFull7290873255550-000-012-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 5.5 | v1 | loaded | 17,832 | 3.65 |
| tivtaam | price_full | `PriceFull7290873255550-000-085-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 5.6 | v1 | loaded | 7,171 | 1.48 |
| tivtaam | price_full | `PriceFull7290873255550-000-087-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 5.6 | v1 | loaded | 6,069 | 1.2 |
| tivtaam | price_full | `PriceFull7290873255550-000-092-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 5.6 | v1 | loaded | 5,851 | 1.21 |
| tivtaam | promo_full | `PromoFull7290873255550-000-012-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 5.6 | v1 | loaded | 2,040 | 1.62 |
| tivtaam | promo_full | `PromoFull7290873255550-000-085-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 5.6 | v1 | loaded | 1,282 | 1.95 |
| tivtaam | promo_full | `PromoFull7290873255550-000-087-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 5.6 | v1 | loaded | 1,126 | 1.15 |
| tivtaam | promo_full | `PromoFull7290873255550-000-092-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 5.6 | v1 | loaded | 1,060 | 0.88 |
| yohananof | price_full | `PriceFull7290803800003-000-020-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 20.4 | v1 | loaded | 11,887 | 2.44 |
| yohananof | price_full | `PriceFull7290803800003-000-021-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 20.4 | v1 | loaded | 11,197 | 2.25 |
| yohananof | promo_full | `PromoFull7290803800003-000-020-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 20.4 | v1 | loaded | 1,277 | 0.38 |
| yohananof | promo_full | `PromoFull7290803800003-000-021-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 20.4 | v1 | loaded | 1,212 | 0.37 |

`file_tracking` after the run: {'loaded': 68}. Alerts raised: 0.

| chain | physical stores | located | online | items | price events | stores with prices | promos | promo items |
|---|---|---|---|---|---|---|---|---|
| king_store | 48 | 28 | - | 6,748 | 10,797 | 3 | 743 | - |
| mega | 147 | 144 | 3 | 13,519 | 49,342 | 7 | 8,828 | - |
| osherad | 24 | 24 | - | 8,715 | 32,754 | 5 | 2,905 | - |
| ramilevy | 98 | 96 | 1 | 18,422 | 69,710 | 7 | 10,804 | - |
| shufersal | 416 | 411 | 1 | 13,613 | 36,699 | 7 | - | - |
| tivtaam | 47 | 47 | 7 | 24,986 | 58,521 | 5 | 5,508 | - |
| yohananof | 50 | 19 | 1 | 13,572 | 33,816 | 3 | 2,489 | - |

Extra downloads (the stores nearest to these city centres, for the optimizer):

- Haifa centre: 6 chains and 39 located stores within 4 km; asked for shufersal 302,353, mega 470,418, king_store 14, ramilevy 57,62, osherad 30, tivtaam 92,12
- Jerusalem centre: 6 chains and 36 located stores within 4 km; asked for shufersal 2,753, mega 457,91, king_store 200, ramilevy 48,703, osherad 26,28, yohananof 20
- Petah Tikva: 6 chains and 36 located stores within 4 km; asked for shufersal 285,300, mega 407,452, ramilevy 725,724, osherad 10, yohananof 21, tivtaam 87,85
- download `shufersal` promo_full: timed out after 240s

### Matching on the real items

99,575 items; 21,514 mapped to a canonical (any level, including the review queue); 5,926 served (no review flag), onto 210 canonicals.

| level | mappings served | mappings in the review queue |
|---|---|---|
| exact | 0 | 0 |
| any_brand | 3,608 | 6,475 |
| close | 2,318 | 9,113 |

| chain | items | mapped | served |
|---|---|---|---|
| shufersal | 13,613 | 3,269 | 947 |
| mega | 13,519 | 2,939 | 1,010 |
| king_store | 6,748 | 1,844 | 324 |
| ramilevy | 18,422 | 3,895 | 1,350 |
| osherad | 8,715 | 2,163 | 690 |
| yohananof | 13,572 | 2,621 | 916 |
| tivtaam | 24,986 | 4,783 | 689 |

- seed: 1.1 s
- normalize: 9.42 s
- extract (rule): 98.42 s
- embed (hash): 326.39 s
- judge (rule): 240.6 s

### Precompute (production semantics)

8,220 rows written in 0.914 s of job time (1.29 s wall including start-up); 5,709 items priced at 37 stores (843 stores of 7 chains considered); 0 rows with a promo, 0 club-only. Canonicals with a real price: 209, of them 191 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 3,610 | 193 | 37 |
| close | 4,610 | 209 | 37 |

### Precompute (stress)

13,602 rows written in 2.15 s of job time (2.51 s wall including start-up); 20,550 items priced at 37 stores (843 stores of 7 chains considered); 0 rows with a promo, 0 club-only. Canonicals with a real price: 241, of them 236 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 6,178 | 237 | 37 |
| close | 7,424 | 241 | 37 |

### /parse-list, /compare and /optimize (production semantics)

Locations: Jerusalem centre (10 priced stores, 6 chains within 5 km); Haifa centre (8 priced stores, 5 chains within 5 km); Petah Tikva (8 priced stores, 5 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 4816.8 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 13559.4 |
| large (32 lines) | 33 | 33 | 5 | 0 | 25387.6 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 10 | 0 | 8.6 | 7.6 | 12.8 | 55 | single: רמי לוי עטרות | 5.73 / 5.73 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 10 | 0 | 11 | 11.8 | 14.6 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 33 | 10 | 0 | 14.3 | 11.2 | 17.9 | 55 | single: רמי לוי עטרות | 86.8 / 86.8 |
| Jerusalem centre | drawn: 5 | 5 | 10 | 6 | 8.4 | 7 | 12.5 | 55 | single: קרפור (מגה) קרפור מרקט ריינס | 5.07 / 5.07 |
| Jerusalem centre | drawn: 10 | 10 | 10 | 0 | 8.9 | 7.7 | 13.2 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | drawn: 20 | 20 | 10 | 0 | 11.3 | 8.9 | 15.5 | 55 | single: רמי לוי עטרות | 66.97 / 66.97 |
| Jerusalem centre | drawn: 40 | 40 | 10 | 0 | 16.8 | 13.9 | 20.2 | 55 | single: רמי לוי עטרות | 203.37 / 203.37 |
| Haifa centre | hand: small (6 lines) | 6 | 8 | 0 | 6.8 | 6 | 10.9 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | hand: weekly (17 lines) | 17 | 8 | 0 | 9.6 | 7.7 | 12.6 | 55 | single: שופרסל שלי חיפה- קלר | -11.87 / -11.87 |
| Haifa centre | hand: large (32 lines) | 33 | 8 | 0 | 12.3 | 8.9 | 14.4 | 55 | single: שופרסל שלי חיפה- קלר | -18.47 / -18.47 |
| Haifa centre | drawn: 5 | 5 | 8 | 2 | 7.1 | 6.5 | 11.2 | 55 | single: שופרסל שלי חיפה- קלר | 4.63 / 4.63 |
| Haifa centre | drawn: 10 | 10 | 8 | 0 | 8.4 | 6.9 | 11.7 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | drawn: 20 | 20 | 8 | 0 | 10.3 | 8.1 | 14.7 | 55 | single: שופרסל שלי חיפה- קלר | -5.17 / -5.17 |
| Haifa centre | drawn: 40 | 40 | 8 | 0 | 16.6 | 9.8 | 16.1 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Petah Tikva | hand: small (6 lines) | 6 | 8 | 0 | 7.8 | 6.8 | 12.4 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 17.64 / 17.64 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 8 | 0 | 10.3 | 8.8 | 15.3 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 17.04 / 17.04 |
| Petah Tikva | hand: large (32 lines) | 33 | 8 | 0 | 14.2 | 11.2 | 16.9 | 55 | single: שופרסל אקספרס סוקולוב פ"ת | -53.62 / -53.62 |
| Petah Tikva | drawn: 5 | 5 | 8 | 2 | 7.8 | 7 | 11.9 | 55 | single: רמי לוי שטמפפר פתח תקווה | 0.0 / 0.0 |
| Petah Tikva | drawn: 10 | 10 | 8 | 0 | 8.5 | 7.2 | 12.8 | 55 | single: רמי לוי שטמפפר פתח תקווה | 0.0 / 0.0 |
| Petah Tikva | drawn: 20 | 20 | 8 | 0 | 11.3 | 9 | 14.7 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 101.96 / 101.96 |
| Petah Tikva | drawn: 40 | 40 | 8 | 0 | 15.2 | 12.3 | 19.9 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 54.86 / 54.86 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 7.8 | 6.8 | 12.4 |
| hand: weekly (17 lines) | 10.3 | 8.8 | 14.6 |
| hand: large (32 lines) | 14.2 | 11.2 | 16.9 |
| drawn: 5 | 7.8 | 7.0 | 11.9 |
| drawn: 10 | 8.5 | 7.2 | 12.8 |
| drawn: 20 | 11.3 | 8.9 | 14.7 |
| drawn: 40 | 16.6 | 12.3 | 19.9 |

### /parse-list, /compare and /optimize (stress: unreviewed mappings included, performance only)

Locations: Jerusalem centre (10 priced stores, 6 chains within 5 km); Haifa centre (8 priced stores, 5 chains within 5 km); Petah Tikva (8 priced stores, 5 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 4686.9 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 12990 |
| large (32 lines) | 33 | 33 | 5 | 0 | 25462.2 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 10 | 5 | 9.7 | 8.9 | 14.6 | 55 | single: רמי לוי עטרות | 57.26 / 57.26 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 10 | 0 | 13.3 | 11.2 | 17.9 | 55 | single: רמי לוי עטרות | 55.54 / 55.54 |
| Jerusalem centre | hand: large (32 lines) | 33 | 10 | 0 | 18.9 | 15 | 23 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | drawn: 5 | 5 | 10 | 4 | 9.8 | 7.4 | 12.9 | 55 | single: רמי לוי עטרות | 110.27 / 110.27 |
| Jerusalem centre | drawn: 10 | 10 | 10 | 0 | 9.6 | 8.2 | 13.9 | 55 | single: קרפור (מגה) קרפור מרקט ריינס | 8.77 / 8.77 |
| Jerusalem centre | drawn: 20 | 20 | 10 | 0 | 12.9 | 11.6 | 17.5 | 55 | single: רמי לוי עטרות | 160.67 / 160.67 |
| Jerusalem centre | drawn: 40 | 40 | 10 | 0 | 19.6 | 16 | 24.5 | 55 | single: רמי לוי עטרות | 568.67 / 568.67 |
| Haifa centre | hand: small (6 lines) | 6 | 8 | 5 | 8 | 6.7 | 11.3 | 55 | single: שופרסל שלי חיפה- קלר | -5.95 / -5.95 |
| Haifa centre | hand: weekly (17 lines) | 17 | 8 | 0 | 11.2 | 8 | 13.4 | 55 | single: שופרסל שלי חיפה- קלר | 23.67 / 23.67 |
| Haifa centre | hand: large (32 lines) | 33 | 8 | 0 | 18.2 | 12.1 | 17.1 | 55 | single: שופרסל שלי חיפה- קלר | 95.97 / 95.97 |
| Haifa centre | drawn: 5 | 5 | 8 | 3 | 7.2 | 6.3 | 11.4 | 55 | single: שופרסל שלי חיפה- קלר | 3.03 / 3.03 |
| Haifa centre | drawn: 10 | 10 | 8 | 0 | 8.6 | 7.1 | 11.9 | 55 | single: שופרסל שלי חיפה- קלר | -5.87 / -5.87 |
| Haifa centre | drawn: 20 | 20 | 8 | 1 | 12.2 | 8.8 | 15.2 | 55 | single: שופרסל שלי חיפה- קלר | 25.43 / 25.43 |
| Haifa centre | drawn: 40 | 40 | 8 | 0 | 17.7 | 10.4 | 16.3 | 55 | single: שופרסל שלי חיפה- קלר | -4.37 / -4.37 |
| Petah Tikva | hand: small (6 lines) | 6 | 8 | 6 | 8 | 6.9 | 12.5 | 55 | single: רמי לוי שטמפפר פתח תקווה | 0.0 / 0.0 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 8 | 0 | 11.3 | 9.4 | 15 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 2.01 / 2.01 |
| Petah Tikva | hand: large (32 lines) | 33 | 8 | 0 | 15.9 | 12.2 | 20 | 55 | split: רמי לוי שטמפפר פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | 14.82 / 14.82 |
| Petah Tikva | drawn: 5 | 5 | 8 | 4 | 7.8 | 7.3 | 12 | 55 | single: רמי לוי שטמפפר פתח תקווה | 0.0 / 0.0 |
| Petah Tikva | drawn: 10 | 10 | 8 | 0 | 8.6 | 7.2 | 12 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 0.16 / 0.16 |
| Petah Tikva | drawn: 20 | 20 | 8 | 0 | 11.7 | 9.5 | 15.2 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 15.86 / 15.86 |
| Petah Tikva | drawn: 40 | 40 | 8 | 0 | 17.4 | 12.9 | 19.5 | 55 | single: רמי לוי שטמפפר פתח תקווה | 0.0 / 0.0 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 8.0 | 6.9 | 12.5 |
| hand: weekly (17 lines) | 11.3 | 9.4 | 15.0 |
| hand: large (32 lines) | 18.2 | 12.2 | 20.0 |
| drawn: 5 | 7.8 | 7.3 | 12.0 |
| drawn: 10 | 8.6 | 7.2 | 12.0 |
| drawn: 20 | 12.2 | 9.5 | 15.2 |
| drawn: 40 | 17.7 | 12.9 | 19.5 |

### Basket index on the real day (#44, dry run, production semantics)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `missing_items` שופרסל has no price for 8 basket items (yellow-cheese-sliced-28, butter, eggs-l, cucumber, banana, pita, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` שופרסל: 4 lines use estimated weighed-goods prices
- warning: `missing_items` קרפור (מגה) has no price for 11 basket items (yellow-cheese-sliced-28, butter, hummus-plain, tomato, cucumber, potato, banana, pita, pasta-spaghetti, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` קרפור (מגה): 2 lines use estimated weighed-goods prices
- warning: `missing_items` קינג סטור has no price for 15 basket items (cottage-5, yellow-cheese-sliced-28, butter, eggs-l, chicken-breast-fresh, hummus-plain, tomato, cucumber, banana, bread-standard, pita, pasta-spaghetti, tuna-in-oil, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` קינג סטור: 2 lines use estimated weighed-goods prices
- warning: `missing_items` רמי לוי has no price for 9 basket items (butter, eggs-l, hummus-plain, cucumber, potato, banana, pita, pasta-spaghetti, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` רמי לוי: 3 lines use estimated weighed-goods prices
- warning: `missing_items` אושר עד has no price for 17 basket items (milk-fresh-3, white-cheese-5, yellow-cheese-sliced-28, yogurt-plain-3, eggs-l, chicken-breast-fresh, hummus-plain, tomato, cucumber, onion, banana, pita, pasta-spaghetti, sugar-white, mineral-water, bamba, chocolate-milk); it is listed but not ranked
- warning: `missing_items` יוחננוף has no price for 11 basket items (yellow-cheese-sliced-28, butter, eggs-l, hummus-plain, cucumber, potato, banana, pita, pasta-spaghetti, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` יוחננוף: 3 lines use estimated weighed-goods prices
- warning: `missing_items` טיב טעם has no price for 12 basket items (milk-fresh-3, yellow-cheese-sliced-28, yogurt-plain-3, butter, eggs-l, hummus-plain, pita, pasta-spaghetti, tuna-in-oil, mineral-water, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` טיב טעם: 6 lines use estimated weighed-goods prices
- error: `too_few_chains` only 0 chain(s) price the whole basket; at least 2 needed

Basket of 25 lines; price date 2026-10-21T15:00:15Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| שופרסל | - | 17 | 8 | 7 | no |
| קרפור (מגה) | - | 14 | 11 | 7 | no |
| קינג סטור | - | 10 | 15 | 3 | no |
| רמי לוי | - | 16 | 9 | 7 | no |
| אושר עד | - | 8 | 17 | 5 | no |
| יוחננוף | - | 14 | 11 | 3 | no |
| טיב טעם | - | 13 | 12 | 5 | no |

### Basket index on the real day (#44, dry run, stress)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `estimated_items` קרפור (מגה): 6 lines use estimated weighed-goods prices
- warning: `missing_items` שופרסל has no price for 1 basket items (eggs-l); it is listed but not ranked
- warning: `estimated_items` שופרסל: 6 lines use estimated weighed-goods prices
- warning: `missing_items` קינג סטור has no price for 3 basket items (eggs-l, bread-standard, tuna-in-oil); it is listed but not ranked
- warning: `estimated_items` קינג סטור: 6 lines use estimated weighed-goods prices
- warning: `missing_items` רמי לוי has no price for 1 basket items (eggs-l); it is listed but not ranked
- warning: `estimated_items` רמי לוי: 3 lines use estimated weighed-goods prices
- warning: `missing_items` אושר עד has no price for 5 basket items (eggs-l, chicken-breast-fresh, onion, banana, pita); it is listed but not ranked
- warning: `missing_items` יוחננוף has no price for 2 basket items (eggs-l, pita); it is listed but not ranked
- warning: `estimated_items` יוחננוף: 6 lines use estimated weighed-goods prices
- warning: `missing_items` טיב טעם has no price for 1 basket items (eggs-l); it is listed but not ranked
- warning: `estimated_items` טיב טעם: 6 lines use estimated weighed-goods prices
- error: `too_few_chains` only 1 chain(s) price the whole basket; at least 2 needed

Basket of 25 lines; price date 2026-10-21T15:00:15Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| קרפור (מגה) | 348.36 | 25 | 0 | 7 | yes |
| שופרסל | - | 24 | 1 | 7 | no |
| קינג סטור | - | 22 | 3 | 3 | no |
| רמי לוי | - | 24 | 1 | 7 | no |
| אושר עד | - | 20 | 5 | 5 | no |
| יוחננוף | - | 23 | 2 | 3 | no |
| טיב טעם | - | 24 | 1 | 5 | no |

### Failures and findings the run recorded (1)

- **download**: shufersal promo_full: timed out after 240s

