"""Who gets a club-only promotion: ``club_member`` evaluates the rule stored in
``promos.club_name`` (``adapters/clubs.py``) against the clubs a person marked.

It lives here, next to the rule grammar and the per-chain club table (``chain_clubs.json``), and
not in the API, because the API (``/compare``, ``/optimize``, ``/barcode``, ``/promo-cycles``, the
alert job) and the catalog CLI (``smartcart-catalog promo-cycles``) must decide membership the same
way; ``smartcart_api.basket`` re-exports these names. ``club_filter`` builds the
``include_club`` callback the promo cycle code takes from the clubs a person marked.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence

import psycopg

from smartcart_ingest.adapters import clubs as clubrules

# --- clubs (issue #19) -------------------------------------------------------------------------

# The adapters name regulation club code 1 "מועדון לקוחות" (the chain's own customer club), 2
# "כרטיס אשראי" and 3 "אחר", and an unknown code "club <n>" (docs/adapters.md, unverified).
CHAIN_OWN_CLUB = "מועדון לקוחות"
_UNPARSEABLE = {"", "אחר", "other"}
_UNKNOWN_CODE = re.compile(r"^club \d+$")


def norm_club(name: str | None) -> str:
    """Trimmed, inner whitespace collapsed, case-folded."""
    return " ".join((name or "").split()).casefold()


class ChainClubNames(list):
    """A chain's ``chains.club_names`` plus its club table: ``ids`` maps a club id the profile
    stores (``ramilevy:club``, lower-cased) to the label a promo's ``club_name`` uses. It is a
    ``list`` of the legacy names so code that only iterates them keeps working."""

    def __init__(self, names: Iterable[str] = (), ids: dict[str, str] | None = None) -> None:
        super().__init__(names)
        self.ids: dict[str, str] = dict(ids or {})


def chain_club_names(chain_id: str, names: Iterable[str] | None = None) -> ChainClubNames:
    """The legacy ``chains.club_names`` of a chain plus the ids of its club table."""
    defs = clubrules.chain_clubs_for(chain_id)
    return ChainClubNames(
        names or [], {c.id.casefold(): c.label for c in defs.clubs} if defs else {}
    )


def club_member(
    club_name: str | None,
    clubs: Iterable[str],
    chain_name: str | None = None,
    chain_club_names: Iterable[str] = (),
) -> bool:
    """Whether a user who marked ``clubs`` gets a club-only promo restricted to ``club_name``.

    ``club_name`` is a rule written by the ingest (``adapters/clubs.py``): a club label, or labels
    joined by ``|`` (any of) and ``&`` (all of) with brackets, e.g. ``(A | B) & C``. The rule is
    evaluated as written; each name in it is checked as below. A name without operators (and a
    text that is not a well-formed rule) is a single name.

    * The name equals one of ``clubs`` (case-insensitive, trimmed, spaces collapsed), or is the
      label of a club of this chain's table whose id (``ramilevy:club``) is in ``clubs``. Credit
      and payment card clubs are clubs of the table too.
    * The chain's own customer club (``CHAIN_OWN_CLUB``, or a name listed in the chain's
      ``chains.club_names``) also matches when the user marked the chain itself (its name, or
      "מועדון <chain name>"): the rule of the first picker, kept for profiles saved before the
      per-chain club list.
    * A restriction that could not be parsed (no name, "אחר", "club <n>") never matches: the
      promo stays restricted (safe default).
    """
    if not (club_name or "").strip():
        return False
    marked = {norm_club(c) for c in clubs} - {""}
    ids: dict[str, str] = getattr(chain_club_names, "ids", None) or {}
    for club_id, label in ids.items():
        if club_id in marked:
            marked.add(norm_club(label))
    chain = norm_club(chain_name)
    own = {norm_club(CHAIN_OWN_CLUB), *(norm_club(n) for n in chain_club_names)}

    def holds(name: str) -> bool:
        want = norm_club(name)
        if want in _UNPARSEABLE or _UNKNOWN_CODE.match(want):
            return False
        if want in marked:
            return True
        if chain and want in own:
            return any(
                m == chain or m == f"{norm_club('מועדון')} {chain}" or chain.startswith(f"{m} ")
                for m in marked
            )
        return False

    node = clubrules.parse_rule(club_name or "")
    if node is None:
        return holds(club_name or "")
    return clubrules.evaluate(node, holds)


def chain_clubs(
    conn: psycopg.Connection, chain_ids: Iterable[str]
) -> dict[str, tuple[str, ChainClubNames]]:
    """chain_id -> (chain name, club names and club ids) for ``club_member``."""
    out: dict[str, tuple[str, ChainClubNames]] = {}
    for chain_id, name, club_names in conn.execute(
        "SELECT id, name, club_names FROM chains WHERE id = ANY(%s)", (sorted(set(chain_ids)),)
    ).fetchall():
        out[chain_id] = (name, chain_club_names(chain_id, club_names))
    return out


def club_filter(
    conn: psycopg.Connection, clubs: Iterable[str]
) -> Callable[[str | None, str, Sequence[str]], bool]:
    """The ``include_club(club_name, chain_name, chain's club_names)`` callback of the promo cycle
    code for a person who marked ``clubs``: a club-only promo counts only when ``club_member``
    says they get it. Nobody marked anything: no club promo counts."""
    marked = [c for c in clubs if c.strip()]
    chain_ids = [r[0] for r in conn.execute("SELECT id FROM chains").fetchall()]
    ids_by_name = {name: names.ids for name, names in chain_clubs(conn, chain_ids).values()}

    def include(club_name: str | None, chain_name: str, own_clubs: Sequence[str]) -> bool:
        names = ChainClubNames(own_clubs, ids_by_name.get(chain_name))
        return bool(marked) and club_member(club_name, marked, chain_name, names)

    return include
