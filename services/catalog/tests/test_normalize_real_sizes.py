"""Size, pack and unit parsing on the names and fields of the seven chains' real price files.

Issue #20 asked for the rule normalizer to be turned from "50 realistic names" into cases taken from
real loads. ``smartcart-catalog normalize`` over the 1,400 real items (the committed fixtures
``services/ingest/tests/fixtures/<chain>/real``, fetched 2026-10-08) reported 165 unparseable items
and 77 other flagged items; reading every digit-bearing name next to the chain's own fields found
more that were not reported at all (a size read from the last digits of a glued number). Each class
below is one real failure, with the names and fields exactly as the chains publish them (some cut
at the chain's name width, see ``test_normalize_real.py``).

A case is ``(chain_id, item_code, raw_name, quantity, unit, is_weighed)`` and the expected
``(one piece, unit, pack count, total, base unit, weighed)``, plus the issue the normalizer must
report (``None``: it must report nothing). Precision over recall: where a size cannot be read
safely the expected result is "no size" (``NONE``), never a guess.
"""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from smartcart_catalog.normalize import (
    MAX_PIECE_G,
    MAX_PIECE_ML,
    clean_name,
    implausible_size,
    normalize_with_issues,
)
from smartcart_catalog.review_packet import load_real_items
from smartcart_ingest.models import ItemRecord

KING = "7290058108879"
MEGA = "7290055700007"  # Carrefour
OSHER = "7290103152017"
RAMI = "7290058140886"
SHUFERSAL = "7290027600007"
TIV = "7290873255550"
YOHANANOF = "7290803800003"

NONE = (None, None, 1, None, None, False)
"""No size: what an item must give when its size cannot be read safely."""

# (chain, code, raw name, quantity, unit, is_weighed) -> (qty, unit, pack, total, base, weighed), issue
Case = tuple[tuple, tuple, "str | None"]

# --- class 1: a number glued to a Hebrew letter was read from its last digit --------------------
# Shufersal prints "מנטה64ג"; the lookbehind that kept the parser out of the middle of a word kept
# it out of the middle of the number too, so 64 g was read as 4 g and the unit price came out 16
# times too high. 25 items, every one of them with a correct field next to the wrong name.
GLUED = [
    (
        (SHUFERSAL, "4009900403023", "מסטיק אורביט ויט מנטה64ג", "64.00", "גרם", False),
        (64, "g", 1, 64, "100g", False),
        None,
    ),
    (
        (SHUFERSAL, "4011800000349", "קורני בייס קרמל סולט138ג", "138.00", "גרם", False),
        (138, "g", 1, 138, "100g", False),
        None,
    ),
    (
        (SHUFERSAL, "18000701223", "תערובת לעוגת שוקולד425גר", "425.00", "גרם", False),
        (425, "g", 1, 425, "100g", False),
        None,
    ),
    (
        (SHUFERSAL, "22200956932", "ספיד סטיק גל24/7כחול85ג", "85.00", "גרם", False),
        (85, "g", 1, 85, "100g", False),
        None,
    ),
    (
        (SHUFERSAL, "40052403", "חטיף קיט קאט אצבעות41ג", "41.00", "גרם", False),
        (41, "g", 1, 41, "100g", False),
        None,
    ),
    (
        (SHUFERSAL, "3608580162506", "סיינט אמור תות שדה275גרם", "275.00", "גרם", False),
        (275, "g", 1, 275, "100g", False),
        None,
    ),
    (
        (SHUFERSAL, "4084500088917", "פיירי לכלים לימון650מל", "650.00", "מיליליטר", False),
        (650, "ml", 1, 650, "100ml", False),
        None,
    ),
    (
        (SHUFERSAL, "36000516890", "קלינקס לושן 3 שכבות120יח", "1.00", "יחידות", False),
        (120, "unit", 1, 120, "unit", False),
        None,
    ),
    (  # the count is glued too: the field is the total, the name gives the pieces
        (SHUFERSAL, "16000548404", "חטיף נייטשר וואלי דבש5יח", "210.00", "גרם", False),
        (42, "g", 5, 210, "100g", False),
        "5 pieces from the name",
    ),
]

# --- class 2: the chain's unit is wrong, so the size is 1000 times too large ---------------------
# Carrefour prints the unit ליטר on grams (400 "liters" of canned corn): 11 of its 11 liter rows
# are 20 to 686. Shufersal prints a cut "500מל" as "500ל". Above 20 L (or 50 kg) in one piece the
# size is unknown, or comes from the other source when there is one.
IMPLAUSIBLE = [
    (
        (MEGA, "7290100704868", "גרעיני תירס מתוק 400", "400.00", "ליטר", False),
        NONE,
        "size in the fields not used: 400.00 L in one piece",
    ),
    (
        (MEGA, "7290010002016", "מימון כוסברה טחונה 1", "100.00", "ליטר", False),
        NONE,
        "size in the fields not used: 100.00 L",
    ),
    (
        (MEGA, "7290116934365", "נפוליאון 16% שום שמי", "225.00", "ליטר", False),
        NONE,
        "size in the fields not used: 225.00 L",
    ),
    (  # exactly 20 L is already not a shelf piece for a spice bag
        (MEGA, "7290010003686", "עלי דפנה מימון שקית", "20.00", "ליטר", False),
        NONE,
        "size in the fields not used: 20.00 L",
    ),
    (  # the name has the real size, in grams
        (MEGA, "7290010002399", "מימון בזיליקום 40 גר", "40.00", "ליטר", False),
        (40, "g", 1, 40, "100g", False),
        "size in the fields not used: 40.00 L",
    ),
    (  # "500ל" is 500 L in the name, 500 ml in the field
        (SHUFERSAL, "3600524163204", "אלביב מרכך לרכות  500ל", "500.00", "מיליליטר", False),
        (500, "ml", 1, 500, "100ml", False),
        "size in the name not used: 500 L in one piece",
    ),
]

# --- class 3: a PLU-style code on an item the chain sells by the piece --------------------------
# 20 bakery, bag, deposit and bottled-water rows have a 3 to 5 digit code AND the field "1 יחידות"
# with bIsWeighted 0. They were read as 1 kg at a per-kg price. A scale item has no unit field.
COUNTED_NOT_WEIGHED = [
    ((MEGA, "996", "חלה קלועה", "1.00", "יחידות", False), (1, "unit", 1, 1, "unit", False), None),
    (
        (MEGA, "401", "פיתה (1461303)", "1.00", "יחידות", False),
        (1, "unit", 1, 1, "unit", False),
        None,
    ),
    ((MEGA, "1009", "בגט שלם.", "1.00", "יחידות", False), (1, "unit", 1, 1, "unit", False), None),
    (
        (KING, "12345", "פיקדון בקבוקים", "1", "יחידות", False),
        (1, "unit", 1, 1, "unit", False),
        None,
    ),
    (
        (YOHANANOF, "2217", "מים מינרלים קטן", "1.00", "יחידות", False),
        (1, "unit", 1, 1, "unit", False),
        None,
    ),
    (  # the count in the name still wins over "1 יחידות"
        (MEGA, "6305", "מארז 10 לחמניות פטיט", "1.00", "יחידות", False),
        (10, "unit", 1, 10, "unit", False),
        None,
    ),
    (  # what the chain flags as weighed is weighed
        (KING, "777082", "אבטיח", "1000", "גרם", True),
        (1000, "g", 1, 1000, "kg", True),
        None,
    ),
    (  # "55 לק"ג" is a price per kilo on a sweet sold by weight
        (TIV, "1460320", 'סוכריות במשקל ב 55 לק"ג', "1.00", "קילוגרם", True),
        (1000, "g", 1, 1000, "kg", True),
        None,
    ),
]

# --- class 4: pack words and counts -------------------------------------------------------------
PACKS = [
    (  # "מארז 5 יחידות" is five pieces, not five packs of five (25)
        (MEGA, "7290000103123", "מארז 5 יחידות ג'בטה", "1.00", "יחידות", False),
        (5, "unit", 1, 5, "unit", False),
        None,
    ),
    (  # a pair of burgers: the 226 g is the pair (the field says so), 452 g was read
        (TIV, "1230000116022", "המבורגר ביונד מיט זוג 226 גרם", "226.00", "גרם", False),
        (113, "g", 2, 226, "100g", False),
        "read as the total of 2 pieces",
    ),
    (  # the size in the name is the pack total as well as the field: still one piece of 226 g
        (KING, "77975094631", "שברי בייגלה בטעם קרם צ'דר 226 ג' סניידרס", "266", "גרם", False),
        (226, "g", 1, 226, "100g", False),
        "fields say 266 g, name says 226 g",
    ),
    (  # a four-pack named in words, the total in the field
        (SHUFERSAL, "3080216064208", "בירה רביעיית 1664 Blanc", "1320.00", "מיליליטר", False),
        (330, "ml", 4, 1320, "100ml", False),
        "4 pieces from the name",
    ),
    (
        (KING, "80310167", "קינדר מקסי שישייה", "126", "גרם", False),
        (21, "g", 6, 126, "100g", False),
        "6 pieces from the name",
    ),
    (  # a pack of bars with the count first: 5 bars of 23 g, then the total 115 g
        (TIV, "18176784907", 'בד"צ טורינו חלב חמישייה 23X5ג 115ג', "115.00", "גרם", False),
        (23, "g", 5, 115, "100g", False),
        None,
    ),
    (  # unit count only, a pack word and no size: per piece, and says so
        (RAMI, "7290017023212", "רביעיית פחיות שוופס", "1.32", "לא ידוע", False),
        (1, "unit", 4, 4, "unit", False),
        "only a pack count was found",
    ),
]

# --- class 5: multiplications -------------------------------------------------------------------
MULTIPLY = [
    (  # two trays of 30: 60 eggs, not 30
        (OSHER, "7290011778477", "ביצים 2*30 יח' בינונ", "60.00", "יחידות", False),
        (30, "unit", 2, 60, "unit", False),
        None,
    ),
    (
        (SHUFERSAL, "3034250007813", "קלינקס טישו כיס 12*9יח", "1.00", "יחידות", False),
        (9, "unit", 12, 108, "unit", False),
        None,
    ),
    (  # 4*140 has no unit; the field 560 g confirms 4 x 140
        (OSHER, "7290019568209", "טונה בשמן טעמן 4*140", "560.00", "גרם", False),
        (140, "g", 4, 560, "100g", False),
        "4 pieces from the name",
    ),
    (
        (SHUFERSAL, "4011800003517", 'קורני פרי בננה לל"ס 6*20', "120.00", "גרם", False),
        (20, "g", 6, 120, "100g", False),
        "6 pieces from the name",
    ),
    (
        (SHUFERSAL, "4011800528416", "קורני בוטנ.מתוק מלוח6*25", "150.00", "גרם", False),
        (25, "g", 6, 150, "100g", False),
        "6 pieces from the name",
    ),
    (  # 3*4 with no field to confirm it: not a size, not a guess
        (OSHER, "835811000068", "מגבוני טואלט קשת 3*4", None, "יחידות", False),
        NONE,
        "unparseable: no quantity",
    ),
    (  # bags times grams: 20 x 3 g, the second number is the size of one bag
        (SHUFERSAL, "4009300524588", "חליטת פירות יער20שקיק*3ג", "60.00", "גרם", False),
        (3, "g", 20, 60, "100g", False),
        None,
    ),
    (
        (SHUFERSAL, "4009300524625", "תה צאי מאסלה20שק*2גר", "40.00", "גרם", False),
        (2, "g", 20, 40, "100g", False),
        None,
    ),
    (
        (SHUFERSAL, "4605246009969", "תה שחור אוכמניות 25שק", "1.00", "יחידות", False),
        (25, "unit", 1, 25, "unit", False),
        None,
    ),
    (
        (SHUFERSAL, "4009300526438", "תה ירוק קלאסי 20 שקיקים", "30.00", "גרם", False),
        (D("1.5"), "g", 20, 30, "100g", False),
        "20 pieces from the name",
    ),
    (  # the count in front of the size, the field is the pack total
        (KING, "666999", "מארז מים קסטל 330 מ\"ל *24 יח'", "7920", "מיליליטר", False),
        (330, "ml", 24, 7920, "100ml", False),
        None,
    ),
    (
        (KING, "87108712", "מנטוס פירות מארז 4 יח' * 37.5 ג'", "150", "גרם", False),
        (D("37.5"), "g", 4, 150, "100g", False),
        None,
    ),
    (
        (SHUFERSAL, "4008287058161", 'בירה קרומבאכר 6*330 מ"ל', "1.98", "ליטר", False),
        (330, "ml", 6, 1980, "100ml", False),
        None,
    ),
]

# --- class 6: a unit cut by the chain's name width ----------------------------------------------
# Only as the last characters of the name, right after a number; a bare מ is a metre as often as
# a millilitre ("מקל מעץ 1.5 מ'", "מפת ניילון גליל 50 מ") and is left alone.
CUT = [
    (  # 1 ק"ג cut to 1 ק", the field says 1 kg and the name now says it too: a pack, not weighed
        (MEGA, "7290015968454", 'מארז צלחות  לבן 1 ק"', "1.00", "קילוגרם", False),
        (1000, "g", 1, 1000, "100g", False),
        None,
    ),
    (
        (OSHER, "7290002007760", 'פירורי לחם הנמל 1 ק"', "1.00", "לא ידוע", False),
        (1000, "g", 1, 1000, "100g", False),
        None,
    ),
    (  # the field has no unit (לא ידוע): the cut word is the only source
        (OSHER, "7290001791349", "אקונומיקה פסגה 4 ליט", "4.00", "לא ידוע", False),
        (4000, "ml", 1, 4000, "100ml", False),
        None,
    ),
    (  # the field says "1 יחידות", the cut מ" is the size
        (RAMI, "6253504185061", 'כוס שתייה קרה 300 מ"', "1.00", "יחידות", False),
        (300, "ml", 1, 300, "100ml", False),
        None,
    ),
    (
        (MEGA, "7290016717044", 'יין באזז מנגו 750 מ"', "750.00", "מיליליטר", False),
        (750, "ml", 1, 750, "100ml", False),
        None,
    ),
    (  # יח' cut to its first letter
        (SHUFERSAL, "3574660464429", "קרפרי אוורירי מגה פק 76י", "1.00", "יחידות", False),
        (76, "unit", 1, 76, "unit", False),
        None,
    ),
    (  # Shufersal's own "4י" in the middle of a name
        (SHUFERSAL, "3014260262709", "סכיני גילוח ונוס4י גילט", "1.00", "יחידות", False),
        (4, "unit", 1, 4, "unit", False),
        None,
    ),
    (  # 20 שקיקים cut to 20ש, the field is the pack total
        (SHUFERSAL, "4009300011958", "פומפדור ניו יורק צאי20ש", "35.00", "גרם", False),
        (D("1.75"), "g", 20, 35, "100g", False),
        "20 pieces from the name",
    ),
    (  # a bare מ: ml or metre, so no size from the name; the field has no unit either
        (OSHER, "11210007352", "רוטב טבסקו שום 150 מ", "150.00", "לא ידוע", False),
        NONE,
        "unparseable: the quantity 150 comes with the unit 'לא ידוע'",
    ),
    (  # a metre: a count of one, never 50 ml
        (RAMI, "7290108358995", "מפת ניילון גליל 50 מ", "1.00", "יחידות", False),
        (1, "unit", 1, 1, "unit", False),
        None,
    ),
    (
        (KING, "111499", "מקל מעץ 1.5 מ'", "1", "יחידות", False),
        (1, "unit", 1, 1, "unit", False),
        None,
    ),
]

# --- class 7: unparseable, and why --------------------------------------------------------------
# 173 of 1,400 real items still have no size: 143 have a quantity with the unit לא ידוע (Rami Levy
# 89, Osher Ad 43, Carrefour 10) or a length, 10 had an implausible field, 20 have no quantity at
# all. The reason is in the issue, not a bare "unparseable"; a quantity without a unit is a gram, a
# millilitre or a piece, and nothing in the item says which.
UNKNOWN = [
    (
        (OSHER, "7290001136287", "שמפו נקה 7 לשיער רגי", "750.00", "לא ידוע", False),
        NONE,
        "unparseable: the quantity 750 comes with the unit 'לא ידוע'",
    ),
    (
        (MEGA, "7290117383759", "פלמוליב חלב ודבש 500", "1.00", "לא ידוע", False),
        NONE,
        "unparseable: the quantity 1 comes with the unit 'לא ידוע'",
    ),
    (
        (SHUFERSAL, "10900302814", 'ניילון נצמד 30ס"מ*30 מטר', "30.00", "מטרים", False),
        NONE,
        "unparseable: the quantity 30 comes with the unit 'מטרים'",
    ),
    (
        (MEGA, "9001616703232", "מחזיק מוצץ יוניסקס", None, "יחידות", False),
        NONE,
        "unparseable: no quantity in the fields or the name",
    ),
]

# --- class 8: the name and the fields disagree --------------------------------------------------
# Both are the chain's. The name wins (documented), the disagreement is reported, and a field that
# the chain only rounded (187 for 187.5) is not a disagreement.
DISAGREE = [
    (
        (SHUFERSAL, "4000417101280", "חטיף אמיצלי 187.5 גרם", "187.00", "גרם", False),
        (D("187.5"), "g", 1, D("187.5"), "100g", False),
        None,
    ),
    (
        (MEGA, "7290012936937", "מימון בהרט 40 גרם", "50.00", "גרם", False),
        (40, "g", 1, 40, "100g", False),
        "fields say 50.00 g, name says 40 g; used the name",
    ),
    (
        (TIV, "15300200234", "ציטוס איטריות גבינות צדר וצילי 60 גרם", "160.00", "גרם", False),
        (60, "g", 1, 60, "100g", False),
        "fields say 160.00 g, name says 60 g",
    ),
    (
        (TIV, "13300282540", "תערובת פנקייק שוקולד ציפס הנרי גק 907 ג", "794.00", "גרם", False),
        (907, "g", 1, 907, "100g", False),
        "fields say 794.00 g, name says 907 g",
    ),
]

ALL_CASES: list[Case] = [
    *GLUED,
    *IMPLAUSIBLE,
    *COUNTED_NOT_WEIGHED,
    *PACKS,
    *MULTIPLY,
    *CUT,
    *UNKNOWN,
    *DISAGREE,
]


def _item(row: tuple) -> ItemRecord:
    chain_id, code, raw, qty, unit, weighed = row
    return ItemRecord(
        chain_id=chain_id,
        item_code=code,
        raw_name=raw,
        quantity=None if qty is None else D(qty),
        unit=unit,
        is_weighed=weighed,
    )


@pytest.mark.parametrize(
    ("row", "expected", "issue"), ALL_CASES, ids=[f"{c[0][0][-4:]}:{c[0][2]}" for c in ALL_CASES]
)
def test_real_item_size(row: tuple, expected: tuple, issue: str | None) -> None:
    r = normalize_with_issues(_item(row))
    n = r.item
    got = (n.quantity, n.unit, n.pack_count, n.total_quantity, n.base_unit, n.is_weighed)
    e_qty, e_unit, e_pack, e_total, e_base, e_weighed = expected
    want = (
        None if e_qty is None else D(e_qty),
        e_unit,
        e_pack,
        None if e_total is None else D(e_total),
        e_base,
        e_weighed,
    )
    assert got == want, r.issues
    if issue is None:
        assert r.issues == ()
    else:
        assert any(issue in i for i in r.issues), (issue, r.issues)


def test_the_table_is_real_items() -> None:
    """Every case is an item of the committed real fixtures, name, code and fields verbatim."""
    real = {
        (i.chain_id, i.item_code, i.raw_name): (
            None if i.quantity is None else D(i.quantity),
            i.unit,
            i.is_weighed,
        )
        for i in load_real_items()
    }
    if not real:
        pytest.skip("real fixtures not present")
    for row, _, _ in ALL_CASES:
        chain_id, code, raw, qty, unit, weighed = row
        key = (chain_id, code, raw)
        assert key in real, f"not a real item: {key}"
        r_qty, r_unit, r_weighed = real[key]
        assert (r_qty, r_unit, r_weighed) == (None if qty is None else D(qty), unit, weighed), key


def test_the_table_has_at_least_fifty_real_names() -> None:
    assert len(ALL_CASES) >= 50


# --- abbreviations seen in the real files -------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('כפות ח"פ 188 יח', "כפות חד פעמי 188 יח"),  # Osher Ad
        ('היינקן ח"פ 330 בקבוק', "היינקן חד פעמי 330 בקבוק"),  # Rami Levy
        ("סכין גילוח חדפ גילט", "סכין גילוח חד פעמי גילט"),
        ("קרם רב\"ש ניוטרוג'ינה300מ", "קרם רב שימושי ניוטרוג'ינה300מ"),
        ("צלעות עגל טרי מס' 2", "צלעות עגל טרי מספר 2"),  # King Store
        ("מארז 5 חב' טישו (5*1", "מארז 5 חבילות טישו (5*1"),  # Rami Levy, cut
        ('דאו.ניוואה רול און 50מ"ל', "דאודורנט ניוואה רול און 50מיליליטר"),
        ('דאו. ניוואה לאשה 150 מ"ל', "דאודורנט ניוואה לאשה 150 מיליליטר"),
        ("חמאת בוטנ.סקיפי קלאסי454", "חמאת בוטנים סקיפי קלאסי454"),
        ("ח.דגנים שוקו.מריר6 קורני", "ח.דגנים שוקולד מריר6 קורני"),
        ('סוכ.שוקולד לל"ס 70ג ורטר', "סוכריות שוקולד ללא סוכר 70ג ורטר"),
        ('סוכריות לל"ס ט.מנגו 14גר', "סוכריות ללא סוכר טעם מנגו 14גר"),
        ("שקיות צליה ג`מבו 5 י", "שקיות צליה ג'מבו 5 יחידות"),  # backtick as the geresh
        ("שברי בייגל גבינת צ`דר 319 ג'", "שברי בייגל גבינת צ'דר 319 גרם"),
        ("חטיף אמיצלי ק.אגוז150ג", "חטיף אמיצלי ק.אגוז150ג"),  # ק. is not known: left as printed
        ("חטיף נייטשר וואלי דבש5יח", "חטיף נייטשר וואלי דבש5יח"),
    ],
)
def test_real_abbreviations(raw: str, expected: str) -> None:
    assert clean_name(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "מקל מעץ 1.5 מ'",  # metres
        "מפת ניילון גליל 50 מ",
        "רוטב טבסקו שום 150 מ",  # a cut מ: ml or metre, not known
        "קיט פס לד 5 מ' USB D",
        "ג'בטה",
        "גן ילדים ט.ב",  # a letter and a dot that is not followed by a word
        "טעם מנגו",
    ],
)
def test_ambiguous_shorthand_is_left_as_printed(raw: str) -> None:
    assert clean_name(raw) == raw


# --- the whole real set --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_results():
    items = load_real_items()
    if not items:
        pytest.skip("real fixtures not present")
    return [(i, normalize_with_issues(i)) for i in items]


def test_every_real_item_normalizes(real_results) -> None:
    assert len(real_results) >= 1400
    assert all(r.item.clean_name for _, r in real_results)


def test_no_real_item_has_an_implausible_piece(real_results) -> None:
    for item, r in real_results:
        n = r.item
        if n.quantity is not None and n.unit != "unit" and n.pack_count == 1 and not n.is_weighed:
            assert implausible_size(n.quantity, n.unit) is None, item.raw_name
    assert MAX_PIECE_ML == D(20000) and MAX_PIECE_G == D(50000)


def test_name_and_fields_agree_except_for_the_known_disagreements(real_results) -> None:
    """Before this work 35 items disagreed with their own fields; most of them because the name
    was read from the last digits of a glued number. The 11 left are the chains' own
    disagreements: a name that says 60 g next to a field of 160 g, or a field in ml on a cream in
    grams. The name wins and the disagreement is in the issue list."""
    flagged = sorted(
        i.raw_name
        for i, r in real_results
        if any(s.startswith("fields say ") and "used the name" in s for s in r.issues)
    )
    assert flagged == sorted(
        [
            "מילקי פי 2 קצפת אקסטרה 170 ג'",
            "שברי בייגלה בטעם קרם צ'דר 226 ג' סניידרס",
            "מימון בהרט 40 גרם",
            'דאו.ניוואה דיפ ביט150מ"ל',
            'טבסקו פלפל אדום 60 מ"ל',
            "ביונד מיט טחון 250 גרם",
            "תערובת פנקייק שוקולד ציפס הנרי גק 907 ג",
            "ציטוס איטריות גבינות צדר וצילי 60 גרם",
            "תערובת לעוגת וניל 517 גרם",
            "תערובת לעוגת שיש 550 גרם",
            "תערובת לבראוניס 552 גרם",
        ]
    )


def test_the_unparseable_have_a_stated_reason(real_results) -> None:
    unparsed = [(i, r) for i, r in real_results if not r.parsed and r.source == "none"]
    assert len(unparsed) <= 175
    for i, r in unparsed:
        text = " ".join(r.issues)
        assert "unparseable:" in text, i.raw_name
        assert (
            "no quantity" in text
            or "comes with the unit" in text
            or "has no unit" in text
            or "not used" in text
        ), (i.raw_name, text)
