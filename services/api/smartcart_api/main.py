"""FastAPI application: the contract schemas (smartcart_api.schemas) and the route modules.

| Route | Module |
|---|---|
| ``GET /health`` | here |
| ``POST /parse-list``, ``GET /search`` | routes/search.py |
| ``POST /compare`` | routes/compare.py |
| ``POST /optimize`` | routes/optimize.py |
| ``POST /feedback/substitution``, ``POST /feedback/gap`` | routes/feedback.py |
| ``GET/PUT /me/profile``, ``/me/lists`` CRUD (Supabase JWT, RLS) | routes/me.py |
| ``POST /events`` first-party beta events (allowlisted, rate limited) | routes/events.py |
| ``POST /parse-recipe`` (phase 3, #71) | routes/recipe.py |
| ``GET/POST /me/spend`` budget and spend (phase 3, #70) | routes/spend.py |
| ``GET /promo-cycles/{canonical_id}`` (phase 3, #69) | routes/promo_cycles.py |

See docs/api.md.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from smartcart_api import schemas
from smartcart_api.db import close_pool
from smartcart_api.routes import (
    alerts,
    barcode,
    beta,
    chains,
    compare,
    events,
    feedback,
    history,
    image,
    me,
    me_delete,
    optimize,
    promo_cycles,
    recipe,
    search,
    shares,
    spend,
    stores,
    swaps,
)
from smartcart_api.settings import API_VERSION, get_settings

VERSION = API_VERSION


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    close_pool()


app = FastAPI(
    title="SmartCart API",
    version=VERSION,
    description="Semantic supermarket price comparison for Israel. Prices are from the chains' transparency files; המחיר הקובע הוא בקופה.",
    openapi_version="3.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", response_model=schemas.Health, tags=["meta"])
def health() -> schemas.Health:
    return schemas.Health(status="ok", version=VERSION)


app.include_router(search.router)
app.include_router(compare.router)
app.include_router(optimize.router)
app.include_router(feedback.router)
app.include_router(me.router)
app.include_router(events.router)
# Phase 2 routers (stubs until their workstreams land; one module per workstream).
app.include_router(me_delete.router)
app.include_router(stores.router)
app.include_router(history.router)
app.include_router(alerts.router)
app.include_router(shares.router)
app.include_router(barcode.router)
app.include_router(swaps.router)
# Phase 3 routers.
app.include_router(recipe.router)
app.include_router(spend.router)
app.include_router(promo_cycles.router)
app.include_router(image.router)
app.include_router(chains.router)
app.include_router(beta.router)


def run() -> None:
    import uvicorn

    uvicorn.run("smartcart_api.main:app", host="0.0.0.0", port=8000, reload=False)
