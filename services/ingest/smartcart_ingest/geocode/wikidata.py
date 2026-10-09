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


API = "https://www.wikidata.org/w/api.php"
SEARCH_TERMS: tuple[tuple[str, str], ...] = (
    ("en", "Central Bureau of Statistics"),
    ("en", "Israel locality"),
    ("en", "Israeli settlement"),
    ("en", "CBS code"),
    ("he", "הלשכה המרכזית לסטטיסטיקה"),
    ("he", "סמל יישוב"),
)
"""Property searches (``wbsearchentities``): language and text."""

# Items whose CBS locality code is well known: Tel Aviv-Yafo 5000, Jerusalem 3000, Haifa 4000. The
# property that holds those exact values on those items is the CBS locality code, whatever it is
# called. (If a Q-id here were wrong, that item simply matches nothing.)
SIGNATURE_ITEMS: tuple[tuple[str, str], ...] = (
    ("Q33935", "5000"),
    ("Q1218", "3000"),
    ("Q41621", "4000"),
)
SIGNATURE_QUERY = (
    "SELECT ?item ?prop ?label WHERE { VALUES (?item ?code) { "
    + " ".join(f'(wd:{q} "{c}")' for q, c in SIGNATURE_ITEMS)
    + " } ?item ?wdt ?v . FILTER(STR(?v) = ?code) "
    '?prop wikibase:directClaim ?wdt ; rdfs:label ?label . FILTER(LANG(?label) = "en") }'
)


def search_url(term: str, language: str) -> str:
    return (
        API
        + "?"
        + urllib.parse.urlencode(
            {
                "action": "wbsearchentities",
                "type": "property",
                "language": language,
                "uselang": language,
                "search": term,
                "limit": 50,
                "format": "json",
            }
        )
    )


def parse_search(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    """``[(property id, label, description)]`` from a ``wbsearchentities`` answer."""
    out = []
    for hit in payload.get("search", []):
        if re.fullmatch(r"P\d+", hit.get("id", "")):
            out.append((hit["id"], hit.get("label", ""), hit.get("description", "")))
    return out


def score_search_hit(label: str, description: str) -> int:
    """How much a property looks like "Israeli locality code": needs Israel and a locality word."""
    text = f"{label} {description}".casefold()
    israel = "israel" in text or "ישראל" in text
    place = any(
        w in text for w in ("locality", "localities", "settlement", "yishuv", "יישוב", "ישוב")
    )
    code = any(w in text for w in ("code", "identifier", "id", "סמל", "מזהה", "מספר"))
    cbs = (
        "central bureau of statistics" in text
        or "cbs" in text
        or "הלמ" in text
        or "לסטטיסטיקה" in text
    )
    if not (israel and place):
        return 0
    return 4 + 2 * code + 2 * cbs


def parse_signature(payload: dict[str, Any]) -> dict[str, tuple[str, int]]:
    """``{property id: (label, number of signature items it matches)}``."""
    hits: dict[str, tuple[str, set[str]]] = {}
    for row in payload.get("results", {}).get("bindings", []):
        m = _PROPERTY_ID.search(row.get("prop", {}).get("value", ""))
        if not m:
            continue
        label, items = hits.setdefault(m.group(1), (row.get("label", {}).get("value", ""), set()))
        items.add(row.get("item", {}).get("value", ""))
    return {pid: (label, len(items)) for pid, (label, items) in hits.items()}


def discover_property(
    fetch: SparqlFetch, log: Callable[[str], None] = lambda _line: None
) -> tuple[str | None, str]:
    """Find the CBS locality-code property. Returns ``(property id or None, how it was found)``.

    1. ``wbsearchentities`` for several terms (every hit is logged); the best hit whose description
       says Israel and locality/settlement wins.
    2. The signature query: the property that holds 5000/3000/4000 on Tel Aviv/Jerusalem/Haifa. A
       property matching at least two of them is taken over a search hit (it is a fact, not a name).
    3. The label query on "Central Bureau of Statistics".
    Everything found is logged, so the choice can be checked in the workflow log.
    """
    best_search: tuple[int, str] | None = None
    for language, term in SEARCH_TERMS:
        try:
            hits = parse_search(fetch(search_url(term, language)))
        except Exception as exc:  # noqa: BLE001 (one failing search must not stop the others)
            log(f"  wikidata search [{language}] {term!r}: error {type(exc).__name__}: {exc}")
            continue
        log(f"  wikidata search [{language}] {term!r}: {len(hits)} properties")
        for pid, label, description in hits:
            score = score_search_hit(label, description)
            log(f"    {pid} | {label} | {description} | score {score}")
            if score and (
                best_search is None
                or (score, -int(pid[1:])) > (best_search[0], -int(best_search[1][1:]))
            ):
                best_search = (score, pid)
    try:
        signature = parse_signature(fetch(sparql_url(SIGNATURE_QUERY)))
    except Exception as exc:  # noqa: BLE001
        log(f"  wikidata signature query: error {type(exc).__name__}: {exc}")
        signature = {}
    for pid, (label, n) in sorted(signature.items(), key=lambda kv: -kv[1][1]):
        log(f"    signature {pid} | {label} | matches {n} of {len(SIGNATURE_ITEMS)} known codes")
    strong = [(n, pid) for pid, (_l, n) in signature.items() if n >= 2]
    if strong:
        return max(strong, key=lambda t: (t[0], -int(t[1][1:])))[
            1
        ], "signature (holds the known codes)"
    if best_search:
        return best_search[1], "search (description names Israel and localities)"
    try:
        prop, candidates = pick_property(fetch(sparql_url(PROPERTY_QUERY)))
    except Exception as exc:  # noqa: BLE001
        log(f"  wikidata label query: error {type(exc).__name__}: {exc}")
        return None, "none"
    for pid, label in candidates:
        log(f"    label query {pid} | {label}")
    return prop, "label query" if prop else "none"


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
    skipped = {
        "no_code": 0,
        "bad_point": 0,
        "outside_israel": 0,
        "no_name": 0,
        "duplicate_codes": 0,
    }
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
    fetch: SparqlFetch,
    *,
    retrieved_at: str,
    prop: str | None = None,
    log: Callable[[str], None] = lambda _line: None,
) -> tuple[list[Locality], dict[str, int], str | None]:
    """Run the discovery (unless ``prop`` is given) and the locality query.

    Returns ``(rows, skipped counts, property id used)``; the property id is None when discovery
    found nothing (rows is then empty).
    """
    if prop is None:
        prop, how = discover_property(fetch, log)
        log(f"  wikidata property: {prop} ({how})")
        if prop is None:
            return [], {}, None
    payload = fetch(sparql_url(locality_query(prop)))
    rows, skipped = parse_localities(payload, retrieved_at=retrieved_at)
    return rows, skipped, prop
