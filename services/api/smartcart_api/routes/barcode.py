"""Barcode lookup for in-store scanning (issue #39). Implemented by workstream P2-A."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from smartcart_api import schemas

router = APIRouter(prefix="/items", tags=["barcode"])


@router.get("/barcode/{barcode}", response_model=schemas.BarcodeLookupResponse)
def lookup_barcode(
    barcode: str, lon: float, lat: float, radius_m: int = 5000, store_id: int | None = None
) -> schemas.BarcodeLookupResponse:
    raise HTTPException(status_code=501, detail="not implemented yet")
