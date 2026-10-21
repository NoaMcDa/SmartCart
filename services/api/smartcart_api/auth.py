"""Supabase Auth for the API (issue #64).

The web app signs in with Supabase Auth and sends the session's access token as
``Authorization: Bearer <jwt>``. The API verifies it with the project's public signing key (ES256 or
RS256, published as a JWKS: ``SUPABASE_JWKS_URL`` or derived from ``SUPABASE_URL``; smartcart_api/jwks.py)
or, for a project not yet migrated, with the shared JWT secret (HS256, ``SUPABASE_JWT_SECRET``), checks
``exp`` and the ``authenticated`` audience, and takes the user id from ``sub``.

Routes that touch user tables depend on ``user_conn``: inside the request transaction it runs
``SET LOCAL ROLE smartcart_app`` (a role without BYPASSRLS, migration 20261007110100) and sets
``request.jwt.claim.sub`` / ``request.jwt.claims``, which is what ``auth.uid()`` reads. So the
same row-level security policies that protect PostgREST protect the API: a bug in a route cannot
read or write another user's rows. Both settings are transaction-local and are reset when the
request ends.

Token checks (docs/security-review.md): the algorithm is pinned by the verifier, not read from the
token: HS256 only with the shared secret, ES256/RS256 only with a JWKS key that declares that
algorithm (a token naming ``none``, ``HS384``, ``EdDSA`` or any other algorithm is refused, and an
HS256 token is never checked against a published public key), ``exp`` and
``sub`` are required, ``aud`` must match ``SUPABASE_JWT_AUDIENCE``, ``iss`` must match
``SUPABASE_JWT_ISSUER`` when that is set, ``iat`` and ``nbf`` are honoured, and ``JWT_LEEWAY_S``
seconds of clock skew are tolerated. The role claim must be ``authenticated`` (an ``anon`` or
``service_role`` token never becomes a user). A refusal is always a 401 with a fixed message: the
verifier's own error text is not echoed.
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
from smartcart_api.jwks import ASYMMETRIC_ALGORITHMS, KeysUnavailable, get_cache
from smartcart_api.settings import Settings, get_settings

# Clock skew tolerated between Supabase Auth (which issues the token) and this server, in seconds.
JWT_LEEWAY_S = 30
# A Supabase access token is about 1 KB; anything past this is not one and is not worth decoding.
MAX_TOKEN_CHARS = 8192


@dataclass(frozen=True)
class User:
    id: uuid.UUID
    claims: dict


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="expected a Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def _signing_material(token: str, settings: Settings) -> tuple[object, str]:
    """The key and the one algorithm this token may be verified with, chosen by us, never by the
    token: the header's ``alg`` only selects *which* configured verifier applies, and must then
    equal what that verifier allows.

    * ``HS256``: the shared secret (``SUPABASE_JWT_SECRET``), when configured. Nothing from the
      JWKS is ever used as an HMAC key, so a token that is HS256-signed with a published public key
      (algorithm confusion) is checked against the secret and fails.
    * ``ES256`` / ``RS256``: the JWKS key with the token's ``kid``, verified with the algorithm
      that key declares.
    * anything else (``none``, ``HS384``, ``EdDSA``, ``PS256``, a missing or odd header): refused.
    """
    jwks_url = settings.jwks_url
    if not settings.jwt_secret and not jwks_url:
        raise HTTPException(status_code=503, detail="SUPABASE_JWT_SECRET is not configured")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise _unauthorized("invalid token") from None
    alg = header.get("alg")
    if alg == "HS256":
        if not settings.jwt_secret:
            raise _unauthorized("invalid token")  # the shared secret is switched off
        return settings.jwt_secret, "HS256"
    kid = header.get("kid")
    if alg not in ASYMMETRIC_ALGORITHMS or not jwks_url or not isinstance(kid, str) or not kid:
        raise _unauthorized("invalid token")
    cache = get_cache(jwks_url, settings.jwks_ttl_s, settings.jwks_min_refresh_s)
    try:
        signing_key = cache.get_key(kid)
    except KeysUnavailable:
        raise HTTPException(
            status_code=503, detail="signing keys are unavailable", headers={"Retry-After": "5"}
        ) from None
    if signing_key is None or signing_key.alg != alg:
        raise _unauthorized("invalid token")
    return signing_key.key, signing_key.alg


def verify_token(token: str, settings: Settings) -> User:
    if len(token) > MAX_TOKEN_CHARS:
        if not settings.jwt_secret and not settings.jwks_url:
            raise HTTPException(status_code=503, detail="SUPABASE_JWT_SECRET is not configured")
        raise _unauthorized("invalid token")
    key, algorithm = _signing_material(token, settings)
    issuer = settings.jwt_issuer or None
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            audience=settings.jwt_audience or None,
            issuer=issuer,
            leeway=JWT_LEEWAY_S,
            options={
                "require": ["exp", "sub", *(["iss"] if issuer else [])],
                "verify_aud": bool(settings.jwt_audience),
                "verify_iss": issuer is not None,
            },
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("token expired") from None
    except jwt.PyJWTError:
        # The library's message (which check failed) is for the log, not for the caller.
        raise _unauthorized("invalid token") from None
    try:
        user_id = uuid.UUID(str(claims["sub"]))
    except ValueError:
        raise _unauthorized("invalid token") from None
    # Supabase always sets the role. The anon key's token and the service role key's token are
    # JWTs signed with the same key; neither is a signed-in person.
    if claims.get("role") not in (None, "authenticated"):
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
        raise HTTPException(
            status_code=401, detail="sign in required", headers={"WWW-Authenticate": "Bearer"}
        )
    return verify_token(token, get_settings())


_RLS_CLAIMS = ("sub", "role", "aud", "exp", "iat", "is_anonymous")


def rls_claims(user: User) -> str:
    """The claims JSON for ``request.jwt.claims``: what the policies and ``auth.uid()`` read, and
    nothing else. A Supabase token also carries the e-mail address and the user metadata; those
    do not go into the database session (statement logs, ``auth.jwt()`` callers)."""
    return json.dumps({k: user.claims[k] for k in _RLS_CLAIMS if k in user.claims}, default=str)


def user_conn(
    user: Annotated[User, Depends(current_user)],
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
) -> Iterator[tuple[User, psycopg.Connection]]:
    """A connection on which row-level security applies as ``user``."""
    role = get_settings().db_user_role
    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
    conn.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true),"
        " set_config('request.jwt.claims', %s, true)",
        (str(user.id), rls_claims(user)),
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
