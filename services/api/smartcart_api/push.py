"""Web push delivery for price alerts (issue #23), with VAPID (RFC 8292) through ``pywebpush``.

| Variable | Meaning |
|---|---|
| ``VAPID_PRIVATE_KEY`` | the application server's private key (base64url raw key, or PEM, or a path to a PEM file) |
| ``VAPID_PUBLIC_KEY`` | the matching public key; the PWA passes it as ``applicationServerKey`` when it subscribes |
| ``VAPID_SUBJECT`` | contact for the push service, ``mailto:...`` or an ``https:`` URL |

Generate a key pair once (``uv run vapid --gen`` from py-vapid, then ``vapid --applicationServerKey``)
and keep the private key in the deployment's secrets, never in the repository. Without the three
variables ``WebPushSender.from_env()`` returns None and the alerts job records deliveries with
channel ``log`` instead of sending.

A sender is any callable ``(PushTarget, payload dict) -> HTTP status``; tests pass a fake one.
404 and 410 mean the subscription is gone (the user revoked permission or uninstalled): the job
deletes it.
"""

from __future__ import annotations

import ipaddress
import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import structlog

log = structlog.get_logger("smartcart_api.push")

GONE = frozenset({404, 410})


def validate_endpoint(url: str) -> str:
    """Refuse a push endpoint the server should never POST to (SSRF), at registration.

    The endpoint is a URL the browser's push service issued, but the person registering it types
    whatever they like, and the alerts job later POSTs to it from inside our network. So: https
    only, on the default port, no credentials, a DNS name (not an address literal), and not a name
    that is local by construction. When ``API_PUSH_ENDPOINT_HOSTS`` is set (comma separated host
    suffixes, e.g. ``fcm.googleapis.com,.push.services.mozilla.com,.notify.windows.com,
    .push.apple.com``) the host must also match one of them. The address the name resolves to is
    checked again right before every send (``WebPushSender``)."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme != "https" or not host:
        raise ValueError("a push endpoint is an https URL")
    if parts.username or parts.password:
        raise ValueError("a push endpoint carries no credentials")
    try:
        port = parts.port
    except ValueError:
        raise ValueError("invalid port") from None
    if port not in (None, 443):
        raise ValueError("a push endpoint uses the default https port")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("a push endpoint is a host name, not an address")
    if "." not in host or host.endswith((".local", ".localhost", ".internal", ".lan", ".home")):
        raise ValueError("a push endpoint is a public host name")
    allowed = [h.strip().lower() for h in os.environ.get("API_PUSH_ENDPOINT_HOSTS", "").split(",")]
    allowed = [h for h in allowed if h]
    if allowed and not any(
        host == h.lstrip(".") or host.endswith("." + h.lstrip(".")) for h in allowed
    ):
        raise ValueError("this push service is not accepted")
    return url


def deliverable(endpoint: str) -> bool | None:
    """True when ``endpoint`` resolves to public addresses only; False when it does not; None when
    the name does not resolve right now (try again on the next run)."""
    from smartcart_api.recipe_fetch import _resolve, public_address

    host = urlsplit(endpoint).hostname or ""
    try:
        addrs = _resolve(host)
    except OSError:
        return None
    return bool(addrs) and all(public_address(a) for a in addrs)


@dataclass(frozen=True)
class PushTarget:
    id: int
    endpoint: str
    p256dh: str
    auth: str


class PushSender(Protocol):
    def __call__(self, target: PushTarget, payload: dict) -> int: ...


class WebPushSender:
    """Sends one encrypted web push message per call; returns the push service's HTTP status."""

    def __init__(
        self, private_key: str, public_key: str, subject: str, ttl: int = 24 * 3600
    ) -> None:
        self.private_key = private_key
        self.public_key = public_key
        self.subject = subject
        self.ttl = ttl

    @classmethod
    def from_env(cls) -> WebPushSender | None:
        private = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
        public = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
        subject = os.environ.get("VAPID_SUBJECT", "").strip()
        if not (private and public and subject):
            return None
        return cls(private, public, subject)

    def __call__(self, target: PushTarget, payload: dict) -> int:
        from pywebpush import WebPushException, webpush
        from requests import RequestException

        ok = deliverable(target.endpoint)
        if ok is None:  # the name does not resolve now: try again on the next run
            return 0
        if not ok:  # registered before the check existed, or the name moved: drop it
            log.warning(
                "push endpoint is not public, subscription dropped", subscription_id=target.id
            )
            return 410
        try:
            resp = webpush(
                subscription_info={
                    "endpoint": target.endpoint,
                    "keys": {"p256dh": target.p256dh, "auth": target.auth},
                },
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=self.private_key,
                vapid_claims={"sub": self.subject},  # pywebpush adds aud and exp
                ttl=self.ttl,
                timeout=10,
            )
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else 0
            log.warning("push failed", status=status, subscription_id=target.id)
            return status
        except RequestException as exc:  # network: try again on the next run
            log.warning(
                "push service unreachable", error=type(exc).__name__, subscription_id=target.id
            )
            return 0
        return int(getattr(resp, "status_code", 201))
