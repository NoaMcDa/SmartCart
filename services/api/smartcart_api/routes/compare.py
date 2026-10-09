"""POST /compare (issue #58): the basket at every store within the radius.

* Stores come from ``stores_within`` (PostGIS, ``stores_geog_gist``); online stores only with
  ``include_online``. Stores that supply none of the basket are left out.
* Each store lists its missing canonicals and ``found_count``; complete baskets sort first, then
  fewer missing items, then the total, then the distance. Compare totals only between complete
  baskets.
* ``saving_vs_home`` is the home store's total minus this store's total over the items both
  supply, and only when ``home_store_id`` is given. There is no comparison with the most
  expensive store or chain anywhere in the response (D7).
* Every line carries ``price_valid_from``; each store carries ``prices_updated_at``, the newest of
  its lines.
* Club deals follow ``basket.club_member`` (issue #19): only for the clubs in ``clubs``; a deal
  the user did not mark is reported as ``club_offer_name`` / ``club_offer_discount``, never in a
  total. Lines carry ``promo_confidence`` when the adapter recorded one; stores carry ``lat`` and
  ``lon`` from ``stores.geog`` (issue #90).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends

from smartcart_api import schemas
from smartcart_api.basket import price_baskets, store_info, stores_in_radius
from smartcart_api.db import get_conn

router = APIRouter()


def sort_key(r: schemas.StoreResult) -> tuple:
    return (len(r.missing), r.total, r.distance_m, r.store_id)


@router.post("/compare", response_model=schemas.CompareResponse, tags=["basket"])
def compare(
    body: schemas.CompareRequest,
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
) -> schemas.CompareResponse:
    stores = stores_in_radius(conn, body.location, body.include_online)
    home_info = None
    if body.home_store_id is not None:
        home_info = next((s for s in stores if s.store_id == body.home_store_id), None)
        if home_info is None:
            home_info = store_info(conn, body.home_store_id, body.location)
    priced = price_baskets(
        conn,
        body.items,
        stores + ([home_info] if home_info and home_info not in stores else []),
        body.clubs,
    )
    home = priced.get(home_info.store_id) if home_info else None
    results = [priced[s.store_id].result(home) for s in stores if priced[s.store_id].lines]
    results.sort(key=sort_key)
    return schemas.CompareResponse(
        stores=results,
        home_store_id=body.home_store_id,
        home_store_total=home.total if home is not None else None,
        generated_at=datetime.now(UTC),
    )
