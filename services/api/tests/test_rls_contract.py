"""Row-level security contract on the phase 1 user tables (issue #64).

The migration creates a stand-in auth.uid() when Supabase's is absent, so these run locally too.
Every check runs through ``smartcart_app`` (migration 20261007110100_app_role.sql), the
non-superuser, non-BYPASSRLS role the API switches to for signed-in requests: ``SET LOCAL ROLE``
inside the test's rolled-back transaction. So these tests never skip because the test connection
is a superuser, locally or in CI. The API-level checks (JWT -> role -> RLS) are in test_me.py.
"""

import uuid

import psycopg
import pytest

pytestmark = pytest.mark.db

APP_ROLE = "smartcart_app"


def _as_user(conn: psycopg.Connection, user_id: uuid.UUID | None) -> None:
    conn.execute(f"SET LOCAL ROLE {APP_ROLE}")
    conn.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(user_id) if user_id else "",))


def _as_owner(conn: psycopg.Connection) -> None:
    conn.execute("RESET ROLE")


@pytest.fixture
def two_users(db: psycopg.Connection) -> tuple[uuid.UUID, uuid.UUID]:
    a, b = uuid.uuid4(), uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s), (%s)", (a, b))
    # Seed one list per user as the connecting role; under FORCE RLS a non-superuser owner needs
    # the matching auth.uid() too, so seed each row as its user.
    for uid, name in ((a, "A"), (b, "B")):
        _as_user(db, uid)
        db.execute("INSERT INTO lists (user_id, name) VALUES (%s, %s)", (uid, name))
    _as_owner(db)
    return a, b


def test_app_role_is_not_privileged(db: psycopg.Connection) -> None:
    sup, bypass = db.execute(
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s", (APP_ROLE,)
    ).fetchone()
    assert not sup and not bypass


def test_user_sees_only_own_rows(db: psycopg.Connection, two_users) -> None:
    a, b = two_users
    _as_user(db, a)
    assert [r[0] for r in db.execute("SELECT name FROM lists").fetchall()] == ["A"]
    _as_user(db, b)
    assert [r[0] for r in db.execute("SELECT name FROM lists").fetchall()] == ["B"]


def test_user_cannot_write_other_users_rows(db: psycopg.Connection, two_users) -> None:
    a, b = two_users
    _as_user(db, a)
    # UPDATE and DELETE of B's row silently match nothing.
    assert db.execute("UPDATE lists SET name = 'hacked' WHERE user_id = %s", (b,)).rowcount == 0
    assert db.execute("DELETE FROM lists WHERE user_id = %s", (b,)).rowcount == 0
    # INSERT as B is rejected by WITH CHECK.
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.transaction():
            db.execute("INSERT INTO lists (user_id, name) VALUES (%s, 'forged')", (b,))
    _as_user(db, b)
    assert [r[0] for r in db.execute("SELECT name FROM lists").fetchall()] == ["B"]


def test_anonymous_sees_nothing(db: psycopg.Connection, two_users) -> None:
    _as_user(db, None)
    assert db.execute("SELECT count(*) FROM lists").fetchone()[0] == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.transaction():
            db.execute("INSERT INTO lists (user_id, name) VALUES (%s, 'anon')", (two_users[0],))


@pytest.mark.parametrize("table", ["profiles", "list_items", "preferences"])
def test_every_user_table_is_isolated(db: psycopg.Connection, two_users, table: str) -> None:
    a, b = two_users
    _as_user(db, b)
    if table == "profiles":
        db.execute("INSERT INTO profiles (user_id) VALUES (%s)", (b,))
    elif table == "preferences":
        db.execute("INSERT INTO preferences (user_id) VALUES (%s)", (b,))
    else:
        list_id = db.execute("SELECT id FROM lists").fetchone()[0]
        db.execute(
            "INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'חלב')",
            (list_id, b),
        )
    assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 1
    _as_user(db, a)
    assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    _as_user(db, None)
    assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_profile_location_is_rounded(db: psycopg.Connection, two_users) -> None:
    a, _ = two_users
    _as_user(db, a)
    db.execute(
        "INSERT INTO profiles (user_id, neighborhood_lat, neighborhood_lon) VALUES (%s, 32.0712345, 34.7812345)",
        (a,),
    )
    lat, lon = db.execute("SELECT neighborhood_lat, neighborhood_lon FROM profiles WHERE user_id = %s", (a,)).fetchone()
    assert str(lat) == "32.071" and str(lon) == "34.781"


def test_catalog_tables_exist(db: psycopg.Connection) -> None:
    for t in ("taxonomy", "canonical_products", "item_attributes", "item_embeddings", "item_canonical",
              "gold_pairs", "substitution_feedback", "effective_prices", "match_runs", "profiles",
              "lists", "list_items", "preferences", "gap_reports"):
        assert db.execute("SELECT to_regclass(%s) IS NOT NULL", (t,)).fetchone()[0], t
