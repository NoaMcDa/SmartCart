"""The demo's stand-in for the human review step (architecture step E).

With the hash embedder (no BGE-M3 here) the rule judge is cautious by design: a mapping whose
name similarity is low goes to the review queue with ``needs_review`` and is left out of the
effective-price precompute until a person accepts it in the review UI
(``smartcart-catalog review``). On the synthetic fixtures that is five of the eight products.

This script plays the reviewer for the demo, with a written answer key instead of a person. It
goes through the real review queue (``review_app.review_queue``) and calls the same function the
review UI calls (``review_app.accept``) for every queued pair that is in the key, at the key's
level. A queued pair that is not in the key is left in the queue, and nothing outside the queue is
touched, so the key cannot accept something the judge did not propose. The reviewer name is
``demo-answer-key`` so these rows are recognisable as scripted.

Never run this against a real database: it is a demo of the flow, not a review.

    DATABASE_URL=... uv run python scripts/demo/review.py
"""

from __future__ import annotations

import json
import os
import sys

import psycopg

from smartcart_catalog import review_app

REVIEWER = "demo-answer-key"

# (item raw name, canonical slug) -> flexibility level. The synthetic fixtures' items, each
# checked by hand against data/canonicals.yaml: same product type, same critical attributes,
# canonical pack size.
ANSWER_KEY: dict[tuple[str, str], str] = {
    ("חלב תנובה 3% בקרטון 1 ליטר", "milk-fresh-3"): "any_brand",
    ("קוטג' 5% תנובה 250 גרם", "cottage-5"): "any_brand",
    ("לחם אחיד פרוס אנג'ל 750 גרם", "bread-standard"): "any_brand",
    ("במבה אסם 80 גרם", "bamba"): "any_brand",
    ("בננה במשקל", "banana"): "any_brand",
    ("עגבניות שרי במשקל", "cherry-tomato"): "any_brand",
    ("שמן קנולה מזולה 1 ליטר", "canola-oil"): "any_brand",
    ("שוקולד פרה מריר 100 גרם", "chocolate-dark-bar"): "any_brand",
    ("חלב טרי 3% שדות בקרטון 1 ליטר", "milk-fresh-3"): "any_brand",
    ('לחם אחיד פרוס שדות 1 ק"ג', "bread-standard"): "close",
}


def review(conn: psycopg.Connection) -> dict[str, int]:
    accepted = left = 0
    queue = review_app.review_queue(conn, limit=10_000)
    for row in queue:
        level = ANSWER_KEY.get((row["item_name"], row["canonical_slug"]))
        if level is None:
            left += 1
            continue
        review_app.accept(conn, row["item_id"], row["canonical_id"], REVIEWER, level)
        accepted += 1
    remaining = conn.execute(
        "SELECT count(*) FROM item_canonical WHERE needs_review AND NOT human_rejected"
    ).fetchone()[0]
    return {"queued": len(queue), "accepted": accepted, "left_in_queue": remaining}


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    with psycopg.connect(dsn) as conn:
        result = review(conn)
        conn.commit()
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
