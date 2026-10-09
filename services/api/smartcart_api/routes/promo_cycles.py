"""``GET /promo-cycles/{canonical_id}``: when a promo is likely to return, per chain (issue #69).

The estimate is the catalog's statistical baseline (``smartcart_catalog.promo_cycles``): promo
windows per chain, the median gap between starts, a confidence from the number of cycles and
their regularity, and the next expected window. Below 3 cycles or a confidence of 0.6 the answer
is ``advice = "unknown"`` with no window (precision over recall, D10). Club-only promos count
only for clubs the caller marked (``clubs``), with the same rule as /compare
(``basket.club_member``). It reads ``promos`` per request and is not on the compare or optimize
path. See docs/promo-cycles.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from smartcart_api import schemas
from smartcart_api.basket import club_member
from smartcart_api.db import get_conn
from smartcart_catalog import promo_cycles as pc

router = APIRouter(prefix="/promo-cycles", tags=["history"])


@router.get("/{canonical_id}", response_model=schemas.PromoCycleResponse)
def get_promo_cycles(
    canonical_id: int,
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
    clubs: Annotated[
        list[str] | None,
        Query(
            max_length=20,
            description="Clubs the user marked; club-only promos count only for these",
        ),
    ] = None,
) -> schemas.PromoCycleResponse:
    if (
        conn.execute("SELECT 1 FROM canonical_products WHERE id = %s", (canonical_id,)).fetchone()
        is None
    ):
        raise HTTPException(status_code=404, detail="canonical product not found")
    marked = [c for c in (clubs or []) if c.strip()]

    def include(club_name: str | None, chain_name: str, chain_clubs: Sequence[str]) -> bool:
        return bool(marked) and club_member(club_name, marked, chain_name, chain_clubs)

    today = datetime.now(UTC).date()
    chains = [
        schemas.PromoCycleChain(
            chain_id=c.chain_id,
            chain_name=c.chain_name,
            cycles_seen=c.estimate.cycles_seen,
            median_gap_days=c.estimate.median_gap_days,
            confidence=c.estimate.confidence,
            last_promo_ends=c.estimate.last_end,
            next_expected_from=c.estimate.next_from,
            next_expected_to=c.estimate.next_to,
            advice=c.estimate.advice,
        )
        for c in pc.promo_cycles(conn, canonical_id, today, include)
    ]
    return schemas.PromoCycleResponse(canonical_id=canonical_id, chains=chains)
