"""Migration 20261022100000: a club name flattened by the older ingest fails closed."""

from __future__ import annotations

from pathlib import Path

import pytest
from api_world import World
from psycopg.types.json import Jsonb

from smartcart_api.basket import club_member
from smartcart_api.precompute import precompute_effective_prices

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]

SQL = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "20261022100000_club_rules.sql"
).read_text(encoding="utf-8")


def test_a_flattened_expression_is_reset_to_unknown(db, world: World) -> None:
    promo = world.promos["eggs_club"]
    # What the older ingest wrote for "((A|B))&(C|D)": the names flattened to "A | B | C | D".
    db.execute(
        "UPDATE promos SET club_name = %s, raw = %s WHERE id = %s",
        (
            "מועדון א | מועדון ב | כרטיס ג | כרטיס ד",
            Jsonb({"club_expression": "((..))&(..)"}),
            promo,
        ),
    )
    precompute_effective_prices(db, chains=world.chains)
    before = db.execute(
        "SELECT club_required, club_name FROM effective_prices WHERE promo_id = %s", (promo,)
    ).fetchall()
    assert before and all(r[0] and "|" in r[1] for r in before)
    # Read as written, the flattened name would now be an OR: the hole the migration closes.
    assert club_member("מועדון א | מועדון ב | כרטיס ג | כרטיס ד", ["מועדון א"])

    db.execute(SQL)

    assert db.execute("SELECT club_name FROM promos WHERE id = %s", (promo,)).fetchone() == ("אחר",)
    rows = db.execute(
        "SELECT club_name, noclub FROM effective_prices WHERE promo_id = %s", (promo,)
    ).fetchall()
    assert rows and all(name == "אחר" and "clubs" not in (noclub or {}) for name, noclub in rows)
    assert not club_member("אחר", ["אחר", "מועדון א"])
    # a promo that was not an expression is left alone
    other = db.execute(
        "SELECT count(*) FROM promos WHERE club_only AND club_name = 'אחר' AND id <> %s", (promo,)
    ).fetchone()[0]
    assert other == 0
