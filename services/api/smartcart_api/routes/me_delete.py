"""Account deletion (issue #90). Implemented by workstream P2-A."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from smartcart_api import schemas

router = APIRouter(prefix="/me", tags=["me"])


@router.delete("", response_model=schemas.Ack)
def delete_me() -> schemas.Ack:
    raise HTTPException(status_code=501, detail="not implemented yet")
