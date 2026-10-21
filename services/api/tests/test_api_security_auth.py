"""How the API verifies the Supabase JWT, and that no user route is reachable without one.

``test_me.py`` has the happy path and four bad tokens; this file is the full matrix (algorithm
pinning, ``alg: none``, every claim, clock skew, oversized and garbage tokens, the issuer pin), the
role claim, fixed error messages, and the route inventory: every route of the app is either listed
as public below or must answer 401 to an anonymous caller and to a garbage token. A new route that
forgets its auth dependency fails ``test_every_route_not_listed_as_public_requires_a_user``.
"""

from __future__ import annotations

import base64
import json
import re
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from api_world import JWT_SECRET, make_token

from smartcart_api.auth import JWT_LEEWAY_S, MAX_TOKEN_CHARS
from smartcart_api.main import app
from smartcart_api.settings import get_settings

pytestmark = pytest.mark.db

UID = uuid.uuid4()
URL = "/me/profile"


def _get(client, token: str | None = None, scheme: str = "Bearer", url: str = URL):
    headers = {} if token is None else {"Authorization": f"{scheme} {token}"}
    return client.get(url, headers=headers)


@pytest.fixture
def user(db) -> uuid.UUID:
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (UID,))
    return UID


def _forge(header: dict, payload: dict, key: bytes = b"") -> str:
    """A token with an arbitrary header, signed with ``key`` (HMAC-SHA256) when the header says
    HS256, left unsigned otherwise: what an attacker can build without the secret."""

    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    signing_input = f"{b64(json.dumps(header).encode())}.{b64(json.dumps(payload).encode())}"
    return f"{signing_input}." + (b64(b"\x00" * 32) if key else "")


def _claims(**over: object) -> dict:
    now = int(time.time())
    return {
        "sub": str(UID),
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + 3600,
        **over,
    }


def _sign(claims: dict, secret: str = JWT_SECRET, alg: str = "HS256") -> str:
    return jwt.encode(claims, secret, algorithm=alg)


# --- the happy path and the scheme -------------------------------------------------------------


def test_a_valid_token_gets_through_and_the_scheme_is_case_insensitive(client, user) -> None:
    token = make_token(user)
    assert _get(client, token).status_code == 200
    assert _get(client, token, scheme="bearer").status_code == 200
    assert _get(client, token, scheme="BEARER").status_code == 200


@pytest.mark.parametrize(
    "header", [None, "", "Bearer", "Bearer ", "Bearer    ", "Token abc", "abc"]
)
def test_a_missing_or_malformed_authorization_header_is_401(client, user, header) -> None:
    headers = {} if header is None else {"Authorization": header}
    r = client.get(URL, headers=headers)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("scheme", ["Basic", "Digest", "Negotiate"])
def test_other_schemes_are_401(client, user, scheme) -> None:
    assert _get(client, make_token(user), scheme=scheme).status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        "not.a.jwt",
        "a.b.c",
        "....",
        "eyJhbGciOiJIUzI1NiJ9",  # a header and nothing else
        "eyJhbGciOiJIUzI1NiJ9.e30.",  # empty signature
        "x" * 200,
        "Bearer",  # the word as a token: "Bearer Bearer"
        "'; DROP TABLE lists; --",
        "../../etc/passwd",
        "‮ل",  # a right-to-left override and an Arabic letter
    ],
)
def test_garbage_tokens_are_401(client, user, token) -> None:
    try:
        r = _get(client, token)
    except UnicodeEncodeError:  # not representable in a header: the client cannot even send it
        return
    assert r.status_code == 401


def test_a_token_with_extra_words_is_401(client, user) -> None:
    assert _get(client, f"{make_token(user)} extra").status_code == 401


def test_an_oversized_token_is_refused_without_decoding(client, user) -> None:
    big = make_token(user, padding="x" * (MAX_TOKEN_CHARS + 10))
    assert len(big) > MAX_TOKEN_CHARS
    assert _get(client, big).status_code == 401


# --- the signature and the algorithm ------------------------------------------------------------


def test_a_token_signed_with_another_secret_is_401(client, user) -> None:
    other = "another-secret-that-is-also-32-bytes-long"
    assert _get(client, _sign(_claims(), secret=other)).status_code == 401


def test_a_token_with_a_tampered_payload_is_401(client, user) -> None:
    head, _, sig = make_token(user).split(".")
    evil = base64.urlsafe_b64encode(json.dumps(_claims(sub=str(uuid.uuid4()))).encode()).rstrip(
        b"="
    )
    assert _get(client, f"{head}.{evil.decode()}.{sig}").status_code == 401


def test_alg_none_is_401(client, user) -> None:
    unsigned = _forge({"alg": "none", "typ": "JWT"}, _claims())
    assert _get(client, unsigned).status_code == 401
    for alg in ("None", "NONE", "nOnE"):
        assert _get(client, _forge({"alg": alg, "typ": "JWT"}, _claims())).status_code == 401


@pytest.mark.filterwarnings("ignore:The HMAC key is")  # the test secret is short for SHA-512
@pytest.mark.parametrize("alg", ["HS384", "HS512"])
def test_other_hmac_algorithms_are_401_even_with_the_right_secret(client, user, alg) -> None:
    assert _get(client, _sign(_claims(), alg=alg)).status_code == 401


@pytest.mark.parametrize("alg", ["RS256", "ES256", "PS256", "EdDSA"])
def test_asymmetric_algorithm_headers_are_401(client, user, alg) -> None:
    """The classic confusion attack: name an asymmetric algorithm and hope the HMAC secret (or a
    public key) is used as its key. The algorithm list is pinned, so the header is not believed."""
    assert _get(client, _forge({"alg": alg, "typ": "JWT"}, _claims(), key=b"k")).status_code == 401


def test_the_header_cannot_smuggle_a_key(client, user) -> None:
    forged = _forge(
        {"alg": "HS256", "typ": "JWT", "jwk": {"kty": "oct", "k": "AAAA"}, "kid": "../../x"},
        _claims(),
        key=b"k",
    )
    assert _get(client, forged).status_code == 401


# --- the claims ---------------------------------------------------------------------------------


def test_exp_and_sub_are_required(client, user) -> None:
    for missing in ("exp", "sub"):
        claims = _claims()
        del claims[missing]
        assert _get(client, _sign(claims)).status_code == 401, missing


@pytest.mark.parametrize("sub", ["", "abc", "123", "null", "1; DROP TABLE x", "z" * 36])
def test_sub_must_be_a_uuid(client, user, sub) -> None:
    assert _get(client, _sign(_claims(sub=sub))).status_code == 401


@pytest.mark.parametrize("sub", [123, None, ["a"], {"a": 1}, True])
def test_sub_must_be_a_string_uuid(client, user, sub) -> None:
    assert _get(client, _sign(_claims(sub=sub))).status_code == 401


def test_the_audience_is_checked(client, user) -> None:
    assert _get(client, _sign(_claims(aud="anon"))).status_code == 401
    assert _get(client, _sign(_claims(aud="service_role"))).status_code == 401
    assert _get(client, _sign(_claims(aud=["anon"]))).status_code == 401
    claims = _claims()
    del claims["aud"]
    assert _get(client, _sign(claims)).status_code == 401
    assert _get(client, _sign(_claims(aud=["authenticated", "other"]))).status_code == 200


@pytest.mark.parametrize("role", ["anon", "service_role", "supabase_admin", "postgres", ""])
def test_only_the_authenticated_role_is_a_user(client, user, role) -> None:
    assert _get(client, _sign(_claims(role=role))).status_code == 401


def test_a_token_without_a_role_claim_still_works(client, user) -> None:
    claims = _claims()
    del claims["role"]
    assert _get(client, _sign(claims)).status_code == 200


def test_expiry_and_clock_skew(client, user) -> None:
    now = int(time.time())
    assert _get(client, _sign(_claims(exp=now - 5))).status_code == 200  # skew tolerated
    assert _get(client, _sign(_claims(exp=now - JWT_LEEWAY_S - 30))).status_code == 401
    r = _get(client, _sign(_claims(exp=now - 3600)))
    assert r.status_code == 401 and r.json()["detail"] == "token expired"
    # not yet valid: nbf and iat in the future
    assert _get(client, _sign(_claims(nbf=now + 5))).status_code == 200
    assert _get(client, _sign(_claims(nbf=now + JWT_LEEWAY_S + 60))).status_code == 401
    assert _get(client, _sign(_claims(iat=now + JWT_LEEWAY_S + 60))).status_code == 401
    # exp must be a number
    assert _get(client, _sign(_claims(exp="tomorrow"))).status_code == 401


def test_the_issuer_pin(client, user, monkeypatch) -> None:
    iss = "https://project.supabase.co/auth/v1"
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", iss)
    get_settings.cache_clear()
    assert _get(client, _sign(_claims(iss=iss))).status_code == 200
    assert _get(client, _sign(_claims())).status_code == 401  # no iss
    assert _get(client, _sign(_claims(iss="https://evil.example/auth/v1"))).status_code == 401
    monkeypatch.delenv("SUPABASE_JWT_ISSUER")
    get_settings.cache_clear()
    assert _get(client, _sign(_claims())).status_code == 200  # unset: no check


def test_without_a_jwt_secret_user_routes_are_503_not_open(client, user, monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_JWT_SECRET")
    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "jwt_secret", None)
    assert _get(client, make_token(user)).status_code == 503
    assert client.get(URL).status_code == 401  # and without a token it is still a 401


def test_a_user_is_the_token_sub_and_not_a_claim_the_client_chose(client, user, db) -> None:
    """user_metadata and app_metadata are user-editable in Supabase; nothing in them is read."""
    other = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (other,))
    token = _sign(_claims(user_metadata={"sub": str(other), "user_id": str(other)}))
    assert client.put(
        URL, json={"radius_m": 700}, headers={"Authorization": f"Bearer {token}"}
    ).json()["user_id"] == str(user)
    assert (
        db.execute("SELECT count(*) FROM profiles WHERE user_id = %s", (other,)).fetchone()[0] == 0
    )


# --- no detail from the verifier leaks ----------------------------------------------------------


def test_refusals_carry_fixed_messages(client, user) -> None:
    cases = [
        _sign(_claims(), secret="another-secret-that-is-also-32-bytes-long"),
        _sign(_claims(aud="anon")),
        _sign(_claims(sub="x")),
        _forge({"alg": "none"}, _claims()),
        "garbage",
    ]
    for token in cases:
        r = _get(client, token)
        assert r.status_code == 401
        assert r.json() == {"detail": "invalid token"}, r.text
    assert not re.search(r"signature|audience|algorithm|decode", r.text, re.I)


# --- the anonymous-capable routes ---------------------------------------------------------------


def test_optional_auth_routes_reject_a_bad_token_but_accept_none(client, user) -> None:
    body = {"store_id": 1}
    # no token: anonymous report accepted by auth (the 422 is the unknown store, not a 401)
    assert client.post("/feedback/gap", json=body).status_code in (200, 422)
    # a token that does not verify is an error, not silently anonymous
    r = client.post("/feedback/gap", json=body, headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_events_treat_a_bad_token_as_anonymous_and_never_trust_a_body_user_id(
    client, user, db
) -> None:
    event = {"name": "split_viewed", "props": {}, "session_id": "session-sec-0001"}
    r = client.post(
        "/events", json={"events": [event]}, headers={"Authorization": "Bearer garbage"}
    )
    assert r.status_code == 200
    forged = {**event, "user_id": str(user)}
    assert client.post("/events", json={"events": [forged]}).status_code == 422  # extra field
    assert db.execute("SELECT count(*) FROM events WHERE user_id IS NOT NULL").fetchone()[0] == 0
    ok = client.post(
        "/events", json={"events": [event]}, headers={"Authorization": f"Bearer {make_token(user)}"}
    )
    assert ok.status_code == 200
    assert db.execute("SELECT user_id FROM events WHERE user_id IS NOT NULL").fetchone()[0] == user


# --- the route inventory ------------------------------------------------------------------------

PUBLIC = {
    ("GET", "/health"),
    ("GET", "/search"),
    ("POST", "/parse-list"),
    ("POST", "/parse-recipe"),
    ("POST", "/parse-image"),
    ("POST", "/compare"),
    ("POST", "/optimize"),
    ("POST", "/optimize/swaps"),
    ("POST", "/feedback/substitution"),  # optional token: records the user id when present
    ("POST", "/feedback/gap"),
    ("POST", "/events"),
    ("GET", "/stores/nearest"),
    ("GET", "/history/{canonical_id}"),
    ("GET", "/items/barcode/{barcode}"),
    ("GET", "/promo-cycles/{canonical_id}"),
    ("GET", "/chains/online"),
    ("GET", "/chains/clubs"),  # a static list of clubs per chain, nothing about a person
}


def _routes() -> list[tuple[str, str]]:
    """Every (method, path) of the API, from its OpenAPI document (the router objects of recent
    FastAPI are lazy, the document is the stable inventory)."""
    return [
        (method.upper(), path)
        for path, item in app.openapi()["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    ]


def _fill(path: str) -> str:
    return re.sub(r"\{[^}]+\}", lambda m: "1" if "id" in m.group(0) else "abc", path)


def test_the_public_list_matches_the_app() -> None:
    assert PUBLIC <= set(_routes()), "a route listed as public no longer exists"


def test_every_route_not_listed_as_public_requires_a_user(client) -> None:
    protected = [r for r in _routes() if r not in PUBLIC]
    assert len(protected) >= 20  # the /me tree, shares, beta, accept, push, delete
    for method, path in protected:
        for headers in ({}, {"Authorization": "Bearer garbage"}):
            r = client.request(method, _fill(path), headers=headers, json={})
            assert r.status_code == 401, (method, path, headers, r.status_code)
    assert any(p.startswith("/me") for _, p in protected)


def test_every_me_route_is_protected_whatever_the_public_list_says() -> None:
    for method, path in _routes():
        if path == "/me" or path.startswith("/me/"):
            assert (method, path) not in PUBLIC


def test_an_expired_token_is_refused_on_every_protected_route(client) -> None:
    expired = _sign(_claims(exp=int((datetime.now(UTC) - timedelta(hours=1)).timestamp())))
    for method, path in (r for r in _routes() if r not in PUBLIC):
        r = client.request(
            method, _fill(path), headers={"Authorization": f"Bearer {expired}"}, json={}
        )
        assert r.status_code == 401, (method, path)
