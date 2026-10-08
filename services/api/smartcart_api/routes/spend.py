"""Budget and spend tracking, ``/me/spend`` (issue #70), under row-level security.

* ``POST /me/spend`` records a shopping trip: a list marked as purchased with the store, the
  date, the total, the item count and whether it was a single store or a split. The total is
  what the client sends: the app's estimate, or the user's actual checkout total, which
  replaces it (``PUT /me/spend/{id}``). It is idempotent per ``client_id``: the browser makes a
  random uuid per entry, and a repeated POST with the same id (a retry after a lost response, a
  double tap, an offline queue replayed twice) answers 200 with the stored entry and inserts
  nothing; the first POST answers 201. The stored row wins even if the repeated body differs, so
  a correction goes through ``PUT``. Without a ``client_id`` every POST inserts.
* ``GET /me/spend?month=YYYY-MM`` returns the month's entries, their total and the profile's
  ``monthly_budget`` (set with ``PUT /me/profile``).
* ``DELETE /me/spend/{id}`` removes one entry; ``GET /me/spend/export`` returns every entry and
  the budget (the user's copy of their data). ``DELETE /me`` removes them all.

Every query runs on ``user_conn`` (role ``smartcart_app``, ``auth.uid()`` = the token's user), so
the ``spend_entries_own`` policy decides which rows exist. Spend data never enters ``events``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from psycopg.rows import dict_row

from smartcart_api import schemas
from smartcart_api.auth import User, user_conn

router = APIRouter(prefix="/me/spend", tags=["me"])
UserConn = Annotated[tuple[User, psycopg.Connection], Depends(user_conn, scope="function")]

_COLS = "id, date, store_id, store_name, total, item_count, plan, client_id"
MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"


def _entry(row: dict) -> schemas.SpendEntry:
    return schemas.SpendEntry(**row)


def _budget(conn: psycopg.Connection, user: User) -> Decimal | None:
    row = conn.execute("SELECT monthly_budget FROM profiles WHERE user_id = %s", (user.id,)).fetchone()
    return row[0] if row else None


def _month_bounds(month: str) -> tuple[date, date]:
    y, m = (int(x) for x in month.split("-"))
    return date(y, m, 1), date(y + (m == 12), m % 12 + 1, 1)


def _write(conn: psycopg.Connection, sql: str, params: dict) -> dict | None:
    try:
        with conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
            return cur.execute(sql, params).fetchone()
    except psycopg.errors.ForeignKeyViolation as exc:
        raise HTTPException(status_code=422, detail="unknown store_id") from exc


@router.post("", response_model=schemas.SpendEntry, status_code=201)
def create_spend(body: schemas.SpendEntryIn, uc: UserConn, response: Response) -> schemas.SpendEntry:
    user, conn = uc
    row = _write(
        conn,
        "INSERT INTO spend_entries (user_id, client_id, date, store_id, store_name, total,"
        " item_count, plan) VALUES (%(uid)s, %(client_id)s, %(date)s, %(store_id)s, %(store_name)s,"
        " %(total)s, %(item_count)s, %(plan)s)"
        " ON CONFLICT (user_id, client_id) WHERE client_id IS NOT NULL DO NOTHING"
        f" RETURNING {_COLS}",
        {"uid": user.id, **body.model_dump()},
    )
    if row is None:  # the same client_id was stored before: a replay
        with conn.cursor(row_factory=dict_row) as cur:
            row = cur.execute(
                f"SELECT {_COLS} FROM spend_entries WHERE user_id = %s AND client_id = %s",
                (user.id, body.client_id),
            ).fetchone()
        response.status_code = 200
    assert row is not None
    return _entry(row)


@router.get("", response_model=schemas.SpendMonth)
def month_spend(
    uc: UserConn,
    month: Annotated[str | None, Query(pattern=MONTH, description="YYYY-MM; default the current month (UTC)")] = None,
) -> schemas.SpendMonth:
    user, conn = uc
    month = month or datetime.now(UTC).strftime("%Y-%m")
    first, after = _month_bounds(month)
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            f"SELECT {_COLS} FROM spend_entries WHERE user_id = %s AND date >= %s AND date < %s"
            " ORDER BY date, id",
            (user.id, first, after),
        ).fetchall()
    entries = [_entry(r) for r in rows]
    return schemas.SpendMonth(
        month=month,
        entries=entries,
        total=sum((e.total for e in entries), Decimal("0.00")),
        budget=_budget(conn, user),
    )


@router.get("/export", response_model=schemas.SpendExport)
def export_spend(uc: UserConn) -> schemas.SpendExport:
    """Every spend entry of the user, oldest first, and the budget."""
    user, conn = uc
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            f"SELECT {_COLS} FROM spend_entries WHERE user_id = %s ORDER BY date, id", (user.id,)
        ).fetchall()
    return schemas.SpendExport(
        budget=_budget(conn, user), entries=[_entry(r) for r in rows], generated_at=datetime.now(UTC)
    )


@router.put("/{entry_id}", response_model=schemas.SpendEntry)
def update_spend(entry_id: int, body: schemas.SpendEntryIn, uc: UserConn) -> schemas.SpendEntry:
    """Replace an entry, e.g. with the actual checkout total."""
    user, conn = uc
    row = _write(
        conn,
        "UPDATE spend_entries SET date = %(date)s, store_id = %(store_id)s,"
        " store_name = %(store_name)s, total = %(total)s, item_count = %(item_count)s,"
        f" plan = %(plan)s WHERE id = %(id)s AND user_id = %(uid)s RETURNING {_COLS}",
        {"uid": user.id, "id": entry_id, **body.model_dump()},
    )
    if row is None:
        raise HTTPException(status_code=404, detail="spend entry not found")
    return _entry(row)


@router.delete("/{entry_id}", status_code=204)
def delete_spend(entry_id: int, uc: UserConn) -> Response:
    user, conn = uc
    deleted = conn.execute(
        "DELETE FROM spend_entries WHERE id = %s AND user_id = %s", (entry_id, user.id)
    ).rowcount
    if not deleted:
        raise HTTPException(status_code=404, detail="spend entry not found")
    return Response(status_code=204)
