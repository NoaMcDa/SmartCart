"""The project's public signing keys (JWKS) for verifying Supabase access tokens (R5).

Supabase projects can sign access tokens with an asymmetric key (ES256 or RS256) and publish the
public half at ``https://<project>.supabase.co/auth/v1/.well-known/jwks.json``. Verifying with it
removes the shared secret from the API host: whoever reads the API's environment can no longer mint
a token for any user.

This is a small client of our own instead of ``jwt.PyJWKClient``, for three reasons:

* ``PyJWKClient`` fetches again on *every* token whose ``kid`` it does not know, so a caller who
  sends random key ids turns each request into an outbound request. Here an unknown ``kid`` (and a
  key set past its TTL) refreshes at most once per ``min_refresh_s``, whatever the callers send.
* The algorithm is decided by the key, never by the token. A JWK declares ``alg`` (or, without it,
  its type decides: an EC P-256 key is ES256, an RSA key is RS256). The caller of ``get_key``
  verifies with exactly that algorithm, so a token cannot choose a weaker or different one, and a
  symmetric (``oct``) entry or one carrying private material is never loaded.
* A failed fetch keeps the keys already held (up to ``MAX_STALE_S`` past their TTL) instead of
  signing everybody out, and is reported as "keys unavailable" (a 503), not as a bad token.

The key set is fetched lazily, the first time an asymmetric token arrives: a project that still
signs with the shared secret never causes a request to the JWKS URL.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import jwt

log = logging.getLogger("smartcart_api.jwks")

# The only algorithms a key may declare. HS* never comes from a key set (algorithm confusion),
# and ``none`` is not an algorithm.
ASYMMETRIC_ALGORITHMS = frozenset({"ES256", "RS256"})
# A key set is a handful of keys; anything bigger is not one.
MAX_RESPONSE_BYTES = 64 * 1024
MAX_KEYS = 20
# How long past its TTL a key set may still be used when the refresh keeps failing. A key that
# Supabase has revoked stays trusted for at most this long during an outage of the endpoint.
MAX_STALE_S = 3600.0
FETCH_TIMEOUT_S = 3.0


class KeysUnavailable(Exception):
    """The key set could not be fetched and nothing usable is held (a 503, not a 401)."""


@dataclass(frozen=True)
class SigningKey:
    kid: str
    alg: str
    key: object  # a cryptography public key


def _declared_alg(jwk: dict) -> str | None:
    """The one algorithm this JWK may verify, or None if it is not a usable signing key."""
    kty = jwk.get("kty")
    declared = jwk.get("alg")
    if kty == "EC":
        derived = "ES256" if jwk.get("crv") == "P-256" else None
    elif kty == "RSA":
        derived = "RS256"
    else:  # "oct" (a shared secret), OKP, anything unknown
        return None
    if declared is not None and declared != derived:
        return None  # declares something the key type cannot do, or an algorithm we do not take
    return derived


def parse_key_set(document: object) -> dict[str, SigningKey]:
    """The usable signing keys of a JWKS document, by ``kid``. Entries that are not usable
    (no ``kid``, symmetric, private, ``use`` other than ``sig``, malformed) are skipped."""
    if not isinstance(document, dict) or not isinstance(document.get("keys"), list):
        raise ValueError("not a JWK set")
    keys: dict[str, SigningKey] = {}
    for jwk in document["keys"][:MAX_KEYS]:
        if not isinstance(jwk, dict):
            continue
        kid = jwk.get("kid")
        alg = _declared_alg(jwk)
        if not isinstance(kid, str) or not kid or alg is None:
            continue
        if jwk.get("use") not in (None, "sig") or "d" in jwk:
            continue
        try:
            key = jwt.PyJWK.from_dict(jwk, algorithm=alg).key
        except Exception:  # noqa: BLE001 - a malformed entry must not take the others down
            log.warning("skipping a JWKS entry that does not load (kid=%.40s)", kid)
            continue
        keys[kid] = SigningKey(kid=kid, alg=alg, key=key)
    return keys


def fetch_key_document(url: str, timeout: float = FETCH_TIMEOUT_S) -> object:
    """GET the document: no redirects, a size cap, a short timeout. The URL is operator
    configuration, not user input."""
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        with client.stream("GET", url, headers={"Accept": "application/json"}) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("JWKS response too large")
    return json.loads(bytes(body))


class JwksCache:
    def __init__(
        self,
        url: str,
        *,
        ttl_s: float = 600.0,
        min_refresh_s: float = 30.0,
        fetch: Callable[[str], object] = fetch_key_document,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.url = url
        self.ttl_s = ttl_s
        self.min_refresh_s = min_refresh_s
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self._keys: dict[str, SigningKey] = {}
        self._fetched_at: float | None = None  # last success
        self._attempted_at: float | None = None  # last try, success or not

    def get_key(self, kid: str) -> SigningKey | None:
        """The key for ``kid``; None when the (fresh) key set has no such key.

        Raises ``KeysUnavailable`` when the key set cannot be had at all."""
        with self._lock:
            now = self._clock()
            key = self._keys.get(kid)
            if key is not None and self._age(now) < self.ttl_s:
                return key
            # Past the TTL, or an unknown kid: refresh, but not more often than min_refresh_s.
            if self._attempted_at is None or now - self._attempted_at >= self.min_refresh_s:
                self._refresh(now)
                key = self._keys.get(kid)
            age = self._age(now)
            if age >= self.ttl_s + MAX_STALE_S:
                raise KeysUnavailable  # never fetched, or too old to trust
            if key is None and age >= self.ttl_s:
                raise KeysUnavailable  # the held set is stale and the refresh did not work
            return key  # None: the current key set has no such kid

    def _age(self, now: float) -> float:
        return float("inf") if self._fetched_at is None else now - self._fetched_at

    def _refresh(self, now: float) -> None:
        self._attempted_at = now
        try:
            keys = parse_key_set(self._fetch(self.url))
        except Exception as exc:  # noqa: BLE001 - any failure keeps what we hold
            log.warning("JWKS refresh failed: %s", type(exc).__name__)
            return
        # An empty set is a valid answer (a project that signs with the shared secret publishes
        # none): remember it, so the endpoint is not asked again for every token.
        self._keys = keys
        self._fetched_at = now

    def reset(self) -> None:
        with self._lock:
            self._keys = {}
            self._fetched_at = None
            self._attempted_at = None


_caches: dict[tuple[str, float, float], JwksCache] = {}
_caches_lock = threading.Lock()


def get_cache(url: str, ttl_s: float, min_refresh_s: float) -> JwksCache:
    """One cache per process and URL (and timing), shared by every request thread."""
    with _caches_lock:
        cache_key = (url, ttl_s, min_refresh_s)
        cache = _caches.get(cache_key)
        if cache is None:
            cache = _caches[cache_key] = JwksCache(url, ttl_s=ttl_s, min_refresh_s=min_refresh_s)
        return cache


def reset_caches() -> None:
    with _caches_lock:
        _caches.clear()
