"""Reading saved lists with their items, shared by ``routes/me.py`` and ``routes/shares.py``.

Runs under the caller's row-level security context: the owner sees their lists, an accepted
member sees the lists shared with them (``lists_shared`` policy) and their own share row
(``list_shares_member``), which gives their role. ``role`` is ``owner`` for the user's own lists,
else the member's role; ``shared`` is true for lists another user owns.
"""

from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from smartcart_api import schemas
from smartcart_api.auth import User

_ITEM_COLS = "id, list_id, canonical_id, input_text, quantity, flex_level, confirmed, checked, sort"


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
            f"SELECT {_ITEM_COLS} FROM list_items WHERE list_id = ANY(%s)"
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
