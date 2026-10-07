"""The demo's signed-in user: a fixed id in ``auth.users`` and HS256 tokens for it.

The API verifies Supabase access tokens with the project's JWT secret (``SUPABASE_JWT_SECRET``,
``smartcart_api/auth.py``). The demo has no Supabase project, so ``up.sh`` starts the API with a
throwaway secret and this module mints tokens with the same claims Supabase puts in an access
token (``sub``, ``aud = authenticated``, ``role = authenticated``, ``exp``). The user row is the
stand-in ``auth.users`` the migrations create locally (on the Supabase image the real table
accepts the same insert).

    python scripts/demo/demo_user.py ensure     # insert the user (idempotent)
    python scripts/demo/demo_user.py token      # print a token valid for one hour

Never use the demo secret anywhere but a throwaway database.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import time

DEMO_USER_ID = "00000000-0000-4000-8000-00000000d3e0"
DEMO_USER_EMAIL = "demo@smartcart.invalid"
DEMO_JWT_SECRET = "smartcart-demo-secret-not-for-production-0123456789"


def secret() -> str:
    return os.environ.get("SUPABASE_JWT_SECRET") or DEMO_JWT_SECRET


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def mint_token(user_id: str = DEMO_USER_ID, ttl_seconds: int = 3600, key: str | None = None) -> str:
    """An HS256 JWT shaped like a Supabase access token."""
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "email": DEMO_USER_EMAIL,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    signing_input = (
        _b64(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64(json.dumps(payload, separators=(",", ":")).encode())
    )
    sig = hmac.new((key or secret()).encode(), signing_input.encode(), hashlib.sha256).digest()
    return signing_input + "." + _b64(sig)


def ensure_user(dsn: str) -> None:
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO auth.users (id, email) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
            (DEMO_USER_ID, DEMO_USER_EMAIL),
        )


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "token"
    if cmd == "ensure":
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            print("DATABASE_URL is not set", file=sys.stderr)
            return 2
        ensure_user(dsn)
        print(DEMO_USER_ID)
        return 0
    if cmd == "token":
        print(mint_token())
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
