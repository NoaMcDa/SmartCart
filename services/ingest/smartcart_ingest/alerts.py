"""Ingestion alerts (issues #32, #42, #49).

An :class:`Alert` always goes to the structlog logger. When ``ALERT_WEBHOOK_URL`` is set it is
also POSTed there as JSON. The payload has a ``text`` field, so a Slack or Discord incoming
webhook shows it as-is, plus the structured fields for anything else.

Alerts fire on:

* ``parse_failure``   the adapter raised AdapterError for a file
* ``unknown_schema``  the adapter raised UnknownSchemaError (neither v1 nor v2)
* ``quarantine``      a file failed a quality gate
* ``load_failure``    the database load failed and was rolled back
* ``portal_failure``  a portal kept failing after the backoff cap
* ``quality_warning`` a soft quality warning (``quality.warnings``); the file is still loaded

A webhook that fails is logged and never interrupts ingestion.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol

import structlog

AlertKind = Literal[
    "parse_failure",
    "unknown_schema",
    "quarantine",
    "load_failure",
    "portal_failure",
    "quality_warning",
]

log = structlog.get_logger("smartcart_ingest.alerts")


@dataclass(frozen=True)
class Alert:
    chain_id: str
    kind: AlertKind
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def text(self) -> str:
        return f"[smartcart-ingest] {self.kind} chain={self.chain_id}: {self.message}"

    def payload(self) -> dict[str, Any]:
        return {"text": self.text(), **asdict(self)}


class AlertSink(Protocol):
    def send(self, alert: Alert) -> None: ...


class HttpClient(Protocol):
    def post_json(self, url: str, payload: dict[str, Any], timeout: float) -> int:
        """POST ``payload`` as JSON and return the HTTP status code."""
        ...


class UrllibClient:
    """Standard-library HTTP client, so alerts add no dependency."""

    def post_json(self, url: str, payload: dict[str, Any], timeout: float) -> int:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST", headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status)


class LogSink:
    def send(self, alert: Alert) -> None:
        log.error(
            "alert",
            alert_kind=alert.kind,
            chain_id=alert.chain_id,
            message=alert.message,
            **{f"detail_{k}": v for k, v in alert.details.items()},
        )


class WebhookSink:
    def __init__(self, url: str, client: HttpClient | None = None, timeout: float = 10.0) -> None:
        self.url = url
        self.client = client or UrllibClient()
        self.timeout = timeout

    def send(self, alert: Alert) -> None:
        try:
            status = self.client.post_json(self.url, alert.payload(), self.timeout)
        except Exception as exc:  # never let alerting break ingestion
            log.warning("alert webhook failed", error=str(exc), alert_kind=alert.kind)
            return
        if status >= 400:
            log.warning("alert webhook rejected", status=status, alert_kind=alert.kind)


class Alerter:
    """Fans an alert out to every sink. Keeps the alerts it sent (handy for run reports)."""

    def __init__(self, sinks: Iterable[AlertSink]) -> None:
        self.sinks = list(sinks)
        self.sent: list[Alert] = []

    def send(self, alert: Alert) -> None:
        self.sent.append(alert)
        for sink in self.sinks:
            sink.send(alert)

    def __call__(self, chain_id: str, kind: AlertKind, message: str, **details: Any) -> Alert:
        alert = Alert(chain_id, kind, message, details)
        self.send(alert)
        return alert


def build_alerter(webhook_url: str | None, client: HttpClient | None = None) -> Alerter:
    sinks: list[AlertSink] = [LogSink()]
    if webhook_url:
        sinks.append(WebhookSink(webhook_url, client))
    return Alerter(sinks)
