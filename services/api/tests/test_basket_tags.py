"""The pack-size unit is folded into the pack_size tag, never shown as a tag of its own."""

from __future__ import annotations

from smartcart_api.basket import _tags


def _by_key(tags):
    return {t.key: (t.value, t.status) for t in tags}


def test_unit_folds_into_pack_size() -> None:
    tags = _by_key(_tags(
        {"pack_size": 1000, "unit": "g", "product_type": "קמח"}, [],
        {"product_type": "קמח"}, {"pack_size": 1000, "unit": "g"}, ["product_type", "pack_size", "unit"],
    ))  # fmt: skip
    assert "unit" not in tags
    assert tags["pack_size"] == ("1000 g", "matched")


def test_unit_mismatch_counts_against_pack_size() -> None:
    tags = _by_key(_tags(
        {"pack_size": 1000, "unit": "ml"}, [], {}, {"pack_size": 1000, "unit": "g"}, ["pack_size", "unit"],
    ))  # fmt: skip
    assert tags == {"pack_size": ("1000 ml", "differs")}


def test_unit_without_pack_size_stays_a_tag() -> None:
    tags = _by_key(_tags({"unit": "g"}, [], {}, {"unit": "g"}, ["unit"]))
    assert tags == {"unit": ("g", "matched")}
