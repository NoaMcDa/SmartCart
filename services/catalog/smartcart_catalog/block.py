"""Blocking and top-k candidate retrieval (issue #29, architecture section 3 step C).

Block first, then search: an item is only ever compared with canonicals whose ``taxonomy_id`` is
inside the item's block prefix and whose ``base_unit`` equals the item's base unit. Within the
block, candidates are ranked by cosine distance (``<=>``) on ``canonical_products.embedding``,
which carries an HNSW index (``vector_cosine_ops``).

``top_k`` is one SQL statement. Two notes on the HNSW index:

* Whether the planner uses it is a cost decision. pgvector's cost model barely costs the
  distance computation on TOASTed vectors, so a seq scan plus top-N sort looks cheaper on small
  tables (measured on this schema with pgvector 0.6: HNSW path about 200-260, seq scan 11-36 at
  300-1,000 rows; the crossover, extrapolated, is in the tens of thousands of rows). At MVP size (150-300 canonicals) the exact seq scan is what runs, which is
  also the most accurate. The statement keeps the index-friendly shape (ORDER BY the raw ``<=>``
  distance, LIMIT k) so the index takes over as the catalog grows; ``tests/test_block.py``
  proves the index can serve it.
* HNSW applies the block filter after the index scan. With a selective block, an index scan can
  return fewer than k rows. pgvector 0.8+ fixes this with iterative index scans, which
  ``configure_session`` turns on when the server supports it (Supabase's Postgres 17 image ships
  0.8); it also raises ``hnsw.ef_search`` above k. On older pgvector a selective block usually
  gets the btree block index plus an exact sort, which is also exact.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import psycopg

from smartcart_catalog.models import BaseUnit, Candidate, CanonicalProduct

_FINAL_FORMS = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})
_NIKUD = re.compile(r"[֑-ׇ]")
_PUNCT = re.compile(r"[\"'`׳״.,;:()\[\]{}/\\|_+*!?־–—-]+")
_SPACES = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Lowercase, strip nikud and quote marks, fold Hebrew final letters, collapse spaces.

    Digits and ``%`` are kept: "3%" and "1%" must stay distinguishable, even if only a little.
    """
    t = unicodedata.normalize("NFKC", text).lower()
    t = _NIKUD.sub("", t).translate(_FINAL_FORMS)
    t = _PUNCT.sub(" ", t)
    return _SPACES.sub(" ", t).strip()


_WEIGHT_UNITS = {
    "g", "gr", "gram", "grams", "גרם", "גרמים", "ג", "גר",
    "kg", "kilo", "ק\"ג", "קג", "קילו", "קילוגרם",
}  # fmt: skip
_VOLUME_UNITS = {
    "ml", "l", "lt", "liter", "litre", "liters", "מ\"ל", "מל", "מיליליטר", "ליטר", "ליטרים", "ל",
}  # fmt: skip
_COUNT_UNITS = {"unit", "units", "יח", "יחידה", "יחידות", "יח'", "מארז", "pcs", "pc"}


@dataclass(frozen=True)
class Block:
    """Where an item may look for candidates. ``prefix`` None means any taxonomy."""

    prefix: str | None
    base_unit: BaseUnit | None

    def describe(self) -> str:
        return f"{self.prefix or '*'} / {self.base_unit or '*'}"


def block_prefix(category_path: str | None, depth: int = 1) -> str | None:
    """The first ``depth`` dot-separated levels of a taxonomy id (``dairy.milk.fresh`` with
    depth 1 is ``dairy``). Depth 1 (department) is the default: wide enough not to lose recall
    to a wrong second-level guess, narrow enough to keep olive oil away from canola oil in a
    different department."""
    if not category_path:
        return None
    parts = [p for p in category_path.strip().split(".") if p]
    return ".".join(parts[:depth]) if parts else None


def base_unit_for(unit: str | None, *, is_weighed: bool = False) -> BaseUnit | None:
    """Map a raw or normalized unit to the comparison base unit (decision D6)."""
    if is_weighed:
        return "kg"
    if not unit:
        return None
    u = unit.strip().lower().replace("׳", "'").replace("״", '"').rstrip(".")
    if u in _WEIGHT_UNITS:
        return "100g"
    if u in _VOLUME_UNITS:
        return "100ml"
    if u in _COUNT_UNITS:
        return "unit"
    if u in {"100g", "100ml", "unit", "kg"}:
        return u  # type: ignore[return-value]
    return None


def prefix_like(prefix: str) -> str:
    """LIKE pattern for the descendants of ``prefix`` (escaping LIKE wildcards)."""
    escaped = re.sub(r"([\\%_])", r"\\\1", prefix)
    return escaped + ".%"


TOP_K_SQL = """
SELECT c.id, 1 - c.distance AS similarity, c.taxonomy_id, c.slug, c.display_name_he,
       c.product_type, c.base_unit, c.critical_attrs, c.soft_attrs, c.is_mvp, c.rank
FROM item_embeddings e
CROSS JOIN LATERAL (
  SELECT cp.*, cp.embedding <=> e.embedding AS distance
  FROM canonical_products cp
  WHERE cp.embedding IS NOT NULL
    AND (%(base_unit)s::text IS NULL OR cp.base_unit = %(base_unit)s::text)
    AND (%(prefix)s::text IS NULL OR cp.taxonomy_id = %(prefix)s::text
         OR cp.taxonomy_id LIKE %(like)s::text)
  ORDER BY cp.embedding <=> e.embedding
  LIMIT %(k)s
) c
WHERE e.item_id = %(item_id)s
ORDER BY c.distance, c.id
"""


def _canonical_from_row(row: tuple[Any, ...]) -> CanonicalProduct:
    cid, _sim, taxonomy_id, slug, name, ptype, base_unit, crit, soft, is_mvp, rank = row
    return CanonicalProduct(
        id=cid,
        taxonomy_id=taxonomy_id,
        slug=slug,
        display_name_he=name,
        product_type=ptype,
        base_unit=base_unit,
        critical_attrs=crit if isinstance(crit, dict) else json.loads(crit or "{}"),
        soft_attrs=soft if isinstance(soft, dict) else json.loads(soft or "{}"),
        is_mvp=is_mvp,
        rank=rank,
    )


def top_k(
    conn: psycopg.Connection,
    item_id: int,
    k: int = 10,
    taxonomy_prefix: str | None = None,
    base_unit: str | None = None,
) -> list[Candidate]:
    """The ``k`` nearest canonicals to the item's embedding inside its block, best first, in a
    single SQL statement. ``similarity`` is cosine similarity (1 - cosine distance). Returns an
    empty list if the item has no embedding."""
    params = {
        "item_id": item_id,
        "k": k,
        "prefix": taxonomy_prefix,
        "like": prefix_like(taxonomy_prefix) if taxonomy_prefix else None,
        "base_unit": base_unit,
    }
    rows = conn.execute(TOP_K_SQL, params).fetchall()
    return [
        Candidate(canonical_id=r[0], similarity=float(r[1]), canonical=_canonical_from_row(r))
        for r in rows
    ]


def pgvector_version(conn: psycopg.Connection) -> tuple[int, ...] | None:
    row = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
    if not row:
        return None
    return tuple(int(p) for p in re.findall(r"\d+", row[0])[:3])


def configure_session(conn: psycopg.Connection, ef_search: int = 100) -> None:
    """Session settings for filtered HNSW search: iterative scans on pgvector >= 0.8 so a
    selective block still returns k rows, and a larger candidate list (``hnsw.ef_search``)."""
    version = pgvector_version(conn)
    if version is None:
        return
    conn.execute(f"SET hnsw.ef_search = {int(ef_search)}")
    if version >= (0, 8, 0):
        conn.execute("SET hnsw.iterative_scan = relaxed_order")
