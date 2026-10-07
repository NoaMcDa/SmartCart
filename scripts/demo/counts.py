"""Row counts after each step of the demo pipeline, as one JSON object.

``up.sh`` prints it at the end; ``docs/fullstack.md`` lists the expected values, and
``--expect FILE`` (a JSON object of the same keys) exits 1 when a count differs, which is how CI
notices that a pipeline step changed what it produces. ``effective_prices_with_promo`` is printed
but kept out of the expected file: the fixture chains' promotions end on 2026-10-14, so it depends
on the day the demo runs.

    DATABASE_URL=... uv run python scripts/demo/counts.py [--expect scripts/demo/expected_counts.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg

QUERIES: dict[str, str] = {
    # ingestion
    "files_loaded": "SELECT count(*) FROM file_tracking WHERE status = 'loaded'",
    "files_quarantined": "SELECT count(*) FROM file_tracking WHERE status = 'quarantined'",
    "files_failed": "SELECT count(*) FROM file_tracking WHERE status = 'failed'",
    "files_held": "SELECT count(*) FROM file_tracking WHERE status = 'held'",
    "chains": "SELECT count(*) FROM chains",
    "stores": "SELECT count(*) FROM stores",
    "stores_physical_located": (
        "SELECT count(*) FROM stores WHERE channel = 'physical' AND geog IS NOT NULL"
    ),
    "items": "SELECT count(*) FROM items",
    "price_events": "SELECT count(*) FROM prices",
    "promos": "SELECT count(*) FROM promos",
    # catalog
    "canonicals": "SELECT count(*) FROM canonical_products",
    "taxonomy_nodes": "SELECT count(*) FROM taxonomy",
    "items_attributes_ok": "SELECT count(*) FROM item_attributes WHERE status = 'ok'",
    "item_embeddings": "SELECT count(*) FROM item_embeddings",
    "canonical_embeddings": "SELECT count(*) FROM canonical_products WHERE embedding IS NOT NULL",
    "matches": "SELECT count(*) FROM item_canonical WHERE NOT human_rejected",
    "matches_any_brand": (
        "SELECT count(*) FROM item_canonical WHERE flex_level = 'any_brand' AND NOT human_rejected"
    ),
    "matches_close": (
        "SELECT count(*) FROM item_canonical WHERE flex_level = 'close' AND NOT human_rejected"
    ),
    "matches_judge_accepted": (
        "SELECT count(*) FROM item_canonical WHERE source <> 'human' AND NOT needs_review"
    ),
    "matches_review_accepted": "SELECT count(*) FROM item_canonical WHERE source = 'human'",
    "matches_needs_review": (
        "SELECT count(*) FROM item_canonical WHERE needs_review AND NOT human_rejected"
    ),
    "canonicals_matched": "SELECT count(DISTINCT canonical_id) FROM item_canonical",
    # API precompute
    "effective_prices": "SELECT count(*) FROM effective_prices",
    "effective_prices_any_brand": (
        "SELECT count(*) FROM effective_prices WHERE flex_level = 'any_brand'"
    ),
    "effective_prices_close": "SELECT count(*) FROM effective_prices WHERE flex_level = 'close'",
    "effective_prices_with_promo": (
        "SELECT count(*) FROM effective_prices WHERE promo_id IS NOT NULL"
    ),
    "stores_priced": "SELECT count(DISTINCT store_id) FROM effective_prices",
}


def counts(conn: psycopg.Connection) -> dict[str, int]:
    return {name: conn.execute(sql).fetchone()[0] for name, sql in QUERIES.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Row counts of the demo pipeline.")
    parser.add_argument("--expect", help="JSON file of expected counts; exit 1 on a difference")
    args = parser.parse_args(argv)
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    with psycopg.connect(dsn) as conn:
        got = counts(conn)
    print(json.dumps(got, indent=2))
    if args.expect:
        with open(args.expect, encoding="utf-8") as fh:
            expected = json.load(fh)
        diff = {k: (v, got.get(k)) for k, v in expected.items() if got.get(k) != v}
        if diff:
            for key, (want, have) in diff.items():
                print(f"count {key}: expected {want}, got {have}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
