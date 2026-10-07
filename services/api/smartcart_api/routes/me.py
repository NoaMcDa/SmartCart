"""The signed-in user's profile and saved lists (issue #64), under row-level security.

Every query here runs on ``user_conn``: role ``smartcart_app`` and ``auth.uid()`` = the token's
user, so the RLS policies decide which rows exist. The ``user_id = %s`` filters are for clarity
and index use, not for security. The web app may use Supabase PostgREST for the same tables; both
paths are protected by the same policies.

Location: a neighborhood location is stored only with ``consent_location`` (D11), and the
database trigger rounds it to 3 decimals (about 100 m).
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from smartcart_api import schemas
from smartcart_api.auth import User, user_conn

router = APIRouter(prefix="/me", tags=["me"])
UserConn = Annotated[tuple[User, psycopg.Connection], Depends(user_conn)]

_PROFILE_COLS = (
    "home_store_id", "radius_m", "neighborhood_lat", "neighborhood_lon", "travel_mode",
    "cost_per_km", "extra_stop_value", "max_stores", "clubs", "diet_flags", "kosher_level",
    "flex_defaults", "theme", "consent_location",
)


def _profile(row: dict | None, user: User) -> schemas.Profile:
    if row is None:
        return schemas.Profile(user_id=str(user.id), exists=False)
    data = {k: row[k] for k in _PROFILE_COLS}
    for k in ("neighborhood_lat", "neighborhood_lon"):
        data[k] = float(data[k]) if data[k] is not None else None
    return schemas.Profile(user_id=str(user.id), exists=True, **data)


@router.get("/profile", response_model=schemas.Profile)
def get_profile(uc: UserConn) -> schemas.Profile:
    user, conn = uc
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute("SELECT * FROM profiles WHERE user_id = %s", (user.id,)).fetchone()
    return _profile(row, user)


@router.put("/profile", response_model=schemas.Profile)
def put_profile(body: schemas.ProfileUpdate, uc: UserConn) -> schemas.Profile:
    user, conn = uc
    has_location = body.neighborhood_lat is not None or body.neighborhood_lon is not None
    if has_location and not body.consent_location:
        raise HTTPException(status_code=422, detail="a location is stored only with consent_location")
    values = body.model_dump()
    values["flex_defaults"] = Jsonb(values["flex_defaults"])
    cols = ", ".join(_PROFILE_COLS)
    placeholders = ", ".join(f"%({c})s" for c in _PROFILE_COLS)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in _PROFILE_COLS)
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            f"INSERT INTO profiles (user_id, {cols}) VALUES (%(user_id)s, {placeholders})"
            f" ON CONFLICT (user_id) DO UPDATE SET {updates} RETURNING *",
            {"user_id": user.id, **values},
        ).fetchone()
    return _profile(row, user)


def _load_lists(conn: psycopg.Connection, user: User, list_id: int | None = None) -> list[schemas.ShoppingList]:
    with conn.cursor(row_factory=dict_row) as cur:
        lists = cur.execute(
            "SELECT id, name, is_recurring, created_at, updated_at FROM lists"
            " WHERE user_id = %s AND (%s::bigint IS NULL OR id = %s) ORDER BY updated_at DESC, id",
            (user.id, list_id, list_id),
        ).fetchall()
        items = cur.execute(
            "SELECT id, list_id, canonical_id, input_text, quantity, flex_level, confirmed, sort"
            " FROM list_items WHERE list_id = ANY(%s) ORDER BY list_id, sort, id",
            ([lst["id"] for lst in lists],),
        ).fetchall()
    by_list: dict[int, list[schemas.ListItem]] = {}
    for it in items:
        lid = it.pop("list_id")
        by_list.setdefault(lid, []).append(schemas.ListItem(**it))
    return [schemas.ShoppingList(**lst, items=by_list.get(lst["id"], [])) for lst in lists]


def _write_items(conn: psycopg.Connection, user: User, list_id: int, items: list[schemas.ListItemIn]) -> None:
    conn.execute("DELETE FROM list_items WHERE list_id = %s", (list_id,))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO list_items (list_id, user_id, canonical_id, input_text, quantity,"
            " flex_level, confirmed, sort) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (list_id, user.id, it.canonical_id, it.input_text, it.quantity, it.flex_level,
                 it.confirmed, n)
                for n, it in enumerate(items)
            ],
        )


@router.get("/lists", response_model=list[schemas.ShoppingList])
def list_lists(uc: UserConn) -> list[schemas.ShoppingList]:
    user, conn = uc
    return _load_lists(conn, user)


@router.post("/lists", response_model=schemas.ShoppingList, status_code=201)
def create_list(body: schemas.ShoppingListIn, uc: UserConn) -> schemas.ShoppingList:
    user, conn = uc
    list_id = conn.execute(
        "INSERT INTO lists (user_id, name, is_recurring) VALUES (%s, %s, %s) RETURNING id",
        (user.id, body.name, body.is_recurring),
    ).fetchone()[0]
    _write_items(conn, user, list_id, body.items)
    return _load_lists(conn, user, list_id)[0]


@router.get("/lists/{list_id}", response_model=schemas.ShoppingList)
def get_list(list_id: int, uc: UserConn) -> schemas.ShoppingList:
    user, conn = uc
    found = _load_lists(conn, user, list_id)
    if not found:
        raise HTTPException(status_code=404, detail="list not found")
    return found[0]


@router.put("/lists/{list_id}", response_model=schemas.ShoppingList)
def update_list(list_id: int, body: schemas.ShoppingListIn, uc: UserConn) -> schemas.ShoppingList:
    """Replace the list's name, recurrence and items."""
    user, conn = uc
    updated = conn.execute(
        "UPDATE lists SET name = %s, is_recurring = %s WHERE id = %s AND user_id = %s",
        (body.name, body.is_recurring, list_id, user.id),
    ).rowcount
    if not updated:
        raise HTTPException(status_code=404, detail="list not found")
    _write_items(conn, user, list_id, body.items)
    return _load_lists(conn, user, list_id)[0]


@router.delete("/lists/{list_id}", status_code=204)
def delete_list(list_id: int, uc: UserConn) -> Response:
    user, conn = uc
    deleted = conn.execute(
        "DELETE FROM lists WHERE id = %s AND user_id = %s", (list_id, user.id)
    ).rowcount
    if not deleted:
        raise HTTPException(status_code=404, detail="list not found")
    return Response(status_code=204)
