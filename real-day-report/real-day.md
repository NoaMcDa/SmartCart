## One real day through the pipeline (dry run)

Mode `portal`, commit `e2ee65d72f90`, runner `GitHub Actions 1000005331` (4 CPUs, Python 3.12.3, Postgres 17.11), 2026-10-22T15:35:06+00:00 to 2026-10-22T16:29:25+00:00 UTC. Measurements on one real day with hand-made baskets; the prices are real, the baskets and locations are not a sample of anything. **Not publishable.**

### Stages

| stage | seconds | result |
|---|---|---|
| download: portal probe (one Stores and one PriceFull per chain) | 1897.37 | ok |
| migrate | 1.15 | 34 applied |
| ingest: Stores files (Scheduler, adapters, gates, loader, store coordinates) | 0.49 | 6 files |
| download: PriceFull and PromoFull of the stores nearest to city centres | 410.58 | 48 files, anchors: Haifa centre, Jerusalem centre, Petah Tikva |
| ingest: PriceFull and PromoFull files (Scheduler, adapters, gates, loader) | 234.06 | 60 files |
| catalog: seed | 1.16 | ok |
| catalog: normalize | 12.07 | ok |
| catalog: extract (rule) | 90.41 | ok |
| catalog: embed (hash) | 279.93 | ok |
| catalog: judge (rule) | 209.89 | ok |
| catalog: proposals for new canonicals (propose-canonicals) | 102.18 | 150 proposals over 2,356 items |
| precompute effective prices (production semantics: reviewed mappings only) | 4.23 | 6992 rows |
| API: parse-list, compare, optimize (production) | 11.82 | 21 basket runs at 3 locations |
| diagnostic: the vector query behind /parse-list and /search | 0.26 | [3.6, 1.2, 1.1] ms per query |
| basket index dry run (production semantics) | 0.5 | status draft |
| diagnostic: real items behind the basket lines no chain prices | 1.55 | butter 60 items, chocolate-milk 72 items, cottage-5 7 items, eggs-l 161 items, milk-fresh-3 24 items, white-cheese-5 12 items, yellow-cheese-sliced-28 60 items, yogurt-plain-3 24 items |

### Portals (the portal probe's own reachability and downloads)

| chain | reachable | login | Stores download | PriceFull download |
|---|---|---|---|---|
| hazihinam | BLOCKED? (403) | n/a | no: no file downloaded | no: no file downloaded |
| king_store | BLOCKED? (403) | n/a | Stores7290058108879-000-20261022-051042.gz | PriceFull7290058108879-000-031-20261022-051042.gz |
| machsanei_hashuk | UNREACHABLE (0) | n/a | no: no file downloaded | no: no file downloaded |
| mega | UNREACHABLE (0) | n/a | no: timed out after 300s | no: timed out after 300s |
| osherad | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290103152017-000-20261020-080500.xml | PriceFull7290103152017-001-003-20261022-080001.gz |
| ramilevy | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290058140886-000-20261020-050500.xml | PriceFull7290058140886-001-003-20261022-001017.gz |
| shufersal | OK (200) | n/a | Stores7290027600007-000-20261022-020.gz | PriceFull7290027600007-002-077-20261022-030000.gz |
| tivtaam | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290873255550-000-20261020-050500.xml | PriceFull7290873255550-000-014-20261022-004004.gz |
| victory | UNREACHABLE (0) | n/a | no: no file downloaded | no: no file downloaded |
| yohananof | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290803800003-000-20261020-010000.xml | PriceFull7290803800003-000-005-20261022-004040.gz |

### Files, gates and rows per chain

| chain | kind | file | published (Israel) | age h | schema | gate result | rows | seconds |
|---|---|---|---|---|---|---|---|---|
| king_store | stores | `Stores7290058108879-000-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 13.9 | v1 | loaded | 48 | 0.07 |
| osherad | stores | `Stores7290103152017-000-20261020-080500.xml` | 2026-10-20T08:05+03:00 | 59.0 | v1 | loaded | 24 | 0.03 |
| ramilevy | stores | `Stores7290058140886-000-20261020-050500.xml` | 2026-10-20T05:05+03:00 | 62.0 | v1 | loaded | 99 | 0.08 |
| shufersal | stores | `Stores7290027600007-000-20261022-020.gz` | 2026-10-22T02:00+03:00 | 17.1 | v1 | loaded | 417 | 0.2 |
| tivtaam | stores | `Stores7290873255550-000-20261020-050500.xml` | 2026-10-20T05:05+03:00 | 62.0 | v1 | loaded | 54 | 0.04 |
| yohananof | stores | `Stores7290803800003-000-20261020-010000.xml` | 2026-10-20T01:00+03:00 | 66.1 | v1 | loaded | 51 | 0.03 |
| king_store | price_full | `PriceFull7290058108879-000-031-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 14.0 | v1 | loaded | 5,991 | 1.26 |
| king_store | promo_full | `PromoFull7290058108879-000-031-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 14.0 | v1 | loaded | 507 | 0.3 |
| osherad | price_full | `PriceFull7290103152017-001-003-20261022-080001.gz` | 2026-10-22T08:00+03:00 | 11.2 | v1 | loaded | 6,741 | 1.36 |
| osherad | promo_full | `PromoFull7290103152017-001-003-20261022-140531.gz` | 2026-10-22T14:05+03:00 | 5.1 | v1 | loaded | 809 | 0.45 |
| ramilevy | price_full | `PriceFull7290058140886-001-003-20261022-001017.gz` | 2026-10-22T00:10+03:00 | 19.1 | v1 | loaded | 7,507 | 1.58 |
| ramilevy | promo_full | `PromoFull7290058140886-001-003-20261022-185700.gz` | 2026-10-22T18:57+03:00 | 0.3 | v1 | loaded | 2,716 | 1.54 |
| shufersal | price_full | `PriceFull7290027600007-002-077-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.2 | v1 | loaded | 8,777 | 1.8 |
| shufersal | promo_full | `PromoFull7290027600007-002-077-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.2 | v1 | loaded | 1,584 | 4.4 |
| tivtaam | price_full | `PriceFull7290873255550-000-014-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 23,274 | 4.74 |
| tivtaam | promo_full | `PromoFull7290873255550-000-014-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 2,349 | 6.3 |
| yohananof | price_full | `PriceFull7290803800003-000-005-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 11,656 | 2.52 |
| yohananof | promo_full | `PromoFull7290803800003-000-005-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 1,241 | 0.92 |
| king_store | price_full | `PriceFull7290058108879-000-014-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 14.1 | v1 | loaded | 4,789 | 0.98 |
| king_store | price_full | `PriceFull7290058108879-000-200-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 14.1 | v1 | loaded | 3,611 | 0.73 |
| king_store | promo_full | `PromoFull7290058108879-000-014-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 14.1 | v1 | loaded | 424 | 0.24 |
| king_store | promo_full | `PromoFull7290058108879-000-200-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 14.1 | v1 | loaded | 306 | 0.18 |
| osherad | price_full | `PriceFull7290103152017-001-026-20261022-140501.gz` | 2026-10-22T14:05+03:00 | 5.2 | v1 | loaded | 6,837 | 1.44 |
| osherad | price_full | `PriceFull7290103152017-001-030-20261022-140501.gz` | 2026-10-22T14:05+03:00 | 5.2 | v1 | loaded | 6,460 | 1.32 |
| osherad | price_full | `PriceFull7290103152017-001-010-20261022-140502.gz` | 2026-10-22T14:05+03:00 | 5.2 | v1 | loaded | 6,693 | 1.35 |
| osherad | price_full | `PriceFull7290103152017-001-028-20261022-140502.gz` | 2026-10-22T14:05+03:00 | 5.2 | v1 | loaded | 6,242 | 1.3 |
| osherad | promo_full | `PromoFull7290103152017-001-026-20261022-140523.gz` | 2026-10-22T14:05+03:00 | 5.2 | v1 | loaded | 723 | 0.44 |
| osherad | promo_full | `PromoFull7290103152017-001-028-20261022-140524.gz` | 2026-10-22T14:05+03:00 | 5.2 | v1 | loaded | 706 | 0.43 |
| osherad | promo_full | `PromoFull7290103152017-001-030-20261022-140541.gz` | 2026-10-22T14:05+03:00 | 5.2 | v1 | loaded | 766 | 0.46 |
| osherad | promo_full | `PromoFull7290103152017-001-010-20261022-140556.gz` | 2026-10-22T14:05+03:00 | 5.1 | v1 | loaded | 724 | 0.44 |
| ramilevy | price_full | `PriceFull7290058140886-001-048-20261022-001016.gz` | 2026-10-22T00:10+03:00 | 19.1 | v1 | loaded | 14,443 | 3.08 |
| ramilevy | price_full | `PriceFull7290058140886-001-062-20261022-120012.gz` | 2026-10-22T12:00+03:00 | 7.2 | v1 | loaded | 14,126 | 2.99 |
| ramilevy | price_full | `PriceFull7290058140886-001-703-20261022-120017.gz` | 2026-10-22T12:00+03:00 | 7.2 | v1 | loaded | 4,959 | 1.06 |
| ramilevy | price_full | `PriceFull7290058140886-001-057-20261022-121507.gz` | 2026-10-22T12:15+03:00 | 7.0 | v1 | loaded | 13,930 | 2.93 |
| ramilevy | price_full | `PriceFull7290058140886-001-724-20261022-180005.gz` | 2026-10-22T18:00+03:00 | 1.2 | v1 | loaded | 5,163 | 1.1 |
| ramilevy | price_full | `PriceFull7290058140886-001-725-20261022-180005.gz` | 2026-10-22T18:00+03:00 | 1.2 | v1 | loaded | 4,121 | 0.86 |
| ramilevy | promo_full | `PromoFull7290058140886-001-048-20261022-120041.gz` | 2026-10-22T12:00+03:00 | 7.2 | v1 | loaded | 2,546 | 1.77 |
| ramilevy | promo_full | `PromoFull7290058140886-001-703-20261022-120047.gz` | 2026-10-22T12:00+03:00 | 7.2 | v1 | loaded | 1,110 | 0.69 |
| ramilevy | promo_full | `PromoFull7290058140886-001-062-20261022-120129.gz` | 2026-10-22T12:01+03:00 | 7.2 | v1 | loaded | 2,550 | 1.81 |
| ramilevy | promo_full | `PromoFull7290058140886-001-057-20261022-121643.gz` | 2026-10-22T12:16+03:00 | 7.0 | v1 | loaded | 2,557 | 1.74 |
| ramilevy | promo_full | `PromoFull7290058140886-001-725-20261022-180029.gz` | 2026-10-22T18:00+03:00 | 1.2 | v1 | loaded | 1,049 | 0.65 |
| ramilevy | promo_full | `PromoFull7290058140886-001-724-20261022-180031.gz` | 2026-10-22T18:00+03:00 | 1.2 | v1 | loaded | 1,062 | 0.69 |
| shufersal | price_full | `PriceFull7290027600007-001-002-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.3 | v1 | loaded | 7,494 | 1.49 |
| shufersal | price_full | `PriceFull7290027600007-001-302-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.3 | v1 | loaded | 6,533 | 1.41 |
| shufersal | price_full | `PriceFull7290027600007-006-300-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.3 | v1 | loaded | 7,721 | 1.64 |
| shufersal | price_full | `PriceFull7290027600007-007-285-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.3 | v1 | loaded | 3,322 | 0.7 |
| shufersal | price_full | `PriceFull7290027600007-007-353-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.3 | v1 | loaded | 2,269 | 0.48 |
| shufersal | price_full | `PriceFull7290027600007-018-753-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.3 | v1 | loaded | 3,553 | 0.72 |
| shufersal | promo_full | `PromoFull7290027600007-001-002-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.3 | v1 | loaded | 1,383 | 3.5 |
| shufersal | promo_full | `PromoFull7290027600007-001-302-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.3 | v1 | loaded | 1,288 | 2.87 |
| shufersal | promo_full | `PromoFull7290027600007-006-300-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.3 | v1 | loaded | 1,012 | 3.04 |
| shufersal | promo_full | `PromoFull7290027600007-007-285-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.3 | v1 | loaded | 744 | 1.23 |
| shufersal | promo_full | `PromoFull7290027600007-007-353-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.3 | v1 | loaded | 617 | 0.79 |
| shufersal | promo_full | `PromoFull7290027600007-018-753-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 16.3 | v1 | loaded | 418 | 1.0 |
| tivtaam | price_full | `PriceFull7290873255550-000-012-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 17,817 | 3.68 |
| tivtaam | price_full | `PriceFull7290873255550-000-085-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 7,171 | 1.49 |
| tivtaam | price_full | `PriceFull7290873255550-000-087-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 6,069 | 1.29 |
| tivtaam | price_full | `PriceFull7290873255550-000-092-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 5,854 | 1.25 |
| tivtaam | promo_full | `PromoFull7290873255550-000-012-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 2,041 | 6.48 |
| tivtaam | promo_full | `PromoFull7290873255550-000-085-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 1,281 | 6.35 |
| tivtaam | promo_full | `PromoFull7290873255550-000-087-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 1,124 | 5.65 |
| tivtaam | promo_full | `PromoFull7290873255550-000-092-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 1,061 | 5.78 |
| yohananof | price_full | `PriceFull7290803800003-000-020-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 11,876 | 2.41 |
| yohananof | price_full | `PriceFull7290803800003-000-021-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 11,196 | 2.33 |
| yohananof | promo_full | `PromoFull7290803800003-000-020-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 1,276 | 0.98 |
| yohananof | promo_full | `PromoFull7290803800003-000-021-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 18.6 | v1 | loaded | 1,218 | 0.93 |

PromoFull files: what they hold and how much reached `promo_items`:

| chain | file | promos | with item codes | distinct codes | codes the chain's items know | promo_items linked | active now | club | rewards |
|---|---|---|---|---|---|---|---|---|---|
| king_store | `PromoFull7290058108879-000-031-20261022-051042.gz` | 507 | 507 | 1,273 | 1,273 | 1,292 | 507 | 160 | {'bundle': 240, 'price': 264, 'other': 2, 'percent': 1} |
| osherad | `PromoFull7290103152017-001-003-20261022-140531.gz` | 809 | 809 | 2,993 | 2,068 | 2,185 | 809 | 0 | {'bundle': 721, 'price': 85, 'other': 3} |
| ramilevy | `PromoFull7290058140886-001-003-20261022-185700.gz` | 2,716 | 2,716 | 9,124 | 3,749 | 6,215 | 2,716 | 37 | {'other': 491, 'price': 1332, 'bundle': 875, 'buy_x_get_y': 16, 'percent': 2} |
| shufersal | `PromoFull7290027600007-002-077-20261022-030000.gz` | 1,584 | 1,581 | 8,871 | 8,669 | 26,219 | 1,584 | 1 | {'other': 133, 'percent': 5, 'bundle': 885, 'price': 545, 'buy_x_get_y': 16} |
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
| shufersal | `PromoFull7290027600007-001-002-20261022-030000.gz` | 1,383 | 1,380 | 7,613 | 7,468 | 22,462 | 1,383 | 1 | {'other': 126, 'percent': 5, 'bundle': 789, 'price': 450, 'buy_x_get_y': 13} |
| shufersal | `PromoFull7290027600007-001-302-20261022-030000.gz` | 1,288 | 1,285 | 6,680 | 6,539 | 19,845 | 1,288 | 1 | {'other': 129, 'percent': 5, 'price': 415, 'bundle': 725, 'buy_x_get_y': 14} |
| shufersal | `PromoFull7290027600007-006-300-20261022-030000.gz` | 1,012 | 1,010 | 7,612 | 7,611 | 17,318 | 1,012 | 0 | {'other': 20, 'bundle': 682, 'price': 310} |
| shufersal | `PromoFull7290027600007-007-285-20261022-030000.gz` | 744 | 741 | 3,494 | 3,353 | 10,167 | 744 | 1 | {'other': 92, 'percent': 3, 'bundle': 448, 'price': 194, 'buy_x_get_y': 7} |
| shufersal | `PromoFull7290027600007-007-353-20261022-030000.gz` | 617 | 614 | 2,490 | 2,349 | 6,947 | 617 | 1 | {'other': 68, 'percent': 3, 'bundle': 396, 'price': 147, 'buy_x_get_y': 3} |
| shufersal | `PromoFull7290027600007-018-753-20261022-030000.gz` | 418 | 416 | 3,530 | 3,530 | 7,956 | 418 | 0 | {'other': 4, 'bundle': 299, 'price': 115} |
| tivtaam | `PromoFull7290873255550-000-012-20261022-004004.gz` | 2,041 | 2,041 | 15,144 | 13,399 | 26,750 | 2,041 | 1,226 | {'other': 18, 'bundle': 875, 'price': 1107, 'percent': 3, 'buy_x_get_y': 38} |
| tivtaam | `PromoFull7290873255550-000-085-20261022-004004.gz` | 1,281 | 1,281 | 13,365 | 11,697 | 23,846 | 1,281 | 711 | {'other': 16, 'bundle': 583, 'price': 670, 'buy_x_get_y': 12} |
| tivtaam | `PromoFull7290873255550-000-087-20261022-004004.gz` | 1,124 | 1,124 | 13,048 | 11,380 | 23,450 | 1,124 | 637 | {'other': 11, 'bundle': 538, 'price': 564, 'buy_x_get_y': 11} |
| tivtaam | `PromoFull7290873255550-000-092-20261022-004004.gz` | 1,061 | 1,061 | 13,221 | 11,553 | 23,408 | 1,061 | 556 | {'other': 15, 'bundle': 519, 'price': 517, 'buy_x_get_y': 10} |
| yohananof | `PromoFull7290803800003-000-020-20261022-004040.gz` | 1,276 | 1,276 | 4,339 | 4,305 | 4,378 | 1,276 | 11 | {'bundle': 779, 'price': 399, 'other': 86, 'percent': 4, 'buy_x_get_y': 8} |
| yohananof | `PromoFull7290803800003-000-021-20261022-004040.gz` | 1,218 | 1,218 | 4,151 | 4,128 | 4,188 | 1,218 | 11 | {'bundle': 796, 'price': 356, 'other': 54, 'percent': 3, 'buy_x_get_y': 9} |

Sample codes (promo / item): king_store ['100601', '13006', '13037'] / ['12', '12345', '13006']; osherad ['1230000292009', '16000423534', '16000548404'] / ['8850006535424', '7290116859606', '8006530174619']; ramilevy ['1220000750166', '1230000068413', '1230000116022'] / ['7290000211169', '7290000211312', '7290000211442']; shufersal ['10900035187', '10900035194', '10900302814'] / ['10900035187', '10900035194', '10900302814']; tivtaam ['10900302814', '11182170603', '11182175271'] / ['10900035187', '10900035194', '10900302814']; yohananof ['1218051', '14098', '15521'] / ['1022788', '1022801', '1022825']

`file_tracking` after the run: {'loaded': 66}. Alerts raised: 0.

| chain | physical stores | located | online | items | price events | stores with prices | promos | promo items |
|---|---|---|---|---|---|---|---|---|
| king_store | 48 | 28 | - | 8,396 | 14,391 | 3 | 1,237 | 3,172 |
| osherad | 24 | 24 | - | 8,679 | 32,973 | 5 | 3,728 | 11,615 |
| ramilevy | 98 | 96 | 1 | 18,315 | 64,249 | 7 | 13,590 | 51,249 |
| shufersal | 416 | 411 | 1 | 14,437 | 39,669 | 7 | 7,046 | 110,914 |
| tivtaam | 47 | 47 | 7 | 25,925 | 60,185 | 5 | 7,856 | 123,109 |
| yohananof | 50 | 19 | 1 | 13,721 | 34,728 | 3 | 3,735 | 12,825 |

Extra downloads (the stores nearest to these city centres, for the optimizer):

- Haifa centre: 5 chains and 32 located stores within 4 km; asked for shufersal 302,353, king_store 14, ramilevy 57,62, osherad 30, tivtaam 92,12
- Jerusalem centre: 5 chains and 32 located stores within 4 km; asked for shufersal 2,753, king_store 200, ramilevy 48,703, osherad 26,28, yohananof 20
- Petah Tikva: 5 chains and 29 located stores within 4 km; asked for shufersal 285,300, ramilevy 725,724, osherad 10, yohananof 21, tivtaam 87,85

### Matching on the real items

89,473 items; 19,314 mapped to a canonical (any level, including the review queue); 5,064 served (no review flag), onto 209 canonicals.

| level | mappings served | mappings in the review queue |
|---|---|---|
| exact | 0 | 0 |
| any_brand | 3,140 | 5,902 |
| close | 1,924 | 8,348 |

| chain | items | mapped | served |
|---|---|---|---|
| shufersal | 14,437 | 3,477 | 1,006 |
| king_store | 8,396 | 2,113 | 354 |
| ramilevy | 18,315 | 3,929 | 1,367 |
| osherad | 8,679 | 2,162 | 694 |
| yohananof | 13,721 | 2,668 | 930 |
| tivtaam | 25,925 | 4,965 | 713 |

- seed: 1.16 s
- normalize: 12.07 s
- extract (rule): 90.41 s
- embed (hash): 279.93 s
- judge (rule): 209.89 s

### Proposals for new canonicals (issue #52)

70,159 of 89,473 items were not mapped (46,904 products by barcode, 28,985 groups). 150 proposals ({'variant': 50, 'new_type': 100}) would cover up to 2,356 of them (3.4%). The coverage is an upper bound: matching still decides. Not proposed: 441 groups (9,009 items) that already have a canonical with those critical values (a matching question), 296 whose critical value no name states, 20,405 sold by one chain.

| # | proposal | kind | chains | stores | items | shared barcodes |
|---|---|---|---|---|---|---|
| 1 | שמנת לבישול 15% | variant | 6 | 30 | 26 | 5 |
| 2 | בולגרית 16% | variant | 6 | 28 | 27 | 7 |
| 3 | גאודה | variant | 6 | 28 | 25 | 5 |
| 4 | תות שדה קפוא | variant | 6 | 27 | 24 | 6 |
| 5 | שוקולד לבן | variant | 6 | 30 | 211 | 56 |
| 6 | חומוס חריף | variant | 6 | 29 | 28 | 5 |
| 7 | תות | variant | 6 | 28 | 15 | 4 |
| 8 | מנגו קפוא | variant | 6 | 24 | 16 | 5 |
| 9 | ביסלי ברביקיו | variant | 6 | 30 | 39 | 8 |
| 10 | תפוציפס טבעי | variant | 6 | 30 | 29 | 7 |

The packet (HTML, CSV, JSON) is in `/home/runner/work/SmartCart/SmartCart/out/proposals` and in the report artifact; see `docs/catalog.md` section 10.

### Precompute (production semantics)

6,992 rows written in 3.724 s of job time (4.12 s wall including start-up); 4,984 items priced at 30 stores (693 stores of 6 chains considered); 2,402 rows with a promo, 229 club-only. Canonicals with a real price: 208, of them 190 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 3,102 | 191 | 30 |
| close | 3,890 | 208 | 30 |

Promos per chain, and what reached a price (production semantics):

| chain | promos | club-only | linked to items | reward `other` | effective rows | with a promo | club required | of them with a non-club fallback |
|---|---|---|---|---|---|---|---|---|
| shufersal | 7,046 | 5 | 7,022 | 572 | 1,512 | 674 | 0 | 0 |
| king_store | 1,237 | 336 | 1,237 | 4 | 523 | 135 | 32 | 32 |
| ramilevy | 13,590 | 218 | 11,811 | 2,690 | 1,912 | 691 | 0 | 0 |
| osherad | 3,728 | 0 | 3,355 | 14 | 1,062 | 291 | 0 | 0 |
| yohananof | 3,735 | 33 | 3,735 | 202 | 850 | 309 | 14 | 14 |
| tivtaam | 7,856 | 4,599 | 7,856 | 79 | 1,133 | 302 | 183 | 183 |

Club rules of the club-only promos (most frequent): `המועדון החדש` x 4,599; `מועדון לקוחות \| לקוחות סיטונאים \| עובדי קינגסטור` x 248; `מועדון חברתי \| מועדון רמי לוי \| מועדון לקוחות אשראי \| מועדון נטען \| לקוחות ארנק` x 132; `מועדון לקוחות \| עובדי קינגסטור` x 56; `מועדון לקוחות אשראי & (תווי זיכוי מימוש \| מולטיפס תו רמי לוי)` x 36; `מועדון עובדים` x 33; `לקוחות סיטונאים` x 26; `מועדון רמי לוי \| מועדון לקוחות אשראי` x 16

### The vector query behind /parse-list and /search

`item_embeddings` holds 89,473 rows (model `hash-ngram-2-3-4-v1`); one `ORDER BY embedding <=> q LIMIT 40` query took [3.6, 1.2, 1.1] ms; with sequential scans disabled 0.9 ms.

```
Limit  (cost=2390.30..2657.27 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2390.30..599564.51 rows=89473 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
--- enable_seqscan = off
Limit  (cost=2390.30..2657.27 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2390.30..599564.51 rows=89473 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
```

One `/parse-list` call (6 lines): 83.7 ms in total, 73.6 ms inside 43 SQL statements. The statements that cost the most:

| statement (first 110 characters) | calls | total ms | max ms |
|---|---|---|---|
| `WITH direct AS ( SELECT c.id AS canonical_id, 1 - (c.embedding <=> %(v)s::vector) AS s FROM canonical_products` | 6 | 37.8 | 8.0 |
| `WITH q AS (SELECT search_norm(%(q)s) AS t) SELECT c.id, word_similarity(q.t, search_norm(c.display_name_he)) A` | 6 | 18.7 | 6.3 |
| `WITH RECURSIVE up AS ( SELECT t.id AS leaf, t.id, t.parent_id, t.name_he, t.level FROM taxonomy t WHERE t.id =` | 6 | 4.2 | 0.9 |
| `SELECT c.id, c.display_name_he, ts_rank_cd(to_tsvector('simple', search_norm(c.display_name_he)), tq) AS r FRO` | 6 | 4.2 | 1.3 |
| `SELECT id, display_name_he, taxonomy_id, base_unit, rank, names_ar[1] FROM canonical_products WHERE id = ANY(%` | 6 | 3.3 | 0.7 |
| `SELECT set_config('hnsw.ef_search', %s, true), (SELECT set_config('hnsw.iterative_scan', 'relaxed_order', true` | 6 | 2.7 | 0.8 |

`EXPLAIN (ANALYZE, BUFFERS)` of the slowest statement:

```
Limit  (cost=3506.08..3506.10 rows=10 width=16) (actual rows=20 loops=1)
  Buffers: shared hit=2936
  ->  Sort  (cost=3506.08..3506.10 rows=10 width=16) (actual rows=20 loops=1)
        Sort Key: (max(direct.s)) DESC, direct.canonical_id
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=2936
        ->  GroupAggregate  (cost=3505.44..3505.91 rows=10 width=16) (actual rows=20 loops=1)
              Group Key: direct.canonical_id
              Buffers: shared hit=2936
              ->  Merge Append  (cost=3505.44..3505.76 rows=10 width=16) (actual rows=24 loops=1)
                    Sort Key: direct.canonical_id
                    Buffers: shared hit=2936
                    ->  Sort  (cost=30.82..30.84 rows=7 width=16) (actual rows=20 loops=1)
                          Sort Key: direct.canonical_id
                          Sort Method: quicksort  Memory: 25kB
                          Buffers: shared hit=1681
                          ->  Subquery Scan on direct  (cost=30.42..30.72 rows=7 width=16) (actual rows=20 loops=1)
                                Filter: (direct.s >= '0.25'::double precision)
                                Buffers: shared hit=1681
                                ->  Limit  (cost=30.42..30.47 rows=20 width=24) (actual rows=20 loops=1)
                                      Buffers: shared hit=1681
                                      ->  Sort  (cost=30.42..31.03 rows=245 width=24) (actual rows=20 loops=1)
                                            Sort Key: ((c.embedding <=> <query vector>))
                                            Sort Method: top-N heapsort  Memory: 27kB
                                            Buffers: shared hit=1681
                                            ->  Seq Scan on canonical_products c  (cost=0.00..23.90 rows=245 width=24) (actual rows=245 loops=1)
                                                  Filter: ((embedding IS NOT NULL) AND (embedding_model = 'hash-ngram-2-3-4-v1'::text))
                                                  Buffers: shared hit=1681
                    ->  GroupAggregate  (cost=3474.62..3474.82 rows=3 width=16) (actual rows=4 loops=1)
                          Group Key: ic.canonical_id
                          Filter: (max((('1'::double precision - (e.embedding <=> <query vector>)))) >= '0.25'::double precision)
                          Buffers: shared hit=1255
                          ->  Sort  (cost=3474.62..3474.64 rows=10 width=16) (actual rows=15 loops=1)
                                Sort Key: ic.canonical_id
                                Sort Method: quicksort  Memory: 25kB
                                Buffers: shared hit=1255
                                ->  Nested Loop  (cost=2390.59..3474.45 rows=10 width=16) (actual rows=15 loops=1)
                                      Buffers: shared hit=1255
                                      ->  Limit  (cost=2390.30..2924.25 rows=80 width=24) (actual rows=57 loops=1)
                                            Buffers: shared hit=1087
                                            ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2390.30..599564.51 rows=89473 width=24) (actual rows=57 loops=1)
                                                  Order By: (embedding <=> <query vector>)
                                                  Filter: (model = 'hash-ngram-2-3-4-v1'::text)
                                                  Buffers: shared hit=1087
                                      ->  Index Scan using item_canonical_pkey on item_canonical ic  (cost=0.29..6.86 rows=1 width=16) (actual rows=0 loops=57)
                                            Index Cond: (item_id = e.item_id)
                                            Filter: ((NOT human_rejected) AND (NOT needs_review) AND (flex_level = ANY ('{exact,any_brand}'::text[])))
                                            Rows Removed by Filter: 1
                                            Buffers: shared hit=168
Planning:
  Buffers: shared hit=475
Planning Time: 1.452 ms
Execution Time: 4.011 ms
```

### /parse-list, /compare and /optimize (production semantics)

Locations: Jerusalem centre (10 priced stores, 5 chains within 5 km); Haifa centre (8 priced stores, 5 chains within 5 km); Petah Tikva (8 priced stores, 5 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 144.1 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 249.3 |
| large (32 lines) | 33 | 33 | 5 | 0 | 379.3 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 10 | 0 | 11.1 | 9.9 | 16.3 | 55 | single: רמי לוי עטרות | 5.13 / 5.13 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 10 | 0 | 15.8 | 12.2 | 20.4 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 33 | 10 | 0 | 22.1 | 16 | 25.4 | 55 | single: רמי לוי עטרות | 54.67 / 54.67 |
| Jerusalem centre | drawn: 5 | 5 | 10 | 0 | 10.4 | 8.6 | 15.9 | 55 | single: אושר עד תלפיות | 8.07 / 8.07 |
| Jerusalem centre | drawn: 10 | 10 | 10 | 0 | 12.9 | 10.4 | 17.9 | 55 | split: אושר עד תלפיות, שופרסל גוד מרקט רש"י ירושלים | -9.38 / -9.38 |
| Jerusalem centre | drawn: 20 | 20 | 10 | 0 | 18.9 | 14.5 | 21.9 | 55 | single: רמי לוי עטרות | 30.08 / 30.08 |
| Jerusalem centre | drawn: 40 | 40 | 10 | 0 | 27.4 | 20.5 | 36.9 | 55 | single: רמי לוי עטרות | 105.68 / 105.68 |
| Haifa centre | hand: small (6 lines) | 6 | 8 | 0 | 9.2 | 7.6 | 13.3 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | hand: weekly (17 lines) | 17 | 8 | 0 | 14.4 | 9.9 | 16.5 | 55 | single: שופרסל שלי חיפה- קלר | -10.34 / -10.34 |
| Haifa centre | hand: large (32 lines) | 33 | 8 | 0 | 20.5 | 12.4 | 19.6 | 55 | single: שופרסל שלי חיפה- קלר | -12.25 / -12.25 |
| Haifa centre | drawn: 5 | 5 | 8 | 2 | 9.3 | 7.7 | 13.6 | 55 | single: שופרסל אקספרס יותם | 0.12 / 0.12 |
| Haifa centre | drawn: 10 | 10 | 8 | 0 | 11.1 | 8.7 | 13.8 | 55 | split: שופרסל שלי חיפה- קלר, טיב טעם מחניים | 33.94 / 33.94 |
| Haifa centre | drawn: 20 | 20 | 8 | 0 | 14.8 | 9.8 | 16.7 | 55 | single: שופרסל שלי חיפה- קלר | 320.81 / 320.81 |
| Haifa centre | drawn: 40 | 40 | 8 | 0 | 24.6 | 13.8 | 21.6 | 55 | single: שופרסל שלי חיפה- קלר | -22.4 / -22.4 |
| Petah Tikva | hand: small (6 lines) | 6 | 8 | 0 | 9.2 | 8.4 | 13.1 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 17.64 / 17.64 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 8 | 0 | 14.3 | 11.7 | 18.4 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 18.04 / 18.04 |
| Petah Tikva | hand: large (32 lines) | 33 | 8 | 0 | 19.3 | 15.1 | 21.9 | 55 | single: רמי לוי שטמפפר פתח תקווה | 0.0 / 0.0 |
| Petah Tikva | drawn: 5 | 5 | 8 | 4 | 10.1 | 9 | 15.4 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 8.96 / 8.96 |
| Petah Tikva | drawn: 10 | 10 | 8 | 0 | 12.2 | 9.8 | 16.4 | 55 | single: רמי לוי קניון אבנת פתח תקווה | -0.74 / -0.74 |
| Petah Tikva | drawn: 20 | 20 | 8 | 0 | 15.5 | 12.6 | 18.9 | 55 | single: רמי לוי שטמפפר פתח תקווה | 0.0 / 0.0 |
| Petah Tikva | drawn: 40 | 40 | 8 | 0 | 24 | 17.5 | 27.3 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 10.16 / 10.16 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 9.2 | 8.4 | 13.3 |
| hand: weekly (17 lines) | 14.4 | 11.7 | 18.4 |
| hand: large (32 lines) | 20.5 | 15.1 | 21.9 |
| drawn: 5 | 10.1 | 8.6 | 15.4 |
| drawn: 10 | 12.2 | 9.8 | 16.4 |
| drawn: 20 | 15.5 | 12.6 | 18.9 |
| drawn: 40 | 24.6 | 17.5 | 27.3 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 9.5 | 15 | - | - | 5.13 / 5.13 |
| Jerusalem centre | hand: weekly (17 lines) | 12.7 | 20.1 | אושר עד תלפיות, רמי לוי עטרות | אושר עד תלפיות, רמי לוי עטרות | 53.57 / 53.57 |
| Jerusalem centre | hand: large (32 lines) | 16 | 25.1 | - | - | 54.67 / 54.67 |
| Jerusalem centre | drawn: 5 | 9.3 | 15.8 | - | - | 8.07 / 8.07 |
| Jerusalem centre | drawn: 10 | 11 | 17.6 | אושר עד תלפיות, שופרסל גוד מרקט רש"י ירושלים | אושר עד תלפיות, שופרסל גוד מרקט רש"י ירושלים | 15.62 / 15.62 |
| Jerusalem centre | drawn: 20 | 13.9 | 21.5 | - | - | 30.08 / 30.08 |
| Jerusalem centre | drawn: 40 | 20.6 | 37 | אושר עד תלפיות, רמי לוי עטרות | אושר עד תלפיות, רמי לוי עטרות | 155.55 / 155.55 |
| Haifa centre | hand: small (6 lines) | 8 | 12.2 | - | - | 0.0 / 0.0 |
| Haifa centre | hand: weekly (17 lines) | 9.7 | 16.2 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 10.87 / 10.87 |
| Haifa centre | hand: large (32 lines) | 12.6 | 19.6 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 11.27 / 11.27 |
| Haifa centre | drawn: 5 | 7.9 | 13.7 | - | - | 0.12 / 0.12 |
| Haifa centre | drawn: 10 | 8.8 | 14.1 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 58.94 / 58.94 |
| Haifa centre | drawn: 20 | 9.9 | 17 | - | - | 320.81 / 320.81 |
| Haifa centre | drawn: 40 | 13.8 | 22.2 | - | - | -22.4 / -22.4 |
| Petah Tikva | hand: small (6 lines) | 8.8 | 13.6 | - | - | 17.64 / 17.64 |
| Petah Tikva | hand: weekly (17 lines) | 11.4 | 17.9 | - | - | 18.04 / 18.04 |
| Petah Tikva | hand: large (32 lines) | 14.7 | 21.9 | - | - | 0.0 / 0.0 |
| Petah Tikva | drawn: 5 | 9.3 | 15.7 | רמי לוי שטמפפר פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | רמי לוי שטמפפר פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | 14.07 / 14.07 |
| Petah Tikva | drawn: 10 | 10.1 | 16.7 | - | - | -0.74 / -0.74 |
| Petah Tikva | drawn: 20 | 12.3 | 19 | - | - | 0.0 / 0.0 |
| Petah Tikva | drawn: 40 | 17 | 25.7 | - | - | 10.16 / 10.16 |

### Basket index on the real day (#44, dry run, production semantics)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `missing_items` שופרסל has no price for 8 basket items (yellow-cheese-sliced-28, butter, eggs-l, cucumber, banana, pita, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` שופרסל: 4 lines use estimated weighed-goods prices
- warning: `missing_items` קינג סטור has no price for 15 basket items (cottage-5, yellow-cheese-sliced-28, butter, eggs-l, chicken-breast-fresh, hummus-plain, tomato, cucumber, banana, bread-standard, pita, pasta-spaghetti, tuna-in-oil, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` קינג סטור: 2 lines use estimated weighed-goods prices
- warning: `missing_items` רמי לוי has no price for 7 basket items (butter, hummus-plain, cucumber, potato, banana, pasta-spaghetti, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` רמי לוי: 3 lines use estimated weighed-goods prices
- warning: `missing_items` אושר עד has no price for 12 basket items (milk-fresh-3, white-cheese-5, yellow-cheese-sliced-28, yogurt-plain-3, eggs-l, hummus-plain, tomato, cucumber, pasta-spaghetti, sugar-white, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` אושר עד: 3 lines use estimated weighed-goods prices
- warning: `missing_items` יוחננוף has no price for 12 basket items (yellow-cheese-sliced-28, butter, eggs-l, hummus-plain, tomato, cucumber, potato, banana, pita, pasta-spaghetti, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` יוחננוף: 2 lines use estimated weighed-goods prices
- warning: `missing_items` טיב טעם has no price for 12 basket items (milk-fresh-3, yellow-cheese-sliced-28, yogurt-plain-3, butter, eggs-l, hummus-plain, pita, pasta-spaghetti, tuna-in-oil, mineral-water, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` טיב טעם: 6 lines use estimated weighed-goods prices
- error: `too_few_chains` only 0 chain(s) price the whole basket; at least 2 needed

Basket of 25 lines; price date 2026-10-22T15:00:05Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| שופרסל | - | 17 | 8 | 7 | no |
| קינג סטור | - | 10 | 15 | 3 | no |
| רמי לוי | - | 18 | 7 | 7 | no |
| אושר עד | - | 13 | 12 | 5 | no |
| יוחננוף | - | 13 | 12 | 3 | no |
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
| mineral-water* | 60 | 10.93 | 10.6 | 9.94 | 67.73 | 9.94 | - |
| onion | 1 | 5.9 | 5.45 | 4.9 | 4.9 | 4.9 | 5.9 |
| pasta-spaghetti | 5 | 2.75 | - | - | - | - | - |
| pita | 10 | - | - | 11.9 | 11.9 | - | - |
| potato | 2 | 13.8 | 13.8 | - | 13.56 | - | 17.8 |
| rice-persian | 10 | 10.0 | 7.9 | 6.0 | 7.07 | 6.0 | 10.9 |
| sugar-white* | 10 | 3.95 | 4.9 | 3.33 | - | 11.9 | 5.5 |
| toilet-paper* | 24 | 813.6 | 20.93 | 597.6 | 405.6 | 420.0 | 24.67 |
| tomato* | 1.5 | 29.85 | - | 25.35 | - | - | 13.35 |
| tuna-in-oil | 4.8 | 18.3 | - | 19.89 | 17.59 | 14.93 | - |
| white-cheese-5 | 5 | 11.74 | 11.74 | 11.6 | - | 11.74 | 11.74 |
| yellow-cheese-sliced-28 | 4 | - | - | 14.0 | - | - | - |
| yogurt-plain-3* | 8 | 29.6 | 18.8 | 12.0 | - | 14.4 | - |

Items behind `yogurt-plain-3` (up to 3 per chain, cheapest unit price first):
- shufersal: יוגורט עזים טבעי 3% 200ג, shelf 7.3, unit price 3.65 per 100g
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
- shufersal: עגבניות מגי ארוז, shelf 18.9, unit price 18.9 per kg (estimated)
- shufersal: עגבניות מגי ארוז, shelf 19.9, unit price 19.9 per kg (estimated)
- shufersal: עגבניות מגי ארוז, shelf 19.9, unit price 19.9 per kg (estimated)
- ramilevy: עגבניות מגי, shelf 13.9, unit price 13.9 per kg (estimated)
- ramilevy: עגבניות מגי, shelf 13.9, unit price 13.9 per kg (estimated)
- ramilevy: עגבניות מגי, shelf 15.9, unit price 15.9 per kg (estimated)
- tivtaam: עגבניות, shelf 7.9, unit price 7.9 per kg (estimated)
- tivtaam: עגבניות, shelf 7.9, unit price 7.9 per kg (estimated)
- tivtaam: עגבניות, shelf 8.9, unit price 8.9 per kg (estimated)

Items behind `sugar-white` (up to 3 per chain, cheapest unit price first):
- shufersal: סוכר לבן 1 ק"ג, shelf 5.9, unit price 0.3333 per 100g
- shufersal: סוכר לבן 1 ק"ג, shelf 5.9, unit price 0.3333 per 100g
- shufersal: סוכר לבן 1 ק"ג, shelf 5.5, unit price 0.3333 per 100g
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
- shufersal: מים מינרליים מי עדן6*1.5, shelf 16.3, unit price 0.1811 per 100ml
- king_store: שישיית מים מינרליים 6* 1.5 ל' מי עדן, shelf 15.9, unit price 0.1767 per 100ml
- king_store: שישיית מים מינרליים 6* 1.5 ל' מי עדן, shelf 15.9, unit price 0.1767 per 100ml
- ramilevy: מים מינרלים מי עדן 6, shelf 14.9, unit price 0.1656 per 100ml
- ramilevy: מים מינרלים מי עדן 6, shelf 14.9, unit price 0.1656 per 100ml
- ramilevy: מים מינרלים מי עדן 6, shelf 14.9, unit price 0.1656 per 100ml
- osherad: מארז מים מינרלים מוג, shelf 14.9, unit price 1.1288 per 100ml
- yohananof: מים מינרלים  מי עדן, shelf 14.9, unit price 0.1656 per 100ml
- yohananof: מים מינרלים  מי עדן, shelf 14.9, unit price 0.1656 per 100ml
- yohananof: מים מינרלים  מי עדן, shelf 14.9, unit price 0.1656 per 100ml

Items behind `toilet-paper` (up to 3 per chain, cheapest unit price first):
- shufersal: נייר טואלט פרימ."יש"32גל, shelf 25.9, unit price 25.9 per unit
- shufersal: נייר טואלט פרימ."יש"32גל, shelf 25.9, unit price 25.9 per unit
- shufersal: נייר טואלט דו שכבתיXPO32, shelf 35.9, unit price 29.9 per unit
- king_store: נייר טואלט 32 גלילים שמורת טבע, shelf 27.9, unit price 0.8719 per unit
- king_store: נייר טואלט 32 גלילים שמורת טבע, shelf 27.9, unit price 0.8719 per unit
- king_store: נייר טואלט 32 גלילים שמורת טבע, shelf 27.9, unit price 0.8719 per unit
- ramilevy: נייר טואלט טאץ 32 יח, shelf 37.9, unit price 1.1844 per unit
- ramilevy: נייר טואלט טאץ 32 יח, shelf 37.9, unit price 1.1844 per unit
- ramilevy: נייר טואלט רויאל 32, shelf 24.9, unit price 24.9 per unit
- osherad: נייר טואלט חתוך הנמל, shelf 7.9, unit price 7.9 per unit
- osherad: נייר טואלט חתוך הנמל, shelf 16.9, unit price 16.9 per unit
- osherad: נייר טואלט חתוך הנמל, shelf 16.9, unit price 16.9 per unit
- yohananof: נייר טואלט עבים במיו, shelf 19.9, unit price 17.5 per unit
- yohananof: נייר טואלט עבים במיו, shelf 19.9, unit price 17.5 per unit
- yohananof: נייר טואלט עבים במיו, shelf 19.9, unit price 17.5 per unit
- tivtaam: נייר טואלט מולט 32 גלילים, shelf 32.9, unit price 1.0281 per unit
- tivtaam: נייר טואלט מולט 32 גלילים, shelf 32.9, unit price 1.0281 per unit
- tivtaam: נייר טואלט מולט 32 גלילים, shelf 32.9, unit price 1.0281 per unit

### Basket lines that no chain prices: the real items that could have been them

Items whose names mention the product, with the attributes extraction gave them, the mapping they got and the rule judge's own reason (re-run for this report, nothing written). The `hint` columns are a reading aid of this script, not the catalog's rules.

#### `butter`: 60 listed of 254 name hits (0 skipped as not the food itself; chains looked in: shufersal, king_store, ramilevy, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | חמאה רכה 250 גרם | ? / ? | butter | 250 g | butter close 0.89 review | review: butter (חמאה): similarity 0.61 \| critical match product_type=butter \| soft differs pack_size 250 vs 200 g \| level close, confidence 0.89 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.13 \| critical mismatch product |
| shufersal | חמאה מלוחה רכה 250גרם | ? / ? | butter | 250 g | butter close 0.81 review | review: butter (חמאה): similarity 0.52 \| critical match product_type=butter \| soft differs pack_size 250 vs 200 g \| level close, confidence 0.81 \| vetoed: grated-mozzarella (גבינה מגורדת (מוצרלה)): similarity 0.13 \| critical misma |
| shufersal | חמאה לה גל זהב 200 גרם | ? / ? | butter | 200 g | butter any_brand 0.76 review | review: butter (חמאה): similarity 0.46 \| critical match product_type=butter \| level any_brand, confidence 0.76 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.13 \| critical mismatch product_type butter vs sour_cream \| criti |
| shufersal | חמאה לה גל זהב עם מלח200 | ? / ? | butter | 200 g | butter any_brand 0.78 review | review: butter (חמאה): similarity 0.47 \| critical match product_type=butter \| level any_brand, confidence 0.78 \| vetoed: pudding-chocolate-cream (מעדן שוקולד עם קצפת): similarity 0.11 \| critical mismatch product_type butter vs pud |
| shufersal | חמאה 60% אלוויר 200 גרם | ? / ? | butter | 200 g | butter any_brand 0.75 review | review: butter (חמאה): similarity 0.44 \| critical match product_type=butter \| level any_brand, confidence 0.75 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.10 \| critical mismatch product_type butter vs sour_cream; fat_pc |
| shufersal | חמאה מלוחה אלוויר 200 גר | ? / ? | butter | 200 g | butter any_brand 0.77 review | review: butter (חמאה): similarity 0.46 \| critical match product_type=butter \| level any_brand, confidence 0.77 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.11 \| critical mismatch product_type butter vs sour_cream \| criti |
| shufersal | סוכריות חמאה וורטר135גרם | ? / ? | butter | 135 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.44 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; sour-cream-15 (שמנת חמוצה 15%): similarity 0.08 |
| shufersal | סוכריות חמאה לל"ס80 ורטר | ? / ? | butter | 80 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.42 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; yogurt-strawberry (יוגורט תות): similarity 0.13 |
| shufersal | סוכריות חמאה 50 גרם ורטר | ? / ? | butter | 50 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.43 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; yogurt-strawberry (יוגורט תות): similarity 0.16 |
| shufersal | חמאה FERMA 82.5%גרם 200 | ? / ? | butter | 200 g | butter any_brand 0.75 review | review: butter (חמאה): similarity 0.43 \| critical match product_type=butter \| level any_brand, confidence 0.75 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.10 \| critical mismatch product_type butter vs sour_cream; fat_pc |
| shufersal | ביסקויט לקפה חמאה185רושן | ? / ? | butter | 185 g | butter close 0.63 review | review: butter (חמאה): similarity 0.29 \| critical match product_type=butter \| soft differs pack_size 185 vs 200 g \| level close, confidence 0.63 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.08 \| critical mismatch product |
| shufersal | חמאה 82.5% רושן 200 גרם | ? / ? | butter | 200 g | butter any_brand 0.74 review | review: butter (חמאה): similarity 0.43 \| critical match product_type=butter \| level any_brand, confidence 0.74 \| vetoed: labane-5 (לבנה 5%): similarity 0.25 \| critical mismatch product_type butter vs labane; fat_pct 82.5 vs 5 ; co |
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

#### `chocolate-milk`: 72 listed of 3493 name hits (0 skipped as not the food itself; chains looked in: shufersal, king_store, ramilevy, osherad, yohananof, tivtaam)

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
| shufersal | שוקולד לינדור סטיק 38גרם | ? / ? | chocolate_bar | 38 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.44 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.42 \| criti |
| shufersal | קורני חט.דגנים+שוקולד6יח | ? / ? | - | 150 g | - | rejected (confidence 0.42 < 0.6): dessert-chocolate (מעדן חלב שוקולד): similarity 0.23 \| critical match flavor=chocolate \| critical unknown product_type \| soft differs pack_size 150 vs 125 g \| ambiguous with wafers-chocolate \| lev |
| shufersal | ח.דגנים שוקו.מריר6 קורני | ? / ? | - | 138 g | - | rejected (confidence 0.42 < 0.6): dessert-chocolate (מעדן חלב שוקולד): similarity 0.17 \| critical match flavor=chocolate \| critical unknown product_type \| soft differs pack_size 138 vs 125 g \| ambiguous with wafers-chocolate \| lev |
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

#### `eggs-l`: 161 listed of 312 name hits (145 skipped as not the food itself; chains looked in: shufersal, king_store, osherad, yohananof, tivtaam)

Name hint of the size against what the item got (served = no review flag):

| size words in the name | result | items |
|---|---|---|
| ? | review | 8 |
| ? | unmapped | 79 |
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
| XL | unmapped | 1 |

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | ביצים ארוזות XL 12יחידות | XL / 12 | eggs_xl | 12 unit | eggs-xl any_brand 0.81 review | review: eggs-xl (ביצים XL): similarity 0.51 \| critical match product_type=eggs_xl \| level any_brand, confidence 0.81 \| vetoed: eggs-m (ביצים M): similarity 0.36 \| critical mismatch product_type eggs_xl vs eggs_m ; eggs-l (ביצים L) |
| shufersal | 12 ביצי משק טריות L לסר | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.68 review | review: eggs-l (ביצים L): similarity 0.35 \| critical match product_type=eggs_l \| level any_brand, confidence 0.68 \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.43 \| critical mismatch product_type eggs_l vs eggs_free_rang |
| shufersal | 12 ביצי משק טריות M לסר | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.68 review | review: eggs-m (ביצים M): similarity 0.35 \| critical match product_type=eggs_m \| level any_brand, confidence 0.68 \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.28 \| critical mismatch product_type eggs_m vs eggs_free_rang |
| shufersal | 30ביצי אומגה3 שופרסל | ? / 30 | eggs | 30 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.16 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.14 \| critical mismatch product_type eggs vs eggs_xl ;  |
| shufersal | ביצים אומגה 3 DHA XL 20י | XL / 20 | eggs | 20 unit | - | every candidate vetoed \| vetoed: eggs-xl (ביצים XL): similarity 0.50 \| critical mismatch product_type eggs vs eggs_xl ; eggs-l (ביצים L): similarity 0.32 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similari |
| shufersal | ביצים אומגה3 12יחידות L | L / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.58 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.39 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| shufersal | ביצי חופש 12יח L | L / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 1.00 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.86 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 1.00 \| vetoed: eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs_free_ran |
| shufersal | ביצי חופש 12יח M | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.69 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs vs eggs_m ; egg |
| shufersal | 12ביצי אומגה3 M לסר | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.30 \| critical mismatch product_type eggs vs eggs_m ; eggs-free-range-l (ביצי חופש L): similarity 0.16 \| critical mismatch product_type eggs vs eggs_free_range_l ; egg |
| shufersal | נודלס ביצים 500 גרם | ? / ? | - | 500 g | - | rejected (confidence 0.34 < 0.6): egg-noodles (אטריות ביצים): similarity 0.37 \| critical unknown product_type \| level any_brand, confidence 0.34 |
| shufersal | איטריות ביצים אוריאנט500 | ? / ? | - | 500 g | - | rejected (confidence 0.50 < 0.6): egg-noodles (אטריות ביצים): similarity 0.57 \| critical unknown product_type \| level any_brand, confidence 0.50 |
| shufersal | ביצי שוקול.סוניק 3*20גרם | ? / 60 | - | 60 g | - | rejected (confidence 0.24 < 0.6): wafers-chocolate (ופלים בטעם שוקולד): similarity 0.25 \| critical unknown product_type, flavor \| soft differs pack_size 60 vs 500 g \| ambiguous with chocolate-milk-bar \| level close, confidence 0.2 |
| shufersal | 12ביצים חופש אורגניות M | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.43 \| critical mismatch product_type eggs vs eggs_m ; eggs-free-range-l (ביצי חופש L): similarity 0.36 \| critical mismatch product_type eggs vs eggs_free_range_l ; egg |
| shufersal | 12ביצי חופש אורגניLגרין | L / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.13 \| critical mismatch product_type eggs vs eggs_xl ;  |
| shufersal | ביצים ארוזות 18יח L | L / 18 | eggs_l | 18 unit | eggs-l close 0.92 | accept: eggs-l (ביצים L): similarity 0.65 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.92 \| vetoed: eggs-m (ביצים M): similarity 0.51 \| critical mismatch product_type eggs |
| shufersal | ביצים ארוזות 18יח M | M / 18 | eggs_m | 18 unit | eggs-m close 0.95 | accept: eggs-m (ביצים M): similarity 0.68 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.95 \| vetoed: eggs-l (ביצים L): similarity 0.45 \| critical mismatch product_type eggs |
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
| osherad | פוליויקס סחלבים 4 לי | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): grapes (ענבים): similarity 0.16 \| critical unknown product_type, state \| ambiguous with lemon-lime-soda \| level any_brand, confidence 0.24 |
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

#### `yellow-cheese-sliced-28`: 60 listed of 423 name hits (0 skipped as not the food itself; chains looked in: shufersal, king_store, osherad, yohananof, tivtaam)

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
| shufersal | גאודה מעושנת 30% במשקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| shufersal | גאודה 28% במשקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| shufersal | משולש גבינת גאודה28%משקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| shufersal | משולש גאודה כמון משקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
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

### Failures and findings the run recorded (1)

- **basket index**: chocolate-milk is priced at no chain (candidates in the report)

