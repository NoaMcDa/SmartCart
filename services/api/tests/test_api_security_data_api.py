"""What the Supabase data API roles (``anon``, ``authenticated``) may touch (finding S2), and what
the API's own login role may do with the closed-beta and photo tables (finding S9).

Migrations 20261021120100_data_api_lockdown.sql and 20261021120200_api_role_beta_ocr.sql. The
roles ``anon`` and ``authenticated`` exist on Supabase and in the CI image
(``supabase/postgres``); on a plain Postgres there is no data API and the matrix tests skip.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest

pytestmark = pytest.mark.db

DML = ("SELECT", "INSERT", "UPDATE", "DELETE")
EVERY_PRIVILEGE = (*DML, "TRUNCATE", "REFERENCES", "TRIGGER")

# What the web app reaches through PostgREST, as `authenticated`, and nothing else: the items of a
# shared list (apps/web/src/features/share/useSharedList.ts, the only supabase-js `.from()` call).
# Every other table goes through the API. A feature that needs another table adds its GRANT in its
# own migration and its line here.
AUTHENTICATED_MAY: dict[str, tuple[str, ...]] = {"list_items": DML}


def _role_exists(db: psycopg.Connection, role: str) -> bool:
    return db.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone() is not None


@pytest.fixture
def data_api_roles(db: psycopg.Connection) -> None:
    if not (_role_exists(db, "anon") and _role_exists(db, "authenticated")):
        pytest.skip("no Supabase data API roles in this database")


def _relations(db: psycopg.Connection) -> list[str]:
    """Tables, partitions, views and materialized views of `public` (the relations PostgREST can
    expose), minus the PostGIS catalog views."""
    return [
        r[0]
        for r in db.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
            " WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f')"
            "   AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')"
            " ORDER BY 1"
        ).fetchall()
    ]


def test_anon_has_no_privilege_on_anything(db: psycopg.Connection, data_api_roles) -> None:
    leaks = [
        f"{rel}:{priv}"
        for rel in _relations(db)
        for priv in EVERY_PRIVILEGE
        if db.execute(
            "SELECT has_table_privilege('anon', %s, %s)", (f"public.{rel}", priv)
        ).fetchone()[0]
    ]
    assert not leaks, f"anon (the public key) can: {leaks}"


def test_authenticated_has_only_what_the_web_app_uses(
    db: psycopg.Connection, data_api_roles
) -> None:
    extra, missing = [], []
    for rel in _relations(db):
        allowed = AUTHENTICATED_MAY.get(rel, ())
        for priv in EVERY_PRIVILEGE:
            has = db.execute(
                "SELECT has_table_privilege('authenticated', %s, %s)", (f"public.{rel}", priv)
            ).fetchone()[0]
            if has and priv not in allowed:
                extra.append(f"{rel}:{priv}")
            if priv in allowed and not has:
                missing.append(f"{rel}:{priv}")
    assert not extra, f"a signed-in user can, through PostgREST: {extra}"
    assert not missing, f"the web app needs, and the role lacks: {missing}"


def test_nobody_in_the_data_api_has_a_sequence(db: psycopg.Connection, data_api_roles) -> None:
    allowed_for_authenticated = {"list_items_id_seq"}
    rows = db.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
        " WHERE n.nspname = 'public' AND c.relkind = 'S'"
    ).fetchall()
    for (seq,) in rows:
        for role in ("anon", "authenticated"):
            for priv in ("USAGE", "SELECT", "UPDATE"):
                has = db.execute(
                    "SELECT has_sequence_privilege(%s, %s, %s)", (role, f"public.{seq}", priv)
                ).fetchone()[0]
                if (
                    role == "authenticated"
                    and seq in allowed_for_authenticated
                    and priv != "UPDATE"
                ):
                    continue
                assert not has, f"{role} has {priv} on {seq}"


def test_a_table_created_later_is_not_open_to_the_data_api(
    db: psycopg.Connection, data_api_roles
) -> None:
    """The default privileges no longer hand new tables to anon and authenticated."""
    db.execute("CREATE TABLE zz_security_probe (id serial PRIMARY KEY, secret text)")
    for role in ("anon", "authenticated"):
        for priv in DML:
            assert not db.execute(
                "SELECT has_table_privilege(%s, 'zz_security_probe', %s)", (role, priv)
            ).fetchone()[0], (role, priv)


def _as(db: psycopg.Connection, role: str, uid: uuid.UUID | None = None) -> None:
    db.execute("RESET ROLE")
    db.execute(f"SET LOCAL ROLE {role}")
    db.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(uid or ""),))


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE prices SET price = 0.01",
        "DELETE FROM prices",
        "INSERT INTO chains (id, name) VALUES ('evil', 'evil')",
        "UPDATE item_canonical SET canonical_id = canonical_id",
        "DELETE FROM canonical_products",
        "SELECT * FROM gap_reports",
        "SELECT * FROM alert_deliveries",
        "SELECT * FROM events",
        "SELECT * FROM profiles",  # the API owns the user tables: consent, ranges and limits
        "UPDATE profiles SET radius_m = 500",
        "INSERT INTO lists (user_id, name) VALUES (gen_random_uuid(), 'x')",
        "SELECT * FROM list_shares",
        "INSERT INTO list_shares (list_id, owner_id, invite_token) VALUES (1, gen_random_uuid(), 'x')",
        "SELECT * FROM spend_entries",
        "SELECT * FROM price_alerts",
        "SELECT * FROM push_subscriptions",
        "SELECT * FROM beta_members",
        "TRUNCATE lists",
        "TRUNCATE list_items",
    ],
)
@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_the_data_api_roles_cannot_touch_the_catalog_or_private_tables(
    db: psycopg.Connection, data_api_roles, role: str, statement: str
) -> None:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    _as(db, role, uid)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.transaction():
            db.execute(statement)


def test_authenticated_still_edits_the_items_of_a_list_it_may_see(
    db: psycopg.Connection, data_api_roles
) -> None:
    """The shared-list screen (supabase-js: insert, update, delete, Realtime select on list_items)."""
    owner, editor, viewer, stranger = (uuid.uuid4() for _ in range(4))
    db.execute(
        "INSERT INTO auth.users (id) SELECT unnest(%s::uuid[])",
        ([owner, editor, viewer, stranger],),
    )
    lid = db.execute(
        "INSERT INTO lists (user_id, name) VALUES (%s, 'x') RETURNING id", (owner,)
    ).fetchone()[0]
    for member, role in ((editor, "editor"), (viewer, "viewer")):
        db.execute(
            "INSERT INTO list_shares (list_id, owner_id, member_id, accepted_at, role, invite_token)"
            " VALUES (%s, %s, %s, now(), %s, %s)",
            (lid, owner, member, role, uuid.uuid4().hex),
        )
    _as(db, "authenticated", owner)
    db.execute(
        "INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'חלב')", (lid, owner)
    )
    _as(db, "authenticated", editor)
    db.execute(
        "INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'ביצים')",
        (lid, editor),
    )
    assert (
        db.execute("UPDATE list_items SET checked = true WHERE list_id = %s", (lid,)).rowcount == 2
    )
    _as(db, "authenticated", viewer)
    assert db.execute("SELECT count(*) FROM list_items").fetchone()[0] == 2
    assert db.execute("UPDATE list_items SET checked = false").rowcount == 0
    _as(db, "authenticated", stranger)
    assert db.execute("SELECT count(*) FROM list_items").fetchone()[0] == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.transaction():
            db.execute(
                "INSERT INTO list_items (list_id, user_id, input_text) VALUES (%s, %s, 'x')",
                (lid, stranger),
            )
    _as(db, "anon")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.transaction():
            db.execute("SELECT count(*) FROM list_items")


# --- the API role and the closed-beta / photo tables (S9) ---------------------------------------

API_ROLE = "zz_api_probe"


@pytest.fixture
def api_login_role(db: psycopg.Connection) -> str:
    db.execute(f"CREATE ROLE {API_ROLE} NOLOGIN NOINHERIT")
    if db.info.server_version >= 160000:
        db.execute(f"GRANT {API_ROLE} TO CURRENT_USER WITH SET TRUE")
    db.execute("SELECT smartcart_grant_api_role(%s)", (API_ROLE,))
    return API_ROLE


def test_the_api_role_can_run_the_beta_and_photo_routes(
    db: psycopg.Connection, api_login_role: str
) -> None:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    db.execute(
        "INSERT INTO beta_invites (code, segment, max_uses) VALUES ('API-PROBE-1', 'general', 2)"
    )
    db.execute(f"SET LOCAL ROLE {api_login_role}")
    # POST /beta/join
    row = db.execute(
        "SELECT segment, max_uses, uses FROM beta_invites WHERE code = 'API-PROBE-1' FOR UPDATE"
    ).fetchone()
    assert row == ("general", 2, 0)
    db.execute("UPDATE beta_invites SET uses = uses + 1 WHERE code = 'API-PROBE-1'")
    db.execute(
        "INSERT INTO beta_members (user_id, code, segment) VALUES (%s, 'API-PROBE-1', 'general')",
        (uid,),
    )
    assert db.execute("SELECT segment FROM beta_members WHERE user_id = %s", (uid,)).fetchone() == (
        "general",
    )
    # POST /beta/feedback
    db.execute("INSERT INTO beta_feedback (segment, rating, body) VALUES ('general', 5, 'ok')")
    # POST /parse-image (the cap counters)
    db.execute(
        "INSERT INTO ocr_usage (month, provider, images, est_cost_usd)"
        " VALUES (date_trunc('month', now())::date, 'fake', 1, 0)"
        " ON CONFLICT (month, provider) DO UPDATE SET images = ocr_usage.images + 1"
    )
    assert db.execute("SELECT sum(images) FROM ocr_usage").fetchone()[0] == 1


def test_the_api_role_gets_no_more_than_the_routes_need_on_the_private_tables(
    db: psycopg.Connection, api_login_role: str
) -> None:
    def may(table: str, priv: str) -> bool:
        return db.execute(
            "SELECT has_table_privilege(%s, %s, %s)", (api_login_role, f"public.{table}", priv)
        ).fetchone()[0]

    assert not may("beta_invites", "INSERT") and not may("beta_invites", "DELETE")
    assert not may("beta_members", "UPDATE") and not may("beta_members", "DELETE")
    assert not may("beta_feedback", "SELECT") and not may("beta_feedback", "UPDATE")
    assert not may("ocr_usage", "DELETE")
    # the feedback text is never readable back through the API role: no user id, and no SELECT
    db.execute(f"SET LOCAL ROLE {api_login_role}")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.transaction():
            db.execute("SELECT body FROM beta_feedback")
