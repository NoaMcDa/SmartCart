# Store coordinates

Why this exists: the phase 0 exit criterion "coordinates for every store" (issues #60, #1) was at
**0 of 827** real physical stores, because none of the seven real chains publishes coordinates. Their
Stores files carry a numeric `City` and an address. Stores are public places, so unlike user
locations (`CLAUDE.md`: rounded to neighbourhood level) they need real coordinates. Labels follow
`docs/README.md`: **measured** is read from a run, **derived** is reasoning from a measured value.

## Status (2026-10-08)

- **Tooling is built and tested. The full data is not in the repository yet**: this build box has no
  route to data.gov.il or Nominatim, so `data/geo/localities.csv` and `data/geo/store_geocodes.csv`
  hold only their header. The workflow **Geocode stores** produces them (below). Its first run (run
  37822494185) got HTTP 403 from data.gov.il; a Wikidata source was added in response and is untested
  against the live service.
- Real Stores files, **measured**: 827 physical stores, 132 distinct non-zero city codes, 76 physical
  stores with city `0` (unknown).
- With the 27-row **sample** table (`data/geo/localities_sample.csv`, hand-entered approximate city
  centres, marked SAMPLE, tests and dry run only) the loader places **511 of 827** physical stores
  at precision `locality`, **measured** by `scripts/exit_dry_run/run.sh`. 316 are listed by
  `stores_missing_geo`. This is a floor for what the real table gives, not the answer: the sample
  has 27 of the 132 codes.
- Unresolved locality codes, **measured**: with the committed full table (header only) all 132;
  after the workflow, the number printed by `fetch_localities.py` ("unresolved") is the one to quote
  here. Never fill it by hand.
- Address-level coverage (`address` and `street`) is **not measured yet**; it needs the workflow's
  Nominatim run. Expect a minority of addresses to fail the city check or to be too vague (for
  example `מרכז מסחרי`, `אזור תעשיה`); that is **an estimate**, not a result.

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

1. **data.gov.il (CKAN API)**: `--resource-id` or `LOCALITIES_RESOURCE_ID`; without one it searches
   `package_search` for a datastore resource with a code, a name and coordinates, and prints its
   candidates. Columns are detected by name (Hebrew and English aliases). WGS 84 `lat/lon` are used
   as they are; ITM (EPSG:2039) `X/Y` are converted by `smartcart_ingest/geocode/itm.py` (the inverse
   transverse Mercator plus the Israel 1993 to WGS 84 Helmert, standard library only, within 0.35 m of
   pyproj on the test points). A converted point outside Israel's bounding box is dropped.
   **Observed from a GitHub runner (workflow run 37822494185): HTTP 403.** data.gov.il refuses that
   request; the cause (the cloud IP range, or the client) is not known. All CKAN requests carry a
   descriptive User-Agent (`SmartCart-geo/0.1 (+<repo URL>; contact: <contact>)`) and `Accept`, which is
   the honest convention; a refusal is reported, not worked around.
2. **Wikidata (SPARQL, `https://query.wikidata.org/sparql`)**: items that have the CBS locality code and
   coordinates (P625), CC0 data. Rows say `source=wikidata`. Two GETs: one that finds the property by
   label (properties whose English label contains "Central Bureau of Statistics" and "locality" or
   "settlement"; the best match wins and every candidate is printed), one that fetches all items with
   that property and P625, Hebrew and English labels optional (a row needs a Hebrew label). When several
   items share a code the lowest Q-id wins. The property can be pinned with the workflow input
   `wikidata_property` / `WIKIDATA_CBS_PROPERTY`, which skips discovery.
   **The property id is not recorded here yet**: the build box cannot reach Wikidata, and a property id
   is not something to recall from memory. The first successful workflow run prints it (line
   `wikidata property candidate P...` and `property P...` in the Wikidata `SOURCE` line); put it in this
   paragraph then and pass it as the input to skip discovery. The parser is tested on a hand-written
   response in the documented format (`data/geo/fixtures/`, see its README), not on a recorded one.
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
- Stores whose city code is `0` are not sent to the geocoder (there is no locality to check the
  answer against). If the store's name is exactly one locality's name (`דליית אל כרמל`), it gets that
  locality's centroid, precision `locality`, source `cbs-name-match`.
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
