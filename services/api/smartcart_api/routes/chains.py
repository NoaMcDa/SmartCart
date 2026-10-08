"""``GET /chains/online``: each chain's own online store, for the cart handoff (issue #72).

Contract only on the base branch. A link to the chain's public site, never a fetch: the app does
not scrape chain online stores (CLAUDE.md). Ranking never reads this data.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from smartcart_api import schemas

router = APIRouter(tags=["stores"])


@router.get("/chains/online", response_model=list[schemas.ChainOnline])
def chains_online() -> list[schemas.ChainOnline]:
    raise HTTPException(status_code=501, detail="not implemented yet")
