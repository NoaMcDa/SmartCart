"""OCR settings from the environment, read per call so tests and deploys can change them.

| Variable | Default | Meaning |
|---|---|---|
| ``OCR_PROVIDER`` | ``auto`` | ``auto`` (claude if a key is set, else tesseract if installed), ``fake``, ``tesseract``, ``claude`` |
| ``OCR_MONTHLY_IMAGE_CAP`` | 2000 | images per calendar month (UTC) across providers; over it, 429 |
| ``OCR_MONTHLY_USD_CAP`` | 20 | estimated dollars per month; over it, 429 |
| ``OCR_CLAUDE_MODEL`` | ``claude-sonnet-5-5`` | model for the vision provider |
| ``ANTHROPIC_API_KEY`` | none | enables the Claude provider (read by the anthropic SDK) |
"""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation

DEFAULT_IMAGE_CAP = 2000
DEFAULT_USD_CAP = Decimal(20)
DEFAULT_CLAUDE_MODEL = "claude-sonnet-5-5"


def provider_name() -> str:
    return (os.environ.get("OCR_PROVIDER") or "auto").strip().lower()


def image_cap() -> int:
    try:
        return max(0, int(os.environ.get("OCR_MONTHLY_IMAGE_CAP", DEFAULT_IMAGE_CAP)))
    except ValueError:
        return DEFAULT_IMAGE_CAP


def usd_cap() -> Decimal:
    try:
        return max(Decimal(0), Decimal(os.environ.get("OCR_MONTHLY_USD_CAP", str(DEFAULT_USD_CAP))))
    except InvalidOperation:
        return DEFAULT_USD_CAP


def claude_model() -> str:
    return os.environ.get("OCR_CLAUDE_MODEL") or DEFAULT_CLAUDE_MODEL


def anthropic_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY") or None
