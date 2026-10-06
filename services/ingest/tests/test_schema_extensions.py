"""Schema and smoke tests that need PostGIS or pgvector (issues #27 and #14).

Skipped locally when the server has no such extension; CI runs them against supabase/postgres
with SMARTCART_REQUIRE_EXTENSIONS=1, so there they fail instead of skipping.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.db

# (name, lon, lat). Distances are straight-line.
TEL_AVIV_AZRIELI = (34.7918, 32.0744)
JERUSALEM_CENTRAL = (35.2033, 31.7890)


def _plan(db, query: str, params: tuple = ()) -> str:
    return "\n".join(r[0] for r in db.execute("EXPLAIN " + query, params).fetchall())


# --- PostGIS -----------------------------------------------------------------------------------


@pytest.mark.postgis
def test_stores_geog_is_a_wgs84_point_geography_with_gist_index(db) -> None:
    coltype = db.execute(
        "SELECT format_type(atttypid, atttypmod) FROM pg_attribute"
        " WHERE attrelid = 'stores'::regclass AND attname = 'geog'"
    ).fetchone()[0]
    assert coltype == "geography(Point,4326)"
    indexdef = db.execute(
        "SELECT indexdef FROM pg_indexes WHERE tablename = 'stores' AND indexname = 'stores_geog_gist'"
    ).fetchone()[0]
    assert "USING gist (geog)" in indexdef


@pytest.mark.postgis
def test_radius_query_uses_the_gist_index(db, seed) -> None:
    # A spread of stores across central Israel, then statistics, then the radius query.
    db.execute(
        "INSERT INTO stores (chain_id, store_code, name, geog)"
        " SELECT 'test-chain', 'g' || g, 'Store ' || g,"
        "        ST_SetSRID(ST_MakePoint(34.6 + (g % 100) * 0.006, 31.5 + (g / 100) * 0.03), 4326)"
        "        ::geography"
        " FROM generate_series(1, 2000) AS g"
    )
    db.execute("ANALYZE stores")
    # With a few thousand rows the planner may still prefer a sequential scan; turning it off
    # proves the index is usable for this predicate, which is what the radius query relies on.
    db.execute("SET LOCAL enable_seqscan = off")
    plan = _plan(
        db,
        "SELECT id FROM stores WHERE ST_DWithin("
        " geog, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 3000)",
        TEL_AVIV_AZRIELI,
    )
    assert "stores_geog_gist" in plan, plan


@pytest.mark.postgis
def test_stores_within_returns_nearest_first(db, seed) -> None:
    db.execute(
        "UPDATE stores SET geog = ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography WHERE id = %s",
        (*TEL_AVIV_AZRIELI, seed.store_a),
    )
    db.execute(
        "UPDATE stores SET geog = ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography WHERE id = %s",
        (34.8018, 32.0744, seed.store_b),  # about 940 m east
    )
    rows = db.execute(
        "SELECT store_id, distance_m FROM stores_within(%s, %s, 2000) WHERE store_id IN (%s, %s)",
        (34.7920, 32.0744, seed.store_a, seed.store_b),
    ).fetchall()
    assert [r[0] for r in rows] == [seed.store_a, seed.store_b]
    assert rows[0][1] < 50 and 800 < rows[1][1] < 1000
    assert (
        db.execute(
            "SELECT count(*) FROM stores_within(%s, %s, 2000) WHERE store_id IN (%s, %s)",
            (*JERUSALEM_CENTRAL, seed.store_a, seed.store_b),
        ).fetchone()[0]
        == 0
    )


# --- #14 smoke test: extensions enabled, one PostGIS and one pgvector query ---------------------


@pytest.mark.postgis
@pytest.mark.pgvector
def test_extensions_are_enabled(db) -> None:
    names = {r[0] for r in db.execute("SELECT extname FROM pg_extension").fetchall()}
    assert {"postgis", "vector", "pg_trgm"} <= names


@pytest.mark.postgis
def test_smoke_postgis_distance(db) -> None:
    meters = db.execute(
        "SELECT ST_Distance(ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,"
        "                   ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography)",
        (*TEL_AVIV_AZRIELI, *JERUSALEM_CENTRAL),
    ).fetchone()[0]
    # Tel Aviv to Jerusalem is roughly 50 km in a straight line.
    assert 45_000 < meters < 55_000


@pytest.mark.pgvector
def test_smoke_pgvector_cosine_similarity(db) -> None:
    db.execute("CREATE TEMP TABLE smoke_vec (label text, embedding vector(3)) ON COMMIT DROP")
    db.execute(
        "INSERT INTO smoke_vec VALUES"
        " ('milk 3%', '[1,0.1,0]'), ('milk 1%', '[0.9,0.3,0]'), ('olive oil', '[0,0.2,1]')"
    )
    db.execute("CREATE INDEX ON smoke_vec USING hnsw (embedding vector_cosine_ops)")
    rows = db.execute(
        "SELECT label, 1 - (embedding <=> '[1,0,0]') AS cosine_similarity"
        " FROM smoke_vec ORDER BY embedding <=> '[1,0,0]' LIMIT 3"
    ).fetchall()
    assert [r[0] for r in rows] == ["milk 3%", "milk 1%", "olive oil"]
    assert rows[0][1] == pytest.approx(0.995, abs=0.001)
    assert rows[2][1] == pytest.approx(0.0, abs=1e-9)
