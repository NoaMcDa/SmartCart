"""GET /stores/nearest (issue #90): the nearest physical store of a chain, PostGIS KNN."""

from __future__ import annotations

import pytest
from api_world import KM_LAT, ORIGIN, World, add_store

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]


def nearest(client, chain: str, lon: float = ORIGIN[0], lat: float = ORIGIN[1]):
    return client.get("/stores/nearest", params={"chain_id": chain, "lon": lon, "lat": lat})


def test_nearest_store_of_the_chain(client, world: World) -> None:
    r = nearest(client, "t-c1")
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["store_id"] == world.stores["home"]  # 1 km north; A is 2 km, F 30 km
    assert s["chain_id"] == "t-c1" and s["chain_name"] == "רשת אחת" and s["channel"] == "physical"
    assert s["distance_m"] == pytest.approx(1000, abs=15)
    assert s["lat"] == pytest.approx(ORIGIN[1] + KM_LAT) and s["lon"] == pytest.approx(ORIGIN[0])
    # From near store A, A is the nearest.
    r = nearest(client, "t-c1", lat=ORIGIN[1] + 2.1 * KM_LAT)
    assert r.json()["store_id"] == world.stores["a"]


def test_online_stores_are_not_home_stores(client, world: World) -> None:
    # Chain two's online store (1.5 km) is nearer than its physical store B (3 km).
    assert nearest(client, "t-c2").json()["store_id"] == world.stores["b"]


def test_404_when_the_chain_has_no_physical_store(client, db, world: World) -> None:
    assert nearest(client, "no-such-chain").status_code == 404
    db.execute("INSERT INTO chains (id, name, portal) VALUES ('t-c3', 'רשת אונליין', 'other')")
    add_store(db, "t-c3", "W", 1.0, channel="online")
    assert nearest(client, "t-c3").status_code == 404


def test_coordinates_are_validated(client, world: World) -> None:
    assert nearest(client, "t-c1", lon=200).status_code == 422
    assert nearest(client, "t-c1", lat=-91).status_code == 422
