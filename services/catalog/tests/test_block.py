from __future__ import annotations

import pytest
from test_match_seed import add_item, embed_all, seed_catalog

from smartcart_catalog.block import (
    TOP_K_SQL,
    base_unit_for,
    block_prefix,
    configure_session,
    prefix_like,
    top_k,
)


def test_block_prefix_depth() -> None:
    assert block_prefix("dairy.milk.fresh") == "dairy"
    assert block_prefix("dairy.milk.fresh", 2) == "dairy.milk"
    assert block_prefix("dairy", 3) == "dairy"
    assert block_prefix(None) is None and block_prefix("") is None


@pytest.mark.parametrize(
    ("unit", "weighed", "expected"),
    [
        ("גרם", False, "100g"),
        ('ק"ג', False, "100g"),
        ("kg", True, "kg"),
        ("ליטר", False, "100ml"),
        ('מ"ל', False, "100ml"),
        ("l", False, "100ml"),
        ("יחידה", False, "unit"),
        ("unit", False, "unit"),
        ("פחית", False, None),
        (None, False, None),
    ],
)
def test_base_unit_for(unit, weighed, expected) -> None:
    assert base_unit_for(unit, is_weighed=weighed) == expected


def test_prefix_like_escapes_wildcards() -> None:
    assert prefix_like("dairy") == "dairy.%"
    assert prefix_like("a_b%") == "a\\_b\\%.%"


@pytest.mark.db
@pytest.mark.pgvector
def test_top_k_never_leaves_the_block(db) -> None:
    ids = seed_catalog(db)
    # 'dairymilk' shares the characters of the prefix but is not under 'dairy.'.
    db.execute("INSERT INTO taxonomy (id, level, name_he) VALUES ('dairymilk', 1, 'decoy')")
    # Decoys with exactly the item's name: the most similar rows possible, but outside the block.
    name = "חלב טרי 3% תנובה 1 ליטר"
    db.execute(
        "INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type,"
        " base_unit) VALUES ('pantry.oil', 'decoy-dept', %(n)s, 'olive_oil', '100ml'),"
        " ('dairy.milk', 'decoy-unit', %(n)s, 'milk', '100g'),"
        " ('dairymilk', 'decoy-prefix', %(n)s, 'milk', '100ml')",
        {"n": name},
    )
    item = add_item(db, "חלב טרי 3% תנובה 1 ליטר")
    embed_all(db)

    inside = top_k(db, item, 10, "dairy", "100ml")
    slugs = [c.canonical.slug for c in inside]
    assert slugs and not any(s.startswith("decoy") for s in slugs)
    assert all(c.canonical.taxonomy_id.startswith("dairy.") for c in inside)
    assert all(c.canonical.base_unit == "100ml" for c in inside)
    assert slugs[0] == "t-milk-3"
    sims = [c.similarity for c in inside]
    assert sims == sorted(sims, reverse=True) and all(-1 <= s <= 1.0001 for s in sims)
    assert {c.canonical_id for c in inside} <= set(ids.values())

    # Without the block the decoys win, which is exactly why blocking runs first.
    unblocked = top_k(db, item, 3)
    assert unblocked[0].canonical.slug.startswith("decoy")
    assert top_k(db, item, 2, "dairy", "100ml")[0].similarity == inside[0].similarity
    assert len(top_k(db, item, 2, "dairy", "100ml")) == 2
    # No embedding, no candidates.
    assert top_k(db, add_item(db, "לא מוטמע"), 5) == []


@pytest.mark.db
@pytest.mark.pgvector
def test_top_k_query_is_served_by_the_hnsw_index(db) -> None:
    """The top-k statement has a shape the HNSW index can serve (ORDER BY the raw ``<=>``
    distance with a LIMIT, the block as a filter).

    Whether the planner picks the index is a cost decision. pgvector's cost model makes a seq
    scan plus top-N sort look cheaper on small tables, because the distance computation on
    TOASTed vectors is barely costed: measured on this schema (pgvector 0.6), the HNSW path
    costs about 200-260 at 300-1,000 rows against 11-36 for the seq scan; the crossover,
    extrapolated, is in the tens of thousands of rows, too many to insert in a unit test. At MVP size (150-300 canonicals) a seq scan with exact distances is what runs, and it
    is exact. So this test checks the natural plan is one of the two, and that with seq scans
    and sorts disabled the planner serves the same statement from the HNSW index, which fails
    if a change to the SQL makes the index unusable (e.g. ordering by ``1 - distance``).
    """
    seed_catalog(db)
    db.execute(
        """
        INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type,
                                        base_unit, embedding)
        SELECT 'dairy.milk', 'bulk-' || g, 'bulk ' || g, 'milk', '100ml',
               array(SELECT random() - 0.5 + g * 0 FROM generate_series(1, 1024))::vector
        FROM generate_series(1, 300) g
        """
    )
    item = add_item(db, "חלב טרי 3% 1 ליטר")
    embed_all(db)
    db.execute("ANALYZE canonical_products")
    configure_session(db)
    params = {"item_id": item, "k": 10, "prefix": "dairy", "like": "dairy.%",
              "base_unit": "100ml"}  # fmt: skip

    def plan() -> str:
        return "\n".join(r[0] for r in db.execute("EXPLAIN " + TOP_K_SQL, params).fetchall())

    natural = plan()
    assert "canonical_products_embedding_hnsw" in natural or "Seq Scan" in natural, natural
    db.execute("SET LOCAL enable_seqscan = off")
    db.execute("SET LOCAL enable_sort = off")
    forced = plan()
    assert "Index Scan using canonical_products_embedding_hnsw" in forced, forced
    results = top_k(db, item, 10, "dairy", "100ml")
    assert len(results) == 10
    assert [r.similarity for r in results] == sorted((r.similarity for r in results), reverse=True)
