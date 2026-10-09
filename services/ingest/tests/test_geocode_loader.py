"""The loader hook that sets stores.geog from data/geo (docs/geocoding.md), on the real Stores files
and on a fake chain. Needs PostGIS (the migration is skipped without it)."""

from __future__ import annotations

from pathlib import Path

import pytest

from smartcart_ingest import tracking
from smartcart_ingest.geocode.localities import normalize_code
from smartcart_ingest.geocode.resolve import StoreGeocode, write_store_geocodes
from smartcart_ingest.loader import load
from tests.fakes import FakeAdapter, encode, parsed_file, store
from tests.test_adapters import REAL_FILES, chain_adapters, parse_fixture

pytestmark = [pytest.mark.db, pytest.mark.postgis]

REPO = Path(__file__).resolve().parents[3]
SAMPLE = REPO / "data" / "geo" / "localities_sample.csv"


@pytest.fixture
def geo_env(tmp_path: Path, monkeypatch):
    """Point the loader at the committed sample localities and an (initially absent) geocode file."""
    geocodes = tmp_path / "store_geocodes.csv"
    monkeypatch.setenv("SMARTCART_GEO_LOCALITIES", str(SAMPLE))
    monkeypatch.setenv("SMARTCART_GEO_STORES", str(geocodes))
    return geocodes


def _load_stores(db, parsed, adapter=None) -> None:
    row, _ = tracking.register(db, parsed.raw)
    tracking.mark_downloaded(db, row.id, parsed.raw.path)
    load(db, parsed, adapter or FakeAdapter())


def _geo(db, chain: str = "fake") -> dict[str, tuple]:
    rows = db.execute(
        "SELECT store_code, ST_Y(geog::geometry), ST_X(geog::geometry), geo_precision, geo_source"
        " FROM stores WHERE chain_id = %s",
        (chain,),
    ).fetchall()
    return {r[0]: r[1:] for r in rows}


def test_migration_adds_the_columns_constraint_and_view(db) -> None:
    cols = dict(
        db.execute(
            "SELECT column_name, data_type FROM information_schema.columns"
            " WHERE table_name = 'stores' AND column_name IN ('geo_precision', 'geo_source')"
        ).fetchall()
    )
    assert cols == {"geo_precision": "text", "geo_source": "text"}
    with pytest.raises(Exception, match="stores_geo_precision_ok"):
        db.execute("INSERT INTO chains (id, name, portal) VALUES ('x', 'x', 'other')")
        db.execute(
            "INSERT INTO stores (chain_id, store_code, name, geog, geo_precision)"
            " VALUES ('x', '1', 'n', ST_MakePoint(34.8, 32.0)::geography, 'rooftop')"
        )


def test_legacy_writers_that_set_only_geog_get_chain_labels(db) -> None:
    db.execute("INSERT INTO chains (id, name, portal) VALUES ('x', 'x', 'other')")
    db.execute(
        "INSERT INTO stores (chain_id, store_code, name, geog)"
        " VALUES ('x', '1', 'n', ST_MakePoint(34.8, 32.0)::geography)"
    )
    assert _geo(db, "x")["1"][2:] == ("address", "chain")
    db.execute("UPDATE stores SET geog = NULL WHERE chain_id = 'x'")
    assert _geo(db, "x")["1"][2:] == (None, None)


def test_locality_centroid_is_used_when_nothing_better_exists(db, geo_env) -> None:
    data = encode(
        stores=[
            store("1", "תל אביב", city="5000", address="דיזנגוף 1"),
            store("2", "ללא עיר", city="0", address="x"),
            store("3", "עיר לא בטבלה", city="123456", address="x"),
            store("90", "Fake Online", city="5000"),
        ]
    )
    _load_stores(db, parsed_file("stores", data))
    geo = _geo(db)
    assert geo["1"][2:] == ("locality", "cbs-locality:5000")
    assert (round(geo["1"][0], 2), round(geo["1"][1], 2)) == (32.08, 34.78)
    assert geo["2"] == (None, None, None, None) and geo["3"] == (None, None, None, None)
    assert geo["90"] == (None, None, None, None)  # an online store is not looked up
    missing = db.execute(
        "SELECT store_code, reason FROM stores_missing_geo WHERE chain_id = 'fake' ORDER BY 1"
    ).fetchall()
    # the online store is not a physical store, so it is not listed
    assert missing == [
        ("2", "city code unknown (0 or missing)"),
        ("3", "city code not in the locality table"),
    ]


def test_geocode_row_beats_the_locality_and_is_not_downgraded_later(db, geo_env) -> None:
    write_store_geocodes(
        geo_env, [StoreGeocode("fake", "1", 32.0853, 34.7818, "address", "nominatim", "k", "d")]
    )
    stores = [store("1", "תל אביב", city="5000"), store("2", "תל אביב 2", city="5000")]
    _load_stores(db, parsed_file("stores", encode(stores=stores, salt="a"), path="raw/a"))
    geo = _geo(db)
    assert geo["1"] == (32.0853, 34.7818, "address", "nominatim")
    assert geo["2"][2] == "locality"
    # The geocode file disappears (or is regenerated without the row): the better location stays.
    geo_env.unlink()
    _load_stores(db, parsed_file("stores", encode(stores=stores, salt="b"), path="raw/b"))
    assert _geo(db)["1"] == (32.0853, 34.7818, "address", "nominatim")


def test_chain_published_coordinates_win_and_are_never_replaced(db, geo_env) -> None:
    write_store_geocodes(
        geo_env, [StoreGeocode("fake", "1", 32.5, 34.9, "address", "nominatim", "k", "d")]
    )
    stores = [store("1", "תל אביב", city="5000", lat=32.07, lon=34.79)]
    _load_stores(db, parsed_file("stores", encode(stores=stores, salt="a"), path="raw/a"))
    assert _geo(db)["1"] == (32.07, 34.79, "address", "chain")
    stores = [store("1", "תל אביב", city="5000")]  # a later file without coordinates
    _load_stores(db, parsed_file("stores", encode(stores=stores, salt="b"), path="raw/b"))
    assert _geo(db)["1"] == (32.07, 34.79, "address", "chain")


def test_radius_queries_work_on_locality_points(db, geo_env) -> None:
    stores = [store("1", "תל אביב", city="5000"), store("2", "ירושלים", city="3000")]
    _load_stores(db, parsed_file("stores", encode(stores=stores)))
    near = db.execute("SELECT chain_id, store_id FROM stores_within(34.78, 32.08, 5000)").fetchall()
    ids = dict(db.execute("SELECT store_code, id FROM stores WHERE chain_id = 'fake'").fetchall())
    assert near == [("fake", ids["1"])]  # Jerusalem is about 55 km away


def test_an_unreadable_geo_dir_does_not_fail_the_load(db, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SMARTCART_GEO_LOCALITIES", str(tmp_path / "does-not-exist.csv"))
    monkeypatch.setenv("SMARTCART_GEO_STORES", str(tmp_path / "nor-this.csv"))
    _load_stores(db, parsed_file("stores", encode(stores=[store("1", "x", city="5000")])))
    assert _geo(db)["1"] == (None, None, None, None)


STORES_FILES = [(slug, p) for slug, p in REAL_FILES if p.name.startswith("Stores")]


@pytest.mark.skipif(not STORES_FILES, reason="no real Stores fixtures")
def test_real_stores_files_get_locality_coordinates_where_the_city_is_in_the_table(
    db, geo_env
) -> None:
    from smartcart_ingest.geocode.localities import load_localities

    table = load_localities(SAMPLE)
    expected_located = expected_missing = 0
    for slug, path in STORES_FILES:
        adapter = chain_adapters()[slug]()
        parsed = parse_fixture(adapter, path)
        _load_stores(db, parsed, adapter)
        for s in parsed.stores:
            if s.channel != "physical":
                continue
            if normalize_code(s.city) in table:
                expected_located += 1
            else:
                expected_missing += 1
    located, wrong_precision = db.execute(
        "SELECT count(*), count(*) FILTER (WHERE geo_precision <> 'locality')"
        " FROM stores WHERE channel = 'physical' AND geog IS NOT NULL"
    ).fetchone()
    missing = db.execute("SELECT count(*) FROM stores_missing_geo").fetchone()[0]
    assert (located, wrong_precision) == (expected_located, 0)
    assert missing == expected_missing
    assert located > 300
    unlocated_with_known_city = db.execute(
        "SELECT count(*) FROM stores_missing_geo WHERE reason LIKE 'city code unknown%'"
    ).fetchone()[0]
    assert 50 <= unlocated_with_known_city <= missing
