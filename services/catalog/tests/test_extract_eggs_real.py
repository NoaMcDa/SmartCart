"""Real egg items on the way to the egg canonicals (docs/matching.md, "Eggs").

The names, fields and chains below are verbatim from the "Real day" run 39739262262 of 2026-10-22
(GitHub runner, transparency files of six chains: ``eggs-l`` candidates of the report). Before the
egg rules not one of them reached ``eggs-l``, ``eggs-m`` or ``eggs-xl`` (an unknown product type
capped them under the 0.6 rejection line), and a free-range item of size M or of no size was served
as ``eggs-free-range-l``. Chains cut names at 20 characters (24 Shufersal, 40 Tiv Taam): a size word
cut in half ("גדו") is not a size.
"""

from __future__ import annotations

import pytest

from smartcart_catalog.extract.rule import RuleExtractor, egg_product_type
from smartcart_catalog.judge import RuleJudge
from smartcart_catalog.models import Attributes, Candidate
from smartcart_catalog.normalize import normalize
from smartcart_catalog.seed import load_catalog

RAMI_LEVY = "7290058140886"
OSHER_AD = "7290103152017"
YOHANANOF = "7290803800003"
TIV_TAAM = "7290873255550"
KING_STORE = "7290058108879"

# (chain, ItemName, Quantity field, unit field, product type, pack count)
SIZED = [
    # the name that opened finding 5: two trays of 30, size word cut at 20 characters
    (OSHER_AD, "ביצים 2*30 יח' בינונ", "60.00", "יחידות", "eggs_m", 60),
    (OSHER_AD, "מארז ביצים בינוני 2*", "60.00", "יחידות", "eggs_m", 60),
    (OSHER_AD, "ביצים 12 יח' גדול זג", "12.00", "יחידות", "eggs_l", 12),
    (OSHER_AD, "ביצים 30 יח' גדול מן", "30.00", "יחידות", "eggs_l", 30),
    (OSHER_AD, "ביצים 12 יח ענק XL ל", "12.00", "יחידות", "eggs_xl", 12),
    (OSHER_AD, "ביצים 12 יח' ענק א.", "12.00", "יחידות", "eggs_xl", 12),
    (OSHER_AD, "ביצים 18 יח' בינוני", "18.00", "יחידות", "eggs_m", 18),
    # Rami Levy: size word and letter, count glued to the unit, a typo (בנוני)
    (RAMI_LEVY, "ביצים 12 יח גדול L", "1.00", "יחידות", "eggs_l", 12),
    (RAMI_LEVY, "ביצים 12 יח' גודל L", "1.00", "יחידות", "eggs_l", 12),
    (RAMI_LEVY, "ביצים 12 יח בינוני M", "1.00", "יחידות", "eggs_m", 12),
    (RAMI_LEVY, "ביצים 18יח בנוני M", "1.00", "יחידות", "eggs_m", 18),
    (RAMI_LEVY, "ביצים 30יח ענק XL", "1.00", "יחידות", "eggs_xl", 30),
    (RAMI_LEVY, "ביצים גדולות לארג 12", "12.00", "יחידות", "eggs_l", 12),
    # Yohananof: Hebrew size word only
    (YOHANANOF, "ביצים 12 יח גדול", "1.00", "יחידות", "eggs_l", 12),
    (YOHANANOF, "ביצים 12 יח  גדול", "1.00", "יחידות", "eggs_l", 12),
    (YOHANANOF, "ביצים 18 יח בינוני", "1.00", "יחידות", "eggs_m", 18),
    (YOHANANOF, "ביצים 30 יח ענק", "1.00", "יחידות", "eggs_xl", 30),
    # King Store: transliterated sizes
    (KING_STORE, "ביצים לארג' 12 יח'", "12", "יחידות", "eggs_l", 12),
    (KING_STORE, "ביצים 18 יח' L לסר", "18", "יחידות", "eggs_l", 18),
    (KING_STORE, "ביצים מידיום 12 יח'", "12", "יחידות", "eggs_m", 12),
    (KING_STORE, "ביצים מידיום עטוף 30יח'", "30", "יחידות", "eggs_m", 30),
    # Tiv Taam: the tray count has no unit and the fields say 1
    (TIV_TAAM, "ביצים אריזון 12 גדול", "1.00", "יחידות", "eggs_l", 12),
    (TIV_TAAM, "ביצים אריזון 18 בינוני", "1.00", "יחידות", "eggs_m", 18),
    (TIV_TAAM, "ביצים אריזון 12 ענק", "1.00", "יחידות", "eggs_xl", 12),
    (TIV_TAAM, "ביצה פלוס 12 יח L", "1.00", "יחידות", "eggs_l", 12),
    (TIV_TAAM, "ביצים רגילות  12 יח M", "1.00", "יחידות", "eggs_m", 12),
    # free range: only with the size the canonical has
    (TIV_TAAM, "ביצי חופש 12 יח L", "1.00", "יחידות", "eggs_free_range_l", 12),
    (RAMI_LEVY, "ביצי חופש 30יח L רמי", "1.00", "יחידות", "eggs_free_range_l", 30),
    (YOHANANOF, "ביצי חופש 12 יח גדול", "1.00", "יחידות", "eggs_free_range_l", 12),
    (TIV_TAAM, "L ביצי חופש יולק חלמון כתום 18 יחידות", "1.00", "יחידות",
     "eggs_free_range_l", 18),
]  # fmt: skip

# An egg whose size is missing, cut, ambiguous or not the canonicals' kind: the generic type, which
# no canonical has. It must never be a size type.
NOT_A_SIZE = [
    (TIV_TAAM, "ביצי חופש 12 יח M", "1.00", "יחידות"),  # free range, but M: no such canonical
    (YOHANANOF, "ביצי חופש 12 יח בינו", "1.00", "יחידות"),  # free range, M cut at 20
    (RAMI_LEVY, "ביצים חופש 12 יחידות", "1.00", "יחידות"),  # free range, no size
    (TIV_TAAM, "ביצי חופש 12 יח", "1.00", "יחידות"),
    (YOHANANOF, "ביצי חופש", "1.00", "יחידות"),
    (OSHER_AD, "ביצי חופש 20 יח' גדו", "20.00", "יחידות"),  # "גדו" is not yet a size
    (OSHER_AD, "ביצים חופש 12 יח גדו", "12.00", "יחידות"),
    (OSHER_AD, "ביצים אורגניות  12 י", "12.00", "יחידות"),
    (YOHANANOF, "ביצים אורגני 12 יח ג", "1.00", "יחידות"),
    (TIV_TAAM, "ביצים אורגניות 12 יח L", "1.00", "יחידות"),  # organic L is not plain L
    (TIV_TAAM, "ביצים אומגה 3 12 יח L", "1.00", "יחידות"),
    (TIV_TAAM, "ביצים אומגה M 12 יח", "1.00", "יחידות"),
    (RAMI_LEVY, "ביצי אומגה 12יח L", "1.00", "יחידות"),
    (OSHER_AD, "ביצים אומגה 12 יח גד", "12.00", "יחידות"),
    (TIV_TAAM, "ביצי שליו 20 יח", "1.00", "יחידות"),  # quail
    (YOHANANOF, "ביצה קשה", "1.00", "יחידות"),  # hard boiled
]  # fmt: skip

# Not eggs to eat: no egg type at all.
NOT_EGGS = [
    (TIV_TAAM, "איטריות ביצים 500 גרם Bechtle", "500.00", "גרם"),
    (RAMI_LEVY, "פתיתי ביצים כוכ", "400.00", "לא ידוע"),
    (YOHANANOF, "ביצי דג שיבוט 200 גר", "200.00", "גרם"),
    (TIV_TAAM, "ביצי דג אלתית אלסקה 500 גרם כשר", "500.00", "גרם"),
    (YOHANANOF, "ביצים עלומות 200 גרם", "200.00", "גרם"),  # poached eggs in a jar
    (YOHANANOF, "מגירת ביצים נתלית אק", "160.00", "גרם"),
    (TIV_TAAM, "חותך ביצים נירוסטה", "1.00", "יחידות"),
    (YOHANANOF, "פורס ביצים כפול", "1.00", "יחידות"),
    (RAMI_LEVY, "בצק משחק -ביצה", "1.00", "יחידות"),
    (KING_STORE, "ביצת קינדר ג'וי 20 ג'", "20", "גרם"),
]  # fmt: skip

EGG_TYPES = {"eggs_l", "eggs_m", "eggs_xl", "eggs_free_range_l"}


@pytest.fixture(scope="module")
def rx() -> RuleExtractor:
    return RuleExtractor()


def extract(rx: RuleExtractor, chain: str, name: str, qty: str, unit: str) -> Attributes:
    item = normalize(
        {"raw_name": name, "item_code": "7290000000000", "chain_id": chain,
         "quantity": qty, "unit": unit},
        item_id=1,
    )  # fmt: skip
    out = rx.extract([item])[0]
    assert isinstance(out, Attributes)
    return out


@pytest.mark.parametrize(("chain", "name", "qty", "unit", "ptype", "pack"), SIZED)
def test_real_egg_names_get_their_size_and_tray_count(rx, chain, name, qty, unit, ptype, pack):
    a = extract(rx, chain, name, qty, unit)
    assert a.product_type == ptype
    assert a.category_path == "dairy.eggs.chicken"
    assert a.unit == "unit" and a.pack_size == pack


@pytest.mark.parametrize(("chain", "name", "qty", "unit"), NOT_A_SIZE)
def test_an_egg_of_unknown_or_other_kind_is_never_a_size_type(rx, chain, name, qty, unit):
    a = extract(rx, chain, name, qty, unit)
    assert a.product_type == "eggs"
    assert a.product_type not in EGG_TYPES


@pytest.mark.parametrize(("chain", "name", "qty", "unit"), NOT_EGGS)
def test_what_is_not_an_egg_to_eat_has_no_egg_type(rx, chain, name, qty, unit):
    a = extract(rx, chain, name, qty, unit)
    assert a.product_type not in EGG_TYPES | {"eggs"}


def test_a_size_word_cut_to_a_stem_counts_only_when_it_is_a_whole_stem() -> None:
    # "בינונ" (the 20-character cut of "בינוני") is read, "גדו" (could be "גדולות מאוד") is not
    assert egg_product_type("ביצים 2*30 יח'", cut_tail="בינונ") == "eggs_m"
    assert egg_product_type("ביצי חופש 20 יח'", cut_tail="גדו") == "eggs"
    # two sizes in one name: ambiguous, not either of them
    assert egg_product_type("ביצים L XL 12 יח") == "eggs"
    # "גדולות מאוד" is XL, the plain "גדולות" is L
    assert egg_product_type("ביצים גדולות מאוד 12 יח") == "eggs_xl"
    assert egg_product_type("ביצים גדולות 12 יח") == "eggs_l"
    assert egg_product_type("אטריות ביצים 500 גרם") is None


def test_a_real_lactose_free_milk_with_the_chains_own_wording_has_its_type(rx) -> None:
    # Osher Ad, cut at 20 characters; "נטול לקטוז" is how it writes "ללא לקטוז" (the other dairy
    # line of the basket index with a typing gap in the real day of 2026-10-22)
    a = extract(rx, OSHER_AD, "חלב נטול לקטוז 2% טר", "1.00", "יחידות")
    assert a.product_type == "milk_lactose_free" and str(a.fat_pct) == "2"


def _judge(rx: RuleExtractor, chain: str, name: str, qty: str, unit: str):
    catalog = load_catalog()
    item = normalize(
        {"raw_name": name, "item_code": "7290000000000", "chain_id": chain,
         "quantity": qty, "unit": unit},
        item_id=7,
    )  # fmt: skip
    attrs = rx.extract([item])[0]
    eggs = [
        c.model_copy(update={"id": i})
        for i, c in enumerate(catalog.canonicals, start=1)
        if c.slug.startswith("eggs-")
    ]
    candidates = [Candidate(canonical_id=c.id, similarity=0.65, canonical=c) for c in eggs]
    return RuleJudge().judge(item, attrs, candidates, catalog.rules), {c.id: c.slug for c in eggs}


@pytest.mark.parametrize(
    ("chain", "name", "qty", "unit", "slug", "level"),
    [
        (RAMI_LEVY, "ביצים 12 יח גדול L", "1.00", "יחידות", "eggs-l", "any_brand"),
        (YOHANANOF, "ביצים 18 יח גדול", "1.00", "יחידות", "eggs-l", "close"),  # tray of 18: soft
        (YOHANANOF, "ביצים 12 יח בינוני", "1.00", "יחידות", "eggs-m", "any_brand"),
        (OSHER_AD, "ביצים 2*30 יח' בינונ", "60.00", "יחידות", "eggs-m", "close"),
        (RAMI_LEVY, "ביצים 30יח ענק XL", "1.00", "יחידות", "eggs-xl", "close"),
        (TIV_TAAM, "ביצי חופש 12 יח L", "1.00", "יחידות", "eggs-free-range-l", "any_brand"),
    ],
)
def test_the_judge_maps_a_real_egg_only_to_the_canonical_of_its_size(
    rx, chain, name, qty, unit, slug, level
):
    decision, slugs = _judge(rx, chain, name, qty, unit)
    assert decision.canonical_id is not None
    assert slugs[decision.canonical_id] == slug
    assert decision.flex_level == level
    assert decision.confidence >= 0.6  # reaches the review queue or better, never rejected


@pytest.mark.parametrize(("chain", "name", "qty", "unit"), NOT_A_SIZE)
def test_the_judge_never_maps_an_egg_of_unknown_size_to_a_size_canonical(
    rx, chain, name, qty, unit
):
    decision, _ = _judge(rx, chain, name, qty, unit)
    assert decision.canonical_id is None
    assert "critical mismatch product_type eggs vs" in decision.reason
