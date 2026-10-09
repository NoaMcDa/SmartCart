"""Hybrid search and the list parser (issues #54, #51)."""

from __future__ import annotations

import time
from decimal import Decimal

import pytest
from api_world import World

from smartcart_api.listparse import parse_fragment, split_items, split_vav
from smartcart_api.search import hybrid_search

D = Decimal
db_marks = [pytest.mark.db, pytest.mark.pgvector]


# --- splitting and quantities (no database) ----------------------------------------------------


def test_split_items() -> None:
    assert split_items("חלב, 2 רסק עגבניות\nסלמון;לחם") == ["חלב", "2 רסק עגבניות", "סלמון", "לחם"]
    assert split_items("- חלב\n• לחם\n\n") == ["חלב", "לחם"]


def test_split_vav() -> None:
    assert split_vav("חלב ולחם") == ["חלב", "לחם"]
    assert split_vav("רסק עגבניות") == ["רסק עגבניות"]
    assert split_vav("2 חלב ו3 לחם") == ["2 חלב ו3 לחם"]  # ו before a digit is not split


@pytest.mark.parametrize(
    ("text", "product", "qty", "unit"),
    [
        ("2 רסק עגבניות", "רסק עגבניות", "2", None),
        ("חלב x3", "חלב", "3", None),
        ("חלב ×3", "חלב", "3", None),
        ("חלב 3x", "חלב", "3", None),
        ("3x חלב", "חלב", "3", None),
        ("חלב 4 יח'", "חלב", "4", None),
        ('1.5 ק"ג עגבניות', "עגבניות", "1.5", "kg"),
        ("1,5 קילו עגבניות", "עגבניות", "1.5", "kg"),
        ("500 גרם גבינה צהובה", "גבינה צהובה", "0.5", "kg"),
        ("שני חלב", "חלב", "2", None),
        ("חלב 3%", "חלב 3%", "1", None),  # a fat percentage is not a quantity
        ("ביצים L 12", "ביצים L 12", "1", None),  # a bare trailing number stays in the text
        ("רסק עגבניות 100 גרם", "רסק עגבניות 100 גרם", "1", None),
        ("סלמון", "סלמון", "1", None),
    ],
)
def test_quantities(text: str, product: str, qty: str, unit: str | None) -> None:
    f = parse_fragment(text)
    assert (f.text, f.quantity, f.unit) == (product, D(qty), unit)


# --- search ------------------------------------------------------------------------------------


@pytest.mark.db
@pytest.mark.pgvector
def test_search_ranks_by_rrf_and_reports_retrievers(db, catalog: World) -> None:
    hits = hybrid_search(db, "רסק עגבניות")
    assert hits[0].canonical_id == catalog.canon["paste"]
    assert set(hits[0].matched_by) == {"trigram", "fts", "vector"}
    assert hits[0].score == 1.0  # rank 1 in every retriever
    assert [h.rrf for h in hits] == sorted((h.rrf for h in hits), reverse=True)


@pytest.mark.db
@pytest.mark.pgvector
@pytest.mark.parametrize(
    ("query", "key"),
    [
        ("חלבב", "milk"),
        ("רסק עגבנייות", "paste"),
        ("סלמונ", "salmon"),
        ("לחם אחד פרוס", "bread"),
        ("ביצים L", "eggs"),
    ],
)
def test_misspelled_queries_find_the_intended_canonical(
    db, catalog: World, query: str, key: str
) -> None:
    hits = hybrid_search(db, query, limit=3)
    wanted = {v for k, v in catalog.canon.items() if k.startswith(key)}
    assert hits and hits[0].canonical_id in wanted, [h.display_name_he for h in hits]


@pytest.mark.db
@pytest.mark.pgvector
def test_meaning_only_query_comes_from_the_vector_retriever(db, catalog: World) -> None:
    # "קצפת" shares no word or trigram with "שמנת מתוקה 32%"; the seeded embedding stands in
    # for a semantic model (BGE-M3), so only the vector retriever can find it.
    hits = hybrid_search(db, "קצפת")
    assert hits and hits[0].canonical_id == catalog.canon["cream"]
    assert hits[0].matched_by == ["vector"]
    assert hybrid_search(db, "קצפת", retrievers=("trigram", "fts")) == []


@pytest.mark.db
@pytest.mark.pgvector
def test_vector_retriever_compares_only_vectors_of_the_query_model(db, world: World) -> None:
    from smartcart_api.embedding import query_embedder
    from smartcart_catalog.embed import HashEmbedder

    # The query embedder is the catalog's: the fixtures' vectors are what `embed` writes.
    assert query_embedder().model_name == HashEmbedder().model_name == "hash-ngram-2-3-4-v1"
    cream = world.canon["cream"]
    assert (
        db.execute(
            "SELECT embedding_model FROM canonical_products WHERE id = %s", (cream,)
        ).fetchone()[0]
        == query_embedder().model_name
    )
    assert [h.canonical_id for h in hybrid_search(db, "קצפת", retrievers=("vector",))][:1] == [
        cream
    ]
    # A NULL model is unknown: skipped until the catalog's embed job records it.
    db.execute("UPDATE canonical_products SET embedding_model = NULL WHERE id = %s", (cream,))
    assert cream not in [h.canonical_id for h in hybrid_search(db, "קצפת", retrievers=("vector",))]
    # Labeled as another model (a BGE-M3 vector, say): never compared with a hash query vector.
    db.execute(
        "UPDATE canonical_products SET embedding_model = 'BAAI/bge-m3' WHERE id = %s", (cream,)
    )
    assert cream not in [h.canonical_id for h in hybrid_search(db, "קצפת", retrievers=("vector",))]

    # Item embeddings: "רסק עגבניות אסם" reaches paste through its item's vector. Relabel every
    # canonical as another model so only the item path is left.
    db.execute("UPDATE canonical_products SET embedding_model = 'BAAI/bge-m3'")
    paste = world.canon["paste"]
    via_items = [
        h.canonical_id for h in hybrid_search(db, "רסק עגבניות אסם", retrievers=("vector",))
    ]
    assert paste in via_items
    db.execute("UPDATE item_embeddings SET model = 'BAAI/bge-m3'")
    assert hybrid_search(db, "רסק עגבניות אסם", retrievers=("vector",)) == []


@pytest.mark.db
@pytest.mark.pgvector
def test_each_retriever_can_be_disabled_and_contributes(db, catalog: World) -> None:
    for only in ("trigram", "fts", "vector"):
        hits = hybrid_search(db, "רסק עגבניות", retrievers=(only,))
        assert hits and hits[0].canonical_id == catalog.canon["paste"], only
        assert all(h.matched_by == [only] for h in hits)
    # A misspelled word: full-text search misses it, trigram search finds it.
    assert hybrid_search(db, "עגבנייות", retrievers=("fts",)) == []
    trigram = hybrid_search(db, "עגבנייות", retrievers=("trigram",))
    assert catalog.canon["tomato"] in [h.canonical_id for h in trigram]


@pytest.mark.db
@pytest.mark.pgvector
def test_hebrew_prefix_is_stripped_for_full_text(db, catalog: World) -> None:
    hits = hybrid_search(db, "והלחם", retrievers=("fts",))
    assert hits and hits[0].canonical_id == catalog.canon["bread"]


@pytest.mark.db
@pytest.mark.pgvector
def test_search_route(client, catalog: World) -> None:
    r = client.get("/search", params={"q": "סלמון", "limit": 3})
    assert r.status_code == 200
    body = r.json()
    top = body["hits"][0]
    assert top["canonical"]["canonical_id"] == catalog.canon["salmon"]
    assert top["canonical"]["category_path_he"] == ["דגים", "דגים טריים"]
    assert top["canonical"]["base_unit"] == "kg"
    assert set(top["matched_by"]) <= {"trigram", "fts", "vector"} and top["matched_by"]
    assert 0 < top["score"] <= 1 and 0 < top["confidence"] <= 1


@pytest.mark.db
@pytest.mark.pgvector
def test_search_unknown_returns_nothing(client, catalog: World) -> None:
    assert client.get("/search", params={"q": "מברג חשמלי"}).json()["hits"] == []


# --- parse-list --------------------------------------------------------------------------------


@pytest.mark.db
@pytest.mark.pgvector
def test_acceptance_example(client, catalog: World) -> None:
    r = client.post("/parse-list", json={"text": "חלב, 2 רסק עגבניות, סלמון"})
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert [row["input_text"] for row in rows] == ["חלב", "2 רסק עגבניות", "סלמון"]
    milk, paste, salmon = rows
    assert (
        D(paste["quantity"]) == 2 and paste["canonical"]["canonical_id"] == catalog.canon["paste"]
    )
    assert D(milk["quantity"]) == 1 and D(salmon["quantity"]) == 1
    assert salmon["canonical"]["canonical_id"] == catalog.canon["salmon"] and salmon["is_weighed"]
    assert not paste["needs_confirmation"] and not salmon["needs_confirmation"]
    # "חלב" fits 3 % and 1 % milk equally: the user is asked, with the alternative.
    assert milk["needs_confirmation"] and milk["confidence"] < 0.75
    ids = {milk["canonical"]["canonical_id"], *(c["canonical_id"] for c in milk["candidates"])}
    assert {catalog.canon["milk3"], catalog.canon["milk1"]} <= ids


@pytest.mark.db
@pytest.mark.pgvector
def test_typos_resolve(client, catalog: World) -> None:
    rows = client.post("/parse-list", json={"text": "חלבב\nרסק עגבנייות"}).json()["rows"]
    assert rows[0]["canonical"]["canonical_id"] in {catalog.canon["milk3"], catalog.canon["milk1"]}
    assert rows[1]["canonical"]["canonical_id"] == catalog.canon["paste"]
    assert not rows[0]["not_found"] and not rows[1]["not_found"]


@pytest.mark.db
@pytest.mark.pgvector
def test_unknown_text_is_an_explicit_not_found(client, catalog: World) -> None:
    rows = client.post("/parse-list", json={"text": "מברג חשמלי, xyzzy"}).json()["rows"]
    assert len(rows) == 2
    for row in rows:
        assert row["not_found"] and row["canonical"] is None and row["needs_confirmation"]
        assert row["confidence"] < 0.35


@pytest.mark.db
@pytest.mark.pgvector
def test_vav_splits_unless_the_whole_name_matches(client, catalog: World) -> None:
    rows = client.post("/parse-list", json={"text": "סלמון ולחם אחיד פרוס, חטיף וופל"}).json()[
        "rows"
    ]
    assert [r["canonical"]["canonical_id"] for r in rows] == [
        catalog.canon["salmon"],
        catalog.canon["bread"],
        catalog.canon["wafer"],
    ]


@pytest.mark.db
@pytest.mark.pgvector
def test_weights_and_flex_defaults(client, catalog: World) -> None:
    rows = client.post(
        "/parse-list",
        json={"text": '1.5 ק"ג עגבניות\nסלמון x2', "flex_defaults": {"t.fish": "close"}},
    ).json()["rows"]
    tomato, salmon = rows
    assert D(tomato["quantity"]) == D("1.5") and tomato["unit"] == "kg" and tomato["is_weighed"]
    assert tomato["canonical"]["canonical_id"] == catalog.canon["tomato"]
    assert salmon["flex_level"] == "close"  # inherited from the parent taxonomy node
    assert tomato["flex_level"] == "any_brand"


@pytest.mark.db
@pytest.mark.pgvector
def test_thirty_items_parse_under_two_seconds(client, catalog: World) -> None:
    names = [
        "חלב",
        "2 רסק עגבניות",
        "סלמון",
        "לחם אחיד",
        "ביצים L",
        "שמנת מתוקה",
        "חטיף וופל",
        '1 ק"ג עגבניות',
        "חלבב",
        "רסק עגבנייות",
    ]
    text = "\n".join((names * 3)[:30])
    client.post("/parse-list", json={"text": "חלב"})  # warm up the connection and plans
    started = time.perf_counter()
    r = client.post("/parse-list", json={"text": text})
    elapsed = time.perf_counter() - started
    assert r.status_code == 200 and len(r.json()["rows"]) == 30
    print(f"parse-list, 30 items: {elapsed:.3f} s")
    assert elapsed < 2.0


def test_search_hit_carries_the_arabic_name(client, db, world) -> None:
    db.execute(
        "UPDATE canonical_products SET names_ar = %s WHERE id = %s",
        (["حليب 3%", "حليب طازج 3%"], world.canon["milk3"]),
    )
    hits = client.get("/search", params={"q": "חלב"}).json()["hits"]
    named = {h["canonical"]["canonical_id"]: h["canonical"] for h in hits}
    assert named[world.canon["milk3"]]["display_name_ar"] == "حليب 3%"
    assert named[world.canon["milk3"]]["display_name_he"]
    assert all(
        c["display_name_ar"] is None for cid, c in named.items() if cid != world.canon["milk3"]
    )
