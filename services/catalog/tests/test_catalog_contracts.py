from decimal import Decimal

import pytest
from pydantic import ValidationError

from smartcart_catalog.models import (
    ALWAYS_UNVERIFIED,
    Attributes,
    Candidate,
    MatchDecision,
    NormalizedItem,
)


def test_attributes_frozen_and_typed() -> None:
    a = Attributes(product_type="milk", fat_pct=Decimal("3"), state="fresh")
    with pytest.raises(ValidationError):
        a.brand = "x"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        Attributes(state="raw")  # type: ignore[arg-type]
    assert a.value("fat_pct") == Decimal("3")


def test_always_unverified_keys() -> None:
    assert {"kosher", "diet_flags"} == set(ALWAYS_UNVERIFIED)


def test_match_decision_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        MatchDecision(
            item_id=1, canonical_id=1, flex_level="any_brand", confidence=1.5,
            source="rule", needs_review=False,
        )
    d = MatchDecision(
        item_id=1, canonical_id=None, flex_level=None, confidence=0, source="rule",
        needs_review=False, reason="no candidates",
    )
    assert d.canonical_id is None


def test_models_construct() -> None:
    NormalizedItem(item_id=1, clean_name="חלב 3% 1 ליטר", quantity=Decimal(1), unit="l")
    Candidate(canonical_id=2, similarity=0.9)
