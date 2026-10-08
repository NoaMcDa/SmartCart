#!/usr/bin/env python3
"""Geocode physical stores by address with OpenStreetMap Nominatim -> data/geo/store_geocodes.csv.

    NOMINATIM_CONTACT=you@example.org uv run python scripts/geo/geocode_stores.py
        [--from fixtures|database] [--max-stores N] [--out FILE] [--localities FILE] [--cache FILE]

Stores come from the real Stores fixtures (services/ingest/tests/fixtures/<chain>/real/) or, with
--from database, from the stores table of $DATABASE_URL. For each store the query is
"<street and number>, <city name>", the city name coming from the CBS locality table
(data/geo/localities.csv, from fetch_localities.py). A result is kept only when Nominatim's returned
address names that same locality; otherwise the store falls back (street-only query, then the locality
centroid the ingest loader applies by itself, then NULL).

Politeness (https://operations.osmfoundation.org/policies/nominatim/): one request per second, a
descriptive User-Agent with the contact from NOMINATIM_CONTACT (required), every answer cached in
--cache so no request is ever sent twice, rows already in --out are never re-geocoded, and at most
--max-stores stores per run. Output is © OpenStreetMap contributors (ODbL); docs/geocoding.md.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from smartcart_ingest.geocode import sources
from smartcart_ingest.geocode.localities import load_localities
from smartcart_ingest.geocode.nominatim import MissingContact, NominatimClient
from smartcart_ingest.geocode.resolve import GeoIndex, load_store_geocodes, write_store_geocodes
from smartcart_ingest.geocode.stores import geocode_stores

REPO = Path(__file__).resolve().parents[2]
GEO = REPO / "data" / "geo"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--from", dest="origin", choices=["fixtures", "database"], default="fixtures")
    ap.add_argument("--max-stores", type=int, default=100, help="stores sent to Nominatim this run")
    ap.add_argument("--out", type=Path, default=GEO / "store_geocodes.csv")
    ap.add_argument("--localities", type=Path, default=GEO / "localities.csv")
    ap.add_argument("--cache", type=Path, default=GEO / "cache" / "nominatim.jsonl")
    ap.add_argument("--no-network", action="store_true", help="only summarize coverage; no requests")
    args = ap.parse_args(argv)

    if args.origin == "database":
        import os

        stores = sources.stores_from_database(os.environ["DATABASE_URL"])
    else:
        stores = sources.stores_from_fixtures()
    localities = load_localities(args.localities)
    existing = load_store_geocodes(args.out)
    print(f"stores: {len(stores)} physical; localities: {len(localities)}; existing rows: {len(existing)}")
    if not localities:
        print("the locality table is empty: run scripts/geo/fetch_localities.py first", file=sys.stderr)

    client = None
    if not args.no_network:
        try:
            client = NominatimClient(args.cache, max_requests=2 * args.max_stores)
        except MissingContact as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    new_rows, stats = geocode_stores(
        stores, localities, client, existing=existing, max_stores=args.max_stores
    )
    merged = {**existing, **{(r.chain_id, r.store_code): r for r in new_rows}}
    n = write_store_geocodes(args.out, list(merged.values()))

    print(f"wrote {n} rows to {args.out} ({len(new_rows)} new)")
    if client is not None:
        print(f"nominatim requests: {client.requests_made}; cache hits: {client.cache_hits}")
    print(
        f"stores tried: {stats.attempted}; no match in the right city: {stats.no_match}; "
        f"errors: {stats.errors}; city code unknown: {stats.unknown_city_code}; "
        f"city code not in the locality table: {stats.no_city}; no usable address: "
        f"{stats.skipped_online_or_no_address}; already had a row: {stats.skipped_existing}"
    )
    if stats.stopped:
        print(f"stopped early: {stats.stopped}")
    print("new rows by precision: " + (", ".join(f"{k}={v}" for k, v in sorted(stats.by_precision.items())) or "none"))
    index = GeoIndex(localities, merged)
    cov: Counter[str] = sources.coverage(stores, index)
    print(
        f"coverage of {len(stores)} physical stores: "
        + ", ".join(f"{p}={cov.get(p, 0)}" for p in ("address", "street", "locality", "none"))
    )
    print("Geocodes: © OpenStreetMap contributors (ODbL), https://www.openstreetmap.org/copyright")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
