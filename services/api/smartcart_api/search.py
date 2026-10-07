"""Hybrid search over canonical products (issue #54), shared by GET /search and POST /parse-list.

Three retrievers, each returning up to ``per_retriever`` canonicals with a similarity in [0, 1]:

* ``trigram``: pg_trgm ``word_similarity`` (and ``similarity``) between the normalized query and
  the normalized display name, above ``TRIGRAM_MIN``. Tolerates typos.
* ``fts``: Postgres full-text search, ``simple`` configuration, prefix terms, each word also
  without its attached one-letter Hebrew prefix. Similarity = the share of query words found.
* ``vector``: pgvector cosine similarity between the query embedding and the canonical's
  embedding, or the embeddings of items mapped to it at ``exact``/``any_brand``, above
  ``VECTOR_MIN``.

Ranking is reciprocal rank fusion: ``rrf = sum(1 / (RRF_K + rank))`` over the retrievers that
found the canonical. ``score`` is that sum divided by its maximum (rank 1 in every enabled
retriever), so it lies in [0, 1].

``confidence`` is the evidence for one hit, used by the list parser's thresholds:
``0.85 * best similarity + 0.15 * share of enabled retrievers that found it``. RRF alone is a
rank statistic and says nothing about whether the best hit is any good, so it orders the hits
and the similarities calibrate them.

``specificity`` says how much of the canonical's name the query covers (trigram: mean of word
similarity and whole-string similarity; full text: share of query words times name coverage;
vector: the cosine similarity). It breaks ties inside each retriever ("עגבניות" prefers
tomatoes over tomato paste) and tells the parser when two hits are equally good (ambiguous).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

import psycopg

from smartcart_api.embedding import HashEmbedder, normalize_text, to_pgvector

Retriever = Literal["trigram", "fts", "vector"]
ALL_RETRIEVERS: tuple[Retriever, ...] = ("trigram", "fts", "vector")

RRF_K = 60
TRIGRAM_MIN = 0.3
VECTOR_MIN = 0.25
PER_RETRIEVER = 20
HEBREW_PREFIXES = "והבלמשכ"

_embedder = HashEmbedder()
_TOKEN = re.compile(r"[\w%.]+", re.UNICODE)


@dataclass
class Hit:
    canonical_id: int
    display_name_he: str
    taxonomy_id: str
    base_unit: str
    basket_rank: int | None
    similarity: dict[str, float] = field(default_factory=dict)
    specificity_by: dict[str, float] = field(default_factory=dict)
    ranks: dict[str, int] = field(default_factory=dict)
    rrf: float = 0.0
    score: float = 0.0
    confidence: float = 0.0
    specificity: float = 0.0
    category_path_he: list[str] = field(default_factory=list)

    @property
    def matched_by(self) -> list[Retriever]:
        return [r for r in ALL_RETRIEVERS if r in self.ranks]


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(normalize_text(text)) if t.strip(".")]


def _variants(token: str) -> list[str]:
    out = [token]
    # One attached prefix letter (ו, ה, ב, ל, מ, ש, כ), and ו + one more (וה, ול, ...).
    if len(token) > 3 and token[0] in HEBREW_PREFIXES:
        out.append(token[1:])
        if len(token) > 4 and token[0] == "ו" and token[1] in HEBREW_PREFIXES:
            out.append(token[2:])
    return out


def _tsquery(words: Sequence[str]) -> str | None:
    parts = []
    for w in words:
        safe = [re.sub(r"[^\w]", "", v) for v in _variants(w)]
        safe = [v for v in safe if v]
        if safe:
            parts.append("(" + " | ".join(f"{v}:*" for v in dict.fromkeys(safe)) + ")")
    return " | ".join(parts) if parts else None


def _fts_share(words: Sequence[str], name: str) -> tuple[float, float]:
    """(share of query words found in the name, share of name words matched)."""
    name_words = normalize_text(name).split()
    if not words or not name_words:
        return 0.0, 0.0
    hit_q = sum(
        1 for w in words if any(nw.startswith(v) for v in _variants(w) for nw in name_words)
    )
    hit_n = sum(
        1 for nw in name_words if any(nw.startswith(v) for w in words for v in _variants(w))
    )
    return hit_q / len(words), hit_n / len(name_words)


Ranked = list[tuple[int, float, float]]  # (canonical_id, similarity, specificity), best first


def _trigram(conn: psycopg.Connection, q: str, k: int) -> Ranked:
    conn.execute(
        "SELECT set_config('pg_trgm.word_similarity_threshold', %s, true)", (str(TRIGRAM_MIN),)
    )
    rows = conn.execute(
        "WITH q AS (SELECT search_norm(%(q)s) AS t)"
        " SELECT c.id, word_similarity(q.t, search_norm(c.display_name_he)) AS ws,"
        "        similarity(q.t, search_norm(c.display_name_he)) AS s"
        " FROM canonical_products AS c, q"
        " WHERE q.t <%% search_norm(c.display_name_he)"
        " ORDER BY ws DESC, s DESC, c.rank NULLS LAST, c.id LIMIT %(k)s",
        {"q": q, "k": k},
    ).fetchall()
    return [(r[0], float(r[1]), (float(r[1]) + float(r[2])) / 2) for r in rows]


def _fts(conn: psycopg.Connection, q: str, k: int) -> Ranked:
    words = tokens(q)
    query = _tsquery(words)
    if not query:
        return []
    rows = conn.execute(
        "SELECT c.id, c.display_name_he,"
        "  ts_rank_cd(to_tsvector('simple', search_norm(c.display_name_he)), tq) AS r"
        " FROM canonical_products AS c, to_tsquery('simple', %(tq)s) AS tq"
        " WHERE to_tsvector('simple', search_norm(c.display_name_he)) @@ tq"
        " ORDER BY r DESC, c.rank NULLS LAST, c.id LIMIT %(k)s",
        {"tq": query, "k": k * 2},
    ).fetchall()
    scored = []
    for cid, name, _ in rows:
        share, coverage = _fts_share(words, name)
        if share > 0:
            scored.append((cid, share, share * (0.5 + 0.5 * coverage)))
    scored.sort(key=lambda x: (-x[1], -x[2]))  # stable: ts_rank order among equals
    return scored[:k]


def _vector(conn: psycopg.Connection, q: str, k: int) -> Ranked:
    vec = to_pgvector(_embedder.embed_one(q))
    rows = conn.execute(
        "WITH qv AS (SELECT %(v)s::vector AS v),"
        " direct AS ("
        "   SELECT c.id AS canonical_id, 1 - (c.embedding <=> qv.v) AS s"
        "   FROM canonical_products AS c, qv WHERE c.embedding IS NOT NULL"
        "   ORDER BY c.embedding <=> qv.v LIMIT %(k)s),"
        " near_items AS ("
        "   SELECT e.item_id, 1 - (e.embedding <=> qv.v) AS s"
        "   FROM item_embeddings AS e, qv ORDER BY e.embedding <=> qv.v LIMIT %(k4)s),"
        " via_items AS ("
        "   SELECT ic.canonical_id, max(n.s) AS s FROM near_items AS n"
        "   JOIN item_canonical AS ic ON ic.item_id = n.item_id"
        "   WHERE ic.flex_level IN ('exact', 'any_brand') GROUP BY ic.canonical_id)"
        " SELECT canonical_id, max(s) AS s FROM (SELECT * FROM direct UNION ALL"
        "   SELECT * FROM via_items) AS u"
        " WHERE s >= %(min)s GROUP BY canonical_id ORDER BY s DESC, canonical_id LIMIT %(k)s",
        {"v": vec, "k": k, "k4": k * 4, "min": VECTOR_MIN},
    ).fetchall()
    return [(r[0], float(r[1]), float(r[1])) for r in rows]


_RETRIEVE = {"trigram": _trigram, "fts": _fts, "vector": _vector}


def hybrid_search(
    conn: psycopg.Connection,
    q: str,
    limit: int = 10,
    retrievers: Iterable[Retriever] = ALL_RETRIEVERS,
    per_retriever: int = PER_RETRIEVER,
) -> list[Hit]:
    """Canonical products for ``q``, best first by RRF. Disable retrievers to test each one."""
    enabled = [r for r in ALL_RETRIEVERS if r in set(retrievers)]
    if not q.strip() or not enabled:
        return []
    found: dict[str, Ranked] = {r: _RETRIEVE[r](conn, q, per_retriever) for r in enabled}
    ids = sorted({cid for hits in found.values() for cid, _, _ in hits})
    if not ids:
        return []
    meta = {
        r[0]: r
        for r in conn.execute(
            "SELECT id, display_name_he, taxonomy_id, base_unit, rank"
            " FROM canonical_products WHERE id = ANY(%s)",
            (ids,),
        ).fetchall()
    }
    hits: dict[int, Hit] = {}
    for name, ranked in found.items():
        for pos, (cid, sim, spec) in enumerate(ranked, start=1):
            m = meta[cid]
            h = hits.setdefault(cid, Hit(cid, m[1], m[2], m[3], m[4]))
            h.ranks[name] = pos
            h.similarity[name] = max(0.0, min(1.0, sim))
            h.specificity_by[name] = max(0.0, min(1.0, spec))
            h.rrf += 1.0 / (RRF_K + pos)
    best_possible = len(enabled) / (RRF_K + 1)
    for h in hits.values():
        h.score = round(h.rrf / best_possible, 6)
        h.confidence = round(
            0.85 * max(h.similarity.values()) + 0.15 * len(h.ranks) / len(enabled), 6
        )
        h.specificity = round(max(h.specificity_by.values()), 6)
    ordered = sorted(
        hits.values(),
        key=lambda h: (-h.rrf, -h.confidence, -h.specificity, h.basket_rank if h.basket_rank is not None else 1 << 30, h.canonical_id),
    )[:limit]
    paths = category_paths(conn, {h.taxonomy_id for h in ordered})
    for h in ordered:
        h.category_path_he = paths.get(h.taxonomy_id, [])
    return ordered


def category_paths(conn: psycopg.Connection, taxonomy_ids: Iterable[str]) -> dict[str, list[str]]:
    """taxonomy_id -> Hebrew names from the root down to that node."""
    ids = sorted(set(taxonomy_ids))
    if not ids:
        return {}
    rows = conn.execute(
        "WITH RECURSIVE up AS ("
        "  SELECT t.id AS leaf, t.id, t.parent_id, t.name_he, t.level FROM taxonomy t"
        "  WHERE t.id = ANY(%s)"
        "  UNION ALL"
        "  SELECT up.leaf, p.id, p.parent_id, p.name_he, p.level FROM up"
        "  JOIN taxonomy p ON p.id = up.parent_id)"
        " SELECT leaf, array_agg(name_he ORDER BY level) FROM up GROUP BY leaf",
        (ids,),
    ).fetchall()
    return {leaf: list(names) for leaf, names in rows}


def ancestors(conn: psycopg.Connection, taxonomy_ids: Iterable[str]) -> dict[str, list[str]]:
    """taxonomy_id -> ids from that node up to the root (the node itself first)."""
    ids = sorted(set(taxonomy_ids))
    if not ids:
        return {}
    rows = conn.execute(
        "WITH RECURSIVE up AS ("
        "  SELECT t.id AS leaf, t.id, t.parent_id, t.level FROM taxonomy t WHERE t.id = ANY(%s)"
        "  UNION ALL"
        "  SELECT up.leaf, p.id, p.parent_id, p.level FROM up JOIN taxonomy p ON p.id = up.parent_id)"
        " SELECT leaf, array_agg(id ORDER BY level DESC) FROM up GROUP BY leaf",
        (ids,),
    ).fetchall()
    return {leaf: list(chain) for leaf, chain in rows}
