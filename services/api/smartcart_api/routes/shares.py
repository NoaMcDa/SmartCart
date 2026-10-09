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
   member's ``role``, and ``GET /me/shared-lists``, the shared ones only).
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
from fastapi import APIRouter, Depends, HTTPException, Response

from smartcart_api import schemas
from smartcart_api.auth import User, current_user, user_conn
from smartcart_api.db import get_conn
from smartcart_api.lists import load_lists
from smartcart_api.routes.me_delete import as_user
from smartcart_api.settings import get_settings

router = APIRouter(tags=["shares"])
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


@router.post("/me/lists/{list_id}/share", response_model=schemas.ShareInvite, status_code=201)
def share_list(list_id: int, body: schemas.ShareRequest, uc: UserConn) -> schemas.ShareInvite:
    user, conn = uc
    if not _sharing_enabled():
        raise HTTPException(status_code=403, detail="family sharing is not enabled")
    if not _owned(conn, user, list_id):
        raise HTTPException(status_code=404, detail="list not found")
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


@router.post("/lists/accept/{token}", response_model=schemas.ShoppingList)
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
