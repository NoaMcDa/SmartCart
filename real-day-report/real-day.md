## One real day through the pipeline (dry run)

Mode `portal`, commit `cc3fa98c5992`, runner `GitHub Actions 1000005008` (4 CPUs, Python 3.12.3, Postgres 17.11), 2026-10-21T20:48:59+00:00 to 2026-10-21T21:21:21+00:00 UTC. Measurements on one real day with hand-made baskets; the prices are real, the baskets and locations are not a sample of anything. **Not publishable.**

### Stages

| stage | seconds | result |
|---|---|---|
| download: portal probe (one Stores and one PriceFull per chain) | 538.73 | ok |
| migrate | 1.19 | 25 applied |
| ingest: Stores files (Scheduler, adapters, gates, loader, store coordinates) | 0.57 | 7 files |
| download: PriceFull and PromoFull of the stores nearest to city centres | 503.61 | 60 files, anchors: Haifa centre, Jerusalem centre, Petah Tikva |
| ingest: PriceFull and PromoFull files (Scheduler, adapters, gates, loader) | 108.67 | 67 files |
| catalog: seed | 1.08 | ok |
| catalog: normalize | 9.41 | ok |
| catalog: extract (rule) | 90.21 | ok |
| catalog: embed (hash) | 331.61 | ok |
| catalog: judge (rule) | 232.69 | ok |
| precompute effective prices (production semantics: reviewed mappings only) | 1.31 | 8221 rows |
| API: parse-list, compare, optimize (production) | 54.8 | 21 basket runs at 3 locations |
| diagnostic: the vector query behind /parse-list and /search | 10.76 | [5.0, 1.1, 1.1] ms per query |
| basket index dry run (production semantics) | 0.45 | status draft |
| stress: mark the machine suggestions accepted (performance only) | 0.27 | 15597 mappings |
| precompute effective prices (stress: unreviewed mappings included) | 2.7 | 13609 rows |
| API: parse-list, compare, optimize (stress) | 52.79 | 21 basket runs at 3 locations |
| basket index dry run (stress) | 0.5 | status draft |

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
| king_store | stores | `Stores7290058108879-000-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 19.9 | v1 | loaded | 48 | 0.07 |
| mega | stores | `Stores7290055700007-000-20261021-000100.xml` | 2026-10-21T00:01+03:00 | 23.9 | v1 | loaded | 147 | 0.08 |
| osherad | stores | `Stores7290103152017-000-20261019-080501.xml` | 2026-10-19T08:05+03:00 | 63.9 (stale on the real clock) | v1 | loaded | 24 | 0.05 |
| ramilevy | stores | `Stores7290058140886-000-20261019-050500.xml` | 2026-10-19T05:05+03:00 | 66.9 (stale on the real clock) | v1 | loaded | 99 | 0.06 |
| shufersal | stores | `Stores7290027600007-000-20261021-020.gz` | 2026-10-21T02:00+03:00 | 22.0 | v1 | loaded | 417 | 0.2 |
| tivtaam | stores | `Stores7290873255550-000-20261019-050501.xml` | 2026-10-19T05:05+03:00 | 66.9 (stale on the real clock) | v1 | loaded | 54 | 0.04 |
| yohananof | stores | `Stores7290803800003-000-20261019-010000.xml` | 2026-10-19T01:00+03:00 | 71.0 (stale on the real clock) | v1 | loaded | 51 | 0.03 |
| king_store | price_full | `PriceFull7290058108879-000-340-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 20.0 | v1 | loaded | 2,336 | 0.45 |
| mega | price_full | `PriceFull7290055700007-001-002-20261021-051019.gz` | 2026-10-21T05:10+03:00 | 18.9 | v1 | loaded | 5,899 | 1.11 |
| osherad | price_full | `PriceFull7290103152017-001-001-20261021-080011.gz` | 2026-10-21T08:00+03:00 | 16.1 | v1 | loaded | 6,508 | 1.32 |
| ramilevy | price_full | `PriceFull7290058140886-001-001-20261021-001002.gz` | 2026-10-21T00:10+03:00 | 23.9 | v1 | loaded | 12,976 | 2.47 |
| shufersal | price_full | `PriceFull7290027600007-001-164-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 5,556 | 1.02 |
| tivtaam | price_full | `PriceFull7290873255550-000-002-20261021-004004.gz` | 2026-10-21T00:40+03:00 | 23.4 | v1 | loaded | 21,598 | 4.07 |
| yohananof | price_full | `PriceFull7290803800003-000-001-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 23.4 | v1 | loaded | 10,732 | 2.24 |
| king_store | price_full | `PriceFull7290058108879-000-014-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 20.0 | v1 | loaded | 4,833 | 0.88 |
| king_store | price_full | `PriceFull7290058108879-000-200-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 20.0 | v1 | loaded | 3,628 | 0.72 |
| king_store | promo_full | `PromoFull7290058108879-000-014-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 20.0 | v1 | loaded | 430 | 0.12 |
| king_store | promo_full | `PromoFull7290058108879-000-200-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 20.0 | v1 | loaded | 313 | 0.09 |
| mega | price_full | `PriceFull7290055700007-001-091-20261021-051007.gz` | 2026-10-21T05:10+03:00 | 18.9 | v1 | loaded | 6,825 | 1.36 |
| mega | price_full | `PriceFull7290055700007-001-418-20261021-051008.gz` | 2026-10-21T05:10+03:00 | 18.9 | v1 | loaded | 5,782 | 1.12 |
| mega | price_full | `PriceFull7290055700007-001-452-20261021-051010.gz` | 2026-10-21T05:10+03:00 | 18.9 | v1 | loaded | 8,176 | 1.73 |
| mega | price_full | `PriceFull7290055700007-001-457-20261021-051015.gz` | 2026-10-21T05:10+03:00 | 18.9 | v1 | loaded | 9,248 | 1.78 |
| mega | price_full | `PriceFull7290055700007-001-407-20261021-051019.gz` | 2026-10-21T05:10+03:00 | 18.9 | v1 | loaded | 8,576 | 1.65 |
| mega | price_full | `PriceFull7290055700007-001-470-20261021-064437.gz` | 2026-10-21T06:44+03:00 | 17.4 | v1 | loaded | 4,836 | 0.95 |
| mega | promo_full | `PromoFull7290055700007-001-418-20261021-051058.gz` | 2026-10-21T05:10+03:00 | 18.9 | v1 | loaded | 1,445 | 0.44 |
| mega | promo_full | `PromoFull7290055700007-001-091-20261021-051103.gz` | 2026-10-21T05:11+03:00 | 18.9 | v1 | loaded | 1,530 | 0.48 |
| mega | promo_full | `PromoFull7290055700007-001-452-20261021-051116.gz` | 2026-10-21T05:11+03:00 | 18.9 | v1 | loaded | 1,518 | 0.45 |
| mega | promo_full | `PromoFull7290055700007-001-407-20261021-051125.gz` | 2026-10-21T05:11+03:00 | 18.9 | v1 | loaded | 1,465 | 0.42 |
| mega | promo_full | `PromoFull7290055700007-001-457-20261021-051126.gz` | 2026-10-21T05:11+03:00 | 18.9 | v1 | loaded | 1,437 | 0.46 |
| mega | promo_full | `PromoFull7290055700007-001-470-20261021-064509.gz` | 2026-10-21T06:45+03:00 | 17.4 | v1 | loaded | 1,433 | 0.45 |
| osherad | price_full | `PriceFull7290103152017-001-026-20261021-140501.gz` | 2026-10-21T14:05+03:00 | 10.0 | v1 | loaded | 6,836 | 1.31 |
| osherad | price_full | `PriceFull7290103152017-001-030-20261021-140501.gz` | 2026-10-21T14:05+03:00 | 10.0 | v1 | loaded | 6,465 | 1.18 |
| osherad | price_full | `PriceFull7290103152017-001-010-20261021-140502.gz` | 2026-10-21T14:05+03:00 | 10.0 | v1 | loaded | 6,699 | 1.22 |
| osherad | price_full | `PriceFull7290103152017-001-028-20261021-140502.gz` | 2026-10-21T14:05+03:00 | 10.0 | v1 | loaded | 6,246 | 1.15 |
| osherad | promo_full | `PromoFull7290103152017-001-028-20261021-140522.gz` | 2026-10-21T14:05+03:00 | 10.0 | v1 | loaded | 716 | 0.22 |
| osherad | promo_full | `PromoFull7290103152017-001-026-20261021-140527.gz` | 2026-10-21T14:05+03:00 | 10.0 | v1 | loaded | 734 | 0.2 |
| osherad | promo_full | `PromoFull7290103152017-001-030-20261021-140545.gz` | 2026-10-21T14:05+03:00 | 10.0 | v1 | loaded | 750 | 0.21 |
| osherad | promo_full | `PromoFull7290103152017-001-010-20261021-140558.gz` | 2026-10-21T14:05+03:00 | 10.0 | v1 | loaded | 705 | 0.22 |
| ramilevy | price_full | `PriceFull7290058140886-001-062-20261021-120007.gz` | 2026-10-21T12:00+03:00 | 12.1 | v1 | loaded | 14,121 | 2.64 |
| ramilevy | price_full | `PriceFull7290058140886-001-703-20261021-120007.gz` | 2026-10-21T12:00+03:00 | 12.1 | v1 | loaded | 4,955 | 0.9 |
| ramilevy | price_full | `PriceFull7290058140886-001-048-20261021-120011.gz` | 2026-10-21T12:00+03:00 | 12.1 | v1 | loaded | 14,448 | 2.65 |
| ramilevy | price_full | `PriceFull7290058140886-001-057-20261021-121509.gz` | 2026-10-21T12:15+03:00 | 11.9 | v1 | loaded | 13,927 | 2.71 |
| ramilevy | price_full | `PriceFull7290058140886-001-724-20261021-180005.gz` | 2026-10-21T18:00+03:00 | 6.1 | v1 | loaded | 5,164 | 0.94 |
| ramilevy | price_full | `PriceFull7290058140886-001-725-20261021-180015.gz` | 2026-10-21T18:00+03:00 | 6.1 | v1 | loaded | 4,119 | 0.78 |
| ramilevy | promo_full | `PromoFull7290058140886-001-703-20261021-120038.gz` | 2026-10-21T12:00+03:00 | 12.1 | v1 | loaded | 1,108 | 0.34 |
| ramilevy | promo_full | `PromoFull7290058140886-001-048-20261021-120055.gz` | 2026-10-21T12:00+03:00 | 12.1 | v1 | loaded | 2,525 | 0.86 |
| ramilevy | promo_full | `PromoFull7290058140886-001-062-20261021-120113.gz` | 2026-10-21T12:01+03:00 | 12.1 | v1 | loaded | 2,532 | 0.89 |
| ramilevy | promo_full | `PromoFull7290058140886-001-057-20261021-121655.gz` | 2026-10-21T12:16+03:00 | 11.8 | v1 | loaded | 2,532 | 0.89 |
| ramilevy | promo_full | `PromoFull7290058140886-001-724-20261021-180029.gz` | 2026-10-21T18:00+03:00 | 6.1 | v1 | loaded | 1,060 | 0.33 |
| ramilevy | promo_full | `PromoFull7290058140886-001-725-20261021-180038.gz` | 2026-10-21T18:00+03:00 | 6.1 | v1 | loaded | 1,047 | 0.33 |
| shufersal | price_full | `PriceFull7290027600007-001-002-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 7,488 | 1.45 |
| shufersal | price_full | `PriceFull7290027600007-001-302-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 6,534 | 1.3 |
| shufersal | price_full | `PriceFull7290027600007-006-300-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 7,723 | 1.54 |
| shufersal | price_full | `PriceFull7290027600007-007-285-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 3,328 | 0.62 |
| shufersal | price_full | `PriceFull7290027600007-007-353-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 2,271 | 0.45 |
| shufersal | price_full | `PriceFull7290027600007-018-753-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 3,547 | 0.68 |
| shufersal | promo_full | `PromoFull7290027600007-001-002-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 1,379 | 0.84 |
| shufersal | promo_full | `PromoFull7290027600007-001-302-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 1,281 | 0.77 |
| shufersal | promo_full | `PromoFull7290027600007-006-300-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 1,008 | 0.68 |
| shufersal | promo_full | `PromoFull7290027600007-007-285-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 743 | 0.43 |
| shufersal | promo_full | `PromoFull7290027600007-007-353-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 616 | 0.35 |
| shufersal | promo_full | `PromoFull7290027600007-018-753-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 19.6 | v1 | loaded | 418 | 0.3 |
| tivtaam | price_full | `PriceFull7290873255550-000-012-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 8.6 | v1 | loaded | 17,832 | 3.45 |
| tivtaam | price_full | `PriceFull7290873255550-000-085-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 8.6 | v1 | loaded | 7,171 | 1.38 |
| tivtaam | price_full | `PriceFull7290873255550-000-087-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 8.6 | v1 | loaded | 6,069 | 1.15 |
| tivtaam | price_full | `PriceFull7290873255550-000-092-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 8.6 | v1 | loaded | 5,851 | 1.13 |
| tivtaam | promo_full | `PromoFull7290873255550-000-012-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 8.6 | v1 | loaded | 2,040 | 1.45 |
| tivtaam | promo_full | `PromoFull7290873255550-000-085-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 8.6 | v1 | loaded | 1,282 | 1.61 |
| tivtaam | promo_full | `PromoFull7290873255550-000-087-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 8.6 | v1 | loaded | 1,126 | 1.12 |
| tivtaam | promo_full | `PromoFull7290873255550-000-092-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 8.6 | v1 | loaded | 1,060 | 0.83 |
| yohananof | price_full | `PriceFull7290803800003-000-020-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 23.5 | v1 | loaded | 11,887 | 2.39 |
| yohananof | price_full | `PriceFull7290803800003-000-021-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 23.5 | v1 | loaded | 11,197 | 2.11 |
| yohananof | promo_full | `PromoFull7290803800003-000-020-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 23.5 | v1 | loaded | 1,277 | 0.41 |
| yohananof | promo_full | `PromoFull7290803800003-000-021-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 23.5 | v1 | loaded | 1,212 | 0.35 |

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

First promo of `PromoFull7290058108879-000-014-20261021-040448.gz` as the adapter returns it:

```
{
 "description": "צלעות עגל טרי 1 קג ב 49.9",
 "reward_type": "other",
 "reward_value": "None",
 "min_qty": "None",
 "raw_keys": [
  "additional_restrictions",
  "additionaliscoupon",
  "additionalrestrictions",
  "allowmultiplediscounts",
  "club_ids",
  "clubid",
  "confidence",
  "confidence_reasons",
  "minnoofitemoffered",
  "promotiondays",
  "promotiondescription",
  "promotionenddatetime",
  "promotionendhour",
  "promotionid",
  "promotionstartdatetime",
  "promotionstarthour",
  "promotionupdatetime",
  "redemptionlimit",
  "remarks"
 ],
 "raw": "{\"promotionupdatetime\": \"2026-10-21T04:07:28.543\", \"allowmultiplediscounts\": \"0\", \"promotionid\": \"587746722\", \"promotiondescription\": \"צלעות עגל טרי 1 קג ב 49.9\", \"promotionstartdatetime\": \"2026-10-19T00:00:00.000\", \"promotionenddatetime\": \"2026-10-25T00:00:00.000\", \"promotionstarthour\": \"\", \"promotionendhour\": \"\", \"promotiondays\": \"\", \"redemptionlimit\": \"\", \"minnoofitemoffered\": \"\", \"clubid\": \"(\\\"לקוחות הקפה=3\\\" | \\\"מועדון לקוחות=3\\\" | \\\"HEBREW=3\\\" | \\\"ARABIC=3\\\" | \\\"לקוחות אתר קניות=3\\\" | \\\"מיתר=3\\\" | \\\"לקוחות סיטונאים=3\\\" | \\\"עובדי קינגסטור -ARABIC=3\\\" | \\\"עובדי קינגסטור -HEBREW=3\\\" | \\\"טסט"
}
```

Sample codes (promo / item): king_store [] / ['12345', '13006', '13174']; king_store [] / ['12345', '13006', '13174']; mega [] / ['7290019790297', '7290019790327', '7290019790334']; mega [] / ['7290019790297', '7290019790327', '7290019790334']; mega [] / ['7290019790297', '7290019790327', '7290019790334']; mega [] / ['7290019790297', '7290019790327', '7290019790334']

`file_tracking` after the run: {'loaded': 74}. Alerts raised: 0.

| chain | physical stores | located | online | items | price events | stores with prices | promos | promo items |
|---|---|---|---|---|---|---|---|---|
| king_store | 48 | 28 | - | 6,748 | 10,797 | 3 | 743 | - |
| mega | 147 | 144 | 3 | 13,519 | 49,342 | 7 | 8,828 | - |
| osherad | 24 | 24 | - | 8,715 | 32,754 | 5 | 2,905 | - |
| ramilevy | 98 | 96 | 1 | 18,422 | 69,710 | 7 | 10,804 | - |
| shufersal | 416 | 411 | 1 | 13,650 | 36,447 | 7 | 5,445 | - |
| tivtaam | 47 | 47 | 7 | 24,986 | 58,521 | 5 | 5,508 | - |
| yohananof | 50 | 19 | 1 | 13,572 | 33,816 | 3 | 2,489 | - |

Extra downloads (the stores nearest to these city centres, for the optimizer):

- Haifa centre: 6 chains and 39 located stores within 4 km; asked for shufersal 302,353, mega 470,418, king_store 14, ramilevy 57,62, osherad 30, tivtaam 92,12
- Jerusalem centre: 6 chains and 36 located stores within 4 km; asked for shufersal 2,753, mega 457,91, king_store 200, ramilevy 48,703, osherad 26,28, yohananof 20
- Petah Tikva: 6 chains and 36 located stores within 4 km; asked for shufersal 285,300, mega 407,452, ramilevy 725,724, osherad 10, yohananof 21, tivtaam 87,85

### Matching on the real items

99,612 items; 21,520 mapped to a canonical (any level, including the review queue); 5,923 served (no review flag), onto 210 canonicals.

| level | mappings served | mappings in the review queue |
|---|---|---|
| exact | 0 | 0 |
| any_brand | 3,609 | 6,481 |
| close | 2,314 | 9,116 |

| chain | items | mapped | served |
|---|---|---|---|
| shufersal | 13,650 | 3,275 | 944 |
| mega | 13,519 | 2,939 | 1,010 |
| king_store | 6,748 | 1,844 | 324 |
| ramilevy | 18,422 | 3,895 | 1,350 |
| osherad | 8,715 | 2,163 | 690 |
| yohananof | 13,572 | 2,621 | 916 |
| tivtaam | 24,986 | 4,783 | 689 |

- seed: 1.08 s
- normalize: 9.41 s
- extract (rule): 90.21 s
- embed (hash): 331.61 s
- judge (rule): 232.69 s

### Precompute (production semantics)

8,221 rows written in 0.91 s of job time (1.29 s wall including start-up); 5,706 items priced at 37 stores (843 stores of 7 chains considered); 0 rows with a promo, 0 club-only. Canonicals with a real price: 209, of them 191 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 3,612 | 193 | 37 |
| close | 4,609 | 209 | 37 |

### Precompute (stress)

13,609 rows written in 2.276 s of job time (2.67 s wall including start-up); 20,556 items priced at 37 stores (843 stores of 7 chains considered); 0 rows with a promo, 0 club-only. Canonicals with a real price: 241, of them 236 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 6,182 | 237 | 37 |
| close | 7,427 | 241 | 37 |

### The vector query behind /parse-list and /search

`item_embeddings` holds 99,612 rows (model `hash-ngram-2-3-4-v1`); one `ORDER BY embedding <=> q LIMIT 40` query took [5.0, 1.1, 1.1] ms; with sequential scans disabled 1.0 ms.

```
Limit  (cost=2327.98..2592.52 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2327.98..661135.33 rows=99612 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
--- enable_seqscan = off
Limit  (cost=2327.98..2592.52 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2327.98..661135.33 rows=99612 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
```

One `/parse-list` call (6 lines): 4943.0 ms in total, 4932.7 ms inside 37 SQL statements. The statements that cost the most:

| statement (first 110 characters) | calls | total ms | max ms |
|---|---|---|---|
| `WITH qv AS (SELECT %(v)s::vector AS v), direct AS ( SELECT c.id AS canonical_id, 1 - (c.embedding <=> qv.v) AS` | 6 | 4895.6 | 847.6 |
| `WITH q AS (SELECT search_norm(%(q)s) AS t) SELECT c.id, word_similarity(q.t, search_norm(c.display_name_he)) A` | 6 | 20.0 | 7.5 |
| `WITH RECURSIVE up AS ( SELECT t.id AS leaf, t.id, t.parent_id, t.name_he, t.level FROM taxonomy t WHERE t.id =` | 6 | 5.1 | 1.1 |
| `SELECT c.id, c.display_name_he, ts_rank_cd(to_tsvector('simple', search_norm(c.display_name_he)), tq) AS r FRO` | 6 | 4.5 | 1.7 |
| `SELECT id, display_name_he, taxonomy_id, base_unit, rank, names_ar[1] FROM canonical_products WHERE id = ANY(%` | 6 | 4.5 | 1.0 |
| `SELECT set_config('pg_trgm.word_similarity_threshold', %s, true)` | 6 | 2.4 | 1.0 |

`EXPLAIN (ANALYZE, BUFFERS)` of the slowest statement:

```
Limit  (cost=8258.65..8258.67 rows=10 width=16) (actual rows=20 loops=1)
  Buffers: shared hit=797726 read=68549
  CTE qv
    ->  Result  (cost=0.00..0.01 rows=1 width=32) (actual rows=1 loops=1)
  ->  Sort  (cost=8258.64..8258.66 rows=10 width=16) (actual rows=20 loops=1)
        Sort Key: (max(direct.s)) DESC, direct.canonical_id
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=797726 read=68549
        ->  GroupAggregate  (cost=8258.00..8258.47 rows=10 width=16) (actual rows=20 loops=1)
              Group Key: direct.canonical_id
              Buffers: shared hit=797723 read=68549
              ->  Merge Append  (cost=8258.00..8258.32 rows=10 width=16) (actual rows=24 loops=1)
                    Sort Key: direct.canonical_id
                    Buffers: shared hit=797723 read=68549
                    ->  Sort  (cost=33.29..33.31 rows=7 width=16) (actual rows=20 loops=1)
                          Sort Key: direct.canonical_id
                          Sort Method: quicksort  Memory: 25kB
                          Buffers: shared hit=1499 read=182
                          ->  Subquery Scan on direct  (cost=32.89..33.19 rows=7 width=16) (actual rows=20 loops=1)
                                Filter: (direct.s >= '0.25'::double precision)
                                Buffers: shared hit=1499 read=182
                                ->  Limit  (cost=32.89..32.94 rows=20 width=24) (actual rows=20 loops=1)
                                      Buffers: shared hit=1499 read=182
                                      ->  Sort  (cost=32.89..33.50 rows=245 width=24) (actual rows=20 loops=1)
                                            Sort Key: ((c.embedding <=> qv.v))
                                            Sort Method: top-N heapsort  Memory: 27kB
                                            Buffers: shared hit=1499 read=182
                                            ->  Nested Loop  (cost=0.00..26.37 rows=245 width=24) (actual rows=245 loops=1)
                                                  Buffers: shared hit=1499 read=182
                                                  ->  CTE Scan on qv  (cost=0.00..0.02 rows=1 width=32) (actual rows=1 loops=1)
                                                  ->  Seq Scan on canonical_products c  (cost=0.00..22.06 rows=245 width=26) (actual rows=245 loops=1)
                                                        Filter: ((embedding IS NOT NULL) AND (embedding_model = 'hash-ngram-2-3-4-v1'::text))
                                                        Buffers: shared hit=5 read=14
                    ->  GroupAggregate  (cost=8224.71..8224.91 rows=3 width=16) (actual rows=4 loops=1)
                          Group Key: ic.canonical_id
                          Filter: (max((('1'::double precision - (e.embedding <=> qv_1.v)))) >= '0.25'::double precision)
                          Buffers: shared hit=796224 read=68367
                          ->  Sort  (cost=8224.71..8224.73 rows=10 width=16) (actual rows=18 loops=1)
                                Sort Key: ic.canonical_id
                                Sort Method: quicksort  Memory: 25kB
```

### /parse-list, /compare and /optimize (production semantics)

Locations: Jerusalem centre (10 priced stores, 6 chains within 5 km); near בית הדובדבן - אונו (9 priced stores, 5 chains within 5 km); Haifa centre (8 priced stores, 5 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 4853.3 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 13773.2 |
| large (32 lines) | 33 | 33 | 5 | 0 | 26672.1 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 10 | 0 | 9.6 | 9.3 | 15.4 | 55 | single: רמי לוי עטרות | 5.73 / 5.73 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 10 | 0 | 13.5 | 10.6 | 17.6 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 33 | 10 | 0 | 16.2 | 13.2 | 19.6 | 55 | single: רמי לוי עטרות | 86.8 / 86.8 |
| Jerusalem centre | drawn: 5 | 5 | 10 | 6 | 9.1 | 8.1 | 14.4 | 55 | single: קרפור (מגה) קרפור מרקט ריינס | 5.07 / 5.07 |
| Jerusalem centre | drawn: 10 | 10 | 10 | 0 | 10.4 | 9.2 | 15.2 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | drawn: 20 | 20 | 10 | 0 | 12.6 | 10.6 | 17.4 | 55 | single: רמי לוי עטרות | 66.97 / 66.97 |
| Jerusalem centre | drawn: 40 | 40 | 10 | 0 | 19.4 | 16.1 | 25 | 55 | single: רמי לוי עטרות | 203.37 / 203.37 |
| near בית הדובדבן - אונו | hand: small (6 lines) | 6 | 9 | 0 | 8.7 | 6.8 | 12 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: weekly (17 lines) | 17 | 9 | 0 | 12.8 | 8.1 | 14 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: large (32 lines) | 33 | 9 | 0 | 16 | 9 | 16.9 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 5 | 5 | 9 | 0 | 8.9 | 7.1 | 12.9 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 10 | 10 | 9 | 0 | 10.3 | 7.2 | 12.7 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 20 | 20 | 9 | 0 | 14.1 | 8.9 | 13.1 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 40 | 40 | 9 | 0 | 21 | 9.8 | 15.9 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| Haifa centre | hand: small (6 lines) | 6 | 8 | 0 | 8.5 | 7.4 | 13.1 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | hand: weekly (17 lines) | 17 | 8 | 0 | 11.6 | 8.9 | 15.5 | 55 | single: שופרסל שלי חיפה- קלר | -11.87 / -11.87 |
| Haifa centre | hand: large (32 lines) | 33 | 8 | 0 | 15.6 | 10.8 | 17.8 | 55 | single: שופרסל שלי חיפה- קלר | -18.47 / -18.47 |
| Haifa centre | drawn: 5 | 5 | 8 | 2 | 8.6 | 8 | 13 | 55 | single: שופרסל שלי חיפה- קלר | 4.63 / 4.63 |
| Haifa centre | drawn: 10 | 10 | 8 | 0 | 9.9 | 7.8 | 13.8 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | drawn: 20 | 20 | 8 | 0 | 11.9 | 8.9 | 15.1 | 55 | single: שופרסל שלי חיפה- קלר | -5.17 / -5.17 |
| Haifa centre | drawn: 40 | 40 | 8 | 0 | 18.3 | 11.2 | 17.8 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 8.7 | 7.4 | 13.1 |
| hand: weekly (17 lines) | 12.8 | 8.9 | 15.5 |
| hand: large (32 lines) | 16.0 | 10.8 | 17.8 |
| drawn: 5 | 8.9 | 8.0 | 13.0 |
| drawn: 10 | 10.3 | 7.8 | 13.8 |
| drawn: 20 | 12.6 | 8.9 | 15.1 |
| drawn: 40 | 19.4 | 11.2 | 17.8 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 8.8 | 16.4 | - | - | 5.73 / 5.73 |
| Jerusalem centre | hand: weekly (17 lines) | 11 | 17.8 | - | - | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 12.4 | 19.1 | - | - | 86.8 / 86.8 |
| Jerusalem centre | drawn: 5 | 8.1 | 14.6 | אושר עד תלפיות, רמי לוי עטרות | אושר עד תלפיות, רמי לוי עטרות | 14.6 / 14.6 |
| Jerusalem centre | drawn: 10 | 8.9 | 14.6 | - | - | 0.0 / 0.0 |
| Jerusalem centre | drawn: 20 | 11.2 | 17.3 | - | - | 66.97 / 66.97 |
| Jerusalem centre | drawn: 40 | 15.2 | 23.4 | - | - | 203.37 / 203.37 |
| near בית הדובדבן - אונו | hand: small (6 lines) | 6.9 | 13.3 | - | - | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: weekly (17 lines) | 8.2 | 15.1 | - | - | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: large (32 lines) | 8.9 | 15.8 | - | - | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 5 | 7.4 | 13.8 | - | - | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 10 | 7.3 | 14.1 | - | - | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 20 | 8.3 | 15.2 | - | - | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 40 | 10 | 18.2 | - | - | 0.0 / 0.0 |
| Haifa centre | hand: small (6 lines) | 7.3 | 13.1 | - | - | 0.0 / 0.0 |
| Haifa centre | hand: weekly (17 lines) | 9.6 | 15.6 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 8.34 / 8.34 |
| Haifa centre | hand: large (32 lines) | 10.8 | 18.2 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 8.34 / 8.34 |
| Haifa centre | drawn: 5 | 6.7 | 14.7 | - | - | 4.63 / 4.63 |
| Haifa centre | drawn: 10 | 7.9 | 13.6 | - | - | 0.0 / 0.0 |
| Haifa centre | drawn: 20 | 8.7 | 15.3 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 17.34 / 17.34 |
| Haifa centre | drawn: 40 | 11.2 | 16.8 | - | - | 0.0 / 0.0 |

### /parse-list, /compare and /optimize (stress: unreviewed mappings included, performance only)

Locations: Jerusalem centre (10 priced stores, 6 chains within 5 km); near בית הדובדבן - אונו (9 priced stores, 5 chains within 5 km); Haifa centre (8 priced stores, 5 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 4916.4 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 13826.7 |
| large (32 lines) | 33 | 33 | 5 | 0 | 26348.9 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 10 | 5 | 10.4 | 10.1 | 15.3 | 55 | single: רמי לוי עטרות | 57.26 / 57.26 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 10 | 0 | 14.2 | 12.6 | 19.8 | 55 | single: רמי לוי עטרות | 55.54 / 55.54 |
| Jerusalem centre | hand: large (32 lines) | 33 | 10 | 0 | 22 | 17.5 | 25.4 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | drawn: 5 | 5 | 10 | 4 | 9.1 | 8.1 | 13.6 | 55 | single: רמי לוי עטרות | 110.27 / 110.27 |
| Jerusalem centre | drawn: 10 | 10 | 10 | 0 | 10 | 9.4 | 15.5 | 55 | single: קרפור (מגה) קרפור מרקט ריינס | 8.77 / 8.77 |
| Jerusalem centre | drawn: 20 | 20 | 10 | 0 | 14.7 | 12 | 18.8 | 55 | single: רמי לוי עטרות | 160.67 / 160.67 |
| Jerusalem centre | drawn: 40 | 40 | 10 | 0 | 23.2 | 17.9 | 26.4 | 55 | single: רמי לוי עטרות | 568.67 / 568.67 |
| near בית הדובדבן - אונו | hand: small (6 lines) | 6 | 9 | 7 | 9.4 | 7.1 | 12 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: weekly (17 lines) | 17 | 9 | 0 | 14.2 | 7.9 | 13.7 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: large (32 lines) | 33 | 9 | 0 | 21.4 | 9.1 | 16.4 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 5 | 5 | 9 | 6 | 9.5 | 6.7 | 12.3 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 10 | 10 | 9 | 0 | 10.6 | 7.3 | 12.7 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 20 | 20 | 9 | 0 | 15.6 | 8.1 | 13.9 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 40 | 40 | 9 | 0 | 24.4 | 9.9 | 16.1 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| Haifa centre | hand: small (6 lines) | 6 | 8 | 5 | 8.7 | 7.3 | 12.6 | 55 | single: שופרסל שלי חיפה- קלר | -5.95 / -5.95 |
| Haifa centre | hand: weekly (17 lines) | 17 | 8 | 0 | 13.3 | 9.2 | 15.5 | 55 | single: שופרסל שלי חיפה- קלר | 23.67 / 23.67 |
| Haifa centre | hand: large (32 lines) | 33 | 8 | 0 | 19.2 | 11.8 | 18.8 | 55 | single: שופרסל שלי חיפה- קלר | 95.97 / 95.97 |
| Haifa centre | drawn: 5 | 5 | 8 | 3 | 8 | 6.8 | 12.2 | 55 | single: שופרסל שלי חיפה- קלר | 3.03 / 3.03 |
| Haifa centre | drawn: 10 | 10 | 8 | 0 | 9 | 7.6 | 13.2 | 55 | single: שופרסל שלי חיפה- קלר | -5.87 / -5.87 |
| Haifa centre | drawn: 20 | 20 | 8 | 1 | 13.8 | 9.6 | 16.3 | 55 | single: שופרסל שלי חיפה- קלר | 25.43 / 25.43 |
| Haifa centre | drawn: 40 | 40 | 8 | 0 | 20.9 | 12.5 | 19.5 | 55 | single: שופרסל שלי חיפה- קלר | -4.37 / -4.37 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 9.4 | 7.3 | 12.6 |
| hand: weekly (17 lines) | 14.2 | 9.2 | 15.5 |
| hand: large (32 lines) | 21.4 | 11.8 | 18.8 |
| drawn: 5 | 9.1 | 6.8 | 12.3 |
| drawn: 10 | 10.0 | 7.6 | 13.2 |
| drawn: 20 | 14.7 | 9.6 | 16.3 |
| drawn: 40 | 23.2 | 12.5 | 19.5 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 9.9 | 15.2 | רמי לוי עטרות, שופרסל שלי ירושלים- אגרון | רמי לוי עטרות, שופרסל שלי ירושלים- אגרון | 58.33 / 58.33 |
| Jerusalem centre | hand: weekly (17 lines) | 12.8 | 19.7 | קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | 73.37 / 73.37 |
| Jerusalem centre | hand: large (32 lines) | 17.4 | 25.8 | קרפור (מגה) קרפור מרקט ריינס, שופרסל שלי ירושלים- אגרון | קרפור (מגה) קרפור מרקט ריינס, שופרסל שלי ירושלים- אגרון | 59.93 / 59.93 |
| Jerusalem centre | drawn: 5 | 7.9 | 13.4 | קרפור (מגה) קרפור מרקט ריינס, אושר עד תלפיות | קרפור (מגה) קרפור מרקט ריינס, אושר עד תלפיות | 139.68 / 139.68 |
| Jerusalem centre | drawn: 10 | 9.2 | 15.6 | קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | 19.9 / 19.9 |
| Jerusalem centre | drawn: 20 | 12.8 | 19.5 | - | - | 160.67 / 160.67 |
| Jerusalem centre | drawn: 40 | 17.8 | 25.2 | - | - | 568.67 / 568.67 |
| near בית הדובדבן - אונו | hand: small (6 lines) | 6.9 | 13.4 | - | - | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: weekly (17 lines) | 7.8 | 15.3 | - | - | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: large (32 lines) | 10 | 17.3 | - | - | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 5 | 7.1 | 13.6 | - | - | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 10 | 7.5 | 14.2 | - | - | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 20 | 8.3 | 15.7 | - | - | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 40 | 9.8 | 17.8 | - | - | 0.0 / 0.0 |
| Haifa centre | hand: small (6 lines) | 7.5 | 13.2 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 1.16 / 1.16 |
| Haifa centre | hand: weekly (17 lines) | 9.7 | 16.3 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 28.28 / 28.28 |
| Haifa centre | hand: large (32 lines) | 12.2 | 19.4 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 109.58 / 109.58 |
| Haifa centre | drawn: 5 | 6.8 | 12.2 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 48.34 / 48.34 |
| Haifa centre | drawn: 10 | 7.9 | 13.7 | - | - | -5.87 / -5.87 |
| Haifa centre | drawn: 20 | 10.2 | 16.6 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 40.14 / 40.14 |
| Haifa centre | drawn: 40 | 12.6 | 19.9 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 84.84 / 84.84 |

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

### Failures and findings the run recorded (4)

- **ingest**: 4 Stores files are older than the stale-date gate's 36 h (osherad 63.9 h, ramilevy 66.9 h, tivtaam 66.9 h, yohananof 71.0 h); on the real clock the gate would quarantine them and no store of those chains would load (this run replayed the clock for them)
- **ingest**: 36722 promos loaded from 30 PromoFull files but 0 promo_items rows: no promo can reach a price (see the PromoFull table)
- **api**: /parse-list took over 2 s (production): {'small (6 lines)': 4853.3, 'weekly (17 lines)': 13773.2, 'large (32 lines)': 26672.1} ms
- **api**: /parse-list took over 2 s (stress): {'small (6 lines)': 4916.4, 'weekly (17 lines)': 13826.7, 'large (32 lines)': 26348.9} ms

