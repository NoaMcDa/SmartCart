"""Shared pieces of the extractors (issue #25).

An extractor turns ``NormalizedItem`` rows into ``Attributes`` (or ``ExtractionError``), one
output per input, in input order (the ``Extractor`` protocol in models.py). The chain, the
manufacturer, the barcode and the raw name, which the private-label check and the model prompt
need, travel on the ``NormalizedItem`` itself (issue #92): ``normalize`` copies them from the
``items`` row.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from smartcart_catalog.models import Attributes, ExtractionError

HUMAN = "human"

Result = Attributes | ExtractionError


def trusted_verified_keys(keys: Iterable[str], source: str) -> list[str]:
    """Keys that may be stored as verified. Only a human verifies. Rule or model output is never
    verified, whatever it claims, and kosher and diet flags (``ALWAYS_UNVERIFIED``) in
    particular stay unverified unless the source is a human."""
    if source != HUMAN:
        return []
    return sorted(set(keys))


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def attrs_json(attrs: Attributes) -> str:
    """The ``item_attributes.attrs`` document: set values only, numbers as JSON numbers.
    ``verified_keys`` and ``confidence`` have their own columns."""
    data = attrs.model_dump(exclude={"verified_keys", "confidence"})
    data = {k: v for k, v in data.items() if v is not None and v != ()}
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=_json_default)


def unverified_keys(attrs: Attributes) -> list[str]:
    """Keys with a value that no human confirmed; the UI labels these "unverified"."""
    data = attrs.model_dump(exclude={"verified_keys", "confidence"})
    set_keys = {k for k, v in data.items() if v is not None and v != ()}
    return sorted(set_keys - set(attrs.verified_keys))
