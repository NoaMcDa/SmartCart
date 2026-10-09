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

import json
import os
from dataclasses import dataclass
from typing import Protocol

import structlog

log = structlog.get_logger("smartcart_api.push")

GONE = frozenset({404, 410})


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
