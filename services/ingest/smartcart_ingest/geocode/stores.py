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
SOURCE_NOMINATIM_TEXT = "nominatim:city-from-text"


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
    by_source: Counter[str] = field(default_factory=Counter)


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


_CITY_KEYS = ("city", "town", "village", "hamlet", "municipality")
"""Address keys that name a settlement (a suburb or district is not enough to name the city)."""


def city_in_text(city: str | None, text: str) -> bool:
    """True when ``city`` (or, for a hyphenated name, one of its parts) appears in ``text`` as whole
    words, after normalization. ``תל אביב-יפו`` is found in ``קרפור תל אביב``."""
    if not city:
        return False
    padded = f" {normalize_name(text)} "
    variants = {city, *(part for part in re.split(r"\s*-\s*", city) if len(part.strip()) >= 3)}
    return any(
        (n := normalize_name(v)) and f" {n} " in padded for v in variants
    )


def judge_result(
    result: dict[str, Any], city_name: str | None, *, text: str | None = None
) -> tuple[float, float, str] | None:
    """``(lat, lon, precision)`` when ``result`` is an address or street in the store's city.

    With ``city_name`` the returned locality must match it (:func:`names_match`). With ``text``
    instead (the store's city code is unknown) the returned city must appear in the store's own
    address or name (:func:`city_in_text`).
    """
    address = result.get("address") or {}
    try:
        lat, lon = float(result["lat"]), float(result["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not in_israel(lat, lon):
        return None
    if address.get("country_code", "il") != "il":
        return None
    if text is not None:
        if not any(city_in_text(address.get(k), text) for k in _CITY_KEYS):
            return None
    elif not any(names_match(city_name, address.get(k)) for k in _LOCALITY_KEYS):
        return None
    has_road = bool(address.get("road") or address.get("pedestrian"))
    if address.get("house_number") and has_road:
        return lat, lon, "address"
    if has_road and (result.get("category") or result.get("class")) == "highway":
        return lat, lon, "street"  # the street itself, no house number
    return None


def pick_result(
    results: list[dict[str, Any]], city_name: str | None, *, text: str | None = None
) -> tuple[float, float, str] | None:
    """The best acceptable result: an address beats a street; ties keep Nominatim's order."""
    judged = [j for r in results if (j := judge_result(r, city_name, text=text))]
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


def text_queries(store: StoreInput) -> list[str]:
    """Queries for a store whose city code gives no locality: the address alone, then the address
    with the store's name (a chain often names a branch after its town). The answer is accepted
    only if the city it returns appears in that same text (:func:`city_in_text`)."""
    street, _has_number = clean_address(store.address)
    if not street:
        return []
    queries = [street]
    name = " ".join((store.name or "").split())
    if name and normalize_name(name) not in normalize_name(street):
        queries.append(f"{street}, {name}")
    return queries


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

    A store whose city code is in the locality table is queried as ``"<address>, <city name>"`` and
    the answer must name that city (source ``nominatim``). A store whose code is unknown or not in
    the table is queried by its address text alone and the answer is accepted only if the city it
    returns appears in the store's own address or name (source ``nominatim:city-from-text``; the
    precision label stays what the result is, a house or a street). If that fails, a store named
    exactly like a locality gets that locality's centroid (``cbs-name-match``, ``locality``).
    """
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = existing or {}
    stats = RunStats()
    new_rows: list[StoreGeocode] = []
    budget_spent = False
    for store in stores:
        key = (store.chain_id, store.store_code)
        if key in existing:
            stats.skipped_existing += 1
            continue
        code = normalize_code(store.city)
        locality = localities.get(code) if code else None
        if code is None:
            stats.unknown_city_code += 1
        elif locality is None:
            stats.no_city += 1

        found: tuple[float, float, str] | None = None
        used_hash = ""
        source = SOURCE_NOMINATIM
        if client is not None and not budget_spent:
            if locality is not None:
                queries = [text for _expected, text in build_queries(store.address, locality.name_he)]
                search: dict[str, str] = {}
            else:
                queries = text_queries(store)
                search = {"limit": "10"}
                source = SOURCE_NOMINATIM_TEXT
            if not queries:
                stats.skipped_online_or_no_address += 1
            elif stats.attempted >= max_stores:
                budget_spent = True
                stats.stopped = f"max_stores={max_stores} reached"
            else:
                stats.attempted += 1
                text_check = None if locality is not None else f"{store.address or ''} {store.name}"
                try:
                    for query in queries:
                        results, used_hash, _cached = client.search(query, **search)
                        found = pick_result(
                            results, locality.name_he if locality else None, text=text_check
                        )
                        if found is not None:
                            break
                except (Blocked, BudgetExhausted) as exc:
                    stats.stopped = str(exc)
                    stats.attempted -= 1
                    budget_spent = True
                except GeocoderError:
                    stats.errors += 1
                else:
                    if found is None:
                        stats.no_match += 1
        if found is not None:
            lat, lon, precision = found
            new_rows.append(StoreGeocode(*key, lat, lon, precision, source, used_hash, stamp))
            stats.by_precision[precision] += 1
            stats.by_source[source] += 1
            continue
        if code is None:
            named = infer_by_name(store, localities)
            if named is not None:
                new_rows.append(
                    StoreGeocode(*key, named.lat, named.lon, "locality", SOURCE_NAME_MATCH, "", stamp)
                )
                stats.by_precision["locality"] += 1
                stats.by_source[SOURCE_NAME_MATCH] += 1
    return new_rows, stats
