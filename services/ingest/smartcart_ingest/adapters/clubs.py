"""Which clubs a promotion needs, and which of them a person is a member of (docs/adapters.md,
"Club promotions").

The transparency files carry ``ClubID`` as free text: ``0 - כלל הלקוחות`` (everyone),
``1 - המועדון החדש`` (code, dash, name), or a boolean expression over club names such as
``((1=מועדון שיווק   השקמה|1=מועדון לקוחות אשראי))&(3=ישראכרט מגנטי|3=תווי זיכוי מימוש)``. This
module turns that text into a **rule over club labels** that is stored in ``promos.club_name`` and
read back by the API:

* ``chain_clubs.json`` lists, per chain, the clubs a person can pick (a stable id such as
  ``ramilevy:club``, a Hebrew label, a kind) and the exact ClubID texts that mean each one.
* A text that is not listed is *unknown* and matches nobody (precision over recall). An unknown
  alternative of an ``|`` is dropped (it could never be true), an unknown part of an ``&`` makes the
  whole rule unknown, and a rule that is entirely unknown is stored as :data:`UNKNOWN_CLUB`
  (``אחר``) or, when it is one plain name, as that name.
* The rule is written with the labels, ``|`` (any of), ``&`` (all of) and brackets, so the same
  string is the display name of the promo and the input of :func:`evaluate`. Labels never contain
  an operator character (checked by a test).

Nothing here touches the database; the API passes the labels the person holds to :func:`evaluate`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

UNKNOWN_CLUB = "אחר"
"""Stored for a club restriction nobody can be a member of as far as we can tell."""

CLUB_KINDS = ("club", "card", "staff", "other")
_OPERATORS = "|&()"
_CODE_LABEL = re.compile(r"^(\d+)\s*(?:[-–]\s*(.*))?$")
_TYPE_FIRST = re.compile(r"^(\d+)\s*=\s*(.*)$", re.S)
_TYPE_LAST = re.compile(r"^(.*?)\s*=\s*(\d+)$", re.S)


def norm_text(text: str | None) -> str:
    """Trimmed, inner whitespace collapsed, case-folded: how club texts are compared."""
    return " ".join((text or "").replace('"', " ").split()).casefold()


# --------------------------------------------------------------------------- the data


@dataclass(frozen=True)
class ClubDef:
    id: str
    label: str
    kind: str
    texts: tuple[str, ...]


@dataclass(frozen=True)
class ChainClubs:
    chain_id: str
    slug: str
    name: str
    clubs: tuple[ClubDef, ...]

    def by_text(self) -> dict[str, ClubDef]:
        """Normalized ClubID text (or label) -> club."""
        out: dict[str, ClubDef] = {}
        for club in self.clubs:
            for text in (club.label, *club.texts):
                out[norm_text(text)] = club
        return out

    def label_of(self, club_id: str) -> str | None:
        return next((c.label for c in self.clubs if c.id == club_id), None)


DATA_FILE = Path(__file__).with_name("chain_clubs.json")


@lru_cache(maxsize=1)
def load_chain_clubs() -> dict[str, ChainClubs]:
    """chain id -> its clubs, from ``chain_clubs.json`` (chains without clubs are absent)."""
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    out: dict[str, ChainClubs] = {}
    for entry in data["chains"]:
        clubs = tuple(
            ClubDef(c["id"], c["label"], c["kind"], tuple(c["texts"])) for c in entry["clubs"]
        )
        out[entry["chain_id"]] = ChainClubs(entry["chain_id"], entry["slug"], entry["name"], clubs)
    return out


def chain_clubs_for(chain_id: str | None) -> ChainClubs | None:
    return load_chain_clubs().get(chain_id or "")


def validate_chain_clubs(chains: Iterable[ChainClubs] | None = None) -> list[str]:
    """Problems in the data file (empty when it is sound); a test runs this."""
    problems: list[str] = []
    seen_ids: set[str] = set()
    for chain in chains if chains is not None else load_chain_clubs().values():
        labels: set[str] = set()
        texts: dict[str, str] = {}
        for club in chain.clubs:
            if not club.id.startswith(f"{chain.slug}:") or club.id in seen_ids:
                problems.append(f"{club.id}: id must be unique and start with {chain.slug}:")
            seen_ids.add(club.id)
            if club.kind not in CLUB_KINDS:
                problems.append(f"{club.id}: kind {club.kind!r}")
            if any(ch in club.label for ch in _OPERATORS + '"') or club.label != club.label.strip():
                problems.append(f"{club.id}: label {club.label!r} has an operator character")
            if norm_text(club.label) in labels or club.label == UNKNOWN_CLUB:
                problems.append(f"{club.id}: label {club.label!r} is not unique")
            labels.add(norm_text(club.label))
            for text in (club.label, *club.texts):
                key = norm_text(text)
                if texts.setdefault(key, club.id) != club.id:
                    problems.append(f"{club.id}: text {text!r} also belongs to {texts[key]}")
    return problems


# --------------------------------------------------------------------------- the grammar

Node = tuple  # ("atom", text) | ("and", [nodes]) | ("or", [nodes])


class _Tokens:
    def __init__(self, text: str) -> None:
        self.items: list[tuple[str, str]] = []
        buf: list[str] = []
        quoted = False

        def flush() -> None:
            atom = "".join(buf).strip()
            buf.clear()
            if atom:
                self.items.append(("atom", atom))

        for ch in text:
            if ch == '"':
                quoted = not quoted
            elif not quoted and ch in _OPERATORS:
                flush()
                self.items.append(("op", ch))
            else:
                buf.append(ch)
        if quoted:
            raise ValueError("unterminated quote")
        flush()
        self.pos = 0

    def peek(self) -> tuple[str, str] | None:
        return self.items[self.pos] if self.pos < len(self.items) else None

    def take(self) -> tuple[str, str]:
        tok = self.items[self.pos]
        self.pos += 1
        return tok


def _parse_or(tokens: _Tokens) -> Node:
    parts = [_parse_and(tokens)]
    while tokens.peek() == ("op", "|"):
        tokens.take()
        parts.append(_parse_and(tokens))
    return parts[0] if len(parts) == 1 else ("or", parts)


def _parse_and(tokens: _Tokens) -> Node:
    parts = [_parse_factor(tokens)]
    while tokens.peek() == ("op", "&"):
        tokens.take()
        parts.append(_parse_factor(tokens))
    return parts[0] if len(parts) == 1 else ("and", parts)


def _parse_factor(tokens: _Tokens) -> Node:
    tok = tokens.peek()
    if tok is None:
        raise ValueError("unexpected end")
    if tok == ("op", "("):
        tokens.take()
        node = _parse_or(tokens)
        if tokens.peek() != ("op", ")"):
            raise ValueError("missing )")
        tokens.take()
        return node
    if tok[0] == "atom":
        tokens.take()
        return ("atom", tok[1])
    raise ValueError(f"unexpected {tok[1]!r}")


def parse_rule(text: str) -> Node | None:
    """Parse ``A | B``, ``A & (B | C)`` and so on; atoms are names (a double-quoted name may
    contain operator characters). ``None`` for text that is not a well-formed rule."""
    try:
        tokens = _Tokens(text)
        node = _parse_or(tokens)
        if tokens.peek() is not None:
            raise ValueError("trailing tokens")
        return node
    except (ValueError, IndexError):
        return None


def file_atom_name(atom: str) -> str:
    """The club name of an expression atom of a file: ``<type>=<name>`` or ``<name>=<type>``."""
    text = atom.strip()
    match = _TYPE_FIRST.match(text)
    if match:
        return match.group(2).strip()
    match = _TYPE_LAST.match(text)
    if match:
        return match.group(1).strip()
    return text


def evaluate(node: Node, holds: Callable[[str], bool]) -> bool:
    """Whether a member of the clubs for which ``holds(name)`` is true satisfies the rule. The
    unknown marker (``אחר``) is never satisfied, whatever ``holds`` says."""
    kind = node[0]
    if kind == "atom":
        return node[1].strip() != UNKNOWN_CLUB and bool(holds(node[1]))
    if kind == "or":
        return any(evaluate(n, holds) for n in node[1])
    return all(evaluate(n, holds) for n in node[1])


def rule_atoms(node: Node) -> list[str]:
    if node[0] == "atom":
        return [node[1]]
    return [a for n in node[1] for a in rule_atoms(n)]


def satisfied(rule: str | None, holds: Callable[[str], bool]) -> bool:
    """``evaluate`` on a stored rule string; unparseable or empty is never satisfied."""
    if not rule or not rule.strip():
        return False
    node = parse_rule(rule)
    return node is not None and evaluate(node, holds)


# --------------------------------------------------------------------------- resolving files


@dataclass(frozen=True)
class _Unknown:
    raw: str | None = None  # the one plain name, when there is exactly one


def _plain(name: str) -> bool:
    return bool(name) and not any(ch in name for ch in _OPERATORS + '"')


def _resolve(node: Node, by_text: dict[str, ClubDef], names: Callable[[str], str]):
    kind = node[0]
    if kind == "atom":
        name = names(node[1])
        club = by_text.get(norm_text(name))
        if club is not None:
            return ("atom", club.label)
        return _Unknown(name if _plain(name) else None)
    children = [_resolve(n, by_text, names) for n in node[1]]
    if kind == "and":
        if any(isinstance(c, _Unknown) for c in children):
            return _Unknown()
        return ("and", children)
    known = [c for c in children if not isinstance(c, _Unknown)]
    if not known:
        raws = {c.raw for c in children if isinstance(c, _Unknown)}
        return _Unknown(next(iter(raws)) if len(raws) == 1 and None not in raws else None)
    return known[0] if len(known) == 1 else ("or", known)


def _dedupe(nodes: list) -> list:
    out: list = []
    for n in nodes:
        if n not in out:
            out.append(n)
    return out


def _render(node, top: bool = True) -> str:
    if isinstance(node, _Unknown):
        return node.raw or UNKNOWN_CLUB
    kind = node[0]
    if kind == "atom":
        return node[1]
    parts = _dedupe([_render(n, top=False) for n in node[1]])
    if len(parts) == 1:
        return parts[0]
    text = (" | " if kind == "or" else " & ").join(parts)
    return text if top else f"({text})"


def value_names(value: str) -> list[str]:
    """The club names a ClubID value mentions (for a report): the label after ``<n> - ``, the
    names of an expression, or the text itself. A bare code has none."""
    text = value.strip()
    match = _CODE_LABEL.match(text)
    if match:
        label = (match.group(2) or "").strip()
        return [label] if label else []
    if any(ch in text for ch in "=|&()"):
        node = parse_rule(text)
        return [file_atom_name(a) for a in rule_atoms(node)] if node else [text]
    return [text] if text else []


def resolve_value(chain_id: str | None, value: str) -> str | None:
    """The stored rule for one ClubID value that is not "everyone", or ``None`` when the value is
    a bare code (``1``) with no text to resolve (the caller keeps its older fallback)."""
    text = value.strip()
    defs = chain_clubs_for(chain_id)
    by_text = defs.by_text() if defs else {}
    match = _CODE_LABEL.match(text)
    if match:
        label = (match.group(2) or "").strip()
        if not label:
            return None
        node: Node = ("atom", label)  # the label is one name, whatever characters it holds
        names: Callable[[str], str] = lambda s: s  # noqa: E731
    elif any(ch in text for ch in "=|&()"):
        parsed = parse_rule(text)
        if parsed is None:
            return UNKNOWN_CLUB
        node, names = parsed, file_atom_name
    else:
        node, names = ("atom", text), lambda s: s  # noqa: E731
    return _render(_resolve(node, by_text, names))


def resolve_requirement(chain_id: str | None, values: list[str]) -> str | None:
    """The stored club rule for the ClubID values of one promotion (``None`` when every value is
    a bare code and the older name fallback applies). Several club values must all hold: that is
    the safe reading (an unknown reading never widens who gets the price)."""
    rules: list[str] = []
    for value in values:
        rule = resolve_value(chain_id, value)
        if rule is None:
            return None
        if rule not in rules:
            rules.append(rule)
    if not rules:
        return None
    if len(rules) == 1:
        return rules[0]
    if UNKNOWN_CLUB in rules:
        return UNKNOWN_CLUB
    return " & ".join(f"({r})" if " | " in r else r for r in rules)
