"""Closed beta membership and feedback (issue #40, docs/beta-plan.md "Running the beta").

* ``POST /beta/join {code}`` (signed in) turns a valid invite code into a ``beta_members`` row.
  The code is looked up on the service connection, because ``beta_invites`` is readable by nobody
  through the app roles. The invite row is locked (``FOR UPDATE``) for the whole request, so two
  people racing for the last place of a code serialize: exactly ``max_uses`` of them get in.
  404 for an unknown code, 410 for an expired or used-up one. A member who sends any code again
  gets their membership back and no place is used.
* ``GET /me/beta`` and ``DELETE /me/beta`` run under row-level security as the user: they read
  and delete only their own ``beta_members`` row. Leaving is idempotent. (Turning the events off
  is the browser's part: ``setTrackingConsent(false)``.)
* ``POST /beta/feedback`` (members only) stores a 1 to 5 rating and up to 1000 characters with
  the member's segment and nothing else: no user id, so the text cannot be tied to a person from
  the database. Only the maintainer reads it (``smartcart-catalog beta-feedback``).

No personal data beyond the user id the app already has is stored.
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from smartcart_api import schemas
from smartcart_api.auth import User, current_user, user_conn
from smartcart_api.db import get_conn

router = APIRouter(tags=["beta"])
UserConn = Annotated[tuple[User, psycopg.Connection], Depends(user_conn, scope="function")]


@router.post(
    "/beta/join",
    response_model=schemas.BetaMembership,
    summary="Join the closed beta with an invite code",
    responses={404: {"description": "unknown code"}, 410: {"description": "expired or used up"}},
)
def join_beta(
    body: schemas.BetaJoinRequest,
    user: Annotated[User, Depends(current_user)],
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
) -> schemas.BetaMembership:
    code = body.code.strip().upper()
    invite = conn.execute(
        "SELECT segment, max_uses, uses, expires_at IS NOT NULL AND expires_at <= now()"
        " FROM beta_invites WHERE code = %s FOR UPDATE",
        (code,),
    ).fetchone()
    if invite is None:
        raise HTTPException(status_code=404, detail="unknown invite code")
    existing = conn.execute(
        "SELECT segment FROM beta_members WHERE user_id = %s", (user.id,)
    ).fetchone()
    if existing is not None:
        return schemas.BetaMembership(member=True, segment=existing[0])
    segment, max_uses, uses, expired = invite
    if expired:
        raise HTTPException(status_code=410, detail="this invite code has expired")
    if uses >= max_uses:
        raise HTTPException(status_code=410, detail="this invite code has been used up")
    try:
        with conn.transaction():
            conn.execute("UPDATE beta_invites SET uses = uses + 1 WHERE code = %s", (code,))
            # a token for an account that no longer exists is a 401, not a server error
            conn.execute(
                "INSERT INTO beta_members (user_id, code, segment)"
                " VALUES ((SELECT id FROM auth.users WHERE id = %s), %s, %s)",
                (user.id, code, segment),
            )
    except psycopg.errors.NotNullViolation as exc:
        raise HTTPException(status_code=401, detail="unknown account") from exc
    return schemas.BetaMembership(member=True, segment=segment)


@router.get("/me/beta", response_model=schemas.BetaMembership, summary="Am I in the closed beta?")
def my_beta(uc: UserConn) -> schemas.BetaMembership:
    user, conn = uc
    row = conn.execute("SELECT segment FROM beta_members WHERE user_id = %s", (user.id,)).fetchone()
    return schemas.BetaMembership(member=row is not None, segment=row[0] if row else None)


@router.delete("/me/beta", response_model=schemas.Ack, summary="Leave the closed beta")
def leave_beta(uc: UserConn) -> schemas.Ack:
    user, conn = uc
    conn.execute("DELETE FROM beta_members WHERE user_id = %s", (user.id,))
    return schemas.Ack(ok=True)


@router.post(
    "/beta/feedback",
    response_model=schemas.Ack,
    status_code=201,
    summary="Send feedback on the beta (members only)",
    responses={403: {"description": "not a beta member"}},
)
def post_feedback(
    body: schemas.BetaFeedbackIn,
    user: Annotated[User, Depends(current_user)],
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
) -> schemas.Ack:
    row = conn.execute("SELECT segment FROM beta_members WHERE user_id = %s", (user.id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=403, detail="beta members only")
    # Deliberately no user_id: the text is stored with the segment and nothing else.
    conn.execute(
        "INSERT INTO beta_feedback (segment, rating, body) VALUES (%s, %s, %s)",
        (row[0], body.rating, body.text.strip()),
    )
    return schemas.Ack(ok=True)
