"""The ``file_tracking`` state machine (issue #37).

One row per distinct file content, keyed by sha256. Statuses and the transitions allowed between
them::

    seen        -> downloaded | failed
    downloaded  -> held | loading | failed
    held        -> held | loading | failed          (a delta waiting for its full file)
    loading     -> loaded | quarantined | failed
    failed      -> downloaded | held | loading | failed   (retry)
    loaded, quarantined: terminal

``loaded`` and ``quarantined`` are terminal: a file with that hash is never processed again.
``failed`` is retried the next time the file is seen (or by ``run`` resuming open files).
Every change goes through :func:`transition`, which updates the row only if its current status
allows the move, so two code paths cannot silently overwrite each other's outcome.

None of these functions commit. In production the CLI uses an autocommit connection, so each
statement is its own transaction; inside ``conn.transaction()`` (the loader) they join it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

from smartcart_ingest.models import FileKind, RawFile

ISRAEL = ZoneInfo("Asia/Jerusalem")

STATUSES = ("seen", "downloaded", "held", "loading", "loaded", "quarantined", "failed")
TERMINAL = frozenset({"loaded", "quarantined"})
DELTA_KINDS: frozenset[str] = frozenset({"price", "promo"})
FULL_KINDS: frozenset[str] = frozenset({"price_full", "promo_full"})

# to-status -> the statuses it may be reached from.
_ALLOWED_FROM: dict[str, frozenset[str]] = {
    "downloaded": frozenset({"seen", "failed"}),
    "held": frozenset({"downloaded", "held", "failed"}),
    "loading": frozenset({"downloaded", "held", "failed"}),
    "loaded": frozenset({"loading"}),
    "quarantined": frozenset({"loading"}),
    "failed": frozenset({"seen", "downloaded", "held", "loading", "failed"}),
}

_COLUMNS = (
    "id, sha256, chain_id, store_code, kind, path, published_at, schema_version, status, reason,"
    " created_at, updated_at"
)
_ITEMS_REASON = re.compile(r"\bitems=(\d+)\b")


class InvalidTransition(RuntimeError):
    def __init__(self, file_id: int, current: str | None, wanted: str) -> None:
        self.file_id = file_id
        self.current = current
        self.wanted = wanted
        super().__init__(f"file {file_id}: cannot go from {current!r} to {wanted!r}")


@dataclass(frozen=True)
class TrackedFile:
    id: int
    sha256: str
    chain_id: str
    store_code: str | None
    kind: FileKind
    path: str | None
    published_at: datetime | None
    schema_version: str
    status: str
    reason: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_delta(self) -> bool:
        return self.kind in DELTA_KINDS

    def to_raw(self) -> RawFile:
        if self.published_at is None or self.path is None:
            raise ValueError(f"file {self.id} has no published_at or path")
        return RawFile(
            chain_id=self.chain_id,
            store_code=self.store_code,
            kind=self.kind,
            published_at=self.published_at,
            sha256=self.sha256,
            path=self.path,
            schema_version=self.schema_version,  # type: ignore[arg-type]
        )


def _row(row: dict[str, Any] | None) -> TrackedFile | None:
    if row is None:
        return None
    row = dict(row)
    row["sha256"] = row["sha256"].strip()
    return TrackedFile(**row)


def _one(conn: psycopg.Connection, query: str, params: tuple | dict) -> TrackedFile | None:
    with conn.cursor(row_factory=dict_row) as cur:
        return _row(cur.execute(query, params).fetchone())


def _many(conn: psycopg.Connection, query: str, params: tuple | dict = ()) -> list[TrackedFile]:
    with conn.cursor(row_factory=dict_row) as cur:
        return [_row(r) for r in cur.execute(query, params).fetchall()]  # type: ignore[misc]


def israel_day(ts: datetime) -> date:
    """The calendar day of ``ts`` in Israel, which is how chains date their files."""
    return ts.astimezone(ISRAEL).date()


def full_kind_for(kind: str) -> FileKind:
    """The full file a delta depends on: Price -> PriceFull, Promo -> PromoFull."""
    if kind == "price":
        return "price_full"
    if kind == "promo":
        return "promo_full"
    raise ValueError(f"{kind!r} is not a delta kind")


# --- reads -------------------------------------------------------------------------------------


def get(conn: psycopg.Connection, file_id: int) -> TrackedFile | None:
    return _one(conn, f"SELECT {_COLUMNS} FROM file_tracking WHERE id = %s", (file_id,))


def get_by_sha(conn: psycopg.Connection, sha256: str) -> TrackedFile | None:
    return _one(conn, f"SELECT {_COLUMNS} FROM file_tracking WHERE sha256 = %s", (sha256,))


def open_files(
    conn: psycopg.Connection, chain_id: str, statuses: tuple[str, ...] = ("downloaded", "held")
) -> list[TrackedFile]:
    """Files of a chain that still need work, oldest publication first."""
    return _many(
        conn,
        f"SELECT {_COLUMNS} FROM file_tracking WHERE chain_id = %s AND status = ANY(%s)"
        " ORDER BY published_at NULLS FIRST, id",
        (chain_id, list(statuses)),
    )


def is_full_loaded(
    conn: psycopg.Connection,
    chain_id: str,
    store_code: str | None,
    day: date,
    kind: FileKind = "price_full",
) -> bool:
    """True when a ``kind`` full file for this store, published on ``day`` (Israel), is loaded.

    A delta (Price or Promo) may be applied only when this is true for its own full kind
    (PriceFull or PromoFull); otherwise it is held and retried later.
    """
    row = conn.execute(
        "SELECT 1 FROM file_tracking"
        " WHERE chain_id = %s AND store_code IS NOT DISTINCT FROM %s AND kind = %s"
        "   AND status = 'loaded'"
        "   AND (published_at AT TIME ZONE 'Asia/Jerusalem')::date = %s"
        " LIMIT 1",
        (chain_id, store_code, kind, day),
    ).fetchone()
    return row is not None


def _has_item_count_column(conn: psycopg.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM pg_attribute WHERE attrelid = 'file_tracking'::regclass"
        " AND attname = 'item_count' AND NOT attisdropped"
    ).fetchone()
    return row is not None


def previous_full_count(
    conn: psycopg.Connection,
    chain_id: str,
    store_code: str | None,
    kind: str,
    before: datetime,
    exclude_id: int | None = None,
) -> int | None:
    """Record count of the latest loaded file of ``kind`` for this store published before
    ``before``, or None when there is none.

    The count is stored by :func:`mark_loaded`. Schema v1 has no column for it, so it is kept in
    ``reason`` as ``items=<n>`` on loaded rows; if a later migration adds
    ``file_tracking.item_count`` that column is used instead (see docs/ingestion.md).
    """
    use_column = _has_item_count_column(conn)
    col = "item_count" if use_column else "reason"
    row = conn.execute(
        f"SELECT {col} FROM file_tracking"
        " WHERE chain_id = %s AND store_code IS NOT DISTINCT FROM %s AND kind = %s"
        "   AND status = 'loaded' AND published_at < %s AND id IS DISTINCT FROM %s"
        " ORDER BY published_at DESC, id DESC LIMIT 1",
        (chain_id, store_code, kind, before, exclude_id),
    ).fetchone()
    if row is None or row[0] is None:
        return None
    if use_column:
        return int(row[0])
    m = _ITEMS_REASON.search(row[0])
    return int(m.group(1)) if m else None


def status_counts(conn: psycopg.Connection) -> list[tuple[str, str, int]]:
    """(chain_id, status, files) for every chain and status present."""
    return [
        (r[0], r[1], int(r[2]))
        for r in conn.execute(
            "SELECT chain_id, status, count(*) FROM file_tracking"
            " GROUP BY chain_id, status ORDER BY chain_id, status"
        ).fetchall()
    ]


QUARANTINE_COUNTS_SQL = """
SELECT ft.chain_id,
       count(*)                                                        AS quarantined_files,
       count(*) FILTER (WHERE ft.updated_at >= now() - interval '1 day') AS last_24h,
       max(ft.updated_at)                                              AS last_quarantined_at
FROM file_tracking AS ft
WHERE ft.status = 'quarantined'
GROUP BY ft.chain_id
ORDER BY ft.chain_id
"""


def quarantine_counts(conn: psycopg.Connection) -> list[tuple[str, int, int]]:
    """(chain_id, quarantined files, of which in the last 24 hours). Query in docs/ingestion.md."""
    return [(r[0], int(r[1]), int(r[2])) for r in conn.execute(QUARANTINE_COUNTS_SQL).fetchall()]


# --- writes ------------------------------------------------------------------------------------


def register(conn: psycopg.Connection, raw: RawFile) -> tuple[TrackedFile, bool]:
    """Record a file as ``seen`` (or return the existing row for that hash).

    Returns ``(row, created)``; ``created`` is False when the hash was already tracked.
    """
    created = _one(
        conn,
        "INSERT INTO file_tracking"
        " (sha256, chain_id, store_code, kind, path, published_at, schema_version, status)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, 'seen')"
        f" ON CONFLICT (sha256) DO NOTHING RETURNING {_COLUMNS}",
        (
            raw.sha256,
            raw.chain_id,
            raw.store_code,
            raw.kind,
            raw.path,
            raw.published_at,
            raw.schema_version,
        ),
    )
    if created is not None:
        return created, True
    existing = get_by_sha(conn, raw.sha256)
    if existing is None:  # pragma: no cover - only if deleted concurrently
        raise RuntimeError(f"file {raw.sha256} vanished from file_tracking")
    return existing, False


_SETTABLE = frozenset({"path", "schema_version"})


def transition(
    conn: psycopg.Connection,
    file_id: int,
    to: str,
    reason: str | None = None,
    **fields: Any,
) -> TrackedFile:
    """Move a file to status ``to`` if its current status allows it; raise otherwise.

    ``reason`` replaces the stored reason (None clears it). ``fields`` may set ``path`` and
    ``schema_version``.
    """
    if to not in _ALLOWED_FROM:
        raise ValueError(f"unknown target status {to!r}")
    bad = set(fields) - _SETTABLE
    if bad:
        raise ValueError(f"cannot set {sorted(bad)} through transition()")
    sets = ["status = %(to)s", "reason = %(reason)s"]
    params: dict[str, Any] = {
        "to": to,
        "reason": reason,
        "id": file_id,
        "allowed": list(_ALLOWED_FROM[to]),
    }
    for name, value in fields.items():
        if value is not None:
            sets.append(f"{name} = %({name})s")
            params[name] = value
    updated = _one(
        conn,
        f"UPDATE file_tracking SET {', '.join(sets)}"
        " WHERE id = %(id)s AND status = ANY(%(allowed)s)"
        f" RETURNING {_COLUMNS}",
        params,
    )
    if updated is None:
        current = get(conn, file_id)
        raise InvalidTransition(file_id, current.status if current else None, to)
    return updated


RETRY_PREFIX = "retry after: "


def mark_downloaded(
    conn: psycopg.Connection, file_id: int, path: str, reason: str | None = None
) -> TrackedFile:
    return transition(conn, file_id, "downloaded", reason, path=path)


def mark_held(conn: psycopg.Connection, file_id: int, reason: str) -> TrackedFile:
    return transition(conn, file_id, "held", reason)


def mark_loading(conn: psycopg.Connection, file_id: int) -> TrackedFile:
    return transition(conn, file_id, "loading")


def mark_loaded(
    conn: psycopg.Connection,
    file_id: int,
    item_count: int,
    schema_version: str | None = None,
) -> TrackedFile:
    row = transition(conn, file_id, "loaded", f"items={item_count}", schema_version=schema_version)
    if _has_item_count_column(conn):
        conn.execute(
            "UPDATE file_tracking SET item_count = %s WHERE id = %s", (item_count, file_id)
        )
    return row


def mark_quarantined(
    conn: psycopg.Connection, file_id: int, reason: str, schema_version: str | None = None
) -> TrackedFile:
    return transition(conn, file_id, "quarantined", reason, schema_version=schema_version)


def mark_failed(conn: psycopg.Connection, file_id: int, reason: str) -> TrackedFile:
    return transition(conn, file_id, "failed", reason[:2000])


def record_quarantine(
    conn: psycopg.Connection,
    file_id: int,
    failures: list[tuple[str, str]],
    schema_version: str | None = None,
) -> TrackedFile:
    """Write one ``quarantine_events`` row per failed gate and set the file quarantined, in
    one transaction. ``failures`` is a list of ``(gate, detail)``."""
    if not failures:
        raise ValueError("record_quarantine needs at least one failure")
    reason = "; ".join(f"{gate}: {detail}" for gate, detail in failures)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO quarantine_events (file_id, gate, detail) VALUES (%s, %s, %s)",
                [(file_id, gate, detail) for gate, detail in failures],
            )
        return mark_quarantined(conn, file_id, reason[:2000], schema_version)


def recover_interrupted(conn: psycopg.Connection, chain_id: str | None = None) -> int:
    """Mark files left in ``loading`` by a process that died as failed, so they are retried.

    Safe because runs are serialized (the systemd units share one flock); call it at the start
    of a run. Returns the number of files recovered.
    """
    rows = conn.execute(
        "UPDATE file_tracking SET status = 'failed', reason = 'interrupted: process stopped mid-load'"
        " WHERE status = 'loading' AND (%s::text IS NULL OR chain_id = %s) RETURNING id",
        (chain_id, chain_id),
    ).fetchall()
    return len(rows)


def strip_retry(reason: str | None) -> str:
    """The original failure reason of a file being retried."""
    reason = reason or ""
    while reason.startswith(RETRY_PREFIX):
        reason = reason[len(RETRY_PREFIX) :]
    return reason
