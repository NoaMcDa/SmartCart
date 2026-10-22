"""The kosher filter: which items may be offered to a person who set a kosher level.

One small module used by every route that picks an item for a person: ``basket.price_baskets``
(so /compare, /optimize, the MILP and /optimize/swaps), the exact-barcode path inside it, and
/search. The rules (docs/matching.md, "Kosher"):

* the chains' files have no kosher field, so what an item states comes from its **name** alone
  (``smartcart_catalog.kosher``: explicit words only, never a brand), plus the ``kosher`` attribute
  when a person verified it (a model's value is never trusted: it is unverified by definition);
* an item whose name rules the level out (it says it is not kosher, or states a different named
  hechsher than the one asked for) is **never offered**;
* an item whose name states nothing that decides it is **unknown**: offered with a label
  ("כשרות לא ידועה"), and left out when the person chose ``only_stated``;
* a store that cannot meet the basket under the filter lists the item as missing. The filter is
  never relaxed, not for a cheaper price and not for a store that would otherwise be empty.

Kosher for Passover is a second, independent test with the same three answers.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from smartcart_api import schemas
from smartcart_catalog import kosher as ck


@dataclass(frozen=True)
class Assessment:
    """What one item's name says, against the filter."""

    marks: frozenset[str]
    level: ck.Verdict  # against the chosen level ("meets" when none was chosen)
    passover: ck.Verdict  # against kosher for Passover ("meets" when not asked)


def active(f: schemas.KosherFilter | None) -> bool:
    """Whether the filter decides anything: a level, or kosher for Passover."""
    return f is not None and (f.level is not None or f.passover)


def assess_marks(marks: frozenset[str], f: schemas.KosherFilter) -> Assessment:
    return Assessment(
        marks=marks,
        level=ck.judge(marks, f.level),
        passover=ck.judge_passover(marks) if f.passover else "meets",
    )


def allowed(a: Assessment, f: schemas.KosherFilter) -> bool:
    """May the item be offered: never when its name rules the filter out, and with
    ``only_stated`` only when its name states enough to meet it."""
    if a.level == "fails" or a.passover == "fails":
        return False
    return not (f.only_stated and (a.level != "meets" or a.passover != "meets"))


def assess_items(
    conn: psycopg.Connection, item_ids: list[int] | set[int], f: schemas.KosherFilter
) -> dict[int, Assessment]:
    """item_id -> assessment, from the item's published name and, when a person verified it, its
    ``kosher`` attribute. One query."""
    if not item_ids:
        return {}
    out: dict[int, Assessment] = {}
    for iid, chain_id, raw_name, kosher_attr, verified in conn.execute(
        "SELECT i.id, i.chain_id, i.raw_name, a.attrs->>'kosher', COALESCE(a.verified_keys, '{}')"
        " FROM items AS i LEFT JOIN item_attributes AS a ON a.item_id = i.id"
        " WHERE i.id = ANY(%s)",
        (sorted(item_ids),),
    ):
        marks = ck.read_item_name(raw_name, chain_id)
        if kosher_attr and "kosher" in verified:
            marks = marks | ck.read_marks(kosher_attr)
        out[iid] = assess_marks(marks, f)
    return out


def allowed_items(
    conn: psycopg.Connection, item_ids: list[int] | set[int], f: schemas.KosherFilter
) -> set[int]:
    """The ids among ``item_ids`` that may be offered."""
    return {i for i, a in assess_items(conn, item_ids, f).items() if allowed(a, f)}


def label(a: Assessment | None, f: schemas.KosherFilter | None) -> schemas.KosherLabel | None:
    """The label an offered item carries. ``None`` when the filter is not active."""
    if f is None or not active(f):
        return None
    if a is None:  # an item that could not be read is unknown, not fine
        return schemas.KosherLabel(
            level="unknown" if f.level else None, passover="unknown" if f.passover else None
        )
    return schemas.KosherLabel(
        level=None if f.level is None else ("meets" if a.level == "meets" else "unknown"),
        passover=None if not f.passover else ("meets" if a.passover == "meets" else "unknown"),
        stated=[code for code in ck.MARKS if code in a.marks],
    )


# --- search --------------------------------------------------------------------------------------


def hit_labels(
    conn: psycopg.Connection, canonical_ids: list[int], f: schemas.KosherFilter
) -> dict[int, schemas.KosherHitLabel]:
    """canonical_id -> what the catalog's items for it say against the filter. A canonical with
    no mapped item has no entry. Items counted are the ones a price line may use: exact or any
    brand, not under review, not rejected."""
    out: dict[int, schemas.KosherHitLabel] = {}
    if not active(f) or not canonical_ids:
        return out
    pairs = conn.execute(
        "SELECT canonical_id, item_id FROM item_canonical"
        " WHERE canonical_id = ANY(%s) AND flex_level IN ('exact', 'any_brand')"
        " AND NOT needs_review AND NOT human_rejected",
        (sorted(set(canonical_ids)),),
    ).fetchall()
    seen = assess_items(conn, {i for _, i in pairs}, f)
    counts: dict[int, list[int]] = {}
    for cid, iid in pairs:
        a = seen.get(iid)
        if a is None:
            continue
        c = counts.setdefault(cid, [0, 0, 0])
        if a.level == "fails" or a.passover == "fails":
            c[2] += 1
        elif a.level == "meets" and a.passover == "meets":
            c[0] += 1
        else:
            c[1] += 1
    for cid, (meets, unknown, fails) in counts.items():
        if meets:
            status = "meets"
        elif unknown and not f.only_stated:
            status = "unknown"
        else:
            status = "none"
        out[cid] = schemas.KosherHitLabel(status=status, meets=meets, unknown=unknown, fails=fails)
    return out
