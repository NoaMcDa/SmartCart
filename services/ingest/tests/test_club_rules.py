"""Club promotions reach the people who are members (docs/adapters.md, "Club promotions").

The ClubID values below are the real ones of the transparency files the Portal probe fetched on
2026-10-21 (``fixtures/<chain>/real/PromoFull*``, read here through the adapters), plus the two
expressions the probe's full-file profile listed for Mega and Shufersal that the trimmed fixtures
do not contain. What is checked:

* a member of a club gets the promos that name it, a non-member never does;
* ``0 - כלל הלקוחות`` is everyone (not a club promo at all);
* ``A | B`` is satisfied by either side, ``(A | B) & (C | D)`` needs one of each;
* a text that is not in ``chain_clubs.json`` matches nobody, and a chain that has no club table
  (Shufersal) can never match, whatever the text says.
"""

from __future__ import annotations

import pytest

from smartcart_ingest.adapters import clubs as cl
from smartcart_ingest.adapters._common import resolve_clubs
from tests.test_adapters import FIXTURES, chain_adapters, parse_fixture

KING, RAMI, MEGA = "7290058108879", "7290058140886", "7290055700007"
TIV, YOH, SHUFERSAL = "7290873255550", "7290803800003", "7290027600007"

KING_18 = (
    '("לקוחות הקפה=3" | "מועדון לקוחות=3" | "HEBREW=3" | "ARABIC=3" | "לקוחות אתר קניות=3" | '
    '"מיתר=3" | "לקוחות סיטונאים=3" | "עובדי קינגסטור -ARABIC=3" | "עובדי קינגסטור -HEBREW=3" | '
    '"טסט הנחות=3" | "לקוח גדול=3" | "עובדי סוא=3" | "בעלים=3" | "לקוחות רכבים=3" | '
    """"ואדי אלג'וז CASHBACK=3" | "לקוחות פרידיס=3" | "לקוחות הקפה שוברים=3" | """
    '"עמותת אפדל אלעולום=3")'
)
KING_WHOLESALE = '("לקוחות סיטונאים=3" | "לקוחות סיטונאים סניפים=3")'
RAMI_AND = (
    "((1=מועדון שיווק   השקמה|1=מועדון לקוחות אשראי))"
    "&(3=ישראכרט מגנטי|3=תווי זיכוי מימוש|3=עיגול אגורות)"
)
RAMI_OR = (
    "(1=מועדון חברתי|1=מועדון שיווק   השקמה|1=מועדון לקוחות אשראי|1=מועדון נטען|1=לקוחות ארנק)"
)
MEGA_OR = "(2=מועדון קרפור אשראי|2=מועדון אפליקציה)"
EVERYONE = ("0", "0 - כלל הלקוחות")


def rule(chain: str, *values: str) -> str | None:
    club_only, name, _ = resolve_clubs(list(values), chain)
    return name if club_only else None


def member(chain: str, held_ids: list[str], name: str | None) -> bool:
    """Whether someone who holds the clubs ``held_ids`` gets a promo whose club_name is ``name``."""
    defs = cl.chain_clubs_for(chain)
    labels = {cl.norm_text(c.label) for c in defs.clubs if c.id in held_ids} if defs else set()
    return cl.satisfied(name, lambda n: cl.norm_text(n) in labels)


# --------------------------------------------------------------------------- the data file


def test_the_club_table_is_sound() -> None:
    assert cl.validate_chain_clubs() == []


def test_the_club_table_names_adapter_chains() -> None:
    adapters = {a.chain_id: a for a in (cls() for cls in chain_adapters().values())}
    for chain_id, defs in cl.load_chain_clubs().items():
        assert chain_id in adapters, chain_id
        assert defs.slug == adapters[chain_id].slug
        assert defs.name == adapters[chain_id].display_name


def test_every_text_of_a_real_file_is_known_or_deliberately_not() -> None:
    """The ClubID texts of the committed real files resolve to a club, except the ones that are
    not a club a person can be in (listed: unknown means nobody matches)."""
    unmapped: dict[str, set[str]] = {}
    for slug, cls in chain_adapters().items():
        for path in (FIXTURES / slug / "real").glob("PromoFull*"):
            parsed = parse_fixture(cls(), path)
            defs = cl.chain_clubs_for(cls.chain_id)
            known = defs.by_text() if defs else {}
            for promo in parsed.promos:
                for value in promo.raw["club_ids"]:
                    club = resolve_clubs([value], cls.chain_id)
                    if club[0]:
                        assert cl.parse_rule(club[1]) is not None, value
                    if not club[0]:
                        continue
                    for atom in cl.rule_atoms(cl.parse_rule(club[1])):
                        if cl.norm_text(atom) not in known:
                            unmapped.setdefault(slug, set()).add(atom)
    assert unmapped == {}, unmapped


# --------------------------------------------------------------------------- resolving texts


def test_zero_is_everyone() -> None:
    for chain in (SHUFERSAL, TIV, YOH, MEGA, None):
        for value in EVERYONE:
            assert resolve_clubs([value], chain) == (False, None, None)
    assert resolve_clubs(["0", "0 - כלל הלקוחות"], TIV) == (False, None, None)


def test_a_named_club_is_its_label() -> None:
    assert rule(TIV, "1 - המועדון החדש") == "המועדון החדש"
    assert rule(YOH, "1 - מועדון עובדים") == "מועדון עובדים"
    assert member(TIV, ["tivtaam:new"], rule(TIV, "1 - המועדון החדש"))
    assert not member(TIV, [], rule(TIV, "1 - המועדון החדש"))
    assert not member(TIV, ["yohananof:staff"], rule(TIV, "1 - המועדון החדש"))


def test_an_expression_is_satisfied_by_either_side() -> None:
    name = rule(MEGA, MEGA_OR)
    assert name == "מועדון קרפור אשראי | מועדון אפליקציה"
    assert member(MEGA, ["mega:credit"], name)
    assert member(MEGA, ["mega:app"], name)
    assert member(MEGA, ["mega:app", "mega:credit"], name)
    assert not member(MEGA, [], name)
    assert not member(MEGA, ["tivtaam:new", "ramilevy:club"], name)
    big = rule(RAMI, RAMI_OR)
    for club in ("social", "club", "credit", "topup", "wallet"):
        assert member(RAMI, [f"ramilevy:{club}"], big), club
    assert not member(RAMI, ["ramilevy:isracard", "ramilevy:vouchers"], big)


def test_an_and_between_groups_needs_one_of_each() -> None:
    name = rule(RAMI, RAMI_AND)
    # "עיגול אגורות" is not a club a person can hold, so it drops out of the alternatives.
    assert name == "(מועדון רמי לוי | מועדון לקוחות אשראי) & (ישראכרט מגנטי | תווי זיכוי מימוש)"
    assert not member(RAMI, ["ramilevy:club"], name)
    assert not member(RAMI, ["ramilevy:isracard"], name)
    assert not member(RAMI, ["ramilevy:club", "ramilevy:social"], name)
    assert member(RAMI, ["ramilevy:club", "ramilevy:isracard"], name)
    assert member(RAMI, ["ramilevy:credit", "ramilevy:vouchers"], name)


def test_king_store_keeps_the_customer_groups_that_are_clubs() -> None:
    name = rule(KING, KING_18)
    assert name == "מועדון לקוחות | לקוחות סיטונאים | עובדי קינגסטור"
    assert member(KING, ["king_store:club"], name)
    assert member(KING, ["king_store:wholesale"], name)
    assert member(KING, ["king_store:staff"], name)
    assert not member(KING, [], name)
    assert rule(KING, KING_WHOLESALE) == "לקוחות סיטונאים"
    assert not member(KING, ["king_store:club"], rule(KING, KING_WHOLESALE))
    assert member(KING, ["king_store:wholesale"], rule(KING, KING_WHOLESALE))


def test_spaces_and_case_are_not_part_of_a_club_name() -> None:
    assert rule(RAMI, "(1=מועדון שיווק השקמה)") == rule(RAMI, "(1=מועדון   שיווק   השקמה)")
    assert rule(RAMI, "(1=מועדון שיווק השקמה)") == "מועדון רמי לוי"
    assert rule(KING, '("עובדי קינגסטור -arabic=3")') == "עובדי קינגסטור"


# --------------------------------------------------------------------------- unknown matches nobody


def test_an_unknown_text_matches_nobody() -> None:
    every_club = {c.id for defs in cl.load_chain_clubs().values() for c in defs.clubs}
    for chain, value in (
        (TIV, "1 - מועדון שלא קיים"),
        (TIV, "2 - המועדון החדש "),  # a known name under another code is still that club
        (YOH, "3 - כרטיס לא ידוע"),
        (SHUFERSAL, "3 - כרטיס אשראי א&כרטיס אשראי ב"),
        (SHUFERSAL, "1 - מועדון שופרסל"),
        (KING, '("טסט הנחות=3" | "לקוח גדול=3")'),
        (RAMI, "((1=מועדון לא מוכר))&(3=ישראכרט מגנטי)"),
        (MEGA, "(2=אחד|2=שניים)"),
    ):
        name = rule(chain, value)
        if chain == TIV and value.startswith("2 - "):
            assert name == "המועדון החדש"
            continue
        assert name is not None
        assert not member(chain, sorted(every_club), name), (chain, value, name)


def test_an_unknown_and_group_makes_the_whole_rule_unknown() -> None:
    # One group of the AND names only texts the table does not know: nobody satisfies it, even
    # someone who holds every club of the other group.
    name = rule(RAMI, "((1=מועדון שיווק השקמה))&(3=תו שלא קיים)")
    assert name == cl.UNKNOWN_CLUB
    assert not member(RAMI, [c.id for c in cl.chain_clubs_for(RAMI).clubs], name)


def test_a_chain_without_a_club_table_never_matches() -> None:
    assert cl.chain_clubs_for(SHUFERSAL) is None
    for value in ("3 - ויזה", "1 - מועדון שופרסל יורס", MEGA_OR, RAMI_AND):
        name = rule(SHUFERSAL, value)
        assert not member(SHUFERSAL, ["tivtaam:new", "mega:app", "ramilevy:club"], name)
        if name == cl.UNKNOWN_CLUB:
            assert not cl.satisfied(name, lambda n: True)  # not even for "everything held"


def test_a_label_that_looks_like_an_expression_stays_one_name() -> None:
    assert rule(SHUFERSAL, "3 - A | B") == cl.UNKNOWN_CLUB
    assert rule(TIV, "3 - א&ב") == cl.UNKNOWN_CLUB


def test_garbage_is_unknown_not_an_error() -> None:
    for value in ("((1=א)", "(1=א))", '"1=א', "(|)", "()&"):
        assert rule(RAMI, value) == cl.UNKNOWN_CLUB, value
    assert not cl.satisfied("", lambda n: True) and not cl.satisfied(None, lambda n: True)
    assert not cl.satisfied("(A", lambda n: True)


def test_several_club_values_must_all_hold() -> None:
    name = rule(RAMI, "1 - מועדון חברתי", "1 - מועדון נטען")
    assert name == "מועדון חברתי & מועדון נטען"
    assert not member(RAMI, ["ramilevy:social"], name)
    assert member(RAMI, ["ramilevy:social", "ramilevy:topup"], name)
    # a bare code is the older layout's fallback name, unchanged
    assert resolve_clubs(["1"], TIV) == (True, "מועדון לקוחות", None)


# --------------------------------------------------------------------------- the real files


def _club_promos(slug: str):
    cls = chain_adapters()[slug]
    path = next((FIXTURES / slug / "real").glob("PromoFull*"))
    return cls.chain_id, [p for p in parse_fixture(cls(), path).promos]


@pytest.mark.parametrize(
    ("slug", "held", "gets", "club_only_total"),
    [
        ("tivtaam", ["tivtaam:new"], 59, 59),
        ("yohananof", ["yohananof:staff"], 2, 2),
        ("king_store", ["king_store:club"], 18, 21),
        ("king_store", ["king_store:wholesale"], 21, 21),
        ("ramilevy", ["ramilevy:social"], 1, 2),
        ("ramilevy", ["ramilevy:club", "ramilevy:isracard"], 2, 2),
    ],
)
def test_members_get_the_real_club_promos_and_non_members_none(
    slug: str, held: list[str], gets: int, club_only_total: int
) -> None:
    chain, promos = _club_promos(slug)
    club = [p for p in promos if p.club_only]
    assert len(club) == club_only_total
    assert sum(member(chain, held, p.club_name) for p in club) == gets
    assert not any(member(chain, [], p.club_name) for p in club)
    others = [c for c in cl.load_chain_clubs() if c != chain]
    other_ids = [c.id for o in others for c in cl.chain_clubs_for(o).clubs]
    assert not any(member(chain, other_ids, p.club_name) for p in club)
    # the promos of "everyone" are not club promos at all
    assert all(not p.club_only for p in promos if p.raw["club_ids"] in (["0"], ["0 - כלל הלקוחות"]))


@pytest.mark.parametrize("slug", ["shufersal", "osherad", "mega"])
def test_chains_whose_real_files_hold_only_everyone_have_no_club_promo(slug: str) -> None:
    _chain, promos = _club_promos(slug)
    assert promos and not any(p.club_only for p in promos)


# --------------------------------------------------------------------------- the report


@pytest.mark.db
def test_the_club_report_lists_the_texts_nobody_matches_yet(db, monkeypatch) -> None:
    from contextlib import contextmanager

    from typer.testing import CliRunner

    from smartcart_ingest import cli
    from smartcart_ingest.clubs_report import club_texts

    for chain in (TIV, SHUFERSAL):
        db.execute("INSERT INTO chains (id, name, portal) VALUES (%s, %s, 'other')", (chain, chain))
    for n, (chain, text) in enumerate(
        [
            (TIV, "1 - המועדון החדש"),
            (TIV, "1 - המועדון החדש"),
            (SHUFERSAL, "3 - ויזה כאל"),
            (TIV, "(2=המועדון החדש|2=מועדון חדש לגמרי)"),
        ]
    ):
        club_only, name, _ = resolve_clubs([text], chain)
        db.execute(
            "INSERT INTO promos (chain_id, promo_id, description, club_only, club_name, raw)"
            " VALUES (%s, %s, 'x', %s, %s, %s::jsonb)",
            (chain, f"p{n}", club_only, name, f'{{"club_ids": ["{text}"]}}'),
        )
    rows = {(r.chain_id, r.text): r for r in club_texts(db)}
    assert rows[(TIV, "1 - המועדון החדש")].promos == 2
    assert rows[(TIV, "1 - המועדון החדש")].unmapped == ()
    assert rows[(SHUFERSAL, "3 - ויזה כאל")].unmapped == ("ויזה כאל",)
    assert rows[(TIV, "(2=המועדון החדש|2=מועדון חדש לגמרי)")].unmapped == ("מועדון חדש לגמרי",)

    @contextmanager
    def use_test_connection(settings):
        yield db

    monkeypatch.setattr(cli, "open_connection", use_test_connection)
    out = CliRunner().invoke(cli.app, ["clubs-report", "--unmapped"])
    assert out.exit_code == 0, out.output
    assert "ויזה כאל" in out.stdout and "מועדון חדש לגמרי" in out.stdout
    assert "1 - המועדון החדש" not in out.stdout
