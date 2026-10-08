"""Hybrid search over canonical products (issue #54), shared by GET /search and POST /parse-list.

Three retrievers, each returning up to ``per_retriever`` canonicals with a similarity in [0, 1]:

* ``trigram``: pg_trgm ``word_similarity`` (and ``similarity``) between the normalized query and
  the normalized display name, above ``TRIGRAM_MIN``. Tolerates typos.
* ``fts``: Postgres full-text search, ``simple`` configuration, prefix terms, each word also
  without its attached one-letter Hebrew prefix. Similarity = the share of query words found.
* ``vector``: pgvector cosine similarity between the query embedding and the canonical's
  embedding, or the embeddings of items mapped to it at ``exact``/``any_brand``, above
  ``VECTOR_MIN``. Only vectors of the query embedder's model are compared (see ``_vector``).

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

Arabic queries (issue #73): a query with more Arabic than Hebrew letters takes the Arabic path
(``_hybrid_search_ar``); Hebrew text never does. The trigram and full-text retrievers read
``canonical_products.names_ar`` through ``search_norm_ar()`` (spelling folded, ال and و tried as
removable prefixes); the vector retriever is unchanged and is *recall only* for Arabic: a hit found
by the vector retriever alone is shown as a candidate but never confident. Hard checks drop any
canonical whose critical attribute (fat %, fresh/frozen/canned, plant base, flavor) the query
contradicts, and confidence is capped when the query states fewer words than the matched name
(an unstated qualifier such as lactose-free) or states them in another order (حليب شوكولاتة is
not شوكولاتة حليب).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal, NamedTuple

import psycopg

from smartcart_api.embedding import normalize_text, query_embedder, to_pgvector
from smartcart_catalog.normalize import (
    ar_attributes,
    ar_clean_query,
    ar_conflicts,
    ar_strip_prefixes,
    ar_variants,
    normalize_ar,
    script_of,
)

Retriever = Literal["trigram", "fts", "vector"]
ALL_RETRIEVERS: tuple[Retriever, ...] = ("trigram", "fts", "vector")

RRF_K = 60
TRIGRAM_MIN = 0.3
VECTOR_MIN = 0.25
PER_RETRIEVER = 20
HEBREW_PREFIXES = "והבלמשכ"

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
    display_name_ar: str | None = None
    """The canonical's first Arabic name; filled on both paths, for the response."""
    names_ar: list[str] = field(default_factory=list)
    """The canonical's Arabic names; filled on the Arabic path only."""
    critical_attrs: dict = field(default_factory=dict)
    """The canonical's critical attributes; filled on the Arabic path only."""

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


def _vector(conn: psycopg.Connection, q: str, k: int, lang: str | None = None) -> Ranked:
    """Cosine similarity, only against vectors made by the query embedder's model.

    ``lang`` ``"ar"`` (the Arabic path) adds the canonicals' Arabic name vectors
    (``canonical_name_embeddings``, ``embed_canonical_names_ar``) to the Hebrew name vectors and
    the mapped items' vectors; a canonical's score is its best. Hebrew passes no ``lang`` and
    reads exactly what it always did.

    Vectors from two models live in different spaces, so comparing them is noise. The query is
    embedded with the catalog's embedder (``smartcart_api.embedding.query_embedder``), and only
    canonicals whose ``embedding_model`` and items whose ``item_embeddings.model`` equal its
    ``model_name`` are compared. A canonical with a NULL ``embedding_model`` is skipped: its
    model is unknown; the catalog's ``embed`` job fills the column (it re-embeds such rows).
    """
    embedder = query_embedder()
    vec = to_pgvector(embedder.embed_one(q))
    rows = conn.execute(
        "WITH qv AS (SELECT %(v)s::vector AS v),"
        " direct AS ("
        "   SELECT c.id AS canonical_id, 1 - (c.embedding <=> qv.v) AS s"
        "   FROM canonical_products AS c, qv WHERE c.embedding IS NOT NULL"
        "     AND c.embedding_model = %(model)s"
        "   ORDER BY c.embedding <=> qv.v LIMIT %(k)s),"
        " near_items AS ("
        "   SELECT e.item_id, 1 - (e.embedding <=> qv.v) AS s"
        "   FROM item_embeddings AS e, qv WHERE e.model = %(model)s"
        "   ORDER BY e.embedding <=> qv.v LIMIT %(k4)s),"
        + (
            " names_ar AS ("
            "   SELECT n.canonical_id, max(1 - (n.embedding <=> qv.v)) AS s"
            "   FROM canonical_name_embeddings AS n, qv"
            "   WHERE n.lang = 'ar' AND n.embedding_model = %(model)s"
            "   GROUP BY n.canonical_id ORDER BY s DESC LIMIT %(k)s),"
            if lang == "ar" else ""
        ) +
        " via_items AS ("
        "   SELECT ic.canonical_id, max(n.s) AS s FROM near_items AS n"
        "   JOIN item_canonical AS ic ON ic.item_id = n.item_id"
        "   WHERE ic.flex_level IN ('exact', 'any_brand') AND NOT ic.human_rejected"
        "     AND NOT ic.needs_review GROUP BY ic.canonical_id)"
        " SELECT canonical_id, max(s) AS s FROM (SELECT * FROM direct UNION ALL"
        + ("   SELECT * FROM names_ar UNION ALL" if lang == "ar" else "") +
        "   SELECT * FROM via_items) AS u"
        " WHERE s >= %(min)s GROUP BY canonical_id ORDER BY s DESC, canonical_id LIMIT %(k)s",
        {"v": vec, "k": k, "k4": k * 4, "min": VECTOR_MIN, "model": embedder.model_name},
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
    if script_of(q) == "ar":
        return _hybrid_search_ar(conn, q, limit, enabled, per_retriever)
    found: dict[str, Ranked] = {r: _RETRIEVE[r](conn, q, per_retriever) for r in enabled}
    ids = sorted({cid for hits in found.values() for cid, _, _ in hits})
    if not ids:
        return []
    meta = {
        r[0]: r
        for r in conn.execute(
            "SELECT id, display_name_he, taxonomy_id, base_unit, rank, names_ar[1]"
            " FROM canonical_products WHERE id = ANY(%s)",
            (ids,),
        ).fetchall()
    }
    hits: dict[int, Hit] = {}
    for name, ranked in found.items():
        for pos, (cid, sim, spec) in enumerate(ranked, start=1):
            m = meta[cid]
            h = hits.setdefault(cid, Hit(cid, m[1], m[2], m[3], m[4], display_name_ar=m[5]))
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


# --- Arabic (issue #73) ---------------------------------------------------------------------------

PREFIX_WEIGHT = 0.8
"""A query word that only starts a name word (not equal to it) counts this much."""
QUALIFIER_CAP = 0.70
"""Confidence cap when the query states fewer words than the best name (an unstated qualifier)."""
ORDER_CAP = 0.60
"""Confidence cap when the query's words are in another order than the name's."""
MIN_NAME_COVERAGE = 0.8
"""The query must cover this share of the best name's words, or confidence is capped at
``QUALIFIER_CAP``. Names are short, so a missing word is a qualifier the shopper did not state."""
VECTOR_ONLY_CAP = 0.60
"""A hit found only by the vector retriever (recall only for Arabic) is never more confident."""
LEXICAL: tuple[Retriever, ...] = ("trigram", "fts")


def _ar_query(q: str) -> str:
    """The normalized query without brands, soft descriptors and bare numbers, which the Arabic
    retrievers read."""
    return ar_clean_query(normalize_ar(q))


def ar_tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(normalize_ar(text)) if t.strip(".")]


def _is_number(token: str) -> bool:
    return any(ch.isdigit() for ch in token)


def _ar_forms(q: str) -> list[str]:
    """Query strings for the trigram retriever: as typed, without the article ال, and without the
    article and the conjunction و (the best similarity wins)."""
    norm = _ar_query(q)
    no_article = ar_strip_prefixes(norm)
    no_prefix = " ".join(ar_variants(t)[-1] for t in norm.split())
    return list(dict.fromkeys(f for f in (norm, no_article, no_prefix) if f))


def _ar_trigram(conn: psycopg.Connection, q: str, k: int) -> Ranked:
    forms = _ar_forms(q)
    if not forms:
        return []
    conn.execute(
        "SELECT set_config('pg_trgm.word_similarity_threshold', %s, true)", (str(TRIGRAM_MIN),)
    )
    cond = " OR ".join(f"%(f{i})s <%% canonical_names_ar_norm(c.names_ar)" for i in range(len(forms)))
    params: dict = {f"f{i}": f for i, f in enumerate(forms)} | {"k": k, "forms": forms}
    rows = conn.execute(
        "SELECT id, ws, s, name FROM ("
        "  SELECT c.id, x.ws, x.s, x.name, c.rank,"
        "    row_number() OVER (PARTITION BY c.id ORDER BY x.ws DESC, x.s DESC) AS rn"
        "  FROM canonical_products AS c"
        "  CROSS JOIN LATERAL ("
        "    SELECT word_similarity(f.t, search_norm_ar(n.name)) AS ws,"
        "           similarity(f.t, search_norm_ar(n.name)) AS s, n.name"
        "    FROM unnest(c.names_ar) AS n(name), unnest(%(forms)s::text[]) AS f(t)) AS x"
        f"  WHERE {cond}"
        ") AS t WHERE rn = 1 AND ws >= %(ws_min)s"
        " ORDER BY ws DESC, s DESC, rank NULLS LAST, id LIMIT %(k)s",
        params | {"ws_min": TRIGRAM_MIN},
    ).fetchall()
    words = ar_tokens(_ar_query(q))
    # Trigram similarity barely sees a fat percentage ("2%" is one short word), so equal
    # similarities are ordered by the share of the query's words (numbers compared whole) that
    # the best name contains.
    scored = [
        (cid, float(ws), (float(ws) + float(s)) / 2, _ar_share(words, normalize_ar(name)).share)
        for cid, ws, s, name in rows
    ]
    scored.sort(key=lambda x: (-round(x[1], 2), -x[3], -x[2]))
    return [(cid, ws, spec) for cid, ws, spec, _ in scored]


def _ar_tsquery(words: Sequence[str]) -> str | None:
    parts = []
    for w in words:
        safe = [re.sub(r"[^\w.]", "", v).strip(".") for v in ar_variants(w)]
        safe = [v for v in dict.fromkeys(safe) if v]
        if safe:
            parts.append("(" + " | ".join(f"'{v}':*" for v in safe) + ")")
    return " | ".join(parts) if parts else None


def _name_forms(word: str) -> list[str]:
    """A name word and the word without ال, for matching a query word against it."""
    return ar_variants(word)


def _prefix_match(query_word: str, name_word: str) -> bool:
    """A query word matches a name word when equal, or when the name word is the query word plus
    a short ending (بندور/بندورة, plural and feminine endings), never a different word that
    starts the same way (زيت/زيتون, لبن/لبنة). Words of up to three letters must be equal."""
    if len(query_word) < 4:
        return name_word == query_word  # لبن (yogurt) is not لبنة (labneh), موز is not موزاريلا
    return name_word.startswith(query_word) and len(name_word) - len(query_word) <= 2


class ArShare(NamedTuple):
    share: float
    """Share of the query's words found in the name."""
    coverage: float
    """Share of the name's non-numeric words the query covers."""
    in_order: bool
    """False when two matched non-numeric words are in another order in the name."""
    stray_percent: bool
    """The query states a percentage the name does not."""


def _ar_share(words: Sequence[str], name: str) -> ArShare:
    """How the query's words sit in one normalized name.

    Each query word is matched to one still unmatched name word: an equal word counts 1, a prefix
    (after the و/ال variants) counts ``PREFIX_WEIGHT``, so "طحين" (flour) is not as good a match
    for "طحينة" (tahini) as for "طحين". Words with a digit or % must be equal, so 3% never meets
    30%. Because each name word is used once, "زيت" covers only one of "زيت زيتون". Coverage
    ignores numeric name words ("لبنة" fully covers "لبنة 5%")."""
    name_words = name.split()
    if not words or not name_words:
        return ArShare(0.0, 0.0, True, False)
    taken: dict[int, float] = {}
    positions: list[int] = []
    hit_q = 0.0
    stray = False
    for w in words:
        numeric = _is_number(w)
        found = None
        weight = 1.0
        for strict in (True, False):
            for j, nw in enumerate(name_words):
                if j in taken:
                    continue
                if numeric or _is_number(nw):
                    ok = w == nw
                elif strict:
                    ok = any(v == nf for v in ar_variants(w) for nf in _name_forms(nw))
                else:
                    ok = any(
                        _prefix_match(v, nf) for v in ar_variants(w) for nf in _name_forms(nw)
                    )
                    weight = PREFIX_WEIGHT
                if ok:
                    found = j
                    break
            if found is not None:
                break
        if found is None:
            stray = stray or "%" in w
            continue
        taken[found] = weight
        hit_q += weight
        if not numeric:
            positions.append(found)
    content = {i for i, nw in enumerate(name_words) if not _is_number(nw)}
    coverage = (
        sum(w for i, w in taken.items() if i in content) / len(content)
        if content
        else sum(taken.values()) / len(name_words)
    )
    in_order = all(a < b for a, b in zip(positions, positions[1:], strict=False))
    return ArShare(hit_q / len(words), coverage, in_order, stray)


def _ar_fts(conn: psycopg.Connection, q: str, k: int) -> Ranked:
    words = ar_tokens(_ar_query(q))
    query = _ar_tsquery(words)
    if not query:
        return []
    rows = conn.execute(
        "SELECT c.id, c.names_ar FROM canonical_products AS c,"
        "   to_tsquery('simple', %(tq)s) AS tq"
        " WHERE to_tsvector('simple', canonical_names_ar_norm(c.names_ar)) @@ tq"
        " ORDER BY ts_rank_cd(to_tsvector('simple', canonical_names_ar_norm(c.names_ar)), tq) DESC,"
        "   c.rank NULLS LAST, c.id LIMIT %(k)s",
        {"tq": query, "k": k * 2},
    ).fetchall()
    scored = []
    for cid, names in rows:
        best = (0.0, 0.0)
        for name in names:
            sh = _ar_share(words, normalize_ar(name))
            best = max(best, (sh.share, sh.share * (0.5 + 0.5 * sh.coverage)))
        if best[0] > 0:
            scored.append((cid, best[0], best[1]))
    scored.sort(key=lambda x: (-x[1], -x[2]))
    return scored[:k]


def _vector_ar(conn: psycopg.Connection, q: str, k: int) -> Ranked:
    return _vector(conn, q, k, "ar")


_RETRIEVE_AR = {"trigram": _ar_trigram, "fts": _ar_fts, "vector": _vector_ar}


def _hard_checks(
    conn: psycopg.Connection, q: str, meta: dict[int, tuple]
) -> dict[int, list[str]]:
    """canonical_id -> the critical attributes of that canonical the query contradicts."""
    attrs = ar_attributes(_ar_query(q))
    if not (attrs.fat_pct or attrs.state or attrs.base or attrs.flavor):
        return {}
    types = sorted({m[5] for m in meta.values()})
    flavors: dict[str, set[str]] = {}
    for ptype, flavor in conn.execute(
        "SELECT product_type, critical_attrs->>'flavor' FROM canonical_products"
        " WHERE product_type = ANY(%s) AND critical_attrs ? 'flavor'",
        (types,),
    ).fetchall():
        flavors.setdefault(ptype, set()).add(str(flavor))
    out = {}
    for cid, m in meta.items():
        bad = ar_conflicts(attrs, m[6], frozenset(flavors.get(m[5], ())))
        if bad:
            out[cid] = bad
    return out


def _hybrid_search_ar(
    conn: psycopg.Connection,
    q: str,
    limit: int,
    enabled: list[Retriever],
    per_retriever: int,
) -> list[Hit]:
    if not any(sum(ch.isalpha() for ch in t) >= 2 for t in ar_tokens(_ar_query(q))):
        return []  # nothing to match: a lone letter, digits
    found: dict[str, Ranked] = {r: _RETRIEVE_AR[r](conn, q, per_retriever) for r in enabled}
    ids = sorted({cid for hits in found.values() for cid, _, _ in hits})
    if not ids:
        return []
    meta = {
        r[0]: r
        for r in conn.execute(
            "SELECT id, display_name_he, taxonomy_id, base_unit, rank, product_type,"
            "       critical_attrs, names_ar"
            " FROM canonical_products WHERE id = ANY(%s)",
            (ids,),
        ).fetchall()
    }
    vetoed = _hard_checks(conn, q, meta)
    if vetoed:
        found = {r: [x for x in hits if x[0] not in vetoed] for r, hits in found.items()}
    query_words = ar_tokens(_ar_query(q))
    hits: dict[int, Hit] = {}
    for name, ranked in found.items():
        for pos, (cid, sim, spec) in enumerate(ranked, start=1):
            m = meta[cid]
            h = hits.setdefault(
                cid,
                Hit(cid, m[1], m[2], m[3], m[4], display_name_ar=m[7][0] if m[7] else None,
                    names_ar=list(m[7]), critical_attrs=m[6]),
            )
            h.ranks[name] = pos
            h.similarity[name] = max(0.0, min(1.0, sim))
            h.specificity_by[name] = max(0.0, min(1.0, spec))
            h.rrf += 1.0 / (RRF_K + pos)
    best_possible = len(enabled) / (RRF_K + 1)
    for h in hits.values():
        h.score = round(h.rrf / best_possible, 6)
        lexical = [h.similarity[r] for r in LEXICAL if r in h.similarity]
        if lexical:
            share = len(h.ranks) / len(enabled)
            conf = 0.85 * max(lexical) + 0.15 * share
            h.specificity = round(
                max(h.specificity_by[r] for r in LEXICAL if r in h.specificity_by), 6
            )
            conf = _ar_caps(conf, query_words, h.names_ar)
        else:
            # recall only: the vector retriever may suggest, never convince
            conf = min(VECTOR_ONLY_CAP, 0.85 * h.similarity.get("vector", 0.0))
            h.specificity = round(h.specificity_by.get("vector", 0.0), 6)
        h.confidence = round(conf, 6)
    ordered = sorted(
        hits.values(),
        key=lambda h: (-h.rrf, -h.confidence, -h.specificity, h.basket_rank if h.basket_rank is not None else 1 << 30, h.canonical_id),
    )[:limit]
    paths = category_paths(conn, {h.taxonomy_id for h in ordered})
    for h in ordered:
        h.category_path_he = paths.get(h.taxonomy_id, [])
    return ordered


def _ar_caps(conf: float, words: Sequence[str], names: Sequence[str]) -> float:
    """Cap the confidence of a lexical hit by its best name: an unstated qualifier, a different
    word order or a percentage the name lacks means the shopper may mean something else, so the
    user confirms."""
    best = None
    for name in names:
        sh = _ar_share(words, normalize_ar(name))
        if best is None or (sh.share, sh.coverage, sh.in_order) > (
            best.share, best.coverage, best.in_order
        ):
            best = sh
    if best is None:
        return conf
    if not best.in_order:
        conf = min(conf, ORDER_CAP)
    if best.coverage < MIN_NAME_COVERAGE or best.stray_percent:
        conf = min(conf, QUALIFIER_CAP)
    return conf
