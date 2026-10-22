## One real day through the pipeline (dry run)

Mode `portal`, commit `2179f3d248aa`, runner `GitHub Actions 1000005090` (4 CPUs, Python 3.12.3, Postgres 17.11), 2026-10-22T06:21:23+00:00 to 2026-10-22T07:11:23+00:00 UTC. Measurements on one real day with hand-made baskets; the prices are real, the baskets and locations are not a sample of anything. **Not publishable.**

### Stages

| stage | seconds | result |
|---|---|---|
| download: portal probe (one Stores and one PriceFull per chain) | 2027.58 | ok |
| migrate | 1.18 | 32 applied |
| ingest: Stores files (Scheduler, adapters, gates, loader, store coordinates) | 0.36 | 6 files |
| download: PriceFull and PromoFull of the stores nearest to city centres | 107.26 | 48 files, anchors: Jerusalem centre, Holon, Petah Tikva |
| ingest: PriceFull and PromoFull files (Scheduler, adapters, gates, loader) | 204.32 | 60 files |
| catalog: seed | 1.19 | ok |
| catalog: normalize | 11.4 | ok |
| catalog: extract (rule) | 88.8 | ok |
| catalog: embed (hash) | 263.62 | ok |
| catalog: judge (rule) | 199.9 | ok |
| precompute effective prices (production semantics: reviewed mappings only) | 1.47 | 6799 rows |
| API: parse-list, compare, optimize (production) | 41.44 | 21 basket runs at 3 locations |
| diagnostic: the vector query behind /parse-list and /search | 8.89 | [4.5, 1.0, 0.9] ms per query |
| basket index dry run (production semantics) | 0.46 | status draft |
| diagnostic: real items behind the basket lines no chain prices | 0.83 | chocolate-milk 72 items, hummus-plain 72 items, pasta-spaghetti 62 items |
| stress: mark the machine suggestions accepted (performance only) | 0.23 | 12907 mappings |
| precompute effective prices (stress: unreviewed mappings included) | 2.84 | 11084 rows |
| API: parse-list, compare, optimize (stress) | 36.82 | 21 basket runs at 3 locations |
| basket index dry run (stress) | 0.46 | status draft |

### Portals (the portal probe's own reachability and downloads)

| chain | reachable | login | Stores download | PriceFull download |
|---|---|---|---|---|
| hazihinam | BLOCKED? (403) | n/a | no: no file downloaded | no: no file downloaded |
| king_store | BLOCKED? (403) | n/a | Stores7290058108879-000-20261022-051042.gz | PriceFull7290058108879-000-340-20261022-051042.gz |
| machsanei_hashuk | UNREACHABLE (0) | n/a | no: no file downloaded | no: no file downloaded |
| mega | OK (200) | n/a | Stores7290055700007-000-20261022-000100.xml | PriceFull7290055700007-001-002-20261022-051018.gz |
| osherad | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290103152017-000-20261020-080500.xml | PriceFull7290103152017-001-001-20261022-080018.gz |
| ramilevy | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290058140886-000-20261020-050500.xml | PriceFull7290058140886-001-001-20261022-001004.gz |
| shufersal | UNREACHABLE (0) | n/a | no: timed out after 300s | no: timed out after 300s |
| tivtaam | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290873255550-000-20261020-050500.xml | PriceFull7290873255550-000-002-20261022-004004.gz |
| victory | UNREACHABLE (0) | n/a | no: no file downloaded | no: no file downloaded |
| yohananof | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290803800003-000-20261020-010000.xml | PriceFull7290803800003-000-001-20261022-004040.gz |

### Files, gates and rows per chain

| chain | kind | file | published (Israel) | age h | schema | gate result | rows | seconds |
|---|---|---|---|---|---|---|---|---|
| king_store | stores | `Stores7290058108879-000-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 4.7 | v1 | loaded | 48 | 0.07 |
| mega | stores | `Stores7290055700007-000-20261022-000100.xml` | 2026-10-22T00:01+03:00 | 9.9 | v1 | loaded | 147 | 0.1 |
| osherad | stores | `Stores7290103152017-000-20261020-080500.xml` | 2026-10-20T08:05+03:00 | 49.8 (stale on the real clock) | v1 | loaded | 24 | 0.03 |
| ramilevy | stores | `Stores7290058140886-000-20261020-050500.xml` | 2026-10-20T05:05+03:00 | 52.8 (stale on the real clock) | v1 | loaded | 99 | 0.06 |
| tivtaam | stores | `Stores7290873255550-000-20261020-050500.xml` | 2026-10-20T05:05+03:00 | 52.8 (stale on the real clock) | v1 | loaded | 54 | 0.04 |
| yohananof | stores | `Stores7290803800003-000-20261020-010000.xml` | 2026-10-20T01:00+03:00 | 56.9 (stale on the real clock) | v1 | loaded | 51 | 0.03 |
| king_store | price_full | `PriceFull7290058108879-000-340-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 2,338 | 0.48 |
| king_store | promo_full | `PromoFull7290058108879-000-340-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 296 | 0.17 |
| mega | price_full | `PriceFull7290055700007-001-002-20261022-051018.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 5,879 | 1.2 |
| mega | promo_full | `PromoFull7290055700007-001-002-20261022-051124.gz` | 2026-10-22T05:11+03:00 | 4.8 | v1 | loaded | 1,547 | 0.78 |
| osherad | price_full | `PriceFull7290103152017-001-001-20261022-080018.gz` | 2026-10-22T08:00+03:00 | 1.9 | v1 | loaded | 6,495 | 1.26 |
| osherad | promo_full | `PromoFull7290103152017-001-001-20261022-080055.gz` | 2026-10-22T08:00+03:00 | 1.9 | v1 | loaded | 660 | 0.36 |
| ramilevy | price_full | `PriceFull7290058140886-001-001-20261022-001004.gz` | 2026-10-22T00:10+03:00 | 9.8 | v1 | loaded | 12,975 | 2.57 |
| ramilevy | promo_full | `PromoFull7290058140886-001-001-20261022-001131.gz` | 2026-10-22T00:11+03:00 | 9.8 | v1 | loaded | 2,660 | 1.63 |
| tivtaam | price_full | `PriceFull7290873255550-000-002-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 21,607 | 4.37 |
| tivtaam | promo_full | `PromoFull7290873255550-000-002-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 2,246 | 6.37 |
| yohananof | price_full | `PriceFull7290803800003-000-001-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 10,722 | 2.13 |
| yohananof | promo_full | `PromoFull7290803800003-000-009-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 1,206 | 0.88 |
| king_store | price_full | `PriceFull7290058108879-000-200-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 3,611 | 0.79 |
| king_store | promo_full | `PromoFull7290058108879-000-200-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 306 | 0.18 |
| mega | price_full | `PriceFull7290055700007-001-407-20261022-051000.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 8,571 | 1.74 |
| mega | price_full | `PriceFull7290055700007-001-091-20261022-051002.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 6,836 | 1.39 |
| mega | price_full | `PriceFull7290055700007-001-452-20261022-051004.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 8,170 | 1.61 |
| mega | price_full | `PriceFull7290055700007-001-345-20261022-051005.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 6,633 | 1.36 |
| mega | price_full | `PriceFull7290055700007-001-457-20261022-051010.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 9,234 | 1.9 |
| mega | price_full | `PriceFull7290055700007-001-067-20261022-051014.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 7,877 | 1.62 |
| mega | promo_full | `PromoFull7290055700007-001-452-20261022-051056.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 1,516 | 0.85 |
| mega | promo_full | `PromoFull7290055700007-001-091-20261022-051057.gz` | 2026-10-22T05:10+03:00 | 4.8 | v1 | loaded | 1,532 | 0.85 |
| mega | promo_full | `PromoFull7290055700007-001-407-20261022-051106.gz` | 2026-10-22T05:11+03:00 | 4.8 | v1 | loaded | 1,462 | 0.8 |
| mega | promo_full | `PromoFull7290055700007-001-067-20261022-051111.gz` | 2026-10-22T05:11+03:00 | 4.8 | v1 | loaded | 1,442 | 0.81 |
| mega | promo_full | `PromoFull7290055700007-001-345-20261022-051117.gz` | 2026-10-22T05:11+03:00 | 4.8 | v1 | loaded | 1,442 | 0.84 |
| mega | promo_full | `PromoFull7290055700007-001-457-20261022-051121.gz` | 2026-10-22T05:11+03:00 | 4.8 | v1 | loaded | 1,434 | 0.83 |
| osherad | price_full | `PriceFull7290103152017-001-028-20261022-070013.gz` | 2026-10-22T07:00+03:00 | 3.0 | v1 | loaded | 6,234 | 1.27 |
| osherad | price_full | `PriceFull7290103152017-001-025-20261022-080000.gz` | 2026-10-22T08:00+03:00 | 2.0 | v1 | loaded | 6,252 | 1.24 |
| osherad | price_full | `PriceFull7290103152017-001-010-20261022-080001.gz` | 2026-10-22T08:00+03:00 | 2.0 | v1 | loaded | 6,690 | 1.36 |
| osherad | price_full | `PriceFull7290103152017-001-026-20261022-080012.gz` | 2026-10-22T08:00+03:00 | 2.0 | v1 | loaded | 6,833 | 1.37 |
| osherad | promo_full | `PromoFull7290103152017-001-028-20261022-070050.gz` | 2026-10-22T07:00+03:00 | 3.0 | v1 | loaded | 715 | 0.45 |
| osherad | promo_full | `PromoFull7290103152017-001-025-20261022-080037.gz` | 2026-10-22T08:00+03:00 | 2.0 | v1 | loaded | 739 | 0.44 |
| osherad | promo_full | `PromoFull7290103152017-001-026-20261022-080049.gz` | 2026-10-22T08:00+03:00 | 2.0 | v1 | loaded | 734 | 0.44 |
| osherad | promo_full | `PromoFull7290103152017-001-010-20261022-080106.gz` | 2026-10-22T08:01+03:00 | 2.0 | v1 | loaded | 705 | 0.44 |
| ramilevy | price_full | `PriceFull7290058140886-001-703-20261022-001001.gz` | 2026-10-22T00:10+03:00 | 9.8 | v1 | loaded | 4,950 | 1.0 |
| ramilevy | price_full | `PriceFull7290058140886-001-048-20261022-001016.gz` | 2026-10-22T00:10+03:00 | 9.8 | v1 | loaded | 14,443 | 2.94 |
| ramilevy | price_full | `PriceFull7290058140886-001-718-20261022-060005.gz` | 2026-10-22T06:00+03:00 | 4.0 | v1 | loaded | 3,809 | 0.78 |
| ramilevy | price_full | `PriceFull7290058140886-001-725-20261022-060005.gz` | 2026-10-22T06:00+03:00 | 4.0 | v1 | loaded | 4,108 | 0.88 |
| ramilevy | price_full | `PriceFull7290058140886-001-050-20261022-060006.gz` | 2026-10-22T06:00+03:00 | 4.0 | v1 | loaded | 14,809 | 3.05 |
| ramilevy | price_full | `PriceFull7290058140886-001-724-20261022-060015.gz` | 2026-10-22T06:00+03:00 | 4.0 | v1 | loaded | 5,147 | 1.07 |
| ramilevy | promo_full | `PromoFull7290058140886-001-703-20261022-001044.gz` | 2026-10-22T00:10+03:00 | 9.8 | v1 | loaded | 1,109 | 0.69 |
| ramilevy | promo_full | `PromoFull7290058140886-001-048-20261022-001113.gz` | 2026-10-22T00:11+03:00 | 9.8 | v1 | loaded | 2,529 | 1.76 |
| ramilevy | promo_full | `PromoFull7290058140886-001-718-20261022-060028.gz` | 2026-10-22T06:00+03:00 | 4.0 | v1 | loaded | 1,072 | 0.7 |
| ramilevy | promo_full | `PromoFull7290058140886-001-725-20261022-060028.gz` | 2026-10-22T06:00+03:00 | 4.0 | v1 | loaded | 1,047 | 0.72 |
| ramilevy | promo_full | `PromoFull7290058140886-001-724-20261022-060039.gz` | 2026-10-22T06:00+03:00 | 4.0 | v1 | loaded | 1,060 | 0.71 |
| ramilevy | promo_full | `PromoFull7290058140886-001-050-20261022-060107.gz` | 2026-10-22T06:01+03:00 | 4.0 | v1 | loaded | 2,507 | 1.71 |
| tivtaam | price_full | `PriceFull7290873255550-000-006-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 16,079 | 3.28 |
| tivtaam | price_full | `PriceFull7290873255550-000-079-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 6,351 | 1.26 |
| tivtaam | price_full | `PriceFull7290873255550-000-085-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 7,171 | 1.47 |
| tivtaam | price_full | `PriceFull7290873255550-000-087-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 6,069 | 1.33 |
| tivtaam | promo_full | `PromoFull7290873255550-000-006-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 2,000 | 6.4 |
| tivtaam | promo_full | `PromoFull7290873255550-000-079-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 567 | 6.03 |
| tivtaam | promo_full | `PromoFull7290873255550-000-085-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 1,281 | 6.4 |
| tivtaam | promo_full | `PromoFull7290873255550-000-087-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 1,124 | 5.76 |
| yohananof | price_full | `PriceFull7290803800003-000-020-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 11,876 | 2.35 |
| yohananof | price_full | `PriceFull7290803800003-000-021-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 11,196 | 2.28 |
| yohananof | price_full | `PriceFull7290803800003-000-029-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 10,462 | 2.1 |
| yohananof | promo_full | `PromoFull7290803800003-000-020-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 1,276 | 0.98 |
| yohananof | promo_full | `PromoFull7290803800003-000-021-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 1,218 | 0.95 |
| yohananof | promo_full | `PromoFull7290803800003-000-029-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 9.3 | v1 | loaded | 1,106 | 0.84 |

PromoFull files: what they hold and how much reached `promo_items`:

| chain | file | promos | with item codes | distinct codes | codes the chain's items know | promo_items linked | active now | club | rewards |
|---|---|---|---|---|---|---|---|---|---|
| king_store | `PromoFull7290058108879-000-340-20261022-051042.gz` | 296 | 296 | 678 | 678 | 685 | 295 | 63 | {'bundle': 166, 'price': 130} |
| mega | `PromoFull7290055700007-001-002-20261022-051124.gz` | 1,547 | 1,547 | 5,382 | 1,985 | 2,185 | 1,547 | 6 | {'other': 104, 'price': 789, 'buy_x_get_y': 7, 'bundle': 631, 'percent': 16} |
| osherad | `PromoFull7290103152017-001-001-20261022-080055.gz` | 660 | 660 | 2,624 | 1,774 | 1,839 | 660 | 0 | {'bundle': 599, 'other': 3, 'price': 58} |
| ramilevy | `PromoFull7290058140886-001-001-20261022-001131.gz` | 2,660 | 2,660 | 8,980 | 5,898 | 8,932 | 2,660 | 37 | {'price': 1288, 'other': 486, 'bundle': 868, 'buy_x_get_y': 16, 'percent': 2} |
| tivtaam | `PromoFull7290873255550-000-002-20261022-004004.gz` | 2,246 | 2,246 | 15,685 | 12,380 | 24,389 | 2,246 | 1,384 | {'other': 19, 'bundle': 927, 'price': 1260, 'percent': 2, 'buy_x_get_y': 38} |
| yohananof | `PromoFull7290803800003-000-009-20261022-004040.gz` | 1,206 | 1,206 | 3,985 | 3,576 | 3,621 | 1,206 | 11 | {'bundle': 794, 'price': 348, 'other': 54, 'percent': 3, 'buy_x_get_y': 7} |
| king_store | `PromoFull7290058108879-000-200-20261022-051042.gz` | 306 | 306 | 813 | 813 | 831 | 306 | 77 | {'price': 143, 'bundle': 162, 'other': 1} |
| mega | `PromoFull7290055700007-001-452-20261022-051056.gz` | 1,516 | 1,516 | 5,385 | 3,838 | 4,143 | 1,516 | 6 | {'price': 754, 'bundle': 633, 'other': 106, 'percent': 16, 'buy_x_get_y': 7} |
| mega | `PromoFull7290055700007-001-091-20261022-051057.gz` | 1,532 | 1,532 | 5,403 | 3,839 | 4,136 | 1,532 | 6 | {'other': 105, 'price': 766, 'bundle': 638, 'buy_x_get_y': 7, 'percent': 16} |
| mega | `PromoFull7290055700007-001-407-20261022-051106.gz` | 1,462 | 1,462 | 5,083 | 3,648 | 3,872 | 1,462 | 6 | {'other': 95, 'buy_x_get_y': 7, 'price': 941, 'bundle': 403, 'percent': 16} |
| mega | `PromoFull7290055700007-001-067-20261022-051111.gz` | 1,442 | 1,442 | 5,122 | 3,683 | 3,992 | 1,442 | 6 | {'buy_x_get_y': 7, 'price': 913, 'bundle': 403, 'other': 103, 'percent': 16} |
| mega | `PromoFull7290055700007-001-345-20261022-051117.gz` | 1,442 | 1,442 | 5,119 | 3,680 | 3,987 | 1,442 | 6 | {'buy_x_get_y': 7, 'price': 913, 'bundle': 403, 'other': 103, 'percent': 16} |
| mega | `PromoFull7290055700007-001-457-20261022-051121.gz` | 1,434 | 1,434 | 5,055 | 3,622 | 3,846 | 1,434 | 6 | {'buy_x_get_y': 7, 'other': 95, 'price': 913, 'bundle': 403, 'percent': 16} |
| osherad | `PromoFull7290103152017-001-028-20261022-070050.gz` | 715 | 715 | 2,710 | 2,214 | 2,271 | 715 | 0 | {'bundle': 633, 'price': 80, 'other': 2} |
| osherad | `PromoFull7290103152017-001-025-20261022-080037.gz` | 739 | 739 | 2,838 | 2,301 | 2,419 | 739 | 0 | {'bundle': 666, 'price': 70, 'other': 3} |
| osherad | `PromoFull7290103152017-001-026-20261022-080049.gz` | 734 | 734 | 2,840 | 2,330 | 2,382 | 734 | 0 | {'bundle': 648, 'other': 3, 'price': 83} |
| osherad | `PromoFull7290103152017-001-010-20261022-080106.gz` | 705 | 705 | 2,771 | 2,263 | 2,362 | 705 | 0 | {'bundle': 640, 'price': 62, 'other': 3} |
| ramilevy | `PromoFull7290058140886-001-703-20261022-001044.gz` | 1,109 | 1,109 | 3,796 | 3,366 | 3,938 | 1,109 | 22 | {'price': 446, 'other': 289, 'bundle': 366, 'buy_x_get_y': 7, 'percent': 1} |
| ramilevy | `PromoFull7290058140886-001-048-20261022-001113.gz` | 2,529 | 2,529 | 8,848 | 7,014 | 10,744 | 2,529 | 37 | {'price': 1196, 'other': 450, 'bundle': 865, 'buy_x_get_y': 16, 'percent': 2} |
| ramilevy | `PromoFull7290058140886-001-718-20261022-060028.gz` | 1,072 | 1,072 | 3,968 | 3,433 | 3,974 | 1,072 | 24 | {'bundle': 357, 'other': 247, 'price': 459, 'buy_x_get_y': 8, 'percent': 1} |
| ramilevy | `PromoFull7290058140886-001-725-20261022-060028.gz` | 1,047 | 1,047 | 3,932 | 3,417 | 3,938 | 1,047 | 24 | {'bundle': 352, 'price': 439, 'other': 247, 'buy_x_get_y': 8, 'percent': 1} |
| ramilevy | `PromoFull7290058140886-001-724-20261022-060039.gz` | 1,060 | 1,060 | 3,951 | 3,425 | 3,966 | 1,060 | 24 | {'bundle': 357, 'price': 447, 'other': 247, 'buy_x_get_y': 8, 'percent': 1} |
| ramilevy | `PromoFull7290058140886-001-050-20261022-060107.gz` | 2,507 | 2,507 | 9,097 | 7,113 | 10,726 | 2,507 | 37 | {'bundle': 843, 'other': 458, 'price': 1188, 'buy_x_get_y': 16, 'percent': 2} |
| tivtaam | `PromoFull7290873255550-000-006-20261022-004004.gz` | 2,000 | 2,000 | 14,607 | 12,826 | 26,066 | 2,000 | 1,249 | {'other': 17, 'bundle': 834, 'price': 1134, 'percent': 2, 'buy_x_get_y': 13} |
| tivtaam | `PromoFull7290873255550-000-079-20261022-004004.gz` | 567 | 567 | 12,600 | 10,907 | 22,262 | 567 | 281 | {'other': 14, 'bundle': 259, 'price': 289, 'percent': 1, 'buy_x_get_y': 4} |
| tivtaam | `PromoFull7290873255550-000-085-20261022-004004.gz` | 1,281 | 1,281 | 13,365 | 11,584 | 23,659 | 1,281 | 711 | {'other': 16, 'bundle': 583, 'price': 670, 'buy_x_get_y': 12} |
| tivtaam | `PromoFull7290873255550-000-087-20261022-004004.gz` | 1,124 | 1,124 | 13,048 | 11,267 | 23,263 | 1,124 | 637 | {'other': 11, 'bundle': 538, 'price': 564, 'buy_x_get_y': 11} |
| yohananof | `PromoFull7290803800003-000-020-20261022-004040.gz` | 1,276 | 1,276 | 4,339 | 4,302 | 4,375 | 1,276 | 11 | {'bundle': 779, 'price': 399, 'other': 86, 'percent': 4, 'buy_x_get_y': 8} |
| yohananof | `PromoFull7290803800003-000-021-20261022-004040.gz` | 1,218 | 1,218 | 4,151 | 4,128 | 4,188 | 1,218 | 11 | {'bundle': 796, 'price': 356, 'other': 54, 'percent': 3, 'buy_x_get_y': 9} |
| yohananof | `PromoFull7290803800003-000-029-20261022-004040.gz` | 1,106 | 1,106 | 3,635 | 3,615 | 3,675 | 1,106 | 11 | {'other': 53, 'bundle': 734, 'price': 310, 'percent': 3, 'buy_x_get_y': 6} |

Sample codes (promo / item): king_store ['13006', '13174', '13747'] / ['12345', '13006', '13174']; mega ['1003', '1073', '1079'] / ['7290122780277', '7290122780291', '7290001598085']; osherad ['1230000292009', '16000423534', '16000548404'] / ['835811001454', '7290018571187', '7290018571163']; ramilevy ['1220000750166', '1230000068413', '1230000116022'] / ['7290017023212', '7290017023229', '7290017023236']; tivtaam ['11182170603', '11182175271', '11182700916'] / ['1101346', '1101421', '1101858']; yohananof ['14098', '16000185517', '16000423534'] / ['1022788', '1022801', '1022825']

`file_tracking` after the run: {'loaded': 66}. Alerts raised: 0.

| chain | physical stores | located | online | items | price events | stores with prices | promos | promo items |
|---|---|---|---|---|---|---|---|---|
| king_store | 48 | 28 | - | 4,530 | 5,949 | 2 | 602 | 1,516 |
| mega | 146 | 144 | 3 | 13,772 | 53,200 | 7 | 10,375 | 26,161 |
| osherad | 24 | 24 | - | 8,671 | 32,504 | 5 | 3,553 | 11,273 |
| ramilevy | 98 | 96 | 1 | 18,161 | 60,241 | 7 | 11,984 | 46,218 |
| tivtaam | 47 | 47 | 7 | 24,779 | 57,277 | 5 | 7,218 | 119,639 |
| yohananof | 50 | 19 | 1 | 13,856 | 44,256 | 4 | 4,806 | 15,859 |

Extra downloads (the stores nearest to these city centres, for the optimizer):

- Jerusalem centre: 5 chains and 17 located stores within 4 km; asked for mega 457,91, king_store 200, ramilevy 48,703, osherad 26,28, yohananof 20
- Holon: 5 chains and 16 located stores within 4 km; asked for mega 67,345, ramilevy 718,50, osherad 25, yohananof 29, tivtaam 79,6
- Petah Tikva: 5 chains and 16 located stores within 4 km; asked for mega 407,452, ramilevy 725,724, osherad 10, yohananof 21, tivtaam 87,85

### Matching on the real items

83,769 items; 17,847 mapped to a canonical (any level, including the review queue); 4,940 served (no review flag), onto 209 canonicals.

| level | mappings served | mappings in the review queue |
|---|---|---|
| exact | 0 | 0 |
| any_brand | 3,055 | 5,539 |
| close | 1,885 | 7,368 |

| chain | items | mapped | served |
|---|---|---|---|
| mega | 13,772 | 2,997 | 1,033 |
| king_store | 4,530 | 1,300 | 238 |
| ramilevy | 18,161 | 3,879 | 1,345 |
| osherad | 8,671 | 2,154 | 687 |
| yohananof | 13,856 | 2,677 | 939 |
| tivtaam | 24,779 | 4,840 | 698 |

- seed: 1.19 s
- normalize: 11.4 s
- extract (rule): 88.8 s
- embed (hash): 263.62 s
- judge (rule): 199.9 s

### Precompute (production semantics)

6,799 rows written in 0.979 s of job time (1.35 s wall including start-up); 4,737 items priced at 30 stores (425 stores of 6 chains considered); 1,834 rows with a promo, 217 club-only. Canonicals with a real price: 207, of them 184 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 3,013 | 189 | 30 |
| close | 3,786 | 207 | 30 |

Promos per chain, and what reached a price (production semantics):

| chain | promos | club-only | linked to items | reward `other` | effective rows | with a promo | club required | of them with a non-club fallback |
|---|---|---|---|---|---|---|---|---|
| mega | 10,375 | 42 | 8,958 | 711 | 1,645 | 274 | 16 | 16 |
| king_store | 602 | 140 | 602 | 1 | 293 | 79 | 19 | 19 |
| ramilevy | 11,984 | 205 | 11,027 | 2,424 | 1,805 | 648 | 0 | 0 |
| osherad | 3,553 | 0 | 3,218 | 14 | 813 | 265 | 0 | 0 |
| yohananof | 4,806 | 44 | 4,722 | 247 | 1,125 | 300 | 14 | 14 |
| tivtaam | 7,218 | 4,262 | 7,218 | 77 | 1,118 | 268 | 168 | 168 |

Club rules of the club-only promos (most frequent): `המועדון החדש` x 4,262; `מועדון חברתי \| מועדון רמי לוי \| מועדון לקוחות אשראי \| מועדון נטען \| לקוחות ארנק` x 132; `מועדון לקוחות \| לקוחות סיטונאים \| עובדי קינגסטור` x 79; `מועדון עובדים` x 44; `מועדון לקוחות \| עובדי קינגסטור` x 43; `מועדון קרפור אשראי \| מועדון אפליקציה` x 42; `מועדון לקוחות אשראי & תווי זיכוי מימוש` x 34; `לקוחות סיטונאים` x 16

### Precompute (stress)

11,084 rows written in 2.343 s of job time (2.71 s wall including start-up); 16,924 items priced at 30 stores (425 stores of 6 chains considered); 3,081 rows with a promo, 430 club-only. Canonicals with a real price: 241, of them 235 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 5,094 | 237 | 30 |
| close | 5,990 | 241 | 30 |

Promos per chain, and what reached a price (stress):

| chain | promos | club-only | linked to items | reward `other` | effective rows | with a promo | club required | of them with a non-club fallback |
|---|---|---|---|---|---|---|---|---|
| mega | 10,375 | 42 | 8,958 | 711 | 2,691 | 466 | 8 | 8 |
| king_store | 602 | 140 | 602 | 1 | 586 | 182 | 49 | 49 |
| ramilevy | 11,984 | 205 | 11,027 | 2,424 | 2,768 | 1,063 | 0 | 0 |
| osherad | 3,553 | 0 | 3,218 | 14 | 1,529 | 352 | 0 | 0 |
| yohananof | 4,806 | 44 | 4,722 | 247 | 1,635 | 410 | 14 | 14 |
| tivtaam | 7,218 | 4,262 | 7,218 | 77 | 1,875 | 608 | 359 | 359 |

Club rules of the club-only promos (most frequent): `המועדון החדש` x 4,262; `מועדון חברתי \| מועדון רמי לוי \| מועדון לקוחות אשראי \| מועדון נטען \| לקוחות ארנק` x 132; `מועדון לקוחות \| לקוחות סיטונאים \| עובדי קינגסטור` x 79; `מועדון עובדים` x 44; `מועדון לקוחות \| עובדי קינגסטור` x 43; `מועדון קרפור אשראי \| מועדון אפליקציה` x 42; `מועדון לקוחות אשראי & תווי זיכוי מימוש` x 34; `לקוחות סיטונאים` x 16

### The vector query behind /parse-list and /search

`item_embeddings` holds 83,769 rows (model `hash-ngram-2-3-4-v1`); one `ORDER BY embedding <=> q LIMIT 40` query took [4.5, 1.0, 0.9] ms; with sequential scans disabled 1.0 ms.

```
Limit  (cost=2263.35..2519.45 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2263.35..538607.65 rows=83769 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
--- enable_seqscan = off
Limit  (cost=2263.35..2519.45 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2263.35..538607.65 rows=83769 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
```

One `/parse-list` call (6 lines): 4063.1 ms in total, 4052.9 ms inside 37 SQL statements. The statements that cost the most:

| statement (first 110 characters) | calls | total ms | max ms |
|---|---|---|---|
| `WITH qv AS (SELECT %(v)s::vector AS v), direct AS ( SELECT c.id AS canonical_id, 1 - (c.embedding <=> qv.v) AS` | 6 | 4015.5 | 696.9 |
| `WITH q AS (SELECT search_norm(%(q)s) AS t) SELECT c.id, word_similarity(q.t, search_norm(c.display_name_he)) A` | 6 | 20.1 | 7.5 |
| `SELECT c.id, c.display_name_he, ts_rank_cd(to_tsvector('simple', search_norm(c.display_name_he)), tq) AS r FRO` | 6 | 4.8 | 1.9 |
| `WITH RECURSIVE up AS ( SELECT t.id AS leaf, t.id, t.parent_id, t.name_he, t.level FROM taxonomy t WHERE t.id =` | 6 | 4.7 | 1.1 |
| `SELECT id, display_name_he, taxonomy_id, base_unit, rank, names_ar[1] FROM canonical_products WHERE id = ANY(%` | 6 | 4.6 | 1.0 |
| `SELECT set_config('pg_trgm.word_similarity_threshold', %s, true)` | 6 | 2.5 | 1.0 |

`EXPLAIN (ANALYZE, BUFFERS)` of the slowest statement:

```
Limit  (cost=7914.29..7914.34 rows=20 width=16) (actual rows=20 loops=1)
  Buffers: shared hit=670988 read=58927
  CTE qv
    ->  Result  (cost=0.00..0.01 rows=1 width=32) (actual rows=1 loops=1)
  ->  Sort  (cost=7914.28..7914.34 rows=23 width=16) (actual rows=20 loops=1)
        Sort Key: (max(direct.s)) DESC, direct.canonical_id
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=670988 read=58927
        ->  GroupAggregate  (cost=7912.21..7913.76 rows=23 width=16) (actual rows=20 loops=1)
              Group Key: direct.canonical_id
              Buffers: shared hit=670985 read=58927
              ->  Merge Append  (cost=7912.21..7913.41 rows=23 width=16) (actual rows=24 loops=1)
                    Sort Key: direct.canonical_id
                    Buffers: shared hit=670985 read=58927
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
                    ->  GroupAggregate  (cost=7878.91..7879.87 rows=16 width=16) (actual rows=4 loops=1)
                          Group Key: ic.canonical_id
                          Filter: (max(n.s) >= '0.25'::double precision)
                          Buffers: shared hit=669486 read=58745
                          ->  Sort  (cost=7878.91..7879.03 rows=48 width=16) (actual rows=14 loops=1)
                                Sort Key: ic.canonical_id
                                Sort Method: quicksort  Memory: 25kB
                                Buffers: shared hit=669486 read=58745
                                ->  Hash Join  (cost=6897.20..7877.57 rows=48 width=16) (actual rows=14 loops=1)
                                      Hash Cond: (ic.item_id = n.item_id)
                                      Buffers: shared hit=669486 read=58745
                                      ->  Bitmap Heap Scan on item_canonical ic  (cost=451.36..1430.79 rows=121 width=16) (actual rows=3055 loops=1)
                                            Recheck Cond: (flex_level = ANY ('{exact,any_brand}'::text[]))
                                            Filter: ((NOT human_rejected) AND (NOT needs_review))
                                            Rows Removed by Filter: 5539
                                            Heap Blocks: exact=1325
                                            Buffers: shared hit=1 read=1345
                                            ->  Bitmap Index Scan on item_canonical_canonical_idx  (cost=0.00..451.33 rows=484 width=0) (actual rows=8594 loops=1)
                                                  Index Cond: (flex_level = ANY ('{exact,any_brand}'::text[]))
                                                  Buffers: shared read=21
                                      ->  Hash  (cost=6444.84..6444.84 rows=80 width=16) (actual rows=80 loops=1)
                                            Buckets: 1024  Batches: 1  Memory Usage: 12kB
                                            Buffers: shared hit=669485 read=57400
                                            ->  Subquery Scan on n  (cost=6443.84..6444.84 rows=80 width=16) (actual rows=80 loops=1)
                                                  Buffers: shared hit=669485 read=57400
                                                  ->  Limit  (cost=6443.84..6444.04 rows=80 width=24) (actual rows=80 loops=1)
                                                        Buffers: shared hit=669485 read=57400
                                                        ->  Sort  (cost=6443.84..6653.27 rows=83769 width=24) (actual rows=80 loops=1)
                                                              Sort Key: ((e.embedding <=> qv_1.v))
                                                              Sort Method: top-N heapsort  Memory: 34kB
                                                              Buffers: shared hit=669485 read=57400
                                                              ->  Nested Loop  (cost=0.00..3377.09 rows=83769 width=24) (actual rows=83769 loops=1)
                                                                    Buffers: shared hit=669485 read=57400
                                                                    ->  CTE Scan on qv qv_1  (cost=0.00..0.02 rows=1 width=32) (actual rows=1 loops=1)
                                                                    ->  Seq Scan on item_embeddings e  (cost=0.00..1911.11 rows=83769 width=26) (actual rows=83769 loops=1)
                                                                          Filter: (model = 'hash-ngram-2-3-4-v1'::text)
                                                                          Buffers: shared read=864
Planning:
  Buffers: shared hit=412 read=60
Planning Time: 1.837 ms
Execution Time: 706.844 ms
```

### /parse-list, /compare and /optimize (production semantics)

Locations: Holon (8 priced stores, 5 chains within 5 km); Jerusalem centre (8 priced stores, 5 chains within 5 km); Petah Tikva (6 priced stores, 4 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 4078.6 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 11486.2 |
| large (32 lines) | 33 | 33 | 5 | 0 | 21919.7 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Holon | hand: small (6 lines) | 6 | 8 | 0 | 10.8 | 9.8 | 16.4 | 55 | single: רמי לוי חולון | -4.17 / -4.17 |
| Holon | hand: weekly (17 lines) | 17 | 8 | 0 | 14.3 | 2.3 | 2.5 | - | - | - / - |
| Holon | hand: large (32 lines) | 33 | 8 | 0 | 18.3 | 2.8 | 2.8 | - | - | - / - |
| Holon | drawn: 5 | 5 | 8 | 0 | 9.9 | 2.8 | 2.8 | - | - | - / - |
| Holon | drawn: 10 | 10 | 8 | 0 | 11.5 | 2.7 | 2.5 | - | - | - / - |
| Holon | drawn: 20 | 20 | 8 | 0 | 17 | 3.3 | 3.3 | - | - | - / - |
| Holon | drawn: 40 | 40 | 8 | 0 | 25 | 2.8 | 2.7 | - | - | - / - |
| Jerusalem centre | hand: small (6 lines) | 6 | 8 | 0 | 9.1 | 2.2 | 2.3 | - | - | - / - |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 8 | 0 | 12.7 | 2.5 | 2.6 | - | - | - / - |
| Jerusalem centre | hand: large (32 lines) | 33 | 8 | 0 | 17.2 | 2.3 | 2.3 | - | - | - / - |
| Jerusalem centre | drawn: 5 | 5 | 8 | 5 | 9.8 | 2.7 | 2.6 | - | - | - / - |
| Jerusalem centre | drawn: 10 | 10 | 8 | 0 | 11.1 | 2.1 | 2.3 | - | - | - / - |
| Jerusalem centre | drawn: 20 | 20 | - | - | 2.7 | - | - | - | - | - / - |
| Jerusalem centre | drawn: 40 | 40 | - | - | 3.1 | - | - | - | - | - / - |
| Petah Tikva | hand: small (6 lines) | 6 | - | - | 2.7 | - | - | - | - | - / - |
| Petah Tikva | hand: weekly (17 lines) | 17 | - | - | 2.9 | - | - | - | - | - / - |
| Petah Tikva | hand: large (32 lines) | 33 | - | - | 2.7 | - | - | - | - | - / - |
| Petah Tikva | drawn: 5 | 5 | - | - | 2.7 | - | - | - | - | - / - |
| Petah Tikva | drawn: 10 | 10 | - | - | 2.9 | - | - | - | - | - / - |
| Petah Tikva | drawn: 20 | 20 | - | - | 3.1 | - | - | - | - | - / - |
| Petah Tikva | drawn: 40 | 40 | - | - | 2.9 | - | - | - | - | - / - |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 9.1 | 6.0 | 9.3 |
| hand: weekly (17 lines) | 12.7 | 2.4 | 2.5 |
| hand: large (32 lines) | 17.2 | 2.5 | 2.5 |
| drawn: 5 | 9.8 | 2.8 | 2.7 |
| drawn: 10 | 11.1 | 2.4 | 2.4 |
| drawn: 20 | 3.1 | 3.3 | 3.3 |
| drawn: 40 | 3.1 | 2.8 | 2.7 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Holon | hand: small (6 lines) | 9.7 | 15.3 | - | - | -4.17 / -4.17 |
| Holon | hand: weekly (17 lines) | 2.8 | 2.7 | - | - | - / - |
| Holon | hand: large (32 lines) | 2.9 | 2.7 | - | - | - / - |
| Holon | drawn: 5 | 2.9 | 2.7 | - | - | - / - |
| Holon | drawn: 10 | 2.5 | 2.2 | - | - | - / - |
| Holon | drawn: 20 | 3.7 | 3.2 | - | - | - / - |
| Holon | drawn: 40 | 3.1 | 2.7 | - | - | - / - |
| Jerusalem centre | hand: small (6 lines) | 2.6 | 2.5 | - | - | - / - |
| Jerusalem centre | hand: weekly (17 lines) | 3.2 | 2.4 | - | - | - / - |
| Jerusalem centre | hand: large (32 lines) | 2.4 | 2.5 | - | - | - / - |
| Jerusalem centre | drawn: 5 | 2.9 | 2.7 | - | - | - / - |
| Jerusalem centre | drawn: 10 | 3 | 2.5 | - | - | - / - |

### /parse-list, /compare and /optimize (stress: unreviewed mappings included, performance only)

Locations: Holon (8 priced stores, 5 chains within 5 km); Jerusalem centre (8 priced stores, 5 chains within 5 km); Petah Tikva (6 priced stores, 4 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 4005.1 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 11158.2 |
| large (32 lines) | 33 | 33 | 5 | 0 | 21545.9 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Holon | hand: small (6 lines) | 6 | - | - | 3.1 | - | - | - | - | - / - |
| Holon | hand: weekly (17 lines) | 17 | - | - | 2.6 | - | - | - | - | - / - |
| Holon | hand: large (32 lines) | 33 | - | - | 2.9 | - | - | - | - | - / - |
| Holon | drawn: 5 | 5 | - | - | 3.2 | - | - | - | - | - / - |
| Holon | drawn: 10 | 10 | - | - | 4.1 | - | - | - | - | - / - |
| Holon | drawn: 20 | 20 | - | - | 3 | - | - | - | - | - / - |
| Holon | drawn: 40 | 40 | - | - | 3 | - | - | - | - | - / - |
| Jerusalem centre | hand: small (6 lines) | 6 | - | - | 2.7 | - | - | - | - | - / - |
| Jerusalem centre | hand: weekly (17 lines) | 17 | - | - | 2.3 | - | - | - | - | - / - |
| Jerusalem centre | hand: large (32 lines) | 33 | - | - | 2.6 | - | - | - | - | - / - |
| Jerusalem centre | drawn: 5 | 5 | - | - | 2.3 | - | - | - | - | - / - |
| Jerusalem centre | drawn: 10 | 10 | - | - | 2.5 | - | - | - | - | - / - |
| Jerusalem centre | drawn: 20 | 20 | - | - | 2.2 | - | - | - | - | - / - |
| Jerusalem centre | drawn: 40 | 40 | - | - | 2.3 | - | - | - | - | - / - |
| Petah Tikva | hand: small (6 lines) | 6 | - | - | 2.6 | - | - | - | - | - / - |
| Petah Tikva | hand: weekly (17 lines) | 17 | - | - | 2.2 | - | - | - | - | - / - |
| Petah Tikva | hand: large (32 lines) | 33 | - | - | 2.5 | - | - | - | - | - / - |
| Petah Tikva | drawn: 5 | 5 | - | - | 2.2 | - | - | - | - | - / - |
| Petah Tikva | drawn: 10 | 10 | - | - | 2.3 | - | - | - | - | - / - |
| Petah Tikva | drawn: 20 | 20 | - | - | 2.6 | - | - | - | - | - / - |
| Petah Tikva | drawn: 40 | 40 | - | - | 2.2 | - | - | - | - | - / - |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 2.7 | - | - |
| hand: weekly (17 lines) | 2.3 | - | - |
| hand: large (32 lines) | 2.6 | - | - |
| drawn: 5 | 2.3 | - | - |
| drawn: 10 | 2.5 | - | - |
| drawn: 20 | 2.6 | - | - |
| drawn: 40 | 2.3 | - | - |

### Basket index on the real day (#44, dry run, production semantics)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `missing_items` קרפור (מגה) has no price for 11 basket items (yellow-cheese-sliced-28, butter, hummus-plain, tomato, cucumber, potato, banana, pita, pasta-spaghetti, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` קרפור (מגה): 2 lines use estimated weighed-goods prices
- warning: `missing_items` קינג סטור has no price for 17 basket items (cottage-5, yellow-cheese-sliced-28, butter, eggs-l, chicken-breast-fresh, hummus-plain, tomato, cucumber, potato, banana, bread-standard, pita, rice-persian, pasta-spaghetti, tuna-in-oil, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` קינג סטור: 1 lines use estimated weighed-goods prices
- warning: `missing_items` רמי לוי has no price for 7 basket items (eggs-l, hummus-plain, cucumber, potato, banana, pasta-spaghetti, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` רמי לוי: 3 lines use estimated weighed-goods prices
- warning: `missing_items` אושר עד has no price for 17 basket items (milk-fresh-3, white-cheese-5, yellow-cheese-sliced-28, yogurt-plain-3, eggs-l, chicken-breast-fresh, hummus-plain, tomato, cucumber, onion, banana, pita, pasta-spaghetti, sugar-white, mineral-water, bamba, chocolate-milk); it is listed but not ranked
- warning: `missing_items` יוחננוף has no price for 11 basket items (yellow-cheese-sliced-28, butter, eggs-l, hummus-plain, cucumber, potato, banana, pita, pasta-spaghetti, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` יוחננוף: 3 lines use estimated weighed-goods prices
- warning: `missing_items` טיב טעם has no price for 12 basket items (milk-fresh-3, yellow-cheese-sliced-28, yogurt-plain-3, butter, eggs-l, hummus-plain, pita, pasta-spaghetti, tuna-in-oil, mineral-water, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` טיב טעם: 6 lines use estimated weighed-goods prices
- error: `too_few_chains` only 0 chain(s) price the whole basket; at least 2 needed

Basket of 25 lines; price date 2026-10-22T05:00:18Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| קרפור (מגה) | - | 14 | 11 | 7 | no |
| קינג סטור | - | 8 | 17 | 2 | no |
| רמי לוי | - | 18 | 7 | 7 | no |
| אושר עד | - | 8 | 17 | 5 | no |
| יוחננוף | - | 14 | 11 | 4 | no |
| טיב טעם | - | 13 | 12 | 5 | no |

### Basket index on the real day (#44, dry run, stress)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `estimated_items` קרפור (מגה): 6 lines use estimated weighed-goods prices
- warning: `missing_items` קינג סטור has no price for 3 basket items (eggs-l, bread-standard, tuna-in-oil); it is listed but not ranked
- warning: `estimated_items` קינג סטור: 6 lines use estimated weighed-goods prices
- warning: `missing_items` רמי לוי has no price for 1 basket items (eggs-l); it is listed but not ranked
- warning: `estimated_items` רמי לוי: 3 lines use estimated weighed-goods prices
- warning: `missing_items` אושר עד has no price for 5 basket items (eggs-l, chicken-breast-fresh, onion, banana, pita); it is listed but not ranked
- warning: `missing_items` יוחננוף has no price for 1 basket items (eggs-l); it is listed but not ranked
- warning: `estimated_items` יוחננוף: 6 lines use estimated weighed-goods prices
- warning: `missing_items` טיב טעם has no price for 1 basket items (eggs-l); it is listed but not ranked
- warning: `estimated_items` טיב טעם: 6 lines use estimated weighed-goods prices
- error: `too_few_chains` only 1 chain(s) price the whole basket; at least 2 needed

Basket of 25 lines; price date 2026-10-22T05:00:18Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| קרפור (מגה) | 339.95 | 25 | 0 | 7 | yes |
| קינג סטור | - | 22 | 3 | 2 | no |
| רמי לוי | - | 24 | 1 | 7 | no |
| אושר עד | - | 20 | 5 | 5 | no |
| יוחננוף | - | 24 | 1 | 4 | no |
| טיב טעם | - | 24 | 1 | 5 | no |

### Basket lines that no chain prices: the real items that could have been them

Items whose names mention the product, with the attributes extraction gave them, the mapping they got and the rule judge's own reason (re-run for this report, nothing written). The `hint` columns are a reading aid of this script, not the catalog's rules.

#### `chocolate-milk`: 72 listed of 3158 name hits (0 skipped as not the food itself)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| mega | VANINI שוקולד מריר 7 | ? / ? | chocolate_bar | 100 g | chocolate-dark-bar any_brand 1.00 | accept: chocolate-dark-bar (שוקולד מריר): similarity 0.75 \| critical match product_type=chocolate_bar, flavor=dark \| level any_brand, confidence 1.00 \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.44 \| critical mismatch f |
| mega | שוקו-גראני ביסקוויט | ? / ? | tea_biscuits | 200 g | tea-biscuits any_brand 0.68 review | review: tea-biscuits (ביסקוויטים (פתי בר)): similarity 0.36 \| critical match product_type=tea_biscuits \| level any_brand, confidence 0.68 \| vetoed: bisli-grill (ביסלי גריל): similarity 0.27 \| critical mismatch product_type tea_bis |
| mega | עוגיות בארקט שוקולד | ? / ? | - | 240 g | - | every candidate vetoed \| vetoed: chocolate-spread (ממרח שוקולד): similarity 0.42 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'ממרח שוקולד' \| critical unknown product_type ; chocolate-milk-bar (שוקולד חל |
| mega | טארטלט שוקולד ואגוזי | ? / ? | chocolate_bar | 150 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.37 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.34 \| criti |
| mega | עוגיות שוקוצ'יפס  50 | ? / ? | - | 500 g | - | every candidate vetoed \| vetoed: french-fries-frozen (צ'יפס קפוא): similarity 0.31 \| critical mismatch name has 'עוגיות' (a derived product), canonical is "צ'יפס קפוא" \| critical unknown product_type ; chicken-thigh-boneless-froze |
| mega | עוגיות שוקוצ'יפס לבן | ? / ? | - | 500 g | - | every candidate vetoed \| vetoed: sugar-white (סוכר לבן): similarity 0.34 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'סוכר לבן' \| critical unknown product_type ; flour-white (קמח לבן): similarity 0.33 \| |
| mega | שוקו תנובה 2.7% שומן | ? / ? | chocolate_milk | -  | chocolate-milk any_brand 0.82 review | review: chocolate-milk (שוקו): similarity 0.52 \| critical match product_type=chocolate_milk \| level any_brand, confidence 0.82 \| vetoed: dessert-chocolate (מעדן חלב שוקולד): similarity 0.19 \| critical mismatch product_type chocola |
| mega | קליק טבלת שוקו קראנץ | ? / ? | - | 85 g | - | rejected (confidence 0.24 < 0.6): chocolate-milk-bar (שוקולד חלב): similarity 0.20 \| critical unknown product_type, flavor \| soft differs pack_size 85 vs 100 g \| ambiguous with pudding-chocolate-cream \| level close, confidence 0.2 |
| mega | בראוניז שוקולד ללא ג | ? / ? | chocolate_bar | 150 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.46 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.43 \| criti |
| mega | שוקו רייס -פתיתי אור | ? / ? | chocolate_milk | 375 g | - | every candidate vetoed \| vetoed: safed-cheese-5 (גבינה צפתית 5%): similarity 0.17 \| critical mismatch product_type chocolate_milk vs safed_cheese \| critical unknown fat_pct ; dessert-chocolate (מעדן חלב שוקולד): similarity 0.16 \|  |
| mega | שוקולד בננית 150 גרם | ? / ? | chocolate_bar | 150 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.40 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.39 \| criti |
| mega | בראוניז קרמל שוקולד | ? / ? | chocolate_bar | 200 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.47 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.44 \| criti |
| king_store | חטיף שוקולד 40 ג'טעמי | ? / ? | chocolate_bar | 40 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.46 \| critical mismatch flavor chocolate vs milk; name has 'חטיף' (a derived product), canonical is 'שוקולד חלב' \| critical match product_type=chocolate |
| king_store | מעדן שוקולד מהדרין 135 ג'  מילקי | ? / ? | pudding_with_cream | 135 g | pudding-chocolate-cream close 0.78 review | review: pudding-chocolate-cream (מעדן שוקולד עם קצפת): similarity 0.47 \| critical match product_type=pudding_with_cream, flavor=chocolate \| soft differs pack_size 135 vs 170 g \| level close, confidence 0.77 \| vetoed: dessert-choco |
| king_store | מעדן חלב בטעם שוקולד 125 ג' דני | ? / ? | dairy_dessert | 125 g | dessert-chocolate any_brand 0.98 | accept: dessert-chocolate (מעדן חלב שוקולד): similarity 0.73 \| critical match product_type=dairy_dessert, flavor=chocolate \| level any_brand, confidence 0.98 \| vetoed: pudding-chocolate-cream (מעדן שוקולד עם קצפת): similarity 0.50 |
| king_store | ממרח שוקולד 750 ג' נוטלה | ? / ? | chocolate_spread | 750 g | chocolate-spread close 0.93 | accept: chocolate-spread (ממרח שוקולד): similarity 0.66 \| critical match product_type=chocolate_spread \| soft differs pack_size 750 vs 400 g \| level close, confidence 0.93 \| vetoed: granola (גרנולה): similarity 0.14 \| critical mis |
| king_store | קינדר שוקולד 50 ג' | ? / ? | chocolate_bar | 50 g | - | every candidate vetoed \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.48 \| critical mismatch flavor chocolate vs dark \| critical match product_type=chocolate_bar ; chocolate-milk-bar (שוקולד חלב): similarity 0.46 \| criti |
| king_store | קינדר שוקולד 100 ג' | ? / ? | chocolate_bar | 100 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.47 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.47 \| criti |
| king_store | חטיף שיבולת שועל שוקולד מריר קראנצי 210ג' ניטשר ואלי | ? / ? | rolled_oats | 210 g | - | every candidate vetoed \| vetoed: rolled-oats (שיבולת שועל): similarity 0.49 \| critical mismatch name has 'חטיף' (a derived product), canonical is 'שיבולת שועל' \| critical match product_type=rolled_oats ; chocolate-spread (ממרח שוק |
| king_store | עוגיות שוקולד ציפס מובחרות 225 ג' | ? / ? | - | 225 g | - | every candidate vetoed \| vetoed: chocolate-spread (ממרח שוקולד): similarity 0.36 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'ממרח שוקולד' \| critical unknown product_type ; chocolate-milk-bar (שוקולד חל |
| king_store | עוגיות עם סוכריות שוקולד חלב צבעונית 150 ג' מרבה | ? / ? | - | 150 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.40 \| critical mismatch flavor chocolate vs milk; name has 'סוכריות' (a derived product), canonical is 'שוקולד חלב' \| critical unknown product_type ; de |
| king_store | שוקולד  חלב שברי אגוזים 100 ג' ריטר | ? / ? | chocolate_bar | 100 g | chocolate-milk-bar any_brand 0.86 review | review: chocolate-milk-bar (שוקולד חלב): similarity 0.57 \| critical match product_type=chocolate_bar, flavor=milk \| level any_brand, confidence 0.86 \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.38 \| critical mismatch f |
| king_store | סוכריות שוקולדן 325ג' storck | ? / ? | - | 325 g | - | rejected (confidence 0.24 < 0.6): sugar-white (סוכר לבן): similarity 0.19 \| critical unknown product_type \| soft differs pack_size 325 vs 1000 g \| ambiguous with sugar-brown \| level close, confidence 0.24 \| vetoed: chocolate-dark- |
| king_store | חטיף שוקולד חלב  140 ג' פיקאפ | ? / ? | chocolate_bar | 140 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.62 \| critical mismatch name has 'חטיף' (a derived product), canonical is 'שוקולד חלב' \| critical match product_type=chocolate_bar, flavor=milk ; chocol |
| ramilevy | קליק טבלת שוקו קראנץ | ? / ? | - | -  | - | rejected (confidence 0.43 < 0.6): chocolate-milk (שוקו): similarity 0.48 \| critical unknown product_type \| level any_brand, confidence 0.43 |
| ramilevy | פיצי שוקו דגני בוקר | ? / ? | chocolate_milk | -  | - | every candidate vetoed \| vetoed: chocolate-milk (שוקו): similarity 0.52 \| critical mismatch name has 'דגני' (a derived product), canonical is 'שוקו' \| critical match product_type=chocolate_milk ; dessert-chocolate (מעדן חלב שוקולד |
| ramilevy | קליק שקית שוקו מיקס | ? / ? | chocolate_milk | -  | chocolate-milk any_brand 0.79 review | review: chocolate-milk (שוקו): similarity 0.49 \| critical match product_type=chocolate_milk \| level any_brand, confidence 0.79 \| vetoed: pudding-chocolate-cream (מעדן שוקולד עם קצפת): similarity 0.17 \| critical mismatch product_ty |
| ramilevy | שוקולד חלב בטעם מילק | ? / ? | chocolate_bar | -  | chocolate-milk-bar any_brand 0.97 | accept: chocolate-milk-bar (שוקולד חלב): similarity 0.71 \| critical match product_type=chocolate_bar, flavor=milk \| level any_brand, confidence 0.97 \| vetoed: wafers-chocolate (ופלים בטעם שוקולד): similarity 0.59 \| critical mismat |
| ramilevy | ממרח בטעם שוקולד בתו | ? / ? | - | -  | chocolate-spread any_brand 0.64 review | review: chocolate-spread (ממרח שוקולד): similarity 0.75 \| critical unknown product_type \| level any_brand, confidence 0.64 \| vetoed: wafers-chocolate (ופלים בטעם שוקולד): similarity 0.58 \| critical mismatch the canonical's words c |
| ramilevy | שוקולד מריר מעולה 70 | ? / ? | chocolate_bar | -  | chocolate-dark-bar any_brand 1.00 | accept: chocolate-dark-bar (שוקולד מריר): similarity 0.74 \| critical match product_type=chocolate_bar, flavor=dark \| level any_brand, confidence 1.00 \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.42 \| critical mismatch f |

#### `hummus-plain`: 72 listed of 465 name hits (0 skipped as not the food itself)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| mega | גרגירי חומוס מושרים | ? / ? | chickpeas | 700 g | chickpeas-canned close 0.69 review | review: chickpeas-canned (גרגרי חומוס בשימורים): similarity 0.59 \| critical match product_type=chickpeas \| critical unknown state \| soft differs pack_size 700 vs 400 g \| level close, confidence 0.69 \| vetoed: hummus-plain (חומוס ( |
| mega | האופה - גרגירי חומוס | ? / ? | - | 550 g | - | rejected (confidence 0.42 < 0.6): chickpeas-dry (גרגרי חומוס יבשים): similarity 0.47 \| critical unknown product_type, state \| soft differs pack_size 550 vs 1000 g \| ambiguous with chickpeas-canned \| level close, confidence 0.42 |
| mega | אחלה חומוס ישראלי 60 | ? / ? | hummus_salad | 600 g | - | rejected (confidence 0.55 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.42 \| critical match product_type=hummus_salad \| critical unknown flavor \| soft differs pack_size 600 vs 400 g \| level close, confidence 0.55 \| vetoed: chic |
| mega | חומוס החומוסייה של א | ? / ? | hummus_salad | 400 g | hummus-plain any_brand 0.64 review | review: hummus-plain (חומוס (סלט)): similarity 0.53 \| critical match product_type=hummus_salad \| critical unknown flavor \| level any_brand, confidence 0.64 \| vetoed: matbucha (מטבוחה): similarity 0.04 \| critical mismatch product_t |
| mega | חומוס שלם יכין 550 ג | ? / ? | hummus_salad | 550 g | - | rejected (confidence 0.54 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.40 \| critical match product_type=hummus_salad \| critical unknown flavor \| soft differs pack_size 550 vs 400 g \| level close, confidence 0.54 \| vetoed: matb |
| mega | גרגרי חומוס מסעדות י | ? / ? | chickpeas | 550 g | chickpeas-dry close 0.75 review | review: chickpeas-dry (גרגרי חומוס יבשים): similarity 0.66 \| critical match product_type=chickpeas \| critical unknown state \| soft differs pack_size 550 vs 1000 g \| level close, confidence 0.75 \| vetoed: hummus-plain (חומוס (סלט)) |
| mega | גרגירי חומוס שלמים ב | ? / ? | chickpeas | 800 g | chickpeas-canned close 0.63 review | review: chickpeas-canned (גרגרי חומוס בשימורים): similarity 0.51 \| critical match product_type=chickpeas \| critical unknown state \| soft differs pack_size 800 vs 400 g \| ambiguous with chickpeas-dry \| level close, confidence 0.63  |
| mega | חומוס גלילי אחלה 400 | ? / ? | hummus_salad | 400 g | - | rejected (confidence 0.54 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.39 \| critical match product_type=hummus_salad \| critical unknown flavor \| level any_brand, confidence 0.54 \| vetoed: eggplant-mayo-salad (סלט חצילים במיונז |
| mega | חומוס גלילי אחלה 600 | ? / ? | hummus_salad | 600 g | - | rejected (confidence 0.55 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.41 \| critical match product_type=hummus_salad \| critical unknown flavor \| soft differs pack_size 600 vs 400 g \| level close, confidence 0.55 \| vetoed: eggp |
| mega | סוגת חומוס 1 ק"ג | ? / ? | hummus_salad | 1000 g | hummus-plain close 0.77 review | review: hummus-plain (חומוס (סלט)): similarity 0.46 \| critical match product_type=hummus_salad, flavor=plain \| soft differs pack_size 1000 vs 400 g \| level close, confidence 0.77 \| vetoed: salami (נקניק סלמי): similarity 0.11 \| cr |
| mega | חומוס 500 גרם | ? / ? | hummus_salad | 500 g | hummus-plain close 0.80 review | review: hummus-plain (חומוס (סלט)): similarity 0.50 \| critical match product_type=hummus_salad, flavor=plain \| soft differs pack_size 500 vs 400 g \| level close, confidence 0.80 \| vetoed: matbucha (מטבוחה): similarity 0.03 \| criti |
| mega | חומוס ענק 1 ק'ג | ? / ? | hummus_salad | -  | hummus-plain any_brand 0.75 review | review: hummus-plain (חומוס (סלט)): similarity 0.44 \| critical match product_type=hummus_salad, flavor=plain \| level any_brand, confidence 0.75 \| vetoed: salami (נקניק סלמי): similarity 0.13 \| critical mismatch product_type hummus |
| king_store | קטניות חומוס 800 ג' אלחסן | ? / ? | hummus_salad | 800 g | hummus-plain close 0.67 review | review: hummus-plain (חומוס (סלט)): similarity 0.34 \| critical match product_type=hummus_salad, flavor=plain \| soft differs pack_size 800 vs 400 g \| level close, confidence 0.67 \| vetoed: chicken-hot-dogs (נקניקיות עוף): similarit |
| king_store | חומוס שלם 550 ג' פרי זה | ? / ? | hummus_salad | 550 g | hummus-plain close 0.70 review | review: hummus-plain (חומוס (סלט)): similarity 0.38 \| critical match product_type=hummus_salad, flavor=plain \| soft differs pack_size 550 vs 400 g \| level close, confidence 0.70 \| vetoed: matbucha (מטבוחה): similarity 0.10 \| criti |
| king_store | גרגירי חומוס קפוא 800 ג' סנפרוסט | ? / ? | chickpeas | 800 g | - | every candidate vetoed \| vetoed: chickpeas-canned (גרגרי חומוס בשימורים): similarity 0.36 \| critical mismatch state frozen vs canned \| critical match product_type=chickpeas ; hummus-plain (חומוס (סלט)): similarity 0.36 \| critical  |
| king_store | חומוס שלם 550 ג' יכין | ? / ? | hummus_salad | 550 g | hummus-plain close 0.72 review | review: hummus-plain (חומוס (סלט)): similarity 0.40 \| critical match product_type=hummus_salad, flavor=plain \| soft differs pack_size 550 vs 400 g \| level close, confidence 0.72 \| vetoed: matbucha (מטבוחה): similarity 0.08 \| criti |
| king_store | חומוס שלם 550ג' תמי | ? / ? | hummus_salad | 550 g | hummus-plain close 0.74 review | review: hummus-plain (חומוס (סלט)): similarity 0.42 \| critical match product_type=hummus_salad, flavor=plain \| soft differs pack_size 550 vs 400 g \| level close, confidence 0.74 \| vetoed: salami (נקניק סלמי): similarity 0.06 \| cri |
| king_store | סלט חומוס אחלה 1 ק"ג | ? / ? | hummus_salad | 1000 g | hummus-plain close 0.93 | accept: hummus-plain (חומוס (סלט)): similarity 0.67 \| critical match product_type=hummus_salad, flavor=plain \| soft differs pack_size 1000 vs 400 g \| level close, confidence 0.93 \| vetoed: tahini-salad (סלט טחינה): similarity 0.29 |
| king_store | חומוס אסלי 650 ג' אלבוסתאן | ? / ? | hummus_salad | 650 g | hummus-plain close 0.73 review | review: hummus-plain (חומוס (סלט)): similarity 0.41 \| critical match product_type=hummus_salad, flavor=plain \| soft differs pack_size 650 vs 400 g \| level close, confidence 0.73 \| vetoed: matbucha (מטבוחה): similarity 0.09 \| criti |
| king_store | חומוס 850 ג' צבר | ? / ? | hummus_salad | 850 g | hummus-plain close 0.78 review | review: hummus-plain (חומוס (סלט)): similarity 0.48 \| critical match product_type=hummus_salad, flavor=plain \| soft differs pack_size 850 vs 400 g \| level close, confidence 0.78 \| vetoed: matbucha (מטבוחה): similarity 0.11 \| criti |
| king_store | חומוס 750 ג' אחלה | ? / ? | hummus_salad | 750 g | hummus-plain close 0.79 review | review: hummus-plain (חומוס (סלט)): similarity 0.49 \| critical match product_type=hummus_salad, flavor=plain \| soft differs pack_size 750 vs 400 g \| level close, confidence 0.79 \| vetoed: matbucha (מטבוחה): similarity 0.11 \| criti |
| king_store | חומוס 900 ג' | ? / ? | hummus_salad | 900 g | hummus-plain close 0.82 review | review: hummus-plain (חומוס (סלט)): similarity 0.53 \| critical match product_type=hummus_salad, flavor=plain \| soft differs pack_size 900 vs 400 g \| level close, confidence 0.82 \| vetoed: matbucha (מטבוחה): similarity 0.10 \| criti |
| king_store | חומוס טחינה אחלה 400 ג' | ? / ? | hummus_salad | 400 g | hummus-plain any_brand 0.70 review | review: hummus-plain (חומוס (סלט)): similarity 0.38 \| critical match product_type=hummus_salad, flavor=plain \| level any_brand, confidence 0.70 \| vetoed: tahini-salad (סלט טחינה): similarity 0.38 \| critical mismatch product_type h |
| king_store | חומוס צנובר 400 ג' אחלה | ? / ? | hummus_salad | 400 g | - | every candidate vetoed \| vetoed: hummus-plain (חומוס (סלט)): similarity 0.37 \| critical mismatch flavor pine_nut vs plain \| critical match product_type=hummus_salad ; matbucha (מטבוחה): similarity 0.10 \| critical mismatch product_ |
| ramilevy | גרגירי חומוס 800 גרם | ? / ? | chickpeas | 800 g | chickpeas-dry close 0.63 review | review: chickpeas-dry (גרגרי חומוס יבשים): similarity 0.51 \| critical match product_type=chickpeas \| critical unknown state \| soft differs pack_size 800 vs 1000 g \| ambiguous with chickpeas-canned \| level close, confidence 0.63 \|  |
| ramilevy | חומוס ישראלי 600 גר | ? / ? | hummus_salad | 600 g | - | rejected (confidence 0.56 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.42 \| critical match product_type=hummus_salad \| critical unknown flavor \| soft differs pack_size 600 vs 400 g \| level close, confidence 0.56 \| vetoed: chic |
| ramilevy | חומוס מועשר בחלבון 1 | ? / ? | hummus_salad | -  | - | rejected (confidence 0.55 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.41 \| critical match product_type=hummus_salad \| critical unknown flavor \| level any_brand, confidence 0.55 \| vetoed: matbucha (מטבוחה): similarity 0.08 \| c |
| ramilevy | חומוס מסבחה ירוק 250 | ? / ? | hummus_salad | -  | - | rejected (confidence 0.53 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.38 \| critical match product_type=hummus_salad \| critical unknown flavor \| level any_brand, confidence 0.53 \| vetoed: matbucha (מטבוחה): similarity 0.13 \| c |
| ramilevy | חומוס עם חציל פיקנטי | ? / ? | hummus_salad | -  | - | every candidate vetoed \| vetoed: hummus-plain (חומוס (סלט)): similarity 0.41 \| critical mismatch flavor other vs plain \| critical match product_type=hummus_salad ; eggplant-mayo-salad (סלט חצילים במיונז): similarity 0.13 \| critica |
| ramilevy | גרגירי חומוס קפואים | ? / ? | chickpeas | -  | - | every candidate vetoed \| vetoed: chickpeas-dry (גרגרי חומוס יבשים): similarity 0.52 \| critical mismatch state frozen vs dry \| critical match product_type=chickpeas ; chickpeas-canned (גרגרי חומוס בשימורים): similarity 0.51 \| criti |

#### `pasta-spaghetti`: 62 listed of 125 name hits (0 skipped as not the food itself)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| mega | ספגטי 500 גרם - קרפו | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.85 review | review: pasta-spaghetti (ספגטי): similarity 0.57 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.85 \| vetoed: turmeric (כורכום): similarity 0.13 \| critical mismatch product_type pasta_spaghetti vs tur |
| mega | פסטה ספגטי פרפקטו 50 | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.83 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.83 \| vetoed: pasta-penne (פסטה פנה): similarity 0.47 \| critical mismatch product_type pasta_spaghetti v |
| mega | ספגטי אסם 500 גרם | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.85 review | review: pasta-spaghetti (ספגטי): similarity 0.56 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.85 \| vetoed: turmeric (כורכום): similarity 0.16 \| critical mismatch product_type pasta_spaghetti vs tur |
| mega | מנה חמה ספגטי בולונז | ? / ? | pasta_spaghetti | 65 g | pasta-spaghetti close 0.86 review | review: pasta-spaghetti (ספגטי): similarity 0.58 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 65 vs 500 g \| level close, confidence 0.86 \| vetoed: mayonnaise (מיונז): similarity 0.19 \| critical mismatch p |
| mega | ספגטי קפליני מס' 1 ב | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.84 \| vetoed: rice-basmati (אורז בסמטי): similarity 0.14 \| critical mismatch product_type pasta_spaghett |
| mega | ספגטי מס' 3 ברילה 50 | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.55 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.84 \| vetoed: granola (גרנולה): similarity 0.10 \| critical mismatch product_type pasta_spaghetti vs gran |
| mega | ספגטי בבטה מס' 13 בר | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.84 \| vetoed: rice-basmati (אורז בסמטי): similarity 0.14 \| critical mismatch product_type pasta_spaghett |
| mega | ספגטי בוקטיני מס' 9 | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.87 review | review: pasta-spaghetti (ספגטי): similarity 0.58 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.87 \| vetoed: rice-basmati (אורז בסמטי): similarity 0.18 \| critical mismatch product_type pasta_spaghett |
| mega | ספגטי מס' 7 ברילה 50 | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.55 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.84 \| vetoed: sweet-paprika (פפריקה מתוקה): similarity 0.12 \| critical mismatch product_type pasta_spagh |
| mega | ברילה ספגטי ללא גלוט | ? / ? | pasta_spaghetti | 400 g | pasta-spaghetti close 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 400 vs 500 g \| level close, confidence 0.84 \| vetoed: granola (גרנולה): similarity 0.13 \| critical mismatch pr |
| mega | פסטה ספגטי מספר 3 - | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.89 review | review: pasta-spaghetti (ספגטי): similarity 0.62 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.89 \| vetoed: pasta-penne (פסטה פנה): similarity 0.45 \| critical mismatch product_type pasta_spaghetti v |
| mega | פרפקטו פסטה ספגטי לל | ? / ? | pasta_spaghetti | 400 g | pasta-spaghetti close 0.83 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 400 vs 500 g \| level close, confidence 0.83 \| vetoed: pasta-penne (פסטה פנה): similarity 0.47 \| critical misma |
| king_store | פסטה ספגטי 500 ג' אסם | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.84 \| vetoed: pasta-penne (פסטה פנה): similarity 0.41 \| critical mismatch product_type pasta_spaghetti v |
| king_store | פרפקטו ספגטי 500 ג' אסם | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.80 review | review: pasta-spaghetti (ספגטי): similarity 0.50 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.80 \| vetoed: rice-basmati (אורז בסמטי): similarity 0.12 \| critical mismatch product_type pasta_spaghett |
| ramilevy | פסטה ספגטי 500 גר wb | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.85 review | review: pasta-spaghetti (ספגטי): similarity 0.56 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.85 \| vetoed: pasta-penne (פסטה פנה): similarity 0.42 \| critical mismatch product_type pasta_spaghetti v |
| ramilevy | ספגטי מחיטת כוסמין מ | ? / ? | pasta_spaghetti | -  | pasta-spaghetti any_brand 0.82 review | review: pasta-spaghetti (ספגטי): similarity 0.53 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.82 \| vetoed: rice-jasmine (אורז יסמין): similarity 0.18 \| critical mismatch product_type pasta_spaghett |
| ramilevy | רומו ספגטי ללא גלוטן | ? / ? | pasta_spaghetti | -  | pasta-spaghetti close 0.82 review | review: pasta-spaghetti (ספגטי): similarity 0.52 \| critical match product_type=pasta_spaghetti \| soft differs diet variant 'ללא גלוטן' \| level close, confidence 0.82 \| vetoed: chickpeas-dry (גרגרי חומוס יבשים): similarity 0.11 \| c |
| ramilevy | ספגטי לבן אורגני הרד | ? / ? | pasta_spaghetti | -  | pasta-spaghetti any_brand 0.83 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.83 \| vetoed: sugar-white (סוכר לבן): similarity 0.35 \| critical mismatch product_type pasta_spaghetti v |
| ramilevy | ספגטי 500גר רמילוי | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.88 review | review: pasta-spaghetti (ספגטי): similarity 0.60 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.88 \| vetoed: black-pepper (פלפל שחור): similarity 0.09 \| critical mismatch product_type pasta_spaghetti |
| ramilevy | פסטה איטלקית ספגטי 5 | ? / ? | pasta_spaghetti | -  | pasta-spaghetti any_brand 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.55 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.84 \| vetoed: pasta-penne (פסטה פנה): similarity 0.42 \| critical mismatch product_type pasta_spaghetti v |
| ramilevy | פליסיה ספגטי כוסמת א | ? / ? | pasta_spaghetti | -  | pasta-spaghetti any_brand 0.83 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.83 \| vetoed: black-pepper (פלפל שחור): similarity 0.16 \| critical mismatch product_type pasta_spaghetti |
| ramilevy | ספגטי ללא גלוטן 400 | ? / ? | pasta_spaghetti | -  | pasta-spaghetti close 0.83 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| soft differs diet variant 'ללא גלוטן' \| level close, confidence 0.83 \| vetoed: sugar-white (סוכר לבן): similarity 0.09 \| critical mis |
| ramilevy | ליגורי- ספגטי מספר 3 | ? / ? | pasta_spaghetti | -  | pasta-spaghetti any_brand 0.87 review | review: pasta-spaghetti (ספגטי): similarity 0.59 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.87 \| vetoed: breadcrumbs (פירורי לחם): similarity 0.19 \| critical mismatch product_type pasta_spaghetti |
| ramilevy | ברילה ספגטי מס 1 קפל | ? / ? | pasta_spaghetti | -  | pasta-spaghetti any_brand 0.83 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.83 \| vetoed: cornflakes (קורנפלקס): similarity 0.13 \| critical mismatch product_type pasta_spaghetti vs |
| ramilevy | ברילה ספגטיני מס 3 5 | ? / ? | - | -  | - | rejected (confidence 0.34 < 0.6): pasta-spaghetti (ספגטי): similarity 0.38 \| critical unknown product_type \| level any_brand, confidence 0.34 |
| ramilevy | ברילה ספגטי מס 5 500 | ? / ? | pasta_spaghetti | -  | pasta-spaghetti any_brand 0.82 review | review: pasta-spaghetti (ספגטי): similarity 0.53 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.82 \| vetoed: granola (גרנולה): similarity 0.10 \| critical mismatch product_type pasta_spaghetti vs gran |
| osherad | דלעת ספגטי | ? / ? | pasta_spaghetti | -  | - | no candidates in block pantry / kg |
| osherad | ספגטי טעמן 500 גרם | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.85 review | review: pasta-spaghetti (ספגטי): similarity 0.56 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.85 \| vetoed: chickpeas-dry (גרגרי חומוס יבשים): similarity 0.13 \| critical mismatch product_type pasta_ |
| osherad | ספגטי אסם 500 גרם | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.85 review | review: pasta-spaghetti (ספגטי): similarity 0.56 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.85 \| vetoed: turmeric (כורכום): similarity 0.16 \| critical mismatch product_type pasta_spaghetti vs tur |
| osherad | מנה חמה ספגטי בולונז | ? / ? | pasta_spaghetti | 65 g | pasta-spaghetti close 0.86 review | review: pasta-spaghetti (ספגטי): similarity 0.58 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 65 vs 500 g \| level close, confidence 0.86 \| vetoed: mayonnaise (מיונז): similarity 0.19 \| critical mismatch p |

### Failures and findings the run recorded (80)

- **ingest**: 4 Stores files are older than the stale-date gate's 36 h (osherad 49.8 h, ramilevy 52.8 h, tivtaam 52.8 h, yohananof 56.9 h); on the real clock the gate would quarantine them and no store of those chains would load (this run replayed the clock for them)
- **api**: /optimize heuristic Holon hand: weekly (17 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize milp Holon hand: weekly (17 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_heuristic Holon hand: weekly (17 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_milp Holon hand: weekly (17 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize heuristic Holon hand: large (32 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize milp Holon hand: large (32 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_heuristic Holon hand: large (32 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_milp Holon hand: large (32 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize heuristic Holon drawn: 5: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize milp Holon drawn: 5: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_heuristic Holon drawn: 5: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_milp Holon drawn: 5: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize heuristic Holon drawn: 10: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize milp Holon drawn: 10: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_heuristic Holon drawn: 10: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_milp Holon drawn: 10: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize heuristic Holon drawn: 20: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize milp Holon drawn: 20: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_heuristic Holon drawn: 20: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_milp Holon drawn: 20: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize heuristic Holon drawn: 40: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize milp Holon drawn: 40: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_heuristic Holon drawn: 40: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_milp Holon drawn: 40: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize heuristic Jerusalem centre hand: small (6 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize milp Jerusalem centre hand: small (6 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_heuristic Jerusalem centre hand: small (6 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_milp Jerusalem centre hand: small (6 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize heuristic Jerusalem centre hand: weekly (17 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize milp Jerusalem centre hand: weekly (17 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_heuristic Jerusalem centre hand: weekly (17 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_milp Jerusalem centre hand: weekly (17 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize heuristic Jerusalem centre hand: large (32 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize milp Jerusalem centre hand: large (32 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_heuristic Jerusalem centre hand: large (32 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_milp Jerusalem centre hand: large (32 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize heuristic Jerusalem centre drawn: 5: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize milp Jerusalem centre drawn: 5: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_heuristic Jerusalem centre drawn: 5: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_milp Jerusalem centre drawn: 5: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize heuristic Jerusalem centre drawn: 10: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize milp Jerusalem centre drawn: 10: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_heuristic Jerusalem centre drawn: 10: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /optimize relaxed_milp Jerusalem centre drawn: 10: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Jerusalem centre drawn: 20: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Jerusalem centre drawn: 40: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva hand: small (6 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva hand: weekly (17 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva hand: large (32 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva drawn: 5: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva drawn: 10: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva drawn: 20: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva drawn: 40: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /parse-list took over 2 s (production): {'small (6 lines)': 4078.6, 'weekly (17 lines)': 11486.2, 'large (32 lines)': 21919.7} ms
- **basket index**: chocolate-milk is priced at no chain (candidates in the report)
- **basket index**: hummus-plain is priced at no chain (candidates in the report)
- **basket index**: pasta-spaghetti is priced at no chain (candidates in the report)
- **api**: /compare Holon hand: small (6 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Holon hand: weekly (17 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Holon hand: large (32 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Holon drawn: 5: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Holon drawn: 10: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Holon drawn: 20: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Holon drawn: 40: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Jerusalem centre hand: small (6 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Jerusalem centre hand: weekly (17 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Jerusalem centre hand: large (32 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Jerusalem centre drawn: 5: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Jerusalem centre drawn: 10: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Jerusalem centre drawn: 20: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Jerusalem centre drawn: 40: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva hand: small (6 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva hand: weekly (17 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva hand: large (32 lines): HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva drawn: 5: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva drawn: 10: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva drawn: 20: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /compare Petah Tikva drawn: 40: HTTP 429 {"detail":"too many requests, try again shortly"}
- **api**: /parse-list took over 2 s (stress): {'small (6 lines)': 4005.1, 'weekly (17 lines)': 11158.2, 'large (32 lines)': 21545.9} ms

