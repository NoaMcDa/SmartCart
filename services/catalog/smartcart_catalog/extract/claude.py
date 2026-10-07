"""Attribute extraction with Claude through the Message Batches API (issue #25, decision D14).

One request per item, all items of a chunk in one batch: ``client.messages.batches.create``,
poll ``retrieve`` until ``processing_status == "ended"``, then read ``results`` keyed by
``custom_id`` (results arrive in any order). Each request asks for a structured output
(``output_config.format`` with the JSON schema from ``schema.py``), runs adaptive thinking at the
model's defaults (no thinking budget) with low effort, and caps ``max_tokens`` at about 1024.

Nothing the model returns is trusted until it validates: a refusal, a cut-off answer
(``max_tokens``), an empty or malformed body, an errored, canceled or expired request, or a
missing result becomes an ``ExtractionError`` and the queue marks the item ``retry``. Usage is
summed per batch for the cost report.

Batches are billed at 50% of the standard rate. ``BATCH_PRICES_PER_MTOK`` holds the batch rates
used for the cost estimate; they are an estimate of the bill, not the bill.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from smartcart_catalog.extract.base import ContextMap, ItemContext, Result
from smartcart_catalog.extract.schema import (
    SchemaError,
    schema_for,
    system_prompt,
    user_message,
    validate_output,
)
from smartcart_catalog.models import Attributes, ExtractionError, NormalizedItem
from smartcart_catalog.seed import Catalog, load_catalog

DEFAULT_MODEL = "claude-sonnet-5-5"

# USD per million tokens with the 50% batch discount (Sonnet 5.5 list price is $2 in / $10 out).
# Cache reads bill at 0.1x input and 5-minute cache writes at 1.25x input. Estimate only.
BATCH_PRICES_PER_MTOK: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet-5-5": (Decimal("1.00"), Decimal("5.00")),
}
CACHE_READ_FACTOR = Decimal("0.1")
CACHE_WRITE_FACTOR = Decimal("1.25")


@dataclass
class BatchUsage:
    batch_id: str
    model: str
    requests: int = 0
    succeeded: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def add(self, usage: Any) -> None:
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_creation_input_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.cache_read_input_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0

    @property
    def estimated_usd(self) -> Decimal | None:
        return estimate_usd(self.model, self.input_tokens, self.output_tokens,
                            self.cache_creation_input_tokens, self.cache_read_input_tokens)

    def as_metrics(self) -> dict[str, Any]:
        usd = self.estimated_usd
        return {
            "batch_id": self.batch_id,
            "model": self.model,
            "requests": self.requests,
            "succeeded": self.succeeded,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "estimated_usd": None if usd is None else str(usd),
        }


def estimate_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> Decimal | None:
    """Estimated batch cost in USD, or None for a model without a price entry."""
    prices = BATCH_PRICES_PER_MTOK.get(model)
    if prices is None:
        return None
    p_in, p_out = prices
    million = Decimal(1_000_000)
    usd = (
        Decimal(input_tokens) * p_in
        + Decimal(cache_creation_input_tokens) * p_in * CACHE_WRITE_FACTOR
        + Decimal(cache_read_input_tokens) * p_in * CACHE_READ_FACTOR
        + Decimal(output_tokens) * p_out
    ) / million
    return usd.quantize(Decimal("0.0001"))


def custom_id(item_id: int) -> str:
    return f"item-{item_id}"


def _size_text(item: NormalizedItem) -> str | None:
    if item.is_weighed:
        return "sold by weight (price per kg)"
    if item.total_quantity is None or item.unit is None:
        return None
    if item.pack_count > 1:
        return f"{item.pack_count} x {item.quantity:f} {item.unit} = {item.total_quantity:f} {item.unit}"
    return f"{item.total_quantity:f} {item.unit}"


@dataclass
class ClaudeExtractor:
    """``Extractor`` backed by Claude batches. Pass ``client`` to inject a fake in tests."""

    client: Any = None
    model: str = DEFAULT_MODEL
    max_tokens: int = 1024
    effort: str = "low"
    poll_seconds: float = 60
    max_wait_seconds: float = 24 * 3600
    api_key: str | None = None
    catalog: Catalog | None = None
    sleep: Callable[[float], None] = time.sleep
    name: str = "claude"
    uses_context: bool = True
    usage_log: list[BatchUsage] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.catalog = self.catalog or load_catalog()
        self._system = system_prompt(self.catalog)
        self._schema = schema_for(self.catalog)
        if self.client is None:
            import anthropic  # only when a real call is about to happen

            self.client = anthropic.Anthropic(api_key=self.api_key)

    # --- request ----------------------------------------------------------------------------------

    def build_request(self, item: NormalizedItem, ctx: ItemContext | None) -> dict[str, Any]:
        ctx = ctx or ItemContext()
        return {
            "custom_id": custom_id(item.item_id),
            "params": {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "thinking": {"type": "adaptive"},
                "output_config": {
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": self._schema},
                },
                # identical for every item, so it is cached after the first request
                "system": [
                    {"type": "text", "text": self._system, "cache_control": {"type": "ephemeral"}}
                ],
                "messages": [
                    {
                        "role": "user",
                        "content": user_message(
                            item_id=item.item_id,
                            name=item.clean_name,
                            raw_name=ctx.raw_name,
                            manufacturer=ctx.manufacturer,
                            chain=ctx.chain_name or ctx.chain_id,
                            size=_size_text(item),
                        ),
                    }
                ],
            },
        }

    # --- batch lifecycle ---------------------------------------------------------------------------

    def submit(self, items: list[NormalizedItem], context: ContextMap | None = None) -> str:
        context = context or {}
        requests = [self.build_request(i, context.get(i.item_id)) for i in items]
        batch = self.client.messages.batches.create(requests=requests)
        return batch.id

    def wait(self, batch_id: str) -> None:
        waited = 0.0
        while True:
            batch = self.client.messages.batches.retrieve(batch_id)
            if batch.processing_status == "ended":
                return
            if waited >= self.max_wait_seconds:
                raise TimeoutError(f"batch {batch_id} not ended after {waited:.0f}s")
            self.sleep(self.poll_seconds)
            waited += self.poll_seconds

    def collect(self, batch_id: str, items: list[NormalizedItem]) -> list[Result]:
        usage = BatchUsage(batch_id=batch_id, model=self.model, requests=len(items))
        by_id: dict[str, Result] = {}
        wanted = {custom_id(i.item_id): i for i in items}
        for entry in self.client.messages.batches.results(batch_id):
            item = wanted.get(entry.custom_id)
            if item is None:
                continue
            outcome = self._read(item, entry.result, usage)
            if isinstance(outcome, Attributes):
                usage.succeeded += 1
            by_id[entry.custom_id] = outcome
        self.usage_log.append(usage)
        return [
            by_id.get(cid)
            or ExtractionError(item_id=i.item_id, reason="no result in the batch output")
            for cid, i in wanted.items()
        ]

    def extract(
        self, items: list[NormalizedItem], *, context: ContextMap | None = None
    ) -> list[Result]:
        if not items:
            return []
        batch_id = self.submit(items, context)
        self.wait(batch_id)
        return self.collect(batch_id, items)

    @property
    def last_usage(self) -> BatchUsage | None:
        return self.usage_log[-1] if self.usage_log else None

    # --- one result -------------------------------------------------------------------------------

    def _read(self, item: NormalizedItem, result: Any, usage: BatchUsage) -> Result:
        kind = getattr(result, "type", None)
        if kind != "succeeded":
            if kind == "errored":
                err = getattr(result, "error", None)
                etype = getattr(getattr(err, "error", None), "type", None) or getattr(
                    err, "type", "error"
                )
                return ExtractionError(
                    item_id=item.item_id,
                    reason=f"request errored: {etype}",
                    retryable=etype != "invalid_request_error",
                )
            return ExtractionError(item_id=item.item_id, reason=f"request {kind}")
        message = result.message
        usage.add(message.usage)
        if message.stop_reason == "refusal":
            return ExtractionError(item_id=item.item_id, reason="model refused")
        if message.stop_reason == "max_tokens":
            return ExtractionError(item_id=item.item_id, reason="cut off at max_tokens")
        text = next((b.text for b in message.content if getattr(b, "type", "") == "text"), "")
        try:
            attrs = validate_output(text, self._schema)
        except SchemaError as exc:
            return ExtractionError(item_id=item.item_id, reason=f"invalid output: {exc}")
        # the parsed size is deterministic and tested; it wins over the model's reading
        if item.total_quantity is not None and not item.is_weighed:
            attrs = attrs.model_copy(update={"pack_size": item.total_quantity, "unit": item.unit})
        return attrs
