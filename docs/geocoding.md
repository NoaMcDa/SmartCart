# Store coordinates

Why this exists: the phase 0 exit criterion "coordinates for every store" (issues #60, #1) was at
**0 of 827** real physical stores, because none of the seven real chains publishes coordinates. Their
Stores files carry a numeric `City` and an address. Stores are public places, so unlike user
locations (`CLAUDE.md`: rounded to neighbourhood level) they need real coordinates. Labels follow
`docs/README.md`: **measured** is read from a run, **derived** is reasoning from a measured value.

## Status (2026-10-09)

Measured by the workflow **Geocode stores** (run 37908586819 on `finish/geo`, 800-store budget) and by
`scripts/exit_dry_run/run.sh` on the committed data:

- **769 of 827 real physical stores have coordinates** (the dry run, through the loader); 58 do not.
  By precision, from `geocode_stores.py`: **address 200, street 304, locality 265, none 58**.
- Locality table: **1306 localities from Wikidata** (property `P3466`, "Israeli CBS municipal ID", found by
  the signature check on the known codes of Tel Aviv, Jerusalem and Haifa). They cover **127 of the 132**
  distinct non-zero city codes in the real Stores files. Unresolved: `10018, 10044, 10098, 1306, 50`.
  data.gov.il gave only names (1484 settlement names, no coordinates) and its file downloads returned
  HTTP 403, so none of the table is CBS-sourced coordinates; they are Wikidata's, many rounded to a town
  centre, which is fine for `locality` precision and not for more.
- Store rows (`data/geo/store_geocodes.csv`, 520): 335 + 185 from two runs; sources `nominatim` (address
  or street inside the store's own city), `nominatim:city-from-text` (6), `cbs-name-match` (16).
- The 58 without coordinates: 54 have city `0` and no city in their address or name, 4 have a code not in
  the table (`stores_missing_geo` lists them with the reason). 304 stores were tried and Nominatim had no
  house or street in the right city (OSM coverage, vague addresses such as `מרכז מסחרי`); those
  stay at `locality`.
- **Not verified**: that the Wikidata points are the localities' centres (the table is OSM/Wikidata,
  not CBS), and the quality of the 304 `street` rows beyond the city check (the street can be long).

Earlier, with only the committed 27-row SAMPLE table (`data/geo/localities_sample.csv`), the loader
placed 511 of 827; the sample is kept for the tests.

## How a store gets a location

The ingest loader (`smartcart_ingest/loader.py`, `_set_locations`) sets `stores.geog` when it loads a
Stores file, in this order:

1. **Chain-published** `Latitude`/`Longitude` in the Stores file: precision `address`, source `chain`.
   Never replaced by anything below. (None of the seven real chains publishes them today.)
2. **A row of `data/geo/store_geocodes.csv`** for `(chain_id, store_code)`: precision `address`,
   `street` or `locality`, source `nominatim` (or `cbs-name-match`).
3. **The centroid of the store's CBS locality**, from `data/geo/localities.csv`: precision `locality`,
   source `cbs-locality:<code>`.
4. **Nothing**: `geog` stays NULL and the store appears in the view `stores_missing_geo` with a reason
   (`city code unknown (0 or missing)` or `city code not in the locality table`).

A lookup never replaces a better location: a locality centroid does not overwrite a street or an
address, and a chain-published point is never overwritten. Online stores are not looked up.
Columns (migration `20261011100900_store_geocode.sql`): `stores.geo_precision`
(`address|street|locality`, NULL exactly when `geog` is NULL) and `stores.geo_source`. A trigger gives a
point written by an older path (only `geog`) the labels `address` / `chain`. `stores_within()` and
the GiST index are unchanged.

Files are read from `data/geo/` (override: `SMARTCART_GEO_DIR`, or `SMARTCART_GEO_LOCALITIES` and
`SMARTCART_GEO_STORES` per file). A missing or unreadable file means an empty table; a price load
never fails because of it. On the VPS the files are in the repository checkout the service runs from.
A new coordinate reaches the database on the next Stores file load of that chain.

## The locality table

`data/geo/localities.csv`: `code, name_he, name_en, lat, lon, source, retrieved_at`. The `City` of a
Stores file is the CBS (הלמ"ס) locality code. `scripts/geo/fetch_localities.py` builds the table from
three sources, in order of preference (a code from an earlier source is never replaced):

1. **data.gov.il (CKAN)**: the resources of the locality datasets, best first (`package_show` on
   `localities-in-israel` and `citiesandsettelments`, plus `package_search`; the CBS "קובץ היישובים"
   ranks first). **Each resource's own file (CSV or XLSX) is tried before the datastore API**, because
   the datastore calls get a firewall HTML 403 from a GitHub runner (run 37823489893: package
   metadata and search answered 200, datastore calls 403) while the file may answer. CSV (UTF-8 or
   Windows-1255, any of `, ; tab`) and XLSX are read with the standard library
   (`geocode/tables.py`, no openpyxl; old binary XLS is refused with a message). The header row is
   found under any title lines; columns are matched by alias and by token rules (`שם יישוב`, `סמל
   יישוב`, `X`/`Y`, `lat`/`lon`). WGS 84 `lat/lon` are used as they are; ITM (EPSG:2039) `X/Y` are
   converted by `smartcart_ingest/geocode/itm.py` (within 0.35 m of pyproj on the test points). A
   converted point outside Israel's bounding box is dropped. `--resource-id` /
   `LOCALITIES_RESOURCE_ID` tries one resource instead. All requests carry a descriptive
   User-Agent (`SmartCart-geo/0.1 (+<repo URL>; contact: <contact>)`) and `Accept`; a refusal is
   reported, not worked around.
2. **Wikidata**, rows marked `source=wikidata` (CC0). The CBS locality-code property is **found, not
   assumed**: (a) `wbsearchentities` for "Central Bureau of Statistics", "Israel locality", "Israeli
   settlement", "CBS code" (English) and "הלשכה המרכזית לסטטיסטיקה", "סמל יישוב" (Hebrew), every hit
   logged with id, label and description, scored on a description that names Israel and
   localities/settlements; (b) a SPARQL **signature check**: the property that holds `5000` on Tel
   Aviv-Yafo (Q33935), `3000` on Jerusalem (Q1218) and `4000` on Haifa (Q41621) is the CBS locality
   code whatever it is called, and a property matching at least two of the three is taken over a search
   hit; (c) the old label query as the last resort. The chosen property and how it was found are
   printed (`wikidata property: P... (signature ...)`). Then one SPARQL query fetches all items with
   that property and P625, Hebrew and English labels optional (a row needs a Hebrew label); on a
   shared code the lowest Q-id wins. `wikidata_property` / `WIKIDATA_CBS_PROPERTY` pins the property.
   **The property is `P3466`** ("Israeli CBS municipal ID", Hebrew label מזהה יישובים של הלמ״ס), recorded
   from run 37824682474: found by the signature check (it holds the known codes of all three items); the
   Hebrew search for `סמל יישוב` also lists it, the English searches did not. Pin it with
   `wikidata_property=P3466` to skip discovery. The parser and the discovery are tested on hand-written
   responses in the documented format (`data/geo/fixtures/`, see its README), not on recorded ones.
   **Not seen in a run: data.gov.il's `קובץ היישובים` coordinates** (the file URLs gave 403 and the
   datastore copy has no coordinate columns the reader recognises; the next run logs its column names).
3. **Nominatim by name** (`--nominatim-for-missing`): a needed code that is still unplaced but has a
   name (from source 1 or 2) is looked up by that name (place centroid of a settlement type, in Israel,
   whose own name matches). Those rows say so in `source`.

Each source prints one line to stdout, which the workflow shows in the log and the job summary:
`SOURCE <name>: HTTP <status> x<n>, ...; rows=<n>; <note>`. The script exits 1, with a
`::error::` annotation, when **no** source produced a row (so the workflow step fails visibly); a
single failing source does not fail it. Rows that cannot be sourced stay out. Unresolved codes are
printed; nothing is invented.

## Address geocoding

`scripts/geo/geocode_stores.py` takes the physical stores (the real Stores fixtures, or
`--from database`) and writes `data/geo/store_geocodes.csv`:
`chain_id, store_code, lat, lon, precision, source, query_hash, geocoded_at`.

- Query: `"<street and number>, <city name>"`, the city name from the locality table. Addresses are
  cleaned first (`האומן,15`, `אבן גבירול157`, `20 נחל פרת`, `46-50 פנקס`, trailing `0`, text after a
  comma). If the house number is not found, a second query asks for the street only.
- Restricted to Israel (`countrycodes=il`). A result is kept only if its returned address names the
  **store's own locality** (`names_match`: equal after normalization, or the store's city is the
  leading part of a longer name such as `תל אביב-יפו`), the point is inside Israel's bounding box, and
  it is a house (`address`) or a street (`street`). A result that is only the city is no better than
  the centroid, so it is not recorded.
- **No locality table needed (third fallback).** A store whose city code is `0` or missing from the
  table is queried by its address text alone (Israel only, up to 10 results), then by the address plus
  the store's name. A result is accepted only if the city it returns (`city`, `town`, `village`,
  `hamlet`, `municipality`) **appears as whole words in the store's own address or name**
  (`city_in_text`; for `תל אביב-יפו` either part counts), and it is a house or a street. Source
  `nominatim:city-from-text`; the precision label stays what the result is (`address` or `street`),
  the weaker evidence is in the source. Stores that still have nothing and are named exactly like a
  locality get that centroid, precision `locality`, source `cbs-name-match`.
- Stdout summary: stores tried, no match in the right city, errors, unknown city, and coverage by
  precision (`address`, `street`, `locality`, `none`).

### Nominatim usage policy

The client (`geocode/nominatim.py`) follows <https://operations.osmfoundation.org/policies/nominatim/>:

- **1 request per second**, enforced in code (the interval cannot be set below 1 s).
- **Identifying User-Agent with a contact**: `SmartCart-store-geocoder/0.1 (+<repo URL>; contact:
  <NOMINATIM_CONTACT>)`. `NOMINATIM_CONTACT` (an e-mail or URL) is required; without it the client
  refuses to run. In the workflow it is the repository variable (or secret) `NOMINATIM_CONTACT`.
- **Cache, never ask twice**: every answer, including an empty one, is stored in
  `data/geo/cache/nominatim.jsonl` keyed by the exact request; rows already in `store_geocodes.csv`
  are not geocoded again; there is no refresh flag. The workflow commits the cache with the CSVs so
  the next run starts from it.
- **No bulk geocoding**: a run sends at most `max_stores` stores (default 150, at most two requests
  each); a 403 or 429 stops the run.
- Use is limited to the stores' addresses, a one-off data build, not a live service.

### Attribution and licence

Geocodes (and locality centroids looked up by name) are © OpenStreetMap contributors, available under
the Open Database Licence (ODbL), <https://www.openstreetmap.org/copyright>. `stores.geo_source`
records which rows are OSM-derived (`nominatim`). Anywhere the product shows a map or publishes the
coordinates, it needs "© OpenStreetMap contributors"; the web follow-up below owns that. The
committed cache is OSM data under the same licence.

## The workflow

**Geocode stores** (`.github/workflows/geocode-stores.yml`, `workflow_dispatch`; a GitHub runner has
open internet, the build box does not). Inputs:

| Input | Default | Meaning |
|---|---|---|
| `max_stores` | 150 | stores sent to Nominatim in this run |
| `fetch_localities` | true | rebuild `localities.csv` from the sources above first |
| `localities_resource_id` | empty | CKAN resource id; empty means discover it |
| `wikidata_property` | empty | Wikidata property id of the CBS locality code; empty means find it by label |
| `nominatim_for_localities` | true | name lookup for localities the list gives no coordinates |

`NOMINATIM_CONTACT` (repository variable or secret) overrides the default contact, this repository's issues page. The `geocode` job only reads the repository; the `commit` job
(the only one with `contents: write`) pushes `geo/localities-<yyyymmdd>` (the locality table) and
`geo/stores-<yyyymmdd>` (locality table, `store_geocodes.csv`, the request cache). No pull request is
opened; review the two CSVs and merge. Re-run it with a higher `max_stores` until the summary shows
`stores tried: 0`; the cache makes every re-run free for stores already answered.

## What the API and the web must do (follow-up, not done here)

`services/api` and `apps/web` are unchanged. A store at precision `locality` is the centre of its
town, not the store: distance, travel cost and the two-store split are **approximate** for it. The
follow-up: expose `geo_precision` with the store, label locality-precision stores "approximate
location" in the store picker and in the travel-cost line, and do not rank two stores of the same
town by distance. Until then the radius query treats a locality point like any other point.

## Re-checking

- `scripts/exit_dry_run/run.sh` (section "Store coordinates") counts stores with coordinates; to see
  the sample table's effect: `SMARTCART_GEO_LOCALITIES=$PWD/data/geo/localities_sample.csv
  scripts/exit_dry_run/run.sh --out /tmp/dry.md` (it writes `docs/phase-0-exit-dry-run.md` unless `--out` is given).
- Tests: `services/ingest/tests/test_geocode.py` (ITM, locality table, client politeness and cache,
  city check, fallback order) and `test_geocode_loader.py` (the loader hook on the real Stores files,
  PostGIS).
