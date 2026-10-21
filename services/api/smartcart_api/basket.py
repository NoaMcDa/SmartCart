"""Basket pricing shared by /compare and /optimize (issues #58, #62).

For a basket (canonical, quantity, flexibility level) and a set of stores, each store gets one
priced line per canonical it can supply, read from ``effective_prices``, and the canonicals it
cannot supply are listed as missing, never dropped.

Line rules:

* Club deals (issue #19): a row whose promo needs a club the user did not mark (``club_member``)
  is replaced by the best of its ``noclub`` option (the best price without any club promo) and
  the deals of clubs the user did mark (``noclub.clubs``). A club deal is never applied for a
  non-member: the line then carries ``club_offer_name`` / ``club_offer_discount`` as information,
  never in a total or a saving. Every caller of ``price_baskets`` (/compare, /optimize and the
  MILP) inherits this rule.
* Exact items: with ``flex_level = exact`` and ``exact_item_id``, the store must sell that
  barcode (an item of the store's chain with the same barcode, mapped to the canonical at exact
  or any_brand); it is priced live with the same promo folding as the precompute. Without
  ``exact_item_id`` the precomputed ``exact`` row is used.
* Quantity: for canonicals sold by weight (base unit ``kg``) the quantity is in kg and the line is
  quantity x effective price per kg (estimated). Otherwise the quantity counts packs: full promo
  bundles at the promo price, the remainder at the shelf price, and when the remainder is short
  of a bundle the line says how many to add and what that saves.
* Substitutes: a line whose item is mapped to the canonical at ``close`` is a substitute. It
  carries the mapping confidence, the attribute tags (matched, differs, unverified) of the item
  against the canonical, and the non-substitute item of that store as ``original_item_id`` when
  there is one, with that item's offer at the same store as ``original_here`` (display only: it
  is the store's ``any_brand`` row, already club-gated, priced at the line's quantity, and read
  from the rows and item lookups the line itself uses, so it adds no query per line).
* Allowed attributes (issue #31, ``BasketItem.allow``): with ``any_brand`` or ``close`` and a
  non-empty ``allow``, a store may also offer an item of a sibling canonical (same product type,
  taxonomy node and base unit) whose critical attributes differ from the requested canonical's
  only in allowed keys (``sibling_candidates``). The cheapest of the canonical's own offer and
  the siblings' (by effective unit price) wins, and a sibling's offer is always a substitute with
  a ``differs`` tag on every allowed attribute that differs, and ``original_here`` is the
  requested canonical's own offer at that store. Nothing the person did not allow is relaxed;
  ``exact`` ignores ``allow``.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any

import psycopg

from smartcart_api import schemas
from smartcart_api.precompute import FLEX_ORDER, Option, item_options
from smartcart_catalog.judge import BRAND_KEYS, quantity_in_base, values_equal
from smartcart_catalog.models import ALWAYS_UNVERIFIED
from smartcart_ingest.adapters import clubs as clubrules

_C2 = Decimal("0.01")
_Q4 = Decimal("0.0001")
ZERO = Decimal(0)


def money(d: Decimal) -> Decimal:
    return d.quantize(_C2, rounding=ROUND_HALF_UP)


def distance_is_approximate(geo_precision: str | None) -> bool:
    """A distance is an estimate for a town-centre (locality) point or a store with no coordinates."""
    return geo_precision not in ("address", "street")


@dataclass
class StoreInfo:
    store_id: int
    chain_id: str
    chain_name: str
    store_name: str
    city: str | None
    channel: str
    distance_m: int
    lat: float | None = None
    lon: float | None = None
    geo_precision: str | None = None  # stores.geo_precision: address | street | locality | None

    @property
    def distance_approximate(self) -> bool:
        """The distance is an estimate: a town-centre (locality) point, or no coordinates at all."""
        return distance_is_approximate(self.geo_precision)


@dataclass
class StoreBasket:
    info: StoreInfo
    lines: dict[int, schemas.PricedItem] = field(default_factory=dict)  # canonical_id -> line
    missing: list[int] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return money(sum((li.line_total for li in self.lines.values()), ZERO))

    def result(
        self, home: StoreBasket | None = None, only: set[int] | None = None
    ) -> schemas.StoreResult:
        lines = [li for cid, li in self.lines.items() if only is None or cid in only]
        total = money(sum((li.line_total for li in lines), ZERO))
        updated = max((li.price_valid_from for li in lines), default=None)
        return schemas.StoreResult(
            store_id=self.info.store_id,
            chain_id=self.info.chain_id,
            chain_name=self.info.chain_name,
            store_name=self.info.store_name,
            city=self.info.city,
            distance_m=self.info.distance_m,
            geo_precision=self.info.geo_precision,
            distance_approximate=self.info.distance_approximate,
            channel=self.info.channel,
            total=total,
            found_count=len(lines),
            missing=list(self.missing),
            substituted_count=sum(1 for li in lines if li.is_substitute),
            items=lines,
            prices_updated_at=updated or datetime.now(UTC),
            saving_vs_home=saving_vs(home, self, only) if home is not None else None,
            lat=self.info.lat,
            lon=self.info.lon,
        )


def saving_vs(home: StoreBasket, other: StoreBasket, only: set[int] | None = None) -> Decimal:
    """Home total minus ``other``'s total over the canonicals both stores supply (and, with
    ``only``, that are among those canonicals: the lines a plan buys at ``other``).

    Missing items are listed separately and never counted as a saving, so a store cannot look
    cheaper than the home store by not stocking part of the list.
    """
    common = home.lines.keys() & other.lines.keys()
    if only is not None:
        common &= only
    return money(sum((home.lines[c].line_total - other.lines[c].line_total for c in common), ZERO))


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


def promo_confidence(raw: Any) -> float | None:
    """``promos.raw->>'confidence'`` as a number in [0, 1] when the adapter recorded one."""
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v != v:  # NaN
        return None
    if v > 1 and v <= 100:  # a percentage
        v = v / 100
    return v if 0 <= v <= 1 else None


# --- stores ------------------------------------------------------------------------------------

_LAT_LON = "ST_Y(s.geog::geometry)::float8, ST_X(s.geog::geometry)::float8, s.geo_precision"


def stores_in_radius(
    conn: psycopg.Connection, loc: schemas.Location, include_online: bool, limit: int | None = None
) -> list[StoreInfo]:
    rows = conn.execute(
        "SELECT sw.store_id, sw.chain_id, c.name, s.name, s.city, sw.channel, round(sw.distance_m)::int,"
        f" {_LAT_LON}"
        " FROM stores_within(%s, %s, %s) AS sw"
        " JOIN stores AS s ON s.id = sw.store_id JOIN chains AS c ON c.id = sw.chain_id"
        " WHERE sw.channel = 'physical' OR %s"
        " ORDER BY sw.distance_m, sw.store_id LIMIT %s",
        (loc.lon, loc.lat, loc.radius_m, include_online, limit),
    ).fetchall()
    return [StoreInfo(*r) for r in rows]


def store_info(conn: psycopg.Connection, store_id: int, loc: schemas.Location) -> StoreInfo | None:
    """One store with its distance from ``loc``, whatever the radius (the user's home store)."""
    row = conn.execute(
        "SELECT s.id, s.chain_id, c.name, s.name, s.city, s.channel,"
        " COALESCE(round(ST_Distance(s.geog, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography))::int, 0),"
        f" {_LAT_LON}"
        " FROM stores AS s JOIN chains AS c ON c.id = s.chain_id WHERE s.id = %s",
        (loc.lon, loc.lat, store_id),
    ).fetchone()
    return StoreInfo(*row) if row else None


# --- lines -------------------------------------------------------------------------------------


@dataclass
class _Choice:
    item_id: int
    shelf_price: Decimal
    effective_price: Decimal
    effective_unit_price: Decimal
    uom: str
    promo_id: int | None
    promo_min_qty: Decimal | None
    club_required: bool
    club_name: str | None
    price_valid_from: datetime
    is_estimated: bool

    def key(self) -> tuple:
        return (self.effective_unit_price, self.effective_price, self.item_id)


def _from_json(js: dict[str, Any], club_name: str | None = None) -> _Choice:
    """A ``noclub`` option, or (with ``club_name``) one of its ``clubs`` alternatives."""
    return _Choice(
        item_id=int(js["item_id"]),
        shelf_price=Decimal(js["shelf_price"]),
        effective_price=Decimal(js["effective_price"]),
        effective_unit_price=Decimal(js["effective_unit_price"]),
        uom=js["uom"],
        promo_id=js.get("promo_id"),
        promo_min_qty=Decimal(js["promo_min_qty"]) if js.get("promo_min_qty") else None,
        club_required=club_name is not None,
        club_name=club_name,
        price_valid_from=datetime.fromisoformat(js["price_valid_from"]),
        is_estimated=bool(js.get("is_estimated")),
    )


def gate_club(
    c: _Choice,
    noclub: dict[str, Any] | str | None,
    clubs: list[str],
    chain: tuple[str, list[str]] | None,
) -> tuple[_Choice | None, _Choice | None]:
    """(what this user pays, a club deal they did not mark) for one ``effective_prices`` row.

    The second value is information only; it never enters a total. The first is None only when
    a club row has no ``noclub`` option (never written by the precompute): the line is then left
    out rather than priced with a deal the user cannot get.
    """
    chain_name, chain_club_names = chain or (None, [])
    if not c.club_required or club_member(c.club_name, clubs, chain_name, chain_club_names):
        return c, None
    if noclub is None:
        return None, c
    js = noclub if isinstance(noclub, dict) else json.loads(noclub)
    pick = _from_json(js)
    for name, alt in (js.get("clubs") or {}).items():
        if club_member(name, clubs, chain_name, chain_club_names):
            opt = _from_json(alt, club_name=name)
            if opt.key() < pick.key():
                pick = opt
    return pick, c


def club_alternatives(
    c: _Choice,
    noclub: dict[str, Any] | str | None,
    clubs: list[str],
    chain: tuple[str, list[str]] | None,
) -> list[_Choice]:
    """The other offers of a club row that are open to this user: the best price without a club
    deal and the deal of every club they marked (``gate_club`` returns the one with the lowest
    unit price; the cheapest for a given quantity can be another, for example when the club deal
    needs three packs and the list has two). Empty for a row without a club deal."""
    if not c.club_required or noclub is None:
        return []
    chain_name, chain_club_names = chain or (None, [])
    js = noclub if isinstance(noclub, dict) else json.loads(noclub)
    out = [_from_json(js)]
    for name, alt in (js.get("clubs") or {}).items():
        if club_member(name, clubs, chain_name, chain_club_names):
            out.append(_from_json(alt, club_name=name))
    if club_member(c.club_name, clubs, chain_name, chain_club_names):
        out.append(c)
    return out


def _from_option(o: Option) -> _Choice:
    return _Choice(
        o.item_id,
        o.shelf_price,
        o.effective_price,
        o.effective_unit_price,
        o.uom,
        o.promo_id,
        o.promo_min_qty,
        o.club_required,
        o.club_name,
        o.price_valid_from,
        o.is_estimated,
    )


def line_total(c: _Choice, quantity: Decimal, by_weight: bool) -> tuple[Decimal, bool]:
    """(line total, promo applied) for ``quantity`` of choice ``c``."""
    if by_weight:
        return money(quantity * c.effective_unit_price), c.promo_id is not None
    need = c.promo_min_qty or Decimal(1)
    if c.promo_id is None:
        return money(quantity * c.shelf_price), False
    if need <= 1:
        return money(quantity * c.effective_price), True
    bundles = (quantity / need).to_integral_value(rounding=ROUND_FLOOR)
    rest = quantity - bundles * need
    total = bundles * money(c.effective_price * need) + rest * c.shelf_price
    return money(total), bundles > 0


def _unit_paid(c: _Choice, total: Decimal, qty: Decimal, by_weight: bool) -> Decimal:
    """The unit price actually paid on a line: the effective one, scaled by what the quantity
    pays against the shelf price (a half-filled bundle pays more than the promo unit price)."""
    shelf_total = money(qty * c.shelf_price) if not by_weight else ZERO
    paid_ratio = total / shelf_total if shelf_total else None  # a quantity too small to cost 0.01
    if paid_ratio is not None and c.effective_price:
        return (c.effective_unit_price * c.shelf_price / c.effective_price * paid_ratio).quantize(
            _Q4
        )
    return c.effective_unit_price


def _tags(
    item_attrs: dict, verified: list[str], critical: dict, soft: dict, rule_keys: list[str]
) -> list[schemas.AttributeTag]:
    keys = list(dict.fromkeys([*rule_keys, *critical.keys(), *soft.keys()]))
    # The pack-size unit (g, ml, unit) is not an attribute of its own: it is folded into the
    # pack_size tag ("1000 g") and its mismatch counts against pack_size.
    unit_have = item_attrs.get("unit") if "pack_size" in keys else None
    unit_want = critical.get("unit", soft.get("unit")) if "pack_size" in keys else None
    out = []
    for key in keys:
        if key == "unit" and "pack_size" in keys:
            continue
        want = critical.get(key, soft.get(key))
        have = item_attrs.get(key)
        if have is None:
            out.append(schemas.AttributeTag(key=key, value=None, status="unverified"))
            continue
        if want is None:
            continue  # nothing to compare against
        same = _same(want, have)
        if key == "pack_size" and unit_want is not None and unit_have is not None:
            same = same and _same(unit_want, unit_have)
        if not same:
            status = "differs"
        elif key in ALWAYS_UNVERIFIED and key not in verified:
            status = "unverified"
        else:
            status = "matched"
        value = _text(have)
        if key == "pack_size" and unit_have is not None:
            value = f"{value} {_text(unit_have)}"
        out.append(schemas.AttributeTag(key=key, value=value, status=status))
    return out


def _same(a: Any, b: Any) -> bool:
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except Exception:
        return str(a).strip().lower() == str(b).strip().lower()


def _text(v: Any) -> str:
    if isinstance(v, list | tuple):
        return ", ".join(map(str, v))
    return str(v)


def _soft_differs(want: dict, have: dict, allow: tuple[str, ...]) -> bool:
    """Whether a sibling's typical soft attributes differ from the requested canonical's in an
    attribute that is not allowed (brand and the pack-size unit are not attributes of the match)."""
    for key in set(want) | set(have):
        if key in BRAND_KEYS or key in {"unit", "barcodes"} or key in allow:
            continue
        if key == "pack_size":
            a = quantity_in_base(want.get(key), want.get("unit"))
            b = quantity_in_base(have.get(key), have.get("unit"))
            if a is not None and b is not None and a != b:
                return True
        elif key in want and key in have and not values_equal(key, have[key], want[key]):
            return True
    return False


def sibling_candidates(
    conn: psycopg.Connection,
    wanted: set[tuple[int, str, tuple[str, ...]]],
    canon: dict[int, tuple],
) -> dict[tuple[int, str, tuple[str, ...]], list[tuple[int, dict[str, Any]]]]:
    """(canonical_id, flex level, allowed attributes) -> [(sibling canonical id, {critical key:
    the sibling's value})] for the siblings a store may offer instead.

    A sibling has the same product type, taxonomy node and base unit and is another canonical.
    It qualifies only when every critical attribute that differs from the requested canonical's
    (a key one of them lacks counts as differing) is in ``allow``, and at least one differs.
    At ``any_brand`` its typical soft attributes (pack size, ...) must also equal the requested
    canonical's unless allowed; at ``close`` soft differences are the level's own business.
    Which allowed keys exist is the caller's list (``schemas.SoftAttribute``); a key that no
    canonical pair differs in (``packaging``, ``pack_size``) never qualifies a sibling.
    """
    out: dict[tuple[int, str, tuple[str, ...]], list[tuple[int, dict[str, Any]]]] = {}
    if not wanted:
        return out
    rows = conn.execute(
        "SELECT c.id, s.id, s.critical_attrs, s.soft_attrs FROM canonical_products AS c"
        " JOIN canonical_products AS s ON s.product_type = c.product_type"
        "  AND s.taxonomy_id = c.taxonomy_id AND s.base_unit = c.base_unit AND s.id <> c.id"
        " WHERE c.id = ANY(%s) ORDER BY c.id, s.id",
        (sorted({w[0] for w in wanted}),),
    ).fetchall()
    for cid, flex, allow in sorted(wanted):
        want_crit, want_soft = canon[cid][2], canon[cid][3]
        found: list[tuple[int, dict[str, Any]]] = []
        for c_id, sib, crit, soft in rows:
            if c_id != cid:
                continue
            keys = set(want_crit) | set(crit)
            differs = {
                k: crit.get(k)
                for k in sorted(keys)
                if not values_equal(k, crit.get(k), want_crit.get(k))
            }
            if not differs or not set(differs) <= set(allow):
                continue
            if flex == "any_brand" and _soft_differs(want_soft, soft, allow):
                continue
            found.append((sib, differs))
        out[(cid, flex, allow)] = found
    return out


def _substitute_tags(
    item_attrs: dict,
    verified: list[str],
    critical: dict,
    soft: dict,
    rule_keys: list[str],
    differs: dict[str, Any],
) -> list[schemas.AttributeTag]:
    """``_tags``, and for a sibling's item every allowed attribute that makes it a sibling is
    tagged ``differs`` even when the item's own value was never extracted: the item is mapped to
    the sibling canonical, so it does not have the requested value."""
    tags = _tags(item_attrs, verified, critical, soft, rule_keys)
    for key, sibling_value in differs.items():
        i = next((n for n, t in enumerate(tags) if t.key == key), None)
        if i is None:
            tags.append(schemas.AttributeTag(key=key, value=_text(sibling_value), status="differs"))
        elif tags[i].status == "unverified":
            tags[i] = schemas.AttributeTag(key=key, value=_text(sibling_value), status="differs")
    return tags


def price_baskets(
    conn: psycopg.Connection,
    items: list[schemas.BasketItem],
    stores: list[StoreInfo],
    clubs: list[str],
    as_of: datetime | None = None,
) -> dict[int, StoreBasket]:
    """store_id -> StoreBasket for ``items`` at each of ``stores``."""
    as_of = as_of or datetime.now(UTC)
    baskets = {s.store_id: StoreBasket(info=s) for s in stores}
    if not stores:
        return baskets
    store_ids = list(baskets)
    # Merge duplicate canonicals with the same flex level, exact item and allowed attributes.
    # The entries of one canonical are visited strictest first (exact, any brand, close; fewer
    # allowed attributes first), so the line below never depends on the order of the list.
    asked: dict[tuple[int, str, int | None, tuple[str, ...]], Decimal] = defaultdict(Decimal)
    for it in items:
        exact = it.exact_item_id if it.flex_level == "exact" else None
        allow = () if it.flex_level == "exact" else tuple(sorted(set(it.allow)))
        asked[(it.canonical_id, it.flex_level, exact, allow)] += it.quantity
    merged = dict(
        sorted(
            asked.items(),
            key=lambda kv: (kv[0][0], FLEX_ORDER[kv[0][1]], len(kv[0][3]), kv[0][3], kv[0][2] or 0),
        )
    )
    canon_ids = sorted({k[0] for k in merged})
    canon = {
        r[0]: r
        for r in conn.execute(
            "SELECT c.id, c.base_unit, c.critical_attrs, c.soft_attrs,"
            " COALESCE(r.critical_keys, '{}') || COALESCE(r.soft_keys, '{}'), c.names_ar[1]"
            " FROM canonical_products AS c"
            " LEFT JOIN product_type_rules AS r ON r.product_type = c.product_type"
            " WHERE c.id = ANY(%s)",
            (canon_ids,),
        ).fetchall()
    }
    siblings = sibling_candidates(conn, {k[:2] + k[3:] for k in merged if k[3]}, canon)
    price_ids = sorted({*canon_ids, *(sid for sibs in siblings.values() for sid, _ in sibs)})
    rows = conn.execute(
        "SELECT canonical_id, store_id, flex_level, item_id, shelf_price, effective_price,"
        " effective_unit_price, uom, promo_id, promo_min_qty, club_required, club_name,"
        " price_valid_from, is_estimated, noclub"
        " FROM effective_prices WHERE store_id = ANY(%s) AND canonical_id = ANY(%s)",
        (store_ids, price_ids),
    ).fetchall()
    chains = chain_clubs(conn, {s.chain_id for s in stores})
    store_chain = {s.store_id: chains.get(s.chain_id) for s in stores}
    eff: dict[tuple[int, int, str], _Choice] = {}
    offers: dict[tuple[int, int, str], _Choice] = {}
    alternatives: dict[tuple[int, int, str], list[_Choice]] = {}
    for r in rows:
        cid, sid, flex = r[0], r[1], r[2]
        c = _Choice(
            r[3],
            r[4],
            r[5] if r[5] is not None else r[4],
            r[6],
            r[7],
            r[8],
            r[9],
            r[10],
            r[11],
            r[12],
            r[13],
        )
        pick, offer = gate_club(c, r[14], clubs, store_chain.get(sid))
        if pick is None:
            continue
        eff[(cid, sid, flex)] = pick
        others = [
            o
            for o in club_alternatives(c, r[14], clubs, store_chain.get(sid))
            if o.key() != pick.key()
        ]
        if others:
            alternatives[(cid, sid, flex)] = others
        if offer is not None:
            offers[(cid, sid, flex)] = offer

    # Exact barcodes, priced live.
    exact_choices: dict[tuple[int, int, int], _Choice] = {}
    exact_offers: dict[tuple[int, int, int], _Choice] = {}
    exact_keys = [(cid, ex) for (cid, _f, ex, _a) in merged if ex is not None]
    if exact_keys:
        exact_choices, exact_offers = _exact_choices(
            conn, exact_keys, stores, clubs, as_of, canon, chains
        )

    # (store, canonical) -> (choice, quantity, flex, exact item, canonical the choice is mapped to,
    # critical key -> the sibling's value where it differs from the requested canonical: non-empty
    # only for a sibling)
    chosen: dict[
        tuple[int, int], tuple[_Choice, Decimal, str, int | None, int, dict[str, Any]]
    ] = {}
    chosen_offer: dict[tuple[int, int], _Choice] = {}
    # (store, canonical) -> the candidates for the line, the canonical's own offer first and then
    # the allowed siblings' by unit price: (choice, canonical it is mapped to, differing attributes)
    options: dict[tuple[int, int], list[tuple[_Choice, int, dict[str, Any]]]] = {}
    unmet: set[tuple[int, int]] = set()  # (store, canonical) whose strictest request has no offer
    for (cid, flex, ex, allow), qty in merged.items():
        for s in stores:
            if (s.store_id, cid) in unmet:
                continue
            src, differs = cid, {}
            cands: list[tuple[_Choice, int, dict[str, Any]]] = []
            if ex is not None:
                c = exact_choices.get((cid, ex, s.store_id))
                offer = exact_offers.get((cid, ex, s.store_id))
            else:
                c = eff.get((cid, s.store_id, flex))
                sibs = sorted(
                    (
                        (sc.key(), sib, diff)
                        for sib, diff in siblings.get((cid, flex, allow), ())
                        if (sc := eff.get((sib, s.store_id, flex))) is not None
                    ),
                    key=lambda t: t[:2],
                )
                cands = ([(c, cid, {})] if c is not None else []) + [
                    (eff[(sib, s.store_id, flex)], sib, diff) for _k, sib, diff in sibs
                ]
                # The canonical's own offer keeps a tie; a sibling must be cheaper per unit.
                if sibs and (c is None or sibs[0][0][:2] < c.key()[:2]):
                    src, differs = sibs[0][1], sibs[0][2]
                    c = eff[(src, s.store_id, flex)]
                offer = offers.get((src, s.store_id, flex))
            prev = chosen.get((s.store_id, cid))
            if c is None:
                if prev is None:
                    # The strictest request for this canonical cannot be met here: the canonical
                    # is missing, not priced for the looser request's share of the quantity.
                    unmet.add((s.store_id, cid))
                continue
            if prev is None:
                chosen[(s.store_id, cid)] = (c, qty, flex, ex, src, differs)
                options[(s.store_id, cid)] = cands
                if offer is not None:
                    chosen_offer[(s.store_id, cid)] = offer
            else:  # the same canonical asked twice at different levels: one line, both quantities
                chosen[(s.store_id, cid)] = (prev[0], prev[1] + qty, *prev[2:])

    # The offers were ranked by unit price (what the precompute keeps), but the line pays for the
    # quantity asked: a deal that needs 4 packs does not help a list with 3. Take the cheapest line
    # among the canonical's own offer, its allowed siblings' and the other offers of a club row
    # open to this user; the own offer first, so it keeps every tie. Marking a club never raises
    # a line, and an allowed sibling is chosen only when it is cheaper for the quantity.
    for key, (c, qty, flex, ex, src, differs) in list(chosen.items()):
        sid, cid = key
        if ex is not None or canon[cid][1] == "kg":
            continue
        full: list[tuple[_Choice, int, dict[str, Any]]] = []
        for oc, osrc, odiff in options.get(key) or [(c, src, differs)]:
            full.append((oc, osrc, odiff))
            full += [(a, osrc, odiff) for a in alternatives.get((osrc, sid, flex), ())]
        best = min(full, key=lambda t: line_total(t[0], qty, False)[0])
        if best[0] is not c:
            chosen[key] = (best[0], qty, flex, ex, best[1], best[2])
            offer = offers.get((best[1], sid, flex))
            if offer is not None:
                chosen_offer[key] = offer
            else:
                chosen_offer.pop(key, None)

    # The original at a substitute's own store (display only): the store's any_brand row of the
    # requested canonical, the cheapest for the quantity of the offers open to this user. A
    # close-level pick or a sibling canonical's offer can be a substitute.
    originals: dict[tuple[int, int], _Choice] = {}
    for (sid, cid), (c, q, flex, ex, _src, differs) in chosen.items():
        if ex is not None or (flex != "close" and not differs):
            continue
        alt = eff.get((cid, sid, "any_brand"))
        if alt is not None:
            if canon[cid][1] != "kg":
                alt = min(
                    [alt, *alternatives.get((cid, sid, "any_brand"), ())],
                    key=lambda o: line_total(o, q, False)[0],
                )
            if alt.item_id != c.item_id:
                originals[(sid, cid)] = alt

    item_ids = sorted(
        {c.item_id for c, *_ in chosen.values()} | {o.item_id for o in originals.values()}
    )
    info = _item_info(conn, item_ids, price_ids)
    promo_rows = conn.execute(
        "SELECT id, description, raw->>'confidence' FROM promos WHERE id = ANY(%s)",
        (
            sorted(
                {c.promo_id for c, *_ in chosen.values() if c.promo_id}
                | {o.promo_id for o in originals.values() if o.promo_id}
            ),
        ),
    ).fetchall()
    promo_desc = {r[0]: r[1] for r in promo_rows}
    promo_conf = {r[0]: promo_confidence(r[2]) for r in promo_rows}
    for (sid, cid), (c, qty, _flex, ex, src, differs) in chosen.items():
        base_unit, critical, soft, rule_keys = (
            canon[cid][1],
            canon[cid][2],
            canon[cid][3],
            canon[cid][4],
        )
        raw_name, mappings, attrs, verified = info.get(c.item_id, ("", {}, {}, []))
        mapping = mappings.get(src)
        level = mapping[0] if mapping else "exact"
        # A sibling canonical's item is never what was asked for: always a labeled substitute.
        is_sub = ex is None and (bool(differs) or FLEX_ORDER.get(level, 0) == FLEX_ORDER["close"])
        by_weight = base_unit == "kg"
        total, applied = line_total(c, qty, by_weight)
        add_qty = add_saving = None
        if not by_weight and c.promo_id is not None and c.promo_min_qty and c.promo_min_qty > 1:
            rest = qty % c.promo_min_qty
            if rest:
                add_qty = c.promo_min_qty - rest
                more = qty + add_qty
                with_promo, _ = line_total(c, more, False)
                add_saving = money(more * c.shelf_price - with_promo)
        unit_paid = _unit_paid(c, total, qty, by_weight)
        original = original_here = None
        alt = originals.get((sid, cid)) if is_sub else None
        if alt is not None:
            original = alt.item_id
            alt_total, alt_applied = line_total(alt, qty, by_weight)
            original_here = schemas.OriginalOffer(
                item_id=alt.item_id,
                display_name_he=info.get(alt.item_id, ("",))[0],
                canonical_name_ar=canon[cid][5],
                shelf_price=alt.shelf_price,
                effective_unit_price=_unit_paid(alt, alt_total, qty, by_weight),
                uom=alt.uom,
                line_total=alt_total,
                is_estimated=alt.is_estimated or by_weight,
                promo_description=promo_desc.get(alt.promo_id) if alt.promo_id else None,
                promo_min_qty=alt.promo_min_qty,
                promo_applied=alt_applied,
                club_required=alt.club_required,
                club_name=alt.club_name,
                price_valid_from=alt.price_valid_from,
                promo_confidence=promo_conf.get(alt.promo_id) if alt.promo_id else None,
            )
        offer_name = offer_discount = None
        offer = chosen_offer.get((sid, cid))
        if offer is not None:
            with_club, _ = line_total(offer, qty, by_weight)
            if with_club < total:
                offer_name, offer_discount = offer.club_name, money(total - with_club)
        baskets[sid].lines[cid] = schemas.PricedItem(
            canonical_id=cid,
            item_id=c.item_id,
            display_name_he=raw_name,
            canonical_name_ar=canon[cid][5],
            quantity=qty,
            shelf_price=c.shelf_price,
            effective_unit_price=unit_paid,
            uom=c.uom,
            line_total=total,
            is_substitute=is_sub,
            is_estimated=c.is_estimated or by_weight,
            promo_description=promo_desc.get(c.promo_id) if c.promo_id else None,
            promo_min_qty=c.promo_min_qty,
            promo_applied=applied,
            promo_add_qty=add_qty,
            promo_add_saving=add_saving,
            club_required=c.club_required,
            club_name=c.club_name,
            price_valid_from=c.price_valid_from,
            confidence=float(mapping[1]) if mapping else None,
            tags=_substitute_tags(attrs, verified, critical, soft, rule_keys, differs)
            if is_sub
            else [],
            original_item_id=original,
            original_here=original_here,
            promo_confidence=promo_conf.get(c.promo_id) if c.promo_id else None,
            club_offer_name=offer_name,
            club_offer_discount=offer_discount,
        )
    for b in baskets.values():
        b.missing = sorted({cid for (cid, _f, _e, _a) in merged if cid not in b.lines})
    return baskets


def _item_info(
    conn: psycopg.Connection, item_ids: list[int], canon_ids: list[int]
) -> dict[int, tuple[str, dict[int, tuple[str, Decimal]], dict, list[str]]]:
    out: dict[int, tuple[str, dict[int, tuple[str, Decimal]], dict, list[str]]] = {}
    if not item_ids:
        return out
    for iid, name, attrs, verified in conn.execute(
        "SELECT i.id, i.raw_name, COALESCE(a.attrs, '{}'), COALESCE(a.verified_keys, '{}')"
        " FROM items AS i LEFT JOIN item_attributes AS a ON a.item_id = i.id WHERE i.id = ANY(%s)",
        (item_ids,),
    ).fetchall():
        out[iid] = (name, {}, attrs, list(verified))
    for iid, cid, level, conf in conn.execute(
        "SELECT ic.item_id, ic.canonical_id, ic.flex_level, ic.confidence FROM item_canonical AS ic"
        " WHERE ic.item_id = ANY(%s) AND ic.canonical_id = ANY(%s) AND NOT ic.human_rejected",
        (item_ids, canon_ids),
    ).fetchall():
        out[iid][1][cid] = (level, conf)
    return out


def _exact_choices(
    conn: psycopg.Connection,
    keys: list[tuple[int, int]],
    stores: list[StoreInfo],
    clubs: list[str],
    as_of: datetime,
    canon: dict[int, tuple],
    chains: dict[str, tuple[str, list[str]]],
) -> tuple[dict[tuple[int, int, int], _Choice], dict[tuple[int, int, int], _Choice]]:
    """(canonical_id, exact_item_id, store_id) -> live choice for that barcode at that store,
    and the club deals the user did not mark (information only), with the same club rule."""
    out: dict[tuple[int, int, int], _Choice] = {}
    offers: dict[tuple[int, int, int], _Choice] = {}
    by_chain: dict[str, list[int]] = defaultdict(list)
    for s in stores:
        by_chain[s.chain_id].append(s.store_id)
    for cid, exact_id in keys:
        # Items of any chain with the same barcode (or the item itself) mapped to the canonical.
        rows = conn.execute(
            "SELECT i.id, i.chain_id FROM items AS i"
            " JOIN items AS x ON x.id = %s"
            " JOIN item_canonical AS ic ON ic.item_id = i.id AND ic.canonical_id = %s"
            "   AND ic.flex_level IN ('exact', 'any_brand') AND NOT ic.needs_review"
            "   AND NOT ic.human_rejected"
            " WHERE i.id = x.id OR (x.barcode IS NOT NULL AND i.barcode = x.barcode)",
            (exact_id, cid),
        ).fetchall()
        base_unit = canon[cid][1]
        for chain_id in {r[1] for r in rows}:
            chain_items = [r[0] for r in rows if r[1] == chain_id]
            chain_name, chain_club_names = chains.get(chain_id, (None, []))
            per_club: dict[tuple[int, int], dict] = {}
            opts = item_options(
                conn,
                chain_id,
                by_chain.get(chain_id, []),
                chain_items,
                as_of,
                {i: base_unit for i in chain_items},
                per_club,
            )
            for (sid, iid), (best, noclub) in opts.items():
                offer = None
                pick = best
                if best.club_required and not club_member(
                    best.club_name, clubs, chain_name, chain_club_names
                ):
                    offer, pick = best, noclub
                    for name, alt in per_club.get((sid, iid), {}).items():
                        if (
                            club_member(name, clubs, chain_name, chain_club_names)
                            and alt.key() < pick.key()
                        ):
                            pick = alt
                cur = out.get((cid, exact_id, sid))
                if cur is None or pick.effective_unit_price < cur.effective_unit_price:
                    out[(cid, exact_id, sid)] = _from_option(pick)
                    if offer is not None:
                        offers[(cid, exact_id, sid)] = _from_option(offer)
                    else:
                        offers.pop((cid, exact_id, sid), None)
    return out, offers
