"""Arabic normalization, units, prefixes and the attribute lexicons (issue #73). Pure functions."""

from __future__ import annotations

from decimal import Decimal

import pytest

from smartcart_catalog.normalize import (
    FOLD_TRANSLATE,
    ar_attributes,
    ar_clean_query,
    ar_conflicts,
    ar_strip_prefixes,
    ar_unit,
    ar_variants,
    fold_ar,
    has_arabic,
    normalize_ar,
    script_of,
)

D = Decimal


# --- folding -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "folded"),
    [
        ("حَلِيب", "حليب"),  # tashkeel
        ("حليـــب", "حليب"),  # tatweel
        ("أبيض", "ابيض"),  # alef with hamza above
        ("إلى", "الي"),  # alef with hamza below, ى to ي
        ("آخر", "اخر"),  # alef with madda
        ("ٱلحليب", "الحليب"),  # alef wasla
        ("بيضاء", "بيضا"),  # standalone hamza removed: بيضاء and بيضا meet
        ("جبنة", "جبنه"),  # ة to ه
        ("مؤسسة", "موسسه"),  # ؤ to و
        ("شرائح", "شرايح"),  # ئ to ي
        ("كوتيج ٥٪", "كوتيج 5%"),  # Arabic-Indic digit, Arabic percent
        ("۱۲۳", "123"),  # Persian digits
        ("٢٫٥ كيلو", "2.5 كيلو"),  # Arabic decimal separator
        ("حليب، خبز؛ بيض", "حليب خبز بيض"),  # Arabic comma and semicolon are separators
        ("ک ی ڤ پ", "ك ي ف ب"),  # Persian and loan letters
        ("ﻻ", "لا"),  # presentation form (NFKC)
        ("MILK  3%", "milk 3%"),
        ('"حليب"', "حليب"),
        ("‏حليب‎", "حليب"),  # bidirectional marks
        ("", ""),
    ],
)
def test_fold_ar(raw: str, folded: str) -> None:
    assert fold_ar(raw) == folded


def test_fold_translate_table_is_aligned() -> None:
    # every mapped character maps to one character, deletions are None
    assert FOLD_TRANSLATE[ord("أ")] == "ا"
    assert FOLD_TRANSLATE[ord("٠")] == "0"
    assert FOLD_TRANSLATE[ord("ء")] is None
    assert FOLD_TRANSLATE[ord("ـ")] is None
    assert FOLD_TRANSLATE[ord("٪")] == "%"


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("حليب %3", "حليب 3%"),
        ("حليب 3 %", "حليب 3%"),
        ("حليب ٣٪", "حليب 3%"),
        ("حليب 3 بالمية", "حليب 3%"),
        ("حليب 3 بالمئة", "حليب 3%"),
        ("حليب 3 بالمائة", "حليب 3%"),
        ("حليب ثلاثة بالمية", "حليب 3%"),
        ("حليب تلاتة بالميه", "حليب 3%"),
        ("حليب واحد بالمية", "حليب 1%"),
        ("زبادي واحد ونص بالمية", "زبادي 1.5%"),
        ("زبادي 1.5 في المية", "زبادي 1.5%"),
        ("كريمة ثمانية وثلاثين بالمية", "كريمه 38%"),
        ("حليب 3% 5", "حليب 3% 5"),  # a later number keeps its place
        ("بيض L", "بيض l"),
    ],
)
def test_normalize_ar(raw: str, normalized: str) -> None:
    assert normalize_ar(raw) == normalized


def test_normalize_keeps_article_and_conjunction() -> None:
    assert normalize_ar("والحليب") == "والحليب"


def test_script_of_and_has_arabic() -> None:
    assert script_of("حليب 3%") == "ar"
    assert script_of("חלב 3%") == "he"
    assert script_of("milk 3%") == "other"
    assert script_of("3") == "other"
    assert script_of("حليب חלב ולחם") == "he"  # Hebrew wins
    assert script_of("חלב حليب خبز") == "ar"
    assert script_of("חלב حلب") == "he"  # a tie keeps the Hebrew path
    assert has_arabic("x ب") and not has_arabic("חלב ،")  # the Arabic comma is not a letter


# --- prefixes ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("token", "variants"),
    [
        ("حليب", ["حليب"]),
        ("الحليب", ["الحليب", "حليب"]),
        ("وحليب", ["وحليب", "حليب"]),
        ("والحليب", ["والحليب", "الحليب", "حليب"]),
        ("ورق", ["ورق"]),  # a waw that starts the word: fewer than three letters would remain
        ("الف", ["الف"]),
        ("بالفراوله", ["بالفراوله", "فراوله"]),
        ("للطبخ", ["للطبخ", "طبخ"]),
        ("وافل", ["وافل", "افل"]),
    ],
)
def test_ar_variants(token: str, variants: list[str]) -> None:
    assert ar_variants(token) == variants


def test_ar_strip_prefixes() -> None:
    assert ar_strip_prefixes("الجبنة البيضاء") == "جبنة بيضاء"
    assert ar_strip_prefixes("حليب") == "حليب"


# --- units (40+) -----------------------------------------------------------------------------------

MASS_KG = [
    "كيلو", "كيلوغرام", "كيلوجرام", "كغم", "كجم", "كغ", "كلغ", "كلو", "الكيلو", "كيلوات",
]  # fmt: skip
MASS_G = ["غرام", "جرام", "غم", "جم", "غرامات", "الغرام"]
VOLUME_L = ["لتر", "ليتر", "لترات", "ليترات", "اللتر"]
VOLUME_ML = ["مل", "ملل", "مليلتر", "مللتر", "ميليلتر"]
COUNT = [
    "علبة", "علبه", "علب", "حبة", "حبات", "قطعة", "قطع", "كيس", "اكياس", "أكياس", "باكيت",
    "زجاجة", "عبوة", "كرتونة", "ربطة", "حزمة", "صندوق",
]  # fmt: skip
DUAL = {
    "علبتين": ("count", 2), "حبتين": ("count", 2), "قطعتين": ("count", 2),
    "كيسين": ("count", 2), "باكيتين": ("count", 2), "زجاجتين": ("count", 2),
    "كيلوين": ("mass", 2), "لترين": ("volume", 2), "غرامين": ("mass", 2),
}  # fmt: skip


@pytest.mark.parametrize("word", MASS_KG)
def test_kilo_words(word: str) -> None:
    u = ar_unit(word)
    assert u is not None and (u.kind, u.factor, u.multiplier) == ("mass", D(1), 1)


@pytest.mark.parametrize("word", MASS_G)
def test_gram_words(word: str) -> None:
    u = ar_unit(word)
    assert u is not None and (u.kind, u.factor) == ("mass", D("0.001"))


@pytest.mark.parametrize("word", VOLUME_L)
def test_litre_words(word: str) -> None:
    u = ar_unit(word)
    assert u is not None and (u.kind, u.factor) == ("volume", D(1))


@pytest.mark.parametrize("word", VOLUME_ML)
def test_millilitre_words(word: str) -> None:
    u = ar_unit(word)
    assert u is not None and (u.kind, u.factor) == ("volume", D("0.001"))


@pytest.mark.parametrize("word", COUNT)
def test_count_words(word: str) -> None:
    u = ar_unit(word)
    assert u is not None and (u.kind, u.factor) == ("count", D(1))


@pytest.mark.parametrize(("word", "expected"), sorted(DUAL.items()))
def test_dual_forms(word: str, expected: tuple[str, int]) -> None:
    u = ar_unit(word)
    assert u is not None and (u.kind, u.multiplier) == expected


@pytest.mark.parametrize("word", ["بندورة", "حليب", "ك", "ورق", "", "3", "علبون"])
def test_not_units(word: str) -> None:
    assert ar_unit(word) is None


def test_plural_units_are_flagged() -> None:
    assert ar_unit("اكياس").plural and ar_unit("علب").plural  # type: ignore[union-attr]
    assert not ar_unit("كيس").plural  # type: ignore[union-attr]


# --- attributes and hard checks ------------------------------------------------------------------------


def test_attributes_of_a_query() -> None:
    a = ar_attributes("حليب طازج 3 بالمية")
    assert a.fat_pct == {D(3)} and a.state == {"fresh"}
    assert ar_attributes("كوتيج 1.5%").fat_pct == {D("1.5")}
    assert ar_attributes("حليب خالي الدسم").fat_pct == {D(0)}
    assert ar_attributes("ذرة معلبة").state == {"canned"}
    assert ar_attributes("صدور دجاج مجمدة").state == {"frozen"}
    assert ar_attributes("حمص ناشف").state == {"dry"}
    assert ar_attributes("حليب لوز").base == {"almond"}
    assert ar_attributes("مشروب صويا").base == {"soy"}
    assert ar_attributes("مشروب الشوفان").base == {"oat"}
    assert ar_attributes("زبادي بالفراولة").flavor == {"strawberry"}
    assert ar_attributes("بسكويت").fat_pct == frozenset()


def test_conflicts_fat_and_state_and_base() -> None:
    q = ar_attributes("حليب 1%")
    assert ar_conflicts(q, {"fat_pct": 3, "state": "fresh"}) == ["fat_pct 3"]
    assert ar_conflicts(q, {"fat_pct": 1, "state": "fresh"}) == []
    assert ar_conflicts(q, {"fat_pct": "1.0"}) == []
    assert ar_conflicts(ar_attributes("صدر دجاج مجمد"), {"state": "fresh"}) == ["state fresh"]
    assert ar_conflicts(ar_attributes("ذرة معلبة"), {"state": "frozen"}) == ["state frozen"]
    assert ar_conflicts(ar_attributes("ذرة معلبة"), {"state": "canned"}) == []
    assert ar_conflicts(ar_attributes("حليب لوز"), {"base": "soy"}) == ["base soy"]
    assert ar_conflicts(ar_attributes("حليب لوز"), {"base": "almond"}) == []
    # not stated: nothing is contradicted
    assert ar_conflicts(ar_attributes("حليب"), {"fat_pct": 3, "state": "fresh"}) == []


def test_dry_does_not_contradict_the_catalogs_fresh_onion() -> None:
    # the catalog's "dry onion" is state fresh; a query that says dry must still find it
    assert ar_conflicts(ar_attributes("بصل ناشف"), {"state": "fresh"}) == []
    assert ar_conflicts(ar_attributes("حمص ناشف"), {"state": "canned"}) == ["state canned"]


def test_flavor_conflict_needs_a_sibling_flavor() -> None:
    q = ar_attributes("بوريكس بطاطا")
    assert ar_conflicts(q, {"flavor": "cheese"}, frozenset({"cheese", "potato"})) == [
        "flavor cheese"
    ]
    assert ar_conflicts(q, {"flavor": "potato"}, frozenset({"cheese", "potato"})) == []
    # a generic noun in the query is not a flavor of a sibling: no veto
    assert ar_conflicts(ar_attributes("جبنة كريمة"), {"flavor": "plain"}, frozenset()) == []
    both = ar_attributes("بوريكس بطاطا وجبنة")
    assert ar_conflicts(both, {"flavor": "cheese"}, frozenset({"cheese", "potato"})) == []


# --- cleaning the query ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("حليب تنوفا 3%", "حليب 3%"),
        ("لو سمحت حليب 3%", "حليب 3%"),
        ("رب بندورة كبير", "رب بندورة"),
        ("ورق تواليت 32 رول", "ورق تواليت"),
        ("مياه معدنية 1.5 لتر", "مياه معدنية"),
        ("بيض l 12", "بيض l"),
        ("زبدة اقتصادي", "زبدة"),
        ("تنوفا", "تنوفا"),  # nothing else left: unchanged
        ("حليب 3%", "حليب 3%"),
    ],
)
def test_ar_clean_query(raw: str, clean: str) -> None:
    assert ar_clean_query(normalize_ar(raw)) == normalize_ar(clean)
