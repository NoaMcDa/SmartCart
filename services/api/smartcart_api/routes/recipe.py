"""``POST /parse-recipe``: a Hebrew recipe (text or one page) to a shopping list (issue #71).

1. Read the recipe with the catalog's rule parser (``smartcart_catalog.recipe``): JSON-LD
   ``Recipe`` first for a page, ingredient lines with amounts in grams, milliliters, pieces or
   packs; lines that are not products, "to taste" or optional go to ``unresolved``.
2. Merge repeated ingredients, scale to ``servings`` when the recipe's yield is known.
3. Resolve each ingredient with the ``/parse-list`` matcher (``routes.search.resolve``): the same
   ambiguity cap, candidates and flexibility defaults, with a stricter floor. A recipe line is
   not written for our catalog ("יין לבן" shares a word with "קמח לבן", "סודה לשתייה" with
   soda water), so a hit under ``RECIPE_MIN_CONFIDENCE`` (0.70, an estimate) goes to
   ``unresolved`` with its line instead of a confirmation prompt: never a guess (D5). Two
   equally good canonicals ("חלב": 3 % or 1 %) are capped at exactly 0.70 by the matcher and
   stay, with ``needs_confirmation`` and candidates.
4. Turn the amount into the row's quantity under the canonical's base unit
   (``recipe.basket_quantity``): kilograms for goods sold by weight, else whole packs of the
   canonical's typical pack size, rounded up. A conversion the tables do not know keeps one pack
   and sets ``needs_confirmation``.

No LLM is needed; the rule parser is the only path. Nothing is stored.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from smartcart_api import schemas
from smartcart_api.db import get_conn
from smartcart_api.listparse import Fragment
from smartcart_api.misses import record_miss
from smartcart_api.recipe_fetch import Fetcher, FetchError, get_fetcher
from smartcart_api.routes.search import AMBIGUOUS_CAP, _row, resolve
from smartcart_api.search import ancestors
from smartcart_catalog import recipe as rp

router = APIRouter()

RECIPE_MIN_CONFIDENCE = AMBIGUOUS_CAP  # 0.70; ambiguous hits are capped at exactly this


def _pack(soft: dict[str, Any] | None) -> tuple[Decimal | None, str | None]:
    soft = soft or {}
    try:
        size = Decimal(str(soft["pack_size"])) if soft.get("pack_size") is not None else None
    except (InvalidOperation, ValueError):
        size = None
    unit = soft.get("unit")
    return size, unit if isinstance(unit, str) else None


def resolve_ingredients(
    conn: psycopg.Connection, ingredients: list[rp.Ingredient]
) -> tuple[list[schemas.ParsedRow], list[str]]:
    found: list[tuple[rp.Ingredient, list, float]] = []
    unresolved: list[str] = []
    for ing in ingredients:
        hits, conf = resolve(conn, ing.name)
        if not hits or conf < RECIPE_MIN_CONFIDENCE:
            unresolved.append(ing.line)
            record_miss(conn, ing.name, "parse_recipe", conf if hits else None)  # issue #52
        else:
            found.append((ing, hits, conf))
    if not found:
        return [], unresolved
    ids = list({h[0].canonical_id for _, h, _ in found})
    soft = dict(conn.execute(
        "SELECT id, soft_attrs FROM canonical_products WHERE id = ANY(%s)", (ids,)
    ).fetchall())
    chains = ancestors(conn, {h[0].taxonomy_id for _, h, _ in found})
    rows = []
    for ing, hits, conf in found:
        top = hits[0]
        size, unit = _pack(soft.get(top.canonical_id))
        q = rp.basket_quantity(ing, top.base_unit, size, unit, top.display_name_he)
        row = _row(conn, Fragment(ing.line, ing.name, q.quantity, q.unit), hits, conf, {}, chains)
        if not q.converted and not row.needs_confirmation:
            row = row.model_copy(update={"needs_confirmation": True})
        rows.append(row)
    return rows, unresolved


@router.post("/parse-recipe", response_model=schemas.ParseRecipeResponse, tags=["basket"])
def parse_recipe(
    body: schemas.ParseRecipeRequest,
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
    fetch: Annotated[Fetcher, Depends(get_fetcher)],
) -> schemas.ParseRecipeResponse:
    if body.text is not None:
        recipe = rp.parse_recipe_text(body.text)
    else:
        try:
            page = fetch(body.url or "")
        except FetchError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        recipe = rp.recipe_from_html(page)
    recipe.ingredients = rp.merge(recipe.ingredients)
    recipe, servings = rp.scale(recipe, body.servings)
    rows, not_found = resolve_ingredients(conn, recipe.ingredients)
    return schemas.ParseRecipeResponse(
        title=recipe.title,
        servings=servings,
        items=rows,
        unresolved=recipe.unresolved + not_found,
    )
