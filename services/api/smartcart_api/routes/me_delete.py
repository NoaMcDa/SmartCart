"""Account deletion, ``DELETE /me`` (issue #90, delete-my-data #30, #55).

Order, chosen so the request never waits on itself:

1. When ``SUPABASE_URL`` and ``SUPABASE_SERVICE_ROLE_KEY`` are set, the auth user is deleted
   first through the Supabase Admin API (``DELETE {SUPABASE_URL}/auth/v1/admin/users/{id}``,
   httpx). Every user table references ``auth.users`` with ``ON DELETE CASCADE``, so Supabase
   removes the rows itself. Doing this before the request transaction touches any row avoids a
   lock wait between that cascade and this transaction. A failure answers 502 and deletes
   nothing; a 404 means the auth user is already gone and the rest proceeds.
2. Under row-level security as the user (``smartcart_app``, ``auth.uid()``): push
   subscriptions, price alerts (their deliveries cascade), shares the user owns, lists (their
   items and shares cascade), profile, preferences and substitution feedback. RLS guarantees
   these statements cannot touch another user's rows.
3. On the service connection: the user's memberships in other people's lists and the items they
   added there, ``gap_reports.user_id`` and ``events.user_id`` set to NULL (anonymous
   statistics, as an auth delete would do for events).
4. Without the Admin API settings, the row of the stand-in ``auth.users`` (local and test
   databases) is deleted. On hosted Supabase the API role may not delete from ``auth.users``;
   the warning ``auth user not deleted`` is then logged and the user must be removed by hand
   (Supabase dashboard, Authentication, Users), as documented in docs/api.md.

``as_user`` is the context manager the phase 2 routes use when a route needs both the service
connection and the user's RLS view in one request (``auth.user_conn`` covers the common case).
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

import httpx
import psycopg
import structlog
from fastapi import APIRouter, Depends, HTTPException
from psycopg import sql
from psycopg.pq import TransactionStatus

from smartcart_api import schemas
from smartcart_api.auth import User, current_user
from smartcart_api.db import get_conn
from smartcart_api.settings import get_settings

log = structlog.get_logger("smartcart_api.me_delete")
router = APIRouter(prefix="/me", tags=["me"])


@contextmanager
def as_user(conn: psycopg.Connection, user: User) -> Iterator[psycopg.Connection]:
    """Row-level security as ``user`` for the block, inside the request transaction."""
    role = get_settings().db_user_role
    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
    conn.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true),"
        " set_config('request.jwt.claims', %s, true)",
        (str(user.id), json.dumps(user.claims, default=str)),
    )
    try:
        yield conn
    finally:
        if conn.info.transaction_status == TransactionStatus.INTRANS:
            conn.execute("RESET ROLE")
            conn.execute(
                "SELECT set_config('request.jwt.claim.sub', '', true),"
                " set_config('request.jwt.claims', '', true)"
            )


def supabase_admin() -> tuple[str, str] | None:
    """(project URL, service role key) when both are configured."""
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    return (url, key) if url and key else None


def delete_auth_user(user_id: uuid.UUID, url: str, key: str, client: httpx.Client | None = None) -> None:
    """Delete the Supabase Auth user; 404 (already gone) counts as done."""
    own = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        r = client.delete(
            f"{url}/auth/v1/admin/users/{user_id}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="could not reach Supabase Auth") from exc
    finally:
        if own:
            client.close()
    if r.status_code not in (200, 204, 404):
        log.error("supabase admin delete failed", status=r.status_code)
        raise HTTPException(status_code=502, detail=f"Supabase Auth answered {r.status_code}")


# Under RLS: each statement can only reach the signed-in user's rows.
_OWN_ROWS = (
    "DELETE FROM push_subscriptions WHERE user_id = %(uid)s",
    "DELETE FROM price_alerts WHERE user_id = %(uid)s",
    "DELETE FROM list_shares WHERE owner_id = %(uid)s",
    "DELETE FROM lists WHERE user_id = %(uid)s",
    "DELETE FROM profiles WHERE user_id = %(uid)s",
    "DELETE FROM preferences WHERE user_id = %(uid)s",
    "DELETE FROM substitution_feedback WHERE user_id = %(uid)s",
)
# Service connection: rows the user's policies do not let them delete.
_SERVICE_ROWS = (
    "DELETE FROM list_shares WHERE member_id = %(uid)s",
    "DELETE FROM list_items WHERE user_id = %(uid)s",
    "UPDATE gap_reports SET user_id = NULL WHERE user_id = %(uid)s",
    "UPDATE events SET user_id = NULL WHERE user_id = %(uid)s",
)


@router.delete("", response_model=schemas.Ack)
def delete_me(
    user: Annotated[User, Depends(current_user)],
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
) -> schemas.Ack:
    admin = supabase_admin()
    if admin is not None:
        delete_auth_user(user.id, *admin)
    params = {"uid": user.id}
    with as_user(conn, user):
        for stmt in _OWN_ROWS:
            conn.execute(stmt, params)
    for stmt in _SERVICE_ROWS:
        conn.execute(stmt, params)
    if admin is None:
        try:
            with conn.transaction():
                conn.execute("DELETE FROM auth.users WHERE id = %s", (user.id,))
        except psycopg.Error as exc:
            log.warning(
                "auth user not deleted; remove it in the Supabase dashboard",
                user_id=str(user.id), error=type(exc).__name__,
            )
        else:
            log.info("auth user deleted from the stand-in auth.users", user_id=str(user.id))
    log.info("account deleted", user_id=str(user.id), via_admin_api=admin is not None)
    return schemas.Ack(ok=True)
