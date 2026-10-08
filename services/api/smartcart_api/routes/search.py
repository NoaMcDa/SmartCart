"""GET /search and POST /parse-list (issues #54, #51)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Query

from smartcart_api import schemas
from smartcart_api.db import get_conn
from smartcart_api.listparse import Fragment, parse_fragment, split_items, split_vav
from smartcart_api.misses import record_miss
from smartcart_api.search import Hit, ancestors, hybrid_search

router = APIRouter()

CONFIRM_BELOW = 0.75
NOT_FOUND_BELOW = 0.35
AMBIGUITY_MARGIN = 0.05
SPECIFICITY_MARGIN = 0.1
AMBIGUOUS_CAP = 0.70
MAX_CANDIDATES = 3


def canonical_ref(h: Hit) -> schemas.CanonicalRef:
    return schemas.CanonicalRef(
        canonical_id=h.canonical_id,
        display_name_he=h.display_name_he,
        display_name_ar=h.display_name_ar,
        taxonomy_id=h.taxonomy_id,
        base_unit=h.base_unit,
        category_path_he=h.category_path_he,
    )


@router.get("/search", response_model=schemas.SearchResponse, tags=["basket"])
def search(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> schemas.SearchResponse:
    hits = hybrid_search(conn, q, limit=limit)
    best = max((h.confidence for h in hits), default=0.0)
    if best < NOT_FOUND_BELOW:
        # Nothing the parser would accept: a demand signal for the catalog (issue #52).
        record_miss(conn, q, "search", best if hits else None)
    return schemas.SearchResponse(
        query=q,
        hits=[
            schemas.SearchHit(
                canonical=canonical_ref(h),
                score=h.score,
                matched_by=h.matched_by,
                confidence=h.confidence,
            )
            for h in hits
        ],
    )


def resolve(conn: psycopg.Connection, text: str) -> tuple[list[Hit], float]:
    """Hits for ``text`` and the confidence of the first one (0 when there is none).

    The confidence of the best hit is capped at AMBIGUOUS_CAP when another canonical is as good:
    nearly the same evidence and nearly the same specificity (3 % versus 1 % milk for "חלב").
    The user picks; the parser never guesses.
    """
    hits = hybrid_search(conn, text, limit=MAX_CANDIDATES + 2)
    if not hits:
        return [], 0.0
    top = hits[0]
    conf = top.confidence
    for other in hits[1:]:
        if (
            top.confidence - other.confidence < AMBIGUITY_MARGIN
            and top.specificity - other.specificity < SPECIFICITY_MARGIN
        ):
            conf = min(conf, AMBIGUOUS_CAP)
            break
    return hits, round(conf, 3)


def _row(
    conn: psycopg.Connection,
    frag: Fragment,
    hits: list[Hit],
    conf: float,
    flex_defaults: dict[str, str],
    chains: dict[str, list[str]],
) -> schemas.ParsedRow:
    if not hits or conf < NOT_FOUND_BELOW:
        return schemas.ParsedRow(
            input_text=frag.input_text.strip(),
            quantity=frag.quantity,
            unit=frag.unit,
            confidence=conf,
            needs_confirmation=True,
            not_found=True,
            candidates=[canonical_ref(h) for h in hits[:MAX_CANDIDATES]],
            is_weighed=frag.unit == "kg",
        )
    top = hits[0]
    flex = next(
        (flex_defaults[t] for t in chains.get(top.taxonomy_id, [top.taxonomy_id]) if t in flex_defaults),
        "any_brand",
    )
    needs = conf < CONFIRM_BELOW
    return schemas.ParsedRow(
        input_text=frag.input_text.strip(),
        canonical=canonical_ref(top),
        quantity=frag.quantity,
        unit=frag.unit,
        flex_level=flex,
        confidence=conf,
        needs_confirmation=needs,
        candidates=[canonical_ref(h) for h in hits[1 : MAX_CANDIDATES + 1]] if needs else [],
        is_weighed=frag.unit == "kg" or top.base_unit == "kg",
    )


@router.post("/parse-list", response_model=schemas.ParseListResponse, tags=["basket"])
def parse_list(
    body: schemas.ParseListRequest,
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
) -> schemas.ParseListResponse:
    resolved: list[tuple[Fragment, list[Hit], float]] = []
    for part in split_items(body.text):
        pieces = split_vav(part)
        parsed = []
        for piece in pieces:
            frag = parse_fragment(piece)
            parsed.append((frag, *resolve(conn, frag.text)))
        if len(pieces) > 1:
            # Split on " ו" only when every part resolves at least as well as the whole
            # fragment: "סלמון ולחם" is two items, "חטיף וופל" is one.
            whole = parse_fragment(part)
            w_hits, w_conf = resolve(conn, whole.text)
            if w_conf > min(c for _, _, c in parsed):
                resolved.append((whole, w_hits, w_conf))
                continue
        resolved.extend(parsed)
    chains = ancestors(conn, {h[0].taxonomy_id for _, h, _ in resolved if h})
    rows = [_row(conn, f, h, c, body.flex_defaults, chains) for f, h, c in resolved]
    for frag, hits, conf in resolved:
        if not hits or conf < NOT_FOUND_BELOW:  # the rows that came back not_found (issue #52)
            record_miss(conn, frag.text, "parse_list", conf if hits else None)
    return schemas.ParseListResponse(rows=rows, generated_at=datetime.now(UTC))

