"""The vector retriever's nearest-neighbour steps must be served by their HNSW indexes.

On one real day (99,612 items) ``/parse-list`` took 0.5 to 0.9 s a list line because the combined
statement of ``smartcart_api.search._vector`` read every row of ``item_embeddings`` and sorted them
(``Seq Scan`` + top-N sort), instead of walking ``item_embeddings_hnsw``. The tests of a few hundred
rows cannot see that: at that size the planner is right to prefer the sequential scan. This file
loads enough rows for the planner to choose the index by cost alone (``enable_seqscan`` stays on)
and fails if a change to the SQL makes the index unusable (the query vector no longer a bind
parameter, ordering by ``1 - distance``, a join in front of the LIMIT, ...). The 100k-row timings
are in ``scripts/bench/search_scale.py``.
"""

from __future__ import annotations

import random

import pytest
from api_world import World

from smartcart_api.embedding import query_embedder, to_pgvector
from smartcart_api.search import VECTOR_MIN, _vector, _vector_sql, hnsw_settings, hybrid_search

pytestmark = [pytest.mark.db, pytest.mark.pgvector]

# The planner prefers a sequential scan plus top-N sort on a few thousand rows of 1024-float
# vectors (the heap holds only TOAST pointers, so a scan looks cheap) and the HNSW scan from about
# 6,000 rows with the statement's LIMIT of 80 and ef_search 160 (measured on pgvector 0.8.2 with
# hash vectors: 5,000 seq scan, 6,000 and up index). 8,000 leaves a margin for planner changes.
FILLER_ROWS = 8_000
K = 20
_WORDS = [
    "רסק", "עגבניות", "חלב", "טרי", "גבינה", "לבנה", "יוגורט", "שמן", "זית", "אורז", "פסטה",
    "קמח", "סוכר", "קפה", "תה", "שוקולד", "עוף", "בקר", "דג", "לחם", "ביצים", "מלפפון", "בצל",
    "תפוח", "בננה", "מים", "מיץ", "קולה", "בירה", "יין", "נייר", "סבון", "שמפו", "אבקה", "בקבוק",
    "גרם", "מל", "אסם", "תנובה", "שטראוס", "אוסם", "עלית", "טרה", "יטבתה", "מעדנות",
]  # fmt: skip
_SYLLABLES = ["לב", "מר", "גן", "דש", "סול", "ברן", "פיר", "ות", "קר", "טל", "שנ", "רוק", "הד", "אל"]  # fmt: skip


def _hnsw_indexes(db, table: str) -> list[tuple[str, str]]:
    return db.execute(
        "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = %s"
        " AND schemaname = current_schema() AND indexdef ILIKE '%%USING hnsw%%'",
        (table,),
    ).fetchall()


def _nodes(plan: dict):
    yield plan
    for child in plan.get("Plans", []):
        yield from _nodes(child)


def _scans(db, sql: str, params: dict) -> dict[str, list[str]]:
    """relation name -> the scan node types that read it, from ``EXPLAIN (FORMAT JSON)``."""
    out = db.execute("EXPLAIN (FORMAT JSON) " + sql, params).fetchone()[0]
    scans: dict[str, list[str]] = {}
    for node in _nodes(out[0]["Plan"]):
        if "Relation Name" in node:
            kind = node["Node Type"]
            if "Index Name" in node:
                kind += f" using {node['Index Name']}"
            scans.setdefault(node["Relation Name"], []).append(kind)
    return scans


def _params(text: str = "רסק עגבניות אסם") -> dict:
    embedder = query_embedder()
    return {
        "v": to_pgvector(embedder.embed_one(text)),
        "k": K,
        "k4": K * 4,
        "min": VECTOR_MIN,
        "model": embedder.model_name,
    }


def _fill_item_embeddings(db, rows: int) -> None:
    """``rows`` unrelated item vectors (hash embeddings of made-up names) of the query embedder's
    model. The HNSW indexes are rebuilt after the load, inside the test's transaction (rolled back):
    inserting into a live HNSW index costs about twice a build."""
    embedder = query_embedder()
    rng = random.Random(5)
    # Product-like names: real words, so the vectors overlap with the query's neighbourhood the way
    # a real catalog's do (a cloud of unrelated gibberish would leave the true neighbour unreachable
    # from the graph's entry point, which says nothing about the SQL), plus made-up brand words.
    names = [
        " ".join(
            [*rng.sample(_WORDS, rng.randint(1, 3)), "".join(rng.choices(_SYLLABLES, k=2))]
            + ([str(rng.choice([100, 250, 500, 750, 1000]))] if rng.random() < 0.5 else [])
        )
        for _ in range(rows)
    ]
    defs = _hnsw_indexes(db, "item_embeddings")
    assert defs, "item_embeddings has no HNSW index"
    for name, _ in defs:
        db.execute(f'DROP INDEX "{name}"')
    ids = [
        r[0]
        for r in db.execute(
            "INSERT INTO items (chain_id, item_code, raw_name)"
            " SELECT 't-c1', 'fill-' || n.i, n.name FROM unnest(%s::text[]) WITH ORDINALITY AS n(name, i)"
            " RETURNING id",
            (names,),
        ).fetchall()
    ]
    with (
        db.cursor() as cur,
        cur.copy("COPY item_embeddings (item_id, embedding, model) FROM STDIN") as copy,
    ):
        for item_id, vec in zip(ids, embedder.inner.embed(names), strict=True):
            copy.write_row((item_id, to_pgvector(vec), embedder.model_name))
    for _, indexdef in defs:
        db.execute(indexdef)
    db.execute("ANALYZE item_embeddings")


def test_item_vectors_are_read_through_the_hnsw_index(db, world: World) -> None:
    """With ``enable_seqscan`` on, the planner picks the item index (the statement's settings in
    force), for the Hebrew and the Arabic statement, and the search through it still finds the
    item that matches the query among unrelated ones, and its canonical."""
    paste = world.canon["paste"]
    db.execute("UPDATE canonical_products SET embedding_model = 'BAAI/bge-m3'")  # items only
    _fill_item_embeddings(db, FILLER_ROWS)
    hnsw_settings(db, K)
    for lang in (None, "ar"):
        scans = _scans(db, _vector_sql(lang), _params())
        assert scans["item_embeddings"] == ["Index Scan using item_embeddings_hnsw"], (lang, scans)
    found = _vector(db, "רסק עגבניות אסם", K)
    assert found and found[0][0] == paste and found[0][1] > 0.7
    assert paste in [h.canonical_id for h in hybrid_search(db, "רסק עגבניות אסם", limit=3)]


def test_every_nearest_neighbour_step_can_use_its_index(db, world: World) -> None:
    """The small tables (a few thousand canonicals) are scanned in full by the planner's choice,
    which is exact and as fast. Their statements still must be shaped for the index: with
    sequential scans and sorts off, each is served by its HNSW index."""
    db.execute("SET LOCAL enable_seqscan = off")
    db.execute("SET LOCAL enable_sort = off")
    scans = _scans(db, _vector_sql("ar"), _params())
    assert scans["canonical_products"] == ["Index Scan using canonical_products_embedding_hnsw"]
    assert scans["canonical_name_embeddings"] == ["Index Scan using canonical_name_embeddings_hnsw"]
    assert scans["item_embeddings"] == ["Index Scan using item_embeddings_hnsw"]


def test_hnsw_settings_hold_for_the_transaction_only(db) -> None:
    default = db.execute("SELECT current_setting('hnsw.ef_search', true)").fetchone()[0]
    hnsw_settings(db, K)
    ef, scan = db.execute(
        "SELECT current_setting('hnsw.ef_search'), current_setting('hnsw.iterative_scan', true)"
    ).fetchone()
    assert int(ef) >= K * 4, "the candidate list must be able to fill the LIMIT"
    version = db.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
    if tuple(int(p) for p in version[0].split(".")[:2]) >= (0, 8):
        assert scan == "relaxed_order"
    db.rollback()
    after = db.execute("SELECT current_setting('hnsw.ef_search', true)").fetchone()[0]
    assert not after or after == default, "set_config(..., true) is transaction-local"
