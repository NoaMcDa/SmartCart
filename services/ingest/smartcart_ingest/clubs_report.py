"""Which ClubID texts the loaded promotions carry, and which of them nobody can match yet.

``smartcart-ingest clubs-report`` lists, per chain, every distinct ClubID text of the club-only
promotions in the database with the rule it resolves to (``adapters/clubs.py``) and the number of
promotions. A text whose rule contains an unknown name is the owner's to-do list: add the exact name
to a club of ``adapters/chain_clubs.json`` (or a new club) once its meaning is known. Until then it
matches nobody, which is the safe side.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from smartcart_ingest.adapters import clubs as cl
from smartcart_ingest.adapters._common import resolve_clubs

_SQL = """
SELECT p.chain_id, v.text, count(*)
FROM promos AS p
CROSS JOIN LATERAL jsonb_array_elements_text(COALESCE(p.raw -> 'club_ids', '[]'::jsonb)) AS v(text)
WHERE p.club_only
GROUP BY p.chain_id, v.text
ORDER BY p.chain_id, count(*) DESC, v.text
"""


@dataclass(frozen=True)
class ClubText:
    chain_id: str
    text: str
    promos: int
    rule: str
    unmapped: tuple[str, ...]  # names in the text that are in no club of the chain's table


def unmapped_names(chain_id: str, text: str) -> tuple[str, ...]:
    """The club names of a ClubID text that the chain's table does not know."""
    defs = cl.chain_clubs_for(chain_id)
    known = defs.by_text() if defs else {}
    names = cl.value_names(text, chain_id)
    out: list[str] = []
    for name in names:
        if cl.norm_text(name) not in known and name not in out:
            out.append(name)
    return tuple(out)


def club_texts(conn: psycopg.Connection) -> list[ClubText]:
    rows: list[ClubText] = []
    for chain_id, text, n in conn.execute(_SQL).fetchall():
        _only, rule, _expr = resolve_clubs([text], chain_id)
        rows.append(ClubText(chain_id, text, n, rule or "", unmapped_names(chain_id, text)))
    return rows
