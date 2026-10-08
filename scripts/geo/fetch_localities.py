#!/usr/bin/env python3
"""Build data/geo/localities.csv: CBS locality code to a centroid in WGS 84.

    uv run python scripts/geo/fetch_localities.py [--resource-id ID] [--out FILE]
        [--nominatim-for-missing] [--needed-from fixtures|database|none] [--max-requests N]

Needs open internet (data.gov.il, and Nominatim for the optional fallback); it runs in the
"Geocode stores" workflow (.github/workflows/geocode-stores.yml). docs/geocoding.md has the method.

1. The locality list comes from data.gov.il's CKAN API: the resource given by --resource-id (or
   $LOCALITIES_RESOURCE_ID), else the best datastore resource that package_search finds. A resource
   with coordinates (WGS 84 lat/lon, or ITM x/y, converted here) gives rows directly.
2. A resource with codes and names only gives the names. With --nominatim-for-missing, each code
   that is NEEDED (a city code in the Stores files; --needed-from) and has no coordinates is looked
   up by its Hebrew name in OpenStreetMap Nominatim (place centroid, same politeness rules as
   geocode_stores.py, cached). The row's source says so.
3. Codes that stay unresolved are NOT in the table and are listed on stdout. Nothing is invented.

Existing rows of the output file are kept unless this run produced a row for the same code.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from smartcart_ingest.geocode import ckan
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--out", type=Path, default=REPO / "data" / "geo" / "localities.csv")
    ap.add_argument("--resource-id", default=os.environ.get("LOCALITIES_RESOURCE_ID") or None)
    ap.add_argument("--base-url", default=ckan.BASE_URL)
    ap.add_argument("--nominatim-for-missing", action="store_true")
    ap.add_argument("--needed-from", choices=["fixtures", "database", "none"], default="fixtures")
    ap.add_argument("--max-requests", type=int, default=400)
    ap.add_argument("--cache", type=Path, default=REPO / "data" / "geo" / "cache" / "nominatim.jsonl")
    args = ap.parse_args(argv)

    now = datetime.now(UTC)
    retrieved = now.strftime("%Y-%m-%d")
    resource_id = args.resource_id
    if not resource_id:
        candidates = ckan.discover(base=args.base_url)
        print("candidate resources:", file=sys.stderr)
        for c in candidates:
            print(f"  {c['kind']:6} {c['id']}  {c['package']} / {c['name']}", file=sys.stderr)
        if not candidates:
            print("no locality resource found on data.gov.il; pass --resource-id", file=sys.stderr)
            return 2
        resource_id = candidates[0]["id"]
    print(f"resource: {resource_id}", file=sys.stderr)
    records = list(ckan.datastore_records(resource_id, base=args.base_url))
    source = f"data.gov.il resource {resource_id}"
    rows, skipped = localities_from_records(records, source=source, retrieved_at=retrieved)
    by_code = {r.code: r for r in rows}
    names = names_from_records(records)
    print(f"records: {len(records)}; with coordinates: {len(by_code)}; skipped: {skipped}")

    needed = needed_codes(args.needed_from)
    missing = sorted(c for c in (needed or set(names)) if c not in by_code)
    if args.nominatim_for_missing and missing:
        client = NominatimClient(args.cache, max_requests=args.max_requests)
        got = 0
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
                        f"{source} (names); OpenStreetMap Nominatim place centroid, request {key}; "
                        "© OpenStreetMap contributors (ODbL)",
                        retrieved,
                    )  # fmt: skip
                    got += 1
        except (Blocked, BudgetExhausted, GeocoderError) as exc:
            print(f"nominatim stopped: {exc}", file=sys.stderr)
        print(f"nominatim: {client.requests_made} requests, {client.cache_hits} cache hits, {got} placed")

    merged = load_localities(args.out)
    merged.update(by_code)
    n = write_localities(args.out, merged.values())
    unresolved = sorted(c for c in needed if c not in merged)
    print(f"wrote {n} localities to {args.out}")
    if needed:
        print(
            f"needed codes: {len(needed)}; resolved: {len(needed) - len(unresolved)}; "
            f"unresolved: {len(unresolved)} {unresolved}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
