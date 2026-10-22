## One real day through the pipeline (dry run)

Mode `portal`, commit `1efc32115a64`, runner `GitHub Actions 1000005404` (4 CPUs, Python 3.12.3, Postgres 17.11), 2026-10-22T17:07:30+00:00 to 2026-10-22T17:52:45+00:00 UTC. Measurements on one real day with hand-made baskets; the prices are real, the baskets and locations are not a sample of anything. **Not publishable.**

### Stages

| stage | seconds | result |
|---|---|---|
| download: portal probe (one Stores and one PriceFull per chain) | 1357.53 | ok |
| migrate | 1.26 | 34 applied |
| ingest: Stores files (Scheduler, adapters, gates, loader, store coordinates) | 0.49 | 6 files |
| download: PriceFull and PromoFull of the stores nearest to city centres | 487.57 | 48 files, anchors: Haifa centre, Jerusalem centre, Petah Tikva |
| ingest: PriceFull and PromoFull files (Scheduler, adapters, gates, loader) | 226.29 | 60 files |
| catalog: seed | 1.12 | ok |
| catalog: normalize | 12.56 | ok |
| catalog: extract (rule) | 97.8 | ok |
| catalog: embed (hash) | 275.02 | ok |
| catalog: judge (rule) | 209.09 | ok |
| precompute effective prices (production semantics: reviewed mappings only) | 4.21 | 6682 rows |
| API: parse-list, compare, optimize (production) | 12.24 | 21 basket runs at 3 locations |
| diagnostic: the vector query behind /parse-list and /search | 0.34 | [3.6, 1.0, 0.9] ms per query |
| basket index dry run (production semantics) | 0.49 | status draft |
| SEO export and basket index on real prices (production semantics) | 0.94 | 200 pages, 191 of 245 canonicals priced, 0 error findings |
| diagnostic: real items behind the basket lines no chain prices | 1.74 | butter 60 items, chocolate-milk 72 items, cottage-5 7 items, eggs-l 159 items, milk-fresh-3 24 items, white-cheese-5 12 items, yellow-cheese-sliced-28 60 items, yogurt-plain-3 24 items |
| stress: mark the machine suggestions accepted (performance only) | 0.24 | 14111 mappings |
| precompute effective prices (stress: unreviewed mappings included) | 12.5 | 11055 rows |
| API: parse-list, compare, optimize (stress) | 11.38 | 21 basket runs at 3 locations |
| basket index dry run (stress) | 0.52 | status draft |
| SEO export and basket index on real prices (stress) | 0.98 | 200 pages, 237 of 245 canonicals priced, 0 error findings |

### Portals (the portal probe's own reachability and downloads)

| chain | reachable | login | Stores download | PriceFull download |
|---|---|---|---|---|
| king_store | BLOCKED? (403) | n/a | Stores7290058108879-000-20261022-051042.gz | PriceFull7290058108879-000-031-20261022-051042.gz |
| mega | UNREACHABLE (0) | n/a | no: timed out after 300s | no: timed out after 300s |
| osherad | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290103152017-000-20261020-080500.xml | PriceFull7290103152017-001-003-20261022-080001.gz |
| ramilevy | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290058140886-000-20261020-050500.xml | PriceFull7290058140886-001-003-20261022-001017.gz |
| shufersal | OK (200) | n/a | Stores7290027600007-000-20261022-020.gz | PriceFull7290027600007-001-002-20261022-030000.gz |
| tivtaam | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290873255550-000-20261020-050500.xml | PriceFull7290873255550-000-014-20261022-004004.gz |
| yohananof | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290803800003-000-20261020-010000.xml | PriceFull7290803800003-000-005-20261022-004040.gz |

### Files, gates and rows per chain

| chain | kind | file | published (Israel) | age h | schema | gate result | rows | seconds |
|---|---|---|---|---|---|---|---|---|
| king_store | stores | `Stores7290058108879-000-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 15.3 | v1 | loaded | 48 | 0.07 |
| osherad | stores | `Stores7290103152017-000-20261020-080500.xml` | 2026-10-20T08:05+03:00 | 60.4 | v1 | loaded | 24 | 0.03 |
| ramilevy | stores | `Stores7290058140886-000-20261020-050500.xml` | 2026-10-20T05:05+03:00 | 63.4 | v1 | loaded | 99 | 0.07 |
| shufersal | stores | `Stores7290027600007-000-20261022-020.gz` | 2026-10-22T02:00+03:00 | 18.5 | v1 | loaded | 417 | 0.21 |
| tivtaam | stores | `Stores7290873255550-000-20261020-050500.xml` | 2026-10-20T05:05+03:00 | 63.4 | v1 | loaded | 54 | 0.04 |
| yohananof | stores | `Stores7290803800003-000-20261020-010000.xml` | 2026-10-20T01:00+03:00 | 67.5 | v1 | loaded | 51 | 0.03 |
| king_store | price_full | `PriceFull7290058108879-000-031-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 15.5 | v1 | loaded | 5,991 | 1.31 |
| king_store | promo_full | `PromoFull7290058108879-000-031-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 15.5 | v1 | loaded | 507 | 0.3 |
| osherad | price_full | `PriceFull7290103152017-001-003-20261022-080001.gz` | 2026-10-22T08:00+03:00 | 12.6 | v1 | loaded | 6,741 | 1.31 |
| osherad | promo_full | `PromoFull7290103152017-001-003-20261022-140531.gz` | 2026-10-22T14:05+03:00 | 6.5 | v1 | loaded | 809 | 0.46 |
| ramilevy | price_full | `PriceFull7290058140886-001-003-20261022-001017.gz` | 2026-10-22T00:10+03:00 | 20.5 | v1 | loaded | 7,507 | 1.57 |
| ramilevy | promo_full | `PromoFull7290058140886-001-003-20261022-185700.gz` | 2026-10-22T18:57+03:00 | 1.7 | v1 | loaded | 2,716 | 1.58 |
| shufersal | price_full | `PriceFull7290027600007-001-002-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.6 | v1 | loaded | 7,494 | 1.51 |
| shufersal | promo_full | `PromoFull7290027600007-001-002-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.6 | v1 | loaded | 1,383 | 3.43 |
| tivtaam | price_full | `PriceFull7290873255550-000-014-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 23,274 | 4.81 |
| tivtaam | promo_full | `PromoFull7290873255550-000-014-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 2,349 | 6.44 |
| yohananof | price_full | `PriceFull7290803800003-000-005-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 11,656 | 2.42 |
| yohananof | promo_full | `PromoFull7290803800003-000-005-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 1,241 | 0.99 |
| king_store | price_full | `PriceFull7290058108879-000-014-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 15.5 | v1 | loaded | 4,789 | 0.98 |
| king_store | price_full | `PriceFull7290058108879-000-200-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 15.5 | v1 | loaded | 3,611 | 0.74 |
| king_store | promo_full | `PromoFull7290058108879-000-014-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 15.5 | v1 | loaded | 424 | 0.24 |
| king_store | promo_full | `PromoFull7290058108879-000-200-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 15.5 | v1 | loaded | 306 | 0.18 |
| osherad | price_full | `PriceFull7290103152017-001-026-20261022-140501.gz` | 2026-10-22T14:05+03:00 | 6.6 | v1 | loaded | 6,837 | 1.4 |
| osherad | price_full | `PriceFull7290103152017-001-030-20261022-140501.gz` | 2026-10-22T14:05+03:00 | 6.6 | v1 | loaded | 6,460 | 1.27 |
| osherad | price_full | `PriceFull7290103152017-001-010-20261022-140502.gz` | 2026-10-22T14:05+03:00 | 6.6 | v1 | loaded | 6,693 | 1.37 |
| osherad | price_full | `PriceFull7290103152017-001-028-20261022-140502.gz` | 2026-10-22T14:05+03:00 | 6.6 | v1 | loaded | 6,242 | 1.31 |
| osherad | promo_full | `PromoFull7290103152017-001-026-20261022-140523.gz` | 2026-10-22T14:05+03:00 | 6.6 | v1 | loaded | 723 | 0.43 |
| osherad | promo_full | `PromoFull7290103152017-001-028-20261022-140524.gz` | 2026-10-22T14:05+03:00 | 6.6 | v1 | loaded | 706 | 0.43 |
| osherad | promo_full | `PromoFull7290103152017-001-030-20261022-140541.gz` | 2026-10-22T14:05+03:00 | 6.6 | v1 | loaded | 766 | 0.46 |
| osherad | promo_full | `PromoFull7290103152017-001-010-20261022-140556.gz` | 2026-10-22T14:05+03:00 | 6.6 | v1 | loaded | 724 | 0.44 |
| ramilevy | price_full | `PriceFull7290058140886-001-048-20261022-001016.gz` | 2026-10-22T00:10+03:00 | 20.5 | v1 | loaded | 14,443 | 3.07 |
| ramilevy | price_full | `PriceFull7290058140886-001-062-20261022-120012.gz` | 2026-10-22T12:00+03:00 | 8.7 | v1 | loaded | 14,126 | 3.03 |
| ramilevy | price_full | `PriceFull7290058140886-001-703-20261022-120017.gz` | 2026-10-22T12:00+03:00 | 8.7 | v1 | loaded | 4,959 | 1.05 |
| ramilevy | price_full | `PriceFull7290058140886-001-057-20261022-121507.gz` | 2026-10-22T12:15+03:00 | 8.4 | v1 | loaded | 13,930 | 2.97 |
| ramilevy | price_full | `PriceFull7290058140886-001-724-20261022-180005.gz` | 2026-10-22T18:00+03:00 | 2.7 | v1 | loaded | 5,163 | 1.09 |
| ramilevy | price_full | `PriceFull7290058140886-001-725-20261022-180005.gz` | 2026-10-22T18:00+03:00 | 2.7 | v1 | loaded | 4,121 | 0.87 |
| ramilevy | promo_full | `PromoFull7290058140886-001-048-20261022-120041.gz` | 2026-10-22T12:00+03:00 | 8.6 | v1 | loaded | 2,546 | 1.71 |
| ramilevy | promo_full | `PromoFull7290058140886-001-703-20261022-120047.gz` | 2026-10-22T12:00+03:00 | 8.6 | v1 | loaded | 1,110 | 0.69 |
| ramilevy | promo_full | `PromoFull7290058140886-001-062-20261022-120129.gz` | 2026-10-22T12:01+03:00 | 8.6 | v1 | loaded | 2,550 | 1.78 |
| ramilevy | promo_full | `PromoFull7290058140886-001-057-20261022-121643.gz` | 2026-10-22T12:16+03:00 | 8.4 | v1 | loaded | 2,557 | 1.79 |
| ramilevy | promo_full | `PromoFull7290058140886-001-725-20261022-180029.gz` | 2026-10-22T18:00+03:00 | 2.7 | v1 | loaded | 1,049 | 0.68 |
| ramilevy | promo_full | `PromoFull7290058140886-001-724-20261022-180031.gz` | 2026-10-22T18:00+03:00 | 2.7 | v1 | loaded | 1,062 | 0.71 |
| shufersal | price_full | `PriceFull7290027600007-001-002-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.7 | v1 | loaded | 7,494 | 0.0 |
| shufersal | price_full | `PriceFull7290027600007-001-302-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.7 | v1 | loaded | 6,533 | 1.36 |
| shufersal | price_full | `PriceFull7290027600007-006-300-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.7 | v1 | loaded | 7,721 | 1.61 |
| shufersal | price_full | `PriceFull7290027600007-007-285-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.7 | v1 | loaded | 3,322 | 0.69 |
| shufersal | price_full | `PriceFull7290027600007-007-353-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.7 | v1 | loaded | 2,269 | 0.48 |
| shufersal | price_full | `PriceFull7290027600007-018-753-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.7 | v1 | loaded | 3,553 | 0.75 |
| shufersal | promo_full | `PromoFull7290027600007-001-002-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.7 | v1 | loaded | 1,383 | 0.0 |
| shufersal | promo_full | `PromoFull7290027600007-001-302-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.7 | v1 | loaded | 1,288 | 2.87 |
| shufersal | promo_full | `PromoFull7290027600007-006-300-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.7 | v1 | loaded | 1,012 | 2.97 |
| shufersal | promo_full | `PromoFull7290027600007-007-285-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.7 | v1 | loaded | 744 | 1.27 |
| shufersal | promo_full | `PromoFull7290027600007-007-353-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.7 | v1 | loaded | 617 | 0.77 |
| shufersal | promo_full | `PromoFull7290027600007-018-753-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 17.7 | v1 | loaded | 418 | 0.97 |
| tivtaam | price_full | `PriceFull7290873255550-000-012-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 17,817 | 3.78 |
| tivtaam | price_full | `PriceFull7290873255550-000-085-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 7,171 | 1.48 |
| tivtaam | price_full | `PriceFull7290873255550-000-087-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 6,069 | 1.3 |
| tivtaam | price_full | `PriceFull7290873255550-000-092-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 5,854 | 1.25 |
| tivtaam | promo_full | `PromoFull7290873255550-000-012-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 2,041 | 6.63 |
| tivtaam | promo_full | `PromoFull7290873255550-000-085-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 1,281 | 6.32 |
| tivtaam | promo_full | `PromoFull7290873255550-000-087-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 1,124 | 5.67 |
| tivtaam | promo_full | `PromoFull7290873255550-000-092-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 1,061 | 5.78 |
| yohananof | price_full | `PriceFull7290803800003-000-020-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 11,876 | 2.41 |
| yohananof | price_full | `PriceFull7290803800003-000-021-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 11,196 | 2.34 |
| yohananof | promo_full | `PromoFull7290803800003-000-020-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 1,276 | 1.02 |
| yohananof | promo_full | `PromoFull7290803800003-000-021-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 20.0 | v1 | loaded | 1,218 | 0.94 |

PromoFull files: what they hold and how much reached `promo_items`:

| chain | file | promos | with item codes | distinct codes | codes the chain's items know | promo_items linked | active now | club | rewards |
|---|---|---|---|---|---|---|---|---|---|
| king_store | `PromoFull7290058108879-000-031-20261022-051042.gz` | 507 | 507 | 1,273 | 1,273 | 1,292 | 507 | 160 | {'bundle': 240, 'price': 264, 'other': 2, 'percent': 1} |
| osherad | `PromoFull7290103152017-001-003-20261022-140531.gz` | 809 | 809 | 2,993 | 2,068 | 2,185 | 809 | 0 | {'bundle': 721, 'price': 85, 'other': 3} |
| ramilevy | `PromoFull7290058140886-001-003-20261022-185700.gz` | 2,716 | 2,716 | 9,124 | 3,749 | 6,215 | 2,716 | 37 | {'other': 491, 'price': 1332, 'bundle': 875, 'buy_x_get_y': 16, 'percent': 2} |
| shufersal | `PromoFull7290027600007-001-002-20261022-030000.gz` | 1,383 | 1,380 | 7,613 | 7,394 | 22,388 | 1,383 | 1 | {'other': 126, 'percent': 5, 'bundle': 789, 'price': 450, 'buy_x_get_y': 13} |
| tivtaam | `PromoFull7290873255550-000-014-20261022-004004.gz` | 2,349 | 2,349 | 15,909 | 13,073 | 25,655 | 2,349 | 1,469 | {'other': 19, 'bundle': 963, 'price': 1321, 'percent': 5, 'buy_x_get_y': 41} |
| yohananof | `PromoFull7290803800003-000-005-20261022-004040.gz` | 1,241 | 1,241 | 4,233 | 4,185 | 4,259 | 1,241 | 11 | {'other': 62, 'bundle': 795, 'price': 373, 'percent': 3, 'buy_x_get_y': 8} |
| king_store | `PromoFull7290058108879-000-014-20261022-051042.gz` | 424 | 424 | 1,032 | 1,032 | 1,049 | 424 | 99 | {'bundle': 229, 'price': 194, 'other': 1} |
| king_store | `PromoFull7290058108879-000-200-20261022-051042.gz` | 306 | 306 | 813 | 813 | 831 | 306 | 77 | {'price': 143, 'bundle': 162, 'other': 1} |
| osherad | `PromoFull7290103152017-001-026-20261022-140523.gz` | 723 | 723 | 2,809 | 2,309 | 2,349 | 723 | 0 | {'bundle': 655, 'other': 3, 'price': 65} |
| osherad | `PromoFull7290103152017-001-028-20261022-140524.gz` | 706 | 706 | 2,689 | 2,199 | 2,241 | 706 | 0 | {'bundle': 642, 'price': 62, 'other': 2} |
| osherad | `PromoFull7290103152017-001-030-20261022-140541.gz` | 766 | 766 | 2,867 | 2,355 | 2,441 | 766 | 0 | {'bundle': 670, 'price': 93, 'other': 3} |
| osherad | `PromoFull7290103152017-001-010-20261022-140556.gz` | 724 | 724 | 2,812 | 2,305 | 2,399 | 724 | 0 | {'bundle': 654, 'price': 67, 'other': 3} |
| ramilevy | `PromoFull7290058140886-001-048-20261022-120041.gz` | 2,546 | 2,546 | 8,906 | 7,113 | 10,908 | 2,546 | 37 | {'bundle': 868, 'price': 1205, 'other': 455, 'buy_x_get_y': 16, 'percent': 2} |
| ramilevy | `PromoFull7290058140886-001-703-20261022-120047.gz` | 1,110 | 1,110 | 3,798 | 3,365 | 3,938 | 1,110 | 22 | {'price': 448, 'other': 289, 'bundle': 365, 'buy_x_get_y': 7, 'percent': 1} |
| ramilevy | `PromoFull7290058140886-001-062-20261022-120129.gz` | 2,550 | 2,550 | 8,858 | 7,059 | 11,094 | 2,550 | 37 | {'bundle': 863, 'price': 1187, 'other': 482, 'buy_x_get_y': 16, 'percent': 2} |
| ramilevy | `PromoFull7290058140886-001-057-20261022-121643.gz` | 2,557 | 2,557 | 8,864 | 7,063 | 11,101 | 2,557 | 37 | {'bundle': 864, 'other': 479, 'price': 1196, 'buy_x_get_y': 16, 'percent': 2} |
| ramilevy | `PromoFull7290058140886-001-725-20261022-180029.gz` | 1,049 | 1,049 | 3,934 | 3,450 | 3,992 | 1,049 | 24 | {'bundle': 354, 'price': 439, 'other': 247, 'buy_x_get_y': 8, 'percent': 1} |
| ramilevy | `PromoFull7290058140886-001-724-20261022-180031.gz` | 1,062 | 1,062 | 3,965 | 3,459 | 4,001 | 1,062 | 24 | {'price': 450, 'bundle': 356, 'other': 247, 'buy_x_get_y': 8, 'percent': 1} |
| shufersal | `PromoFull7290027600007-001-002-20261022-030000.gz` | 1,383 | 1,380 | 7,613 | 7,459 | 22,388 | 1,383 | 1 | {'other': 126, 'percent': 5, 'bundle': 789, 'price': 450, 'buy_x_get_y': 13} |
| shufersal | `PromoFull7290027600007-001-302-20261022-030000.gz` | 1,288 | 1,285 | 6,680 | 6,530 | 19,836 | 1,288 | 1 | {'other': 129, 'percent': 5, 'price': 415, 'bundle': 725, 'buy_x_get_y': 14} |
| shufersal | `PromoFull7290027600007-006-300-20261022-030000.gz` | 1,012 | 1,010 | 7,612 | 7,611 | 17,318 | 1,012 | 0 | {'other': 20, 'bundle': 682, 'price': 310} |
| shufersal | `PromoFull7290027600007-007-285-20261022-030000.gz` | 744 | 741 | 3,494 | 3,344 | 10,158 | 744 | 1 | {'other': 92, 'percent': 3, 'bundle': 448, 'price': 194, 'buy_x_get_y': 7} |
| shufersal | `PromoFull7290027600007-007-353-20261022-030000.gz` | 617 | 614 | 2,490 | 2,340 | 6,938 | 617 | 1 | {'other': 68, 'percent': 3, 'bundle': 396, 'price': 147, 'buy_x_get_y': 3} |
| shufersal | `PromoFull7290027600007-018-753-20261022-030000.gz` | 418 | 416 | 3,530 | 3,530 | 7,956 | 418 | 0 | {'other': 4, 'bundle': 299, 'price': 115} |
| tivtaam | `PromoFull7290873255550-000-012-20261022-004004.gz` | 2,041 | 2,041 | 15,144 | 13,399 | 26,750 | 2,041 | 1,226 | {'other': 18, 'bundle': 875, 'price': 1107, 'percent': 3, 'buy_x_get_y': 38} |
| tivtaam | `PromoFull7290873255550-000-085-20261022-004004.gz` | 1,281 | 1,281 | 13,365 | 11,697 | 23,846 | 1,281 | 711 | {'other': 16, 'bundle': 583, 'price': 670, 'buy_x_get_y': 12} |
| tivtaam | `PromoFull7290873255550-000-087-20261022-004004.gz` | 1,124 | 1,124 | 13,048 | 11,380 | 23,450 | 1,124 | 637 | {'other': 11, 'bundle': 538, 'price': 564, 'buy_x_get_y': 11} |
| tivtaam | `PromoFull7290873255550-000-092-20261022-004004.gz` | 1,061 | 1,061 | 13,221 | 11,553 | 23,408 | 1,061 | 556 | {'other': 15, 'bundle': 519, 'price': 517, 'buy_x_get_y': 10} |
| yohananof | `PromoFull7290803800003-000-020-20261022-004040.gz` | 1,276 | 1,276 | 4,339 | 4,305 | 4,378 | 1,276 | 11 | {'bundle': 779, 'price': 399, 'other': 86, 'percent': 4, 'buy_x_get_y': 8} |
| yohananof | `PromoFull7290803800003-000-021-20261022-004040.gz` | 1,218 | 1,218 | 4,151 | 4,128 | 4,188 | 1,218 | 11 | {'bundle': 796, 'price': 356, 'other': 54, 'percent': 3, 'buy_x_get_y': 9} |

Sample codes (promo / item): king_store ['100601', '13006', '13037'] / ['12', '12345', '13006']; osherad ['1230000292009', '16000423534', '16000548404'] / ['8850006535424', '7290116859606', '8006530174619']; ramilevy ['1220000750166', '1230000068413', '1230000116022'] / ['7290000211169', '7290000211312', '7290000211442']; shufersal ['10900035187', '10900302814', '11182700954'] / ['10900035187', '10900302814', '11182700954']; tivtaam ['10900302814', '11182170603', '11182175271'] / ['10900035187', '10900035194', '10900302814']; yohananof ['1218051', '14098', '15521'] / ['1022788', '1022801', '1022825']

`file_tracking` after the run: {'loaded': 64}. Alerts raised: 0.

| chain | physical stores | located | online | items | price events | stores with prices | promos | promo items |
|---|---|---|---|---|---|---|---|---|
| king_store | 48 | 28 | - | 8,396 | 14,391 | 3 | 1,237 | 3,172 |
| osherad | 24 | 24 | - | 8,679 | 32,973 | 5 | 3,728 | 11,615 |
| ramilevy | 98 | 96 | 1 | 18,315 | 64,249 | 7 | 13,590 | 51,249 |
| shufersal | 416 | 411 | 1 | 13,472 | 30,892 | 6 | 5,462 | 84,594 |
| tivtaam | 47 | 47 | 7 | 25,925 | 60,185 | 5 | 7,856 | 123,109 |
| yohananof | 50 | 19 | 1 | 13,721 | 34,728 | 3 | 3,735 | 12,825 |

Extra downloads (the stores nearest to these city centres, for the optimizer):

- Haifa centre: 5 chains and 32 located stores within 4 km; asked for shufersal 302,353, king_store 14, ramilevy 57,62, osherad 30, tivtaam 92,12
- Jerusalem centre: 5 chains and 32 located stores within 4 km; asked for shufersal 2,753, king_store 200, ramilevy 48,703, osherad 26,28, yohananof 20
- Petah Tikva: 5 chains and 29 located stores within 4 km; asked for shufersal 285,300, ramilevy 725,724, osherad 10, yohananof 21, tivtaam 87,85

### Matching on the real items

88,508 items; 19,109 mapped to a canonical (any level, including the review queue); 4,998 served (no review flag), onto 209 canonicals.

| level | mappings served | mappings in the review queue |
|---|---|---|
| exact | 0 | 0 |
| any_brand | 3,073 | 5,807 |
| close | 1,925 | 8,304 |

| chain | items | mapped | served |
|---|---|---|---|
| shufersal | 13,472 | 3,276 | 936 |
| king_store | 8,396 | 2,113 | 354 |
| ramilevy | 18,315 | 3,927 | 1,369 |
| osherad | 8,679 | 2,158 | 694 |
| yohananof | 13,721 | 2,670 | 932 |
| tivtaam | 25,925 | 4,965 | 713 |

- seed: 1.12 s
- normalize: 12.56 s
- extract (rule): 97.8 s
- embed (hash): 275.02 s
- judge (rule): 209.09 s

### Precompute (production semantics)

6,682 rows written in 3.708 s of job time (4.1 s wall including start-up); 4,726 items priced at 29 stores (693 stores of 6 chains considered); 2,260 rows with a promo, 229 club-only. Canonicals with a real price: 208, of them 189 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 2,964 | 191 | 29 |
| close | 3,718 | 208 | 29 |

Promos per chain, and what reached a price (production semantics):

| chain | promos | club-only | linked to items | reward `other` | effective rows | with a promo | club required | of them with a non-club fallback |
|---|---|---|---|---|---|---|---|---|
| shufersal | 5,462 | 4 | 5,442 | 439 | 1,252 | 544 | 0 | 0 |
| king_store | 1,237 | 336 | 1,237 | 4 | 521 | 135 | 32 | 32 |
| ramilevy | 13,590 | 218 | 11,811 | 2,690 | 1,901 | 688 | 0 | 0 |
| osherad | 3,728 | 0 | 3,355 | 14 | 1,038 | 283 | 0 | 0 |
| yohananof | 3,735 | 33 | 3,735 | 202 | 839 | 308 | 14 | 14 |
| tivtaam | 7,856 | 4,599 | 7,856 | 79 | 1,131 | 302 | 183 | 183 |

Club rules of the club-only promos (most frequent): `המועדון החדש` x 4,599; `מועדון לקוחות \| לקוחות סיטונאים \| עובדי קינגסטור` x 248; `מועדון חברתי \| מועדון רמי לוי \| מועדון לקוחות אשראי \| מועדון נטען \| לקוחות ארנק` x 132; `מועדון לקוחות \| עובדי קינגסטור` x 56; `מועדון לקוחות אשראי & (תווי זיכוי מימוש \| מולטיפס תו רמי לוי)` x 36; `מועדון עובדים` x 33; `לקוחות סיטונאים` x 26; `מועדון רמי לוי \| מועדון לקוחות אשראי` x 16

### Precompute (stress)

11,055 rows written in 11.983 s of job time (12.38 s wall including start-up); 18,319 items priced at 29 stores (693 stores of 6 chains considered); 3,749 rows with a promo, 468 club-only. Canonicals with a real price: 241, of them 237 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 5,061 | 237 | 29 |
| close | 5,994 | 241 | 29 |

Promos per chain, and what reached a price (stress):

| chain | promos | club-only | linked to items | reward `other` | effective rows | with a promo | club required | of them with a non-club fallback |
|---|---|---|---|---|---|---|---|---|
| shufersal | 5,462 | 4 | 5,442 | 439 | 2,180 | 982 | 0 | 0 |
| king_store | 1,237 | 336 | 1,237 | 4 | 1,009 | 301 | 84 | 84 |
| ramilevy | 13,590 | 218 | 11,811 | 2,690 | 2,880 | 1,020 | 0 | 0 |
| osherad | 3,728 | 0 | 3,355 | 14 | 1,840 | 362 | 0 | 0 |
| yohananof | 3,735 | 33 | 3,735 | 202 | 1,241 | 420 | 14 | 14 |
| tivtaam | 7,856 | 4,599 | 7,856 | 79 | 1,905 | 664 | 370 | 370 |

Club rules of the club-only promos (most frequent): `המועדון החדש` x 4,599; `מועדון לקוחות \| לקוחות סיטונאים \| עובדי קינגסטור` x 248; `מועדון חברתי \| מועדון רמי לוי \| מועדון לקוחות אשראי \| מועדון נטען \| לקוחות ארנק` x 132; `מועדון לקוחות \| עובדי קינגסטור` x 56; `מועדון לקוחות אשראי & (תווי זיכוי מימוש \| מולטיפס תו רמי לוי)` x 36; `מועדון עובדים` x 33; `לקוחות סיטונאים` x 26; `מועדון רמי לוי \| מועדון לקוחות אשראי` x 16

### The vector query behind /parse-list and /search

`item_embeddings` holds 88,508 rows (model `hash-ngram-2-3-4-v1`); one `ORDER BY embedding <=> q LIMIT 40` query took [3.6, 1.0, 0.9] ms; with sequential scans disabled 0.9 ms.

```
Limit  (cost=2387.21..2653.75 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2387.21..592161.97 rows=88508 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
--- enable_seqscan = off
Limit  (cost=2387.21..2653.75 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2387.21..592161.97 rows=88508 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
```

One `/parse-list` call (6 lines): 133.9 ms in total, 124.6 ms inside 43 SQL statements. The statements that cost the most:

| statement (first 110 characters) | calls | total ms | max ms |
|---|---|---|---|
| `WITH direct AS ( SELECT c.id AS canonical_id, 1 - (c.embedding <=> %(v)s::vector) AS s FROM canonical_products` | 6 | 88.3 | 17.8 |
| `WITH q AS (SELECT search_norm(%(q)s) AS t) SELECT c.id, word_similarity(q.t, search_norm(c.display_name_he)) A` | 6 | 18.8 | 6.5 |
| `WITH RECURSIVE up AS ( SELECT t.id AS leaf, t.id, t.parent_id, t.name_he, t.level FROM taxonomy t WHERE t.id =` | 6 | 4.3 | 1.0 |
| `SELECT c.id, c.display_name_he, ts_rank_cd(to_tsvector('simple', search_norm(c.display_name_he)), tq) AS r FRO` | 6 | 4.3 | 1.5 |
| `SELECT id, display_name_he, taxonomy_id, base_unit, rank, names_ar[1] FROM canonical_products WHERE id = ANY(%` | 6 | 3.5 | 0.8 |
| `SELECT set_config('hnsw.ef_search', %s, true), (SELECT set_config('hnsw.iterative_scan', 'relaxed_order', true` | 6 | 2.7 | 0.8 |

`EXPLAIN (ANALYZE, BUFFERS)` of the slowest statement:

```
Limit  (cost=4502.31..4502.36 rows=20 width=16) (actual rows=20 loops=1)
  Buffers: shared hit=4189 read=5
  ->  Sort  (cost=4502.31..4502.37 rows=24 width=16) (actual rows=20 loops=1)
        Sort Key: (max(direct.s)) DESC, direct.canonical_id
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=4189 read=5
        ->  GroupAggregate  (cost=4500.10..4501.76 rows=24 width=16) (actual rows=20 loops=1)
              Group Key: direct.canonical_id
              Buffers: shared hit=4189 read=5
              ->  Merge Append  (cost=4500.10..4501.40 rows=24 width=16) (actual rows=24 loops=1)
                    Sort Key: direct.canonical_id
                    Buffers: shared hit=4189 read=5
                    ->  Sort  (cost=30.82..30.84 rows=7 width=16) (actual rows=20 loops=1)
                          Sort Key: direct.canonical_id
                          Sort Method: quicksort  Memory: 25kB
                          Buffers: shared hit=1680 read=1
                          ->  Subquery Scan on direct  (cost=30.42..30.72 rows=7 width=16) (actual rows=20 loops=1)
                                Filter: (direct.s >= '0.25'::double precision)
                                Buffers: shared hit=1680 read=1
                                ->  Limit  (cost=30.42..30.47 rows=20 width=24) (actual rows=20 loops=1)
                                      Buffers: shared hit=1680 read=1
                                      ->  Sort  (cost=30.42..31.03 rows=245 width=24) (actual rows=20 loops=1)
                                            Sort Key: ((c.embedding <=> <query vector>))
                                            Sort Method: top-N heapsort  Memory: 27kB
                                            Buffers: shared hit=1680 read=1
                                            ->  Seq Scan on canonical_products c  (cost=0.00..23.90 rows=245 width=24) (actual rows=245 loops=1)
                                                  Filter: ((embedding IS NOT NULL) AND (embedding_model = 'hash-ngram-2-3-4-v1'::text))
                                                  Buffers: shared hit=1680 read=1
                    ->  GroupAggregate  (cost=4469.27..4470.31 rows=17 width=16) (actual rows=4 loops=1)
                          Group Key: ic.canonical_id
                          Filter: (max(n.s) >= '0.25'::double precision)
                          Buffers: shared hit=2509 read=4
                          ->  Sort  (cost=4469.27..4469.40 rows=52 width=16) (actual rows=15 loops=1)
                                Sort Key: ic.canonical_id
                                Sort Method: quicksort  Memory: 25kB
                                Buffers: shared hit=2509 read=4
                                ->  Hash Join  (cost=3415.96..4467.79 rows=52 width=16) (actual rows=15 loops=1)
                                      Hash Cond: (ic.item_id = n.item_id)
                                      Buffers: shared hit=2509 read=4
                                      ->  Bitmap Heap Scan on item_canonical ic  (cost=493.87..1544.69 rows=130 width=16) (actual rows=3073 loops=1)
                                            Recheck Cond: (flex_level = ANY ('{exact,any_brand}'::text[]))
                                            Filter: ((NOT human_rejected) AND (NOT needs_review))
                                            Rows Removed by Filter: 5807
                                            Heap Blocks: exact=1402
                                            Buffers: shared hit=1427
                                            ->  Bitmap Index Scan on item_canonical_canonical_idx  (cost=0.00..493.84 rows=519 width=0) (actual rows=8880 loops=1)
                                                  Index Cond: (flex_level = ANY ('{exact,any_brand}'::text[]))
                                                  Buffers: shared hit=25
                                      ->  Hash  (cost=2921.09..2921.09 rows=80 width=16) (actual rows=57 loops=1)
                                            Buckets: 1024  Batches: 1  Memory Usage: 11kB
                                            Buffers: shared hit=1082 read=4
                                            ->  Subquery Scan on n  (cost=2387.21..2921.09 rows=80 width=16) (actual rows=57 loops=1)
                                                  Buffers: shared hit=1082 read=4
                                                  ->  Limit  (cost=2387.21..2920.29 rows=80 width=24) (actual rows=57 loops=1)
                                                        Buffers: shared hit=1082 read=4
                                                        ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2387.21..592161.97 rows=88508 width=24) (actual rows=57 loops=1)
                                                              Order By: (embedding <=> <query vector>)
                                                              Filter: (model = 'hash-ngram-2-3-4-v1'::text)
                                                              Buffers: shared hit=1082 read=4
Planning:
  Buffers: shared hit=455 read=16
Planning Time: 1.530 ms
Execution Time: 9.495 ms
```

### /parse-list, /compare and /optimize (production semantics)

Locations: Jerusalem centre (10 priced stores, 5 chains within 5 km); Haifa centre (8 priced stores, 5 chains within 5 km); Petah Tikva (8 priced stores, 5 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 167.5 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 316.3 |
| large (32 lines) | 33 | 33 | 5 | 0 | 508.4 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 10 | 0 | 11.5 | 10 | 17.4 | 55 | single: רמי לוי עטרות | 5.13 / 5.13 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 10 | 0 | 15.9 | 12.3 | 20.2 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 33 | 10 | 0 | 22.5 | 16.7 | 25.4 | 55 | single: רמי לוי עטרות | 45.67 / 45.67 |
| Jerusalem centre | drawn: 5 | 5 | 10 | 6 | 11.6 | 9.4 | 16.5 | 55 | single: רמי לוי עטרות | 28.77 / 28.77 |
| Jerusalem centre | drawn: 10 | 10 | 10 | 0 | 13.2 | 10.5 | 17 | 55 | split: אושר עד תלפיות, רמי לוי עטרות | -77.02 / -77.02 |
| Jerusalem centre | drawn: 20 | 20 | 10 | 0 | 18.7 | 14.1 | 25.4 | 55 | single: רמי לוי עטרות | 18.37 / 18.37 |
| Jerusalem centre | drawn: 40 | 40 | 10 | 0 | 29.4 | 20.3 | 35.1 | 55 | single: רמי לוי עטרות | 138.15 / 138.15 |
| Haifa centre | hand: small (6 lines) | 6 | 8 | 0 | 9.4 | 7.5 | 12.6 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | hand: weekly (17 lines) | 17 | 8 | 0 | 14.8 | 10.3 | 17.4 | 55 | single: שופרסל שלי חיפה- קלר | -10.34 / -10.34 |
| Haifa centre | hand: large (32 lines) | 33 | 8 | 0 | 20.8 | 12.5 | 19.4 | 55 | single: שופרסל שלי חיפה- קלר | -12.25 / -12.25 |
| Haifa centre | drawn: 5 | 5 | 8 | 2 | 9.9 | 8.4 | 14.2 | 55 | single: שופרסל אקספרס יותם | 0.12 / 0.12 |
| Haifa centre | drawn: 10 | 10 | 8 | 0 | 12.6 | 8.7 | 15.3 | 55 | single: שופרסל שלי חיפה- קלר | 47.23 / 47.23 |
| Haifa centre | drawn: 20 | 20 | 8 | 0 | 15.3 | 10.1 | 17.2 | 55 | single: שופרסל שלי חיפה- קלר | 8.51 / 8.51 |
| Haifa centre | drawn: 40 | 40 | 8 | 0 | 24 | 13.3 | 24.7 | 55 | single: שופרסל שלי חיפה- קלר | 6.89 / 6.89 |
| Petah Tikva | hand: small (6 lines) | 6 | 8 | 0 | 9.2 | 8 | 12.9 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 17.64 / 17.64 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 8 | 0 | 14.2 | 11.2 | 18.7 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 18.04 / 18.04 |
| Petah Tikva | hand: large (32 lines) | 33 | 8 | 0 | 18.8 | 14.4 | 21.8 | 55 | single: רמי לוי שטמפפר פתח תקווה | 0.0 / 0.0 |
| Petah Tikva | drawn: 5 | 5 | 8 | 1 | 9.8 | 8.7 | 14.9 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 2.46 / 2.46 |
| Petah Tikva | drawn: 10 | 10 | 8 | 0 | 12.3 | 9.9 | 16.4 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 52.06 / 52.06 |
| Petah Tikva | drawn: 20 | 20 | 8 | 0 | 15.3 | 12.3 | 19.8 | 55 | single: רמי לוי קניון אבנת פתח תקווה | -13.24 / -13.24 |
| Petah Tikva | drawn: 40 | 40 | 8 | 0 | 26 | 17.4 | 27.7 | 55 | single: רמי לוי שטמפפר פתח תקווה | 0.0 / 0.0 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 9.4 | 8.0 | 12.9 |
| hand: weekly (17 lines) | 14.8 | 11.2 | 18.7 |
| hand: large (32 lines) | 20.8 | 14.4 | 21.8 |
| drawn: 5 | 9.9 | 8.7 | 14.9 |
| drawn: 10 | 12.6 | 9.9 | 16.4 |
| drawn: 20 | 15.3 | 12.3 | 19.8 |
| drawn: 40 | 26.0 | 17.4 | 27.7 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 9.9 | 16.2 | - | - | 5.13 / 5.13 |
| Jerusalem centre | hand: weekly (17 lines) | 12.5 | 20.9 | רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | 23.07 / 23.07 |
| Jerusalem centre | hand: large (32 lines) | 16.2 | 24.8 | - | - | 45.67 / 45.67 |
| Jerusalem centre | drawn: 5 | 9.7 | 16.8 | אושר עד תלפיות, רמי לוי עטרות | אושר עד תלפיות, רמי לוי עטרות | 37.0 / 37.0 |
| Jerusalem centre | drawn: 10 | 10.1 | 16.6 | אושר עד תלפיות, רמי לוי עטרות | אושר עד תלפיות, רמי לוי עטרות | -52.02 / -52.02 |
| Jerusalem centre | drawn: 20 | 14.3 | 25.3 | - | - | 18.37 / 18.37 |
| Jerusalem centre | drawn: 40 | 22.8 | 35.7 | - | - | 138.15 / 138.15 |
| Haifa centre | hand: small (6 lines) | 7.5 | 13.2 | - | - | 0.0 / 0.0 |
| Haifa centre | hand: weekly (17 lines) | 10.6 | 17.2 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 10.87 / 10.87 |
| Haifa centre | hand: large (32 lines) | 12.4 | 20.1 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 11.27 / 11.27 |
| Haifa centre | drawn: 5 | 8.3 | 14.1 | - | - | 0.12 / 0.12 |
| Haifa centre | drawn: 10 | 8.5 | 14.5 | - | - | 47.23 / 47.23 |
| Haifa centre | drawn: 20 | 10.6 | 17.4 | - | - | 8.51 / 8.51 |
| Haifa centre | drawn: 40 | 14.1 | 25.5 | - | - | 6.89 / 6.89 |
| Petah Tikva | hand: small (6 lines) | 7.9 | 12.7 | - | - | 17.64 / 17.64 |
| Petah Tikva | hand: weekly (17 lines) | 11.8 | 18.1 | - | - | 18.04 / 18.04 |
| Petah Tikva | hand: large (32 lines) | 15.8 | 22.1 | - | - | 0.0 / 0.0 |
| Petah Tikva | drawn: 5 | 8.1 | 14.2 | - | - | 2.46 / 2.46 |
| Petah Tikva | drawn: 10 | 10.5 | 16.6 | - | - | 52.06 / 52.06 |
| Petah Tikva | drawn: 20 | 12.2 | 19 | - | - | -13.24 / -13.24 |
| Petah Tikva | drawn: 40 | 18.1 | 27.4 | - | - | 0.0 / 0.0 |

### /parse-list, /compare and /optimize (stress: unreviewed mappings included, performance only)

Locations: Jerusalem centre (10 priced stores, 5 chains within 5 km); Haifa centre (8 priced stores, 5 chains within 5 km); Petah Tikva (8 priced stores, 5 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 160.5 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 323.4 |
| large (32 lines) | 33 | 33 | 5 | 0 | 526.3 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 10 | 8 | 13.3 | 11.1 | 17.2 | 55 | single: רמי לוי עטרות | 27.26 / 27.26 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 10 | 2 | 19.5 | 15.4 | 23.6 | 55 | split: אושר עד תלפיות, שופרסל גוד מרקט רש"י ירושלים | 36.32 / 36.32 |
| Jerusalem centre | hand: large (32 lines) | 33 | 10 | 1 | 31 | 21.5 | 31.2 | 55 | split: רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | 77.69 / 77.69 |
| Jerusalem centre | drawn: 5 | 5 | 10 | 5 | 11.9 | 9.2 | 15 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | drawn: 10 | 10 | 10 | 1 | 14.1 | 11.2 | 18 | 55 | split: רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | 69.03 / 69.03 |
| Jerusalem centre | drawn: 20 | 20 | 10 | 0 | 20.5 | 14.6 | 28.5 | 55 | single: רמי לוי עטרות | 40.01 / 30.81 |
| Jerusalem centre | drawn: 40 | 40 | 10 | 0 | 33.4 | 23.2 | 34.6 | 55 | single: רמי לוי עטרות | 267.17 / 267.17 |
| Haifa centre | hand: small (6 lines) | 6 | 8 | 6 | 11.4 | 8.7 | 14 | 55 | single: שופרסל שלי חיפה- קלר | 2.85 / 2.85 |
| Haifa centre | hand: weekly (17 lines) | 17 | 8 | 2 | 17.7 | 11.4 | 18.1 | 55 | single: שופרסל שלי חיפה- קלר | 22.9 / 22.9 |
| Haifa centre | hand: large (32 lines) | 33 | 8 | 1 | 27.4 | 15.9 | 23 | 55 | single: שופרסל שלי חיפה- קלר | 73.31 / 73.31 |
| Haifa centre | drawn: 5 | 5 | 8 | 2 | 10.6 | 8.3 | 14.6 | 55 | single: שופרסל שלי חיפה- קלר | 11.52 / 11.52 |
| Haifa centre | drawn: 10 | 10 | 8 | 1 | 13.2 | 8.7 | 14.5 | 55 | single: שופרסל שלי חיפה- קלר | -11.37 / -11.37 |
| Haifa centre | drawn: 20 | 20 | 8 | 1 | 18.9 | 11.9 | 19.7 | 55 | single: שופרסל שלי חיפה- קלר | 81.53 / 81.53 |
| Haifa centre | drawn: 40 | 40 | 8 | 0 | 31.8 | 16.3 | 31.6 | 55 | single: שופרסל שלי חיפה- קלר | 247.38 / 247.38 |
| Petah Tikva | hand: small (6 lines) | 6 | 8 | 8 | 11 | 9.2 | 15.2 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 50.69 / 50.69 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 8 | 4 | 17.6 | 13.4 | 21.3 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 35.31 / 35.31 |
| Petah Tikva | hand: large (32 lines) | 33 | 8 | 0 | 27 | 19.9 | 30.1 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 90.32 / 90.32 |
| Petah Tikva | drawn: 5 | 5 | 8 | 4 | 10.6 | 9.4 | 15 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 46.15 / 46.15 |
| Petah Tikva | drawn: 10 | 10 | 8 | 2 | 13.3 | 11.3 | 17.7 | 55 | split: רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | 33.63 / 33.63 |
| Petah Tikva | drawn: 20 | 20 | 8 | 0 | 18.6 | 15.2 | 23.4 | 55 | split: רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | 85.53 / 85.53 |
| Petah Tikva | drawn: 40 | 40 | 8 | 0 | 32.8 | 23.1 | 41.7 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 10.16 / 10.16 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 11.4 | 9.2 | 15.2 |
| hand: weekly (17 lines) | 17.7 | 13.4 | 21.3 |
| hand: large (32 lines) | 27.4 | 19.9 | 30.1 |
| drawn: 5 | 10.6 | 9.2 | 15.0 |
| drawn: 10 | 13.3 | 11.2 | 17.7 |
| drawn: 20 | 18.9 | 14.6 | 23.4 |
| drawn: 40 | 32.8 | 23.1 | 34.6 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 10.7 | 17.1 | רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | 29.7 / 29.7 |
| Jerusalem centre | hand: weekly (17 lines) | 14.9 | 22.7 | אושר עד תלפיות, שופרסל גוד מרקט רש"י ירושלים | אושר עד תלפיות, שופרסל גוד מרקט רש"י ירושלים | 61.32 / 61.32 |
| Jerusalem centre | hand: large (32 lines) | 21.3 | 31.8 | רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | 102.69 / 102.69 |
| Jerusalem centre | drawn: 5 | 9.4 | 15.6 | רמי לוי עטרות, שופרסל שלי ירושלים- אגרון | רמי לוי עטרות, שופרסל שלי ירושלים- אגרון | 8.34 / 8.34 |
| Jerusalem centre | drawn: 10 | 11.2 | 17.2 | רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | 94.03 / 94.03 |
| Jerusalem centre | drawn: 20 | 15.8 | 29.3 | - | - | 40.01 / 30.81 |
| Jerusalem centre | drawn: 40 | 23.5 | 35 | - | - | 267.17 / 267.17 |
| Haifa centre | hand: small (6 lines) | 9 | 15.2 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 3.96 / 3.96 |
| Haifa centre | hand: weekly (17 lines) | 11.4 | 18.6 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 28.97 / 28.97 |
| Haifa centre | hand: large (32 lines) | 15.5 | 24 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 85.09 / 85.09 |
| Haifa centre | drawn: 5 | 8.3 | 14.6 | - | - | 11.52 / 11.52 |
| Haifa centre | drawn: 10 | 9.2 | 17.3 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 2.34 / 2.34 |
| Haifa centre | drawn: 20 | 11.2 | 19.5 | - | - | 81.53 / 81.53 |
| Haifa centre | drawn: 40 | 16.7 | 32.5 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 337.16 / 337.16 |
| Petah Tikva | hand: small (6 lines) | 9.5 | 18 | - | - | 50.69 / 50.69 |
| Petah Tikva | hand: weekly (17 lines) | 14.1 | 22.9 | רמי לוי שטמפפר פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | רמי לוי שטמפפר פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | 39.42 / 39.42 |
| Petah Tikva | hand: large (32 lines) | 19.5 | 27.6 | - | - | 90.32 / 90.32 |
| Petah Tikva | drawn: 5 | 9 | 18.1 | - | - | 46.15 / 46.15 |
| Petah Tikva | drawn: 10 | 11.1 | 17.7 | רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | 58.63 / 58.63 |
| Petah Tikva | drawn: 20 | 14.6 | 22 | רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | 110.53 / 110.53 |
| Petah Tikva | drawn: 40 | 22.5 | 41 | - | - | 10.16 / 10.16 |

Invariant violations seen on responses (1):
- Jerusalem centre drawn: 20: MILP net saving 30.81 is below the heuristic's 40.01

### Basket index on the real day (#44, dry run, production semantics)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `missing_items` שופרסל has no price for 8 basket items (yellow-cheese-sliced-28, butter, eggs-l, cucumber, banana, pita, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` שופרסל: 4 lines use estimated weighed-goods prices
- warning: `missing_items` קינג סטור has no price for 15 basket items (cottage-5, yellow-cheese-sliced-28, butter, eggs-l, chicken-breast-fresh, hummus-plain, tomato, cucumber, banana, bread-standard, pita, pasta-spaghetti, tuna-in-oil, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` קינג סטור: 2 lines use estimated weighed-goods prices
- warning: `missing_items` רמי לוי has no price for 7 basket items (butter, hummus-plain, cucumber, potato, banana, pasta-spaghetti, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` רמי לוי: 3 lines use estimated weighed-goods prices
- warning: `missing_items` אושר עד has no price for 13 basket items (milk-fresh-3, white-cheese-5, yellow-cheese-sliced-28, yogurt-plain-3, eggs-l, hummus-plain, tomato, cucumber, pasta-spaghetti, sugar-white, bamba, chocolate-milk, toilet-paper); it is listed but not ranked
- warning: `estimated_items` אושר עד: 3 lines use estimated weighed-goods prices
- warning: `missing_items` יוחננוף has no price for 13 basket items (yellow-cheese-sliced-28, butter, eggs-l, hummus-plain, tomato, cucumber, potato, banana, pita, pasta-spaghetti, bamba, chocolate-milk, toilet-paper); it is listed but not ranked
- warning: `estimated_items` יוחננוף: 2 lines use estimated weighed-goods prices
- warning: `missing_items` טיב טעם has no price for 12 basket items (milk-fresh-3, yellow-cheese-sliced-28, yogurt-plain-3, butter, eggs-l, hummus-plain, pita, pasta-spaghetti, tuna-in-oil, mineral-water, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` טיב טעם: 6 lines use estimated weighed-goods prices
- error: `line_outlier` mineral-water: אושר עד costs 67.73 against 9.94 at יוחננוף, 6.8 times (limit 4); read the unit prices and pack counts of the items behind it
- error: `too_few_chains` only 0 chain(s) price the whole basket; at least 2 needed

Basket of 25 lines; price date 2026-10-22T15:00:05Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| שופרסל | - | 17 | 8 | 6 | no |
| קינג סטור | - | 10 | 15 | 3 | no |
| רמי לוי | - | 18 | 7 | 7 | no |
| אושר עד | - | 12 | 13 | 5 | no |
| יוחננוף | - | 12 | 13 | 3 | no |
| טיב טעם | - | 13 | 12 | 5 | no |

Cost of each line per chain (ILS, median store x amount; the lines two chains price 2x apart or more are marked *):

| line | amount | shufersal | king_store | ramilevy | osherad | yohananof | tivtaam |
|---|---|---|---|---|---|---|---|
| bamba | 2 | - | - | 7.5 | - | - | - |
| banana | 1 | - | - | - | 8.9 | - | 11.9 |
| bread-standard | 7.5 | 7.36 | - | 6.92 | 6.3 | 7.6 | 8.38 |
| butter | 2 | - | - | - | 9.5 | - | - |
| canola-oil | 10 | 10.36 | 10.9 | 7.5 | 7.5 | 7.5 | 10.9 |
| chicken-breast-fresh | 1 | 37.91 | - | 30.0 | 29.9 | 34.9 | 41.9 |
| cottage-5 | 5 | 12.8 | - | 12.0 | 12.0 | 12.4 | 12.2 |
| cucumber | 1 | - | - | - | - | - | 7.9 |
| eggs-l | 12 | - | - | 14.2 | - | - | - |
| hummus-plain | 4 | 11.0 | - | - | - | - | - |
| milk-fresh-3 | 20 | 14.7 | 14.7 | 14.2 | - | 14.7 | - |
| mineral-water* | 60 | 11.0 | 10.6 | 9.94 | 67.73 | 9.94 | - |
| onion | 1 | 5.9 | 5.45 | 4.9 | 4.9 | 4.9 | 5.9 |
| pasta-spaghetti | 5 | 2.75 | - | - | - | - | - |
| pita | 10 | - | - | 11.9 | 11.9 | - | - |
| potato | 2 | 15.8 | 13.8 | - | 13.56 | - | 17.8 |
| rice-persian | 10 | 10.0 | 7.9 | 6.0 | 7.07 | 6.0 | 10.9 |
| sugar-white* | 10 | 3.95 | 4.9 | 3.33 | - | 11.9 | 5.5 |
| toilet-paper | 24 | 25.43 | 20.93 | 28.43 | - | - | 24.67 |
| tomato* | 1.5 | 29.85 | - | 25.35 | - | - | 13.35 |
| tuna-in-oil | 4.8 | 18.67 | - | 19.89 | 17.59 | 14.93 | - |
| white-cheese-5 | 5 | 11.74 | 11.74 | 11.6 | - | 11.74 | 11.74 |
| yellow-cheese-sliced-28 | 4 | - | - | 14.0 | - | - | - |
| yogurt-plain-3* | 8 | 30.0 | 18.8 | 12.0 | - | 14.4 | - |

Items behind `yogurt-plain-3` (up to 3 per chain, cheapest unit price first):
- shufersal: יוגורט עזים טבעי 3% 200ג, shelf 7.5, unit price 3.75 per 100g
- king_store: יוגורט טבעי 3% שומן 200 ג' תנובה, shelf 3.7, unit price 1.85 per 100g
- king_store: דנונה ביו יוגורט טבעי 3% 200 ג', shelf 4.7, unit price 2.35 per 100g
- king_store: דנונה ביו יוגורט טבעי 3% 200 ג', shelf 4.7, unit price 2.35 per 100g
- ramilevy: יוגורט ביו טבעי 3% 5, shelf 7.8, unit price 1.3 per 100g
- ramilevy: יוגורט ביו טבעי 3% 5, shelf 7.8, unit price 1.3 per 100g
- ramilevy: יוגורט ביו טבעי 3% 5, shelf 7.8, unit price 1.3 per 100g
- yohananof: יוגורט תנובה טבעי 3%, shelf 3.6, unit price 1.8 per 100g
- yohananof: יוגורט תנובה טבעי 3%, shelf 3.6, unit price 1.8 per 100g
- yohananof: יוגורט תנובה טבעי 3%, shelf 3.6, unit price 1.8 per 100g

Items behind `tomato` (up to 3 per chain, cheapest unit price first):
- shufersal: עגבניות מגי ארוז, shelf 19.9, unit price 19.9 per kg (estimated)
- shufersal: עגבניות מגי ארוז, shelf 19.9, unit price 19.9 per kg (estimated)
- shufersal: עגבניות מגי ארוז, shelf 22.9, unit price 22.9 per kg (estimated)
- ramilevy: עגבניות מגי, shelf 13.9, unit price 13.9 per kg (estimated)
- ramilevy: עגבניות מגי, shelf 13.9, unit price 13.9 per kg (estimated)
- ramilevy: עגבניות מגי, shelf 15.9, unit price 15.9 per kg (estimated)
- tivtaam: עגבניות, shelf 7.9, unit price 7.9 per kg (estimated)
- tivtaam: עגבניות, shelf 7.9, unit price 7.9 per kg (estimated)
- tivtaam: עגבניות, shelf 8.9, unit price 8.9 per kg (estimated)

Items behind `sugar-white` (up to 3 per chain, cheapest unit price first):
- shufersal: סוכר לבן 1 ק"ג, shelf 5.9, unit price 0.3333 per 100g
- shufersal: סוכר לבן 1 ק"ג, shelf 5.9, unit price 0.3333 per 100g
- shufersal: סוכר לבן 1 ק"ג, shelf 6.1, unit price 0.395 per 100g
- king_store: סוכר לבן 1 ק"ג ROSE, shelf 4.9, unit price 0.49 per 100g
- king_store: סוכר לבן 1 ק"ג ROSE, shelf 4.9, unit price 0.49 per 100g
- king_store: סוכר לבן 1 ק"ג ROSE, shelf 4.9, unit price 0.49 per 100g
- ramilevy: סוכר לבן 1 ק"ג שטודן, shelf 4.9, unit price 0.3333 per 100g
- ramilevy: סוכר לבן 1 ק"ג שטודן, shelf 4.9, unit price 0.3333 per 100g
- ramilevy: סוכר לבן 1 ק"ג שטודן, shelf 4.9, unit price 0.3333 per 100g
- yohananof: סוכר לבן בצנצנת 1ק"ג, shelf 9.9, unit price 0.99 per 100g
- yohananof: סוכר לבן בצנצנת 1ק"ג, shelf 11.9, unit price 1.19 per 100g
- yohananof: סוכר לבן בצנצנת 1ק"ג, shelf 11.9, unit price 1.19 per 100g
- tivtaam: סוכר לבן 1 ק"ג, shelf 5.5, unit price 0.55 per 100g
- tivtaam: סוכר לבן 1 ק"ג, shelf 5.5, unit price 0.55 per 100g
- tivtaam: סוכר לבן 1 ק"ג, shelf 5.5, unit price 0.55 per 100g

Items behind `mineral-water` (up to 3 per chain, cheapest unit price first):
- shufersal: מים מינרליים מי עדן6*1.5, shelf 14.8, unit price 0.1644 per 100ml
- shufersal: מים מינרליים מי עדן6*1.5, shelf 15.9, unit price 0.1767 per 100ml
- shufersal: מים מינרליים מי עדן6*1.5, shelf 16.5, unit price 0.1833 per 100ml
- king_store: שישיית מים מינרליים 6* 1.5 ל' מי עדן, shelf 15.9, unit price 0.1767 per 100ml
- king_store: שישיית מים מינרליים 6* 1.5 ל' מי עדן, shelf 15.9, unit price 0.1767 per 100ml
- ramilevy: מים מינרלים מי עדן 6, shelf 14.9, unit price 0.1656 per 100ml
- ramilevy: מים מינרלים מי עדן 6, shelf 14.9, unit price 0.1656 per 100ml
- ramilevy: מים מינרלים מי עדן 6, shelf 14.9, unit price 0.1656 per 100ml
- osherad: מארז מים מינרלים מוג, shelf 14.9, unit price 1.1288 per 100ml
- yohananof: מים מינרלים  מי עדן, shelf 14.9, unit price 0.1656 per 100ml
- yohananof: מים מינרלים  מי עדן, shelf 14.9, unit price 0.1656 per 100ml
- yohananof: מים מינרלים  מי עדן, shelf 14.9, unit price 0.1656 per 100ml

### Basket index on the real day (#44, dry run, stress)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `estimated_items` רמי לוי: 6 lines use estimated weighed-goods prices
- warning: `estimated_items` שופרסל: 6 lines use estimated weighed-goods prices
- warning: `estimated_items` טיב טעם: 6 lines use estimated weighed-goods prices
- warning: `missing_items` קינג סטור has no price for 2 basket items (bread-standard, tuna-in-oil); it is listed but not ranked
- warning: `estimated_items` קינג סטור: 6 lines use estimated weighed-goods prices
- warning: `missing_items` אושר עד has no price for 1 basket items (toilet-paper); it is listed but not ranked
- warning: `estimated_items` אושר עד: 5 lines use estimated weighed-goods prices
- warning: `missing_items` יוחננוף has no price for 1 basket items (toilet-paper); it is listed but not ranked
- warning: `estimated_items` יוחננוף: 6 lines use estimated weighed-goods prices
- error: `line_outlier` chicken-breast-fresh: קינג סטור costs 39.90 against 8.90 at אושר עד, 4.5 times (limit 4); read the unit prices and pack counts of the items behind it

Basket of 25 lines; price date 2026-10-22T15:00:05Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| רמי לוי | 275.55 | 25 | 0 | 7 | yes |
| שופרסל | 343.89 | 25 | 0 | 6 | yes |
| טיב טעם | 346.36 | 25 | 0 | 5 | yes |
| קינג סטור | - | 23 | 2 | 3 | no |
| אושר עד | - | 24 | 1 | 5 | no |
| יוחננוף | - | 24 | 1 | 3 | no |

Cost of each line per chain (ILS, median store x amount; the lines two chains price 2x apart or more are marked *):

| line | amount | shufersal | king_store | ramilevy | osherad | yohananof | tivtaam |
|---|---|---|---|---|---|---|---|
| bamba | 2 | 10.42 | 12.42 | 7.5 | 7.5 | 8.33 | 11.58 |
| banana | 1 | 12.9 | 10.9 | 9.9 | 8.9 | 9.9 | 11.9 |
| bread-standard | 7.5 | 7.66 | - | 6.92 | 6.3 | 4.9 | 8.38 |
| butter | 2 | 10.7 | 11.5 | 7.3 | 6.1 | 6.2 | 9.9 |
| canola-oil | 10 | 10.36 | 10.9 | 7.5 | 7.5 | 7.5 | 9.9 |
| chicken-breast-fresh* | 1 | 32.9 | 39.9 | 31.4 | 8.9 | 24.9 | 33.9 |
| chocolate-milk | 10 | 14.2 | 13.2 | 7.9 | 7.9 | 8.0 | 12.45 |
| cottage-5 | 5 | 12.8 | 13.2 | 11.8 | 11.8 | 12.4 | 12.2 |
| cucumber | 1 | 8.9 | 7.9 | 4.9 | 6.9 | 6.9 | 7.9 |
| eggs-l | 12 | 14.24 | 14.24 | 14.2 | 14.09 | 14.24 | 14.24 |
| hummus-plain | 4 | 11.0 | 10.5 | 8.9 | 9.5 | 8.9 | 8.78 |
| milk-fresh-3 | 20 | 12.82 | 14.7 | 12.6 | 12.6 | 14.7 | 14.7 |
| mineral-water | 60 | 11.0 | 7.27 | 9.94 | 9.94 | 9.94 | 13.93 |
| onion | 1 | 5.9 | 5.0 | 4.9 | 4.9 | 4.9 | 5.9 |
| pasta-spaghetti* | 5 | 3.33 | 4.5 | 2.5 | 2.9 | 3.75 | 6.5 |
| pita | 10 | 11.61 | 14.9 | 13.9 | 11.9 | 9.9 | 16.9 |
| potato | 2 | 13.11 | 9.8 | 7.8 | 11.96 | 7.8 | 13.8 |
| rice-persian | 10 | 10.0 | 7.9 | 6.0 | 7.07 | 6.0 | 9.9 |
| sugar-white | 10 | 3.95 | 4.9 | 3.33 | 4.9 | 4.9 | 5.5 |
| toilet-paper | 24 | 25.43 | 20.93 | 28.43 | - | - | 24.67 |
| tomato | 1.5 | 14.85 | 16.35 | 8.85 | 9.87 | 11.85 | 13.35 |
| tuna-in-oil | 4.8 | 18.67 | - | 19.89 | 17.59 | 13.13 | 19.13 |
| white-cheese-5 | 5 | 11.74 | 11.74 | 11.6 | 11.6 | 11.74 | 11.74 |
| yellow-cheese-sliced-28* | 4 | 37.8 | 39.8 | 14.0 | 12.0 | 35.8 | 33.6 |
| yogurt-plain-3 | 8 | 17.6 | 18.8 | 13.6 | 15.2 | 14.4 | 15.6 |

Items behind `yellow-cheese-sliced-28` (up to 3 per chain, cheapest unit price first):
- shufersal: גבינת עמק דק דק 28% 200ג, shelf 17.2, unit price 8.6 per 100g
- shufersal: פתיתי עמק 28% 200 גרם, shelf 18.9, unit price 9.45 per 100g
- shufersal: פתיתי עמק 28% 200 גרם, shelf 18.9, unit price 9.45 per 100g
- king_store: גבינת דק דק 28% 200 ג' עמק, shelf 19.9, unit price 9.95 per 100g
- king_store: גבינת דק דק 28% 200 ג' עמק, shelf 19.9, unit price 9.95 per 100g
- king_store: גבינת דק דק 28% 200 ג' עמק, shelf 19.9, unit price 9.95 per 100g
- ramilevy: גבינה צהובה 28% רמי, shelf 14, unit price 3.5 per 100g
- ramilevy: גבינה צהובה 28% רמי, shelf 14, unit price 3.5 per 100g
- ramilevy: גבינה צהובה 28% רמי, shelf 14, unit price 3.5 per 100g
- osherad: גבינת גאודה פרוסה 28, shelf 29.9, unit price 2.99 per 100g
- osherad: גבינת גאודה פרוסה 28, shelf 30, unit price 3 per 100g
- osherad: גבינת גאודה פרוסה 28, shelf 30, unit price 3 per 100g
- yohananof: פתיתי עמק 28% שומן, shelf 17.9, unit price 8.95 per 100g
- yohananof: פתיתי עמק 28% שומן, shelf 17.9, unit price 8.95 per 100g
- yohananof: פתיתי עמק 28% שומן, shelf 17.9, unit price 8.95 per 100g
- tivtaam: גבינה צהובה גוש חלב 200 גרם, shelf 16.8, unit price 8.4 per 100g
- tivtaam: גבינה צהובה גוש חלב 200 גרם, shelf 16.8, unit price 8.4 per 100g
- tivtaam: גבינה צהובה גוש חלב 200 גרם, shelf 16.8, unit price 8.4 per 100g

Items behind `chicken-breast-fresh` (up to 3 per chain, cheapest unit price first):
- shufersal: עצמות עוף טרי, shelf 9.9, unit price 9.9 per kg (estimated)
- shufersal: עוף טרי מוכשר תפ, shelf 21.9, unit price 21.9 per kg (estimated)
- shufersal: עוף טרי ארוז עטרה, shelf 27.9, unit price 27.9 per kg (estimated)
- king_store: חזה עוף, shelf 39.9, unit price 39.9 per kg (estimated)
- king_store: חזה עוף, shelf 39.9, unit price 39.9 per kg (estimated)
- ramilevy: חזה עוף שלם טרי, shelf 19.9, unit price 19.9 per kg (estimated)
- ramilevy: לב עוף טרי כשר, shelf 27.9, unit price 27.9 per kg (estimated)
- ramilevy: חזה שלם עוף טרי כשר, shelf 34.9, unit price 34.9 per kg (estimated)
- osherad: עצמות עוף טרי עטרה, shelf 3.9, unit price 3.9 per kg (estimated)
- osherad: עצמות עוף טרי עטרה, shelf 4.9, unit price 4.9 per kg (estimated)
- osherad: עצמות עוף טרי עטרה, shelf 8.9, unit price 8.9 per kg (estimated)
- yohananof: עוף טרי  מפורק, shelf 24.9, unit price 24.9 per kg (estimated)
- yohananof: עוף טרי  מפורק, shelf 24.9, unit price 24.9 per kg (estimated)
- yohananof: עוף טרי  מפורק, shelf 24.9, unit price 24.9 per kg (estimated)
- tivtaam: לב עוף טרי, shelf 33.9, unit price 33.9 per kg (estimated)
- tivtaam: לב עוף טרי, shelf 33.9, unit price 33.9 per kg (estimated)
- tivtaam: לב עוף טרי, shelf 33.9, unit price 33.9 per kg (estimated)

Items behind `pasta-spaghetti` (up to 3 per chain, cheapest unit price first):
- shufersal: ספגטי 500 גרם MANTINI, shelf 6.9, unit price 0.5 per 100g
- shufersal: ספגטי 500 גרם, shelf 4.9, unit price 0.55 per 100g
- shufersal: ספגטי 500 גרם MANTINI, shelf 7.9, unit price 0.6667 per 100g
- king_store: ספגטי 500 ג' ויליפוד, shelf 4.5, unit price 0.9 per 100g
- king_store: ספגטי 500 ג' ויליפוד, shelf 4.5, unit price 0.9 per 100g
- king_store: פרפקטו ספגטי 500 ג' אסם, shelf 8.5, unit price 1.39 per 100g
- ramilevy: פסטה ספגטי 500 גר wb, shelf 4, unit price 0.5 per 100g
- ramilevy: פסטה ספגטי 500 גר wb, shelf 4, unit price 0.5 per 100g
- ramilevy: פסטה ספגטי 500 גר wb, shelf 4, unit price 0.5 per 100g
- osherad: פסטה ספגטי מונו פוד, shelf 2.9, unit price 0.58 per 100g
- osherad: פסטה ספגטי מונו פוד, shelf 2.9, unit price 0.58 per 100g
- osherad: פסטה ספגטי מונו פוד, shelf 2.9, unit price 0.58 per 100g
- yohananof: פסטה ספגטי ריסקוסה 5, shelf 5.9, unit price 0.75 per 100g
- yohananof: פסטה ספגטי ריסקוסה 5, shelf 5.9, unit price 0.75 per 100g
- yohananof: פסטה ספגטי ריסקוסה 5, shelf 4.9, unit price 0.75 per 100g
- tivtaam: ספגטי (3) 500 גרם, shelf 6.5, unit price 1.3 per 100g
- tivtaam: ספגטי (3) 500 גרם, shelf 6.5, unit price 1.3 per 100g
- tivtaam: ספגטי (3) 500 גרם, shelf 6.5, unit price 1.3 per 100g

### SEO export, production semantics

| | |
|---|---|
| Pages generated | 200 (70 category, 130 product) |
| Canonicals priced / unpriced | 191 / 54 |
| Product pages priced / unpriced | 108 / 22 |
| Price cells (chain x product), of them estimated | 700, 154 |
| Chains per priced product | 1 chain(s): 34, 2 chain(s): 26, 3 chain(s): 27, 4 chain(s): 24, 5 chain(s): 43, 6 chain(s): 37 |
| Error-level findings | 0 |
| Findings by code | basket_line 1, withheld 4 |

Basket index 2026-10: **draft**, 0 of 6 chains rank (price every one of 25 lines), spread None%.

| Chain | Lines priced | Total |
|---|---|---|
| שופרסל | 17 of 25 | - |
| קינג סטור | 10 of 25 | - |
| רמי לוי | 18 of 25 | - |
| אושר עד | 12 of 25 | - |
| יוחננוף | 12 of 25 | - |
| טיב טעם | 13 of 25 | - |

| Level | Check | Message |
|---|---|---|
| warning | missing_items | שופרסל has no price for 8 basket items (yellow-cheese-sliced-28, butter, eggs-l, cucumber, banana, pita, bamba, chocolate-milk); it is listed but not ranked |
| warning | estimated_items | שופרסל: 4 lines use estimated weighed-goods prices |
| warning | missing_items | קינג סטור has no price for 15 basket items (cottage-5, yellow-cheese-sliced-28, butter, eggs-l, chicken-breast-fresh, hummus-plain, tomato, cucumber, banana, bread-standard, pita, pasta-spaghetti, tuna-in-oil, bamba, chocolate-milk); it is listed but not ranked |
| warning | estimated_items | קינג סטור: 2 lines use estimated weighed-goods prices |
| warning | missing_items | רמי לוי has no price for 7 basket items (butter, hummus-plain, cucumber, potato, banana, pasta-spaghetti, chocolate-milk); it is listed but not ranked |
| warning | estimated_items | רמי לוי: 3 lines use estimated weighed-goods prices |
| warning | missing_items | אושר עד has no price for 13 basket items (milk-fresh-3, white-cheese-5, yellow-cheese-sliced-28, yogurt-plain-3, eggs-l, hummus-plain, tomato, cucumber, pasta-spaghetti, sugar-white, bamba, chocolate-milk, toilet-paper); it is listed but not ranked |
| warning | estimated_items | אושר עד: 3 lines use estimated weighed-goods prices |
| warning | missing_items | יוחננוף has no price for 13 basket items (yellow-cheese-sliced-28, butter, eggs-l, hummus-plain, tomato, cucumber, potato, banana, pita, pasta-spaghetti, bamba, chocolate-milk, toilet-paper); it is listed but not ranked |
| warning | estimated_items | יוחננוף: 2 lines use estimated weighed-goods prices |
| warning | missing_items | טיב טעם has no price for 12 basket items (milk-fresh-3, yellow-cheese-sliced-28, yogurt-plain-3, butter, eggs-l, hummus-plain, pita, pasta-spaghetti, tuna-in-oil, mineral-water, bamba, chocolate-milk); it is listed but not ranked |
| warning | estimated_items | טיב טעם: 6 lines use estimated weighed-goods prices |
| error | line_outlier | mineral-water: אושר עד costs 67.73 against 9.94 at יוחננוף, 6.8 times (limit 4); read the unit prices and pack counts of the items behind it |
| error | too_few_chains | only 0 chain(s) price the whole basket; at least 2 needed |

| Code | Subject | Detail |
|---|---|---|
| withheld | mineral-water | אושר עד: chain_outlier (1.1288 against the chains' median 0.1767) |
| withheld | salt | יוחננוף: chain_outlier (0.1800 against the chains' median 0.7900) |
| withheld | soup-powder-chicken | רמי לוי: chain_outlier (1.1900 against the chains' median 4.9750) |
| withheld | rice-brown | רמי לוי: store_outlier (store 123: 5.4000 against 0.9400) |
| basket_line | mineral-water | אושר עד 67.73 against יוחננוף 9.94 |

### SEO export, stress

| | |
|---|---|
| Pages generated | 200 (70 category, 130 product) |
| Canonicals priced / unpriced | 237 / 8 |
| Product pages priced / unpriced | 128 / 2 |
| Price cells (chain x product), of them estimated | 1141, 234 |
| Chains per priced product | 1 chain(s): 13, 2 chain(s): 18, 3 chain(s): 19, 4 chain(s): 21, 5 chain(s): 45, 6 chain(s): 121 |
| Error-level findings | 0 |
| Findings by code | basket_line 1, withheld 8 |

Basket index 2026-10: **draft**, 3 of 6 chains rank (price every one of 25 lines), spread 25.7%.

| Chain | Lines priced | Total |
|---|---|---|
| רמי לוי | 25 of 25 | 275.55 |
| שופרסל | 25 of 25 | 343.89 |
| טיב טעם | 25 of 25 | 346.36 |
| קינג סטור | 23 of 25 | - |
| אושר עד | 24 of 25 | - |
| יוחננוף | 24 of 25 | - |

| Level | Check | Message |
|---|---|---|
| warning | estimated_items | רמי לוי: 6 lines use estimated weighed-goods prices |
| warning | estimated_items | שופרסל: 6 lines use estimated weighed-goods prices |
| warning | estimated_items | טיב טעם: 6 lines use estimated weighed-goods prices |
| warning | missing_items | קינג סטור has no price for 2 basket items (bread-standard, tuna-in-oil); it is listed but not ranked |
| warning | estimated_items | קינג סטור: 6 lines use estimated weighed-goods prices |
| warning | missing_items | אושר עד has no price for 1 basket items (toilet-paper); it is listed but not ranked |
| warning | estimated_items | אושר עד: 5 lines use estimated weighed-goods prices |
| warning | missing_items | יוחננוף has no price for 1 basket items (toilet-paper); it is listed but not ranked |
| warning | estimated_items | יוחננוף: 6 lines use estimated weighed-goods prices |
| error | line_outlier | chicken-breast-fresh: קינג סטור costs 39.90 against 8.90 at אושר עד, 4.5 times (limit 4); read the unit prices and pack counts of the items behind it |

| Code | Subject | Detail |
|---|---|---|
| withheld | salmon-fillet-fresh | קינג סטור: store_outlier (store 23: 10.0000 against 79.9000) |
| withheld | mushrooms-fresh | רמי לוי: chain_outlier (1.2250 against the chains' median 5.1600) |
| withheld | chicken-whole-frozen | טיב טעם: chain_outlier (99.9000 against the chains' median 24.9000) |
| withheld | chicken-ground-fresh | שופרסל: store_outlier (store 454: 6.9000 against 39.9000) |
| withheld | chicken-ground-fresh | טיב טעם: store_outlier (store 627: 45.9000 against 6.9000) |
| withheld | turkey-breast-fresh | טיב טעם: store_outlier (store 594: 9.9000 against 89.0000) |
| withheld | cauliflower | יוחננוף: chain_outlier (85.0000 against the chains' median 17.4000) |
| withheld | rice-brown | רמי לוי: store_outlier (store 159: 6.3571 against 0.9900) |
| basket_line | chicken-breast-fresh | קינג סטור 39.90 against אושר עד 8.90 |

### Basket lines that no chain prices: the real items that could have been them

Items whose names mention the product, with the attributes extraction gave them, the mapping they got and the rule judge's own reason (re-run for this report, nothing written). The `hint` columns are a reading aid of this script, not the catalog's rules.

#### `butter`: 60 listed of 252 name hits (0 skipped as not the food itself; chains looked in: shufersal, king_store, ramilevy, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | חמאה רכה 250 גרם | ? / ? | butter | 250 g | butter close 0.89 review | review: butter (חמאה): similarity 0.61 \| critical match product_type=butter \| soft differs pack_size 250 vs 200 g \| level close, confidence 0.89 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.13 \| critical mismatch product |
| shufersal | חמאה מלוחה רכה 250גרם | ? / ? | butter | 250 g | butter close 0.81 review | review: butter (חמאה): similarity 0.52 \| critical match product_type=butter \| soft differs pack_size 250 vs 200 g \| level close, confidence 0.81 \| vetoed: grated-mozzarella (גבינה מגורדת (מוצרלה)): similarity 0.13 \| critical misma |
| shufersal | חמאה לה גל זהב 200 גרם | ? / ? | butter | 200 g | butter any_brand 0.76 review | review: butter (חמאה): similarity 0.46 \| critical match product_type=butter \| level any_brand, confidence 0.76 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.13 \| critical mismatch product_type butter vs sour_cream \| criti |
| shufersal | חמאה לה גל זהב עם מלח200 | ? / ? | butter | 200 g | butter any_brand 0.78 review | review: butter (חמאה): similarity 0.47 \| critical match product_type=butter \| level any_brand, confidence 0.78 \| vetoed: pudding-chocolate-cream (מעדן שוקולד עם קצפת): similarity 0.11 \| critical mismatch product_type butter vs pud |
| shufersal | חמאה 60% אלוויר 200 גרם | ? / ? | butter | 200 g | butter any_brand 0.75 review | review: butter (חמאה): similarity 0.44 \| critical match product_type=butter \| level any_brand, confidence 0.75 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.10 \| critical mismatch product_type butter vs sour_cream; fat_pc |
| shufersal | סוכריות חמאה וורטר135גרם | ? / ? | butter | 135 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.44 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; sour-cream-15 (שמנת חמוצה 15%): similarity 0.08 |
| shufersal | סוכריות חמאה לל"ס80 ורטר | ? / ? | butter | 80 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.42 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; yogurt-strawberry (יוגורט תות): similarity 0.13 |
| shufersal | סוכריות חמאה 50 גרם ורטר | ? / ? | butter | 50 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.43 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; yogurt-strawberry (יוגורט תות): similarity 0.16 |
| shufersal | חמאה FERMA 82.5%גרם 200 | ? / ? | butter | 200 g | butter any_brand 0.75 review | review: butter (חמאה): similarity 0.43 \| critical match product_type=butter \| level any_brand, confidence 0.75 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.10 \| critical mismatch product_type butter vs sour_cream; fat_pc |
| shufersal | ביסקויט לקפה חמאה185רושן | ? / ? | butter | 185 g | butter close 0.63 review | review: butter (חמאה): similarity 0.29 \| critical match product_type=butter \| soft differs pack_size 185 vs 200 g \| level close, confidence 0.63 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.08 \| critical mismatch product |
| shufersal | חמאה 82.5% רושן 200 גרם | ? / ? | butter | 200 g | butter any_brand 0.74 review | review: butter (חמאה): similarity 0.43 \| critical match product_type=butter \| level any_brand, confidence 0.74 \| vetoed: labane-5 (לבנה 5%): similarity 0.25 \| critical mismatch product_type butter vs labane; fat_pct 82.5 vs 5 ; co |
| shufersal | הוטפופ טעם חמאה6*100גר | ? / ? | butter | 600 g | butter close 0.61 review | review: butter (חמאה): similarity 0.26 \| critical match product_type=butter \| soft differs pack_size 600 vs 200 g \| level close, confidence 0.61 \| vetoed: yogurt-plain-1-5 (יוגורט טבעי 1.5%): similarity 0.05 \| critical mismatch pr |
| king_store | סוכריות וורטר חמאה 400 ג' וורטר | ? / ? | butter | 400 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.33 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; yogurt-strawberry (יוגורט תות): similarity 0.16 |
| king_store | פופ קורן בטעם חמאה 600 ג' | ? / ? | - | 600 g | - | rejected (confidence 0.24 < 0.6): cornflakes (קורנפלקס): similarity 0.19 \| critical unknown product_type \| soft differs pack_size 600 vs 750 g \| level close, confidence 0.24 \| vetoed: butter (חמאה): similarity 0.42 \| critical mism |
| king_store | ממרח עוגיות חמאה 300 ג' CHOCOLAKE | ? / ? | - | 300 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.37 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'חמאה' \| critical unknown product_type ; chocolate-spread (ממרח שוקולד): similarity 0.25 \| cri |
| king_store | פופקו חטיף בטעם חמאה 80 ג' אסם | ? / ? | - | 80 g | - | rejected (confidence 0.29 < 0.6): bamba (חטיף בוטנים (במבה)): similarity 0.31 \| critical unknown product_type \| level any_brand, confidence 0.29 \| vetoed: butter (חמאה): similarity 0.40 \| critical mismatch name has 'חטיף' (a deriv |
| king_store | חמישייה פופקורן חמאה למיקרוגל 500 ג' פופ סטואר | ? / ? | butter | 500 g | butter close 0.66 review | review: butter (חמאה): similarity 0.33 \| critical match product_type=butter \| soft differs pack_size 500 vs 200 g \| level close, confidence 0.66 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.12 \| critical mismatch product |
| king_store | מרגרינה בטעם חמאה 200 ג' שמרית | ? / ? | margarine | 200 g | margarine close 0.85 review | review: margarine (מרגרינה): similarity 0.56 \| critical match product_type=margarine \| soft differs pack_size 200 vs 250 g \| level close, confidence 0.85 \| vetoed: butter (חמאה): similarity 0.42 \| critical mismatch product_type ma |
| king_store | תרסיס שמן קנולה בטעם חמאה 200 מ"ל עץ הזית | ? / ? | canola_oil | 200 ml | canola-oil close 0.79 review | review: canola-oil (שמן קנולה): similarity 0.49 \| critical match product_type=canola_oil \| soft differs pack_size 200 vs 1000 ml \| level close, confidence 0.79 \| vetoed: olive-oil (שמן זית כתית מעולה): similarity 0.30 \| critical m |
| king_store | חמאה עלמה 200ג' | ? / ? | butter | 200 g | butter any_brand 0.88 review | review: butter (חמאה): similarity 0.60 \| critical match product_type=butter \| level any_brand, confidence 0.88 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.13 \| critical mismatch product_type butter vs white_cheese \| cri |
| king_store | עוגיות חמאה סנדוויץ מילוי טעם שוקולד 188  ג' צ'וקטה | ? / ? | - | 188 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.33 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'חמאה' \| critical unknown product_type ; chocolate-spread (ממרח שוקולד): similarity 0.28 \| cri |
| king_store | עוגיות חמאה סנדוויץ מילוי טעם וניל 188  ג' צ'וקטה | ? / ? | - | 188 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.33 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'חמאה' \| critical unknown product_type ; vanilla-sugar (סוכר וניל): similarity 0.26 \| critical |
| king_store | מארז פופקורן חמאה ודבש מארז 12*20 ג' אסם | ? / ? | butter | 240 g | butter close 0.66 review | review: butter (חמאה): similarity 0.33 \| critical match product_type=butter \| soft differs pack_size 240 vs 200 g \| level close, confidence 0.66 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.08 \| critical mismatch product |
| king_store | סוכריות טעם חמאה  400 ג' פסטוס | ? / ? | butter | 400 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.35 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; cream-cheese-30-plain (גבינת שמנת 30% טבעית): s |
| ramilevy | סוכריות בטעם חמאה לל | ? / ? | - | 1 unit | - | every candidate vetoed \| vetoed: rolls (לחמניות): similarity 0.20 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'לחמניות'; the canonical's words come only after 'בטעם' (a flavor, not the product) \| criti |
| ramilevy | פאם בטעם חמאה | ? / ? | - | -  | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.56 \| critical mismatch the canonical's words come only after 'בטעם' (a flavor, not the product) \| critical unknown product_type ; flavored-water-lemon (מים בטעם לימון):  |
| ramilevy | הוט חמאה 600 ג') ב(1 | ? / ? | butter | 600 g | butter close 0.79 review | review: butter (חמאה): similarity 0.49 \| critical match product_type=butter \| soft differs pack_size 600 vs 200 g \| level close, confidence 0.79 \| vetoed: yogurt-plain-1-5 (יוגורט טבעי 1.5%): similarity 0.18 \| critical mismatch pr |
| ramilevy | בצק עלים חמאה מעדנות | ? / ? | butter | -  | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.53 \| critical mismatch name has 'בצק' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; dessert-vanilla (מעדן חלב וניל): similarity 0.19 \|  |
| ramilevy | מרגרינה בטעם חמאה 20 | ? / ? | margarine | -  | margarine any_brand 0.89 review | review: margarine (מרגרינה): similarity 0.62 \| critical match product_type=margarine \| level any_brand, confidence 0.89 \| vetoed: butter (חמאה): similarity 0.53 \| critical mismatch product_type margarine vs butter; the canonical's |
| ramilevy | חמאה מפינלנד 200 ג ל | ? / ? | butter | 200 g | butter any_brand 0.76 review | review: butter (חמאה): similarity 0.45 \| critical match product_type=butter \| level any_brand, confidence 0.76 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.10 \| critical mismatch product_type butter vs sour_cream \| criti |

#### `chocolate-milk`: 72 listed of 3475 name hits (0 skipped as not the food itself; chains looked in: shufersal, king_store, ramilevy, osherad, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | חטיף שיבולת ושוקולד5 | ? / ? | chocolate_bar | 210 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.31 \| critical mismatch flavor chocolate vs milk; name has 'חטיף' (a derived product), canonical is 'שוקולד חלב' \| critical match product_type=chocolate |
| shufersal | תערובת לעוגת שוקולד425גר | ? / ? | chocolate_bar | 425 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.32 \| critical mismatch flavor chocolate vs milk; name has 'עוגת' (a derived product), canonical is 'שוקולד חלב' \| critical match product_type=chocolate |
| shufersal | שוקולד אקסלנס קרמל100גרם | ? / ? | chocolate_bar | 100 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.40 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.38 \| criti |
| shufersal | שוקולד מריר לינדט מלח 10 | ? / ? | chocolate_bar | 100 g | - | every candidate vetoed \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.68 \| critical mismatch flavor dark+salted vs dark \| critical match product_type=chocolate_bar ; chocolate-milk-bar (שוקולד חלב): similarity 0.37 \| cri |
| shufersal | חט.שוקולד בוטנים39ג ריסז | ? / ? | chocolate_bar | 39 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.42 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.39 \| criti |
| shufersal | סירופ שוקולד 680 גרם | ? / ? | chocolate_bar | 680 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.44 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.43 \| criti |
| shufersal | שוקולד מריר עם מרציפן100 | ? / ? | chocolate_bar | 100 g | - | every candidate vetoed \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.70 \| critical mismatch flavor dark+other vs dark \| critical match product_type=chocolate_bar ; chocolate-milk-bar (שוקולד חלב): similarity 0.37 \| crit |
| shufersal | שוקולד חלב+אגוזי לוז 100 | ? / ? | chocolate_bar | 100 g | chocolate-milk-bar any_brand 0.92 | accept: chocolate-milk-bar (שוקולד חלב): similarity 0.65 \| critical match product_type=chocolate_bar, flavor=milk \| level any_brand, confidence 0.92 \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.39 \| critical mismatch f |
| shufersal | שוקולד ריטר מריר שקד100ג | ? / ? | chocolate_bar | 100 g | chocolate-dark-bar any_brand 0.96 | accept: chocolate-dark-bar (שוקולד מריר): similarity 0.70 \| critical match product_type=chocolate_bar, flavor=dark \| level any_brand, confidence 0.96 \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.40 \| critical mismatch f |
| shufersal | קורני חט.דגנים+שוקולד6יח | ? / ? | - | 150 g | - | rejected (confidence 0.42 < 0.6): dessert-chocolate (מעדן חלב שוקולד): similarity 0.23 \| critical match flavor=chocolate \| critical unknown product_type \| soft differs pack_size 150 vs 125 g \| ambiguous with wafers-chocolate \| lev |
| shufersal | ח.דגנים שוקו.מריר6 קורני | ? / ? | - | 138 g | - | rejected (confidence 0.42 < 0.6): dessert-chocolate (מעדן חלב שוקולד): similarity 0.17 \| critical match flavor=chocolate \| critical unknown product_type \| soft differs pack_size 138 vs 125 g \| ambiguous with wafers-chocolate \| lev |
| shufersal | קורני FREE שוקולד חלב6יח | ? / ? | chocolate_bar | 120 g | chocolate-milk-bar close 0.83 review | review: chocolate-milk-bar (שוקולד חלב): similarity 0.54 \| critical match product_type=chocolate_bar, flavor=milk \| soft differs pack_size 120 vs 100 g \| level close, confidence 0.83 \| vetoed: chocolate-dark-bar (שוקולד מריר): sim |
| king_store | עוגיות אוזני המן בטעם שוקולד מרגרט בונג'ור | ? / ? | - | -  | - | every candidate vetoed \| vetoed: cherry-tomato (עגבניות שרי): similarity 0.15 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'עגבניות שרי'; the canonical's words come only after 'בטעם' (a flavor, not the p |
| king_store | מעדן סויה טעם שוקו אלפרו רביעיה 125 ג' | ? / ? | chocolate_milk | 125 g | - | every candidate vetoed \| vetoed: dessert-chocolate (מעדן חלב שוקולד): similarity 0.30 \| critical mismatch product_type chocolate_milk vs dairy_dessert \| critical unknown flavor ; pudding-chocolate-cream (מעדן שוקולד עם קצפת): simi |
| king_store | חטיף שוקולד 45 ג' אגוזי | ? / ? | chocolate_bar | 45 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.49 \| critical mismatch flavor chocolate vs milk; name has 'חטיף' (a derived product), canonical is 'שוקולד חלב' \| critical match product_type=chocolate |
| king_store | חטיף שוקולד 40 ג'טעמי | ? / ? | chocolate_bar | 40 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.46 \| critical mismatch flavor chocolate vs milk; name has 'חטיף' (a derived product), canonical is 'שוקולד חלב' \| critical match product_type=chocolate |
| king_store | חטיף שוקולד 28 ג' טוויסט | ? / ? | chocolate_bar | 28 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.41 \| critical mismatch flavor chocolate vs milk; name has 'חטיף' (a derived product), canonical is 'שוקולד חלב' \| critical match product_type=chocolate |
| king_store | מעדן שוקולד מהדרין 135 ג'  מילקי | ? / ? | pudding_with_cream | 135 g | pudding-chocolate-cream close 0.78 review | review: pudding-chocolate-cream (מעדן שוקולד עם קצפת): similarity 0.47 \| critical match product_type=pudding_with_cream, flavor=chocolate \| soft differs pack_size 135 vs 170 g \| level close, confidence 0.77 \| vetoed: dessert-choco |
| king_store | מילקי מיני שוקולד 70 ג' | ? / ? | chocolate_bar | 70 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.42 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.39 \| criti |
| king_store | מעדן שוקו 2% שומן 125 ג' באדי | ? / ? | chocolate_milk | 125 g | - | every candidate vetoed \| vetoed: dessert-chocolate (מעדן חלב שוקולד): similarity 0.41 \| critical mismatch product_type chocolate_milk vs dairy_dessert \| critical unknown flavor ; pudding-chocolate-cream (מעדן שוקולד עם קצפת): simi |
| king_store | מעדן חלב בטעם שוקולד 125 ג' דני | ? / ? | dairy_dessert | 125 g | dessert-chocolate any_brand 0.98 | accept: dessert-chocolate (מעדן חלב שוקולד): similarity 0.73 \| critical match product_type=dairy_dessert, flavor=chocolate \| level any_brand, confidence 0.98 \| vetoed: pudding-chocolate-cream (מעדן שוקולד עם קצפת): similarity 0.50 |
| king_store | גרדינה שוקולד לבן במילוי קרם אגוזים 38 ג' | ? / ? | chocolate_bar | 38 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.35 \| critical mismatch flavor white vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.29 \| critical  |
| king_store | ממרח שוקולד 750 ג' נוטלה | ? / ? | chocolate_spread | 750 g | chocolate-spread close 0.93 | accept: chocolate-spread (ממרח שוקולד): similarity 0.66 \| critical match product_type=chocolate_spread \| soft differs pack_size 750 vs 400 g \| level close, confidence 0.93 \| vetoed: granola (גרנולה): similarity 0.14 \| critical mis |
| king_store | קינדר שוקולד 50 ג' | ? / ? | chocolate_bar | 50 g | - | every candidate vetoed \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.48 \| critical mismatch flavor chocolate vs dark \| critical match product_type=chocolate_bar ; chocolate-milk-bar (שוקולד חלב): similarity 0.46 \| criti |
| ramilevy | קראנץ צדפים טעם שוקו | ? / ? | - | -  | - | rejected (confidence 0.41 < 0.6): chocolate-milk (שוקו): similarity 0.46 \| critical unknown product_type \| level any_brand, confidence 0.41 |
| ramilevy | טילון מגנום שוקולד ל | ? / ? | chocolate_bar | 1 unit | - | no candidates in block snacks / unit |
| ramilevy | שוקולד חלב בטעם מילק | ? / ? | chocolate_bar | -  | chocolate-milk-bar any_brand 0.97 | accept: chocolate-milk-bar (שוקולד חלב): similarity 0.71 \| critical match product_type=chocolate_bar, flavor=milk \| level any_brand, confidence 0.97 \| vetoed: wafers-chocolate (ופלים בטעם שוקולד): similarity 0.59 \| critical mismat |
| ramilevy | רביעיית שוקולד מריר | ? / ? | chocolate_bar | 4 unit | - | no candidates in block snacks / unit |
| ramilevy | נטיפי ציפס בטעם שוקו | ? / ? | - | -  | - | rejected (confidence 0.30 < 0.6): potato-chips-salted (צ'יפס תפוחי אדמה בטעם מלח): similarity 0.33 \| critical unknown product_type, flavor \| level any_brand, confidence 0.30 \| vetoed: chocolate-milk (שוקו): similarity 0.47 \| criti |
| ramilevy | פילסברי עוגת שוקולד | ? / ? | chocolate_bar | -  | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.46 \| critical mismatch flavor chocolate vs milk; name has 'עוגת' (a derived product), canonical is 'שוקולד חלב' \| critical match product_type=chocolate |

#### `cottage-5`: 7 listed of 7 name hits (0 skipped as not the food itself; chains looked in: king_store)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| king_store | קוטג תנובה גביע 250 גר5% | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.70 review | review: cottage-5 (קוטג' 5%): similarity 0.37 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.70 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.33 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' 5% שומן 250 ג' טרה | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.87 review | review: cottage-5 (קוטג' 5%): similarity 0.59 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.87 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.39 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' 5% 250 ג' תנובה | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.89 review | review: cottage-5 (קוטג' 5%): similarity 0.61 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.89 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.39 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' 9% שומן 250 ג' תנובה | ? / ? | cottage_cheese | 250 g | - | every candidate vetoed \| vetoed: cottage-5 (קוטג' 5%): similarity 0.38 \| critical mismatch fat_pct 9 vs 5 \| critical match product_type=cottage_cheese ; cottage-3 (קוטג' 3%): similarity 0.38 \| critical mismatch fat_pct 9 vs 3 \| cr |
| king_store | קוטג' 5% שומן 250 ג' שטראוס | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.84 review | review: cottage-5 (קוטג' 5%): similarity 0.55 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.84 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.37 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' בקטנה % 5 100 ג' תנובה | ? / ? | cottage_cheese | 100 g | - | rejected (confidence 0.51 < 0.6): cottage-5 (קוטג' 5%): similarity 0.36 \| critical match product_type=cottage_cheese \| critical unknown fat_pct \| soft differs pack_size 100 vs 250 g \| ambiguous with cottage-3 \| level close, confid |
| king_store | קוטג' 3% שומן 250 ג' תנובה | ? / ? | cottage_cheese | 250 g | cottage-3 any_brand 0.84 review | review: cottage-3 (קוטג' 3%): similarity 0.55 \| critical match product_type=cottage_cheese, fat_pct=3 \| level any_brand, confidence 0.84 \| vetoed: cottage-5 (קוטג' 5%): similarity 0.35 \| critical mismatch fat_pct 3 vs 5 \| critical |

#### `eggs-l`: 159 listed of 306 name hits (141 skipped as not the food itself; chains looked in: shufersal, king_store, osherad, yohananof, tivtaam)

Name hint of the size against what the item got (served = no review flag):

| size words in the name | result | items |
|---|---|---|
| ? | review | 8 |
| ? | unmapped | 78 |
| L | eggs-free-range-l any_brand | 2 |
| L | eggs-free-range-l close | 1 |
| L | eggs-l close | 2 |
| L | review | 23 |
| L | unmapped | 8 |
| M | eggs-m close | 2 |
| M | review | 24 |
| M | unmapped | 6 |
| S | unmapped | 1 |
| XL | review | 4 |

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | ביצים ארוזות XL 12יחידות | XL / 12 | eggs_xl | 12 unit | eggs-xl any_brand 0.81 review | review: eggs-xl (ביצים XL): similarity 0.51 \| critical match product_type=eggs_xl \| level any_brand, confidence 0.81 \| vetoed: eggs-m (ביצים M): similarity 0.36 \| critical mismatch product_type eggs_xl vs eggs_m ; eggs-l (ביצים L) |
| shufersal | 12 ביצי משק טריות L לסר | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.68 review | review: eggs-l (ביצים L): similarity 0.35 \| critical match product_type=eggs_l \| level any_brand, confidence 0.68 \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.43 \| critical mismatch product_type eggs_l vs eggs_free_rang |
| shufersal | 12 ביצי משק טריות M לסר | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.68 review | review: eggs-m (ביצים M): similarity 0.35 \| critical match product_type=eggs_m \| level any_brand, confidence 0.68 \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.28 \| critical mismatch product_type eggs_m vs eggs_free_rang |
| shufersal | ביצים ארוזות 18יח L | L / 18 | eggs_l | 18 unit | eggs-l close 0.92 | accept: eggs-l (ביצים L): similarity 0.65 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.92 \| vetoed: eggs-m (ביצים M): similarity 0.51 \| critical mismatch product_type eggs |
| shufersal | ביצים ארוזות 18יח M | M / 18 | eggs_m | 18 unit | eggs-m close 0.95 | accept: eggs-m (ביצים M): similarity 0.68 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.95 \| vetoed: eggs-l (ביצים L): similarity 0.45 \| critical mismatch product_type eggs |
| shufersal | ביצים אומגה3 12יחידות L | L / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.58 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.39 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| shufersal | ביצי חופש 12יח L | L / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 1.00 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.86 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 1.00 \| vetoed: eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs_free_ran |
| shufersal | ביצי חופש 12יח M | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.69 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs vs eggs_m ; egg |
| shufersal | 12ביצי אומגה3 M לסר | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.30 \| critical mismatch product_type eggs vs eggs_m ; eggs-free-range-l (ביצי חופש L): similarity 0.16 \| critical mismatch product_type eggs vs eggs_free_range_l ; egg |
| shufersal | נודלס ביצים 500 גרם | ? / ? | - | 500 g | - | rejected (confidence 0.34 < 0.6): egg-noodles (אטריות ביצים): similarity 0.37 \| critical unknown product_type \| level any_brand, confidence 0.34 |
| shufersal | איטריות ביצים אוריאנט500 | ? / ? | - | 500 g | - | rejected (confidence 0.50 < 0.6): egg-noodles (אטריות ביצים): similarity 0.57 \| critical unknown product_type \| level any_brand, confidence 0.50 |
| shufersal | ביצי שוקול.סוניק 3*20גרם | ? / 60 | - | 60 g | - | rejected (confidence 0.24 < 0.6): wafers-chocolate (ופלים בטעם שוקולד): similarity 0.25 \| critical unknown product_type, flavor \| soft differs pack_size 60 vs 500 g \| ambiguous with chocolate-milk-bar \| level close, confidence 0.2 |
| shufersal | 12ביצים חופש אורגניות M | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.43 \| critical mismatch product_type eggs vs eggs_m ; eggs-free-range-l (ביצי חופש L): similarity 0.36 \| critical mismatch product_type eggs vs eggs_free_range_l ; egg |
| shufersal | 12ביצי חופש אורגניLגרין | L / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.13 \| critical mismatch product_type eggs vs eggs_xl ;  |
| shufersal | ביצים אומגה L שופרסל 6יח | L / 6 | eggs | 6 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.56 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.39 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| shufersal | 12ביצים אורגנ.L+אומגה3 | L / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.40 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarity 0.28 \| critical mismatch product_type eggs vs eggs_xl ; eggs-free-range-l (ביצי חו |
| shufersal | ביצים ארוזות L 12 יחידות | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.84 review | review: eggs-l (ביצים L): similarity 0.55 \| critical match product_type=eggs_l \| level any_brand, confidence 0.84 \| vetoed: eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| shufersal | ביצים ארוזות M 12 יחידות | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.86 review | review: eggs-m (ביצים M): similarity 0.58 \| critical match product_type=eggs_m \| level any_brand, confidence 0.86 \| vetoed: eggs-l (ביצים L): similarity 0.37 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| shufersal | ביצים ארוזות M 30 יחידות | M / 30 | eggs_m | 30 unit | eggs-m close 0.87 review | review: eggs-m (ביצים M): similarity 0.59 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.87 \| vetoed: eggs-l (ביצים L): similarity 0.38 \| critical mismatch product_type eggs |
| shufersal | ביצים ארוזות L 12 יחידות | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.84 review | review: eggs-l (ביצים L): similarity 0.55 \| critical match product_type=eggs_l \| level any_brand, confidence 0.84 \| vetoed: eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| shufersal | ביצים ארוזות M 12 יחידות | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.86 review | review: eggs-m (ביצים M): similarity 0.58 \| critical match product_type=eggs_m \| level any_brand, confidence 0.86 \| vetoed: eggs-l (ביצים L): similarity 0.37 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| shufersal | ביצת ממתקים | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): facial-tissues (ממחטות נייר): similarity 0.13 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| king_store | מארז ביצים חופש 30 L | L / 30 | eggs_free_range_l | 30 unit | eggs-free-range-l close 0.90 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.63 \| critical match product_type=eggs_free_range_l \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.90 \| vetoed: eggs-l (ביצים L): similarity 0.63 \| critical  |
| king_store | ביצים 18 יח' L לסר | L / 18 | eggs_l | 18 unit | eggs-l close 0.95 | accept: eggs-l (ביצים L): similarity 0.68 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.95 \| vetoed: eggs-m (ביצים M): similarity 0.48 \| critical mismatch product_type eggs |
| king_store | ביצים מידיום 30 יח' | ? / 30 | eggs_m | 30 unit | eggs-m close 0.79 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs |
| king_store | ביצים S 30 יח' | S / 30 | eggs | 30 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.53 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.53 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| king_store | ביצים אריזון M  חופש 12 יח' ביצי כפר | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.59 \| critical mismatch product_type eggs vs eggs_m ; eggs-free-range-l (ביצי חופש L): similarity 0.57 \| critical mismatch product_type eggs vs eggs_free_range_l ; egg |
| king_store | ביצים מידיום 12 יח' | ? / 12 | eggs_m | 12 unit | eggs-m any_brand 0.78 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| level any_brand, confidence 0.78 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| king_store | ביצי הכפר ביצים אורגניות 12יח' L | L / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.61 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarity 0.49 \| critical mismatch product_type eggs vs eggs_xl ; eggs-m (ביצים M): similari |
| king_store | ביצים לארג' 15 יח' | ? / 15 | eggs_l | 15 unit | eggs-l close 0.80 review | review: eggs-l (ביצים L): similarity 0.50 \| critical match product_type=eggs_l \| soft differs pack_size 15 vs 12 unit \| level close, confidence 0.80 \| vetoed: eggs-m (ביצים M): similarity 0.50 \| critical mismatch product_type eggs |
| king_store | איטריות ביצים פפרדלה 250ג' ברילה | ? / ? | - | 250 g | - | rejected (confidence 0.28 < 0.6): mushrooms-fresh (פטריות שמפיניון טריות): similarity 0.30 \| critical unknown product_type, state \| level any_brand, confidence 0.28 |
| king_store | נודלס ביצים להקפצה מאסטר שף 400 ג' | ? / ? | - | 400 g | - | rejected (confidence 0.26 < 0.6): egg-noodles (אטריות ביצים): similarity 0.28 \| critical unknown product_type \| soft differs pack_size 400 vs 500 g \| ambiguous with pickled-cucumbers \| level close, confidence 0.26 |
| king_store | לקט ירקות 400 ג' veggers | ? / ? | - | 400 g | - | rejected (confidence 0.24 < 0.6): fish-fingers (אצבעות דגים): similarity 0.11 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| king_store | ביצים מידיום עטוף 30יח' | ? / 30 | eggs_m | 30 unit | eggs-m close 0.73 review | review: eggs-m (ביצים M): similarity 0.41 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.73 \| vetoed: eggs-l (ביצים L): similarity 0.41 \| critical mismatch product_type eggs |
| king_store | ביצים לארג' 12 יח' | ? / 12 | eggs_l | 12 unit | eggs-l any_brand 0.79 review | review: eggs-l (ביצים L): similarity 0.49 \| critical match product_type=eggs_l \| level any_brand, confidence 0.79 \| vetoed: eggs-m (ביצים M): similarity 0.49 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| king_store | ביצים מידיום 12 יח' | ? / 12 | eggs_m | 12 unit | eggs-m any_brand 0.78 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| level any_brand, confidence 0.78 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| osherad | ביצים 2*30 יח' בינונ | M / 60 | eggs_m | 60 unit | eggs-m close 0.79 review | review: eggs-m (ביצים M): similarity 0.49 \| critical match product_type=eggs_m \| soft differs pack_size 60 vs 12 unit \| level close, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.49 \| critical mismatch product_type eggs |
| osherad | ביצים 18 יח גדול לסר | L / 18 | eggs_l | 18 unit | eggs-l close 0.76 review | review: eggs-l (ביצים L): similarity 0.45 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.76 \| vetoed: eggs-m (ביצים M): similarity 0.45 \| critical mismatch product_type eggs |
| osherad | ביצים 18 יח בינוני ל | M / 18 | eggs_m | 18 unit | eggs-m close 0.78 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.78 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs |
| osherad | ביצים 12 יח בינוני ר | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.77 review | review: eggs-m (ביצים M): similarity 0.46 \| critical match product_type=eggs_m \| level any_brand, confidence 0.77 \| vetoed: eggs-l (ביצים L): similarity 0.46 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| osherad | ביצים 18 יח' בינוני | M / 18 | eggs_m | 18 unit | eggs-m close 0.81 review | review: eggs-m (ביצים M): similarity 0.51 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.81 \| vetoed: eggs-l (ביצים L): similarity 0.51 \| critical mismatch product_type eggs |
| osherad | ביצים 30 יח' בינוני | M / 30 | eggs_m | 30 unit | eggs-m close 0.80 review | review: eggs-m (ביצים M): similarity 0.50 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.80 \| vetoed: eggs-l (ביצים L): similarity 0.50 \| critical mismatch product_type eggs |
| osherad | ביצים 30 יח' גדול מן | L / 30 | eggs_l | 30 unit | eggs-l close 0.76 review | review: eggs-l (ביצים L): similarity 0.45 \| critical match product_type=eggs_l \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.76 \| vetoed: eggs-m (ביצים M): similarity 0.45 \| critical mismatch product_type eggs |
| osherad | ביצים 18 יח' גדול מן | L / 18 | eggs_l | 18 unit | eggs-l close 0.77 review | review: eggs-l (ביצים L): similarity 0.46 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.77 \| vetoed: eggs-m (ביצים M): similarity 0.46 \| critical mismatch product_type eggs |
| osherad | ביצים אורגני 12 יח' | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.47 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.44 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| osherad | ביצי חופש 20 יח' גדו | ? / 20 | eggs | 20 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.62 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.25 \| critical mismatch product_type eggs vs eggs_xl ;  |
| osherad | ביצי אומגה 30 יח' בי | ? / 30 | eggs | 30 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.36 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.28 \| critical mismatch product_type eggs vs eggs_xl ;  |
| osherad | ביצי חופש 20 יח' גדו | ? / 20 | eggs | 20 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.62 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.25 \| critical mismatch product_type eggs vs eggs_xl ;  |
| osherad | ג'ל ביצת עין וס.קופצ | ? / ? | - | 98 g | - | rejected (confidence 0.24 < 0.6): cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.16 \| critical unknown product_type, fat_pct, flavor \| soft differs pack_size 98 vs 200 g \| ambiguous with couscous \| level close, confide |
| osherad | פורס ביצים אולינהום | ? / ? | - | -  | - | rejected (confidence 0.45 < 0.6): eggs-l (ביצים L): similarity 0.51 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.45 |
| osherad | ג'ל ביצת עין וס.קופצ | ? / ? | - | 168 g | - | rejected (confidence 0.24 < 0.6): cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.16 \| critical unknown product_type, fat_pct, flavor \| soft differs pack_size 168 vs 200 g \| ambiguous with couscous \| level close, confid |
| osherad | ביצים אומגה 30 יח גד | ? / 30 | eggs | 30 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.43 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.43 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| osherad | ביצים אומגה 12 יח גד | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| osherad | ביצים אומגה 12 יח' ב | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.44 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| osherad | ביצים אורגניות  12 י | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| osherad | ביצים 12 יח ענק XL ל | XL / 12 | eggs_xl | 12 unit | eggs-xl any_brand 0.86 review | review: eggs-xl (ביצים XL): similarity 0.57 \| critical match product_type=eggs_xl \| level any_brand, confidence 0.86 \| vetoed: eggs-m (ביצים M): similarity 0.35 \| critical mismatch product_type eggs_xl vs eggs_m ; eggs-l (ביצים L) |
| osherad | ביצים 12 יח' בינוני | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.79 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| level any_brand, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| osherad | ביצי אומגה 30 יח' גד | ? / 30 | eggs | 30 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.28 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.22 \| critical mismatch product_type eggs vs eggs_xl ;  |
| osherad | ביצים 12 יח' גדול זג | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.74 review | review: eggs-l (ביצים L): similarity 0.42 \| critical match product_type=eggs_l \| level any_brand, confidence 0.74 \| vetoed: eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| osherad | ביצים 30 יח בינוני ל | M / 30 | eggs_m | 30 unit | eggs-m close 0.78 review | review: eggs-m (ביצים M): similarity 0.47 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.78 \| vetoed: eggs-l (ביצים L): similarity 0.47 \| critical mismatch product_type eggs |
| osherad | מארז ביצים בינוני 2* | M / ? | eggs_m | 60 unit | eggs-m close 0.79 review | review: eggs-m (ביצים M): similarity 0.49 \| critical match product_type=eggs_m \| soft differs pack_size 60 vs 12 unit \| level close, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.49 \| critical mismatch product_type eggs |
| osherad | ביצים 12 יח' ענק א. | XL / 12 | eggs_xl | 12 unit | eggs-xl any_brand 0.72 review | review: eggs-xl (ביצים XL): similarity 0.40 \| critical match product_type=eggs_xl \| level any_brand, confidence 0.72 \| vetoed: eggs-m (ביצים M): similarity 0.45 \| critical mismatch product_type eggs_xl vs eggs_m ; eggs-l (ביצים L) |
| yohananof | ביצי דג שיבוט 200 גר | ? / ? | - | 200 g | - | rejected (confidence 0.24 < 0.6): rolled-oats (שיבולת שועל): similarity 0.23 \| critical unknown product_type \| soft differs pack_size 200 vs 500 g \| ambiguous with green-beans-frozen \| level close, confidence 0.24 |
| yohananof | ביצים 12 יח גדול | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.79 review | review: eggs-l (ביצים L): similarity 0.49 \| critical match product_type=eggs_l \| level any_brand, confidence 0.79 \| vetoed: eggs-m (ביצים M): similarity 0.49 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| yohananof | ביצים 12 יח בינוני | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.79 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| level any_brand, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| yohananof | ביצים אורגני 12 יח ג | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.41 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצים אורגני 12 יח ב | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.45 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.43 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצים אומגה 3 30 יח | ? / 30 | eggs | 30 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.43 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.43 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצים אומגה 30 יח גד | ? / 30 | eggs | 30 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.43 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.43 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצים ישר מהלול לבן | ? / ? | eggs | 1 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.57 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.47 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצים אומגה 3  12 יח | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצי חופש 12 יח גדול | L / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 0.89 review | review: eggs-free-range-l (ביצי חופש L): similarity 0.61 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 0.89 \| vetoed: eggs-xl (ביצים XL): similarity 0.22 \| critical mismatch product_type eggs_free_r |
| yohananof | ביצי חופש 12 יח בינו | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.65 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.28 \| critical mismatch product_type eggs vs eggs_xl ;  |
| yohananof | ביצים 30 יח בינוני | M / 30 | eggs_m | 30 unit | eggs-m close 0.80 review | review: eggs-m (ביצים M): similarity 0.50 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.80 \| vetoed: eggs-l (ביצים L): similarity 0.50 \| critical mismatch product_type eggs |
| yohananof | פורס ביצים | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): parsley (פטרוזיליה): similarity 0.06 \| critical unknown product_type, state \| ambiguous with cling-wrap \| level any_brand, confidence 0.24 |
| yohananof | פורס ביצים כפול | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): parsley (פטרוזיליה): similarity 0.05 \| critical unknown product_type, state \| ambiguous with green-onion \| level any_brand, confidence 0.24 |
| yohananof | פורס ביצים BETTER | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): cling-wrap (ניילון נצמד): similarity 0.06 \| critical unknown product_type \| ambiguous with baguette \| level any_brand, confidence 0.24 |
| yohananof | ביצים 12 יח בינוני | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.79 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| level any_brand, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| yohananof | ביצים 12 יח  גדול | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.79 review | review: eggs-l (ביצים L): similarity 0.49 \| critical match product_type=eggs_l \| level any_brand, confidence 0.79 \| vetoed: eggs-m (ביצים M): similarity 0.49 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| yohananof | ביצים 30 יח בינוני | M / 30 | eggs_m | 30 unit | eggs-m close 0.80 review | review: eggs-m (ביצים M): similarity 0.50 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.80 \| vetoed: eggs-l (ביצים L): similarity 0.50 \| critical mismatch product_type eggs |
| yohananof | ביצים 12 יח גדול | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.79 review | review: eggs-l (ביצים L): similarity 0.49 \| critical match product_type=eggs_l \| level any_brand, confidence 0.79 \| vetoed: eggs-m (ביצים M): similarity 0.49 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| yohananof | ביצים 12 יח בינוני | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.79 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| level any_brand, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| yohananof | ביצים 18 יח גדול | L / 18 | eggs_l | 18 unit | eggs-l close 0.80 review | review: eggs-l (ביצים L): similarity 0.50 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.80 \| vetoed: eggs-m (ביצים M): similarity 0.50 \| critical mismatch product_type eggs |
| yohananof | ביצים 18 יח בינוני | M / 18 | eggs_m | 18 unit | eggs-m close 0.81 review | review: eggs-m (ביצים M): similarity 0.51 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.81 \| vetoed: eggs-l (ביצים L): similarity 0.51 \| critical mismatch product_type eggs |
| yohananof | ביצים אורגני 12 יח ג | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.41 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצים אומגה 12 יח גד | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצי חופש 12 יח גדול | L / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 0.89 review | review: eggs-free-range-l (ביצי חופש L): similarity 0.61 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 0.89 \| vetoed: eggs-xl (ביצים XL): similarity 0.22 \| critical mismatch product_type eggs_free_r |
| yohananof | ביצי חופש 12 יח בינו | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.65 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.28 \| critical mismatch product_type eggs vs eggs_xl ;  |
| yohananof | ביצים אומגה 12 יח בי | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.47 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.47 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצים 12 יח בינוני | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.79 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| level any_brand, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| yohananof | פורס ביצים סולתם | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): green-onion (בצל ירוק): similarity 0.05 \| critical unknown product_type, state \| ambiguous with cling-wrap \| level any_brand, confidence 0.24 |
| yohananof | מגירת ביצים נתלית אק | ? / ? | - | 160 g | - | rejected (confidence 0.37 < 0.6): egg-noodles (אטריות ביצים): similarity 0.41 \| critical unknown product_type \| soft differs pack_size 160 vs 500 g \| level close, confidence 0.37 |
| yohananof | ביצים 18 יח בינוני | M / 18 | eggs_m | 18 unit | eggs-m close 0.81 review | review: eggs-m (ביצים M): similarity 0.51 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.81 \| vetoed: eggs-l (ביצים L): similarity 0.51 \| critical mismatch product_type eggs |
| yohananof | ביצים 18 יח גדול | L / 18 | eggs_l | 18 unit | eggs-l close 0.80 review | review: eggs-l (ביצים L): similarity 0.50 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.80 \| vetoed: eggs-m (ביצים M): similarity 0.50 \| critical mismatch product_type eggs |
| yohananof | ביצים 12 יח ענק | XL / 12 | eggs_xl | 12 unit | eggs-xl any_brand 0.75 review | review: eggs-xl (ביצים XL): similarity 0.44 \| critical match product_type=eggs_xl \| level any_brand, confidence 0.75 \| vetoed: eggs-m (ביצים M): similarity 0.50 \| critical mismatch product_type eggs_xl vs eggs_m ; eggs-l (ביצים L) |
| yohananof | ביצים 30 יח גדול | L / 30 | eggs_l | 30 unit | eggs-l close 0.79 review | review: eggs-l (ביצים L): similarity 0.49 \| critical match product_type=eggs_l \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.79 \| vetoed: eggs-m (ביצים M): similarity 0.49 \| critical mismatch product_type eggs |
| yohananof | ביצי דג טונה אדמחוט | ? / ? | - | 85 g | - | rejected (confidence 0.33 < 0.6): tuna-in-oil (טונה בשמן): similarity 0.36 \| critical unknown product_type \| soft differs pack_size 85 vs 640 g \| ambiguous with tuna-in-water \| level close, confidence 0.33 |
| yohananof | ביצת עין 220 גרם | ? / ? | - | 220 g | - | rejected (confidence 0.24 < 0.6): cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.15 \| critical unknown product_type, fat_pct, flavor \| soft differs pack_size 220 vs 200 g \| ambiguous with sunflower-seeds \| level close, |
| yohananof | ביצים עלומות 200 גרם | ? / ? | - | 200 g | - | rejected (confidence 0.24 < 0.6): sunflower-seeds (גרעינים): similarity 0.17 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| tivtaam | ביצי דג חדקן מומלחים | ? / ? | - | 50 g | - | rejected (confidence 0.24 < 0.6): potato-chips-salted (צ'יפס תפוחי אדמה בטעם מלח): similarity 0.14 \| critical unknown product_type, flavor \| level any_brand, confidence 0.24 |
| tivtaam | ביצי דג פורל מומלחים מצוננים מפוסטר 90 ג | ? / ? | - | 90 g | - | rejected (confidence 0.24 < 0.6): pickled-cucumbers (מלפפונים חמוצים): similarity 0.25 \| critical unknown product_type \| soft differs pack_size 90 vs 560 g \| ambiguous with sunflower-seeds \| level close, confidence 0.24 |
| tivtaam | ביצי דג חדקן מומלחים | ? / ? | - | 100 g | - | rejected (confidence 0.24 < 0.6): egg-noodles (אטריות ביצים): similarity 0.20 \| critical unknown product_type \| soft differs pack_size 100 vs 500 g \| ambiguous with bread-multigrain \| level close, confidence 0.24 |
| tivtaam | מעדן בטעם ביצי דג פלטוס 100 גרם | ? / ? | dairy_dessert | 100 g | - | rejected (confidence 0.42 < 0.6): dessert-vanilla (מעדן חלב וניל): similarity 0.24 \| critical match product_type=dairy_dessert \| critical unknown flavor \| soft differs pack_size 100 vs 125 g \| ambiguous with dessert-chocolate \| le |
| tivtaam | ביצי דג טרוטונית אטלנטי חסילונים 180 גר | ? / ? | - | 180 g | - | rejected (confidence 0.24 < 0.6): egg-noodles (אטריות ביצים): similarity 0.23 \| critical unknown product_type \| soft differs pack_size 180 vs 500 g \| ambiguous with sunflower-seeds \| level close, confidence 0.24 |
| tivtaam | ביצי דג שיבוט מומלח מצונן 130 גר | ? / ? | - | 130 g | - | rejected (confidence 0.24 < 0.6): salt (מלח): similarity 0.21 \| critical unknown product_type \| soft differs pack_size 130 vs 1000 g \| ambiguous with matzah \| level close, confidence 0.24 \| vetoed: chickpeas-canned (גרגרי חומוס בש |
| tivtaam | ביצי דג זהבנון מומלח מצונן 130 גר | ? / ? | - | 130 g | - | rejected (confidence 0.24 < 0.6): matzah (מצות): similarity 0.19 \| critical unknown product_type \| soft differs pack_size 130 vs 1000 g \| ambiguous with salt \| level close, confidence 0.24 \| vetoed: tilapia-fillet-frozen (פילה אמנ |
| tivtaam | איקרה ביצי דג טרוטונית והרינג 180 גרם | ? / ? | - | 180 g | - | rejected (confidence 0.24 < 0.6): green-beans-frozen (שעועית ירוקה קפואה): similarity 0.16 \| critical unknown product_type, state \| soft differs pack_size 180 vs 800 g \| ambiguous with egg-noodles \| level close, confidence 0.24 |
| tivtaam | איקרה ביצי דג טרוטונית והרינג עם פורל וס | ? / ? | - | 180 g | - | rejected (confidence 0.24 < 0.6): green-beans-frozen (שעועית ירוקה קפואה): similarity 0.15 \| critical unknown product_type, state \| soft differs pack_size 180 vs 800 g \| ambiguous with frozen-pizza \| level close, confidence 0.24 \| |
| tivtaam | איקרה ביצי דג טרוטונית והרינג עם אבקדו | ? / ? | - | 180 g | - | rejected (confidence 0.24 < 0.6): laundry-powder (אבקת כביסה): similarity 0.18 \| critical unknown product_type \| soft differs pack_size 180 vs 3000 g \| ambiguous with egg-noodles \| level close, confidence 0.24 \| vetoed: soup-powde |
| tivtaam | נטוראה עוף וביצה 100% רכיבים טבעיים - 2 | ? / ? | - | -  | - | rejected (confidence 0.42 < 0.6): soup-powder-chicken (אבקת מרק עוף): similarity 0.18 \| critical match flavor=chicken \| critical unknown product_type \| level any_brand, confidence 0.42 |
| tivtaam | ביצי דג שיבוט 200 גרם יורו פוד | ? / ? | - | 200 g | - | rejected (confidence 0.24 < 0.6): sunflower-seeds (גרעינים): similarity 0.14 \| critical unknown product_type \| ambiguous with greek-yogurt-plain \| level any_brand, confidence 0.24 |
| tivtaam | ביצי דג מויבה במשקל | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): sweet-potato (בטטה): similarity 0.12 \| critical unknown product_type, state \| ambiguous with chicken-schnitzel-fresh \| level any_brand, confidence 0.24 |
| tivtaam | פורס ביצים נירוסטה | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): cling-wrap (ניילון נצמד): similarity 0.14 \| critical unknown product_type \| ambiguous with facial-tissues \| level any_brand, confidence 0.24 |
| tivtaam | שימורי ביצי דג מינטאי מעושן פמלי פק 185 | ? / ? | - | 185 g | - | rejected (confidence 0.29 < 0.6): smoked-salmon-sliced (סלמון מעושן פרוס): similarity 0.31 \| critical unknown product_type \| soft differs pack_size 185 vs 100 g \| level close, confidence 0.29 \| vetoed: sweet-corn-canned (תירס מתוק |
| tivtaam | איטריות ביצים 500 גרם Bechtle | ? / ? | - | 500 g | - | rejected (confidence 0.47 < 0.6): egg-noodles (אטריות ביצים): similarity 0.53 \| critical unknown product_type \| level any_brand, confidence 0.47 |
| tivtaam | איטריות ביצים רחבות 500 גרם Bechtle | ? / ? | - | 500 g | - | rejected (confidence 0.45 < 0.6): egg-noodles (אטריות ביצים): similarity 0.51 \| critical unknown product_type \| level any_brand, confidence 0.45 |
| tivtaam | איטריות ביצים קלאסי 500 גרם Bechtle | ? / ? | - | 500 g | - | rejected (confidence 0.43 < 0.6): egg-noodles (אטריות ביצים): similarity 0.49 \| critical unknown product_type \| level any_brand, confidence 0.43 |
| tivtaam | ביצים אריזון 12 גדול | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.74 review | review: eggs-l (ביצים L): similarity 0.43 \| critical match product_type=eggs_l \| level any_brand, confidence 0.74 \| vetoed: eggs-m (ביצים M): similarity 0.43 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| tivtaam | ביצים אריזון 12 בינוני | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.76 review | review: eggs-m (ביצים M): similarity 0.44 \| critical match product_type=eggs_m \| level any_brand, confidence 0.76 \| vetoed: eggs-l (ביצים L): similarity 0.44 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| tivtaam | ביצים אריזון 18 בינוני | M / 18 | eggs_m | 18 unit | eggs-m close 0.77 review | review: eggs-m (ביצים M): similarity 0.47 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.77 \| vetoed: eggs-l (ביצים L): similarity 0.47 \| critical mismatch product_type eggs |
| tivtaam | ביצים אומגה 3 30 יח L | L / 30 | eggs | 30 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.58 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.40 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| tivtaam | ביצים אורגניות 12 יח L | L / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.59 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| tivtaam | ביצים אומגה 3 12 יח L | L / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.58 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.40 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| tivtaam | ביצי חופש 12 יח L | L / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 1.00 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.83 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 1.00 \| vetoed: eggs-l (ביצים L): similarity 0.40 \| critical mismatch product_type eggs_free_ran |
| tivtaam | ביצי חופש 12 יח M | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.66 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-m (ביצים M): similarity 0.40 \| critical mismatch product_type eggs vs eggs_m ; egg |
| tivtaam | ביצים אומגה M 12 יח | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.62 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| tivtaam | טליאטלה ביצים 450 גרם | ? / ? | - | 450 g | - | rejected (confidence 0.34 < 0.6): egg-noodles (אטריות ביצים): similarity 0.38 \| critical unknown product_type \| soft differs pack_size 450 vs 500 g \| level close, confidence 0.35 |
| tivtaam | ביצי דג אלתית קוויאר במשקל | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): sweet-potato (בטטה): similarity 0.11 \| critical unknown product_type, state \| ambiguous with cauliflower \| level any_brand, confidence 0.24 |
| tivtaam | ביצי דגים 113 גר זכוכית | ? / ? | - | 113 g | - | rejected (confidence 0.28 < 0.6): fish-fingers (אצבעות דגים): similarity 0.30 \| critical unknown product_type \| soft differs pack_size 113 vs 400 g \| level close, confidence 0.28 |
| tivtaam | ביצי דגים 250 גר בזכוכית | ? / ? | - | 250 g | - | rejected (confidence 0.28 < 0.6): fish-fingers (אצבעות דגים): similarity 0.30 \| critical unknown product_type \| soft differs pack_size 250 vs 400 g \| level close, confidence 0.28 |
| tivtaam | ביצי דג אדום בצנצנת 200 גרם | ? / ? | - | 200 g | - | rejected (confidence 0.24 < 0.6): egg-noodles (אטריות ביצים): similarity 0.22 \| critical unknown product_type \| soft differs pack_size 200 vs 500 g \| ambiguous with bread-multigrain \| level close, confidence 0.24 |
| tivtaam | מנה אסייאתי נודלס ביצים להקפצה 400 מ.שף | ? / ? | - | 400 g | - | rejected (confidence 0.24 < 0.6): peas-canned (אפונה בשימורים): similarity 0.14 \| critical unknown product_type, state \| level any_brand, confidence 0.24 |
| tivtaam | L ביצי חופש יולק חלמון כתום 18 יחידות | L / 18 | eggs_free_range_l | 18 unit | eggs-free-range-l close 0.86 review | review: eggs-free-range-l (ביצי חופש L): similarity 0.57 \| critical match product_type=eggs_free_range_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.86 \| vetoed: eggs-l (ביצים L): similarity 0.29 \| critical  |
| tivtaam | L ביצי חופש יולק חלמון כתום 12 יחידות | L / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 0.86 review | review: eggs-free-range-l (ביצי חופש L): similarity 0.58 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 0.86 \| vetoed: eggs-l (ביצים L): similarity 0.27 \| critical mismatch product_type eggs_free_ran |
| tivtaam | פתיתי ביצים כוכבים אוריינט 400 גר | ? / ? | - | 400 g | - | rejected (confidence 0.24 < 0.6): chickpeas-canned (גרגרי חומוס בשימורים): similarity 0.19 \| critical unknown product_type, state \| level any_brand, confidence 0.24 |
| tivtaam | פתיתי ביצים ילדים 400 גר | ? / ? | - | 400 g | - | rejected (confidence 0.35 < 0.6): ptitim (פתיתים אפויים): similarity 0.39 \| critical unknown product_type \| soft differs pack_size 400 vs 500 g \| level close, confidence 0.35 |
| tivtaam | חותך ביצים ABS שחור | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): dill (שמיר): similarity 0.12 \| critical unknown product_type, state \| level any_brand, confidence 0.24 |
| tivtaam | כדור תה (ביצה) | ? / ? | tea_black | 1 unit | tea-black close 0.63 review | review: tea-black (תה שחור בשקיקים): similarity 0.29 \| critical match product_type=tea_black \| soft differs pack_size 1 vs 100 unit \| level close, confidence 0.63 |
| tivtaam | חותך ביצים 3 ב 1 | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): parsley (פטרוזיליה): similarity 0.07 \| critical unknown product_type, state \| ambiguous with green-onion \| level any_brand, confidence 0.24 |
| tivtaam | ביצי שליו 20 יח | ? / 20 | eggs | 20 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.37 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.27 \| critical mismatch product_type eggs vs eggs_xl ;  |
| tivtaam | בירה קרושוביצה  500 מ"ל פחית | ? / ? | lager_beer | 500 ml | lager-beer any_brand 0.68 review | review: lager-beer (בירה לאגר): similarity 0.35 \| critical match product_type=lager_beer \| level any_brand, confidence 0.68 \| vetoed: red-wine-dry (יין אדום יבש): similarity 0.00 \| critical mismatch product_type lager_beer vs red_ |
| tivtaam | ליקר בולס אדבוקט ליקר ביצים 700 מ"ל | ? / ? | - | 700 ml | - | rejected (confidence 0.25 < 0.6): lemon-lime-soda (משקה מוגז לימון-ליים): similarity 0.26 \| critical unknown product_type \| soft differs pack_size 700 vs 1500 ml \| ambiguous with flavored-water-lemon \| level close, confidence 0.25 |
| tivtaam | חותך ביצים F | ? / ? | - | 1 unit | - | rejected (confidence 0.50 < 0.6): eggs-l (ביצים L): similarity 0.57 \| critical unknown product_type \| soft differs pack_size 1 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.50 |
| tivtaam | ביצי דג אלתית גבנוני | ? / ? | - | 250 g | - | rejected (confidence 0.24 < 0.6): safed-cheese-5 (גבינה צפתית 5%): similarity 0.23 \| critical unknown product_type, fat_pct \| ambiguous with white-cheese-9 \| level any_brand, confidence 0.24 |
| tivtaam | ביצי דג פורל מומלחים | ? / ? | - | 250 g | - | rejected (confidence 0.24 < 0.6): pretzels (בייגלה): similarity 0.13 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| tivtaam | פריזר ביצה במשקל | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): chicken-schnitzel-fresh (שניצל עוף טרי (חזה פרוס)): similarity 0.20 \| critical unknown product_type, state \| ambiguous with beef-ground-fresh \| level any_brand, confidence 0.24 |
| tivtaam | ביצי דג אילתית 190 גר | ? / ? | - | 190 g | - | rejected (confidence 0.24 < 0.6): egg-noodles (אטריות ביצים): similarity 0.20 \| critical unknown product_type \| soft differs pack_size 190 vs 500 g \| ambiguous with green-beans-frozen \| level close, confidence 0.24 |
| tivtaam | ביצי דג אלתית אלסקה 500 גרם כשר | ? / ? | - | 500 g | - | rejected (confidence 0.24 < 0.6): egg-noodles (אטריות ביצים): similarity 0.19 \| critical unknown product_type \| ambiguous with frozen-pizza \| level any_brand, confidence 0.24 |
| tivtaam | ביצה פלוס 6 יח L | L / 6 | eggs_l | 6 unit | eggs-l close 0.67 review | review: eggs-l (ביצים L): similarity 0.34 \| critical match product_type=eggs_l \| soft differs pack_size 6 vs 12 unit \| level close, confidence 0.67 \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.30 \| critical mismatch pro |
| tivtaam | ביצה פלוס 12 יח L | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.65 review | review: eggs-l (ביצים L): similarity 0.32 \| critical match product_type=eggs_l \| level any_brand, confidence 0.65 \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.30 \| critical mismatch product_type eggs_l vs eggs_free_rang |
| tivtaam | ביצי חופש 12 יח | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.72 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.25 \| critical mismatch product_type eggs vs eggs_xl ;  |
| tivtaam | ביצים רגילות 12 יח L | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.87 review | review: eggs-l (ביצים L): similarity 0.59 \| critical match product_type=eggs_l \| level any_brand, confidence 0.87 \| vetoed: eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| tivtaam | ביצים רגילות  12 יח M | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.90 review | review: eggs-m (ביצים M): similarity 0.62 \| critical match product_type=eggs_m \| level any_brand, confidence 0.90 \| vetoed: eggs-l (ביצים L): similarity 0.38 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| tivtaam | ביצים אורגניות 12 יח | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| tivtaam | ביצה פלוס 30 יח M | M / 30 | eggs_m | 30 unit | eggs-m close 0.67 review | review: eggs-m (ביצים M): similarity 0.34 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.67 \| vetoed: eggs-xl (ביצים XL): similarity 0.16 \| critical mismatch product_type eg |
| tivtaam | ביצה פלוס 30 יח L | L / 30 | eggs_l | 30 unit | eggs-l close 0.67 review | review: eggs-l (ביצים L): similarity 0.34 \| critical match product_type=eggs_l \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.67 \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.30 \| critical mismatch pr |
| tivtaam | ביצים רגילות 18 יח L | L / 18 | eggs_l | 18 unit | eggs-l close 0.88 review | review: eggs-l (ביצים L): similarity 0.61 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.88 \| vetoed: eggs-m (ביצים M): similarity 0.46 \| critical mismatch product_type eggs |
| tivtaam | ביצים 18 יח M | M / 18 | eggs_m | 18 unit | eggs-m close 1.00 | accept: eggs-m (ביצים M): similarity 0.77 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 1.00 \| vetoed: eggs-l (ביצים L): similarity 0.55 \| critical mismatch product_type eggs |
| tivtaam | חותך ביצים נירוסטה | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): facial-tissues (ממחטות נייר): similarity 0.12 \| critical unknown product_type \| level any_brand, confidence 0.24 |

#### `milk-fresh-3`: 24 listed of 1035 name hits (0 skipped as not the food itself; chains looked in: osherad, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| osherad | חלב מועשר 3% וויטמין | ? / ? | milk | -  | milk-fresh-3 any_brand 0.67 review | review: milk-fresh-3 (חלב טרי 3%): similarity 0.49 \| critical match product_type=milk, fat_pct=3 \| critical unknown state \| level any_brand, confidence 0.67 \| vetoed: milk-long-life-3 (חלב עמיד 3%): similarity 0.49 \| critical mism |
| osherad | חלב טבעי 4% רמת הגול | ? / ? | milk | -  | - | every candidate vetoed \| vetoed: milk-fresh-3 (חלב טרי 3%): similarity 0.33 \| critical mismatch fat_pct 4 vs 3 \| critical match product_type=milk \| critical unknown state ; yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.33 \| critic |
| osherad | שוקולד פרה חלב 100 ג | ? / ? | chocolate_bar | 100 g | chocolate-milk-bar any_brand 0.97 | accept: chocolate-milk-bar (שוקולד חלב): similarity 0.71 \| critical match product_type=chocolate_bar, flavor=milk \| level any_brand, confidence 0.97 \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.42 \| critical mismatch f |
| osherad | פריכיות  פרו 20 חלבו | ? / ? | rice_cakes | 55 g | rice-cakes close 0.79 review | review: rice-cakes (פריכיות אורז): similarity 0.48 \| critical match product_type=rice_cakes \| soft differs pack_size 55 vs 100 g \| level close, confidence 0.79 \| vetoed: halva (חלבה): similarity 0.17 \| critical mismatch product_ty |
| osherad | פריכיות  פרו 20 חלבו | ? / ? | rice_cakes | 55 g | rice-cakes close 0.79 review | review: rice-cakes (פריכיות אורז): similarity 0.48 \| critical match product_type=rice_cakes \| soft differs pack_size 55 vs 100 g \| level close, confidence 0.79 \| vetoed: halva (חלבה): similarity 0.17 \| critical mismatch product_ty |
| osherad | פריכיות  פרו 20 חלבו | ? / ? | rice_cakes | 55 g | rice-cakes close 0.79 review | review: rice-cakes (פריכיות אורז): similarity 0.48 \| critical match product_type=rice_cakes \| soft differs pack_size 55 vs 100 g \| level close, confidence 0.79 \| vetoed: halva (חלבה): similarity 0.17 \| critical mismatch product_ty |
| osherad | חלב מועשר 3% רמת הגו | ? / ? | milk | -  | milk-fresh-3 any_brand 0.67 review | review: milk-fresh-3 (חלב טרי 3%): similarity 0.49 \| critical match product_type=milk, fat_pct=3 \| critical unknown state \| level any_brand, confidence 0.67 \| vetoed: milk-long-life-3 (חלב עמיד 3%): similarity 0.47 \| critical mism |
| osherad | פוליויקס סחלבים 4 לי | ? / ? | - | 4000 ml | - | rejected (confidence 0.24 < 0.6): floor-cleaner (נוזל לניקוי רצפות): similarity 0.11 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| osherad | שוקולד פרה חלב קרם ח | ? / ? | chocolate_bar | 100 g | chocolate-milk-bar any_brand 0.98 | accept: chocolate-milk-bar (שוקולד חלב): similarity 0.72 \| critical match product_type=chocolate_bar, flavor=milk \| level any_brand, confidence 0.98 \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.42 \| critical mismatch f |
| osherad | חלב 3% תנובה 1 ליטר | ? / ? | milk | 1000 ml | milk-fresh-3 any_brand 0.69 review | review: milk-fresh-3 (חלב טרי 3%): similarity 0.51 \| critical match product_type=milk, fat_pct=3 \| critical unknown state \| level any_brand, confidence 0.69 \| vetoed: milk-long-life-3 (חלב עמיד 3%): similarity 0.47 \| critical mism |
| osherad | חלב שקית 3% תנובה 1 | ? / ? | milk | -  | milk-fresh-3 any_brand 0.66 review | review: milk-fresh-3 (חלב טרי 3%): similarity 0.48 \| critical match product_type=milk, fat_pct=3 \| critical unknown state \| level any_brand, confidence 0.66 \| vetoed: milk-long-life-3 (חלב עמיד 3%): similarity 0.46 \| critical mism |
| osherad | גרנולה עם חלבה רפאלס | ? / ? | granola | 850 g | granola close 0.87 review | review: granola (גרנולה): similarity 0.58 \| critical match product_type=granola \| soft differs pack_size 850 vs 500 g \| level close, confidence 0.87 \| vetoed: white-beans (שעועית לבנה יבשה): similarity 0.10 \| critical mismatch pro |
| tivtaam | עוגיות שוקולד חלב מקדמיה סוסליטו 204 גרם | ? / ? | - | 204 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.50 \| critical mismatch flavor chocolate vs milk; name has 'עוגיות' (a derived product), canonical is 'שוקולד חלב' \| critical unknown product_type ; des |
| tivtaam | בד"צ סוויס חלב 100ג | ? / ? | milk | 100 g | - | every candidate vetoed \| vetoed: dessert-vanilla (מעדן חלב וניל): similarity 0.26 \| critical mismatch product_type milk vs dairy_dessert \| critical unknown flavor ; dessert-chocolate (מעדן חלב שוקולד): similarity 0.21 \| critical m |
| tivtaam | בד"צ טורינו חלב שלישייה 46X5ג 138ג | ? / ? | milk | 230 g | - | every candidate vetoed \| vetoed: dessert-vanilla (מעדן חלב וניל): similarity 0.18 \| critical mismatch product_type milk vs dairy_dessert \| critical unknown flavor ; dessert-chocolate (מעדן חלב שוקולד): similarity 0.17 \| critical m |
| tivtaam | אבקת חלבון מי גבינה קומבט עוגיות 2.27 ק" | ? / ? | - | 2270 g | - | every candidate vetoed \| vetoed: white-cheese-3 (גבינה לבנה 3%): similarity 0.30 \| critical mismatch name has 'אבקת' (a derived product), canonical is 'גבינה לבנה 3%' \| critical unknown product_type, fat_pct ; bulgarian-cheese-24  |
| tivtaam | מנצגו חלב כבשים במשקל | ? / ? | milk | -  | - | no candidates in block dairy / kg |
| tivtaam | עוגיות סנדוויץ שוקולד חלב 285 גרם BN | ? / ? | - | 285 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.52 \| critical mismatch flavor chocolate vs milk; name has 'עוגיות' (a derived product), canonical is 'שוקולד חלב' \| critical unknown product_type ; des |
| tivtaam | חלב מלא צרפתי 3%  ECHIRE 1 ל | ? / ? | milk | 1000 ml | milk-fresh-3 any_brand 0.73 review | review: milk-fresh-3 (חלב טרי 3%): similarity 0.42 \| critical match product_type=milk, fat_pct=3, state=fresh \| level any_brand, confidence 0.73 \| vetoed: milk-long-life-3 (חלב עמיד 3%): similarity 0.38 \| critical mismatch product |
| tivtaam | חלבה במשקל | ? / ? | halva | -  | - | no candidates in block snacks / kg |
| tivtaam | פיסטוק חלבי מקולף | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): salmon-fillet-fresh (פילה סלמון טרי): similarity 0.16 \| critical unknown product_type, state \| ambiguous with broccoli-fresh \| level any_brand, confidence 0.24 |
| tivtaam | פיסטוק חלבי לא קלוי | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): salmon-fillet-fresh (פילה סלמון טרי): similarity 0.13 \| critical unknown product_type, state \| ambiguous with chicken-schnitzel-fresh \| level any_brand, confidence 0.24 |
| tivtaam | ריבת חלב צימבוטה 430 גרם | ? / ? | jam | 430 g | - | rejected (confidence 0.48 < 0.6): jam-strawberry (ריבת תות): similarity 0.32 \| critical match product_type=jam \| critical unknown flavor \| soft differs pack_size 430 vs 340 g \| level close, confidence 0.48 \| vetoed: peanut-butter  |
| tivtaam | גבינת רסטה טורקית 20% שומן חלב בקר | ? / ? | milk | -  | - | no candidates in block dairy / kg |

#### `white-cheese-5`: 12 listed of 20 name hits (0 skipped as not the food itself; chains looked in: osherad)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| osherad | משחת אורביטול הלבנה | ? / ? | labane | 435 g | - | rejected (confidence 0.42 < 0.6): labane-5 (לבנה 5%): similarity 0.22 \| critical match product_type=labane \| critical unknown fat_pct \| soft differs pack_size 435 vs 250 g \| level close, confidence 0.42 \| vetoed: white-cheese-9 (ג |
| osherad | שעועית לבנה ברוטב מב | ? / ? | white_beans | 560 g | - | every candidate vetoed \| vetoed: white-beans (שעועית לבנה יבשה): similarity 0.63 \| critical mismatch name has 'רוטב' (a derived product), canonical is 'שעועית לבנה יבשה'; name has 'ברוטב' (prepared or preserved), canonical is not  |
| osherad | טחינה לבנה אחלה 400 | ? / ? | tahini_raw | 400 g | tahini-raw close 0.71 review | review: tahini-raw (טחינה גולמית): similarity 0.39 \| critical match product_type=tahini_raw \| soft differs pack_size 400 vs 500 g \| level close, confidence 0.71 \| vetoed: white-beans (שעועית לבנה יבשה): similarity 0.37 \| critical  |
| osherad | שעועית לבנה סלקטד 50 | ? / ? | white_beans | 500 g | white-beans close 0.91 | accept: white-beans (שעועית לבנה יבשה): similarity 0.64 \| critical match product_type=white_beans \| soft differs pack_size 500 vs 1000 g \| level close, confidence 0.91 \| vetoed: sugar-white (סוכר לבן): similarity 0.13 \| critical m |
| osherad | בפלות טורטית לבנה  3 | ? / ? | labane | 360 g | - | rejected (confidence 0.55 < 0.6): labane-5 (לבנה 5%): similarity 0.41 \| critical match product_type=labane \| critical unknown fat_pct \| soft differs pack_size 360 vs 250 g \| level close, confidence 0.55 \| vetoed: white-cheese-5 (ג |
| osherad | איקרה לבנה דלידג 300 | ? / ? | labane | 300 g | - | rejected (confidence 0.54 < 0.6): labane-5 (לבנה 5%): similarity 0.40 \| critical match product_type=labane \| critical unknown fat_pct \| soft differs pack_size 300 vs 250 g \| level close, confidence 0.54 \| vetoed: white-cheese-3 (ג |
| osherad | שעועית לבנה אינדירה | ? / ? | white_beans | -  | white-beans any_brand 0.94 | accept: white-beans (שעועית לבנה יבשה): similarity 0.68 \| critical match product_type=white_beans \| level any_brand, confidence 0.94 \| vetoed: flour-white (קמח לבן): similarity 0.15 \| critical mismatch product_type white_beans vs  |
| osherad | שעועית לבנה סלקטד 90 | ? / ? | white_beans | 900 g | white-beans close 0.90 | accept: white-beans (שעועית לבנה יבשה): similarity 0.63 \| critical match product_type=white_beans \| soft differs pack_size 900 vs 1000 g \| level close, confidence 0.90 \| vetoed: sugar-white (סוכר לבן): similarity 0.16 \| critical m |
| osherad | שעועית לבנה שטראוס ב | ? / ? | white_beans | 380 g | white-beans close 0.91 | accept: white-beans (שעועית לבנה יבשה): similarity 0.64 \| critical match product_type=white_beans \| soft differs pack_size 380 vs 1000 g \| level close, confidence 0.91 \| vetoed: flour-white (קמח לבן): similarity 0.12 \| critical mi |
| osherad | מי פה אורביטול הלבנה | ? / ? | - | -  | - | rejected (confidence 0.27 < 0.6): white-cheese-9 (גבינה לבנה 9%): similarity 0.29 \| critical unknown product_type, fat_pct \| ambiguous with white-cheese-5 \| level any_brand, confidence 0.27 |
| osherad | שעועית לבנה הנמל 1.2 | ? / ? | white_beans | -  | white-beans any_brand 0.90 | accept: white-beans (שעועית לבנה יבשה): similarity 0.63 \| critical match product_type=white_beans \| level any_brand, confidence 0.90 \| vetoed: sugar-white (סוכר לבן): similarity 0.13 \| critical mismatch product_type white_beans vs |
| osherad | מי פה ליסטרין הלבנה | ? / ? | labane | -  | - | rejected (confidence 0.43 < 0.6): labane-5 (לבנה 5%): similarity 0.26 \| critical match product_type=labane \| critical unknown fat_pct \| level any_brand, confidence 0.43 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.30 \| c |

#### `yellow-cheese-sliced-28`: 60 listed of 421 name hits (0 skipped as not the food itself; chains looked in: shufersal, king_store, osherad, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | גבינת עמק 15% פרוס 200ג | ? / ? | yellow_cheese | 200 g | - | every candidate vetoed \| vetoed: cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.32 \| critical mismatch product_type yellow_cheese vs cream_cheese; fat_pct 15 vs 30 \| critical unknown flavor ; sour-cream-15 (שמנת חמוצה  |
| shufersal | טל העמק 32% במשקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| shufersal | גבינת עמק 28% חריץ במשקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| shufersal | גבינת עמק דק דק 28% 200ג | ? / ? | yellow_cheese | 200 g | yellow-cheese-sliced-28 any_brand 0.60 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.24 \| critical match product_type=yellow_cheese, fat_pct=28 \| level any_brand, confidence 0.60 \| vetoed: cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity |
| shufersal | גבינת עמק פרוסה28% 400ג | ? / ? | yellow_cheese | 400 g | yellow-cheese-sliced-28 close 0.69 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.36 \| critical match product_type=yellow_cheese, fat_pct=28 \| soft differs pack_size 400 vs 200 g \| level close, confidence 0.69 \| vetoed: cream-cheese-30-plain  |
| shufersal | שעועית צהובה חתוכה 800 ג | ? / ? | - | 800 g | - | rejected (confidence 0.32 < 0.6): green-beans-frozen (שעועית ירוקה קפואה): similarity 0.36 \| critical unknown product_type, state \| level any_brand, confidence 0.32 |
| shufersal | מאגדת טעמקור 8*52ג | ? / ? | - | 416 g | - | rejected (confidence 0.24 < 0.6): cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.09 \| critical unknown product_type, fat_pct, flavor \| soft differs pack_size 416 vs 200 g \| ambiguous with halva \| level close, confidenc |
| shufersal | גבינה צהובה מגורדת 500גר | ? / ? | grated_cheese | 500 g | grated-mozzarella close 0.89 review | review: grated-mozzarella (גבינה מגורדת (מוצרלה)): similarity 0.62 \| critical match product_type=grated_cheese \| soft differs pack_size 500 vs 200 g \| level close, confidence 0.89 \| vetoed: yellow-cheese-sliced-9 (גבינה צהובה פרוס |
| shufersal | גבינה גאודה 30% משקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| shufersal | גאודה כמון 30% משקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| shufersal | גאודה תום עיזים30% גד | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| shufersal | גאודה מעושנת 30% במשקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| king_store | גבינת גאודה כמון במשקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| king_store | גבינת עמק 28% במשקל תנובה | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| king_store | טל עמק חריץ 32% | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| king_store | צהובה מעושנת כפיר | ? / ? | - | -  | - | every candidate vetoed \| vetoed: beef-shoulder-fresh (צלי כתף בקר טרי): similarity 0.15 \| critical mismatch name has 'מעושנת' (prepared or preserved), canonical is not \| critical unknown product_type, state ; lemon (לימונים): simi |
| king_store | גבינת גאודה הולנדית30.3% | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| king_store | שעועית צהובה ארוז | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): parsley (פטרוזיליה): similarity 0.10 \| critical unknown product_type, state \| ambiguous with lettuce \| level any_brand, confidence 0.24 |
| king_store | גבינת גאודה פסטו אדום שקיל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| king_store | גאודה עיזים הולנד במשקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| king_store | גבינה אמנטל פריקו | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| king_store | גבינת דק דק 28% 200 ג' עמק | ? / ? | yellow_cheese | 200 g | yellow-cheese-sliced-28 any_brand 0.60 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.25 \| critical match product_type=yellow_cheese, fat_pct=28 \| level any_brand, confidence 0.60 \| vetoed: cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity |
| king_store | המעדניה של עמק 28% 400 ג' | ? / ? | yellow_cheese | 400 g | yellow-cheese-sliced-28 close 0.60 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.19 \| critical match product_type=yellow_cheese, fat_pct=28 \| soft differs pack_size 400 vs 200 g \| level close, confidence 0.60 \| vetoed: pudding-chocolate-crea |
| king_store | שעועית צהובה חתוכה 800 ג' סנפרוסט | ? / ? | - | 800 g | - | rejected (confidence 0.27 < 0.6): green-beans-frozen (שעועית ירוקה קפואה): similarity 0.28 \| critical unknown product_type, state \| level any_brand, confidence 0.27 |
| osherad | שעועית צהובה ערוגות | ? / ? | - | -  | - | rejected (confidence 0.36 < 0.6): white-beans (שעועית לבנה יבשה): similarity 0.40 \| critical unknown product_type \| ambiguous with green-beans-frozen \| level any_brand, confidence 0.36 |
| osherad | מארז קסטה טעמקור 8 י | ? / ? | - | 416 g | - | rejected (confidence 0.24 < 0.6): couscous (קוסקוס): similarity 0.18 \| critical unknown product_type \| soft differs pack_size 416 vs 500 g \| ambiguous with cornflakes \| level close, confidence 0.24 |
| osherad | יין אדום יבש עמק שיל | ? / ? | red_wine_dry | -  | red-wine-dry any_brand 1.00 | accept: red-wine-dry (יין אדום יבש): similarity 0.79 \| critical match product_type=red_wine_dry \| level any_brand, confidence 1.00 \| vetoed: lager-beer (בירה לאגר): similarity 0.02 \| critical mismatch product_type red_wine_dry vs  |
| osherad | יין אדום יבש עמק שכם | ? / ? | red_wine_dry | -  | red-wine-dry any_brand 1.00 | accept: red-wine-dry (יין אדום יבש): similarity 0.80 \| critical match product_type=red_wine_dry \| level any_brand, confidence 1.00 \| vetoed: lager-beer (בירה לאגר): similarity 0.02 \| critical mismatch product_type red_wine_dry vs  |
| osherad | גבינה עמק 28% 600 גר | ? / ? | yellow_cheese | 600 g | yellow-cheese-sliced-28 close 0.78 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.48 \| critical match product_type=yellow_cheese, fat_pct=28 \| soft differs pack_size 600 vs 200 g \| level close, confidence 0.78 \| vetoed: white-cheese-9 (גבינה  |
| osherad | גבינה אמנטל מגורדת 2 | ? / ? | grated_cheese | 200 g | grated-mozzarella any_brand 0.89 review | review: grated-mozzarella (גבינה מגורדת (מוצרלה)): similarity 0.61 \| critical match product_type=grated_cheese \| level any_brand, confidence 0.89 \| vetoed: white-cheese-5 (גבינה לבנה 5%): similarity 0.39 \| critical mismatch produc |

#### `yogurt-plain-3`: 24 listed of 205 name hits (0 skipped as not the food itself; chains looked in: osherad, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| osherad | מולר פרופ יוגורט עם | ? / ? | yogurt | -  | - | every candidate vetoed \| vetoed: yogurt-peach (יוגורט אפרסק): similarity 0.49 \| critical mismatch product_type yogurt vs yogurt_fruit; flavor other vs peach ; yogurt-strawberry (יוגורט תות): similarity 0.49 \| critical mismatch pro |
| osherad | מולר יוגורט בסגנון י | ? / ? | yogurt | 130 g | - | rejected (confidence 0.51 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.44 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| soft differs pack_size 130 vs 200 g \| ambiguous with yogurt-plain-1-5 \| l |
| osherad | יוגורט ביו דנונה 1.7 | ? / ? | yogurt | 200 g | - | rejected (confidence 0.55 < 0.6): yogurt-plain-1-5 (יוגורט טבעי 1.5%): similarity 0.49 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| level any_brand, confidence 0.55 \| vetoed: yogurt-strawberry (יוגורט  |
| osherad | מארז יוגורט פרוביוטי | ? / ? | yogurt | -  | - | rejected (confidence 0.51 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.44 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| ambiguous with yogurt-plain-1-5 \| level any_brand, confidence 0.51 \| veto |
| osherad | מארז יוגורט פרוביוטי | ? / ? | yogurt | -  | - | rejected (confidence 0.51 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.44 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| ambiguous with yogurt-plain-1-5 \| level any_brand, confidence 0.51 \| veto |
| osherad | מארז יוגורט אקטיביה | ? / ? | yogurt | -  | - | rejected (confidence 0.49 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.41 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| ambiguous with yogurt-plain-1-5 \| level any_brand, confidence 0.49 \| veto |
| osherad | יוגורט עיזים צוריאל | ? / ? | yogurt | -  | - | rejected (confidence 0.50 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.43 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| ambiguous with yogurt-plain-1-5 \| level any_brand, confidence 0.50 \| veto |
| osherad | משקה יוגורט 4% טרה 3 | ? / ? | yogurt | -  | - | every candidate vetoed \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.44 \| critical mismatch product_type yogurt vs yogurt_fruit \| critical unknown flavor ; yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.43 \| critical misma |
| osherad | יוגורט יווני 10% גד | ? / ? | greek_yogurt | 600 g | greek-yogurt-plain close 0.77 review | review: greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.68 \| critical match product_type=greek_yogurt \| critical unknown flavor \| soft differs pack_size 600 vs 200 g \| level close, confidence 0.77 \| vetoed: yogurt-strawberry  |
| osherad | משקה יוגורט עיזים פי | ? / ? | yogurt | 500 g | - | rejected (confidence 0.50 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.43 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| soft differs pack_size 500 vs 200 g \| level close, confidence 0.50 \| veto |
| osherad | משקה יוגורט עיזים תו | ? / ? | yogurt | 200 g | - | rejected (confidence 0.48 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.41 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| level any_brand, confidence 0.48 \| vetoed: yogurt-strawberry (יוגורט תות) |
| osherad | משקה יוגורט עיזים אנ | ? / ? | yogurt | -  | - | rejected (confidence 0.48 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.41 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| level any_brand, confidence 0.48 \| vetoed: yogurt-peach (יוגורט אפרסק): s |
| tivtaam | תחליב רחצה יוגורט וקוקוס גונסונס 750 | ? / ? | body_wash | 750 ml | body-wash any_brand 0.62 review | review: body-wash (סבון רחצה): similarity 0.28 \| critical match product_type=body_wash \| level any_brand, confidence 0.62 \| vetoed: hand-soap (סבון ידיים נוזלי): similarity 0.06 \| critical mismatch product_type body_wash vs hand_s |
| tivtaam | שוקולד ריטר ספורט יוגורט - גאווה 100 גרם | ? / ? | yogurt | 100 g | - | every candidate vetoed \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.38 \| critical mismatch product_type yogurt vs yogurt_fruit; flavor chocolate vs strawberry ; yogurt-peach (יוגורט אפרסק): similarity 0.37 \| critical mis |
| tivtaam | ג. יוגורט עם אוכמניות שחורות בכוס 82 גר | ? / ? | yogurt | 82 g | - | every candidate vetoed \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.45 \| critical mismatch product_type yogurt vs yogurt_fruit; flavor other vs strawberry ; yogurt-peach (יוגורט אפרסק): similarity 0.36 \| critical mismatc |
| tivtaam | יוגורט יווני 200 גר | ? / ? | greek_yogurt | 200 g | greek-yogurt-plain any_brand 0.78 review | review: greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.70 \| critical match product_type=greek_yogurt \| critical unknown flavor \| level any_brand, confidence 0.78 \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.53 \| cr |
| tivtaam | יוגורט יווני עם דובדבן 150 גר | ? / ? | greek_yogurt | 150 g | - | every candidate vetoed \| vetoed: greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.60 \| critical mismatch flavor other vs plain \| critical match product_type=greek_yogurt ; yogurt-strawberry (יוגורט תות): similarity 0.44 \| crit |
| tivtaam | יוגורט יווני 150 גר | ? / ? | greek_yogurt | 150 g | greek-yogurt-plain close 0.79 review | review: greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.71 \| critical match product_type=greek_yogurt \| critical unknown flavor \| soft differs pack_size 150 vs 200 g \| level close, confidence 0.79 \| vetoed: yogurt-strawberry  |
| tivtaam | יוגורט יווני 1 ק"ג | ? / ? | greek_yogurt | 1000 g | greek-yogurt-plain close 0.78 review | review: greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.70 \| critical match product_type=greek_yogurt \| critical unknown flavor \| soft differs pack_size 1000 vs 200 g \| level close, confidence 0.78 \| vetoed: yogurt-plain-1-5  |
| tivtaam | יוגורט יווני זכוכית 375 גרם 10% שומן | ? / ? | greek_yogurt | 375 g | greek-yogurt-plain close 0.66 review | review: greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.55 \| critical match product_type=greek_yogurt \| critical unknown flavor \| soft differs pack_size 375 vs 200 g \| level close, confidence 0.66 \| vetoed: yogurt-strawberry  |
| tivtaam | יוגורט יווני 500 גר 10% שומן | ? / ? | greek_yogurt | 500 g | greek-yogurt-plain close 0.70 review | review: greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.60 \| critical match product_type=greek_yogurt \| critical unknown flavor \| soft differs pack_size 500 vs 200 g \| level close, confidence 0.70 \| vetoed: yogurt-strawberry  |
| tivtaam | שוקולד חלב דובדבנים ויוגורט 235 גר | ? / ? | yogurt | 235 g | - | every candidate vetoed \| vetoed: dessert-chocolate (מעדן חלב שוקולד): similarity 0.45 \| critical mismatch product_type yogurt vs dairy_dessert \| critical match flavor=chocolate ; yogurt-strawberry (יוגורט תות): similarity 0.25 \| c |
| tivtaam | שוקולד חלב קיווי ויוגורט 235 גר | ? / ? | yogurt | 235 g | - | every candidate vetoed \| vetoed: dessert-chocolate (מעדן חלב שוקולד): similarity 0.48 \| critical mismatch product_type yogurt vs dairy_dessert \| critical match flavor=chocolate ; pudding-chocolate-cream (מעדן שוקולד עם קצפת): simi |
| tivtaam | עוגת פנדה עם יוגורט ופודינג 270 גרם a1 | ? / ? | yogurt | 270 g | - | every candidate vetoed \| vetoed: yogurt-peach (יוגורט אפרסק): similarity 0.32 \| critical mismatch product_type yogurt vs yogurt_fruit; flavor other vs peach; name has 'עוגת' (a derived product), canonical is 'יוגורט אפרסק' ; yogur |

### Failures and findings the run recorded (2)

- **basket index**: chocolate-milk is priced at no chain (candidates in the report)
- **api**: Jerusalem centre drawn: 20: MILP net saving 30.81 is below the heuristic's 40.01

