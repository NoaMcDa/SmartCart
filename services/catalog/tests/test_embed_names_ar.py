"""Arabic name vectors (issue #73): ``embed_canonicals`` also fills ``canonical_name_embeddings``."""

from __future__ import annotations

import pytest
from test_match_seed import seed_catalog

from smartcart_catalog.embed import HashEmbedder, embed_canonicals

pytestmark = [pytest.mark.db, pytest.mark.pgvector]


def _rows(db, ids: list[int]) -> list[tuple]:
    return db.execute(
        "SELECT canonical_id, lang, name, embedding_model FROM canonical_name_embeddings"
        " WHERE canonical_id = ANY(%s) ORDER BY canonical_id, name",
        (ids,),
    ).fetchall()


def test_every_arabic_name_gets_a_vector_and_reruns_skip_them(db) -> None:
    ids = seed_catalog(db)
    milk, soy = ids["t-milk-3"], ids["t-soy"]
    db.execute(
        "UPDATE canonical_products SET names_ar = %s WHERE id = %s",
        (["حليب 3%", "حليب طازج 3%"], milk),
    )
    db.execute("UPDATE canonical_products SET names_ar = %s WHERE id = %s", (["حليب صويا"], soy))
    emb = HashEmbedder()

    first = embed_canonicals(db, emb)
    assert first["ar_embedded"] == 3 and first["ar_skipped"] == 0 and first["ar_removed"] == 0
    assert _rows(db, [milk, soy]) == sorted(
        [
            (milk, "ar", "حليب 3%", emb.model_name),
            (milk, "ar", "حليب طازج 3%", emb.model_name),
            (soy, "ar", "حليب صويا", emb.model_name),
        ],
        key=lambda r: (r[0], r[2]),
    )
    # a canonical without Arabic names has no row, and the Hebrew vectors are as before
    assert db.execute(
        "SELECT count(*) FROM canonical_name_embeddings WHERE canonical_id NOT IN (%s, %s)",
        (milk, soy),
    ).fetchone() == (0,)
    assert (
        db.execute(
            "SELECT count(*) FROM canonical_products WHERE embedding IS NOT NULL AND embedding_model = %s",
            (emb.model_name,),
        ).fetchone()[0]
        == first["embedded"] + first["skipped"]
    )

    again = embed_canonicals(db, emb)
    assert again["embedded"] == 0
    assert again["ar_embedded"] == 0 and again["ar_skipped"] == 3


def test_a_changed_name_is_redone_and_a_dropped_name_is_removed(db) -> None:
    ids = seed_catalog(db)
    milk = ids["t-milk-3"]
    db.execute(
        "UPDATE canonical_products SET names_ar = %s WHERE id = %s",
        (["حليب 3%", "حليب طازج 3%"], milk),
    )
    emb = HashEmbedder()
    embed_canonicals(db, emb)

    db.execute(
        "UPDATE canonical_products SET names_ar = %s WHERE id = %s", (["حليب 3%", "لبن 3%"], milk)
    )
    second = embed_canonicals(db, emb)
    assert (second["ar_embedded"], second["ar_skipped"], second["ar_removed"]) == (1, 1, 1)
    assert [r[2] for r in _rows(db, [milk])] == sorted(["حليب 3%", "لبن 3%"])

    db.execute("UPDATE canonical_products SET names_ar = '{}' WHERE id = %s", (milk,))
    third = embed_canonicals(db, emb)
    assert third["ar_removed"] == 2 and _rows(db, [milk]) == []


def test_another_model_or_force_re_embeds_the_arabic_names(db) -> None:
    ids = seed_catalog(db)
    milk = ids["t-milk-3"]
    db.execute("UPDATE canonical_products SET names_ar = %s WHERE id = %s", (["حليب 3%"], milk))
    emb = HashEmbedder()
    embed_canonicals(db, emb)

    other = HashEmbedder(ngram_sizes=(3,))
    assert embed_canonicals(db, other)["ar_embedded"] == 1
    assert _rows(db, [milk]) == [(milk, "ar", "حليب 3%", other.model_name)]  # replaced, not added
    assert embed_canonicals(db, other)["ar_embedded"] == 0
    assert embed_canonicals(db, other, force=True)["ar_embedded"] == 1


def test_a_deleted_canonical_takes_its_name_vectors_along(db) -> None:
    ids = seed_catalog(db)
    soy = ids["t-soy"]
    db.execute("UPDATE canonical_products SET names_ar = %s WHERE id = %s", (["حليب صويا"], soy))
    embed_canonicals(db, HashEmbedder())
    assert _rows(db, [soy])
    db.execute("DELETE FROM canonical_products WHERE id = %s", (soy,))
    assert _rows(db, [soy]) == []
