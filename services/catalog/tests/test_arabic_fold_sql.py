"""search_norm_ar() in Postgres must equal fold_ar() in Python (issue #73).

The trigram and full-text indexes read the database function, the API folds the query with the
Python one; if they disagree an Arabic name stops matching its own spelling."""

from __future__ import annotations

import random

import pytest
import yaml

from smartcart_catalog.normalize import fold_ar
from smartcart_catalog.taxonomy import default_data_dir

ALPHABET = (
    "ابتثجحخدذرزسشصضطظعغفقكلمنهويءأإآٱىةؤئ"  # letters, hamza forms
    "ًٌٍَُِّْٰ"  # tashkeel
    "ـ"  # tatweel
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳"  # Arabic-Indic and Persian digits
    "0123456789.%٪٫،؛؟,;:!?()[]{}/\\*+=|<>~#&^$@«»…–—•·- "
    "\"'`’‘“”"
    "abcXYZ"
    "کیڤپ"
    "‎‏؜"
)


def _corpus() -> list[str]:
    doc = yaml.safe_load((default_data_dir() / "canonicals.yaml").read_text(encoding="utf-8"))
    names = [n for c in doc["canonicals"] for n in c["names_ar"]]
    rng = random.Random(73)
    noise = ["".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, 24))) for _ in range(400)]
    fixed = [
        "", " ", "حَلِيب  طازَج ٣٪", "بيضاء", "إلى آخره", "٢٫٥ كيلو", "ک ی ڤ پ", "'\"حليب\"'",
        "a  b", "‏حليب‎", "كوتيج - 5%", "حليب|خبز", "ـــ", "ء", "مؤسسة مائة",
    ]  # fmt: skip
    return names + noise + fixed


@pytest.mark.db
def test_search_norm_ar_equals_fold_ar(db) -> None:
    mismatches = []
    for text in _corpus():
        (sql,) = db.execute("SELECT search_norm_ar(%s)", (text,)).fetchone()
        if sql != fold_ar(text):
            mismatches.append((text, sql, fold_ar(text)))
    assert not mismatches, mismatches[:10]


@pytest.mark.db
def test_names_index_function_joins_the_names(db) -> None:
    (joined,) = db.execute(
        "SELECT canonical_names_ar_norm(ARRAY['حَلِيب طازج ٣٪', 'جبنة بيضاء'])"
    ).fetchone()
    assert joined == "حليب طازج 3% جبنه بيضا"
    (empty,) = db.execute("SELECT canonical_names_ar_norm('{}')").fetchone()
    assert empty == ""


@pytest.mark.db
def test_names_ar_column_and_indexes_exist(db) -> None:
    (col,) = db.execute(
        "SELECT data_type FROM information_schema.columns"
        " WHERE table_name = 'canonical_products' AND column_name = 'names_ar'"
    ).fetchone()
    assert col == "ARRAY"
    idx = {
        r[0]
        for r in db.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'canonical_products'"
        ).fetchall()
    }
    assert {"canonical_products_names_ar_trgm", "canonical_products_names_ar_fts"} <= idx
