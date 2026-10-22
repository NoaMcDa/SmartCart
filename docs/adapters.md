# Chain adapters

How SmartCart turns each chain's transparency files into the internal model
(`services/ingest/smartcart_ingest/models.py`). Covers issues #32 (adapter framework), #57 (dual
schema), #53 (sales channel) and #81 (the last two D13 chains: Machsanei Hashuk and King Store).

> **All fixtures are synthetic.** The chain portals cannot be reached from the development
> container (at least one portal blocks cloud IP ranges), so no real file has been downloaded
> yet. The fixtures in `services/ingest/tests/fixtures/<chain>/` were built by
> `tests/fixtures/build_synthetic.py`. They follow the layouts in the pinned upstream parser
> (il-supermarket-parser 1.0.12) and the regulation's uniform structure. They are not copies of
> real files. Once the Israeli VPS exists, run `fetch_fixtures.py` (see below) and replace them.
> Until then, every per-chain detail below that is marked *provisional* is a hypothesis.

Sources for each statement are marked as follows:

- **verified**: from the research documents (`docs/research/`, summarized in
  `docs/product-and-market.md`).
- **upstream**: read from the pinned source of `il_supermarket_parsers` 1.0.12 or
  `il_supermarket_scarper` 1.0.15.
- **provisional**: our best guess. It is encoded in a synthetic fixture and must be confirmed
  against a real file.

## Layers

```
portal bytes ──> xmlutil.decode ──> xmlutil.read_header ──> detect_schema ──> iter_rows ──> internal records
                 (gzip/zip,         (header + first row      (v1 / v2 /       (streaming,     (StoreRecord, ItemRecord,
                  encoding)          container)               unknown)         cleared rows)   PriceRecord, PromoRecord)
                                                                                         └──> channel.tag_channel
```

- `smartcart_ingest/xmlutil.py` works only on bytes. It knows nothing about chains.
  - `unwrap` detects gzip and zip by magic bytes, never by extension. Some Cerberus downloads
    keep a `.gz` name but are zip files. A zip yields its first `.xml` member. Nesting is
    unwrapped up to 3 levels.
  - `detect_encoding` / `to_utf8` check, in order: a BOM (UTF-8, UTF-16 LE/BE), UTF-16 without a
    BOM (NUL-byte pattern), strict UTF-8, then the declared encoding, then windows-1255. The
    declaration is trusted only when the bytes are not valid UTF-8, because `ISO-8859-8` is
    often declared over UTF-8 content (upstream works around the same problem). The output is
    always UTF-8 with the declaration rewritten. Plain UTF-8 input is not copied.
  - `read_header` parses until the first row element starts. `iter_rows` streams complete row
    elements and frees each one before the next, so memory stays flat on large PriceFull files.
  - Entity resolution and network access are off in the parser.
- `adapters/base.py` holds the shared contract (`ChainAdapter`, `AdapterError`,
  `UnknownSchemaError`, `REGISTRY`, `@register`). It is unchanged by this work.
- `adapters/_common.py` holds `RegulationAdapter`, one implementation of the contract for the
  regulation's uniform XML. It is configured per chain with class attributes: chain ids,
  accepted container elements, upstream names, and the online-store rule.
- `adapters/<chain>.py` is one small module per chain. Importing the module registers it. The
  package `__init__` imports all of them.
- `adapters/_upstream.py` reads upstream converter configuration as plain strings, for a test
  only. No upstream type is returned, and parsing never calls upstream code.
- `channel.py` tags each store as `physical` or `online`.

`parse(raw, data)` returns a `ParsedFile` whose `raw.schema_version` is set to the detected
version. That value populates `file_tracking`, the column itself is owned by the loader
workstream. Store codes are normalized (`"039"` and `"39"` are the same store), so Stores, Price
and Promo files join cleanly. Timestamps in the files are Israel local time and are returned
as timezone-aware datetimes (`Asia/Jerusalem`).

## Phase 0 chains

| Module | Chain | Chain id | Portal (upstream) | Filename pattern (upstream) |
|---|---|---|---|---|
| `shufersal` | שופרסל | 7290027600007 | own portal `prices.shufersal.co.il` | `PriceFull7290027600007-001-202610060300.gz` |
| `ramilevy` | רמי לוי | 7290058140886 | Cerberus `url.retail.publishedprices.co.il` (user RamiLevi) | `PriceFull7290058140886-039-202610060300.gz`, `Stores7290058140886-202610060100.xml` |
| `osherad` | אושר עד | 7290103152017 | Cerberus (user osherad) | same as Cerberus above |
| `yohananof` | יוחננוף | 7290803800003 | Cerberus (user yohananof) | same as Cerberus above |
| `victory` | ויקטורי | 7290696200003, 7290058103393 | Matrix / laibcatalog (`laibcatalog.co.il`) | `PriceFull7290696200003-001-202610060300.xml.gz` |
| `hazihinam` | חצי חינם | 7290700100008 | own web portal `shop.hazi-hinam.co.il/Prices` | `Promo7290700100008-000-207-20261006-103225.xml.gz` (chain-subchain-store-date-time) |
| `tivtaam` | טיב טעם | 7290873255550 | Cerberus (user TivTaam) | same as Cerberus above |
| `mega` | קרפור (מגה) | 7290055700007 | PublishPrice web portal `prices.carrefour.co.il` | `PriceFull7290055700007-2960-202610060300.gz` |
| `machsanei_hashuk` | מחסני השוק | 7290661400001, 7290633800006 | laibcatalog JSON API (`laibcatalog.co.il/webapi/api/getfiles`), scraper `MAHSANI_ASHUK_NEW_SOURCE`; portal value `matrix` | `PriceFull7290661400001-003-202610060810.xml.gz` |
| `king_store` | קינג סטור | 7290058108879 | Bina `kingstore.binaprojects.com` (plain HTTP, `MainIO_Hok.aspx`), scraper `KING_STORE`; portal value `bina` | `PriceFull7290058108879-001-202610060510.xml` (compressed content, see below) |

All ten D13 chains have an adapter, so `smartcart-ingest run --mode full` no longer skips any
of them (`test_every_d13_chain_has_an_adapter`).

Notes:

- **Mega is not a Bina portal.** Upstream, Mega's own portal (PublishPrice engine,
  `prices.mega.co.il`) was marked "removed 1.7.2025, merged". The same chain id now publishes
  through the Yayno Bitan and Carrefour PublishPrice portal. The adapter is named `mega` because
  of the phase 0 chain list. Its portal is `web`.
- **Victory publishes under two chain ids.** `REGISTRY` is keyed by a single chain id, so the
  second id is accepted through `chain_ids` but is not registered separately. See the contract
  notes below.
- **Machsanei Hashuk** (upstream, `scrappers/machsani_ashuk.py`): the active scraper is
  `MahsaniAShukNewSource`, a `_LaibcatalogApiScraper` (upstream engine `ApiWebEngine`) on the same
  laibcatalog host as Victory; the older Matrix ASPX scraper is deprecated. The `portal` value is
  `matrix`, the same as Victory, because both publish through that host and engine; if the column
  ever has to tell the laibcatalog API from the legacy Matrix site, both chains change together.
  It **needs the Israeli-IP VPS** (laibcatalog blocks cloud IPs, verified, research) and its
  listing is empty overnight until about 08:00 and, per upstream's stability notes, on Saturdays
  (upstream `scraper_stability.MahsaniAshukNewSource`). It publishes under two chain ids; the
  second, 7290633800006, is in `chain_ids` and is also registered as an alias, so
  `get_adapter("7290633800006")` works.
- **King Store** (upstream, `scrappers/king_store.py`, `engines/bina.py`): the only Bina chain.
  The listing is ASPX returning JSON; a file name is resolved through `Download.aspx?FileNm=` to
  its `SPath`. Upstream notes that King Store serves gzip content under names that do not end in
  `.gz`; `xmlutil.unwrap` detects compression by magic bytes, so no special case is needed.
- `parse_filename` handles all three upstream name shapes: chain-store-datetime, five-part
  chain-subchain-store-date-time, and Stores files with no store segment. It also accepts the
  `NULL` prefix some portals emit. A file whose name or header carries another chain's id is
  rejected.

### Dialects

Upstream encodes each chain's layout as its container elements. The tests check our dialects
against upstream (`test_adapters_upstream.py`). An upstream version bump that changes a
container fails the test and names the chain.

| Chain | Price rows | Promo rows | Stores nesting | Synthetic fixture encoding / container |
|---|---|---|---|---|
| shufersal | `Items/Item` | `Promotions/Promotion` | SAP `asx:abap/asx:values/STORES/STORE`, upper-case fields; `SubChains` also accepted (upstream) | UTF-8 (Stores with BOM), gzip |
| ramilevy | `Items/Item` (`ItemNm`) | `Promotions/Promotion` | `SubChains/SubChain/Stores/Store` | Stores: plain `.xml`, UTF-16 LE with BOM; prices: UTF-8 with BOM, gzip |
| osherad | `Items/Item` (`ItemNm`) | `Promotions/Promotion` | `SubChains` | Stores: UTF-16 LE with BOM; prices: UTF-8, gzip |
| yohananof | `Items/Item` (`ItemNm`) | `Promotions/Promotion` | `SubChains` | PriceFull: a **zip under a `.gz` name** |
| victory | legacy `Products/Product` (`ChainID` casing, `ManufactureName`, `UnitMeasure`); new source `Items/Item` | legacy flat `Sales/Sale`, one row per item, grouped by PromotionID; new source `Promotions/Promotion` | legacy `Branches/Branch`; new source `SubChains` | legacy: **windows-1255**, `.xml.gz`; new source: UTF-8 |
| hazihinam | `Items/Item` | `Promotions/Promotion` | `SubChains`, `StoreID` casing | Stores: **declared ISO-8859-8 over UTF-8 content** |
| tivtaam | `Items/Item`, or **`NewDataSet/item`** (.NET DataSet export with inline `xs:schema`) | `Promotions/Promotion` | `SubChains` | Stores: UTF-16 BE with BOM, gzip |
| mega | `Items/Item` | `Promotions/Promotion` | `SubChains` (two sub-chains) | Stores: **windows-1255 with no XML declaration** |
| machsanei_hashuk | new source `Items/Item` (`ChainID` casing); legacy `Products/Product` | new source `Promotions/Promotion` (`PromotionID`), falling back to legacy flat `Sales/Sale` (upstream conditional converter) | new source `SubChains` (`StoreID`); legacy `Branches` | UTF-8, `.xml.gz` (Stores with BOM); a `Sales` promo delta under the second chain id in **windows-1255** |
| king_store | `Items/Item` | `Promotions/Promotion` | `SubChains` | Stores: plain `.xml`; PriceFull and Price delta: **gzip under a `.xml` name**; PromoFull: **zip under a `.xml` name** |

The container and row elements are taken from upstream. The encoding and container assigned to
each chain's fixture is **provisional**: it was chosen so that every decoding path runs through
at least one real adapter. Element names match case-insensitively (`ChainId` / `ChainID` /
`CHAINID`), and namespaces are ignored.

There is one known divergence from upstream, kept in `DIVERGENCES` in the upstream test. The
legacy Victory converter reads stores under `<Store>`. We read the BigID `Branches/Branch`
layout and the new-source `SubChains` layout. Confirm this against a real legacy file.

### Field mapping

| Internal field | Source fields |
|---|---|
| `StoreRecord.store_code` / `name` / `address` / `city` | `StoreId`, `StoreName`, `Address`, `City` (any casing). `lat`/`lon` come from `Latitude`/`Longitude` when present and inside Israel's bounding box; otherwise `None`. |
| `ItemRecord.item_code` / `raw_name` / `manufacturer` | `ItemCode`; `ItemName` or `ItemNm`; `ManufacturerName` or `ManufactureName` |
| `ItemRecord.barcode` | `ItemCode` when `ItemType` is not 0 and the code is 8–14 digits; otherwise `None` (internal code) |
| `ItemRecord.quantity` / `unit` / `is_weighed` | `Quantity` (0 becomes `None`), `UnitQty`, `bIsWeighted`/`BisWeighted` = 1 |
| `PriceRecord.price` / `unit_price` / `unit_of_measure` / `observed_at` | `ItemPrice`, `UnitOfMeasurePrice`, `UnitOfMeasure` or `UnitMeasure`, `PriceUpdateDate` (falls back to the file's publish time) |
| `PriceRecord.quantity` / `quantity_unit` | `Quantity` (0 becomes `None`), `UnitQty`: the pack size the loader divides the price by ("Unit prices in real files") |
| `PromoRecord` | `PromotionId`/`PromotionID`, `PromotionDescription`, the item codes (see "Promotions in real files"), start and end (`PromotionStartDateTime`/`PromotionEndDateTime`, or the older start/end date plus hour), `MinQty`, `MaxQty` (0 becomes `None`), `ClubID`/`Clubs/ClubId` |

The full promo row is always kept in `PromoRecord.raw` (its scalar fields, `club_ids`, `layout`,
`groups`, `unapplied`, `min_purchase_amount`, `club_expression`, `confidence`).

### Unit prices in real files (measured 2026-10-21 and 2026-10-08)

`UnitOfMeasurePrice` is a chain's own number and its `UnitOfMeasure` label does not always say what
the number is. Measured on the committed real PriceFull of each chain, 200 rows on 2026-10-21
(`fixtures/<chain>/real/`) and 200 on 2026-10-08 (`data/audit/real-2026-10-08/`): the published
value was compared with `ItemPrice / Quantity` scaled to the label's unit (`Quantity` is in the
unit of `UnitQty`; when that is `לא ידוע`, in the label's own unit: grams for `100 גרם`, kilograms
for `ק"ג`, liters for `ליטר`, milliliters for `100 מ"ל`). "Agree" is within half a cent plus 2 %
(the published price is rounded to two decimals); "x100 low" is a published value 100 times smaller
than its label implies. The table is `tests/test_unit_price_real.py` (`MEASURED`); it runs on every
build.

| Chain | What it publishes, as measured (400 rows, 2 days) | Reading the loader applies |
|---|---|---|
| Rami Levy | `100 גרם` (155 rows) and `100 מיליליטר` (60): **x100 low**, the price of **one gram / one ml**, never per 100. `ליטר` (25), `קילוגרם` (6 + 5 weighed), `יחידות` (147): agree. `2   יחידות` (2 rows, one product): per unit, label wrong. `UnitQty` is `לא ידוע` for weight and volume. | `100 גרם` / `100 מיליליטר` x100 (`PUBLISHED_SCALE`); the rest as labelled |
| Osher Ad | `100 גרם` (179), `ליטר` (47), `ק"ג` (31): agree. `100 מ"ל` (33): **x100 low**, per ml. `יחידה` (54): `Quantity` 0 and a published 0.00 on 50, no unit price at all. 56 weighed rows are labelled `יחידה` (per unit) but are per kg: the published value equals the shelf price. | `100 מ"ל` x100; weighed = shelf price per kg |
| Mega | `100 גרם` (201), `100 מיליליטר` (75), `יחידות` (56), `ליטר` (23), `קילוגרם` (17): agree. `מיליליטר` (12): **x100 high**, the value is per 100 ml. `ליטר 1` with `UnitQty` ליטר (16): the pack is grams (`Quantity` 80 to 686 of chips, spices, canned peas) published per gram under a liter label; 14 of 16 have no sane pack. | `מיליליטר` x0.01; `ליטר 1` with an impossible pack: no unit price |
| King Store | `100 גרם`, `100 מיליליטר`, `1 קילוגרם`, `1 ליטר`, `יחידות`: agree (177 weighed rows `1 קילוגרם`, price per kg, `Quantity` in grams). | as labelled |
| Shufersal | `100 גרם`, `100 מיליליטר`, `1ליטר`, `יחידות`: agree. `מטרים` (2): no unit this system knows. | as labelled |
| Tiv Taam | `100 גרם`, `100 מיליליטר`, `יחידות`: agree; weighed `1קילוגרם` (183). | as labelled |
| Yohananof | `100 גרם`, `100 מיליליטר`, `1ליטר`, `1קילוגרם`, `יחידות`: agree; weighed `1קילוגרם` (130). | as labelled |

Hazi Hinam, Machsanei Hashuk and Victory have no real PriceFull yet (their portals did not answer
from the runner); they are read as labelled until a real file is measured.

**What the loader does** (`smartcart_ingest/unitprice.py`, called from `loader._insert_prices`):

1. A **weighed** item is `kg` with `is_estimated`, and its value is the shelf price (a weighed
   price is per kilogram; every weighed row in the 14 files that publishes a per-kg unit price
   equals it). The published value is only compared.
2. Otherwise the unit price is **computed**: `price / pack size` per 100 g, per 100 ml or per unit,
   when `Quantity` is present and sane (positive; at most 50 kg, 50 l or 10,000 units; in a unit
   that does not contradict the label's dimension). It is `computed` in `LoadResult.unit_price_sources`.
3. The published value is the **fallback** when there is no sane pack size: the label's reading
   times the chain's measured factor (`PUBLISHED_SCALE`: Rami Levy `100 גרם` and `100 מיליליטר` x100,
   Osher Ad `100 מ"ל` x100, Mega `מיליליטר` x0.01), refused (`none`, the shelf price is still
   stored) when the pack size it implies is not 1 g to 50 kg, 1 ml to 50 l. A published `0.00` is
   refused.
4. **Cross-check**: when both exist, the published value is compared with the computed one under
   the chain's reading and the disagreements are counted per class (`off_x100_low`, `off_x100_high`,
   `off_x10_*`, `off_x1000_*`, `other`) in `LoadResult.unit_price_disagreements` and a
   `published unit prices disagree with price / quantity` warning in the log. They are a
   data-quality signal: the price is stored and the file is never quarantined for them. Measured
   after the rules above: 2 rows of 2,800 (Rami Levy's `2   יחידות`), all of them `other`.

A chain's factor is added only with a measurement: `test_the_chain_scales_are_what_the_files_measure`
re-derives `PUBLISHED_SCALE` from the 14 files (the class of at least 90 % of a label's rows, five
or more rows) and fails when a chain is missing or wrong. When the next real file of a chain shows
`unit_price_disagreements` in the log, that is the signal to measure again.

### What the real day's rows showed the loader cannot know (verified 2026-10-22, run 39812688285)

The loader sees a row, never the name, so it cannot tell a wrong `Quantity` from a right one. Measured on
the PriceFull rows of the real day (`services/api/tests/real_unit_rows.py`, every field verbatim); the
loader's reading is right for each file as published, and each one is a wrong or missing size the
precompute settles from the name (docs/optimizer.md, "Packs"):

| Row | What the file says | What the loader stores |
|---|---|---|
| Shufersal, Tiv Taam, Rami Levy, Yohananof toilet paper and paper towels | `UnitQty` and `UnitOfMeasure` `מטרים`: the paper's length (528 for 32 rolls, 0.06 per metre) | no unit price (a length is no unit this system knows); the roll count is only in the name |
| Osher Ad toilet paper, garbage bags, some towels | `Quantity` `0.00`, `UnitOfMeasure` `יחידה`, `UnitOfMeasurePrice` `0.00` | no unit price; the count is missing or in a name cut at 20 characters |
| Rami Levy, Tiv Taam, Yohananof garbage bags | `Quantity` `1.00` `יחידות`, published unit price equal to the shelf price | the shelf price as price per unit (the count is in the name, if anywhere) |
| Tiv Taam `שמן חמניות 1 ליטר` at 10.90 | `Quantity` `100.00`, `UnitQty` `מיליליטר`: 100 ml for a 1 liter bottle (Rami Levy and Osher Ad publish `1.00` `ליטר` for the same barcode) | 10.90 per 100 ml (computed from the file's own size) |
| Rami Levy `סודה מי עדן 1.5 לי` at 2.70 | `Quantity` `9.00` `ליטר`: the six-pack's total for one bottle | 0.03 per 100 ml |
| Osher Ad `מארז מים מינרלים מוג` at 14.90 | `Quantity` `1.32` `ליטר`: 4 x 330 ml of sparkling water, the chain publishes 11.29 a liter | 1.1288 per 100 ml: a correct price of a different product |

No loader rule changes for these: a size the file states is used, and a name-based correction belongs
where the name is read (the precompute and `normalize`).

### Promotions in real files (#47, verified 2026-10-21)

The first real PromoFull files were fetched by the Portal probe from a GitHub runner on
2026-10-21 (runs 39642633971 and 39647593706): Shufersal, Rami Levy, Mega (Yeinot Bitan and
Carrefour), Tiv Taam, Osher Ad, Yohananof and King Store. Victory, Machsanei Hashuk and Hazi Hinam
did not answer from the runner (laibcatalog timed out, Hazi Hinam returned 403), so nothing about
their promo layout is verified. **Verified** below means: shown on those files, by a test in
`services/ingest/tests/test_real_promos.py` or by the probe's full-file profile (seven files of 301
to 2660 promotions each); the files are committed trimmed to 100 promotions, evenly spaced, each
whole.

What the real files showed against the rules this repository started with:

- **Every real file used a different layout from the one the adapters assumed**, and before this
  change the adapters read **100 % of the real promotions as reward `other` with no item code**
  (the probe's first full-file profile: 1358, 2660, 1550, 2246, 658 and 301 promotions, all
  `reward_unparsed`, confidence 0.1, `items_per_promo` 0). The reward is not on the promotion; it is
  on the items, inside groups:

  ```
  Root > ChainID, SubChainID, StoreID, BikoretNo
       > Promotions > Promotion: PromotionID, PromotionDescription, PromotionUpdateTime,
           PromotionStartDateTime, PromotionEndDateTime, PromotionStartHour, PromotionEndHour,
           PromotionDays, RedemptionLimit, MinNoOfItemOffered, ClubID, IsGiftItem,
           AdditionalIsCoupon, AdditionalRestrictions, Remarks, AllowMultipleDiscounts
         > Groups > Group: GroupID, MinPurchaseAmount, DiscountType
           > PromotionItems > PromotionItem: ItemCode, ItemType, RewardType, MinQty, MaxQty,
               DiscountRate, DiscountedPrice, DiscountedPricePerMida, bIsWeighted
  ```

  The file is per store (`StoreID` in the header), so promotions are per store here. Only one store
  per chain was sampled, so whether other stores of a chain carry the same promotions is not known.
  Shufersal's file starts with a UTF-8 BOM and a `Root` element, all seven are gzip.
- **`DiscountedPrice` is the total price for `MinQty` units, and `DiscountRate` is the percentage off
  the shelf price** (verified): for the items whose shelf price is in the same store's PriceFull
  fixture, `DiscountedPrice / MinQty = shelf price x (1 - DiscountRate / 100)` within rounding (21
  items checked in the test, King Store, Osher Ad, Rami Levy and Tiv Taam; in a first, wider check
  over all seven chains every row matched to four decimals but one Mega wine row, 22.43 against
  22.99 percent), and the descriptions that quote a price
  ("3ב11.90", "2 ב 24") quote exactly `MinQty` and `DiscountedPrice`. For weighed items
  (`bIsWeighted` 1) `DiscountedPricePerMida` is the price per kg (King Store "2 kg for 89.90":
  `MinQty` 2, `DiscountedPrice` 89.90, per kg 44.95; "1 kg for 49.90": `MinQty` 0.1, per kg 49.90),
  so `MinQty` of a weighed item is a step, not a pack size.
- **`RewardType`** on an item: `3` is one unit at a price (seen with `MinQty` 1 and with weighed
  items), `10` and `1` are N units for a total (`MinQty` 2 to 8), all three read alike; `2` is a
  percentage (`DiscountRate` is in percent units: 5, 60, 100 is free); `0` is a condition item (a
  trigger, or the all-zeros item code that stands for "any item" in a basket condition); `6` appeared
  once, in a Tiv Taam coupon. What separates `1` from `10` is **not determined** (a guess: `10` is a
  mix-and-match over the group's items, `1` a single item); the adapter does not branch on it.
- **`IsGiftItem` on the promotion is not a 0/1 flag** (provisional rule was `IsGiftItem` = 1 means a
  gift): it holds the quantity (`1`, `2.0000`, `3`) or is empty. The grouped reading ignores it.
- **`PromotionStartHour`/`PromotionEndHour` repeat the time of day of the date-times** in every
  promotion that has them (verified on all seven files); they are not a daily window. `hours` is
  therefore `None` for these files (it used to hold e.g. "00:00-02:59", which would have been read
  as a daily window). Shufersal ends most promotions at `2031-01-01T02:59`, Rami Levy, Mega, Osher Ad
  and Tiv Taam at 23:59, King Store at 00:00 of the end day. King Store's 00:00 is read literally
  (the promotion ends at that instant), which is the safe side: 38 of its 301 promotions end before
  the file's publication time, so the file carries promotions that are over, or its end date is
  inclusive; **not determined**. No promotion started after the file was written.
- **`ClubID` is text, not a code** (the old rule treated any value other than `0` as a club, so
  every Shufersal and Tiv Taam promotion was club-only): `0`, `0 - כלל הלקוחות` (everyone),
  `1 - המועדון החדש` (Tiv Taam's club: code, dash, name), and expressions: Mega
  `(2=מועדון קרפור אשראי|2=מועדון אפליקציה)`, King Store `("לקוחות הקפה=3" | "מועדון לקוחות=3" | ...)`
  (18 groups), Rami Levy `((2=...))&(3=...|3=...)`, Shufersal `3 - <23 club names joined by &>` (12 distinct, quoted under "Club promotions").
  `parse_club` reads these (see its docstring): code 0 is everyone; otherwise the label after
  the dash is the club name; an expression lists its distinct club names joined by ` | `, cut at 120
  characters, the full text kept in `raw`. That is the text-level reading; which club a person has to
  be in is decided by the per-chain table (see "Club promotions": `resolve_clubs(values, chain_id)`
  stores a rule over club labels, `&` kept, no cut). Club promotions are 22 % of King Store's, 62 % of
  Tiv Taam's ("המועדון החדש") and 2 % or fewer of the others'.
- **Promotions that are read but not applied** (new: `raw.unapplied`, reward `other`, confidence 0.1,
  the reason also in `confidence_reasons`), because applying them as a shelf discount would show a
  price nobody gets: `coupon_required` (`AdditionalIsCoupon` 1: 12 % of Rami Levy's promotions, 9 % of
  Shufersal's, 5 % of Mega's, under 2 % elsewhere), `basket_condition` (a group with `MinPurchaseAmount`,
  "מעל 75", or the all-zeros item: 148 of Rami Levy's 2660, 25 of Mega's 1550, 25 of Yohananof's
  1199), `multi_group` (more than one group that is not a same-item pair: a reward for another
  product than the trigger, three groups, quantities of a price-only reward such as "1+3"; the
  two-group "1+1", "2+1" and "second at 50 %" shapes are applied now, see "Two-group promotions"
  below), `weekday_restricted` (`PromotionDays` other than all seven days; the numbering of the
  days is **not known**: no promotion in the seven full files has one, see below),
  `packaging_credit` (a description of the form "זיכוי אריזה"/"קיזוז אריזה": a weight adjustment at
  the till with a 1 to 4 percent reward, Tiv Taam and Yohananof), `reward_type_unhandled`,
  `reward_value_unusable` (no price, or a percentage that is not between 0 and 100) and
  `reward_values_differ` (items of one promotion with different prices), and for two-group pairs
  `redemption_limited` (a `RedemptionLimit` above 0, which is applied nowhere),
  `club_in_description` (the description names a club while `ClubID` says everyone) and
  `pair_description_disagrees` (the words contradict the fields). Across the seven full files
82 % (Rami Levy) to 100 % (King Store) of the promotions are applied; with the two-group pairs,
  Rami Levy 2179 of 2660 (was 2163), Shufersal 1232 of 1358 (1218), Mega 1446 of 1550 (1439), Tiv Taam
  2226 of 2246 (2187), Yohananof 1144 of 1199 (1138), Osher Ad 655 of 658 and King Store 301 of 301
  unchanged (probe runs 39663328336 and 39665275662, 2026-10-21; Shufersal's run 39665275662 file
  is the 1358-promotion one, run 39663328336 happened to fetch a one-promotion file).
- **Reading of an applied promotion** (one group, real item codes, no coupon, no basket condition):

| Items | `reward_type` | `reward_value` | `min_qty` |
|---|---|---|---|
| `RewardType` 1, 3 or 10, `MinQty` above 1 | `bundle` | `DiscountedPrice` (the total) | `MinQty` |
| the same, `MinQty` 1 or less, not weighed | `price` | `DiscountedPrice` | `MinQty` |
| the same, weighed, `MinQty` above 1 (kg) | `bundle` | `DiscountedPrice` | `MinQty` |
| the same, weighed, `MinQty` 1 or less | `price` | `DiscountedPricePerMida` (per kg) | 1 |
| `RewardType` 2 | `percent` | `DiscountRate` in percent units | `MinQty` (below 1: 1) |

  Item codes are those of the group items (all-zeros removed); promotions with a coupon or condition
  still link their items. `RedemptionLimit`, `MinNoOfItemOffered` (10, 1 or empty: meaning **not
  known**), `AllowMultipleDiscounts` and `max_qty` are stored in `raw` and not applied anywhere.

**Two-group promotions: "buy X, get Y at P % off"** (new; verified on the full files of Shufersal,
Rami Levy, Mega, Tiv Taam and Yohananof, run 39663328336 and the one before it, 39660333324;
`grouped_terms` → `_pair_terms`, tests in `test_promo_pairs.py`, the real counts in
`test_real_promos.py`). Every `multi_group` promotion in the seven full files was classified by a
signature (groups, `RewardType`, quantities, rate, how the groups' item sets relate; the probe prints
them as `PROMO_SHAPES`). The shapes, with what each is and what is done:

| Shape (full files) | Meaning | Done |
|---|---|---|
| trigger group `RewardType` 0 (`MinQty` 1) + reward group `RewardType` 1 or 10, rate 100, price 0, same items: "1+1" (Shufersal 13, Tiv Taam 10, Yohananof 6, Rami Levy 6, Mega 3) | buy one, get one free | **applied**: `buy_x_get_y`, `min_qty` 1, `reward_value` 1, `raw.get_percent` 100 |
| the same with `MinQty` 2 on the trigger: "2+1 הזול מבניהם" (Rami Levy 7, Shufersal 1) | buy two, the cheapest of the three free | **applied**: `min_qty` 2, `reward_value` 1 |
| trigger (`MinQty` 1) + reward `RewardType` 10, rate 40 to 70, price = trigger price x (1 - rate), items equal or the reward group larger: "השני ב 50%" (Tiv Taam 31, Rami Levy 3, Mega 4) | buy one, the second at P % off | **applied**: `buy_x_get_y`, 1 and 1, `raw.get_percent` P |
| a trigger group with the all-zeros item and `MinPurchaseAmount`, or a reward group with it ("מעל 75"; `basket_condition` is 148 of Rami Levy's promotions, 11 of Shufersal's, 25 of Mega's and 25 of Yohananof's, two-group or not) | a basket threshold | unapplied: `basket_condition` (as before) |
| the same groups with `AdditionalIsCoupon` 1 (Mega's "פיצוי ..." compensation coupons, Shufersal's `20ש - קופון ח"ע` series) | a coupon | unapplied: `coupon_required` |
| price-only rewards with no rate ("1+3 חינם הזול מביניהם", "1+2", Yohananof 2) | unknown semantics | unapplied: `multi_group` |
| `RewardType` 6 in both groups (Tiv Taam "קופון 25 ש\"ח הנחה"), an empty trigger group (Osher Ad "חלון מכירת שקיות"), three groups | coupons, bag sales | unapplied: `multi_group` |
| rate 65 with description "ב35% הנחה" (Yohananof 1), one more in Tiv Taam | the words say 35 % off, the price says 65 % off | unapplied: `pair_description_disagrees` |

What makes a pair applied (every condition; otherwise the promotion keeps its reason): exactly one
trigger group (all items `RewardType` 0, real item codes) and one reward group (`RewardType` 1, 2, 3
or 10, with `DiscountRate` and `DiscountedPrice`); nothing weighed; whole-number `MinQty` X and Y
(1 to 10) which are free only for rate 100 and reward price 0, and exactly 1 and 1 for a percentage
off; one rate for all items; with the trigger's `DiscountedPrice` present the reward price equals
`trigger x (1 - rate / 100)` within an agora; no redemption limit; no coupon, no basket condition,
no weekday restriction; the description names no other `N+M` than X+Y and no other percentage than
the rate (a fat percentage in a product name does not count); and it does not name a club while
`ClubID` says everyone. Only the items that are in both groups are linked: such an item pairs with
itself, which is true however the store lets a pair mix products; items only in the reward group
(Tiv Taam: 2 of 35) need a trigger of another item, are counted in `raw.reward_only_items` and are not
linked. The reading is `buy_x_get_y` with `raw.get_percent` P (the percentage the "got" units are
off; 100 is free), so the effective price per pack is `shelf x (X + Y (1 - P/100)) / (X + Y)`, needed
`X + Y` packs, in the precompute, `/compare` and the MILP (docs/optimizer.md).

What is **verified**: the structure (trigger group at the shelf price, reward group at rate and price)
and the arithmetic `reward = trigger x (1 - rate / 100)` on every promotion of the fixtures
(`test_promo_pairs.py`, `test_real_promos.py`), and **against the stores' own shelf prices** (the
probe's `shelf_check`, run 39665275662, for the chains whose PriceFull is for the promotion file's
store): Tiv Taam 708 of 708 reward items cost `shelf x (1 - rate / 100)` and 708 of 708 trigger
prices equal the shelf price, Rami Levy 157 of 157 and Mega 37 of 37 reward prices (their trigger
groups carry no price), no mismatch. (Shufersal's and Yohananof's PriceFull files of that run were
for other stores; the probe now fetches the PriceFull of the PromoFull's own store, and all seven
chains are in "Shelf check against the same store" below.) The descriptions agree
with the fields ("1+1", "2+1", "השני ב 50%", "השני בחצי"); **Tiv Taam writes the price percentage**:
"השני ב 40%" is a reward of rate 60 (the second costs 40 % of the shelf price; 15 promotions, 40 /
60 / 70 against rates 60 / 40 / 30, all complementary), so a percentage without the word "הנחה" is
read as the rate or as `100 - rate`, and with "הנחה" as the rate only (Yohananof "ב35% הנחה" on a
rate of 65 stays unapplied, 1 promotion). What is **not determined**: whether the pair may mix
products of the group. For "2+1 הזול מבניהם" ("the cheapest of them") the description says it does,
for the others the file does not; the adapter applies only the same-item reading and the MILP's
mixed-pair rule is a lower bound (docs/optimizer.md), so a promo with more than one item has
confidence 0.9 (`mixed_items_unverified`). The meaning of `MinNoOfItemOffered` (10 everywhere) and of
`AllowMultipleDiscounts` is still not known. Rami Levy's and Mega's trigger groups carry no price
(`MinPurchaseAmount` is `0.00`, not a threshold), so there the reward group's rate and price are all
the file shows.

**Shelf check against the same store** (**verified**, probe run 39681477048, 2026-10-21, whole
files, not the trimmed fixtures). A promotion's prices can only be compared with the shelf prices
of its own store, and for Shufersal and Yohananof the PriceFull and the PromoFull the probe had
fetched were for different stores. The probe (`scripts/unblock/portal_probe.py`, `fetch_chain`) now
takes the largest of the first ten PromoFull files the portal lists and then asks the scraper for
the PriceFull of **that store** (`store_id`, the store code in the file name); the manifest of every
chain's fixtures records the numbers (`full_file` of the PromoFull entry). The first check is for
one-group promotions (`DiscountedPrice / MinQty` against the shelf price, not weighed, with a
rate); the second for trigger and reward pairs (reward price against `shelf x (1 - rate / 100)`,
trigger price against the shelf price):

| Chain (store) | Promotions in the file | One-group items with a shelf price | price = `shelf x (1 - rate)` to the agora | within the rate's rounding | below the shelf price | Pairs: reward / trigger price equal |
|---|---|---|---|---|---|---|
| Shufersal (39) | 1408 | 2251 | 1477 | 2172 | 2251 | 61 of 61 / 61 of 61 |
| Yohananof (5) | 1241 | 2108 | 760 | 2108 | 2108 | 70 of 70 / 70 of 70 |
| Rami Levy (3) | 2676 | 5753 | 5474 | 5515 | 5751 | 1 of 1 / (trigger group has no price) |
| Mega | 1653 | not checked: the PriceFull named for store 416 carries `StoreId` 134 inside | | | | earlier run 39665275662: 37 of 37 rewards |
| King Store (31) | 516 | 505 | 490 | 505 | 502 | none |
| Osher Ad (3) | 798 | 2113 | 1845 | 1915 | 2113 | none |
| Tiv Taam (2) | 2245 | 2391 | 438 | 2117 | 2390 | 707 of 707 / 707 of 707 |

"Within the rate's rounding" allows half a percentage point of the shelf price plus two agorot,
because Shufersal, Yohananof and Tiv Taam publish whole-percent rates (Tiv Taam's 438 exact ones
against 2117 is that); Rami Levy and Osher Ad publish two-decimal rates (seen in the logged
examples). What this shows: every checked pair price is exactly the shelf price or the shelf price
times `1 - rate` (839 reward and 838 trigger prices over four chains, no mismatch), and a
promotion's unit price is below the shelf price on 15,115 of the 15,121 one-group items checked (2
Rami Levy, 3 King Store and 1 Tiv Taam item are at or above it; which ones is not logged). What it
does **not** show: the 79 Shufersal, 238 Rami Levy, 198 Osher Ad and 274 Tiv Taam items outside the
rate's rounding are not wrong prices. The eight logged examples per chain are of two kinds:
promotions where one price covers several items with different shelf prices (mix-and-match: Rami
Levy "3 for 20" over items of 7.50 to 7.90, Osher Ad "4 for 11" over items of 3.50 to 3.90), where
`DiscountRate` cannot be a per-item percentage, and single items whose whole-percent rate is a loose
rounding of the real one (Shufersal: rate 5 on a 14.90 shelf price gives 14.46, which is 2.95 %).
That is **inferred** from the logged examples, not checked on all of them. The app uses
`DiscountedPrice`, never the rate, so these items do not move a price. The Mega gap is a file quirk to look at (a PriceFull whose file
name and header disagree on the store), not a result.

**Weekday-restricted promotions** (`PromotionDays`): none of the 9972 promotions of the seven full
files has a value other than empty or `1,2,3,4,5,6,7` (Osher Ad's two list all seven), so the day
numbering (Sunday = 1 as in Israeli systems, or Monday = 1 as in ISO) **cannot be pinned from real
data**, and a promotion with a restriction keeps `weekday_restricted`, unapplied, with a test on an
inline file. If a chain publishes one, the day numbering needs a promotion whose description names
the day ("יום שלישי") before it is applied.

**Still provisional** (no real file has shown it): the **older layouts**, the one the synthetic
fixtures use (`PromotionItems/Item` with `MinQty`, `DiscountedPrice`, `DiscountRate`,
`DiscountType`, `AdditionalGiftCount` and `IsGiftItem` on the promotion) and the legacy flat
`Sales/Sale` rows, which the three unreachable chains may still publish; their mapping below is
unchanged and unverified. In that older layout `buy_x_get_y` comes from `IsGiftItem` 1 or
`AdditionalGiftCount` above 0 (no real promotion maps to it that way); the real files' "1+1" and
"second at 50 %" reach the same reward type through the two-group reading above. Whether `v2` is this grouped layout is not known: none of
the real promo files carries a `SchemaVersion`, so they are all `v1` by the container rule.

| Condition (older layout only, provisional) | `reward_type` | `reward_value` |
|---|---|---|
| any `IsGiftItem` = 1, or `AdditionalGiftCount` > 0 | `buy_x_get_y` | gift count (default 1) |
| `DiscountedPrice` present and `MinQty` > 1 | `bundle` | `DiscountedPrice` as published |
| `DiscountedPrice` present, `MinQty` ≤ 1 | `price` | `DiscountedPrice` |
| `DiscountType` = 2 with a `DiscountRate` | `percent` | `DiscountRate` as published |
| otherwise | `other` | `None` |

The effective-price precompute (`services/api/smartcart_api/precompute.py`, `fold_promo`) agrees with
the verified reading for `price`, `bundle` (value is the total, divided by `min_qty`) and `percent`
(a percentage). It keeps two guards for the unverified older layout that the real files do not need:
a bundle value below one shelf price is read as a per-unit price, and a percentage of 1 or less as a
fraction; both can only understate a saving on a real file. `max_qty`, redemption limits and
`PromotionDays` are not applied. Club matching is described in "Club promotions" below.

### Club promotions

`ClubID` is free text in the real files, so a promo's club cannot be matched by a code. The
ingest turns the text into a **rule over club labels** with a per-chain table, and the API
evaluates the rule against the club ids the person marked in their profile. Everything below is
**verified** on the seven committed real PromoFull files (`services/ingest/tests/fixtures/<chain>/real/`,
trimmed to 100 promotions each) unless it says otherwise.

**The distinct `ClubID` values, per chain** (promotions of the 100 kept per file):

| Chain | `ClubID` value | Promos | What it is |
|---|---|---|---|
| all seven | `0`, `0 - כלל הלקוחות` | 41 to 100 | everyone: not a club promo |
| Tiv Taam | `1 - המועדון החדש` | 59 | the chain's club (code, dash, name) |
| Yohananof | `1 - מועדון עובדים` | 2 | staff club |
| King Store | `("לקוחות הקפה=3" \| "מועדון לקוחות=3" \| "HEBREW=3" \| "ARABIC=3" \| "לקוחות אתר קניות=3" \| "מיתר=3" \| "לקוחות סיטונאים=3" \| "עובדי קינגסטור -ARABIC=3" \| "עובדי קינגסטור -HEBREW=3" \| "טסט הנחות=3" \| "לקוח גדול=3" \| "עובדי סוא=3" \| "בעלים=3" \| "לקוחות רכבים=3" \| "ואדי אלג'וז CASHBACK=3" \| "לקוחות פרידיס=3" \| "לקוחות הקפה שוברים=3" \| "עמותת אפדל אלעולום=3")` (353 characters; 15 promos), the same with `\| "לקוחות סיטונאים סניפים=3"` added (382 characters; 3 promos) | 15 + 3 | any of 18 customer groups, `<name>=<type 3>`; only "מועדון לקוחות" is the consumer club, the rest are internal groups (wholesale, staff, a test group, owners, ...) |
| King Store | `("לקוחות סיטונאים=3" \| "לקוחות סיטונאים סניפים=3")` | 3 | wholesale customers |
| Rami Levy | `(1=מועדון חברתי\|1=מועדון שיווק   השקמה\|1=מועדון לקוחות אשראי\|1=מועדון נטען\|1=לקוחות ארנק)` | 1 | any of five clubs (note the three spaces inside the second name) |
| Rami Levy | `((1=מועדון שיווק   השקמה\|1=מועדון לקוחות אשראי))&(3=ישראכרט מגנטי\|3=תווי זיכוי מימוש\|3=עיגול אגורות)` | 1 | one of two clubs **and** one of three payment options |
| Mega | only `0` in the committed file; the whole file (1653 promotions, probe run 39681477048) also has `(2=מועדון קרפור אשראי\|2=מועדון אפליקציה)` (6) and `(3=Goodi)` (4), neither in a committed fixture | | any of a credit-card club and the app club; "Goodi" is not understood and stays unmapped |
| Shufersal | only `0 - כלל הלקוחות` in the committed file; the whole file of store 39 (1408 promotions) has it on 1407 and one more text, quoted below | 1 | a list of 23 club names joined by ` & `, 12 distinct |
| Osher Ad | only `0` | | |
| Victory, Machsanei Hashuk, Hazi Hinam | no real file (their portals did not answer from the runner) | | |

The number in `<type>=<name>` is a club type. Which type goes with what is **not determined**
(Rami Levy puts its clubs under 1 and its payment options under 3, Mega its clubs under 2, King
Store its groups under 3), so the mapping ignores the type and matches on the name.

**Shufersal's club text, verbatim** (probe run 39681477048, the PromoFull of store 39, 1 of 1408
promotions; 447 characters; the file does not say what a club promotion of another store holds, so
more texts are likely; the probe now logs every distinct `ClubID` text of the file it fetched as
`PROMO_CLUBS` lines, and the manifest keeps them whole):

```
3 - מועדון לקוחות & עמותת לשובע-אשראי & מועדון עובדים אשראי & מועדון לקוחות אשראי & מועדון עובדים אשראי & מועדון לקוחות פ משולב & עובדי בי"ח תה"ש-משולב & בי"ח משולב(בלנס/השרון/שנ & ארגון עובדים משולב & מועדון לקוחות אשראי & מועדון לקוחות אשראי & הקרן לידידות-אשראי & מועדון לקוחות-אשראי & אקים-משולב & מועדון לקוחות & מועדון לקוחות & מועדון לקוחות & הקרן לרווחה-אשראי & מועדון לקוחות & מועדון לקוחות & מועדון לקוחות & מועדון לקוחות & מועדון לקוחות
```

| Distinct name in the list | Times | In the table | Kind | Why |
|---|---|---|---|---|
| מועדון לקוחות | 9 | no | | generic ("customer club"); repeated under what are probably different club ids, so which club it is is not known |
| מועדון לקוחות אשראי, מועדון לקוחות-אשראי | 4 (3 and 1) | `shufersal:credit` | card | the credit-card club; the hyphenated spelling is read as the same club (**inferred**) |
| מועדון עובדים אשראי | 2 | `shufersal:staff_credit` | card | the employees' credit-card club (**inferred** from the words) |
| עמותת לשובע-אשראי, הקרן לידידות-אשראי, הקרן לרווחה-אשראי | 1 each | no | | credit-card groups of one association or fund each: organisation-specific, they would fill the profile picker for no one |
| מועדון לקוחות פ משולב, עובדי בי"ח תה"ש-משולב, בי"ח משולב(בלנס/השרון/שנ, ארגון עובדים משולב, אקים-משולב | 1 each | no | | "combined" groups of one organisation or hospital each (the third name is cut at 25 characters by the chain) |

**How the list is read is inferred, not verified**: the names are joined by `&`, but nobody can be
in a dozen different card clubs at once, so the table reads the list as **any of** (`label_separator`
in the chain's entry). If the chain meant "all of", a person holding one card would be shown a
price the till refuses; only two names are mapped, so that is the whole exposure, and a list with
no mapped name is `אחר` and matches nobody (never a plain name that the older chain-own-club rule
could meet). The text of the one promotion therefore becomes `מועדון עובדים אשראי | מועדון לקוחות
אשראי`.

**The mapping** is `services/ingest/smartcart_ingest/adapters/chain_clubs.json`, read by
`adapters/clubs.py`. Per chain it lists the clubs a person can pick, each with a stable id
(`<adapter slug>:<name>`), a Hebrew label, a kind (`club`, `card` for credit and payment cards,
`staff`, `other`) and the exact `ClubID` names it covers (compared after trimming, collapsing spaces
and case-folding; the label counts as a name too):

| Chain | Club id | Label | Kind | `ClubID` names |
|---|---|---|---|---|
| King Store | `king_store:club` | מועדון לקוחות | club | מועדון לקוחות |
| | `king_store:wholesale` | לקוחות סיטונאים | other | לקוחות סיטונאים, לקוחות סיטונאים סניפים |
| | `king_store:staff` | עובדי קינגסטור | staff | עובדי קינגסטור -ARABIC, עובדי קינגסטור -HEBREW |
| Rami Levy | `ramilevy:club` | מועדון רמי לוי | club | מועדון שיווק השקמה |
| | `ramilevy:social` | מועדון חברתי | club | מועדון חברתי |
| | `ramilevy:credit` | מועדון לקוחות אשראי | card | מועדון לקוחות אשראי |
| | `ramilevy:topup` | מועדון נטען | card | מועדון נטען |
| | `ramilevy:wallet` | לקוחות ארנק | card | לקוחות ארנק |
| | `ramilevy:isracard` | ישראכרט מגנטי | card | ישראכרט מגנטי |
| | `ramilevy:vouchers` | תווי זיכוי מימוש | card | תווי זיכוי מימוש |
| | `ramilevy:multipass` | מולטיפס תו רמי לוי | card | מולטיפס תו רמי לוי |
| Shufersal | `shufersal:credit` | מועדון לקוחות אשראי | card | מועדון לקוחות אשראי, מועדון לקוחות-אשראי |
| | `shufersal:staff_credit` | מועדון עובדים אשראי | card | מועדון עובדים אשראי |
| Mega | `mega:app` | מועדון אפליקציה | club | מועדון אפליקציה |
| | `mega:credit` | מועדון קרפור אשראי | card | מועדון קרפור אשראי |
| Tiv Taam | `tivtaam:new` | המועדון החדש | club | המועדון החדש |
| Yohananof | `yohananof:staff` | מועדון עובדים | staff | מועדון עובדים |

What is **inferred, not verified**: that "מועדון שיווק השקמה" is Rami Levy's own club (it is the
chain's legal name; the label says "מועדון רמי לוי"), what "מועדון נטען", "לקוחות ארנק" and
"מועדון חברתי" are, that "מולטיפס תו רמי לוי" (new in run 39681477048, a payment option under type
3 like the vouchers) is the Multipass voucher, and everything said about Shufersal above. Not mapped
on purpose: King Store's internal groups (HEBREW, ARABIC, test, owners, vehicles, an association,
...) and its "לקוחות מועדון" and "לקחות פרידיס" (a variant and a misspelling, each on a few
promotions that name the 18 groups anyway), "עיגול אגורות" (rounding to the agora is a payment
option, not a membership), Mega's "Goodi", and the nine Shufersal names in the table above. The
owner's list of to-dos is `smartcart-ingest clubs-report [--unmapped]`: every
`ClubID` text of the loaded club promotions, the rule it became, and the names the table does not
know. Add a name to a club (or a new club) in `chain_clubs.json` and the next load of that
chain's PromoFull file picks it up.

**The rule** (`promos.club_name`, no schema change; migration `20261022100000_club_rules.sql`
resets rows the older ingest flattened): the label of the club, `A | B` (any of), `A & B` (all of),
with brackets, e.g. Rami Levy's AND text is stored as
`(מועדון רמי לוי | מועדון לקוחות אשראי) & (ישראכרט מגנטי | תווי זיכוי מימוש)`. How a `ClubID`
becomes a rule (`resolve_clubs(values, chain_id)`):

- `0` and `0 - כלל הלקוחות` are everyone: `club_only` stays false.
- `<n> - <name>` is one name, whatever characters it holds, except for a chain whose entry has a
  `label_separator` (Shufersal, `&`): its label is a list of names read as any of (inferred, see
  above). `clubs-report` splits it the same way, so it lists the nine unmapped names, not one
  447-character name.
- A boolean expression is parsed (`|` any of, `&` all of, brackets, double-quoted names; `&` binds
  tighter than `|`), and each `type=name` or `"name=type"` is looked up in the chain's table.
- **Unknown matches nobody.** An unknown alternative of an `|` is dropped (it could never be
  true); an unknown part of an `&` makes the whole rule unknown; a rule with no known name is
  stored as `אחר`, or as the name itself when it is one plain name (so the owner sees it); `אחר`
  and a text that does not parse are never satisfied. A chain with no table (Osher Ad, and
  the three whose portals did not answer) can never match.
- Several club values on one promotion must all hold (`A & B`): the safe reading, since the files
  do not say whether they are alternatives. A bare numeric code (`1`) keeps the older fallback
  name of `CLUB_NAMES`.

The API side is in docs/api.md ("Club filtering"). Tests: `test_club_rules.py` (real strings of the
fixtures: a member gets the promos, a non-member none, everyone, either side of an `|`, an AND needs
one of each, unknown matches nobody, the report), `test_api_clubs_real.py` (real text, through
the stored rule and the precompute, to /compare for a person holding club ids),
`test_api_club_migration.py`.

### Promo parse confidence (#12, #102)

Every adapter records how sure it is that it read a promo's terms right: `PromoRecord.raw`
(stored in `promos.raw`) gets `confidence`, a number in [0, 1], and `confidence_reasons`, the
deductions that apply. It is computed once, in `RegulationAdapter._promo_record` through
`promo_parse_confidence` (`adapters/_common.py`), so every chain module inherits it. The API shows
it as `PricedItem.promo_confidence` on /compare and /optimize (`basket.promo_confidence` reads
`promos.raw->>'confidence'`) and as `PromoWindow.confidence` on the price history.

| Situation | Confidence | Reason recorded |
|---|---|---|
| reward type, quantity (`MinQty`) and value (`DiscountedPrice`, `DiscountRate`; older layout: `DiscountRate` with `DiscountType` 2, or `AdditionalGiftCount`) all explicit, description consistent | 1.0 | none |
| `MinQty` missing: the quantity (buy X) defaults to 1 | minus 0.2 | `min_qty_missing` |
| `buy_x_get_y` known only from `IsGiftItem`: "get Y" defaults to 1 | minus 0.2 | `gift_count_inferred` |
| no end date | minus 0.1 | `end_date_missing` |
| a two-group pair whose group has more than one item: whether a pair may mix products is not shown | minus 0.1 | `mixed_items_unverified` |
| the description contradicts the reward: an `N+M` pattern on a promo that is not `buy_x_get_y`, a percentage written as a discount ("20% הנחה", "50% על השני", "ב-60%") on one that is not `percent`, or an `N ב P` ("3ב11.90") on a `bundle` whose price is neither `P` nor `P` per `N` units | minus 0.3 | `description_disagrees` |
| read but not applied (coupon, basket condition, two groups, weekday restriction, packaging credit, unusable or differing values; see "Promotions in real files") | 0.1 | the reason (`coupon_required`, `basket_condition`, `multi_group`, ...) |
| no explicit reward field at all (`reward_type = other`, never applied to a price) | 0.1 | `reward_unparsed` |

Deductions add up (at most 0.8), so a parsed promo always scores above an unparsed one (lowest
0.2). The reward is **never** inferred from the description text; the description only lowers the
confidence when it disagrees with the explicit fields (and a "packaging credit" description blocks
a reward). Checked on the real files: a bare `%` in a description is nearly always a product
attribute (3.6 % milk fat, 100 % juice, 25 % cream cheese: 6 of the 12 descriptions with a
percent sign in the committed samples), so only a percentage written as a discount counts; the `N ב P` cross-check agrees with
the fields on 99 % of the descriptions that quote a price (Rami Levy, Osher Ad, Tiv Taam, King
Store; Mega's descriptions name the product only) and flags the rest, mostly deposit-inclusive
prices ("3ב24.10 פקדון בירה" with `DiscountedPrice` 25.00, Shufersal) and a few real mismatches
("3 ב 25.9" with 25.00). The rubric is still provisional for the older layout: whether `MinQty`
counts the gift item (does `MinQty` 2 with one gift mean 1+1 or 2+1?) is open, and no real
promotion is a `buy_x_get_y`. The synthetic fixtures' four standard promos all score
1.0 (`services/ingest/tests/test_promo_confidence.py`; end to end through the loader, the
precompute and /compare in `services/api/tests/test_adapter_promo_confidence.py`).

## Schema versions (#57)

The consumer authority is rolling out an improved reporting model through 2026 (**verified**,
from its 2025 annual report). The timing per chain is **not verified**. Every file is
classified as one of:

- **`v1`**: the current 2015 regulation format. The file declares no version of the reporting
  model, its containers are in no XML namespace, its root points at no XSD, and it contains at
  least one container element this chain is known to use. A container outside the chain's
  dialect (for example, Shufersal suddenly publishing `<Products>`) is treated as unknown
  rather than guessed.
- **`v2`**: the new model. No specification and no real new-model file could be reached (see
  "What was found", below), so the marker is a **provisional** placeholder kept in one
  constant, `PROVISIONAL_V2_MARKER` in `adapters/_common.py`: a root attribute or header
  element named `SchemaVersion` whose major version is `2`. Change it there, and only there,
  when the first real file arrives. There is **no v2 field mapping**: a file the placeholder
  calls `v2` goes through the v1 mapping, and one that renames a field fails loudly on the
  first row (`missing ItemCode`, test `test_a_new_model_that_renames_the_rows_fails_loudly_not_silently`).
- **`unknown`**: anything else. `parse` raises `UnknownSchemaError` (a subclass of
  `AdapterError`), so the file is never loaded (`file_tracking` status `failed`, reason
  `unknown schema: ...`), one `unknown_schema` alert names the chain, and the message says
  why (`SchemaVersion='3.1': major '3' is not '2'`, `the header declares a reporting-model
  version this adapter does not know (modelversion='4.0')`, `the root points at an XSD`, `a
  container is in an XML namespace (...)`, `no container this chain uses (found: ...; expected
  one of: ...)`).

Detection is deliberately one-sided (`read_schema` in `adapters/_common.py`): every signal of
a different model ends in `unknown`, never in `v1`. In order: (1) the `SchemaVersion` marker
decides alone (major `2` is v2; any other value, an empty one included, is unknown); (2) any
other declared model version (`ModelVersion`, `FormatVersion`, `ReportVersion`,
`ReportingVersion`, `SpecVersion`, `XsdVersion`, as a root attribute or a header field, any
case; this name list is an **estimate**, it is `UNSUPPORTED_VERSION_FIELDS`), a root
`schemaLocation` / `noNamespaceSchemaLocation`, or a namespace on the container elements makes
it unknown; (3) otherwise v1 if a known container is present. `XmlDocVersion` and `DllVerNo`
are **not** signals: they are the issuing software's version stamps in older dialects
(**upstream**: they are in the parser's `ignore_column` lists for Hazi Hinam, Confix, City
Market, Salach Dabach and Tiv Taam) and no real file of 2026-10-21 carries either, so they
neither reject nor promote a file; the probe reports them. A bare `xmlns:xsi` declaration (the
parser's 2024 sample files of chain 7290172900007 have one) does not count as a namespace; the
SAP Stores dialect's `asx:abap` root namespace does not either, because only the containers are
checked. Tests: `services/ingest/tests/test_schema_detection.py` (204 cases across all ten
adapters, the real files and one end-to-end Scheduler run).

Both versions map to the same internal model through the same code path. A test parses a v1
and a synthetic v2 Shufersal PriceFull and checks that the item and price records are equal.
**No downstream code branches on the schema version**: quality gates, the loader and the
dashboard see only internal records. The version is recorded in `RawFile.schema_version`, so
`file_tracking` can store it.

**Noticing the first real v2 file.** `portal_probe.py gate` prints one `SCHEMA {...}` line per
chain (files per detected schema: `v1`, `v2`, `unknown`, `unreadable`, plus declared versions,
namespaces and the not-v1 files with the adapter's reason) and one `SCHEMA_TOTAL {...}` line
(totals and `chains_not_all_v1`) on stderr, and the report gets a "Files per detected schema
(#57)" table. It is computed by `adapter.inspect_schema(bytes)` before any gate, so a file the
adapters refuse is counted too. When a chain has a `v2` or `unknown` file the table opens with a
bold line naming the chain; the file is in the `portal-probe-files` artifact for 7 days. A
corrupt download is counted as `unreadable` and listed, but is not flagged as a new model. The
real fixtures are pinned by `test_every_real_file_is_v1_and_declares_no_version`: the day a
re-fetched real file carries a marker, that test names it.

Known differences in the new model, as listed in `docs/product-and-market.md` (**verified** that
the authority announced them; the file-level details are **not yet known**):

| Announced change | Expected effect on adapters |
|---|---|
| Uniform promo definitions | The real files (2026-10-21) already carry an explicit `RewardType` per item, but not on a `SchemaVersion` marker; see "Promotions in real files". Whether that is the announced model is not known. |
| Item-and-store accuracy | Possibly per-store item identity or stricter store codes. Store-code normalization stays. |
| AI for substitutes | Possibly new substitute or category fields. Extra fields are ignored today; nothing reads them until a specification says what they are. |

### What was found (research for #57, 2026-10-22)

**Result: no official specification and no real new-model file was reachable, so no v2 parsing
path was written.** A v2 mapping built without either would be a guess dressed as code; the
work stopped at making detection safe and the first real file noticeable (above). Every claim
below is marked **verified** (read by us from a primary source or a real file) or **estimate**
(secondary, snippet only, or inference).

What could not be reached, precisely. This session's egress proxy refuses every Israeli host
(`CONNECT` answered 403; the fetch tool could not resolve them): `www.gov.il` (the authority's
regulations page and its reports), `www.nevo.co.il`, `fs.knesset.gov.il`, `www.chamber.org.il`,
`www.ice.co.il`, `www.hon.co.il`, `www.globes.co.il`, `data.gov.il`, `www.odata.org.il`. So the
authority's own publications were not read. GitHub's API and the issue trackers of the two
upstream projects were not readable either (the session has no GitHub access to them; the one
issue search that ran returned 0 hits, which is not evidence that there are none), so upstream
was read from public git clones and PyPI only.

| # | Source (date read 2026-10-22) | What it says about a new schema | Status |
|---|---|---|---|
| 1 | `israeli-supermarket-scarpers`, public clone `https://github.com/OpenIsraeliSupermarkets/israeli-supermarket-scarpers`, HEAD `ee4359f` (2026-10-19), shallow clone of 200 commits (the latest ~40 read in full, the rest searched by subject), PyPI `il-supermarket-scraper` 1.0.17 (2026-10-18) | No commit, README line or code handles a new reporting model or a schema version. The last two months are CI, stability and reachability work. It only downloads files; it does not read their schema. Its README links the authority's regulations page, `https://www.gov.il/he/departments/legalInfo/cpfta_prices_regulations` (the link only; the page was unreachable). | **verified** (absence in the commits read; the older history was not read) |
| 2 | `israeli-supermarket-parsers`, public clone `https://github.com/OpenIsraeliSupermarkets/israeli-supermarket-parsers`, HEAD `2992110` (2026-10-17), shallow clone of 300 commits (the latest ~40 read in full, the rest searched by subject), PyPI `il-supermarket-parser` 1.0.13 (2026-10-17; the project pins 1.0.12, 2026-10-04) | 1.0.12 to 1.0.13 is a CI runner pin only. No schema detection. Version stamps `XmlDocVersion` and `DllVerNo` are ignored columns for five older chain dialects. Commit `398449b` (2026-04-24) says one chain's feed ("VictoryNewSource") "differs from the original Victory source on every file type": a chain-specific dialect, not the authority's model. | **verified** |
| 3 | Our own real files of 2026-10-21 (`services/ingest/tests/fixtures/*/real/`, 21 files, 7 chains, from the probe runs in this document) | No file declares any version, namespace or schema reference; all use the containers of the 2015 format; the promo files already use the grouped `RewardType` layout (see "Promotions in real files"). | **verified** (these 7 chains, that day) |
| 4 | `docs/research/2026-10-market-research-and-product-plan.he.md`, section 2.2, quoting the authority's 2025 annual report ("הטמיעה הרשות בשיתוף הקמעונאים מודל דיווח מטוייב", expected "to continue through 2026") and Dr. Dalia Shilian in Globes ("הגדרה אחידה למבצעים, דיווחים מדויקים ברמת פריט וסניף, ושילוב כלי בינה מלאכותית ... תחליפיים") | That a refined reporting model is being introduced, and its three themes. No file format, field names, version or dates. | verified as a quotation in our research; the primary reports were **not re-read** by us |
| 5 | Web searches in Hebrew and English (6 queries, e.g. "מודל דיווח מטויב", "שקיפות מחירים פורמט חדש", "price transparency XML new schema 2026") | No page announcing, specifying or sampling a new format. Snippets only (not fetched, so **estimate**): the 2014 regulations (`https://www.nevo.co.il/law_html/law00/135376.htm`: files are XML, with field-length tables for Stores and Promo), a 2015 authority field-spec document (`https://www.chamber.org.il/media/148016/1002.pdf`, 7 pages, described as a recommendation), a 2023 ynet article on an authority and Amazon price database (`https://www.ynet.co.il/economy/article/b1q511iwzkg`), and the State Comptroller's 2026 economic report (`https://library.mevaker.gov.il/sites/DigitalLibrary/Documents/2026/Economic-Report/2026-Economic-Report-108.pdf`, consumer protection audit; no format detail seen). | **estimate** (snippets), and the absence of a result is not proof the spec does not exist |

What this means for the adapters: the 2015 format still is what the 7 reachable chains
publish today (**verified**, row 3), the new model is announced but its file-level shape is
unknown (**verified** that it is announced, row 4; the shape is **not known**), and nothing
in the upstream libraries has moved yet (row 1 and 2). The "uniform promo definitions" row
above may already be live in the grouped `RewardType` promo files, but nothing links them to the
announced model, so they stay `v1`.

**To finish #57** (needs a person with access, or an Israeli IP): (a) fetch the authority's
price-transparency page and the 2025 annual report from an Israeli network and look for a
format specification, version number and effective dates; (b) run the portal probe daily (it
already does) and read the "Files per detected schema" table; (c) on the first `v2` or
`unknown` file, take it from the `portal-probe-files` artifact, run it through
`adapter.inspect_schema` and `adapter.parse` locally to read the reason, replace
`PROVISIONAL_V2_MARKER` with the real marker, add the field mapping behind the existing `v2`
branch, and commit a trimmed real fixture (`portal_probe.py fixtures`) with a quality-gate
test. A fixture built from a specification instead of a real file must say so in its
`expected.json` and its comment (spec-derived, not real).

## Sales channel (#53)

Online prices differ from in-store prices (**verified**). Every `StoreRecord` therefore leaves
`parse` with `channel` set to `physical` or `online`. `channel.tag_channel(adapter, store)`
applies the following rules in order, and the first match wins. It is also available for
re-tagging stored rows.

1. **Declared by the source** (applied while parsing, because the field is not part of
   `StoreRecord`): `StoreType` = 2 (the regulation's "internet" store type), or a sub-chain name
   that matches the chain's `online_subchain_markers`.
2. **Chain rule**: `adapter.online_store_rule(store)` checks the chain's name markers, address
   markers and `online_store_codes`.
3. **Shared fallback heuristic**: the store name, city or address contains one of `אונליין`,
   `און ליין`, `online`, `משלוחים`, `אינטרנט` (case-insensitive), or the store code is in the
   adapter's `online_store_codes`.

Online records often have no real address or coordinates. They get `lat`/`lon` = `None`, and
radius queries should skip them, filtering to `channel = 'physical'` by default. That query
belongs to the API and database workstream.

Every rule below is **provisional**. Each is proven by a synthetic Stores fixture
(`tests/test_channel.py`). Store codes marked as placeholders are synthetic and must be
replaced with the real codes after the first real Stores file.

| Chain | Identification rule | Path proven by the fixture | Online record |
|---|---|---|---|
| shufersal | `SUBCHAINNAME` contains `ONLINE`/`אונליין`; or name contains ONLINE/אונליין | sub-chain `שופרסל ONLINE`, store 90 named `מרכז ליקוט מודיעין` (no keyword in the name) | yes |
| ramilevy | `StoreType` 2; name contains `אינטרנט`; code in `{331}` (placeholder) | code 331, `רמי לוי מרכז לוגיסטי` | yes |
| osherad | none; only the shared heuristic runs | no store tagged online | **no online record known** |
| yohananof | `StoreType` 2; name contains משלוחים/אונליין | `StoreType` 2, `יוחננוף - מרכז ליקוט` | yes |
| victory | name contains אונליין/משלוחים | `ויקטורי אונליין`, store 45 | yes |
| hazihinam | name contains `אתר` (the web shop); code in `{299}` (placeholder) | `חצי חינם אתר` | yes |
| tivtaam | address contains `מרכז הפצה`; name contains משלוחים | `טיב טעם - הזמנות` at `מרכז הפצה ראשון לציון` (no shared keyword) | yes |
| mega | code in `{5000}` (placeholder) | `קרפור מרכז ליקוט` (no keyword in the name) | yes |
| machsanei_hashuk | name contains אונליין/משלוחים; code in `{90}` (placeholder) | `מחסני השוק אונליין`, store 90, no address or coordinates | yes |
| king_store | none; only the shared heuristic runs | no store tagged online | **no online record known** |

**Chains with no online record:** Osher Ad and King Store, as far as we know. This is a hypothesis to confirm
on the first real Stores file. Every other chain is expected to have an online record because
it runs an online shop, but the exact record has not been seen. `has_online_record` on each
adapter records this, and a test keeps it consistent with the fixtures.

## Alerts (#32)

`parse` never returns an empty result silently. It raises `AdapterError` whose message starts
with `[<chain id>]` when:

- the bytes are empty, the gzip or zip is corrupt or truncated, or the payload is not
  well-formed XML (for example an HTML "link expired" page);
- the schema is unknown (`UnknownSchemaError`);
- the file's name, `RawFile.chain_id`, header `ChainId` or a row's `ChainId` belongs to
  another chain;
- the content does not match the file kind (a file named PriceFull that holds promotions);
- a required field is missing or malformed (`ItemCode`, `ItemName`, `ItemPrice`, `StoreId`,
  `StoreName`, `PromotionId`, an unparsable number or date). Precision over recall: one bad
  row fails the file, and the file is never partly loaded;
- rows exist but none produced a record;
- a **Stores or PriceFull file has no rows at all**.

A Promo, PromoFull or Price delta file with zero rows is legitimate (a store with no
promotions, or an hour with no changes) and returns an empty `ParsedFile`. Each case has a test.
Routing the exception to an alert channel is the loader's job.

## Adding a chain

1. Add `smartcart_ingest/adapters/<slug>.py` with a `@register` subclass of
   `RegulationAdapter`. Set `chain_id`, `display_name`, `slug`, `portal`, `containers` (when
   they differ from `Items`/`Promotions`/`SubChains`), `upstream_parsers`, `upstream_scraper`,
   the online-rule attributes and `has_online_record`. Then add the module to the import line in
   `adapters/__init__.py`.
2. Add `tests/fixtures/<slug>/` with at least a Stores, a PriceFull and a PromoFull file,
   named exactly as the portal names them, plus an `expected.json` with literal counts, field
   values and the online store codes.

No test, loader or core code changes. `test_registry_matches_fixture_folders` fails until both
exist, and `test_adding_a_chain_needs_only_a_module_and_a_fixture` proves the path end to end
with a throwaway chain. A chain whose XML is not the regulation layout can implement
`ChainAdapter` directly instead.

## Real fixtures

`smartcart_ingest/adapters/fetch_fixtures.py` downloads one real Stores, PriceFull and
PromoFull file per chain through the pinned upstream scraper. It contacts only the mandated
transparency portals, never a chain's online store. Run it on a machine with portal access:

```
uv run python -m smartcart_ingest.adapters.fetch_fixtures --list     # plan, no network
uv run python -m smartcart_ingest.adapters.fetch_fixtures            # all chains
uv run python -m smartcart_ingest.adapters.fetch_fixtures shufersal ramilevy
uv run python -m smartcart_ingest.adapters.fetch_fixtures machsanei_hashuk king_store
```

The plan covers every registered chain, Machsanei Hashuk and King Store included. A listing that
puts an unusable file first (Yohananof's portal lists `PromoFull0000000000000-00-1-202411010501.gz`,
chain id all zeros, 2024, before its real files) is handled: when the first file is not one the
adapter accepts, `fetch` asks the scraper for ten and takes the newest usable one. Run the
laibcatalog chains (victory, machsanei_hashuk) after about 08:00 Israel time, and Machsanei
Hashuk not on a Saturday: their listings are empty outside those hours (upstream stability notes).

`fetch` also takes `--store N` (only that store's files) and `--candidates N` (download N and keep
the largest). The Portal probe uses both: the largest of ten PromoFull files, then the PriceFull
of the same store, so the committed PriceFull and PromoFull of a chain are for one store (Shufersal
store 39 and Yohananof store 5 were replaced for this on 2026-10-22; the other five already were).
The probe's reachability column reports files downloaded or a passing FTP login when the HTTP root
does not answer (the four Cerberus chains, King Store's 403), see `portal_probe.reachability`.

Files land raw (still compressed) in `tests/fixtures/real/<slug>/`, together with a
`manifest.json` that holds the sha256 and our adapter's parse result for each file. The test
suite parses everything under `fixtures/real/` automatically. To promote a real file, move it
into the chain folder, write its literal expectations into `expected.json`, delete the
synthetic file it replaces, and fix any rule marked *provisional* above that the real file
contradicts.

## Upstream

- Pinned in `services/ingest/pyproject.toml`: `il-supermarket-parser==1.0.12`,
  `il-supermarket-scraper>=1.0.11,<2` (1.0.15 installed). A test asserts the parser pin.
- Upstream is imported only inside `smartcart_ingest/adapters/` (`_upstream.py` for the
  layout cross-check and `fetch_fixtures.py` for downloads). A test scans the package and fails
  on any other import. Parse results contain only `smartcart_ingest.models` types.
- We do not run the upstream converters at parse time, because they build pandas frames and
  the project is beta. Their layout knowledge is reused through the cross-check test instead.

## Contract notes

The shared contract files were not changed. Requests for the contract owner:

1. **`StoreRecord` has no source fields** (`StoreType`, `SubChainName`), so
   `online_store_rule(store)` cannot see them. The workaround: the adapter applies those
   declared signals while parsing and sets `channel` before `tag_channel` runs. Suggested
   change: add `store_type: str | None` and `sub_chain_name: str | None`, or a `raw: dict`, to
   `StoreRecord`.
2. **One chain id per adapter in `REGISTRY`.** Victory publishes under two ids. The workaround:
   `RegulationAdapter.chain_ids` accepts the extra id, but `get_adapter("7290058103393")`
   fails. `ChainAdapter.aliases` now exists (`register` registers each alias); Machsanei Hashuk
   uses it for its second id, and Victory can adopt it the same way.
3. **`detect_schema(xml_root: Any)`** receives the partial root from `xmlutil.read_header`
   (header plus the first row). It would help to document that adapters must not expect a
   fully built tree.
