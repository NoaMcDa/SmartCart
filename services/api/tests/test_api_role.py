"""The API's least-privilege database role (migration 20261011100500, docs/deploy.md).

The grants are tested on a throwaway role made by the same function the migration calls
(``smartcart_grant_api_role``). The whole API suite can also run as that role:

    SMARTCART_TEST_AS_API_ROLE=1 uv run pytest services/api/tests

(one test, the stand-in ``auth.users`` delete of ``DELETE /me`` without the Supabase Admin API,
differs on purpose: the role must not delete auth users).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import psycopg
import pytest
from api_world import World, assume_role, make_token, release_role
from test_me_delete import COUNTS, counts, seed_user

from smartcart_api.routes import me_delete

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]

MIGRATION = Path(__file__).resolve().parents[3] / "supabase" / "migrations" / "20261011100500_api_role.sql"


def h(user_id) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


@pytest.fixture
def users(db, monkeypatch) -> tuple[uuid.UUID, uuid.UUID]:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    a, b = uuid.uuid4(), uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s), (%s)", (a, b))
    return a, b


def allowed(db: psycopg.Connection, sql: str, params=()) -> None:
    with db.transaction():  # a savepoint: a refusal must not abort the test's transaction
        db.execute(sql, params)


def refused(db: psycopg.Connection, sql: str, params=()) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute(sql, params)


# --- the function and the migration -------------------------------------------------------------


def test_granting_twice_is_fine_and_an_unknown_role_is_an_error(db, api_role: str) -> None:
    db.execute("SELECT smartcart_grant_api_role(%s)", (api_role,))
    db.execute("SELECT smartcart_grant_api_role(%s)", (api_role,))
    names = [r[0] for r in db.execute(
        "SELECT policyname FROM pg_policies WHERE policyname LIKE %s", (f"%\\_api\\_%{api_role}",)
    ).fetchall()]
    assert len(names) == len(set(names)) == 11  # one set of policies, not two
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("SELECT smartcart_grant_api_role('no_such_role_anywhere')")


def test_the_function_is_not_for_the_public(db, api_role: str) -> None:
    assert not db.execute(
        "SELECT has_function_privilege('public', 'smartcart_grant_api_role(name)', 'EXECUTE')"
    ).fetchone()[0]


def _login_block() -> str:
    text = MIGRATION.read_text(encoding="utf-8")
    return text[text.rindex("DO $$\nDECLARE\n  pw text"):]


def test_the_migration_creates_the_login_role_only_when_a_password_is_set(db) -> None:
    notices: list[str] = []
    db.add_notice_handler(lambda d: notices.append(d.message_primary or ""))
    existed = db.execute("SELECT 1 FROM pg_roles WHERE rolname = 'smartcart_api'").fetchone()
    db.execute(_login_block())  # no setting
    if existed is None:
        assert db.execute("SELECT 1 FROM pg_roles WHERE rolname = 'smartcart_api'").fetchone() is None
        assert any("smartcart_api not created" in n for n in notices), notices

    db.execute("SELECT set_config('smartcart.api_password', 'test-password', true)")
    db.execute(_login_block())
    role = db.execute(
        "SELECT rolcanlogin, rolinherit, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls,"
        " rolreplication FROM pg_roles WHERE rolname = 'smartcart_api'"
    ).fetchone()
    assert role == (True, False, False, False, False, False, False)
    assert db.execute("SELECT pg_has_role('smartcart_api', 'smartcart_app', 'MEMBER')").fetchone()[0]
    # the membership lets it SET ROLE to smartcart_app and does not hand over smartcart_app's rights
    assert db.execute("SELECT pg_has_role('smartcart_api', 'smartcart_app', 'USAGE')").fetchone()[0] is False
    assert db.execute("SELECT has_table_privilege('smartcart_api', 'canonical_products', 'SELECT')").fetchone()[0]
    assert not db.execute("SELECT has_table_privilege('smartcart_api', 'profiles', 'SELECT')").fetchone()[0]
    # the password is stored hashed, never in clear text
    assert db.execute(
        "SELECT rolpassword IS NOT NULL AND rolpassword NOT LIKE '%test-password%'"
        " FROM pg_authid WHERE rolname = 'smartcart_api'"
    ).fetchone()[0]


# --- what the role can and cannot do -----------------------------------------------------------


def test_the_role_reads_the_catalog_and_writes_nothing_of_it(db, api_role: str, world: World) -> None:
    assume_role(db, api_role)
    try:
        assert db.execute("SELECT session_user, current_user").fetchone() == (api_role, api_role)
        for table in ("canonical_products", "taxonomy", "items", "prices", "effective_prices",
                      "item_canonical", "stores", "chains", "promos", "file_tracking"):
            allowed(db, f"SELECT count(*) FROM {table}")
        refused(db, "INSERT INTO taxonomy (id, parent_id, level, name_he) VALUES ('x', NULL, 1, 'x')")
        refused(db, "UPDATE canonical_products SET display_name_he = 'x'")
        refused(db, "DELETE FROM canonical_products")
        refused(db, "UPDATE prices SET price = 0")
        refused(db, "DELETE FROM effective_prices")
        refused(db, "UPDATE items SET raw_name = 'x'")
        refused(db, "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
                    " SELECT 1, 1, 'exact', 1, 'rule'")
        refused(db, "UPDATE item_canonical SET confidence = 0")  # only needs_review may change
        allowed(db, "UPDATE item_canonical SET needs_review = true WHERE false")
        refused(db, "SELECT * FROM gold_pairs")
        refused(db, "SELECT * FROM quality_warnings")
        refused(db, "SELECT * FROM schema_migrations")
        refused(db, "CREATE TABLE api_role_scratch (id int)")
        refused(db, "SELECT smartcart_grant_api_role('postgres')")
        refused(db, "SELECT purge_search_misses()")  # the inserts purge inline; the function is for cron
    finally:
        release_role(db)


def test_user_tables_are_reachable_only_through_smartcart_app(db, api_role: str, users) -> None:
    a, _ = users
    assume_role(db, api_role)
    try:
        for table in ("profiles", "lists", "list_items", "preferences", "price_alerts",
                      "push_subscriptions", "spend_entries"):
            refused(db, f"SELECT * FROM {table}")
        refused(db, "SELECT * FROM auth.users")  # only the id column is readable
        allowed(db, "SELECT id FROM auth.users")
        with db.transaction():
            db.execute("SET LOCAL ROLE smartcart_app")
            db.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(a),))
            assert db.execute("SELECT count(*) FROM spend_entries").fetchone()[0] == 0
            db.execute("RESET ROLE")
    finally:
        release_role(db)


def test_the_role_writes_its_own_tables_only(db, api_role: str, world: World) -> None:
    assume_role(db, api_role)
    try:
        allowed(db, "INSERT INTO events (session_id, name, props) VALUES ('abcdefgh', 'app_opened', '{}')")
        allowed(db, "SELECT count(*) FROM events")
        refused(db, "DELETE FROM events")
        refused(db, "UPDATE events SET name = 'x'")
        allowed(db, "INSERT INTO search_misses (query_norm, source) VALUES ('x y', 'search')")
        allowed(db, "DELETE FROM search_misses")
        allowed(db, "INSERT INTO gap_reports (store_id, note) VALUES (%s, 'x')", (world.stores["home"],))
        refused(db, "DELETE FROM gap_reports")
        allowed(db, "INSERT INTO substitution_feedback (canonical_id, substitute_item_id, verdict)"
                    " VALUES (%s, %s, 'accepted') RETURNING id",
                (world.canon["salmon"], world.items["salmon_c2_frozen"]))
        refused(db, "SELECT verdict FROM substitution_feedback")  # only the id column
        refused(db, "DELETE FROM substitution_feedback")
        refused(db, "DELETE FROM profiles")
    finally:
        release_role(db)


# --- the routes, as the role -------------------------------------------------------------------


def test_routes_tour_as_the_api_role(client_as_api_role, db, world: World, users, monkeypatch) -> None:
    client = client_as_api_role
    a, b = users
    # anonymous routes
    assert client.get("/search", params={"q": "חלב"}).json()["hits"]
    assert client.get("/search", params={"q": "xqzvbn plorf"}).json()["hits"] == []  # a logged miss
    assert db.execute("SELECT count(*) FROM search_misses").fetchone()[0] == 1
    assert client.post("/parse-list", json={"text": "חלב\nxqzvbn plorf"}).status_code == 200
    assert client.post("/events", json={"events": [{"name": "app_opened", "session_id": "abcdefgh1"}]},
                       headers=h(a)).status_code == 200
    assert db.execute("SELECT user_id FROM events").fetchone()[0] == a  # the user id passes the auth.users check
    assert client.post("/feedback/gap", json={"store_id": world.stores["home"]}).status_code == 200
    assert client.post("/feedback/substitution", headers=h(a), json={
        "canonical_id": world.canon["salmon"], "substitute_item_id": world.items["salmon_c2_frozen"],
        "verdict": "not_good"}).status_code == 200
    assert db.execute("SELECT needs_review FROM item_canonical WHERE item_id = %s",
                      (world.items["salmon_c2_frozen"],)).fetchone()[0]
    # user routes under RLS, the idempotent spend entry, the service-connection corners
    list_a = seed_user(client, db, world, a)
    seed_user(client, db, world, b)
    cid = str(uuid.uuid4())
    body = {"date": "2026-10-03", "store_id": world.stores["home"], "store_name": "x", "total": "5",
            "item_count": 1, "plan": "single", "client_id": cid}
    assert client.post("/me/spend", json=body, headers=h(a)).status_code == 201
    assert client.post("/me/spend", json=body, headers=h(a)).status_code == 200
    # another account registers the same push endpoint: the first registration is taken over
    endpoint = f"https://push.example/{a}"
    assert client.post("/me/push-subscriptions", headers=h(b),
                       json={"endpoint": endpoint, "p256dh": "k", "auth": "a"}).status_code == 201
    assert db.execute("SELECT user_id FROM push_subscriptions WHERE endpoint = %s", (endpoint,)).fetchone()[0] == b
    # a pending invite is read and accepted by someone who cannot see it yet
    tok = client.post(f"/me/lists/{list_a}/share", headers=h(a), json={}).json()["token"]
    assert client.post(f"/lists/accept/{tok}", headers=h(b)).status_code == 200
    # delete the account (the Admin API stands in for Supabase Auth)
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setattr(me_delete, "delete_auth_user", lambda *_a, **_k: None)
    assert client.delete("/me", headers=h(a)).status_code == 200
    gone = counts(db, a)
    assert {k: v for k, v in gone.items() if k != "auth.users"} == dict.fromkeys(
        (k for k in COUNTS if k != "auth.users"), 0)
    assert db.execute("SELECT count(*) FROM events WHERE user_id = %s", (a,)).fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 1  # kept, anonymous


def test_stand_in_auth_user_delete_is_not_something_the_role_does(client_as_api_role, db, world, users) -> None:
    a, _ = users
    assert client_as_api_role.delete("/me", headers=h(a)).status_code == 200  # still answers ok
    assert db.execute("SELECT count(*) FROM auth.users WHERE id = %s", (a,)).fetchone()[0] == 1
