## One real day through the pipeline (dry run)

Mode `portal`, commit `627a7e3be842`, runner `GitHub Actions 1000005154` (4 CPUs, Python 3.12.3, Postgres 17.11), 2026-10-22T07:57:10+00:00 to 2026-10-22T08:39:16+00:00 UTC. Measurements on one real day with hand-made baskets; the prices are real, the baskets and locations are not a sample of anything. **Not publishable.**

### Stages

| stage | seconds | result |
|---|---|---|
| download: portal probe (one Stores and one PriceFull per chain) | 964.54 | ok |
| migrate | 1.18 | 32 applied |
| ingest: Stores files (Scheduler, adapters, gates, loader, store coordinates) | 0.37 | 6 files |
| download: PriceFull and PromoFull of the stores nearest to city centres | 728.76 | 36 files, anchors: Jerusalem centre, Holon, Petah Tikva |
| ingest: PriceFull and PromoFull files (Scheduler, adapters, gates, loader) | 177.93 | 49 files |
| catalog: seed | 1.11 | ok |
| catalog: normalize | 11.4 | ok |
| catalog: extract (rule) | 78.69 | ok |
| catalog: embed (hash) | 253.29 | ok |
| catalog: judge (rule) | 198.55 | ok |
| precompute effective prices (production semantics: reviewed mappings only) | 1.32 | 5627 rows |
| API: parse-list, compare, optimize (production) | 47.81 | 21 basket runs at 3 locations |
| diagnostic: the vector query behind /parse-list and /search | 8.8 | [4.2, 1.2, 1.0] ms per query |
| basket index dry run (production semantics) | 0.48 | status draft |
| diagnostic: real items behind the basket lines no chain prices | 1.97 | butter 60 items, chocolate-milk 84 items, cottage-5 6 items, eggs-l 145 items, milk-fresh-3 36 items, pasta-spaghetti 73 items, white-cheese-5 12 items, yellow-cheese-sliced-28 72 items, yogurt-plain-3 36 items |
| stress: mark the machine suggestions accepted (performance only) | 0.23 | 13027 mappings |
| precompute effective prices (stress: unreviewed mappings included) | 2.59 | 9213 rows |
| API: parse-list, compare, optimize (stress) | 46.03 | 21 basket runs at 3 locations |
| basket index dry run (stress) | 0.48 | status draft |

### Portals (the portal probe's own reachability and downloads)

| chain | reachable | login | Stores download | PriceFull download |
|---|---|---|---|---|
| king_store | BLOCKED? (403) | n/a | Stores7290058108879-000-20261022-051042.gz | PriceFull7290058108879-000-340-20261022-051042.gz |
| mega | OK (200) | n/a | Stores7290055700007-000-20261022-000100.xml | PriceFull7290055700007-001-002-20261022-051018.gz |
| osherad | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290103152017-000-20261020-080500.xml | PriceFull7290103152017-001-001-20261022-080018.gz |
| ramilevy | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290058140886-000-20261020-050500.xml | PriceFull7290058140886-001-001-20261022-001004.gz |
| shufersal | UNREACHABLE (0) | n/a | no: TimeoutError:  | PriceFull7290027600007-001-316-20261022-030000.gz |
| tivtaam | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290873255550-000-20261020-050500.xml | PriceFull7290873255550-000-002-20261022-004004.gz |
| yohananof | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290803800003-000-20261020-010000.xml | PriceFull7290803800003-000-001-20261022-004040.gz |

### Files, gates and rows per chain

| chain | kind | file | published (Israel) | age h | schema | gate result | rows | seconds |
|---|---|---|---|---|---|---|---|---|
| king_store | stores | `Stores7290058108879-000-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 6.0 | v1 | loaded | 48 | 0.07 |
| mega | stores | `Stores7290055700007-000-20261022-000100.xml` | 2026-10-22T00:01+03:00 | 11.2 | v1 | loaded | 147 | 0.1 |
| osherad | stores | `Stores7290103152017-000-20261020-080500.xml` | 2026-10-20T08:05+03:00 | 51.1 | v1 | loaded | 24 | 0.03 |
| ramilevy | stores | `Stores7290058140886-000-20261020-050500.xml` | 2026-10-20T05:05+03:00 | 54.1 | v1 | loaded | 99 | 0.07 |
| tivtaam | stores | `Stores7290873255550-000-20261020-050500.xml` | 2026-10-20T05:05+03:00 | 54.1 | v1 | loaded | 54 | 0.04 |
| yohananof | stores | `Stores7290803800003-000-20261020-010000.xml` | 2026-10-20T01:00+03:00 | 58.2 | v1 | loaded | 51 | 0.03 |
| king_store | price_full | `PriceFull7290058108879-000-340-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 6.2 | v1 | loaded | 2,338 | 0.48 |
| king_store | promo_full | `PromoFull7290058108879-000-340-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 6.2 | v1 | loaded | 296 | 0.17 |
| mega | price_full | `PriceFull7290055700007-001-002-20261022-051018.gz` | 2026-10-22T05:10+03:00 | 6.3 | v1 | loaded | 5,879 | 1.19 |
| mega | promo_full | `PromoFull7290055700007-001-002-20261022-051124.gz` | 2026-10-22T05:11+03:00 | 6.2 | v1 | loaded | 1,547 | 0.77 |
| osherad | price_full | `PriceFull7290103152017-001-001-20261022-080018.gz` | 2026-10-22T08:00+03:00 | 3.4 | v1 | loaded | 6,495 | 1.35 |
| osherad | promo_full | `PromoFull7290103152017-001-001-20261022-080055.gz` | 2026-10-22T08:00+03:00 | 3.4 | v1 | loaded | 660 | 0.38 |
| ramilevy | price_full | `PriceFull7290058140886-001-001-20261022-001004.gz` | 2026-10-22T00:10+03:00 | 11.3 | v1 | loaded | 12,975 | 2.58 |
| ramilevy | promo_full | `PromoFull7290058140886-001-001-20261022-001131.gz` | 2026-10-22T00:11+03:00 | 11.2 | v1 | loaded | 2,660 | 1.66 |
| shufersal | price_full | `PriceFull7290027600007-001-316-20261022-030000.gz` | 2026-10-22T03:00+03:00 | 8.4 | v1 | loaded | 5,718 | 1.15 |
| tivtaam | price_full | `PriceFull7290873255550-000-002-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 21,607 | 4.45 |
| tivtaam | promo_full | `PromoFull7290873255550-000-002-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 2,246 | 6.16 |
| yohananof | price_full | `PriceFull7290803800003-000-001-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 10,722 | 2.13 |
| yohananof | promo_full | `PromoFull7290803800003-000-009-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 1,206 | 0.89 |
| king_store | price_full | `PriceFull7290058108879-000-200-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 6.3 | v1 | loaded | 3,611 | 0.71 |
| king_store | promo_full | `PromoFull7290058108879-000-200-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 6.3 | v1 | loaded | 306 | 0.23 |
| osherad | price_full | `PriceFull7290103152017-001-025-20261022-110501.gz` | 2026-10-22T11:05+03:00 | 0.4 | v1 | loaded | 6,253 | 1.19 |
| osherad | price_full | `PriceFull7290103152017-001-026-20261022-110501.gz` | 2026-10-22T11:05+03:00 | 0.4 | v1 | loaded | 6,834 | 1.32 |
| osherad | price_full | `PriceFull7290103152017-001-028-20261022-110501.gz` | 2026-10-22T11:05+03:00 | 0.4 | v1 | loaded | 6,236 | 1.21 |
| osherad | price_full | `PriceFull7290103152017-001-010-20261022-110502.gz` | 2026-10-22T11:05+03:00 | 0.4 | v1 | loaded | 6,690 | 1.28 |
| osherad | promo_full | `PromoFull7290103152017-001-025-20261022-110521.gz` | 2026-10-22T11:05+03:00 | 0.3 | v1 | loaded | 759 | 0.46 |
| osherad | promo_full | `PromoFull7290103152017-001-026-20261022-110522.gz` | 2026-10-22T11:05+03:00 | 0.3 | v1 | loaded | 721 | 0.42 |
| osherad | promo_full | `PromoFull7290103152017-001-028-20261022-110522.gz` | 2026-10-22T11:05+03:00 | 0.3 | v1 | loaded | 704 | 0.43 |
| osherad | promo_full | `PromoFull7290103152017-001-010-20261022-110555.gz` | 2026-10-22T11:05+03:00 | 0.3 | v1 | loaded | 723 | 0.44 |
| ramilevy | price_full | `PriceFull7290058140886-001-703-20261022-001001.gz` | 2026-10-22T00:10+03:00 | 11.3 | v1 | loaded | 4,950 | 0.98 |
| ramilevy | price_full | `PriceFull7290058140886-001-048-20261022-001016.gz` | 2026-10-22T00:10+03:00 | 11.3 | v1 | loaded | 14,443 | 2.8 |
| ramilevy | price_full | `PriceFull7290058140886-001-718-20261022-060005.gz` | 2026-10-22T06:00+03:00 | 5.4 | v1 | loaded | 3,809 | 0.75 |
| ramilevy | price_full | `PriceFull7290058140886-001-725-20261022-060005.gz` | 2026-10-22T06:00+03:00 | 5.4 | v1 | loaded | 4,108 | 0.79 |
| ramilevy | price_full | `PriceFull7290058140886-001-050-20261022-060006.gz` | 2026-10-22T06:00+03:00 | 5.4 | v1 | loaded | 14,809 | 2.99 |
| ramilevy | price_full | `PriceFull7290058140886-001-724-20261022-060015.gz` | 2026-10-22T06:00+03:00 | 5.4 | v1 | loaded | 5,147 | 1.04 |
| ramilevy | promo_full | `PromoFull7290058140886-001-703-20261022-001044.gz` | 2026-10-22T00:10+03:00 | 11.3 | v1 | loaded | 1,109 | 0.68 |
| ramilevy | promo_full | `PromoFull7290058140886-001-048-20261022-001113.gz` | 2026-10-22T00:11+03:00 | 11.3 | v1 | loaded | 2,529 | 1.7 |
| ramilevy | promo_full | `PromoFull7290058140886-001-718-20261022-060028.gz` | 2026-10-22T06:00+03:00 | 5.4 | v1 | loaded | 1,072 | 0.69 |
| ramilevy | promo_full | `PromoFull7290058140886-001-725-20261022-060028.gz` | 2026-10-22T06:00+03:00 | 5.4 | v1 | loaded | 1,047 | 0.7 |
| ramilevy | promo_full | `PromoFull7290058140886-001-724-20261022-060039.gz` | 2026-10-22T06:00+03:00 | 5.4 | v1 | loaded | 1,060 | 0.69 |
| ramilevy | promo_full | `PromoFull7290058140886-001-050-20261022-060107.gz` | 2026-10-22T06:01+03:00 | 5.4 | v1 | loaded | 2,507 | 1.66 |
| tivtaam | price_full | `PriceFull7290873255550-000-006-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 16,079 | 3.22 |
| tivtaam | price_full | `PriceFull7290873255550-000-079-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 6,351 | 1.26 |
| tivtaam | price_full | `PriceFull7290873255550-000-085-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 7,171 | 1.47 |
| tivtaam | price_full | `PriceFull7290873255550-000-087-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 6,069 | 1.24 |
| tivtaam | promo_full | `PromoFull7290873255550-000-006-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 2,000 | 6.2 |
| tivtaam | promo_full | `PromoFull7290873255550-000-079-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 567 | 5.87 |
| tivtaam | promo_full | `PromoFull7290873255550-000-085-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 1,281 | 6.29 |
| tivtaam | promo_full | `PromoFull7290873255550-000-087-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 1,124 | 5.71 |
| yohananof | price_full | `PriceFull7290803800003-000-020-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 11,876 | 2.36 |
| yohananof | price_full | `PriceFull7290803800003-000-021-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 11,196 | 2.23 |
| yohananof | price_full | `PriceFull7290803800003-000-029-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 10,462 | 2.06 |
| yohananof | promo_full | `PromoFull7290803800003-000-020-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 1,276 | 0.99 |
| yohananof | promo_full | `PromoFull7290803800003-000-021-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 1,218 | 0.9 |
| yohananof | promo_full | `PromoFull7290803800003-000-029-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 10.8 | v1 | loaded | 1,106 | 0.82 |

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
| osherad | `PromoFull7290103152017-001-025-20261022-110521.gz` | 759 | 759 | 2,882 | 2,343 | 2,459 | 759 | 0 | {'bundle': 678, 'price': 78, 'other': 3} |
| osherad | `PromoFull7290103152017-001-026-20261022-110522.gz` | 721 | 721 | 2,790 | 2,285 | 2,326 | 721 | 0 | {'bundle': 655, 'other': 3, 'price': 63} |
| osherad | `PromoFull7290103152017-001-028-20261022-110522.gz` | 704 | 704 | 2,664 | 2,173 | 2,220 | 704 | 0 | {'bundle': 640, 'price': 62, 'other': 2} |
| osherad | `PromoFull7290103152017-001-010-20261022-110555.gz` | 723 | 723 | 2,810 | 2,301 | 2,395 | 723 | 0 | {'bundle': 652, 'price': 68, 'other': 3} |
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

`file_tracking` after the run: {'loaded': 55}. Alerts raised: 0.

| chain | physical stores | located | online | items | price events | stores with prices | promos | promo items |
|---|---|---|---|---|---|---|---|---|
| king_store | 48 | 28 | - | 4,530 | 5,949 | 2 | 602 | 1,516 |
| mega | 144 | 144 | 3 | 5,879 | 5,879 | 1 | 1,547 | 2,185 |
| osherad | 24 | 24 | - | 8,672 | 32,508 | 5 | 3,567 | 11,239 |
| ramilevy | 98 | 96 | 1 | 18,161 | 60,241 | 7 | 11,984 | 46,218 |
| shufersal | 1 | - | - | 5,718 | 5,718 | 1 | - | - |
| tivtaam | 47 | 47 | 7 | 24,779 | 57,277 | 5 | 7,218 | 119,639 |
| yohananof | 50 | 19 | 1 | 13,856 | 44,256 | 4 | 4,806 | 15,859 |

Extra downloads (the stores nearest to these city centres, for the optimizer):

- Jerusalem centre: 5 chains and 17 located stores within 4 km; asked for mega 457,91, king_store 200, ramilevy 48,703, osherad 26,28, yohananof 20
- Holon: 5 chains and 16 located stores within 4 km; asked for mega 67,345, ramilevy 718,50, osherad 25, yohananof 29, tivtaam 79,6
- Petah Tikva: 5 chains and 16 located stores within 4 km; asked for mega 407,452, ramilevy 725,724, osherad 10, yohananof 21, tivtaam 87,85
- download `mega` price_full: no file matched
- download `mega` promo_full: no file matched

### Matching on the real items

81,595 items; 17,939 mapped to a canonical (any level, including the review queue); 4,912 served (no review flag), onto 210 canonicals.

| level | mappings served | mappings in the review queue |
|---|---|---|
| exact | 0 | 0 |
| any_brand | 3,075 | 5,543 |
| close | 1,837 | 7,484 |

| chain | items | mapped | served |
|---|---|---|---|
| shufersal | 5,718 | 1,548 | 435 |
| mega | 5,879 | 1,488 | 565 |
| king_store | 4,530 | 1,307 | 239 |
| ramilevy | 18,161 | 3,890 | 1,355 |
| osherad | 8,672 | 2,166 | 685 |
| yohananof | 13,856 | 2,692 | 937 |
| tivtaam | 24,779 | 4,848 | 696 |

- seed: 1.11 s
- normalize: 11.4 s
- extract (rule): 78.69 s
- embed (hash): 253.29 s
- judge (rule): 198.55 s

### Precompute (production semantics)

5,627 rows written in 0.838 s of job time (1.22 s wall including start-up); 4,707 items priced at 25 stores (424 stores of 7 chains considered); 1,642 rows with a promo, 205 club-only. Canonicals with a real price: 208, of them 180 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 2,504 | 190 | 25 |
| close | 3,123 | 208 | 25 |

Promos per chain, and what reached a price (production semantics):

| chain | promos | club-only | linked to items | reward `other` | effective rows | with a promo | club required | of them with a non-club fallback |
|---|---|---|---|---|---|---|---|---|
| mega | 1,547 | 6 | 947 | 104 | 220 | 82 | 4 | 4 |
| king_store | 602 | 140 | 602 | 1 | 294 | 79 | 19 | 19 |
| ramilevy | 11,984 | 205 | 11,027 | 2,424 | 1,834 | 648 | 0 | 0 |
| osherad | 3,567 | 0 | 3,230 | 14 | 813 | 265 | 0 | 0 |
| yohananof | 4,806 | 44 | 4,722 | 247 | 1,121 | 300 | 14 | 14 |
| tivtaam | 7,218 | 4,262 | 7,218 | 77 | 1,116 | 268 | 168 | 168 |

Club rules of the club-only promos (most frequent): `המועדון החדש` x 4,262; `מועדון חברתי \| מועדון רמי לוי \| מועדון לקוחות אשראי \| מועדון נטען \| לקוחות ארנק` x 132; `מועדון לקוחות \| לקוחות סיטונאים \| עובדי קינגסטור` x 79; `מועדון עובדים` x 44; `מועדון לקוחות \| עובדי קינגסטור` x 43; `מועדון לקוחות אשראי & תווי זיכוי מימוש` x 34; `לקוחות סיטונאים` x 16; `מועדון רמי לוי \| מועדון לקוחות אשראי` x 12

### Precompute (stress)

9,213 rows written in 2.088 s of job time (2.48 s wall including start-up); 17,030 items priced at 25 stores (424 stores of 7 chains considered); 2,757 rows with a promo, 424 club-only. Canonicals with a real price: 241, of them 234 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 4,237 | 235 | 25 |
| close | 4,976 | 241 | 25 |

Promos per chain, and what reached a price (stress):

| chain | promos | club-only | linked to items | reward `other` | effective rows | with a promo | club required | of them with a non-club fallback |
|---|---|---|---|---|---|---|---|---|
| mega | 1,547 | 6 | 947 | 104 | 356 | 142 | 2 | 2 |
| king_store | 602 | 140 | 602 | 1 | 593 | 182 | 49 | 49 |
| ramilevy | 11,984 | 205 | 11,027 | 2,424 | 2,794 | 1,063 | 0 | 0 |
| osherad | 3,567 | 0 | 3,230 | 14 | 1,540 | 352 | 0 | 0 |
| yohananof | 4,806 | 44 | 4,722 | 247 | 1,655 | 410 | 14 | 14 |
| tivtaam | 7,218 | 4,262 | 7,218 | 77 | 1,895 | 608 | 359 | 359 |

Club rules of the club-only promos (most frequent): `המועדון החדש` x 4,262; `מועדון חברתי \| מועדון רמי לוי \| מועדון לקוחות אשראי \| מועדון נטען \| לקוחות ארנק` x 132; `מועדון לקוחות \| לקוחות סיטונאים \| עובדי קינגסטור` x 79; `מועדון עובדים` x 44; `מועדון לקוחות \| עובדי קינגסטור` x 43; `מועדון לקוחות אשראי & תווי זיכוי מימוש` x 34; `לקוחות סיטונאים` x 16; `מועדון רמי לוי \| מועדון לקוחות אשראי` x 12

### The vector query behind /parse-list and /search

`item_embeddings` holds 81,595 rows (model `hash-ngram-2-3-4-v1`); one `ORDER BY embedding <=> q LIMIT 40` query took [4.2, 1.2, 1.0] ms; with sequential scans disabled 1.0 ms.

```
Limit  (cost=2310.64..2569.56 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2310.64..530475.86 rows=81595 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
--- enable_seqscan = off
Limit  (cost=2310.64..2569.56 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2310.64..530475.86 rows=81595 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
```

One `/parse-list` call (6 lines): 4024.5 ms in total, 4014.4 ms inside 37 SQL statements. The statements that cost the most:

| statement (first 110 characters) | calls | total ms | max ms |
|---|---|---|---|
| `WITH qv AS (SELECT %(v)s::vector AS v), direct AS ( SELECT c.id AS canonical_id, 1 - (c.embedding <=> qv.v) AS` | 6 | 3976.7 | 698.5 |
| `WITH q AS (SELECT search_norm(%(q)s) AS t) SELECT c.id, word_similarity(q.t, search_norm(c.display_name_he)) A` | 6 | 20.4 | 7.6 |
| `WITH RECURSIVE up AS ( SELECT t.id AS leaf, t.id, t.parent_id, t.name_he, t.level FROM taxonomy t WHERE t.id =` | 6 | 5.0 | 1.2 |
| `SELECT c.id, c.display_name_he, ts_rank_cd(to_tsvector('simple', search_norm(c.display_name_he)), tq) AS r FRO` | 6 | 4.8 | 1.8 |
| `SELECT id, display_name_he, taxonomy_id, base_unit, rank, names_ar[1] FROM canonical_products WHERE id = ANY(%` | 6 | 4.4 | 0.9 |
| `SELECT set_config('pg_trgm.word_similarity_threshold', %s, true)` | 6 | 2.5 | 1.0 |

`EXPLAIN (ANALYZE, BUFFERS)` of the slowest statement:

```
Limit  (cost=6857.63..6857.66 rows=11 width=16) (actual rows=20 loops=1)
  Buffers: shared hit=653748 read=56192
  CTE qv
    ->  Result  (cost=0.00..0.01 rows=1 width=32) (actual rows=1 loops=1)
  ->  Sort  (cost=6857.62..6857.65 rows=11 width=16) (actual rows=20 loops=1)
        Sort Key: (max(direct.s)) DESC, direct.canonical_id
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=653748 read=56192
        ->  GroupAggregate  (cost=6856.92..6857.43 rows=11 width=16) (actual rows=20 loops=1)
              Group Key: direct.canonical_id
              Buffers: shared hit=653745 read=56192
              ->  Merge Append  (cost=6856.92..6857.27 rows=11 width=16) (actual rows=24 loops=1)
                    Sort Key: direct.canonical_id
                    Buffers: shared hit=653745 read=56192
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
                    ->  GroupAggregate  (cost=6823.62..6823.84 rows=4 width=16) (actual rows=4 loops=1)
                          Group Key: ic.canonical_id
                          Filter: (max((('1'::double precision - (e.embedding <=> qv_1.v)))) >= '0.25'::double precision)
                          Buffers: shared hit=652246 read=56010
                          ->  Sort  (cost=6823.62..6823.65 rows=11 width=16) (actual rows=16 loops=1)
                                Sort Key: ic.canonical_id
                                Sort Method: quicksort  Memory: 25kB
                                Buffers: shared hit=652246 read=56010
                                ->  Nested Loop  (cost=6277.32..6823.43 rows=11 width=16) (actual rows=16 loops=1)
                                      Buffers: shared hit=652246 read=56010
                                      ->  Limit  (cost=6277.03..6277.23 rows=80 width=24) (actual rows=80 loops=1)
                                            Buffers: shared hit=652110 read=55911
                                            ->  Sort  (cost=6277.03..6481.02 rows=81595 width=24) (actual rows=80 loops=1)
                                                  Sort Key: ((e.embedding <=> qv_1.v))
                                                  Sort Method: top-N heapsort  Memory: 34kB
                                                  Buffers: shared hit=652110 read=55911
                                                  ->  Nested Loop  (cost=0.00..3289.87 rows=81595 width=24) (actual rows=81595 loops=1)
                                                        Buffers: shared hit=652110 read=55911
                                                        ->  CTE Scan on qv qv_1  (cost=0.00..0.02 rows=1 width=32) (actual rows=1 loops=1)
                                                        ->  Seq Scan on item_embeddings e  (cost=0.00..1861.94 rows=81595 width=26) (actual rows=81595 loops=1)
                                                              Filter: (model = 'hash-ngram-2-3-4-v1'::text)
                                                              Buffers: shared read=842
                                      ->  Index Scan using item_canonical_pkey on item_canonical ic  (cost=0.29..6.81 rows=1 width=16) (actual rows=0 loops=80)
                                            Index Cond: (item_id = e.item_id)
                                            Filter: ((NOT human_rejected) AND (NOT needs_review) AND (flex_level = ANY ('{exact,any_brand}'::text[])))
                                            Rows Removed by Filter: 1
                                            Buffers: shared hit=136 read=99
Planning:
  Buffers: shared hit=414 read=63
Planning Time: 2.179 ms
Execution Time: 704.856 ms
```

### /parse-list, /compare and /optimize (production semantics)

Locations: Jerusalem centre (7 priced stores, 4 chains within 5 km); Holon (6 priced stores, 4 chains within 5 km); Petah Tikva (6 priced stores, 4 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 3933.2 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 10966.1 |
| large (32 lines) | 33 | 33 | 5 | 0 | 21321.3 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 7 | 0 | 10.6 | 9.6 | 16.5 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 7 | 0 | 13.2 | 11.6 | 19.4 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 33 | 7 | 0 | 17.5 | 14.6 | 22.8 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 5 | 5 | 7 | 3 | 10.4 | 9.2 | 14.8 | 55 | single: רמי לוי בית הפירות פת | 5.2 / 5.2 |
| Jerusalem centre | drawn: 10 | 10 | 7 | 0 | 10.9 | 10.2 | 17.7 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 20 | 20 | 7 | 0 | 14.6 | 13.1 | 20.7 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 40 | 40 | 7 | 0 | 22.5 | 18 | 34.1 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Holon | hand: small (6 lines) | 6 | 6 | 0 | 8.9 | 8.7 | 15.2 | 55 | single: רמי לוי חולון | 24.95 / 24.95 |
| Holon | hand: weekly (17 lines) | 17 | 6 | 0 | 12.3 | 12.4 | 19.6 | 55 | single: רמי לוי חולון | 15.75 / 15.75 |
| Holon | hand: large (32 lines) | 33 | 6 | 0 | 16.8 | 16.4 | 24.9 | 55 | single: רמי לוי חולון | 19.25 / 19.25 |
| Holon | drawn: 5 | 5 | 6 | 1 | 8.6 | 8.8 | 15.7 | 55 | single: רמי לוי חולון | -0.79 / -0.79 |
| Holon | drawn: 10 | 10 | 6 | 0 | 10.5 | 10.2 | 17.2 | 55 | single: רמי לוי חולון | -5.99 / -5.99 |
| Holon | drawn: 20 | 20 | 6 | 0 | 13.7 | 13.9 | 21.7 | 55 | single: רמי לוי חולון | 44.03 / 44.03 |
| Holon | drawn: 40 | 40 | 6 | 0 | 22.1 | 21.3 | 32 | 55 | single: רמי לוי חולון | 102.51 / 102.51 |
| Petah Tikva | hand: small (6 lines) | 6 | 6 | 0 | 9.2 | 9.1 | 15.8 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 17.64 / 17.64 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 6 | 0 | 12.4 | 12 | 19.5 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 16.04 / 16.04 |
| Petah Tikva | hand: large (32 lines) | 33 | 6 | 0 | 16.8 | 15.6 | 24.6 | 55 | single: יוחננוף סגולה פתח תקווה | 1.52 / 1.52 |
| Petah Tikva | drawn: 5 | 5 | 6 | 1 | 9.7 | 9 | 15.6 | 55 | single: רמי לוי קניון אבנת פתח תקווה | -22.54 / -22.54 |
| Petah Tikva | drawn: 10 | 10 | 6 | 0 | 10.8 | 10.7 | 18.4 | 55 | single: רמי לוי קניון אבנת פתח תקווה | -12.74 / -12.74 |
| Petah Tikva | drawn: 20 | 20 | 6 | 0 | 14.7 | 13.3 | 21.7 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | -28.99 / -28.99 |
| Petah Tikva | drawn: 40 | 40 | 6 | 0 | 22.3 | 20.2 | 36.6 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 42.16 / 42.16 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 9.2 | 9.1 | 15.8 |
| hand: weekly (17 lines) | 12.4 | 12.0 | 19.5 |
| hand: large (32 lines) | 16.8 | 15.6 | 24.6 |
| drawn: 5 | 9.7 | 9.0 | 15.6 |
| drawn: 10 | 10.8 | 10.2 | 17.7 |
| drawn: 20 | 14.6 | 13.3 | 21.7 |
| drawn: 40 | 22.3 | 20.2 | 34.1 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 10.1 | 16.9 | רמי לוי עטרות, רמי לוי בית הפירות פת | רמי לוי עטרות, רמי לוי בית הפירות פת | 10.27 / 10.27 |
| Jerusalem centre | hand: weekly (17 lines) | 11.6 | 19 | - | - | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 15 | 22.7 | - | - | 0.0 / 0.0 |
| Jerusalem centre | drawn: 5 | 10.4 | 14.7 | קינג סטור ואדי אלגוז', רמי לוי עטרות | קינג סטור ואדי אלגוז', רמי לוי עטרות | 49.63 / 49.63 |
| Jerusalem centre | drawn: 10 | 10.4 | 17.6 | - | - | 0.0 / 0.0 |
| Jerusalem centre | drawn: 20 | 12.6 | 21.1 | - | - | 0.0 / 0.0 |
| Jerusalem centre | drawn: 40 | 18.4 | 34.9 | - | - | 0.0 / 0.0 |
| Holon | hand: small (6 lines) | 8.6 | 15.6 | - | - | 24.95 / 24.95 |
| Holon | hand: weekly (17 lines) | 12.6 | 20.3 | - | - | 15.75 / 15.75 |
| Holon | hand: large (32 lines) | 16.2 | 24.4 | - | - | 19.25 / 19.25 |
| Holon | drawn: 5 | 8.6 | 15.6 | רמי לוי שוויצריה סוקולוב, יוחננוף בת ים | רמי לוי שוויצריה סוקולוב, יוחננוף בת ים | 11.21 / 11.21 |
| Holon | drawn: 10 | 10.5 | 17.8 | - | - | -5.99 / -5.99 |
| Holon | drawn: 20 | 13.7 | 21.7 | רמי לוי חולון, טיב טעם בת ים | רמי לוי חולון, טיב טעם בת ים | 56.3 / 56.3 |
| Holon | drawn: 40 | 21.4 | 32.6 | - | - | 102.51 / 102.51 |
| Petah Tikva | hand: small (6 lines) | 8.9 | 15.6 | - | - | 17.64 / 17.64 |
| Petah Tikva | hand: weekly (17 lines) | 12.3 | 19.9 | - | - | 16.04 / 16.04 |
| Petah Tikva | hand: large (32 lines) | 16.3 | 24.5 | - | - | 1.52 / 1.52 |
| Petah Tikva | drawn: 5 | 9.1 | 17.1 | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | 4.7 / 4.7 |
| Petah Tikva | drawn: 10 | 9.8 | 17.8 | - | - | -12.74 / -12.74 |
| Petah Tikva | drawn: 20 | 13.7 | 22.8 | - | - | -28.99 / -28.99 |
| Petah Tikva | drawn: 40 | 20.5 | 36.9 | - | - | 42.16 / 42.16 |

### /parse-list, /compare and /optimize (stress: unreviewed mappings included, performance only)

Locations: Jerusalem centre (7 priced stores, 4 chains within 5 km); Holon (6 priced stores, 4 chains within 5 km); Petah Tikva (6 priced stores, 4 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 3998.8 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 11232.2 |
| large (32 lines) | 33 | 33 | 5 | 0 | 21254.7 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 7 | 4 | 10.8 | 10.9 | 17.9 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 7 | 3 | 15.5 | 13.2 | 20.9 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 33 | 7 | 1 | 23.2 | 18.6 | 29 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 5 | 5 | 7 | 4 | 9.4 | 8.2 | 14.1 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 10 | 10 | 7 | 2 | 10.6 | 9.3 | 15.7 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 20 | 20 | 7 | 0 | 14.8 | 12.3 | 21.2 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 40 | 40 | 7 | 0 | 22.7 | 17.9 | 27.9 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Holon | hand: small (6 lines) | 6 | 6 | 2 | 9.2 | 8.6 | 14.6 | 55 | single: רמי לוי חולון | 8.08 / 8.08 |
| Holon | hand: weekly (17 lines) | 17 | 6 | 1 | 14.4 | 12.7 | 20 | 55 | single: רמי לוי חולון | 0.32 / 0.32 |
| Holon | hand: large (32 lines) | 33 | 6 | 1 | 20 | 18.7 | 27.7 | 55 | split: רמי לוי חולון, יוחננוף בת ים | 20.76 / 20.76 |
| Holon | drawn: 5 | 5 | 6 | 3 | 9.3 | 8.7 | 13.8 | 55 | single: רמי לוי חולון | 24.83 / 24.83 |
| Holon | drawn: 10 | 10 | 6 | 1 | 10.9 | 10.6 | 17 | 55 | single: רמי לוי חולון | 18.61 / 18.61 |
| Holon | drawn: 20 | 20 | 6 | 0 | 15.2 | 13.7 | 22.4 | 55 | single: רמי לוי חולון | 79.01 / 79.01 |
| Holon | drawn: 40 | 40 | 6 | 0 | 24.6 | 22.5 | 32.7 | 55 | single: רמי לוי חולון | 367.14 / 367.14 |
| Petah Tikva | hand: small (6 lines) | 6 | 6 | 5 | 8.9 | 8.7 | 15.3 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 1.26 / 1.26 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 6 | 2 | 14.4 | 13.3 | 20.7 | 55 | split: רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | -5.84 / -5.84 |
| Petah Tikva | hand: large (32 lines) | 33 | 6 | 1 | 20.9 | 19.6 | 29.4 | 55 | split: רמי לוי שטמפפר פתח תקווה, יוחננוף סגולה פתח תקווה | 8.7 / 8.7 |
| Petah Tikva | drawn: 5 | 5 | 6 | 1 | 8.6 | 8.8 | 14.3 | 55 | split: אושר עד פתח תקווה - סגולה, רמי לוי שטמפפר פתח תקווה | -14.28 / -14.28 |
| Petah Tikva | drawn: 10 | 10 | 6 | 1 | 11.1 | 11 | 17.6 | 55 | split: רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | -13.7 / -13.7 |
| Petah Tikva | drawn: 20 | 20 | 6 | 0 | 16.5 | 15.7 | 23 | 55 | single: יוחננוף סגולה פתח תקווה | -8.41 / -8.41 |
| Petah Tikva | drawn: 40 | 40 | 6 | 0 | 23.4 | 20.8 | 31.1 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 32.89 / 32.89 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 9.2 | 8.7 | 15.3 |
| hand: weekly (17 lines) | 14.4 | 13.2 | 20.7 |
| hand: large (32 lines) | 20.9 | 18.7 | 29.0 |
| drawn: 5 | 9.3 | 8.7 | 14.1 |
| drawn: 10 | 10.9 | 10.6 | 17.0 |
| drawn: 20 | 15.2 | 13.7 | 22.4 |
| drawn: 40 | 23.4 | 20.8 | 31.1 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 10.5 | 17.4 | אושר עד שמגר, רמי לוי עטרות | אושר עד שמגר, רמי לוי עטרות | 0.09 / 0.09 |
| Jerusalem centre | hand: weekly (17 lines) | 14.2 | 22 | אושר עד תלפיות, רמי לוי עטרות | אושר עד תלפיות, רמי לוי עטרות | 20.64 / 20.64 |
| Jerusalem centre | hand: large (32 lines) | 20.2 | 27.8 | - | - | 0.0 / 0.0 |
| Jerusalem centre | drawn: 5 | 8.3 | 14.9 | רמי לוי עטרות, רמי לוי בית הפירות פת | רמי לוי עטרות, רמי לוי בית הפירות פת | 12.13 / 12.13 |
| Jerusalem centre | drawn: 10 | 9.3 | 14.9 | קינג סטור ואדי אלגוז', רמי לוי עטרות | קינג סטור ואדי אלגוז', רמי לוי עטרות | 17.43 / 17.43 |
| Jerusalem centre | drawn: 20 | 12.9 | 20.1 | - | - | 0.0 / 0.0 |
| Jerusalem centre | drawn: 40 | 18.7 | 27.9 | - | - | 0.0 / 0.0 |
| Holon | hand: small (6 lines) | 9.1 | 18.4 | - | - | 8.08 / 8.08 |
| Holon | hand: weekly (17 lines) | 13.6 | 20.7 | רמי לוי חולון, יוחננוף בת ים | רמי לוי חולון, יוחננוף בת ים | 20.99 / 20.99 |
| Holon | hand: large (32 lines) | 19.4 | 26.7 | רמי לוי חולון, יוחננוף בת ים | רמי לוי חולון, יוחננוף בת ים | 45.76 / 45.76 |
| Holon | drawn: 5 | 9 | 16.1 | - | - | 24.83 / 24.83 |
| Holon | drawn: 10 | 11.2 | 16.8 | רמי לוי חולון, טיב טעם בת ים | רמי לוי חולון, טיב טעם בת ים | 33.88 / 33.88 |
| Holon | drawn: 20 | 14 | 22 | - | - | 79.01 / 79.01 |
| Holon | drawn: 40 | 22.3 | 31.8 | - | - | 367.14 / 367.14 |
| Petah Tikva | hand: small (6 lines) | 9 | 17.5 | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | 3.36 / 3.36 |
| Petah Tikva | hand: weekly (17 lines) | 13.8 | 20.5 | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | 19.16 / 19.16 |
| Petah Tikva | hand: large (32 lines) | 19.4 | 27.9 | רמי לוי שטמפפר פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי שטמפפר פתח תקווה, יוחננוף סגולה פתח תקווה | 33.7 / 33.7 |
| Petah Tikva | drawn: 5 | 9.2 | 14.5 | אושר עד פתח תקווה - סגולה, רמי לוי שטמפפר פתח תקווה | אושר עד פתח תקווה - סגולה, רמי לוי שטמפפר פתח תקווה | 10.72 / 10.72 |
| Petah Tikva | drawn: 10 | 10.6 | 16.9 | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | 11.3 / 11.3 |
| Petah Tikva | drawn: 20 | 14.8 | 23.1 | טיב טעם מונטיפיורי פתח תקוה, יוחננוף סגולה פתח תקווה | טיב טעם מונטיפיורי פתח תקוה, יוחננוף סגולה פתח תקווה | 41.66 / 41.66 |
| Petah Tikva | drawn: 40 | 20.4 | 30.9 | - | - | 32.89 / 32.89 |

### Basket index on the real day (#44, dry run, production semantics)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `missing_items` שופרסל has no price for 11 basket items (milk-fresh-3, yellow-cheese-sliced-28, yogurt-plain-3, butter, eggs-l, cucumber, banana, pita, pasta-spaghetti, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` שופרסל: 4 lines use estimated weighed-goods prices
- warning: `missing_items` קרפור (מגה) has no price for 13 basket items (yellow-cheese-sliced-28, butter, hummus-plain, tomato, cucumber, onion, potato, banana, bread-standard, pita, pasta-spaghetti, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` קרפור (מגה): 1 lines use estimated weighed-goods prices
- warning: `missing_items` קינג סטור has no price for 17 basket items (cottage-5, yellow-cheese-sliced-28, butter, eggs-l, chicken-breast-fresh, hummus-plain, tomato, cucumber, potato, banana, bread-standard, pita, rice-persian, pasta-spaghetti, tuna-in-oil, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` קינג סטור: 1 lines use estimated weighed-goods prices
- warning: `missing_items` רמי לוי has no price for 6 basket items (hummus-plain, cucumber, potato, banana, pasta-spaghetti, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` רמי לוי: 3 lines use estimated weighed-goods prices
- warning: `missing_items` אושר עד has no price for 17 basket items (milk-fresh-3, white-cheese-5, yellow-cheese-sliced-28, yogurt-plain-3, eggs-l, chicken-breast-fresh, hummus-plain, tomato, cucumber, onion, banana, pita, pasta-spaghetti, sugar-white, mineral-water, bamba, chocolate-milk); it is listed but not ranked
- warning: `missing_items` יוחננוף has no price for 11 basket items (yellow-cheese-sliced-28, butter, eggs-l, hummus-plain, cucumber, potato, banana, pita, pasta-spaghetti, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` יוחננוף: 3 lines use estimated weighed-goods prices
- warning: `missing_items` טיב טעם has no price for 12 basket items (milk-fresh-3, yellow-cheese-sliced-28, yogurt-plain-3, butter, eggs-l, hummus-plain, pita, pasta-spaghetti, tuna-in-oil, mineral-water, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` טיב טעם: 6 lines use estimated weighed-goods prices
- error: `too_few_chains` only 0 chain(s) price the whole basket; at least 2 needed

Basket of 25 lines; price date 2026-10-22T08:05:02Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| שופרסל | - | 14 | 11 | 1 | no |
| קרפור (מגה) | - | 12 | 13 | 1 | no |
| קינג סטור | - | 8 | 17 | 2 | no |
| רמי לוי | - | 19 | 6 | 7 | no |
| אושר עד | - | 8 | 17 | 5 | no |
| יוחננוף | - | 14 | 11 | 4 | no |
| טיב טעם | - | 13 | 12 | 5 | no |

### Basket index on the real day (#44, dry run, stress)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `estimated_items` רמי לוי: 3 lines use estimated weighed-goods prices
- warning: `estimated_items` יוחננוף: 6 lines use estimated weighed-goods prices
- warning: `estimated_items` טיב טעם: 6 lines use estimated weighed-goods prices
- warning: `missing_items` שופרסל has no price for 1 basket items (pita); it is listed but not ranked
- warning: `estimated_items` שופרסל: 6 lines use estimated weighed-goods prices
- warning: `missing_items` קרפור (מגה) has no price for 3 basket items (onion, bread-standard, pita); it is listed but not ranked
- warning: `estimated_items` קרפור (מגה): 5 lines use estimated weighed-goods prices
- warning: `missing_items` קינג סטור has no price for 2 basket items (bread-standard, tuna-in-oil); it is listed but not ranked
- warning: `estimated_items` קינג סטור: 6 lines use estimated weighed-goods prices
- warning: `missing_items` אושר עד has no price for 4 basket items (chicken-breast-fresh, onion, banana, pita); it is listed but not ranked
- error: `implausible_spread` cheapest and dearest chain differ by 56.5% (limit 50.00%)

Basket of 25 lines; price date 2026-10-22T08:05:02Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| רמי לוי | 908.27 | 25 | 0 | 7 | yes |
| יוחננוף | 928.27 | 25 | 0 | 4 | yes |
| טיב טעם | 1421.25 | 25 | 0 | 5 | yes |
| שופרסל | - | 24 | 1 | 1 | no |
| קרפור (מגה) | - | 22 | 3 | 1 | no |
| קינג סטור | - | 23 | 2 | 2 | no |
| אושר עד | - | 21 | 4 | 5 | no |

### Basket lines that no chain prices: the real items that could have been them

Items whose names mention the product, with the attributes extraction gave them, the mapping they got and the rule judge's own reason (re-run for this report, nothing written). The `hint` columns are a reading aid of this script, not the catalog's rules.

#### `butter`: 60 listed of 209 name hits (0 skipped as not the food itself; chains looked in: shufersal, mega, king_store, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | חמאה רכה 250 גרם | ? / ? | butter | 250 g | butter close 0.89 review | review: butter (חמאה): similarity 0.61 \| critical match product_type=butter \| soft differs pack_size 250 vs 200 g \| level close, confidence 0.89 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.13 \| critical mismatch product |
| shufersal | חמאה מלוחה רכה 250גרם | ? / ? | butter | 250 g | butter close 0.81 review | review: butter (חמאה): similarity 0.52 \| critical match product_type=butter \| soft differs pack_size 250 vs 200 g \| level close, confidence 0.81 \| vetoed: grated-mozzarella (גבינה מגורדת (מוצרלה)): similarity 0.13 \| critical misma |
| shufersal | חמאה לה גל זהב 200 גרם | ? / ? | butter | 200 g | butter any_brand 0.76 review | review: butter (חמאה): similarity 0.46 \| critical match product_type=butter \| level any_brand, confidence 0.76 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.13 \| critical mismatch product_type butter vs sour_cream \| criti |
| shufersal | חמאה 60% אלוויר 200 גרם | ? / ? | butter | 200 g | butter any_brand 0.75 review | review: butter (חמאה): similarity 0.44 \| critical match product_type=butter \| level any_brand, confidence 0.75 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.10 \| critical mismatch product_type butter vs sour_cream; fat_pc |
| shufersal | חמאה מלוחה אלוויר 200 גר | ? / ? | butter | 200 g | butter any_brand 0.77 review | review: butter (חמאה): similarity 0.46 \| critical match product_type=butter \| level any_brand, confidence 0.77 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.11 \| critical mismatch product_type butter vs sour_cream \| criti |
| shufersal | סוכריות חמאה לל"ס80 ורטר | ? / ? | butter | 80 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.42 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; yogurt-strawberry (יוגורט תות): similarity 0.13 |
| shufersal | חמאה FERMA 82.5%גרם 200 | ? / ? | butter | 200 g | butter any_brand 0.75 review | review: butter (חמאה): similarity 0.43 \| critical match product_type=butter \| level any_brand, confidence 0.75 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.10 \| critical mismatch product_type butter vs sour_cream; fat_pc |
| shufersal | ביסקויט לקפה חמאה185רושן | ? / ? | butter | 185 g | butter close 0.63 review | review: butter (חמאה): similarity 0.29 \| critical match product_type=butter \| soft differs pack_size 185 vs 200 g \| level close, confidence 0.63 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.08 \| critical mismatch product |
| shufersal | חמאה 82.5% רושן 200 גרם | ? / ? | butter | 200 g | butter any_brand 0.74 review | review: butter (חמאה): similarity 0.43 \| critical match product_type=butter \| level any_brand, confidence 0.74 \| vetoed: labane-5 (לבנה 5%): similarity 0.25 \| critical mismatch product_type butter vs labane; fat_pct 82.5 vs 5 ; co |
| shufersal | הוטפופ טעם חמאה6*100גר | ? / ? | butter | 600 g | butter close 0.61 review | review: butter (חמאה): similarity 0.26 \| critical match product_type=butter \| soft differs pack_size 600 vs 200 g \| level close, confidence 0.61 \| vetoed: yogurt-plain-1-5 (יוגורט טבעי 1.5%): similarity 0.05 \| critical mismatch pr |
| shufersal | פופקו בטעם חמאה ודבש80גר | ? / ? | honey | 80 g | - | every candidate vetoed \| vetoed: peanut-butter (חמאת בוטנים): similarity 0.12 \| critical mismatch product_type honey vs peanut_butter; the canonical's words come only after 'בטעם' (a flavor, not the product) ; quinoa (קינואה): sim |
| shufersal | עוגיות חמאה ללת"ס 200 גר | ? / ? | sugar_white | 200 g | - | every candidate vetoed \| vetoed: jam-strawberry (ריבת תות): similarity 0.18 \| critical mismatch product_type sugar_white vs jam; name has 'עוגיות' (a derived product), canonical is 'ריבת תות' \| critical unknown flavor ; peanut-but |
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

#### `chocolate-milk`: 84 listed of 3233 name hits (0 skipped as not the food itself; chains looked in: shufersal, mega, king_store, ramilevy, osherad, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | חטיף שיבולת ושוקולד5 | ? / ? | chocolate_bar | 210 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.31 \| critical mismatch flavor chocolate vs milk; name has 'חטיף' (a derived product), canonical is 'שוקולד חלב' \| critical match product_type=chocolate |
| shufersal | תערובת לעוגת שוקולד425גר | ? / ? | chocolate_bar | 425 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.32 \| critical mismatch flavor chocolate vs milk; name has 'עוגת' (a derived product), canonical is 'שוקולד חלב' \| critical match product_type=chocolate |
| shufersal | שוקולד אקסלנס קרמל100גרם | ? / ? | chocolate_bar | 100 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.40 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.38 \| criti |
| shufersal | שוקולד מריר לינדט מלח 10 | ? / ? | chocolate_bar | 100 g | - | every candidate vetoed \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.68 \| critical mismatch flavor dark+salted vs dark \| critical match product_type=chocolate_bar ; chocolate-milk-bar (שוקולד חלב): similarity 0.37 \| cri |
| shufersal | סירופ שוקולד 680 גרם | ? / ? | chocolate_bar | 680 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.44 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.43 \| criti |
| shufersal | שוקולד מריר עם מרציפן100 | ? / ? | chocolate_bar | 100 g | - | every candidate vetoed \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.70 \| critical mismatch flavor dark+other vs dark \| critical match product_type=chocolate_bar ; chocolate-milk-bar (שוקולד חלב): similarity 0.37 \| crit |
| shufersal | שוקולד חלב+אגוזי לוז 100 | ? / ? | chocolate_bar | 100 g | chocolate-milk-bar any_brand 0.92 | accept: chocolate-milk-bar (שוקולד חלב): similarity 0.65 \| critical match product_type=chocolate_bar, flavor=milk \| level any_brand, confidence 0.92 \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.39 \| critical mismatch f |
| shufersal | שוקולד ריטר מריר שקד100ג | ? / ? | chocolate_bar | 100 g | chocolate-dark-bar any_brand 0.96 | accept: chocolate-dark-bar (שוקולד מריר): similarity 0.70 \| critical match product_type=chocolate_bar, flavor=dark \| level any_brand, confidence 0.96 \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.40 \| critical mismatch f |
| shufersal | שוקולד לינדור סטיק 38גרם | ? / ? | chocolate_bar | 38 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.44 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.42 \| criti |
| shufersal | קורני חט.דגנים+שוקולד6יח | ? / ? | - | 150 g | - | rejected (confidence 0.42 < 0.6): dessert-chocolate (מעדן חלב שוקולד): similarity 0.23 \| critical match flavor=chocolate \| critical unknown product_type \| soft differs pack_size 150 vs 125 g \| ambiguous with wafers-chocolate \| lev |
| shufersal | ח.דגנים שוקו.מריר6 קורני | ? / ? | - | 138 g | - | rejected (confidence 0.42 < 0.6): dessert-chocolate (מעדן חלב שוקולד): similarity 0.17 \| critical match flavor=chocolate \| critical unknown product_type \| soft differs pack_size 138 vs 125 g \| ambiguous with wafers-chocolate \| lev |
| shufersal | קורני FREE שוקולד חלב6יח | ? / ? | chocolate_bar | 120 g | chocolate-milk-bar close 0.83 review | review: chocolate-milk-bar (שוקולד חלב): similarity 0.54 \| critical match product_type=chocolate_bar, flavor=milk \| soft differs pack_size 120 vs 100 g \| level close, confidence 0.83 \| vetoed: chocolate-dark-bar (שוקולד מריר): sim |
| mega | VANINI שוקולד מריר 7 | ? / ? | chocolate_bar | 100 g | chocolate-dark-bar any_brand 1.00 | accept: chocolate-dark-bar (שוקולד מריר): similarity 0.75 \| critical match product_type=chocolate_bar, flavor=dark \| level any_brand, confidence 1.00 \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.44 \| critical mismatch f |
| mega | שוקו-גראני ביסקוויט | ? / ? | tea_biscuits | 200 g | tea-biscuits any_brand 0.68 review | review: tea-biscuits (ביסקוויטים (פתי בר)): similarity 0.36 \| critical match product_type=tea_biscuits \| level any_brand, confidence 0.68 \| vetoed: bisli-grill (ביסלי גריל): similarity 0.27 \| critical mismatch product_type tea_bis |
| mega | עוגיות בארקט שוקולד | ? / ? | - | 240 g | - | every candidate vetoed \| vetoed: chocolate-spread (ממרח שוקולד): similarity 0.42 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'ממרח שוקולד' \| critical unknown product_type ; chocolate-milk-bar (שוקולד חל |
| mega | טארטלט שוקולד ואגוזי | ? / ? | chocolate_bar | 150 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.37 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.34 \| criti |
| mega | עוגיות שוקוצ'יפס  50 | ? / ? | - | 500 g | - | every candidate vetoed \| vetoed: french-fries-frozen (צ'יפס קפוא): similarity 0.31 \| critical mismatch name has 'עוגיות' (a derived product), canonical is "צ'יפס קפוא" \| critical unknown product_type ; chicken-thigh-boneless-froze |
| mega | עוגיות שוקוצ'יפס לבן | ? / ? | - | 500 g | - | every candidate vetoed \| vetoed: sugar-white (סוכר לבן): similarity 0.34 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'סוכר לבן' \| critical unknown product_type ; flour-white (קמח לבן): similarity 0.33 \| |
| mega | שוקו תנובה 2.7% שומן | ? / ? | chocolate_milk | 1000 ml | chocolate-milk any_brand 0.82 review | review: chocolate-milk (שוקו): similarity 0.52 \| critical match product_type=chocolate_milk \| level any_brand, confidence 0.82 \| vetoed: cooking-cream-10 (שמנת לבישול 10%): similarity 0.14 \| critical mismatch product_type chocolat |
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

#### `cottage-5`: 6 listed of 6 name hits (0 skipped as not the food itself; chains looked in: king_store)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| king_store | קוטג' 5% שומן 250 ג' טרה | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.87 review | review: cottage-5 (קוטג' 5%): similarity 0.59 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.87 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.39 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' 5% שומן 250 ג' שטראוס | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.84 review | review: cottage-5 (קוטג' 5%): similarity 0.55 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.84 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.37 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' בקטנה % 5 100 ג' תנובה | ? / ? | cottage_cheese | 100 g | - | rejected (confidence 0.51 < 0.6): cottage-5 (קוטג' 5%): similarity 0.36 \| critical match product_type=cottage_cheese \| critical unknown fat_pct \| soft differs pack_size 100 vs 250 g \| ambiguous with cottage-3 \| level close, confid |
| king_store | קוטג תנובה גביע 250 גר5% | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.70 review | review: cottage-5 (קוטג' 5%): similarity 0.37 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.70 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.33 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' 5% 250 ג' תנובה | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.89 review | review: cottage-5 (קוטג' 5%): similarity 0.61 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.89 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.39 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' 9% שומן 250 ג' תנובה | ? / ? | cottage_cheese | 250 g | - | every candidate vetoed \| vetoed: cottage-5 (קוטג' 5%): similarity 0.38 \| critical mismatch fat_pct 9 vs 5 \| critical match product_type=cottage_cheese ; cottage-3 (קוטג' 3%): similarity 0.38 \| critical mismatch fat_pct 9 vs 3 \| cr |

#### `eggs-l`: 145 listed of 262 name hits (114 skipped as not the food itself; chains looked in: shufersal, king_store, osherad, yohananof, tivtaam)

Name hint of the size against what the item got (served = no review flag):

| size words in the name | result | items |
|---|---|---|
| ? | review | 12 |
| ? | unmapped | 76 |
| L | eggs-free-range-l any_brand | 2 |
| L | eggs-l close | 2 |
| L | review | 18 |
| L | unmapped | 4 |
| M | review | 21 |
| M | unmapped | 5 |
| XL | review | 5 |

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | 12 ביצי משק טריות L לסר | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.68 review | review: eggs-l (ביצים L): similarity 0.35 \| critical match product_type=eggs_l \| level any_brand, confidence 0.68 \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.43 \| critical mismatch product_type eggs_l vs eggs_free_rang |
| shufersal | 12 ביצי משק טריות M לסר | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.68 review | review: eggs-m (ביצים M): similarity 0.35 \| critical match product_type=eggs_m \| level any_brand, confidence 0.68 \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.28 \| critical mismatch product_type eggs_m vs eggs_free_rang |
| shufersal | ביצים ארוזות 18יח L | L / 18 | eggs_l | 18 unit | eggs-l close 0.92 | accept: eggs-l (ביצים L): similarity 0.65 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.92 \| vetoed: eggs-m (ביצים M): similarity 0.51 \| critical mismatch product_type eggs |
| shufersal | ביצי חופש 12יח L | L / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 1.00 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.86 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 1.00 \| vetoed: eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs_free_ran |
| shufersal | ביצי חופש 12יח M | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.69 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs vs eggs_m ; egg |
| shufersal | 12ביצי אומגה3 M לסר | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.30 \| critical mismatch product_type eggs vs eggs_m ; eggs-free-range-l (ביצי חופש L): similarity 0.16 \| critical mismatch product_type eggs vs eggs_free_range_l ; egg |
| shufersal | נודלס ביצים 500 גרם | ? / ? | - | 500 g | - | rejected (confidence 0.34 < 0.6): egg-noodles (אטריות ביצים): similarity 0.37 \| critical unknown product_type \| level any_brand, confidence 0.34 |
| shufersal | ביצי שוקול.סוניק 3*20גרם | ? / 60 | - | 60 g | - | rejected (confidence 0.24 < 0.6): wafers-chocolate (ופלים בטעם שוקולד): similarity 0.25 \| critical unknown product_type, flavor \| soft differs pack_size 60 vs 500 g \| ambiguous with chocolate-milk-bar \| level close, confidence 0.2 |
| king_store | ביצים 18 יח' L לסר | L / 18 | eggs_l | 18 unit | eggs-l close 0.95 | accept: eggs-l (ביצים L): similarity 0.68 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.95 \| vetoed: eggs-m (ביצים M): similarity 0.48 \| critical mismatch product_type eggs |
| king_store | ביצים מידיום 12 יח' | ? / 12 | eggs_m | 12 unit | eggs-m any_brand 0.78 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| level any_brand, confidence 0.78 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| king_store | ביצים מידיום 12 יח' | ? / 12 | eggs_m | 12 unit | eggs-m any_brand 0.78 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| level any_brand, confidence 0.78 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| king_store | נודלס ביצים להקפצה מאסטר שף 400 ג' | ? / ? | - | 400 g | - | rejected (confidence 0.26 < 0.6): egg-noodles (אטריות ביצים): similarity 0.28 \| critical unknown product_type \| soft differs pack_size 400 vs 500 g \| ambiguous with pickled-cucumbers \| level close, confidence 0.26 |
| king_store | ביצים לארג' 18 יח' | ? / 18 | eggs_l | 18 unit | eggs-l close 0.80 review | review: eggs-l (ביצים L): similarity 0.50 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.80 \| vetoed: eggs-m (ביצים M): similarity 0.50 \| critical mismatch product_type eggs |
| king_store | איטריות ביצים פפרדלה 250ג' ברילה | ? / ? | - | 250 g | - | rejected (confidence 0.28 < 0.6): mushrooms-fresh (פטריות שמפיניון טריות): similarity 0.30 \| critical unknown product_type, state \| level any_brand, confidence 0.28 |
| king_store | ביצים מידיום 30 יח' | ? / 30 | eggs_m | 30 unit | eggs-m close 0.79 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs |
| king_store | ביצים מידיום עטוף 30יח' | ? / 30 | eggs_m | 30 unit | eggs-m close 0.73 review | review: eggs-m (ביצים M): similarity 0.41 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.73 \| vetoed: eggs-l (ביצים L): similarity 0.41 \| critical mismatch product_type eggs |
| king_store | ביצים לארג' 12 יח' | ? / 12 | eggs_l | 12 unit | eggs-l any_brand 0.79 review | review: eggs-l (ביצים L): similarity 0.49 \| critical match product_type=eggs_l \| level any_brand, confidence 0.79 \| vetoed: eggs-m (ביצים M): similarity 0.49 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| osherad | ביצים 2*30 יח' בינונ | M / 60 | eggs_m | 60 unit | eggs-m close 0.79 review | review: eggs-m (ביצים M): similarity 0.49 \| critical match product_type=eggs_m \| soft differs pack_size 60 vs 12 unit \| level close, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.49 \| critical mismatch product_type eggs |
| osherad | ביצים 30 יח בינוני ל | M / 30 | eggs_m | 30 unit | eggs-m close 0.78 review | review: eggs-m (ביצים M): similarity 0.47 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.78 \| vetoed: eggs-l (ביצים L): similarity 0.47 \| critical mismatch product_type eggs |
| osherad | ביצים 18 יח' בינוני | M / 18 | eggs_m | 18 unit | eggs-m close 0.81 review | review: eggs-m (ביצים M): similarity 0.51 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.81 \| vetoed: eggs-l (ביצים L): similarity 0.51 \| critical mismatch product_type eggs |
| osherad | ביצים 30 יח' בינוני | M / 30 | eggs_m | 30 unit | eggs-m close 0.80 review | review: eggs-m (ביצים M): similarity 0.50 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.80 \| vetoed: eggs-l (ביצים L): similarity 0.50 \| critical mismatch product_type eggs |
| osherad | ביצים 30 יח' גדול מן | L / 30 | eggs_l | 30 unit | eggs-l close 0.76 review | review: eggs-l (ביצים L): similarity 0.45 \| critical match product_type=eggs_l \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.76 \| vetoed: eggs-m (ביצים M): similarity 0.45 \| critical mismatch product_type eggs |
| osherad | ביצים 18 יח' גדול מן | L / 18 | eggs_l | 18 unit | eggs-l close 0.77 review | review: eggs-l (ביצים L): similarity 0.46 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.77 \| vetoed: eggs-m (ביצים M): similarity 0.46 \| critical mismatch product_type eggs |
| osherad | ביצים אורגני 12 יח' | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.47 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.44 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| osherad | ביצי חופש 20 יח' גדו | ? / 20 | eggs | 20 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.62 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.25 \| critical mismatch product_type eggs vs eggs_xl ;  |
| osherad | ביצי אומגה 30 יח' בי | ? / 30 | eggs | 30 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.36 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.28 \| critical mismatch product_type eggs vs eggs_xl ;  |
| osherad | ביצי חופש 20 יח' גדו | ? / 20 | eggs | 20 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.62 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.25 \| critical mismatch product_type eggs vs eggs_xl ;  |
| osherad | ביצים אורגניות  12 י | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| osherad | פורס ביצים אולינהום | ? / ? | - | -  | - | rejected (confidence 0.45 < 0.6): eggs-l (ביצים L): similarity 0.51 \| critical unknown product_type \| ambiguous with eggs-m \| level any_brand, confidence 0.45 |
| osherad | ביצים 18 יח גדול לסר | L / 18 | eggs_l | 18 unit | eggs-l close 0.76 review | review: eggs-l (ביצים L): similarity 0.45 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.76 \| vetoed: eggs-m (ביצים M): similarity 0.45 \| critical mismatch product_type eggs |
| osherad | מארז ביצים בינוני 2* | M / ? | eggs_m | 60 unit | eggs-m close 0.79 review | review: eggs-m (ביצים M): similarity 0.49 \| critical match product_type=eggs_m \| soft differs pack_size 60 vs 12 unit \| level close, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.49 \| critical mismatch product_type eggs |
| osherad | ביצים 18 יח בינוני ל | M / 18 | eggs_m | 18 unit | eggs-m close 0.78 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.78 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs |
| osherad | ביצים אומגה 30 יח גד | ? / 30 | eggs | 30 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.43 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.43 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| osherad | ביצים אומגה 12 יח גד | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| osherad | ביצים חופש 12 יח גדו | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.47 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-l (ביצים L): similarity 0.43 \| critical mismatch product_type eggs vs eggs_l ; egg |
| osherad | ביצים אומגה 12 יח' ב | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.44 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| osherad | ג'ל ביצת עין וס.קופצ | ? / ? | - | 168 g | - | rejected (confidence 0.24 < 0.6): cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.16 \| critical unknown product_type, fat_pct, flavor \| soft differs pack_size 168 vs 200 g \| ambiguous with couscous \| level close, confid |
| osherad | ביצים 12 יח בינוני ר | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.77 review | review: eggs-m (ביצים M): similarity 0.46 \| critical match product_type=eggs_m \| level any_brand, confidence 0.77 \| vetoed: eggs-l (ביצים L): similarity 0.46 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| osherad | ביצים 12 יח ענק XL ל | XL / 12 | eggs_xl | 12 unit | eggs-xl any_brand 0.86 review | review: eggs-xl (ביצים XL): similarity 0.57 \| critical match product_type=eggs_xl \| level any_brand, confidence 0.86 \| vetoed: eggs-m (ביצים M): similarity 0.35 \| critical mismatch product_type eggs_xl vs eggs_m ; eggs-l (ביצים L) |
| osherad | ביצים 12 יח' בינוני | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.79 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| level any_brand, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| osherad | ביצי אומגה 30 יח' גד | ? / 30 | eggs | 30 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.28 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.22 \| critical mismatch product_type eggs vs eggs_xl ;  |
| osherad | ביצים 12 יח' גדול זג | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.74 review | review: eggs-l (ביצים L): similarity 0.42 \| critical match product_type=eggs_l \| level any_brand, confidence 0.74 \| vetoed: eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| osherad | ג'ל ביצת עין וס.קופצ | ? / ? | - | 98 g | - | rejected (confidence 0.24 < 0.6): cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.16 \| critical unknown product_type, fat_pct, flavor \| soft differs pack_size 98 vs 200 g \| ambiguous with couscous \| level close, confide |
| osherad | ביצים 12 יח' ענק א. | XL / 12 | eggs_xl | 12 unit | eggs-xl any_brand 0.72 review | review: eggs-xl (ביצים XL): similarity 0.40 \| critical match product_type=eggs_xl \| level any_brand, confidence 0.72 \| vetoed: eggs-m (ביצים M): similarity 0.45 \| critical mismatch product_type eggs_xl vs eggs_m ; eggs-l (ביצים L) |
| yohananof | ביצי דג שיבוט 200 גר | ? / ? | - | 200 g | - | rejected (confidence 0.24 < 0.6): rolled-oats (שיבולת שועל): similarity 0.23 \| critical unknown product_type \| soft differs pack_size 200 vs 500 g \| ambiguous with green-beans-frozen \| level close, confidence 0.24 |
| yohananof | ביצים אורגני 12 יח ג | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.41 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצי חופש 12 יח גדול | L / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 0.89 review | review: eggs-free-range-l (ביצי חופש L): similarity 0.61 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 0.89 \| vetoed: eggs-xl (ביצים XL): similarity 0.22 \| critical mismatch product_type eggs_free_r |
| yohananof | ביצים 12 יח גדול | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.79 review | review: eggs-l (ביצים L): similarity 0.49 \| critical match product_type=eggs_l \| level any_brand, confidence 0.79 \| vetoed: eggs-m (ביצים M): similarity 0.49 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| yohananof | ביצים 12 יח בינוני | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.79 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| level any_brand, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| yohananof | ביצים אורגני 12 יח ב | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.45 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.43 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצים אורגני 12 יח ע | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.41 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצים אומגה 3  12 יח | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצים אומגה 3 גדול 1 | L / ? | eggs | 1 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| yohananof | ביצי חופש | ? / ? | eggs | 1 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.89 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.35 \| critical mismatch product_type eggs vs eggs_xl ;  |
| yohananof | ביצים אומגה 3 גדול | L / ? | eggs | 1 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.45 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.45 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| yohananof | פורס ביצים | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): parsley (פטרוזיליה): similarity 0.06 \| critical unknown product_type, state \| ambiguous with cling-wrap \| level any_brand, confidence 0.24 |
| yohananof | פורס ביצים כפול | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): parsley (פטרוזיליה): similarity 0.05 \| critical unknown product_type, state \| ambiguous with green-onion \| level any_brand, confidence 0.24 |
| yohananof | פורס ביצים BETTER | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): cling-wrap (ניילון נצמד): similarity 0.06 \| critical unknown product_type \| ambiguous with baguette \| level any_brand, confidence 0.24 |
| yohananof | ביצים 12 יח בינוני | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.79 review | review: eggs-m (ביצים M): similarity 0.48 \| critical match product_type=eggs_m \| level any_brand, confidence 0.79 \| vetoed: eggs-l (ביצים L): similarity 0.48 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| yohananof | ביצים 12 יח  גדול | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.79 review | review: eggs-l (ביצים L): similarity 0.49 \| critical match product_type=eggs_l \| level any_brand, confidence 0.79 \| vetoed: eggs-m (ביצים M): similarity 0.49 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| yohananof | ביצים 18 יח בינוני | M / 18 | eggs_m | 18 unit | eggs-m close 0.81 review | review: eggs-m (ביצים M): similarity 0.51 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.81 \| vetoed: eggs-l (ביצים L): similarity 0.51 \| critical mismatch product_type eggs |
| yohananof | ביצים 18 יח גדול | L / 18 | eggs_l | 18 unit | eggs-l close 0.80 review | review: eggs-l (ביצים L): similarity 0.50 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.80 \| vetoed: eggs-m (ביצים M): similarity 0.50 \| critical mismatch product_type eggs |
| yohananof | ביצים 30 יח בינוני | M / 30 | eggs_m | 30 unit | eggs-m close 0.80 review | review: eggs-m (ביצים M): similarity 0.50 \| critical match product_type=eggs_m \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.80 \| vetoed: eggs-l (ביצים L): similarity 0.50 \| critical mismatch product_type eggs |
| yohananof | ביצים 30 יח גדול | L / 30 | eggs_l | 30 unit | eggs-l close 0.79 review | review: eggs-l (ביצים L): similarity 0.49 \| critical match product_type=eggs_l \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.79 \| vetoed: eggs-m (ביצים M): similarity 0.49 \| critical mismatch product_type eggs |
| yohananof | ביצים 30 יח ענק | XL / 30 | eggs_xl | 30 unit | eggs-xl close 0.76 review | review: eggs-xl (ביצים XL): similarity 0.45 \| critical match product_type=eggs_xl \| soft differs pack_size 30 vs 12 unit \| level close, confidence 0.76 \| vetoed: eggs-m (ביצים M): similarity 0.51 \| critical mismatch product_type e |
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
| yohananof | ביצים 12 יח ענק | XL / 12 | eggs_xl | 12 unit | eggs-xl any_brand 0.75 review | review: eggs-xl (ביצים XL): similarity 0.44 \| critical match product_type=eggs_xl \| level any_brand, confidence 0.75 \| vetoed: eggs-m (ביצים M): similarity 0.50 \| critical mismatch product_type eggs_xl vs eggs_m ; eggs-l (ביצים L) |
| yohananof | ביצי דג טונה אדמחוט | ? / ? | - | 85 g | - | rejected (confidence 0.33 < 0.6): tuna-in-oil (טונה בשמן): similarity 0.36 \| critical unknown product_type \| soft differs pack_size 85 vs 640 g \| ambiguous with tuna-in-water \| level close, confidence 0.33 |
| yohananof | ביצת עין 220 גרם | ? / ? | - | 220 g | - | rejected (confidence 0.24 < 0.6): cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.15 \| critical unknown product_type, fat_pct, flavor \| soft differs pack_size 220 vs 200 g \| ambiguous with sunflower-seeds \| level close, |
| yohananof | ביצים עלומות 200 גרם | ? / ? | - | 200 g | - | rejected (confidence 0.24 < 0.6): sunflower-seeds (גרעינים): similarity 0.17 \| critical unknown product_type \| level any_brand, confidence 0.24 |
| yohananof | ביצים 18 יח בינוני | M / 18 | eggs_m | 18 unit | eggs-m close 0.81 review | review: eggs-m (ביצים M): similarity 0.51 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.81 \| vetoed: eggs-l (ביצים L): similarity 0.51 \| critical mismatch product_type eggs |
| yohananof | ביצי דג בורי אדמחוט | ? / ? | - | 125 g | - | rejected (confidence 0.24 < 0.6): burekas-potato (בורקס תפוחי אדמה קפוא): similarity 0.24 \| critical unknown product_type, flavor \| soft differs pack_size 125 vs 800 g \| ambiguous with egg-noodles \| level close, confidence 0.24 |
| yohananof | ביצה קשה | ? / ? | eggs | 1 unit | - | every candidate vetoed \| vetoed: eggs-xl (ביצים XL): similarity 0.24 \| critical mismatch product_type eggs vs eggs_xl ; eggs-l (ביצים L): similarity 0.21 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similari |
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
| tivtaam | ביצים אריזון 12 גדול | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.74 review | review: eggs-l (ביצים L): similarity 0.43 \| critical match product_type=eggs_l \| level any_brand, confidence 0.74 \| vetoed: eggs-m (ביצים M): similarity 0.43 \| critical mismatch product_type eggs_l vs eggs_m ; eggs-xl (ביצים XL):  |
| tivtaam | ביצים אריזון 12 בינוני | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.76 review | review: eggs-m (ביצים M): similarity 0.44 \| critical match product_type=eggs_m \| level any_brand, confidence 0.76 \| vetoed: eggs-l (ביצים L): similarity 0.44 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| tivtaam | ביצים אריזון 18 גדול | L / 18 | eggs_l | 18 unit | eggs-l close 0.76 review | review: eggs-l (ביצים L): similarity 0.45 \| critical match product_type=eggs_l \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.76 \| vetoed: eggs-m (ביצים M): similarity 0.45 \| critical mismatch product_type eggs |
| tivtaam | ביצים אריזון 18 בינוני | M / 18 | eggs_m | 18 unit | eggs-m close 0.77 review | review: eggs-m (ביצים M): similarity 0.47 \| critical match product_type=eggs_m \| soft differs pack_size 18 vs 12 unit \| level close, confidence 0.77 \| vetoed: eggs-l (ביצים L): similarity 0.47 \| critical mismatch product_type eggs |
| tivtaam | ביצים אומגה 3 30 יח M | M / 30 | eggs | 30 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.58 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.40 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| tivtaam | ביצים אורגניות 12 יח L | L / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.59 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.42 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| tivtaam | ביצים אומגה 3 12 יח L | L / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-l (ביצים L): similarity 0.58 \| critical mismatch product_type eggs vs eggs_l ; eggs-m (ביצים M): similarity 0.40 \| critical mismatch product_type eggs vs eggs_m ; eggs-xl (ביצים XL): similarit |
| tivtaam | ביצי חופש 12 יח L | L / 12 | eggs_free_range_l | 12 unit | eggs-free-range-l any_brand 1.00 | accept: eggs-free-range-l (ביצי חופש L): similarity 0.83 \| critical match product_type=eggs_free_range_l \| level any_brand, confidence 1.00 \| vetoed: eggs-l (ביצים L): similarity 0.40 \| critical mismatch product_type eggs_free_ran |
| tivtaam | ביצי חופש 12 יח M | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.66 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-m (ביצים M): similarity 0.40 \| critical mismatch product_type eggs vs eggs_m ; egg |
| tivtaam | ביצים אומגה M 12 יח | M / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.62 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
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
| tivtaam | ביצי שליו 20 יח | ? / 20 | eggs | 20 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.37 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.27 \| critical mismatch product_type eggs vs eggs_xl ;  |
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
| tivtaam | ביצה פלוס 12 יח L | L / 12 | eggs_l | 12 unit | eggs-l any_brand 0.65 review | review: eggs-l (ביצים L): similarity 0.32 \| critical match product_type=eggs_l \| level any_brand, confidence 0.65 \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.30 \| critical mismatch product_type eggs_l vs eggs_free_rang |
| tivtaam | ביצי חופש 12 יח | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-free-range-l (ביצי חופש L): similarity 0.72 \| critical mismatch product_type eggs vs eggs_free_range_l ; eggs-xl (ביצים XL): similarity 0.25 \| critical mismatch product_type eggs vs eggs_xl ;  |
| tivtaam | ביצים רגילות  12 יח M | M / 12 | eggs_m | 12 unit | eggs-m any_brand 0.90 review | review: eggs-m (ביצים M): similarity 0.62 \| critical match product_type=eggs_m \| level any_brand, confidence 0.90 \| vetoed: eggs-l (ביצים L): similarity 0.38 \| critical mismatch product_type eggs_m vs eggs_l ; eggs-xl (ביצים XL):  |
| tivtaam | ביצים אורגניות 12 יח | ? / 12 | eggs | 12 unit | - | every candidate vetoed \| vetoed: eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs vs eggs_m ; eggs-l (ביצים L): similarity 0.42 \| critical mismatch product_type eggs vs eggs_l ; eggs-xl (ביצים XL): similarit |
| tivtaam | איקרה ביצי דג טרוטונית והרינג עם אבקדו | ? / ? | - | 180 g | - | rejected (confidence 0.24 < 0.6): laundry-powder (אבקת כביסה): similarity 0.18 \| critical unknown product_type \| soft differs pack_size 180 vs 3000 g \| ambiguous with egg-noodles \| level close, confidence 0.24 \| vetoed: soup-powde |
| tivtaam | חותך ביצים F | ? / ? | - | 1 unit | - | rejected (confidence 0.50 < 0.6): eggs-l (ביצים L): similarity 0.57 \| critical unknown product_type \| soft differs pack_size 1 vs 12 unit \| ambiguous with eggs-m \| level close, confidence 0.50 |
| tivtaam | ביצים אריזון 12 ענק | XL / 12 | eggs_xl | 12 unit | eggs-xl any_brand 0.71 review | review: eggs-xl (ביצים XL): similarity 0.39 \| critical match product_type=eggs_xl \| level any_brand, confidence 0.71 \| vetoed: eggs-m (ביצים M): similarity 0.44 \| critical mismatch product_type eggs_xl vs eggs_m ; eggs-l (ביצים L) |
| tivtaam | חותך ביצים ABS שחור | ? / ? | - | 1 unit | - | rejected (confidence 0.24 < 0.6): dill (שמיר): similarity 0.12 \| critical unknown product_type, state \| level any_brand, confidence 0.24 |
| tivtaam | מארז ביצי דג שחור מצונן במלח 56.8+113 גר | ? / ? | salt | 113 g | salt close 0.60 review | review: salt (מלח): similarity 0.20 \| critical match product_type=salt \| soft differs pack_size 113 vs 1000 g \| level close, confidence 0.60 \| vetoed: black-pepper (פלפל שחור): similarity 0.18 \| critical mismatch product_type salt |
| tivtaam | ביצי דג שחור בופין במלח 56.8 גר | ? / ? | salt | 56.8 g | salt close 0.60 review | review: salt (מלח): similarity 0.16 \| critical match product_type=salt \| soft differs pack_size 56.8 vs 1000 g \| level close, confidence 0.60 \| vetoed: black-pepper (פלפל שחור): similarity 0.23 \| critical mismatch product_type sal |

#### `milk-fresh-3`: 36 listed of 1141 name hits (0 skipped as not the food itself; chains looked in: shufersal, osherad, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | שוק.ריטר חלב אגוז שלם100 | ? / ? | chocolate_bar | 100 g | chocolate-milk-bar any_brand 0.69 review | review: chocolate-milk-bar (שוקולד חלב): similarity 0.36 \| critical match product_type=chocolate_bar, flavor=milk \| level any_brand, confidence 0.69 \| vetoed: halva (חלבה): similarity 0.17 \| critical mismatch product_type chocolat |
| shufersal | שוקולד חלב+אגוזי לוז 100 | ? / ? | chocolate_bar | 100 g | chocolate-milk-bar any_brand 0.92 | accept: chocolate-milk-bar (שוקולד חלב): similarity 0.65 \| critical match product_type=chocolate_bar, flavor=milk \| level any_brand, confidence 0.92 \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.39 \| critical mismatch f |
| shufersal | ש.חלב עם פיסטוק קלוי100ג | ? / ? | milk | 100 g | - | every candidate vetoed \| vetoed: dessert-vanilla (מעדן חלב וניל): similarity 0.23 \| critical mismatch product_type milk vs dairy_dessert \| critical unknown flavor ; dessert-chocolate (מעדן חלב שוקולד): similarity 0.22 \| critical m |
| shufersal | קורני FREE שוקולד חלב6יח | ? / ? | chocolate_bar | 120 g | chocolate-milk-bar close 0.83 review | review: chocolate-milk-bar (שוקולד חלב): similarity 0.54 \| critical match product_type=chocolate_bar, flavor=milk \| soft differs pack_size 120 vs 100 g \| level close, confidence 0.83 \| vetoed: chocolate-dark-bar (שוקולד מריר): sim |
| shufersal | שוקולד חלב אגוזי לוז100ג | ? / ? | chocolate_bar | 100 g | chocolate-milk-bar any_brand 0.93 | accept: chocolate-milk-bar (שוקולד חלב): similarity 0.67 \| critical match product_type=chocolate_bar, flavor=milk \| level any_brand, confidence 0.93 \| vetoed: chocolate-dark-bar (שוקולד מריר): similarity 0.39 \| critical mismatch f |
| shufersal | שוק.חלב עם אגוזי לוז100ג | ? / ? | chocolate_bar | 100 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.34 \| critical mismatch flavor milk+other vs milk \| critical match product_type=chocolate_bar ; halva (חלבה): similarity 0.17 \| critical mismatch produc |
| shufersal | שוקולד חלב שקדים 100 גרם | ? / ? | almond_drink | 100 g | - | every candidate vetoed \| vetoed: coffee-turkish (קפה שחור טחון): similarity 0.03 \| critical mismatch product_type almond_drink vs coffee_turkish ; coffee-instant (קפה נמס): similarity 0.00 \| critical mismatch product_type almond_d |
| shufersal | חלב מרוכז ממותק 370 גרם | ? / ? | milk | 370 g | - | every candidate vetoed \| vetoed: dessert-vanilla (מעדן חלב וניל): similarity 0.25 \| critical mismatch product_type milk vs dairy_dessert \| critical unknown flavor ; dessert-chocolate (מעדן חלב שוקולד): similarity 0.19 \| critical m |
| shufersal | סוכריות טופי חלב205 רושן | ? / ? | milk | 205 g | - | every candidate vetoed \| vetoed: dessert-vanilla (מעדן חלב וניל): similarity 0.09 \| critical mismatch product_type milk vs dairy_dessert; name has 'סוכריות' (a derived product), canonical is 'מעדן חלב וניל' \| critical unknown flav |
| shufersal | חטיף שוקולד חלב מרוכז43ג | ? / ? | chocolate_bar | 43 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.68 \| critical mismatch name has 'חטיף' (a derived product), canonical is 'שוקולד חלב' \| critical match product_type=chocolate_bar, flavor=milk ; chocol |
| shufersal | ביסקויט לקפה חלב185 רושן | ? / ? | - | 185 g | - | rejected (confidence 0.24 < 0.6): tea-biscuits (ביסקוויטים (פתי בר)): similarity 0.23 \| critical unknown product_type \| soft differs pack_size 185 vs 200 g \| ambiguous with halva \| level close, confidence 0.24 \| vetoed: bisli-onio |
| shufersal | סוכריות קרם חלב150ג רושן | ? / ? | - | 150 g | - | rejected (confidence 0.26 < 0.6): sugar-white (סוכר לבן): similarity 0.27 \| critical unknown product_type \| soft differs pack_size 150 vs 1000 g \| ambiguous with sugar-brown \| level close, confidence 0.26 \| vetoed: mushrooms-fresh |
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

#### `pasta-spaghetti`: 73 listed of 128 name hits (0 skipped as not the food itself; chains looked in: shufersal, mega, king_store, ramilevy, osherad, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | פסטה ספגטי מס 8 אסם 500ג | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.81 review | review: pasta-spaghetti (ספגטי): similarity 0.51 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.81 \| vetoed: pasta-penne (פסטה פנה): similarity 0.38 \| critical mismatch product_type pasta_spaghetti v |
| shufersal | מנה חמה ספגטי בולונז 65ג | ? / ? | pasta_spaghetti | 65 g | pasta-spaghetti close 0.83 review | review: pasta-spaghetti (ספגטי): similarity 0.53 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 65 vs 500 g \| level close, confidence 0.83 \| vetoed: mayonnaise (מיונז): similarity 0.18 \| critical mismatch p |
| shufersal | ספגטיני מספר 3 500 גרם | ? / ? | - | 500 g | - | rejected (confidence 0.34 < 0.6): pasta-spaghetti (ספגטי): similarity 0.38 \| critical unknown product_type \| level any_brand, confidence 0.34 |
| shufersal | ספגטי מס 5 מוריני 500ג | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.81 review | review: pasta-spaghetti (ספגטי): similarity 0.52 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.81 \| vetoed: rice-basmati (אורז בסמטי): similarity 0.17 \| critical mismatch product_type pasta_spaghett |
| shufersal | ספגטי ללא גלוטן 400 גרם | ? / ? | pasta_spaghetti | 400 g | pasta-spaghetti close 0.79 review | review: pasta-spaghetti (ספגטי): similarity 0.48 \| critical match product_type=pasta_spaghetti \| soft differs diet variant 'ללא גלוטן'; pack_size 400 vs 500 g \| level close, confidence 0.79 \| vetoed: granola (גרנולה): similarity 0 |
| shufersal | ספגטי מס 5 MANTANINO | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.55 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.84 \| vetoed: rice-basmati (אורז בסמטי): similarity 0.12 \| critical mismatch product_type pasta_spaghett |
| shufersal | ספגטיני מס 3 MANTANINO | ? / ? | - | 500 g | - | rejected (confidence 0.33 < 0.6): pasta-spaghetti (ספגטי): similarity 0.37 \| critical unknown product_type \| level any_brand, confidence 0.33 |
| shufersal | ספגטי מספר 5 PUMINO | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.85 review | review: pasta-spaghetti (ספגטי): similarity 0.56 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.85 \| vetoed: rice-basmati (אורז בסמטי): similarity 0.10 \| critical mismatch product_type pasta_spaghett |
| shufersal | ספגטיני מספר 3 PUMINO | ? / ? | - | 500 g | - | rejected (confidence 0.35 < 0.6): pasta-spaghetti (ספגטי): similarity 0.39 \| critical unknown product_type \| level any_brand, confidence 0.35 |
| shufersal | ספגטי 500 גרם MANTINI | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.82 review | review: pasta-spaghetti (ספגטי): similarity 0.52 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.82 \| vetoed: chickpeas-dry (גרגרי חומוס יבשים): similarity 0.12 \| critical mismatch product_type pasta_ |
| shufersal | פסטה ספגטי 400 Poplino | ? / ? | pasta_spaghetti | 400 g | pasta-spaghetti close 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 400 vs 500 g \| level close, confidence 0.84 \| vetoed: pasta-penne (פסטה פנה): similarity 0.41 \| critical misma |
| shufersal | ספגטי לה מוליזנה 500 גרם | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.81 review | review: pasta-spaghetti (ספגטי): similarity 0.51 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.81 \| vetoed: granola (גרנולה): similarity 0.20 \| critical mismatch product_type pasta_spaghetti vs gran |
| mega | ספגטי 500 גרם - קרפו | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.85 review | review: pasta-spaghetti (ספגטי): similarity 0.57 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.85 \| vetoed: turmeric (כורכום): similarity 0.13 \| critical mismatch product_type pasta_spaghetti vs tur |
| mega | פסטה ספגטי פרפקטו 50 | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.83 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.83 \| vetoed: pasta-penne (פסטה פנה): similarity 0.47 \| critical mismatch product_type pasta_spaghetti v |
| mega | ספגטי אסם 500 גרם | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.85 review | review: pasta-spaghetti (ספגטי): similarity 0.56 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.85 \| vetoed: turmeric (כורכום): similarity 0.16 \| critical mismatch product_type pasta_spaghetti vs tur |
| mega | מנה חמה ספגטי בולונז | ? / ? | pasta_spaghetti | 65 g | pasta-spaghetti close 0.86 review | review: pasta-spaghetti (ספגטי): similarity 0.58 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 65 vs 500 g \| level close, confidence 0.86 \| vetoed: mayonnaise (מיונז): similarity 0.19 \| critical mismatch p |
| mega | ספגטי קפליני מס' 1 ב | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.84 \| vetoed: rice-basmati (אורז בסמטי): similarity 0.14 \| critical mismatch product_type pasta_spaghett |
| mega | ספגטי מס' 3 ברילה 50 | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.55 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.84 \| vetoed: granola (גרנולה): similarity 0.10 \| critical mismatch product_type pasta_spaghetti vs gran |
| mega | ספגטי בבטה מס' 13 בר | ? / ? | pasta_spaghetti | -  | - | every candidate vetoed \| vetoed: soybean-oil (שמן סויה): similarity 0.07 \| critical mismatch product_type pasta_spaghetti vs soybean_oil ; soy-sauce (רוטב סויה): similarity 0.06 \| critical mismatch product_type pasta_spaghetti vs  |
| mega | ספגטי בוקטיני מס' 9 | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.87 review | review: pasta-spaghetti (ספגטי): similarity 0.58 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.87 \| vetoed: rice-basmati (אורז בסמטי): similarity 0.18 \| critical mismatch product_type pasta_spaghett |
| mega | ספגטי מס' 7 ברילה 50 | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.55 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.84 \| vetoed: sweet-paprika (פפריקה מתוקה): similarity 0.12 \| critical mismatch product_type pasta_spagh |
| mega | ברילה ספגטי ללא גלוט | ? / ? | pasta_spaghetti | 400 g | pasta-spaghetti close 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 400 vs 500 g \| level close, confidence 0.84 \| vetoed: granola (גרנולה): similarity 0.13 \| critical mismatch pr |
| mega | פסטה ספגטי מספר 3 - | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.89 review | review: pasta-spaghetti (ספגטי): similarity 0.62 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.89 \| vetoed: pasta-penne (פסטה פנה): similarity 0.45 \| critical mismatch product_type pasta_spaghetti v |
| king_store | פסטה ספגטי 500 ג' אסם | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.84 \| vetoed: pasta-penne (פסטה פנה): similarity 0.41 \| critical mismatch product_type pasta_spaghetti v |
| king_store | פרפקטו ספגטי 500 ג' אסם | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.80 review | review: pasta-spaghetti (ספגטי): similarity 0.50 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.80 \| vetoed: rice-basmati (אורז בסמטי): similarity 0.12 \| critical mismatch product_type pasta_spaghett |
| ramilevy | פסטה ספגטי 500 גר wb | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.85 review | review: pasta-spaghetti (ספגטי): similarity 0.56 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.85 \| vetoed: pasta-penne (פסטה פנה): similarity 0.42 \| critical mismatch product_type pasta_spaghetti v |
| ramilevy | ספגטי מחיטת כוסמין מ | ? / ? | pasta_spaghetti | -  | pasta-spaghetti any_brand 0.82 review | review: pasta-spaghetti (ספגטי): similarity 0.53 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.82 \| vetoed: rice-jasmine (אורז יסמין): similarity 0.18 \| critical mismatch product_type pasta_spaghett |
| ramilevy | רומו ספגטי ללא גלוטן | ? / ? | pasta_spaghetti | -  | pasta-spaghetti close 0.82 review | review: pasta-spaghetti (ספגטי): similarity 0.52 \| critical match product_type=pasta_spaghetti \| soft differs diet variant 'ללא גלוטן' \| level close, confidence 0.82 \| vetoed: chickpeas-dry (גרגרי חומוס יבשים): similarity 0.11 \| c |
| ramilevy | ספגטי לבן אורגני הרד | ? / ? | pasta_spaghetti | -  | pasta-spaghetti any_brand 0.83 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.83 \| vetoed: sugar-white (סוכר לבן): similarity 0.35 \| critical mismatch product_type pasta_spaghetti v |
| ramilevy | ספגטי 500גר רמילוי | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.88 review | review: pasta-spaghetti (ספגטי): similarity 0.60 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.88 \| vetoed: black-pepper (פלפל שחור): similarity 0.09 \| critical mismatch product_type pasta_spaghetti |

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

#### `yellow-cheese-sliced-28`: 72 listed of 356 name hits (0 skipped as not the food itself; chains looked in: shufersal, mega, king_store, osherad, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | גבינת עמק 15% פרוס 200ג | ? / ? | yellow_cheese | 200 g | - | every candidate vetoed \| vetoed: cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.32 \| critical mismatch product_type yellow_cheese vs cream_cheese; fat_pct 15 vs 30 \| critical unknown flavor ; sour-cream-15 (שמנת חמוצה  |
| shufersal | טל העמק 32% במשקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| shufersal | גבינת עמק 28% חריץ במשקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| shufersal | גבינת עמק דק דק 28% 200ג | ? / ? | yellow_cheese | 200 g | yellow-cheese-sliced-28 any_brand 0.60 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.24 \| critical match product_type=yellow_cheese, fat_pct=28 \| level any_brand, confidence 0.60 \| vetoed: cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity |
| shufersal | גבינת עמק פרוסה28% 400ג | ? / ? | yellow_cheese | 400 g | yellow-cheese-sliced-28 close 0.69 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.36 \| critical match product_type=yellow_cheese, fat_pct=28 \| soft differs pack_size 400 vs 200 g \| level close, confidence 0.69 \| vetoed: cream-cheese-30-plain  |
| shufersal | שעועית צהובה חתוכה 800 ג | ? / ? | - | 800 g | - | rejected (confidence 0.32 < 0.6): green-beans-frozen (שעועית ירוקה קפואה): similarity 0.36 \| critical unknown product_type, state \| level any_brand, confidence 0.32 |
| shufersal | מאגדת טעמקור 8*52ג | ? / ? | - | 416 g | - | rejected (confidence 0.24 < 0.6): cream-cheese-30-plain (גבינת שמנת 30% טבעית): similarity 0.09 \| critical unknown product_type, fat_pct, flavor \| soft differs pack_size 416 vs 200 g \| ambiguous with halva \| level close, confidenc |
| shufersal | גאודה הולנד גלגל30% משקל | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| shufersal | גבינת עמק 9% פרוס 200 גר | ? / ? | yellow_cheese | 200 g | yellow-cheese-sliced-9 any_brand 0.72 review | review: yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.40 \| critical match product_type=yellow_cheese, fat_pct=9 \| level any_brand, confidence 0.72 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.34 \| critical  |
| shufersal | אצבעות ג.צהובה עמק172גר | ? / ? | yellow_cheese | 172 g | - | rejected (confidence 0.45 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.29 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| soft differs pack_size 172 vs 200 g \| ambiguous with yellow- |
| shufersal | גב.עמק פרוס 28%קופסא400ג | ? / ? | yellow_cheese | 400 g | yellow-cheese-sliced-28 close 0.60 review | review: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.24 \| critical match product_type=yellow_cheese, fat_pct=28 \| soft differs pack_size 400 vs 200 g \| level close, confidence 0.60 \| vetoed: yellow-cheese-sliced-9 |
| shufersal | גבינה צהובה לייט9% 200גר | ? / ? | yellow_cheese | 200 g | yellow-cheese-sliced-9 any_brand 0.87 review | review: yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.59 \| critical match product_type=yellow_cheese, fat_pct=9 \| level any_brand, confidence 0.87 \| vetoed: yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity |
| mega | גבינה מותכת גאודה 17 | ? / ? | yellow_cheese | 150 g | - | rejected (confidence 0.51 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.36 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| soft differs pack_size 150 vs 200 g \| ambiguous with yellow- |
| mega | גבינה מותכת גאודה 14 | ? / ? | yellow_cheese | 70 g | - | rejected (confidence 0.51 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.36 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| soft differs pack_size 70 vs 200 g \| ambiguous with yellow-c |
| mega | סיי ציז גבינת גאודה | ? / ? | yellow_cheese | -  | - | every candidate vetoed \| vetoed: cooking-cream-10 (שמנת לבישול 10%): similarity 0.07 \| critical mismatch product_type yellow_cheese vs cooking_cream \| critical unknown fat_pct ; whipping-cream-32 (שמנת מתוקה 32%): similarity 0.05  |
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

#### `yogurt-plain-3`: 36 listed of 246 name hits (0 skipped as not the food itself; chains looked in: shufersal, osherad, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| shufersal | יוגורט קוליוס יווני 500ג | ? / ? | greek_yogurt | 500 g | greek-yogurt-plain close 0.73 review | review: greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.64 \| critical match product_type=greek_yogurt \| critical unknown flavor \| soft differs pack_size 500 vs 200 g \| level close, confidence 0.73 \| vetoed: yogurt-strawberry  |
| shufersal | יוגורט בכד 4% 1.5 ל | ? / ? | yogurt | 1500 ml | - | every candidate vetoed \| vetoed: cooking-cream-10 (שמנת לבישול 10%): similarity 0.07 \| critical mismatch product_type yogurt vs cooking_cream; fat_pct 4 vs 10 ; milk-long-life-1 (חלב עמיד 1%): similarity 0.06 \| critical mismatch p |
| shufersal | יוגורט בכד4% 3 ליטר | ? / ? | yogurt | 3000 ml | - | every candidate vetoed \| vetoed: whipping-cream-32 (שמנת מתוקה 32%): similarity 0.07 \| critical mismatch product_type yogurt vs whipping_cream; fat_pct 4 vs 32 ; milk-fresh-3 (חלב טרי 3%): similarity 0.06 \| critical mismatch produ |
| shufersal | משקה יוגורט תות-מלון250ג | ? / ? | yogurt_fruit | 250 g | yogurt-strawberry close 0.93 | accept: yogurt-strawberry (יוגורט תות): similarity 0.67 \| critical match product_type=yogurt_fruit, flavor=strawberry \| soft differs pack_size 250 vs 150 g \| level close, confidence 0.93 \| vetoed: greek-yogurt-plain (יוגורט יווני  |
| shufersal | משקה יוגורט בננ.אפרסק250 | ? / ? | - | 250 g | yogurt-peach close 0.69 review | review: yogurt-peach (יוגורט אפרסק): similarity 0.59 \| critical match flavor=peach \| critical unknown product_type \| soft differs pack_size 250 vs 150 g \| level close, confidence 0.69 \| vetoed: yogurt-strawberry (יוגורט תות): simi |
| shufersal | משקה יוגורט טרופי 250גרם | ? / ? | yogurt | 250 g | - | rejected (confidence 0.48 < 0.6): yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.39 \| critical match product_type=yogurt \| critical unknown fat_pct, flavor \| soft differs pack_size 250 vs 200 g \| level close, confidence 0.48 \| veto |
| shufersal | יוגורט ביו 3% 200ג תנובה | ? / ? | yogurt | 200 g | yogurt-plain-3 any_brand 0.69 review | review: yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.52 \| critical match product_type=yogurt, fat_pct=3 \| critical unknown flavor \| level any_brand, confidence 0.69 \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.43 \| crit |
| shufersal | יוגורט ביו 3% דנונה 200ג | ? / ? | yogurt | 200 g | yogurt-plain-3 any_brand 0.69 review | review: yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.52 \| critical match product_type=yogurt, fat_pct=3 \| critical unknown flavor \| level any_brand, confidence 0.69 \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.42 \| crit |
| shufersal | יוגורט ביו 0% דנונה 200ג | ? / ? | yogurt | 200 g | - | every candidate vetoed \| vetoed: yogurt-strawberry (יוגורט תות): similarity 0.40 \| critical mismatch product_type yogurt vs yogurt_fruit \| critical unknown flavor ; greek-yogurt-plain (יוגורט יווני טבעי): similarity 0.37 \| critica |
| shufersal | יוגורט עיזים ביו 3% 150ג | ? / ? | yogurt | 150 g | yogurt-plain-3 close 0.74 review | review: yogurt-plain-3 (יוגורט טבעי 3%): similarity 0.57 \| critical match product_type=yogurt, fat_pct=3 \| critical unknown flavor \| soft differs pack_size 150 vs 200 g \| level close, confidence 0.74 \| vetoed: yogurt-strawberry (י |
| shufersal | אירן משקה יוגורט 500 מ"ל | ? / ? | yogurt | 500 ml | - | every candidate vetoed \| vetoed: whipping-cream-32 (שמנת מתוקה 32%): similarity 0.09 \| critical mismatch product_type yogurt vs whipping_cream \| critical unknown fat_pct ; whipping-cream-38 (שמנת מתוקה 38%): similarity 0.06 \| crit |
| shufersal | יוגורט בכד6.5%  1.5 ליטר | ? / ? | yogurt | 1500 ml | - | every candidate vetoed \| vetoed: whipping-cream-32 (שמנת מתוקה 32%): similarity 0.08 \| critical mismatch product_type yogurt vs whipping_cream; fat_pct 6.5 vs 32 ; cooking-cream-10 (שמנת לבישול 10%): similarity 0.08 \| critical mis |
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

### Failures and findings the run recorded (6)

- **download**: mega price_full: no file matched
- **download**: mega promo_full: no file matched
- **api**: /parse-list took over 2 s (production): {'small (6 lines)': 3933.2, 'weekly (17 lines)': 10966.1, 'large (32 lines)': 21321.3} ms
- **basket index**: chocolate-milk is priced at no chain (candidates in the report)
- **basket index**: pasta-spaghetti is priced at no chain (candidates in the report)
- **api**: /parse-list took over 2 s (stress): {'small (6 lines)': 3998.8, 'weekly (17 lines)': 11232.2, 'large (32 lines)': 21254.7} ms

