"""POST /optimize/swaps (issue #45): smart-cart swap suggestions for one store.

The logic is in smartcart_api/swaps.py; see docs/optimizer.md. The request is the /compare
body (the list, location and clubs) plus ``store_id``: the store the user shops at, typically
the chosen plan's store. Nothing is stored and nothing is applied.
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from smartcart_api import schemas
from smartcart_api.basket import store_info
from smartcart_api.db import get_conn
from smartcart_api.swaps import suggest_swaps

router = APIRouter(prefix="/optimize", tags=["basket"])


@router.post("/swaps", response_model=schemas.SwapSuggestionResponse)
def swap_suggestions(
    body: schemas.CompareRequest,
    store_id: int,
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
) -> schemas.SwapSuggestionResponse:
    store = store_info(conn, store_id, body.location)
    if store is None:
        raise HTTPException(status_code=404, detail="store not found")
    return suggest_swaps(conn, body, store)
