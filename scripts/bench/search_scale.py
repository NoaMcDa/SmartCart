"""Benchmark /search and /parse-list at a real catalog size (synthetic embeddings).

On one real day (99,612 items) a list line took 0.5 to 0.9 s because the vector statement of
``smartcart_api.search`` scanned every row of ``item_embeddings`` (docs/real-day-dry-run.md). The
unit tests run on a few hundred rows and cannot see that. This script fills a scratch database with
~100k synthetic item embeddings (the catalog's hash embedder over made-up Hebrew names; real names
are not needed for timing, but hashed n-grams cluster like real text, unlike random vectors),
builds the indexes the migrations create, then times ``hybrid_search`` for 1, 6 and 33 list lines
and records the plan of each vector statement.

    DATABASE_URL=postgresql://postgres:postgres@localhost:55443/bench \\
        uv run python scripts/bench/search_scale.py setup --items 100000   # once, minutes
    DATABASE_URL=... uv run python scripts/bench/search_scale.py run        # timings and plans

The database must already be migrated (``uv run smartcart-ingest migrate``). ``setup`` is
idempotent: it tops the tables up to ``--items`` and skips what is there. It writes only synthetic
rows (chain ``bench``) and ``clean`` deletes them. Not part of the default test run.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time

import psycopg
import psycopg.sql

from smartcart_api.embedding import query_embedder, to_pgvector
from smartcart_api.search import hybrid_search

CHAIN = "bench"
N_CANONICALS = 3000

# Made-up product vocabulary: enough distinct words that names are varied and n-grams spread.
_SYL = [
    "לב",
    "מר",
    "גן",
    "דש",
    "סול",
    "ברן",
    "פיר",
    "ות",
    "קר",
    "טל",
    "שנ",
    "רוק",
    "הד",
    "אל",
    "ים",
]
_FORMS = ["", "ה", "ים", "ות", "ון", "ית"]

LIST_LINES = [
    "חלב 3%", "ביצים L", "עגבניות", "לחם אחיד", "גבינה צהובה", "יוגורט טבעי",
    "שמן זית", "אורז בסמטי", "פסטה", "קוטג׳ 5%", "מלפפונים", "בננות",
    "קפה נמס", "סוכר", "קמח", "שוקולד חלב", "עוף שלם", "חזה עוף",
    "נקניקיות", "טונה בשמן", "מיונז", "קטשופ", "חומוס", "טחינה",
    "מים מינרליים", "קולה זירו", "נייר טואלט", "אבקת כביסה", "שמפו", "משחת שיניים",
    "בצל", "תפוחי אדמה", "גזר",
]  # fmt: skip


def _word(rng: random.Random) -> str:
    return "".join(rng.choice(_SYL) for _ in range(rng.randint(1, 2))) + rng.choice(_FORMS)


def _name(rng: random.Random, vocab: list[str]) -> str:
    words = [rng.choice(vocab) for _ in range(rng.randint(2, 4))]
    if rng.random() < 0.4:
        words.append(f"{rng.choice([1, 2, 3, 5, 250, 500, 750])}")
    return " ".join(words)


def _insert_vectors(conn: psycopg.Connection, sql: str, rows: list[tuple]) -> None:
    with conn.cursor() as cur, cur.copy(sql) as copy:
        for r in rows:
            copy.write_row(r)


def setup(conn: psycopg.Connection, items: int, seed: int = 7) -> None:
    emb = query_embedder()
    model = emb.model_name
    rng = random.Random(seed)
    vocab = sorted({_word(rng) for _ in range(1500)} | {w.split()[0] for w in LIST_LINES})
    conn.execute(
        "INSERT INTO chains (id, name, portal) VALUES (%s, 'bench', 'other') ON CONFLICT DO NOTHING",
        (CHAIN,),
    )
    conn.execute(
        "INSERT INTO taxonomy (id, level, name_he) VALUES ('bench', 1, 'bench')"
        " ON CONFLICT DO NOTHING"
    )
    conn.execute(
        "INSERT INTO product_type_rules (product_type) VALUES ('bench') ON CONFLICT DO NOTHING"
    )
    have_c = conn.execute(
        "SELECT count(*) FROM canonical_products WHERE slug LIKE 'bench-%'"
    ).fetchone()[0]
    for start in range(have_c, N_CANONICALS, 500):
        names = [_name(rng, vocab) for _ in range(min(500, N_CANONICALS - start))]
        vecs = emb.inner.embed(names)
        for i, (name, vec) in enumerate(zip(names, vecs, strict=True)):
            conn.execute(
                "INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type,"
                " base_unit, embedding, embedding_model, rank)"
                " VALUES ('bench', %s, %s, 'bench', 'unit', %s::vector, %s, %s)",
                (f"bench-{start + i}", name, to_pgvector(vec), model, start + i),
            )
    conn.commit()
    canon_ids = [
        r[0]
        for r in conn.execute(
            "SELECT id FROM canonical_products WHERE slug LIKE 'bench-%' ORDER BY id"
        ).fetchall()
    ]
    have = conn.execute("SELECT count(*) FROM items WHERE chain_id = %s", (CHAIN,)).fetchone()[0]
    print(f"items: have {have}, want {items}", file=sys.stderr)
    # Bulk loading into a live HNSW index is slow: drop the item_embeddings vector indexes (their
    # definitions are kept) and build them once at the end.
    index_defs = conn.execute(
        "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'item_embeddings'"
        " AND indexdef ILIKE '%hnsw%' AND schemaname = current_schema()"
    ).fetchall()
    if have < items:
        for name, _ in index_defs:
            conn.execute(psycopg.sql.SQL("DROP INDEX {}").format(psycopg.sql.Identifier(name)))
        conn.commit()
    t0 = time.time()
    for start in range(have, items, 1000):
        n = min(1000, items - start)
        names = [_name(rng, vocab) for _ in range(n)]
        ids = [
            r[0]
            for r in conn.execute(
                "INSERT INTO items (chain_id, item_code, raw_name)"
                " SELECT %s, 'b' || g, name FROM unnest(%s::text[], %s::int[]) AS t(name, g)"
                " RETURNING id",
                (CHAIN, names, list(range(start, start + n))),
            ).fetchall()
        ]
        vecs = emb.inner.embed(names)
        _insert_vectors(
            conn,
            "COPY item_embeddings (item_id, embedding, model) FROM STDIN",
            [(i, to_pgvector(v), model) for i, v in zip(ids, vecs, strict=True)],
        )
        # ~35% of items are mapped to a canonical, mostly any_brand, some exact and close.
        maps = [
            (i, rng.choice(canon_ids), rng.choice(["exact", "any_brand", "any_brand", "close"]))
            for i in ids
            if rng.random() < 0.35
        ]
        _insert_vectors(
            conn,
            "COPY item_canonical (item_id, canonical_id, flex_level, confidence, source)"
            " FROM STDIN",
            [(i, c, f, 0.9, "rule") for i, c, f in maps],
        )
        conn.commit()
        if (start // 1000) % 10 == 0:
            print(f"  {start + n} items, {time.time() - t0:.0f}s", file=sys.stderr)
    conn.execute("SET maintenance_work_mem = '1GB'")
    conn.execute("SET max_parallel_maintenance_workers = 0")
    if have < items:
        for name, indexdef in index_defs:
            print(f"building {name}", file=sys.stderr)
            t1 = time.time()
            conn.execute(indexdef)
            conn.commit()
            print(f"  {time.time() - t1:.0f}s", file=sys.stderr)
    print("building statistics", file=sys.stderr)
    conn.autocommit = True
    conn.execute("VACUUM ANALYZE items")
    conn.execute("VACUUM ANALYZE item_embeddings")
    conn.execute("VACUUM ANALYZE item_canonical")
    conn.execute("VACUUM ANALYZE canonical_products")
    print("done", file=sys.stderr)


def clean(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM items WHERE chain_id = %s", (CHAIN,))
    conn.execute("DELETE FROM canonical_products WHERE slug LIKE 'bench-%'")
    conn.commit()


def _timed(conn: psycopg.Connection, lines: list[str], repeat: int) -> float:
    best = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        for line in lines:
            hybrid_search(conn, line, limit=12)
            conn.commit()
        best.append((time.perf_counter() - t0) * 1000)
    return statistics.median(best)


def vector_plan(conn: psycopg.Connection) -> dict[str, list[str]] | str:
    """Relation -> scan node types of the vector retriever's statement (EXPLAIN FORMAT JSON)."""
    from smartcart_api import search

    build = getattr(search, "_vector_sql", None)
    if build is None:  # before the fix the statement was built inline in _vector
        return "not available"
    embedder = query_embedder()
    params = {
        "v": to_pgvector(embedder.embed_one(LIST_LINES[0])),
        "k": 20,
        "k4": 80,
        "min": search.VECTOR_MIN,
        "model": embedder.model_name,
    }
    search.hnsw_settings(conn, 20)
    plan = conn.execute("EXPLAIN (FORMAT JSON) " + build(), params).fetchone()[0][0]["Plan"]
    scans: dict[str, list[str]] = {}
    todo = [plan]
    while todo:
        node = todo.pop()
        todo.extend(node.get("Plans", []))
        if "Relation Name" in node:
            kind = node["Node Type"]
            if "Index Name" in node:
                kind += f" using {node['Index Name']}"
            scans.setdefault(node["Relation Name"], []).append(kind)
    conn.rollback()
    return scans


def run(conn: psycopg.Connection, repeat: int) -> dict:
    out: dict = {"model": query_embedder().model_name}
    out["item_embeddings"] = conn.execute("SELECT count(*) FROM item_embeddings").fetchone()[0]
    out["pgvector"] = conn.execute(
        "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
    ).fetchone()[0]
    out["indexes"] = [
        r[0]
        for r in conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename IN"
            " ('item_embeddings', 'canonical_products') AND indexdef ILIKE '%hnsw%'"
        ).fetchall()
    ]
    out["vector_plan"] = vector_plan(conn)
    hybrid_search(conn, LIST_LINES[0])  # warm caches and the query embedder
    conn.commit()
    out["ms"] = {}
    for n in (1, 6, 33):
        out["ms"][f"{n}_lines"] = round(_timed(conn, LIST_LINES[:n], repeat), 1)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("command", choices=["setup", "run", "clean"])
    p.add_argument("--items", type=int, default=100_000)
    p.add_argument("--repeat", type=int, default=3)
    args = p.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is required (a scratch, migrated database)")
    with psycopg.connect(url) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        if args.command == "setup":
            setup(conn, args.items)
        elif args.command == "clean":
            clean(conn)
        else:
            print(json.dumps(run(conn, args.repeat), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
