#!/usr/bin/env python3
"""Build data/geo/localities.csv: CBS locality code to a centroid in WGS 84.

    uv run python scripts/geo/fetch_localities.py [--resource-id ID] [--out FILE]
        [--wikidata-property P123] [--no-wikidata] [--no-ckan]
        [--nominatim-for-missing] [--needed-from fixtures|database|none] [--max-requests N]

Needs open internet; it runs in the "Geocode stores" workflow (.github/workflows/geocode-stores.yml).
docs/geocoding.md has the method. Sources, in order of preference (a code taken from an earlier
source is never replaced by a later one):

1. data.gov.il (CKAN): the resources of the locality datasets (package_show / package_search, the CBS
   "קובץ היישובים" first), each by its own file URL (CSV or XLSX) before the datastore API, or the
   resource given by --resource-id (or $LOCALITIES_RESOURCE_ID). WGS 84 lat/lon, or ITM x/y
   converted here.
2. Wikidata: the CBS locality-code property is found with wbsearchentities (every hit printed) and a
   check on the known codes of Tel Aviv, Jerusalem and Haifa; then one SPARQL query for items with
   that property and coordinates (P625). Rows say source=wikidata.
3. With --nominatim-for-missing: each NEEDED code (a city code in the Stores files) that is still
   unplaced but has a name (from 1 or 2) is looked up by that name in OpenStreetMap Nominatim.

Every source prints one "SOURCE ..." line on stdout with its HTTP status counts and row count, so the
outcome can be read from the workflow log. The exit code is 1 when no source produced any row.
Codes that stay unresolved are NOT in the table and are listed; nothing is invented.
Existing rows of the output file are kept unless this run produced a row for the same code.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from smartcart_ingest.geocode import ckan, tables, wikidata
from smartcart_ingest.geocode.http import StatusLog, get_bytes, get_json
from smartcart_ingest.geocode.localities import (
    Locality,
    centroid_from_nominatim,
    load_localities,
    localities_from_records,
    names_from_records,
    normalize_code,
    write_localities,
)
from smartcart_ingest.geocode.nominatim import (
    Blocked,
    BudgetExhausted,
    GeocoderError,
    NominatimClient,
)

REPO = Path(__file__).resolve().parents[2]


def needed_codes(source: str) -> set[str]:
    from smartcart_ingest.geocode import sources

    if source == "fixtures":
        stores = sources.stores_from_fixtures()
    elif source == "database":
        stores = sources.stores_from_database(os.environ["DATABASE_URL"])
    else:
        return set()
    return {c for s in stores if (c := normalize_code(s.city))}


def report(name: str, log: StatusLog, rows: int, note: str = "") -> None:
    line = f"SOURCE {name}: {log.summary()}; rows={rows}"
    print(line + (f"; {note}" if note else ""), flush=True)


ENOUGH_ROWS = 300
"""Stop trying further CKAN resources once this many localities have coordinates."""


def from_ckan(args, retrieved: str):
    """``(rows, names, note)``; never raises.

    For each candidate resource (the CBS locality file first), the resource's own file (CSV/XLSX)
    is tried before the datastore API: the datastore calls can be refused (HTTP 403 from the site's
    firewall) while package metadata and the file answer.
    """
    log = StatusLog()

    def fetch(url: str):
        return get_json(url, timeout=60, log=log)

    by_code: dict[str, Locality] = {}
    names: dict[str, tuple[str, str]] = {}
    note = ""
    try:
        if args.resource_id:
            res = {"id": args.resource_id, "name": "", "format": "", "url": "", "package": "",
                   "datastore_active": True, "score": 0}  # fmt: skip
            try:
                info = fetch(ckan._api(args.base_url, "resource_show", id=args.resource_id))["result"]
                res.update(name=info.get("name", ""), url=info.get("url", ""), format=str(info.get("format", "")).upper())
            except Exception as exc:  # noqa: BLE001
                print(f"  resource_show {args.resource_id}: {exc}")
            candidates = [res]
        else:
            candidates = ckan.resource_candidates(base=args.base_url, fetch=fetch)
        for c in candidates:
            print(f"  ckan candidate {c['id']} [{c['format'] or 'datastore'}] score {c['score']} "
                  f"{c['package']} / {c['name']}")  # fmt: skip
        if not candidates:
            note = "no locality resource found (pass --resource-id)"
        for c in candidates:
            if len(by_code) >= ENOUGH_ROWS:
                break
            attempts = []
            if c["url"]:
                attempts.append(("file", lambda c=c: tables.read_records(get_bytes(c["url"], log=log))))
            if c["datastore_active"]:
                attempts.append(
                    ("datastore", lambda c=c: list(ckan.datastore_records(c["id"], base=args.base_url, fetch=fetch)))
                )
            for how, read in attempts:
                try:
                    records = read()
                except Exception as exc:  # noqa: BLE001 (HttpFailure, UnsupportedFile, bad data)
                    print(f"  ckan {how} {c['id']}: {type(exc).__name__}: {exc}")
                    continue
                rows, skipped = localities_from_records(
                    records, source=f"data.gov.il resource {c['id']} ({how})", retrieved_at=retrieved
                )
                for pair_code, pair in names_from_records(records).items():
                    names.setdefault(pair_code, pair)
                for r in rows:
                    by_code.setdefault(r.code, r)
                print(f"  ckan {how} {c['id']}: {len(records)} records, {len(rows)} with coordinates; skipped {skipped}")
                if rows:
                    break  # the file gave coordinates; no need for the datastore copy of it
        if not note:
            note = f"{len(by_code)} localities with coordinates, {len(names)} names"
    except Exception as exc:  # noqa: BLE001 (a broken source must not hide the others)
        note = f"error: {type(exc).__name__}: {exc}"
    report("data.gov.il CKAN", log, len(by_code), note)
    return list(by_code.values()), names, note


def from_wikidata(args, retrieved: str):
    """``(rows, names, note)``; never raises."""
    log = StatusLog()

    def fetch(url: str):
        host_is_sparql = url.startswith(wikidata.ENDPOINT)
        return get_json(
            url, accept=wikidata.ACCEPT if host_is_sparql else "application/json", timeout=120, log=log
        )

    rows: list[Locality] = []
    note = ""
    try:
        rows, skipped, prop = wikidata.fetch_localities(
            fetch, retrieved_at=retrieved, prop=args.wikidata_property, log=print
        )
        note = (
            f"property {prop}; skipped {skipped}"
            if prop
            else "no property for the CBS locality code found (pass --wikidata-property)"
        )
    except Exception as exc:  # noqa: BLE001
        note = f"error: {type(exc).__name__}: {exc}"
    report("Wikidata SPARQL", log, len(rows), note)
    return rows, {r.code: (r.name_he, r.name_en) for r in rows}, note


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--out", type=Path, default=REPO / "data" / "geo" / "localities.csv")
    ap.add_argument("--resource-id", default=os.environ.get("LOCALITIES_RESOURCE_ID") or None)
    ap.add_argument("--base-url", default=ckan.BASE_URL)
    ap.add_argument("--wikidata-property", default=os.environ.get("WIKIDATA_CBS_PROPERTY") or None)
    ap.add_argument("--no-ckan", action="store_true")
    ap.add_argument("--no-wikidata", action="store_true")
    ap.add_argument("--nominatim-for-missing", action="store_true")
    ap.add_argument("--needed-from", choices=["fixtures", "database", "none"], default="fixtures")
    ap.add_argument("--max-requests", type=int, default=400)
    ap.add_argument("--cache", type=Path, default=REPO / "data" / "geo" / "cache" / "nominatim.jsonl")
    args = ap.parse_args(argv)

    retrieved = datetime.now(UTC).strftime("%Y-%m-%d")
    by_code: dict[str, Locality] = {}
    names: dict[str, tuple[str, str]] = {}

    if not args.no_ckan:
        rows, ckan_names, _ = from_ckan(args, retrieved)
        by_code.update({r.code: r for r in rows})
        names.update(ckan_names)
    if not args.no_wikidata:
        rows, wd_names, _ = from_wikidata(args, retrieved)
        for r in rows:  # data.gov.il (CBS) stays preferred where both have the code
            by_code.setdefault(r.code, r)
        for code, pair in wd_names.items():
            names.setdefault(code, pair)

    needed = needed_codes(args.needed_from)
    missing = sorted(c for c in (needed or set(names)) if c not in by_code)
    nominatim_rows = 0
    if args.nominatim_for_missing and missing:
        client = NominatimClient(args.cache, max_requests=args.max_requests)
        try:
            for code in missing:
                name = names.get(code, ("", ""))[0]
                if not name:
                    continue
                hit = centroid_from_nominatim(client, name)
                if hit:
                    lat, lon, key = hit
                    by_code[code] = Locality(
                        code, name, names[code][1], round(lat, 6), round(lon, 6),
                        f"OpenStreetMap Nominatim place centroid by name, request {key}; "
                        "© OpenStreetMap contributors (ODbL)",
                        retrieved,
                    )  # fmt: skip
                    nominatim_rows += 1
        except (Blocked, BudgetExhausted, GeocoderError) as exc:
            print(f"nominatim stopped: {exc}", file=sys.stderr)
        print(
            f"SOURCE Nominatim by name: {client.requests_made} requests, "
            f"{client.cache_hits} cache hits; rows={nominatim_rows}"
        )

    if not by_code:
        print(
            "::error::no source returned any locality row (see the SOURCE lines above); "
            "data/geo/localities.csv was not changed"
        )
        return 1

    merged = load_localities(args.out)
    merged.update(by_code)
    n = write_localities(args.out, merged.values())
    by_source: dict[str, int] = {}
    for loc in by_code.values():
        key = loc.source.split(" ")[0].split(";")[0]
        by_source[key] = by_source.get(key, 0) + 1
    print(f"wrote {n} localities to {args.out}; rows from this run by source: {by_source}")
    if needed:
        unresolved = sorted(c for c in needed if c not in merged)
        print(
            f"needed codes: {len(needed)}; resolved: {len(needed) - len(unresolved)}; "
            f"unresolved: {len(unresolved)} {unresolved}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
