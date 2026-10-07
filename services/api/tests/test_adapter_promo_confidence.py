"""Promo parse confidence end to end (issues #12, #102): a synthetic chain fixture goes through
the real adapter and loader, the nightly precompute picks the promo, and /compare reports the
adapter's ``promos.raw['confidence']`` as ``promo_confidence`` instead of null."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from api_world import World

from smartcart_api.precompute import precompute_effective_prices
from smartcart_ingest import loader, tracking
from smartcart_ingest.adapters import get_adapter

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]

SHUFERSAL = "7290027600007"
FIXTURES = Path(__file__).resolve().parents[2] / "ingest" / "tests" / "fixtures" / "shufersal"
FILES = (
    "Stores7290027600007-000-202610060201.gz",
    "PriceFull7290027600007-001-202610060300.gz",
    "PromoFull7290027600007-001-202610060300.gz",
)
AS_OF = datetime(2026, 10, 6, 10, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
MILK_BARCODE = "7290004131074"  # promo 1004: "חלב ב-5.90", every field explicit


def _load_fixture(db) -> None:
    db.execute("SELECT ensure_price_partitions('2026-09-01', '2026-11-01')")
    adapter = get_adapter(SHUFERSAL)
    for name in FILES:
        data = (FIXTURES / name).read_bytes()
        parsed = adapter.parse(adapter.raw_file_for(name, data, path=f"fixtures/{name}"), data)
        row, _ = tracking.register(db, parsed.raw)
        tracking.mark_downloaded(db, row.id, parsed.raw.path)
        loader.load(db, parsed, adapter)


def test_compare_reports_the_adapter_promo_confidence(client, db, catalog: World) -> None:
    _load_fixture(db)
    milk = db.execute(
        "SELECT id FROM items WHERE chain_id = %s AND barcode = %s", (SHUFERSAL, MILK_BARCODE)
    ).fetchone()[0]
    raw_conf = db.execute(
        "SELECT p.raw->>'confidence', p.raw->'confidence_reasons' FROM promos p"
        " JOIN promo_items pi ON pi.promo_id = p.id WHERE pi.item_id = %s",
        (milk,),
    ).fetchone()
    assert raw_conf == ("1.0", [])
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
        " VALUES (%s, %s, 'any_brand', 0.97, 'rule')",
        (milk, catalog.canon["milk3"]),
    )
    precompute_effective_prices(db, as_of=AS_OF, chains=[SHUFERSAL])
    store_id, lon, lat = db.execute(
        "SELECT id, ST_X(geog::geometry), ST_Y(geog::geometry) FROM stores"
        " WHERE chain_id = %s AND store_code = '1'",
        (SHUFERSAL,),
    ).fetchone()
    body = {
        "items": [{"canonical_id": catalog.canon["milk3"], "quantity": 1}],
        "location": {"lon": lon, "lat": lat, "radius_m": 1000},
    }
    r = client.post("/compare", json=body)
    assert r.status_code == 200, r.text
    store = next(s for s in r.json()["stores"] if s["store_id"] == store_id)
    line = store["items"][0]
    assert line["item_id"] == milk
    assert Decimal(str(line["line_total"])) == Decimal("5.90")  # the promo price, not 7.12
    assert line["promo_applied"] and line["promo_description"] == "חלב ב-5.90 בשעות הבוקר"
    assert line["promo_confidence"] == pytest.approx(1.0)


def test_a_lower_confidence_reaches_compare_unchanged(client, db, catalog: World) -> None:
    """A promo the adapter was less sure of keeps its own number (here: no end date)."""
    _load_fixture(db)
    milk = db.execute(
        "SELECT id FROM items WHERE chain_id = %s AND barcode = %s", (SHUFERSAL, MILK_BARCODE)
    ).fetchone()[0]
    db.execute(
        "UPDATE promos SET raw = raw || '{\"confidence\": 0.9}' WHERE id IN"
        " (SELECT promo_id FROM promo_items WHERE item_id = %s)",
        (milk,),
    )
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
        " VALUES (%s, %s, 'any_brand', 0.97, 'rule')",
        (milk, catalog.canon["milk3"]),
    )
    precompute_effective_prices(db, as_of=AS_OF, chains=[SHUFERSAL])
    lon, lat = db.execute(
        "SELECT ST_X(geog::geometry), ST_Y(geog::geometry) FROM stores"
        " WHERE chain_id = %s AND store_code = '1'",
        (SHUFERSAL,),
    ).fetchone()
    body = {
        "items": [{"canonical_id": catalog.canon["milk3"], "quantity": 1}],
        "location": {"lon": lon, "lat": lat, "radius_m": 1000},
    }
    line = client.post("/compare", json=body).json()["stores"][0]["items"][0]
    assert line["promo_confidence"] == pytest.approx(0.9)
