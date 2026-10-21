"""Saved lists and their items, shared by ``routes/me.py`` and ``routes/shares.py``: reading, the
caller's role on a list, and writing items (the whole set id-stably, or one item).

Runs under the caller's row-level security context: the owner sees their lists, an accepted
member sees the lists shared with them (``lists_shared`` policy) and their own share row
(``list_shares_member``), which gives their role. ``role`` is ``owner`` for the user's own lists,
else the member's role; ``shared`` is true for lists another user owns.
"""

from __future__ import annotations

from typing import Literal

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row

from smartcart_api import schemas
from smartcart_api.auth import User

ITEM_COLS = (
    "id, list_id, canonical_id, input_text, quantity, flex_level, confirmed, checked, sort,"
    " updated_at, client_id"
)
MAX_ITEMS_PER_LIST = 200  # the same cap as ShoppingListIn.items
Role = Literal["owner", "editor", "viewer"]


def load_lists(
    conn: psycopg.Connection,
    user: User,
    ids: list[int] | None = None,
    *,
    include_shared: bool = True,
    owned: bool = True,
) -> list[schemas.ShoppingList]:
    """The user's lists (``owned``) and the accepted shared lists (``include_shared``), optionally
    restricted to ``ids``. Owned lists come first, each group newest first."""
    with conn.cursor(row_factory=dict_row) as cur:
        lists = cur.execute(
            "SELECT l.id, l.name, l.is_recurring, l.created_at, l.updated_at,"
            "  CASE WHEN l.user_id = %(uid)s THEN 'owner' ELSE m.role END AS role"
            " FROM lists AS l"
            " LEFT JOIN LATERAL ("
            "   SELECT s.role FROM list_shares AS s"
            "   WHERE s.list_id = l.id AND s.member_id = %(uid)s AND s.accepted_at IS NOT NULL"
            "   ORDER BY s.role = 'editor' DESC LIMIT 1) AS m ON true"
            " WHERE (%(ids)s::bigint[] IS NULL OR l.id = ANY(%(ids)s))"
            "   AND ((%(owned)s AND l.user_id = %(uid)s)"
            "     OR (%(shared)s AND l.user_id <> %(uid)s AND m.role IS NOT NULL))"
            " ORDER BY l.user_id = %(uid)s DESC, l.updated_at DESC, l.id",
            {"uid": user.id, "ids": ids, "owned": owned, "shared": include_shared},
        ).fetchall()
        items = cur.execute(
            f"SELECT {ITEM_COLS} FROM list_items WHERE list_id = ANY(%s)"
            " ORDER BY list_id, sort, id",
            ([lst["id"] for lst in lists],),
        ).fetchall()
    by_list: dict[int, list[schemas.ListItem]] = {}
    for it in items:
        lid = it.pop("list_id")
        by_list.setdefault(lid, []).append(schemas.ListItem(**it))
    return [
        schemas.ShoppingList(**lst, shared=lst["role"] != "owner", items=by_list.get(lst["id"], []))
        for lst in lists
    ]


def lock_list_items(conn: psycopg.Connection, list_id: int) -> None:
    """Serializes the writers that count or renumber a list's items (the size cap, the sort
    position of a new item) until the transaction ends. The key is per list; a clash between two
    lists only makes them wait for each other."""
    conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (0x6C69, list_id % 2**31))


def list_role(conn: psycopg.Connection, user: User, list_id: int) -> Role | None:
    """The caller's access to the list: ``owner``, the role of their accepted share, or None when
    the list does not exist or row-level security hides it from them."""
    row = conn.execute(
        "SELECT CASE WHEN l.user_id = %(uid)s THEN 'owner' ELSE ("
        "   SELECT s.role FROM list_shares AS s"
        "   WHERE s.list_id = l.id AND s.member_id = %(uid)s AND s.accepted_at IS NOT NULL"
        "   ORDER BY s.role = 'editor' DESC LIMIT 1) END"
        " FROM lists AS l WHERE l.id = %(id)s",
        {"uid": user.id, "id": list_id},
    ).fetchone()
    return row[0] if row else None


def require_editor(conn: psycopg.Connection, user: User, list_id: int) -> Role:
    """The caller's role when they may change the list's items (owner or editor). A list the
    caller cannot see is a 404, like every other list route; a viewer can see it, so gets a 403."""
    role = list_role(conn, user, list_id)
    if role is None:
        raise HTTPException(status_code=404, detail="list not found")
    if role == "viewer":
        raise HTTPException(status_code=403, detail="this list is shared with you as a viewer")
    return role


def item_from_row(row: dict) -> schemas.ListItem:
    return schemas.ListItem(**{k: v for k, v in row.items() if k != "list_id"})


def write_items(
    conn: psycopg.Connection, user: User, list_id: int, items: list[schemas.ListItemIn]
) -> None:
    """Makes the list's items exactly ``items``, in that order, keeping ids: an entry with the id
    of one of this list's items updates that row (only when something changed, so an unchanged
    item keeps its ``updated_at`` and sends nothing to Realtime subscribers); an entry with no id,
    or one this list does not have (never another list's row), is inserted; a row no entry names
    is deleted. The author (``user_id``) of a kept row stays."""
    ids = [it.id for it in items if it.id is not None]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="an item id appears twice")
    lock_list_items(conn, list_id)
    existing = {
        r[0] for r in conn.execute("SELECT id FROM list_items WHERE list_id = %s", (list_id,))
    }
    kept: list[int] = []
    with conn.cursor() as cur:
        for n, it in enumerate(items):
            values = (
                it.canonical_id,
                it.input_text,
                it.quantity,
                it.flex_level,
                it.confirmed,
                it.checked,
                n,
            )
            if it.id is not None and it.id in existing:
                cur.execute(
                    "UPDATE list_items SET canonical_id = %s, input_text = %s, quantity = %s,"
                    " flex_level = %s, confirmed = %s, checked = %s, sort = %s"
                    " WHERE id = %s AND list_id = %s AND ("
                    "   canonical_id IS DISTINCT FROM %s::bigint"
                    "   OR input_text IS DISTINCT FROM %s::text"
                    "   OR quantity IS DISTINCT FROM %s::numeric"
                    "   OR flex_level IS DISTINCT FROM %s::text"
                    "   OR confirmed IS DISTINCT FROM %s::boolean"
                    "   OR checked IS DISTINCT FROM %s::boolean"
                    "   OR sort IS DISTINCT FROM %s::integer)",
                    (*values, it.id, list_id, *values),
                )
                kept.append(it.id)
            else:
                new_id = cur.execute(
                    "INSERT INTO list_items (list_id, user_id, canonical_id, input_text, quantity,"
                    " flex_level, confirmed, checked, sort)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (list_id, user.id, *values),
                ).fetchone()[0]
                kept.append(new_id)
        cur.execute(
            "DELETE FROM list_items WHERE list_id = %s AND NOT (id = ANY(%s))", (list_id, kept)
        )
