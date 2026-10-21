"""``smartcart-catalog promo-cycles --club ...`` judges club-only promos with the same rule
evaluation as the API (``smartcart_ingest.adapters.membership.club_member`` and the per-chain club
table ``chain_clubs.json``), on stored rule strings as the ingest writes them (``A | B``,
``A & B``, brackets, the unknown marker). Before, the CLI compared the whole stored text with the
names given, so any rule with an operator matched nobody and a club id (``ramilevy:club``) matched
nothing.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from smartcart_catalog import cli
from smartcart_catalog import promo_cycles as pc
from smartcart_ingest.adapters.membership import club_member

TODAY = date(2026, 10, 20)
RAMI = ("7290058140886", "רמי לוי")
MEGA = ("7290055700007", "קרפור (מגה)")
TIV = ("7290873255550", "טיב טעם")

BOTH = "(מועדון רמי לוי | מועדון לקוחות אשראי) & (ישראכרט מגנטי | תווי זיכוי מימוש)"
EITHER = "מועדון קרפור אשראי | מועדון אפליקציה"


def _seed(db, chain: tuple[str, str], rule: str | None) -> int:
    """One canonical sold by ``chain`` with a six-cycle club-only promo restricted to ``rule``."""
    db.execute(
        "INSERT INTO taxonomy (id, parent_id, level, name_he) VALUES ('pcc', NULL, 1, 'בדיקה')"
    )
    db.execute(
        "INSERT INTO product_type_rules (product_type, critical_keys, soft_keys)"
        " VALUES ('pcc_coffee', '{}', '{}')"
    )
    cid = db.execute(
        "INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type,"
        " base_unit) VALUES ('pcc', 'pcc-coffee', 'קפה נמס', 'pcc_coffee', '100g') RETURNING id"
    ).fetchone()[0]
    db.execute(
        "INSERT INTO chains (id, name, portal, club_names) VALUES (%s, %s, 'other', '{}')"
        " ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, club_names = '{}'",
        chain,
    )
    iid = db.execute(
        "INSERT INTO items (chain_id, item_code, raw_name) VALUES (%s, 'c1', 'קפה') RETURNING id",
        (chain[0],),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source,"
        " needs_review) VALUES (%s, %s, 'any_brand', 0.95, 'rule', false)",
        (iid, cid),
    )
    first = TODAY - timedelta(days=35 * 5 + 10)
    windows = [
        pc.Window(first + timedelta(days=35 * n), first + timedelta(days=35 * n + 6))
        for n in range(6)
    ]
    pc.seed_promo_history(
        db, chain[0], [iid], windows, club_only=True, club_name=rule, prefix="CLUB"
    )
    return cid


@pytest.fixture
def run(db, monkeypatch):
    @contextmanager
    def same_connection(settings):
        yield db

    monkeypatch.setattr(cli, "open_connection", same_connection)

    def invoke(*clubs: str) -> list[str]:
        args = ["promo-cycles", "pcc-coffee", "--as-of", TODAY.isoformat(), "--json"]
        for club in clubs:
            args += ["--club", club]
        result = CliRunner().invoke(cli.app, args)
        assert result.exit_code == 0, result.output
        return [c["chain_id"] for c in json.loads(result.output)["chains"]]

    return invoke


CASES = [
    # (chain, stored rule, clubs given, does the chain's history show)
    (RAMI, BOTH, [], False),
    (RAMI, BOTH, ["ramilevy:club"], False),  # one half of an "&" is not enough
    (RAMI, BOTH, ["ramilevy:club", "ramilevy:vouchers"], True),  # by club id, as the profile stores
    (RAMI, BOTH, ["ramilevy:credit", "ramilevy:isracard"], True),  # the other alternatives
    (RAMI, BOTH, ["מועדון רמי לוי", "תווי זיכוי מימוש"], True),  # by label
    (RAMI, BOTH, ["  מועדון   רמי לוי ", "תווי זיכוי מימוש"], True),  # spaces and case are ignored
    (
        RAMI,
        BOTH,
        ["ramilevy:wallet", "ramilevy:topup"],
        False,
    ),  # clubs of the chain, not in the rule
    (MEGA, EITHER, ["mega:app"], True),
    (MEGA, EITHER, ["mega:credit"], True),
    (MEGA, EITHER, ["ramilevy:club"], False),  # another chain's club
    (
        TIV,
        EITHER,
        ["mega:app"],
        False,
    ),  # a rule of Mega's clubs on Tiv Taam: not that chain's table
    (RAMI, "מועדון רמי לוי", ["ramilevy:club"], True),  # a plain name still works, by id
    (RAMI, "מועדון רמי לוי", ["מועדון רמי לוי"], True),  # and by exact label, as before
    (RAMI, "אחר", ["אחר", "ramilevy:club"], False),  # unknown matches nobody
    (RAMI, "(אחר) & מועדון רמי לוי", ["ramilevy:club", "אחר"], False),
    (RAMI, "אחר | מועדון רמי לוי", ["ramilevy:club"], True),
    (RAMI, "(A", ["ramilevy:club", "אחר"], False),  # a rule that does not parse is one unknown name
]


@pytest.mark.db
@pytest.mark.parametrize(("chain", "rule", "clubs", "shows"), CASES)
def test_the_cli_evaluates_stored_club_rules_like_the_api(
    db, run, chain, rule, clubs, shows
) -> None:
    _seed(db, chain, rule)
    assert run(*clubs) == ([chain[0]] if shows else [])


def test_the_cli_and_the_api_agree_on_every_case() -> None:
    """The expectations above are what the shared ``club_member`` says on the chain's own table
    (so a change to the rule evaluation has to change both on purpose)."""
    from smartcart_ingest.adapters.membership import chain_club_names

    for chain, rule, clubs, shows in CASES:
        names = chain_club_names(chain[0], [])
        assert club_member(rule, clubs, chain[1], names) is shows, (chain, rule, clubs)


@pytest.mark.db
def test_without_a_club_the_club_promos_stay_out(db, run) -> None:
    _seed(db, RAMI, "מועדון רמי לוי")
    assert run() == []
    assert run("", "  ") == []
