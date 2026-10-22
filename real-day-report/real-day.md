## One real day through the pipeline (dry run)

Mode `portal`, commit `01212a727797`, runner `GitHub Actions 1000005159` (4 CPUs, Python 3.12.3, Postgres 17.11), 2026-10-22T08:43:14+00:00 to 2026-10-22T09:25:21+00:00 UTC. Measurements on one real day with hand-made baskets; the prices are real, the baskets and locations are not a sample of anything. **Not publishable.**

### Stages

| stage | seconds | result |
|---|---|---|
| download: portal probe (one Stores and one PriceFull per chain) | 2014.45 | ok |
| migrate | 0.86 | 32 applied |
| ingest: Stores files (Scheduler, adapters, gates, loader, store coordinates) | 0.15 | 5 files |
| download: PriceFull and PromoFull of the stores nearest to city centres | 88.72 | 36 files, anchors: Jerusalem centre, Holon, Petah Tikva |
| ingest: PriceFull and PromoFull files (Scheduler, adapters, gates, loader) | 101.35 | 46 files |
| catalog: seed | 0.62 | ok |
| catalog: normalize | 4.8 | ok |
| catalog: extract (rule) | 32.01 | ok |
| catalog: embed (hash) | 133.73 | ok |
| catalog: judge (rule) | 91.34 | ok |
| precompute effective prices (production semantics: reviewed mappings only) | 0.75 | 5196 rows |
| API: parse-list, compare, optimize (production) | 25.11 | 21 basket runs at 3 locations |
| diagnostic: the vector query behind /parse-list and /search | 4.59 | [2.9, 0.8, 0.7] ms per query |
| basket index dry run (production semantics) | 0.29 | status draft |
| diagnostic: real items behind the basket lines no chain prices | 1.07 | butter 36 items, chocolate-milk 60 items, cottage-5 6 items, eggs-l 137 items, hummus-plain 60 items, milk-fresh-3 24 items, pasta-spaghetti 50 items, white-cheese-5 12 items, yellow-cheese-sliced-28 48 items, yogurt-plain-3 24 items |
| stress: mark the machine suggestions accepted (performance only) | 0.14 | 10996 mappings |
| precompute effective prices (stress: unreviewed mappings included) | 1.39 | 8477 rows |
| API: parse-list, compare, optimize (stress) | 24.27 | 21 basket runs at 3 locations |
| basket index dry run (stress) | 0.32 | status draft |

### Portals (the portal probe's own reachability and downloads)

| chain | reachable | login | Stores download | PriceFull download |
|---|---|---|---|---|
| king_store | BLOCKED? (403) | n/a | Stores7290058108879-000-20261022-051042.gz | PriceFull7290058108879-000-340-20261022-051042.gz |
| mega | UNREACHABLE (0) | n/a | no: timed out after 300s | no: timed out after 300s |
| osherad | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290103152017-000-20261020-080500.xml | PriceFull7290103152017-001-001-20261022-080018.gz |
| ramilevy | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290058140886-000-20261020-050500.xml | PriceFull7290058140886-001-001-20261022-001004.gz |
| shufersal | UNREACHABLE (0) | n/a | no: timed out after 300s | no: timed out after 300s |
| tivtaam | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290873255550-000-20261020-050500.xml | PriceFull7290873255550-000-002-20261022-004004.gz |
| yohananof | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290803800003-000-20261020-010000.xml | PriceFull7290803800003-000-001-20261022-004040.gz |

### Files, gates and rows per chain

| chain | kind | file | published (Israel) | age h | schema | gate result | rows | seconds |
|---|---|---|---|---|---|---|---|---|
| king_store | stores | `Stores7290058108879-000-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 7.1 | v1 | loaded | 48 | 0.04 |
| osherad | stores | `Stores7290103152017-000-20261020-080500.xml` | 2026-10-20T08:05+03:00 | 52.2 | v1 | loaded | 24 | 0.02 |
| ramilevy | stores | `Stores7290058140886-000-20261020-050500.xml` | 2026-10-20T05:05+03:00 | 55.2 | v1 | loaded | 99 | 0.05 |
| tivtaam | stores | `Stores7290873255550-000-20261020-050500.xml` | 2026-10-20T05:05+03:00 | 55.2 | v1 | loaded | 54 | 0.02 |
| yohananof | stores | `Stores7290803800003-000-20261020-010000.xml` | 2026-10-20T01:00+03:00 | 59.3 | v1 | loaded | 51 | 0.02 |
| king_store | price_full | `PriceFull7290058108879-000-340-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 7.1 | v1 | loaded | 2,338 | 0.24 |
| king_store | promo_full | `PromoFull7290058108879-000-340-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 7.1 | v1 | loaded | 296 | 0.07 |
| osherad | price_full | `PriceFull7290103152017-001-001-20261022-080018.gz` | 2026-10-22T08:00+03:00 | 4.3 | v1 | loaded | 6,495 | 0.62 |
| osherad | promo_full | `PromoFull7290103152017-001-001-20261022-080055.gz` | 2026-10-22T08:00+03:00 | 4.3 | v1 | loaded | 660 | 0.26 |
| ramilevy | price_full | `PriceFull7290058140886-001-001-20261022-001004.gz` | 2026-10-22T00:10+03:00 | 12.1 | v1 | loaded | 12,975 | 1.18 |
| ramilevy | promo_full | `PromoFull7290058140886-001-001-20261022-001131.gz` | 2026-10-22T00:11+03:00 | 12.1 | v1 | loaded | 2,660 | 0.86 |
| tivtaam | price_full | `PriceFull7290873255550-000-002-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 11.6 | v1 | loaded | 21,607 | 2.05 |
| tivtaam | promo_full | `PromoFull7290873255550-000-002-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 11.6 | v1 | loaded | 2,246 | 3.53 |
| yohananof | price_full | `PriceFull7290803800003-000-001-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 11.6 | v1 | loaded | 10,722 | 1.08 |
| yohananof | promo_full | `PromoFull7290803800003-000-009-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 11.6 | v1 | loaded | 1,206 | 0.41 |
| king_store | price_full | `PriceFull7290058108879-000-200-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 7.1 | v1 | loaded | 3,611 | 0.35 |
| king_store | promo_full | `PromoFull7290058108879-000-200-20261022-051042.gz` | 2026-10-22T05:10+03:00 | 7.1 | v1 | loaded | 306 | 0.1 |
| osherad | price_full | `PriceFull7290103152017-001-025-20261022-110501.gz` | 2026-10-22T11:05+03:00 | 1.2 | v1 | loaded | 6,253 | 0.64 |
| osherad | price_full | `PriceFull7290103152017-001-026-20261022-110501.gz` | 2026-10-22T11:05+03:00 | 1.2 | v1 | loaded | 6,834 | 0.6 |
| osherad | price_full | `PriceFull7290103152017-001-028-20261022-110501.gz` | 2026-10-22T11:05+03:00 | 1.2 | v1 | loaded | 6,236 | 0.59 |
| osherad | price_full | `PriceFull7290103152017-001-010-20261022-110502.gz` | 2026-10-22T11:05+03:00 | 1.2 | v1 | loaded | 6,690 | 0.6 |
| osherad | promo_full | `PromoFull7290103152017-001-025-20261022-110521.gz` | 2026-10-22T11:05+03:00 | 1.2 | v1 | loaded | 759 | 0.19 |
| osherad | promo_full | `PromoFull7290103152017-001-026-20261022-110522.gz` | 2026-10-22T11:05+03:00 | 1.2 | v1 | loaded | 721 | 0.18 |
| osherad | promo_full | `PromoFull7290103152017-001-028-20261022-110522.gz` | 2026-10-22T11:05+03:00 | 1.2 | v1 | loaded | 704 | 0.22 |
| osherad | promo_full | `PromoFull7290103152017-001-010-20261022-110555.gz` | 2026-10-22T11:05+03:00 | 1.2 | v1 | loaded | 723 | 0.31 |
| ramilevy | price_full | `PriceFull7290058140886-001-048-20261022-001016.gz` | 2026-10-22T00:10+03:00 | 12.1 | v1 | loaded | 14,443 | 1.34 |
| ramilevy | price_full | `PriceFull7290058140886-001-724-20261022-060015.gz` | 2026-10-22T06:00+03:00 | 6.3 | v1 | loaded | 5,147 | 0.46 |
| ramilevy | price_full | `PriceFull7290058140886-001-718-20261022-120005.gz` | 2026-10-22T12:00+03:00 | 0.3 | v1 | loaded | 3,818 | 0.32 |
| ramilevy | price_full | `PriceFull7290058140886-001-050-20261022-120007.gz` | 2026-10-22T12:00+03:00 | 0.3 | v1 | loaded | 14,819 | 1.48 |
| ramilevy | price_full | `PriceFull7290058140886-001-725-20261022-120015.gz` | 2026-10-22T12:00+03:00 | 0.3 | v1 | loaded | 4,115 | 0.4 |
| ramilevy | price_full | `PriceFull7290058140886-001-703-20261022-120017.gz` | 2026-10-22T12:00+03:00 | 0.3 | v1 | loaded | 4,959 | 0.51 |
| ramilevy | promo_full | `PromoFull7290058140886-001-724-20261022-120015.gz` | 2026-10-22T12:00+03:00 | 0.3 | v1 | loaded | 1,059 | 0.33 |
| ramilevy | promo_full | `PromoFull7290058140886-001-718-20261022-120029.gz` | 2026-10-22T12:00+03:00 | 0.3 | v1 | loaded | 1,073 | 0.32 |
| ramilevy | promo_full | `PromoFull7290058140886-001-725-20261022-120038.gz` | 2026-10-22T12:00+03:00 | 0.3 | v1 | loaded | 1,049 | 0.31 |
| ramilevy | promo_full | `PromoFull7290058140886-001-048-20261022-120041.gz` | 2026-10-22T12:00+03:00 | 0.3 | v1 | loaded | 2,546 | 0.92 |
| ramilevy | promo_full | `PromoFull7290058140886-001-703-20261022-120047.gz` | 2026-10-22T12:00+03:00 | 0.3 | v1 | loaded | 1,110 | 0.36 |
| ramilevy | promo_full | `PromoFull7290058140886-001-050-20261022-120104.gz` | 2026-10-22T12:01+03:00 | 0.3 | v1 | loaded | 2,522 | 0.9 |
| tivtaam | price_full | `PriceFull7290873255550-000-006-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 11.6 | v1 | loaded | 16,079 | 1.77 |
| tivtaam | price_full | `PriceFull7290873255550-000-079-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 11.6 | v1 | loaded | 6,351 | 0.6 |
| tivtaam | price_full | `PriceFull7290873255550-000-085-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 11.6 | v1 | loaded | 7,171 | 0.69 |
| tivtaam | price_full | `PriceFull7290873255550-000-087-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 11.7 | v1 | loaded | 6,069 | 0.66 |
| tivtaam | promo_full | `PromoFull7290873255550-000-006-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 11.7 | v1 | loaded | 2,000 | 3.41 |
| tivtaam | promo_full | `PromoFull7290873255550-000-079-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 11.7 | v1 | loaded | 567 | 3.88 |
| tivtaam | promo_full | `PromoFull7290873255550-000-085-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 11.7 | v1 | loaded | 1,281 | 4.21 |
| tivtaam | promo_full | `PromoFull7290873255550-000-087-20261022-004004.gz` | 2026-10-22T00:40+03:00 | 11.7 | v1 | loaded | 1,124 | 3.28 |
| yohananof | price_full | `PriceFull7290803800003-000-020-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 11.7 | v1 | loaded | 11,876 | 1.08 |
| yohananof | price_full | `PriceFull7290803800003-000-021-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 11.7 | v1 | loaded | 11,196 | 1.02 |
| yohananof | price_full | `PriceFull7290803800003-000-029-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 11.7 | v1 | loaded | 10,462 | 1.01 |
| yohananof | promo_full | `PromoFull7290803800003-000-020-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 11.7 | v1 | loaded | 1,276 | 0.44 |
| yohananof | promo_full | `PromoFull7290803800003-000-021-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 11.7 | v1 | loaded | 1,218 | 0.46 |
| yohananof | promo_full | `PromoFull7290803800003-000-029-20261022-004040.gz` | 2026-10-22T00:40+03:00 | 11.7 | v1 | loaded | 1,106 | 0.38 |

PromoFull files: what they hold and how much reached `promo_items`:

| chain | file | promos | with item codes | distinct codes | codes the chain's items know | promo_items linked | active now | club | rewards |
|---|---|---|---|---|---|---|---|---|---|
| king_store | `PromoFull7290058108879-000-340-20261022-051042.gz` | 296 | 296 | 678 | 678 | 685 | 295 | 63 | {'bundle': 166, 'price': 130} |
| osherad | `PromoFull7290103152017-001-001-20261022-080055.gz` | 660 | 660 | 2,624 | 1,774 | 1,839 | 660 | 0 | {'bundle': 599, 'other': 3, 'price': 58} |
| ramilevy | `PromoFull7290058140886-001-001-20261022-001131.gz` | 2,660 | 2,660 | 8,980 | 5,898 | 8,932 | 2,660 | 37 | {'price': 1288, 'other': 486, 'bundle': 868, 'buy_x_get_y': 16, 'percent': 2} |
| tivtaam | `PromoFull7290873255550-000-002-20261022-004004.gz` | 2,246 | 2,246 | 15,685 | 12,380 | 24,389 | 2,246 | 1,384 | {'other': 19, 'bundle': 927, 'price': 1260, 'percent': 2, 'buy_x_get_y': 38} |
| yohananof | `PromoFull7290803800003-000-009-20261022-004040.gz` | 1,206 | 1,206 | 3,985 | 3,576 | 3,621 | 1,206 | 11 | {'bundle': 794, 'price': 348, 'other': 54, 'percent': 3, 'buy_x_get_y': 7} |
| king_store | `PromoFull7290058108879-000-200-20261022-051042.gz` | 306 | 306 | 813 | 813 | 831 | 306 | 77 | {'price': 143, 'bundle': 162, 'other': 1} |
| osherad | `PromoFull7290103152017-001-025-20261022-110521.gz` | 759 | 759 | 2,882 | 2,343 | 2,459 | 759 | 0 | {'bundle': 678, 'price': 78, 'other': 3} |
| osherad | `PromoFull7290103152017-001-026-20261022-110522.gz` | 721 | 721 | 2,790 | 2,285 | 2,326 | 721 | 0 | {'bundle': 655, 'other': 3, 'price': 63} |
| osherad | `PromoFull7290103152017-001-028-20261022-110522.gz` | 704 | 704 | 2,664 | 2,173 | 2,220 | 704 | 0 | {'bundle': 640, 'price': 62, 'other': 2} |
| osherad | `PromoFull7290103152017-001-010-20261022-110555.gz` | 723 | 723 | 2,810 | 2,301 | 2,395 | 723 | 0 | {'bundle': 652, 'price': 68, 'other': 3} |
| ramilevy | `PromoFull7290058140886-001-724-20261022-120015.gz` | 1,059 | 1,059 | 3,953 | 3,428 | 3,966 | 1,059 | 24 | {'bundle': 356, 'price': 447, 'other': 247, 'buy_x_get_y': 8, 'percent': 1} |
| ramilevy | `PromoFull7290058140886-001-718-20261022-120029.gz` | 1,073 | 1,073 | 3,972 | 3,436 | 3,974 | 1,073 | 24 | {'bundle': 356, 'other': 247, 'price': 461, 'buy_x_get_y': 8, 'percent': 1} |
| ramilevy | `PromoFull7290058140886-001-725-20261022-120038.gz` | 1,049 | 1,049 | 3,934 | 3,420 | 3,961 | 1,049 | 24 | {'bundle': 354, 'price': 439, 'other': 247, 'buy_x_get_y': 8, 'percent': 1} |
| ramilevy | `PromoFull7290058140886-001-048-20261022-120041.gz` | 2,546 | 2,546 | 8,906 | 7,067 | 10,794 | 2,546 | 37 | {'bundle': 868, 'price': 1205, 'other': 455, 'buy_x_get_y': 16, 'percent': 2} |
| ramilevy | `PromoFull7290058140886-001-703-20261022-120047.gz` | 1,110 | 1,110 | 3,798 | 3,368 | 3,937 | 1,110 | 22 | {'price': 448, 'other': 289, 'bundle': 365, 'buy_x_get_y': 7, 'percent': 1} |
| ramilevy | `PromoFull7290058140886-001-050-20261022-120104.gz` | 2,522 | 2,522 | 9,149 | 7,164 | 10,769 | 2,522 | 37 | {'bundle': 847, 'price': 1194, 'other': 463, 'buy_x_get_y': 16, 'percent': 2} |
| tivtaam | `PromoFull7290873255550-000-006-20261022-004004.gz` | 2,000 | 2,000 | 14,607 | 12,826 | 26,066 | 2,000 | 1,249 | {'other': 17, 'bundle': 834, 'price': 1134, 'percent': 2, 'buy_x_get_y': 13} |
| tivtaam | `PromoFull7290873255550-000-079-20261022-004004.gz` | 567 | 567 | 12,600 | 10,907 | 22,262 | 567 | 281 | {'other': 14, 'bundle': 259, 'price': 289, 'percent': 1, 'buy_x_get_y': 4} |
| tivtaam | `PromoFull7290873255550-000-085-20261022-004004.gz` | 1,281 | 1,281 | 13,365 | 11,584 | 23,659 | 1,281 | 711 | {'other': 16, 'bundle': 583, 'price': 670, 'buy_x_get_y': 12} |
| tivtaam | `PromoFull7290873255550-000-087-20261022-004004.gz` | 1,124 | 1,124 | 13,048 | 11,267 | 23,263 | 1,124 | 637 | {'other': 11, 'bundle': 538, 'price': 564, 'buy_x_get_y': 11} |
| yohananof | `PromoFull7290803800003-000-020-20261022-004040.gz` | 1,276 | 1,276 | 4,339 | 4,302 | 4,375 | 1,276 | 11 | {'bundle': 779, 'price': 399, 'other': 86, 'percent': 4, 'buy_x_get_y': 8} |
| yohananof | `PromoFull7290803800003-000-021-20261022-004040.gz` | 1,218 | 1,218 | 4,151 | 4,128 | 4,188 | 1,218 | 11 | {'bundle': 796, 'price': 356, 'other': 54, 'percent': 3, 'buy_x_get_y': 9} |
| yohananof | `PromoFull7290803800003-000-029-20261022-004040.gz` | 1,106 | 1,106 | 3,635 | 3,615 | 3,675 | 1,106 | 11 | {'other': 53, 'bundle': 734, 'price': 310, 'percent': 3, 'buy_x_get_y': 6} |

Sample codes (promo / item): king_store ['13006', '13174', '13747'] / ['12345', '13006', '13174']; osherad ['1230000292009', '16000423534', '16000548404'] / ['835811001454', '7290018571187', '7290018571163']; ramilevy ['1220000750166', '1230000068413', '1230000116022'] / ['7290017023212', '7290017023229', '7290017023236']; tivtaam ['11182170603', '11182175271', '11182700916'] / ['1101346', '1101421', '1101858']; yohananof ['14098', '16000185517', '16000423534'] / ['1022788', '1022801', '1022825']; king_store ['13006', '16000423534', '16000548404'] / ['12345', '13006', '13174']

`file_tracking` after the run: {'loaded': 51}. Alerts raised: 0.

| chain | physical stores | located | online | items | price events | stores with prices | promos | promo items |
|---|---|---|---|---|---|---|---|---|
| king_store | 48 | 28 | - | 4,530 | 5,949 | 2 | 602 | 1,516 |
| osherad | 24 | 24 | - | 8,672 | 32,508 | 5 | 3,567 | 11,239 |
| ramilevy | 98 | 96 | 1 | 18,164 | 60,276 | 7 | 12,019 | 46,333 |
| tivtaam | 47 | 47 | 7 | 24,779 | 57,277 | 5 | 7,218 | 119,639 |
| yohananof | 50 | 19 | 1 | 13,856 | 44,256 | 4 | 4,806 | 15,859 |

Extra downloads (the stores nearest to these city centres, for the optimizer):

- Jerusalem centre: 4 chains and 13 located stores within 4 km; asked for king_store 200, ramilevy 48,703, osherad 26,28, yohananof 20
- Holon: 4 chains and 10 located stores within 4 km; asked for ramilevy 718,50, osherad 25, yohananof 29, tivtaam 79,6
- Petah Tikva: 4 chains and 9 located stores within 4 km; asked for ramilevy 725,724, osherad 10, yohananof 21, tivtaam 87,85

### Matching on the real items

70,001 items; 14,913 mapped to a canonical (any level, including the review queue); 3,917 served (no review flag), onto 207 canonicals.

| level | mappings served | mappings in the review queue |
|---|---|---|
| exact | 0 | 0 |
| any_brand | 2,519 | 4,805 |
| close | 1,398 | 6,191 |

| chain | items | mapped | served |
|---|---|---|---|
| king_store | 4,530 | 1,309 | 239 |
| ramilevy | 18,164 | 3,894 | 1,356 |
| osherad | 8,672 | 2,167 | 688 |
| yohananof | 13,856 | 2,694 | 938 |
| tivtaam | 24,779 | 4,849 | 696 |

- seed: 0.62 s
- normalize: 4.8 s
- extract (rule): 32.01 s
- embed (hash): 133.73 s
- judge (rule): 91.34 s

### Precompute (production semantics)

5,196 rows written in 0.458 s of job time (0.69 s wall including start-up); 3,725 items priced at 23 stores (276 stores of 5 chains considered); 1,564 rows with a promo, 201 club-only. Canonicals with a real price: 205, of them 179 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 2,317 | 185 | 23 |
| close | 2,879 | 205 | 23 |

Promos per chain, and what reached a price (production semantics):

| chain | promos | club-only | linked to items | reward `other` | effective rows | with a promo | club required | of them with a non-club fallback |
|---|---|---|---|---|---|---|---|---|
| king_store | 602 | 140 | 602 | 1 | 294 | 79 | 19 | 19 |
| ramilevy | 12,019 | 205 | 11,054 | 2,434 | 1,834 | 652 | 0 | 0 |
| osherad | 3,567 | 0 | 3,230 | 14 | 823 | 265 | 0 | 0 |
| yohananof | 4,806 | 44 | 4,722 | 247 | 1,129 | 300 | 14 | 14 |
| tivtaam | 7,218 | 4,262 | 7,218 | 77 | 1,116 | 268 | 168 | 168 |

Club rules of the club-only promos (most frequent): `המועדון החדש` x 4,262; `מועדון חברתי \| מועדון רמי לוי \| מועדון לקוחות אשראי \| מועדון נטען \| לקוחות ארנק` x 132; `מועדון לקוחות \| לקוחות סיטונאים \| עובדי קינגסטור` x 79; `מועדון עובדים` x 44; `מועדון לקוחות \| עובדי קינגסטור` x 43; `מועדון לקוחות אשראי & תווי זיכוי מימוש` x 34; `לקוחות סיטונאים` x 16; `מועדון רמי לוי \| מועדון לקוחות אשראי` x 12

### Precompute (stress)

8,477 rows written in 1.088 s of job time (1.33 s wall including start-up); 14,056 items priced at 23 stores (276 stores of 5 chains considered); 2,619 rows with a promo, 422 club-only. Canonicals with a real price: 241, of them 234 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 3,905 | 235 | 23 |
| close | 4,572 | 241 | 23 |

Promos per chain, and what reached a price (stress):

| chain | promos | club-only | linked to items | reward `other` | effective rows | with a promo | club required | of them with a non-club fallback |
|---|---|---|---|---|---|---|---|---|
| king_store | 602 | 140 | 602 | 1 | 593 | 182 | 49 | 49 |
| ramilevy | 12,019 | 205 | 11,054 | 2,434 | 2,794 | 1,067 | 0 | 0 |
| osherad | 3,567 | 0 | 3,230 | 14 | 1,540 | 352 | 0 | 0 |
| yohananof | 4,806 | 44 | 4,722 | 247 | 1,655 | 410 | 14 | 14 |
| tivtaam | 7,218 | 4,262 | 7,218 | 77 | 1,895 | 608 | 359 | 359 |

Club rules of the club-only promos (most frequent): `המועדון החדש` x 4,262; `מועדון חברתי \| מועדון רמי לוי \| מועדון לקוחות אשראי \| מועדון נטען \| לקוחות ארנק` x 132; `מועדון לקוחות \| לקוחות סיטונאים \| עובדי קינגסטור` x 79; `מועדון עובדים` x 44; `מועדון לקוחות \| עובדי קינגסטור` x 43; `מועדון לקוחות אשראי & תווי זיכוי מימוש` x 34; `לקוחות סיטונאים` x 16; `מועדון רמי לוי \| מועדון לקוחות אשראי` x 12

### The vector query behind /parse-list and /search

`item_embeddings` holds 70,001 rows (model `hash-ngram-2-3-4-v1`); one `ORDER BY embedding <=> q LIMIT 40` query took [2.9, 0.8, 0.7] ms; with sequential scans disabled 0.6 ms.

```
Limit  (cost=2308.65..2563.42 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2308.65..448165.03 rows=70001 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
--- enable_seqscan = off
Limit  (cost=2308.65..2563.42 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2308.65..448165.03 rows=70001 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
```

One `/parse-list` call (6 lines): 2102.3 ms in total, 2095.8 ms inside 37 SQL statements. The statements that cost the most:

| statement (first 110 characters) | calls | total ms | max ms |
|---|---|---|---|
| `WITH qv AS (SELECT %(v)s::vector AS v), direct AS ( SELECT c.id AS canonical_id, 1 - (c.embedding <=> qv.v) AS` | 6 | 2071.7 | 376.1 |
| `WITH q AS (SELECT search_norm(%(q)s) AS t) SELECT c.id, word_similarity(q.t, search_norm(c.display_name_he)) A` | 6 | 12.2 | 4.8 |
| `WITH RECURSIVE up AS ( SELECT t.id AS leaf, t.id, t.parent_id, t.name_he, t.level FROM taxonomy t WHERE t.id =` | 6 | 3.5 | 0.9 |
| `SELECT id, display_name_he, taxonomy_id, base_unit, rank, names_ar[1] FROM canonical_products WHERE id = ANY(%` | 6 | 3.4 | 0.8 |
| `SELECT c.id, c.display_name_he, ts_rank_cd(to_tsvector('simple', search_norm(c.display_name_he)), tq) AS r FRO` | 6 | 2.9 | 1.1 |
| `SELECT set_config('pg_trgm.word_similarity_threshold', %s, true)` | 6 | 1.6 | 0.7 |

`EXPLAIN (ANALYZE, BUFFERS)` of the slowest statement:

```
Limit  (cost=5949.07..5949.09 rows=10 width=16) (actual rows=20 loops=1)
  Buffers: shared hit=561094 read=48246
  CTE qv
    ->  Result  (cost=0.00..0.01 rows=1 width=32) (actual rows=1 loops=1)
  ->  Sort  (cost=5949.06..5949.08 rows=10 width=16) (actual rows=20 loops=1)
        Sort Key: (max(direct.s)) DESC, direct.canonical_id
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=561094 read=48246
        ->  GroupAggregate  (cost=5948.43..5948.89 rows=10 width=16) (actual rows=20 loops=1)
              Group Key: direct.canonical_id
              Buffers: shared hit=561091 read=48246
              ->  Merge Append  (cost=5948.43..5948.74 rows=10 width=16) (actual rows=24 loops=1)
                    Sort Key: direct.canonical_id
                    Buffers: shared hit=561091 read=48246
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
                    ->  GroupAggregate  (cost=5915.13..5915.33 rows=3 width=16) (actual rows=4 loops=1)
                          Group Key: ic.canonical_id
                          Filter: (max((('1'::double precision - (e.embedding <=> qv_1.v)))) >= '0.25'::double precision)
                          Buffers: shared hit=559592 read=48064
                          ->  Sort  (cost=5915.13..5915.15 rows=10 width=16) (actual rows=11 loops=1)
                                Sort Key: ic.canonical_id
                                Sort Method: quicksort  Memory: 25kB
                                Buffers: shared hit=559592 read=48064
                                ->  Nested Loop  (cost=5385.05..5914.96 rows=10 width=16) (actual rows=11 loops=1)
                                      Buffers: shared hit=559592 read=48064
                                      ->  Limit  (cost=5384.76..5384.96 rows=80 width=24) (actual rows=80 loops=1)
                                            Buffers: shared hit=559454 read=47967
                                            ->  Sort  (cost=5384.76..5559.76 rows=70001 width=24) (actual rows=80 loops=1)
                                                  Sort Key: ((e.embedding <=> qv_1.v))
                                                  Sort Method: top-N heapsort  Memory: 34kB
                                                  Buffers: shared hit=559454 read=47967
                                                  ->  Nested Loop  (cost=0.00..2822.05 rows=70001 width=24) (actual rows=70001 loops=1)
                                                        Buffers: shared hit=559454 read=47967
                                                        ->  CTE Scan on qv qv_1  (cost=0.00..0.02 rows=1 width=32) (actual rows=1 loops=1)
                                                        ->  Seq Scan on item_embeddings e  (cost=0.00..1597.01 rows=70001 width=26) (actual rows=70001 loops=1)
                                                              Filter: (model = 'hash-ngram-2-3-4-v1'::text)
                                                              Buffers: shared read=722
                                      ->  Index Scan using item_canonical_pkey on item_canonical ic  (cost=0.29..6.60 rows=1 width=16) (actual rows=0 loops=80)
                                            Index Cond: (item_id = e.item_id)
                                            Filter: ((NOT human_rejected) AND (NOT needs_review) AND (flex_level = ANY ('{exact,any_brand}'::text[])))
                                            Rows Removed by Filter: 1
                                            Buffers: shared hit=138 read=97
Planning:
  Buffers: shared hit=413 read=64
Planning Time: 1.287 ms
Execution Time: 374.405 ms
```

### /parse-list, /compare and /optimize (production semantics)

Locations: Jerusalem centre (7 priced stores, 4 chains within 5 km); Holon (6 priced stores, 4 chains within 5 km); Petah Tikva (6 priced stores, 4 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 2114.8 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 5988.6 |
| large (32 lines) | 33 | 33 | 5 | 0 | 11060.3 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 7 | 0 | 5.8 | 4.9 | 9 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 7 | 0 | 7.1 | 5.6 | 9.6 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 33 | 7 | 0 | 8 | 6.7 | 10.8 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 5 | 5 | 7 | 3 | 4.2 | 3.9 | 6.8 | 55 | single: רמי לוי בית הפירות פת | 5.2 / 5.2 |
| Jerusalem centre | drawn: 10 | 10 | 7 | 0 | 4.9 | 4.6 | 8.7 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 20 | 20 | 7 | 0 | 6.7 | 6 | 10.1 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 40 | 40 | 7 | 0 | 10 | 7.9 | 17.4 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Holon | hand: small (6 lines) | 6 | 6 | 0 | 3.8 | 3.8 | 7.5 | 55 | single: רמי לוי חולון | 24.95 / 24.95 |
| Holon | hand: weekly (17 lines) | 17 | 6 | 0 | 5.9 | 5.5 | 9.8 | 55 | single: רמי לוי חולון | 15.75 / 15.75 |
| Holon | hand: large (32 lines) | 33 | 6 | 0 | 7.1 | 7.2 | 12.5 | 55 | single: רמי לוי חולון | 19.25 / 19.25 |
| Holon | drawn: 5 | 5 | 6 | 1 | 3.7 | 3.8 | 7.2 | 55 | single: רמי לוי חולון | -0.79 / -0.79 |
| Holon | drawn: 10 | 10 | 6 | 0 | 4.8 | 4.5 | 8.2 | 55 | single: רמי לוי חולון | -5.99 / -5.99 |
| Holon | drawn: 20 | 20 | 6 | 0 | 5.9 | 6.1 | 10.1 | 55 | single: רמי לוי חולון | 44.03 / 44.03 |
| Holon | drawn: 40 | 40 | 6 | 0 | 9.3 | 9.5 | 15.5 | 55 | single: רמי לוי חולון | 98.51 / 98.51 |
| Petah Tikva | hand: small (6 lines) | 6 | 6 | 0 | 3.9 | 4 | 7.4 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 17.64 / 17.64 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 6 | 0 | 5.1 | 5.3 | 9.3 | 55 | single: טיב טעם בית הדובדבן - אונו | 8.38 / 8.38 |
| Petah Tikva | hand: large (32 lines) | 33 | 6 | 0 | 6.9 | 6.8 | 11.5 | 55 | single: יוחננוף סגולה פתח תקווה | 1.52 / 1.52 |
| Petah Tikva | drawn: 5 | 5 | 6 | 1 | 4 | 4.1 | 7.8 | 55 | single: רמי לוי קניון אבנת פתח תקווה | -22.54 / -22.54 |
| Petah Tikva | drawn: 10 | 10 | 6 | 0 | 5 | 4.5 | 8.3 | 55 | single: רמי לוי קניון אבנת פתח תקווה | -12.74 / -12.74 |
| Petah Tikva | drawn: 20 | 20 | 6 | 0 | 5.8 | 6 | 10.4 | 55 | single: טיב טעם בית הדובדבן - אונו | -33.0 / -33.0 |
| Petah Tikva | drawn: 40 | 40 | 6 | 0 | 9.5 | 9.8 | 20.2 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 42.16 / 42.16 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 3.9 | 4.0 | 7.5 |
| hand: weekly (17 lines) | 5.9 | 5.5 | 9.6 |
| hand: large (32 lines) | 7.1 | 6.8 | 11.5 |
| drawn: 5 | 4.0 | 3.9 | 7.2 |
| drawn: 10 | 4.9 | 4.5 | 8.3 |
| drawn: 20 | 5.9 | 6.0 | 10.1 |
| drawn: 40 | 9.5 | 9.5 | 17.4 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 4.9 | 8.6 | רמי לוי עטרות, רמי לוי בית הפירות פת | רמי לוי עטרות, רמי לוי בית הפירות פת | 10.27 / 10.27 |
| Jerusalem centre | hand: weekly (17 lines) | 5.5 | 9.6 | - | - | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 6.4 | 10.5 | - | - | 0.0 / 0.0 |
| Jerusalem centre | drawn: 5 | 4 | 6.9 | קינג סטור ואדי אלגוז', רמי לוי עטרות | קינג סטור ואדי אלגוז', רמי לוי עטרות | 49.63 / 49.63 |
| Jerusalem centre | drawn: 10 | 4.8 | 8.6 | - | - | 0.0 / 0.0 |
| Jerusalem centre | drawn: 20 | 5.8 | 9.8 | - | - | 0.0 / 0.0 |
| Jerusalem centre | drawn: 40 | 8 | 17 | - | - | 0.0 / 0.0 |
| Holon | hand: small (6 lines) | 4 | 8 | - | - | 24.95 / 24.95 |
| Holon | hand: weekly (17 lines) | 5.6 | 9.9 | - | - | 15.75 / 15.75 |
| Holon | hand: large (32 lines) | 7.2 | 12.3 | - | - | 19.25 / 19.25 |
| Holon | drawn: 5 | 3.9 | 7.4 | רמי לוי שוויצריה סוקולוב, יוחננוף בת ים | רמי לוי שוויצריה סוקולוב, יוחננוף בת ים | 11.21 / 11.21 |
| Holon | drawn: 10 | 4.5 | 8.2 | - | - | -5.99 / -5.99 |
| Holon | drawn: 20 | 6.2 | 10.2 | רמי לוי חולון, טיב טעם בת ים | רמי לוי חולון, טיב טעם בת ים | 56.3 / 56.3 |
| Holon | drawn: 40 | 9.6 | 15.7 | - | - | 98.51 / 98.51 |
| Petah Tikva | hand: small (6 lines) | 3.9 | 7.3 | - | - | 17.64 / 17.64 |
| Petah Tikva | hand: weekly (17 lines) | 5.5 | 9.3 | - | - | 8.38 / 8.38 |
| Petah Tikva | hand: large (32 lines) | 7.1 | 11.6 | - | - | 1.52 / 1.52 |
| Petah Tikva | drawn: 5 | 4.3 | 7.9 | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | 4.7 / 4.7 |
| Petah Tikva | drawn: 10 | 4.4 | 8.2 | - | - | -12.74 / -12.74 |
| Petah Tikva | drawn: 20 | 6.1 | 10.8 | - | - | -33.0 / -33.0 |
| Petah Tikva | drawn: 40 | 9.9 | 19.8 | - | - | 42.16 / 42.16 |

### /parse-list, /compare and /optimize (stress: unreviewed mappings included, performance only)

Locations: Jerusalem centre (7 priced stores, 4 chains within 5 km); Holon (6 priced stores, 4 chains within 5 km); Petah Tikva (6 priced stores, 4 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 2101.7 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 5940.3 |
| large (32 lines) | 33 | 33 | 5 | 0 | 10903.7 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 7 | 4 | 5.8 | 5.2 | 8.8 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 7 | 3 | 7.4 | 6.4 | 11.3 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 33 | 7 | 1 | 10.6 | 8.3 | 21.9 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 5 | 5 | 7 | 4 | 4.5 | 4.2 | 7.4 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 10 | 10 | 7 | 2 | 5.1 | 4.5 | 7.9 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 20 | 20 | 7 | 0 | 7.4 | 6.3 | 10.3 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Jerusalem centre | drawn: 40 | 40 | 7 | 0 | 11.1 | 8.9 | 14.5 | 55 | single: רמי לוי עטרות | 0.0 / 0.0 |
| Holon | hand: small (6 lines) | 6 | 6 | 2 | 4.3 | 4.4 | 8 | 55 | single: רמי לוי חולון | 8.04 / 8.04 |
| Holon | hand: weekly (17 lines) | 17 | 6 | 1 | 6.8 | 6.9 | 11.3 | 55 | single: רמי לוי חולון | 0.28 / 0.28 |
| Holon | hand: large (32 lines) | 33 | 6 | 1 | 9.7 | 9.8 | 14.9 | 55 | split: רמי לוי חולון, יוחננוף בת ים | 20.72 / 20.72 |
| Holon | drawn: 5 | 5 | 6 | 3 | 5.1 | 5.9 | 8.3 | 55 | single: רמי לוי חולון | 24.83 / 24.83 |
| Holon | drawn: 10 | 10 | 6 | 1 | 4.9 | 5 | 8.5 | 55 | single: רמי לוי חולון | 18.61 / 18.61 |
| Holon | drawn: 20 | 20 | 6 | 0 | 7.3 | 7.4 | 12.6 | 55 | single: רמי לוי חולון | 79.01 / 79.01 |
| Holon | drawn: 40 | 40 | 6 | 0 | 11.6 | 11.6 | 18.9 | 55 | single: רמי לוי חולון | 367.84 / 367.84 |
| Petah Tikva | hand: small (6 lines) | 6 | 6 | 5 | 4.7 | 4.8 | 8.6 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 1.26 / 1.26 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 6 | 2 | 6.7 | 6.8 | 11 | 55 | split: רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | -5.84 / -5.84 |
| Petah Tikva | hand: large (32 lines) | 33 | 6 | 1 | 9.5 | 9.5 | 14.5 | 55 | split: רמי לוי שטמפפר פתח תקווה, יוחננוף סגולה פתח תקווה | 8.7 / 8.7 |
| Petah Tikva | drawn: 5 | 5 | 6 | 1 | 11.7 | 4.4 | 7.4 | 55 | split: אושר עד פתח תקווה - סגולה, רמי לוי שטמפפר פתח תקווה | -14.28 / -14.28 |
| Petah Tikva | drawn: 10 | 10 | 6 | 1 | 5.3 | 5.4 | 9.7 | 55 | split: רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | -13.7 / -13.7 |
| Petah Tikva | drawn: 20 | 20 | 6 | 0 | 7.8 | 7.9 | 12.2 | 55 | single: יוחננוף סגולה פתח תקווה | -8.41 / -8.41 |
| Petah Tikva | drawn: 40 | 40 | 6 | 0 | 12.4 | 11.7 | 17.9 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 32.89 / 32.89 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 4.7 | 4.8 | 8.6 |
| hand: weekly (17 lines) | 6.8 | 6.8 | 11.3 |
| hand: large (32 lines) | 9.7 | 9.5 | 14.9 |
| drawn: 5 | 5.1 | 4.4 | 7.4 |
| drawn: 10 | 5.1 | 5.0 | 8.5 |
| drawn: 20 | 7.4 | 7.4 | 12.2 |
| drawn: 40 | 11.6 | 11.6 | 17.9 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 5.2 | 8.7 | אושר עד שמגר, רמי לוי עטרות | אושר עד שמגר, רמי לוי עטרות | 0.09 / 0.09 |
| Jerusalem centre | hand: weekly (17 lines) | 7.1 | 10.9 | אושר עד תלפיות, רמי לוי עטרות | אושר עד תלפיות, רמי לוי עטרות | 20.64 / 20.64 |
| Jerusalem centre | hand: large (32 lines) | 17.8 | 13.1 | - | - | 0.0 / 0.0 |
| Jerusalem centre | drawn: 5 | 4 | 7.2 | רמי לוי עטרות, רמי לוי בית הפירות פת | רמי לוי עטרות, רמי לוי בית הפירות פת | 12.13 / 12.13 |
| Jerusalem centre | drawn: 10 | 4.5 | 8.2 | קינג סטור ואדי אלגוז', רמי לוי עטרות | קינג סטור ואדי אלגוז', רמי לוי עטרות | 17.43 / 17.43 |
| Jerusalem centre | drawn: 20 | 6.3 | 10.2 | - | - | 0.0 / 0.0 |
| Jerusalem centre | drawn: 40 | 9 | 14.3 | - | - | 0.0 / 0.0 |
| Holon | hand: small (6 lines) | 4.5 | 9.7 | - | - | 8.04 / 8.04 |
| Holon | hand: weekly (17 lines) | 7 | 11.9 | אושר עד ראשון לציון, רמי לוי חולון | אושר עד ראשון לציון, רמי לוי חולון | 35.0 / 35.0 |
| Holon | hand: large (32 lines) | 9.6 | 15.8 | רמי לוי חולון, יוחננוף בת ים | רמי לוי חולון, יוחננוף בת ים | 45.72 / 45.72 |
| Holon | drawn: 5 | 4.4 | 9.2 | - | - | 24.83 / 24.83 |
| Holon | drawn: 10 | 5.2 | 9 | רמי לוי חולון, טיב טעם בת ים | רמי לוי חולון, טיב טעם בת ים | 33.88 / 33.88 |
| Holon | drawn: 20 | 7.2 | 12.5 | - | - | 79.01 / 79.01 |
| Holon | drawn: 40 | 11.7 | 18.2 | - | - | 367.84 / 367.84 |
| Petah Tikva | hand: small (6 lines) | 4.8 | 8.5 | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | 3.36 / 3.36 |
| Petah Tikva | hand: weekly (17 lines) | 7 | 11.2 | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | 19.16 / 19.16 |
| Petah Tikva | hand: large (32 lines) | 9.4 | 14.6 | רמי לוי שטמפפר פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי שטמפפר פתח תקווה, יוחננוף סגולה פתח תקווה | 33.7 / 33.7 |
| Petah Tikva | drawn: 5 | 4.5 | 7.7 | אושר עד פתח תקווה - סגולה, רמי לוי שטמפפר פתח תקווה | אושר עד פתח תקווה - סגולה, רמי לוי שטמפפר פתח תקווה | 10.72 / 10.72 |
| Petah Tikva | drawn: 10 | 5.8 | 9.2 | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | רמי לוי קניון אבנת פתח תקווה, יוחננוף סגולה פתח תקווה | 11.3 / 11.3 |
| Petah Tikva | drawn: 20 | 7.8 | 12.7 | טיב טעם בית הדובדבן - אונו, יוחננוף סגולה פתח תקווה | טיב טעם בית הדובדבן - אונו, יוחננוף סגולה פתח תקווה | 62.9 / 62.9 |
| Petah Tikva | drawn: 40 | 11.2 | 17.8 | - | - | 32.89 / 32.89 |

### Basket index on the real day (#44, dry run, production semantics)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

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

Basket of 25 lines; price date 2026-10-22T09:00:17Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| קינג סטור | - | 8 | 17 | 2 | no |
| רמי לוי | - | 19 | 6 | 7 | no |
| אושר עד | - | 8 | 17 | 5 | no |
| יוחננוף | - | 14 | 11 | 4 | no |
| טיב טעם | - | 13 | 12 | 5 | no |

Cost of each line per chain (ILS, median store x amount; the lines two chains price 2x apart or more are marked *):

| line | amount | king_store | ramilevy | osherad | yohananof | tivtaam |
|---|---|---|---|---|---|---|
| bamba | 2 | - | 0.09 | - | - | - |
| banana | 1 | - | - | - | - | 11.9 |
| bread-standard* | 7.5 | - | 0.07 | 6.67 | 7.58 | 8.4 |
| butter* | 2 | - | 0.1 | 9.5 | - | - |
| canola-oil* | 10 | 10.9 | 0.9 | 0.54 | 7.5 | 10.9 |
| chicken-breast-fresh | 1 | - | 37.5 | - | 34.9 | 41.9 |
| cottage-5* | 5 | - | 0.15 | 12.0 | 12.4 | 12.2 |
| cucumber | 1 | - | - | - | - | 7.9 |
| eggs-l | 12 | - | 170.4 | - | - | - |
| milk-fresh-3 | 20 | 14.7 | 14.2 | - | 14.7 | - |
| mineral-water | 60 | 10.56 | 0.0 | - | 9.96 | - |
| onion | 1 | 5.22 | 4.9 | - | 4.4 | 5.9 |
| pita | 10 | - | 14.7 | - | - | - |
| potato | 2 | - | - | 13.56 | - | 16.8 |
| rice-persian* | 10 | - | 0.09 | 4.9 | 7.45 | 10.9 |
| sugar-white* | 10 | 4.9 | 0.1 | - | 11.9 | 5.5 |
| toilet-paper | 24 | 20.88 | 669.6 | 0.0 | 420.0 | 789.6 |
| tomato* | 1.5 | - | 25.35 | - | 84.0 | 13.35 |
| tuna-in-oil* | 4.8 | - | 0.61 | 16.42 | 14.93 | - |
| white-cheese-5* | 5 | 11.7 | 0.1 | - | 11.75 | 11.75 |
| yellow-cheese-sliced-28 | 4 | - | 0.16 | - | - | - |
| yogurt-plain-3* | 8 | 14.8 | 0.15 | - | 14.4 | - |

Items behind `white-cheese-5` (up to 3 per chain, cheapest unit price first):
- king_store: גבינה לבנה 5% שומן 250 ג' תנובה, shelf 5.87, unit price 2.34 per 100g
- ramilevy: גבינה לבנה סקי 5% שו, shelf 5.8, unit price 0.02 per 100g
- ramilevy: גבינה לבנה סקי 5% שו, shelf 5.8, unit price 0.02 per 100g
- ramilevy: גבינה לבנה סקי 5% שו, shelf 5.8, unit price 0.02 per 100g
- yohananof: גבינה לבנה 5% 250 גר, shelf 5.81, unit price 2.32 per 100g
- yohananof: גבינה לבנה 5% 250 גר, shelf 5.87, unit price 2.35 per 100g
- yohananof: גבינה לבנה 5% 250 גר, shelf 5.87, unit price 2.35 per 100g
- tivtaam: גבינה לבנה 5% 250 גר, shelf 5.87, unit price 2.35 per 100g
- tivtaam: גבינה לבנה 5% 250 גר, shelf 5.87, unit price 2.35 per 100g
- tivtaam: גבינה לבנה 5% 250 גר, shelf 5.87, unit price 2.35 per 100g

Items behind `yogurt-plain-3` (up to 3 per chain, cheapest unit price first):
- king_store: יוגורט טבעי 3% שומן 200 ג' תנובה, shelf 3.7, unit price 1.85 per 100g
- ramilevy: יוגורט ביו טבעי 3% 5, shelf 7.8, unit price 0.0167 per 100g
- ramilevy: יוגורט ביו טבעי 3% 5, shelf 7.8, unit price 0.0167 per 100g
- ramilevy: יוגורט ביו טבעי 3% 5, shelf 7.8, unit price 0.0167 per 100g
- yohananof: יוגורט תנובה טבעי 3%, shelf 3.6, unit price 1.8 per 100g
- yohananof: יוגורט תנובה טבעי 3%, shelf 3.6, unit price 1.8 per 100g
- yohananof: יוגורט תנובה טבעי 3%, shelf 3.6, unit price 1.8 per 100g

Items behind `sugar-white` (up to 3 per chain, cheapest unit price first):
- king_store: סוכר לבן 1 ק"ג ROSE, shelf 4.9, unit price 0.49 per 100g
- king_store: סוכר לבן 1 ק"ג ROSE, shelf 4.9, unit price 0.49 per 100g
- ramilevy: סוכר לבן 1 ק"ג שטודן, shelf 4.9, unit price 0 per 100g
- ramilevy: סוכר לבן 1 ק"ג שטודן, shelf 4.9, unit price 0 per 100g
- ramilevy: סוכר לבן 1 ק"ג שטודן, shelf 4.9, unit price 0 per 100g
- yohananof: סוכר לבן בצנצנת 1ק"ג, shelf 9.9, unit price 0.99 per 100g
- yohananof: סוכר לבן בצנצנת 1ק"ג, shelf 11.9, unit price 1.19 per 100g
- yohananof: סוכר לבן בצנצנת 1ק"ג, shelf 11.9, unit price 1.19 per 100g
- tivtaam: סוכר לבן 1 ק"ג, shelf 5.5, unit price 0.55 per 100g
- tivtaam: סוכר לבן 1 ק"ג, shelf 5.5, unit price 0.55 per 100g
- tivtaam: סוכר לבן 1 ק"ג, shelf 5.5, unit price 0.55 per 100g

Items behind `canola-oil` (up to 3 per chain, cheapest unit price first):
- king_store: שמן קנולה מילומור 1 ל', shelf 10.9, unit price 1.09 per 100ml
- king_store: שמן קנולה מילומור 1 ל', shelf 10.9, unit price 1.09 per 100ml
- ramilevy: שמן קנולה אורגני בכב, shelf 27.9, unit price 0.03 per 100ml
- ramilevy: תרסיס שמן קנולה עץ ה, shelf 15.9, unit price 0.0649 per 100ml
- ramilevy: תרסיס שמן קנולה עץ ה, shelf 15.9, unit price 0.0649 per 100ml
- osherad: תרסיס שמן קנולה שקדי, shelf 9.9, unit price 0.05 per 100ml
- osherad: תרסיס שמן קנולה שקדי, shelf 13.9, unit price 0.0504 per 100ml
- osherad: תרסיס שמן קנולה שקדי, shelf 14.9, unit price 0.0537 per 100ml
- yohananof: שמן קנולה 1 ליטר  יו, shelf 8.9, unit price 0.75 per 100ml
- yohananof: שמן קנולה 1 ליטר  יו, shelf 8.9, unit price 0.75 per 100ml
- yohananof: שמן קנולה 1 ליטר  יו, shelf 8.9, unit price 0.75 per 100ml
- tivtaam: שמן קנולה 1 ליטר, shelf 10.9, unit price 1.09 per 100ml
- tivtaam: שמן קנולה 1 ליטר, shelf 10.9, unit price 1.09 per 100ml
- tivtaam: שמן קנולה 1 ליטר, shelf 10.9, unit price 1.09 per 100ml

Items behind `cottage-5` (up to 3 per chain, cheapest unit price first):
- ramilevy: גבינת קוטג' מועשר 5%, shelf 6, unit price 0.02 per 100g
- ramilevy: גבינת קוטג' מועשר 5%, shelf 6, unit price 0.02 per 100g
- ramilevy: גבינת קוטג' מועשר 5%, shelf 6, unit price 0.02 per 100g
- osherad: קוטג 5% טרה 250 גרם, shelf 5.9, unit price 2.36 per 100g
- osherad: קוטג 5% טרה 250 גרם, shelf 6, unit price 2.4 per 100g
- osherad: קוטג 5% טרה 250 גרם, shelf 6, unit price 2.4 per 100g
- yohananof: קוטג 5% 250 גרם נעם, shelf 6, unit price 2.4 per 100g
- yohananof: קוטג 5% 250 גרם נעם, shelf 6.2, unit price 2.48 per 100g
- yohananof: קוטג 5% 250 גרם נעם, shelf 6.2, unit price 2.48 per 100g
- tivtaam: גבינת קוטג  5% 250 גרם, shelf 6.1, unit price 2.44 per 100g
- tivtaam: גבינת קוטג  5% 250 גרם, shelf 6.1, unit price 2.44 per 100g
- tivtaam: גבינת קוטג  5% 250 גרם, shelf 6.1, unit price 2.44 per 100g

Items behind `butter` (up to 3 per chain, cheapest unit price first):
- ramilevy: חמאה טרה 200 גרם, shelf 9.5, unit price 0.05 per 100g
- osherad: חמאה טרה 200 גרם, shelf 8.9, unit price 4.45 per 100g
- osherad: חמאה טרה 200 גרם, shelf 9.5, unit price 4.75 per 100g
- osherad: חמאה טרה 200 גרם, shelf 9.5, unit price 4.75 per 100g

Items behind `tomato` (up to 3 per chain, cheapest unit price first):
- ramilevy: עגבניות מגי, shelf 13.9, unit price 13.9 per kg (estimated)
- ramilevy: עגבניות מגי, shelf 15.9, unit price 15.9 per kg (estimated)
- ramilevy: עגבניות מגי, shelf 16.9, unit price 16.9 per kg (estimated)
- yohananof: סלט עגבניות מבושל, shelf 56, unit price 56 per kg (estimated)
- tivtaam: עגבניות, shelf 7.9, unit price 7.9 per kg (estimated)
- tivtaam: עגבניות, shelf 7.9, unit price 7.9 per kg (estimated)
- tivtaam: עגבניות, shelf 8.9, unit price 8.9 per kg (estimated)

Items behind `bread-standard` (up to 3 per chain, cheapest unit price first):
- ramilevy: לחם אחיד פרוס ודש בר, shelf 7.7, unit price 0.01 per 100g
- ramilevy: לחם אחיד פרוס ברמן, shelf 8.2, unit price 0.01 per 100g
- ramilevy: לחם אחיד אנג'ל 750 ג, shelf 7.36, unit price 0.01 per 100g
- osherad: לחם אחיד פרוס דוידוב, shelf 5.9, unit price 0.79 per 100g
- osherad: לחם אחיד פרוס דוידוב, shelf 6.7, unit price 0.89 per 100g
- osherad: לחם אחיד פרוס דוידוב, shelf 6.7, unit price 0.89 per 100g
- yohananof: לחם אחיד פרוס 750 גר, shelf 7.6, unit price 1.01 per 100g
- yohananof: לחם אחיד פרוס 750 גר, shelf 7.6, unit price 1.01 per 100g
- yohananof: לחם אחיד פרוס 750 גר, shelf 7.6, unit price 1.01 per 100g
- tivtaam: לחם אחיד פרוס, shelf 8.38, unit price 1.12 per 100g
- tivtaam: לחם אחיד פרוס, shelf 8.38, unit price 1.12 per 100g
- tivtaam: לחם אחיד פרוס, shelf 8.38, unit price 1.12 per 100g

Items behind `rice-persian` (up to 3 per chain, cheapest unit price first):
- ramilevy: אורז פרסי 1קג שקדיה, shelf 8.9, unit price 0.0056 per 100g
- ramilevy: אורז פרסי 1קג שקדיה, shelf 8.9, unit price 0.0067 per 100g
- ramilevy: אורז פרסי 1קג שקדיה, shelf 8.9, unit price 0.0067 per 100g
- osherad: אורז פרסי הנמל 1 ק"ג, shelf 7.9, unit price 0.49 per 100g
- osherad: אורז פרסי הנמל 1 ק"ג, shelf 7.9, unit price 0.49 per 100g
- osherad: אורז פרסי הנמל 1 ק"ג, shelf 7.9, unit price 0.49 per 100g
- yohananof: אורז פרסי שקדיה 1 ק", shelf 8.9, unit price 0.6 per 100g
- yohananof: אורז פרסי שקדיה 1 ק", shelf 8.9, unit price 0.6 per 100g
- yohananof: אורז פרסי דוואט 1 ק", shelf 11.9, unit price 0.69 per 100g
- tivtaam: אורז פרסי שקדיה 1 ק"ג, shelf 9.9, unit price 0.79 per 100g
- tivtaam: אורז פרסי שקדיה 1 ק"ג, shelf 9.9, unit price 0.79 per 100g
- tivtaam: אורז פרסי טילדה 1 ק"ג, shelf 15.9, unit price 1.09 per 100g

Items behind `tuna-in-oil` (up to 3 per chain, cheapest unit price first):
- ramilevy: ויליגר טונה בשמן 140, shelf 5.8, unit price 0.04 per 100g
- ramilevy: ויליגר טונה בשמן 140, shelf 5, unit price 0.04 per 100g
- ramilevy: נתחי טונה בשמן קנולה, shelf 12.9, unit price 0.05 per 100g
- osherad: טונה בשמן צמחי פילטו, shelf 21.9, unit price 3.42 per 100g
- osherad: טונה בשמן צמחי פילטו, shelf 21.9, unit price 3.42 per 100g
- osherad: טונה בשמן סטארקיסט 4, shelf 24.9, unit price 3.4369 per 100g
- yohananof: שימורי טונה בשמן  4*, shelf 17.9, unit price 2.8 per 100g
- yohananof: רביעיית טונה בשמן קנ, shelf 19.9, unit price 3.11 per 100g
- yohananof: רביעיית טונה בשמן קנ, shelf 22.9, unit price 3.111 per 100g

### Basket index on the real day (#44, dry run, stress)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `estimated_items` רמי לוי: 3 lines use estimated weighed-goods prices
- warning: `estimated_items` יוחננוף: 6 lines use estimated weighed-goods prices
- warning: `estimated_items` טיב טעם: 6 lines use estimated weighed-goods prices
- warning: `missing_items` קינג סטור has no price for 2 basket items (bread-standard, tuna-in-oil); it is listed but not ranked
- warning: `estimated_items` קינג סטור: 6 lines use estimated weighed-goods prices
- warning: `missing_items` אושר עד has no price for 4 basket items (chicken-breast-fresh, onion, banana, pita); it is listed but not ranked
- error: `implausible_spread` cheapest and dearest chain differ by 56.5% (limit 50.00%)

Basket of 25 lines; price date 2026-10-22T09:00:17Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| רמי לוי | 908.24 | 25 | 0 | 7 | yes |
| יוחננוף | 928.27 | 25 | 0 | 4 | yes |
| טיב טעם | 1421.25 | 25 | 0 | 5 | yes |
| קינג סטור | - | 23 | 2 | 2 | no |
| אושר עד | - | 21 | 4 | 5 | no |

Cost of each line per chain (ILS, median store x amount; the lines two chains price 2x apart or more are marked *):

| line | amount | king_store | ramilevy | osherad | yohananof | tivtaam |
|---|---|---|---|---|---|---|
| bamba* | 2 | 12.41 | 0.08 | 7.49 | 8.76 | 11.59 |
| banana* | 1 | 10.45 | 5.69 | - | 9.4 | 11.9 |
| bread-standard* | 7.5 | - | 0.07 | 6.67 | 4.88 | 8.4 |
| butter* | 2 | 11.5 | 0.08 | 6.1 | 6.2 | 10.0 |
| canola-oil* | 10 | 10.9 | 0.9 | 0.54 | 7.5 | 10.9 |
| chicken-breast-fresh | 1 | 39.9 | 26.4 | - | 24.9 | 33.9 |
| chocolate-milk* | 10 | 13.2 | 0.2 | 0.1 | 9.0 | 12.45 |
| cottage-5* | 5 | 13.3 | 0.1 | 11.8 | 12.4 | 12.2 |
| cucumber | 1 | 5.45 | 0.1 | 0.0 | 6.4 | 7.9 |
| eggs-l* | 12 | 14.16 | 170.4 | 14.04 | 170.88 | 170.88 |
| hummus-plain* | 4 | 7.21 | 0.12 | 9.52 | 8.92 | 8.8 |
| milk-fresh-3 | 20 | 14.7 | 14.2 | 14.4 | 14.7 | 14.8 |
| mineral-water | 60 | 7.25 | 0.0 | 0.39 | 9.96 | 13.92 |
| onion | 1 | 5.22 | 4.9 | - | 4.4 | 5.9 |
| pasta-spaghetti* | 5 | 6.97 | 0.04 | 3.9 | 3.75 | 6.5 |
| pita* | 10 | 14.9 | 13.9 | - | 99.0 | 169.0 |
| potato* | 2 | 10.4 | 0.4 | 9.96 | 7.8 | 13.8 |
| rice-persian* | 10 | 12.9 | 0.09 | 4.9 | 7.45 | 9.9 |
| sugar-white | 10 | 4.9 | 0.1 | 0.0 | 4.9 | 5.5 |
| toilet-paper | 24 | 20.88 | 669.6 | 0.0 | 420.0 | 789.6 |
| tomato* | 1.5 | 11.55 | 0.22 | 16.12 | 11.1 | 13.35 |
| tuna-in-oil* | 4.8 | - | 0.24 | 16.42 | 14.03 | 19.1 |
| white-cheese-5* | 5 | 11.7 | 0.1 | 11.6 | 11.75 | 11.75 |
| yellow-cheese-sliced-28* | 4 | 39.8 | 0.16 | 12.0 | 35.8 | 33.6 |
| yogurt-plain-3* | 8 | 14.8 | 0.15 | 15.2 | 14.4 | 15.6 |

Items behind `cottage-5` (up to 3 per chain, cheapest unit price first):
- king_store: קוטג תנובה גביע 250 גר5%, shelf 6.6, unit price 2.64 per 100g
- king_store: קוטג' 5% שומן 250 ג' שטראוס, shelf 6.7, unit price 2.68 per 100g
- ramilevy: קוטג' תנובה 5% שומן, shelf 5.9, unit price 0.02 per 100g
- ramilevy: קוטג' תנובה 5% שומן, shelf 5.9, unit price 0.02 per 100g
- ramilevy: קוטג' תנובה 5% שומן, shelf 6.1, unit price 0.02 per 100g
- osherad: קוטג 5% תנובה 250 גר, shelf 5.9, unit price 2.36 per 100g
- osherad: קוטג 5% תנובה 250 גר, shelf 5.9, unit price 2.36 per 100g
- osherad: קוטג 5% תנובה 250 גר, shelf 5.9, unit price 2.36 per 100g
- yohananof: קוטג 5% 250 גרם נעם, shelf 6, unit price 2.4 per 100g
- yohananof: קוטג 5% 250 גרם נעם, shelf 6.2, unit price 2.48 per 100g
- yohananof: קוטג 5% 250 גרם נעם, shelf 6.2, unit price 2.48 per 100g
- tivtaam: גבינת קוטג מהדרין 5% 250 גרם, shelf 6.1, unit price 2.44 per 100g
- tivtaam: גבינת קוטג מהדרין 5% 250 גרם, shelf 6.1, unit price 2.44 per 100g
- tivtaam: גבינת קוטג מהדרין 5% 250 גרם, shelf 6.1, unit price 2.44 per 100g

Items behind `white-cheese-5` (up to 3 per chain, cheapest unit price first):
- king_store: גבינה לבנה 5% שומן 250 ג' תנובה, shelf 5.87, unit price 2.34 per 100g
- ramilevy: גבינה לבנה סקי 5% שו, shelf 5.8, unit price 0.02 per 100g
- ramilevy: גבינה לבנה סקי 5% שו, shelf 5.8, unit price 0.02 per 100g
- ramilevy: גבינה לבנה סקי 5% שו, shelf 5.8, unit price 0.02 per 100g
- osherad: גבינה 5% טרה 250 גרם, shelf 4.7, unit price 1.88 per 100g
- osherad: גבינה 5% סקי 250 גרם, shelf 5.8, unit price 2 per 100g
- osherad: גבינה 5% סקי 250 גרם, shelf 5.8, unit price 2.32 per 100g
- yohananof: גבינה לבנה 5% 250 גר, shelf 5.81, unit price 2.32 per 100g
- yohananof: גבינה לבנה 5% 250 גר, shelf 5.87, unit price 2.35 per 100g
- yohananof: גבינה לבנה 5% 250 גר, shelf 5.87, unit price 2.35 per 100g
- tivtaam: גבינה לבנה 5% 250 גר, shelf 5.87, unit price 2.35 per 100g
- tivtaam: גבינה לבנה 5% 250 גר, shelf 5.87, unit price 2.35 per 100g
- tivtaam: גבינה לבנה 5% 250 גר, shelf 5.87, unit price 2.35 per 100g

Items behind `yellow-cheese-sliced-28` (up to 3 per chain, cheapest unit price first):
- king_store: גבינת דק דק 28% 200 ג' עמק, shelf 19.9, unit price 9.95 per 100g
- king_store: גבינת דק דק 28% 200 ג' עמק, shelf 19.9, unit price 9.95 per 100g
- ramilevy: גבינה צהובה 28% רמי, shelf 14, unit price 0.04 per 100g
- ramilevy: גבינה צהובה 28% רמי, shelf 14, unit price 0.04 per 100g
- ramilevy: גבינה צהובה 28% רמי, shelf 14, unit price 0.04 per 100g
- osherad: גבינת גאודה פרוסה 28, shelf 30, unit price 3 per 100g
- osherad: גבינת גאודה פרוסה 28, shelf 30, unit price 3 per 100g
- osherad: גבינת גאודה פרוסה 28, shelf 30, unit price 3 per 100g
- yohananof: פתיתי עמק 28% שומן, shelf 17.9, unit price 8.95 per 100g
- yohananof: פתיתי עמק 28% שומן, shelf 17.9, unit price 8.95 per 100g
- yohananof: פתיתי עמק 28% שומן, shelf 17.9, unit price 8.95 per 100g
- tivtaam: גבינה צהובה גוש חלב 200 גרם, shelf 16.8, unit price 8.4 per 100g
- tivtaam: גבינה צהובה גוש חלב 200 גרם, shelf 16.8, unit price 8.4 per 100g
- tivtaam: גבינה צהובה גוש חלב 200 גרם, shelf 16.8, unit price 8.4 per 100g

Items behind `yogurt-plain-3` (up to 3 per chain, cheapest unit price first):
- king_store: יוגורט טבעי 3% שומן 200 ג' תנובה, shelf 3.7, unit price 1.85 per 100g
- ramilevy: יוגורט ביו טבעי 3% 5, shelf 7.8, unit price 0.0167 per 100g
- ramilevy: יוגורט ביו טבעי 3% 5, shelf 7.8, unit price 0.0167 per 100g
- ramilevy: יוגורט ביו טבעי 3% 5, shelf 7.8, unit price 0.0167 per 100g
- osherad: יוגורט ביו תנובה 3%, shelf 2.9, unit price 1.45 per 100g
- osherad: יוגורט ביו דנונה 3%, shelf 3.8, unit price 1.9 per 100g
- osherad: יוגורט ביו דנונה 3%, shelf 3.8, unit price 1.9 per 100g
- yohananof: יוגורט תנובה טבעי 3%, shelf 3.6, unit price 1.8 per 100g
- yohananof: יוגורט תנובה טבעי 3%, shelf 3.6, unit price 1.8 per 100g
- yohananof: יוגורט תנובה טבעי 3%, shelf 3.6, unit price 1.8 per 100g
- tivtaam: יוגורט תנובה 3% 200 גר, shelf 3.9, unit price 1.95 per 100g
- tivtaam: יוגורט תנובה 3% 200 גר, shelf 3.9, unit price 1.95 per 100g
- tivtaam: יוגורט תנובה 3% 200 גר, shelf 3.9, unit price 1.95 per 100g

Items behind `butter` (up to 3 per chain, cheapest unit price first):
- king_store: חמאה 200 ג' תנובה, shelf 11.5, unit price 5.75 per 100g
- king_store: חמאה 200 ג' תנובה, shelf 11.5, unit price 5.75 per 100g
- ramilevy: חמאה עלמה 200 גר, shelf 9.9, unit price 0.0399 per 100g
- ramilevy: חמאה עלמה 200 גר, shelf 9.9, unit price 0.0399 per 100g
- ramilevy: חמאה עלמה 200 גר, shelf 9.9, unit price 0.0399 per 100g
- osherad: מחמאה בלובנד 200 גרם, shelf 5.2, unit price 2.6 per 100g
- osherad: מחמאה בלובנד 200 גרם, shelf 6.1, unit price 3.05 per 100g
- osherad: מחמאה בלובנד 200 גרם, shelf 6.1, unit price 3.05 per 100g
- yohananof: מחמאה בלובנד 200 גרם, shelf 6.2, unit price 3.1 per 100g
- yohananof: מחמאה בלובנד 200 גרם, shelf 6.2, unit price 3.1 per 100g
- yohananof: מחמאה בלובנד 200 גרם, shelf 6.2, unit price 3.1 per 100g
- tivtaam: ממרח חמאה 72.5% 200 גר, shelf 9.9, unit price 4.95 per 100g
- tivtaam: חמאה צרפתית 200 גר, shelf 19.9, unit price 5 per 100g
- tivtaam: חמאה צרפתית 200 גר, shelf 19.9, unit price 5 per 100g

Items behind `eggs-l` (up to 3 per chain, cheapest unit price first):
- king_store: ביצים לארג' 12 יח', shelf 14.24, unit price 1.18 per unit
- ramilevy: ביצים גדולות לארג 12, shelf 14.2, unit price 1.18 per unit
- ramilevy: ביצים 12 יח גדול L, shelf 14.2, unit price 14.2 per unit
- ramilevy: ביצים 12 יח גדול L, shelf 14.2, unit price 14.2 per unit
- osherad: ביצים 12 יח' גדול זג, shelf 14.09, unit price 1.17 per unit
- yohananof: ביצים 12 יח גדול, shelf 14.24, unit price 14.24 per unit
- yohananof: ביצים 12 יח  גדול, shelf 14.24, unit price 14.24 per unit
- yohananof: ביצים 12 יח  גדול, shelf 14.24, unit price 14.24 per unit
- tivtaam: ביצים אריזון 12 גדול, shelf 14.24, unit price 14.24 per unit
- tivtaam: ביצים אריזון 12 גדול, shelf 14.24, unit price 14.24 per unit
- tivtaam: ביצים אריזון 12 גדול, shelf 14.24, unit price 14.24 per unit

Items behind `hummus-plain` (up to 3 per chain, cheapest unit price first):
- king_store: חומוס 400 ג' ג'נא, shelf 3.5, unit price 0.87 per 100g
- king_store: חומוס טחינה אחלה 400 ג', shelf 12.9, unit price 2.7333 per 100g
- ramilevy: סלט חומוס אחלה 400 ג, shelf 8.9, unit price 0.02 per 100g
- ramilevy: סלט חומוס אחלה 400 ג, shelf 8.9, unit price 0.02 per 100g
- ramilevy: סלט חומוס אחלה 400 ג, shelf 8.9, unit price 0.02 per 100g
- osherad: סלט חומוס מסבחה אסלי, shelf 8.9, unit price 2.23 per 100g
- osherad: חומוס אחלה 400 גרם, shelf 9.5, unit price 2.38 per 100g
- osherad: חומוס אחלה 400 גרם, shelf 9.5, unit price 2.38 per 100g
- yohananof: חומוס 400 אחלה, shelf 8.9, unit price 2.23 per 100g
- yohananof: חומוס 400 אחלה, shelf 8.9, unit price 2.23 per 100g
- yohananof: חומוס 400 אחלה, shelf 8.9, unit price 2.23 per 100g
- tivtaam: חומוס הבית להכנת חומוס טרי יכין 400 גר, shelf 9, unit price 2.2 per 100g
- tivtaam: חומוס הבית להכנת חומוס טרי יכין 400 גר, shelf 9, unit price 2.2 per 100g
- tivtaam: חומוס הבית להכנת חומוס טרי יכין 400 גר, shelf 9, unit price 2.2 per 100g

Items behind `tomato` (up to 3 per chain, cheapest unit price first):
- king_store: עגבניה, shelf 3.5, unit price 3.5 per kg (estimated)
- king_store: עגבניה, shelf 11.9, unit price 11.9 per kg (estimated)
- ramilevy: עגבניות פלופה צ'יריו, shelf 5, unit price 0.1 per kg
- ramilevy: עגבניות חתוכות דק בק, shelf 12.9, unit price 0.138 per kg
- ramilevy: עגבניות חתוכות דק בק, shelf 12.9, unit price 0.138 per kg
- osherad: מארז עגבניות קוביות, shelf 7.9, unit price 6.58 per kg
- osherad: מארז עגבניות קצוצות, shelf 7.9, unit price 6.58 per kg
- osherad: מארז עגבניות קוביות, shelf 12.9, unit price 10.75 per kg
- yohananof: עגבניה, shelf 6.9, unit price 6.9 per kg (estimated)
- yohananof: עגבניה, shelf 6.9, unit price 6.9 per kg (estimated)
- yohananof: עגבניה, shelf 7.9, unit price 7.9 per kg (estimated)
- tivtaam: עגבניות, shelf 7.9, unit price 7.9 per kg (estimated)
- tivtaam: עגבניות, shelf 7.9, unit price 7.9 per kg (estimated)
- tivtaam: עגבניות, shelf 8.9, unit price 8.9 per kg (estimated)

Items behind `potato` (up to 3 per chain, cheapest unit price first):
- king_store: תפו"א לבן ארוז, shelf 4.5, unit price 4.5 per kg (estimated)
- king_store: תפו"א לבן ארוז, shelf 5.9, unit price 5.9 per kg (estimated)
- ramilevy: בורקס תפוחי אדמה שלו, shelf 16.8, unit price 0.1786 per kg
- ramilevy: בורקס תפוחי אדמה שלו, shelf 16.8, unit price 0.1786 per kg
- ramilevy: בורקס תפוחי אדמה שלו, shelf 16.8, unit price 0.1786 per kg
- osherad: תפוח אדמה לבן יח אפי, shelf 6.9, unit price 1.38 per kg
- osherad: תפוח אדמה אדום לאפיה, shelf 5.9, unit price 2.36 per kg
- osherad: תפוח אדמה לבן, shelf 24.9, unit price 4.98 per kg
- yohananof: תפו"א לבן ארוז, shelf 3.9, unit price 3.9 per kg (estimated)
- yohananof: תפו"א לבן ארוז, shelf 3.9, unit price 3.9 per kg (estimated)
- yohananof: תפו"א לבן ארוז, shelf 3.9, unit price 3.9 per kg (estimated)
- tivtaam: תפו"א אדום, shelf 5.9, unit price 5.9 per kg (estimated)
- tivtaam: תפו"א אדום, shelf 5.9, unit price 5.9 per kg (estimated)
- tivtaam: תפו"א אדום, shelf 6.9, unit price 6.9 per kg (estimated)

Items behind `banana` (up to 3 per chain, cheapest unit price first):
- king_store: בננה, shelf 10, unit price 10 per kg (estimated)
- king_store: בננה, shelf 10.9, unit price 10.9 per kg (estimated)
- ramilevy: סמוזי בננה תרד, shelf 5.9, unit price 0.4746 per kg
- ramilevy: סמוזי בננה תרד, shelf 5.9, unit price 0.4746 per kg
- ramilevy: סמוזי בננה תרד, shelf 5.9, unit price 0.4746 per kg
- yohananof: בננה, shelf 7.9, unit price 7.9 per kg (estimated)
- yohananof: בננה, shelf 8.9, unit price 8.9 per kg (estimated)
- yohananof: בננה, shelf 9.9, unit price 9.9 per kg (estimated)
- tivtaam: בננות, shelf 10.9, unit price 10.9 per kg (estimated)
- tivtaam: בננות, shelf 10.9, unit price 10.9 per kg (estimated)
- tivtaam: בננות, shelf 11.9, unit price 11.9 per kg (estimated)

Items behind `pita` (up to 3 per chain, cheapest unit price first):
- king_store: עשיריית פיתות אנגל, shelf 14.9, unit price 1.49 per unit
- ramilevy: פיתות ביס 10 יח, shelf 11.9, unit price 1.19 per unit
- ramilevy: פיתות אסלי 10יח ברמן, shelf 13.9, unit price 1.39 per unit
- ramilevy: פיתות אסלי 10יח ברמן, shelf 13.9, unit price 1.39 per unit
- yohananof: פיתות מארז 10 יח, shelf 9.9, unit price 9.9 per unit
- yohananof: פיתות מארז 10 יח, shelf 9.9, unit price 9.9 per unit
- yohananof: פיתות מארז 10 יח, shelf 9.9, unit price 9.9 per unit
- tivtaam: פיתות מיני ביס עננים 10 יחידות, shelf 16.9, unit price 16.9 per unit
- tivtaam: פיתות מיני ביס עננים 10 יחידות, shelf 16.9, unit price 16.9 per unit
- tivtaam: פיתות מיני ביס עננים 10 יחידות, shelf 16.9, unit price 16.9 per unit

Items behind `rice-persian` (up to 3 per chain, cheapest unit price first):
- king_store: אורז פרסי קלאסי 1 ק"ג סוגת, shelf 12.9, unit price 1.29 per 100g
- king_store: אורז פרסי קלאסי 1 ק"ג סוגת, shelf 12.9, unit price 1.29 per 100g
- ramilevy: אורז פרסי 1קג שקדיה, shelf 8.9, unit price 0.0056 per 100g
- ramilevy: אורז פרסי 1קג שקדיה, shelf 8.9, unit price 0.0067 per 100g
- ramilevy: אורז פרסי 1קג שקדיה, shelf 8.9, unit price 0.0067 per 100g
- osherad: אורז פרסי הנמל 1 ק"ג, shelf 7.9, unit price 0.49 per 100g
- osherad: אורז פרסי הנמל 1 ק"ג, shelf 7.9, unit price 0.49 per 100g
- osherad: אורז פרסי הנמל 1 ק"ג, shelf 7.9, unit price 0.49 per 100g
- yohananof: אורז פרסי שקדיה 1 ק", shelf 8.9, unit price 0.6 per 100g
- yohananof: אורז פרסי שקדיה 1 ק", shelf 8.9, unit price 0.6 per 100g
- yohananof: אורז פרסי דוואט 1 ק", shelf 11.9, unit price 0.69 per 100g
- tivtaam: אורז פרסי שקדיה 1 ק"ג, shelf 9.9, unit price 0.79 per 100g
- tivtaam: אורז פרסי שקדיה 1 ק"ג, shelf 9.9, unit price 0.79 per 100g
- tivtaam: אורז פרסי 1 ק"ג DAAWAT, shelf 13.9, unit price 0.99 per 100g

Items behind `pasta-spaghetti` (up to 3 per chain, cheapest unit price first):
- king_store: פרפקטו ספגטי 500 ג' אסם, shelf 8.5, unit price 1.39 per 100g
- king_store: פסטה ספגטי 500 ג' אסם, shelf 7, unit price 1.4 per 100g
- ramilevy: פסטה ספגטי 500 גר wb, shelf 4, unit price 0.0063 per 100g
- ramilevy: פסטה ספגטי 500 גר wb, shelf 4, unit price 0.0063 per 100g
- ramilevy: פסטה ספגטי 500 גר wb, shelf 4, unit price 0.0063 per 100g
- osherad: פסטה ספגטי מונו פוד, shelf 2.9, unit price 0.58 per 100g
- osherad: פסטה ספגטי מונו פוד, shelf 2.9, unit price 0.58 per 100g
- osherad: ספגטי טעמן 500 גרם, shelf 3.9, unit price 0.78 per 100g
- yohananof: פסטה ספגטי ריסקוסה 5, shelf 5.9, unit price 0.75 per 100g
- yohananof: פסטה ספגטי ריסקוסה 5, shelf 5.9, unit price 0.75 per 100g
- yohananof: פסטה ספגטי ריסקוסה 5, shelf 4.9, unit price 0.75 per 100g
- tivtaam: ספגטי (3) 500 גרם, shelf 6.5, unit price 1.3 per 100g
- tivtaam: ספגטי (3) 500 גרם, shelf 6.5, unit price 1.3 per 100g
- tivtaam: ספגטי (3) 500 גרם, shelf 6.5, unit price 1.3 per 100g

Items behind `canola-oil` (up to 3 per chain, cheapest unit price first):
- king_store: שמן קנולה מילומור 1 ל', shelf 10.9, unit price 1.09 per 100ml
- king_store: שמן קנולה מילומור 1 ל', shelf 10.9, unit price 1.09 per 100ml
- ramilevy: שמן קנולה אורגני בכב, shelf 27.9, unit price 0.03 per 100ml
- ramilevy: תרסיס שמן קנולה עץ ה, shelf 15.9, unit price 0.0649 per 100ml
- ramilevy: תרסיס שמן קנולה עץ ה, shelf 15.9, unit price 0.0649 per 100ml
- osherad: תרסיס שמן קנולה שקדי, shelf 9.9, unit price 0.05 per 100ml
- osherad: תרסיס שמן קנולה שקדי, shelf 13.9, unit price 0.0504 per 100ml
- osherad: תרסיס שמן קנולה שקדי, shelf 14.9, unit price 0.0537 per 100ml
- yohananof: שמן קנולה 1 ליטר  יו, shelf 8.9, unit price 0.75 per 100ml
- yohananof: שמן קנולה 1 ליטר  יו, shelf 8.9, unit price 0.75 per 100ml
- yohananof: שמן קנולה 1 ליטר  יו, shelf 8.9, unit price 0.75 per 100ml
- tivtaam: שמן קנולה תפארת מזוכך וילי פוד 1 ליטר, shelf 9.9, unit price 0.99 per 100ml
- tivtaam: שמן קנולה תפארת מזוכך וילי פוד 1 ליטר, shelf 9.9, unit price 0.99 per 100ml
- tivtaam: שמן קנולה 1 ליטר, shelf 10.9, unit price 1.09 per 100ml

Items behind `bamba` (up to 3 per chain, cheapest unit price first):
- king_store: במבה פרו 80 ג אסם, shelf 6.3, unit price 6.2044 per 100g
- king_store: במבה פרו 80 ג אסם, shelf 6.3, unit price 6.2044 per 100g
- ramilevy: בוטני חטיף בוטנים 80, shelf 3, unit price 0.0267 per 100g
- ramilevy: בוטני חטיף בוטנים 80, shelf 3, unit price 0.0267 per 100g
- ramilevy: בוטני חטיף בוטנים 80, shelf 3, unit price 0.0267 per 100g
- osherad: במבה 80 גרם, shelf 3.9, unit price 3.7462 per 100g
- osherad: במבה 80 גרם, shelf 3.9, unit price 3.7462 per 100g
- osherad: במבה 80 גרם, shelf 3.9, unit price 3.7462 per 100g
- yohananof: פופקו במבה 80 גרם, shelf 4.5, unit price 4.1703 per 100g
- yohananof: פופקו במבה 80 גרם, shelf 4.5, unit price 4.1703 per 100g
- yohananof: במבה קלאסי 80 ג, shelf 4.9, unit price 4.5871 per 100g
- tivtaam: במבה 80 גרם, shelf 4.9, unit price 5.7964 per 100g
- tivtaam: במבה 80 גרם, shelf 4.9, unit price 5.7964 per 100g
- tivtaam: במבה 80 גרם, shelf 4.9, unit price 5.7964 per 100g

Items behind `chocolate-milk` (up to 3 per chain, cheapest unit price first):
- king_store: שוקו בקבוק 1 ל' יוטבתה, shelf 13.2, unit price 1.32 per 100ml
- king_store: שוקו בקבוק 1 ל' יוטבתה, shelf 13.2, unit price 1.32 per 100ml
- ramilevy: משקה שוקו 1ליטר, shelf 10.8, unit price 0.01 per 100ml
- ramilevy: משקה שוקו 1ליטר, shelf 10.8, unit price 0.01 per 100ml
- ramilevy: שוקו פקק ספורט יטבתה, shelf 4.9, unit price 0.02 per 100ml
- osherad: שוקו שקית יטבתה 225, shelf 2.5, unit price 0.01 per 100ml
- osherad: שוקו שקית יטבתה 225, shelf 2.5, unit price 0.01 per 100ml
- osherad: שוקו שקית יטבתה 225, shelf 2.5, unit price 0.01 per 100ml
- yohananof: שוקו 1 ליטר יטבתה, shelf 12.3, unit price 0.8 per 100ml
- yohananof: שוקו 1 ליטר יטבתה, shelf 10.9, unit price 0.8 per 100ml
- yohananof: אלפרו סויה שוקו 1 לי, shelf 15.9, unit price 1 per 100ml
- tivtaam: שוקו מקופלת בקבוק יטבתה 1 ליטר, shelf 12.3, unit price 1.23 per 100ml
- tivtaam: שוקו מקופלת בקבוק יטבתה 1 ליטר, shelf 12.3, unit price 1.23 per 100ml
- tivtaam: שוקו מועשר טרה 1 ליטר, shelf 15.5, unit price 1.245 per 100ml

Items behind `bread-standard` (up to 3 per chain, cheapest unit price first):
- ramilevy: לחם אחיד פרוס ודש בר, shelf 7.7, unit price 0.01 per 100g
- ramilevy: לחם אחיד פרוס ברמן, shelf 8.2, unit price 0.01 per 100g
- ramilevy: לחם אחיד אנג'ל 750 ג, shelf 7.36, unit price 0.01 per 100g
- osherad: לחם אחיד פרוס דוידוב, shelf 5.9, unit price 0.79 per 100g
- osherad: לחם אחיד פרוס דוידוב, shelf 6.7, unit price 0.89 per 100g
- osherad: לחם אחיד פרוס דוידוב, shelf 6.7, unit price 0.89 per 100g
- yohananof: לחם אחיד כהה 750 גרם, shelf 4.9, unit price 0.65 per 100g
- yohananof: לחם אחיד כהה 750 גרם, shelf 4.9, unit price 0.65 per 100g
- yohananof: לחם אחיד כהה 750 גרם, shelf 4.9, unit price 0.65 per 100g
- tivtaam: לחם אחיד פרוס, shelf 8.38, unit price 1.12 per 100g
- tivtaam: לחם אחיד פרוס, shelf 8.38, unit price 1.12 per 100g
- tivtaam: לחם אחיד פרוס, shelf 8.38, unit price 1.12 per 100g

Items behind `tuna-in-oil` (up to 3 per chain, cheapest unit price first):
- ramilevy: ויליגר טונה בשמן 140, shelf 5, unit price 0.04 per 100g
- ramilevy: ויליגר טונה בשמן 140, shelf 5.8, unit price 0.04 per 100g
- ramilevy: טונה מהדרין בשמן צמח, shelf 25.8, unit price 0.05 per 100g
- osherad: טונה בשמן צמחי פילטו, shelf 21.9, unit price 3.42 per 100g
- osherad: טונה בשמן צמחי פילטו, shelf 21.9, unit price 3.42 per 100g
- osherad: טונה בשמן סטארקיסט 4, shelf 24.9, unit price 3.4369 per 100g
- yohananof: נתחי טונה בהירה בשמן, shelf 19.9, unit price 2.7349 per 100g
- yohananof: נתחי טונה בהירה בשמן, shelf 19.9, unit price 2.7349 per 100g
- yohananof: טונה רביעייה בשמן, shelf 19.9, unit price 3.11 per 100g
- tivtaam: נתחי טונה בשמן צמחי 4*160, shelf 25.5, unit price 3.5898 per 100g
- tivtaam: נתחי טונה בשמן צמחי 4*160, shelf 25.5, unit price 3.5898 per 100g
- tivtaam: נתחי טונה בשמן צמחי 4*160, shelf 25.5, unit price 3.5898 per 100g

### Basket lines that no chain prices: the real items that could have been them

Items whose names mention the product, with the attributes extraction gave them, the mapping they got and the rule judge's own reason (re-run for this report, nothing written). The `hint` columns are a reading aid of this script, not the catalog's rules.

#### `butter`: 36 listed of 162 name hits (0 skipped as not the food itself; chains looked in: king_store, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
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
| yohananof | סוכריות חמאה במילוי | ? / ? | butter | 125 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.51 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; sour-cream-15 (שמנת חמוצה 15%): similarity 0.11 |
| yohananof | סוכריות חמאה 80 גרם | ? / ? | butter | 80 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.50 \| critical mismatch name has 'סוכריות' (a derived product), canonical is 'חמאה' \| critical match product_type=butter ; sour-cream-15 (שמנת חמוצה 15%): similarity 0.11 |
| yohananof | חמאה פרמה 200 גרם | ? / ? | butter | 200 g | butter any_brand 0.77 review | review: butter (חמאה): similarity 0.47 \| critical match product_type=butter \| level any_brand, confidence 0.77 \| vetoed: yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.13 \| critical mismatch product_type butter vs yel |
| yohananof | עוגיות חמאה עם קקאו | ? / ? | - | 140 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.49 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'חמאה' \| critical unknown product_type ; pudding-chocolate-cream (מעדן שוקולד עם קצפת): simila |
| yohananof | פופקורן בטעם חמאה הו | ? / ? | - | 600 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.46 \| critical mismatch the canonical's words come only after 'בטעם' (a flavor, not the product) \| critical unknown product_type ; wafers-chocolate (ופלים בטעם שוקולד): s |
| yohananof | תרסיס שמן בטעם חמאה | ? / ? | - | 148 ml | - | rejected (confidence 0.32 < 0.6): sunflower-oil (שמן חמניות): similarity 0.35 \| critical unknown product_type \| soft differs pack_size 148 vs 1000 ml \| ambiguous with soybean-oil \| level close, confidence 0.32 \| vetoed: flavored-w |
| tivtaam | עוגיות חמאה קריספי - ב. באטרס 200 גר | ? / ? | - | 200 g | - | every candidate vetoed \| vetoed: butter (חמאה): similarity 0.36 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'חמאה' \| critical unknown product_type ; breaded-schnitzel (שניצל עוף מצופה קפוא): similarity  |
| tivtaam | אלוויר חמאה רכה 250 גר | ? / ? | butter | 250 g | butter close 0.79 review | review: butter (חמאה): similarity 0.48 \| critical match product_type=butter \| soft differs pack_size 250 vs 200 g \| level close, confidence 0.78 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.10 \| critical mismatch product |
| tivtaam | אלוויר חמאה רכה מלוחה 250 גר | ? / ? | butter | 250 g | butter close 0.76 review | review: butter (חמאה): similarity 0.45 \| critical match product_type=butter \| soft differs pack_size 250 vs 200 g \| level close, confidence 0.76 \| vetoed: white-cheese-9 (גבינה לבנה 9%): similarity 0.13 \| critical mismatch product |
| tivtaam | אלוויר חמאה נורמנדי מלוחה 200 גרם | ? / ? | butter | 200 g | butter any_brand 0.71 review | review: butter (חמאה): similarity 0.39 \| critical match product_type=butter \| level any_brand, confidence 0.71 \| vetoed: sour-cream-15 (שמנת חמוצה 15%): similarity 0.09 \| critical mismatch product_type butter vs sour_cream \| criti |
| tivtaam | חמאה צרפתית פרזידנט 200 גרם | ? / ? | butter | 200 g | butter any_brand 0.69 review | review: butter (חמאה): similarity 0.36 \| critical match product_type=butter \| level any_brand, confidence 0.69 \| vetoed: safed-cheese-5 (גבינה צפתית 5%): similarity 0.18 \| critical mismatch product_type butter vs safed_cheese \| cr |
| tivtaam | חמאה צרפתית 100 גר פלשארד | ? / ? | butter | 100 g | butter close 0.73 review | review: butter (חמאה): similarity 0.42 \| critical match product_type=butter \| soft differs pack_size 100 vs 200 g \| level close, confidence 0.73 \| vetoed: safed-cheese-5 (גבינה צפתית 5%): similarity 0.19 \| critical mismatch produc |

#### `chocolate-milk`: 60 listed of 2734 name hits (0 skipped as not the food itself; chains looked in: king_store, ramilevy, osherad, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
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
| ramilevy | עוגיות שוקוציפס 500ג | ? / ? | - | 500 g | - | every candidate vetoed \| vetoed: chicken-thigh-boneless-frozen (פרגיות קפואות): similarity 0.18 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'פרגיות קפואות' \| critical unknown product_type, state ; choco |
| ramilevy | שוקולד מריר חלבי 60% | ? / ? | chocolate_bar | -  | chocolate-dark-bar any_brand 1.00 | accept: chocolate-dark-bar (שוקולד מריר): similarity 0.74 \| critical match product_type=chocolate_bar, flavor=dark \| level any_brand, confidence 1.00 \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.57 \| critical mismatch f |
| ramilevy | עוגיות שוקוציפס לבן | ? / ? | - | -  | - | every candidate vetoed \| vetoed: flour-white (קמח לבן): similarity 0.34 \| critical mismatch name has 'עוגיות' (a derived product), canonical is 'קמח לבן' \| critical unknown product_type ; sugar-white (סוכר לבן): similarity 0.32 \|  |
| ramilevy | שלישיה שוקולד מריר 5 | ? / ? | chocolate_bar | -  | chocolate-dark-bar any_brand 1.00 | accept: chocolate-dark-bar (שוקולד מריר): similarity 0.75 \| critical match product_type=chocolate_bar, flavor=dark \| level any_brand, confidence 1.00 \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.45 \| critical mismatch f |
| ramilevy | טבלת שוקולד חלבון עם | ? / ? | chocolate_bar | -  | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.57 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.39 \| criti |
| ramilevy | שוקולד מריר 70% 100ג | ? / ? | chocolate_bar | 100 g | chocolate-dark-bar any_brand 0.98 | accept: chocolate-dark-bar (שוקולד מריר): similarity 0.73 \| critical match product_type=chocolate_bar, flavor=dark \| level any_brand, confidence 0.98 \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.41 \| critical mismatch f |
| osherad | שוקולד בלונדי חלק 10 | ? / ? | chocolate_bar | 100 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.52 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.47 \| criti |
| osherad | חטיפי גלידה שוקולידה | ? / ? | ice_cream | 700 g | - | every candidate vetoed \| vetoed: broccoli-frozen (ברוקולי קפוא): similarity 0.16 \| critical mismatch product_type ice_cream vs broccoli; name has 'חטיפי' (a derived product), canonical is 'ברוקולי קפוא' \| critical unknown state ;  |
| osherad | שוקולד פרה פצפוצי או | ? / ? | chocolate_bar | 100 g | - | every candidate vetoed \| vetoed: chocolate-milk-bar (שוקולד חלב): similarity 0.45 \| critical mismatch flavor chocolate vs milk \| critical match product_type=chocolate_bar ; chocolate-dark-bar (שוקולד מריר): similarity 0.42 \| criti |
| osherad | שוקולד פרה חלב סוכרי | ? / ? | chocolate_bar | 90 g | chocolate-milk-bar close 0.96 | accept: chocolate-milk-bar (שוקולד חלב): similarity 0.70 \| critical match product_type=chocolate_bar, flavor=milk \| soft differs pack_size 90 vs 100 g \| level close, confidence 0.96 \| vetoed: chocolate-dark-bar (שוקולד מריר): simi |
| osherad | מעדן הגולן שוקולד 12 | ? / ? | dairy_dessert | -  | dessert-chocolate any_brand 0.94 | accept: dessert-chocolate (מעדן חלב שוקולד): similarity 0.67 \| critical match product_type=dairy_dessert, flavor=chocolate \| level any_brand, confidence 0.94 \| vetoed: pudding-chocolate-cream (מעדן שוקולד עם קצפת): similarity 0.58 |
| osherad | מעדן הגולן שוקולד מר | ? / ? | dairy_dessert | -  | dessert-chocolate any_brand 0.94 | accept: dessert-chocolate (מעדן חלב שוקולד): similarity 0.68 \| critical match product_type=dairy_dessert, flavor=chocolate \| level any_brand, confidence 0.94 \| vetoed: pudding-chocolate-cream (מעדן שוקולד עם קצפת): similarity 0.59 |

#### `cottage-5`: 6 listed of 6 name hits (0 skipped as not the food itself; chains looked in: king_store)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| king_store | קוטג' 5% שומן 250 ג' טרה | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.87 review | review: cottage-5 (קוטג' 5%): similarity 0.59 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.87 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.39 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' 5% שומן 250 ג' שטראוס | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.84 review | review: cottage-5 (קוטג' 5%): similarity 0.55 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.84 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.37 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' בקטנה % 5 100 ג' תנובה | ? / ? | cottage_cheese | 100 g | - | rejected (confidence 0.51 < 0.6): cottage-5 (קוטג' 5%): similarity 0.36 \| critical match product_type=cottage_cheese \| critical unknown fat_pct \| soft differs pack_size 100 vs 250 g \| ambiguous with cottage-3 \| level close, confid |
| king_store | קוטג תנובה גביע 250 גר5% | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.70 review | review: cottage-5 (קוטג' 5%): similarity 0.37 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.70 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.33 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' 5% 250 ג' תנובה | ? / ? | cottage_cheese | 250 g | cottage-5 any_brand 0.89 review | review: cottage-5 (קוטג' 5%): similarity 0.61 \| critical match product_type=cottage_cheese, fat_pct=5 \| level any_brand, confidence 0.89 \| vetoed: cottage-3 (קוטג' 3%): similarity 0.39 \| critical mismatch fat_pct 5 vs 3 \| critical |
| king_store | קוטג' 9% שומן 250 ג' תנובה | ? / ? | cottage_cheese | 250 g | - | every candidate vetoed \| vetoed: cottage-5 (קוטג' 5%): similarity 0.38 \| critical mismatch fat_pct 9 vs 5 \| critical match product_type=cottage_cheese ; cottage-3 (קוטג' 3%): similarity 0.38 \| critical mismatch fat_pct 9 vs 3 \| cr |

#### `eggs-l`: 137 listed of 246 name hits (106 skipped as not the food itself; chains looked in: king_store, osherad, yohananof, tivtaam)

Name hint of the size against what the item got (served = no review flag):

| size words in the name | result | items |
|---|---|---|
| ? | review | 12 |
| ? | unmapped | 74 |
| L | eggs-free-range-l any_brand | 1 |
| L | eggs-l close | 1 |
| L | review | 17 |
| L | unmapped | 4 |
| M | review | 20 |
| M | unmapped | 3 |
| XL | review | 5 |

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
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

#### `hummus-plain`: 60 listed of 382 name hits (0 skipped as not the food itself; chains looked in: king_store, ramilevy, osherad, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
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
| ramilevy | חומוס מסבחה חריף 250 | ? / ? | hummus_salad | -  | - | every candidate vetoed \| vetoed: hummus-plain (חומוס (סלט)): similarity 0.40 \| critical mismatch flavor spicy vs plain \| critical match product_type=hummus_salad ; matbucha (מטבוחה): similarity 0.15 \| critical mismatch product_typ |
| ramilevy | חומוס גדול 500ג רמי | ? / ? | hummus_salad | 500 g | - | rejected (confidence 0.56 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.43 \| critical match product_type=hummus_salad \| critical unknown flavor \| soft differs pack_size 500 vs 400 g \| level close, confidence 0.56 \| vetoed: turk |
| ramilevy | חומוס ענק 500ג רמי ל | ? / ? | hummus_salad | 500 g | - | rejected (confidence 0.54 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.40 \| critical match product_type=hummus_salad \| critical unknown flavor \| soft differs pack_size 500 vs 400 g \| level close, confidence 0.54 \| vetoed: sala |
| ramilevy | חומוס עם מטבוחה חריפ | ? / ? | matbucha | -  | matbucha any_brand 0.88 review | review: matbucha (מטבוחה): similarity 0.60 \| critical match product_type=matbucha \| level any_brand, confidence 0.88 \| vetoed: hummus-plain (חומוס (סלט)): similarity 0.46 \| critical mismatch product_type matbucha vs hummus_salad \| |
| ramilevy | שימורי גרגירי חומוס | ? / ? | chickpeas | -  | chickpeas-canned any_brand 0.93 | accept: chickpeas-canned (גרגרי חומוס בשימורים): similarity 0.67 \| critical match product_type=chickpeas, state=canned \| level any_brand, confidence 0.93 \| vetoed: mushrooms-canned (פטריות בשימורים): similarity 0.27 \| critical mis |
| ramilevy | חומוס אסלי מסבחה פיק | ? / ? | hummus_salad | -  | - | rejected (confidence 0.53 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.39 \| critical match product_type=hummus_salad \| critical unknown flavor \| level any_brand, confidence 0.53 \| vetoed: matbucha (מטבוחה): similarity 0.13 \| c |
| osherad | חומוס גרגירים אינדיר | ? / ? | - | -  | - | rejected (confidence 0.43 < 0.6): chickpeas-canned (גרגרי חומוס בשימורים): similarity 0.49 \| critical unknown product_type, state \| ambiguous with chickpeas-dry \| level any_brand, confidence 0.43 |
| osherad | חומוס ענק יכין 550 ג | ? / ? | hummus_salad | 550 g | - | rejected (confidence 0.54 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.40 \| critical match product_type=hummus_salad \| critical unknown flavor \| soft differs pack_size 550 vs 400 g \| level close, confidence 0.54 \| vetoed: matb |
| osherad | חומוס ענק סלקטד 900ג | ? / ? | hummus_salad | 900 g | hummus-plain close 0.61 review | review: hummus-plain (חומוס (סלט)): similarity 0.49 \| critical match product_type=hummus_salad \| critical unknown flavor \| soft differs pack_size 900 vs 400 g \| level close, confidence 0.61 \| vetoed: tahini-salad (סלט טחינה): simi |
| osherad | חומוס עשיר ב50% טחינ | ? / ? | hummus_salad | 400 g | - | rejected (confidence 0.55 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.42 \| critical match product_type=hummus_salad \| critical unknown flavor \| level any_brand, confidence 0.55 \| vetoed: tahini-salad (סלט טחינה): similarity 0 |
| osherad | חומוס גלילי אחלה 600 | ? / ? | hummus_salad | 600 g | - | rejected (confidence 0.55 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.41 \| critical match product_type=hummus_salad \| critical unknown flavor \| soft differs pack_size 600 vs 400 g \| level close, confidence 0.55 \| vetoed: eggp |
| osherad | חומוס ישראלי  אחלה 6 | ? / ? | hummus_salad | 600 g | - | rejected (confidence 0.56 < 0.6): hummus-plain (חומוס (סלט)): similarity 0.42 \| critical match product_type=hummus_salad \| critical unknown flavor \| soft differs pack_size 600 vs 400 g \| level close, confidence 0.56 \| vetoed: matb |

#### `milk-fresh-3`: 24 listed of 990 name hits (0 skipped as not the food itself; chains looked in: osherad, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
| osherad | שוקולד פרה חלב סוכרי | ? / ? | chocolate_bar | 90 g | chocolate-milk-bar close 0.96 | accept: chocolate-milk-bar (שוקולד חלב): similarity 0.70 \| critical match product_type=chocolate_bar, flavor=milk \| soft differs pack_size 90 vs 100 g \| level close, confidence 0.96 \| vetoed: chocolate-dark-bar (שוקולד מריר): simi |
| osherad | מעדן חלב מעושר בחלבו | ? / ? | dairy_dessert | 150 g | dessert-vanilla close 0.70 review | review: dessert-vanilla (מעדן חלב וניל): similarity 0.60 \| critical match product_type=dairy_dessert \| critical unknown flavor \| soft differs pack_size 150 vs 125 g \| ambiguous with dessert-chocolate \| level close, confidence 0.70 |
| osherad | מעדן חלב עם שוקולד פ | ? / ? | dairy_dessert | 150 g | dessert-chocolate close 1.00 | accept: dessert-chocolate (מעדן חלב שוקולד): similarity 0.86 \| critical match product_type=dairy_dessert, flavor=chocolate \| soft differs pack_size 150 vs 125 g \| level close, confidence 1.00 \| vetoed: pudding-chocolate-cream (מעד |
| osherad | חלב 3% תנובה 1.5 ליט | ? / ? | milk | 1500 ml | milk-fresh-3 close 0.66 review | review: milk-fresh-3 (חלב טרי 3%): similarity 0.47 \| critical match product_type=milk, fat_pct=3 \| critical unknown state \| soft differs pack_size 1500 vs 1000 ml \| level close, confidence 0.66 \| vetoed: milk-long-life-3 (חלב עמיד |
| osherad | חלב נטול לקטוז 2% טר | ? / ? | milk_lactose_free | -  | milk-lactose-free-2 any_brand 0.96 | accept: milk-lactose-free-2 (חלב ללא לקטוז 2%): similarity 0.70 \| critical match product_type=milk_lactose_free, fat_pct=2 \| level any_brand, confidence 0.96 \| vetoed: milk-fresh-3 (חלב טרי 3%): similarity 0.35 \| critical mismatch |
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

#### `pasta-spaghetti`: 50 listed of 102 name hits (0 skipped as not the food itself; chains looked in: king_store, ramilevy, osherad, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
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
| osherad | פסטה ספגטי דורומי 90 | ? / ? | pasta_spaghetti | 900 g | pasta-spaghetti close 0.86 review | review: pasta-spaghetti (ספגטי): similarity 0.57 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 900 vs 500 g \| level close, confidence 0.86 \| vetoed: pasta-penne (פסטה פנה): similarity 0.41 \| critical misma |
| osherad | ספגטי ברילה מס 5 500 | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.82 review | review: pasta-spaghetti (ספגטי): similarity 0.53 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.82 \| vetoed: granola (גרנולה): similarity 0.10 \| critical mismatch product_type pasta_spaghetti vs gran |
| osherad | ספגטי ל.גלוטן ברילה | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.85 review | review: pasta-spaghetti (ספגטי): similarity 0.56 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.85 \| vetoed: granola (גרנולה): similarity 0.13 \| critical mismatch product_type pasta_spaghetti vs gran |
| osherad | ספגטי מחיטה מלאה טעמ | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.56 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.85 \| vetoed: flour-whole-wheat (קמח מלא): similarity 0.18 \| critical mismatch product_type pasta_spaghe |
| osherad | ספגטי ללא גלוטן פסטה | ? / ? | pasta_spaghetti | 400 g | pasta-spaghetti close 0.84 review | review: pasta-spaghetti (ספגטי): similarity 0.55 \| critical match product_type=pasta_spaghetti \| soft differs diet variant 'ללא גלוטן'; pack_size 400 vs 500 g \| level close, confidence 0.84 \| vetoed: pasta-penne (פסטה פנה): simila |
| osherad | פסטה ספגטי מונו פוד | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.83 review | review: pasta-spaghetti (ספגטי): similarity 0.54 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.83 \| vetoed: pasta-penne (פסטה פנה): similarity 0.47 \| critical mismatch product_type pasta_spaghetti v |
| osherad | ספגטי פרפקטו ללא גלו | ? / ? | pasta_spaghetti | 400 g | pasta-spaghetti close 0.81 review | review: pasta-spaghetti (ספגטי): similarity 0.52 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 400 vs 500 g \| level close, confidence 0.81 \| vetoed: pasta-fusilli (פסטה פוזילי): similarity 0.11 \| critical  |
| osherad | פסטה ספגטי אורז חום | ? / ? | pasta_spaghetti | 454 g | pasta-spaghetti close 0.88 review | review: pasta-spaghetti (ספגטי): similarity 0.60 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 454 vs 500 g \| level close, confidence 0.88 \| vetoed: pasta-penne (פסטה פנה): similarity 0.42 \| critical misma |
| yohananof | פרפקטו ספגטי 3 500 ג | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.82 review | review: pasta-spaghetti (ספגטי): similarity 0.52 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.82 \| vetoed: pasta-fusilli (פסטה פוזילי): similarity 0.11 \| critical mismatch product_type pasta_spaghe |
| yohananof | ספגטי אסם 500 גרם | ? / ? | pasta_spaghetti | 500 g | pasta-spaghetti any_brand 0.85 review | review: pasta-spaghetti (ספגטי): similarity 0.56 \| critical match product_type=pasta_spaghetti \| level any_brand, confidence 0.85 \| vetoed: turmeric (כורכום): similarity 0.16 \| critical mismatch product_type pasta_spaghetti vs tur |
| yohananof | מנה חמה ספגטי בולונז | ? / ? | pasta_spaghetti | 55 g | pasta-spaghetti close 0.86 review | review: pasta-spaghetti (ספגטי): similarity 0.58 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 55 vs 500 g \| level close, confidence 0.86 \| vetoed: mayonnaise (מיונז): similarity 0.19 \| critical mismatch p |
| yohananof | סקיני פסטה ספגטי | ? / ? | pasta_spaghetti | 270 g | pasta-spaghetti close 0.92 | accept: pasta-spaghetti (ספגטי): similarity 0.65 \| critical match product_type=pasta_spaghetti \| soft differs pack_size 270 vs 500 g \| level close, confidence 0.92 \| vetoed: pasta-penne (פסטה פנה): similarity 0.45 \| critical misma |

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

#### `yellow-cheese-sliced-28`: 48 listed of 286 name hits (0 skipped as not the food itself; chains looked in: king_store, osherad, yohananof, tivtaam)

| chain | name | hint size / pack | product type | pack | mapped | judge |
|---|---|---|---|---|---|---|
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
| osherad | פרוסות גבינת גאודה ע | ? / ? | yellow_cheese | 150 g | - | rejected (confidence 0.46 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.31 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| soft differs pack_size 150 vs 200 g \| ambiguous with yellow- |
| osherad | פרוסות גאודה גד 200 | ? / ? | yellow_cheese | 200 g | - | rejected (confidence 0.42 < 0.6): yellow-cheese-sliced-28 (גבינה צהובה פרוסה 28%): similarity 0.20 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| ambiguous with yellow-cheese-sliced-9 \| level any_brand, c |
| osherad | מארז קסטה טעמקור 8 י | ? / ? | - | 416 g | - | rejected (confidence 0.24 < 0.6): couscous (קוסקוס): similarity 0.18 \| critical unknown product_type \| soft differs pack_size 416 vs 500 g \| ambiguous with cornflakes \| level close, confidence 0.24 |
| osherad | טבעות גאודה בציפוי פ | ? / ? | yellow_cheese | -  | - | rejected (confidence 0.42 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.08 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| level any_brand, confidence 0.42 \| vetoed: cream-cheese-30-p |
| osherad | גבינה בסגנון גאודה י | ? / ? | yellow_cheese | 160 g | - | rejected (confidence 0.53 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.39 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| soft differs pack_size 160 vs 200 g \| ambiguous with yellow- |
| osherad | גבינת גאודה עיזים יע | ? / ? | yellow_cheese | 160 g | - | rejected (confidence 0.42 < 0.6): yellow-cheese-sliced-9 (גבינה צהובה פרוסה 9%): similarity 0.23 \| critical match product_type=yellow_cheese \| critical unknown fat_pct \| soft differs pack_size 160 vs 200 g \| ambiguous with yellow- |
| yohananof | גבינה צהובה קלאסית 2 | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| yohananof | גבינת גאודה 28% | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| yohananof | גבינת גאודה כמון 28% | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| yohananof | *מבצע* גבינת גאודה ב | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| yohananof | גבינת גאודה עשבי תיב | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |
| yohananof | גבינת גאודה הולנדית | ? / ? | yellow_cheese | -  | - | no candidates in block dairy / kg |

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

- **api**: /parse-list took over 2 s (production): {'small (6 lines)': 2114.8, 'weekly (17 lines)': 5988.6, 'large (32 lines)': 11060.3} ms
- **basket index**: chocolate-milk is priced at no chain (candidates in the report)
- **basket index**: hummus-plain is priced at no chain (candidates in the report)
- **basket index**: pasta-spaghetti is priced at no chain (candidates in the report)
- **api**: /parse-list took over 2 s (stress): {'small (6 lines)': 2101.7, 'weekly (17 lines)': 5940.3, 'large (32 lines)': 10903.7} ms

