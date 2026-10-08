# Phase 0 exit dry run

> **This is not the exit validation.** It is a rehearsal of issue #60 on the files we have
> today: one real day of seven chains, trimmed to 200 price rows each, plus the synthetic set.
> The exit needs fourteen consecutive nightly loads on the VPS (`phase-0-exit-report.md`),
> and `phase-0-exit-report.md` stays **NO-GO**. Nothing here may be pasted into it as evidence.

Generated 2026-10-08 from commit `977a6a1` by `scripts/exit_dry_run/run.sh` (re-run it to
refresh this file; the evidence blocks below are the generator's own output, not typed).
Labels follow `docs/README.md`: **measured** is read from the databases of this run,
**estimate** is a judgement, **derived** is reasoning from a measured value and the repo.

## 1. What was run

- Server: PostgreSQL 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1), PostGIS 3.4.2, pgvector 0.6.0 on Linux (a throwaway cluster; migrations applied by `smartcart-ingest`'s own migrator).
- Path: the production one. A fake portal lists one file at a time; the real `Scheduler` downloads, hashes, tracks, archives, parses (chain adapter), runs the quality gates and loads in one transaction. Same method as `scripts/demo/load_fixtures.py` and the `gate` step of `scripts/unblock/portal_probe.py`. The scheduler's clock is replayed: one hour after each file's publication time, so the stale-date gate judges a file against its own day.
- Real set: 14 files of 7 chains (אושר עד, טיב טעם, יוחננוף, קינג סטור, קרפור (מגה), רמי לוי, שופרסל), published 2026-10-06 to 2026-10-08, fetched by the portal probe from a GitHub runner (the files are committed under `services/ingest/tests/fixtures/<chain>/real/`, with a `MANIFEST.json` each). Stores files are whole; each PriceFull is cut to its first 200 rows.
- Synthetic set: the ten chains' demo files (promos, coordinates, and deliberately broken files) over 2026-10-06 to 2026-10-09.
- Report: `python -m smartcart_ingest.report` (`build_exit_report` and `render_markdown`), window 2026-10-08 to 2026-10-08 for the real database, 2026-10-06 to 2026-10-09 for the synthetic one.

## 2. The real files, one real day per chain

14 of 14 real files reached `loaded`; 0 alerts were raised (measured). `Pass` is the first full-sync pass of `infra/vps/smartcart-ingest-full.timer` (06:00 and 08:30 Israel time) that can see the file (derived).

| Chain | Kind | File | Published (Israel) | Pass | Schema | Status | Gates failed |
|---|---|---|---|---|---|---|---|
| אושר עד | stores | `Stores7290103152017-000-20261006-080501.xml` | 2026-10-06 08:05 |  | v1 | loaded | none |
| אושר עד | price_full | `PriceFull7290103152017-001-001-20261008-080000.gz` | 2026-10-08 08:00 | 08:30 | v1 | loaded | none |
| טיב טעם | stores | `Stores7290873255550-000-20261006-050500.xml` | 2026-10-06 05:05 |  | v1 | loaded | none |
| טיב טעם | price_full | `PriceFull7290873255550-000-002-20261008-004004.gz` | 2026-10-08 00:40 | 06:00 | v1 | loaded | none |
| יוחננוף | stores | `Stores7290803800003-000-20261006-010001.xml` | 2026-10-06 01:00 |  | v1 | loaded | none |
| יוחננוף | price_full | `PriceFull7290803800003-000-001-20261008-004031.gz` | 2026-10-08 00:40 | 06:00 | v1 | loaded | none |
| קינג סטור | stores | `Stores7290058108879-000-20261008-043451.gz` | 2026-10-08 04:34 |  | v1 | loaded | none |
| קינג סטור | price_full | `PriceFull7290058108879-000-340-20261008-043451.gz` | 2026-10-08 04:34 | 06:00 | v1 | loaded | none |
| קרפור (מגה) | stores | `Stores7290055700007-000-20261008-000100.xml` | 2026-10-08 00:01 |  | v1 | loaded | none |
| קרפור (מגה) | price_full | `PriceFull7290055700007-001-002-20261008-051017.gz` | 2026-10-08 05:10 | 06:00 | v1 | loaded | none |
| רמי לוי | stores | `Stores7290058140886-000-20261006-050500.xml` | 2026-10-06 05:05 |  | v1 | loaded | none |
| רמי לוי | price_full | `PriceFull7290058140886-001-001-20261008-001000.gz` | 2026-10-08 00:10 | 06:00 | v1 | loaded | none |
| שופרסל | stores | `Stores7290027600007-000-20261008-020.gz` | 2026-10-08 02:00 |  | v1 | loaded | none |
| שופרסל | price_full | `PriceFull7290027600007-001-164-20261008-030000.gz` | 2026-10-08 03:00 | 06:00 | v1 | loaded | none |

What the files contain (measured):

| Chain | Physical stores | Online | With coordinates | City is a numeric code | Items | With barcode | Weighed | Manufacturer unknown | Price events | Stores with prices | Longest item name |
|---|---|---|---|---|---|---|---|---|---|---|---|
| אושר עד | 24 | 0 | 0 | 100% | 200 | 100% | 14% | 0% | 200 | 1 | 20 |
| טיב טעם | 47 | 7 | 0 | 100% | 200 | 54% | 46% | 99% | 200 | 1 | 40 |
| יוחננוף | 50 | 1 | 0 | 100% | 200 | 66% | 24% | 24% | 200 | 1 | 20 |
| קינג סטור | 48 | 0 | 0 | 100% | 200 | 46% | 46% | 100% | 200 | 1 | 55 |
| קרפור (מגה) | 144 | 3 | 0 | 100% | 200 | 90% | 6% | 0% | 200 | 1 | 20 |
| רמי לוי | 98 | 1 | 0 | 100% | 200 | 100% | 1% | 78% | 200 | 1 | 20 |
| שופרסל | 416 | 1 | 0 | 100% | 200 | 100% | 0% | 1% | 200 | 1 | 24 |

Totals: 827 physical and 13 online stores, **0 with coordinates**; 839 of 839 stores have a numeric city. Sample stores:

- אושר עד, store 1: מגדל העמק; city `874`; address `האיצטדיון 11`
- אושר עד, store 10: פתח תקווה - סגולה; city `7900`; address `בן ציון גליס 30`
- טיב טעם, store 10: כרמיאל; city `1139`; address `מעלה כמון 3 מתחם ביג`
- טיב טעם, store 12: חוצות המפרץ (קריות); city `4000`; address `החרושת 10 מתחם חוצות המפרץ`
- יוחננוף, store 1: יוחננוף מפוח; city `0`; address `רחוב המפוח 11, אזור התעשיה`
- יוחננוף, store 12: רמלה; city `0`; address `שדרות ירושלים פינת נופי חמד`
- קינג סטור, store 1: אום אלפחם; city `2710`; address `שרפה 22, כביש ראשי של העיר 0`
- קינג סטור, store 10: דליית אל כרמל; city `0`; address `ואדי אלפש, כביש 672 0`
- קרפור (מגה), store 10: קרפור היפר   כפר סבא; city `6900`; address `השקמה 21`
- קרפור (מגה), store 108: קרפור סיטי  פנקס; city `5000`; address `46-50 פנקס`
- רמי לוי, store 1: תלפיות; city `3000`; address `האומן,15`
- רמי לוי, store 10: מודיעין חדש; city `1165`; address `א.ת שילת`
- שופרסל, store 1: שלי ת"א- בן יהודה; city `5000`; address `בן יהודה 79`
- שופרסל, store 101: שלי הוד השרון- ק מרגלית; city `9700`; address `נחליאלי 2`

## 3. The exit report generator on that day

`build_exit_report` for 2026-10-08 to 2026-10-08 over the ten D13 chains, then over the 7 chains that have a real file. One day cannot meet a 14-day criterion, so the generator says "not met" by construction; what this run checks is that every section renders on real data and that the numbers are the ones the database holds.

- Ten chains: success rate **70.0%** (7 of 10 chain-days), longest streak 0 days.
- The 7 chains with a real file: **100.0%**, streak 1.
- Chains with no loaded full file on the day: Victory, Hazi Hinam, Machsanei Hashuk.
- Stores: 827 physical, 0 with coordinates, 827 listed as exceptions (the report prints the first 50).
- Promos: 0 parsed (the real set has no PromoFull file).

<details><summary>Generator output, real day, ten chains (verbatim)</summary>

## Phase 0 exit evidence, 2026-10-08 to 2026-10-08

Generated 2026-10-08 17:42 UTC by `python -m smartcart_ingest.report`.

### 1. Nightly loads

- Window: 1 days (2026-10-08 to 2026-10-08), 10 chains.
- Success rate: **70.0%** (7 of 10 chain-days with a loaded full file). Criterion: above 95.0% over at least 14 days: **not met**.
- Longest streak of days above 95.0%: **0**.

Per chain and day (`ok` = a `price_full` or `promo_full` file reached `loaded`):

| Chain | Rate | 10-08 |
|---|---|---|
| Shufersal | 100.0% | ok |
| Rami Levy | 100.0% | ok |
| Victory | 0.0% | FAIL |
| Yeinot Bitan and Carrefour | 100.0% | ok |
| Hazi Hinam | 0.0% | FAIL |
| Tiv Taam | 100.0% | ok |
| Osher Ad | 100.0% | ok |
| Yohananof | 100.0% | ok |
| Machsanei Hashuk | 0.0% | FAIL |
| King Store | 100.0% | ok |
| **All chains** | 70.0% | 70.0% |

### 2. Store coordinates

- Physical stores: 827; with coordinates: 0; without: **827**.

| Chain id | Store | Name | City | Address | Reason |
|---|---|---|---|---|---|
| 7290027600007 | 1 | שלי ת"א- בן יהודה | 5000 | בן יהודה 79 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 101 | שלי הוד השרון- ק מרגלית | 9700 | נחליאלי 2 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 102 | שלי פרדסיה- הנשיא | 171 | הנשיא 1 צ.פרדסיה | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 103 | שלי שוהם- מרכז מסחרי | 1304 | מרכז מסחרי | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 104 | שלי פ"ת- גד מכנס | 7900 | רוטשילד 180 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 105 | דיל פ"ת- אליעזר פרדימן | 7900 | אליעזר פרידמן 9 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 106 | יוניברס נס ציונה - הפטיש | 7200 | הפטיש 8,א.ת. | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 109 | שלי ראש העין- ז'בוטינסקי | 2640 | גבעת טל | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 11 | שלי ת"א- נורדאו | 5000 | אבן גבירול157 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 110 | דיל הפארק ב"ש | 9000 | 20 נחל פרת | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 111 | יש חסד טבריה עלית-לב האג | 6700 | לב האגם 10 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 112 | BE קרית מוצקין | 8200 | ש"י עגנון 18 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 113 | דיל ראשל"צ- גולדה מאיר | 8300 | גולדה מאיר 1 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 114 | דיל ירושלים- גילה | 3000 | צביה ויצחק 17 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 116 | שלי גבעתיים- מכתש | 6300 | בורוכוב 54 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 117 | שלי תל אביב-איכילוב | 5000 | ויצמן 6 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 118 | דיל אילת  הסתת | 2600 | הסתת 15 א תעשיה | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 119 | דיל מודיעין- סנטר | 1200 | צאלון   21 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 12 | יש בני ברק- ירושלים | 6100 | ירושלים  70 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 121 | יוניברס נהריה- לוחמי הגטאות | 9100 | לוחמי הגטאות 36 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 122 | דיל יבנה- ברוש דרך הים | 2660 | דרך הים 3 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 123 | דיל חולון- גולדה | 6600 | גולדה מאיר  7 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 124 | יוניברס בת ים- אורט ישראל | 6200 | אורט ישראל 25 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 127 | אקספרס טירת הכרמל | 2100 | הדולפין 1 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 128 | יוניברס טירת הכרמל- נחום חת | 2100 | נחום חת 5 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 129 | יוניברס נתניה המלאכה | 7400 | רח' המלאכה 32 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 13 | יוניברס בית שמש- העליה | 2610 | העליה 1 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 130 | דיל נתניה- קלאוזנר עמליה | 7400 | קלאוזנר 1 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 131 | אקספרס הוד השרון | 9700 | סוקולוב 37 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 133 | יש חסד ביתר עילית-  הר"ן | 3780 | הר"ן 6 פינת פנים המאירים | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 134 | יוניברס מודיעין- ישפרו סנטר | 1200 | ישפרו סנטר | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 135 | יוניברס אשקלון- פאור סנטר | 7100 | צומת כפר סילבר | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 139 | יוניברס צפת- דובק ויצמן | 8000 | ויצמן 20 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 14 | דיל ברנע אשקלון | 7100 | שדרות ירושלים 122 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 140 | אקספרס תל חי | 6900 |  | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 141 | דיל יוקנעם- שדרות רבין | 240 | שדרות רבין 9 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 142 | דיל זכרון- המייסדים | 9300 | המייסדים | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 144 | דיל שבירו כפר סבא | 6900 | רפפורט 6 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 145 | BE נתיבות | 246 | בעלי המלאכה 3 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 147 | אקספרס זכרון | 9300 | ההנפה | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 148 | אקספרס מלצר רחובות | 8400 | מלצר 20 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 15 | יש פ"ת- רוטשילד | 7900 | רוטשילד 79 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 150 | אקספרס רודנסקי ת"א | 5000 | רודנסקי 5 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 151 | דיל רעננה- קניון רננים | 8700 | רח.המלאכה 2 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 152 | דיל ערד- ישפרו המנוף | 2560 | המנוף 7 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 153 | דיל אופקים- ז'בוטינסקי | 31 | זבוטינסקי 25 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 155 | יוניברס צור יגאל- מרכז מסחרי | 1306 | מרכז מסחרי | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 159 | דיל רמת הנשיא חיפה | 4000 | שלמה המלך 55 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 161 | המפיץ סיטונאות אשדוד | 70 | הבושם 16 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290027600007 | 163 | דיל שדרות- הפלדה | 1031 | הפלדה קניון אחים | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |

(777 more not shown.)

Each exception needs a plan before go: geocode from the address, ask the chain, or accept it with a stated reason.

### 3. Promo parsing, main chains

| Chain | Promos parsed | By reward type |
|---|---|---|
| Shufersal | 0 | none |
| Rami Levy | 0 | none |
| Victory | 0 | none |
| Yeinot Bitan and Carrefour | 0 | none |
| Hazi Hinam | 0 | none |
| Tiv Taam | 0 | none |

#### Shufersal

No promos in the database for this chain.

#### Rami Levy

No promos in the database for this chain.

#### Victory

No promos in the database for this chain.

#### Yeinot Bitan and Carrefour

No promos in the database for this chain.

#### Hazi Hinam

No promos in the database for this chain.

#### Tiv Taam

No promos in the database for this chain.

Tick `Checked` by comparing each structured field with the raw description.

### 4. Basket price across stores in a radius

Barcodes: 16000548404, 16000548503, 16000548909. Point: 34.7818, 32.0853; radius 5000.0 m; online stores excluded.

| Store | Chain id | Name | Distance (m) | Total | Found | Missing | Complete |
|---|---|---|---|---|---|---|---|

</details>

Basket query on the real database (`supabase/queries/basket_radius.sql`):

- Barcodes sold by more than one chain in this sample: 1 chain: 966, 2 chains: 55, 3 chains: 2, 4 chains: 4, 5 chains: 3 (each chain's file is cut to 200 rows, so overlap here says little about the full catalogs; estimate).
- Prices do come back for real items (spot check with `current_price`, barcodes `16000548404`, `16000548503`, `16000548909`):

| Barcode | Item (as the chain names it) | Chain | Store | Store name | Price | Valid from |
|---|---|---|---|---|---|---|
| 16000548404 | מארז נייטשר ואלי  קר | אושר עד | 1 | מגדל העמק | 10.90 | 2026-10-08 05:00 |
| 16000548404 | קראנצי בטעם שיבולת שועל ודבש 210 גר | טיב טעם | 2 | נתניה | 21.90 | 2026-10-07 21:40 |
| 16000548404 | קראנצי חטיף שיבולת | יוחננוף | 1 | יוחננוף מפוח | 14.90 | 2026-10-07 21:40 |
| 16000548404 | חטיף קראנצי גרנולה שיבולת שועל 210 ג' ניטשר ואלי | קינג סטור | 340 | מיני קינג סח'נין | 18.90 | 2026-10-08 01:34 |
| 16000548404 | חטיף נייטשר וואלי דבש5יח | שופרסל | 164 | שלי רמת גן- ביאליק | 22.90 | 2026-10-08 00:00 |
| 16000548503 | מארז נייטשר ואלי קרא | אושר עד | 1 | מגדל העמק | 10.90 | 2026-10-08 05:00 |
| 16000548503 | קראנצי בטעם מייפל וסוכר חום 210 גר | טיב טעם | 2 | נתניה | 21.90 | 2026-10-07 21:40 |
| 16000548503 | קראנצי חטיף שיבולת | יוחננוף | 1 | יוחננוף מפוח | 14.90 | 2026-10-07 21:40 |
| 16000548503 | חטיף שיבולת שועל עם סירופ מייפל 210 ג' ניטשר ואלי | קינג סטור | 340 | מיני קינג סח'נין | 18.90 | 2026-10-08 01:34 |
| 16000548503 | נייטשר וואלי מייפל 5יח | שופרסל | 164 | שלי רמת גן- ביאליק | 22.90 | 2026-10-08 00:00 |
| 16000548909 | מארז נייטשר ואלי קרא | אושר עד | 1 | מגדל העמק | 10.90 | 2026-10-08 05:00 |
| 16000548909 | חטיף ניישטר וואלי 1/5 בריאות מעורב 210 ג | טיב טעם | 2 | נתניה | 21.90 | 2026-10-07 21:40 |
| 16000548909 | קראנצי חטיף שיבולת | יוחננוף | 1 | יוחננוף מפוח | 14.90 | 2026-10-07 21:40 |
| 16000548909 | חטיפי שיבולת שועל מלאה במגוון טעמים  210 ג'  ניטשר ואלי | קינג סטור | 340 | מיני קינג סח'נין | 18.90 | 2026-10-08 01:34 |
| 16000548909 | חט.נייטשר וואלי מעורב5יח | שופרסל | 164 | שלי רמת גן- ביאליק | 22.90 | 2026-10-08 00:00 |

- Run for 3 shared barcodes around Tel Aviv (lat 32.0853, lon 34.7818), 5 km: **0 stores returned**. No store has coordinates, so `stores_within` finds none. The query is not the blocker; the coordinates are.

## 4. The synthetic set through the same report

Sections 2 to 4 of the report need data the real set does not have (promos, coordinates, several days, failures). The synthetic set has them, so this shows what the finished report looks like. Synthetic data proves the generator, not the pipeline's behavior on chains (measured on fixtures written by us).

- Files: 44; failed 7, held 1, loaded 35, quarantined 1.
- Window 2026-10-06 to 2026-10-09: success rate **25.0%**, longest streak 1 days, 8 full files that did not load (listed by the generator with their reasons).
- Stores: 27 physical, 24 with coordinates.
- Promos parsed for the main chains: 23; the sampler gives up to 10 per chain with the raw description next to the structured fields.
- Basket: 6 stores in 15000 m of (32.0808, 34.9161); 3 complete; missing items are listed per store, not dropped.

<details><summary>Generator output, synthetic window (verbatim)</summary>

## Phase 0 exit evidence, 2026-10-06 to 2026-10-09

Generated 2026-10-08 17:42 UTC by `python -m smartcart_ingest.report`.

### 1. Nightly loads

- Window: 4 days (2026-10-06 to 2026-10-09), 10 chains.
- Success rate: **25.0%** (10 of 40 chain-days with a loaded full file). Criterion: above 95.0% over at least 14 days: **not met**.
- Longest streak of days above 95.0%: **1** (2026-10-06 to 2026-10-06).

Per chain and day (`ok` = a `price_full` or `promo_full` file reached `loaded`):

| Chain | Rate | 10-06 | 10-07 | 10-08 | 10-09 |
|---|---|---|---|---|---|
| Shufersal | 25.0% | ok | FAIL | FAIL | FAIL |
| Rami Levy | 25.0% | ok | FAIL | FAIL | FAIL |
| Victory | 25.0% | ok | FAIL | FAIL | FAIL |
| Yeinot Bitan and Carrefour | 25.0% | ok | FAIL | FAIL | FAIL |
| Hazi Hinam | 25.0% | ok | FAIL | FAIL | FAIL |
| Tiv Taam | 25.0% | ok | FAIL | FAIL | FAIL |
| Osher Ad | 25.0% | ok | FAIL | FAIL | FAIL |
| Yohananof | 25.0% | ok | FAIL | FAIL | FAIL |
| Machsanei Hashuk | 25.0% | ok | FAIL | FAIL | FAIL |
| King Store | 25.0% | ok | FAIL | FAIL | FAIL |
| **All chains** | 25.0% | 100.0% | 0.0% | 0.0% | 0.0% |

Full files that did not load:

| Day | Chain id | Kind | Status | Reason |
|---|---|---|---|---|
| 2026-10-06 | 7290055700007 | price_full | failed | parse failed: [7290055700007] raw/7290055700007/2026/10/06/PriceFull7290055700007-3012-202610060300.gz: content does not match kind price_full (containers: Promotions) |
| 2026-10-06 | 7290058108879 | price_full | failed | parse failed: [7290058108879] raw/7290058108879/2026/10/06/PriceFull7290058108879-004-202610060510.xml: corrupt gzip container: Compressed file ended before the end-of-stream marker was reached |
| 2026-10-06 | 7290103152017 | price_full | failed | parse failed: [7290103152017] raw/7290103152017/2026/10/06/PriceFull7290103152017-021-202610060300.gz: price_full file has no rows |
| 2026-10-06 | 7290700100008 | price_full | failed | parse failed: [7290700100008] raw/7290700100008/2026/10/06/PriceFull7290700100008-000-201-20261006-030000.xml.gz: not a number: 'abc' |
| 2026-10-07 | 7290027600007 | price_full | quarantined | item_count_drop: 3 records versus 8 in the previous price_full file (below 50%) |
| 2026-10-08 | 7290027600007 | price_full | failed | unknown schema: [7290027600007] raw/7290027600007/2026/10/08/PriceFull7290027600007-001-202610080300.gz: unrecognised schema (root <root>, containers: Items); file must not be loaded |
| 2026-10-08 | 7290058140886 | price_full | failed | unknown schema: [7290058140886] raw/7290058140886/2026/10/08/PriceFull7290058140886-039-202610080300.gz: unrecognised schema (root <Root>, containers: none); file must not be loaded |
| 2026-10-09 | 7290027600007 | price_full | failed | parse failed: [7290027600007] raw/7290027600007/2026/10/09/PriceFull7290027600007-001-202610090300.gz: corrupt gzip container: Compressed file ended before the end-of-stream marker was reached |

### 2. Store coordinates

- Physical stores: 27; with coordinates: 24; without: **3**.

| Chain id | Store | Name | City | Address | Reason |
|---|---|---|---|---|---|
| 7290696200003 | 1 | ויקטורי באר יעקב | באר יעקב | הרצל 1 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290696200003 | 52 | ויקטורי גדרה | גדרה | הבנים 4 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |
| 7290696200003 | 7 | ויקטורי אשקלון | אשקלון | בן גוריון 12 | no coordinates (stores.geog is NULL): not published by the chain, not geocoded yet |

Each exception needs a plan before go: geocode from the address, ask the chain, or accept it with a stated reason.

### 3. Promo parsing, main chains

| Chain | Promos parsed | By reward type |
|---|---|---|
| Shufersal | 4 | bundle: 1, buy_x_get_y: 1, percent: 1, price: 1 |
| Rami Levy | 4 | bundle: 1, buy_x_get_y: 1, percent: 1, price: 1 |
| Victory | 3 | bundle: 1, buy_x_get_y: 1, price: 1 |
| Yeinot Bitan and Carrefour | 4 | bundle: 1, buy_x_get_y: 1, percent: 1, price: 1 |
| Hazi Hinam | 4 | bundle: 1, buy_x_get_y: 1, percent: 1, price: 1 |
| Tiv Taam | 4 | bundle: 1, buy_x_get_y: 1, percent: 1, price: 1 |

#### Shufersal

| Promo | Store | Raw description | Reward | Value | Min qty | Max qty | Club | Dates | Hours | Items | Checked |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1002 | 1 | קוטג' 1+1 | buy_x_get_y | 1 | 2 |  | no | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 1 | [ ] |
| 1001 | 1 | במבה 2 ב-8 ש"ח לחברי מועדון | bundle | 8.00 | 2 | 6 | מועדון לקוחות | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 1 | [ ] |
| 1004 | 1 | חלב ב-5.90 בשעות הבוקר | price | 5.90 | 1 |  | no | 2026-10-01 to 2026-10-14 | 07:00-12:00 | 1 | [ ] |
| 1003 | 1 | 20% הנחה על שמן ושוקולד | percent | 20 | 1 |  | no | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 2 | [ ] |

#### Rami Levy

| Promo | Store | Raw description | Reward | Value | Min qty | Max qty | Club | Dates | Hours | Items | Checked |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1001 | 39 | במבה 2 ב-8 ש"ח לחברי מועדון | bundle | 8.00 | 2 | 6 | מועדון לקוחות | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 1 | [ ] |
| 1004 | 39 | חלב ב-5.90 בשעות הבוקר | price | 5.90 | 1 |  | no | 2026-10-01 to 2026-10-14 | 07:00-12:00 | 1 | [ ] |
| 1003 | 39 | 20% הנחה על שמן ושוקולד | percent | 20 | 1 |  | no | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 2 | [ ] |
| 1002 | 39 | קוטג' 1+1 | buy_x_get_y | 1 | 2 |  | no | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 1 | [ ] |

#### Victory

| Promo | Store | Raw description | Reward | Value | Min qty | Max qty | Club | Dates | Hours | Items | Checked |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 55003 | 1 | לחם ב-6.90 | price | 6.90 | 1.00 |  | no | 2026-09-30 to 2026-10-10 | 00:00-23:59 | 1 | [ ] |
| 55001 | 1 | חטיפים 3 ב-12 למועדון | bundle | 12.00 | 3 |  | מועדון לקוחות | 2026-09-30 to 2026-10-10 | 00:00-23:59 | 2 | [ ] |
| 55002 | 1 | חלב 1+1 | buy_x_get_y | 1 | 2 |  | no | 2026-09-30 to 2026-10-10 | 00:00-23:59 | 1 | [ ] |

#### Yeinot Bitan and Carrefour

| Promo | Store | Raw description | Reward | Value | Min qty | Max qty | Club | Dates | Hours | Items | Checked |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1003 | 2960 | 20% הנחה על שמן ושוקולד | percent | 20 | 1 |  | no | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 2 | [ ] |
| 1002 | 2960 | קוטג' 1+1 | buy_x_get_y | 1 | 2 |  | no | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 1 | [ ] |
| 1001 | 2960 | במבה 2 ב-8 ש"ח לחברי מועדון | bundle | 8.00 | 2 | 6 | מועדון לקוחות | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 1 | [ ] |
| 1004 | 2960 | חלב ב-5.90 בשעות הבוקר | price | 5.90 | 1 |  | no | 2026-10-01 to 2026-10-14 | 07:00-12:00 | 1 | [ ] |

#### Hazi Hinam

| Promo | Store | Raw description | Reward | Value | Min qty | Max qty | Club | Dates | Hours | Items | Checked |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1004 | 207 | חלב ב-5.90 בשעות הבוקר | price | 5.90 | 1 |  | no | 2026-10-01 to 2026-10-14 | 07:00-12:00 | 1 | [ ] |
| 1003 | 207 | 20% הנחה על שמן ושוקולד | percent | 20 | 1 |  | no | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 2 | [ ] |
| 1002 | 207 | קוטג' 1+1 | buy_x_get_y | 1 | 2 |  | no | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 1 | [ ] |
| 1001 | 207 | במבה 2 ב-8 ש"ח לחברי מועדון | bundle | 8.00 | 2 | 6 | מועדון לקוחות | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 1 | [ ] |

#### Tiv Taam

| Promo | Store | Raw description | Reward | Value | Min qty | Max qty | Club | Dates | Hours | Items | Checked |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1002 | 2 | קוטג' 1+1 | buy_x_get_y | 1 | 2 |  | no | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 1 | [ ] |
| 1001 | 2 | במבה 2 ב-8 ש"ח לחברי מועדון | bundle | 8.00 | 2 | 6 | מועדון לקוחות | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 1 | [ ] |
| 1003 | 2 | 20% הנחה על שמן ושוקולד | percent | 20 | 1 |  | no | 2026-09-30 to 2026-10-14 | 00:00-23:59 | 2 | [ ] |
| 1004 | 2 | חלב ב-5.90 בשעות הבוקר | price | 5.90 | 1 |  | no | 2026-10-01 to 2026-10-14 | 07:00-12:00 | 1 | [ ] |

Tick `Checked` by comparing each structured field with the raw description.

### 4. Basket price across stores in a radius

Barcodes: 7290000042442, 7290000066318, 7290004131074. Point: 34.916133333333335, 32.0808375; radius 15000.0 m; online stores excluded.

| Store | Chain id | Name | Distance (m) | Total | Found | Missing | Complete |
|---|---|---|---|---|---|---|---|
| 51 | 7290661400001 | מחסני השוק בני ברק | 7762 | 16.32 | 3 | none | yes |
| 24 | 7290027600007 | שופרסל שלי תל אביב - אבן גבירול | 12692 | 17.52 | 3 | none | yes |
| 21 | 7290873255550 | טיב טעם רמת גן | 9760 | 20.52 | 3 | none | yes |
| 48 | 7290058108879 | קינג סטור כפר קאסם | 6742 | 0 | 0 | 7290000042442, 7290000066318, 7290004131074 | no |
| 9 | 7290103152017 | אושר עד בני ברק | 7406 | 0 | 0 | 7290000042442, 7290000066318, 7290004131074 | no |
| 16 | 7290700100008 | חצי חינם הרצליה | 13690 | 0 | 0 | 7290000042442, 7290000066318, 7290004131074 | no |

</details>

## 5. Which criteria can pass, and which cannot yet

Criteria are those of issue #60 and `phase-0-exit-report.md`.

| Criterion | Dry run (measured) | Can it pass yet? |
|---|---|---|
| 1. More than 95% nightly loads over 14 consecutive days | 1 day, 7 of 10 chains had a loaded full file (70%). On the 7 chains with a real file, 100% (one day, one file each, no nightly history). | **No.** Needs 14 days of timers on the VPS (#14, #22), and a real file for Victory, Hazi Hinam and Machsanei Hashuk (not in the committed set). |
| 2. Every physical store has coordinates, or exceptions listed with reasons | 0 of 827 physical stores have coordinates. The city field is a number for all 839 stores that have one (76 of them `0`); street addresses are present for most. | **No.** Nothing in the repository geocodes stores (`stores.geog` is NULL until something fills it). Needs a decision on the method and a city-code table first. |
| 3. Promo parsing demonstrated for the top chains, with a checked sample | 0 real promos (no PromoFull in the real set). Synthetic: 23 promos parsed, the sampler and its table render. | **No.** Needs real PromoFull files from the six main chains and a person to tick the sample against the raw descriptions. |
| 4. Basket SQL over a radius, missing items reported | Runs on real prices (spot check above) but returns 0 stores because no store has coordinates. Synthetic: 6 stores with missing barcodes listed. | **Partly.** The query and its sample output are done (`phase-0-exit-report.md` section 4); the real-data run waits for criterion 2. |
| Go or no-go | Not decided on evidence. | **NO-GO**, unchanged. |

## 6. Findings from the real files

Each is measured on the committed fixtures unless it says otherwise.

1. **Stores carry no coordinates, and the city is a number.** All 839 stores with a city field hold a number, not a name: 76 hold `0` (no city; the store name usually names the place), the others a code, most often `5000` (82), `3000` (42), `4000` (41), `7900` (30), `9000` (27). They look like Central Bureau of Statistics locality codes (3000 is Jerusalem and 7100 is Ashkelon, and the stores carrying them are there; estimate from the sample, confirm against the published code list). Geocoding needs the code turned into a name where there is one, and the store name and street address where there is not.
2. **A PriceFull is one store.** Each chain's real file is the prices of a single store (7 stores with prices across 7 chains), so a basket run on real data can price 7 stores today. The nightly run must fetch every store's file; the size of that run (files and minutes per night) is unmeasured.
3. **Item names are cut by the chains.** The longest name is אושר עד 20, טיב טעם 40, יוחננוף 20, קינג סטור 55, קרפור (מגה) 20, רמי לוי 20, שופרסל 24 characters; 5 of 7 chains stop at 24 or fewer (אושר עד, יוחננוף, קרפור (מגה), רמי לוי, שופרסל). Names alone will not carry matching (D4, D5): the barcode and the manufacturer field matter more.
4. **Barcode coverage differs a lot.** אושר עד 100%; טיב טעם 54%; יוחננוף 66%; קינג סטור 46%; קרפור (מגה) 90%; רמי לוי 100%; שופרסל 100%. Items without a barcode can only be matched by name.
5. **Manufacturer is often "לא ידוע" or empty:** אושר עד 0%; טיב טעם 99%; יוחננוף 24%; קינג סטור 100%; קרפור (מגה) 0%; רמי לוי 78%; שופרסל 1%. The private-label rules cannot lean on it.
6. **Publication time decides which pass loads a file** (derived from the timers). PriceFull files published after 06:00 Israel time: אושר עד. They wait for the 08:30 pass, so a check at 06:00 would show them missing. Published in the first hour of the day: רמי לוי, טיב טעם, יוחננוף; the report counts a file on the Israel date of `published_at`, so those belong to the date in their name.
7. **Two gates had nothing to compare against.** `price_jump` and `item_count_drop` need a previous load of the same store or file kind; on a first real day they cannot fire, so none of the gates' real-data behavior beyond `zero_price` and `stale_date` is shown. Day 2 of the real window is the first test of them.
8. **No promo file was fetched.** The probe's fixtures are Stores and PriceFull only. The promo parser has never read a real chain file in this repository. This is the largest unknown for criterion 3.
9. **Three D13 chains are missing from the real set** (Victory, Hazi Hinam, Machsanei Hashuk). The probe ran on a non-Israeli runner; the reason for each is in that probe run's report, not in this repository (to confirm).

## 7. What the owner runs on the VPS later

Everything here is written from the unit files in `infra/vps` and from `docs/infra-provisioning.md`; none of it has run on a VPS (the VPS does not exist yet). The order is that document's section 8.

**Once, after #14 and #22 exist** (`infra-provisioning.md` sections 5.3 to 5.5):

```bash
cd ~/SmartCart && sudo bash infra/vps/setup.sh
sudoedit /etc/smartcart/ingest.env        # DATABASE_URL, S3_* (see .env.example)
sudo systemctl start smartcart-ingest-full.timer smartcart-ingest-delta.timer
bash infra/smoke/check_israeli_ip.sh && bash infra/smoke/check_portals.sh
sudo systemctl start smartcart-ingest-full.service      # first full sync now
```

**Every day for 14 days** (a minute; the day is attributed by Israel date of `published_at`):

```bash
systemctl list-timers 'smartcart-*'
sudo -u smartcart -H bash -c 'set -a; . /etc/smartcart/ingest.env; /opt/smartcart/.venv/bin/smartcart-ingest status'
tail -n 100 /var/log/smartcart/ingest-full.log
```

**Fix the gaps this dry run found, before the window closes:** a geocoding step for criterion 2 (none exists), real PromoFull files for criterion 3, and real files for the three missing chains. Decide the tie-break of D13 early (see the `--only-chains` note below).

**After day 14** (`phase-0-exit-report.md`, "How to regenerate"). Replace START, END and the barcodes; the barcodes should be 10 to 20 products several chains sell (milk, eggs, bread, oil):

```bash
START=<first day> END=<last day>     # YYYY-MM-DD, inclusive, at least 14 days
BARCODES=<comma-separated barcodes>
sudo -u smartcart -H env START="$START" END="$END" BARCODES="$BARCODES" bash -c '
  set -a; . /etc/smartcart/ingest.env; cd /opt/smartcart
  .venv/bin/python -m smartcart_ingest.report --start "$START" --end "$END" \
    --basket-barcodes "$BARCODES" --lon 34.7818 --lat 32.0853 --radius-m 3000 \
    --out /var/lib/smartcart/phase-0-evidence.md'
cat /var/lib/smartcart/phase-0-evidence.md      # or copy it to your laptop with scp
```

If the D13 tie-break drops King Store and Machsanei Hashuk, add this flag to the report command and say so in the report: `--only-chains "Shufersal,Rami Levy,Victory,Yeinot Bitan and Carrefour,Hazi Hinam,Tiv Taam,Osher Ad,Yohananof"`.

Then paste the generated sections into `docs/phase-0-exit-report.md`, tick the promo sample by hand, fill the exception plans, and make the go or no-go decision there.

## 8. Reproduce this file

```bash
scripts/exit_dry_run/run.sh          # needs Postgres server binaries with PostGIS and pgvector
```

`run.sh` starts a throwaway cluster (or uses `DATABASE_URL` as a server), creates two databases, loads both file sets, runs the report over each window, writes this file, and removes the databases. Tests: `uv run --no-sync pytest scripts/exit_dry_run/tests -q`.
