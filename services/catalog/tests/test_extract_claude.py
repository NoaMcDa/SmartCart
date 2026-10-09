"""Claude batch extractor (issue #25, D14) against a fake client. No network in tests.

Fixtures in tests/fixtures/claude/: ``request_item.json`` is the request the extractor builds for
one item (prompt and schema as placeholders); ``batch_results.json`` holds batch results in the
API's shape, keyed by the item's raw name. They are hand-written, not recorded from a live call
(no API key yet); see the note inside each file.
"""

from __future__ import annotations

import copy
import json
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psycopg
import pytest
from anthropic.types.messages import MessageBatchIndividualResponse
from typer.testing import CliRunner

from smartcart_catalog import cli
from smartcart_catalog.extract.claude import ClaudeExtractor, estimate_usd
from smartcart_catalog.extract.queue import cost_report, run_extraction
from smartcart_catalog.models import Attributes, ExtractionError, NormalizedItem
from smartcart_catalog.normalize import normalize
from smartcart_catalog.seed import load_catalog

FIXTURES = Path(__file__).parent / "fixtures" / "claude"
RESULTS = json.loads((FIXTURES / "batch_results.json").read_text(encoding="utf-8"))["results"]
REQUEST = json.loads((FIXTURES / "request_item.json").read_text(encoding="utf-8"))["request"]


class FakeBatches:
    """``client.messages.batches``: create / retrieve / results, answering from fixtures."""

    def __init__(self, entries: list[dict[str, Any]], polls_before_end: int = 1) -> None:
        self.by_name = {e["raw_name"]: e for e in entries}
        self.created: list[list[dict[str, Any]]] = []
        self.polls_before_end = polls_before_end
        self.retrieved = 0

    def create(self, requests: list[dict[str, Any]]) -> SimpleNamespace:
        self.created.append(copy.deepcopy(requests))
        return SimpleNamespace(
            id=f"msgbatch_fake_{len(self.created)}", processing_status="in_progress"
        )

    def retrieve(self, batch_id: str) -> SimpleNamespace:
        self.retrieved += 1
        done = self.retrieved > self.polls_before_end
        return SimpleNamespace(id=batch_id, processing_status="ended" if done else "in_progress")

    def results(self, batch_id: str):
        requests = self.created[int(batch_id.rsplit("_", 1)[1]) - 1]
        out = []
        for req in reversed(requests):  # results come back in any order
            msg = json.loads(req["params"]["messages"][0]["content"])
            entry = self.by_name.get(msg["raw_name"] or msg["name"])
            if entry is None or entry.get("omit"):
                continue
            out.append(
                MessageBatchIndividualResponse.model_validate(
                    {"custom_id": req["custom_id"], "result": entry["result"]}
                )
            )
        return iter(out)


def fake_client(entries: list[dict[str, Any]], **kw: Any) -> SimpleNamespace:
    return SimpleNamespace(messages=SimpleNamespace(batches=FakeBatches(entries, **kw)))


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def _extractor(catalog, entries=RESULTS, **kw) -> tuple[ClaudeExtractor, FakeBatches]:
    client = fake_client(entries)
    sleeps: list[float] = []
    x = ClaudeExtractor(client=client, catalog=catalog, poll_seconds=5, sleep=sleeps.append, **kw)
    return x, client.messages.batches


def _items() -> list[NormalizedItem]:
    return [
        normalize({"raw_name": entry["raw_name"], "item_code": "7290000",
                   "chain_id": "7290027600007"}, item_id=n)
        for n, entry in enumerate(RESULTS, start=101)
    ]  # fmt: skip


# --- request ---------------------------------------------------------------------------------------


def test_request_matches_recorded_shape(catalog) -> None:
    x, _ = _extractor(catalog)
    item = normalize(
        {
            "raw_name": "חלב תנובה 3% בקרטון 1 ליטר",
            "quantity": 1,
            "unit": "ליטר",
            "item_code": "7290004131074",
            "chain_id": "7290027600007",
            "chain_name": "שופרסל",
            "manufacturer": "תנובה",
            "barcode": "7290004131074",
        },
        item_id=101,
    )
    req = x.build_request(item)
    schema = req["params"]["output_config"]["format"]["schema"]
    assert schema["additionalProperties"] is False
    assert "Product types" in req["params"]["system"][0]["text"]
    req["params"]["system"][0]["text"] = "<system_prompt(catalog)>"
    req["params"]["output_config"]["format"]["schema"] = "<schema_for(catalog)>"
    assert req == REQUEST


def test_request_uses_batch_defaults(catalog) -> None:
    params = REQUEST["params"]
    assert params["model"] == "claude-sonnet-5-5"
    assert params["max_tokens"] == 1024
    assert params["thinking"] == {"type": "adaptive"}  # adaptive, never a budget
    assert "budget_tokens" not in json.dumps(params)
    assert params["output_config"]["format"]["type"] == "json_schema"
    assert REQUEST["custom_id"] == "item-101"


# --- results ---------------------------------------------------------------------------------------


def test_extract_reads_results_by_custom_id_and_classifies_failures(catalog) -> None:
    x, batches = _extractor(catalog)
    items = _items()
    out = x.extract(items)
    assert len(out) == len(items)
    assert batches.retrieved == 2  # polled until "ended"
    for entry, result in zip(RESULTS, out, strict=True):
        if entry["expect"] == "ok":
            assert isinstance(result, Attributes), entry["raw_name"]
            assert result.verified_keys == ()
        else:
            assert isinstance(result, ExtractionError), entry["raw_name"]
            assert result.reason.startswith(entry["reason"]), (entry["raw_name"], result.reason)
            assert result.retryable == (entry["expect"] == "retry")
    milk = out[0]
    assert (milk.product_type, milk.fat_pct, milk.state) == ("milk", Decimal(3), "fresh")
    assert (milk.pack_size, milk.unit) == (Decimal(1000), "ml")


def test_usage_and_estimated_cost(catalog) -> None:
    x, _ = _extractor(catalog)
    items = _items()
    x.extract(items)
    usage = x.last_usage
    succeeded = [
        e["result"]["message"]["usage"]
        for e in RESULTS
        if e.get("result", {}).get("type") == "succeeded"
    ]
    assert usage.input_tokens == sum(u["input_tokens"] for u in succeeded)
    assert usage.output_tokens == sum(u["output_tokens"] for u in succeeded)
    assert usage.cache_read_input_tokens == sum(u["cache_read_input_tokens"] for u in succeeded)
    assert usage.succeeded == 2 and usage.requests == len(RESULTS)
    expected = (
        Decimal(usage.input_tokens) * 1
        + Decimal(usage.output_tokens) * 5
        + Decimal(usage.cache_read_input_tokens) * Decimal("0.1")
        + Decimal(usage.cache_creation_input_tokens) * Decimal("1.25")
    ) / 1_000_000
    assert usage.estimated_usd == expected.quantize(Decimal("0.0001"))


def test_estimate_usd_rates() -> None:
    # $1 per MTok input and $5 per MTok output with the batch discount (estimate)
    assert estimate_usd("claude-sonnet-5-5", 1_000_000, 1_000_000) == Decimal("6.0000")
    assert estimate_usd("some-other-model", 10, 10) is None


# --- the queue with the model: malformed output goes to retry, never to trusted ----------------


def _seed_items(db: psycopg.Connection, names: list[str]) -> dict[str, int]:
    db.execute("INSERT INTO chains (id, name, portal) VALUES ('7290027600007', 'שופרסל', 'other')")
    ids = {}
    for n, name in enumerate(names):
        ids[name] = db.execute(
            "INSERT INTO items (chain_id, item_code, raw_name) VALUES ('7290027600007', %s, %s)"
            " RETURNING id",
            (f"72900000{n:05d}", name),
        ).fetchone()[0]
    return ids


def _rows(db: psycopg.Connection) -> dict[int, tuple]:
    return {
        r[0]: r[1:]
        for r in db.execute(
            "SELECT item_id, status, attrs, verified_keys, confidence, extractor, model"
            " FROM item_attributes"
        ).fetchall()
    }


@pytest.mark.db
@pytest.mark.pgvector
def test_malformed_output_goes_to_retry_and_is_never_trusted(db, catalog) -> None:
    ids = _seed_items(db, [e["raw_name"] for e in RESULTS])
    x, batches = _extractor(catalog)
    run = run_extraction(db, x, batch_size=50)
    assert (run.items, run.ok, run.retry, run.failed) == (12, 2, 9, 1)
    rows = _rows(db)

    malformed = rows[ids['פילה סלמון קפוא 1 ק"ג']]
    status, attrs, verified, confidence, extractor, model = malformed
    assert status == "retry"
    assert set(attrs) == {"_retry"}  # no attribute value is stored
    assert attrs["_retry"]["attempts"] == 1 and "not JSON" in attrs["_retry"]["reason"]
    assert confidence is None and verified == []
    assert (extractor, model) == ("claude", "claude-sonnet-5-5")
    assert rows[ids["חלב עמיד 1% 1 ליטר"]][0] == "failed"

    soy = rows[ids['משקה סויה אלפרו בד"ץ 1 ליטר']]
    assert soy[0] == "ok"
    assert soy[1]["kosher"] == 'בד"ץ' and soy[1]["diet_flags"] == ["vegan"]
    assert soy[2] == []  # kosher and diet flags stay unverified
    assert soy[3] == Decimal("0.88")

    # second run: only the retry rows are sent again; this time the model answers well
    fixed = [dict(e, result=RESULTS[0]["result"]) | {"omit": False} for e in RESULTS]
    x2, batches2 = _extractor(catalog, fixed)
    run2 = run_extraction(db, x2, batch_size=50)
    sent = {
        json.loads(r["params"]["messages"][0]["content"])["raw_name"] for r in batches2.created[0]
    }
    assert len(sent) == 9
    assert RESULTS[0]["raw_name"] not in sent and "חלב עמיד 1% 1 ליטר" not in sent
    assert (run2.ok, run2.retry, run2.failed) == (9, 0, 0)

    # third run: nothing left to do, no batch is created
    x3, batches3 = _extractor(catalog)
    assert run_extraction(db, x3).items == 0
    assert batches3.created == []


@pytest.mark.db
@pytest.mark.pgvector
def test_retry_becomes_failed_after_max_attempts(db, catalog) -> None:
    name = 'פילה סלמון קפוא 1 ק"ג'
    ids = _seed_items(db, [name])
    entries = [e for e in RESULTS if e["raw_name"] == name]
    for attempt in (1, 2, 3):
        x, _ = _extractor(catalog, entries)
        run_extraction(db, x, max_attempts=3)
        status, attrs = db.execute(
            "SELECT status, attrs FROM item_attributes WHERE item_id = %s", (ids[name],)
        ).fetchone()
        assert attrs["_retry"]["attempts"] == attempt
        assert status == ("failed" if attempt == 3 else "retry")


@pytest.mark.db
@pytest.mark.pgvector
def test_cost_report_from_recorded_runs(db, catalog, monkeypatch) -> None:
    _seed_items(db, [e["raw_name"] for e in RESULTS])
    x, _ = _extractor(catalog)
    run_extraction(db, x, batch_size=5)  # three batches
    lines = cost_report(db)
    assert len(lines) == 3
    assert {ln.model for ln in lines} == {"claude-sonnet-5-5"}
    assert sum(ln.requests for ln in lines) == len(RESULTS)

    @contextmanager
    def same_connection(settings):
        yield db

    monkeypatch.setattr(cli, "open_connection", same_connection)
    result = CliRunner().invoke(cli.app, ["cost-report"])
    assert result.exit_code == 0, result.output
    assert "estimated at batch rates" in result.output and "estimate" in result.output
    assert lines[0].batch_id in result.output
