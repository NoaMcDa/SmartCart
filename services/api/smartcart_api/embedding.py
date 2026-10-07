"""The query embedder for search, and the text normalization the search retrievers share.

Query vectors must come from the same model as the stored vectors, or the cosine similarity is
noise. The stored vectors are written by the catalog workstream (``smartcart_catalog.embed``:
``embed_canonicals`` fills ``canonical_products.embedding`` and ``embedding_model``,
``embed_items`` fills ``item_embeddings`` and its ``model``), so the API embeds queries with the
catalog's embedder too, chosen by ``API_QUERY_EMBEDDER``:

* ``hash`` (default): the catalog's deterministic character n-gram ``HashEmbedder``
  (``hash-ngram-2-3-4-v1``). It captures spelling, not meaning; for tests, CI and local runs.
* ``bge-m3``: BGE-M3 through sentence-transformers (the catalog's optional ``embed`` extra must be
  installed in the API's environment, and the model is loaded on the first query).

``smartcart_api.search`` compares a query only with vectors whose recorded model is this
embedder's ``model_name``.
"""

from __future__ import annotations

import os
import re
import unicodedata
from functools import lru_cache

from smartcart_catalog.embed import get_embedder, to_pgvector
from smartcart_catalog.models import Embedder

__all__ = ["QueryEmbedder", "normalize_text", "query_embedder", "to_pgvector"]

QUERY_EMBEDDER_ENV = "API_QUERY_EMBEDDER"

_NIQQUD = re.compile(r"[֑-ׇ]")
_QUOTES = re.compile(r"[\"'`׳״“”’]")
_NON_WORD = re.compile(r"[\s,;:!?()\[\]{}/\\*+=|<>~#&^$@-]+")
_FINAL = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})


def normalize_text(text: str) -> str:
    """Lowercase, NFKC, no niqqud, no quote marks, Hebrew final letters folded, single spaces."""
    s = unicodedata.normalize("NFKC", text).lower()
    s = _NIQQUD.sub("", s)
    s = _QUOTES.sub("", s)
    s = s.translate(_FINAL)
    s = _NON_WORD.sub(" ", s)
    return " ".join(s.split())


class QueryEmbedder:
    """One query at a time over a catalog ``Embedder``."""

    def __init__(self, inner: Embedder) -> None:
        self.inner = inner

    @property
    def model_name(self) -> str:
        """The model name stored next to each vector (``canonical_products.embedding_model``,
        ``item_embeddings.model``); search compares only vectors with this name."""
        return self.inner.model_name

    name = model_name

    @property
    def dim(self) -> int:
        return self.inner.dim

    def embed_one(self, text: str) -> list[float]:
        return self.inner.embed([text])[0]


@lru_cache(maxsize=1)
def query_embedder() -> QueryEmbedder:
    """The process-wide query embedder (``API_QUERY_EMBEDDER``, default ``hash``)."""
    return QueryEmbedder(get_embedder(os.environ.get(QUERY_EMBEDDER_ENV, "hash") or "hash"))
