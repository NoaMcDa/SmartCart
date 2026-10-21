## One real day through the pipeline (dry run)

Mode `portal`, commit `282b402577c0`, runner `GitHub Actions 1000004858` (4 CPUs, Python 3.12.3, Postgres 17.11), 2026-10-21T19:39:16+00:00 to 2026-10-21T20:08:21+00:00 UTC. Measurements on one real day with hand-made baskets; the prices are real, the baskets and locations are not a sample of anything. **Not publishable.**

### Stages

| stage | seconds | result |
|---|---|---|
| download: portal probe (one Stores and one PriceFull per chain) | 725.42 | ok |
| migrate | 0.89 | 25 applied |
| ingest: Stores files (Scheduler, adapters, gates, loader, store coordinates) | 0.29 | 7 files |
| download: PriceFull and PromoFull of the stores nearest to city centres | 431.28 | 60 files, anchors: Haifa centre, Jerusalem centre, Petah Tikva |
| ingest: PriceFull and PromoFull files (Scheduler, adapters, gates, loader) | 75.38 | 67 files |
| catalog: seed | 0.76 | ok |
| catalog: normalize | 4.84 | ok |
| catalog: extract (rule) | 47.18 | ok |
| catalog: embed (hash) | 246.84 | ok |
| catalog: judge (rule) | 139.03 | ok |
| precompute effective prices (production semantics: reviewed mappings only) | 0.79 | 8221 rows |
| API: parse-list, compare, optimize (production) | 32.83 | 21 basket runs at 3 locations |
| diagnostic: the vector query behind /parse-list and /search | 6 | [3.0, 0.7, 0.5] ms per query |
| basket index dry run (production semantics) | 0.25 | status draft |
| stress: mark the machine suggestions accepted (performance only) | 0.25 | 15597 mappings |
| precompute effective prices (stress: unreviewed mappings included) | 1.51 | 13609 rows |
| API: parse-list, compare, optimize (stress) | 30.58 | 21 basket runs at 3 locations |
| basket index dry run (stress) | 0.28 | status draft |

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
| king_store | stores | `Stores7290058108879-000-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 18.8 | v1 | loaded | 48 | 0.04 |
| mega | stores | `Stores7290055700007-000-20261021-000100.xml` | 2026-10-21T00:01+03:00 | 22.8 | v1 | loaded | 147 | 0.04 |
| osherad | stores | `Stores7290103152017-000-20261019-080501.xml` | 2026-10-19T08:05+03:00 | 62.8 (stale on the real clock) | v1 | loaded | 24 | 0.03 |
| ramilevy | stores | `Stores7290058140886-000-20261019-050500.xml` | 2026-10-19T05:05+03:00 | 65.8 (stale on the real clock) | v1 | loaded | 99 | 0.03 |
| shufersal | stores | `Stores7290027600007-000-20261021-020.gz` | 2026-10-21T02:00+03:00 | 20.9 | v1 | loaded | 417 | 0.08 |
| tivtaam | stores | `Stores7290873255550-000-20261019-050501.xml` | 2026-10-19T05:05+03:00 | 65.8 (stale on the real clock) | v1 | loaded | 54 | 0.02 |
| yohananof | stores | `Stores7290803800003-000-20261019-010000.xml` | 2026-10-19T01:00+03:00 | 69.9 (stale on the real clock) | v1 | loaded | 51 | 0.02 |
| king_store | price_full | `PriceFull7290058108879-000-340-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 18.9 | v1 | loaded | 2,336 | 0.25 |
| mega | price_full | `PriceFull7290055700007-001-002-20261021-051019.gz` | 2026-10-21T05:10+03:00 | 17.8 | v1 | loaded | 5,899 | 0.59 |
| osherad | price_full | `PriceFull7290103152017-001-001-20261021-080011.gz` | 2026-10-21T08:00+03:00 | 15.0 | v1 | loaded | 6,508 | 0.69 |
| ramilevy | price_full | `PriceFull7290058140886-001-001-20261021-001002.gz` | 2026-10-21T00:10+03:00 | 22.8 | v1 | loaded | 12,976 | 1.38 |
| shufersal | price_full | `PriceFull7290027600007-001-164-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 5,556 | 0.62 |
| tivtaam | price_full | `PriceFull7290873255550-000-002-20261021-004004.gz` | 2026-10-21T00:40+03:00 | 22.3 | v1 | loaded | 21,598 | 2.33 |
| yohananof | price_full | `PriceFull7290803800003-000-001-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 22.3 | v1 | loaded | 10,732 | 1.11 |
| king_store | price_full | `PriceFull7290058108879-000-014-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 18.9 | v1 | loaded | 4,833 | 0.61 |
| king_store | price_full | `PriceFull7290058108879-000-200-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 18.9 | v1 | loaded | 3,628 | 0.39 |
| king_store | promo_full | `PromoFull7290058108879-000-014-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 18.9 | v1 | loaded | 430 | 0.06 |
| king_store | promo_full | `PromoFull7290058108879-000-200-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 18.9 | v1 | loaded | 313 | 0.05 |
| mega | price_full | `PriceFull7290055700007-001-091-20261021-051007.gz` | 2026-10-21T05:10+03:00 | 17.8 | v1 | loaded | 6,825 | 0.82 |
| mega | price_full | `PriceFull7290055700007-001-418-20261021-051008.gz` | 2026-10-21T05:10+03:00 | 17.8 | v1 | loaded | 5,782 | 0.66 |
| mega | price_full | `PriceFull7290055700007-001-452-20261021-051010.gz` | 2026-10-21T05:10+03:00 | 17.8 | v1 | loaded | 8,176 | 0.99 |
| mega | price_full | `PriceFull7290055700007-001-457-20261021-051015.gz` | 2026-10-21T05:10+03:00 | 17.8 | v1 | loaded | 9,248 | 0.96 |
| mega | price_full | `PriceFull7290055700007-001-407-20261021-051019.gz` | 2026-10-21T05:10+03:00 | 17.8 | v1 | loaded | 8,576 | 1.0 |
| mega | price_full | `PriceFull7290055700007-001-470-20261021-064437.gz` | 2026-10-21T06:44+03:00 | 16.2 | v1 | loaded | 4,836 | 0.49 |
| mega | promo_full | `PromoFull7290055700007-001-418-20261021-051058.gz` | 2026-10-21T05:10+03:00 | 17.8 | v1 | loaded | 1,445 | 0.25 |
| mega | promo_full | `PromoFull7290055700007-001-091-20261021-051103.gz` | 2026-10-21T05:11+03:00 | 17.8 | v1 | loaded | 1,530 | 0.34 |
| mega | promo_full | `PromoFull7290055700007-001-452-20261021-051116.gz` | 2026-10-21T05:11+03:00 | 17.8 | v1 | loaded | 1,518 | 0.24 |
| mega | promo_full | `PromoFull7290055700007-001-407-20261021-051125.gz` | 2026-10-21T05:11+03:00 | 17.8 | v1 | loaded | 1,465 | 0.25 |
| mega | promo_full | `PromoFull7290055700007-001-457-20261021-051126.gz` | 2026-10-21T05:11+03:00 | 17.8 | v1 | loaded | 1,437 | 0.26 |
| mega | promo_full | `PromoFull7290055700007-001-470-20261021-064509.gz` | 2026-10-21T06:45+03:00 | 16.2 | v1 | loaded | 1,433 | 0.24 |
| osherad | price_full | `PriceFull7290103152017-001-026-20261021-140501.gz` | 2026-10-21T14:05+03:00 | 8.9 | v1 | loaded | 6,836 | 0.77 |
| osherad | price_full | `PriceFull7290103152017-001-030-20261021-140501.gz` | 2026-10-21T14:05+03:00 | 8.9 | v1 | loaded | 6,465 | 0.67 |
| osherad | price_full | `PriceFull7290103152017-001-010-20261021-140502.gz` | 2026-10-21T14:05+03:00 | 8.9 | v1 | loaded | 6,699 | 0.79 |
| osherad | price_full | `PriceFull7290103152017-001-028-20261021-140502.gz` | 2026-10-21T14:05+03:00 | 8.9 | v1 | loaded | 6,246 | 0.66 |
| osherad | promo_full | `PromoFull7290103152017-001-028-20261021-140522.gz` | 2026-10-21T14:05+03:00 | 8.9 | v1 | loaded | 716 | 0.12 |
| osherad | promo_full | `PromoFull7290103152017-001-026-20261021-140527.gz` | 2026-10-21T14:05+03:00 | 8.9 | v1 | loaded | 734 | 0.12 |
| osherad | promo_full | `PromoFull7290103152017-001-030-20261021-140545.gz` | 2026-10-21T14:05+03:00 | 8.9 | v1 | loaded | 750 | 0.1 |
| osherad | promo_full | `PromoFull7290103152017-001-010-20261021-140558.gz` | 2026-10-21T14:05+03:00 | 8.9 | v1 | loaded | 705 | 0.12 |
| ramilevy | price_full | `PriceFull7290058140886-001-062-20261021-120007.gz` | 2026-10-21T12:00+03:00 | 11.0 | v1 | loaded | 14,121 | 1.56 |
| ramilevy | price_full | `PriceFull7290058140886-001-703-20261021-120007.gz` | 2026-10-21T12:00+03:00 | 11.0 | v1 | loaded | 4,955 | 0.59 |
| ramilevy | price_full | `PriceFull7290058140886-001-048-20261021-120011.gz` | 2026-10-21T12:00+03:00 | 11.0 | v1 | loaded | 14,448 | 1.65 |
| ramilevy | price_full | `PriceFull7290058140886-001-057-20261021-121509.gz` | 2026-10-21T12:15+03:00 | 10.7 | v1 | loaded | 13,927 | 1.45 |
| ramilevy | price_full | `PriceFull7290058140886-001-724-20261021-180005.gz` | 2026-10-21T18:00+03:00 | 5.0 | v1 | loaded | 5,164 | 0.59 |
| ramilevy | price_full | `PriceFull7290058140886-001-725-20261021-180015.gz` | 2026-10-21T18:00+03:00 | 5.0 | v1 | loaded | 4,119 | 0.53 |
| ramilevy | promo_full | `PromoFull7290058140886-001-703-20261021-120038.gz` | 2026-10-21T12:00+03:00 | 11.0 | v1 | loaded | 1,108 | 0.18 |
| ramilevy | promo_full | `PromoFull7290058140886-001-048-20261021-120055.gz` | 2026-10-21T12:00+03:00 | 11.0 | v1 | loaded | 2,525 | 0.47 |
| ramilevy | promo_full | `PromoFull7290058140886-001-062-20261021-120113.gz` | 2026-10-21T12:01+03:00 | 11.0 | v1 | loaded | 2,532 | 0.64 |
| ramilevy | promo_full | `PromoFull7290058140886-001-057-20261021-121655.gz` | 2026-10-21T12:16+03:00 | 10.7 | v1 | loaded | 2,532 | 0.54 |
| ramilevy | promo_full | `PromoFull7290058140886-001-724-20261021-180029.gz` | 2026-10-21T18:00+03:00 | 5.0 | v1 | loaded | 1,060 | 0.27 |
| ramilevy | promo_full | `PromoFull7290058140886-001-725-20261021-180038.gz` | 2026-10-21T18:00+03:00 | 5.0 | v1 | loaded | 1,047 | 0.19 |
| shufersal | price_full | `PriceFull7290027600007-001-002-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 7,488 | 0.78 |
| shufersal | price_full | `PriceFull7290027600007-001-302-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 6,534 | 0.64 |
| shufersal | price_full | `PriceFull7290027600007-006-300-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 7,723 | 0.85 |
| shufersal | price_full | `PriceFull7290027600007-007-285-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 3,328 | 0.33 |
| shufersal | price_full | `PriceFull7290027600007-007-353-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 2,271 | 0.24 |
| shufersal | price_full | `PriceFull7290027600007-018-753-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 3,547 | 0.35 |
| shufersal | promo_full | `PromoFull7290027600007-001-002-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 1,379 | 0.76 |
| shufersal | promo_full | `PromoFull7290027600007-001-302-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 1,281 | 0.6 |
| shufersal | promo_full | `PromoFull7290027600007-006-300-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 1,008 | 0.71 |
| shufersal | promo_full | `PromoFull7290027600007-007-285-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 743 | 0.27 |
| shufersal | promo_full | `PromoFull7290027600007-007-353-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 616 | 0.21 |
| shufersal | promo_full | `PromoFull7290027600007-018-753-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 18.5 | v1 | loaded | 418 | 0.21 |
| tivtaam | price_full | `PriceFull7290873255550-000-012-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 7.4 | v1 | loaded | 17,832 | 1.89 |
| tivtaam | price_full | `PriceFull7290873255550-000-085-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 7.4 | v1 | loaded | 7,171 | 0.74 |
| tivtaam | price_full | `PriceFull7290873255550-000-087-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 7.4 | v1 | loaded | 6,069 | 0.71 |
| tivtaam | price_full | `PriceFull7290873255550-000-092-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 7.4 | v1 | loaded | 5,851 | 0.6 |
| tivtaam | promo_full | `PromoFull7290873255550-000-012-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 7.4 | v1 | loaded | 2,040 | 1.41 |
| tivtaam | promo_full | `PromoFull7290873255550-000-085-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 7.4 | v1 | loaded | 1,282 | 2.5 |
| tivtaam | promo_full | `PromoFull7290873255550-000-087-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 7.4 | v1 | loaded | 1,126 | 1.22 |
| tivtaam | promo_full | `PromoFull7290873255550-000-092-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 7.4 | v1 | loaded | 1,060 | 0.72 |
| yohananof | price_full | `PriceFull7290803800003-000-020-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 22.3 | v1 | loaded | 11,887 | 1.38 |
| yohananof | price_full | `PriceFull7290803800003-000-021-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 22.3 | v1 | loaded | 11,197 | 1.21 |
| yohananof | promo_full | `PromoFull7290803800003-000-020-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 22.3 | v1 | loaded | 1,277 | 0.2 |
| yohananof | promo_full | `PromoFull7290803800003-000-021-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 22.3 | v1 | loaded | 1,212 | 0.2 |

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

- seed: 0.76 s
- normalize: 4.84 s
- extract (rule): 47.18 s
- embed (hash): 246.84 s
- judge (rule): 139.03 s

### Precompute (production semantics)

8,221 rows written in 0.539 s of job time (0.77 s wall including start-up); 5,706 items priced at 37 stores (843 stores of 7 chains considered); 0 rows with a promo, 0 club-only. Canonicals with a real price: 209, of them 191 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 3,612 | 193 | 37 |
| close | 4,609 | 209 | 37 |

### Precompute (stress)

13,609 rows written in 1.243 s of job time (1.49 s wall including start-up); 20,556 items priced at 37 stores (843 stores of 7 chains considered); 0 rows with a promo, 0 club-only. Canonicals with a real price: 241, of them 236 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 6,182 | 237 | 37 |
| close | 7,427 | 241 | 37 |

### The vector query behind /parse-list and /search

`item_embeddings` holds 99,612 rows (model `hash-ngram-2-3-4-v1`); one `ORDER BY embedding <=> q LIMIT 40` query took [3.0, 0.7, 0.5] ms; with sequential scans disabled 0.5 ms.

```
Limit  (cost=2328.11..2592.67 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2328.11..661155.33 rows=99612 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
--- enable_seqscan = off
Limit  (cost=2328.11..2592.67 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2328.11..661155.33 rows=99612 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
```

One `/parse-list` call (6 lines): 2957.2 ms in total, 2950.6 ms inside 37 SQL statements. The statements that cost the most:

| statement (first 110 characters) | calls | total ms | max ms |
|---|---|---|---|
| `WITH qv AS (SELECT %(v)s::vector AS v), direct AS ( SELECT c.id AS canonical_id, 1 - (c.embedding <=> qv.v) AS` | 6 | 2923.9 | 514.8 |
| `WITH q AS (SELECT search_norm(%(q)s) AS t) SELECT c.id, word_similarity(q.t, search_norm(c.display_name_he)) A` | 6 | 12.5 | 4.9 |
| `WITH RECURSIVE up AS ( SELECT t.id AS leaf, t.id, t.parent_id, t.name_he, t.level FROM taxonomy t WHERE t.id =` | 6 | 4.7 | 1.1 |
| `SELECT id, display_name_he, taxonomy_id, base_unit, rank, names_ar[1] FROM canonical_products WHERE id = ANY(%` | 6 | 3.9 | 1.0 |
| `SELECT c.id, c.display_name_he, ts_rank_cd(to_tsvector('simple', search_norm(c.display_name_he)), tq) AS r FRO` | 6 | 3.3 | 1.1 |
| `SELECT set_config('pg_trgm.word_similarity_threshold', %s, true)` | 6 | 1.9 | 0.7 |

### /parse-list, /compare and /optimize (production semantics)

Locations: Jerusalem centre (10 priced stores, 6 chains within 5 km); near בית הדובדבן - אונו (9 priced stores, 5 chains within 5 km); Haifa centre (8 priced stores, 5 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 3161.5 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 8798.1 |
| large (32 lines) | 33 | 33 | 5 | 0 | 16750.7 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 10 | 0 | 5.6 | 4.9 | 8.1 | 55 | single: רמי לוי עטרות | 5.73 / 5.73 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 10 | 0 | 7.7 | 5.1 | 8.7 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 33 | 10 | 0 | 7.9 | 6.5 | 11.6 | 55 | single: רמי לוי עטרות | 86.8 / 86.8 |
| Jerusalem centre | drawn: 5 | 5 | 10 | 6 | 4.5 | 3.8 | 7.7 | 55 | single: קרפור (מגה) קרפור מרקט ריינס | 5.07 / 5.07 |
| Jerusalem centre | drawn: 10 | 10 | 10 | 0 | 5.5 | 4.7 | 8.8 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | drawn: 20 | 20 | 10 | 0 | 6.7 | 5.4 | 12.3 | 55 | single: רמי לוי עטרות | 66.97 / 66.97 |
| Jerusalem centre | drawn: 40 | 40 | 10 | 0 | 10.6 | 8.6 | 16.1 | 55 | single: רמי לוי עטרות | 203.37 / 203.37 |
| near בית הדובדבן - אונו | hand: small (6 lines) | 6 | 9 | 0 | 4.4 | 3.2 | 6 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: weekly (17 lines) | 17 | 9 | 0 | 6.1 | 3.9 | 6.8 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: large (32 lines) | 33 | 9 | 0 | 8 | 4.2 | 7.5 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 5 | 5 | 9 | 0 | 4.1 | 3.3 | 6.1 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 10 | 10 | 9 | 0 | 5.4 | 3.8 | 7.1 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 20 | 20 | 9 | 0 | 7.4 | 4.4 | 7.2 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 40 | 40 | 9 | 0 | 11.1 | 5 | 8.3 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| Haifa centre | hand: small (6 lines) | 6 | 8 | 0 | 3.9 | 3.4 | 6.7 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | hand: weekly (17 lines) | 17 | 8 | 0 | 5.2 | 3.9 | 7.4 | 55 | single: שופרסל שלי חיפה- קלר | -11.87 / -11.87 |
| Haifa centre | hand: large (32 lines) | 33 | 8 | 0 | 7.5 | 5.1 | 9.4 | 55 | single: שופרסל שלי חיפה- קלר | -18.47 / -18.47 |
| Haifa centre | drawn: 5 | 5 | 8 | 2 | 3.8 | 3.3 | 6.7 | 55 | single: שופרסל שלי חיפה- קלר | 4.63 / 4.63 |
| Haifa centre | drawn: 10 | 10 | 8 | 0 | 4.7 | 3.8 | 7.8 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | drawn: 20 | 20 | 8 | 0 | 6.9 | 4.6 | 9.6 | 55 | single: שופרסל שלי חיפה- קלר | -5.17 / -5.17 |
| Haifa centre | drawn: 40 | 40 | 8 | 0 | 9.2 | 5.8 | 9.5 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 4.4 | 3.4 | 6.7 |
| hand: weekly (17 lines) | 6.1 | 3.9 | 7.4 |
| hand: large (32 lines) | 7.9 | 5.1 | 9.4 |
| drawn: 5 | 4.1 | 3.3 | 6.7 |
| drawn: 10 | 5.4 | 3.8 | 7.8 |
| drawn: 20 | 6.9 | 4.6 | 9.6 |
| drawn: 40 | 10.6 | 5.8 | 9.5 |

### /parse-list, /compare and /optimize (stress: unreviewed mappings included, performance only)

Locations: Jerusalem centre (10 priced stores, 6 chains within 5 km); near בית הדובדבן - אונו (9 priced stores, 5 chains within 5 km); Haifa centre (8 priced stores, 5 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 2935.7 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 8414.3 |
| large (32 lines) | 33 | 33 | 5 | 0 | 16691 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 10 | 5 | 6.2 | 5.2 | 15.6 | 55 | single: רמי לוי עטרות | 57.26 / 57.26 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 10 | 0 | 7.5 | 6.1 | 10.4 | 55 | single: רמי לוי עטרות | 55.54 / 55.54 |
| Jerusalem centre | hand: large (32 lines) | 33 | 10 | 0 | 10.3 | 8 | 11.9 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | drawn: 5 | 5 | 10 | 4 | 4.3 | 3.6 | 7.1 | 55 | single: רמי לוי עטרות | 110.27 / 110.27 |
| Jerusalem centre | drawn: 10 | 10 | 10 | 0 | 4.6 | 4.2 | 8 | 55 | single: קרפור (מגה) קרפור מרקט ריינס | 8.77 / 8.77 |
| Jerusalem centre | drawn: 20 | 20 | 10 | 0 | 7 | 5.7 | 10.1 | 55 | single: רמי לוי עטרות | 160.67 / 160.67 |
| Jerusalem centre | drawn: 40 | 40 | 10 | 0 | 13.8 | 8.8 | 14 | 55 | single: רמי לוי עטרות | 568.67 / 568.67 |
| near בית הדובדבן - אונו | hand: small (6 lines) | 6 | 9 | 7 | 4.7 | 3.3 | 5.8 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: weekly (17 lines) | 17 | 9 | 0 | 7.1 | 4.1 | 7.2 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | hand: large (32 lines) | 33 | 9 | 0 | 10.5 | 5 | 8.6 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 5 | 5 | 9 | 6 | 4.7 | 3.4 | 6.2 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 10 | 10 | 9 | 0 | 5.4 | 3.8 | 6.8 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 20 | 20 | 9 | 0 | 7.7 | 4.1 | 7.1 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| near בית הדובדבן - אונו | drawn: 40 | 40 | 9 | 0 | 12 | 5 | 8.6 | 55 | single: טיב טעם בית הדובדבן - אונו | 0.0 / 0.0 |
| Haifa centre | hand: small (6 lines) | 6 | 8 | 5 | 4.5 | 3.7 | 6.7 | 55 | single: שופרסל שלי חיפה- קלר | -5.95 / -5.95 |
| Haifa centre | hand: weekly (17 lines) | 17 | 8 | 0 | 6.1 | 4.6 | 8.1 | 55 | single: שופרסל שלי חיפה- קלר | 23.67 / 23.67 |
| Haifa centre | hand: large (32 lines) | 33 | 8 | 0 | 9.1 | 5.9 | 9.3 | 55 | single: שופרסל שלי חיפה- קלר | 95.97 / 95.97 |
| Haifa centre | drawn: 5 | 5 | 8 | 3 | 3.8 | 3.3 | 6.5 | 55 | single: שופרסל שלי חיפה- קלר | 3.03 / 3.03 |
| Haifa centre | drawn: 10 | 10 | 8 | 0 | 4.8 | 3.7 | 7 | 55 | single: שופרסל שלי חיפה- קלר | -5.87 / -5.87 |
| Haifa centre | drawn: 20 | 20 | 8 | 1 | 6.8 | 4.6 | 8.3 | 55 | single: שופרסל שלי חיפה- קלר | 25.43 / 25.43 |
| Haifa centre | drawn: 40 | 40 | 8 | 0 | 10.5 | 6.1 | 10.4 | 55 | single: שופרסל שלי חיפה- קלר | -4.37 / -4.37 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 4.7 | 3.7 | 6.7 |
| hand: weekly (17 lines) | 7.1 | 4.6 | 8.1 |
| hand: large (32 lines) | 10.3 | 5.9 | 9.3 |
| drawn: 5 | 4.3 | 3.4 | 6.5 |
| drawn: 10 | 4.8 | 3.8 | 7.0 |
| drawn: 20 | 7.0 | 4.6 | 8.3 |
| drawn: 40 | 12.0 | 6.1 | 10.4 |

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

- **ingest**: 4 Stores files are older than the stale-date gate's 36 h (osherad 62.8 h, ramilevy 65.8 h, tivtaam 65.8 h, yohananof 69.9 h); on the real clock the gate would quarantine them and no store of those chains would load (this run replayed the clock for them)
- **ingest**: 36722 promos loaded from 30 PromoFull files but 0 promo_items rows: no promo can reach a price (see the PromoFull table)
- **api**: /parse-list took over 2 s (production): {'small (6 lines)': 3161.5, 'weekly (17 lines)': 8798.1, 'large (32 lines)': 16750.7} ms
- **api**: /parse-list took over 2 s (stress): {'small (6 lines)': 2935.7, 'weekly (17 lines)': 8414.3, 'large (32 lines)': 16691.0} ms

