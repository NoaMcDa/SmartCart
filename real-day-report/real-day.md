## One real day through the pipeline (dry run)

Mode `portal`, commit `8541a2999f97`, runner `GitHub Actions 1000005127` (4 CPUs, Python 3.12.3, Postgres 17.11), 2026-10-22T07:16:22+00:00 to 2026-10-22T07:47:57+00:00 UTC. Measurements on one real day with hand-made baskets; the prices are real, the baskets and locations are not a sample of anything. **Not publishable.**

### Stages

| stage | seconds | result |
|---|---|---|
| download: portal probe (one Stores and one PriceFull per chain) | 1068.83 | ok |
| migrate | 1.75 | 32 applied |
| ingest: Stores files (Scheduler, adapters, gates, loader, store coordinates) | 0.63 | 6 files |
| download: PriceFull and PromoFull of the stores nearest to city centres | 91.18 | 48 files, anchors: Jerusalem centre, Holon, Petah Tikva |
| ingest: PriceFull and PromoFull files (Scheduler, adapters, gates, loader) | 156.09 | 60 files |
| catalog: seed | 0.95 | ok |
| catalog: normalize | 7.82 | ok |
| catalog: extract (rule) | 63.89 | ok |
| catalog: embed (hash) | 255.05 | ok |
| catalog: judge (rule) | 151.38 | ok |
| precompute effective prices (production semantics: reviewed mappings only) | 1.33 | 6799 rows |
| API: parse-list, compare, optimize (production) | 41.71 | 21 basket runs at 3 locations |
| diagnostic: the vector query behind /parse-list and /search | 7.64 | [3.9, 1.0, 0.7] ms per query |
| basket index dry run (production semantics) | 0.35 | status draft |
| diagnostic: real items behind the basket lines no chain prices | 1.74 | butter 48 items, chocolate-milk 72 items, cottage-5 6 items, eggs-l 168 items, hummus-plain 72 items, milk-fresh-3 24 items, pasta-spaghetti 62 items, white-cheese-5 12 items, yellow-cheese-sliced-28 60 items, yogurt-plain-3 24 items |
| stress: mark the machine suggestions accepted (performance only) | 0.34 | 12907 mappings |
| precompute effective prices (stress: unreviewed mappings included) | 2.26 | 11084 rows |
| API: parse-list, compare, optimize (stress) | 40.44 | 21 basket runs at 3 locations |
| basket index dry run (stress) | 0.37 | status draft |

### Portals (the portal probe's own reachability and downloads)

| chain | reachable | login | Stores download | PriceFull download |
|---|---|---|---|---|
| king_store | BLOCKED? (403) | n/a | Stores7290058108879-000-20261022-051042.gz | PriceFull7290058108879-000-340-20261022-051042.gz |
| mega | OK (200) | n/a | Stores7290055700007-000-20261022-000100.xml | PriceFull7290055700007-001-002-20261022-051018.gz |
| osherad | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290103152017-000-20261020-080500.xml | PriceFull7290103152017-001-001-20261022-080018.gz |
| ramilevy | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290058140886-000-20261020-050500.xml | PriceFull7290058140886-001-001-20261022-001004.gz |
| shufersal | UNREACHABLE (0) | n/a | no: timed out after 300s | no: timed out after 300s |
| tivtaam | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290873255550-000-20261020-050500.xml | PriceFull7290873255550-000-002-20261022-004004.gz |
| yohananof | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290803800003-000-20261020-010000.xml | PriceFull7290803800003-000-001-20261022-004040.gz |

### Files, gates and rows per chain

| chain | kind | file | published (Israel) | age h | schema | gate result | rows | seconds |
|---|---|---|---|---|---|---|---|---|
| king_store | stores | `Stores7290058108879-000-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 48 | 0.06 |
| mega | stores | `Stores7290055700007-000-20261022-000100.xml` | 2026-10-22T00:01+03:00 | 10.6 | v1 | loaded | 147 | 0.3 |
| osherad | stores | `Stores7290103152017-000-20261020-080500.xml` | 2026-10-20T08:05+03:00 | 50.5 | v1 | loaded | 24 | 0.02 |
| ramilevy | stores | `Stores7290058140886-000-20261020-050500.xml` | 2026-10-20T05:05+03:00 | 53.5 | v1 | loaded | 99 | 0.04 |
| tivtaam | stores | `Stores7290873255550-000-20261020-050500.xml` | 2026-10-20T05:05+03:00 | 53.5 | v1 | loaded | 54 | 0.03 |
| yohananof | stores | `Stores7290803800003-000-20261020-010000.xml` | 2026-10-20T01:00+03:00 | 57.6 | v1 | loaded | 51 | 0.15 |
| king_store | price_full | `PriceFull7290058108879-000-340-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 2,338 | 0.68 |
| king_store | promo_full | `PromoFull7290058108879-000-340-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 296 | 0.15 |
| mega | price_full | `PriceFull7290055700007-001-002-20261022-051018.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 5,879 | 0.8 |
| mega | promo_full | `PromoFull7290055700007-001-002-20261022-051124.gz` | 2026-10-22T05:11+03:00 | 5.4 | v1 | loaded | 1,547 | 0.62 |
| osherad | price_full | `PriceFull7290103152017-001-001-20261022-080018.gz` | 2026-10-22T08:00+03:00 | 2.6 | v1 | loaded | 6,495 | 0.86 |
| osherad | promo_full | `PromoFull7290103152017-001-001-20261022-080055.gz` | 2026-10-22T08:00+03:00 | 2.6 | v1 | loaded | 660 | 0.25 |
| ramilevy | price_full | `PriceFull7290058140886-001-001-20261022-001004.gz` | 2026-10-22T00:10+03:00 | 10.4 | v1 | loaded | 12,975 | 1.87 |
| ramilevy | promo_full | `PromoFull7290058140886-001-001-20261022-001131.gz` | 2026-10-22T00:11+03:00 | 10.4 | v1 | loaded | 2,660 | 1.21 |
| tivtaam | price_full | `PriceFull7290873255550-000-002-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 9.9 | v1 | loaded | 21,607 | 3.17 |
| tivtaam | promo_full | `PromoFull7290873255550-000-002-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 9.9 | v1 | loaded | 2,246 | 4.66 |
| yohananof | price_full | `PriceFull7290803800003-000-001-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 9.9 | v1 | loaded | 10,722 | 1.37 |
| yohananof | promo_full | `PromoFull7290803800003-000-009-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 9.9 | v1 | loaded | 1,206 | 0.75 |
| king_store | price_full | `PriceFull7290058108879-000-200-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 3,611 | 0.47 |
| king_store | promo_full | `PromoFull7290058108879-000-200-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 306 | 0.12 |
| mega | price_full | `PriceFull7290055700007-001-407-20261022-051000.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 8,571 | 1.26 |
| mega | price_full | `PriceFull7290055700007-001-091-20261022-051002.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 6,836 | 1.02 |
| mega | price_full | `PriceFull7290055700007-001-452-20261022-051004.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 8,170 | 1.26 |
| mega | price_full | `PriceFull7290055700007-001-345-20261022-051005.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 6,633 | 0.92 |
| mega | price_full | `PriceFull7290055700007-001-457-20261022-051010.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 9,234 | 1.32 |
| mega | price_full | `PriceFull7290055700007-001-067-20261022-051014.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 7,877 | 1.1 |
| mega | promo_full | `PromoFull7290055700007-001-452-20261022-051056.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 1,516 | 0.55 |
| mega | promo_full | `PromoFull7290055700007-001-091-20261022-051057.gz` | 2026-10-22T05:10+03:00 | 5.4 | v1 | loaded | 1,532 | 0.68 |
| mega | promo_full | `PromoFull7290055700007-001-407-20261022-051106.gz` | 2026-10-22T05:11+03:00 | 5.4 | v1 | loaded | 1,462 | 0.75 |
| mega | promo_full | `PromoFull7290055700007-001-067-20261022-051111.gz` | 2026-10-22T05:11+03:00 | 5.4 | v1 | loaded | 1,442 | 0.7 |
| mega | promo_full | `PromoFull7290055700007-001-345-20261022-051117.gz` | 2026-10-22T05:11+03:00 | 5.4 | v1 | loaded | 1,442 | 0.6 |
| mega | promo_full | `PromoFull7290055700007-001-457-20261022-051121.gz` | 2026-10-22T05:11+03:00 | 5.4 | v1 | loaded | 1,434 | 0.61 |
| osherad | price_full | `PriceFull7290103152017-001-028-20261022-070013.gz` | 2026-10-22T07:00+03:00 | 3.6 | v1 | loaded | 6,234 | 0.96 |
| osherad | price_full | `PriceFull7290103152017-001-025-20261022-080000.gz` | 2026-10-22T08:00+03:00 | 2.6 | v1 | loaded | 6,252 | 0.81 |
| osherad | price_full | `PriceFull7290103152017-001-010-20261022-080001.gz` | 2026-10-22T08:00+03:00 | 2.6 | v1 | loaded | 6,690 | 0.9 |
| osherad | price_full | `PriceFull7290103152017-001-026-20261022-080012.gz` | 2026-10-22T08:00+03:00 | 2.6 | v1 | loaded | 6,833 | 1.22 |
| osherad | promo_full | `PromoFull7290103152017-001-028-20261022-070050.gz` | 2026-10-22T07:00+03:00 | 3.6 | v1 | loaded | 715 | 0.29 |
| osherad | promo_full | `PromoFull7290103152017-001-025-20261022-080037.gz` | 2026-10-22T08:00+03:00 | 2.6 | v1 | loaded | 739 | 0.33 |
| osherad | promo_full | `PromoFull7290103152017-001-026-20261022-080049.gz` | 2026-10-22T08:00+03:00 | 2.6 | v1 | loaded | 734 | 0.33 |
| osherad | promo_full | `PromoFull7290103152017-001-010-20261022-080106.gz` | 2026-10-22T08:01+03:00 | 2.6 | v1 | loaded | 705 | 0.29 |
| ramilevy | price_full | `PriceFull7290058140886-001-703-20261022-001001.gz` | 2026-10-22T00:10+03:00 | 10.4 | v1 | loaded | 4,950 | 0.72 |
| ramilevy | price_full | `PriceFull7290058140886-001-048-20261022-001016.gz` | 2026-10-22T00:10+03:00 | 10.4 | v1 | loaded | 14,443 | 2.3 |
| ramilevy | price_full | `PriceFull7290058140886-001-718-20261022-060005.gz` | 2026-10-22T06:00+03:00 | 4.6 | v1 | loaded | 3,809 | 0.5 |
| ramilevy | price_full | `PriceFull7290058140886-001-725-20261022-060005.gz` | 2026-10-22T06:00+03:00 | 4.6 | v1 | loaded | 4,108 | 0.6 |
| ramilevy | price_full | `PriceFull7290058140886-001-050-20261022-060006.gz` | 2026-10-22T06:00+03:00 | 4.6 | v1 | loaded | 14,809 | 2.42 |
| ramilevy | price_full | `PriceFull7290058140886-001-724-20261022-060015.gz` | 2026-10-22T06:00+03:00 | 4.6 | v1 | loaded | 5,147 | 0.75 |
| ramilevy | promo_full | `PromoFull7290058140886-001-703-20261022-001044.gz` | 2026-10-22T00:10+03:00 | 10.4 | v1 | loaded | 1,109 | 0.5 |
| ramilevy | promo_full | `PromoFull7290058140886-001-048-20261022-001113.gz` | 2026-10-22T00:11+03:00 | 10.4 | v1 | loaded | 2,529 | 1.36 |
| ramilevy | promo_full | `PromoFull7290058140886-001-718-20261022-060028.gz` | 2026-10-22T06:00+03:00 | 4.6 | v1 | loaded | 1,072 | 0.6 |
| ramilevy | promo_full | `PromoFull7290058140886-001-725-20261022-060028.gz` | 2026-10-22T06:00+03:00 | 4.6 | v1 | loaded | 1,047 | 0.45 |
| ramilevy | promo_full | `PromoFull7290058140886-001-724-20261022-060039.gz` | 2026-10-22T06:00+03:00 | 4.6 | v1 | loaded | 1,060 | 0.48 |
| ramilevy | promo_full | `PromoFull7290058140886-001-050-20261022-060107.gz` | 2026-10-22T06:01+03:00 | 4.6 | v1 | loaded | 2,507 | 1.15 |
| tivtaam | price_full | `PriceFull7290873255550-000-006-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 16,079 | 2.39 |
| tivtaam | price_full | `PriceFull7290873255550-000-079-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 6,351 | 0.9 |
| tivtaam | price_full | `PriceFull7290873255550-000-085-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 7,171 | 1.09 |
| tivtaam | price_full | `PriceFull7290873255550-000-087-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 6,069 | 0.8 |
| tivtaam | promo_full | `PromoFull7290873255550-000-006-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 2,000 | 4.66 |
| tivtaam | promo_full | `PromoFull7290873255550-000-079-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 567 | 4.65 |
| tivtaam | promo_full | `PromoFull7290873255550-000-085-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 1,281 | 5.11 |
| tivtaam | promo_full | `PromoFull7290873255550-000-087-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 1,124 | 4.47 |
| yohananof | price_full | `PriceFull7290803800003-000-020-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 11,876 | 1.72 |
| yohananof | price_full | `PriceFull7290803800003-000-021-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 11,196 | 1.62 |
| yohananof | price_full | `PriceFull7290803800003-000-029-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 10,462 | 1.46 |
| yohananof | promo_full | `PromoFull7290803800003-000-020-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 1,276 | 0.86 |
| yohananof | promo_full | `PromoFull7290803800003-000-021-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 1,218 | 0.66 |
| yohananof | promo_full | `PromoFull7290803800003-000-029-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.0 | v1 | loaded | 1,106 | 0.77 |

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

- seed: 0.95 s
- normalize: 7.82 s
- extract (rule): 63.89 s
- embed (hash): 255.05 s
- judge (rule): 151.38 s

### Precompute (production semantics)

6,799 rows written in 0.899 s of job time (1.23 s wall including start-up); 4,737 items priced at 30 stores (425 stores of 6 chains considered); 1,834 rows with a promo, 217 club-only. Canonicals with a real price: 207, of them 184 at two or more stores (any brand).

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

11,084 rows written in 1.86 s of job time (2.15 s wall including start-up); 16,924 items priced at 30 stores (425 stores of 6 chains considered); 3,081 rows with a promo, 430 club-only. Canonicals with a real price: 241, of them 235 at two or more stores (any brand).

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

`item_embeddings` holds 83,769 rows (model `hash-ngram-2-3-4-v1`); one `ORDER BY embedding <=> q LIMIT 40` query took [3.9, 1.0, 0.7] ms; with sequential scans disabled 0.7 ms.

```
Limit  (cost=2263.54..2519.66 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2263.54..538631.65 rows=83769 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
--- enable_seqscan = off
Limit  (cost=2263.54..2519.66 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2263.54..538631.65 rows=83769 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
```

One `/parse-list` call (6 lines): 3491.5 ms in total, 3483.4 ms inside 37 SQL statements. The statements that cost the most:

| statement (first 110 characters) | calls | total ms | max ms |
|---|---|---|---|
| `WITH qv AS (SELECT %(v)s::vector AS v), direct AS ( SELECT c.id AS canonical_id, 1 - (c.embedding <=> qv.v) AS` | 6 | 3453.3 | 607.3 |
| `WITH q AS (SELECT search_norm(%(q)s) AS t) SELECT c.id, word_similarity(q.t, search_norm(c.display_name_he)) A` | 6 | 15.8 | 6.1 |
| `WITH RECURSIVE up AS ( SELECT t.id AS leaf, t.id, t.parent_id, t.name_he, t.level FROM taxonomy t WHERE t.id =` | 6 | 4.1 | 1.1 |
| `SELECT id, display_name_he, taxonomy_id, base_unit, rank, names_ar[1] FROM canonical_products WHERE id = ANY(%` | 6 | 4.0 | 0.9 |
| `SELECT c.id, c.display_name_he, ts_rank_cd(to_tsvector('simple', search_norm(c.display_name_he)), tq) AS r FRO` | 6 | 3.7 | 1.4 |
| `SELECT set_config('pg_trgm.word_similarity_threshold', %s, true)` | 6 | 1.9 | 0.8 |

`EXPLAIN (ANALYZE, BUFFERS)` of the slowest statement:

```
Limit  (cost=7024.44..7024.47 rows=11 width=16) (actual rows=20 loops=1)
  Buffers: shared hit=671118 read=57686
  CTE qv
    ->  Result  (cost=0.00..0.01 rows=1 width=32) (actual rows=1 loops=1)
  ->  Sort  (cost=7024.43..7024.46 rows=11 width=16) (actual rows=20 loops=1)
        Sort Key: (max(direct.s)) DESC, direct.canonical_id
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=671118 read=57686
        ->  GroupAggregate  (cost=7023.73..7024.24 rows=11 width=16) (actual rows=20 loops=1)
              Group Key: direct.canonical_id
              Buffers: shared hit=671115 read=57686
              ->  Merge Append  (cost=7023.73..7024.08 rows=11 width=16) (actual rows=24 loops=1)
                    Sort Key: direct.canonical_id
                    Buffers: shared hit=671115 read=57686
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
                    ->  GroupAggregate  (cost=6990.43..6990.65 rows=4 width=16) (actual rows=4 loops=1)
                          Group Key: ic.canonical_id
                          Filter: (max((('1'::double precision - (e.embedding <=> qv_1.v)))) >= '0.25'::double precision)
                          Buffers: shared hit=669616 read=57504
                          ->  Sort  (cost=6990.43..6990.46 rows=11 width=16) (actual rows=14 loops=1)
                                Sort Key: ic.canonical_id
                                Sort Method: quicksort  Memory: 25kB
                                Buffers: shared hit=669616 read=57504
                                ->  Nested Loop  (cost=6444.13..6990.24 rows=11 width=16) (actual rows=14 loops=1)
                                      Buffers: shared hit=669616 read=57504
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
                                      ->  Index Scan using item_canonical_pkey on item_canonical ic  (cost=0.29..6.81 rows=1 width=16) (actual rows=0 loops=80)
                                            Index Cond: (item_id = e.item_id)
                                            Filter: ((NOT human_rejected) AND (NOT needs_review) AND (flex_level = ANY ('{exact,any_brand}'::text[])))
                                            Rows Removed by Filter: 1
                                            Buffers: shared hit=131 read=104
Planning:
  Buffers: shared hit=415 read=62
Planning Time: 1.661 ms
Execution Time: 606.699 ms
```

### /parse-list, /compare and /optimize (production semantics)

Locations: Holon (8 priced stores, 5 chains within 5 km); Jerusalem centre (8 priced stores, 5 chains within 5 km); Petah Tikva (6 priced stores, 4 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 3612.3 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 9884.4 |
| large (32 lines) | 33 | 33 | 5 | 0 | 19188.9 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Holon | hand: small (6 lines) | 6 | 8 | 0 | 7.2 | 7.3 | 12.3 | 55 | single: רמי לוי חולון | -4.17 / -4.17 |
| Holon | hand: weekly (17 lines) | 17 | 8 | 0 | 10.1 | 9.3 | 14.8 | 55 | single: טיב טעם בת ים | 6.84 / 6.84 |
| Holon | hand: large (32 lines) | 33 | 8 | 0 | 13.1 | 11.3 | 18.3 | 55 | single: רמי לוי חולון | 93.6 / 93.6 |
| Holon | drawn: 5 | 5 | 8 | 0 | 6.4 | 5.7 | 11.4 | 55 | single: רמי לוי שוויצריה סוקולוב | 27.48 / 27.48 |
| Holon | drawn: 10 | 10 | 8 | 0 | 8 | 7.5 | 14.3 | 55 | single: רמי לוי חולון | 112.49 / 112.49 |
| Holon | drawn: 20 | 20 | 8 | 0 | 12.2 | 10.7 | 17.3 | 55 | single: רמי לוי חולון | 186.81 / 186.81 |
| Holon | drawn: 40 | 40 | 8 | 0 | 17.8 | 15.8 | 30.5 | 55 | single: רמי לוי חולון | 246.49 / 246.49 |
| Jerusalem centre | hand: small (6 lines) | 6 | 8 | 0 | 5.7 | 5.8 | 11.3 | 55 | single: רמי לוי עטרות | 1.15 / 1.15 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 8 | 0 | 9.9 | 8.7 | 14.5 | 55 | single: רמי לוי עטרות | -8.05 / -8.05 |
| Jerusalem centre | hand: large (32 lines) | 33 | 8 | 0 | 13 | 10.4 | 16.4 | 55 | single: רמי לוי עטרות | 9.22 / 9.22 |
| Jerusalem centre | drawn: 5 | 5 | 8 | 5 | 6.6 | 6.4 | 12 | 55 | single: קרפור (מגה) קרפור מרקט ריינס | 0.0 / 0.0 |
| Jerusalem centre | drawn: 10 | 10 | 8 | 0 | 9.7 | 7.6 | 13.1 | 55 | single: רמי לוי עטרות | 60.0 / 60.0 |
| Jerusalem centre | drawn: 20 | 20 | 8 | 0 | 12 | 10 | 15.9 | 55 | single: רמי לוי עטרות | 68.4 / 68.4 |
| Jerusalem centre | drawn: 40 | 40 | 8 | 0 | 18.9 | 14.7 | 28 | 55 | single: רמי לוי עטרות | 80.8 / 85.5 |
| Petah Tikva | hand: small (6 lines) | 6 | 6 | 0 | 5.8 | 5.4 | 10.9 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 17.64 / 17.64 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 6 | 0 | 8.2 | 7.5 | 12.5 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 16.04 / 16.04 |
| Petah Tikva | hand: large (32 lines) | 33 | 6 | 0 | 11 | 9.8 | 16.7 | 55 | single: יוחננוף סגולה פתח תקווה | 1.52 / 1.52 |
| Petah Tikva | drawn: 5 | 5 | 6 | 2 | 6.5 | 5.7 | 11.3 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 2.86 / 2.86 |
| Petah Tikva | drawn: 10 | 10 | 6 | 0 | 7.5 | 6.7 | 12.3 | 55 | single: יוחננוף סגולה פתח תקווה | 18.85 / 18.85 |
| Petah Tikva | drawn: 20 | 20 | 6 | 0 | 10.9 | 9 | 16.1 | 55 | single: יוחננוף סגולה פתח תקווה | 20.13 / 20.13 |
| Petah Tikva | drawn: 40 | 40 | 6 | 0 | 15.6 | 13.8 | 22.3 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 6.36 / 6.36 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 5.8 | 5.8 | 11.3 |
| hand: weekly (17 lines) | 9.9 | 8.7 | 14.5 |
| hand: large (32 lines) | 13.0 | 10.4 | 16.7 |
| drawn: 5 | 6.5 | 5.7 | 11.4 |
| drawn: 10 | 8.0 | 7.5 | 13.1 |
| drawn: 20 | 12.0 | 10.0 | 16.1 |
| drawn: 40 | 17.8 | 14.7 | 28.0 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Holon | hand: small (6 lines) | 6.7 | 11.8 | - | - | -4.17 / -4.17 |
| Holon | hand: weekly (17 lines) | 8.6 | 13.8 | - | - | 6.84 / 6.84 |
| Holon | hand: large (32 lines) | 11.8 | 18.9 | - | - | 93.6 / 93.6 |
| Holon | drawn: 5 | 6.3 | 11.7 | - | - | 27.48 / 27.48 |
| Holon | drawn: 10 | 8.4 | 15.3 | - | - | 112.49 / 112.49 |
| Holon | drawn: 20 | 10.4 | 16.5 | - | - | 186.81 / 186.81 |
| Holon | drawn: 40 | 15.8 | 30.6 | - | - | 246.49 / 246.49 |
| Jerusalem centre | hand: small (6 lines) | 5.9 | 11.6 | רמי לוי עטרות, רמי לוי בית הפירות פת | רמי לוי עטרות, רמי לוי בית הפירות פת | -2.92 / -2.92 |
| Jerusalem centre | hand: weekly (17 lines) | 8.1 | 13.3 | - | - | -8.05 / -8.05 |
| Jerusalem centre | hand: large (32 lines) | 10.1 | 16.4 | - | - | 9.22 / 9.22 |
| Jerusalem centre | drawn: 5 | 6.6 | 12.5 | קינג סטור ואדי אלגוז', קרפור (מגה) קרפור מרקט ריינס | קינג סטור ואדי אלגוז', קרפור (מגה) קרפור מרקט ריינס | 16.03 / 16.03 |
| Jerusalem centre | drawn: 10 | 7.1 | 13 | אושר עד שמגר, רמי לוי בית הפירות פת | אושר עד שמגר, רמי לוי בית הפירות פת | 64.89 / 64.89 |
| Jerusalem centre | drawn: 20 | 10 | 16.8 | - | - | 68.4 / 68.4 |
| Jerusalem centre | drawn: 40 | 15 | 29.7 | אושר עד שמגר, רמי לוי עטרות | אושר עד שמגר, רמי לוי עטרות | 114.09 / 118.79 |
| Petah Tikva | hand: small (6 lines) | 5.5 | 10.2 | - | - | 17.64 / 17.64 |
| Petah Tikva | hand: weekly (17 lines) | 7.5 | 12.6 | - | - | 16.04 / 16.04 |
| Petah Tikva | hand: large (32 lines) | 11.1 | 17.3 | - | - | 1.52 / 1.52 |
| Petah Tikva | drawn: 5 | 6 | 11.3 | אושר עד פתח תקווה - סגולה, רמי לוי שטמפפר פתח תקווה | אושר עד פתח תקווה - סגולה, רמי לוי שטמפפר פתח תקווה | 52.42 / 52.42 |
| Petah Tikva | drawn: 10 | 7.2 | 13.2 | - | - | 18.85 / 18.85 |
| Petah Tikva | drawn: 20 | 9 | 16.4 | - | - | 20.13 / 20.13 |
| Petah Tikva | drawn: 40 | 14 | 21.6 | - | - | 6.36 / 6.36 |

### /parse-list, /compare and /optimize (stress: unreviewed mappings included, performance only)

Locations: Holon (8 priced stores, 5 chains within 5 km); Jerusalem centre (8 priced stores, 5 chains within 5 km); Petah Tikva (6 priced stores, 4 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 3505.5 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 9827.7 |
| large (32 lines) | 33 | 33 | 5 | 0 | 19096.4 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Holon | hand: small (6 lines) | 6 | 8 | 4 | 8.2 | 7.8 | 14.6 | 55 | single: רמי לוי חולון | 81.28 / 81.28 |
| Holon | hand: weekly (17 lines) | 17 | 8 | 2 | 14 | 11.6 | 18.9 | 55 | split: קרפור (מגה) קרפור סיטי  חולון בסיטי, רמי לוי חולון | 99.89 / 99.89 |
| Holon | hand: large (32 lines) | 33 | 8 | 0 | 19.7 | 18.7 | 28.1 | 55 | single: יוחננוף בת ים | 127.81 / 127.81 |
| Holon | drawn: 5 | 5 | 8 | 3 | 7.8 | 6.4 | 10.5 | 55 | single: רמי לוי חולון | 80.59 / 80.59 |
| Holon | drawn: 10 | 10 | 8 | 2 | 9 | 8.6 | 14.5 | 55 | single: טיב טעם בת ים | -2.46 / -2.46 |
| Holon | drawn: 20 | 20 | 8 | 0 | 13.6 | 12.4 | 19.4 | 55 | single: רמי לוי חולון | 168.2 / 168.2 |
| Holon | drawn: 40 | 40 | 8 | 0 | 22.3 | 20.6 | 29.1 | 55 | single: רמי לוי חולון | 979.9 / 979.9 |
| Jerusalem centre | hand: small (6 lines) | 6 | 8 | 4 | 7.5 | 7.5 | 13.5 | 55 | single: רמי לוי עטרות | 47.12 / 47.12 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 8 | 0 | 13.2 | 10.9 | 16.5 | 55 | single: רמי לוי עטרות | 39.44 / 39.44 |
| Jerusalem centre | hand: large (32 lines) | 33 | 8 | 0 | 17.8 | 15 | 22.4 | 55 | split: קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | 86.43 / 86.43 |
| Jerusalem centre | drawn: 5 | 5 | 8 | 3 | 6.9 | 6.2 | 11.1 | 55 | single: רמי לוי עטרות | -29.4 / -29.4 |
| Jerusalem centre | drawn: 10 | 10 | 8 | 2 | 8.4 | 7.2 | 12.8 | 55 | single: רמי לוי עטרות | 5.7 / 5.7 |
| Jerusalem centre | drawn: 20 | 20 | 8 | 0 | 13.1 | 10.9 | 19.2 | 55 | split: קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | 2.03 / 2.03 |
| Jerusalem centre | drawn: 40 | 40 | 8 | 0 | 21.9 | 16.4 | 29.4 | 55 | single: רמי לוי עטרות | 335.2 / 335.2 |
| Petah Tikva | hand: small (6 lines) | 6 | 6 | 5 | 6.3 | 6 | 10.9 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 1.26 / 1.26 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 6 | 0 | 10 | 9.7 | 14.8 | 55 | split: רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | -5.84 / -5.84 |
| Petah Tikva | hand: large (32 lines) | 33 | 6 | 0 | 14.3 | 13.4 | 20.9 | 55 | split: רמי לוי שטמפפר פתח תקווה, יוחננוף סגולה פתח תקווה | 11.2 / 11.2 |
| Petah Tikva | drawn: 5 | 5 | 6 | 3 | 6.3 | 6.1 | 10.9 | 55 | single: רמי לוי שטמפפר פתח תקווה | 0.0 / 0.0 |
| Petah Tikva | drawn: 10 | 10 | 6 | 2 | 7.9 | 7.5 | 13.4 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 23.59 / 23.59 |
| Petah Tikva | drawn: 20 | 20 | 6 | 0 | 11.2 | 10.7 | 16.1 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 9.26 / 9.26 |
| Petah Tikva | drawn: 40 | 40 | 6 | 0 | 18.1 | 16.5 | 26.3 | 55 | split: אושר עד פתח תקווה - סגולה, רמי לוי שטמפפר פתח תקווה | 70.54 / 70.54 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 7.5 | 7.5 | 13.5 |
| hand: weekly (17 lines) | 13.2 | 10.9 | 16.5 |
| hand: large (32 lines) | 17.8 | 15.0 | 22.4 |
| drawn: 5 | 6.9 | 6.2 | 10.9 |
| drawn: 10 | 8.4 | 7.5 | 13.4 |
| drawn: 20 | 13.1 | 10.9 | 19.2 |
| drawn: 40 | 21.9 | 16.5 | 29.1 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Holon | hand: small (6 lines) | 8.9 | 16.3 | - | - | 81.28 / 81.28 |
| Holon | hand: weekly (17 lines) | 11.7 | 18.8 | קרפור (מגה) קרפור סיטי  חולון בסיטי, רמי לוי חולון | קרפור (מגה) קרפור סיטי  חולון בסיטי, רמי לוי חולון | 124.89 / 124.89 |
| Holon | hand: large (32 lines) | 17.6 | 24.1 | - | - | 127.81 / 127.81 |
| Holon | drawn: 5 | 6.4 | 12.4 | - | - | 80.59 / 80.59 |
| Holon | drawn: 10 | 9 | 15.1 | רמי לוי חולון, טיב טעם בת ים | רמי לוי חולון, טיב טעם בת ים | 43.96 / 43.96 |
| Holon | drawn: 20 | 13.5 | 22.7 | - | - | 168.2 / 168.2 |
| Holon | drawn: 40 | 19.4 | 29.4 | - | - | 979.9 / 979.9 |
| Jerusalem centre | hand: small (6 lines) | 7.5 | 12.6 | אושר עד שמגר, רמי לוי עטרות | אושר עד שמגר, רמי לוי עטרות | 47.21 / 47.21 |
| Jerusalem centre | hand: weekly (17 lines) | 10.3 | 16.3 | קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | 58.37 / 58.37 |
| Jerusalem centre | hand: large (32 lines) | 15 | 22.7 | קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | 111.43 / 111.43 |
| Jerusalem centre | drawn: 5 | 6.1 | 11.4 | קינג סטור ואדי אלגוז', קרפור (מגה) קרפור מרקט ריינס | קינג סטור ואדי אלגוז', קרפור (מגה) קרפור מרקט ריינס | 16.63 / 16.63 |
| Jerusalem centre | drawn: 10 | 7 | 12.8 | קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | 23.63 / 23.63 |
| Jerusalem centre | drawn: 20 | 10.9 | 18.2 | קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | קרפור (מגה) קרפור מרקט ריינס, רמי לוי עטרות | 27.03 / 27.03 |
| Jerusalem centre | drawn: 40 | 17 | 28.7 | - | - | 335.2 / 335.2 |
| Petah Tikva | hand: small (6 lines) | 6.4 | 11.1 | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | 3.36 / 3.36 |
| Petah Tikva | hand: weekly (17 lines) | 9.8 | 15.9 | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | 19.16 / 19.16 |
| Petah Tikva | hand: large (32 lines) | 13.6 | 20.8 | רמי לוי שטמפפר פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי שטמפפר פתח תקווה, יוחננוף סגולה פתח תקווה | 36.2 / 36.2 |
| Petah Tikva | drawn: 5 | 6.4 | 11.3 | רמי לוי שטמפפר פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי שטמפפר פתח תקווה, יוחננוף סגולה פתח תקווה | 42.94 / 42.94 |
| Petah Tikva | drawn: 10 | 7.9 | 13.9 | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | 32.93 / 32.93 |
| Petah Tikva | drawn: 20 | 12.4 | 16.1 | - | - | 9.26 / 9.26 |
| Petah Tikva | drawn: 40 | 16.4 | 25.2 | אושר עד פתח תקווה - סגולה, רמי לוי שטמפפר פתח תקווה | אושר עד פתח תקווה - סגולה, רמי לוי שטמפפר פתח תקווה | 95.54 / 95.54 |

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

#### `butter`: 48 listed of 199 name hits (0 skipped as not the food itself; chains looked in: mega, king_store, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| mega | מאסט סוכריות חמאה לל | ? / ? | butter | 80 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.52 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; sour-cream-15 (שמנת חמוצה 15%): similarity 0.12 |
| mega | חמאה מלוחה משמנת מפו | ? / ? | butter | 250 g | butter close 0.81 review | review: butter (חמאה): similarity 0.51 \| critical match product_type=butter \| soft differs pack_size 250 vs 200 g \| level close, confidence 0.81 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.25 \| critical mismatch product |
| mega | ROSHEN חמאה 82.5% 20 | ? / ? | butter | 200 g | butter any_brand 0.79 review | review: butter (חמאה): similarity 0.49 \| critical match product_type=butter \| level any_brand, confidence 0.79 \| vetoed: labane-5 (לבנה 5%): similarity 0.26 \| critical mismatch product_type butter vs labane; fat_pct 82.5 vs 5 ; co |
| mega | וילי פוד חמאה בלגית | ? / ? | butter | 200 g | butter any_brand 0.76 review | review: butter (חמאה): similarity 0.45 \| critical match product_type=butter \| level any_brand, confidence 0.76 \| vetoed: bulgarian-cheese-5 (גבינה בולגרית 5%): similarity 0.11 \| critical mismatch product_type butter vs bulgarian_c |
| mega | מאסט סוכריות חמאה לל | ? / ? | butter | 80 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.52 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; sour-cream-15 (שמנת חמוצה 15%): similarity 0.12 |
| mega | ויליפוד חמאה רכה למר | ? / ? | butter | 200 g | butter any_brand 0.81 review | review: butter (חמאה): similarity 0.51 \| critical match product_type=butter \| level any_brand, confidence 0.81 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.13 \| critical mismatch product_type butter vs white_cheese \| cri |
| mega | חמאה 200 גרם מהדרין | ? / ? | butter | 200 g | butter any_brand 0.78 review | review: butter (חמאה): similarity 0.48 \| critical match product_type=butter \| level any_brand, confidence 0.78 \| vetoed: margarine (מרגרינה): similarity 0.15 \| critical mismatch product_type butter vs margarine ; sour-cream-15 (שמ |
| mega | מחמאה מרגרינה בטעם ח | ? / ? | margarine | 200 g | margarine close 0.90 | accept: margarine (מרגרינה): similarity 0.63 \| critical match product_type=margarine \| soft differs pack_size 200 vs 250 g \| level close, confidence 0.90 \| vetoed: butter (חמאה): similarity 0.35 \| critical mismatch product_type ma |
| mega | מזולה בטעם חמאה 250 | ? / ? | - | 250 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.50 \| critical mismatch the canonical's words come only after 'בטעם' (a flavor, not the product) \| critical unknown product_type ; wafers-chocolate (ופלים בטעם שוקולד): s |
| mega | פופסטאר פופקורן חמאה | ? / ? | - | 500 g | - | rejected (confidence 0.24 < 0.6): pasta-fusilli (פסטה פוזילי): similarity 0.15 \| critical unknown product_type \| ambiguous with pasta-penne \| level any_brand, confidence 0.24 |
| mega | בצק עלים חמאה מעדנות | ? / ? | butter | 600 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.53 \| critical mismatch name has 'בצק' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; dessert-vanilla (מעדן חלב וניל): similarity 0.19 \|  |
| mega | FERMA   חמאה 82.5% 2 | ? / ? | butter | 200 g | butter any_brand 0.80 review | review: butter (חמאה): similarity 0.50 \| critical match product_type=butter \| level any_brand, confidence 0.80 \| vetoed: labane-5 (לבנה 5%): similarity 0.27 \| critical mismatch product_type butter vs labane; fat_pct 82.5 vs 5 ; co |
| king_store | פופ קורן בטעם חמאה 600 ג' | ? / ? | - | 600 g | - | rejected (confidence 0.24 < 0.6): cornflakes (קורנפלקס): similarity 0.19 \| critical unknown product_type \| soft differs pack_size 600 vs 750 g \| level close, confidence 0.24 \| vetoed: butter (חמאה): similarity 0.42 \| critical mism |
| king_store | פופקו חטיף בטעם חמאה 80 ג' אסם | ? / ? | - | 80 g | - | rejected (confidence 0.29 < 0.6): bamba (חטיף בוטנים (במבה)): similarity 0.31 \| critical unknown product_type \| level any_brand, confidence 0.29 \| vetoed: butter (חמאה): similarity 0.40 \| critical mismatch name has 'חטיף' (a deriv |
| king_store | חמאה עלמה 200ג' | ? / ? | butter | 200 g | butter any_brand 0.88 review | review: butter (חמאה): similarity 0.60 \| critical match product_type=butter \| level any_brand, confidence 0.88 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.13 \| critical mismatch product_type butter vs white_cheese \| cri |
| king_store | מארז פופקורן חמאה ודבש מארז 12*20 ג' אסם | ? / ? | butter | 240 g | butter close 0.66 review | review: butter (חמאה): similarity 0.33 \| critical match product_type=butter \| soft differs pack_size 240 vs 200 g \| level close, confidence 0.66 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.08 \| critical mismatch product |
| king_store | חמאה 200 ג' תנובה | ? / ? | butter | 200 g | butter any_brand 0.83 review | review: butter (חמאה): similarity 0.53 \| critical match product_type=butter \| level any_brand, confidence 0.83 \| vetoed: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.17 \| critical mismatch product_type butter vs y |
| king_store | עוגיות בטעם חמאה 340 ג' עוגלה | ? / ? | - | 340 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.43 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'חמאה'; the canonical's words come only after 'בטעם' (a flavor, not the product) \| critical un |
| king_store | סוכריות חמאה בטעם קפה ללא סוכר 80 ג' MUST | ? / ? | butter | 80 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.37 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; white-cheese-9 (גבינה לבנה 9%): similarity 0.11 |
| king_store | חמאה 200 ג' אלחלוב | ? / ? | butter | 200 g | butter any_brand 0.80 review | review: butter (חמאה): similarity 0.50 \| critical match product_type=butter \| level any_brand, confidence 0.80 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.10 \| critical mismatch product_type butter vs sour_cream \| criti |
| king_store | מחמאה מרגרינה בטעם חמאה 200 ג' בלו בנד | ? / ? | margarine | 200 g | margarine close 0.76 review | review: margarine (מרגרינה): similarity 0.46 \| critical match product_type=margarine \| soft differs pack_size 200 vs 250 g \| level close, confidence 0.76 \| vetoed: butter (חמאה): similarity 0.53 \| critical mismatch product_type ma |
| king_store | עוגיות בטעם חמאה 340 ג' grande | ? / ? | - | 340 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.43 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'חמאה'; the canonical's words come only after 'בטעם' (a flavor, not the product) \| critical un |
| king_store | סוכריות וורטר חמאה 400 ג' וורטר | ? / ? | butter | 400 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.33 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; yogurt-strawberry (יוגורט תות): similarity 0.16 |
| king_store | ממרח עוגיות חמאה 300 ג' CHOCOLAKE | ? / ? | - | 300 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.37 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'חמאה' \| critical unknown product_type ; chocolate-spread (ממרח שוקולד): similarity 0.25 \| cri |
| yohananof | חמאה רכה אלוויר 250 | ? / ? | butter | 250 g | butter close 0.82 review | review: butter (חמאה): similarity 0.52 \| critical match product_type=butter \| soft differs pack_size 250 vs 200 g \| level close, confidence 0.82 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.10 \| critical mismatch product |
| yohananof | חמאה רכה מלוחה אלווי | ? / ? | butter | 250 g | butter close 0.82 review | review: butter (חמאה): similarity 0.53 \| critical match product_type=butter \| soft differs pack_size 250 vs 200 g \| level close, confidence 0.82 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.13 \| critical mismatch product |
| yohananof | חמאה נורמנדי מלוחה א | ? / ? | butter | 200 g | butter any_brand 0.82 review | review: butter (חמאה): similarity 0.53 \| critical match product_type=butter \| level any_brand, confidence 0.82 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.10 \| critical mismatch product_type butter vs sour_cream \| criti |
| yohananof | *מבצע* חמאה חצי שמנה | ? / ? | butter | 200 g | butter any_brand 0.83 review | review: butter (חמאה): similarity 0.54 \| critical match product_type=butter \| level any_brand, confidence 0.83 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.26 \| critical mismatch product_type butter vs sour_cream \| criti |
| yohananof | *מבצע* חמאה מלוחה חצ | ? / ? | butter | 200 g | butter any_brand 0.84 review | review: butter (חמאה): similarity 0.56 \| critical match product_type=butter \| level any_brand, confidence 0.84 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.14 \| critical mismatch product_type butter vs sour_cream \| criti |
| yohananof | סוכריות חמאה 135 גרם | ? / ? | butter | 135 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.50 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; sour-cream-15 (שמנת חמוצה 15%): similarity 0.13 |

#### `chocolate-milk`: 72 listed of 3158 name hits (0 skipped as not the food itself; chains looked in: mega, king_store, ramilevy, osherad, yohananof, tivtaam)

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

#### `cottage-5`: 6 listed of 6 name hits (0 skipped as not the food itself; chains looked in: king_store)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| king_store | קוטג' 5% שומן 250 ג' טרה | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.87 review | review: cottage-5 (קוטג' 5%): similarity 0.59 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.87 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.39 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' 5% שומן 250 ג' שטראוס | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.84 review | review: cottage-5 (קוטג' 5%): similarity 0.55 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.84 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.37 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' בקטנה % 5 100 ג' תנובה | ? / ? | cottage_cheese | 100 g | - | rejected (confidence 0.51 < 0.6): cottage-5 (קוטג' 5%): similarity 0.36 \| critical match product_type=cottage_cheese \| critical unknown fat_pct \| soft differs pack_size 100 vs 250 g \| ambiguous with cottage-3 \| level close, confid |
| king_store | קוטג תנובה גביע 250 גר5% | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.70 review | review: cottage-5 (קוטג' 5%): similarity 0.37 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.70 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.33 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' 5% 250 ג' תנובה | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.89 review | review: cottage-5 (קוטג' 5%): similarity 0.61 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.89 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.39 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' 9% שומן 250 ג' תנובה | ? / ? | cottage_cheese | 250 g | - | every candidate vetoed \| vetoed: cottage-5 (קוטג' 5%): similarity 0.38 \| critical mismatch fat_pct 9 vs 5 \| critical match product_type=cottage_cheese ; cottage-3 (קוטג' 3%): similarity 0.38 \| critical mismatch fat_pct 9 vs 3 \| cr |

#### `eggs-l`: 168 listed of 309 name hits (138 skipped as not the food itself; chains looked in: king_store, ramilevy, osherad, yohananof, tivtaam)

Name hint of the size against what the item got (served = no review flag):

| size words in the name | result | items |
|---|---|---|
| ? | eggs-free-range-l any_brand | 2 |
| ? | eggs-free-range-l close | 1 |
| ? | review | 10 |
| ? | unmapped | 88 |
| L | eggs-free-range-l any_brand | 1 |
| L | eggs-free-range-l close | 2 |
| L | review | 4 |
| L | unmapped | 26 |
| M | eggs-free-range-l any_brand | 1 |
| M | unmapped | 27 |
| XL | unmapped | 6 |

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| king_store | ביצים 18 יח' L לסר | L / 18 | - | 18 unit | - | rejected (confidence 0.59 < 0.6): eggs-l (ביצים L): similarity 0.68 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.59 |
| king_store | ביצים מידיום 12 יח' | ? / 12 | - | 12 unit | - | rejected (confidence 0.42 < 0.6): eggs-l (ביצים L): similarity 0.48 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.42 |
| king_store | ביצים מידיום 12 יח' | ? / 12 | - | 12 unit | - | rejected (confidence 0.42 < 0.6): eggs-l (ביצים L): similarity 0.48 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.42 |
| king_store | נודלס ביצים להקפצה מאסטר שף 400 ג' | ? / ? | - | 400 g | - | rejected (confidence 0.26 < 0.6): egg-noodles (אטריות ביצים): similarity 0.28 \| critical unknown product_type \| soft differs pack_size 400 vs 500 g \| ambiguous with pickled-cucumbers \| level close, confidence 0.26 |
| king_store | ביצים לארג' 18 יח' | ? / 18 | - | 18 unit | - | rejected (confidence 0.44 < 0.6): eggs-l (ביצים L): similarity 0.50 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.44 |
| king_store | איטריות ביצים פפרדלה 250ג' ברילה | ? / ? | - | 250 g | - | rejected (confidence 0.28 < 0.6): mushrooms-fresh (פטריות שמפיניון טריות): similarity 0.30 \| critical unknown product_type, state \| level any_brand, confidence 0.28 |
| king_store | ביצים מידיום 30 יח' | ? / 30 | - | 30 unit | - | rejected (confidence 0.43 < 0.6): eggs-l (ביצים L): similarity 0.48 \| critical unknown product_type \| soft differs pack_size 30 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.43 |
| king_store | ביצים מידיום עטוף 30יח' | ? / 30 | - | 30 unit | - | rejected (confidence 0.37 < 0.6): eggs-l (ביצים L): similarity 0.41 \| critical unknown product_type \| soft differs pack_size 30 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.37 |
| king_store | ביצים לארג' 12 יח' | ? / 12 | - | 12 unit | - | rejected (confidence 0.43 < 0.6): eggs-l (ביצים L): similarity 0.49 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.43 |
| ramilevy | ביצים 12 יח גדול L | L / 12 | - | 12 unit | - | rejected (confidence 0.56 < 0.6): eggs-l (ביצים L): similarity 0.65 \| critical unknown product_type \| level any_brand, confidence 0.56 |
| ramilevy | ביצים 12 יח בינוני M | M / 12 | - | 12 unit | - | rejected (confidence 0.55 < 0.6): eggs-m (ביצים M): similarity 0.64 \| critical unknown product_type \| level any_brand, confidence 0.55 |
| ramilevy | ביצים 12 יח בינוני M | M / 12 | - | 12 unit | - | rejected (confidence 0.55 < 0.6): eggs-m (ביצים M): similarity 0.64 \| critical unknown product_type \| level any_brand, confidence 0.55 |
| ramilevy | ביצים 12 יח גדול L | L / 12 | - | 12 unit | - | rejected (confidence 0.56 < 0.6): eggs-l (ביצים L): similarity 0.65 \| critical unknown product_type \| level any_brand, confidence 0.56 |
| ramilevy | ביצים 18יח בנוני M | M / 18 | - | 18 unit | - | rejected (confidence 0.57 < 0.6): eggs-m (ביצים M): similarity 0.66 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.57 |
| ramilevy | ביצים 18יח גדול L | L / 18 | - | 18 unit | - | rejected (confidence 0.59 < 0.6): eggs-l (ביצים L): similarity 0.69 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.59 |
| ramilevy | ביצים 30יח בינוני M | M / 30 | - | 30 unit | - | rejected (confidence 0.58 < 0.6): eggs-m (ביצים M): similarity 0.67 \| critical unknown product_type \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.58 |
| ramilevy | ביצים 30יח גדול L | L / 30 | - | 30 unit | - | rejected (confidence 0.58 < 0.6): eggs-l (ביצים L): similarity 0.68 \| critical unknown product_type \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.58 |
| ramilevy | ביצי חופש 30יח L רמי | L / 30 | eggs_free_range_l | 30 unit | eggs-free-range-l close 1.00 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.79 \| critical match product_type=eggs_free_range_l \| soft differs pack_size 30 vs 12 unit \| level close, confidence 1.00 \| vetoed: eggs-l (ביצים L): similarity 0.40 \| critical  |
| ramilevy | פורס ביצה משובח | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): parsley (פטרוזיליה): similarity 0.07 \| critical unknown product_type, state \| ambiguous with coriander \| level any_brand, confidence 0.24 |
| ramilevy | ביצים 30יח ענק XL | XL / 30 | - | 30 unit | - | rejected (confidence 0.56 < 0.6): eggs-xl (ביצים XL): similarity 0.65 \| critical unknown product_type \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.56 |
| ramilevy | בצק משחק -ביצה | ? / ? | - | 1 unit | - | every candidate vetoed \| vetoed: eggs-xl (ביצים XL): similarity 0.22 \| critical mismatch name has 'בצק' (a derived product), canonical is 'ביצים XL' \| critical unknown product_type ; eggs-free-range-l (ביצי חופש L): similarity 0.2 |
| ramilevy | איטריות ביצים מזרח ו | ? / ? | - | -  | - | rejected (confidence 0.54 < 0.6): egg-noodles (אטריות ביצים): similarity 0.63 \| critical unknown product_type \| level any_brand, confidence 0.54 |
| ramilevy | ביצי דג שיבוט 200 גר | ? / ? | - | 200 g | - | rejected (confidence 0.24 < 0.6): rolled-oats (שיבולת שועל): similarity 0.23 \| critical unknown product_type \| soft differs pack_size 200 vs 500 g \| ambiguous with green-beans-frozen \| level close, confidence 0.24 |
| ramilevy | פורס ביצה קפיצי | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): parsley (פטרוזיליה): similarity 0.07 \| critical unknown product_type, state \| ambiguous with cling-wrap \| level any_brand, confidence 0.24 |
| ramilevy | ביצי אומגה 12יח M | M / 12 | - | 12 unit | - | rejected (confidence 0.35 < 0.6): eggs-m (ביצים M): similarity 0.39 \| critical unknown product_type \| level any_brand, confidence 0.35 |
| ramilevy | ביצי חופש 30יח L | L / 30 | eggs_free_range_l | 30 unit | eggs-free-range-l close 1.00 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.85 \| critical match product_type=eggs_free_range_l \| soft differs pack_size 30 vs 12 unit \| level close, confidence 1.00 \| vetoed: eggs-l (ביצים L): similarity 0.44 \| critical  |
| ramilevy | פתיתי ביצים כוכ | ? / ? | - | -  | - | rejected (confidence 0.41 < 0.6): eggs-m (ביצים M): similarity 0.46 \| critical unknown product_type \| ambiguous with eggs-l \| level any_brand, confidence 0.41 |
| ramilevy | כורסת רביצה בואקום - | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): coriander (כוסברה): similarity 0.11 \| critical unknown product_type, state \| ambiguous with parsley \| level any_brand, confidence 0.24 |
| ramilevy | כורסת רביצה בואקום - | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): coriander (כוסברה): similarity 0.11 \| critical unknown product_type, state \| ambiguous with parsley \| level any_brand, confidence 0.24 |
| ramilevy | פתיתי ביצים ילד | ? / ? | - | -  | - | rejected (confidence 0.41 < 0.6): eggs-m (ביצים M): similarity 0.46 \| critical unknown product_type \| ambiguous with eggs-l \| level any_brand, confidence 0.41 |
| ramilevy | כורסת רביצה בואקום - | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): coriander (כוסברה): similarity 0.11 \| critical unknown product_type, state \| ambiguous with parsley \| level any_brand, confidence 0.24 |
| ramilevy | חטיף חלביצה 200 גר | ? / ? | - | 200 g | - | rejected (confidence 0.28 < 0.6): bamba (חטיף בוטנים (במבה)): similarity 0.30 \| critical unknown product_type \| soft differs pack_size 200 vs 80 g \| level close, confidence 0.28 \| vetoed: halva (חלבה): similarity 0.25 \| critical m |
| ramilevy | ביצים גדולות לארג 12 | L / 12 | - | 12 unit | - | rejected (confidence 0.38 < 0.6): eggs-l (ביצים L): similarity 0.42 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.38 |
| ramilevy | גומי ביצה בשקית 500 | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): eggs-xl (ביצים XL): similarity 0.19 \| critical unknown product_type \| ambiguous with tea-black \| level any_brand, confidence 0.24 |
| ramilevy | נודלס ביצים להקפצה ו | ? / ? | - | -  | - | rejected (confidence 0.42 < 0.6): eggs-m (ביצים M): similarity 0.48 \| critical unknown product_type \| ambiguous with eggs-l \| level any_brand, confidence 0.42 |
| ramilevy | נודלס ביצים מסולסלות | ? / ? | - | -  | - | rejected (confidence 0.39 < 0.6): eggs-m (ביצים M): similarity 0.44 \| critical unknown product_type \| ambiguous with eggs-l \| level any_brand, confidence 0.39 |
| ramilevy | ביצים 30 יח גדול L | L / 30 | - | 30 unit | - | rejected (confidence 0.56 < 0.6): eggs-l (ביצים L): similarity 0.65 \| critical unknown product_type \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.56 |
| ramilevy | ביצי אומגה 12יח L | L / 12 | - | 12 unit | - | rejected (confidence 0.43 < 0.6): eggs-free-range-l (ביצי חופש L): similarity 0.49 \| critical unknown product_type \| level any_brand, confidence 0.43 |
| ramilevy | ביצים חופש 12 יחידות | ? / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 0.80 review | review: eggs-free-range-l (ביצי חופש L): similarity 0.50 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 0.80 \| vetoed: eggs-l (ביצים L): similarity 0.44 \| critical mismatch product_type eggs_free_ran |
| ramilevy | ביצים 12 יח' גודל L | L / 12 | - | 12 unit | - | rejected (confidence 0.53 < 0.6): eggs-l (ביצים L): similarity 0.61 \| critical unknown product_type \| level any_brand, confidence 0.53 |
| osherad | ביצים 2*30 יח' בינונ | M / 60 | - | 60 unit | - | rejected (confidence 0.43 < 0.6): eggs-l (ביצים L): similarity 0.49 \| critical unknown product_type \| soft differs pack_size 60 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.43 |
| osherad | ביצים 30 יח בינוני ל | M / 30 | - | 30 unit | - | rejected (confidence 0.42 < 0.6): eggs-l (ביצים L): similarity 0.47 \| critical unknown product_type \| soft differs pack_size 30 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.42 |
| osherad | ביצים 18 יח' בינוני | M / 18 | - | 18 unit | - | rejected (confidence 0.45 < 0.6): eggs-l (ביצים L): similarity 0.51 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.45 |
| osherad | ביצים 30 יח' בינוני | M / 30 | - | 30 unit | - | rejected (confidence 0.44 < 0.6): eggs-l (ביצים L): similarity 0.50 \| critical unknown product_type \| soft differs pack_size 30 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.44 |
| osherad | ביצים 30 יח' גדול מן | L / 30 | - | 30 unit | - | rejected (confidence 0.40 < 0.6): eggs-l (ביצים L): similarity 0.45 \| critical unknown product_type \| soft differs pack_size 30 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.40 |
| osherad | ביצים 18 יח' גדול מן | L / 18 | - | 18 unit | - | rejected (confidence 0.41 < 0.6): eggs-l (ביצים L): similarity 0.46 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.41 |
| osherad | ביצים אורגני 12 יח' | ? / 12 | - | 12 unit | - | rejected (confidence 0.41 < 0.6): eggs-m (ביצים M): similarity 0.47 \| critical unknown product_type \| ambiguous with eggs-l \| level any_brand, confidence 0.41 |
| osherad | ביצי חופש 20 יח' גדו | ? / 20 | eggs_free_range_l | 20 unit | eggs-free-range-l close 0.89 review | review: eggs-free-range-l (ביצי חופש L): similarity 0.62 \| critical match product_type=eggs_free_range_l \| soft differs pack_size 20 vs 12 unit \| level close, confidence 0.89 \| vetoed: eggs-xl (ביצים XL): similarity 0.25 \| critica |
| osherad | ביצי אומגה 30 יח' בי | ? / 30 | - | 30 unit | - | rejected (confidence 0.24 < 0.6): garbage-bags (שקיות אשפה): similarity 0.06 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| osherad | ביצי חופש 20 יח' גדו | ? / 20 | eggs_free_range_l | 20 unit | eggs-free-range-l close 0.89 review | review: eggs-free-range-l (ביצי חופש L): similarity 0.62 \| critical match product_type=eggs_free_range_l \| soft differs pack_size 20 vs 12 unit \| level close, confidence 0.89 \| vetoed: eggs-xl (ביצים XL): similarity 0.25 \| critica |
| osherad | ביצים אורגניות  12 י | ? / 12 | - | 12 unit | - | rejected (confidence 0.39 < 0.6): eggs-m (ביצים M): similarity 0.44 \| critical unknown product_type \| ambiguous with eggs-l \| level any_brand, confidence 0.39 |
| osherad | פורס ביצים אולינהום | ? / ? | - | -  | - | rejected (confidence 0.45 < 0.6): eggs-l (ביצים L): similarity 0.51 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.45 |
| osherad | ביצים 18 יח גדול לסר | L / 18 | - | 18 unit | - | rejected (confidence 0.40 < 0.6): eggs-l (ביצים L): similarity 0.45 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.40 |
| osherad | ביצים 18 יח בינוני ל | M / 18 | - | 18 unit | - | rejected (confidence 0.42 < 0.6): eggs-l (ביצים L): similarity 0.48 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.42 |
| osherad | ג'ל ביצת עין וס.קופצ | ? / ? | - | 98 g | - | rejected (confidence 0.24 < 0.6): cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.16 \| critical unknown product_type, fat_pct, flavor \| soft differs pack_size 98 vs 200 g \| ambiguous with couscous \| level close, confide |
| osherad | מארז ביצים בינוני 2* | M / ? | - | 60 unit | - | rejected (confidence 0.43 < 0.6): eggs-l (ביצים L): similarity 0.49 \| critical unknown product_type \| soft differs pack_size 60 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.43 |
| osherad | ביצים אומגה 30 יח גד | ? / 30 | - | 30 unit | - | rejected (confidence 0.24 < 0.6): garbage-bags (שקיות אשפה): similarity 0.06 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| osherad | ביצים אומגה 12 יח גד | ? / 12 | - | 12 unit | - | rejected (confidence 0.37 < 0.6): eggs-l (ביצים L): similarity 0.42 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.37 |
| osherad | ביצים חופש 12 יח גדו | ? / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 0.78 review | review: eggs-free-range-l (ביצי חופש L): similarity 0.47 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 0.78 \| vetoed: eggs-l (ביצים L): similarity 0.43 \| critical mismatch product_type eggs_free_ran |
| osherad | ביצים אומגה 12 יח' ב | ? / 12 | - | 12 unit | - | rejected (confidence 0.39 < 0.6): eggs-l (ביצים L): similarity 0.44 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.39 |
| osherad | ביצים 12 יח' ענק א. | XL / 12 | - | 12 unit | - | rejected (confidence 0.40 < 0.6): eggs-m (ביצים M): similarity 0.45 \| critical unknown product_type \| level any_brand, confidence 0.40 |
| osherad | ג'ל ביצת עין וס.קופצ | ? / ? | - | 168 g | - | rejected (confidence 0.24 < 0.6): cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.16 \| critical unknown product_type, fat_pct, flavor \| soft differs pack_size 168 vs 200 g \| ambiguous with couscous \| level close, confid |
| osherad | ביצים 12 יח בינוני ר | M / 12 | - | 12 unit | - | rejected (confidence 0.41 < 0.6): eggs-l (ביצים L): similarity 0.46 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.41 |
| osherad | ביצים 12 יח ענק XL ל | XL / 12 | - | 12 unit | - | rejected (confidence 0.50 < 0.6): eggs-xl (ביצים XL): similarity 0.57 \| critical unknown product_type \| level any_brand, confidence 0.50 |
| osherad | ביצים 12 יח' בינוני | M / 12 | - | 12 unit | - | rejected (confidence 0.43 < 0.6): eggs-l (ביצים L): similarity 0.48 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.43 |
| osherad | ביצי אומגה 30 יח' גד | ? / 30 | - | 30 unit | - | rejected (confidence 0.24 < 0.6): garbage-bags (שקיות אשפה): similarity 0.06 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| osherad | ביצים 12 יח' גדול זג | L / 12 | - | 12 unit | - | rejected (confidence 0.38 < 0.6): eggs-l (ביצים L): similarity 0.42 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.38 |
| yohananof | ביצי דג שיבוט 200 גר | ? / ? | - | 200 g | - | rejected (confidence 0.24 < 0.6): rolled-oats (שיבולת שועל): similarity 0.23 \| critical unknown product_type \| soft differs pack_size 200 vs 500 g \| ambiguous with green-beans-frozen \| level close, confidence 0.24 |
| yohananof | ביצים אורגני 12 יח ג | ? / 12 | - | 12 unit | - | rejected (confidence 0.39 < 0.6): eggs-m (ביצים M): similarity 0.44 \| critical unknown product_type \| ambiguous with eggs-l \| level any_brand, confidence 0.39 |
| yohananof | ביצי חופש 12 יח גדול | L / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 0.89 review | review: eggs-free-range-l (ביצי חופש L): similarity 0.61 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 0.89 \| vetoed: eggs-xl (ביצים XL): similarity 0.22 \| critical mismatch product_type eggs_free_r |
| yohananof | ביצים 12 יח גדול | L / 12 | - | 12 unit | - | rejected (confidence 0.43 < 0.6): eggs-l (ביצים L): similarity 0.49 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.43 |
| yohananof | ביצים 12 יח בינוני | M / 12 | - | 12 unit | - | rejected (confidence 0.43 < 0.6): eggs-l (ביצים L): similarity 0.48 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.43 |
| yohananof | ביצים אורגני 12 יח ב | ? / 12 | - | 12 unit | - | rejected (confidence 0.40 < 0.6): eggs-m (ביצים M): similarity 0.45 \| critical unknown product_type \| ambiguous with eggs-l \| level any_brand, confidence 0.40 |
| yohananof | ביצים אורגני 12 יח ע | ? / 12 | - | 12 unit | - | rejected (confidence 0.39 < 0.6): eggs-m (ביצים M): similarity 0.44 \| critical unknown product_type \| ambiguous with eggs-l \| level any_brand, confidence 0.39 |
| yohananof | ביצים אומגה 3  12 יח | ? / 12 | - | 12 unit | - | rejected (confidence 0.38 < 0.6): eggs-l (ביצים L): similarity 0.42 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.38 |
| yohananof | ביצים אומגה 3 גדול 1 | L / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): green-onion (בצל ירוק): similarity 0.07 \| critical unknown product_type, state \| ambiguous with parsley \| level any_brand, confidence 0.24 |
| yohananof | ביצי חופש | ? / ? | eggs_free_range_l | 1 unit | eggs-free-range-l close 1.00 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.89 \| critical match product_type=eggs_free_range_l \| soft differs pack_size 1 vs 12 unit \| level close, confidence 1.00 \| vetoed: eggs-xl (ביצים XL): similarity 0.35 \| critical |
| yohananof | ביצים אומגה 3 גדול | L / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): green-onion (בצל ירוק): similarity 0.07 \| critical unknown product_type, state \| ambiguous with parsley \| level any_brand, confidence 0.24 |
| yohananof | פורס ביצים | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): parsley (פטרוזיליה): similarity 0.06 \| critical unknown product_type, state \| ambiguous with cling-wrap \| level any_brand, confidence 0.24 |
| yohananof | פורס ביצים כפול | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): parsley (פטרוזיליה): similarity 0.05 \| critical unknown product_type, state \| ambiguous with green-onion \| level any_brand, confidence 0.24 |
| yohananof | פורס ביצים BETTER | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): cling-wrap (ניילון נצמד): similarity 0.06 \| critical unknown product_type \| ambiguous with baguette \| level any_brand, confidence 0.24 |
| yohananof | ביצים 12 יח בינוני | M / 12 | - | 12 unit | - | rejected (confidence 0.43 < 0.6): eggs-l (ביצים L): similarity 0.48 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.43 |
| yohananof | ביצים 12 יח  גדול | L / 12 | - | 12 unit | - | rejected (confidence 0.43 < 0.6): eggs-l (ביצים L): similarity 0.49 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.43 |
| yohananof | ביצים 18 יח בינוני | M / 18 | - | 18 unit | - | rejected (confidence 0.45 < 0.6): eggs-l (ביצים L): similarity 0.51 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.45 |
| yohananof | ביצים 18 יח גדול | L / 18 | - | 18 unit | - | rejected (confidence 0.44 < 0.6): eggs-l (ביצים L): similarity 0.50 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.44 |
| yohananof | ביצים 30 יח בינוני | M / 30 | - | 30 unit | - | rejected (confidence 0.44 < 0.6): eggs-l (ביצים L): similarity 0.50 \| critical unknown product_type \| soft differs pack_size 30 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.44 |
| yohananof | ביצים 30 יח גדול | L / 30 | - | 30 unit | - | rejected (confidence 0.24 < 0.6): garbage-bags (שקיות אשפה): similarity 0.05 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| yohananof | ביצים 30 יח ענק | XL / 30 | - | 30 unit | - | rejected (confidence 0.24 < 0.6): garbage-bags (שקיות אשפה): similarity 0.05 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| yohananof | ביצים 30 יח בינוני | M / 30 | - | 30 unit | - | rejected (confidence 0.44 < 0.6): eggs-l (ביצים L): similarity 0.50 \| critical unknown product_type \| soft differs pack_size 30 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.44 |
| yohananof | ביצים 12 יח גדול | L / 12 | - | 12 unit | - | rejected (confidence 0.43 < 0.6): eggs-l (ביצים L): similarity 0.49 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.43 |
| yohananof | ביצים 12 יח בינוני | M / 12 | - | 12 unit | - | rejected (confidence 0.43 < 0.6): eggs-l (ביצים L): similarity 0.48 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.43 |
| yohananof | ביצים 18 יח גדול | L / 18 | - | 18 unit | - | rejected (confidence 0.44 < 0.6): eggs-l (ביצים L): similarity 0.50 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.44 |
| yohananof | ביצים 18 יח בינוני | M / 18 | - | 18 unit | - | rejected (confidence 0.45 < 0.6): eggs-l (ביצים L): similarity 0.51 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.45 |
| yohananof | ביצים אורגני 12 יח ג | ? / 12 | - | 12 unit | - | rejected (confidence 0.39 < 0.6): eggs-m (ביצים M): similarity 0.44 \| critical unknown product_type \| ambiguous with eggs-l \| level any_brand, confidence 0.39 |
| yohananof | ביצים אומגה 12 יח גד | ? / 12 | - | 12 unit | - | rejected (confidence 0.37 < 0.6): eggs-l (ביצים L): similarity 0.42 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.37 |
| yohananof | ביצי חופש 12 יח גדול | L / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 0.89 review | review: eggs-free-range-l (ביצי חופש L): similarity 0.61 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 0.89 \| vetoed: eggs-xl (ביצים XL): similarity 0.22 \| critical mismatch product_type eggs_free_r |
| yohananof | ביצי חופש 12 יח בינו | ? / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 0.92 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.65 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 0.92 \| vetoed: eggs-xl (ביצים XL): similarity 0.28 \| critical mismatch product_type eggs_free_r |
| yohananof | ביצים אומגה 12 יח בי | ? / 12 | - | 12 unit | - | rejected (confidence 0.41 < 0.6): eggs-l (ביצים L): similarity 0.47 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.41 |
| yohananof | ביצים 12 יח בינוני | M / 12 | - | 12 unit | - | rejected (confidence 0.43 < 0.6): eggs-l (ביצים L): similarity 0.48 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.43 |
| yohananof | פורס ביצים סולתם | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): green-onion (בצל ירוק): similarity 0.05 \| critical unknown product_type, state \| ambiguous with cling-wrap \| level any_brand, confidence 0.24 |
| yohananof | מגירת ביצים נתלית אק | ? / ? | - | 160 g | - | rejected (confidence 0.37 < 0.6): egg-noodles (אטריות ביצים): similarity 0.41 \| critical unknown product_type \| soft differs pack_size 160 vs 500 g \| level close, confidence 0.37 |
| yohananof | ביצים 12 יח ענק | XL / 12 | - | 12 unit | - | rejected (confidence 0.44 < 0.6): eggs-m (ביצים M): similarity 0.50 \| critical unknown product_type \| level any_brand, confidence 0.44 |
| yohananof | ביצי דג טונה אדמחוט | ? / ? | - | 85 g | - | rejected (confidence 0.33 < 0.6): tuna-in-oil (טונה בשמן): similarity 0.36 \| critical unknown product_type \| soft differs pack_size 85 vs 640 g \| ambiguous with tuna-in-water \| level close, confidence 0.33 |
| yohananof | ביצת עין 220 גרם | ? / ? | - | 220 g | - | rejected (confidence 0.24 < 0.6): cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.15 \| critical unknown product_type, fat_pct, flavor \| soft differs pack_size 220 vs 200 g \| ambiguous with sunflower-seeds \| level close, |
| yohananof | ביצים עלומות 200 גרם | ? / ? | - | 200 g | - | rejected (confidence 0.24 < 0.6): sunflower-seeds (גרעינים): similarity 0.17 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| yohananof | ביצים 18 יח בינוני | M / 18 | - | 18 unit | - | rejected (confidence 0.45 < 0.6): eggs-l (ביצים L): similarity 0.51 \| critical unknown product_type \| soft differs pack_size 18 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.45 |
| yohananof | ביצי דג בורי אדמחוט | ? / ? | - | 125 g | - | rejected (confidence 0.24 < 0.6): burekas-potato (בורקס תפוחי אדמה קפוא): similarity 0.24 \| critical unknown product_type, flavor \| soft differs pack_size 125 vs 800 g \| ambiguous with egg-noodles \| level close, confidence 0.24 |
| yohananof | ביצה קשה | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): lettuce (חסה): similarity 0.15 \| critical unknown product_type, state \| ambiguous with coriander \| level any_brand, confidence 0.24 |
| tivtaam | ביצי דג חדקן מומלחים | ? / ? | - | 50 g | - | rejected (confidence 0.24 < 0.6): potato-chips-salted (צ'יפס תפוחי אדמה בטעם מלח): similarity 0.14 \| critical unknown product_type, flavor \| level any_brand, confidence 0.24 |
| tivtaam | ביצי דג חדקן מומלחים | ? / ? | - | 100 g | - | rejected (confidence 0.24 < 0.6): egg-noodles (אטריות ביצים): similarity 0.20 \| critical unknown product_type \| soft differs pack_size 100 vs 500 g \| ambiguous with bread-multigrain \| level close, confidence 0.24 |
| tivtaam | מעדן בטעם ביצי דג פלטוס 100 גרם | ? / ? | dairy_dessert | 100 g | - | rejected (confidence 0.42 < 0.6): dessert-vanilla (מעדן חלב וניל): similarity 0.24 \| critical match product_type=dairy_dessert \| critical unknown flavor \| soft differs pack_size 100 vs 125 g \| ambiguous with dessert-chocolate \| le |
| tivtaam | ביצי דג טרוטונית אטלנטי חסילונים 180 גר | ? / ? | - | 180 g | - | rejected (confidence 0.24 < 0.6): egg-noodles (אטריות ביצים): similarity 0.23 \| critical unknown product_type \| soft differs pack_size 180 vs 500 g \| ambiguous with sunflower-seeds \| level close, confidence 0.24 |
| tivtaam | ביצי דג שיבוט מומלח מצונן 130 גר | ? / ? | - | 130 g | - | rejected (confidence 0.24 < 0.6): salt (מלח): similarity 0.21 \| critical unknown product_type \| soft differs pack_size 130 vs 1000 g \| ambiguous with matzah \| level close, confidence 0.24 \| vetoed: chickpeas-canned (גרגרי חומוס בש |
| tivtaam | ביצי דג זהבנון מומלח מצונן 130 גר | ? / ? | - | 130 g | - | rejected (confidence 0.24 < 0.6): matzah (מצות): similarity 0.19 \| critical unknown product_type \| soft differs pack_size 130 vs 1000 g \| ambiguous with salt \| level close, confidence 0.24 \| vetoed: tilapia-fillet-frozen (פילה אמנ |
| tivtaam | איקרה ביצי דג טרוטונית והרינג 180 גרם | ? / ? | - | 180 g | - | rejected (confidence 0.24 < 0.6): green-beans-frozen (שעועית ירוקה קפואה): similarity 0.16 \| critical unknown product_type, state \| soft differs pack_size 180 vs 800 g \| ambiguous with egg-noodles \| level close, confidence 0.24 |
| tivtaam | איקרה ביצי דג טרוטונית והרינג עם פורל וס | ? / ? | - | 180 g | - | rejected (confidence 0.24 < 0.6): green-beans-frozen (שעועית ירוקה קפואה): similarity 0.15 \| critical unknown product_type, state \| soft differs pack_size 180 vs 800 g \| ambiguous with frozen-pizza \| level close, confidence 0.24 \| |
| tivtaam | נטוראה עוף וביצה 100% רכיבים טבעיים - 2 | ? / ? | - | -  | - | rejected (confidence 0.42 < 0.6): soup-powder-chicken (אבקת מרק עוף): similarity 0.18 \| critical match flavor=chicken \| critical unknown product_type \| level any_brand, confidence 0.42 |
| tivtaam | ביצי דג מויבה במשקל | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): sweet-potato (בטטה): similarity 0.12 \| critical unknown product_type, state \| ambiguous with chicken-schnitzel-fresh \| level any_brand, confidence 0.24 |
| tivtaam | פריזר ביצה במשקל | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): chicken-schnitzel-fresh (שניצל עוף טרי (חזה פרוס)): similarity 0.20 \| critical unknown product_type, state \| ambiguous with beef-ground-fresh \| level any_brand, confidence 0.24 |
| tivtaam | שימורי ביצי דג מינטאי מעושן פמלי פק 185 | ? / ? | - | 185 g | - | rejected (confidence 0.29 < 0.6): smoked-salmon-sliced (סלמון מעושן פרוס): similarity 0.31 \| critical unknown product_type \| soft differs pack_size 185 vs 100 g \| level close, confidence 0.29 \| vetoed: sweet-corn-canned (תירס מתוק |
| tivtaam | איטריות ביצים 500 גרם Bechtle | ? / ? | - | 500 g | - | rejected (confidence 0.47 < 0.6): egg-noodles (אטריות ביצים): similarity 0.53 \| critical unknown product_type \| level any_brand, confidence 0.47 |
| tivtaam | איטריות ביצים רחבות 500 גרם Bechtle | ? / ? | - | 500 g | - | rejected (confidence 0.45 < 0.6): egg-noodles (אטריות ביצים): similarity 0.51 \| critical unknown product_type \| level any_brand, confidence 0.45 |
| tivtaam | איטריות ביצים קלאסי 500 גרם Bechtle | ? / ? | - | 500 g | - | rejected (confidence 0.43 < 0.6): egg-noodles (אטריות ביצים): similarity 0.49 \| critical unknown product_type \| level any_brand, confidence 0.43 |
| tivtaam | ביצים אריזון 12 גדול | L / 12 | - | 1 unit | - | rejected (confidence 0.24 < 0.6): cling-wrap (ניילון נצמד): similarity 0.08 \| critical unknown product_type \| ambiguous with parsley \| level any_brand, confidence 0.24 |
| tivtaam | ביצים אריזון 12 בינוני | M / 12 | - | 1 unit | - | rejected (confidence 0.24 < 0.6): cling-wrap (ניילון נצמד): similarity 0.07 \| critical unknown product_type \| ambiguous with baguette \| level any_brand, confidence 0.24 |
| tivtaam | ביצים אריזון 18 גדול | L / 18 | - | 1 unit | - | rejected (confidence 0.24 < 0.6): cling-wrap (ניילון נצמד): similarity 0.08 \| critical unknown product_type \| ambiguous with green-onion \| level any_brand, confidence 0.24 |
| tivtaam | ביצים אריזון 18 בינוני | M / 18 | - | 1 unit | - | rejected (confidence 0.24 < 0.6): cling-wrap (ניילון נצמד): similarity 0.07 \| critical unknown product_type \| ambiguous with baguette \| level any_brand, confidence 0.24 |
| tivtaam | ביצים אומגה 3 30 יח M | M / 30 | - | 30 unit | - | rejected (confidence 0.24 < 0.6): garbage-bags (שקיות אשפה): similarity 0.06 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| tivtaam | ביצים אורגניות 12 יח L | L / 12 | - | 12 unit | - | rejected (confidence 0.51 < 0.6): eggs-l (ביצים L): similarity 0.59 \| critical unknown product_type \| level any_brand, confidence 0.51 |
| tivtaam | ביצים אומגה 3 12 יח L | L / 12 | - | 12 unit | - | rejected (confidence 0.51 < 0.6): eggs-l (ביצים L): similarity 0.58 \| critical unknown product_type \| level any_brand, confidence 0.51 |
| tivtaam | ביצי חופש 12 יח L | L / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 1.00 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.83 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 1.00 \| vetoed: eggs-l (ביצים L): similarity 0.40 \| critical mismatch product_type eggs_free_ran |
| tivtaam | ביצי חופש 12 יח M | M / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 0.93 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.66 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 0.93 \| vetoed: eggs-m (ביצים M): similarity 0.40 \| critical mismatch product_type eggs_free_ran |
| tivtaam | ביצים אומגה M 12 יח | M / 12 | - | 12 unit | - | rejected (confidence 0.54 < 0.6): eggs-m (ביצים M): similarity 0.62 \| critical unknown product_type \| level any_brand, confidence 0.54 |
| tivtaam | ביצי דג אילתית 190 גר | ? / ? | - | 190 g | - | rejected (confidence 0.24 < 0.6): egg-noodles (אטריות ביצים): similarity 0.20 \| critical unknown product_type \| soft differs pack_size 190 vs 500 g \| ambiguous with green-beans-frozen \| level close, confidence 0.24 |
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
| tivtaam | כדור תה (ביצה) | ? / ? | tea_black | 1 unit | tea-black close 0.63 review | review: tea-black (תה שחור בשקיקים): similarity 0.29 \| critical match product_type=tea_black \| soft differs pack_size 1 vs 100 unit \| level close, confidence 0.63 |
| tivtaam | חותך ביצים נירוסטה | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): facial-tissues (ממחטות נייר): similarity 0.12 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| tivtaam | חותך ביצים 3 ב 1 | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): parsley (פטרוזיליה): similarity 0.07 \| critical unknown product_type, state \| ambiguous with green-onion \| level any_brand, confidence 0.24 |
| tivtaam | ביצי שליו 20 יח | ? / 20 | - | 20 unit | - | rejected (confidence 0.34 < 0.6): eggs-free-range-l (ביצי חופש L): similarity 0.37 \| critical unknown product_type \| soft differs pack_size 20 vs 12 unit \| level close, confidence 0.34 |
| tivtaam | מארז ביצות עין Yo Egg 220 גרם | ? / ? | - | 220 g | - | rejected (confidence 0.24 < 0.6): sunflower-seeds (גרעינים): similarity 0.20 \| critical unknown product_type \| soft differs pack_size 220 vs 200 g \| ambiguous with bisli-grill \| level close, confidence 0.24 |
| tivtaam | בירה קרושוביצה  500 מ"ל פחית | ? / ? | lager_beer | 500 ml | lager-beer any_brand 0.68 review | review: lager-beer (בירה לאגר): similarity 0.35 \| critical match product_type=lager_beer \| level any_brand, confidence 0.68 \| vetoed: red-wine-dry (יין אדום יבש): similarity 0.00 \| critical mismatch product_type lager_beer vs red_ |
| tivtaam | ליקר בולס אדבוקט ליקר ביצים 700 מ"ל | ? / ? | - | 700 ml | - | rejected (confidence 0.25 < 0.6): lemon-lime-soda (משקה מוגז לימון-ליים): similarity 0.26 \| critical unknown product_type \| soft differs pack_size 700 vs 1500 ml \| ambiguous with flavored-water-lemon \| level close, confidence 0.25 |
| tivtaam | סביצה סלמון | ? / ? | salmon_fillet | -  | salmon-fillet-fresh any_brand 0.62 review | review: salmon-fillet-fresh (פילה סלמון טרי): similarity 0.50 \| critical match product_type=salmon_fillet \| critical unknown state \| level any_brand, confidence 0.62 \| vetoed: sea-bream-fresh (דניס שלם טרי): similarity 0.00 \| crit |
| tivtaam | סביצה ילוטייל | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): salmon-fillet-fresh (פילה סלמון טרי): similarity 0.09 \| critical unknown product_type, state \| ambiguous with lemon \| level any_brand, confidence 0.24 |
| tivtaam | ביצי דג אלתית גבנוני | ? / ? | - | 250 g | - | rejected (confidence 0.24 < 0.6): safed-cheese-5 (גבינה צפתית 5%): similarity 0.23 \| critical unknown product_type, fat_pct \| ambiguous with white-cheese-9 \| level any_brand, confidence 0.24 |
| tivtaam | ביצי דג פורל מומלחים | ? / ? | - | 250 g | - | rejected (confidence 0.24 < 0.6): pretzels (בייגלה): similarity 0.13 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| tivtaam | שימורי ביצי דג מינטאי פמלי פק 185 גר | ? / ? | - | 185 g | - | rejected (confidence 0.45 < 0.6): chickpeas-canned (גרגרי חומוס בשימורים): similarity 0.29 \| critical match state=canned \| critical unknown product_type \| soft differs pack_size 185 vs 400 g \| level close, confidence 0.45 \| vetoed |
| tivtaam | ביצי דג אלתית אלסקה 500 גרם כשר | ? / ? | - | 500 g | - | rejected (confidence 0.24 < 0.6): egg-noodles (אטריות ביצים): similarity 0.19 \| critical unknown product_type \| ambiguous with frozen-pizza \| level any_brand, confidence 0.24 |
| tivtaam | ביצי דג שחור בופן במלח מצונן 113 גר | ? / ? | salt | 113 g | salt close 0.60 review | review: salt (מלח): similarity 0.18 \| critical match product_type=salt \| soft differs pack_size 113 vs 1000 g \| level close, confidence 0.60 \| vetoed: bulgur (בורגול): similarity 0.24 \| critical mismatch product_type salt vs bulgu |
| tivtaam | ביצה פלוס 12 יח L | L / 12 | - | 12 unit | - | rejected (confidence 0.29 < 0.6): eggs-l (ביצים L): similarity 0.32 \| critical unknown product_type \| ambiguous with eggs-free-range-l \| level any_brand, confidence 0.29 |
| tivtaam | ביצי חופש 12 יח | ? / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 0.97 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.72 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 0.97 \| vetoed: eggs-xl (ביצים XL): similarity 0.25 \| critical mismatch product_type eggs_free_r |

#### `hummus-plain`: 72 listed of 465 name hits (0 skipped as not the food itself; chains looked in: mega, king_store, ramilevy, osherad, yohananof, tivtaam)

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

#### `milk-fresh-3`: 24 listed of 990 name hits (0 skipped as not the food itself; chains looked in: osherad, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| osherad | שוקולד פרה חלב סוכרי | ? / ? | chocolate_bar | 90 g | chocolate-milk-bar close 0.96 | accept: chocolate-milk-bar (שוקולד חלב): similarity 0.70 \| critical match product_type=chocolate_bar, flavor=milk \| soft differs pack_size 90 vs 100 g \| level close, confidence 0.96 \| vetoed: chocolate-dark-bar (שוקולד מריר): simi |
| osherad | מעדן חלב מעושר בחלבו | ? / ? | dairy_dessert | 150 g | dessert-vanilla close 0.70 review | review: dessert-vanilla (מעדן חלב וניל): similarity 0.60 \| critical match product_type=dairy_dessert \| critical unknown flavor \| soft differs pack_size 150 vs 125 g \| ambiguous with dessert-chocolate \| level close, confidence 0.70 |
| osherad | מעדן חלב עם שוקולד פ | ? / ? | dairy_dessert | 150 g | dessert-chocolate close 1.00 | accept: dessert-chocolate (מעדן חלב שוקולד): similarity 0.86 \| critical match product_type=dairy_dessert, flavor=chocolate \| soft differs pack_size 150 vs 125 g \| level close, confidence 1.00 \| vetoed: pudding-chocolate-cream (מעד |
| osherad | חלב 3% תנובה 1.5 ליט | ? / ? | milk | 1500 ml | milk-fresh-3 close 0.66 review | review: milk-fresh-3 (חלב טרי 3%): similarity 0.47 \| critical match product_type=milk, fat_pct=3 \| critical unknown state \| soft differs pack_size 1500 vs 1000 ml \| level close, confidence 0.66 \| vetoed: milk-long-life-3 (חלב עמיד |
| osherad | חלב נטול לקטוז 2% טר | ? / ? | - | -  | milk-lactose-free-2 any_brand 0.78 review | review: milk-lactose-free-2 (חלב ללא לקטוז 2%): similarity 0.70 \| critical match fat_pct=2 \| critical unknown product_type \| level any_brand, confidence 0.78 \| vetoed: milk-fresh-3 (חלב טרי 3%): similarity 0.35 \| critical mismatch |
| osherad | ריבת חלב אמיתי מיה 3 | ? / ? | jam | 340 g | - | rejected (confidence 0.50 < 0.6): jam-strawberry (ריבת תות): similarity 0.35 \| critical match product_type=jam \| critical unknown flavor \| level any_brand, confidence 0.50 \| vetoed: ptitim (פתיתים אפויים): similarity 0.12 \| critic |
| osherad | פוליויקס סחלבים 4 לי | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): grapes (ענבים): similarity 0.16 \| critical unknown product_type, state \| ambiguous with lemon-lime-soda \| level any_brand, confidence 0.24 |
| osherad | חלב 3% תנובה 1 ליטר | ? / ? | milk | 1000 ml | milk-fresh-3 any_brand 0.69 review | review: milk-fresh-3 (חלב טרי 3%): similarity 0.51 \| critical match product_type=milk, fat_pct=3 \| critical unknown state \| level any_brand, confidence 0.69 \| vetoed: milk-long-life-3 (חלב עמיד 3%): similarity 0.47 \| critical mism |
| osherad | חלב פרוטאין מועשר בח | ? / ? | milk | -  | - | rejected (confidence 0.38 < 0.6): milk-fresh-3 (חלב טרי 3%): similarity 0.28 \| critical match product_type=milk \| critical unknown fat_pct, state \| ambiguous with milk-fresh-1 \| level any_brand, confidence 0.38 \| vetoed: dessert-c |
| osherad | אבקת חלבון בטעם וניל | ? / ? | - | -  | - | rejected (confidence 0.32 < 0.6): laundry-powder (אבקת כביסה): similarity 0.35 \| critical unknown product_type \| level any_brand, confidence 0.32 \| vetoed: dessert-vanilla (מעדן חלב וניל): similarity 0.43 \| critical mismatch name  |
| osherad | אבקת חלבון בטעם שוקו | ? / ? | - | -  | - | rejected (confidence 0.30 < 0.6): laundry-powder (אבקת כביסה): similarity 0.33 \| critical unknown product_type \| ambiguous with soup-powder-chicken \| level any_brand, confidence 0.30 \| vetoed: chocolate-milk (שוקו): similarity 0.4 |
| osherad | חלב 3% טרה 2 ליטר | ? / ? | milk | 2000 ml | milk-fresh-3 close 0.87 review | review: milk-fresh-3 (חלב טרי 3%): similarity 0.59 \| critical match product_type=milk, fat_pct=3, state=fresh \| soft differs pack_size 2000 vs 1000 ml \| level close, confidence 0.87 \| vetoed: milk-long-life-3 (חלב עמיד 3%): simila |
| tivtaam | עוגיות שוקולד חלב מקדמיה סוסליטו 204 גרם | ? / ? | - | 204 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.50 \| critical mismatch flavor chocolate vs milk; name has 'עוגיות' (a derived product), canonical is 'שוקולד חלב' \| critical unknown product_type ; des |
| tivtaam | בד"צ טורינו חלב חמישייה 23X5ג 115ג | ? / ? | milk | 115 g | - | every candidate vetoed \| vetoed: dessert-chocolate (מעדן חלב שוקולד): similarity 0.16 \| critical mismatch product_type milk vs dairy_dessert \| critical unknown flavor ; dessert-vanilla (מעדן חלב וניל): similarity 0.16 \| critical m |
| tivtaam | עוגיות סנדוויץ שוקולד חלב 285 גרם BN | ? / ? | - | 285 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.52 \| critical mismatch flavor chocolate vs milk; name has 'עוגיות' (a derived product), canonical is 'שוקולד חלב' \| critical unknown product_type ; des |
| tivtaam | חלבה במשקל | ? / ? | halva | -  | - | no candidates in block snacks / kg |
| tivtaam | פיסטוק חלבי מקולף | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): salmon-fillet-fresh (פילה סלמון טרי): similarity 0.16 \| critical unknown product_type, state \| ambiguous with broccoli-fresh \| level any_brand, confidence 0.24 |
| tivtaam | פיסטוק חלבי לא קלוי | ? / ? | - | -  | - | rejected (confidence 0.24 < 0.6): salmon-fillet-fresh (פילה סלמון טרי): similarity 0.13 \| critical unknown product_type, state \| ambiguous with chicken-schnitzel-fresh \| level any_brand, confidence 0.24 |
| tivtaam | ריבת חלב צימבוטה 430 גרם | ? / ? | jam | 430 g | - | rejected (confidence 0.48 < 0.6): jam-strawberry (ריבת תות): similarity 0.32 \| critical match product_type=jam \| critical unknown flavor \| soft differs pack_size 430 vs 340 g \| level close, confidence 0.48 \| vetoed: peanut-butter  |
| tivtaam | גבינת רסטה טורקית 20% שומן חלב בקר | ? / ? | milk | -  | - | no candidates in block dairy / kg |
| tivtaam | סדרת ורדים בוטניקל חלב פנים גרנייה 200 מ | ? / ? | milk | 200 ml | - | rejected (confidence 0.36 < 0.6): milk-fresh-3 (חלב טרי 3%): similarity 0.20 \| critical match product_type=milk \| critical unknown fat_pct, state \| soft differs pack_size 200 vs 1000 ml \| ambiguous with milk-fresh-1 \| level close, |
| tivtaam | טריז-שוקולד חלב בטעם מנטה 90 גרם | ? / ? | chocolate_bar | 90 g | chocolate-milk-bar close 0.82 review | review: chocolate-milk-bar (שוקולד חלב): similarity 0.52 \| critical match product_type=chocolate_bar, flavor=milk \| soft differs pack_size 90 vs 100 g \| level close, confidence 0.82 \| vetoed: wafers-chocolate (ופלים בטעם שוקולד):  |
| tivtaam | קיט קאט-וופל בשוק. חלב בצק עוגיות 99 גר | ? / ? | wafers | 99 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.22 \| critical mismatch product_type wafers vs chocolate_bar; flavor chocolate vs milk; name has 'בצק' (a derived product), canonical is 'שוקולד חלב' ;  |
| tivtaam | קיט קאט-וופל בשוק. חלב בצק עוגיות 99 גר | ? / ? | wafers | 99 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.22 \| critical mismatch product_type wafers vs chocolate_bar; flavor chocolate vs milk; name has 'בצק' (a derived product), canonical is 'שוקולד חלב' ;  |

#### `pasta-spaghetti`: 62 listed of 125 name hits (0 skipped as not the food itself; chains looked in: mega, king_store, ramilevy, osherad, yohananof, tivtaam)

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

#### `white-cheese-5`: 12 listed of 19 name hits (0 skipped as not the food itself; chains looked in: osherad)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| osherad | משחת אורביטול הלבנה | ? / ? | labane | 435 g | - | rejected (confidence 0.42 < 0.6): labane-5 (לבנה 5%): similarity 0.22 \| critical match product_type=labane \| critical unknown fat_pct \| soft differs pack_size 435 vs 250 g \| level close, confidence 0.42 \| vetoed: white-cheese-9 (ג |
| osherad | משחת סנסודיין הלבנה | ? / ? | labane | -  | - | rejected (confidence 0.42 < 0.6): labane-5 (לבנה 5%): similarity 0.22 \| critical match product_type=labane \| critical unknown fat_pct \| level any_brand, confidence 0.42 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.22 \| c |
| osherad | שעועית לבנה ברוטב עג | ? / ? | white_beans | 580 g | - | every candidate vetoed \| vetoed: white-beans (שעועית לבנה יבשה): similarity 0.64 \| critical mismatch name has 'רוטב' (a derived product), canonical is 'שעועית לבנה יבשה'; name has 'ברוטב' (prepared or preserved), canonical is not  |
| osherad | טחינה לבנה אחלה 400 | ? / ? | tahini_raw | 400 g | tahini-raw close 0.71 review | review: tahini-raw (טחינה גולמית): similarity 0.39 \| critical match product_type=tahini_raw \| soft differs pack_size 400 vs 500 g \| level close, confidence 0.71 \| vetoed: white-beans (שעועית לבנה יבשה): similarity 0.37 \| critical  |
| osherad | שעועית לבנה שטראוס ב | ? / ? | white_beans | 380 g | white-beans close 0.91 | accept: white-beans (שעועית לבנה יבשה): similarity 0.64 \| critical match product_type=white_beans \| soft differs pack_size 380 vs 1000 g \| level close, confidence 0.91 \| vetoed: flour-white (קמח לבן): similarity 0.12 \| critical mi |
| osherad | איקרה לבנה דלידג 300 | ? / ? | labane | 300 g | - | rejected (confidence 0.54 < 0.6): labane-5 (לבנה 5%): similarity 0.40 \| critical match product_type=labane \| critical unknown fat_pct \| soft differs pack_size 300 vs 250 g \| level close, confidence 0.54 \| vetoed: white-cheese-3 (ג |
| osherad | שעועית לבנה ברוטב יכ | ? / ? | white_beans | 560 g | - | every candidate vetoed \| vetoed: white-beans (שעועית לבנה יבשה): similarity 0.66 \| critical mismatch name has 'רוטב' (a derived product), canonical is 'שעועית לבנה יבשה'; name has 'ברוטב' (prepared or preserved), canonical is not  |
| osherad | בפלות טורטית לבנה  3 | ? / ? | labane | 360 g | - | rejected (confidence 0.55 < 0.6): labane-5 (לבנה 5%): similarity 0.41 \| critical match product_type=labane \| critical unknown fat_pct \| soft differs pack_size 360 vs 250 g \| level close, confidence 0.55 \| vetoed: white-cheese-5 (ג |
| osherad | שעועית לבנה ערוגות 8 | ? / ? | white_beans | 800 g | white-beans close 0.91 | accept: white-beans (שעועית לבנה יבשה): similarity 0.64 \| critical match product_type=white_beans \| soft differs pack_size 800 vs 1000 g \| level close, confidence 0.91 \| vetoed: sugar-white (סוכר לבן): similarity 0.13 \| critical m |
| osherad | שעועית לבנה הנמל 1.2 | ? / ? | white_beans | -  | white-beans any_brand 0.90 | accept: white-beans (שעועית לבנה יבשה): similarity 0.63 \| critical match product_type=white_beans \| level any_brand, confidence 0.90 \| vetoed: sugar-white (סוכר לבן): similarity 0.13 \| critical mismatch product_type white_beans vs |
| osherad | שעועית לבנה אינדירה | ? / ? | white_beans | -  | white-beans any_brand 0.94 | accept: white-beans (שעועית לבנה יבשה): similarity 0.68 \| critical match product_type=white_beans \| level any_brand, confidence 0.94 \| vetoed: flour-white (קמח לבן): similarity 0.15 \| critical mismatch product_type white_beans vs  |
| osherad | שעועית לבנה סלקטד 90 | ? / ? | white_beans | 900 g | white-beans close 0.90 | accept: white-beans (שעועית לבנה יבשה): similarity 0.63 \| critical match product_type=white_beans \| soft differs pack_size 900 vs 1000 g \| level close, confidence 0.90 \| vetoed: sugar-white (סוכר לבן): similarity 0.16 \| critical m |

#### `yellow-cheese-sliced-28`: 60 listed of 365 name hits (0 skipped as not the food itself; chains looked in: mega, king_store, osherad, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| mega | גבינה מותכת גאודה 17 | ? / ? | yellow_cheese | 150 g | - | rejected (confidence 0.51 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.36 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| soft differs pack_size 150 vs 200 g \| ambiguous with yellow- |
| mega | גבינה מותכת גאודה 14 | ? / ? | yellow_cheese | 70 g | - | rejected (confidence 0.51 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.36 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| soft differs pack_size 70 vs 200 g \| ambiguous with yellow-c |
| mega | סיי ציז גבינת גאודה | ? / ? | yellow_cheese | 500 g | - | rejected (confidence 0.42 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.19 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| soft differs pack_size 500 vs 200 g \| ambiguous with yellow- |
| mega | שלגוני טעמקור 8 יחיד | ? / ? | - | 416 g | - | rejected (confidence 0.24 < 0.6): greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.16 \| critical unknown product_type, flavor \| soft differs pack_size 416 vs 200 g \| ambiguous with bread-standard \| level close, confidence 0.24 |
| mega | שלגון טעמקור XL 75 ג | ? / ? | - | 75 g | - | rejected (confidence 0.24 < 0.6): cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.08 \| critical unknown product_type, fat_pct, flavor \| soft differs pack_size 75 vs 200 g \| ambiguous with coffee-turkish \| level close, c |
| mega | נעם גבינה צהובה מגור | ? / ? | yellow_cheese | 500 g | yellow-cheese-sliced-9 close 0.68 review | review: yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.57 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| soft differs pack_size 500 vs 200 g \| ambiguous with yellow-cheese-sliced-28 \| level c |
| mega | נעם גבינה צהובה דק ד | ? / ? | yellow_cheese | 200 g | yellow-cheese-sliced-9 any_brand 0.68 review | review: yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.58 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| ambiguous with yellow-cheese-sliced-28 \| level any_brand, confidence 0.68 \| vetoed: wh |
| mega | נעם צהובה דק דק 22% | ? / ? | - | 200 g | - | rejected (confidence 0.24 < 0.6): frozen-pizza (פיצה קפואה): similarity 0.13 \| critical unknown product_type \| soft differs pack_size 200 vs 500 g \| ambiguous with bread-multigrain \| level close, confidence 0.24 \| vetoed: yellow-c |
| mega | שעועית צהובה חתוכה ס | ? / ? | - | 800 g | - | rejected (confidence 0.34 < 0.6): green-beans-frozen (שעועית ירוקה קפואה): similarity 0.38 \| critical unknown product_type, state \| level any_brand, confidence 0.34 |
| mega | עמק מהדרין 15% 200 ג | ? / ? | yellow_cheese | 200 g | - | every candidate vetoed \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.28 \| critical mismatch product_type yellow_cheese vs sour_cream \| critical match fat_pct=15 ; white-cheese-5 (גבינה לבנה 5%): similarity 0.10 \| critical |
| mega | עמק דק דק 28% 200 גר | ? / ? | yellow_cheese | 200 g | yellow-cheese-sliced-28 any_brand 0.60 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.16 \| critical match product_type=yellow_cheese, fat_pct=28 \| level any_brand, confidence 0.60 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.07 \| critic |
| mega | עמק סמי 28% 400 גרם. | ? / ? | yellow_cheese | 400 g | yellow-cheese-sliced-28 close 0.60 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.23 \| critical match product_type=yellow_cheese, fat_pct=28 \| soft differs pack_size 400 vs 200 g \| level close, confidence 0.60 \| vetoed: yellow-cheese-sliced-9 |
| king_store | גבינת עמק 28% במשקל תנובה | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| king_store | טל עמק חריץ 32% | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| king_store | גבינת דק דק 28% 200 ג' עמק | ? / ? | yellow_cheese | 200 g | yellow-cheese-sliced-28 any_brand 0.60 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.25 \| critical match product_type=yellow_cheese, fat_pct=28 \| level any_brand, confidence 0.60 \| vetoed: cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity |
| king_store | המעדניה של עמק 28% 400 ג' | ? / ? | yellow_cheese | 400 g | yellow-cheese-sliced-28 close 0.60 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.19 \| critical match product_type=yellow_cheese, fat_pct=28 \| soft differs pack_size 400 vs 200 g \| level close, confidence 0.60 \| vetoed: pudding-chocolate-crea |
| king_store | שעועית צהובה חתוכה 800 ג' סנפרוסט | ? / ? | - | 800 g | - | rejected (confidence 0.27 < 0.6): green-beans-frozen (שעועית ירוקה קפואה): similarity 0.28 \| critical unknown product_type, state \| level any_brand, confidence 0.27 |
| king_store | צהובה פרוסה ריץ 1 ק"ג | ? / ? | - | 1000 g | - | rejected (confidence 0.24 < 0.6): salmon-fillet-frozen (פילה סלמון קפוא): similarity 0.13 \| critical unknown product_type, state \| level any_brand, confidence 0.24 |
| king_store | צהובה מגורדת על בסיס חלב 500 ג' ריץ | ? / ? | grated_cheese | 500 g | grated-mozzarella close 0.64 review | review: grated-mozzarella (גבינה מגורדת (מוצרלה)): similarity 0.30 \| critical match product_type=grated_cheese \| soft differs pack_size 500 vs 200 g \| level close, confidence 0.64 \| vetoed: yellow-cheese-sliced-9 (גבינה צהובה פרוס |
| king_store | שעועית צהובה חתוכה קפואה 800 ג' ויליגר טבע | ? / ? | - | 800 g | green-beans-frozen any_brand 0.62 review | review: green-beans-frozen (שעועית ירוקה קפואה): similarity 0.49 \| critical match state=frozen \| critical unknown product_type \| level any_brand, confidence 0.62 |
| king_store | גבינה צהובה פרוס בקופסא %28 200 ג' עמק | ? / ? | yellow_cheese | 200 g | yellow-cheese-sliced-28 any_brand 0.66 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.55 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| ambiguous with yellow-cheese-sliced-9 \| level any_brand, confidence 0.66 \| vetoed: w |
| king_store | חטיף גבינת אצבעות 28% 172 ג' עמק | ? / ? | yellow_cheese | 172 g | - | every candidate vetoed \| vetoed: cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.32 \| critical mismatch product_type yellow_cheese vs cream_cheese; fat_pct 28 vs 30; name has 'חטיף' (a derived product), canonical is 'גב |
| king_store | גבינה צהובה 28% שומן 400 ג' עמק | ? / ? | yellow_cheese | 400 g | yellow-cheese-sliced-28 close 0.92 | accept: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.64 \| critical match product_type=yellow_cheese, fat_pct=28 \| soft differs pack_size 400 vs 200 g \| level close, confidence 0.92 \| vetoed: yellow-cheese-sliced-9 |
| king_store | חטיף אצבעות גבינת מוצרלה 20% 172 ג' עמק | ? / ? | yellow_cheese | 172 g | - | every candidate vetoed \| vetoed: grated-mozzarella (גבינה מגורדת (מוצרלה)): similarity 0.35 \| critical mismatch product_type yellow_cheese vs grated_cheese; name has 'חטיף' (a derived product), canonical is 'גבינה מגורדת (מוצרלה)' |
| osherad | גבינה גאודה עיזים  מ | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| osherad | גבינת גאודה עיזים פר | ? / ? | yellow_cheese | 150 g | - | rejected (confidence 0.44 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.28 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| soft differs pack_size 150 vs 200 g \| ambiguous with yellow- |
| osherad | גבינה גאודה משולשים | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| osherad | גבינה עמק 28% 600 גר | ? / ? | yellow_cheese | 600 g | yellow-cheese-sliced-28 close 0.78 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.48 \| critical match product_type=yellow_cheese, fat_pct=28 \| soft differs pack_size 600 vs 200 g \| level close, confidence 0.78 \| vetoed: white-cheese-9 (גבינה  |
| osherad | גבינה נעם אמנטל פרוס | ? / ? | yellow_cheese | 200 g | - | rejected (confidence 0.56 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.42 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| ambiguous with yellow-cheese-sliced-28 \| level any_brand, co |
| osherad | גבינה נעם גאודה עם פ | ? / ? | yellow_cheese | 200 g | - | rejected (confidence 0.51 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.36 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| ambiguous with yellow-cheese-sliced-28 \| level any_brand, co |

#### `yogurt-plain-3`: 24 listed of 200 name hits (0 skipped as not the food itself; chains looked in: osherad, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| osherad | מארז יוגורט דנונה יו | ? / ? | yogurt | -  | - | rejected (confidence 0.50 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.42 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| ambiguous with yogurt-plain-1-5 \| level any_brand, confidence 0.50 \| veto |
| osherad | מארז יוגורט פרוביוטי | ? / ? | yogurt | -  | - | rejected (confidence 0.51 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.44 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| ambiguous with yogurt-plain-1-5 \| level any_brand, confidence 0.51 \| veto |
| osherad | מארז יוגורט פרוביוטי | ? / ? | yogurt | -  | - | rejected (confidence 0.51 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.44 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| ambiguous with yogurt-plain-1-5 \| level any_brand, confidence 0.51 \| veto |
| osherad | משקה יוגורט עיזים חל | ? / ? | yogurt | -  | - | rejected (confidence 0.48 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.41 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| level any_brand, confidence 0.48 \| vetoed: yogurt-strawberry (יוגורט תות) |
| osherad | משקה יוגורט בננה מנג | ? / ? | yogurt | 267 g | - | every candidate vetoed \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.43 \| critical mismatch product_type yogurt vs yogurt_fruit; flavor banana vs strawberry ; yogurt-peach (יוגורט אפרסק): similarity 0.40 \| critical mismat |
| osherad | משקה יוגורט קוקוס בנ | ? / ? | - | 267 g | - | rejected (confidence 0.40 < 0.6): yogurt-strawberry (יוגורט תות): similarity 0.45 \| critical unknown product_type, flavor \| soft differs pack_size 267 vs 150 g \| ambiguous with greek-yogurt-plain \| level close, confidence 0.40 |
| osherad | מולר סימפלי יוגורט א | ? / ? | yogurt | 150 g | - | rejected (confidence 0.51 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.43 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| soft differs pack_size 150 vs 200 g \| ambiguous with yogurt-plain-1-5 \| l |
| osherad | יוגורט 4% תנובה 3 לי | ? / ? | yogurt | -  | - | every candidate vetoed \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.48 \| critical mismatch product_type yogurt vs yogurt_fruit \| critical unknown flavor ; yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.45 \| critical misma |
| osherad | יוגורט עיזים צוריאל | ? / ? | yogurt | -  | - | rejected (confidence 0.50 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.43 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| ambiguous with yogurt-plain-1-5 \| level any_brand, confidence 0.50 \| veto |
| osherad | משקה יוגורט 6.5% תנו | ? / ? | yogurt | -  | - | every candidate vetoed \| vetoed: yogurt-plain-1-5 (יוגורט טבעי 1.5%): similarity 0.51 \| critical mismatch fat_pct 6.5 vs 1.5 \| critical match product_type=yogurt \| critical unknown flavor ; yogurt-strawberry (יוגורט תות): similari |
| osherad | משקה יוגורט 4% טרה 3 | ? / ? | yogurt | -  | - | every candidate vetoed \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.44 \| critical mismatch product_type yogurt vs yogurt_fruit \| critical unknown flavor ; yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.43 \| critical misma |
| osherad | מארז יוגורט אקטיביה | ? / ? | yogurt | -  | - | rejected (confidence 0.49 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.41 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| ambiguous with yogurt-plain-1-5 \| level any_brand, confidence 0.49 \| veto |
| tivtaam | תחליב רחצה יוגורט וקוקוס גונסונס 750 | ? / ? | body_wash | 750 ml | body-wash any_brand 0.62 review | review: body-wash (סבון רחצה): similarity 0.28 \| critical match product_type=body_wash \| level any_brand, confidence 0.62 \| vetoed: hand-soap (סבון ידיים נוזלי): similarity 0.06 \| critical mismatch product_type body_wash vs hand_s |
| tivtaam | שוקולד ריטר ספורט יוגורט - גאווה 100 גרם | ? / ? | yogurt | 100 g | - | every candidate vetoed \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.38 \| critical mismatch product_type yogurt vs yogurt_fruit; flavor chocolate vs strawberry ; yogurt-peach (יוגורט אפרסק): similarity 0.37 \| critical mis |
| tivtaam | ג. יוגורט עם אוכמניות שחורות בכוס 82 גר | ? / ? | yogurt | 82 g | - | every candidate vetoed \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.45 \| critical mismatch product_type yogurt vs yogurt_fruit; flavor other vs strawberry ; yogurt-peach (יוגורט אפרסק): similarity 0.36 \| critical mismatc |
| tivtaam | יוגורט יווני 200 גר | ? / ? | greek_yogurt | 200 g | greek-yogurt-plain any_brand 0.78 review | review: greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.70 \| critical match product_type=greek_yogurt \| critical unknown flavor \| level any_brand, confidence 0.78 \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.53 \| cr |
| tivtaam | יוגורט יווני עם דובדבן 150 גר | ? / ? | greek_yogurt | 150 g | - | every candidate vetoed \| vetoed: greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.60 \| critical mismatch flavor other vs plain \| critical match product_type=greek_yogurt ; yogurt-strawberry (יוגורט תות): similarity 0.44 \| crit |
| tivtaam | יוגורט יווני 150 גר | ? / ? | greek_yogurt | 150 g | greek-yogurt-plain close 0.79 review | review: greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.71 \| critical match product_type=greek_yogurt \| critical unknown flavor \| soft differs pack_size 150 vs 200 g \| level close, confidence 0.79 \| vetoed: yogurt-strawberry  |
| tivtaam | יוגורט יווני 1 ק"ג | ? / ? | greek_yogurt | 1000 g | greek-yogurt-plain close 0.78 review | review: greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.70 \| critical match product_type=greek_yogurt \| critical unknown flavor \| soft differs pack_size 1000 vs 200 g \| level close, confidence 0.78 \| vetoed: yogurt-plain-1-5  |
| tivtaam | שוקולד חלב דובדבנים ויוגורט 235 גר | ? / ? | yogurt | 235 g | - | every candidate vetoed \| vetoed: dessert-chocolate (מעדן חלב שוקולד): similarity 0.45 \| critical mismatch product_type yogurt vs dairy_dessert \| critical match flavor=chocolate ; yogurt-strawberry (יוגורט תות): similarity 0.25 \| c |
| tivtaam | שוקולד חלב קיווי ויוגורט 235 גר | ? / ? | yogurt | 235 g | - | every candidate vetoed \| vetoed: dessert-chocolate (מעדן חלב שוקולד): similarity 0.48 \| critical mismatch product_type yogurt vs dairy_dessert \| critical match flavor=chocolate ; pudding-chocolate-cream (מעדן שוקולד עם קצפת): simi |
| tivtaam | יוגורט 4% 1.5 ליטר | ? / ? | yogurt | 1500 ml | - | every candidate vetoed \| vetoed: milk-fresh-1 (חלב טרי 1%): similarity 0.06 \| critical mismatch product_type yogurt vs milk; fat_pct 4 vs 1 \| critical unknown state ; cooking-cream-10 (שמנת לבישול 10%): similarity 0.05 \| critical  |
| tivtaam | יוגורט 4.5% 3 ליטר | ? / ? | yogurt | 3000 ml | - | every candidate vetoed \| vetoed: whipping-cream-32 (שמנת מתוקה 32%): similarity 0.07 \| critical mismatch product_type yogurt vs whipping_cream; fat_pct 4.5 vs 32 ; whipping-cream-38 (שמנת מתוקה 38%): similarity 0.07 \| critical mis |
| tivtaam | משקה יוגורט יופלה בטעם תות-מלון 250 גר | ? / ? | melon | 250 g | - | every candidate vetoed \| vetoed: mushrooms-fresh (פטריות שמפיניון טריות): similarity 0.15 \| critical mismatch product_type melon vs mushrooms; the canonical's words come only after 'בטעם' (a flavor, not the product) \| critical mat |

### Failures and findings the run recorded (5)

- **api**: /parse-list took over 2 s (production): {'small (6 lines)': 3612.3, 'weekly (17 lines)': 9884.4, 'large (32 lines)': 19188.9} ms
- **basket index**: chocolate-milk is priced at no chain (candidates in the report)
- **basket index**: hummus-plain is priced at no chain (candidates in the report)
- **basket index**: pasta-spaghetti is priced at no chain (candidates in the report)
- **api**: /parse-list took over 2 s (stress): {'small (6 lines)': 3505.5, 'weekly (17 lines)': 9827.7, 'large (32 lines)': 19096.4} ms

