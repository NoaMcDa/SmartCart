"""What an item name states about its kashrut, and whether that meets a level a person chose.

The chains' transparency files have no kosher field. The only certification an item can have is the
one its own name prints ("מהדרין", 'בד"צ', "כשר לפסח"), so this module reads **explicit words only**
(precision over recall, ``docs/matching.md`` "Kosher"):

* a certification is never inferred from a brand, a manufacturer, a product type or a chain;
* a word that also means something else is not read ("חלק" is glatt meat and also "smooth" and "part",
  "מלח כשר" is a kind of salt, "פרווה" is also fur);
* a name a chain cut at a fixed width loses its last word, which may be a fragment
  (``read_item_name``), exactly as ``RuleExtractor.words_of`` does.

``read_marks`` turns text into a set of mark codes (``MARKS``); ``judge`` compares the marks with a
level and answers ``meets``, ``unknown`` (the name states nothing that decides it) or ``fails`` (the
name states something that rules it out). Nothing here reads a database; the API's filter
(``smartcart_api/kosher.py``) and the rule extractor both call it, so the two cannot disagree.

Levels are the person's choice (profile ``kosher_level``): ``regular`` (any stated supervision),
``mehadrin`` (a stated mehadrin, or a stated beit din hechsher), ``badatz`` (a stated beit din
hechsher, any), and one named hechsher. Whether a beit din hechsher satisfies "mehadrin" is a
product decision (**not verified**; to confirm with the kosher beta segment, ``docs/beta-plan.md``).
"""

from __future__ import annotations

import re
from typing import Literal

from smartcart_catalog.normalize import clean_name, is_full_width

Verdict = Literal["meets", "unknown", "fails"]

# --- marks -----------------------------------------------------------------------------------------

KOSHER = "kosher"
RABBANUT = "rabbanut"
MEHADRIN = "mehadrin"
RABBANUT_MEHADRIN = "rabbanut_mehadrin"
BADATZ = "badatz"
BADATZ_EIDA = "badatz_eida"
BADATZ_BEIT_YOSEF = "badatz_beit_yosef"
BADATZ_CHATAM_SOFER = "badatz_chatam_sofer"
BADATZ_AGUDAT = "badatz_agudat"
LANDAU = "landau"
PASSOVER = "passover"
NOT_KOSHER = "not_kosher"
NOT_PASSOVER = "not_passover"
DAIRY = "dairy"
MEAT = "meat"
PAREVE = "pareve"

# The text a mark is written as (the ``kosher`` attribute of an item), in the order it is written.
MARKS: dict[str, str] = {
    BADATZ_EIDA: 'בד"ץ העדה החרדית',
    BADATZ_BEIT_YOSEF: 'בד"ץ בית יוסף',
    BADATZ_CHATAM_SOFER: 'בד"ץ חתם סופר',
    BADATZ_AGUDAT: 'בד"ץ אגודת ישראל',
    BADATZ: 'בד"ץ',
    LANDAU: "הרב לנדא",
    RABBANUT_MEHADRIN: "רבנות מהדרין",
    MEHADRIN: "מהדרין",
    RABBANUT: "רבנות",
    KOSHER: "כשר",
    NOT_KOSHER: "לא כשר",
    PASSOVER: "כשר לפסח",
    NOT_PASSOVER: "לא כשר לפסח",
    DAIRY: "חלבי",
    MEAT: "בשרי",
    PAREVE: "פרווה",
}

NAMED_BADATZ = frozenset({BADATZ_EIDA, BADATZ_BEIT_YOSEF, BADATZ_CHATAM_SOFER, BADATZ_AGUDAT})
"""A named beit din hechsher; each also implies the generic ``badatz`` mark."""
SPECIFIC = NAMED_BADATZ | {LANDAU, RABBANUT_MEHADRIN}
"""Marks a person can ask for by name; a different one stated on an item rules it out."""
BADATZ_FAMILY = NAMED_BADATZ | {BADATZ}
SUPERVISED = BADATZ_FAMILY | {KOSHER, MEHADRIN, RABBANUT, RABBANUT_MEHADRIN, LANDAU}
"""Marks that state some kosher supervision."""
MEHADRIN_FAMILY = BADATZ_FAMILY | {MEHADRIN, RABBANUT_MEHADRIN}

# The levels a person can choose. ``None`` (no preference) is not a level.
LEVELS: tuple[str, ...] = (
    "regular",
    "mehadrin",
    "badatz",
    BADATZ_EIDA,
    BADATZ_BEIT_YOSEF,
    BADATZ_CHATAM_SOFER,
    BADATZ_AGUDAT,
    LANDAU,
    RABBANUT_MEHADRIN,
)

# --- reading ---------------------------------------------------------------------------------------

_L = "[א-תA-Za-z]"
_B = rf"(?<!{_L})"  # not inside a word, on the left
_E = rf"(?!{_L})"  # not inside a word, on the right
_BADATZ = r"בד[\"']?[צץ]"
# the words that introduce a hechsher's name: 'בד"ץ בית יוסף', "בהשגחת הרב לנדא", "מהדרין חתם סופר"
_CUE = rf"(?:{_BADATZ}|בית\s+דין|[בה]?השגחת|השגחה|כשרות|מהדרין)"
_OF = r"(?:של\s+)?(?:ה)?"


def _re(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


_PASSOVER_NO = _re(rf"{_B}(?:לא|אינו|אינה|ללא)\s+כשר(?:ה)?\s+לפסח{_E}")
_PASSOVER = _re(rf"{_B}כשר(?:ה)?\s+לפסח{_E}")
_NOT_KOSHER = _re(
    rf"{_B}(?:לא|אינו|אינה)\s+כשר(?:ה)?{_E}"
    rf"|{_B}ללא\s+(?:תעודת\s+)?(?:כשרות|השגחה){_E}"
    rf"|{_B}לא\s+מושגח(?:ת)?{_E}"
)
_KOSHER = _re(rf"{_B}כשר(?:ה)?{_E}")
_KOSHER_SALT = _re(rf"{_B}מלח{_E}")  # "מלח גס כשר" is kosher salt, a kind of salt
_MEHADRIN = _re(rf"{_B}[לה]?מהדרין{_E}")
_RABBANUT_MEHADRIN = _re(rf"{_B}רבנות\s+מהדרין{_E}|{_B}מהדרין\s+{_OF}רבנות{_E}")
_RABBANUT = _re(rf"{_B}ה?רבנות{_E}")
_BADATZ_RE = _re(rf"{_B}{_BADATZ}{_E}|{_B}בית\s+דין\s+צדק{_E}")
_EIDA = _re(rf"{_B}העדה\s+החרדית{_E}|{_B}עדה\s+חרדית{_E}|{_B}{_BADATZ}\s+העדה{_E}")
_BEIT_YOSEF = _re(rf"{_B}{_CUE}\s+{_OF}בית\s+יוסף{_E}")
_CHATAM_SOFER = _re(rf"{_B}{_CUE}\s+{_OF}חתם\s+סופר{_E}")
_AGUDAT = _re(rf"{_B}{_CUE}\s+{_OF}אגודת\s+ישראל{_E}")
_LANDAU = _re(rf"{_B}(?:הרב\s+|{_CUE}\s+{_OF}(?:הרב\s+)?)לנדאו?{_E}")
_DAIRY = _re(rf"{_B}חלבי(?:ת)?{_E}")
# "פרווה" is also fur: a notebook, a toy, a collar
_PAREVE = _re(rf"{_B}(?:פרווה|פרוה|פארווה){_E}")
_NOT_FOOD_FUR = _re(
    rf"{_B}(?:מחברת|בובה|בובת|צעצוע|כרית|מעיל|כובע|צעיף|כפפות|שטיח|צווארון|קישוט|נעלי)\S*"
)
# "בשרי" is the meat meal; "בשרית" is a fleshy tomato, and a fleshy pepper is "בשרי" too
_MEAT = _re(rf"{_B}בשרי{_E}")
_FLESHY = _re(rf"{_B}(?:עגבני|פלפל|מלפפון|חציל|בצל|פטריות|תפוח|אפרסק|אבוקדו|ענב)\S*\s+בשרי{_E}")


def _consume(pattern: re.Pattern[str], text: str) -> tuple[bool, str]:
    """Whether ``pattern`` is in ``text``, and ``text`` with every match blanked out."""
    found = pattern.search(text) is not None
    return found, pattern.sub(" ", text) if found else text


def read_marks(text: str | None) -> frozenset[str]:
    """The marks ``text`` states, from explicit words only. ``text`` is a name or an attribute
    value; quotes are unified here. An empty set means the text states nothing."""
    if not text:
        return frozenset()
    s = clean_name(text)
    marks: set[str] = set()

    no_pesach, s = _consume(_PASSOVER_NO, s)
    if no_pesach:
        marks.add(NOT_PASSOVER)
    pesach, s = _consume(_PASSOVER, s)
    if pesach:
        marks.add(PASSOVER)
    not_kosher, s = _consume(_NOT_KOSHER, s)
    if not_kosher:
        marks.add(NOT_KOSHER)

    rabbanut_mehadrin, s = _consume(_RABBANUT_MEHADRIN, s)
    if rabbanut_mehadrin:
        marks |= {RABBANUT_MEHADRIN, MEHADRIN, RABBANUT}
    for code, pattern in (
        (BADATZ_EIDA, _EIDA),
        (BADATZ_BEIT_YOSEF, _BEIT_YOSEF),
        (BADATZ_CHATAM_SOFER, _CHATAM_SOFER),
        (BADATZ_AGUDAT, _AGUDAT),
    ):
        if pattern.search(s):
            marks |= {code, BADATZ}
    if _LANDAU.search(s):
        marks.add(LANDAU)
    if _BADATZ_RE.search(s):
        marks.add(BADATZ)
    if _MEHADRIN.search(s):
        marks.add(MEHADRIN)
    if _RABBANUT.search(s):
        marks.add(RABBANUT)
    if _KOSHER.search(s) and not _KOSHER_SALT.search(s) and not not_kosher:
        marks.add(KOSHER)

    if _DAIRY.search(s):
        marks.add(DAIRY)
    if _PAREVE.search(s) and not _NOT_FOOD_FUR.search(s):
        marks.add(PAREVE)
    if _MEAT.search(s) and not _FLESHY.search(s):
        marks.add(MEAT)
    # a name that says it is not kosher states no supervision: the words around it were about
    # something else ("לא כשר" next to a certified brand is not read as both)
    if NOT_KOSHER in marks:
        marks -= SUPERVISED
    return frozenset(marks)


def read_item_name(raw_name: str | None, chain_id: str | None = None) -> frozenset[str]:
    """The marks an item's published name states. A chain that cuts names at a fixed width
    (``normalize.NAME_LIMITS``) leaves the last word of a full-width name as a possible fragment
    ("כשרות" cut to "כשר"), so that word is not read unless it carries a digit."""
    if not raw_name:
        return frozenset()
    name = clean_name(raw_name)
    if is_full_width(chain_id, raw_name):
        head, _, tail = name.rstrip().rpartition(" ")
        if head and not any(ch.isdigit() for ch in tail):
            name = head
    return read_marks(name)


def render(marks: frozenset[str] | set[str]) -> str | None:
    """The marks as the text of the ``kosher`` attribute, in the order of ``MARKS``; a generic
    mark a named one already implies is left out. ``read_marks(render(m))`` is ``m`` again for the
    marks a name can state (the ones ``render`` keeps)."""
    keep = set(marks)
    if keep & NAMED_BADATZ:
        keep.discard(BADATZ)
    if RABBANUT_MEHADRIN in keep:
        keep -= {MEHADRIN, RABBANUT}
    if keep & (SUPERVISED - {KOSHER}):
        keep.discard(KOSHER)  # "כשר" next to a named supervision adds nothing
    parts = [text for code, text in MARKS.items() if code in keep]
    return ", ".join(parts) if parts else None


# --- judging ---------------------------------------------------------------------------------------


def judge(marks: frozenset[str] | set[str], level: str | None) -> Verdict:
    """Whether an item with these stated ``marks`` meets ``level``.

    ``fails`` only when the name rules the level out: it says it is not kosher, or it states a
    different named hechsher than the one asked for. Stating less than the level needs (a plain
    "כשר" for a mehadrin shopper) is ``unknown``, never ``fails``: the name may be incomplete.
    No level (no preference) always ``meets``."""
    if level is None:
        return "meets"
    if NOT_KOSHER in marks:
        return "fails"
    if level == "regular":
        return "meets" if marks & SUPERVISED else "unknown"
    if level == "mehadrin":
        return "meets" if marks & MEHADRIN_FAMILY else "unknown"
    if level == "badatz":
        return "meets" if marks & BADATZ_FAMILY else "unknown"
    if level in SPECIFIC:
        if level in marks:
            return "meets"
        return "fails" if marks & (SPECIFIC - {level}) else "unknown"
    raise ValueError(f"unknown kosher level: {level!r}")


def judge_passover(marks: frozenset[str] | set[str]) -> Verdict:
    """Kosher for Passover: stated, stated not, or not stated."""
    if NOT_PASSOVER in marks or NOT_KOSHER in marks:
        return "fails"
    return "meets" if PASSOVER in marks else "unknown"
