"""Store geo precision on every response that carries a store location or a distance.

``stores.geo_precision`` (address | street | locality) is passed through as ``geo_precision`` and a
locality point (a town centre) makes ``distance_approximate`` true. Neither changes ranking or the
radius filter.
"""

from __future__ import annotations

import json

import pytest
from api_world import ORIGIN, World, add_store

from smartcart_api.basket import store_info, stores_in_radius
from smartcart_api.precompute import precompute_effective_prices
from smartcart_api.schemas import Location

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]

NEW_FIELDS = ("geo_precision", "distance_approximate")


@pytest.fixture
def w(db, world: World) -> World:
    precompute_effective_prices(db, chains=world.chains)
    return world


def set_precision(db, w: World, **by_key: str) -> None:
    for key, precision in by_key.items():
        db.execute("UPDATE stores SET geo_precision = %s WHERE id = %s", (precision, w.stores[key]))


def items(w: World) -> list[dict]:
    return [
        {"canonical_id": w.canon["milk3"], "quantity": 2},
        {"canonical_id": w.canon["paste"], "quantity": 1},
        {"canonical_id": w.canon["bread"], "quantity": 3},
        {"canonical_id": w.canon["eggs"], "quantity": 1},
    ]


def compare(client, w: World) -> dict:
    r = client.post(
        "/compare",
        json={"items": items(w), "location": w.location, "home_store_id": w.stores["home"]},
    )
    assert r.status_code == 200, r.text
    return r.json()


def strip(node):
    """The same JSON without the new fields and the clock, to compare outputs across precision data."""
    if isinstance(node, dict):
        return {k: strip(v) for k, v in node.items() if k not in (*NEW_FIELDS, "generated_at")}
    if isinstance(node, list):
        return [strip(v) for v in node]
    return node


def test_compare_round_trips_precision_per_store(client, db, w: World) -> None:
    set_precision(db, w, home="address", a="locality", b="street")
    stores = {s["store_id"]: s for s in compare(client, w)["stores"]}
    assert stores[w.stores["home"]]["geo_precision"] == "address"
    assert stores[w.stores["home"]]["distance_approximate"] is False
    assert stores[w.stores["a"]]["geo_precision"] == "locality"
    assert stores[w.stores["a"]]["distance_approximate"] is True
    assert stores[w.stores["b"]]["geo_precision"] == "street"
    assert stores[w.stores["b"]]["distance_approximate"] is False


def test_default_stores_are_address_precision(client, w: World) -> None:
    for s in compare(client, w)["stores"]:
        assert s["geo_precision"] == "address" and s["distance_approximate"] is False


def test_ranking_and_radius_do_not_depend_on_precision(client, db, w: World) -> None:
    before = compare(client, w)
    set_precision(db, w, home="locality", a="locality", b="street", far="locality")
    after = compare(client, w)
    assert [s["store_id"] for s in after["stores"]] == [s["store_id"] for s in before["stores"]]
    # Byte-identical apart from the new fields (and the clock).
    assert json.dumps(strip(after), sort_keys=True) == json.dumps(strip(before), sort_keys=True)
    assert after != before  # the new fields themselves do differ
    assert w.stores["far"] not in {s["store_id"] for s in after["stores"]}


@pytest.mark.parametrize("solver", ["heuristic", "milp"])
def test_optimize_plans_carry_precision(client, db, w: World, solver: str) -> None:
    set_precision(db, w, a="locality")
    r = client.post(
        "/optimize",
        json={
            "items": items(w),
            "location": w.location,
            "home_store_id": w.stores["home"],
            "solver": solver,
        },
    )
    assert r.status_code == 200, r.text
    seen = {}
    for kind in ("single", "split", "minimum_effort"):
        plan = r.json().get(kind)
        for assignment in (plan or {}).get("stores", []):
            st = assignment["store"]
            seen[st["store_id"]] = st
            assert st["geo_precision"] in ("address", "locality")
            assert st["distance_approximate"] is (st["geo_precision"] == "locality")
    assert seen, "no plan returned a store"
    if w.stores["a"] in seen:
        assert seen[w.stores["a"]]["geo_precision"] == "locality"


@pytest.mark.parametrize("solver", ["heuristic", "milp"])
def test_optimize_choice_does_not_depend_on_precision(client, db, w: World, solver: str) -> None:
    body = {
        "items": items(w),
        "location": w.location,
        "home_store_id": w.stores["home"],
        "solver": solver,
    }
    before = client.post("/optimize", json=body).json()
    set_precision(db, w, home="locality", a="locality", b="locality")
    after = client.post("/optimize", json=body).json()
    assert json.dumps(strip(after), sort_keys=True) == json.dumps(strip(before), sort_keys=True)


def test_stores_nearest_round_trips_precision(client, db, w: World) -> None:
    def nearest() -> dict:
        r = client.get(
            "/stores/nearest", params={"chain_id": "t-c1", "lon": ORIGIN[0], "lat": ORIGIN[1]}
        )
        assert r.status_code == 200, r.text
        return r.json()

    assert nearest()["geo_precision"] == "address" and nearest()["distance_approximate"] is False
    set_precision(db, w, home="locality")
    s = nearest()
    assert s["store_id"] == w.stores["home"]
    assert s["geo_precision"] == "locality" and s["distance_approximate"] is True
    assert s["distance_m"] > 0  # the distance is still reported, only flagged


def test_barcode_store_refs_carry_precision(client, db, w: World) -> None:
    set_precision(db, w, a="locality")
    r = client.get(
        "/items/barcode/7290000000000",
        params={"lon": ORIGIN[0], "lat": ORIGIN[1], "store_id": w.stores["home"]},
    )
    assert r.status_code == 200, r.text
    resp = r.json()
    refs = [
        resp[k]["store"] for k in ("here", "cheapest_nearby", "cheaper_substitute") if resp.get(k)
    ]
    assert refs
    for st in refs:
        assert st["geo_precision"] in ("address", "locality")
        assert st["distance_approximate"] is (st["geo_precision"] == "locality")
    near = resp["cheapest_nearby"]["store"]
    assert near["store_id"] == w.stores["a"]
    assert near["geo_precision"] == "locality" and near["distance_approximate"] is True


def test_basket_layer_flags_locality_and_missing_coordinates(db, w: World) -> None:
    loc = Location(**w.location)
    set_precision(db, w, a="locality", b="street")
    by_id = {s.store_id: s for s in stores_in_radius(db, loc, include_online=False)}
    assert by_id[w.stores["a"]].distance_approximate is True
    assert by_id[w.stores["b"]].distance_approximate is False
    assert by_id[w.stores["home"]].geo_precision == "address"
    # A store without coordinates has no real distance (reported 0), so it is flagged too.
    nogeo = db.execute(
        "INSERT INTO stores (chain_id, store_code, name, city, channel) VALUES"
        " ('t-c1', 'NG', 'ללא מיקום', 'תל אביב', 'physical') RETURNING id"
    ).fetchone()[0]
    info = store_info(db, nogeo, loc)
    assert info is not None and info.geo_precision is None
    assert info.distance_m == 0 and info.distance_approximate is True


def test_add_store_helper_sets_precision(db, w: World) -> None:
    sid = add_store(db, "t-c1", "LOC", 1.2, geo_precision="locality")
    assert (
        db.execute("SELECT geo_precision FROM stores WHERE id = %s", (sid,)).fetchone()[0]
        == "locality"
    )
