"""The locality table: CBS locality code to a centroid in WGS 84.

The numeric ``City`` of a transparency Stores file is the Central Bureau of Statistics locality
code. ``data/geo/localities.csv`` maps it to a name and a centroid:

    code,name_he,name_en,lat,lon,source,retrieved_at

Rows come from ``scripts/geo/fetch_localities.py`` (the official list on data.gov.il) and nowhere
else. A code the source does not give coordinates for stays out of the table; this module never
fills a gap with a guess. ``0``, empty and non-numeric codes mean "unknown" and resolve to nothing.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from smartcart_ingest.geocode.itm import in_israel, itm_to_wgs84

FIELDS = ("code", "name_he", "name_en", "lat", "lon", "source", "retrieved_at")


@dataclass(frozen=True)
class Locality:
    code: str
    name_he: str
    name_en: str
    lat: float
    lon: float
    source: str
    retrieved_at: str


def normalize_code(raw: object) -> str | None:
    """``' 0874 '`` to ``'874'``; ``0``, empty, ``None`` and non-numeric values to ``None``."""
    text = str(raw).strip() if raw is not None else ""
    if text.endswith(".0"):
        text = text[:-2]
    if not text.isdigit():
        return None
    text = text.lstrip("0")
    return text or None


_QUOTES = re.compile(r"[\"'`׳״’”]")
_SEPARATORS = re.compile(r"[-‐‑‒–—־_/,()]+")
"""Hyphens, dashes and the Hebrew maqaf (U+05BE): OSM writes ``תל־אביב–יפו``, the CBS ``תל אביב -יפו``."""
_SPACES = re.compile(r"\s+")


def normalize_name(name: str | None) -> str:
    """A comparison key for a Hebrew place name: no quotes, hyphens as spaces, one spelling of
    "Kiryat" (קרית/קריית), single spaces. Used to compare a store's city with a geocoder's."""
    text = _QUOTES.sub("", name or "")
    text = _SEPARATORS.sub(" ", text)
    text = _SPACES.sub(" ", text).strip()
    return text.replace("קריית", "קרית").replace("קריה", "קרית")


def names_match(a: str | None, b: str | None) -> bool:
    """Same place name: equal after normalization, or one is the other plus extra words
    (``תל אביב`` / ``תל אביב יפו``). Single-word containment is not enough on its own."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = na.split(), nb.split()
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return len(short) < len(long_) and long_[: len(short)] == short


def load_localities(path: Path) -> dict[str, Locality]:
    """The table at ``path`` keyed by normalized code; a missing file is an empty table."""
    if not path.is_file():
        return {}
    out: dict[str, Locality] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            code = normalize_code(row.get("code"))
            try:
                lat, lon = float(row["lat"]), float(row["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if code is None or not in_israel(lat, lon):
                continue
            out[code] = Locality(
                code=code,
                name_he=(row.get("name_he") or "").strip(),
                name_en=(row.get("name_en") or "").strip(),
                lat=lat,
                lon=lon,
                source=(row.get("source") or "").strip(),
                retrieved_at=(row.get("retrieved_at") or "").strip(),
            )
    return out


def write_localities(path: Path, rows: Iterable[Locality]) -> int:
    ordered = sorted(rows, key=lambda r: int(r.code))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(FIELDS)
        for r in ordered:
            writer.writerow(
                [r.code, r.name_he, r.name_en, f"{r.lat:.6f}", f"{r.lon:.6f}", r.source, r.retrieved_at]
            )
    return len(ordered)


# --- reading the source list (data.gov.il CKAN records) ---------------------------------------

_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "code": ("סמל יישוב", "סמל ישוב", "סמל_ישוב", "סמל_יישוב", "קוד יישוב", "yishuv_code",
             "locality_code", "code", "symbol", "סמל"),  # fmt: skip
    "name_he": ("שם יישוב", "שם ישוב", "שם_ישוב", "שם_יישוב", "yishuv_name", "locality_name",
                "name_he", "name"),  # fmt: skip
    "name_en": ("שם יישוב באנגלית", "שם_ישוב_לועזי", "שם_יישוב_לועזי", "english_name",
                "name_en", "yishuv_name_en"),  # fmt: skip
    "lat": ("lat", "latitude", "קו רוחב", "רוחב"),
    "lon": ("lon", "lng", "long", "longitude", "קו אורך", "אורך"),
    "x": ("x", "itm_x", "x_itm", "east", "easting", "קואורדינטה x", "קואורדינטת x", "קואורדינטה_x"),
    "y": ("y", "itm_y", "y_itm", "north", "northing", "קואורדינטה y", "קואורדינטת y", "קואורדינטה_y"),
}


def _key(name: str) -> str:
    return _SPACES.sub(" ", name.replace("_", " ").strip().casefold())


_SETTLEMENT = {"יישוב", "ישוב", "יישובים", "ישובים", "yishuv", "locality", "settlement"}
_ENGLISH = {"אנגלית", "לועזי", "לועזית", "english", "en", "eng"}


def _tokens(header: str) -> set[str]:
    return {t for t in re.split(r"[^\w\u0590-\u05ff]+", _key(header)) if t}


def _fuzzy(field: str, headers: Iterable[str]) -> str | None:
    """Looser header matching for files whose headers are not exactly the aliases (token rules)."""
    for h in headers:
        t = _tokens(h)
        settle = bool(t & _SETTLEMENT)
        english = bool(t & _ENGLISH)
        named = bool(t & {"שם", "name"})
        if field == "code" and settle and t & {"סמל", "קוד", "code", "symbol", "id"}:
            return h
        if field == "name_en" and settle and english and named:
            return h
        if field == "name_he" and settle and named and not english:
            return h
        if field == "x" and t & {"x", "itm_x", "east", "easting", "מזרח"} and not t & {"y"}:
            return h
        if field == "y" and t & {"y", "itm_y", "north", "northing", "צפון"} and not t & {"x"}:
            return h
        if field == "lat" and t & {"lat", "latitude"}:
            return h
        if field == "lon" and t & {"lon", "lng", "long", "longitude"}:
            return h
    return None


def detect_columns(headers: Iterable[str]) -> dict[str, str]:
    """Map our field names to the source's header names (an exact alias first, then token rules)."""
    headers = list(headers)
    by_key = {_key(h): h for h in headers}
    found: dict[str, str] = {}
    for field, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if _key(alias) in by_key:
                found[field] = by_key[_key(alias)]
                break
    for field in _COLUMN_ALIASES:
        if field not in found and (h := _fuzzy(field, headers)):
            found[field] = h
    return found


def _number(value: object) -> float | None:
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def localities_from_records(
    records: Iterable[Mapping[str, object]], *, source: str, retrieved_at: str
) -> tuple[list[Locality], dict[str, int]]:
    """Convert CKAN records to table rows, plus counts of what was left out and why.

    A record becomes a row only with a code, a Hebrew name and coordinates: WGS 84 ``lat``/``lon``
    columns, else ITM ``x``/``y`` converted with :func:`itm_to_wgs84`. A converted point outside
    Israel's bounding box is dropped (a unit or datum mix-up must not become a coordinate).
    """
    rows: dict[str, Locality] = {}
    skipped = {"no_code": 0, "no_name": 0, "no_coordinates": 0, "outside_israel": 0}
    columns: dict[str, str] | None = None
    for record in records:
        if columns is None:
            columns = detect_columns(record.keys())
        code = normalize_code(record.get(columns.get("code", "")))
        if code is None:
            skipped["no_code"] += 1
            continue
        name = str(record.get(columns.get("name_he", ""), "") or "").strip()
        if not name:
            skipped["no_name"] += 1
            continue
        lat = _number(record.get(columns.get("lat", "")))
        lon = _number(record.get(columns.get("lon", "")))
        if lat is None or lon is None:
            x, y = _number(record.get(columns.get("x", ""))), _number(record.get(columns.get("y", "")))
            if x is None or y is None or x <= 0 or y <= 0:
                skipped["no_coordinates"] += 1
                continue
            lat, lon = itm_to_wgs84(x, y)
        if not in_israel(lat, lon):
            skipped["outside_israel"] += 1
            continue
        rows[code] = Locality(
            code=code,
            name_he=name,
            name_en=str(record.get(columns.get("name_en", ""), "") or "").strip(),
            lat=round(lat, 6),
            lon=round(lon, 6),
            source=source,
            retrieved_at=retrieved_at,
        )
    return list(rows.values()), skipped


def classify_fields(field_names: Iterable[str]) -> str | None:
    """``"coords"`` when the fields give a code, a name and coordinates (WGS 84 or ITM),
    ``"names"`` when they give a code and a name only, else None."""
    cols = detect_columns(field_names)
    if "code" not in cols or "name_he" not in cols:
        return None
    if {"lat", "lon"} <= cols.keys() or {"x", "y"} <= cols.keys():
        return "coords"
    return "names"


def names_from_records(records: Iterable[Mapping[str, object]]) -> dict[str, tuple[str, str]]:
    """``{code: (name_he, name_en)}`` for records that have a code and a Hebrew name."""
    out: dict[str, tuple[str, str]] = {}
    columns: dict[str, str] | None = None
    for record in records:
        if columns is None:
            columns = detect_columns(record.keys())
        code = normalize_code(record.get(columns.get("code", "")))
        name = str(record.get(columns.get("name_he", ""), "") or "").strip()
        if code and name:
            out[code] = (name, str(record.get(columns.get("name_en", ""), "") or "").strip())
    return out


_PLACE_TYPES = {"city", "town", "village", "hamlet", "municipality", "locality", "suburb", "island"}


def centroid_from_nominatim(client: Any, name_he: str) -> tuple[float, float, str] | None:
    """The OSM place centroid for a locality name: ``(lat, lon, request_key)`` or None.

    Only a result that is a ``place`` of a settlement type, inside Israel, whose own name matches
    ``name_he`` is accepted; the first such result wins (Nominatim orders by importance).
    """
    results, key, _cached = client.search(name_he, limit="5")
    for r in results:
        if (r.get("category") or r.get("class")) != "place" or r.get("type") not in _PLACE_TYPES:
            continue
        try:
            lat, lon = float(r["lat"]), float(r["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not in_israel(lat, lon):
            continue
        shown = r.get("name") or (r.get("address") or {}).get(r.get("type", ""), "")
        if names_match(name_he, shown):
            return lat, lon, key
    return None
