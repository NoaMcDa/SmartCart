"""Read the locality list from data.gov.il (a CKAN site) through its public API.

``datastore_search`` pages through one resource; ``package_search`` finds candidates when no
resource id is given. All requests are plain GETs of public open data; the User-Agent names the
project. The functions take a ``fetch`` callable so the tests run without a network.
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Callable, Iterator
from typing import Any

from smartcart_ingest.geocode.http import StatusLog, get_json
from smartcart_ingest.geocode.localities import classify_fields

BASE_URL = "https://data.gov.il"
DEFAULT_QUERIES = ("ערים ויישובים", "רשימת יישובים", "יישובים", "localities")
PAGE = 5000

JsonFetch = Callable[[str], Any]


def http_json(url: str, timeout: float = 60.0, log: StatusLog | None = None) -> Any:
    """GET with the descriptive User-Agent of :mod:`smartcart_ingest.geocode.http`."""
    return get_json(url, timeout=timeout, log=log)


def _api(base: str, action: str, **params: object) -> str:
    return f"{base}/api/3/action/{action}?" + urllib.parse.urlencode(params)


def datastore_records(
    resource_id: str, *, base: str = BASE_URL, fetch: JsonFetch = http_json
) -> Iterator[dict[str, Any]]:
    offset = 0
    while True:
        payload = fetch(
            _api(base, "datastore_search", resource_id=resource_id, limit=PAGE, offset=offset)
        )
        records = payload["result"]["records"]
        yield from records
        offset += len(records)
        total = payload["result"].get("total")
        if not records or len(records) < PAGE or (total is not None and offset >= total):
            return


def resource_fields(
    resource_id: str, *, base: str = BASE_URL, fetch: JsonFetch = http_json
) -> list[str]:
    payload = fetch(_api(base, "datastore_search", resource_id=resource_id, limit=1))
    return [f["id"] for f in payload["result"].get("fields", []) if f["id"] != "_id"]


def discover(
    queries: tuple[str, ...] = DEFAULT_QUERIES,
    *,
    base: str = BASE_URL,
    fetch: JsonFetch = http_json,
) -> list[dict[str, str]]:
    """Datastore resources whose fields look like a locality list: ``[{id, kind, package, name}]``,
    resources with coordinates first. An error on one candidate skips that candidate."""
    seen: set[str] = set()
    found: list[dict[str, str]] = []
    for query in queries:
        try:
            payload = fetch(_api(base, "package_search", q=query, rows=20))
        except Exception:  # noqa: BLE001 (a failing query must not hide the others)
            continue
        for package in payload["result"].get("results", []):
            for res in package.get("resources", []):
                rid = res.get("id")
                if not rid or rid in seen or not res.get("datastore_active"):
                    continue
                seen.add(rid)
                try:
                    kind = classify_fields(resource_fields(rid, base=base, fetch=fetch))
                except Exception:  # noqa: BLE001
                    continue
                if kind:
                    found.append(
                        {
                            "id": rid,
                            "kind": kind,
                            "package": package.get("name", ""),
                            "name": res.get("name", ""),
                        }
                    )
    return sorted(found, key=lambda r: r["kind"] != "coords")


# --- the resources' own files (CSV / XLSX), tried before the datastore API --------------------------

SEED_PACKAGES = ("localities-in-israel", "citiesandsettelments")
"""Datasets seen in the first workflow runs: the CBS "קובץ היישובים" and the settlement list."""
FILE_FORMATS = {"CSV", "XLSX", "XLS", "TSV"}


def rank_resource(package_name: str, resource: dict[str, Any]) -> int:
    """Higher is better: the CBS locality file first, then anything about settlements."""
    name = str(resource.get("name") or "")
    score = 0
    if "קובץ היישובים" in name or "קובץ הישובים" in name:
        score += 10
    if "יישוב" in name or "ישוב" in name:
        score += 3
    if package_name in SEED_PACKAGES:
        score += 5
    if package_name == "localities-in-israel":
        score += 2
    if str(resource.get("format") or "").upper() in {"XLSX", "CSV"}:
        score += 2
    return score


def resource_candidates(
    queries: tuple[str, ...] = DEFAULT_QUERIES,
    *,
    seeds: tuple[str, ...] = SEED_PACKAGES,
    base: str = BASE_URL,
    fetch: JsonFetch = http_json,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Resources of the locality datasets, best first: ``[{id, name, format, url, package,
    datastore_active, score}]``. Uses ``package_show`` (seeds) and ``package_search``, which answer
    where the datastore API may not. A resource qualifies with a file URL (CSV/XLSX/XLS) or an
    active datastore."""
    packages: dict[str, dict[str, Any]] = {}
    for name in seeds:
        try:
            pkg = fetch(_api(base, "package_show", id=name))["result"]
            packages[pkg.get("name", name)] = pkg
        except Exception:  # noqa: BLE001
            continue
    for query in queries:
        try:
            payload = fetch(_api(base, "package_search", q=query, rows=20))
        except Exception:  # noqa: BLE001
            continue
        for pkg in payload["result"].get("results", []):
            packages.setdefault(pkg.get("name", pkg.get("id", "")), pkg)
    found: dict[str, dict[str, Any]] = {}
    for pname, pkg in packages.items():
        for res in pkg.get("resources", []):
            rid = res.get("id")
            fmt = str(res.get("format") or "").upper()
            url = res.get("url") or ""
            has_file = bool(url) and (
                fmt in FILE_FORMATS or url.lower().split("?")[0].endswith((".csv", ".xlsx", ".xls"))
            )
            if not rid or not (has_file or res.get("datastore_active")):
                continue
            found[rid] = {
                "id": rid,
                "name": res.get("name", ""),
                "format": fmt,
                "url": url if has_file else "",
                "package": pname,
                "datastore_active": bool(res.get("datastore_active")),
                "score": rank_resource(pname, res),
            }
    ranked = sorted(found.values(), key=lambda r: (-r["score"], r["package"], r["id"]))
    return ranked[:limit]
