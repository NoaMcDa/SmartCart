"""Supabase Auth for the API (issue #64).

The web app signs in with Supabase Auth and sends the session's access token as
``Authorization: Bearer <jwt>``. The API verifies it with the project's JWT secret (HS256,
``SUPABASE_JWT_SECRET``), checks ``exp`` and the ``authenticated`` audience, and takes the user id
from ``sub``.

Routes that touch user tables depend on ``user_conn``: inside the request transaction it runs
``SET LOCAL ROLE smartcart_app`` (a role without BYPASSRLS, migration 20261007110100) and sets
``request.jwt.claim.sub`` / ``request.jwt.claims``, which is what ``auth.uid()`` reads. So the
same row-level security policies that protect PostgREST protect the API: a bug in a route cannot
read or write another user's rows. Both settings are transaction-local and are reset when the
request ends.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

import jwt
import psycopg
from fastapi import Depends, Header, HTTPException
from psycopg import sql
from psycopg.pq import TransactionStatus

from smartcart_api.db import get_conn
from smartcart_api.settings import Settings, get_settings


@dataclass(frozen=True)
class User:
    id: uuid.UUID
    claims: dict


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="expected a Bearer token",
                            headers={"WWW-Authenticate": "Bearer"})
    return token.strip()


def verify_token(token: str, settings: Settings) -> User:
    if not settings.jwt_secret:
        raise HTTPException(status_code=503, detail="SUPABASE_JWT_SECRET is not configured")
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience or None,
            options={"require": ["exp", "sub"], "verify_aud": bool(settings.jwt_audience)},
        )
        user_id = uuid.UUID(str(claims["sub"]))
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail=f"invalid token: {exc}",
                            headers={"WWW-Authenticate": "Bearer"}) from exc
    if claims.get("role") == "anon":
        raise HTTPException(status_code=401, detail="sign in required")
    return User(id=user_id, claims=claims)


def optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    """The signed-in user when a valid token is sent, else None (anonymous feedback)."""
    token = _bearer(authorization)
    if token is None:
        return None
    return verify_token(token, get_settings())


def current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    token = _bearer(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="sign in required",
                            headers={"WWW-Authenticate": "Bearer"})
    return verify_token(token, get_settings())


def user_conn(
    user: Annotated[User, Depends(current_user)],
    conn: Annotated[psycopg.Connection, Depends(get_conn)],
) -> Iterator[tuple[User, psycopg.Connection]]:
    """A connection on which row-level security applies as ``user``."""
    role = get_settings().db_user_role
    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
    conn.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true),"
        " set_config('request.jwt.claims', %s, true)",
        (str(user.id), json.dumps(user.claims, default=str)),
    )
    try:
        yield user, conn
    finally:
        if conn.info.transaction_status == TransactionStatus.INTRANS:
            conn.execute("RESET ROLE")
            conn.execute(
                "SELECT set_config('request.jwt.claim.sub', '', true),"
                " set_config('request.jwt.claims', '', true)"
            )
