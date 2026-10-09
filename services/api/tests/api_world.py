"""The seeded test world for the API tests: catalog, chains, stores, items, prices, promos.

Imported by conftest.py and by the tests (a uniquely named module, because several test
directories have a top-level ``conftest``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import jwt
import psycopg
import psycopg.sql
import pytest
from psycopg.types.json import Jsonb

from smartcart_api.embedding import query_embedder, to_pgvector

JWT_SECRET = "test-secret-at-least-32-bytes-long-for-hs256"
ORIGIN = (34.7800, 32.0800)  # lon, lat
KM_LAT = 1 / 111.0  # degrees of latitude per km (close enough for tests)
EMB = query_embedder()  # the catalog's hash embedder: the same vectors `embed` would write
D = Decimal


def make_token(user_id: uuid.UUID | str, secret: str = JWT_SECRET, **claims: object) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        **claims,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@dataclass
class World:
    chains: tuple[str, str] = ("t-c1", "t-c2")
    stores: dict[str, int] = field(default_factory=dict)
    canon: dict[str, int] = field(default_factory=dict)
    items: dict[str, int] = field(default_factory=dict)
    promos: dict[str, int] = field(default_factory=dict)
    valid_from: datetime = field(default_factory=lambda: datetime.now(UTC) - timedelta(days=1))

    @property
    def location(self) -> dict:
        return {"lon": ORIGIN[0], "lat": ORIGIN[1], "radius_m": 5000}


def add_store(
    db: psycopg.Connection,
    chain: str,
    code: str,
    km_north: float,
    channel: str = "physical",
    name: str | None = None,
    geo_precision: str | None = None,
) -> int:
    """``geo_precision`` None keeps the DB default (the trigger labels a bare point ``address``)."""
    return db.execute(
        "INSERT INTO stores (chain_id, store_code, name, city, channel, geog, geo_precision) VALUES"
        " (%s, %s, %s, 'תל אביב', %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)"
        " RETURNING id",
        (
            chain,
            code,
            name or f"סניף {code}",
            channel,
            ORIGIN[0],
            ORIGIN[1] + km_north * KM_LAT,
            geo_precision,
        ),
    ).fetchone()[0]


def add_price(
    db: psycopg.Connection,
    item_id: int,
    store_id: int | None,
    price: str,
    unit_price: str | None,
    uom: str | None,
    at: datetime,
    estimated: bool = False,
    file_id: int | None = None,
) -> None:
    db.execute(
        "INSERT INTO prices (item_id, store_id, price, unit_price, uom, is_estimated, valid_from,"
        " file_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            item_id,
            store_id,
            D(price),
            D(unit_price) if unit_price else None,
            uom,
            estimated,
            at,
            file_id,
        ),
    )


def add_promo(
    db: psycopg.Connection,
    chain: str,
    store_id: int | None,
    promo_id: str,
    items: list[int],
    reward_type: str,
    reward_value: str | None,
    min_qty: str | None = None,
    club_only: bool = False,
    club_name: str | None = None,
    description: str = "מבצע",
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    file_id: int | None = None,
) -> int:
    pid = db.execute(
        "INSERT INTO promos (chain_id, store_id, promo_id, description, starts_at, ends_at,"
        " club_only, club_name, min_qty, reward_type, reward_value, file_id)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            chain,
            store_id,
            promo_id,
            description,
            starts_at,
            ends_at,
            club_only,
            club_name,
            D(min_qty) if min_qty else None,
            reward_type,
            D(reward_value) if reward_value else None,
            file_id,
        ),
    ).fetchone()[0]
    for iid in items:
        db.execute("INSERT INTO promo_items (promo_id, item_id) VALUES (%s, %s)", (pid, iid))
    return pid


CANONICALS = [
    # key, taxonomy, display name, product type, base unit, critical, soft, rank
    (
        "milk3",
        "t.dairy.milk",
        "חלב 3% בקרטון 1 ליטר",
        "t_milk",
        "100ml",
        {"fat_pct": 3},
        {"brand": None},
        1,
    ),
    (
        "milk1",
        "t.dairy.milk",
        "חלב 1% בקרטון 1 ליטר",
        "t_milk",
        "100ml",
        {"fat_pct": 1},
        {"brand": None},
        5,
    ),
    (
        "paste",
        "t.pantry.canned",
        "רסק עגבניות",
        "t_paste",
        "100g",
        {"product_type": "רסק"},
        {"pack_size": 100},
        2,
    ),
    (
        "salmon",
        "t.fish.fresh",
        "סלמון נורווגי טרי",
        "t_fish",
        "kg",
        {"product_type": "סלמון"},
        {"state": "fresh"},
        8,
    ),
    ("cream", "t.dairy.cream", "שמנת מתוקה 32%", "t_cream", "100ml", {"fat_pct": 32}, {}, 9),
    ("bread", "t.bakery.bread", "לחם אחיד פרוס", "t_bread", "unit", {"product_type": "לחם"}, {}, 3),
    ("eggs", "t.dairy.eggs", "ביצים L 12 יחידות", "t_eggs", "unit", {"size": "L"}, {}, 4),
    ("wafer", "t.snacks.wafer", "חטיף וופל", "t_wafer", "100g", {}, {}, 20),
    ("tomato", "t.produce.veg", "עגבניות", "t_veg", "kg", {}, {}, 6),
]

TAXONOMY = [
    ("t.dairy", None, 1, "מוצרי חלב"),
    ("t.dairy.milk", "t.dairy", 2, "חלב"),
    ("t.dairy.cream", "t.dairy", 2, "שמנת"),
    ("t.dairy.eggs", "t.dairy", 2, "ביצים"),
    ("t.pantry", None, 1, "מזווה"),
    ("t.pantry.canned", "t.pantry", 2, "שימורים"),
    ("t.fish", None, 1, "דגים"),
    ("t.fish.fresh", "t.fish", 2, "דגים טריים"),
    ("t.bakery", None, 1, "מאפייה"),
    ("t.bakery.bread", "t.bakery", 2, "לחם"),
    ("t.snacks", None, 1, "חטיפים"),
    ("t.snacks.wafer", "t.snacks", 2, "וופלים"),
    ("t.produce", None, 1, "פירות וירקות"),
    ("t.produce.veg", "t.produce", 2, "ירקות"),
]

# key, chain, raw name, canonical, flex level, confidence, quantity, unit, weighed, attrs, verified
ITEMS = [
    (
        "milk3_c1_tnuva",
        "t-c1",
        "חלב תנובה 3% 1 ליטר",
        "milk3",
        "exact",
        "0.99",
        "1",
        "ליטר",
        False,
        {"fat_pct": 3, "brand": "תנובה"},
        ["fat_pct"],
    ),
    (
        "milk3_c1_private",
        "t-c1",
        "חלב 3% מותג הבית 1 ליטר",
        "milk3",
        "any_brand",
        "0.95",
        "1",
        "ליטר",
        False,
        {"fat_pct": 3, "brand": "מותג הבית"},
        [],
    ),
    (
        "milk1_c1",
        "t-c1",
        "חלב 1% תנובה 1 ליטר",
        "milk1",
        "exact",
        "0.99",
        "1",
        "ליטר",
        False,
        {"fat_pct": 1, "brand": "תנובה"},
        [],
    ),
    (
        "paste_c1",
        "t-c1",
        "רסק עגבניות אסם 100 גרם",
        "paste",
        "any_brand",
        "0.97",
        "100",
        "גרם",
        False,
        {"product_type": "רסק", "pack_size": 100},
        [],
    ),
    (
        "salmon_c1",
        "t-c1",
        "סלמון נורווגי טרי במשקל",
        "salmon",
        "exact",
        "0.98",
        None,
        'ק"ג',
        True,
        {"product_type": "סלמון", "state": "fresh"},
        ["state"],
    ),
    (
        "bread_c1",
        "t-c1",
        "לחם אחיד פרוס 750 גרם",
        "bread",
        "any_brand",
        "0.96",
        "1",
        "יחידה",
        False,
        {"product_type": "לחם"},
        [],
    ),
    (
        "eggs_c1",
        "t-c1",
        "ביצים L תריסר",
        "eggs",
        "any_brand",
        "0.95",
        "12",
        "יחידה",
        False,
        {"size": "L"},
        [],
    ),
    (
        "milk3_c2",
        "t-c2",
        "חלב טרה 3% 1 ליטר",
        "milk3",
        "any_brand",
        "0.96",
        "1",
        "ליטר",
        False,
        {"fat_pct": 3, "brand": "טרה"},
        [],
    ),
    (
        "paste_c2",
        "t-c2",
        "רסק עגבניות 22% 260 גרם",
        "paste",
        "any_brand",
        "0.93",
        "260",
        "גרם",
        False,
        {"product_type": "רסק", "pack_size": 260},
        [],
    ),
    (
        "salmon_c2_frozen",
        "t-c2",
        "פילה סלמון קפוא 400 גרם",
        "salmon",
        "close",
        "0.81",
        "400",
        "גרם",
        False,
        {"product_type": "סלמון", "state": "frozen"},
        [],
    ),
    (
        "bread_c2",
        "t-c2",
        "לחם אחיד פרוס אנג'ל",
        "bread",
        "any_brand",
        "0.95",
        "1",
        "יחידה",
        False,
        {"product_type": "לחם"},
        [],
    ),
    (
        "eggs_c2",
        "t-c2",
        "ביצים L 12 יח'",
        "eggs",
        "any_brand",
        "0.95",
        "12",
        "יחידה",
        False,
        {"size": "L"},
        [],
    ),
]

# Base (chain-level) prices: item key -> (price, unit price, uom, estimated)
BASE_PRICES = {
    "milk3_c1_tnuva": ("6.90", "0.69", "100ml", False),
    "milk3_c1_private": ("6.20", "0.62", "100ml", False),
    "milk1_c1": ("6.80", "0.68", "100ml", False),
    "paste_c1": ("3.00", "3.00", "100g", False),
    "salmon_c1": ("89.90", "89.90", "kg", True),
    "bread_c1": ("7.00", None, None, False),
    "eggs_c1": ("12.90", None, None, False),
    "milk3_c2": ("6.40", "0.64", "100ml", False),
    "paste_c2": ("6.50", "2.50", "100g", False),
    "salmon_c2_frozen": ("39.90", "9.975", "100g", False),
    "bread_c2": ("6.00", None, None, False),
    "eggs_c2": ("13.50", None, None, False),
}


def seed_catalog(db: psycopg.Connection, w: World) -> None:
    for tid, parent, level, name in TAXONOMY:
        db.execute(
            "INSERT INTO taxonomy (id, parent_id, level, name_he) VALUES (%s, %s, %s, %s)",
            (tid, parent, level, name),
        )
    for pt, crit, soft in (
        ("t_milk", ["fat_pct"], ["brand"]),
        ("t_paste", ["product_type"], ["pack_size"]),
        ("t_fish", ["product_type"], ["state"]),
        ("t_cream", ["fat_pct"], []),
        ("t_bread", ["product_type"], []),
        ("t_eggs", ["size"], []),
        ("t_wafer", [], []),
        ("t_veg", [], []),
    ):
        db.execute(
            "INSERT INTO product_type_rules (product_type, critical_keys, soft_keys) VALUES (%s, %s, %s)",
            (pt, crit, soft),
        )
    for key, tax, name, pt, base, crit, soft, rank in CANONICALS:
        # The cream canonical gets the embedding of a synonym, standing in for a semantic model:
        # only the vector retriever can find it for "קצפת".
        emb_text = "קצפת" if key == "cream" else name
        w.canon[key] = db.execute(
            "INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type,"
            " base_unit, critical_attrs, soft_attrs, embedding, embedding_model, is_mvp, rank)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, %s, true, %s) RETURNING id",
            (
                tax,
                f"t-{key}",
                name,
                pt,
                base,
                Jsonb(crit),
                Jsonb(soft),
                to_pgvector(EMB.embed_one(emb_text)),
                EMB.model_name,
                rank,
            ),
        ).fetchone()[0]


def seed_world(db: psycopg.Connection) -> World:
    w = World()
    db.execute(
        "INSERT INTO chains (id, name, portal) VALUES ('t-c1', 'רשת אחת', 'other'),"
        " ('t-c2', 'רשת שתיים', 'other')"
    )
    w.stores["home"] = add_store(db, "t-c1", "H", 1.0, name="הבית")
    w.stores["a"] = add_store(db, "t-c1", "A", 2.0)
    w.stores["b"] = add_store(db, "t-c2", "B", 3.0)
    w.stores["online"] = add_store(db, "t-c2", "O", 1.5, channel="online")
    w.stores["far"] = add_store(db, "t-c1", "F", 30.0)
    seed_catalog(db, w)
    for n, (key, chain, raw, ckey, flex, conf, qty, unit, weighed, attrs, verified) in enumerate(
        ITEMS
    ):
        iid = db.execute(
            "INSERT INTO items (chain_id, item_code, barcode, raw_name, quantity, unit, is_weighed)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (chain, key, f"7290000{n:06d}", raw, D(qty) if qty else None, unit, weighed),
        ).fetchone()[0]
        w.items[key] = iid
        db.execute(
            "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
            " VALUES (%s, %s, %s, %s, 'rule')",
            (iid, w.canon[ckey], flex, D(conf)),
        )
        db.execute(
            "INSERT INTO item_attributes (item_id, attrs, verified_keys, extractor)"
            " VALUES (%s, %s, %s, 'rule')",
            (iid, Jsonb(attrs), verified),
        )
        db.execute(
            "INSERT INTO item_embeddings (item_id, embedding, model) VALUES (%s, %s::vector, %s)",
            (iid, to_pgvector(EMB.embed_one(raw)), EMB.model_name),
        )
    db.execute("SELECT ensure_price_partition(%s::date)", (w.valid_from.date(),))
    for key, (price, unit_price, uom, est) in BASE_PRICES.items():
        add_price(db, w.items[key], None, price, unit_price, uom, w.valid_from, est)
    # Store exceptions: store A sells Tnuva 3% cheaper; the home store sells paste dearer.
    add_price(db, w.items["milk3_c1_tnuva"], w.stores["a"], "5.90", "0.59", "100ml", w.valid_from)
    add_price(db, w.items["paste_c1"], w.stores["home"], "3.50", "3.50", "100g", w.valid_from)
    # Promos: 1+1 on paste at store A; "3 for 20" on bread chain-wide in c1; a club deal on eggs.
    w.promos["paste_1plus1"] = add_promo(
        db,
        "t-c1",
        w.stores["a"],
        "P1",
        [w.items["paste_c1"]],
        "buy_x_get_y",
        "1",
        description="רסק 1+1",
    )
    w.promos["bread_3for20"] = add_promo(
        db,
        "t-c1",
        None,
        "P2",
        [w.items["bread_c1"]],
        "bundle",
        "20",
        min_qty="3",
        description="3 לחמים ב-20",
    )
    w.promos["eggs_club"] = add_promo(
        db,
        "t-c1",
        None,
        "P3",
        [w.items["eggs_c1"]],
        "price",
        "9.90",
        club_only=True,
        club_name="מועדון לקוחות",
        description="ביצים למועדון",
    )
    # Salmon is not sold at all in chain c2 at "any brand" (only a frozen close substitute).
    return w


# --- the API's least-privilege role (migration 20261011100500) ---------------------------------

API_TEST_ROLE = "smartcart_api_t"


def make_api_role(db: psycopg.Connection, name: str = API_TEST_ROLE) -> str:
    """A throwaway role with exactly the grants of ``smartcart_api`` (migration 20261011100500).

    It is made inside the test's transaction, so it disappears with the rollback. NOINHERIT as in
    the migration, so smartcart_app's rights are reachable only through SET ROLE. Skips the test
    when the database does not let the migrating role grant on the ``auth`` schema (Supabase's
    own), because the API cannot work there without it either."""
    ident = psycopg.sql.Identifier(name)
    db.execute(psycopg.sql.SQL("CREATE ROLE {} NOLOGIN NOINHERIT").format(ident))
    if db.info.server_version >= 160000:  # the creator may administer the role, not SET to it
        db.execute(psycopg.sql.SQL("GRANT {} TO CURRENT_USER WITH SET TRUE").format(ident))
    db.execute("SELECT smartcart_grant_api_role(%s)", (name,))
    if not db.execute("SELECT has_schema_privilege(%s, 'auth', 'USAGE')", (name,)).fetchone()[0]:
        pytest.skip("this database does not let the migrating role grant on the auth schema")
    return name


def assume_role(db: psycopg.Connection, role: str) -> None:
    """Run what follows as ``role``. SET SESSION AUTHORIZATION (superuser) survives the RESET ROLE
    that the user routes end with; without superuser, SET ROLE has to do."""
    superuser = db.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user").fetchone()[
        0
    ]
    stmt = "SET SESSION AUTHORIZATION {}" if superuser else "SET ROLE {}"
    db.execute(psycopg.sql.SQL(stmt).format(psycopg.sql.Identifier(role)))


def release_role(db: psycopg.Connection) -> None:
    db.execute("RESET SESSION AUTHORIZATION")
    db.execute("RESET ROLE")
