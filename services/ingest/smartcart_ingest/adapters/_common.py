"""Shared machinery for chains that publish the regulation's uniform XML.

Every phase 0 chain publishes the same three file families defined by the Price Transparency
Regulations (Stores, PriceFull/Price, PromoFull/Promo). They differ in container (gzip, zip,
plain), encoding, element casing (``ChainId`` / ``ChainID`` / ``CHAINID``), row element
(``<Item>``, ``<Product>``, ``<item>``), promo layout (nested ``<Promotion>`` with
``<PromotionItems>`` versus flat per-item ``<Sale>`` rows) and Stores nesting (``SubChains``,
SAP ``asx:abap`` ``STORES``, BigID ``Branches``).

:class:`RegulationAdapter` implements the contract once for all of these. A chain module only
declares its identity, which containers it is expected to use, and its online-store rule.
Upstream library objects never leave this package: field mappings are cross-checked against
``il_supermarket_parsers`` in the tests (see ``_upstream.py``), not imported at parse time.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lxml import etree

from smartcart_ingest import channel as _channel
from smartcart_ingest import xmlutil
from smartcart_ingest.adapters.base import AdapterError, ChainAdapter, UnknownSchemaError
from smartcart_ingest.models import (
    FileKind,
    ItemRecord,
    ParsedFile,
    PriceRecord,
    PromoRecord,
    RawFile,
    RewardType,
    SchemaVersion,
    StoreRecord,
)

try:
    ISRAEL_TZ: Any = ZoneInfo("Asia/Jerusalem")
except ZoneInfoNotFoundError:  # pragma: no cover - only on hosts without tzdata
    ISRAEL_TZ = timezone(timedelta(hours=2), "IST")
"""Timestamps inside the files are Israel local time without an offset."""


# --------------------------------------------------------------------------- schema version


class SchemaMarker(NamedTuple):
    name: str
    major: str


PROVISIONAL_V2_MARKER = SchemaMarker(name="SchemaVersion", major="2")
"""PROVISIONAL best guess at how a file in the authority's improved reporting model will
identify itself. No real new-model file exists yet (October 2026), so this is a placeholder:
a root attribute or a header element named ``SchemaVersion`` (case-insensitive) whose major
version is ``2`` means v2; the same marker with any other major version means unknown.
Change it here, and only here, when the first real new-model file arrives."""


# --------------------------------------------------------------------------- layouts

CONTAINERS: dict[str, tuple[str, str]] = {
    # container element: (file group, row element)
    "Items": ("price", "Item"),
    "Products": ("price", "Product"),
    "NewDataSet": ("price", "item"),
    "Promotions": ("promo", "Promotion"),
    "Sales": ("promo", "Sale"),
    "SubChains": ("stores", "Store"),
    "Stores": ("stores", "Store"),
    "STORES": ("stores", "STORE"),
    "Branches": ("stores", "Branch"),
}
ALL_ROW_TAGS: frozenset[str] = frozenset(row for _group, row in CONTAINERS.values())

KIND_GROUP: dict[str, str] = {
    "stores": "stores",
    "price_full": "price",
    "price": "price",
    "promo_full": "promo",
    "promo": "promo",
}

EMPTY_ALLOWED: frozenset[str] = frozenset({"price", "promo", "promo_full"})
"""Kinds where a file with zero rows is legitimate (a store with no promos, a delta with no
changes). A Stores or PriceFull file with zero rows is always an error."""

CLUB_NAMES: dict[str, str] = {"1": "מועדון לקוחות", "2": "כרטיס אשראי", "3": "אחר"}
"""Fallback names for a bare numeric club code (0 = all customers). The real files do not use
bare codes: they publish ``0``, ``0 - כלל הלקוחות``, ``1 - המועדון החדש`` or an expression such as
``(2=מועדון קרפור אשראי|2=מועדון אפליקציה)`` (see :func:`parse_club`), so the fallback only serves
the older layout, which is unverified."""

_CLUB_CODE = re.compile(r"^(\d+)\s*(?:[-\u2013]\s*(.*))?$")
_CLUB_EXPR_CHARS = re.compile(r"[=|&()]")
_CLUB_ALT = re.compile(r"[|&()]")


class Club(NamedTuple):
    """One reading of a ``ClubID`` value: ``all_customers`` (code 0), or a club ``name``."""

    all_customers: bool
    name: str | None
    expression: bool = False


def _shorten(name: str, limit: int = 120) -> str:
    """A very long club label (Shufersal lists dozens of credit-card clubs after "3 - ") cut to
    ``limit`` characters; the full value stays in ``raw.club_ids``."""
    return name if len(name) <= limit else name[: limit - 1].rstrip() + "\u2026"


def parse_club(value: str) -> Club:
    """Read one ``ClubID`` value from a promotion (verified on real files, 2026-10-21).

    * ``""`` and ``0`` and ``0 - כלל הלקוחות``: every customer (code 0, any label).
    * ``<n>`` and ``<n> - <name>`` (n not 0): a club; the name is the label after the dash, else
      the fallback of :data:`CLUB_NAMES`, else ``club <n>``.
    * anything with ``=``, ``|``, ``&`` or brackets is a boolean expression over clubs, written
      ``<type>=<name>`` or ``"<name>=<type>"`` and joined by ``|`` (any of) and ``&``. It is a club
      restriction; ``name`` lists the distinct club names joined by `` | `` (alternatives), which
      never equals a name a user marked, so the promo stays restricted (safe default), and the
      full text is kept in ``raw``. An ``&`` between bracketed groups (Rami Levy) is an AND that
      no flat name list can express; it is flagged the same way.
    """
    text = value.strip()
    if not text:
        return Club(True, None)
    match = _CLUB_CODE.match(text)
    if match:
        code, label = match.group(1), (match.group(2) or "").strip()
        if int(code) == 0:
            return Club(True, None)
        return Club(False, _shorten(label) or CLUB_NAMES.get(code) or f"club {code}")
    if _CLUB_EXPR_CHARS.search(text):
        names: list[str] = []
        for token in _CLUB_ALT.split(text):
            token = token.strip().strip('"').strip()
            if "=" not in token:
                continue
            left, right = (part.strip().strip('"').strip() for part in token.split("=", 1))
            name = right if left.isdigit() else left
            if name and name not in names:
                names.append(name)
        joined = " | ".join(names)
        if len(joined) > 120:  # King Store lists 18 customer groups; the full text stays in raw
            joined = " | ".join(names[:3]) + f" | +{len(names) - 3}"
        return Club(False, joined or text, True)
    return Club(False, _shorten(text))


def resolve_clubs(values: list[str]) -> tuple[bool, str | None, str | None]:
    """``(club_only, club_name, expression text)`` for the ClubID values of one promotion: club
    only when any value names a club other than 0; the first such club names it."""
    for value in values:
        club = parse_club(value)
        if not club.all_customers:
            return True, club.name, value.strip() if club.expression else None
    return False, None, None


# --------------------------------------------------------------------------- filenames

_FILENAME = re.compile(r"^(?P<prefix>[A-Za-z]+)(?P<chain>\d{13})(?P<rest>(?:-\d+)*)")


@dataclass(frozen=True)
class FileName:
    kind: FileKind
    chain_id: str
    store_code: str | None
    published_at: datetime | None


def kind_from_prefix(prefix: str) -> FileKind | None:
    p = prefix.lower().replace("null", "")
    if p.startswith("promofull"):
        return "promo_full"
    if p.startswith("pricefull"):
        return "price_full"
    if p.startswith("promo"):
        return "promo"
    if p.startswith("price"):
        return "price"
    if p.startswith("store"):
        return "stores"
    return None


def parse_filename(filename: str) -> FileName:
    """Parse a portal filename into kind, chain id, store code and publish time.

    Handles every pattern seen in the upstream scrapers:
    ``PriceFull7290027600007-001-202610060300.gz`` (chain-store-YYYYMMDDHHMM),
    ``Promo7290700100008-000-207-20261006-030000.xml.gz`` (chain-subchain-store-date-time),
    ``Stores7290058140886-202610060100.xml`` (no store segment), and the real Shufersal Stores name
    ``Stores7290027600007-000-20261008-020.gz`` (date, then a three-digit HHM time, the minute in
    tens; seen on the portal on 2026-10-08, provisional until a second day confirms it).
    """
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = base.split(".", 1)[0]
    match = _FILENAME.match(stem)
    if not match:
        raise ValueError(f"filename {base!r} does not match <Kind><13-digit chain id>-...")
    kind = kind_from_prefix(match.group("prefix"))
    if kind is None:
        raise ValueError(f"filename {base!r} has unknown file type {match.group('prefix')!r}")
    parts = [p for p in match.group("rest").split("-") if p]
    published: datetime | None = None
    if parts and len(parts[-1]) in (12, 14):
        published = _parse_compact(parts[-1])
        parts = parts[:-1]
    elif len(parts) >= 2 and len(parts[-2]) == 8 and len(parts[-1]) in (4, 6):
        published = _parse_compact(parts[-2] + parts[-1])
        parts = parts[:-2]
    elif len(parts) >= 2 and len(parts[-2]) == 8 and len(parts[-1]) == 3:
        published = _parse_compact(parts[-2] + parts[-1] + "0")  # HHM, minute in tens
        parts = parts[:-2]
    store = normalize_store_code(parts[-1]) if parts else None
    if kind == "stores" or store == "0":
        store = None
    return FileName(
        kind=kind, chain_id=match.group("chain"), store_code=store, published_at=published
    )


def _parse_compact(value: str) -> datetime:
    fmt = "%Y%m%d%H%M%S" if len(value) == 14 else "%Y%m%d%H%M"
    return datetime.strptime(value, fmt).replace(tzinfo=ISRAEL_TZ)


def normalize_store_code(code: str) -> str:
    """``"039"`` and ``"39"`` are the same store: strip leading zeros from numeric codes."""
    code = code.strip()
    return str(int(code)) if code.isdigit() else code


# --------------------------------------------------------------------------- value parsing

_DT_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y%m%d%H%M%S",
    "%Y%m%d%H%M",
    "%Y%m%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
)


def parse_datetime(value: str | None, hour: str | None = None) -> datetime | None:
    """Parse a file timestamp (Israel local time). ``hour`` is joined to a date-only value."""
    if not value:
        return None
    text = value.strip()
    if hour and hour.strip():
        text = f"{text.split(' ')[0].split('T')[0]} {hour.strip()}"
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=ISRAEL_TZ)
        except ValueError:
            continue
    raise ValueError(f"unrecognised date/time {text!r}")


def parse_decimal(value: str | None) -> Decimal | None:
    if value is None or not value.strip():
        return None
    try:
        return Decimal(value.strip().replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {value!r}") from exc


def _first(fields: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = fields.get(name)
        if value:
            return value
    return None


def _coordinate(value: str | None, low: float, high: float) -> float | None:
    """Coordinates outside Israel's bounding box (0, swapped, garbage) become None."""
    if not value:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if low <= number <= high else None


def containers_in(root: etree._Element) -> set[str]:
    return {name for el in root.iter() if (name := xmlutil.localname(el)) in CONTAINERS}


def header_fields(root: etree._Element) -> dict[str, str]:
    """Scalar header values (ChainId, StoreId, SchemaVersion...) at depth 1 and 2, lowercased."""
    out = xmlutil.scalar_children(root)
    for child in root:
        name = xmlutil.localname(child)
        if len(child) and name not in CONTAINERS and name not in ALL_ROW_TAGS:
            for key, value in xmlutil.scalar_children(child).items():
                out.setdefault(key, value)
    return out


def _ancestor_field(element: etree._Element, field: str) -> str | None:
    node = element.getparent()
    while node is not None:
        for child in node:
            if not len(child) and xmlutil.localname(child).lower() == field:
                return (child.text or "").strip() or None
        node = node.getparent()
    return None


def _child(element: etree._Element, name: str) -> etree._Element | None:
    for child in element:
        if xmlutil.localname(child) == name:
            return child
    return None


# --------------------------------------------------------------------------- promo confidence

PROMO_CONFIDENCE_UNPARSED = 0.1
"""A promo whose reward could not be read from any explicit field (``reward_type = other``).
The deductions below add up to at most 0.8, so a parsed promo always scores above this."""
_DESC_X_PLUS_Y = re.compile(r"\d+\s*\+\s*\d+")
_DESC_PERCENT = re.compile(
    r"(?:הנחה\s*(?:של\s*)?\d+(?:[.,]\d+)?\s*%|\d+(?:[.,]\d+)?\s*%\s*(?:הנחה|על\s)"
    r"|\bב-?\s*\d+(?:[.,]\d+)?\s*%)"
)
"""A percentage the description presents as a discount ("20% הנחה", "50% על השני", "ב-60%"). A bare
``%`` is mostly a product attribute in the real files (3.6% milk fat, 100% juice, 25% cheese), so it
no longer counts."""
_DESC_PERCENT_NUMBER = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_DESC_N_FOR_P = re.compile(r"(\d+)\s*ב[-\s]*(\d+(?:[.,]\d+)?)")
"""``3ב11.90`` / ``2 ב 15``: N units for P, as Rami Levy, Osher Ad, Tiv Taam and King Store write it."""


def promo_parse_confidence(
    reward_type: RewardType,
    *,
    min_qty: Decimal | None,
    gift_count: Decimal | None,
    description: str,
    ends_at: datetime | None,
    reward_value: Decimal | None = None,
    unapplied: str | None = None,
    get_percent: Decimal | None = None,
    mixed_items: bool = False,
) -> tuple[float, list[str]]:
    """How sure the adapter is that it read the promo's terms right, in [0, 1], with the reasons
    for every deduction (docs/adapters.md, "Promo parse confidence").

    1.0 means the reward type, the quantity (``MinQty``) and the value (``DiscountedPrice``,
    ``DiscountRate`` with ``DiscountType`` 2, or ``AdditionalGiftCount``) were all explicit in
    the file and the description does not contradict them. The reward is never inferred from
    the description; the description is only a cross-check that lowers the confidence.
    """
    if unapplied:
        return PROMO_CONFIDENCE_UNPARSED, [unapplied]  # read, but not a plain per-item reward
    if reward_type == "other":
        return PROMO_CONFIDENCE_UNPARSED, ["reward_unparsed"]
    score = 1.0
    reasons: list[str] = []
    if min_qty is None:
        score -= 0.2  # the quantity defaults to 1 (buy X defaults to 1)
        reasons.append("min_qty_missing")
    if reward_type == "buy_x_get_y" and not (gift_count is not None and gift_count > 0):
        score -= 0.2  # only IsGiftItem said so: "get Y" defaults to 1
        reasons.append("gift_count_inferred")
    if ends_at is None:
        score -= 0.1
        reasons.append("end_date_missing")
    text = description or ""
    disagrees = (_DESC_X_PLUS_Y.search(text) and reward_type != "buy_x_get_y") or (
        _DESC_PERCENT.search(text) and reward_type != "percent"
    )
    if reward_type == "buy_x_get_y" and get_percent is not None and reward_value is not None:
        # A two-group "buy X, get Y at P % off": the pair is only read when the description agrees
        # (_pair_terms), so this holds for every pair that reaches here.
        disagrees = not _pair_description_agrees(
            text, min_qty or Decimal(1), reward_value, get_percent
        )
    if mixed_items:
        score -= 0.1  # whether a pair may mix the group's items is not shown by the file
        reasons.append("mixed_items_unverified")
    n_for_p = _DESC_N_FOR_P.search(text)
    if n_for_p and reward_type == "bundle" and reward_value is not None and min_qty is not None:
        n, price = Decimal(n_for_p.group(1)), Decimal(n_for_p.group(2).replace(",", "."))
        # The price must agree, or at least the price per unit (a weighed "2 ב 120" is 1.9 kg for
        # 114 in the fields). A number in a product name ("יין פורטה 26 ב 90") does not count when
        # the stated price is the published one.
        same_unit_price = n > 0 and min_qty > 0 and price / n == reward_value / min_qty
        disagrees = disagrees or not (price == reward_value or same_unit_price)
    if disagrees:
        score -= 0.3
        reasons.append("description_disagrees")
    return round(score, 2), reasons


# --------------------------------------------------------------------------- grouped promotions

_WILDCARD_ITEM = re.compile(r"^0+$")
_FULL_WEEK = frozenset(range(1, 8))
_PACKAGING_CREDIT = re.compile(r"(?:זיכוי|קיזוז)\s+אריזה")
"""Tiv Taam and Yohananof publish packaging credits ("זיכוי אריזה ירקות", "קיזוז אריזה פילה") as
promotions with a 1 to 4 percent reward: a weight adjustment at the till, not a discount on the
shelf price. The description only blocks (never creates) a reward."""
UNAPPLIED_REASONS = (
    "coupon_required",
    "packaging_credit",
    "basket_condition",
    "multi_group",
    "weekday_restricted",
    "reward_type_unhandled",
    "reward_value_unusable",
    "reward_values_differ",
    "redemption_limited",
    "club_in_description",
    "pair_description_disagrees",
)
"""Why a grouped promotion was read but is not applied to a price (``reward_type`` ``other``, the
reason in ``promos.raw->>'unapplied'`` and in ``confidence_reasons``, confidence 0.1)."""


def _safe_decimal(value: str | None) -> Decimal | None:
    """:func:`parse_decimal`, but a malformed number is "missing" instead of an error."""
    try:
        return parse_decimal(value)
    except ValueError:
        return None


_PRICE_TOLERANCE = Decimal("0.011")
_CLUB_WORD = re.compile(r"מועדון")
_MAX_PAIR_QUANTITY = 10


def _common_quantity(items: list[dict[str, str]]) -> Decimal | None:
    """The one ``MinQty`` all ``items`` share, when it is a whole number of at least 1."""
    quantities = {_safe_decimal(i.get("minqty")) for i in items}
    if len(quantities) != 1:
        return None
    (qty,) = quantities
    return qty if qty is not None and qty >= 1 and qty == qty.to_integral_value() else None


def _pair_description_agrees(description: str, x: Decimal, y: Decimal, rate: Decimal) -> bool:
    """Whether the description does not contradict the pair the fields describe: an ``N+M`` must be
    X+Y, and a presented percentage must be the rate. Tiv Taam writes "השני ב 40%" for a reward
    whose ``DiscountRate`` is 60 (verified on 708 items against the store's shelf prices: the
    price is 40 % of the shelf price), so a percentage without the word "הנחה" (discount) is
    also read as the price fraction ``100 - rate``; with "הנחה" it must be the rate itself
    ("ב35% הנחה" on a rate of 65, Yohananof, is a contradiction). Words that say "free" ("N+M")
    cannot go with a rate below 100. A number inside a product name (a fat percentage) is not a
    presented percentage."""
    shown = {Decimal(n.replace(",", ".")) for n in _DESC_PERCENT_NUMBER.findall(description)}
    says_discount = "הנחה" in description
    percent_ok = rate in shown or (not says_discount and 100 - rate in shown)
    if _DESC_PERCENT.search(description) and (rate >= 100 or not percent_ok):
        return False
    plus = _DESC_X_PLUS_Y.search(description)
    if plus:
        left, right = (Decimal(n) for n in re.findall(r"\d+", plus.group(0)))
        if (left, right) != (x, y) or (rate < 100 and not percent_ok):
            return False
    return True


def _pair_terms(groups: list[dict[str, Any]], fields: dict[str, str]) -> dict[str, Any] | str:
    """Read a two-group promotion as "buy X, get Y at a percentage off" (1+1, 2+1, "the second at
    50 %"), or return the reason it is left unapplied.

    Seen in the real files of Shufersal, Rami Levy, Mega, Tiv Taam and Yohananof (2026-10-21): a
    trigger group of ``RewardType`` 0 items (``MinQty`` X, sometimes ``DiscountedPrice`` = the shelf
    price) and a reward group of ``RewardType`` 1 or 10 (``MinQty`` Y, ``DiscountRate`` the
    percentage off, ``DiscountedPrice`` the price after it). "1+1" is rate 100 and price 0, "השני ב
    50%" rate 50 and half the trigger price, "2+1 הזול מבניהם" X = 2, Y = 1, rate 100. The reading
    is the narrowest one the file proves:

    * exactly one trigger group and one reward group, nothing weighed, every ``MinQty`` a whole
      number: X and Y are free (up to 10) only when the rate is 100 and the reward price 0 (nothing
      to price); a percentage off needs X = Y = 1 (the only quantities seen with a price, so the
      price semantics of larger ones are not verified);
    * the rate is the same for every item and the reward price follows from it: with the trigger
      price present, ``reward = trigger x (1 - rate / 100)`` (one agora of tolerance), always a
      positive price below 100 % and exactly 0 at 100 %;
    * only items in **both** groups are linked: such an item pairs with itself (buy it, get another
      of it at the rate), which holds however the store lets a pair mix items. Items only in the
      reward group (Tiv Taam: 2 of 35) need a trigger of another item and are not linked;
    * the description does not contradict the fields (:func:`_pair_description_agrees`), no
      redemption limit (a limit is not applied anywhere), and a description that names a club
      while ``ClubID`` says everyone is left alone (one Tiv Taam "1+1 מועדון").

    The result is ``buy_x_get_y`` with ``min_qty`` X, ``reward_value`` Y and ``get_percent`` the
    rate: pay full for X units, get Y at the rate off, per pack of X + Y.
    """
    trigger = [g for g in groups if {i.get("rewardtype", "") for i in g["items"]} == {"0"}]
    reward = [g for g in groups if g not in trigger]
    if len(trigger) != 1 or len(reward) != 1:
        return "multi_group"
    t_items, r_items = trigger[0]["items"], reward[0]["items"]
    if not t_items or not r_items:
        return "multi_group"
    if {i.get("rewardtype", "") for i in r_items} - {"1", "2", "3", "10"}:
        return "multi_group"
    if any(
        i.get("bisweighted", "0").strip().lower() in ("1", "true") for i in (*t_items, *r_items)
    ):
        return "multi_group"
    if any(_WILDCARD_ITEM.match(i.get("itemcode", "0")) for i in (*t_items, *r_items)):
        return "basket_condition"
    x, y = _common_quantity(t_items), _common_quantity(r_items)
    if x is None or y is None or max(x, y) > _MAX_PAIR_QUANTITY:
        return "multi_group"
    if any(not (i.get("discountrate") or "").strip() for i in r_items):
        return "multi_group"  # a reward by price only ("1+3" with no rate): not a rate we can read
    limit = _safe_decimal(fields.get("redemptionlimit"))
    if limit is not None and limit > 0:
        return "redemption_limited"
    clubid = fields.get("clubid", "").strip()
    description = fields.get("promotiondescription", "")
    if _CLUB_WORD.search(description) and (not clubid or clubid.startswith("0")):
        return "club_in_description"
    trigger_by_code = {i.get("itemcode", ""): i for i in t_items}
    codes: list[str] = []
    rates: set[Decimal] = set()
    for item in r_items:
        code = item.get("itemcode", "")
        mate = trigger_by_code.get(code)
        if mate is None or code in codes:
            continue
        shelf = _safe_decimal(mate.get("discountedprice"))
        price = _safe_decimal(item.get("discountedprice"))
        rate = _safe_decimal(item.get("discountrate"))
        if rate is None or not 0 < rate <= 100 or price is None or price < 0:
            return "reward_value_unusable"
        if rate == 100:
            if price != 0:
                return "reward_values_differ"
        else:
            if (x, y) != (1, 1) or price == 0:
                return "multi_group"
            if (
                shelf is not None
                and shelf > 0
                and abs(shelf * (1 - rate / 100) - price) > (_PRICE_TOLERANCE)
            ):
                return "reward_values_differ"
        rates.add(rate)
        codes.append(code)
    if not codes:
        return "multi_group"
    if len(rates) != 1:
        return "reward_values_differ"
    (rate,) = rates
    if not _pair_description_agrees(description, x, y, rate):
        return "pair_description_disagrees"
    return {
        "item_codes": codes,
        "min_qty": x,
        "max_qty": None,
        "reward_type": "buy_x_get_y",
        "reward_value": y,
        "get_percent": rate,
        "shape": "pair",
        "reward_only_items": len({i.get("itemcode", "") for i in r_items} - set(trigger_by_code)),
    }


def grouped_terms(groups_el: etree._Element, fields: dict[str, str]) -> dict[str, Any]:
    """Read the reward of a promotion in the grouped layout.

    Seen in every real PromoFull of the six reachable chains (2026-10-21)::

        <Promotion> PromotionID, PromotionDescription, PromotionStartDateTime, PromotionEndDateTime,
          PromotionDays, MinNoOfItemOffered, ClubID, AdditionalIsCoupon, ...
          <Groups><Group> GroupID, MinPurchaseAmount, DiscountType
            <PromotionItems><PromotionItem> ItemCode, ItemType, RewardType, MinQty, MaxQty,
              DiscountRate, DiscountedPrice, DiscountedPricePerMida, bIsWeighted

    The reward is on the items. Verified against the stores' own shelf prices (docs/adapters.md):
    for ``RewardType`` 1, 3 and 10, ``DiscountedPrice`` is the total price for ``MinQty`` units and
    ``DiscountRate`` the percentage off ``MinQty`` shelf prices; for a weighed item
    (``bIsWeighted`` 1) ``DiscountedPricePerMida`` is the price per kg. ``RewardType`` 2 is a
    percentage (``DiscountRate`` in percent: 5 is 5 %, 100 is free). ``RewardType`` 0 is a
    condition item (the basket condition of a multi-group promotion), item code all zeros stands
    for "any item".

    Only the plain case is applied to a price: one group, real item codes, no coupon, no minimum
    purchase, no weekday restriction, every item the same reward. Everything else is read but
    left unapplied (``unapplied`` names the reason, one of :data:`UNAPPLIED_REASONS`): applying a
    coupon, a basket threshold or half of a two-group promotion as a shelf discount would show a
    price nobody gets. Returns ``item_codes`` (wildcards removed), ``min_qty``, ``max_qty``,
    ``reward_type``, ``reward_value``, ``unapplied``, ``groups`` (a summary for ``raw``) and
    ``min_purchase``.
    """
    groups: list[dict[str, Any]] = []
    item_codes: list[str] = []
    wildcard = False
    min_purchase: Decimal | None = None
    for group in groups_el:
        if xmlutil.localname(group) != "Group":
            continue
        gf = xmlutil.scalar_children(group)
        items_el = _child(group, "PromotionItems")
        items = [xmlutil.scalar_children(it) for it in items_el] if items_el is not None else []
        amount = _safe_decimal(gf.get("minpurchaseamount"))
        if amount is not None and amount > 0:
            min_purchase = max(min_purchase or amount, amount)
        for item in items:
            code = item.get("itemcode", "")
            if _WILDCARD_ITEM.match(code):
                wildcard = True
            elif code and code not in item_codes:
                item_codes.append(code)
        groups.append({"items": items, "summary": {
            "id": gf.get("groupid"),
            "min_purchase": str(amount) if amount else None,
            "discount_type": gf.get("discounttype") or None,
            "items": len(items),
            "reward_types": sorted({i.get("rewardtype", "") for i in items}),
        }})  # fmt: skip

    out: dict[str, Any] = {
        "item_codes": item_codes,
        "min_qty": None,
        "max_qty": None,
        "reward_type": "other",
        "reward_value": None,
        "unapplied": None,
        "get_percent": None,
        "shape": None,
        "reward_only_items": 0,
        "groups": [g["summary"] for g in groups],
        "min_purchase": min_purchase,
    }
    days = fields.get("promotiondays", "").replace(" ", "")
    try:
        weekdays = {int(d) for d in days.split(",") if d}
    except ValueError:
        weekdays = set()
    if fields.get("additionaliscoupon") == "1":
        out["unapplied"] = "coupon_required"
    elif _PACKAGING_CREDIT.search(fields.get("promotiondescription", "")):
        out["unapplied"] = "packaging_credit"
    elif min_purchase is not None or wildcard:
        out["unapplied"] = "basket_condition"
    elif len(groups) != 1:
        pair = _pair_terms(groups, fields) if len(groups) == 2 else "multi_group"
        if isinstance(pair, str):
            out["unapplied"] = pair
        elif days and weekdays != _FULL_WEEK:
            out["unapplied"] = "weekday_restricted"
        else:
            out.update(pair)
    elif days and weekdays != _FULL_WEEK:
        out["unapplied"] = "weekday_restricted"
    else:
        items = groups[0]["items"]
        reward_types = {i.get("rewardtype", "") for i in items}
        readings: set[tuple[str, Decimal | None, Decimal | None]] = set()
        usable = bool(items)
        for item in items:
            qty = _safe_decimal(item.get("minqty"))
            if qty is not None and 0 < qty < 1:
                qty = Decimal(1)  # a weighed item's 0.01 or 0.1 kg is a step, not a pack size
            price = _safe_decimal(item.get("discountedprice"))
            per_kg = _safe_decimal(item.get("discountedpricepermida"))
            rate = _safe_decimal(item.get("discountrate"))
            weighed = item.get("bisweighted", "0").strip().lower() in ("1", "true")
            if reward_types <= {"1", "3", "10"}:
                if price is None or price <= 0:
                    usable = False
                elif qty is not None and qty > 1:
                    readings.add(("bundle", price, qty))  # N units (kg) for the total price
                elif weighed:
                    readings.add(("price", per_kg if per_kg and per_kg > 0 else price, qty))
                else:
                    readings.add(("price", price, qty))
            elif reward_types == {"2"}:
                if rate is None or not 0 < rate < 100:
                    usable = False
                else:
                    readings.add(("percent", rate, qty))
        if not items or not (reward_types <= {"1", "3", "10"} or reward_types == {"2"}):
            out["unapplied"] = "reward_type_unhandled"
        elif not usable:
            out["unapplied"] = "reward_value_unusable"
        elif len(readings) != 1:
            out["unapplied"] = "reward_values_differ"
        else:
            kind, value, qty = next(iter(readings))
            out.update(reward_type=kind, reward_value=value, min_qty=qty)
            maxima = [m for i in items if (m := _safe_decimal(i.get("maxqty")))]
            out["max_qty"] = maxima[0] if maxima else None
    return out


# --------------------------------------------------------------------------- adapter base


class RegulationAdapter(ChainAdapter):
    """Contract implementation for the regulation's uniform XML, configured per chain."""

    slug: ClassVar[str]
    """Folder name under tests/fixtures and module name."""
    chain_ids: ClassVar[tuple[str, ...]] = ()
    """Extra chain ids published under the same adapter (Victory has two)."""
    containers: ClassVar[frozenset[str]] = frozenset({"Items", "Promotions", "SubChains", "Stores"})
    """Container elements this chain is known to use. Anything else is an unknown schema."""
    upstream_parsers: ClassVar[tuple[str, ...]] = ()
    """il_supermarket_parsers ParserFactory names, for the layout cross-check test."""
    upstream_scraper: ClassVar[str | None] = None
    """il_supermarket_scarper ScraperFactory name, used by fetch_fixtures.py."""
    online_name_markers: ClassVar[tuple[str, ...]] = ()
    online_address_markers: ClassVar[tuple[str, ...]] = ()
    online_subchain_markers: ClassVar[tuple[str, ...]] = ()
    online_store_codes: ClassVar[frozenset[str]] = frozenset()
    has_online_record: ClassVar[bool | None] = None
    """True / False / None (unknown until a real Stores file is checked)."""

    @classmethod
    def accepted_chain_ids(cls) -> tuple[str, ...]:
        return (cls.chain_id, *cls.chain_ids)

    # -- contract -----------------------------------------------------------------------

    def detect_kind(self, filename: str) -> FileKind:
        info = self.parse_filename(filename)
        return info.kind

    def detect_schema(self, xml_root: Any) -> SchemaVersion:
        marker = self._marker_value(xml_root)
        if marker is not None:
            major = marker.strip().split(".", 1)[0]
            return "v2" if major == PROVISIONAL_V2_MARKER.major else "unknown"
        return "v1" if containers_in(xml_root) & self.containers else "unknown"

    def online_store_rule(self, store: StoreRecord) -> bool:
        name = store.name.casefold()
        if any(marker.casefold() in name for marker in self.online_name_markers):
            return True
        address = (store.address or "").casefold()
        if any(marker.casefold() in address for marker in self.online_address_markers):
            return True
        return store.store_code in self.online_store_codes

    def parse(self, raw: RawFile, data: bytes) -> ParsedFile:
        where = raw.path or raw.kind
        if raw.chain_id not in self.accepted_chain_ids():
            raise AdapterError(self.chain_id, f"{where}: file belongs to chain {raw.chain_id}")
        try:
            decoded = xmlutil.decode(data)
            root = xmlutil.read_header(decoded.data, ALL_ROW_TAGS)
        except xmlutil.XmlDecodeError as exc:
            raise AdapterError(self.chain_id, f"{where}: {exc}") from exc

        schema = self.detect_schema(root)
        if schema == "unknown":
            found = ", ".join(sorted(containers_in(root))) or "none"
            raise UnknownSchemaError(
                self.chain_id,
                f"{where}: unrecognised schema (root <{xmlutil.localname(root)}>, "
                f"containers: {found}); file must not be loaded",
            )
        header = header_fields(root)
        file_chain = header.get("chainid")
        if file_chain and file_chain not in self.accepted_chain_ids():
            raise AdapterError(self.chain_id, f"{where}: header ChainId is {file_chain}")
        row_tags = self._row_tags_for(raw.kind, root, where)
        out_raw = raw.model_copy(update={"schema_version": schema})

        try:
            group = KIND_GROUP[raw.kind]
            if group == "stores":
                seen, parsed = self._parse_stores(out_raw, decoded.data, row_tags)
                produced = len(parsed.stores)
            elif group == "price":
                seen, parsed = self._parse_prices(out_raw, decoded.data, row_tags, header)
                produced = len(parsed.prices)
            else:
                seen, parsed = self._parse_promos(out_raw, decoded.data, row_tags, header)
                produced = len(parsed.promos)
        except AdapterError:
            raise
        except (xmlutil.XmlDecodeError, ValueError) as exc:
            raise AdapterError(self.chain_id, f"{where}: {exc}") from exc

        if seen and not produced:
            raise AdapterError(self.chain_id, f"{where}: {seen} rows but no records parsed")
        if not seen and raw.kind not in EMPTY_ALLOWED:
            raise AdapterError(self.chain_id, f"{where}: {raw.kind} file has no rows")
        return parsed

    # -- helpers for loaders and tests -----------------------------------------------------

    def parse_filename(self, filename: str) -> FileName:
        try:
            info = parse_filename(filename)
        except ValueError as exc:
            raise AdapterError(self.chain_id, str(exc)) from exc
        if info.chain_id not in self.accepted_chain_ids():
            raise AdapterError(self.chain_id, f"filename {filename!r} is for chain {info.chain_id}")
        return info

    def raw_file_for(self, filename: str, data: bytes, path: str | None = None) -> RawFile:
        """Build the RawFile a loader would create for ``filename`` (schema still unknown)."""
        info = self.parse_filename(filename)
        return RawFile(
            chain_id=info.chain_id,
            store_code=info.store_code,
            kind=info.kind,
            published_at=info.published_at or datetime.now(ISRAEL_TZ),
            sha256=hashlib.sha256(data).hexdigest(),
            path=path or filename,
        )

    # -- internals ----------------------------------------------------------------------

    @staticmethod
    def _marker_value(root: etree._Element) -> str | None:
        wanted = PROVISIONAL_V2_MARKER.name.lower()
        for key, value in root.attrib.items():
            if etree.QName(key).localname.lower() == wanted:
                return str(value)
        return header_fields(root).get(wanted)

    def _row_tags_for(self, kind: FileKind, root: etree._Element, where: str) -> set[str]:
        group = KIND_GROUP[kind]
        matching = {c for c in containers_in(root) if CONTAINERS[c][0] == group}
        if not matching:
            found = ", ".join(sorted(containers_in(root))) or "none"
            raise AdapterError(
                self.chain_id, f"{where}: content does not match kind {kind} (containers: {found})"
            )
        return {CONTAINERS[c][1] for c in matching}

    def _check_row_chain(self, fields: dict[str, str], where: str) -> None:
        row_chain = fields.get("chainid")
        if row_chain and row_chain not in self.accepted_chain_ids():
            raise AdapterError(self.chain_id, f"{where}: row ChainId is {row_chain}")

    def _parse_stores(self, raw: RawFile, xml: bytes, row_tags: set[str]) -> tuple[int, ParsedFile]:
        stores: list[StoreRecord] = []
        seen = 0
        for index, row in enumerate(xmlutil.iter_rows(xml, row_tags)):
            seen += 1
            fields = xmlutil.scalar_children(row)
            self._check_row_chain(fields, f"store row {index}")
            code = normalize_store_code(fields.get("storeid", ""))
            name = fields.get("storename")
            if not code or not name:
                raise ValueError(f"store row {index}: missing StoreId or StoreName")
            sub_chain = fields.get("subchainname") or _ancestor_field(row, "subchainname") or ""
            declared_online = fields.get("storetype") == "2" or any(
                marker.casefold() in sub_chain.casefold() for marker in self.online_subchain_markers
            )
            store = StoreRecord(
                chain_id=raw.chain_id,
                store_code=code,
                name=name,
                address=fields.get("address") or None,
                city=fields.get("city") or None,
                lat=_coordinate(_first(fields, "latitude", "lat"), 29.0, 33.5),
                lon=_coordinate(_first(fields, "longitude", "lon", "lng"), 34.0, 36.0),
                channel="online" if declared_online else "physical",
            )
            stores.append(_channel.tag_channel(self, store))
        return seen, ParsedFile(raw=raw, stores=stores)

    def _parse_prices(
        self, raw: RawFile, xml: bytes, row_tags: set[str], header: dict[str, str]
    ) -> tuple[int, ParsedFile]:
        items: list[ItemRecord] = []
        prices: list[PriceRecord] = []
        seen = 0
        header_store = header.get("storeid") or raw.store_code or ""
        for index, row in enumerate(xmlutil.iter_rows(xml, row_tags)):
            seen += 1
            fields = xmlutil.scalar_children(row)
            self._check_row_chain(fields, f"item row {index}")
            code = fields.get("itemcode", "")
            if not code:
                raise ValueError(f"item row {index}: missing ItemCode")
            store_code = normalize_store_code(fields.get("storeid") or header_store)
            if not store_code:
                raise ValueError(f"item row {index}: no StoreId in header, row or filename")
            name = _first(fields, "itemname", "itemnm", "itemdesc")
            if not name:
                raise ValueError(f"item row {index} ({code}): missing ItemName")
            price = parse_decimal(fields.get("itemprice"))
            if price is None:
                raise ValueError(f"item row {index} ({code}): missing ItemPrice")
            item_type = fields.get("itemtype", "1")
            is_barcode = item_type != "0" and code.isdigit() and 8 <= len(code) <= 14
            quantity = parse_decimal(fields.get("quantity"))
            items.append(
                ItemRecord(
                    chain_id=raw.chain_id,
                    item_code=code,
                    barcode=code if is_barcode else None,
                    raw_name=name,
                    manufacturer=_first(fields, "manufacturername", "manufacturename"),
                    quantity=quantity if quantity else None,
                    unit=fields.get("unitqty") or None,
                    is_weighed=fields.get("bisweighted", "0").lower() in ("1", "true"),
                )
            )
            prices.append(
                PriceRecord(
                    chain_id=raw.chain_id,
                    store_code=store_code,
                    item_code=code,
                    price=price,
                    unit_price=parse_decimal(fields.get("unitofmeasureprice")),
                    unit_of_measure=_first(fields, "unitofmeasure", "unitmeasure"),
                    observed_at=parse_datetime(fields.get("priceupdatedate")) or raw.published_at,
                )
            )
        return seen, ParsedFile(raw=raw, items=items, prices=prices)

    def _parse_promos(
        self, raw: RawFile, xml: bytes, row_tags: set[str], header: dict[str, str]
    ) -> tuple[int, ParsedFile]:
        header_store = header.get("storeid") or raw.store_code or ""
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        seen = 0
        for index, row in enumerate(xmlutil.iter_rows(xml, row_tags)):
            seen += 1
            fields = xmlutil.scalar_children(row)
            self._check_row_chain(fields, f"promo row {index}")
            promo_id = fields.get("promotionid", "")
            if not promo_id:
                raise ValueError(f"promo row {index}: missing PromotionId")
            store_code = normalize_store_code(fields.get("storeid") or header_store)
            if not store_code:
                raise ValueError(f"promo row {index}: no StoreId in header, row or filename")
            groups_el = _child(row, "Groups")
            terms = grouped_terms(groups_el, fields) if groups_el is not None else None
            items_el = _child(row, "PromotionItems")
            if terms is not None:
                item_rows = [{"itemcode": code} for code in terms["item_codes"]]
            elif items_el is not None:
                item_rows = [xmlutil.scalar_children(it) for it in items_el]
            else:
                item_rows = []
            if not item_rows and terms is None and fields.get("itemcode"):
                item_rows = [fields]  # flat <Sale> rows carry one item each
            restrictions_el = _child(row, "AdditionalRestrictions")
            restrictions = (
                xmlutil.scalar_children(restrictions_el) if restrictions_el is not None else {}
            )
            clubs = [
                (el.text or "").strip()
                for el in row.iter()
                if xmlutil.localname(el).lower() == "clubid" and (el.text or "").strip()
            ]
            key = (store_code, promo_id)
            entry = merged.setdefault(
                key,
                {
                    "fields": fields,
                    "items": [],
                    "gift": False,
                    "clubs": [],
                    "restrictions": {},
                    "terms": terms,
                },
            )
            for item in item_rows:
                code = item.get("itemcode")
                if code and code not in entry["items"]:
                    entry["items"].append(code)
                if item.get("isgiftitem") == "1":
                    entry["gift"] = True
            entry["clubs"].extend(c for c in clubs if c not in entry["clubs"])
            entry["restrictions"].update(restrictions)

        promos = [
            self._promo_record(raw, store_code, promo_id, entry)
            for (store_code, promo_id), entry in merged.items()
        ]
        return seen, ParsedFile(raw=raw, promos=promos)

    def _promo_record(
        self, raw: RawFile, store_code: str, promo_id: str, entry: dict[str, Any]
    ) -> PromoRecord:
        f: dict[str, str] = entry["fields"]
        restrictions: dict[str, str] = entry["restrictions"]
        terms: dict[str, Any] | None = entry["terms"]
        gift_count: Decimal | None = None
        unapplied: str | None = None
        reward_type: RewardType = "other"
        reward_value: Decimal | None = None
        if terms is not None:
            # The grouped layout (Groups/Group/PromotionItems/PromotionItem): the reward lives on
            # the items, see grouped_terms.
            min_qty, max_qty = terms["min_qty"], terms["max_qty"]
            reward_type, reward_value = terms["reward_type"], terms["reward_value"]
            unapplied = terms["unapplied"]
            if terms["shape"] == "pair":
                gift_count = reward_value  # "get Y" is explicit in the reward group
        else:
            min_qty = parse_decimal(f.get("minqty"))
            max_qty = parse_decimal(f.get("maxqty"))
            discounted = parse_decimal(f.get("discountedprice"))
            rate = parse_decimal(f.get("discountrate"))
            gift_count = parse_decimal(
                restrictions.get("additionalgiftcount") or f.get("additionalgiftcount")
            )
            if entry["gift"] or (gift_count is not None and gift_count > 0):
                reward_type = "buy_x_get_y"
                reward_value = gift_count if gift_count else Decimal(1)
            elif discounted is not None:
                reward_type = "bundle" if min_qty is not None and min_qty > 1 else "price"
                reward_value = discounted
            elif rate is not None and f.get("discounttype") == "2":
                reward_type = "percent"
                reward_value = rate
        club_only, club_name, club_expression = resolve_clubs(entry["clubs"])
        start_dt, end_dt = f.get("promotionstartdatetime"), f.get("promotionenddatetime")
        start_hour, end_hour = f.get("promotionstarthour"), f.get("promotionendhour")
        if start_dt or end_dt:
            # Date-time layout (verified): the Start/EndHour elements only repeat the time of day
            # of the date-times, they are not a daily window.
            starts_at, ends_at, hours = parse_datetime(start_dt), parse_datetime(end_dt), None
        else:
            starts_at = parse_datetime(f.get("promotionstartdate"), start_hour)
            ends_at = parse_datetime(f.get("promotionenddate"), end_hour)
            hours = (
                f"{start_hour.strip()[:5]}-{end_hour.strip()[:5]}"
                if start_hour and end_hour
                else None
            )
        description = f.get("promotiondescription", "")
        confidence, confidence_reasons = promo_parse_confidence(
            reward_type,
            min_qty=min_qty,
            gift_count=gift_count,
            description=description,
            ends_at=ends_at,
            reward_value=reward_value,
            unapplied=unapplied,
            get_percent=terms["get_percent"] if terms is not None else None,
            mixed_items=terms is not None and terms["shape"] == "pair" and len(entry["items"]) > 1,
        )
        # Flat <Sale> rows carry one item each; the grouped layout has IsGiftItem on the promotion.
        skipped = (
            ("itemcode", "itemtype")
            if terms is not None
            else ("itemcode", "itemtype", "isgiftitem")
        )
        extra: dict[str, Any] = {}
        if terms is not None:
            extra = {"layout": "grouped", "groups": terms["groups"], "unapplied": unapplied}
            if terms["shape"] == "pair":
                extra["shape"] = "pair"
                extra["get_percent"] = str(terms["get_percent"])
                extra["reward_only_items"] = terms["reward_only_items"]
            if terms["min_purchase"] is not None:
                extra["min_purchase_amount"] = str(terms["min_purchase"])
        if club_expression:
            extra["club_expression"] = club_expression
        return PromoRecord(
            chain_id=raw.chain_id,
            store_code=store_code,
            promo_id=promo_id,
            description=description,
            item_codes=list(entry["items"]),
            starts_at=starts_at,
            ends_at=ends_at,
            hours=hours,
            club_only=club_only,
            club_name=club_name,
            min_qty=min_qty,
            max_qty=max_qty if max_qty else None,
            reward_type=reward_type,
            reward_value=reward_value,
            raw={
                **{k: v for k, v in f.items() if k not in skipped},
                "club_ids": list(entry["clubs"]),
                "additional_restrictions": dict(restrictions),
                **extra,
                "confidence": confidence,
                "confidence_reasons": confidence_reasons,
            },
        )
