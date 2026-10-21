"""Row-level security on EVERY user table, through the non-superuser role the API uses.

``test_rls_contract.py`` covers profiles, lists, list_items and preferences (issue #64). The tables
the later phases added (price_alerts, push_subscriptions, list_shares, spend_entries,
substitution_feedback, beta_members) had no cross-user test at the database level, and one of them,
list_shares, had a policy that let a user write a row for somebody else's list (finding S1,
migration 20261021120000). This file closes both gaps:

* ``test_every_table_with_a_user_column_is_covered`` fails when a new table with a user column
  appears without a case below, so the next user table cannot ship untested;
* each covered table is checked for: another user sees nothing, cannot update or delete the row,
  cannot insert a row for somebody else, and an anonymous caller (no ``auth.uid()``) sees nothing;
* the private tables (events, ocr_usage, beta_invites, beta_feedback, search_misses, gap_reports)
  are invisible to the app role.

Everything runs inside the test's rolled-back transaction as ``smartcart_app`` (``SET LOCAL ROLE``).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from pathlib import Path

import psycopg
import pytest
from api_world import World

pytestmark = pytest.mark.db

APP_ROLE = "smartcart_app"
MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "20261021120000_list_shares_owner_check.sql"
)


def _as_user(db: psycopg.Connection, uid: uuid.UUID | None) -> None:
    db.execute("RESET ROLE")
    db.execute(f"SET LOCAL ROLE {APP_ROLE}")
    db.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(uid) if uid else "",))


def _owner(db: psycopg.Connection) -> None:
    db.execute("RESET ROLE")


@pytest.fixture
def two_users(db: psycopg.Connection) -> tuple[uuid.UUID, uuid.UUID]:
    a, b = uuid.uuid4(), uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s), (%s)", (a, b))
    return a, b


# --- one case per user table: how B writes a row, and how A would forge one ---------------------
# insert(db, owner_uid, world) -> primary-key tuple; every insert runs as owner_uid.


def _list(db: psycopg.Connection, uid: uuid.UUID) -> int:
    return db.execute(
        "INSERT INTO lists (user_id, name) VALUES (%s, 'L') RETURNING id", (uid,)
    ).fetchone()[0]


def _ins_profiles(db, uid, w):
    db.execute("INSERT INTO profiles (user_id) VALUES (%s)", (uid,))


def _ins_lists(db, uid, w):
    _list(db, uid)


def _ins_list_items(db, uid, w):
    db.execute(
        "INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'חלב')",
        (_list(db, uid), uid),
    )


def _ins_preferences(db, uid, w):
    db.execute("INSERT INTO preferences (user_id) VALUES (%s)", (uid,))


def _ins_price_alerts(db, uid, w):
    db.execute(
        "INSERT INTO price_alerts (user_id, canonical_id, threshold_unit_price) VALUES (%s, %s, 1)",
        (uid, w.canon["milk3"]),
    )


def _ins_push_subscriptions(db, uid, w):
    db.execute(
        "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth)"
        " VALUES (%s, %s, 'k', 'a')",
        (uid, f"https://push.example/{uuid.uuid4()}"),
    )


def _ins_list_shares(db, uid, w):
    db.execute(
        "INSERT INTO list_shares (list_id, owner_id, invite_token) VALUES (%s, %s, %s)",
        (_list(db, uid), uid, uuid.uuid4().hex),
    )


def _ins_spend_entries(db, uid, w):
    db.execute(
        "INSERT INTO spend_entries (user_id, date, store_id, store_name, total, item_count, plan)"
        " VALUES (%s, %s, %s, 'x', 10, 1, 'single')",
        (uid, date(2026, 10, 1), next(iter(w.stores.values()))),
    )


def _ins_substitution_feedback(db, uid, w):
    db.execute(
        "INSERT INTO substitution_feedback (user_id, verdict) VALUES (%s, 'accepted')", (uid,)
    )


CASES: dict[str, tuple[Callable, str]] = {
    # table: (insert as that user, the column that holds the owner)
    "profiles": (_ins_profiles, "user_id"),
    "lists": (_ins_lists, "user_id"),
    "list_items": (_ins_list_items, "user_id"),
    "preferences": (_ins_preferences, "user_id"),
    "price_alerts": (_ins_price_alerts, "user_id"),
    "push_subscriptions": (_ins_push_subscriptions, "user_id"),
    "list_shares": (_ins_list_shares, "owner_id"),
    "spend_entries": (_ins_spend_entries, "user_id"),
    "substitution_feedback": (_ins_substitution_feedback, "user_id"),
}

# Tables with a user column that the app role never reaches at all (no grant, or RLS with no
# policy): asserted invisible below instead of cross-user.
PRIVATE = {
    "events",
    "gap_reports",
    "beta_members",  # SELECT and DELETE of the own row only; checked in its own test
    "beta_invites",
    "beta_feedback",
    "search_misses",
    "ocr_usage",
}


def test_every_table_with_a_user_column_is_covered(db: psycopg.Connection) -> None:
    """A new table with user_id/owner_id/member_id must be added to CASES or to PRIVATE."""
    rows = db.execute(
        "SELECT DISTINCT c.table_name FROM information_schema.columns c"
        " JOIN information_schema.tables t USING (table_schema, table_name)"
        " WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'"
        "   AND c.column_name IN ('user_id', 'owner_id', 'member_id')"
    ).fetchall()
    unknown = {r[0] for r in rows} - set(CASES) - PRIVATE
    assert not unknown, (
        f"add a cross-user RLS case to test_api_security_rls.py for: {sorted(unknown)}"
    )


@pytest.mark.parametrize("table", sorted(CASES))
def test_rls_is_on_and_forced_for_user_tables(db: psycopg.Connection, table: str) -> None:
    on, forced = db.execute(
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = %s::regclass",
        (table,),
    ).fetchone()
    assert on and forced, table


@pytest.mark.parametrize("table", sorted(CASES))
def test_another_user_sees_and_changes_nothing(
    db: psycopg.Connection, two_users, world: World, table: str
) -> None:
    a, b = two_users
    insert, owner_col = CASES[table]
    _as_user(db, b)
    insert(db, b, world)
    assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] >= 1

    _as_user(db, a)
    assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0, "A reads B's rows"
    assert db.execute(f"DELETE FROM {table} WHERE {owner_col} = %s", (b,)).rowcount == 0
    # UPDATE of the owner column to A would be a hijack of B's row: it matches no row either.
    assert (
        db.execute(f"UPDATE {table} SET {owner_col} = %s WHERE {owner_col} = %s", (a, b)).rowcount
        == 0
    )
    _as_user(db, None)
    assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0, "anonymous reads rows"

    _as_user(db, b)
    assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] >= 1, "B lost the row"


@pytest.mark.parametrize("table", sorted(set(CASES) - {"list_items", "list_shares"}))
def test_a_row_cannot_be_written_for_another_user(
    db: psycopg.Connection, two_users, world: World, table: str
) -> None:
    a, b = two_users
    insert, _ = CASES[table]
    _as_user(db, a)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.transaction():
            insert(db, b, world)  # A is signed in, the row says B
    _as_user(db, None)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.transaction():
            insert(db, b, world)


def test_a_list_item_cannot_be_added_to_another_users_list(
    db: psycopg.Connection, two_users
) -> None:
    a, b = two_users
    _as_user(db, b)
    victim_list = _list(db, b)
    _as_user(db, a)
    for as_user in (a, b):  # the row names A, or B: both are refused
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.transaction():
                db.execute(
                    "INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'x')",
                    (victim_list, as_user),
                )


def test_a_user_cannot_forge_a_membership_of_somebody_elses_list(
    db: psycopg.Connection, two_users
) -> None:
    """Finding S1. Before migration 20261021120000 this INSERT succeeded and gave A the list."""
    a, b = two_users
    _as_user(db, b)
    victim_list = _list(db, b)
    db.execute(
        "INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'secret')",
        (victim_list, b),
    )

    _as_user(db, a)
    for owner_id in (a, b):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.transaction():
                db.execute(
                    "INSERT INTO list_shares (list_id, owner_id, member_id, accepted_at, invite_token)"
                    " VALUES (%s, %s, %s, now(), %s)",
                    (victim_list, owner_id, a, uuid.uuid4().hex),
                )
    assert db.execute("SELECT count(*) FROM lists").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM list_items").fetchone()[0] == 0

    # Re-pointing a share A legitimately owns at B's list is refused as well (WITH CHECK of UPDATE).
    own_list = _list(db, a)
    db.execute(
        "INSERT INTO list_shares (list_id, owner_id, invite_token) VALUES (%s, %s, 'mine')",
        (own_list, a),
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.transaction():
            db.execute(
                "UPDATE list_shares SET list_id = %s, member_id = %s, accepted_at = now()"
                " WHERE invite_token = 'mine'",
                (victim_list, a),
            )
    assert db.execute("SELECT count(*) FROM lists WHERE user_id = %s", (b,)).fetchone()[0] == 0


def test_the_migration_removes_forged_shares(db: psycopg.Connection, two_users) -> None:
    """Running 20261021120000 again: a row whose owner does not own the list goes, an honest one
    stays, and the migration can be re-run."""
    a, b = two_users
    _as_user(db, b)
    victim_list = _list(db, b)
    _owner(db)  # the migrating role bypasses row-level security (BYPASSRLS or superuser)
    db.execute(
        "INSERT INTO list_shares (list_id, owner_id, member_id, accepted_at, invite_token)"
        " VALUES (%s, %s, %s, now(), 'forged')",
        (victim_list, a, a),
    )
    db.execute(
        "INSERT INTO list_shares (list_id, owner_id, invite_token) VALUES (%s, %s, 'honest')",
        (victim_list, b),
    )
    db.execute(MIGRATION.read_text(encoding="utf-8"))
    assert [r[0] for r in db.execute("SELECT invite_token FROM list_shares").fetchall()] == [
        "honest"
    ]


def test_a_viewer_reads_and_an_editor_writes_but_neither_owns(
    db: psycopg.Connection, two_users
) -> None:
    a, b = two_users
    _as_user(db, b)
    lid = _list(db, b)
    db.execute(
        "INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'חלב')", (lid, b)
    )
    db.execute(
        "INSERT INTO list_shares (list_id, owner_id, member_id, accepted_at, invite_token, role)"
        " VALUES (%s, %s, %s, now(), 'v', 'viewer')",
        (lid, b, a),
    )
    _as_user(db, a)
    assert db.execute("SELECT count(*) FROM list_items").fetchone()[0] == 1
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.transaction():
            db.execute(
                "INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'x')",
                (lid, a),
            )
    # a viewer cannot rename or delete the list, and cannot hand the list to somebody else
    assert db.execute("UPDATE lists SET name = 'mine' WHERE id = %s", (lid,)).rowcount == 0
    assert db.execute("DELETE FROM lists WHERE id = %s", (lid,)).rowcount == 0
    assert db.execute("DELETE FROM list_shares WHERE list_id = %s", (lid,)).rowcount == 0

    _as_user(db, b)
    db.execute("UPDATE list_shares SET role = 'editor' WHERE invite_token = 'v'")
    _as_user(db, a)
    db.execute(
        "INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'ביצים')", (lid, a)
    )
    assert db.execute("UPDATE lists SET name = 'mine' WHERE id = %s", (lid,)).rowcount == 0
    assert db.execute("DELETE FROM lists WHERE id = %s", (lid,)).rowcount == 0


@pytest.mark.parametrize(
    "table",
    ["events", "gap_reports", "beta_invites", "beta_feedback", "search_misses", "ocr_usage"],
)
def test_private_tables_are_closed_to_the_app_role(
    db: psycopg.Connection, two_users, table: str
) -> None:
    a, _ = two_users
    _as_user(db, a)
    # either no privilege at all, or row-level security with no policy: nothing is readable
    try:
        with db.transaction():
            n = db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    except psycopg.errors.InsufficientPrivilege:
        return
    assert n == 0


def test_beta_membership_is_readable_and_deletable_by_its_owner_only(
    db: psycopg.Connection, two_users
) -> None:
    a, b = two_users
    _owner(db)
    db.execute(
        "INSERT INTO beta_invites (code, segment, max_uses) VALUES ('SECURITY-1', 'general', 5)"
    )
    db.execute(
        "INSERT INTO beta_members (user_id, code, segment)"
        " VALUES (%s, 'SECURITY-1', 'general'), (%s, 'SECURITY-1', 'general')",
        (a, b),
    )
    _as_user(db, a)
    assert [r[0] for r in db.execute("SELECT user_id FROM beta_members").fetchall()] == [a]
    assert db.execute("DELETE FROM beta_members WHERE user_id = %s", (b,)).rowcount == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):  # nobody joins through the data API
        with db.transaction():
            db.execute(
                "INSERT INTO beta_members (user_id, code, segment)"
                " VALUES (%s, 'SECURITY-1', 'general')",
                (uuid.uuid4(),),
            )
    assert db.execute("DELETE FROM beta_members WHERE user_id = %s", (a,)).rowcount == 1
    _as_user(db, None)
    assert db.execute("SELECT count(*) FROM beta_members").fetchone()[0] == 0
