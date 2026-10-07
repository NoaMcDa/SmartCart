"""Promo parse confidence recorded by every chain adapter in ``promos.raw`` (issues #12, #102).

The rubric is in docs/adapters.md ("Promo parse confidence") and in
``adapters._common.promo_parse_confidence``.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import pytest

from smartcart_ingest.adapters._common import (
    PROMO_CONFIDENCE_UNPARSED,
    RegulationAdapter,
    promo_parse_confidence,
)
from tests.test_adapters import chain_adapters, chain_dirs, parse_fixture

D = Decimal
END = datetime(2026, 10, 14, 23, 59)


def _promo_fixtures() -> list[tuple[str, str]]:
    out = []
    for folder in chain_dirs():
        expected = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
        for name, exp in expected["files"].items():
            if exp["kind"] in ("promo", "promo_full") and "error" not in exp:
                out.append((folder.name, name))
    return out


PROMO_FIXTURES = _promo_fixtures()


def test_every_chain_has_a_promo_fixture() -> None:
    assert {slug for slug, _ in PROMO_FIXTURES} == set(chain_adapters())


@pytest.mark.parametrize(("slug", "name"), PROMO_FIXTURES)
def test_every_adapter_records_a_confidence_on_every_promo(slug: str, name: str) -> None:
    cls: type[RegulationAdapter] = chain_adapters()[slug]
    folder = next(f for f in chain_dirs() if f.name == slug)
    parsed = parse_fixture(cls(), folder / name)
    for promo in parsed.promos:
        conf = promo.raw["confidence"]
        assert isinstance(conf, float) and 0 <= conf <= 1, (name, promo.promo_id, conf)
        assert isinstance(promo.raw["confidence_reasons"], list)
        if promo.reward_type == "other":
            assert conf == PROMO_CONFIDENCE_UNPARSED
        else:
            assert conf > PROMO_CONFIDENCE_UNPARSED
        if not promo.raw["confidence_reasons"]:
            assert conf == 1.0
        # The raw column is JSON: the value must survive a round trip.
        assert json.loads(json.dumps(promo.raw))["confidence"] == conf


def test_the_standard_synthetic_promos_are_fully_explicit() -> None:
    cls = chain_adapters()["shufersal"]
    folder = next(f for f in chain_dirs() if f.name == "shufersal")
    parsed = parse_fixture(cls(), folder / "PromoFull7290027600007-001-202610060300.gz")
    got = {p.promo_id: (p.reward_type, p.raw["confidence"]) for p in parsed.promos}
    assert got == {
        "1001": ("bundle", 1.0),
        "1002": ("buy_x_get_y", 1.0),
        "1003": ("percent", 1.0),
        "1004": ("price", 1.0),
    }


@pytest.mark.parametrize(
    ("reward_type", "min_qty", "gift_count", "description", "ends_at", "want", "reasons"),
    [
        ("price", D(1), None, "חלב ב-5.90", END, 1.0, []),
        ("bundle", D(3), None, "3 ב-20", END, 1.0, []),
        ("percent", D(1), None, "20% הנחה", END, 1.0, []),
        ("buy_x_get_y", D(2), D(1), "קוטג' 1+1", END, 1.0, []),
        ("price", None, None, "חלב ב-5.90", END, 0.8, ["min_qty_missing"]),
        ("buy_x_get_y", D(1), None, "1+1", END, 0.8, ["gift_count_inferred"]),
        ("buy_x_get_y", None, D(0), "1+1", END, 0.6, ["min_qty_missing", "gift_count_inferred"]),
        ("price", D(1), None, "מבצע", None, 0.9, ["end_date_missing"]),
        ("price", D(1), None, "20% הנחה", END, 0.7, ["description_disagrees"]),
        ("percent", D(1), None, "1+1 על כל המדף", END, 0.7, ["description_disagrees"]),
        ("bundle", D(2), None, "2 ב-10, השני ב-50 %", END, 0.7, ["description_disagrees"]),
        (
            "buy_x_get_y",
            None,
            None,
            "50% על השני",
            None,
            0.2,
            ["min_qty_missing", "gift_count_inferred", "end_date_missing", "description_disagrees"],
        ),  # fmt: skip
        ("other", D(1), None, "מבצע", END, PROMO_CONFIDENCE_UNPARSED, ["reward_unparsed"]),
    ],
)
def test_confidence_rubric(reward_type, min_qty, gift_count, description, ends_at, want, reasons):
    got = promo_parse_confidence(
        reward_type,
        min_qty=min_qty,
        gift_count=gift_count,
        description=description,
        ends_at=ends_at,
    )
    assert got == (want, reasons)
