## One real day through the pipeline (dry run)

Mode `portal`, commit `3c7551968e8c`, runner `GitHub Actions 1000004786` (4 CPUs, Python 3.12.3, Postgres 17.11), 2026-10-21T19:00:05+00:00 to 2026-10-21T19:37:12+00:00 UTC. Measurements on one real day with hand-made baskets; the prices are real, the baskets and locations are not a sample of anything. **Not publishable.**

### Stages

| stage | seconds | result |
|---|---|---|
| download: portal probe (one Stores and one PriceFull per chain) | 690.82 | ok |
| migrate | 1.14 | 25 applied |
| ingest: Stores files (Scheduler, adapters, gates, loader, store coordinates) | 0.47 | 7 files |
| download: PriceFull and PromoFull of the stores nearest to city centres | 762.34 | 54 files, anchors: Haifa centre, Jerusalem centre, Petah Tikva |
| ingest: PriceFull and PromoFull files (Scheduler, adapters, gates, loader) | 92.26 | 61 files |
| catalog: seed | 1.01 | ok |
| catalog: normalize | 7.7 | ok |
| catalog: extract (rule) | 72.28 | ok |
| catalog: embed (hash) | 317.16 | ok |
| catalog: judge (rule) | 190.88 | ok |
| precompute effective prices (production semantics: reviewed mappings only) | 1.04 | 6977 rows |
| API: parse-list, compare, optimize (production) | 44.46 | 21 basket runs at 3 locations |
| diagnostic: the vector query behind /parse-list and /search | 0.03 | [3.7, 1.4, 1.2] ms per query |
| basket index dry run (production semantics) | 0.42 | status draft |
| stress: mark the machine suggestions accepted (performance only) | 0.25 | 14341 mappings |
| precompute effective prices (stress: unreviewed mappings included) | 1.93 | 11463 rows |
| API: parse-list, compare, optimize (stress) | 41.4 | 21 basket runs at 3 locations |
| basket index dry run (stress) | 0.39 | status draft |

### Portals (the portal probe's own reachability and downloads)

| chain | reachable | login | Stores download | PriceFull download |
|---|---|---|---|---|
| hazihinam | BLOCKED? (403) | n/a | no: no file downloaded | no: no file downloaded |
| king_store | BLOCKED? (403) | n/a | Stores7290058108879-000-20261021-040448.gz | PriceFull7290058108879-000-340-20261021-040448.gz |
| machsanei_hashuk | UNREACHABLE (0) | n/a | no: no file downloaded | no: no file downloaded |
| mega | OK (200) | n/a | Stores7290055700007-000-20261021-000100.xml | PriceFull7290055700007-001-002-20261021-051019.gz |
| osherad | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290103152017-000-20261019-080501.xml | PriceFull7290103152017-001-001-20261021-080011.gz |
| ramilevy | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290058140886-000-20261019-050500.xml | PriceFull7290058140886-001-001-20261021-001002.gz |
| shufersal | OK (200) | n/a | Stores7290027600007-000-20261021-020.gz | PriceFull7290027600007-001-164-20261021-043100.gz |
| tivtaam | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290873255550-000-20261019-050501.xml | PriceFull7290873255550-000-002-20261021-004004.gz |
| victory | UNREACHABLE (0) | n/a | no: no file downloaded | no: no file downloaded |
| yohananof | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290803800003-000-20261019-010000.xml | PriceFull7290803800003-000-001-20261021-004031.gz |

### Files, gates and rows per chain

| chain | kind | file | published (Israel) | age h | schema | gate result | rows | seconds |
|---|---|---|---|---|---|---|---|---|
| king_store | stores | `Stores7290058108879-000-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 18.1 | v1 | loaded | 48 | 0.06 |
| mega | stores | `Stores7290055700007-000-20261021-000100.xml` | 2026-10-21T00:01+03:00 | 22.2 | v1 | loaded | 147 | 0.07 |
| osherad | stores | `Stores7290103152017-000-20261019-080501.xml` | 2026-10-19T08:05+03:00 | 62.1 (stale on the real clock) | v1 | loaded | 24 | 0.04 |
| ramilevy | stores | `Stores7290058140886-000-20261019-050500.xml` | 2026-10-19T05:05+03:00 | 65.1 (stale on the real clock) | v1 | loaded | 99 | 0.05 |
| shufersal | stores | `Stores7290027600007-000-20261021-020.gz` | 2026-10-21T02:00+03:00 | 20.2 | v1 | loaded | 417 | 0.15 |
| tivtaam | stores | `Stores7290873255550-000-20261019-050501.xml` | 2026-10-19T05:05+03:00 | 65.1 (stale on the real clock) | v1 | loaded | 54 | 0.04 |
| yohananof | stores | `Stores7290803800003-000-20261019-010000.xml` | 2026-10-19T01:00+03:00 | 69.2 (stale on the real clock) | v1 | loaded | 51 | 0.03 |
| king_store | price_full | `PriceFull7290058108879-000-340-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 18.3 | v1 | loaded | 2,336 | 0.36 |
| mega | price_full | `PriceFull7290055700007-001-002-20261021-051019.gz` | 2026-10-21T05:10+03:00 | 17.2 | v1 | loaded | 5,899 | 0.86 |
| osherad | price_full | `PriceFull7290103152017-001-001-20261021-080011.gz` | 2026-10-21T08:00+03:00 | 14.4 | v1 | loaded | 6,508 | 0.93 |
| ramilevy | price_full | `PriceFull7290058140886-001-001-20261021-001002.gz` | 2026-10-21T00:10+03:00 | 22.2 | v1 | loaded | 12,976 | 1.96 |
| shufersal | price_full | `PriceFull7290027600007-001-164-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 17.9 | v1 | loaded | 5,556 | 0.82 |
| tivtaam | price_full | `PriceFull7290873255550-000-002-20261021-004004.gz` | 2026-10-21T00:40+03:00 | 21.7 | v1 | loaded | 21,598 | 3.24 |
| yohananof | price_full | `PriceFull7290803800003-000-001-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 21.7 | v1 | loaded | 10,732 | 1.64 |
| king_store | price_full | `PriceFull7290058108879-000-014-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 18.3 | v1 | loaded | 4,833 | 0.69 |
| king_store | price_full | `PriceFull7290058108879-000-200-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 18.3 | v1 | loaded | 3,628 | 0.53 |
| king_store | promo_full | `PromoFull7290058108879-000-014-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 18.3 | v1 | loaded | 430 | 0.09 |
| king_store | promo_full | `PromoFull7290058108879-000-200-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 18.3 | v1 | loaded | 313 | 0.07 |
| mega | price_full | `PriceFull7290055700007-001-091-20261021-051007.gz` | 2026-10-21T05:10+03:00 | 17.2 | v1 | loaded | 6,825 | 1.02 |
| mega | price_full | `PriceFull7290055700007-001-418-20261021-051008.gz` | 2026-10-21T05:10+03:00 | 17.2 | v1 | loaded | 5,782 | 0.88 |
| mega | price_full | `PriceFull7290055700007-001-452-20261021-051010.gz` | 2026-10-21T05:10+03:00 | 17.2 | v1 | loaded | 8,176 | 1.27 |
| mega | price_full | `PriceFull7290055700007-001-457-20261021-051015.gz` | 2026-10-21T05:10+03:00 | 17.2 | v1 | loaded | 9,248 | 1.4 |
| mega | price_full | `PriceFull7290055700007-001-407-20261021-051019.gz` | 2026-10-21T05:10+03:00 | 17.2 | v1 | loaded | 8,576 | 1.31 |
| mega | price_full | `PriceFull7290055700007-001-470-20261021-064437.gz` | 2026-10-21T06:44+03:00 | 15.7 | v1 | loaded | 4,836 | 0.7 |
| mega | promo_full | `PromoFull7290055700007-001-418-20261021-051058.gz` | 2026-10-21T05:10+03:00 | 17.2 | v1 | loaded | 1,445 | 0.37 |
| mega | promo_full | `PromoFull7290055700007-001-091-20261021-051103.gz` | 2026-10-21T05:11+03:00 | 17.2 | v1 | loaded | 1,530 | 0.47 |
| mega | promo_full | `PromoFull7290055700007-001-452-20261021-051116.gz` | 2026-10-21T05:11+03:00 | 17.2 | v1 | loaded | 1,518 | 0.4 |
| mega | promo_full | `PromoFull7290055700007-001-407-20261021-051125.gz` | 2026-10-21T05:11+03:00 | 17.2 | v1 | loaded | 1,465 | 0.33 |
| mega | promo_full | `PromoFull7290055700007-001-457-20261021-051126.gz` | 2026-10-21T05:11+03:00 | 17.2 | v1 | loaded | 1,437 | 0.38 |
| mega | promo_full | `PromoFull7290055700007-001-470-20261021-064509.gz` | 2026-10-21T06:45+03:00 | 15.7 | v1 | loaded | 1,433 | 0.35 |
| osherad | price_full | `PriceFull7290103152017-001-026-20261021-140501.gz` | 2026-10-21T14:05+03:00 | 8.3 | v1 | loaded | 6,836 | 0.97 |
| osherad | price_full | `PriceFull7290103152017-001-030-20261021-140501.gz` | 2026-10-21T14:05+03:00 | 8.3 | v1 | loaded | 6,465 | 0.96 |
| osherad | price_full | `PriceFull7290103152017-001-010-20261021-140502.gz` | 2026-10-21T14:05+03:00 | 8.3 | v1 | loaded | 6,699 | 1.1 |
| osherad | price_full | `PriceFull7290103152017-001-028-20261021-140502.gz` | 2026-10-21T14:05+03:00 | 8.3 | v1 | loaded | 6,246 | 0.93 |
| osherad | promo_full | `PromoFull7290103152017-001-028-20261021-140522.gz` | 2026-10-21T14:05+03:00 | 8.3 | v1 | loaded | 716 | 0.17 |
| osherad | promo_full | `PromoFull7290103152017-001-026-20261021-140527.gz` | 2026-10-21T14:05+03:00 | 8.3 | v1 | loaded | 734 | 0.16 |
| osherad | promo_full | `PromoFull7290103152017-001-030-20261021-140545.gz` | 2026-10-21T14:05+03:00 | 8.3 | v1 | loaded | 750 | 0.18 |
| osherad | promo_full | `PromoFull7290103152017-001-010-20261021-140558.gz` | 2026-10-21T14:05+03:00 | 8.3 | v1 | loaded | 705 | 0.2 |
| ramilevy | price_full | `PriceFull7290058140886-001-062-20261021-120007.gz` | 2026-10-21T12:00+03:00 | 10.4 | v1 | loaded | 14,121 | 2.05 |
| ramilevy | price_full | `PriceFull7290058140886-001-703-20261021-120007.gz` | 2026-10-21T12:00+03:00 | 10.4 | v1 | loaded | 4,955 | 0.73 |
| ramilevy | price_full | `PriceFull7290058140886-001-048-20261021-120011.gz` | 2026-10-21T12:00+03:00 | 10.4 | v1 | loaded | 14,448 | 2.24 |
| ramilevy | price_full | `PriceFull7290058140886-001-057-20261021-121509.gz` | 2026-10-21T12:15+03:00 | 10.2 | v1 | loaded | 13,927 | 2.17 |
| ramilevy | price_full | `PriceFull7290058140886-001-724-20261021-180005.gz` | 2026-10-21T18:00+03:00 | 4.4 | v1 | loaded | 5,164 | 0.81 |
| ramilevy | price_full | `PriceFull7290058140886-001-725-20261021-180015.gz` | 2026-10-21T18:00+03:00 | 4.4 | v1 | loaded | 4,119 | 0.64 |
| ramilevy | promo_full | `PromoFull7290058140886-001-703-20261021-120038.gz` | 2026-10-21T12:00+03:00 | 10.4 | v1 | loaded | 1,108 | 0.28 |
| ramilevy | promo_full | `PromoFull7290058140886-001-048-20261021-120055.gz` | 2026-10-21T12:00+03:00 | 10.4 | v1 | loaded | 2,525 | 0.73 |
| ramilevy | promo_full | `PromoFull7290058140886-001-062-20261021-120113.gz` | 2026-10-21T12:01+03:00 | 10.4 | v1 | loaded | 2,532 | 0.84 |
| ramilevy | promo_full | `PromoFull7290058140886-001-057-20261021-121655.gz` | 2026-10-21T12:16+03:00 | 10.1 | v1 | loaded | 2,532 | 0.92 |
| ramilevy | promo_full | `PromoFull7290058140886-001-724-20261021-180029.gz` | 2026-10-21T18:00+03:00 | 4.4 | v1 | loaded | 1,060 | 0.28 |
| ramilevy | promo_full | `PromoFull7290058140886-001-725-20261021-180038.gz` | 2026-10-21T18:00+03:00 | 4.4 | v1 | loaded | 1,047 | 0.28 |
| shufersal | promo_full | `PromoFull7290027600007-001-002-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 17.9 | v1 | loaded | 1,379 | 0.78 |
| shufersal | promo_full | `PromoFull7290027600007-001-302-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 17.9 | v1 | loaded | 1,281 | 0.82 |
| shufersal | promo_full | `PromoFull7290027600007-006-300-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 17.9 | v1 | loaded | 1,008 | 1.05 |
| shufersal | promo_full | `PromoFull7290027600007-007-285-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 17.9 | v1 | loaded | 743 | 0.46 |
| shufersal | promo_full | `PromoFull7290027600007-007-353-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 17.9 | v1 | loaded | 616 | 0.37 |
| shufersal | promo_full | `PromoFull7290027600007-018-753-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 17.9 | v1 | loaded | 418 | 0.37 |
| tivtaam | price_full | `PriceFull7290873255550-000-012-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 6.9 | v1 | loaded | 17,832 | 2.83 |
| tivtaam | price_full | `PriceFull7290873255550-000-085-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 6.9 | v1 | loaded | 7,171 | 1.13 |
| tivtaam | price_full | `PriceFull7290873255550-000-087-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 6.9 | v1 | loaded | 6,069 | 0.86 |
| tivtaam | price_full | `PriceFull7290873255550-000-092-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 6.9 | v1 | loaded | 5,851 | 0.87 |
| tivtaam | promo_full | `PromoFull7290873255550-000-012-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 6.9 | v1 | loaded | 2,040 | 1.26 |
| tivtaam | promo_full | `PromoFull7290873255550-000-085-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 6.9 | v1 | loaded | 1,282 | 2.2 |
| tivtaam | promo_full | `PromoFull7290873255550-000-087-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 6.9 | v1 | loaded | 1,126 | 1.36 |
| tivtaam | promo_full | `PromoFull7290873255550-000-092-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 6.9 | v1 | loaded | 1,060 | 0.82 |
| yohananof | price_full | `PriceFull7290803800003-000-020-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 21.8 | v1 | loaded | 11,887 | 1.81 |
| yohananof | price_full | `PriceFull7290803800003-000-021-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 21.8 | v1 | loaded | 11,197 | 1.67 |
| yohananof | promo_full | `PromoFull7290803800003-000-020-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 21.8 | v1 | loaded | 1,277 | 0.28 |
| yohananof | promo_full | `PromoFull7290803800003-000-021-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 21.8 | v1 | loaded | 1,212 | 0.27 |

PromoFull files: what they hold and how much reached `promo_items`:

| chain | file | promos | with item codes | distinct codes | codes the chain's items know | promo_items linked | active now | club | rewards |
|---|---|---|---|---|---|---|---|---|---|
| king_store | `PromoFull7290058108879-000-014-20261021-040448.gz` | 430 | 0 | 0 | 0 | 0 | 430 | 106 | {'other': 430} |
| king_store | `PromoFull7290058108879-000-200-20261021-040448.gz` | 313 | 0 | 0 | 0 | 0 | 313 | 82 | {'other': 313} |
| mega | `PromoFull7290055700007-001-418-20261021-051058.gz` | 1,445 | 0 | 0 | 0 | 0 | 1,445 | 11 | {'other': 1445} |
| mega | `PromoFull7290055700007-001-091-20261021-051103.gz` | 1,530 | 0 | 0 | 0 | 0 | 1,530 | 11 | {'other': 1530} |
| mega | `PromoFull7290055700007-001-452-20261021-051116.gz` | 1,518 | 0 | 0 | 0 | 0 | 1,518 | 11 | {'other': 1518} |
| mega | `PromoFull7290055700007-001-407-20261021-051125.gz` | 1,465 | 0 | 0 | 0 | 0 | 1,465 | 11 | {'other': 1465} |
| mega | `PromoFull7290055700007-001-457-20261021-051126.gz` | 1,437 | 0 | 0 | 0 | 0 | 1,437 | 11 | {'other': 1437} |
| mega | `PromoFull7290055700007-001-470-20261021-064509.gz` | 1,433 | 0 | 0 | 0 | 0 | 1,433 | 11 | {'other': 1433} |
| osherad | `PromoFull7290103152017-001-028-20261021-140522.gz` | 716 | 0 | 0 | 0 | 0 | 716 | 0 | {'other': 716} |
| osherad | `PromoFull7290103152017-001-026-20261021-140527.gz` | 734 | 0 | 0 | 0 | 0 | 734 | 0 | {'other': 734} |
| osherad | `PromoFull7290103152017-001-030-20261021-140545.gz` | 750 | 0 | 0 | 0 | 0 | 750 | 0 | {'other': 750} |
| osherad | `PromoFull7290103152017-001-010-20261021-140558.gz` | 705 | 0 | 0 | 0 | 0 | 705 | 0 | {'other': 705} |
| ramilevy | `PromoFull7290058140886-001-703-20261021-120038.gz` | 1,108 | 0 | 0 | 0 | 0 | 1,108 | 22 | {'other': 1108} |
| ramilevy | `PromoFull7290058140886-001-048-20261021-120055.gz` | 2,525 | 0 | 0 | 0 | 0 | 2,525 | 37 | {'other': 2525} |
| ramilevy | `PromoFull7290058140886-001-062-20261021-120113.gz` | 2,532 | 0 | 0 | 0 | 0 | 2,532 | 37 | {'other': 2532} |
| ramilevy | `PromoFull7290058140886-001-057-20261021-121655.gz` | 2,532 | 0 | 0 | 0 | 0 | 2,532 | 37 | {'other': 2532} |
| ramilevy | `PromoFull7290058140886-001-724-20261021-180029.gz` | 1,060 | 0 | 0 | 0 | 0 | 1,060 | 24 | {'other': 1060} |
| ramilevy | `PromoFull7290058140886-001-725-20261021-180038.gz` | 1,047 | 0 | 0 | 0 | 0 | 1,047 | 24 | {'other': 1047} |
| shufersal | `PromoFull7290027600007-001-002-20261021-043100.gz` | 1,379 | 0 | 0 | 0 | 0 | 1,379 | 1,379 | {'other': 1379} |
| shufersal | `PromoFull7290027600007-001-302-20261021-043100.gz` | 1,281 | 0 | 0 | 0 | 0 | 1,281 | 1,281 | {'other': 1281} |
| shufersal | `PromoFull7290027600007-006-300-20261021-043100.gz` | 1,008 | 0 | 0 | 0 | 0 | 1,008 | 1,008 | {'other': 1008} |
| shufersal | `PromoFull7290027600007-007-285-20261021-043100.gz` | 743 | 0 | 0 | 0 | 0 | 743 | 743 | {'other': 743} |
| shufersal | `PromoFull7290027600007-007-353-20261021-043100.gz` | 616 | 0 | 0 | 0 | 0 | 616 | 616 | {'other': 616} |
| shufersal | `PromoFull7290027600007-018-753-20261021-043100.gz` | 418 | 0 | 0 | 0 | 0 | 418 | 418 | {'other': 418} |
| tivtaam | `PromoFull7290873255550-000-012-20261021-153358.gz` | 2,040 | 0 | 0 | 0 | 0 | 2,040 | 2,040 | {'other': 2040} |
| tivtaam | `PromoFull7290873255550-000-085-20261021-153358.gz` | 1,282 | 0 | 0 | 0 | 0 | 1,282 | 1,282 | {'other': 1282} |
| tivtaam | `PromoFull7290873255550-000-087-20261021-153358.gz` | 1,126 | 0 | 0 | 0 | 0 | 1,126 | 1,126 | {'other': 1126} |
| tivtaam | `PromoFull7290873255550-000-092-20261021-153358.gz` | 1,060 | 0 | 0 | 0 | 0 | 1,060 | 1,060 | {'other': 1060} |
| yohananof | `PromoFull7290803800003-000-020-20261021-004031.gz` | 1,277 | 0 | 0 | 0 | 0 | 1,277 | 1,277 | {'other': 1277} |
| yohananof | `PromoFull7290803800003-000-021-20261021-004031.gz` | 1,212 | 0 | 0 | 0 | 0 | 1,212 | 1,212 | {'other': 1212} |

Sample codes (promo / item): king_store [] / ['12345', '13006', '13174']; king_store [] / ['12345', '13006', '13174']; mega [] / ['7290019790297', '7290019790327', '7290019790334']; mega [] / ['7290019790297', '7290019790327', '7290019790334']; mega [] / ['7290019790297', '7290019790327', '7290019790334']; mega [] / ['7290019790297', '7290019790327', '7290019790334']

`file_tracking` after the run: {'loaded': 68}. Alerts raised: 0.

| chain | physical stores | located | online | items | price events | stores with prices | promos | promo items |
|---|---|---|---|---|---|---|---|---|
| king_store | 48 | 28 | - | 6,748 | 10,797 | 3 | 743 | - |
| mega | 147 | 144 | 3 | 13,519 | 49,342 | 7 | 8,828 | - |
| osherad | 24 | 24 | - | 8,715 | 32,754 | 5 | 2,905 | - |
| ramilevy | 98 | 96 | 1 | 18,422 | 69,710 | 7 | 10,804 | - |
| shufersal | 416 | 411 | 1 | 5,556 | 5,556 | 1 | 5,445 | - |
| tivtaam | 47 | 47 | 7 | 24,986 | 58,521 | 5 | 5,508 | - |
| yohananof | 50 | 19 | 1 | 13,572 | 33,816 | 3 | 2,489 | - |

Extra downloads (the stores nearest to these city centres, for the optimizer):

- Haifa centre: 6 chains and 39 located stores within 4 km; asked for shufersal 302,353, mega 470,418, king_store 14, ramilevy 57,62, osherad 30, tivtaam 92,12
- Jerusalem centre: 6 chains and 36 located stores within 4 km; asked for shufersal 2,753, mega 457,91, king_store 200, ramilevy 48,703, osherad 26,28, yohananof 20
- Petah Tikva: 6 chains and 36 located stores within 4 km; asked for shufersal 285,300, mega 407,452, ramilevy 725,724, osherad 10, yohananof 21, tivtaam 87,85
- download `shufersal` price_full: timed out after 240s

### Matching on the real items

91,518 items; 19,748 mapped to a canonical (any level, including the review queue); 5,407 served (no review flag), onto 210 canonicals.

| level | mappings served | mappings in the review queue |
|---|---|---|
| exact | 0 | 0 |
| any_brand | 3,357 | 6,011 |
| close | 2,050 | 8,330 |

| chain | items | mapped | served |
|---|---|---|---|
| shufersal | 5,556 | 1,503 | 428 |
| mega | 13,519 | 2,939 | 1,010 |
| king_store | 6,748 | 1,844 | 324 |
| ramilevy | 18,422 | 3,895 | 1,350 |
| osherad | 8,715 | 2,163 | 690 |
| yohananof | 13,572 | 2,621 | 916 |
| tivtaam | 24,986 | 4,783 | 689 |

- seed: 1.01 s
- normalize: 7.7 s
- extract (rule): 72.28 s
- embed (hash): 317.16 s
- judge (rule): 190.88 s

### Precompute (production semantics)

6,977 rows written in 0.669 s of job time (1.02 s wall including start-up); 5,192 items priced at 31 stores (843 stores of 7 chains considered); 0 rows with a promo, 0 club-only. Canonicals with a real price: 208, of them 185 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 3,083 | 191 | 31 |
| close | 3,894 | 208 | 31 |

### Precompute (stress)

11,463 rows written in 1.546 s of job time (1.9 s wall including start-up); 18,795 items priced at 31 stores (843 stores of 7 chains considered); 0 rows with a promo, 0 club-only. Canonicals with a real price: 241, of them 235 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 5,239 | 237 | 31 |
| close | 6,224 | 241 | 31 |

### The vector query behind /parse-list and /search

`item_embeddings` holds 91,518 rows (model `hash-ngram-2-3-4-v1`); one `ORDER BY embedding <=> q LIMIT 40` query took [3.7, 1.4, 1.2] ms; with sequential scans disabled 1.0 ms.

```
Limit  (cost=2298.59..2559.39 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2298.59..598980.74 rows=91518 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
--- enable_seqscan = off
Limit  (cost=2298.59..2559.39 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2298.59..598980.74 rows=91518 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
```

### /parse-list, /compare and /optimize (production semantics)

Locations: Jerusalem centre (8 priced stores, 5 chains within 5 km); near בית הדובדבן - אונו (7 priced stores, 5 chains within 5 km); Haifa centre (6 priced stores, 4 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 4136.5 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 11671 |
| large (32 lines) | 33 | 33 | 5 | 0 | 22602.5 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 8 | 0 | 7.4 | 7.1 | 11.4 | 55 | single: רמי לוי עטרות | -1.0 / -1.0 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 8 | 0 | 8.9 | 7.6 | 11.9 | 55 | single: רמי לוי עטרות | 6.0 / 6.0 |
| Jerusalem centre | hand: large (32 lines) | 33 | 8 | 0 | 10.6 | 9.1 | 14.9 | 55 | single: רמי לוי עטרות | 22.1 / 22.1 |
| Jerusalem centre | drawn: 5 | 5 | 8 | 5 | 7.4 | 6.5 | 11.2 | 55 | single: קרפור (מגה) קרפור מרקט ריינס | -15.6 / -15.6 |
| Jerusalem centre | drawn: 10 | 10 | 8 | 0 | 8.3 | 7.3 | 12.4 | 55 | single: רמי לוי עטרות | 3.9 / 3.9 |
| Jerusalem centre | drawn: 20 | 20 | 8 | 0 | 10 | 8.4 | 13.4 | 55 | single: רמי לוי עטרות | 125.9 / 125.9 |
| Jerusalem centre | drawn: 40 | 40 | 8 | 0 | 16.1 | 12.4 | 20 | 55 | single: רמי לוי עטרות | 175.2 / 175.2 |
| near בית הדובדבן - אונו | hand: small (6 lines) | 6 | 7 | 0 | 7.2 | 5.9 | 10.5 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: weekly (17 lines) | 17 | 7 | 0 | 10.6 | 8 | 12.7 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: large (32 lines) | 33 | 7 | 0 | 12.7 | 7.6 | 12.7 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 5 | 5 | 7 | 2 | 8.1 | 6.2 | 11.8 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 10 | 10 | 7 | 1 | 9.9 | 7.2 | 12.8 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 20 | 20 | 7 | 0 | 13.3 | 8.2 | 13.3 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 40 | 40 | 7 | 0 | 16.8 | 9.5 | 14.1 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| Haifa centre | hand: small (6 lines) | 6 | 6 | 0 | 6.6 | 5.6 | 9.5 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | hand: weekly (17 lines) | 17 | 6 | 0 | 8.2 | 6.5 | 11.9 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | hand: large (32 lines) | 33 | 6 | 0 | 11.5 | 8.1 | 14.2 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | drawn: 5 | 5 | 6 | 2 | 7.6 | 6.6 | 11.5 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | drawn: 10 | 10 | 6 | 0 | 8.1 | 6.9 | 12.5 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | drawn: 20 | 20 | 6 | 0 | 10.6 | 7.9 | 12.4 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | drawn: 40 | 40 | 6 | 0 | 15.2 | 9.3 | 15.5 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 7.2 | 5.9 | 10.5 |
| hand: weekly (17 lines) | 8.9 | 7.6 | 11.9 |
| hand: large (32 lines) | 11.5 | 8.1 | 14.2 |
| drawn: 5 | 7.6 | 6.5 | 11.5 |
| drawn: 10 | 8.3 | 7.2 | 12.5 |
| drawn: 20 | 10.6 | 8.2 | 13.3 |
| drawn: 40 | 16.1 | 9.5 | 15.5 |

### /parse-list, /compare and /optimize (stress: unreviewed mappings included, performance only)

Locations: Jerusalem centre (8 priced stores, 5 chains within 5 km); near בית הדובדבן - אונו (7 priced stores, 5 chains within 5 km); Haifa centre (6 priced stores, 4 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 4082.7 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 11517.6 |
| large (32 lines) | 33 | 33 | 5 | 0 | 22244.4 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 8 | 4 | 9.9 | 9.5 | 15.6 | 55 | single: רמי לוי עטרות | 25.8 / 25.8 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 8 | 0 | 12.9 | 9.8 | 14.6 | 55 | single: רמי לוי עטרות | 105.16 / 105.16 |
| Jerusalem centre | hand: large (32 lines) | 33 | 8 | 0 | 14.3 | 11.4 | 16.7 | 55 | split: קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | 39.31 / 39.31 |
| Jerusalem centre | drawn: 5 | 5 | 8 | 3 | 6.7 | 6.1 | 10.6 | 55 | split: קרפור (מגה) קרפור מרקט ריינס, אושר עד תלפיות | 65.43 / 65.43 |
| Jerusalem centre | drawn: 10 | 10 | 8 | 2 | 7.9 | 7.2 | 11.8 | 55 | single: רמי לוי עטרות | 140.4 / 140.4 |
| Jerusalem centre | drawn: 20 | 20 | 8 | 0 | 11.4 | 9.9 | 15.8 | 55 | single: רמי לוי עטרות | 13.7 / 13.7 |
| Jerusalem centre | drawn: 40 | 40 | 8 | 0 | 16.1 | 13 | 20.5 | 55 | single: רמי לוי עטרות | 261.85 / 261.85 |
| near בית הדובדבן - אונו | hand: small (6 lines) | 6 | 7 | 6 | 7.9 | 6 | 10 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: weekly (17 lines) | 17 | 7 | 0 | 10.7 | 6.8 | 11.4 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: large (32 lines) | 33 | 7 | 0 | 16.3 | 8.9 | 14.4 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 5 | 5 | 7 | 2 | 7.2 | 5.6 | 10 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 10 | 10 | 7 | 0 | 8.1 | 6.2 | 10.2 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 20 | 20 | 7 | 0 | 11.6 | 7 | 11.9 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 40 | 40 | 7 | 0 | 17.2 | 8.1 | 14.2 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| Haifa centre | hand: small (6 lines) | 6 | 6 | 3 | 6.9 | 6.1 | 10.1 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | hand: weekly (17 lines) | 17 | 6 | 0 | 9.4 | 6.5 | 11 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | hand: large (32 lines) | 33 | 6 | 0 | 12.5 | 7.3 | 12 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | drawn: 5 | 5 | 6 | 2 | 6.6 | 5.9 | 9.8 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | drawn: 10 | 10 | 6 | 0 | 7.5 | 5.9 | 10 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | drawn: 20 | 20 | 6 | 0 | 10 | 6.6 | 11.1 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | drawn: 40 | 40 | 6 | 0 | 13.5 | 7.9 | 12.5 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 7.9 | 6.1 | 10.1 |
| hand: weekly (17 lines) | 10.7 | 6.8 | 11.4 |
| hand: large (32 lines) | 14.3 | 8.9 | 14.4 |
| drawn: 5 | 6.7 | 5.9 | 10.0 |
| drawn: 10 | 7.9 | 6.2 | 10.2 |
| drawn: 20 | 11.4 | 7.0 | 11.9 |
| drawn: 40 | 16.1 | 8.1 | 14.2 |

### Basket index on the real day (#44, dry run, production semantics)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `missing_items` שופרסל has no price for 12 basket items (milk-fresh-3, yellow-cheese-sliced-28, yogurt-plain-3, butter, eggs-l, cucumber, banana, pita, pasta-spaghetti, tuna-in-oil, bamba, chocolate-milk); it is listed but not ranked
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
| שופרסל | - | 13 | 12 | 1 | no |
| קרפור (מגה) | - | 14 | 11 | 7 | no |
| קינג סטור | - | 10 | 15 | 3 | no |
| רמי לוי | - | 16 | 9 | 7 | no |
| אושר עד | - | 8 | 17 | 5 | no |
| יוחננוף | - | 14 | 11 | 3 | no |
| טיב טעם | - | 13 | 12 | 5 | no |

### Basket index on the real day (#44, dry run, stress)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `estimated_items` קרפור (מגה): 6 lines use estimated weighed-goods prices
- warning: `missing_items` שופרסל has no price for 2 basket items (eggs-l, tuna-in-oil); it is listed but not ranked
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
| שופרסל | - | 23 | 2 | 1 | no |
| קינג סטור | - | 22 | 3 | 3 | no |
| רמי לוי | - | 24 | 1 | 7 | no |
| אושר עד | - | 20 | 5 | 5 | no |
| יוחננוף | - | 23 | 2 | 3 | no |
| טיב טעם | - | 24 | 1 | 5 | no |

### Failures and findings the run recorded (5)

- **download**: shufersal price_full: timed out after 240s
- **ingest**: 4 Stores files are older than the stale-date gate's 36 h (osherad 62.1 h, ramilevy 65.1 h, tivtaam 65.1 h, yohananof 69.2 h); on the real clock the gate would quarantine them and no store of those chains would load (this run replayed the clock for them)
- **ingest**: 36722 promos loaded from 30 PromoFull files but 0 promo_items rows: no promo can reach a price (see the PromoFull table)
- **api**: /parse-list took over 2 s (production): {'small (6 lines)': 4136.5, 'weekly (17 lines)': 11671.0, 'large (32 lines)': 22602.5} ms
- **api**: /parse-list took over 2 s (stress): {'small (6 lines)': 4082.7, 'weekly (17 lines)': 11517.6, 'large (32 lines)': 22244.4} ms

