"""Asymmetric Supabase tokens: ES256 and RS256 verified against the project's JWKS (R5).

A fake JWKS endpoint (a real HTTP server on 127.0.0.1) serves keys generated here, so the whole path
is exercised: the fetch, the cache, the algorithm taken from the key, the claim checks (the same as
for HS256: ``test_api_security_auth.py``), the refresh on an unknown ``kid`` and its rate limit, and
the attacks that asymmetric verification invites: ``alg: none``, an HS256 token "signed" with the
published public key, a header that names another algorithm than the key's, a key set that offers a
shared secret, and keys embedded in the token. The HS256 fallback (``SUPABASE_JWT_SECRET``) is
checked on and off.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
import pytest
from api_world import JWT_SECRET, make_token
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import HTTPException

from smartcart_api import jwks
from smartcart_api.auth import verify_token
from smartcart_api.jwks import JwksCache, KeysUnavailable, parse_key_set
from smartcart_api.settings import Settings, get_settings

UID = uuid.uuid4()
ISSUER = "https://abc.supabase.co/auth/v1"


# --- keys and tokens ----------------------------------------------------------------------------------


def _ec() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(scope="module")
def keys() -> dict:
    return {
        "ec1": _ec(),
        "ec2": _ec(),
        "rsa1": rsa.generate_private_key(public_exponent=65537, key_size=2048),
        "attacker": _ec(),
        "attacker_rsa": rsa.generate_private_key(public_exponent=65537, key_size=2048),
    }


def public_jwk(private_key, kid: str, **over) -> dict:
    public = private_key.public_key()
    algo = (
        jwt.algorithms.ECAlgorithm
        if isinstance(private_key, ec.EllipticCurvePrivateKey)
        else (jwt.algorithms.RSAAlgorithm)
    )
    jwk = algo.to_jwk(public, as_dict=True)
    jwk.update(
        {
            "kid": kid,
            "use": "sig",
            "alg": "ES256" if algo is jwt.algorithms.ECAlgorithm else "RS256",
        }
    )
    jwk.update(over)
    return {k: v for k, v in jwk.items() if v is not None}


def public_pem(private_key) -> bytes:
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def claims(**over) -> dict:
    now = int(time.time())
    base = {
        "sub": str(UID),
        "aud": "authenticated",
        "role": "authenticated",
        "iss": ISSUER,
        "iat": now,
        "exp": now + 3600,
    }
    base.update(over)
    return {k: v for k, v in base.items() if v is not None}


def sign(private_key, kid: str | None, alg: str | None = None, **over) -> str:
    if alg is None:
        alg = "ES256" if isinstance(private_key, ec.EllipticCurvePrivateKey) else "RS256"
    headers = {"kid": kid} if kid else {}
    return jwt.encode(claims(**over), private_key, algorithm=alg, headers=headers)


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def forge(header: dict, payload: dict, secret: bytes | None = None) -> str:
    """A token with any header, HMAC-SHA256-signed with ``secret`` (or left unsigned): what an
    attacker who knows only the public key can build."""
    signing_input = f"{b64(json.dumps(header).encode())}.{b64(json.dumps(payload).encode())}"
    sig = b64(hmac.new(secret, signing_input.encode(), hashlib.sha256).digest()) if secret else ""
    return f"{signing_input}.{sig}"


# --- a JWKS endpoint ----------------------------------------------------------------------------------


class FakeJwks:
    def __init__(self) -> None:
        self.keys: list[dict] = []
        self.body: bytes | None = None  # overrides the key set
        self.status = 200
        self.requests = 0
        self.lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                with outer.lock:
                    outer.requests += 1
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/auth/v1/.well-known/jwks.json")
                    self.end_headers()
                    return
                body = (
                    outer.body
                    if outer.body is not None
                    else json.dumps({"keys": outer.keys}).encode()
                )
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    @property
    def url(self) -> str:
        return f"{self.base}/auth/v1/.well-known/jwks.json"

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def endpoint():
    server = FakeJwks()
    yield server
    server.stop()


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, endpoint: FakeJwks, keys):
    """The API configured for asymmetric tokens: the JWKS URL, the shared secret off, the issuer
    pinned. ``endpoint.keys`` is what the project publishes."""
    for var in ("SUPABASE_URL", "SUPABASE_JWT_SECRET", "SUPABASE_JWT_ISSUER", "SUPABASE_JWKS_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SUPABASE_JWKS_URL", endpoint.url)
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", ISSUER)
    endpoint.keys = [public_jwk(keys["ec1"], "ec-1"), public_jwk(keys["rsa1"], "rsa-1")]
    jwks.reset_caches()
    get_settings.cache_clear()
    yield monkeypatch
    jwks.reset_caches()
    get_settings.cache_clear()


def verify(token: str):
    get_settings.cache_clear()
    return verify_token(token, get_settings())


def refused(token: str, status: int = 401, detail: str | None = "invalid token") -> HTTPException:
    with pytest.raises(HTTPException) as caught:
        verify(token)
    assert caught.value.status_code == status
    if detail is not None:
        assert caught.value.detail == detail
    return caught.value


# --- the happy paths ----------------------------------------------------------------------------------


def test_an_es256_token_verifies_against_the_published_key(env, keys, endpoint) -> None:
    user = verify(sign(keys["ec1"], "ec-1"))
    assert user.id == UID and user.claims["role"] == "authenticated"
    assert endpoint.requests == 1


def test_an_rs256_token_verifies_against_the_published_key(env, keys) -> None:
    assert verify(sign(keys["rsa1"], "rsa-1")).id == UID


def test_keys_are_cached_one_fetch_for_many_tokens(env, keys, endpoint) -> None:
    for _ in range(20):
        verify(sign(keys["ec1"], "ec-1"))
        verify(sign(keys["rsa1"], "rsa-1"))
    assert endpoint.requests == 1


def test_the_url_is_derived_from_the_project_url(env, keys, endpoint) -> None:
    env.delenv("SUPABASE_JWKS_URL")
    env.setenv("SUPABASE_URL", endpoint.base + "/")  # a trailing slash is fine
    assert get_settings().jwks_url == endpoint.url
    assert verify(sign(keys["ec1"], "ec-1")).id == UID
    env.setenv("SUPABASE_JWKS_URL", "https://keys.example/jwks.json")  # explicit wins
    get_settings.cache_clear()
    assert get_settings().jwks_url == "https://keys.example/jwks.json"
    env.delenv("SUPABASE_URL")
    env.delenv("SUPABASE_JWKS_URL")
    get_settings.cache_clear()
    assert get_settings().jwks_url is None


def test_a_project_that_signs_with_the_secret_never_asks_for_keys(env, endpoint) -> None:
    env.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    assert verify(make_token(UID, iss=ISSUER)).id == UID
    assert endpoint.requests == 0


def test_the_api_accepts_an_asymmetric_token_end_to_end(client, db, env, keys) -> None:
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (UID,))
    get_settings.cache_clear()
    r = client.get("/me/profile", headers={"Authorization": f"Bearer {sign(keys['ec1'], 'ec-1')}"})
    assert r.status_code == 200
    r = client.get(
        "/me/profile", headers={"Authorization": f"Bearer {sign(keys['attacker'], 'ec-1')}"}
    )
    assert r.status_code == 401 and r.json() == {"detail": "invalid token"}


# --- the claims are checked as for HS256 -----------------------------------------------------------------

SIGNERS = ["hs256", "es256", "rs256"]


def token_for(signer: str, keys, **over) -> str:
    if signer == "hs256":
        return jwt.encode(claims(**over), JWT_SECRET, algorithm="HS256")
    if signer == "es256":
        return sign(keys["ec1"], "ec-1", **over)
    return sign(keys["rsa1"], "rsa-1", **over)


@pytest.fixture
def both(env):
    env.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    get_settings.cache_clear()


@pytest.mark.parametrize("signer", SIGNERS)
def test_a_good_token_of_each_kind(both, keys, signer) -> None:
    assert verify(token_for(signer, keys)).id == UID


@pytest.mark.parametrize("signer", SIGNERS)
def test_expired_is_a_401_with_its_own_message(both, keys, signer) -> None:
    now = int(time.time())
    refused(token_for(signer, keys, exp=now - 3600), detail="token expired")
    # the clock skew tolerance is the same: 10 s past is fine, 60 s past is not
    assert verify(token_for(signer, keys, exp=now - 10)).id == UID
    refused(token_for(signer, keys, exp=now - 60), detail="token expired")


@pytest.mark.parametrize("signer", SIGNERS)
def test_wrong_audience_issuer_and_role(both, keys, signer) -> None:
    refused(token_for(signer, keys, aud="somebody-else"))
    refused(token_for(signer, keys, aud=None))
    refused(token_for(signer, keys, iss="https://evil.example/auth/v1"))
    refused(token_for(signer, keys, iss=None))  # the issuer is pinned: it must be there
    for role in ("anon", "service_role", "supabase_admin"):
        refused(token_for(signer, keys, role=role), detail="sign in required")
    assert verify(token_for(signer, keys, role=None)).id == UID  # no role claim: as for HS256


@pytest.mark.parametrize("signer", SIGNERS)
def test_sub_exp_and_nbf(both, keys, signer) -> None:
    refused(token_for(signer, keys, sub=None))
    refused(token_for(signer, keys, sub="not-a-uuid"))
    refused(token_for(signer, keys, sub=12345))
    refused(token_for(signer, keys, exp=None))
    now = int(time.time())
    assert verify(token_for(signer, keys, nbf=now + 10)).id == UID  # inside the skew
    refused(token_for(signer, keys, nbf=now + 120))


@pytest.mark.parametrize("signer", SIGNERS)
def test_the_issuer_pin_is_optional_for_both(both, env, keys, signer) -> None:
    env.delenv("SUPABASE_JWT_ISSUER")
    get_settings.cache_clear()
    assert verify(token_for(signer, keys, iss="anything")).id == UID


def test_a_tampered_asymmetric_token_is_refused(env, keys) -> None:
    token = sign(keys["ec1"], "ec-1")
    head, payload, sig = token.split(".")
    other = b64(json.dumps(claims(sub=str(uuid.uuid4()))).encode())
    refused(f"{head}.{other}.{sig}")
    refused(f"{head}.{payload}.{sig[:-4]}AAAA")
    refused(f"{head}.{payload}.")


def test_a_key_that_is_not_ours_signing_with_our_kid_is_refused(env, keys) -> None:
    refused(sign(keys["attacker"], "ec-1"))
    refused(sign(keys["attacker_rsa"], "rsa-1"))


def test_a_token_over_the_size_limit_is_refused_undecoded(env, keys, endpoint) -> None:
    refused(sign(keys["ec1"], "ec-1", pad="x" * 9000))
    assert endpoint.requests == 0


# --- attacks that asymmetric verification invites ---------------------------------------------------------


@pytest.mark.parametrize("shared_secret_on", [False, True])
def test_hs256_signed_with_the_public_key_is_refused(env, keys, shared_secret_on) -> None:
    """The classic algorithm confusion: the verifier is told HS256 and uses the (public) key it has
    as the HMAC secret. The published key is never an HMAC key here, whatever else is configured."""
    if shared_secret_on:
        env.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    jwk = public_jwk(keys["ec1"], "ec-1")
    material = [
        public_pem(keys["ec1"]),
        public_pem(keys["ec1"]).strip(),
        json.dumps(jwk).encode(),
        base64.urlsafe_b64decode(jwk["x"] + "=="),
        base64.urlsafe_b64decode(jwk["y"] + "=="),
        public_pem(keys["rsa1"]),
        base64.urlsafe_b64decode(public_jwk(keys["rsa1"], "rsa-1")["n"] + "=="),
    ]
    for kid in ("ec-1", "rsa-1", None):
        header = {"alg": "HS256", "typ": "JWT", **({"kid": kid} if kid else {})}
        for secret in material:
            refused(forge(header, claims(), secret))


def test_alg_none_is_refused_with_and_without_a_kid(env, keys) -> None:
    for header in ({"alg": "none"}, {"alg": "none", "kid": "ec-1"}, {"alg": "None", "kid": "ec-1"}):
        refused(forge(header, claims()))
        refused(forge(header, claims(), b"whatever"))
    env.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    refused(forge({"alg": "none"}, claims()))


@pytest.mark.parametrize(
    "alg",
    [
        "HS384",
        "HS512",
        "PS256",
        "ES384",
        "ES512",
        "RS384",
        "RS512",
        "EdDSA",
        "es256",
        "rs256",
        "",
        "HS256 ",
        "ES256,RS256",
        None,
    ],
)
def test_only_the_algorithms_the_key_declares_are_accepted(env, keys, alg) -> None:
    header = {"typ": "JWT", "kid": "ec-1"}
    if alg is not None:
        header["alg"] = alg
    refused(forge(header, claims(), b"x" * 32))
    # a real signature, on the right key, under a header that names a different algorithm
    token = sign(keys["ec1"], "ec-1")
    _, payload, sig = token.split(".")
    refused(f"{b64(json.dumps(header).encode())}.{payload}.{sig}")


def test_the_header_cannot_move_a_token_to_another_keys_algorithm(env, keys) -> None:
    # ES256 header naming the RSA key's kid, RS256 header naming the EC key's kid
    refused(sign(keys["ec1"], "rsa-1", alg="ES256"))
    refused(sign(keys["rsa1"], "ec-1", alg="RS256"))
    # a token that is a valid RS256 signature, relabelled ES256
    _, payload, sig = sign(keys["rsa1"], "rsa-1").split(".")
    refused(f"{b64(json.dumps({'alg': 'ES256', 'kid': 'rsa-1'}).encode())}.{payload}.{sig}")


def test_asymmetric_tokens_need_a_kid(env, keys) -> None:
    refused(sign(keys["ec1"], None))
    refused(sign(keys["ec1"], ""))
    refused(forge({"alg": "ES256", "kid": 7}, claims(), b"x"))
    refused(forge({"alg": "ES256", "kid": ["ec-1"]}, claims(), b"x"))


def test_keys_or_urls_carried_by_the_token_are_ignored(env, keys) -> None:
    """``jwk`` (a key inside the token) and ``jku`` (where to fetch the keys) are never followed."""
    mine = public_jwk(keys["attacker"], "attacker")
    token = jwt.encode(
        claims(),
        keys["attacker"],
        algorithm="ES256",
        headers={"kid": "attacker", "jwk": mine, "jku": "http://127.0.0.1:1/evil"},
    )
    refused(token)
    token = jwt.encode(
        claims(),
        keys["attacker"],
        algorithm="ES256",
        headers={"kid": "ec-1", "jwk": mine, "x5u": "http://127.0.0.1:1/evil", "x5c": ["AAAA"]},
    )
    refused(token)


def test_a_shared_secret_published_in_the_key_set_is_not_used(env, endpoint, keys) -> None:
    secret = b"a-secret-that-the-key-set-offers-as-oct-key"
    endpoint.keys = [
        {"kty": "oct", "kid": "oct-1", "alg": "HS256", "k": b64(secret), "use": "sig"},
        public_jwk(keys["ec1"], "ec-1"),
    ]
    header = {"alg": "HS256", "typ": "JWT", "kid": "oct-1"}
    refused(forge(header, claims(), secret))
    refused(forge({**header, "alg": "ES256"}, claims(), secret))
    assert verify(sign(keys["ec1"], "ec-1")).id == UID  # the rest of the set still works


def test_entries_that_are_not_usable_signing_keys_are_skipped(env, endpoint, keys) -> None:
    ec_jwk = public_jwk(keys["ec1"], "x")
    rsa_jwk = public_jwk(keys["rsa1"], "x")
    private_ec = jwt.algorithms.ECAlgorithm.to_jwk(keys["ec2"], as_dict=True)  # carries "d"
    endpoint.keys = [
        {**private_ec, "kid": "private", "alg": "ES256", "use": "sig"},
        {**ec_jwk, "kid": "enc-only", "use": "enc"},
        {**ec_jwk, "kid": "ec-says-rs", "alg": "RS256"},
        {**rsa_jwk, "kid": "rsa-says-es", "alg": "ES256"},
        {**ec_jwk, "kid": "ec-says-hs", "alg": "HS256"},
        {**ec_jwk, "kid": "wrong-curve", "crv": "P-384"},
        {**ec_jwk, "kid": ""},
        {"kty": "EC", "kid": "broken", "crv": "P-256", "x": "AAAA", "y": "AAAA"},
        {"kty": "OKP", "kid": "ed", "crv": "Ed25519", "x": "AAAA"},
        "not-an-object",
        {**ec_jwk, "kid": "good"},
    ]
    parsed = parse_key_set({"keys": endpoint.keys})
    assert set(parsed) == {"good"}
    refused(sign(keys["ec2"], "private"))
    assert verify(sign(keys["ec1"], "good")).id == UID


def test_a_key_without_alg_gets_the_one_its_type_allows(env, endpoint, keys) -> None:
    endpoint.keys = [
        public_jwk(keys["ec1"], "ec-1", alg=None),
        public_jwk(keys["rsa1"], "rsa-1", alg=None),
    ]
    assert verify(sign(keys["ec1"], "ec-1")).id == UID
    assert verify(sign(keys["rsa1"], "rsa-1")).id == UID
    refused(sign(keys["rsa1"], "rsa-1", alg="PS256"))  # an RSA key is RS256 only here


# --- the HS256 fallback, on and off ------------------------------------------------------------------------


def test_the_fallback_on_hs256_tokens_still_verify_beside_asymmetric_ones(env, keys) -> None:
    env.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    assert verify(jwt.encode(claims(), JWT_SECRET, algorithm="HS256")).id == UID
    assert verify(sign(keys["ec1"], "ec-1")).id == UID
    refused(jwt.encode(claims(), "the-wrong-secret-of-at-least-32-bytes", algorithm="HS256"))


def test_the_fallback_off_hs256_is_refused_even_with_the_right_secret(env, keys, endpoint) -> None:
    # no SUPABASE_JWT_SECRET: the API cannot verify HS256, and says it is invalid (not "not configured")
    err = refused(jwt.encode(claims(), JWT_SECRET, algorithm="HS256"))
    assert err.status_code == 401
    assert verify(sign(keys["ec1"], "ec-1")).id == UID
    assert endpoint.requests == 1


def test_nothing_configured_is_a_503_as_before(monkeypatch) -> None:
    for var in ("SUPABASE_URL", "SUPABASE_JWT_SECRET", "SUPABASE_JWKS_URL"):
        monkeypatch.delenv(var, raising=False)
    jwks.reset_caches()
    refused(make_token(UID), status=503, detail="SUPABASE_JWT_SECRET is not configured")
    get_settings.cache_clear()


def test_the_secret_alone_is_the_previous_behaviour(monkeypatch, keys) -> None:
    for var in ("SUPABASE_URL", "SUPABASE_JWKS_URL", "SUPABASE_JWT_ISSUER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    jwks.reset_caches()
    assert verify(make_token(UID)).id == UID
    refused(sign(keys["ec1"], "ec-1"))  # no JWKS configured: an asymmetric token is simply invalid
    get_settings.cache_clear()


# --- unknown kid, refresh, rate limit --------------------------------------------------------------------------


def test_a_rotated_in_key_is_picked_up_on_its_first_token(env, keys, endpoint) -> None:
    env.setenv("SUPABASE_JWKS_MIN_REFRESH_S", "0")
    assert verify(sign(keys["ec1"], "ec-1")).id == UID
    assert endpoint.requests == 1
    endpoint.keys = [public_jwk(keys["ec1"], "ec-1"), public_jwk(keys["ec2"], "ec-2")]
    assert verify(sign(keys["ec2"], "ec-2")).id == UID  # unknown kid: refreshed
    assert endpoint.requests == 2
    assert verify(sign(keys["ec1"], "ec-1")).id == UID  # the old key still works
    assert endpoint.requests == 2


def test_random_kids_cannot_make_the_api_fetch_over_and_over(env, keys, endpoint) -> None:
    verify(sign(keys["ec1"], "ec-1"))
    assert endpoint.requests == 1
    for n in range(50):
        refused(sign(keys["attacker"], f"guess-{n}"))
    assert endpoint.requests == 1  # the default 30 s between fetches holds
    # and a good token still works while the unknown ones are being refused
    assert verify(sign(keys["ec1"], "ec-1")).id == UID


def test_an_unknown_kid_after_a_successful_fetch_is_a_401_not_a_503(env, keys) -> None:
    env.setenv("SUPABASE_JWKS_MIN_REFRESH_S", "0")
    refused(sign(keys["ec2"], "never-published"))


def test_first_requests_in_parallel_fetch_once(env, keys, endpoint) -> None:
    results: list[object] = []

    def work() -> None:
        results.append(verify_token(sign(keys["ec1"], "ec-1"), get_settings()).id)

    get_settings.cache_clear()
    get_settings()
    threads = [threading.Thread(target=work) for _ in range(16)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results == [UID] * 16 and endpoint.requests == 1


# --- the endpoint is unavailable ------------------------------------------------------------------------------


def test_an_unreachable_or_broken_endpoint_is_a_503_not_a_bad_token(env, keys, endpoint) -> None:
    endpoint.status = 500
    err = refused(sign(keys["ec1"], "ec-1"), status=503, detail="signing keys are unavailable")
    assert err.headers["Retry-After"] == "5"
    for body in (b"not json", b'{"keys": "nope"}', b"[]", b"x" * (jwks.MAX_RESPONSE_BYTES + 1)):
        jwks.reset_caches()
        endpoint.status, endpoint.body = 200, body
        refused(sign(keys["ec1"], "ec-1"), status=503, detail="signing keys are unavailable")


def test_the_endpoint_is_not_followed_through_a_redirect(env, keys, endpoint) -> None:
    env.setenv("SUPABASE_JWKS_URL", endpoint.base + "/redirect")
    refused(sign(keys["ec1"], "ec-1"), status=503, detail="signing keys are unavailable")


def test_nothing_is_listening(env, keys) -> None:
    env.setenv("SUPABASE_JWKS_URL", "http://127.0.0.1:1/jwks.json")
    refused(sign(keys["ec1"], "ec-1"), status=503, detail="signing keys are unavailable")


def test_the_503_reaches_the_caller_through_the_api(client, db, env, keys, endpoint) -> None:
    endpoint.status = 500
    get_settings.cache_clear()
    r = client.get("/me/profile", headers={"Authorization": f"Bearer {sign(keys['ec1'], 'ec-1')}"})
    assert r.status_code == 503 and r.headers["retry-after"] == "5"
    assert "127.0.0.1" not in r.text  # the URL is not echoed


# --- the cache on a controlled clock ---------------------------------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def cache_with(documents: list, clock: Clock, **kw) -> tuple[JwksCache, list[int]]:
    """A cache whose fetch returns documents[i] (an Exception is raised) and counts its calls."""
    calls: list[int] = []

    def fetch(_url: str):
        calls.append(1)
        doc = documents[min(len(calls) - 1, len(documents) - 1)]
        if isinstance(doc, Exception):
            raise doc
        return doc

    return JwksCache(
        "http://keys", ttl_s=600, min_refresh_s=30, fetch=fetch, clock=clock, **kw
    ), calls


@pytest.fixture
def docs(keys):
    return {
        "one": {"keys": [public_jwk(keys["ec1"], "a")]},
        "two": {"keys": [public_jwk(keys["ec1"], "a"), public_jwk(keys["ec2"], "b")]},
        "empty": {"keys": []},
    }


def test_the_ttl_refreshes_and_an_unknown_kid_is_rate_limited(docs) -> None:
    clock = Clock()
    cache, calls = cache_with([docs["one"], docs["two"]], clock)
    assert cache.get_key("a").alg == "ES256" and len(calls) == 1
    clock.now += 5
    assert cache.get_key("b") is None and len(calls) == 1  # unknown, but fetched 5 s ago
    clock.now += 30
    assert cache.get_key("b").kid == "b" and len(calls) == 2  # now allowed, and it is there
    clock.now += 599
    assert cache.get_key("a") and len(calls) == 2  # within the TTL of the second fetch
    clock.now += 2
    assert cache.get_key("a") and len(calls) == 3  # past the TTL: refreshed


def test_a_failed_refresh_keeps_serving_the_keys_it_has(docs) -> None:
    clock = Clock()
    cache, calls = cache_with([docs["one"], OSError("down")], clock)
    assert cache.get_key("a")
    clock.now += 601  # past the TTL, the refresh fails
    assert cache.get_key("a") is not None and len(calls) == 2
    clock.now += 10  # a failed attempt is not retried at once either
    assert cache.get_key("a") is not None and len(calls) == 2
    clock.now += 30
    assert cache.get_key("a") is not None and len(calls) == 3
    # but not forever: past the stale limit the keys are no longer trusted
    clock.now += jwks.MAX_STALE_S
    with pytest.raises(KeysUnavailable):
        cache.get_key("a")
    # and an unknown kid while stale and failing is "unavailable", not "invalid"
    clock2 = Clock()
    cache2, _ = cache_with([docs["one"], OSError("down")], clock2)
    cache2.get_key("a")
    clock2.now += 601
    with pytest.raises(KeysUnavailable):
        cache2.get_key("zzz")


def test_the_first_fetch_failing_is_unavailable_and_retried_after_the_interval(docs) -> None:
    clock = Clock()
    cache, calls = cache_with([OSError("down"), docs["one"]], clock)
    with pytest.raises(KeysUnavailable):
        cache.get_key("a")
    with pytest.raises(KeysUnavailable):
        cache.get_key("a")
    assert len(calls) == 1
    clock.now += 31
    assert cache.get_key("a") is not None and len(calls) == 2


def test_an_empty_key_set_is_remembered_not_refetched_per_token(docs) -> None:
    clock = Clock()
    cache, calls = cache_with([docs["empty"]], clock)
    for _ in range(10):
        assert cache.get_key("a") is None
    assert len(calls) == 1


def test_a_key_that_disappears_from_the_set_stops_working_at_the_next_refresh(docs) -> None:
    clock = Clock()
    cache, calls = cache_with([docs["two"], docs["one"]], clock)
    assert cache.get_key("b")
    clock.now += 601
    assert cache.get_key("b") is None  # revoked: the refresh dropped it
    assert cache.get_key("a")


# --- settings -----------------------------------------------------------------------------------------------------


def test_the_settings_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.jwks_ttl_s == 600 and s.jwks_min_refresh_s == 30
    assert s.jwks_url is None
    assert Settings(SUPABASE_URL="https://p.supabase.co", _env_file=None).jwks_url == (
        "https://p.supabase.co/auth/v1/.well-known/jwks.json"
    )
    assert Settings(
        SUPABASE_URL="https://p.supabase.co", SUPABASE_JWKS_URL="  ", _env_file=None
    ).jwks_url == ("https://p.supabase.co/auth/v1/.well-known/jwks.json")
    with pytest.raises(ValueError):
        Settings(SUPABASE_JWKS_TTL_S=0, _env_file=None)
