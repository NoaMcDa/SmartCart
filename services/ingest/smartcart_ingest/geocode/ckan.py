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
