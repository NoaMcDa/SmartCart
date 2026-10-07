"""User feedback on substitutes as a labeling signal (issue #43, decision D5).

``record_feedback`` is the write path the API calls when a user presses "not a good
substitute" (or keeps the original, or accepts the substitute). A ``not_good`` verdict flags
the mapping (substitute item -> canonical) ``needs_review`` so it enters the review queue with a
feedback marker. It never changes the mapping itself: only a human decision in the review UI
does (``review_app``), and ``match.apply_decisions`` keeps the flag set on re-runs while the
report is unresolved.

A user report alone is not ground truth: ``feedback_gold_candidates`` exports reported pairs as
candidate gold pairs for a human to confirm.

Context columns (issue #92): ``list_item_id`` (the list line the substitute was shown for),
``flex_level`` (the level the user's list asked for) and ``match_confidence`` (the confidence
shown with the substitute) are written when the caller gives them.

Privacy: ``user_id`` is optional and nothing about location is stored here. The table has row
level security (migration 20261008100000): a signed-in user reads and inserts only their own
rows; the catalog jobs and the review UI run as a role that bypasses it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, get_args
from uuid import UUID

import psycopg

from smartcart_catalog.models import FlexLevel

Verdict = Literal["not_good", "kept_original", "accepted"]
VERDICTS: frozenset[str] = frozenset({"not_good", "kept_original", "accepted"})
LEVELS: frozenset[str] = frozenset(get_args(FlexLevel))


@dataclass(frozen=True)
class FeedbackResult:
    feedback_id: int
    flagged: bool
    """True when a ``not_good`` verdict flagged an existing mapping for review."""
    flex_level: str | None
    """The mapping's level when the feedback was recorded (context for the reviewer)."""
    confidence: float | None


def record_feedback(
    conn: psycopg.Connection,
    user_id: UUID | str | None,
    canonical_id: int,
    original_item_id: int | None,
    substitute_item_id: int,
    verdict: Verdict,
    *,
    list_item_id: int | None = None,
    flex_level: FlexLevel | None = None,
    match_confidence: float | Decimal | None = None,
) -> FeedbackResult:
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(VERDICTS)}, got {verdict!r}")
    if flex_level is not None and flex_level not in LEVELS:
        raise ValueError(f"flex_level must be one of {sorted(LEVELS)}, got {flex_level!r}")
    if match_confidence is not None and not 0 <= float(match_confidence) <= 1:
        raise ValueError(f"match_confidence must be within 0..1, got {match_confidence!r}")
    mapping = conn.execute(
        "SELECT flex_level, confidence FROM item_canonical"
        " WHERE item_id = %s AND canonical_id = %s AND NOT human_rejected",
        (substitute_item_id, canonical_id),
    ).fetchone()
    fid = conn.execute(
        "INSERT INTO substitution_feedback"
        " (user_id, canonical_id, original_item_id, substitute_item_id, verdict, list_item_id,"
        "  flex_level, match_confidence)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (str(user_id) if user_id else None, canonical_id, original_item_id, substitute_item_id,
         verdict, list_item_id, flex_level,
         None if match_confidence is None else Decimal(str(match_confidence))),
    ).fetchone()[0]  # fmt: skip
    flagged = False
    if verdict == "not_good" and mapping is not None:
        cur = conn.execute(
            "UPDATE item_canonical SET needs_review = true"
            " WHERE item_id = %s AND canonical_id = %s AND NOT human_rejected",
            (substitute_item_id, canonical_id),
        )
        flagged = cur.rowcount > 0
    return FeedbackResult(
        feedback_id=fid,
        flagged=flagged,
        flex_level=mapping[0] if mapping else None,
        confidence=float(mapping[1]) if mapping else None,
    )


def rejection_rates(conn: psycopg.Connection) -> list[dict[str, Any]]:
    """Substitution rejection rate per category (taxonomy level 2) and current flex level."""
    rows = conn.execute(
        """
        SELECT split_part(cp.taxonomy_id, '.', 1) || coalesce('.' || nullif(
                 split_part(cp.taxonomy_id, '.', 2), ''), '') AS category,
               CASE WHEN ic.human_rejected THEN 'rejected'
                    ELSE coalesce(ic.flex_level, 'unmapped') END AS flex_level,
               count(*) AS reports,
               count(*) FILTER (WHERE f.verdict = 'not_good') AS not_good
        FROM substitution_feedback f
        JOIN canonical_products cp ON cp.id = f.canonical_id
        LEFT JOIN item_canonical ic
               ON ic.item_id = f.substitute_item_id AND ic.canonical_id = f.canonical_id
        GROUP BY 1, 2
        ORDER BY 1, 2
        """
    ).fetchall()
    return [
        {"category": c, "flex_level": lvl, "reports": n, "not_good": bad,
         "rejection_rate": bad / n if n else 0.0}
        for c, lvl, n, bad in rows
    ]  # fmt: skip


def feedback_gold_candidates(conn: psycopg.Connection) -> list[dict[str, Any]]:
    """Reported (substitute item, canonical) pairs not yet in ``gold_pairs``, most reported
    first, as candidate ``no_match`` pairs for a human to confirm or overturn."""
    rows = conn.execute(
        """
        SELECT f.substitute_item_id, f.canonical_id, i.raw_name, cp.slug,
               count(*) AS reports, max(f.created_at) AS last_report
        FROM substitution_feedback f
        JOIN items i ON i.id = f.substitute_item_id
        JOIN canonical_products cp ON cp.id = f.canonical_id
        LEFT JOIN gold_pairs g
               ON g.item_id = f.substitute_item_id AND g.canonical_id = f.canonical_id
        WHERE f.verdict = 'not_good' AND g.id IS NULL
        GROUP BY 1, 2, 3, 4
        ORDER BY reports DESC, last_report DESC
        """
    ).fetchall()
    return [
        {"item_id": i, "canonical_id": c, "item_name": name, "canonical_slug": slug,
         "reports": n, "last_report": last, "suggested_label": "no_match"}
        for i, c, name, slug, n, last in rows
    ]  # fmt: skip
