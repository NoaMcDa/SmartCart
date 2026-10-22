"""What a name states about kashrut, and the levels (``smartcart_catalog/kosher.py``; docs/matching.md,
"Kosher").

Names marked "real" are verbatim from the committed real fixtures
(``services/ingest/tests/fixtures/*/real`` and ``data/audit/real-2026-10-08``); the others are written
for the test (the real files of October have no named hechsher and no Passover item) and say so.
"""

from __future__ import annotations

import pytest

from smartcart_catalog import kosher as k
from smartcart_catalog.extract.rule import RuleExtractor
from smartcart_catalog.models import Attributes
from smartcart_catalog.normalize import normalize
from smartcart_catalog.review_packet import AUDIT_SNAPSHOT_DIR, FIXTURES_DIR, load_real_items

TIV_TAAM = "7290873255550"
YOHANANOF = "7290803800003"
KING_STORE = "7290058108879"
RAMI_LEVY = "7290058140886"
OSHER_AD = "7290103152017"
MEGA = "7290055700007"


def marks(text: str) -> set[str]:
    return set(k.read_marks(text))


# --- reading: real names -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("chain", "name", "expected"),
    [
        (TIV_TAAM, 'בד"צ סוויס לבן 100ג', {k.BADATZ}),
        (TIV_TAAM, 'בד"צ טורינו חלב חמישייה 23X5ג 115ג', {k.BADATZ}),
        (KING_STORE, "מוצרלה חריץ מהדרין 20%", {k.MEHADRIN}),
        (KING_STORE, "מעדן שוקולד מהדרין 135 ג'  מילקי", {k.MEHADRIN}),
        (MEGA, "דנונה מהדרין טבעי 3%", {k.MEHADRIN}),
        (OSHER_AD, "תירס טרי מהדרין ברכת", {k.MEHADRIN}),
        (RAMI_LEVY, "תירס מהדרין טרי רמי", {k.MEHADRIN}),
        (YOHANANOF, "בשר ראש קפוא כשר", {k.KOSHER}),
        (YOHANANOF, "דונטס חלבי", {k.DAIRY}),
        (RAMI_LEVY, "פרלינו חלבי בונבוניי", {k.DAIRY}),
        (MEGA, "רוגלך פרווה", {k.PAREVE}),
    ],
)
def test_real_names_that_state_something(chain, name, expected) -> None:
    assert set(k.read_item_name(name, chain)) == expected


@pytest.mark.parametrize(
    ("chain", "name"),
    [
        (RAMI_LEVY, "מארז מעיין 5 חלקים ש"),  # "חלקים" is parts, not glatt
        (
            YOHANANOF,
            "בשר מס 5 חלק גראס פד",
        ),  # "חלק" is glatt meat here, and "smooth" elsewhere: not read
        (YOHANANOF, "לשון חלק  קפוא"),
        (RAMI_LEVY, "מחברת A5 פרווה בובה"),  # fur, not pareve
        (MEGA, "חלב תנובה 3% 1 ליטר"),  # "חלב" is milk, not "חלבי"
        (YOHANANOF, "חלב טרה 3% בקבוק"),
        (RAMI_LEVY, "קוטג' 5% תנובה"),
        (OSHER_AD, "מים מינרליים 6*1.5 ל'"),
        (KING_STORE, "פיקדון בקבוקים"),
    ],
)
def test_real_names_that_state_nothing(chain, name) -> None:
    assert k.read_item_name(name, chain) == frozenset()


def test_a_brand_never_gives_a_certification() -> None:
    # Brands that are Haredi-certified in practice are not read as such: the file does not say so.
    for name in ("מעדני חלב תנובה", "גבינה לבנה יטבתה 5%", "אסם פתיתים", "שטראוס עלית שוקולד"):
        assert k.read_marks(name) == frozenset()


# --- reading: spellings and phrases (written for the test) ------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('חלב בד"ץ', {k.BADATZ}),
        ("חלב בד״ץ", {k.BADATZ}),  # gershayim
        ('חלב בד"צ', {k.BADATZ}),  # final tsadi spelling
        ("חלב בדץ", {k.BADATZ}),
        ("חלב בדצ", {k.BADATZ}),
        ('גבינה בד"ץ העדה החרדית', {k.BADATZ, k.BADATZ_EIDA}),
        ("גבינה העדה החרדית", {k.BADATZ, k.BADATZ_EIDA}),
        ('חמאה בד"ץ בית יוסף', {k.BADATZ, k.BADATZ_BEIT_YOSEF}),
        ("חמאה בהשגחת בית יוסף", {k.BADATZ, k.BADATZ_BEIT_YOSEF}),
        ('שמן בד"ץ חתם סופר', {k.BADATZ, k.BADATZ_CHATAM_SOFER}),
        ('אורז בד"ץ אגודת ישראל', {k.BADATZ, k.BADATZ_AGUDAT}),
        ("עוגיות הרב לנדא", {k.LANDAU}),
        ("עוגיות בהשגחת הרב לנדא", {k.LANDAU}),
        ("עוגיות בד״ץ לנדא", {k.BADATZ, k.LANDAU}),
        ("חלב מהדרין", {k.MEHADRIN}),
        ("חלב כשר למהדרין", {k.MEHADRIN, k.KOSHER}),
        ("חלב רבנות מהדרין", {k.RABBANUT_MEHADRIN, k.MEHADRIN, k.RABBANUT}),
        ("חלב מהדרין הרבנות", {k.RABBANUT_MEHADRIN, k.MEHADRIN, k.RABBANUT}),
        ("חלב רבנות", {k.RABBANUT}),
        ("חלב כשר", {k.KOSHER}),
        ("מצות כשר לפסח", {k.PASSOVER}),  # Passover is its own mark, not "kosher"
        ("מצות כשרה לפסח", {k.PASSOVER}),
        ('מצות כשר לפסח בד"ץ', {k.PASSOVER, k.BADATZ}),
        ("חלב לא כשר", {k.NOT_KOSHER}),
        ("גבינה ללא כשרות", {k.NOT_KOSHER}),
        ("חטיף לא כשר לפסח", {k.NOT_PASSOVER}),
        ("שניצל בשרי", {k.MEAT}),
        ("גבינה צהובה חלבית", {k.DAIRY}),
        ("עוגה פארווה", {k.PAREVE}),
        ("עוגה פרוה", {k.PAREVE}),
    ],
)
def test_explicit_words(text, expected) -> None:
    assert marks(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "מלח גס כשר",  # kosher salt is a kind of salt
        'מלח כשר 1 ק"ג',
        "עגבנייה בשרית",  # fleshy tomato
        "פלפל בשרי",
        "בית יוסף חומוס",  # no cue: a brand or a place, not a hechsher
        "אגודת ישראל",  # no cue
        "מארז לפסח",  # "for Passover" is not "kosher for Passover"
        "כשרות",  # the word "kashrut" alone states nothing
        "מהדרינים",  # not a whole word
        "חתם סופר",  # no cue
        "גלאט",  # glatt is not read (see the docs)
    ],
)
def test_words_that_do_not_state_a_certification(text) -> None:
    assert not marks(text) & k.SUPERVISED, text


def test_not_kosher_wins_over_a_certified_word() -> None:
    got = k.read_marks('מוצר לא כשר בד"ץ')
    assert got == {k.NOT_KOSHER}
    assert k.judge(got, "regular") == "fails"


def test_a_name_cut_by_its_chain_loses_its_last_word() -> None:
    # Rami Levy cuts names at 20 characters: a last word of a full-width name may be a fragment
    # ("כשרות" cut to "כשר"), so it is not read; a name of another length was not cut
    twenty = "חלב באריזה חדשה כשרה"
    assert len(twenty) == 20
    assert k.read_item_name(twenty, RAMI_LEVY) == frozenset()  # last word dropped
    assert k.read_item_name(twenty, KING_STORE) == {k.KOSHER}  # King Store does not cut
    longer = "חלב מהדרין באריזה כשרה"
    assert len(longer) > 20
    assert k.read_item_name(longer, RAMI_LEVY) == {k.MEHADRIN, k.KOSHER}
    # a word with a digit is kept: a size is not cut mid-word
    assert k.read_item_name("חלב מהדרין 1 ליטר 3%", RAMI_LEVY) == {k.MEHADRIN}


# --- render --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        'מצות כשר לפסח בד"ץ',
        'גבינה בד"ץ העדה החרדית חלבי',
        "חלב מהדרין",
        "חלב רבנות מהדרין",
        "עוגיות הרב לנדא פרווה",
        "חלב כשר",
        "חלב לא כשר לפסח",
        "חלב לא כשר",
    ],
)
def test_render_is_read_back_as_the_same_marks(text) -> None:
    m = k.read_marks(text)
    shown = k.render(m)
    assert shown is not None
    back = k.read_marks(shown)
    assert (back & set(k.MARKS)) >= m - {k.KOSHER, k.RABBANUT}  # implied marks are not repeated
    assert k.judge(back, "badatz") == k.judge(m, "badatz")
    assert k.judge(back, "regular") == k.judge(m, "regular")


def test_render_examples() -> None:
    assert k.render(k.read_marks('מצות כשר לפסח בד"ץ')) == 'בד"ץ, כשר לפסח'
    assert k.render(k.read_marks("שום")) is None
    assert k.render(k.read_marks("בד״ץ העדה החרדית מהדרין")) == 'בד"ץ העדה החרדית, מהדרין'


# --- judging -------------------------------------------------------------------------------------------

BADATZ_EIDA = {k.BADATZ, k.BADATZ_EIDA}
BADATZ_BY = {k.BADATZ, k.BADATZ_BEIT_YOSEF}


@pytest.mark.parametrize(
    ("level", "stated", "verdict"),
    [
        # nothing stated: unknown at every level, never "meets" and never "fails"
        *[(level, set(), "unknown") for level in k.LEVELS],
        # regular: any stated supervision
        ("regular", {k.KOSHER}, "meets"),
        ("regular", {k.MEHADRIN}, "meets"),
        ("regular", {k.BADATZ}, "meets"),
        ("regular", {k.LANDAU}, "meets"),
        ("regular", {k.RABBANUT}, "meets"),
        ("regular", {k.PASSOVER}, "unknown"),  # a Passover mark is its own axis
        ("regular", {k.DAIRY}, "unknown"),  # dairy is not a supervision
        # mehadrin: mehadrin, or a beit din hechsher; a plain "kosher" does not decide it
        ("mehadrin", {k.MEHADRIN}, "meets"),
        ("mehadrin", {k.RABBANUT_MEHADRIN, k.MEHADRIN}, "meets"),
        ("mehadrin", {k.BADATZ}, "meets"),
        ("mehadrin", BADATZ_EIDA, "meets"),
        ("mehadrin", {k.KOSHER}, "unknown"),
        ("mehadrin", {k.RABBANUT}, "unknown"),
        ("mehadrin", {k.LANDAU}, "unknown"),
        # badatz: a beit din hechsher, any
        ("badatz", {k.BADATZ}, "meets"),
        ("badatz", BADATZ_BY, "meets"),
        ("badatz", {k.MEHADRIN}, "unknown"),
        ("badatz", {k.KOSHER}, "unknown"),
        ("badatz", {k.LANDAU}, "unknown"),
        # a named hechsher: that one meets, a different named one fails, the rest is unknown
        (k.BADATZ_EIDA, BADATZ_EIDA, "meets"),
        (k.BADATZ_EIDA, BADATZ_BY, "fails"),
        (k.BADATZ_EIDA, {k.BADATZ}, "unknown"),
        (k.BADATZ_EIDA, {k.MEHADRIN}, "unknown"),
        (k.BADATZ_EIDA, {k.LANDAU}, "fails"),
        (
            k.BADATZ_EIDA,
            BADATZ_EIDA | BADATZ_BY,
            "meets",
        ),  # both stated: the one asked for is there
        (k.BADATZ_BEIT_YOSEF, BADATZ_BY, "meets"),
        (k.BADATZ_CHATAM_SOFER, {k.BADATZ, k.BADATZ_CHATAM_SOFER}, "meets"),
        (k.BADATZ_AGUDAT, {k.BADATZ, k.BADATZ_AGUDAT}, "meets"),
        (k.LANDAU, {k.LANDAU}, "meets"),
        (k.LANDAU, BADATZ_EIDA, "fails"),
        (k.RABBANUT_MEHADRIN, {k.RABBANUT_MEHADRIN, k.MEHADRIN, k.RABBANUT}, "meets"),
        (k.RABBANUT_MEHADRIN, {k.MEHADRIN}, "unknown"),
        (k.RABBANUT_MEHADRIN, BADATZ_EIDA, "fails"),
        # stated not kosher: fails everything
        *[(level, {k.NOT_KOSHER}, "fails") for level in k.LEVELS],
    ],
)
def test_judge(level, stated, verdict) -> None:
    assert k.judge(stated, level) == verdict


def test_no_level_always_meets_and_an_unknown_level_is_an_error() -> None:
    assert k.judge(set(), None) == "meets"
    with pytest.raises(ValueError):
        k.judge(set(), "super")


def test_judge_passover() -> None:
    assert k.judge_passover({k.PASSOVER}) == "meets"
    assert k.judge_passover(set()) == "unknown"
    assert (
        k.judge_passover({k.MEHADRIN}) == "unknown"
    )  # mehadrin year-round says nothing about Passover
    assert k.judge_passover({k.NOT_PASSOVER}) == "fails"
    assert k.judge_passover({k.NOT_KOSHER}) == "fails"


# --- the rule extractor --------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rx() -> RuleExtractor:
    return RuleExtractor()


def extract(rx: RuleExtractor, name: str, chain: str) -> Attributes:
    row = {"raw_name": name, "item_code": "7290000000000", "chain_id": chain}
    out = rx.extract([normalize(row, item_id=1)])[0]
    assert isinstance(out, Attributes)
    return out


def test_the_rule_extractor_writes_the_stated_marks_unverified(rx) -> None:
    got = extract(rx, 'בד"צ טורינו חלב חמישייה 23X5ג 115ג', TIV_TAAM)
    assert got.kosher == 'בד"ץ'
    assert got.verified_keys == ()
    assert extract(rx, "דנונה מהדרין טבעי 3%", MEGA).kosher == "מהדרין"
    assert extract(rx, "גבינה העדה החרדית 250 גרם", KING_STORE).kosher == 'בד"ץ העדה החרדית'


def test_the_rule_extractor_states_nothing_for_a_brand(rx) -> None:
    assert extract(rx, "חלב תנובה 3% 1 ליטר", KING_STORE).kosher is None
    assert extract(rx, "גבינה לבנה טרה 5% 250 גרם", KING_STORE).kosher is None


def test_a_cut_last_word_is_not_read_by_the_extractor(rx) -> None:
    assert extract(rx, "חלב באריזה חדשה כשרה", RAMI_LEVY).kosher is None
    assert extract(rx, "חלב באריזה חדשה כשרה", KING_STORE).kosher == "כשר"


# --- how much of the real catalog states anything --------------------------------------------------------


@pytest.fixture(scope="module")
def real_items():
    found = {}
    for folder in (FIXTURES_DIR, AUDIT_SNAPSHOT_DIR):
        for it in load_real_items(folder):
            found.setdefault((it.chain_id, it.raw_name), it)
    if not found:
        pytest.skip("real fixtures not present")
    return list(found)


def test_what_the_real_items_state(real_items) -> None:
    """A measurement kept as a test: 200 items per chain from seven chains, two days in October 2026
    (no Passover on the shelf). Under one percent state a certification; the filter has to work with
    "unknown" for almost everything, which is why unknown is shown, labelled, and not hidden."""
    states = {key: k.read_item_name(key[1], key[0]) for key in real_items}
    stated = {key: m for key, m in states.items() if m}
    certified = {key: m for key, m in stated.items() if m & k.SUPERVISED}
    assert len(real_items) >= 1500
    assert len(stated) == 13
    assert len(certified) == 9
    assert sum(1 for m in certified.values() if k.MEHADRIN in m) == 6
    assert sum(1 for m in certified.values() if k.BADATZ in m) == 2
    assert sum(1 for m in certified.values() if k.KOSHER in m) == 1
    assert not any(k.PASSOVER in m for m in stated.values())
    assert len(certified) / len(real_items) < 0.01
    # no real name states a named hechsher or "not kosher": no item is ever ruled out by a real name
    assert not any(m & (k.SPECIFIC | {k.NOT_KOSHER}) for m in stated.values())
