"""Where does a store's location come from? One resolver, shared by the loader and the scripts.

Order, best first (``docs/geocoding.md``):

1. coordinates the chain publishes in its Stores file (the loader handles these itself; chains
   that publish them are the exception, none of the seven real ones does today);
2. a row of ``data/geo/store_geocodes.csv`` for ``(chain_id, store_code)``: precision ``address``,
   ``street`` or ``locality``, produced by ``scripts/geo/geocode_stores.py``;
3. the centroid of the store's CBS locality (``City`` of the Stores file) from
   ``data/geo/localities.csv``, precision ``locality``;
4. nothing: ``stores.geog`` stays NULL and the store is listed by the ``stores_missing_geo`` view.

The files are found in ``$SMARTCART_GEO_DIR`` or ``<repo>/data/geo``; ``SMARTCART_GEO_LOCALITIES``
and ``SMARTCART_GEO_STORES`` override one file each (the tests and the dry run use that to point
at the committed sample). A missing file is an empty table, never an error.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

from smartcart_ingest.geocode.itm import in_israel
from smartcart_ingest.geocode.localities import Locality, load_localities, normalize_code

PRECISIONS = ("address", "street", "locality")
"""Best to worst. The database CHECK constraint lists the same three."""
RANK = {p: i for i, p in enumerate(PRECISIONS)}

STORE_FIELDS = (
    "chain_id",
    "store_code",
    "lat",
    "lon",
    "precision",
    "source",
    "query_hash",
    "geocoded_at",
)


@dataclass(frozen=True)
class StoreGeocode:
    chain_id: str
    store_code: str
    lat: float
    lon: float
    precision: str
    source: str
    query_hash: str = ""
    geocoded_at: str = ""


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lon: float
    precision: str
    source: str


def default_geo_dir() -> Path:
    env = os.environ.get("SMARTCART_GEO_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[4] / "data" / "geo"


def locality_path() -> Path:
    env = os.environ.get("SMARTCART_GEO_LOCALITIES")
    return Path(env) if env else default_geo_dir() / "localities.csv"


def store_geocodes_path() -> Path:
    env = os.environ.get("SMARTCART_GEO_STORES")
    return Path(env) if env else default_geo_dir() / "store_geocodes.csv"


def load_store_geocodes(path: Path) -> dict[tuple[str, str], StoreGeocode]:
    if not path.is_file():
        return {}
    out: dict[tuple[str, str], StoreGeocode] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                lat, lon = float(row["lat"]), float(row["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            precision = (row.get("precision") or "").strip()
            chain_id, code = (row.get("chain_id") or "").strip(), (row.get("store_code") or "").strip()
            if precision not in RANK or not chain_id or not code or not in_israel(lat, lon):
                continue
            out[(chain_id, code)] = StoreGeocode(
                chain_id=chain_id,
                store_code=code,
                lat=lat,
                lon=lon,
                precision=precision,
                source=(row.get("source") or "").strip(),
                query_hash=(row.get("query_hash") or "").strip(),
                geocoded_at=(row.get("geocoded_at") or "").strip(),
            )
    return out


def write_store_geocodes(path: Path, rows: list[StoreGeocode]) -> int:
    ordered = sorted(rows, key=lambda r: (r.chain_id, r.store_code))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(STORE_FIELDS)
        for r in ordered:
            writer.writerow(
                [r.chain_id, r.store_code, f"{r.lat:.6f}", f"{r.lon:.6f}", r.precision, r.source,
                 r.query_hash, r.geocoded_at]  # fmt: skip
            )
    return len(ordered)


class GeoIndex:
    def __init__(
        self,
        localities: dict[str, Locality] | None = None,
        geocodes: dict[tuple[str, str], StoreGeocode] | None = None,
    ) -> None:
        self.localities = localities or {}
        self.geocodes = geocodes or {}

    @classmethod
    def load(cls, *, localities: Path | None = None, geocodes: Path | None = None) -> GeoIndex:
        return cls(
            load_localities(localities or locality_path()),
            load_store_geocodes(geocodes or store_geocodes_path()),
        )

    def resolve(self, chain_id: str, store_code: str, city: str | None) -> GeoPoint | None:
        row = self.geocodes.get((chain_id, store_code))
        if row is not None:
            return GeoPoint(row.lat, row.lon, row.precision, row.source or "store_geocodes.csv")
        code = normalize_code(city)
        loc = self.localities.get(code) if code else None
        if loc is not None:
            return GeoPoint(loc.lat, loc.lon, "locality", f"cbs-locality:{loc.code}")
        return None


def load_index() -> GeoIndex:
    """The index from the configured files; read fresh on every call (the files are small and a
    load is once per Stores file)."""
    return GeoIndex.load()
