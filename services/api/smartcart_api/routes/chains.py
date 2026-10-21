"""``GET /chains/online``: each chain's own online store, for the cart handoff (issue #72).

A link to the chain's public site, never a fetch: the app does not scrape chain online stores
(CLAUDE.md, docs/cart-transfer.md). The user's browser opens the address.

``enabled`` is the per-chain feature flag: the chain id is listed in ``CART_HANDOFF_CHAINS`` and the
chain has an online address. With the variable unset every row is disabled and the web app shows no
handoff. Ranking (``/compare``, ``/optimize``) never reads these columns: the basket code selects the
chain columns it needs by name, and ``tests/test_api_handoff_independence.py`` proves the responses
are byte-identical with the flag and the referral flags on or off.
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Response

from smartcart_api import schemas
from smartcart_api.db import get_conn
from smartcart_api.settings import Settings, get_settings
from smartcart_ingest.adapters.clubs import load_chain_clubs

router = APIRouter(tags=["stores"])

CACHE_CONTROL = "public, max-age=3600"


@router.get("/chains/online", response_model=list[schemas.ChainOnline])
def chains_online(
    response: Response,
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[schemas.ChainOnline]:
    response.headers["Cache-Control"] = CACHE_CONTROL
    flagged = set(settings.cart_handoff_chains)
    rows = conn.execute(
        "SELECT id, name, online_url, search_url_template, online_referral"
        " FROM chains ORDER BY name, id"
    ).fetchall()
    return [
        schemas.ChainOnline(
            chain_id=chain_id,
            chain_name=name,
            online_url=url,
            search_url_template=template,
            enabled=chain_id in flagged and bool(url),
            referral=referral,
        )
        for chain_id, name, url, template, referral in rows
    ]


@router.get("/chains/clubs", response_model=list[schemas.ChainClubs])
def chains_clubs(response: Response) -> list[schemas.ChainClubs]:
    """The clubs a person can be a member of, per chain: what the profile's club picker lists and
    what `clubs` of /compare, /optimize and the barcode lookup take (the ids). The data is
    `adapters/chain_clubs.json`: only clubs seen in real transparency files; a chain missing here
    has no club promotion we can attribute. Nothing about the person is read."""
    response.headers["Cache-Control"] = CACHE_CONTROL
    return [
        schemas.ChainClubs(
            chain_id=chain.chain_id,
            chain_name=chain.name,
            clubs=[
                schemas.ClubChoice(id=c.id, label=c.label, kind=c.kind)  # type: ignore[arg-type]
                for c in chain.clubs
            ],
        )
        for chain in load_chain_clubs().values()
    ]
