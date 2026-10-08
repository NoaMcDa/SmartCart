"""Arabic search over canonical names, with the real 245 canonicals (issue #73).

The shared ``world`` catalog is Hebrew only, so these tests seed the shipped canonicals with
their Arabic names (``smartcart_catalog.seed``) inside the test's rolled-back transaction."""

from __future__ import annotations

import psycopg
import pytest
from api_world import JWT_SECRET
from fastapi.testclient import TestClient

from smartcart_api import search
from smartcart_api.db import get_conn
from smartcart_api.main import app
from smartcart_api.routes.search import CONFIRM_BELOW, resolve
from smartcart_api.search import hybrid_search
from smartcart_api.settings import get_settings
from smartcart_catalog.seed import load_catalog, seed_all

pytestmark = [pytest.mark.db, pytest.mark.pgvector]


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture(scope="module")
def db(database, catalog):
    """One connection for the module with the shipped canonicals seeded and never committed: every
    test here only reads (seeding 245 canonicals per test would take minutes)."""
    with psycopg.connect(database.dsn) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        seed_all(conn, catalog)
        try:
            yield conn
        finally:
            conn.rollback()


@pytest.fixture(scope="module")
def ar(db):
    """slug -> canonical id."""
    return {slug: cid for cid, slug in db.execute("SELECT id, slug FROM canonical_products")}


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    get_settings.cache_clear()

    def _conn():
        yield db

    app.dependency_overrides[get_conn] = _conn
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_conn, None)
        get_settings.cache_clear()


def _slugs(db, q: str, limit: int = 8) -> list[str]:
    slug = {cid: s for cid, s in db.execute("SELECT id, slug FROM canonical_products")}
    return [slug[h.canonical_id] for h in hybrid_search(db, q, limit=limit)]


def _served(db, q: str) -> str | None:
    """The slug /parse-list would answer without asking the user, or None."""
    hits, conf = resolve(db, q)
    if not hits or conf < CONFIRM_BELOW:
        return None
    return db.execute("SELECT slug FROM canonical_products WHERE id = %s", (hits[0].canonical_id,)).fetchone()[0]


# --- the basics ------------------------------------------------------------------------------------


def test_arabic_query_finds_the_canonical(db, ar) -> None:
    hits = hybrid_search(db, "حليب 3%")
    assert hits[0].canonical_id == ar["milk-fresh-3"]
    assert hits[0].matched_by == ["trigram", "fts"]  # the hash embedder knows no Arabic
    assert hits[0].names_ar == ["حليب طازج 3%", "حليب 3%"]
    assert hits[0].display_name_he == "חלב טרי 3%"
    assert hits[0].category_path_he  # the category path is filled like for Hebrew


@pytest.mark.parametrize(
    ("query", "slug"),
    [
        ("حليب 3%", "milk-fresh-3"),
        ("الحليب طازج 3 بالمية", "milk-fresh-3"),
        ("حليب ٣٪", "milk-fresh-3"),
        ("حليب %1", "milk-fresh-1"),
        ("كوتج ٥٪", "cottage-5"),  # dialect spelling and Arabic-Indic digit
        ("جبنة بيضا 9%", "white-cheese-9"),  # بيضا and بيضاء are one word after folding
        ("لبنه", "labane-5"),  # ة and ه meet
        ("البندورة", "tomato"),  # the article
        ("وبندورة", "tomato"),  # the conjunction
        ("طماطم شيري", "cherry-tomato"),
        ("بيض لارج", "eggs-l"),
        ("زيت الزيتون", "olive-oil"),
        ("يوغورت بالفراولة", "yogurt-strawberry"),  # بال: with the
        ("كريمة للطبخ 10%", "cooking-cream-10"),  # لل: for the
        ("حليب تنوفا 3%", "milk-fresh-3"),  # a brand is dropped
        ("لو سمحت حليب 3%", "milk-fresh-3"),  # politeness is dropped
        ("ورق تواليت 32 رول", "toilet-paper"),  # a pack size is dropped
    ],
)
def test_served_with_spelling_variants(db, ar, query: str, slug: str) -> None:
    assert _served(db, query) == slug


@pytest.mark.parametrize(
    "query",
    ["حليب", "جبنة بيضاء", "كوتيج", "رز", "خبز", "بيض", "صدر دجاج", "ذرة", "حمص", "زيت",
     "شوكولاتة", "قهوة", "تفاح", "سلمون", "بيسلي", "بوريكس", "عصير"],
)  # fmt: skip
def test_ambiguous_lines_are_not_served(db, ar, query: str) -> None:
    assert _served(db, query) is None
    assert hybrid_search(db, query)  # but candidates are offered


@pytest.mark.parametrize(
    "query",
    ["بطاريات", "لابتوب", "حذاء", "هاتف", "ملوخية", "ويسكي", "ورق عنب", "قائمة التسوق", "ء", "-", "٣", "%"],
)
def test_unknown_lines_are_not_served(db, ar, query: str) -> None:
    assert _served(db, query) is None


def test_queries_with_sql_and_regex_characters(db, ar) -> None:
    for q in ["حليب'; DROP TABLE canonical_products; --", "حليب (3%)", "حليب [3%]", "حليب \\ 3%",
              "حليب & جبنة | بيض", "'حليب'", "حليب:*", "حليب 1.5.5%", "%%%حليب"]:  # fmt: skip
        hybrid_search(db, q)  # no exception
    assert db.execute("SELECT count(*) FROM canonical_products").fetchone()[0] == 245


# --- attribute hard checks ---------------------------------------------------------------------------

CONTRADICTIONS = [
    ("حليب 1%", {"milk-fresh-3", "milk-long-life-3", "milk-lactose-free-2"}),
    ("حليب 3%", {"milk-fresh-1", "milk-long-life-1"}),
    ("كوتيج 5%", {"cottage-3"}),
    ("كوتيج 3%", {"cottage-5"}),
    ("جبنة بيضاء 9%", {"white-cheese-5", "white-cheese-3"}),
    ("لبنة 9%", {"labane-5"}),
    ("زبادي 3%", {"yogurt-plain-1-5"}),
    ("حليب لوز", {"soy-drink", "oat-drink"}),
    ("حليب صويا", {"almond-drink", "oat-drink"}),
    ("مشروب شوفان", {"almond-drink", "soy-drink"}),
    ("صدر دجاج مجمد", {"chicken-breast-fresh"}),
    ("صدر دجاج طازج", {"chicken-breast-frozen"}),
    ("سلمون طازج", {"salmon-fillet-frozen"}),
    ("لحمة مفرومة مجمدة", {"beef-ground-fresh"}),
    ("ذرة معلبة", {"sweet-corn-frozen"}),
    ("ذرة مجمدة", {"sweet-corn-canned"}),
    ("حمص ناشف", {"chickpeas-canned"}),
    ("حمص معلب", {"chickpeas-dry"}),
    ("بروكلي طازج", {"broccoli-frozen"}),
    ("بازلاء مجمدة", {"peas-canned"}),
    ("زبادي فراولة", {"yogurt-peach"}),
    ("زبادي خوخ", {"yogurt-strawberry"}),
    ("بوريكس بطاطا", {"burekas-cheese"}),
    ("بوريكس جبنة", {"burekas-potato"}),
    ("شوكولاتة داكنة", {"chocolate-milk-bar"}),
    ("شوكولاتة حليب", {"chocolate-dark-bar"}),
    ("بيسلي غريل", {"bisli-onion"}),
    ("ميلكي فانيلا", {"dessert-chocolate"}),
]


@pytest.mark.parametrize(("query", "forbidden"), CONTRADICTIONS)
def test_no_result_contradicts_a_stated_attribute(db, ar, query: str, forbidden: set[str]) -> None:
    got = set(_slugs(db, query, limit=20))
    assert not got & forbidden, (query, got & forbidden)


def test_a_fat_percentage_no_canonical_has_finds_nothing_of_that_family(db, ar) -> None:
    for q in ["حليب 2%", "كوتيج 2%", "جبنة بيضاء 4%", "لبنة 7%", "زبادي 2%"]:
        slugs = set(_slugs(db, q, limit=20))
        fats = {
            s: f
            for s, f in db.execute(
                "SELECT slug, critical_attrs->>'fat_pct' FROM canonical_products"
                " WHERE critical_attrs ? 'fat_pct'"
            )
        }
        stated = q.split()[-1].rstrip("%")
        assert not [s for s in slugs if s in fats and float(fats[s]) != float(stated)], q


def test_fat_never_matches_by_prefix(db, ar) -> None:
    # 3% is not 30% or 38%: whipping cream and cream cheese must not answer "حليب 3%"
    assert not set(_slugs(db, "حليب 3%", 20)) & {"whipping-cream-32", "whipping-cream-38"}
    assert _served(db, "كريمة حلوة 32%") == "whipping-cream-32"
    assert _served(db, "كريمة حلوة 38%") == "whipping-cream-38"


def test_swapping_the_stated_attribute_never_returns_the_canonical(db, ar, catalog) -> None:
    """For every canonical, change what its name states (the fat percentage, fresh/frozen) to what
    a sibling states: the canonical must not come back. This is the 98%-precision guarantee."""
    fats = sorted({float(c.critical_attrs["fat_pct"]) for c in catalog.canonicals
                   if "fat_pct" in c.critical_attrs})  # fmt: skip
    checked = 0
    for c in catalog.canonicals:
        for name in c.names_ar:
            variants: list[str] = []
            if "fat_pct" in c.critical_attrs:
                own = f"{c.critical_attrs['fat_pct']}%"
                variants += [name.replace(own, f"{f:g}%") for f in fats if f"{f:g}%" != own]
            state = c.critical_attrs.get("state")
            if state == "frozen":
                variants += [name.replace("مجمدة", "طازجة").replace("مجمد", "طازج")]
            if state == "fresh" and ("طازج" in name):
                variants += [name.replace("طازجة", "مجمدة").replace("طازج", "مجمد")]
            if state == "canned":
                variants += [name.replace("معلبة", "مجمدة").replace("معلب", "مجمد")]
            for v in (v for v in variants if v != name):
                checked += 1
                assert c.slug not in _slugs(db, v, limit=20), (c.slug, name, v)
    assert checked > 150


# --- every name finds its canonical --------------------------------------------------------------------


def test_every_name_is_served_for_its_own_canonical(db, ar, catalog) -> None:
    """A canonical's own name, typed as the query, is the top hit and is answered without asking,
    except where another canonical's name contains it (then the user must confirm)."""
    not_top, unserved = [], []
    for c in catalog.canonicals:
        for name in c.names_ar:
            hits, conf = resolve(db, name)
            if not hits or hits[0].canonical_id != ar[c.slug]:
                not_top.append((c.slug, name, [h.display_name_he for h in hits[:3]]))
            elif conf < CONFIRM_BELOW:
                unserved.append((c.slug, name, conf))
    assert not not_top, not_top[:10]
    assert len(unserved) <= 3, unserved


# --- the vector retriever only suggests ------------------------------------------------------------------


def test_vector_only_hits_are_never_confident(db, ar, monkeypatch) -> None:
    def fake_vector(conn, q, k):
        return [(ar["butter"], 0.99, 0.99)]

    monkeypatch.setitem(search._RETRIEVE_AR, "vector", fake_vector)
    hits = hybrid_search(db, "لابتوب")
    assert [h.canonical_id for h in hits] == [ar["butter"]]
    assert hits[0].matched_by == ["vector"]
    assert hits[0].confidence <= search.VECTOR_ONLY_CAP < CONFIRM_BELOW
    assert _served(db, "لابتوب") is None


def test_vector_agreement_does_not_override_a_veto(db, ar, monkeypatch) -> None:
    def fake_vector(conn, q, k):
        return [(ar["milk-fresh-3"], 0.99, 0.99)]

    monkeypatch.setitem(search._RETRIEVE_AR, "vector", fake_vector)
    assert ar["milk-fresh-3"] not in [h.canonical_id for h in hybrid_search(db, "حليب 1%")]


def test_hash_embedder_query_is_unchanged_for_arabic(db, ar) -> None:
    # the vector retriever is called with the raw query
    seen = []

    def spy(conn, q, k):
        seen.append(q)
        return []

    search._RETRIEVE_AR["vector"] = spy
    try:
        hybrid_search(db, "الحليب ٣٪")
    finally:
        search._RETRIEVE_AR["vector"] = search._vector
    assert seen == ["الحليب ٣٪"]


# --- ordering and qualifiers ------------------------------------------------------------------------------


def test_word_order_matters(db, ar) -> None:
    # "milk chocolate" (the bar) is not "chocolate milk" (the drink)
    assert _served(db, "شوكولاتة حليب") == "chocolate-milk-bar"
    assert _served(db, "حليب شوكولاتة") is None
    assert _served(db, "شوكو") == "chocolate-milk"


def test_an_unstated_qualifier_asks_the_user(db, ar) -> None:
    # lactose-free milk is milk with 2%, but "حليب 2%" does not say lactose-free
    assert _served(db, "حليب 2%") is None
    assert _served(db, "حليب بدون لاكتوز 2%") == "milk-lactose-free-2"


def test_a_short_query_word_is_not_a_prefix_of_another_word(db, ar) -> None:
    assert _served(db, "لبن") is None  # yogurt/laban, not labneh (لبنة)
    assert _served(db, "موز") == "banana"  # not mozzarella (موزاريلا)
    assert _served(db, "زيت") is None  # not olive oil (زيتون)


def test_a_percentage_the_name_lacks_asks_the_user(db, ar) -> None:
    assert _served(db, "حليب لوز 3%") is None


# --- Hebrew is unchanged --------------------------------------------------------------------------------------


def test_hebrew_queries_never_take_the_arabic_path(db, ar) -> None:
    hits = hybrid_search(db, "חלב 3%")
    assert hits and hits[0].names_ar == [] and hits[0].critical_attrs == {}
    assert hybrid_search(db, "milk 3%") is not None
