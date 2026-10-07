"""The extraction queue: which items still need attributes, and writing the results (issue #25).

Pending = items with no ``item_attributes`` row, plus rows in ``status = 'retry'``. Items are
read in id order in chunks of ``batch_size``, normalized, handed to the extractor, and written
back:

* ``Attributes`` -> ``status 'ok'``: ``attrs`` holds the values, ``verified_keys`` is empty
  unless the source is a human (kosher and diet flags never count as verified otherwise),
  ``confidence``, ``extractor`` and ``model`` are recorded.
* ``ExtractionError`` -> ``status 'retry'`` with ``attrs = {"_retry": {"reason", "attempts"}}``
  and no confidence: no attribute value is written, so nothing untrusted can be read as a value.
  After ``max_attempts`` (or a non-retryable error) the status becomes ``'failed'``.

Rows with ``status 'ok'`` or ``'failed'`` are never selected again, so a re-run skips done items
and every item is processed once. Within a run each item is attempted at most once.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg.rows import dict_row

from smartcart_catalog.extract.base import (
    HUMAN,
    ItemContext,
    Result,
    attrs_json,
    trusted_verified_keys,
)
from smartcart_catalog.models import Attributes, Extractor, NormalizedItem
from smartcart_catalog.normalize import normalize

_PENDING = """
SELECT i.id, i.chain_id, c.name AS chain_name, i.item_code, i.barcode, i.raw_name,
       i.manufacturer, i.quantity, i.unit, i.is_weighed,
       COALESCE((a.attrs -> '_retry' ->> 'attempts')::int, 0) AS attempts
FROM items i
LEFT JOIN chains c ON c.id = i.chain_id
LEFT JOIN item_attributes a ON a.item_id = i.id
WHERE (a.item_id IS NULL OR a.status = 'retry')
  AND i.id > %(after)s
  AND (%(chain)s::text IS NULL OR i.chain_id = %(chain)s::text)
ORDER BY i.id
LIMIT %(limit)s
"""


@dataclass
class ExtractionRun:
    extractor: str
    model: str | None
    items: int = 0
    ok: int = 0
    retry: int = 0
    failed: int = 0
    batches: list[dict[str, Any]] = field(default_factory=list)

    def as_metrics(self) -> dict[str, Any]:
        return {
            "extractor": self.extractor,
            "model": self.model,
            "items": self.items,
            "ok": self.ok,
            "retry": self.retry,
            "failed": self.failed,
            "batches": self.batches,
        }


def pending_items(
    conn: psycopg.Connection, *, limit: int, after: int = 0, chain: str | None = None
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(_PENDING, {"after": after, "chain": chain, "limit": limit}).fetchall()


def count_pending(conn: psycopg.Connection, chain: str | None = None) -> int:
    row = conn.execute(
        "SELECT count(*) FROM items i LEFT JOIN item_attributes a ON a.item_id = i.id"
        " WHERE (a.item_id IS NULL OR a.status = 'retry')"
        "   AND (%(chain)s::text IS NULL OR i.chain_id = %(chain)s::text)",
        {"chain": chain},
    ).fetchone()
    return int(row[0]) if row else 0


def write_result(
    conn: psycopg.Connection,
    item_id: int,
    result: Result,
    *,
    extractor: str,
    model: str | None,
    attempts: int,
    max_attempts: int,
) -> str:
    """Upsert one ``item_attributes`` row and return its status."""
    if isinstance(result, Attributes):
        conn.execute(
            "INSERT INTO item_attributes AS a"
            "   (item_id, attrs, verified_keys, extractor, model, confidence, status, extracted_at)"
            " VALUES (%s, %s::jsonb, %s, %s, %s, %s, 'ok', now())"
            " ON CONFLICT (item_id) DO UPDATE SET attrs = EXCLUDED.attrs,"
            "   verified_keys = EXCLUDED.verified_keys, extractor = EXCLUDED.extractor,"
            "   model = EXCLUDED.model, confidence = EXCLUDED.confidence, status = 'ok',"
            "   extracted_at = now()"
            " WHERE a.status <> 'ok'",
            (
                item_id,
                attrs_json(result),
                trusted_verified_keys(result.verified_keys, extractor),
                extractor,
                model,
                result.confidence,
            ),
        )
        return "ok"
    attempts += 1
    status = "retry" if result.retryable and attempts < max_attempts else "failed"
    retry_doc = {"_retry": {"reason": result.reason[:500], "attempts": attempts}}
    conn.execute(
        "INSERT INTO item_attributes AS a"
        "   (item_id, attrs, verified_keys, extractor, model, confidence, status, extracted_at)"
        " VALUES (%s, %s::jsonb, '{}', %s, %s, NULL, %s, now())"
        " ON CONFLICT (item_id) DO UPDATE SET attrs = EXCLUDED.attrs, verified_keys = '{}',"
        "   extractor = EXCLUDED.extractor, model = EXCLUDED.model, confidence = NULL,"
        "   status = EXCLUDED.status, extracted_at = now()"
        " WHERE a.status <> 'ok'",
        (item_id, json.dumps(retry_doc, ensure_ascii=False), extractor, model, status),
    )
    return status


def run_extraction(
    conn: psycopg.Connection,
    extractor: Extractor,
    *,
    batch_size: int = 500,
    limit: int | None = None,
    chain: str | None = None,
    max_attempts: int = 3,
    commit: bool = False,
    record_run: bool = True,
) -> ExtractionRun:
    """Extract every pending item (or ``limit`` of them). ``commit=True`` commits after each
    chunk so a long run keeps its progress; tests leave it off and roll back."""
    name = getattr(extractor, "name", "unknown")
    model = getattr(extractor, "model", None)
    if name == HUMAN:
        raise ValueError("human attributes come from the review UI, not the queue")
    run = ExtractionRun(extractor=name, model=model)
    after = 0
    while limit is None or run.items < limit:
        size = batch_size if limit is None else min(batch_size, limit - run.items)
        rows = pending_items(conn, limit=size, after=after, chain=chain)
        if not rows:
            break
        after = rows[-1]["id"]
        items: list[NormalizedItem] = [normalize(r, item_id=r["id"]) for r in rows]
        context = {
            r["id"]: ItemContext(
                chain_id=r["chain_id"], chain_name=r["chain_name"],
                manufacturer=r["manufacturer"], raw_name=r["raw_name"], barcode=r["barcode"],
            )
            for r in rows
        }
        if getattr(extractor, "uses_context", False):
            results = extractor.extract(items, context=context)  # type: ignore[call-arg]
        else:
            results = extractor.extract(items)
        if len(results) != len(items):
            raise RuntimeError(f"{name} returned {len(results)} results for {len(items)} items")
        for row, result in zip(rows, results, strict=True):
            status = write_result(
                conn, row["id"], result, extractor=name, model=model,
                attempts=row["attempts"], max_attempts=max_attempts,
            )
            setattr(run, status, getattr(run, status) + 1)
        run.items += len(rows)
        last = getattr(extractor, "last_usage", None)
        if last is not None and (not run.batches or run.batches[-1]["batch_id"] != last.batch_id):
            run.batches.append(last.as_metrics())
        if commit:
            conn.commit()
    if record_run and run.items:
        conn.execute(
            "INSERT INTO match_runs (kind, finished_at, metrics) VALUES ('extract', now(), %s)",
            (json.dumps(run.as_metrics()),),
        )
        if commit:
            conn.commit()
    return run


# --- cost report ---------------------------------------------------------------------------------


@dataclass
class CostLine:
    run_id: int
    finished_at: Any
    batch_id: str
    model: str | None
    requests: int
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    estimated_usd: str | None


def cost_report(conn: psycopg.Connection, *, runs: int = 20) -> list[CostLine]:
    """One line per model batch of the last ``runs`` extraction runs, newest first. Token counts
    are what the API reported; the USD figure is an estimate at batch rates (claude.py)."""
    lines: list[CostLine] = []
    for run_id, finished_at, metrics in conn.execute(
        "SELECT id, finished_at, metrics FROM match_runs WHERE kind = 'extract'"
        " ORDER BY id DESC LIMIT %s",
        (runs,),
    ).fetchall():
        for b in metrics.get("batches", []):
            lines.append(
                CostLine(
                    run_id=run_id,
                    finished_at=finished_at,
                    batch_id=b.get("batch_id", "?"),
                    model=b.get("model"),
                    requests=int(b.get("requests", 0)),
                    input_tokens=int(b.get("input_tokens", 0)),
                    output_tokens=int(b.get("output_tokens", 0)),
                    cache_read_input_tokens=int(b.get("cache_read_input_tokens", 0)),
                    cache_creation_input_tokens=int(b.get("cache_creation_input_tokens", 0)),
                    estimated_usd=b.get("estimated_usd"),
                )
            )
    return lines
