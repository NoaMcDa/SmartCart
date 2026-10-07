"""Price history (issue #28). Implemented by workstream P2-A."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from smartcart_api import schemas

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/{canonical_id}", response_model=schemas.PriceHistoryResponse)
def price_history(canonical_id: int, store_id: int | None = None, days: int = 90) -> schemas.PriceHistoryResponse:
    raise HTTPException(status_code=501, detail="not implemented yet")
