"""Store lookups (issue #90). Implemented by workstream P2-A."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from smartcart_api import schemas

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("/nearest", response_model=schemas.StoreRef)
def nearest_store(chain_id: str, lon: float, lat: float) -> schemas.StoreRef:
    raise HTTPException(status_code=501, detail="not implemented yet")
