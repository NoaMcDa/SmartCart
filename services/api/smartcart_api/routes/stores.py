"""Store lookups (issue #90).

``GET /stores/nearest?chain_id=&lon=&lat=``: the nearest physical store of a chain, so onboarding
can turn "my chain" into a home store id. PostGIS KNN (``geog <-> point``) on the
``stores_geog_gist`` index; 404 when the chain has no physical store with a location.
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from smartcart_api import schemas
from smartcart_api.db import get_conn

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("/nearest", response_model=schemas.StoreRef)
def nearest_store(
    chain_id: str,
    lon: Annotated[float, Query(ge=-180, le=180)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
) -> schemas.StoreRef:
    row = conn.execute(
        "WITH p AS (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography AS g)"
        " SELECT s.id, s.chain_id, c.name, s.name, s.city,"
        "   round(ST_Distance(s.geog, p.g))::int,"
        "   ST_Y(s.geog::geometry)::float8, ST_X(s.geog::geometry)::float8, s.channel"
        " FROM stores AS s JOIN chains AS c ON c.id = s.chain_id, p"
        " WHERE s.chain_id = %(chain)s AND s.channel = 'physical' AND s.geog IS NOT NULL"
        " ORDER BY s.geog <-> p.g, s.id LIMIT 1",
        {"lon": lon, "lat": lat, "chain": chain_id},
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="no physical store of this chain")
    return schemas.StoreRef(
        store_id=row[0], chain_id=row[1], chain_name=row[2], store_name=row[3], city=row[4],
        distance_m=row[5], lat=row[6], lon=row[7], channel=row[8],
    )
