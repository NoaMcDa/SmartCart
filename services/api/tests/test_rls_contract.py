"""Row-level security contract on the phase 1 user tables (issue #64, baseline checks).

The migration creates a stand-in auth.uid() when Supabase's is absent, so these run locally too.
Workstream W3 extends them with PostgREST-level checks in CI.
"""

import uuid

import psycopg
import pytest

pytestmark = pytest.mark.db


def _as_user(conn: psycopg.Connection, user_id: uuid.UUID | None) -> None:
    conn.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(user_id) if user_id else "",))


@pytest.fixture
def two_users(db: psycopg.Connection) -> tuple[uuid.UUID, uuid.UUID]:
    a, b = uuid.uuid4(), uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s), (%s)", (a, b))
    # Bypass RLS as the table owner to seed one list per user.
    db.execute("INSERT INTO lists (user_id, name) VALUES (%s, 'A'), (%s, 'B')", (a, b))
    return a, b


def _rls_enforced_for_owner(conn: psycopg.Connection) -> bool:
    """FORCE ROW LEVEL SECURITY applies to the table owner too, unless the role is a superuser
    or has BYPASSRLS (the Supabase image's postgres role has both)."""
    row = conn.execute(
        "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
    ).fetchone()
    return not row[0]


def test_user_sees_only_own_rows(db: psycopg.Connection, two_users) -> None:
    if not _rls_enforced_for_owner(db):
        pytest.skip("superuser bypasses RLS; the CI job runs this as a non-superuser role")
    a, b = two_users
    _as_user(db, a)
    names = [r[0] for r in db.execute("SELECT name FROM lists").fetchall()]
    assert names == ["A"]


def test_anonymous_sees_nothing(db: psycopg.Connection, two_users) -> None:
    if not _rls_enforced_for_owner(db):
        pytest.skip("superuser bypasses RLS; the CI job runs this as a non-superuser role")
    _as_user(db, None)
    assert db.execute("SELECT count(*) FROM lists").fetchone()[0] == 0


def test_profile_location_is_rounded(db: psycopg.Connection, two_users) -> None:
    a, _ = two_users
    db.execute(
        "INSERT INTO profiles (user_id, neighborhood_lat, neighborhood_lon) VALUES (%s, 32.0712345, 34.7812345)",
        (a,),
    )
    lat, lon = db.execute("SELECT neighborhood_lat, neighborhood_lon FROM profiles WHERE user_id = %s", (a,)).fetchone()
    assert str(lat) == "32.071" and str(lon) == "34.781"


def test_catalog_tables_exist(db: psycopg.Connection) -> None:
    for t in ("taxonomy", "canonical_products", "item_attributes", "item_embeddings", "item_canonical",
              "gold_pairs", "substitution_feedback", "effective_prices", "match_runs", "profiles",
              "lists", "list_items", "preferences"):
        assert db.execute("SELECT to_regclass(%s) IS NOT NULL", (t,)).fetchone()[0], t
