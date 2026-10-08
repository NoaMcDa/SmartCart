"""Human review of uncertain matches (issue #38, architecture section 3 step E).

Run from the repo root (needs a DATABASE_URL role that may write ``item_canonical`` and
``gold_pairs``)::

    uv run smartcart-catalog review          # or:
    uv run streamlit run services/catalog/smartcart_catalog/review_app.py

Three tabs: the review queue (``needs_review`` mappings, uncertain ones first: items a user
reported as "not a good substitute", then those closest to the accept threshold, where the
embedders disagree and by canonical rank; see ``active.select_for_review``), the best-seller
checklist (the 300 top-ranked canonicals must have every mapping human-reviewed before launch) and
feedback rates. The sidebar shows labels per hour from the reviewers' own timestamps.

All reads and writes are plain functions below, tested without Streamlit:

* ``accept``  the mapping becomes ``source='human'``, ``needs_review=false``, with
  ``reviewed_by``/``reviewed_at``; the pair is added to ``gold_pairs`` with its level.
* ``reject``  the mapping is kept as a human decision with ``human_rejected=true`` ("not this
  canonical", issue #92): the matching pipeline drops that canonical from the item's
  candidates, so the judge never proposes it again. A ``no_match`` gold pair is recorded too,
  for evaluation only. The row also gets ``needs_review=true`` and ``confidence=0``, so a reader
  that only filters on ``needs_review`` still never serves it; readers filter
  ``NOT human_rejected``.
* ``remap``   reject the old canonical and accept the new one.

The queue shows the judge's own reason, stored in ``item_canonical.reason`` when the mapping
was written; ``explain`` re-runs retrieval only to list the candidates a reviewer can re-map to.
"""

from __future__ import annotations

import os
from typing import Any

import psycopg

from smartcart_catalog.active import labels_per_hour, select_for_review
from smartcart_catalog.judge import RuleJudge
from smartcart_catalog.match import Lexicon, load_items, load_rules, match_item
from smartcart_catalog.models import FlexLevel, Judge

REJECTED_REASON = "human: not this canonical"


def review_queue(conn: psycopg.Connection, limit: int = 100) -> list[dict[str, Any]]:
    """The mappings to review, most useful label first (``active.select_for_review``): user
    reports, then closeness to the accept threshold, embedder disagreement, basket rank."""
    return select_for_review(conn, limit)


def explain(
    conn: psycopg.Connection,
    item_id: int,
    judge: Judge | None = None,
    *,
    k: int = 5,
    lexicon: Lexicon | None = None,
) -> dict[str, Any]:
    """Attributes, block and the current candidates of one item, for re-mapping.

    ``stored_reason`` is the judge's reason as stored with each of the item's mappings
    (``item_canonical.reason``); the per-candidate reasons come from re-running retrieval and
    the rule judge now. Human-rejected canonicals are not offered as candidates."""
    judge = judge or RuleJudge()
    ctx = load_items(conn, [item_id], lexicon)[item_id]
    rules = load_rules(conn)
    res = match_item(conn, ctx, judge, rules, k=k)
    stored = {cid: reason or "" for cid, reason in conn.execute(
        "SELECT canonical_id, reason FROM item_canonical WHERE item_id = %s", (item_id,)
    ).fetchall()}  # fmt: skip
    cands = []
    assess = RuleJudge().assess_all(ctx.item, ctx.attrs, res.candidates, rules)
    by_id = {a.canonical_id: a for a in assess}
    for c in res.candidates:
        a = by_id.get(c.canonical_id)
        cands.append({
            "canonical_id": c.canonical_id,
            "slug": c.canonical.slug if c.canonical else None,
            "name": c.canonical.display_name_he if c.canonical else None,
            "similarity": round(c.similarity, 4),
            "eligible": a.eligible if a else None,
            "flex_level": a.flex_level if a else None,
            "confidence": round(a.confidence, 4) if a else None,
            "reason": a.reason() if a else "",
        })  # fmt: skip
    return {
        "item_id": item_id,
        "item_name": ctx.raw_name,
        "attributes": ctx.attrs.model_dump(mode="json", exclude_defaults=True),
        "attributes_source": ctx.attrs_source,
        "block": res.block.describe(),
        "candidates": cands,
        "decision": res.decision.model_dump(mode="json"),
        "stored_reason": stored,
        "rejected": sorted(ctx.rejected),
    }


def bestseller_status(conn: psycopg.Connection, top: int = 300) -> list[dict[str, Any]]:
    """Review progress of the ``top`` best-selling canonicals (by ``rank``)."""
    rows = conn.execute(
        """
        SELECT cp.id, cp.slug, cp.display_name_he, cp.rank,
               count(ic.item_id) AS mapped,
               count(ic.item_id) FILTER (WHERE ic.source = 'human') AS human_reviewed,
               count(ic.item_id) FILTER (WHERE ic.needs_review) AS pending
        FROM (SELECT * FROM canonical_products WHERE rank IS NOT NULL
              ORDER BY rank LIMIT %s) cp
        LEFT JOIN item_canonical ic ON ic.canonical_id = cp.id AND NOT ic.human_rejected
        GROUP BY cp.id, cp.slug, cp.display_name_he, cp.rank
        ORDER BY cp.rank
        """,
        (top,),
    ).fetchall()
    return [
        {"canonical_id": cid, "slug": slug, "name": name, "rank": rank, "mapped": mapped,
         "human_reviewed": human, "pending": pending,
         "fully_reviewed": mapped > 0 and human == mapped}
        for cid, slug, name, rank, mapped, human, pending in rows
    ]  # fmt: skip


def search_canonicals(conn: psycopg.Connection, text: str, limit: int = 20) -> list[dict[str, Any]]:
    pattern = f"%{text.strip()}%"
    rows = conn.execute(
        "SELECT id, slug, display_name_he, taxonomy_id FROM canonical_products"
        " WHERE slug ILIKE %s OR display_name_he ILIKE %s ORDER BY rank NULLS LAST, slug LIMIT %s",
        (pattern, pattern, limit),
    ).fetchall()
    return [{"canonical_id": r[0], "slug": r[1], "name": r[2], "taxonomy_id": r[3]} for r in rows]


def _record_gold(
    conn: psycopg.Connection, item_id: int, canonical_id: int, label: str, note: str
) -> None:
    conn.execute(
        "INSERT INTO gold_pairs (item_id, canonical_id, label, category, note)"
        " SELECT %s, cp.id, %s, split_part(cp.taxonomy_id, '.', 1), %s"
        " FROM canonical_products cp WHERE cp.id = %s"
        " ON CONFLICT (item_id, canonical_id) DO UPDATE SET label = EXCLUDED.label,"
        " note = EXCLUDED.note",
        (item_id, label, note, canonical_id),
    )


def accept(
    conn: psycopg.Connection,
    item_id: int,
    canonical_id: int,
    reviewer: str,
    flex_level: FlexLevel | None = None,
) -> None:
    """Confirm (or create) the mapping as a human decision, optionally at another level."""
    if not reviewer.strip():
        raise ValueError("reviewer is required")
    row = conn.execute(
        "SELECT flex_level FROM item_canonical WHERE item_id = %s AND canonical_id = %s",
        (item_id, canonical_id),
    ).fetchone()
    level = flex_level or (row[0] if row else None)
    if level is None:
        raise ValueError("flex_level is required when there is no mapping to confirm")
    conn.execute(
        "INSERT INTO item_canonical AS ic (item_id, canonical_id, flex_level, confidence, source,"
        " needs_review, reviewed_by, reviewed_at, human_rejected, reason)"
        " VALUES (%(item)s, %(canon)s, %(level)s, 1, 'human', false, %(who)s, now(), false,"
        "  %(reason)s)"
        " ON CONFLICT (item_id, canonical_id) DO UPDATE SET flex_level = EXCLUDED.flex_level,"
        " confidence = 1, source = 'human', needs_review = false, human_rejected = false,"
        " reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at,"
        " reason = CASE WHEN ic.source = 'human' THEN EXCLUDED.reason"
        "   ELSE EXCLUDED.reason || coalesce(' | judge: ' || nullif(ic.reason, ''), '') END",
        {"item": item_id, "canon": canonical_id, "level": level, "who": reviewer,
         "reason": f"human: accepted by {reviewer}"},
    )  # fmt: skip
    # The human decision replaces any other machine mapping of this item.
    conn.execute(
        "DELETE FROM item_canonical WHERE item_id = %s AND canonical_id <> %s"
        " AND source <> 'human'",
        (item_id, canonical_id),
    )
    _record_gold(conn, item_id, canonical_id, level, f"review: accepted by {reviewer}")


def reject(conn: psycopg.Connection, item_id: int, canonical_id: int, reviewer: str) -> None:
    """The item is not this canonical: keep the pair as a human rejection (``human_rejected``)
    so the judge never proposes it again, and record a ``no_match`` gold pair (evaluation)."""
    if not reviewer.strip():
        raise ValueError("reviewer is required")
    conn.execute(
        "INSERT INTO item_canonical AS ic (item_id, canonical_id, flex_level, confidence, source,"
        " needs_review, reviewed_by, reviewed_at, human_rejected, reason)"
        " VALUES (%(item)s, %(canon)s, 'close', 0, 'human', true, %(who)s, now(), true,"
        "  %(reason)s)"
        " ON CONFLICT (item_id, canonical_id) DO UPDATE SET confidence = 0, source = 'human',"
        " needs_review = true, human_rejected = true, reviewed_by = EXCLUDED.reviewed_by,"
        " reviewed_at = EXCLUDED.reviewed_at,"
        " reason = CASE WHEN ic.source = 'human' THEN EXCLUDED.reason"
        "   ELSE EXCLUDED.reason || coalesce(' | judge: ' || nullif(ic.reason, ''), '') END",
        {"item": item_id, "canon": canonical_id, "who": reviewer,
         "reason": f"{REJECTED_REASON} ({reviewer})"},
    )  # fmt: skip
    _record_gold(conn, item_id, canonical_id, "no_match", f"review: rejected by {reviewer}")


def remap(
    conn: psycopg.Connection,
    item_id: int,
    old_canonical_id: int,
    new_canonical_id: int,
    flex_level: FlexLevel,
    reviewer: str,
) -> None:
    if old_canonical_id == new_canonical_id:
        accept(conn, item_id, new_canonical_id, reviewer, flex_level)
        return
    reject(conn, item_id, old_canonical_id, reviewer)
    accept(conn, item_id, new_canonical_id, reviewer, flex_level)


# --- Streamlit UI -------------------------------------------------------------------------------


def main() -> None:  # pragma: no cover - UI glue, the functions above are tested
    import streamlit as st

    from smartcart_catalog.feedback import rejection_rates

    st.set_page_config(page_title="SmartCart match review", layout="wide")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        st.error("DATABASE_URL is not set")
        return
    reviewer = st.sidebar.text_input("Reviewer (name or email)", key="reviewer")
    limit = st.sidebar.number_input("Queue size", 10, 500, 50, step=10)
    tab_queue, tab_best, tab_feedback = st.tabs(
        ["Review queue", "Best sellers (top 300)", "Feedback"]
    )
    with psycopg.connect(dsn) as conn:
        speed = labels_per_hour(conn, days=7)
        st.sidebar.metric(
            "Labels per hour (7 days)",
            "-" if speed["labels_per_hour"] is None else speed["labels_per_hour"],
            help=f"{speed['labels']} labels in {speed['active_hours']} active hours, "
                 "from the reviewers' own decision timestamps",
        )  # fmt: skip
        with tab_queue:
            queue = review_queue(conn, int(limit))
            st.caption(
                f"{len(queue)} mappings need review, most uncertain first: user reports, then "
                f"closeness to the accept threshold, embedder disagreement and basket rank."
            )
            for row in queue:
                marker = f" · REPORTED BY USERS ({row['reports']})" if row["feedback_marker"] else ""
                title = (f"{row['item_name']} → {row['canonical_name']} "
                         f"({row['flex_level']}, {row['confidence']:.2f}){marker}")  # fmt: skip
                with st.expander(title):
                    info = explain(conn, row["item_id"])
                    st.write(f"chain {row['chain_id']}, barcode {row['barcode'] or '-'}, "
                             f"block {info['block']}, attributes from {info['attributes_source']}")  # fmt: skip
                    st.json(info["attributes"])
                    st.write("Judge:", row["reason"] or "(no reason stored)")
                    st.dataframe(info["candidates"], use_container_width=True)
                    key = f"{row['item_id']}-{row['canonical_id']}"
                    levels = ["exact", "any_brand", "close"]
                    level = st.selectbox("Level", levels, levels.index(row["flex_level"]),
                                         key=f"lvl-{key}")  # fmt: skip
                    c1, c2, c3 = st.columns(3)
                    if c1.button("Accept", key=f"acc-{key}", disabled=not reviewer):
                        accept(conn, row["item_id"], row["canonical_id"], reviewer, level)
                        conn.commit()
                        st.rerun()
                    if c2.button("Reject", key=f"rej-{key}", disabled=not reviewer):
                        reject(conn, row["item_id"], row["canonical_id"], reviewer)
                        conn.commit()
                        st.rerun()
                    options = {f"{c['slug']} ({c['name']})": c["canonical_id"]
                               for c in info["candidates"] if c["eligible"]}  # fmt: skip
                    target = c3.selectbox("Re-map to", ["", *options], key=f"tgt-{key}")
                    if target and c3.button("Re-map", key=f"map-{key}", disabled=not reviewer):
                        remap(conn, row["item_id"], row["canonical_id"], options[target], level,
                              reviewer)  # fmt: skip
                        conn.commit()
                        st.rerun()
        with tab_best:
            status = bestseller_status(conn)
            done = sum(1 for s in status if s["fully_reviewed"])
            st.metric("Best sellers fully human-reviewed", f"{done} / {len(status)}")
            st.dataframe(status, use_container_width=True)
        with tab_feedback:
            st.dataframe(rejection_rates(conn), use_container_width=True)
        conn.rollback()


if __name__ == "__main__":
    main()
