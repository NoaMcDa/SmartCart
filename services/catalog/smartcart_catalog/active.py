"""Active learning for the catalog (issue #52): what a reviewer should look at first, how fast
they label, and which products the catalog should learn next.

``select_for_review`` fills the review queue. Human time is the scarce resource, so the queue is
not "oldest first" but "where a label changes the most":

1. **user reports.** Mappings that users called "not a good substitute"
   (``substitution_feedback``, verdict ``not_good``), most reports first. A person already looked
   at the pair and disagreed with us; that is the strongest signal there is.
2. **closeness to the accept threshold.** ``|confidence - ACCEPT_THRESHOLD|`` ascending. A pair
   at 0.89 could go either way; a pair at 0.62 is almost certainly reviewed and rejected, a pair at
   0.99 would have been accepted. Distances are cut into bands of ``DISTANCE_BAND`` (0.02, a
   choice, not a measurement) so that the next two keys can break ties; with exact distances they
   would almost never apply.
3. **embedder disagreement.** When the item and the canonical both have a vector from a learned
   model (``item_embeddings.model`` equals ``canonical_products.embedding_model`` and is not the
   hash model), the learned cosine similarity is compared with the cosine similarity of the two
   names under the hash embedder (character n-grams: spelling, no meaning). A large gap means one
   sees a match the other does not, which is where the judge is least reliable. ``item_embeddings``
   keeps one vector per item, so "the other embedder" is recomputed from the names; pairs whose
   stored vectors are hash vectors have only one embedder, so no disagreement is known (counted
   as 0).
4. **basket rank.** ``canonical_products.rank`` ascending: a mistake on milk costs more than one on
   a niche spread.

The result is the order of the keys above, then ``item_id``. Pairs a human rejected
(``human_rejected``) are never in the queue.

``labels_per_hour`` is the throughput metric from the reviewers' own decision timestamps
(``item_canonical.reviewed_at`` with ``source = 'human'``): labels divided by active time, where
active time adds up the gaps between consecutive labels of one reviewer that are shorter than
``SESSION_GAP_MINUTES`` (a longer gap is a break, not work), plus one typical gap per session for
the first label. A re-decision overwrites the row's ``reviewed_at``, so a label is counted once,
at its latest decision; a re-map writes two rows (the rejection and the new mapping).

``catalog_backlog`` runs ``supabase/queries/catalog_backlog.sql``: the expansion input, ranked
from search misses and from products in the price files that no canonical covers.
"""

from __future__ import annotations

import math
import os
import statistics
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg

from smartcart_catalog.embed import HASH_MODEL_NAME, HashEmbedder
from smartcart_catalog.judge import ACCEPT_THRESHOLD

DISTANCE_BAND = 0.02
SESSION_GAP_MINUTES = 10
DEFAULT_GAP_SECONDS = 60.0
QUERIES_DIR_ENV = "SMARTCART_QUERIES_DIR"

FEEDBACK_SQL = (
    "(SELECT count(*) FROM substitution_feedback f WHERE f.substitute_item_id = ic.item_id"
    " AND f.canonical_id = ic.canonical_id AND f.verdict = 'not_good')"
)

_KEYS = ("item_id", "canonical_id", "item_name", "chain_id", "barcode", "canonical_slug",
         "canonical_name", "canonical_rank", "flex_level", "confidence", "source", "attrs",
         "verified_keys", "feedback", "reason")  # fmt: skip


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def select_for_review(
    conn: psycopg.Connection,
    limit: int = 100,
    *,
    threshold: float = ACCEPT_THRESHOLD,
    band: float = DISTANCE_BAND,
) -> list[dict[str, Any]]:
    """The ``limit`` pending mappings a reviewer should label first (order in the module doc).

    Each row has the keys the review UI shows (``item_id``, ``canonical_id``, ``item_name``,
    ``canonical_name``, ``flex_level``, ``confidence``, ``attrs``, ``reason`` ...), the marker
    ``feedback_marker`` and the keys the order came from: ``reports`` (user reports),
    ``distance`` (to ``threshold``) and ``disagreement`` (None when it cannot be computed).
    """
    if limit <= 0:
        return []
    # Stage 1: only what the order needs, in the order of the first two keys. Names are fetched
    # only for pairs whose stored vectors can be compared with the hash embedder.
    light = conn.execute(
        f"""
        SELECT ic.item_id, ic.canonical_id, {FEEDBACK_SQL} AS reports,
               floor(abs(ic.confidence::float8 - %(thr)s) / %(band)s)::int AS band_idx,
               abs(ic.confidence::float8 - %(thr)s) AS distance,
               cp.rank,
               CASE WHEN ie.model = cp.embedding_model AND ie.model <> %(hash)s
                    THEN 1 - (ie.embedding <=> cp.embedding) END AS learned_cosine,
               CASE WHEN ie.model = cp.embedding_model AND ie.model <> %(hash)s
                    THEN i.raw_name END AS item_name,
               CASE WHEN ie.model = cp.embedding_model AND ie.model <> %(hash)s
                    THEN cp.display_name_he END AS canonical_name
        FROM item_canonical ic
        JOIN items i ON i.id = ic.item_id
        JOIN canonical_products cp ON cp.id = ic.canonical_id
        LEFT JOIN item_embeddings ie ON ie.item_id = ic.item_id
        WHERE ic.needs_review AND NOT ic.human_rejected
        ORDER BY reports DESC, band_idx ASC
        """,
        {"thr": threshold, "hash": HASH_MODEL_NAME, "band": band},
    ).fetchall()
    # Walk the groups of equal (reports, band) until the limit is covered, so the tie-breakers
    # only run where they can change which rows are in the first ``limit``.
    groups: list[list[tuple]] = []
    taken = 0
    last_key: tuple | None = None
    for row in light:
        key = (row[2], row[3])
        if key != last_key:
            if taken >= limit:
                break
            groups.append([])
            last_key = key
        groups[-1].append(row)
        taken += 1
    hasher = HashEmbedder()
    ordered: list[tuple[int, int, int, float, float | None]] = []
    for members in groups:
        scored = []
        for item_id, canonical_id, reports, _band, distance, rank, learned, name, canon in members:
            disagreement = None
            if learned is not None and name and canon:
                a, b = hasher.embed([name, canon])
                disagreement = round(abs(float(learned) - _cosine(a, b)), 3)  # float4 noise is not signal
            scored.append((item_id, canonical_id, reports, distance, disagreement, rank))
        # no known disagreement counts as none; then the best seller first
        scored.sort(key=lambda s: (
            -(s[4] or 0.0), s[5] is None, s[5] if s[5] is not None else 0, s[0], s[1]
        ))
        ordered.extend((s[0], s[1], s[2], s[3], s[4]) for s in scored)
    chosen = ordered[:limit]
    if not chosen:
        return []
    # Stage 2: the rows the reviewer sees, for the chosen pairs only.
    pairs = [(c[0], c[1]) for c in chosen]
    details = {}
    for r in conn.execute(
        f"""
        SELECT ic.item_id, ic.canonical_id, i.raw_name, i.chain_id, i.barcode, cp.slug,
               cp.display_name_he, cp.rank, ic.flex_level, ic.confidence, ic.source,
               a.attrs, a.verified_keys, {FEEDBACK_SQL} AS feedback, ic.reason
        FROM item_canonical ic
        JOIN items i ON i.id = ic.item_id
        JOIN canonical_products cp ON cp.id = ic.canonical_id
        LEFT JOIN item_attributes a ON a.item_id = ic.item_id
        WHERE (ic.item_id, ic.canonical_id) IN (SELECT * FROM unnest(%s::bigint[], %s::bigint[]))
        """,
        ([p[0] for p in pairs], [p[1] for p in pairs]),
    ).fetchall():
        details[(r[0], r[1])] = dict(zip(_KEYS, r, strict=True))
    out = []
    for item_id, canonical_id, reports, distance, disagreement in chosen:
        d = details[(item_id, canonical_id)]
        d["confidence"] = float(d["confidence"])
        d["feedback_marker"] = d["feedback"] > 0
        d["reason"] = d["reason"] or ""
        d["reports"] = reports
        d["distance"] = round(distance, 4)
        d["disagreement"] = disagreement
        out.append(d)
    return out


# --- labels per hour --------------------------------------------------------------------------


def _active_seconds(times: list[datetime], gap: timedelta) -> float:
    """Working time implied by one reviewer's sorted decision timestamps."""
    if not times:
        return 0.0
    in_session = [(b - a).total_seconds() for a, b in zip(times, times[1:], strict=False) if b - a <= gap]
    typical = statistics.median(in_session) if in_session else DEFAULT_GAP_SECONDS
    sessions = 1 + sum(1 for a, b in zip(times, times[1:], strict=False) if b - a > gap)
    return sum(in_session) + typical * sessions


def labels_per_hour(
    conn: psycopg.Connection,
    *,
    days: int = 7,
    since: datetime | None = None,
    gap_minutes: int = SESSION_GAP_MINUTES,
) -> dict[str, Any]:
    """Labels per active hour from the human decisions of the last ``days`` days.

    Returns ``labels``, ``active_hours``, ``labels_per_hour`` (None with no labels) and the same
    per reviewer (``by_reviewer``) and per UTC day (``by_day``: labels only).
    """
    cutoff = since
    if cutoff is None:
        cutoff = conn.execute("SELECT now() - make_interval(days => %s)", (days,)).fetchone()[0]
    rows = conn.execute(
        "SELECT reviewed_by, reviewed_at FROM item_canonical"
        " WHERE source = 'human' AND reviewed_by IS NOT NULL AND reviewed_at >= %s"
        " ORDER BY reviewed_by, reviewed_at",
        (cutoff,),
    ).fetchall()
    gap = timedelta(minutes=gap_minutes)
    times: dict[str, list[datetime]] = defaultdict(list)
    days_count: dict[str, int] = defaultdict(int)
    for who, at in rows:
        times[who].append(at)
        days_count[at.astimezone(UTC).date().isoformat()] += 1
    by_reviewer = []
    total_seconds = 0.0
    for who, ts in sorted(times.items()):
        seconds = _active_seconds(ts, gap)
        total_seconds += seconds
        hours = seconds / 3600
        by_reviewer.append({
            "reviewer": who, "labels": len(ts), "active_hours": round(hours, 3),
            "labels_per_hour": round(len(ts) / hours, 1) if hours else None,
        })  # fmt: skip
    total_hours = total_seconds / 3600
    return {
        "since": cutoff,
        "labels": len(rows),
        "active_hours": round(total_hours, 3),
        "labels_per_hour": round(len(rows) / total_hours, 1) if total_hours else None,
        "by_reviewer": by_reviewer,
        "by_day": sorted(days_count.items()),
    }


# --- the expansion backlog --------------------------------------------------------------------


def backlog_sql_path() -> Path:
    base = os.environ.get(QUERIES_DIR_ENV)
    if base:
        return Path(base) / "catalog_backlog.sql"
    # services/catalog/smartcart_catalog/active.py -> the repository root is three levels up.
    return Path(__file__).resolve().parents[3] / "supabase" / "queries" / "catalog_backlog.sql"


def catalog_backlog(
    conn: psycopg.Connection,
    *,
    days: int = 30,
    top: int = 20,
    min_similarity: float = 0.5,
    min_misses: int = 1,
    item_days: int = 60,
) -> list[dict[str, Any]]:
    """Rows of ``catalog_backlog.sql``: ``kind`` (``missed_query`` or ``unmapped_item``),
    ``position``, ``label``, ``demand``, ``secondary``, ``examples``, ``last_seen``."""
    sql = backlog_sql_path().read_text(encoding="utf-8")
    cur = conn.execute(
        sql,  # type: ignore[arg-type]
        {"days": days, "top": top, "min_similarity": min_similarity, "min_misses": min_misses,
         "item_days": item_days},
    )
    cols = [c.name for c in cur.description or []]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
