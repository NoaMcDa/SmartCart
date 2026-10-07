"""Embeddings for chain items and canonical products (issue #29, architecture section 3 step C).

Embeddings are the recall engine of matching: they find "same thing, different words"
candidates. They never decide a match (decision D5); the judge does, with hard rules on top.

Two embedders implement the ``Embedder`` protocol from ``models``:

* ``HashEmbedder``: deterministic, dependency-free, 1024 dimensions. Character n-grams of the
  normalized Hebrew text are hashed into the vector (signed feature hashing) and the result is
  L2-normalized, so strings that share many n-grams ("חלב טרי 3%" and "חלב 3% טרי") get a high
  cosine similarity. It has no semantics at all: it is for tests, CI and local development
  where the real model cannot be downloaded.
* ``BgeM3Embedder``: BGE-M3 dense vectors through sentence-transformers (the optional ``embed``
  extra). Imported lazily so the package works without torch.

The batch jobs ``embed_canonicals`` and ``embed_items`` are idempotent: a row already embedded
with the same model, and unchanged since, is skipped. The model is stored next to each vector
(``canonical_products.embedding_model``, ``item_embeddings.model``), so a model change is
visible on the row itself. Each call records a ``match_runs`` row.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Sequence
from typing import Any

import psycopg

from smartcart_catalog.block import normalize_text
from smartcart_catalog.match import finish_run, start_run
from smartcart_catalog.models import Embedder

DIM = 1024
"""Dimension of ``canonical_products.embedding`` and ``item_embeddings.embedding``."""


def _bucket(feature: str, dim: int) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "little")
    return value % dim, (1.0 if (value >> 63) & 1 else -1.0)


class HashEmbedder:
    """Character n-gram feature hashing into ``dim`` buckets with L2 normalization."""

    def __init__(self, dim: int = DIM, ngram_sizes: Sequence[int] = (2, 3, 4)) -> None:
        self.dim = dim
        self.ngram_sizes = tuple(ngram_sizes)
        self.model_name = f"hash-ngram-{'-'.join(map(str, self.ngram_sizes))}-v1"

    def _features(self, text: str) -> Iterable[tuple[str, float]]:
        norm = normalize_text(text)
        for word in norm.split(" "):
            if not word:
                continue
            yield f"w:{word}", 1.0
            padded = f" {word} "
            for n in self.ngram_sizes:
                for i in range(max(len(padded) - n + 1, 1)):
                    yield f"{n}:{padded[i : i + n]}", 0.5

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for feature, weight in self._features(text):
                idx, sign = _bucket(feature, self.dim)
                vec[idx] += sign * weight
            norm = math.sqrt(sum(v * v for v in vec))
            if norm == 0:
                # An empty string: a fixed unit vector keeps cosine distance defined.
                vec[0] = 1.0
                norm = 1.0
            out.append([v / norm for v in vec])
        return out


class BgeM3Embedder:
    """BGE-M3 dense embeddings (1024 dimensions) via sentence-transformers, loaded lazily."""

    def __init__(
        self, model_name: str = "BAAI/bge-m3", batch_size: int = 32, device: str | None = None
    ) -> None:
        self.model_name = model_name
        self.dim = DIM
        self.batch_size = batch_size
        self.device = device
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - depends on the optional extra
                raise RuntimeError(
                    "BgeM3Embedder needs the optional 'embed' extra: "
                    "uv sync --extra embed (sentence-transformers, torch)"
                ) from exc
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vectors = model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        rows = [[float(x) for x in v] for v in vectors]
        if rows and len(rows[0]) != self.dim:
            raise ValueError(f"{self.model_name} returned {len(rows[0])} dims, expected {self.dim}")
        return rows


def get_embedder(name: str, model_name: str | None = None) -> Embedder:
    """``hash`` (default for tests and local dev) or ``bge-m3``."""
    key = name.strip().lower()
    if key == "hash":
        return HashEmbedder()
    if key in {"bge-m3", "bge_m3", "bgem3"}:
        return BgeM3Embedder(model_name or "BAAI/bge-m3")
    raise ValueError(f"unknown embedder {name!r}: expected 'hash' or 'bge-m3'")


def to_pgvector(vec: Sequence[float]) -> str:
    """pgvector's text input format, cast with ``::vector`` in SQL."""
    return "[" + ",".join(f"{v:.7g}" for v in vec) + "]"


def _check_dim(embedder: Embedder) -> None:
    if embedder.dim != DIM:
        raise ValueError(f"embedder {embedder.model_name} has dim {embedder.dim}, schema has {DIM}")


def _batches(rows: list[Any], size: int) -> Iterable[list[Any]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _fingerprint(text: str) -> str:
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()


def _last_canonical_fingerprints(conn: psycopg.Connection) -> dict[str, str]:
    row = conn.execute(
        "SELECT metrics->'fingerprints' FROM match_runs"
        " WHERE kind = 'embed' AND metrics->>'target' = 'canonicals' AND finished_at IS NOT NULL"
        " ORDER BY finished_at DESC, id DESC LIMIT 1"
    ).fetchone()
    return (row[0] or {}) if row else {}


def embed_canonicals(
    conn: psycopg.Connection, embedder: Embedder, *, batch_size: int = 256, force: bool = False
) -> dict[str, Any]:
    """Embed ``canonical_products.display_name_he`` into ``canonical_products.embedding`` and
    record the model in ``canonical_products.embedding_model``.

    A canonical is (re-)embedded when it has no vector, when its ``embedding_model`` differs
    from ``embedder.model_name`` (read from the row itself), when its name changed since the
    last canonical embed run (a name fingerprint kept in that run's ``match_runs`` metrics), or
    with ``force``.
    """
    _check_dim(embedder)
    prints = _last_canonical_fingerprints(conn)
    rows_all = conn.execute(
        "SELECT id, display_name_he, embedding IS NOT NULL, embedding_model"
        " FROM canonical_products ORDER BY id"
    ).fetchall()
    rows = [
        (cid, name)
        for cid, name, has_vec, model in rows_all
        if force
        or not has_vec
        or model != embedder.model_name
        or prints.get(str(cid)) != _fingerprint(name)
    ]
    full = bool(rows_all) and len(rows) == len(rows_all)
    run_id = start_run(conn, "embed")
    for batch in _batches(rows, batch_size):
        vectors = embedder.embed([name for _, name in batch])
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE canonical_products SET embedding = %s::vector, embedding_model = %s"
                " WHERE id = %s",
                [
                    (to_pgvector(v), embedder.model_name, cid)
                    for (cid, _), v in zip(batch, vectors, strict=True)
                ],
            )
    metrics = {
        "target": "canonicals",
        "model": embedder.model_name,
        "embedded": len(rows),
        "skipped": len(rows_all) - len(rows),
        "full": full,
        "fingerprints": {str(cid): _fingerprint(name) for cid, name, _, _ in rows_all},
    }
    finish_run(conn, run_id, metrics)
    return {k: v for k, v in metrics.items() if k != "fingerprints"}


def embed_items(
    conn: psycopg.Connection,
    embedder: Embedder,
    item_ids: Sequence[int] | None = None,
    *,
    batch_size: int = 256,
    force: bool = False,
) -> dict[str, Any]:
    """Embed ``items.raw_name`` into ``item_embeddings``; skip rows already embedded with the
    same model and not updated since. ``item_ids`` limits the job to those items."""
    _check_dim(embedder)
    params: dict[str, Any] = {"model": embedder.model_name, "force": force}
    where = ""
    if item_ids is not None:
        where = "AND i.id = ANY(%(ids)s)"
        params["ids"] = list(item_ids)
    rows = conn.execute(
        "SELECT i.id, i.raw_name FROM items i"
        " LEFT JOIN item_embeddings e ON e.item_id = i.id"
        " WHERE (%(force)s OR e.item_id IS NULL OR e.model <> %(model)s"
        "        OR i.updated_at > e.embedded_at) " + where + " ORDER BY i.id",
        params,
    ).fetchall()
    if item_ids is None:
        total = conn.execute("SELECT count(*) FROM items").fetchone()[0]
    else:
        total = len(set(item_ids))
    run_id = start_run(conn, "embed")
    for batch in _batches(rows, batch_size):
        vectors = embedder.embed([name for _, name in batch])
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO item_embeddings (item_id, embedding, model, embedded_at)"
                " VALUES (%s, %s::vector, %s, clock_timestamp())"
                " ON CONFLICT (item_id) DO UPDATE SET embedding = EXCLUDED.embedding,"
                " model = EXCLUDED.model, embedded_at = EXCLUDED.embedded_at",
                [
                    (iid, to_pgvector(v), embedder.model_name)
                    for (iid, _), v in zip(batch, vectors, strict=True)
                ],
            )
    metrics = {
        "target": "items",
        "model": embedder.model_name,
        "embedded": len(rows),
        "skipped": total - len(rows),
    }
    finish_run(conn, run_id, metrics)
    return metrics
