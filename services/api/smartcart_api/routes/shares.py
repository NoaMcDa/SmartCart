"""Shared lists (issue #34).

Flow:

1. The owner creates an invite: ``POST /me/lists/{list_id}/share`` with a role (``editor`` or
   ``viewer``). The token is 32 random bytes (``secrets.token_urlsafe``); only its SHA-256 is
   stored (``list_shares.invite_token``), so a database read does not reveal usable links. The
   invite expires after ``API_SHARE_INVITE_DAYS`` days (default 7) unless accepted. The link is
   ``{API_PUBLIC_WEB_URL}/lists/accept/{token}`` (default: the first CORS origin).
2. A signed-in user accepts it: ``POST /lists/accept/{token}`` sets ``member_id`` and
   ``accepted_at``. An invite is single use: accepted by someone else, revoked or expired, it
   cannot be used (409, 404, 410). The owner accepting their own link gets the list back.
   Pending invites are invisible to the invitee under RLS, so this one step runs on the service
   connection; the list is then read back under RLS as the new member.
3. Access is row-level security (migrations 20261008100000_phase2.sql and
   20261008100100_shared_lists_rls.sql): owners and accepted members read the list and its
   items; owners and editors write items; viewers cannot write; strangers see nothing. Members
   edit items through Supabase PostgREST and receive changes through Realtime; the API offers
   the read side (``GET /me/lists``, which includes accepted shared lists with ``shared`` and the
   member's ``role``, and ``GET /me/shared-lists``, the shared ones only). Where there is no
   Supabase client (local development, the mock) owner and editors write through the per-item
   routes below instead: ``POST /me/lists/{id}/items``, ``PATCH`` and ``DELETE`` on
   ``/me/lists/{id}/items/{item_id}``, with ``updated_at`` as the item's version.
4. The owner lists members (``GET /me/lists/{list_id}/members``; a member sees the owner and
   themselves only; every invite and membership row carries its ``share_id``), revokes a
   pending invite or removes a member by that id (``DELETE /me/lists/{list_id}/shares/{share_id}``),
   revokes an invite or a membership by token (``DELETE /me/lists/{list_id}/share/{token}``) or
   removes a member by user id (``DELETE /me/lists/{list_id}/members/{member_id}``). Access ends
   with the transaction.

Family sharing is a paid-tier feature (D12): ``API_FAMILY_SHARING`` (default on) gates invite
creation; when off, creating an invite answers 403. Members never see each other's profile,
location or preferences (those tables stay owner-only under RLS).
"""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row
from pydantic import AwareDatetime

from smartcart_api import schemas
from smartcart_api.auth import User, current_user, user_conn
from smartcart_api.db import get_conn
from smartcart_api.lists import (
    ITEM_COLS,
    MAX_ITEMS_PER_LIST,
    item_from_row,
    load_lists,
    lock_list_items,
    require_editor,
)
from smartcart_api.ratelimit import limit
from smartcart_api.routes.me_delete import as_user
from smartcart_api.settings import get_settings

router = APIRouter(tags=["shares"], dependencies=[Depends(limit("me", 240))])
MAX_SHARES_PER_LIST = 50  # invites (pending and accepted) per list
UserConn = Annotated[tuple[User, psycopg.Connection], Depends(user_conn, scope="function")]


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _invite_days() -> int:
    try:
        return max(1, int(os.environ.get("API_SHARE_INVITE_DAYS", "7")))
    except ValueError:
        return 7


def _sharing_enabled() -> bool:
    return os.environ.get("API_FAMILY_SHARING", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _web_origin() -> str:
    origin = os.environ.get("API_PUBLIC_WEB_URL", "").strip()
    if not origin:
        origins = get_settings().cors_origins
        origin = origins[0] if origins else ""
    return origin.rstrip("/")


def _owned(conn: psycopg.Connection, user: User, list_id: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM lists WHERE id = %s AND user_id = %s", (list_id, user.id)
        ).fetchone()
        is not None
    )


@router.post(
    "/me/lists/{list_id}/share",
    response_model=schemas.ShareInvite,
    status_code=201,
    dependencies=[Depends(limit("share", 10, per_hour=60))],
)
def share_list(list_id: int, body: schemas.ShareRequest, uc: UserConn) -> schemas.ShareInvite:
    user, conn = uc
    if not _sharing_enabled():
        raise HTTPException(status_code=403, detail="family sharing is not enabled")
    if not _owned(conn, user, list_id):
        raise HTTPException(status_code=404, detail="list not found")
    rows = conn.execute(
        "SELECT count(*) FROM list_shares WHERE list_id = %s", (list_id,)
    ).fetchone()
    if rows[0] >= MAX_SHARES_PER_LIST:
        raise HTTPException(
            status_code=403,
            detail=f"a list has at most {MAX_SHARES_PER_LIST} invites and members; revoke some",
        )
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO list_shares (list_id, owner_id, role, invite_token, expires_at)"
        " VALUES (%s, %s, %s, %s, %s)",
        (
            list_id,
            user.id,
            body.role,
            token_hash(token),
            datetime.now(UTC) + timedelta(days=_invite_days()),
        ),
    )
    return schemas.ShareInvite(
        list_id=list_id, token=token, url=f"{_web_origin()}/lists/accept/{token}", role=body.role
    )


@router.get("/me/lists/{list_id}/members", response_model=list[schemas.ListMember])
def list_members(list_id: int, uc: UserConn) -> list[schemas.ListMember]:
    """The owner sees every invite and member; a member sees the owner and themselves."""
    user, conn = uc
    owner = conn.execute(
        "SELECT user_id, created_at FROM lists WHERE id = %s", (list_id,)
    ).fetchone()
    if owner is None:  # RLS: neither the owner nor a member
        raise HTTPException(status_code=404, detail="list not found")
    out = [
        schemas.ListMember(
            user_id=str(owner[0]), role="editor", accepted_at=owner[1], is_owner=True
        )
    ]
    for share_id, member_id, role, accepted_at in conn.execute(
        "SELECT id, member_id, role, accepted_at FROM list_shares WHERE list_id = %s"
        " AND (member_id IS NOT NULL OR expires_at IS NULL OR expires_at > now())"
        " ORDER BY accepted_at NULLS LAST, created_at, id",
        (list_id,),
    ).fetchall():
        out.append(
            schemas.ListMember(
                user_id=str(member_id) if member_id else None,
                role=role,
                accepted_at=accepted_at,
                share_id=share_id,
            )
        )
    return out


@router.delete("/me/lists/{list_id}/shares/{share_id}", status_code=204)
def delete_share(list_id: int, share_id: int, uc: UserConn) -> Response:
    """Owner only: revoke a pending invite or remove a member by the share's id (the ``share_id``
    of ``GET /me/lists/{list_id}/members``). The member, if any, loses access at once."""
    user, conn = uc
    deleted = conn.execute(
        "DELETE FROM list_shares WHERE list_id = %s AND id = %s AND owner_id = %s",
        (list_id, share_id, user.id),
    ).rowcount
    if not deleted:
        raise HTTPException(status_code=404, detail="share not found")
    return Response(status_code=204)


@router.delete("/me/lists/{list_id}/share/{token}", status_code=204)
def revoke_share(list_id: int, token: str, uc: UserConn) -> Response:
    """Owner only: the invite is revoked, and its member (if accepted) loses access."""
    user, conn = uc
    deleted = conn.execute(
        "DELETE FROM list_shares WHERE list_id = %s AND invite_token = %s AND owner_id = %s",
        (list_id, token_hash(token), user.id),
    ).rowcount
    if not deleted:
        raise HTTPException(status_code=404, detail="invite not found")
    return Response(status_code=204)


@router.delete("/me/lists/{list_id}/members/{member_id}", status_code=204)
def remove_member(list_id: int, member_id: uuid.UUID, uc: UserConn) -> Response:
    """Owner only: remove an accepted member."""
    user, conn = uc
    deleted = conn.execute(
        "DELETE FROM list_shares WHERE list_id = %s AND member_id = %s AND owner_id = %s",
        (list_id, member_id, user.id),
    ).rowcount
    if not deleted:
        raise HTTPException(status_code=404, detail="member not found")
    return Response(status_code=204)


# --- single items: the write path of a shared list ---------------------------------------------
#
# Owner and accepted editors change one item at a time, so two people editing the same list never
# overwrite each other's items the way a whole-list PUT does. Every statement runs under the
# caller's row-level security (list_items_insert / _update / _delete), and the list in the path
# must be the item's list (an item id of another list is a 404, never touched). Viewers read only
# (403); a list the caller cannot see is a 404.
#
# Version check: each item has ``updated_at`` (a trigger moves it on every real change). PATCH
# takes ``expected_updated_at`` in the body and DELETE takes it as a query parameter (URL-encode
# the "+" of an offset); when it is not the item's current version, nothing is changed and the
# answer is a 409 with the current row (``ListItemConflict``). Not ``If-Unmodified-Since``: that
# header has a resolution of one second, and two people tick the same item within a second.

_CONFLICT = {
    409: {
        "model": schemas.ListItemConflict,
        "description": "The item changed since expected_updated_at; the body has its current state",
    }
}
_PATCHABLE = ("canonical_id", "input_text", "quantity", "flex_level", "confirmed", "checked")


def _conflict(row: dict) -> JSONResponse:
    body = schemas.ListItemConflict(
        detail="the item changed since you read it", current=item_from_row(row)
    )
    return JSONResponse(status_code=409, content=body.model_dump(mode="json"))


def _locked_item(
    conn: psycopg.Connection, list_id: int, item_id: int, expected: datetime | None
) -> tuple[dict, bool]:
    """The item, locked for this transaction, and whether it still has the expected version
    (always true without one). 404 when the list has no such item (or it is not visible)."""
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            f"SELECT {ITEM_COLS},"
            " date_trunc('milliseconds', updated_at) = date_trunc('milliseconds', %s::timestamptz)"
            "   AS fresh FROM list_items WHERE id = %s AND list_id = %s FOR UPDATE",
            (expected, item_id, list_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="item not found")
    return row, expected is None or bool(row.pop("fresh"))


@router.post(
    "/me/lists/{list_id}/items",
    response_model=schemas.ListItem,
    status_code=201,
    responses={200: {"model": schemas.ListItem, "description": "A replay: the item stored before"}},
)
def add_item(
    list_id: int, body: schemas.ListItemIn, uc: UserConn, response: Response
) -> schemas.ListItem:
    """Appends an item to the end of the list (owner or editor). ``id`` in the body is ignored.
    With a ``client_id`` the add is idempotent per list: a replay answers 200 with the stored item
    (the one that was added first, as it is now) and inserts nothing, also when the list has since
    reached its size cap."""
    user, conn = uc
    require_editor(conn, user, list_id)
    lock_list_items(conn, list_id)
    if body.client_id is not None:
        with conn.cursor(row_factory=dict_row) as cur:
            stored = cur.execute(
                f"SELECT {ITEM_COLS} FROM list_items WHERE list_id = %s AND client_id = %s",
                (list_id, body.client_id),
            ).fetchone()
        if stored is not None:
            response.status_code = 200
            return item_from_row(stored)
    count, top = conn.execute(
        "SELECT count(*), COALESCE(max(sort), -1) FROM list_items WHERE list_id = %s", (list_id,)
    ).fetchone()
    if count >= MAX_ITEMS_PER_LIST:
        raise HTTPException(
            status_code=403, detail=f"a list has at most {MAX_ITEMS_PER_LIST} items"
        )
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            "INSERT INTO list_items (list_id, user_id, canonical_id, input_text, quantity,"
            " flex_level, confirmed, checked, sort, client_id)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            f" RETURNING {ITEM_COLS}",
            (
                list_id,
                user.id,
                body.canonical_id,
                body.input_text,
                body.quantity,
                body.flex_level,
                body.confirmed,
                body.checked,
                top + 1,
                body.client_id,
            ),
        ).fetchone()
    return item_from_row(row)


@router.patch(
    "/me/lists/{list_id}/items/{item_id}",
    response_model=schemas.ListItem,
    responses=_CONFLICT,
)
def patch_item(
    list_id: int, item_id: int, body: schemas.ListItemPatch, uc: UserConn
) -> schemas.ListItem | JSONResponse:
    """Changes the named fields of one item (owner or editor), and answers the item. With
    ``expected_updated_at`` the change is made only if nobody changed the item since: otherwise
    409 with the current item. 404 when the item is gone."""
    user, conn = uc
    require_editor(conn, user, list_id)
    row, fresh = _locked_item(conn, list_id, item_id, body.expected_updated_at)
    if not fresh:
        return _conflict(row)
    changes = {c: getattr(body, c) for c in _PATCHABLE if c in body.model_fields_set}
    if changes:
        sets = ", ".join(f"{c} = %({c})s" for c in changes)
        with conn.cursor(row_factory=dict_row) as cur:
            row = cur.execute(
                f"UPDATE list_items SET {sets} WHERE id = %(item_id)s AND list_id = %(list_id)s"
                f" RETURNING {ITEM_COLS}",
                {**changes, "item_id": item_id, "list_id": list_id},
            ).fetchone()
    return item_from_row(row)


@router.delete(
    "/me/lists/{list_id}/items/{item_id}",
    status_code=204,
    responses=_CONFLICT,
)
def delete_item(
    list_id: int,
    item_id: int,
    uc: UserConn,
    expected_updated_at: Annotated[
        AwareDatetime | None, Query(description="Delete only if this is still the item's version")
    ] = None,
) -> Response:
    """Removes one item (owner or editor). With ``expected_updated_at``, only if nobody changed it
    since: otherwise 409 with the current item. 404 when the item is already gone."""
    user, conn = uc
    require_editor(conn, user, list_id)
    row, fresh = _locked_item(conn, list_id, item_id, expected_updated_at)
    if not fresh:
        return _conflict(row)
    conn.execute("DELETE FROM list_items WHERE id = %s AND list_id = %s", (item_id, list_id))
    return Response(status_code=204)


@router.get("/me/shared-lists", response_model=list[schemas.ShoppingList])
def shared_lists(uc: UserConn) -> list[schemas.ShoppingList]:
    """Lists other users shared with the signed-in user (accepted invites)."""
    user, conn = uc
    ids = [
        r[0]
        for r in conn.execute(
            "SELECT list_id FROM list_shares WHERE member_id = %s AND accepted_at IS NOT NULL",
            (user.id,),
        ).fetchall()
    ]
    return load_lists(conn, user, ids, owned=False)


@router.post(
    "/lists/accept/{token}",
    response_model=schemas.ShoppingList,
    dependencies=[Depends(limit("accept-share", 10, per_hour=60))],
)
def accept_share(
    token: str,
    user: Annotated[User, Depends(current_user)],
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
) -> schemas.ShoppingList:
    # Service connection: a pending invite is not visible to the invitee under RLS.
    row = conn.execute(
        "SELECT list_id, owner_id, member_id, expires_at FROM list_shares"
        " WHERE invite_token = %s FOR UPDATE",
        (token_hash(token),),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="invite not found or revoked")
    list_id, owner_id, member_id, expires_at = row
    if owner_id != user.id:
        if member_id is not None and member_id != user.id:
            raise HTTPException(status_code=409, detail="invite already used")
        if member_id is None:
            if expires_at is not None and expires_at <= datetime.now(UTC):
                raise HTTPException(status_code=410, detail="invite expired")
            conn.execute(
                "UPDATE list_shares SET member_id = %s, accepted_at = now()"
                " WHERE invite_token = %s",
                (user.id, token_hash(token)),
            )
    with as_user(conn, user):
        found = load_lists(conn, user, [list_id])
    if not found:
        raise HTTPException(status_code=404, detail="list not found")
    return found[0]
