"""Alerts: sinks, and the pipeline events that fire them (issues #32, #42, #49)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from structlog.testing import capture_logs

from smartcart_ingest.alerts import Alert, LogSink, WebhookSink, build_alerter
from tests.fakes import NOW, encode, item, make_harness, price, statuses


class FakeHttp:
    def __init__(self, status: int = 200, error: Exception | None = None) -> None:
        self.status = status
        self.error = error
        self.posts: list[tuple[str, dict, float]] = []

    def post_json(self, url, payload, timeout):
        self.posts.append((url, payload, timeout))
        if self.error:
            raise self.error
        return self.status


def test_log_sink_always_logs() -> None:
    with capture_logs() as logs:
        LogSink().send(Alert("7290027600007", "quarantine", "bad file", {"file_id": 3}))
    assert logs[0]["event"] == "alert"
    assert logs[0]["alert_kind"] == "quarantine" and logs[0]["chain_id"] == "7290027600007"
    assert logs[0]["detail_file_id"] == 3 and logs[0]["log_level"] == "error"


def test_webhook_receives_a_slack_compatible_payload() -> None:
    http = FakeHttp()
    alerter = build_alerter("https://hooks.example.invalid/x", client=http)
    alerter("7290058140886", "portal_failure", "portal down", attempts=5)
    url, payload, _ = http.posts[0]
    assert url == "https://hooks.example.invalid/x"
    assert payload["chain_id"] == "7290058140886" and payload["kind"] == "portal_failure"
    assert payload["message"] == "portal down" and payload["details"] == {"attempts": 5}
    assert "portal_failure" in payload["text"] and "7290058140886" in payload["text"]


def test_no_webhook_without_url() -> None:
    alerter = build_alerter(None)
    assert [type(s) for s in alerter.sinks] == [LogSink]


@pytest.mark.parametrize("http", [FakeHttp(status=500), FakeHttp(error=OSError("refused"))])
def test_webhook_failure_never_breaks_ingestion(http) -> None:
    with capture_logs() as logs:
        WebhookSink("https://hooks.example.invalid/x", http).send(Alert("c", "quarantine", "m"))
    assert any("webhook" in e["event"] for e in logs)


# --- pipeline alerts (database) ----------------------------------------------------------------


@pytest.fixture
def h(db, tmp_path):
    return make_harness(db, tmp_path)


@pytest.mark.db
def test_parse_failure_alerts_once_per_failure(h) -> None:
    remote = h.fetcher.add("price_full", b"!parse-error", at=NOW - timedelta(hours=2))
    h.scheduler().run_full(["fake"])
    assert statuses(h.conn)[remote.name] == "failed"
    assert h.kinds_of_alerts() == ["parse_failure"]
    assert "broken XML" in h.sink.alerts[0].message and "[fake]" in h.sink.alerts[0].message
    # Seen again on the next tick: retried, still failing, not alerted again.
    report = h.scheduler().run_full(["fake"])
    assert report.chains[0].failed == 1 and not report.ok
    assert h.kinds_of_alerts() == ["parse_failure"]
    reason = h.conn.execute("SELECT reason FROM file_tracking WHERE chain_id = 'fake'").fetchone()[
        0
    ]
    assert reason.startswith("parse failed:")


@pytest.mark.db
def test_unknown_schema_alerts_and_is_not_loaded(h) -> None:
    remote = h.fetcher.add("price_full", b"!unknown-schema", at=NOW - timedelta(hours=2))
    h.scheduler().run_full(["fake"])
    assert statuses(h.conn)[remote.name] == "failed"
    assert h.kinds_of_alerts() == ["unknown_schema"]


@pytest.mark.db
def test_load_failure_alerts(h) -> None:
    h.fetcher.add(
        "price_full", encode(items=[], prices=[price("GHOST", "1", "5")]),
        at=NOW - timedelta(hours=2),
    )  # fmt: skip
    h.scheduler().run_full(["fake"])
    assert h.kinds_of_alerts() == ["load_failure"]
    assert "unknown items" in h.sink.alerts[0].message


@pytest.mark.db
def test_quarantine_alert_names_chain_store_file_and_gate(h) -> None:
    remote = h.fetcher.add(
        "price_full", encode(items=[item("A")], prices=[price("A", "1", "0")]),
        at=NOW - timedelta(hours=2),
    )  # fmt: skip
    h.scheduler().run_full(["fake"])
    (alert,) = h.sink.alerts
    assert alert.kind == "quarantine" and alert.chain_id == "fake"
    assert remote.name in alert.message and "store 1" in alert.message
    assert alert.details["gates"] == ["zero_price"]
