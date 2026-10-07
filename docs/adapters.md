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
| `PromoRecord` | `PromotionId`, `PromotionDescription`, `PromotionItems/Item/ItemCode` (or one `ItemCode` per flat `Sale` row), start and end date plus hour, `MinQty`, `MaxQty` (0 becomes `None`), `Clubs/ClubId` or `ClubID` |

Promo reward mapping is **provisional** (unverified against real files). The full promo row is
always kept in `PromoRecord.raw`.

| Condition | `reward_type` | `reward_value` |
|---|---|---|
| any `IsGiftItem` = 1, or `AdditionalGiftCount` > 0 | `buy_x_get_y` | gift count (default 1) |
| `DiscountedPrice` present and `MinQty` > 1 | `bundle` | `DiscountedPrice` as published |
| `DiscountedPrice` present, `MinQty` ≤ 1 | `price` | `DiscountedPrice` |
| `DiscountType` = 2 with a `DiscountRate` | `percent` | `DiscountRate` as published |
| otherwise | `other` | `None` |

Whether `DiscountedPrice` is per unit or per bundle, and the scale of `DiscountRate`, are not
yet verified. Club codes map 0 to all customers and 1/2/3 to מועדון לקוחות / כרטיס אשראי / אחר
(regulation codes, unverified against real files). Any non-zero club id sets `club_only`.

## Schema versions (#57)

The consumer authority is rolling out an improved reporting model through 2026 (**verified**,
from its 2025 annual report). The timing per chain is **not verified**. Every file is
classified as one of:

- **`v1`**: the current 2015 regulation format. The root contains at least one container
  element this chain is known to use. A container outside the chain's dialect (for example,
  Shufersal suddenly publishing `<Products>`) is treated as unknown rather than guessed.
- **`v2`**: the new model. No real new-model file exists yet, so the marker is a
  **provisional** placeholder kept in one constant, `PROVISIONAL_V2_MARKER` in
  `adapters/_common.py`: a root attribute or header element named `SchemaVersion` whose major
  version is `2`. Change it there, and only there, when the first real file arrives.
- **`unknown`**: anything else, including the marker with a different major version (`3.1`)
  or no recognised container. `parse` raises `UnknownSchemaError` (a subclass of
  `AdapterError`), so the file is never loaded and the alert names the chain.

Both versions map to the same internal model through the same code path. A test parses a v1
and a synthetic v2 Shufersal PriceFull and checks that the item and price records are equal.
**No downstream code branches on the schema version**: quality gates, the loader and the
dashboard see only internal records. The version is recorded in `RawFile.schema_version`, so
`file_tracking` can store it.

Known differences in the new model, as listed in `docs/product-and-market.md` (**verified** that
the authority announced them; the file-level details are **not yet known**):

| Announced change | Expected effect on adapters |
|---|---|
| Uniform promo definitions | Promo reward types should map directly instead of through the provisional heuristic above. Revisit `_promo_record` when real files exist. |
| Item-and-store accuracy | Possibly per-store item identity or stricter store codes. Store-code normalization stays. |
| AI for substitutes | Possibly new substitute or category fields. Out of scope until phase 3 ("Adaptation to the authority's new reporting schema"). Extra fields are ignored today. |

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

The plan covers every registered chain, Machsanei Hashuk and King Store included. Run the
laibcatalog chains (victory, machsanei_hashuk) after about 08:00 Israel time, and Machsanei
Hashuk not on a Saturday: their listings are empty outside those hours (upstream stability notes).

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
