"""A polite OpenStreetMap Nominatim client (https://operations.osmfoundation.org/policies/nominatim/).

What the usage policy asks for, and how this client keeps to it:

* at most one request per second: every request waits until ``min_interval`` seconds have passed
  since the previous one (the policy's limit, enforced here, not left to the caller);
* a User-Agent that identifies the application, with a way to reach us: ``NOMINATIM_CONTACT``
  (an e-mail or a URL) is required and is put into the User-Agent; without it the client refuses
  to start rather than send an anonymous request;
* cache results: every answer, including an empty one, is stored in a local JSON-lines file keyed
  by the exact request, so no query is ever sent twice, across runs too. There is no "refresh"
  option on purpose; delete the cache file by hand if a re-run is really wanted;
* no bulk geocoding: a run has a request budget (``max_requests``); when it is spent the client
  raises :class:`BudgetExhausted` and the caller stops, leaving the rest for a later run;
* a 429 or 403 stops the run (:class:`Blocked`); the client never retries against a block.

Results are OpenStreetMap data, © OpenStreetMap contributors, under the ODbL
(https://www.openstreetmap.org/copyright). Anything derived from them that we publish carries
that attribution (docs/geocoding.md).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

BASE_URL = "https://nominatim.openstreetmap.org/search"
APP_NAME = "SmartCart-store-geocoder/0.1"
PROJECT_URL = "https://github.com/NoaMcDa/SmartCart"
ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"

Fetch = Callable[[str, Mapping[str, str], float], Any]
"""``fetch(url, headers, timeout)`` returns the decoded JSON; raises ``urllib.error.HTTPError``."""


class GeocoderError(RuntimeError):
    pass


class MissingContact(GeocoderError):
    """``NOMINATIM_CONTACT`` is not set."""


class BudgetExhausted(GeocoderError):
    """The run's request budget is spent."""


class Blocked(GeocoderError):
    """Nominatim answered 403 or 429: stop and do not retry."""


def user_agent(contact: str | None = None) -> str:
    contact = (contact or os.environ.get("NOMINATIM_CONTACT") or "").strip()
    if not contact:
        raise MissingContact(
            "set NOMINATIM_CONTACT to an e-mail address or URL where the operator can be reached "
            "(Nominatim's usage policy requires an identifying User-Agent)"
        )
    return f"{APP_NAME} (+{PROJECT_URL}; contact: {contact})"


def request_key(query: str, params: Mapping[str, str]) -> str:
    """Stable hash of one request: the query text (whitespace-normalized) plus the parameters."""
    canonical = json.dumps(
        {"q": " ".join(query.split()), **{k: str(v) for k, v in sorted(params.items())}},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _urllib_fetch(url: str, headers: Mapping[str, str], timeout: float) -> Any:
    req = urllib.request.Request(url, headers=dict(headers))  # noqa: S310 (https URL constant)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


_KEEP = (
    "lat",
    "lon",
    "category",
    "class",
    "type",
    "addresstype",
    "name",
    "display_name",
    "address",
)


def _trim(result: dict[str, Any]) -> dict[str, Any]:
    """Only the fields the judges read; keeps the committed cache small."""
    return {k: result[k] for k in _KEEP if k in result}


class NominatimClient:
    DEFAULT_PARAMS = {
        "format": "jsonv2",
        "addressdetails": "1",
        "countrycodes": "il",
        "accept-language": "he",
        "limit": "3",
    }

    def __init__(
        self,
        cache_path: Path,
        *,
        contact: str | None = None,
        max_requests: int = 100,
        min_interval: float = 1.0,
        timeout: float = 20.0,
        fetch: Fetch | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        base_url: str = BASE_URL,
    ) -> None:
        self.user_agent = user_agent(contact)
        self.cache_path = cache_path
        self.max_requests = max_requests
        # The policy's limit is one request per second; never go below it.
        self.min_interval = max(1.0, min_interval)
        self.timeout = timeout
        self._fetch = fetch or _urllib_fetch
        self._sleep = sleep
        self._clock = clock
        self.base_url = base_url
        self.requests_made = 0
        self.cache_hits = 0
        self._last_request: float | None = None
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._load()

    def _load(self) -> None:
        if not self.cache_path.is_file():
            return
        with self.cache_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._cache[entry["key"]] = entry["results"]

    def _store(self, key: str, query: str, results: list[dict[str, Any]]) -> None:
        self._cache[key] = results
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps({"key": key, "query": query, "results": results}, ensure_ascii=False)
                + "\n"
            )

    def search(self, query: str, **overrides: str) -> tuple[list[dict[str, Any]], str, bool]:
        """Geocode ``query``. Returns ``(results, request_key, from_cache)``."""
        params = {**self.DEFAULT_PARAMS, **overrides}
        key = request_key(query, params)
        if key in self._cache:
            self.cache_hits += 1
            return self._cache[key], key, True
        if self.requests_made >= self.max_requests:
            raise BudgetExhausted(f"request budget of {self.max_requests} is spent")
        if self._last_request is not None:
            wait = self.min_interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        url = self.base_url + "?" + urllib.parse.urlencode({"q": " ".join(query.split()), **params})
        self._last_request = self._clock()
        self.requests_made += 1
        try:
            data = self._fetch(
                url, {"User-Agent": self.user_agent, "Accept": "application/json"}, self.timeout
            )
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                raise Blocked(f"Nominatim answered HTTP {exc.code}; stopping") from exc
            raise GeocoderError(f"Nominatim answered HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GeocoderError(f"Nominatim request failed: {exc}") from exc
        results = [_trim(r) for r in data if isinstance(r, dict)] if isinstance(data, list) else []
        self._store(key, query, results)
        return results, key, False
