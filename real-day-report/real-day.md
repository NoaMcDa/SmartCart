## One real day through the pipeline (dry run)

Mode `portal`, commit `e9416aa8fdbe`, runner `GitHub Actions 1000005028` (4 CPUs, Python 3.12.3, Postgres 17.11), 2026-10-21T21:22:20+00:00 to 2026-10-21T21:50:54+00:00 UTC. Measurements on one real day with hand-made baskets; the prices are real, the baskets and locations are not a sample of anything. **Not publishable.**

### Stages

| stage | seconds | result |
|---|---|---|
| download: portal probe (one Stores and one PriceFull per chain) | 617.29 | ok |
| migrate | 0.98 | 25 applied |
| ingest: Stores files (Scheduler, adapters, gates, loader, store coordinates) | 0.4 | 7 files |
| download: PriceFull and PromoFull of the stores nearest to city centres | 405.42 | 46 files, anchors: Haifa centre, Jerusalem centre, Petah Tikva |
| ingest: PriceFull and PromoFull files (Scheduler, adapters, gates, loader) | 65.09 | 53 files |
| catalog: seed | 0.79 | ok |
| catalog: normalize | 6.13 | ok |
| catalog: extract (rule) | 78.64 | ok |
| catalog: embed (hash) | 270.81 | ok |
| catalog: judge (rule) | 172.34 | ok |
| precompute effective prices (production semantics: reviewed mappings only) | 0.9 | 6666 rows |
| API: parse-list, compare, optimize (production) | 42.64 | 21 basket runs at 3 locations |
| diagnostic: the vector query behind /parse-list and /search | 8.55 | [3.3, 0.7, 0.7] ms per query |
| basket index dry run (production semantics) | 0.31 | status draft |
| stress: mark the machine suggestions accepted (performance only) | 0.29 | 15168 mappings |
| precompute effective prices (stress: unreviewed mappings included) | 1.77 | 10970 rows |
| API: parse-list, compare, optimize (stress) | 41.23 | 21 basket runs at 3 locations |
| basket index dry run (stress) | 0.32 | status draft |

### Portals (the portal probe's own reachability and downloads)

| chain | reachable | login | Stores download | PriceFull download |
|---|---|---|---|---|
| hazihinam | BLOCKED? (403) | n/a | no: no file downloaded | no: no file downloaded |
| king_store | BLOCKED? (403) | n/a | Stores7290058108879-000-20261021-040448.gz | PriceFull7290058108879-000-340-20261021-040448.gz |
| machsanei_hashuk | UNREACHABLE (0) | n/a | no: no file downloaded | no: no file downloaded |
| mega | OK (200) | n/a | Stores7290055700007-000-20261022-000100.xml | PriceFull7290055700007-001-416-20261022-000012.gz |
| osherad | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290103152017-000-20261019-080501.xml | PriceFull7290103152017-001-001-20261021-080011.gz |
| ramilevy | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290058140886-000-20261019-050500.xml | PriceFull7290058140886-001-001-20261021-001002.gz |
| shufersal | OK (200) | n/a | Stores7290027600007-000-20261021-020.gz | PriceFull7290027600007-001-036-20261021-043100.gz |
| tivtaam | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290873255550-000-20261019-050501.xml | PriceFull7290873255550-000-002-20261021-004004.gz |
| victory | UNREACHABLE (0) | n/a | no: no file downloaded | no: no file downloaded |
| yohananof | UNREACHABLE (0) | ok (certificate not verified, as upstrea | Stores7290803800003-000-20261019-010000.xml | PriceFull7290803800003-000-001-20261021-004031.gz |

### Files, gates and rows per chain

| chain | kind | file | published (Israel) | age h | schema | gate result | rows | seconds |
|---|---|---|---|---|---|---|---|---|
| king_store | stores | `Stores7290058108879-000-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 20.5 | v1 | loaded | 48 | 0.05 |
| mega | stores | `Stores7290055700007-000-20261022-000100.xml` | 2026-10-22T00:01+03:00 | 0.5 | v1 | loaded | 147 | 0.06 |
| osherad | stores | `Stores7290103152017-000-20261019-080501.xml` | 2026-10-19T08:05+03:00 | 64.5 (stale on the real clock) | v1 | loaded | 24 | 0.03 |
| ramilevy | stores | `Stores7290058140886-000-20261019-050500.xml` | 2026-10-19T05:05+03:00 | 67.5 (stale on the real clock) | v1 | loaded | 99 | 0.04 |
| shufersal | stores | `Stores7290027600007-000-20261021-020.gz` | 2026-10-21T02:00+03:00 | 22.5 | v1 | loaded | 417 | 0.13 |
| tivtaam | stores | `Stores7290873255550-000-20261019-050501.xml` | 2026-10-19T05:05+03:00 | 67.5 (stale on the real clock) | v1 | loaded | 54 | 0.03 |
| yohananof | stores | `Stores7290803800003-000-20261019-010000.xml` | 2026-10-19T01:00+03:00 | 71.5 (stale on the real clock) | v1 | loaded | 51 | 0.02 |
| king_store | price_full | `PriceFull7290058108879-000-340-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 20.6 | v1 | loaded | 2,336 | 0.3 |
| mega | price_full | `PriceFull7290055700007-001-416-20261022-000012.gz` | 2026-10-22T00:00+03:00 | 0.7 | v1 | loaded | 11,082 | 1.44 |
| osherad | price_full | `PriceFull7290103152017-001-001-20261021-080011.gz` | 2026-10-21T08:00+03:00 | 16.7 | v1 | loaded | 6,508 | 0.89 |
| ramilevy | price_full | `PriceFull7290058140886-001-001-20261021-001002.gz` | 2026-10-21T00:10+03:00 | 24.5 | v1 | loaded | 12,976 | 1.6 |
| shufersal | price_full | `PriceFull7290027600007-001-036-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.1 | v1 | loaded | 5,808 | 0.69 |
| tivtaam | price_full | `PriceFull7290873255550-000-002-20261021-004004.gz` | 2026-10-21T00:40+03:00 | 24.0 | v1 | loaded | 21,598 | 2.81 |
| yohananof | price_full | `PriceFull7290803800003-000-001-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 24.0 | v1 | loaded | 10,732 | 1.34 |
| king_store | price_full | `PriceFull7290058108879-000-014-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 20.6 | v1 | loaded | 4,833 | 0.57 |
| king_store | price_full | `PriceFull7290058108879-000-200-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 20.6 | v1 | loaded | 3,628 | 0.43 |
| king_store | promo_full | `PromoFull7290058108879-000-014-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 20.6 | v1 | loaded | 430 | 0.09 |
| king_store | promo_full | `PromoFull7290058108879-000-200-20261021-040448.gz` | 2026-10-21T04:04+03:00 | 20.6 | v1 | loaded | 313 | 0.06 |
| osherad | price_full | `PriceFull7290103152017-001-026-20261021-140501.gz` | 2026-10-21T14:05+03:00 | 10.6 | v1 | loaded | 6,836 | 1.07 |
| osherad | price_full | `PriceFull7290103152017-001-030-20261021-140501.gz` | 2026-10-21T14:05+03:00 | 10.6 | v1 | loaded | 6,465 | 0.82 |
| osherad | price_full | `PriceFull7290103152017-001-010-20261021-140502.gz` | 2026-10-21T14:05+03:00 | 10.6 | v1 | loaded | 6,699 | 0.84 |
| osherad | price_full | `PriceFull7290103152017-001-028-20261021-140502.gz` | 2026-10-21T14:05+03:00 | 10.6 | v1 | loaded | 6,246 | 0.88 |
| osherad | promo_full | `PromoFull7290103152017-001-028-20261021-140522.gz` | 2026-10-21T14:05+03:00 | 10.6 | v1 | loaded | 716 | 0.15 |
| osherad | promo_full | `PromoFull7290103152017-001-026-20261021-140527.gz` | 2026-10-21T14:05+03:00 | 10.6 | v1 | loaded | 734 | 0.16 |
| osherad | promo_full | `PromoFull7290103152017-001-030-20261021-140545.gz` | 2026-10-21T14:05+03:00 | 10.6 | v1 | loaded | 750 | 0.17 |
| osherad | promo_full | `PromoFull7290103152017-001-010-20261021-140558.gz` | 2026-10-21T14:05+03:00 | 10.6 | v1 | loaded | 705 | 0.15 |
| ramilevy | price_full | `PriceFull7290058140886-001-703-20261022-001001.gz` | 2026-10-22T00:10+03:00 | 0.5 | v1 | loaded | 4,950 | 0.67 |
| ramilevy | price_full | `PriceFull7290058140886-001-724-20261022-001007.gz` | 2026-10-22T00:10+03:00 | 0.5 | v1 | loaded | 5,147 | 0.73 |
| ramilevy | price_full | `PriceFull7290058140886-001-062-20261022-001010.gz` | 2026-10-22T00:10+03:00 | 0.5 | v1 | loaded | 14,119 | 1.84 |
| ramilevy | price_full | `PriceFull7290058140886-001-048-20261022-001016.gz` | 2026-10-22T00:10+03:00 | 0.5 | v1 | loaded | 14,443 | 1.83 |
| ramilevy | price_full | `PriceFull7290058140886-001-057-20261022-001019.gz` | 2026-10-22T00:10+03:00 | 0.5 | v1 | loaded | 13,924 | 1.77 |
| ramilevy | promo_full | `PromoFull7290058140886-001-703-20261022-001044.gz` | 2026-10-22T00:10+03:00 | 0.5 | v1 | loaded | 1,109 | 0.23 |
| ramilevy | promo_full | `PromoFull7290058140886-001-724-20261022-001045.gz` | 2026-10-22T00:10+03:00 | 0.5 | v1 | loaded | 1,060 | 0.24 |
| ramilevy | promo_full | `PromoFull7290058140886-001-048-20261022-001113.gz` | 2026-10-22T00:11+03:00 | 0.5 | v1 | loaded | 2,529 | 0.56 |
| ramilevy | promo_full | `PromoFull7290058140886-001-057-20261022-001122.gz` | 2026-10-22T00:11+03:00 | 0.5 | v1 | loaded | 2,539 | 0.63 |
| ramilevy | promo_full | `PromoFull7290058140886-001-062-20261022-001134.gz` | 2026-10-22T00:11+03:00 | 0.5 | v1 | loaded | 2,534 | 0.62 |
| shufersal | price_full | `PriceFull7290027600007-001-002-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.1 | v1 | loaded | 7,488 | 0.93 |
| shufersal | price_full | `PriceFull7290027600007-001-302-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.1 | v1 | loaded | 6,534 | 0.81 |
| shufersal | price_full | `PriceFull7290027600007-006-300-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.1 | v1 | loaded | 7,723 | 0.99 |
| shufersal | price_full | `PriceFull7290027600007-007-285-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.2 | v1 | loaded | 3,328 | 0.42 |
| shufersal | price_full | `PriceFull7290027600007-007-353-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.2 | v1 | loaded | 2,271 | 0.28 |
| shufersal | price_full | `PriceFull7290027600007-018-753-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.2 | v1 | loaded | 3,547 | 0.53 |
| shufersal | promo_full | `PromoFull7290027600007-001-002-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.2 | v1 | loaded | 1,379 | 0.59 |
| shufersal | promo_full | `PromoFull7290027600007-001-302-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.2 | v1 | loaded | 1,281 | 0.57 |
| shufersal | promo_full | `PromoFull7290027600007-006-300-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.2 | v1 | loaded | 1,008 | 0.5 |
| shufersal | promo_full | `PromoFull7290027600007-007-285-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.2 | v1 | loaded | 743 | 0.33 |
| shufersal | promo_full | `PromoFull7290027600007-007-353-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.2 | v1 | loaded | 616 | 0.24 |
| shufersal | promo_full | `PromoFull7290027600007-018-753-20261021-043100.gz` | 2026-10-21T04:31+03:00 | 20.2 | v1 | loaded | 418 | 0.22 |
| tivtaam | price_full | `PriceFull7290873255550-000-012-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 9.1 | v1 | loaded | 17,832 | 2.39 |
| tivtaam | price_full | `PriceFull7290873255550-000-085-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 9.1 | v1 | loaded | 7,171 | 0.91 |
| tivtaam | price_full | `PriceFull7290873255550-000-087-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 9.1 | v1 | loaded | 6,069 | 0.77 |
| tivtaam | price_full | `PriceFull7290873255550-000-092-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 9.1 | v1 | loaded | 5,851 | 0.82 |
| tivtaam | promo_full | `PromoFull7290873255550-000-012-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 9.1 | v1 | loaded | 2,040 | 1.18 |
| tivtaam | promo_full | `PromoFull7290873255550-000-085-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 9.1 | v1 | loaded | 1,282 | 1.3 |
| tivtaam | promo_full | `PromoFull7290873255550-000-087-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 9.1 | v1 | loaded | 1,126 | 0.77 |
| tivtaam | promo_full | `PromoFull7290873255550-000-092-20261021-153358.gz` | 2026-10-21T15:33+03:00 | 9.1 | v1 | loaded | 1,060 | 0.59 |
| yohananof | price_full | `PriceFull7290803800003-000-020-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 24.0 | v1 | loaded | 11,887 | 1.46 |
| yohananof | price_full | `PriceFull7290803800003-000-021-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 24.0 | v1 | loaded | 11,197 | 1.41 |
| yohananof | promo_full | `PromoFull7290803800003-000-020-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 24.0 | v1 | loaded | 1,277 | 0.25 |
| yohananof | promo_full | `PromoFull7290803800003-000-021-20261021-004031.gz` | 2026-10-21T00:40+03:00 | 24.0 | v1 | loaded | 1,212 | 0.23 |

PromoFull files: what they hold and how much reached `promo_items`:

| chain | file | promos | with item codes | distinct codes | codes the chain's items know | promo_items linked | active now | club | rewards |
|---|---|---|---|---|---|---|---|---|---|
| king_store | `PromoFull7290058108879-000-014-20261021-040448.gz` | 430 | 0 | 0 | 0 | 0 | 430 | 106 | {'other': 430} |
| king_store | `PromoFull7290058108879-000-200-20261021-040448.gz` | 313 | 0 | 0 | 0 | 0 | 313 | 82 | {'other': 313} |
| osherad | `PromoFull7290103152017-001-028-20261021-140522.gz` | 716 | 0 | 0 | 0 | 0 | 716 | 0 | {'other': 716} |
| osherad | `PromoFull7290103152017-001-026-20261021-140527.gz` | 734 | 0 | 0 | 0 | 0 | 734 | 0 | {'other': 734} |
| osherad | `PromoFull7290103152017-001-030-20261021-140545.gz` | 750 | 0 | 0 | 0 | 0 | 750 | 0 | {'other': 750} |
| osherad | `PromoFull7290103152017-001-010-20261021-140558.gz` | 705 | 0 | 0 | 0 | 0 | 705 | 0 | {'other': 705} |
| ramilevy | `PromoFull7290058140886-001-703-20261022-001044.gz` | 1,109 | 0 | 0 | 0 | 0 | 1,109 | 22 | {'other': 1109} |
| ramilevy | `PromoFull7290058140886-001-724-20261022-001045.gz` | 1,060 | 0 | 0 | 0 | 0 | 1,060 | 24 | {'other': 1060} |
| ramilevy | `PromoFull7290058140886-001-048-20261022-001113.gz` | 2,529 | 0 | 0 | 0 | 0 | 2,529 | 37 | {'other': 2529} |
| ramilevy | `PromoFull7290058140886-001-057-20261022-001122.gz` | 2,539 | 0 | 0 | 0 | 0 | 2,539 | 37 | {'other': 2539} |
| ramilevy | `PromoFull7290058140886-001-062-20261022-001134.gz` | 2,534 | 0 | 0 | 0 | 0 | 2,534 | 37 | {'other': 2534} |
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

Sample codes (promo / item): king_store [] / ['12345', '13006', '13174']; king_store [] / ['12345', '13006', '13174']; osherad [] / ['7290001041017', '7290000066431', '7290003029792']; osherad [] / ['7290001041017', '7290000066431', '7290003029792']; osherad [] / ['7290001041017', '7290000066431', '7290003029792']; osherad [] / ['7290001041017', '7290000066431', '7290003029792']

`file_tracking` after the run: {'loaded': 60}. Alerts raised: 0.

| chain | physical stores | located | online | items | price events | stores with prices | promos | promo items |
|---|---|---|---|---|---|---|---|---|
| king_store | 48 | 28 | - | 6,748 | 10,797 | 3 | 743 | - |
| mega | 145 | 144 | 3 | 11,082 | 11,082 | 1 | - | - |
| osherad | 24 | 24 | - | 8,715 | 32,754 | 5 | 2,905 | - |
| ramilevy | 98 | 96 | 1 | 18,250 | 65,559 | 6 | 9,771 | - |
| shufersal | 416 | 411 | 1 | 13,613 | 36,699 | 7 | 5,445 | - |
| tivtaam | 47 | 47 | 7 | 24,986 | 58,521 | 5 | 5,508 | - |
| yohananof | 50 | 19 | 1 | 13,572 | 33,816 | 3 | 2,489 | - |

Extra downloads (the stores nearest to these city centres, for the optimizer):

- Haifa centre: 6 chains and 39 located stores within 4 km; asked for shufersal 302,353, mega 470,418, king_store 14, ramilevy 57,62, osherad 30, tivtaam 92,12
- Jerusalem centre: 6 chains and 36 located stores within 4 km; asked for shufersal 2,753, mega 457,91, king_store 200, ramilevy 48,703, osherad 26,28, yohananof 20
- Petah Tikva: 6 chains and 36 located stores within 4 km; asked for shufersal 285,300, mega 407,452, ramilevy 725,724, osherad 10, yohananof 21, tivtaam 87,85
- download `mega` price_full: no file matched
- download `mega` promo_full: no file matched

### Matching on the real items

96,966 items; 20,876 mapped to a canonical (any level, including the review queue); 5,708 served (no review flag), onto 210 canonicals.

| level | mappings served | mappings in the review queue |
|---|---|---|
| exact | 0 | 0 |
| any_brand | 3,484 | 6,301 |
| close | 2,224 | 8,867 |

| chain | items | mapped | served |
|---|---|---|---|
| shufersal | 13,613 | 3,269 | 947 |
| mega | 11,082 | 2,339 | 809 |
| king_store | 6,748 | 1,844 | 324 |
| ramilevy | 18,250 | 3,857 | 1,333 |
| osherad | 8,715 | 2,163 | 690 |
| yohananof | 13,572 | 2,621 | 916 |
| tivtaam | 24,986 | 4,783 | 689 |

- seed: 0.79 s
- normalize: 6.13 s
- extract (rule): 78.64 s
- embed (hash): 270.81 s
- judge (rule): 172.34 s

### Precompute (production semantics)

6,666 rows written in 0.597 s of job time (0.88 s wall including start-up); 5,470 items priced at 30 stores (841 stores of 7 chains considered); 0 rows with a promo, 0 club-only. Canonicals with a real price: 209, of them 186 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 2,932 | 193 | 30 |
| close | 3,734 | 209 | 30 |

### Precompute (stress)

10,970 rows written in 1.475 s of job time (1.75 s wall including start-up); 19,817 items priced at 30 stores (841 stores of 7 chains considered); 0 rows with a promo, 0 club-only. Canonicals with a real price: 240, of them 233 at two or more stores (any brand).

| level | rows | canonicals priced | stores |
|---|---|---|---|
| any_brand | 4,985 | 236 | 30 |
| close | 5,985 | 240 | 30 |

### The vector query behind /parse-list and /search

`item_embeddings` holds 96,966 rows (model `hash-ngram-2-3-4-v1`); one `ORDER BY embedding <=> q LIMIT 40` query took [3.3, 0.7, 0.7] ms; with sequential scans disabled 0.6 ms.

```
Limit  (cost=2331.97..2596.34 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2331.97..643210.56 rows=96966 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
--- enable_seqscan = off
Limit  (cost=2331.97..2596.34 rows=40 width=24)
  ->  Index Scan using item_embeddings_hnsw on item_embeddings e  (cost=2331.97..643210.56 rows=96966 width=24)
        Order By: (embedding <=> <query vector>)
        Filter: (model = 'hash-ngram-2-3-4-v1'::text)
```

One `/parse-list` call (6 lines): 3920.0 ms in total, 3912.9 ms inside 37 SQL statements. The statements that cost the most:

| statement (first 110 characters) | calls | total ms | max ms |
|---|---|---|---|
| `WITH qv AS (SELECT %(v)s::vector AS v), direct AS ( SELECT c.id AS canonical_id, 1 - (c.embedding <=> qv.v) AS` | 6 | 3884.0 | 671.8 |
| `WITH q AS (SELECT search_norm(%(q)s) AS t) SELECT c.id, word_similarity(q.t, search_norm(c.display_name_he)) A` | 6 | 15.4 | 5.8 |
| `WITH RECURSIVE up AS ( SELECT t.id AS leaf, t.id, t.parent_id, t.name_he, t.level FROM taxonomy t WHERE t.id =` | 6 | 4.1 | 0.9 |
| `SELECT id, display_name_he, taxonomy_id, base_unit, rank, names_ar[1] FROM canonical_products WHERE id = ANY(%` | 6 | 3.6 | 0.9 |
| `SELECT c.id, c.display_name_he, ts_rank_cd(to_tsvector('simple', search_norm(c.display_name_he)), tq) AS r FRO` | 6 | 3.6 | 1.3 |
| `SELECT set_config('pg_trgm.word_similarity_threshold', %s, true)` | 6 | 1.7 | 0.7 |

`EXPLAIN (ANALYZE, BUFFERS)` of the slowest statement:

```
Limit  (cost=8051.40..8051.42 rows=10 width=16) (actual rows=20 loops=1)
  Buffers: shared hit=776587 read=66727
  CTE qv
    ->  Result  (cost=0.00..0.01 rows=1 width=32) (actual rows=1 loops=1)
  ->  Sort  (cost=8051.39..8051.41 rows=10 width=16) (actual rows=20 loops=1)
        Sort Key: (max(direct.s)) DESC, direct.canonical_id
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=776587 read=66727
        ->  GroupAggregate  (cost=8050.75..8051.22 rows=10 width=16) (actual rows=20 loops=1)
              Group Key: direct.canonical_id
              Buffers: shared hit=776584 read=66727
              ->  Merge Append  (cost=8050.75..8051.07 rows=10 width=16) (actual rows=24 loops=1)
                    Sort Key: direct.canonical_id
                    Buffers: shared hit=776584 read=66727
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
                    ->  GroupAggregate  (cost=8017.46..8017.66 rows=3 width=16) (actual rows=4 loops=1)
                          Group Key: ic.canonical_id
                          Filter: (max((('1'::double precision - (e.embedding <=> qv_1.v)))) >= '0.25'::double precision)
                          Buffers: shared hit=775085 read=66545
                          ->  Sort  (cost=8017.46..8017.48 rows=10 width=16) (actual rows=18 loops=1)
                                Sort Key: ic.canonical_id
                                Sort Method: quicksort  Memory: 25kB
                                Buffers: shared hit=775085 read=66545
                                ->  Nested Loop  (cost=7459.18..8017.29 rows=10 width=16) (actual rows=18 loops=1)
                                      Buffers: shared hit=775085 read=66545
                                      ->  Limit  (cost=7458.89..7459.09 rows=80 width=24) (actual rows=80 loops=1)
                                            Buffers: shared hit=774952 read=66443
                                            ->  Sort  (cost=7458.89..7701.31 rows=96966 width=24) (actual rows=80 loops=1)
                                                  Sort Key: ((e.embedding <=> qv_1.v))
                                                  Sort Method: top-N heapsort  Memory: 33kB
                                                  Buffers: shared hit=774952 read=66443
                                                  ->  Nested Loop  (cost=0.00..3909.00 rows=96966 width=24) (actual rows=96966 loops=1)
                                                        Buffers: shared hit=774952 read=66443
                                                        ->  CTE Scan on qv qv_1  (cost=0.00..0.02 rows=1 width=32) (actual rows=1 loops=1)
                                                        ->  Seq Scan on item_embeddings e  (cost=0.00..2212.07 rows=96966 width=26) (actual rows=96966 loops=1)
                                                              Filter: (model = 'hash-ngram-2-3-4-v1'::text)
                                                              Buffers: shared read=1000
                                      ->  Index Scan using item_canonical_pkey on item_canonical ic  (cost=0.29..6.96 rows=1 width=16) (actual rows=0 loops=80)
                                            Index Cond: (item_id = e.item_id)
                                            Filter: ((NOT human_rejected) AND (NOT needs_review) AND (flex_level = ANY ('{exact,any_brand}'::text[])))
                                            Rows Removed by Filter: 1
                                            Buffers: shared hit=133 read=102
Planning:
  Buffers: shared hit=414 read=63
Planning Time: 1.493 ms
Execution Time: 675.239 ms
```

### /parse-list, /compare and /optimize (production semantics)

Locations: Jerusalem centre (9 priced stores, 5 chains within 5 km); Haifa centre (8 priced stores, 5 chains within 5 km); Petah Tikva (7 priced stores, 5 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 3963 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 11188.7 |
| large (32 lines) | 33 | 33 | 5 | 0 | 21099 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 9 | 0 | 6.3 | 5.7 | 9.3 | 55 | single: רמי לוי עטרות | 5.73 / 5.73 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 9 | 0 | 7.3 | 5.9 | 10.6 | 55 | single: שופרסל שלי ירושלים- אגרון | 0.0 / 0.0 |
| Jerusalem centre | hand: large (32 lines) | 33 | 9 | 0 | 9.2 | 7.5 | 13.3 | 55 | single: רמי לוי עטרות | 86.8 / 86.8 |
| Jerusalem centre | drawn: 5 | 5 | 9 | 5 | 5.2 | 4.8 | 8.6 | 55 | single: שופרסל גוד מרקט רש"י ירושלים | 3.51 / 3.51 |
| Jerusalem centre | drawn: 10 | 10 | 9 | 0 | 6.2 | 5.5 | 9.5 | 55 | single: רמי לוי עטרות | 26.25 / 26.25 |
| Jerusalem centre | drawn: 20 | 20 | 9 | 0 | 7.4 | 6.3 | 10.5 | 55 | single: רמי לוי עטרות | 61.97 / 61.97 |
| Jerusalem centre | drawn: 40 | 40 | 9 | 0 | 11.1 | 8.7 | 13.9 | 55 | single: רמי לוי עטרות | 155.97 / 155.97 |
| Haifa centre | hand: small (6 lines) | 6 | 8 | 0 | 5.3 | 4.7 | 8.1 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | hand: weekly (17 lines) | 17 | 8 | 0 | 6.9 | 5.5 | 9.5 | 55 | single: שופרסל שלי חיפה- קלר | -11.87 / -11.87 |
| Haifa centre | hand: large (32 lines) | 33 | 8 | 0 | 8.8 | 6.4 | 10.6 | 55 | single: שופרסל שלי חיפה- קלר | -18.47 / -18.47 |
| Haifa centre | drawn: 5 | 5 | 8 | 2 | 5 | 4.5 | 8 | 55 | single: שופרסל שלי חיפה- קלר | 4.63 / 4.63 |
| Haifa centre | drawn: 10 | 10 | 8 | 0 | 5.9 | 4.9 | 8.7 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Haifa centre | drawn: 20 | 20 | 8 | 0 | 7.2 | 5.4 | 9.4 | 55 | single: שופרסל שלי חיפה- קלר | -5.17 / -5.17 |
| Haifa centre | drawn: 40 | 40 | 8 | 0 | 10.7 | 6.9 | 11.4 | 55 | single: טיב טעם מחניים | 0.0 / 0.0 |
| Petah Tikva | hand: small (6 lines) | 6 | 7 | 0 | 4.8 | 4.4 | 8.1 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 30.61 / 30.61 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 7 | 0 | 6.5 | 5.6 | 9.7 | 55 | single: טיב טעם מונטיפיורי פתח תקוה | 33.81 / 33.81 |
| Petah Tikva | hand: large (32 lines) | 33 | 7 | 0 | 8.6 | 6.9 | 11.3 | 55 | single: שופרסל אקספרס סוקולוב פ"ת | 0.0 / 0.0 |
| Petah Tikva | drawn: 5 | 5 | 7 | 0 | 4.7 | 4.4 | 8 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 59.31 / 59.31 |
| Petah Tikva | drawn: 10 | 10 | 7 | 0 | 5.9 | 5.1 | 9.1 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 41.41 / 41.41 |
| Petah Tikva | drawn: 20 | 20 | 7 | 0 | 7.2 | 5.9 | 10.4 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 80.61 / 80.61 |
| Petah Tikva | drawn: 40 | 40 | 7 | 0 | 11.8 | 8.3 | 13.2 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 73.51 / 73.51 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 5.3 | 4.7 | 8.1 |
| hand: weekly (17 lines) | 6.9 | 5.6 | 9.7 |
| hand: large (32 lines) | 8.8 | 6.9 | 11.3 |
| drawn: 5 | 5.0 | 4.5 | 8.0 |
| drawn: 10 | 5.9 | 5.1 | 9.1 |
| drawn: 20 | 7.2 | 5.9 | 10.4 |
| drawn: 40 | 11.1 | 8.3 | 13.2 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 5.9 | 10.6 | - | - | 5.73 / 5.73 |
| Jerusalem centre | hand: weekly (17 lines) | 6.3 | 10.7 | רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | 26.6 / 26.6 |
| Jerusalem centre | hand: large (32 lines) | 7.7 | 12.3 | - | - | 86.8 / 86.8 |
| Jerusalem centre | drawn: 5 | 5 | 8.9 | אושר עד תלפיות, רמי לוי עטרות | אושר עד תלפיות, רמי לוי עטרות | 14.6 / 14.6 |
| Jerusalem centre | drawn: 10 | 5.5 | 10.8 | - | - | 26.25 / 26.25 |
| Jerusalem centre | drawn: 20 | 6.3 | 10.6 | - | - | 61.97 / 61.97 |
| Jerusalem centre | drawn: 40 | 8.7 | 14.1 | - | - | 155.97 / 155.97 |
| Haifa centre | hand: small (6 lines) | 4.5 | 8.4 | - | - | 0.0 / 0.0 |
| Haifa centre | hand: weekly (17 lines) | 5.6 | 9.6 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 8.34 / 8.34 |
| Haifa centre | hand: large (32 lines) | 6.7 | 10.9 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 8.34 / 8.34 |
| Haifa centre | drawn: 5 | 4.6 | 9.4 | - | - | 4.63 / 4.63 |
| Haifa centre | drawn: 10 | 4.9 | 8.7 | - | - | 0.0 / 0.0 |
| Haifa centre | drawn: 20 | 5.5 | 9.6 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 17.34 / 17.34 |
| Haifa centre | drawn: 40 | 6.8 | 11.3 | - | - | 0.0 / 0.0 |
| Petah Tikva | hand: small (6 lines) | 4.5 | 8.1 | - | - | 30.61 / 30.61 |
| Petah Tikva | hand: weekly (17 lines) | 5.6 | 9.7 | - | - | 33.81 / 33.81 |
| Petah Tikva | hand: large (32 lines) | 7 | 11.6 | שופרסל אקספרס סוקולוב פ"ת, טיב טעם מונטיפיורי פתח תקוה | שופרסל אקספרס סוקולוב פ"ת, טיב טעם מונטיפיורי פתח תקוה | 48.87 / 48.87 |
| Petah Tikva | drawn: 5 | 4.3 | 8 | - | - | 59.31 / 59.31 |
| Petah Tikva | drawn: 10 | 5.3 | 9.4 | - | - | 41.41 / 41.41 |
| Petah Tikva | drawn: 20 | 6.1 | 10.1 | - | - | 80.61 / 80.61 |
| Petah Tikva | drawn: 40 | 8.1 | 13.3 | - | - | 73.51 / 73.51 |

### /parse-list, /compare and /optimize (stress: unreviewed mappings included, performance only)

Locations: Jerusalem centre (9 priced stores, 5 chains within 5 km); Haifa centre (8 priced stores, 5 chains within 5 km); Petah Tikva (7 priced stores, 5 chains within 5 km).

| hand-made list | rows | resolved | need confirmation | not found | ms |
|---|---|---|---|---|---|
| small (6 lines) | 6 | 6 | 0 | 0 | 3927.1 |
| weekly (17 lines) | 17 | 17 | 2 | 0 | 10989.4 |
| large (32 lines) | 33 | 33 | 5 | 0 | 21351.4 |

Times are the median over the repeats, in ms, through the in-process test client (no network).

| location | basket | lines | stores in radius | complete | /compare | heuristic | MILP | subsets | recommended (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 6 | 9 | 5 | 6.9 | 5.8 | 9.9 | 55 | single: רמי לוי עטרות | 57.26 / 57.26 |
| Jerusalem centre | hand: weekly (17 lines) | 17 | 9 | 0 | 8.6 | 7.1 | 11.5 | 55 | single: רמי לוי עטרות | 55.54 / 55.54 |
| Jerusalem centre | hand: large (32 lines) | 33 | 9 | 0 | 12 | 9.5 | 15.4 | 55 | split: רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | 148.59 / 148.59 |
| Jerusalem centre | drawn: 5 | 5 | 9 | 4 | 5.6 | 5 | 8.7 | 55 | single: רמי לוי עטרות | 104.27 / 104.27 |
| Jerusalem centre | drawn: 10 | 10 | 9 | 2 | 6.3 | 5.6 | 9.6 | 55 | single: רמי לוי עטרות | 54.27 / 54.27 |
| Jerusalem centre | drawn: 20 | 20 | 9 | 2 | 9.2 | 7.2 | 12 | 55 | single: רמי לוי עטרות | 166.77 / 166.77 |
| Jerusalem centre | drawn: 40 | 40 | 9 | 0 | 12.9 | 10.1 | 15.7 | 55 | single: רמי לוי עטרות | 398.37 / 398.37 |
| Haifa centre | hand: small (6 lines) | 6 | 8 | 5 | 5.7 | 4.8 | 8.4 | 55 | single: שופרסל שלי חיפה- קלר | -5.95 / -5.95 |
| Haifa centre | hand: weekly (17 lines) | 17 | 8 | 0 | 8.1 | 5.7 | 9.7 | 55 | single: שופרסל שלי חיפה- קלר | 23.67 / 23.67 |
| Haifa centre | hand: large (32 lines) | 33 | 8 | 0 | 11.2 | 7.5 | 12.1 | 55 | single: שופרסל שלי חיפה- קלר | 95.97 / 95.97 |
| Haifa centre | drawn: 5 | 5 | 8 | 3 | 5.3 | 4.3 | 8 | 55 | single: שופרסל שלי חיפה- קלר | 3.03 / 3.03 |
| Haifa centre | drawn: 10 | 10 | 8 | 0 | 6 | 5 | 9.1 | 55 | single: שופרסל שלי חיפה- קלר | -5.87 / -5.87 |
| Haifa centre | drawn: 20 | 20 | 8 | 1 | 8.4 | 6.1 | 10.2 | 55 | single: שופרסל שלי חיפה- קלר | 25.43 / 25.43 |
| Haifa centre | drawn: 40 | 40 | 8 | 0 | 12.3 | 7.7 | 12.5 | 55 | single: שופרסל שלי חיפה- קלר | -4.37 / -4.37 |
| Petah Tikva | hand: small (6 lines) | 6 | 7 | 5 | 5.2 | 4.7 | 8.3 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 37.21 / 37.21 |
| Petah Tikva | hand: weekly (17 lines) | 17 | 7 | 0 | 7.7 | 6.3 | 10.5 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 93.21 / 93.21 |
| Petah Tikva | hand: large (32 lines) | 33 | 7 | 0 | 10.6 | 8.4 | 13.4 | 55 | split: רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | 182.38 / 182.38 |
| Petah Tikva | drawn: 5 | 5 | 7 | 3 | 5 | 4.5 | 8.3 | 55 | single: שופרסל יש חסד בארות יצחק- פאוור | 160.51 / 160.51 |
| Petah Tikva | drawn: 10 | 10 | 7 | 2 | 5.9 | 5.1 | 9.3 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 87.81 / 87.81 |
| Petah Tikva | drawn: 20 | 20 | 7 | 0 | 8 | 6.4 | 10.9 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 66.51 / 66.51 |
| Petah Tikva | drawn: 40 | 40 | 7 | 0 | 12.6 | 8.5 | 15.8 | 55 | single: רמי לוי קניון אבנת פתח תקווה | 291.21 / 291.21 |

Median of the per-location medians, by basket:

| basket | /compare ms | heuristic ms | MILP ms |
|---|---|---|---|
| hand: small (6 lines) | 5.7 | 4.8 | 8.4 |
| hand: weekly (17 lines) | 8.1 | 6.3 | 10.5 |
| hand: large (32 lines) | 11.2 | 8.4 | 13.4 |
| drawn: 5 | 5.3 | 4.5 | 8.3 |
| drawn: 10 | 6.0 | 5.1 | 9.3 |
| drawn: 20 | 8.4 | 6.4 | 10.9 |
| drawn: 40 | 12.6 | 8.5 | 15.7 |

Relaxed variant (an extra stop is worth 0 and `min_split_saving` is 0, so a split is returned whenever it is at least as cheap): this is the heavy path of the MILP.

| location | basket | heuristic ms | MILP ms | split (heuristic) | split (MILP) | net saving heuristic / MILP |
|---|---|---|---|---|---|---|
| Jerusalem centre | hand: small (6 lines) | 5.6 | 9.7 | רמי לוי עטרות, שופרסל שלי ירושלים- אגרון | רמי לוי עטרות, שופרסל שלי ירושלים- אגרון | 58.33 / 58.33 |
| Jerusalem centre | hand: weekly (17 lines) | 7.2 | 11.7 | רמי לוי עטרות, שופרסל שלי ירושלים- אגרון | רמי לוי עטרות, שופרסל שלי ירושלים- אגרון | 72.23 / 72.23 |
| Jerusalem centre | hand: large (32 lines) | 9.8 | 15.1 | רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | רמי לוי עטרות, שופרסל גוד מרקט רש"י ירושלים | 173.59 / 173.59 |
| Jerusalem centre | drawn: 5 | 5 | 8.8 | קינג סטור ואדי אלגוז', אושר עד תלפיות | קינג סטור ואדי אלגוז', אושר עד תלפיות | 147.88 / 147.88 |
| Jerusalem centre | drawn: 10 | 5.9 | 9.8 | רמי לוי עטרות, שופרסל שלי ירושלים- אגרון | רמי לוי עטרות, שופרסל שלי ירושלים- אגרון | 73.93 / 73.93 |
| Jerusalem centre | drawn: 20 | 7.6 | 12.2 | אושר עד תלפיות, רמי לוי עטרות | אושר עד תלפיות, רמי לוי עטרות | 211.1 / 211.1 |
| Jerusalem centre | drawn: 40 | 10.4 | 15.9 | - | - | 398.37 / 398.37 |
| Haifa centre | hand: small (6 lines) | 4.8 | 8.7 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 1.16 / 1.16 |
| Haifa centre | hand: weekly (17 lines) | 6 | 10.2 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 28.28 / 28.28 |
| Haifa centre | hand: large (32 lines) | 7.7 | 12.4 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 109.58 / 109.58 |
| Haifa centre | drawn: 5 | 4.4 | 8.3 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 48.34 / 48.34 |
| Haifa centre | drawn: 10 | 4.9 | 8.7 | - | - | -5.87 / -5.87 |
| Haifa centre | drawn: 20 | 6.2 | 10.3 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 40.14 / 40.14 |
| Haifa centre | drawn: 40 | 7.8 | 12.5 | שופרסל שלי חיפה- קלר, טיב טעם מחניים | שופרסל שלי חיפה- קלר, טיב טעם מחניים | 84.84 / 84.84 |
| Petah Tikva | hand: small (6 lines) | 4.8 | 8.5 | רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | 51.61 / 51.61 |
| Petah Tikva | hand: weekly (17 lines) | 6.2 | 10.4 | רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | 127.19 / 127.19 |
| Petah Tikva | hand: large (32 lines) | 8.3 | 13.2 | רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | רמי לוי קניון אבנת פתח תקווה, שופרסל יש חסד בארות יצחק- פאוור | 207.38 / 207.38 |
| Petah Tikva | drawn: 5 | 4.6 | 10 | - | - | 160.51 / 160.51 |
| Petah Tikva | drawn: 10 | 5.3 | 9.3 | רמי לוי קניון אבנת פתח תקווה, טיב טעם מונטיפיורי פתח תקוה | רמי לוי קניון אבנת פתח תקווה, טיב טעם מונטיפיורי פתח תקוה | 88.18 / 88.18 |
| Petah Tikva | drawn: 20 | 6.4 | 10.8 | - | - | 66.51 / 66.51 |
| Petah Tikva | drawn: 40 | 8.7 | 13.9 | - | - | 291.21 / 291.21 |

### Basket index on the real day (#44, dry run, production semantics)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `missing_items` שופרסל has no price for 8 basket items (yellow-cheese-sliced-28, butter, eggs-l, cucumber, banana, pita, bamba, chocolate-milk); it is listed but not ranked
- warning: `estimated_items` שופרסל: 4 lines use estimated weighed-goods prices
- warning: `missing_items` קרפור (מגה) has no price for 12 basket items (milk-fresh-3, yellow-cheese-sliced-28, butter, hummus-plain, tomato, cucumber, potato, banana, pita, pasta-spaghetti, bamba, chocolate-milk); it is listed but not ranked
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

Basket of 25 lines; price date 2026-10-21T21:10:19Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| שופרסל | - | 17 | 8 | 7 | no |
| קרפור (מגה) | - | 13 | 12 | 1 | no |
| קינג סטור | - | 10 | 15 | 3 | no |
| רמי לוי | - | 16 | 9 | 6 | no |
| אושר עד | - | 8 | 17 | 5 | no |
| יוחננוף | - | 14 | 11 | 3 | no |
| טיב טעם | - | 13 | 12 | 5 | no |

### Basket index on the real day (#44, dry run, stress)

`smartcart-catalog basket-index` into a scratch directory (month 2026-10, status `draft`, exit 0): **a dry run on one day, never publishable.**

- warning: `missing_items` שופרסל has no price for 1 basket items (eggs-l); it is listed but not ranked
- warning: `estimated_items` שופרסל: 6 lines use estimated weighed-goods prices
- warning: `missing_items` קרפור (מגה) has no price for 2 basket items (yellow-cheese-sliced-28, cucumber); it is listed but not ranked
- warning: `estimated_items` קרפור (מגה): 5 lines use estimated weighed-goods prices
- warning: `missing_items` קינג סטור has no price for 3 basket items (eggs-l, bread-standard, tuna-in-oil); it is listed but not ranked
- warning: `estimated_items` קינג סטור: 6 lines use estimated weighed-goods prices
- warning: `missing_items` רמי לוי has no price for 1 basket items (eggs-l); it is listed but not ranked
- warning: `estimated_items` רמי לוי: 3 lines use estimated weighed-goods prices
- warning: `missing_items` אושר עד has no price for 5 basket items (eggs-l, chicken-breast-fresh, onion, banana, pita); it is listed but not ranked
- warning: `missing_items` יוחננוף has no price for 2 basket items (eggs-l, pita); it is listed but not ranked
- warning: `estimated_items` יוחננוף: 6 lines use estimated weighed-goods prices
- warning: `missing_items` טיב טעם has no price for 1 basket items (eggs-l); it is listed but not ranked
- warning: `estimated_items` טיב טעם: 6 lines use estimated weighed-goods prices
- error: `too_few_chains` only 0 chain(s) price the whole basket; at least 2 needed

Basket of 25 lines; price date 2026-10-21T21:10:19Z.

| chain | total (ILS) | lines priced | lines missing | stores | ranked |
|---|---|---|---|---|---|
| שופרסל | - | 24 | 1 | 7 | no |
| קרפור (מגה) | - | 23 | 2 | 1 | no |
| קינג סטור | - | 22 | 3 | 3 | no |
| רמי לוי | - | 24 | 1 | 6 | no |
| אושר עד | - | 20 | 5 | 5 | no |
| יוחננוף | - | 23 | 2 | 3 | no |
| טיב טעם | - | 24 | 1 | 5 | no |

### Failures and findings the run recorded (6)

- **download**: mega price_full: no file matched
- **download**: mega promo_full: no file matched
- **ingest**: 4 Stores files are older than the stale-date gate's 36 h (osherad 64.5 h, ramilevy 67.5 h, tivtaam 67.5 h, yohananof 71.5 h); on the real clock the gate would quarantine them and no store of those chains would load (this run replayed the clock for them)
- **ingest**: 26861 promos loaded from 23 PromoFull files but 0 promo_items rows: no promo can reach a price (see the PromoFull table)
- **api**: /parse-list took over 2 s (production): {'small (6 lines)': 3963.0, 'weekly (17 lines)': 11188.7, 'large (32 lines)': 21099.0} ms
- **api**: /parse-list took over 2 s (stress): {'small (6 lines)': 3927.1, 'weekly (17 lines)': 10989.4, 'large (32 lines)': 21351.4} ms

