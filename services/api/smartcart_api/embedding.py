"""A deterministic 1024-dimension character n-gram hash embedding.

This is a stand-in for BGE-M3 (decision D5) so search, the list parser and their tests work
without a model download. It captures spelling, not meaning: typos and word order are fine,
synonyms are not. The catalog workstream defines the same idea (``HashEmbedder``) in
``smartcart_catalog``; when real embeddings are loaded into ``canonical_products.embedding`` and
``item_embeddings``, swap the query embedder in ``smartcart_api.search`` for the same model.

The vector of a text is the L2-normalized sum of signed hashed features: character 2-, 3- and
4-grams of each word padded with spaces, plus the whole word. blake2b keeps it stable across
processes and Python versions (``hash()`` is salted per process).
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata

DIM = 1024

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


def _features(text: str) -> list[str]:
    out: list[str] = []
    for word in normalize_text(text).split():
        out.append(f"w:{word}")
        padded = f" {word} "
        for n in (2, 3, 4):
            out.extend(f"{n}:{padded[i : i + n]}" for i in range(max(0, len(padded) - n + 1)))
    return out


class HashEmbedder:
    model_name = "hash-ngram-1024"
    dim = DIM

    def embed_one(self, text: str) -> list[float]:
        vec = [0.0] * DIM
        for feat in _features(text):
            h = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % DIM
            sign = 1.0 if h[4] & 1 else -1.0
            weight = 2.0 if feat.startswith("w:") else 1.0
            vec[idx] += sign * weight
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(t) for t in texts]


def to_pgvector(vec: list[float]) -> str:
    """The text form pgvector parses: ``[0.1,0.2,...]``."""
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))
