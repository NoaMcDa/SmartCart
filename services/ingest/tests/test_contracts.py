"""Smoke tests for the shared contracts. Workstreams add their own test modules."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from smartcart_ingest.adapters import REGISTRY, ChainAdapter, get_adapter, register
from smartcart_ingest.models import ParsedFile, PriceRecord, RawFile


def _raw() -> RawFile:
    return RawFile(
        chain_id="test",
        store_code="001",
        kind="price_full",
        published_at=datetime(2026, 10, 6, 6, 0, tzinfo=UTC),
        sha256="a" * 64,
        path="raw/test/001/PriceFull.gz",
        schema_version="v1",
    )


def test_models_are_frozen() -> None:
    raw = _raw()
    with pytest.raises(ValidationError):
        raw.chain_id = "other"  # type: ignore[misc]


def test_parsed_file_defaults_empty() -> None:
    pf = ParsedFile(raw=_raw())
    assert pf.stores == [] and pf.items == [] and pf.prices == [] and pf.promos == []


def test_price_record_uses_decimal() -> None:
    p = PriceRecord(
        chain_id="test",
        store_code="001",
        item_code="123",
        price=Decimal("6.90"),
        observed_at=datetime(2026, 10, 6, tzinfo=UTC),
    )
    assert p.price == Decimal("6.90")


def test_registry_round_trip() -> None:
    @register
    class _Fake(ChainAdapter):
        chain_id = "fake-test"
        display_name = "Fake"
        portal = "other"

        def detect_kind(self, filename: str):
            return "price_full"

        def detect_schema(self, xml_root):
            return "v1"

        def parse(self, raw, data):
            return ParsedFile(raw=raw)

    try:
        assert isinstance(get_adapter("fake-test"), _Fake)
        with pytest.raises(KeyError):
            get_adapter("nope")
    finally:
        REGISTRY.pop("fake-test", None)


def test_registry_aliases() -> None:
    @register
    class _Twin(ChainAdapter):
        chain_id = "twin-main"
        display_name = "Twin"
        portal = "other"
        aliases = ("twin-alt",)

        def detect_kind(self, filename: str):
            return "price_full"

        def detect_schema(self, xml_root):
            return "v1"

        def parse(self, raw, data):
            return ParsedFile(raw=raw)

    try:
        assert type(get_adapter("twin-alt")) is type(get_adapter("twin-main"))
    finally:
        REGISTRY.pop("twin-main", None)
        REGISTRY.pop("twin-alt", None)
