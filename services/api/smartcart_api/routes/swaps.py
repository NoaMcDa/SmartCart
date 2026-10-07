"""Smart-cart swap suggestions (issue #45). Implemented by workstream P2-B."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from smartcart_api import schemas

router = APIRouter(prefix="/optimize", tags=["basket"])


@router.post("/swaps", response_model=schemas.SwapSuggestionResponse)
def swap_suggestions(body: schemas.CompareRequest, store_id: int) -> schemas.SwapSuggestionResponse:
    raise HTTPException(status_code=501, detail="not implemented yet")
