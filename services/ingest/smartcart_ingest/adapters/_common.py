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
"""Regulation ClubId codes (0 = all customers). Unverified against real files; raw kept."""


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
    return FileName(kind=kind, chain_id=match.group("chain"), store_code=store, published_at=published)


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
_DESC_PERCENT = re.compile(r"\d+(?:[.,]\d+)?\s*%")


def promo_parse_confidence(
    reward_type: RewardType,
    *,
    min_qty: Decimal | None,
    gift_count: Decimal | None,
    description: str,
    ends_at: datetime | None,
) -> tuple[float, list[str]]:
    """How sure the adapter is that it read the promo's terms right, in [0, 1], with the reasons
    for every deduction (docs/adapters.md, "Promo parse confidence").

    1.0 means the reward type, the quantity (``MinQty``) and the value (``DiscountedPrice``,
    ``DiscountRate`` with ``DiscountType`` 2, or ``AdditionalGiftCount``) were all explicit in
    the file and the description does not contradict them. The reward is never inferred from
    the description; the description is only a cross-check that lowers the confidence.
    """
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
    if (_DESC_X_PLUS_Y.search(text) and reward_type != "buy_x_get_y") or (
        _DESC_PERCENT.search(text) and reward_type != "percent"
    ):
        score -= 0.3
        reasons.append("description_disagrees")
    return round(score, 2), reasons


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
            raise AdapterError(
                self.chain_id, f"filename {filename!r} is for chain {info.chain_id}"
            )
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

    def _parse_stores(
        self, raw: RawFile, xml: bytes, row_tags: set[str]
    ) -> tuple[int, ParsedFile]:
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
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
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
            items_el = _child(row, "PromotionItems")
            item_rows = [xmlutil.scalar_children(it) for it in items_el] if items_el is not None else []
            if not item_rows and fields.get("itemcode"):
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
            entry = grouped.setdefault(
                key,
                {"fields": fields, "items": [], "gift": False, "clubs": [], "restrictions": {}},
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
            for (store_code, promo_id), entry in grouped.items()
        ]
        return seen, ParsedFile(raw=raw, promos=promos)

    def _promo_record(
        self, raw: RawFile, store_code: str, promo_id: str, entry: dict[str, Any]
    ) -> PromoRecord:
        f: dict[str, str] = entry["fields"]
        restrictions: dict[str, str] = entry["restrictions"]
        min_qty = parse_decimal(f.get("minqty"))
        max_qty = parse_decimal(f.get("maxqty"))
        discounted = parse_decimal(f.get("discountedprice"))
        rate = parse_decimal(f.get("discountrate"))
        gift_count = parse_decimal(
            restrictions.get("additionalgiftcount") or f.get("additionalgiftcount")
        )
        reward_type: RewardType = "other"
        reward_value: Decimal | None = None
        if entry["gift"] or (gift_count is not None and gift_count > 0):
            reward_type = "buy_x_get_y"
            reward_value = gift_count if gift_count else Decimal(1)
        elif discounted is not None:
            reward_type = "bundle" if min_qty is not None and min_qty > 1 else "price"
            reward_value = discounted
        elif rate is not None and f.get("discounttype") == "2":
            reward_type = "percent"
            reward_value = rate
        clubs = [c for c in entry["clubs"] if c != "0"]
        start_hour, end_hour = f.get("promotionstarthour"), f.get("promotionendhour")
        hours = (
            f"{start_hour.strip()[:5]}-{end_hour.strip()[:5]}" if start_hour and end_hour else None
        )
        ends_at = parse_datetime(f.get("promotionenddate"), end_hour)
        description = f.get("promotiondescription", "")
        confidence, confidence_reasons = promo_parse_confidence(
            reward_type,
            min_qty=min_qty,
            gift_count=gift_count,
            description=description,
            ends_at=ends_at,
        )
        return PromoRecord(
            chain_id=raw.chain_id,
            store_code=store_code,
            promo_id=promo_id,
            description=description,
            item_codes=list(entry["items"]),
            starts_at=parse_datetime(f.get("promotionstartdate"), start_hour),
            ends_at=ends_at,
            hours=hours,
            club_only=bool(clubs),
            club_name=CLUB_NAMES.get(clubs[0], f"club {clubs[0]}") if clubs else None,
            min_qty=min_qty,
            max_qty=max_qty if max_qty else None,
            reward_type=reward_type,
            reward_value=reward_value,
            raw={
                **{k: v for k, v in f.items() if k not in ("itemcode", "itemtype", "isgiftitem")},
                "club_ids": list(entry["clubs"]),
                "additional_restrictions": dict(restrictions),
                "confidence": confidence,
                "confidence_reasons": confidence_reasons,
            },
        )
