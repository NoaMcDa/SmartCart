from __future__ import annotations

import math
import sys

import pytest
from test_match_seed import add_item, seed_catalog

from smartcart_catalog.block import top_k
from smartcart_catalog.embed import (
    BGE_M3_MODEL_NAME,
    DIM,
    HASH_MODEL_NAME,
    BgeM3Embedder,
    HashEmbedder,
    embed_canonicals,
    embed_items,
    get_embedder,
    to_pgvector,
)
from smartcart_catalog.models import Embedder


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_hash_embedder_shape_norm_and_determinism() -> None:
    emb = HashEmbedder()
    assert isinstance(emb, Embedder)
    a, b, empty = emb.embed(["חלב טרי 3% 1 ליטר", "חלב טרי 3% 1 ליטר", ""])
    assert len(a) == DIM == emb.dim
    assert math.isclose(math.sqrt(sum(x * x for x in a)), 1.0, rel_tol=1e-9)
    assert a == b
    assert math.isclose(math.sqrt(sum(x * x for x in empty)), 1.0)
    assert HashEmbedder().embed(["סלמון"]) == emb.embed(["סלמון"])  # stable across instances


def test_hash_embedder_similar_strings_are_closer() -> None:
    emb = HashEmbedder()
    milk, milk_reordered, milk_abbrev, salmon = emb.embed(
        ["חלב טרי 3% תנובה 1 ליטר", "תנובה חלב 3% טרי 1 ליטר", "ח. טרי 3% 1 ל'", "פילה סלמון קפוא"]
    )
    assert _cos(milk, milk_reordered) > 0.9
    assert _cos(milk, milk_abbrev) > _cos(milk, salmon)
    assert _cos(milk, salmon) < 0.3


def test_hash_embedder_folds_final_letters_and_nikud() -> None:
    emb = HashEmbedder()
    a, b = emb.embed(["שמן זית", "שמנ זית"])
    assert _cos(a, b) > 0.999


def test_get_embedder_and_lazy_bge() -> None:
    assert isinstance(get_embedder("hash"), HashEmbedder)
    bge = get_embedder("bge-m3", "BAAI/bge-m3")
    assert isinstance(bge, BgeM3Embedder) and bge.dim == 1024
    assert bge.model_name == "BAAI/bge-m3"
    assert "sentence_transformers" not in sys.modules or bge._model is None
    assert bge.embed([]) == []  # no model load for an empty batch
    with pytest.raises(ValueError):
        get_embedder("word2vec")


def test_embedder_model_names_are_stable() -> None:
    """The API filters stored vectors by these names (issue #102); changing one needs a
    re-embed of every row, so it is pinned here."""
    assert HashEmbedder().model_name == HASH_MODEL_NAME == "hash-ngram-2-3-4-v1"
    assert get_embedder("hash").model_name == HASH_MODEL_NAME
    assert get_embedder("bge-m3").model_name == BGE_M3_MODEL_NAME == "BAAI/bge-m3"
    assert HashEmbedder(ngram_sizes=(3,)).model_name != HASH_MODEL_NAME  # another space

    class Nameless:
        dim = DIM

        def embed(self, texts: list[str]) -> list[list[float]]:
            return []

    assert not isinstance(Nameless(), Embedder)  # model_name is part of the protocol


def test_to_pgvector_format() -> None:
    assert to_pgvector([0.5, -0.25, 1e-9]) == "[0.5,-0.25,1e-09]"


@pytest.mark.db
@pytest.mark.pgvector
def test_embed_jobs_are_idempotent_and_record_runs(db) -> None:
    ids = seed_catalog(db)
    item = add_item(db, "חלב טרי 3% תנובה 1 ליטר")
    emb = HashEmbedder()
    before = db.execute("SELECT count(*) FROM match_runs WHERE kind = 'embed'").fetchone()[0]

    first = embed_canonicals(db, emb)
    assert first["embedded"] >= len(ids) and first["model"] == emb.model_name
    again = embed_canonicals(db, emb)
    assert again["embedded"] == 0 and again["skipped"] == first["embedded"]

    items_first = embed_items(db, emb, [item])
    assert items_first["embedded"] == 1
    assert embed_items(db, emb, [item])["embedded"] == 0
    row = db.execute("SELECT model FROM item_embeddings WHERE item_id = %s", (item,)).fetchone()
    assert row == (emb.model_name,)

    # A renamed canonical is re-embedded; nothing else is.
    db.execute(
        "UPDATE canonical_products SET display_name_he = %s WHERE id = %s",
        ("חלב טרי 3% בקרטון 1 ליטר", ids["t-milk-3"]),
    )
    assert embed_canonicals(db, emb)["embedded"] == 1

    # A different model re-embeds everything.
    other = HashEmbedder(ngram_sizes=(3,))
    assert embed_canonicals(db, other)["embedded"] == first["embedded"]
    assert embed_items(db, other, [item])["embedded"] == 1

    after = db.execute("SELECT count(*) FROM match_runs WHERE kind = 'embed'").fetchone()[0]
    assert after - before == 7
    unfinished = db.execute(
        "SELECT count(*) FROM match_runs WHERE kind = 'embed' AND finished_at IS NULL"
    ).fetchone()[0]
    assert unfinished == 0


@pytest.mark.db
@pytest.mark.pgvector
def test_canonical_rows_record_their_embedding_model(db) -> None:
    """canonical_products.embedding_model makes a model change visible on the row (#92)."""
    ids = seed_catalog(db)
    emb = HashEmbedder()
    embed_canonicals(db, emb)
    models = {r[0] for r in db.execute(
        "SELECT embedding_model FROM canonical_products WHERE id = ANY(%s)", (list(ids.values()),)
    ).fetchall()}  # fmt: skip
    assert models == {emb.model_name}
    # One row embedded by another model (or before the column existed) is redone, alone.
    db.execute("UPDATE canonical_products SET embedding_model = NULL WHERE id = %s",
               (ids["t-soy"],))  # fmt: skip
    assert embed_canonicals(db, emb)["embedded"] == 1
    db.execute("UPDATE canonical_products SET embedding_model = 'old-model' WHERE id = %s",
               (ids["t-almond"],))  # fmt: skip
    res = embed_canonicals(db, emb)
    assert res["embedded"] == 1 and res["full"] is False


@pytest.mark.db
@pytest.mark.pgvector
def test_items_and_canonicals_carry_the_same_model_and_retrieval_never_mixes_models(db) -> None:
    """Issue #102: both tables record ``Embedder.model_name``; top-k compares an item only with
    canonicals embedded by the item's model."""
    ids = seed_catalog(db)
    item = add_item(db, "חלב טרי 3% תנובה 1 ליטר")
    emb = HashEmbedder()
    embed_canonicals(db, emb)
    embed_items(db, emb, [item])
    canon_models = {r[0] for r in db.execute(
        "SELECT embedding_model FROM canonical_products WHERE id = ANY(%s)", (list(ids.values()),)
    ).fetchall()}  # fmt: skip
    item_model = db.execute("SELECT model FROM item_embeddings WHERE item_id = %s",
                            (item,)).fetchone()[0]  # fmt: skip
    assert canon_models == {item_model} == {HASH_MODEL_NAME}
    assert top_k(db, item, 5, "dairy", "100ml")

    # The item moves to another model while the canonicals still hold the old one: no
    # candidates rather than distances between two vector spaces.
    other = HashEmbedder(ngram_sizes=(3,))
    embed_items(db, other, [item])
    assert top_k(db, item, 5, "dairy", "100ml") == []
    embed_canonicals(db, other)
    assert top_k(db, item, 5, "dairy", "100ml")
