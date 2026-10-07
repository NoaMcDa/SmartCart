"""Feedback routes: substitution verdicts and report-a-gap (D10 trust signals).

Both accept anonymous callers; with a valid Bearer token the user id is recorded. Neither stores
a location.

* ``POST /feedback/substitution`` records the verdict through the catalog's write path,
  ``smartcart_catalog.feedback.record_feedback``, with its context (``list_item_id``,
  ``flex_level``, ``match_confidence``) and its ``source``: the substitution card, or the
  smart-cart swap (apply = ``accepted``, undo = ``kept_original``, dismiss = ``not_good``). A
  ``not_good`` verdict also flags the (substitute item, canonical) mapping in ``item_canonical``
  with ``needs_review`` (unless a human already rejected it), which removes it from the next
  effective-price precompute until a human reviews it. Swap verdicts count in the catalog's
  ``rejection_rates`` like any other.
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
from smartcart_catalog.feedback import record_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/substitution", response_model=schemas.Ack)
def substitution(
    body: schemas.SubstitutionFeedbackRequest,
    conn: Annotated[psycopg.Connection, Depends(get_conn)],
    user: Annotated[User | None, Depends(optional_user)],
) -> schemas.Ack:
    try:
        with conn.transaction():  # a savepoint: a bad id must not abort the request transaction
            result = record_feedback(
                conn,
                user.id if user else None,
                body.canonical_id,
                body.original_item_id,
                body.substitute_item_id,
                body.verdict,
                list_item_id=body.list_item_id,
                flex_level=body.flex_level,
                match_confidence=body.match_confidence,
            )
            if body.source != "substitution_card":  # the column's default
                conn.execute(
                    "UPDATE substitution_feedback SET source = %s WHERE id = %s",
                    (body.source, result.feedback_id),
                )
    except psycopg.errors.ForeignKeyViolation as exc:
        raise HTTPException(status_code=422, detail="unknown canonical or item") from exc
    return schemas.Ack(id=result.feedback_id)


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
