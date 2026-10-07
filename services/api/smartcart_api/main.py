"""FastAPI application. Routes are declared here with the contract schemas; the implementations
live in smartcart_api.routes.* and are wired by workstream W3. Until then every route returns 501.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from smartcart_api import schemas

VERSION = "0.1.0"

app = FastAPI(
    title="SmartCart API",
    version=VERSION,
    description="Semantic supermarket price comparison for Israel. Prices are from the chains' transparency files; המחיר הקובע הוא בקופה.",
    openapi_version="3.1.0",
)


def _not_implemented() -> None:
    raise HTTPException(status_code=501, detail="not implemented yet")


@app.get("/health", response_model=schemas.Health, tags=["meta"])
def health() -> schemas.Health:
    return schemas.Health(status="ok", version=VERSION)


@app.post("/parse-list", response_model=schemas.ParseListResponse, tags=["basket"])
def parse_list(body: schemas.ParseListRequest) -> schemas.ParseListResponse:
    _not_implemented()
    raise AssertionError


@app.get("/search", response_model=schemas.SearchResponse, tags=["basket"])
def search(q: str, limit: int = 10) -> schemas.SearchResponse:
    _not_implemented()
    raise AssertionError


@app.post("/compare", response_model=schemas.CompareResponse, tags=["basket"])
def compare(body: schemas.CompareRequest) -> schemas.CompareResponse:
    _not_implemented()
    raise AssertionError


@app.post("/optimize", response_model=schemas.OptimizeResponse, tags=["basket"])
def optimize(body: schemas.OptimizeRequest) -> schemas.OptimizeResponse:
    _not_implemented()
    raise AssertionError


@app.post("/feedback/substitution", response_model=schemas.Ack, tags=["feedback"])
def feedback_substitution(body: schemas.SubstitutionFeedbackRequest) -> schemas.Ack:
    _not_implemented()
    raise AssertionError


@app.post("/feedback/gap", response_model=schemas.Ack, tags=["feedback"])
def feedback_gap(body: schemas.GapReportRequest) -> schemas.Ack:
    _not_implemented()
    raise AssertionError


def run() -> None:
    import uvicorn

    uvicorn.run("smartcart_api.main:app", host="0.0.0.0", port=8000, reload=False)
