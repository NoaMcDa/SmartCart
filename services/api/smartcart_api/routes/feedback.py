"""Feedback routes: substitution verdicts and report-a-gap (D10 trust signals).

Both accept anonymous callers; with a valid Bearer token the user id is recorded. Neither stores
a location.

* ``POST /feedback/substitution`` records the verdict in ``substitution_feedback``. A
  ``not_good`` verdict also flags the (substitute item, canonical) mapping in ``item_canonical``
  with ``needs_review``, which removes it from the next effective-price precompute until a human
  reviews it.
* ``POST /feedback/gap`` records a shown-versus-actual price (or a missing item) in
  ``gap_reports`` for the data-quality review.
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from smartcart_api import schemas
from smartcart_api.auth import User, optional_user
from smartcart_api.db import get_conn

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/substitution", response_model=schemas.Ack)
def substitution(
    body: schemas.SubstitutionFeedbackRequest,
    conn: Annotated[psycopg.Connection, Depends(get_conn)],
    user: Annotated[User | None, Depends(optional_user)],
) -> schemas.Ack:
    try:
        with conn.transaction():  # a savepoint: a bad id must not abort the request transaction
            fid = conn.execute(
                "INSERT INTO substitution_feedback (user_id, canonical_id, original_item_id,"
                " substitute_item_id, verdict) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (user.id if user else None, body.canonical_id, body.original_item_id,
                 body.substitute_item_id, body.verdict),
            ).fetchone()[0]
    except psycopg.errors.ForeignKeyViolation as exc:
        raise HTTPException(status_code=422, detail="unknown canonical or item") from exc
    if body.verdict == "not_good":
        conn.execute(
            "UPDATE item_canonical SET needs_review = true"
            " WHERE item_id = %s AND canonical_id = %s AND NOT needs_review",
            (body.substitute_item_id, body.canonical_id),
        )
    return schemas.Ack(id=fid)


@router.post("/gap", response_model=schemas.Ack)
def gap(
    body: schemas.GapReportRequest,
    conn: Annotated[psycopg.Connection, Depends(get_conn)],
    user: Annotated[User | None, Depends(optional_user)],
) -> schemas.Ack:
    try:
        with conn.transaction():
            gid = conn.execute(
                "INSERT INTO gap_reports (store_id, item_id, canonical_id, shown_price,"
                " actual_price, note, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (body.store_id, body.item_id, body.canonical_id, body.shown_price,
                 body.actual_price, body.note, user.id if user else None),
            ).fetchone()[0]
    except psycopg.errors.ForeignKeyViolation as exc:
        raise HTTPException(status_code=422, detail="unknown store, item or canonical") from exc
    return schemas.Ack(id=gid)
