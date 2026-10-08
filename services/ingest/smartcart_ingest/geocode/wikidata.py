"""Israeli localities with their CBS code and coordinates from Wikidata (a second source).

data.gov.il's CKAN API refuses some cloud ranges (HTTP 403 from a GitHub runner), so the locality
table has a second source that runners can reach: the Wikidata Query Service
(https://query.wikidata.org/sparql). Wikidata items for Israeli settlements carry the CBS locality
code (a property found by label, below) and coordinates (P625); the data is CC0.

One discovery query finds the property id by label (it only reads the ~12k property entities), one
query fetches every item that has both the code and a coordinate. Both are single GETs with a
descriptive User-Agent, within the service's limits (60 s query time, one request at a time).
The property id can be pinned (``--wikidata-property P123`` or ``WIKIDATA_CBS_PROPERTY``), which
skips discovery.
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable
from typing import Any

from smartcart_ingest.geocode.itm import in_israel
from smartcart_ingest.geocode.localities import Locality, normalize_code

ENDPOINT = "https://query.wikidata.org/sparql"
SOURCE = "wikidata"
ACCEPT = "application/sparql-results+json"

SparqlFetch = Callable[[str], Any]
"""``fetch(url)`` returns the decoded SPARQL JSON result."""

PROPERTY_QUERY = """
SELECT ?prop ?label WHERE {
  ?prop a wikibase:Property ; rdfs:label ?label .
  FILTER(LANG(?label) = "en")
  FILTER(CONTAINS(LCASE(STR(?label)), "central bureau of statistics"))
}
""".strip()

_PROPERTY_ID = re.compile(r"/entity/(P\d+)$")
_ITEM_ID = re.compile(r"/entity/(Q\d+)$")
_POINT = re.compile(r"^Point\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)$")


def sparql_url(query: str) -> str:
    return ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})


def locality_query(prop: str) -> str:
    if not re.fullmatch(r"P\d+", prop):
        raise ValueError(f"not a Wikidata property id: {prop!r}")
    return f"""
SELECT ?item ?code ?coord ?he ?en WHERE {{
  ?item wdt:{prop} ?code ;
        wdt:P625 ?coord .
  OPTIONAL {{ ?item rdfs:label ?he . FILTER(LANG(?he) = "he") }}
  OPTIONAL {{ ?item rdfs:label ?en . FILTER(LANG(?en) = "en") }}
}}
""".strip()


def _score(label: str) -> int:
    text = label.casefold()
    return (
        ("locality" in text or "settlement" in text) * 4
        + ("israel" in text) * 2
        + ("code" in text or "id" in text.split()) * 1
    )


def pick_property(payload: dict[str, Any]) -> tuple[str | None, list[tuple[str, str]]]:
    """``(best property id or None, [(id, label), ...] all candidates)`` from the discovery result.

    A candidate must mention locality or settlement; among those the best score wins, ties go to
    the lowest property number. Returns None when nothing qualifies (the caller then fails
    loudly instead of guessing).
    """
    candidates: list[tuple[str, str]] = []
    for row in payload.get("results", {}).get("bindings", []):
        m = _PROPERTY_ID.search(row.get("prop", {}).get("value", ""))
        if m:
            candidates.append((m.group(1), row.get("label", {}).get("value", "")))
    qualifying = [c for c in candidates if _score(c[1]) >= 4]
    if not qualifying:
        return None, candidates
    best = min(qualifying, key=lambda c: (-_score(c[1]), int(c[0][1:])))
    return best[0], candidates


def parse_localities(
    payload: dict[str, Any], *, retrieved_at: str
) -> tuple[list[Locality], dict[str, int]]:
    """Table rows from the locality query's result, plus counts of what was dropped.

    One row per CBS code. When several items share a code the lowest item number (Q-id) wins and
    ``duplicate_codes`` counts the extras. A point that is not ``Point(lon lat)`` or lies outside
    Israel's bounding box is dropped. A row needs a Hebrew label (``name_he``).
    """
    skipped = {"no_code": 0, "bad_point": 0, "outside_israel": 0, "no_name": 0, "duplicate_codes": 0}
    best: dict[str, tuple[int, Locality]] = {}
    for row in payload.get("results", {}).get("bindings", []):
        code = normalize_code(row.get("code", {}).get("value"))
        if code is None:
            skipped["no_code"] += 1
            continue
        point = _POINT.match(row.get("coord", {}).get("value", ""))
        if not point:
            skipped["bad_point"] += 1
            continue
        lon, lat = float(point.group(1)), float(point.group(2))
        if not in_israel(lat, lon):
            skipped["outside_israel"] += 1
            continue
        name_he = row.get("he", {}).get("value", "").strip()
        if not name_he:
            skipped["no_name"] += 1
            continue
        item = _ITEM_ID.search(row.get("item", {}).get("value", ""))
        qid = int(item.group(1)[1:]) if item else 10**12
        loc = Locality(
            code=code,
            name_he=name_he,
            name_en=row.get("en", {}).get("value", "").strip(),
            lat=round(lat, 6),
            lon=round(lon, 6),
            source=SOURCE,
            retrieved_at=retrieved_at,
        )
        if code in best:
            skipped["duplicate_codes"] += 1
            if qid >= best[code][0]:
                continue
        best[code] = (qid, loc)
    return [loc for _, loc in best.values()], skipped


def fetch_localities(
    fetch: SparqlFetch, *, retrieved_at: str, prop: str | None = None
) -> tuple[list[Locality], dict[str, int], str | None]:
    """Run the discovery (unless ``prop`` is given) and the locality query.

    Returns ``(rows, skipped counts, property id used)``; the property id is None when discovery
    found nothing (rows is then empty).
    """
    if prop is None:
        prop, _candidates = pick_property(fetch(sparql_url(PROPERTY_QUERY)))
        if prop is None:
            return [], {}, None
    payload = fetch(sparql_url(locality_query(prop)))
    rows, skipped = parse_localities(payload, retrieved_at=retrieved_at)
    return rows, skipped, prop
