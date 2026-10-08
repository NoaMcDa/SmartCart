"""Geocode stores by address with Nominatim, keeping a result only when it is in the right city.

``geocode_stores`` takes the physical stores of a chain (from the real Stores fixtures or the
database), asks the :class:`NominatimClient` for ``"<street and number>, <city name>"`` and keeps
a result only when

* the returned address names the store's own locality (the CBS city of the Stores file, looked up
  in the locality table), compared with :func:`names_match`;
* the point lies inside Israel's bounding box;
* the result is a house or a street (a result that is merely the city or a suburb is no better
  than the locality centroid the loader falls back to, so it is not recorded as an address).

Everything else falls back, in order: the street-only query (one more request, only when the first
asked for a house number), the locality centroid (no request; done by the loader), NULL.

Stores whose city code is unknown (``0``, 76 of 827 real physical stores) cannot be checked against
a locality, so they are not sent to the geocoder. The one thing done for them: a store whose name
is exactly a locality's name (a chain that calls its Daliyat al-Karmel branch "דליית אל כרמל")
gets that locality's centroid, precision ``locality``, source ``cbs-name-match``.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from smartcart_ingest.geocode.itm import in_israel
from smartcart_ingest.geocode.localities import (
    Locality,
    names_match,
    normalize_code,
    normalize_name,
)
from smartcart_ingest.geocode.nominatim import (
    Blocked,
    BudgetExhausted,
    GeocoderError,
    NominatimClient,
)
from smartcart_ingest.geocode.resolve import RANK, StoreGeocode

SOURCE_NOMINATIM = "nominatim"
SOURCE_NAME_MATCH = "cbs-name-match"


@dataclass(frozen=True)
class StoreInput:
    chain_id: str
    store_code: str
    name: str
    address: str | None
    city: str | None
    """The raw ``City`` of the Stores file: a CBS locality code, ``0`` when unknown."""


@dataclass
class RunStats:
    attempted: int = 0
    skipped_existing: int = 0
    skipped_online_or_no_address: int = 0
    no_city: int = 0
    unknown_city_code: int = 0
    no_match: int = 0
    errors: int = 0
    stopped: str = ""
    by_precision: Counter[str] = field(default_factory=Counter)


# --- the query ---------------------------------------------------------------------------------

_HEB_DIGIT = re.compile(r"(?<=[֐-׿])(?=\d)|(?<=\d)(?=[֐-׿])")
_COMMA_NUMBER = re.compile(r"(?<=\S),\s*(?=\d+\s*$)")
_LEADING_NUMBER = re.compile(r"^(\d+)(?:\s*[-/]\s*\d+)?[א-ת]?\s+(\D.*)$")
_TRAILING_ZERO = re.compile(r"\s+0\s*$")
_NOISE = re.compile(r"\b(?:ת\.?\s?ד\.?|תא דואר)\b")


def clean_address(address: str | None) -> tuple[str, bool]:
    """``(street_text, has_house_number)`` for a Stores-file address, or ``("", False)``.

    Handles the shapes seen in real files: ``האומן,15``, ``אבן גבירול157``, ``20 נחל פרת``,
    ``46-50 פנקס``, ``רחוב המפוח 11, אזור התעשיה``, ``שרפה 22, כביש ראשי של העיר 0``. Only the
    first comma-separated part is kept; PO boxes and addresses with no letters give nothing.
    """
    text = (address or "").strip()
    if not text or _NOISE.search(text):
        return "", False
    text = _COMMA_NUMBER.sub(" ", text)
    text = text.split(",")[0].strip()
    text = _TRAILING_ZERO.sub("", text)
    text = _HEB_DIGIT.sub(" ", text)
    lead = _LEADING_NUMBER.match(text)
    if lead:
        text = f"{lead.group(2)} {lead.group(1)}"
    text = " ".join(text.split())
    if not re.search(r"[֐-׿A-Za-z]{2}", text):
        return "", False
    has_number = bool(re.search(r"\s\d+$", text))
    return text, has_number


def build_queries(address: str | None, city_name: str) -> list[tuple[str, str]]:
    """``[(expected precision, query text)]``, best first; at most two."""
    street, has_number = clean_address(address)
    if not street or not city_name:
        return []
    queries = [("address" if has_number else "street", f"{street}, {city_name}")]
    if has_number:
        bare = re.sub(r"\s\d+$", "", street)
        if bare:
            queries.append(("street", f"{bare}, {city_name}"))
    return queries


# --- judging a result --------------------------------------------------------------------------

_LOCALITY_KEYS = ("city", "town", "village", "hamlet", "municipality", "suburb", "city_district")


def judge_result(result: dict[str, Any], city_name: str) -> tuple[float, float, str] | None:
    """``(lat, lon, precision)`` when ``result`` is an address or street inside ``city_name``."""
    address = result.get("address") or {}
    try:
        lat, lon = float(result["lat"]), float(result["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not in_israel(lat, lon):
        return None
    if address.get("country_code", "il") != "il":
        return None
    if not any(names_match(city_name, address.get(k)) for k in _LOCALITY_KEYS):
        return None
    has_road = bool(address.get("road") or address.get("pedestrian"))
    if address.get("house_number") and has_road:
        return lat, lon, "address"
    if has_road and (result.get("category") or result.get("class")) == "highway":
        return lat, lon, "street"  # the street itself, no house number
    return None


def pick_result(results: list[dict[str, Any]], city_name: str) -> tuple[float, float, str] | None:
    """The best acceptable result: an address beats a street; ties keep Nominatim's order."""
    judged = [j for r in results if (j := judge_result(r, city_name))]
    if not judged:
        return None
    return min(judged, key=lambda j: RANK[j[2]])


# --- the run -----------------------------------------------------------------------------------


def infer_by_name(store: StoreInput, localities: dict[str, Locality]) -> Locality | None:
    """A locality whose name equals the store's name (after normalization), or None.

    Ambiguous matches (two localities with the same name) return None.
    """
    wanted = normalize_name(store.name)
    if not wanted:
        return None
    hits = [loc for loc in localities.values() if normalize_name(loc.name_he) == wanted]
    return hits[0] if len(hits) == 1 else None


def geocode_stores(
    stores: Iterable[StoreInput],
    localities: dict[str, Locality],
    client: NominatimClient | None,
    *,
    existing: dict[tuple[str, str], StoreGeocode] | None = None,
    max_stores: int = 100,
    now: datetime | None = None,
) -> tuple[list[StoreGeocode], RunStats]:
    """Geocode the stores that have no row in ``existing``; returns the new rows and the stats.

    ``max_stores`` bounds the stores sent to the geocoder in this run. With ``client`` None no
    request is made (only the name-match rows are produced).
    """
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = existing or {}
    stats = RunStats()
    new_rows: list[StoreGeocode] = []
    for store in stores:
        key = (store.chain_id, store.store_code)
        if key in existing:
            stats.skipped_existing += 1
            continue
        code = normalize_code(store.city)
        locality = localities.get(code) if code else None
        if code is None:
            stats.unknown_city_code += 1
            named = infer_by_name(store, localities)
            if named is not None:
                new_rows.append(
                    StoreGeocode(*key, named.lat, named.lon, "locality", SOURCE_NAME_MATCH, "", stamp)
                )
                stats.by_precision["locality"] += 1
            continue
        if locality is None:
            stats.no_city += 1
            continue
        if client is None:
            continue
        queries = build_queries(store.address, locality.name_he)
        if not queries:
            stats.skipped_online_or_no_address += 1
            continue
        if stats.attempted >= max_stores:
            stats.stopped = f"max_stores={max_stores} reached"
            break
        stats.attempted += 1
        found: tuple[float, float, str] | None = None
        used_hash = ""
        try:
            for _expected, text in queries:
                results, used_hash, _cached = client.search(text)
                found = pick_result(results, locality.name_he)
                if found is not None:
                    break
        except (Blocked, BudgetExhausted) as exc:
            stats.stopped = str(exc)
            stats.attempted -= 1
            break
        except GeocoderError:
            stats.errors += 1
            continue
        if found is None:
            stats.no_match += 1
            continue
        lat, lon, precision = found
        new_rows.append(StoreGeocode(*key, lat, lon, precision, SOURCE_NOMINATIM, used_hash, stamp))
        stats.by_precision[precision] += 1
    return new_rows, stats
