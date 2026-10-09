"""Plain HTTP GET of JSON for the open-data sources (data.gov.il, Wikidata), standard library only.

Every request carries an honest, descriptive User-Agent (application name, project URL and a
contact) and ``Accept``. That is the polite convention for these services; it is not browser
impersonation, and a refusal (HTTP 403 and the like) is reported, never worked around.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

PROJECT_URL = "https://github.com/NoaMcDa/SmartCart"
DEFAULT_CONTACT = f"{PROJECT_URL}/issues"
APP = "SmartCart-geo/0.1"


def contact() -> str:
    return (
        os.environ.get("GEO_CONTACT") or os.environ.get("NOMINATIM_CONTACT") or DEFAULT_CONTACT
    ).strip() or DEFAULT_CONTACT


def user_agent() -> str:
    return f"{APP} (+{PROJECT_URL}; contact: {contact()})"


class HttpFailure(RuntimeError):
    """A non-2xx answer or a connection failure. ``status`` is None when there was no answer."""

    def __init__(self, status: int | None, message: str) -> None:
        self.status = status
        super().__init__(message)


@dataclass
class StatusLog:
    """Every request made through :func:`get_json`: ``(host + path, HTTP status or None)``."""

    entries: list[tuple[str, int | None]] = field(default_factory=list)

    def add(self, url: str, status: int | None) -> None:
        self.entries.append((url.split("?", 1)[0].removeprefix("https://"), status))

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for _, status in self.entries:
            key = str(status) if status is not None else "no-response"
            counts[key] = counts.get(key, 0) + 1
        return ", ".join(f"HTTP {k} x{v}" for k, v in sorted(counts.items())) or "no requests"

    def last_failure(self) -> int | None:
        bad = [s for _, s in self.entries if s is None or s >= 400]
        return bad[-1] if bad else None


def get_json(
    url: str,
    *,
    accept: str = "application/json",
    timeout: float = 60.0,
    log: StatusLog | None = None,
) -> Any:
    """GET ``url`` and decode the JSON body. Raises :class:`HttpFailure` otherwise."""
    req = urllib.request.Request(  # noqa: S310 (https URLs built by this package)
        url, headers={"User-Agent": user_agent(), "Accept": accept}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            status = resp.status
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if log is not None:
            log.add(url, exc.code)
        snippet = exc.read(200).decode("utf-8", "replace").replace("\n", " ") if exc.fp else ""
        raise HttpFailure(exc.code, f"HTTP {exc.code} {exc.reason} {snippet}".strip()) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        if log is not None:
            log.add(url, None)
        raise HttpFailure(None, f"request failed: {exc}") from exc
    if log is not None:
        log.add(url, status)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise HttpFailure(status, f"HTTP {status} but the body is not JSON: {body[:120]!r}") from exc


def get_bytes(
    url: str,
    *,
    accept: str = "*/*",
    timeout: float = 120.0,
    max_bytes: int = 30_000_000,
    log: StatusLog | None = None,
) -> bytes:
    """GET ``url`` and return the body (at most ``max_bytes``). Raises :class:`HttpFailure`."""
    req = urllib.request.Request(  # noqa: S310
        url, headers={"User-Agent": user_agent(), "Accept": accept}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            status = resp.status
            body = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        if log is not None:
            log.add(url, exc.code)
        raise HttpFailure(exc.code, f"HTTP {exc.code} {exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        if log is not None:
            log.add(url, None)
        raise HttpFailure(None, f"request failed: {exc}") from exc
    if log is not None:
        log.add(url, status)
    if len(body) > max_bytes:
        raise HttpFailure(status, f"body larger than {max_bytes} bytes")
    return body
