"""The extraction output contract (issue #25): strict JSON schema and validation."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from smartcart_catalog.extract.schema import (
    ATTRIBUTES_SCHEMA,
    OUTPUT_KEYS,
    SchemaError,
    schema_for,
    system_prompt,
    validate_output,
)
from smartcart_catalog.seed import load_catalog

ISSUE_FIELDS = {
    "category_path", "product_type", "brand", "is_private_label", "fat_pct", "state", "flavor",
    "kosher", "diet_flags", "pack_size", "unit",
}


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_schema_has_the_issue_fields_and_is_strict(catalog) -> None:
    for schema in (ATTRIBUTES_SCHEMA, schema_for(catalog)):
        assert set(schema["properties"]) == ISSUE_FIELDS | {"confidence"}
        assert schema["required"] == list(OUTPUT_KEYS)
        for node in _walk(schema):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
            # structured outputs do not support numerical or string-length constraints
            assert not {"minimum", "maximum", "minLength", "maxLength"} & set(node)


def test_closed_vocabularies_come_from_the_seed_files(catalog) -> None:
    schema = schema_for(catalog)
    types = schema["properties"]["product_type"]["anyOf"][0]["enum"]
    assert set(types) == set(catalog.rules)
    ids = schema["properties"]["category_path"]["anyOf"][0]["enum"]
    assert "dairy.milk.fresh" in ids and len(ids) == len(catalog.taxonomy)


def _good(**kw) -> dict:
    base = dict.fromkeys(OUTPUT_KEYS)
    base.update(diet_flags=[], confidence=0.9, product_type="milk", fat_pct=3, state="fresh")
    base.update(kw)
    return base


def test_valid_output_becomes_unverified_attributes(catalog) -> None:
    a = validate_output(json.dumps(_good(kosher='בד"ץ', diet_flags=["vegan"])), schema_for(catalog))
    assert a.product_type == "milk" and a.fat_pct == Decimal("3") and a.state == "fresh"
    assert a.kosher == 'בד"ץ' and a.diet_flags == ("vegan",)
    assert a.verified_keys == ()


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ("", "empty response"),
        ("   ", "empty response"),
        ('{"product_type": "mil', "not JSON"),
        (json.dumps({k: v for k, v in _good().items() if k != "confidence"}), "schema"),
        (json.dumps(_good(verified_keys=["kosher"])), "schema"),
        (json.dumps(_good(state="raw")), "schema"),
        (json.dumps(_good(product_type="milk_powder")), "schema"),
        (json.dumps(_good(fat_pct="3%")), "schema"),
        (json.dumps(_good(confidence=1.7)), "attributes: confidence"),
        (json.dumps([_good()]), "schema"),
    ],
)
def test_invalid_output_is_rejected(catalog, payload: str, reason: str) -> None:
    with pytest.raises(SchemaError, match=reason):
        validate_output(payload, schema_for(catalog))


def test_system_prompt_lists_vocabularies(catalog) -> None:
    prompt = system_prompt(catalog)
    assert "soy_drink |" in prompt and "almond_drink |" in prompt
    assert "dairy.milk.fresh | חלב טרי" in prompt
    assert "Never infer kashrut" in prompt
