"""Regenerate the SYNTHETIC transparency-file fixtures.

The chain portals are not reachable from the build container, so these fixtures are synthetic.
They follow the real layouts as encoded in the pinned upstream parsers
(il-supermarket-parser 1.0.12) and the regulation's uniform structure, with Hebrew names,
real chain ids, weighed items, a club promo and a buy-X-get-Y promo. Replace them with real
files from ``smartcart_ingest/adapters/fetch_fixtures.py`` once the Israeli VPS exists.

Run from the repo root:  uv run python services/ingest/tests/fixtures/build_synthetic.py
Output is deterministic (gzip mtime 0, fixed zip timestamps). ``expected.json`` in each chain
folder holds the literal regression expectations; they are written here by hand, not computed.
"""

from __future__ import annotations

import gzip
import io
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DECL = '<?xml version="1.0" encoding="{enc}"?>\n'


# --------------------------------------------------------------------------- containers


def encode(xml: str, encoding: str, *, declare: str | None = None, bom: bool = False) -> bytes:
    """``declare`` is the encoding named in the declaration (None = no declaration)."""
    text = (DECL.format(enc=declare) if declare else "") + xml
    codec = {"utf-16-le": "utf-16-le", "utf-16-be": "utf-16-be"}.get(encoding, encoding)
    data = text.encode(codec)
    if bom:
        data = {
            "utf-8": b"\xef\xbb\xbf",
            "utf-16-le": b"\xff\xfe",
            "utf-16-be": b"\xfe\xff",
        }[encoding] + data
    return data


def gz(data: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as fh:
        fh.write(data)
    return buf.getvalue()


def zipped(members: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 6, 3, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return buf.getvalue()


def write(folder: str, name: str, data: bytes) -> None:
    path = HERE / folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_expected(folder: str, expected: dict) -> None:
    path = HERE / folder / "expected.json"
    path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- XML builders


def el(tag: str, value: object) -> str:
    return f"<{tag}>{value}</{tag}>"


def row(tag: str, fields: dict[str, object]) -> str:
    return f"<{tag}>" + "".join(el(k, v) for k, v in fields.items()) + f"</{tag}>"


# Items: code, type, name, manufacturer, unit_qty, quantity, weighed, uom, price, uom_price
ITEMS = [
    ("7290004131074", 1, "חלב תנובה 3% בקרטון 1 ליטר", "תנובה", "ליטר", "1.00", 0, "ליטר", "7.12", "7.12"),
    ("7290000042442", 1, "קוטג' 5% תנובה 250 גרם", "תנובה", "גרם", "250.00", 0, "100 גרם", "5.90", "2.36"),
    ("7290112337023", 1, "לחם אחיד פרוס אנג'ל 750 גרם", "אנג'ל", "גרם", "750.00", 0, "100 גרם", "8.30", "1.11"),
    ("2000123", 0, "עגבניות שרי במשקל", "לא ידוע", "קילוגרמים", "1.00", 1, "קילו", "12.90", "12.90"),
    ("7290000066318", 1, "במבה אסם 80 גרם", "אסם", "גרם", "80.00", 0, "100 גרם", "4.50", "5.63"),
    ("7290011194246", 1, "שמן קנולה מזולה 1 ליטר", "שמן תעשיות", "ליטר", "1.00", 0, "ליטר", "11.90", "11.90"),
    ("2000456", 0, "בננה במשקל", "לא ידוע", "קילוגרמים", "1.00", 1, "קילו", "8.90", "8.90"),
    ("7290107932158", 1, "שוקולד פרה מריר 100 גרם", "עלית", "גרם", "100.00", 0, "100 גרם", "6.90", "6.90"),
]


def item_fields(
    item: tuple, *, price_delta: str = "0", name_tag: str = "ItemName", big_id: bool = False
) -> dict[str, object]:
    code, itype, name, manu, unit_qty, qty, weighed, uom, price, uom_price = item
    price = f"{float(price) + float(price_delta):.2f}"
    if big_id:  # legacy Matrix (Victory) spelling
        return {
            "PriceUpdateDate": "2026-10-05 22:10:00",
            "ItemCode": code,
            "ItemType": itype,
            "ItemName": name,
            "ManufactureName": manu,
            "ManufactureCountry": "IL",
            "ManufactureItemDescription": name,
            "UnitQty": unit_qty,
            "Quantity": qty,
            "BisWeighted": weighed,
            "UnitMeasure": uom,
            "QtyInPackage": 0,
            "ItemPrice": price,
            "UnitOfMeasurePrice": uom_price,
            "AllowDiscount": 1,
            "itemStatus": 1,
        }
    return {
        "PriceUpdateDate": "2026-10-05 22:01:00",
        "ItemCode": code,
        "ItemType": itype,
        name_tag: name,
        "ManufacturerName": manu,
        "ManufactureCountry": "IL",
        "ManufacturerItemDescription": name,
        "UnitQty": unit_qty,
        "Quantity": qty,
        "bIsWeighted": weighed,
        "UnitOfMeasure": uom,
        "QtyInPackage": 0,
        "ItemPrice": price,
        "UnitOfMeasurePrice": uom_price,
        "AllowDiscount": 1,
        "ItemStatus": 1,
    }


def price_doc(
    chain: str,
    store: str,
    items: list[tuple],
    *,
    root: str = "Root",
    id_case: str = "Id",
    name_tag: str = "ItemName",
    price_delta: str = "0",
    extra_header: str = "",
    container: str = "Items",
    row_tag: str = "Item",
    big_id: bool = False,
) -> str:
    rows = "".join(
        row(row_tag, item_fields(i, price_delta=price_delta, name_tag=name_tag, big_id=big_id))
        for i in items
    )
    schema = (
        '<xs:schema id="NewDataSet" xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="NewDataSet"/></xs:schema>'
        if container == "NewDataSet"
        else ""
    )
    count = f' Count="{len(items)}"' if container == "Items" else ""
    return (
        f"<{root}>{extra_header}"
        + el(f"Chain{id_case}", chain)
        + el(f"SubChain{id_case}", "001")
        + el(f"Store{id_case}", store)
        + el("BikoretNo", 7)
        + el("DllVerNo", "8.0.1.3")
        + f"<{container}{count}>{schema}{rows}</{container}>"
        + f"</{root}>"
    )


def promotion(
    promo_id: str,
    desc: str,
    items: list[tuple[str, int]],
    *,
    club: str = "0",
    min_qty: str = "1",
    max_qty: str = "0",
    discounted: str | None = None,
    discount_type: str = "1",
    rate: str | None = None,
    gift_count: str = "0",
    start: str = "2026-10-01",
    end: str = "2026-10-14",
    start_hour: str = "00:00:00",
    end_hour: str = "23:59:00",
) -> str:
    fields: dict[str, object] = {
        "PromotionId": promo_id,
        "AllowMultipleDiscounts": 1,
        "PromotionDescription": desc,
        "PromotionUpdateDate": "2026-09-30 18:00:00",
        "PromotionStartDate": start,
        "PromotionStartHour": start_hour,
        "PromotionEndDate": end,
        "PromotionEndHour": end_hour,
        "IsWeightedPromo": 0,
        "MinQty": min_qty,
        "MaxQty": max_qty,
        "DiscountType": discount_type,
        "RewardType": 1,
    }
    if rate is not None:
        fields["DiscountRate"] = rate
    if discounted is not None:
        fields["DiscountedPrice"] = discounted
    body = "".join(el(k, v) for k, v in fields.items())
    body += (
        f'<PromotionItems Count="{len(items)}">'
        + "".join(
            row("Item", {"ItemCode": code, "ItemType": 1, "IsGiftItem": gift}) for code, gift in items
        )
        + "</PromotionItems>"
    )
    body += row(
        "AdditionalRestrictions",
        {
            "AdditionalIsCoupon": 0,
            "AdditionalGiftCount": gift_count,
            "AdditionalIsTotal": 0,
            "AdditionalIsActive": 0,
        },
    )
    body += el("Remarks", "")
    body += f"<Clubs>{el('ClubId', club)}</Clubs>"
    return f"<Promotion>{body}</Promotion>"


def standard_promos() -> list[str]:
    return [
        promotion(
            "1001",
            "במבה 2 ב-8 ש\"ח לחברי מועדון",
            [("7290000066318", 0)],
            club="1",
            min_qty="2",
            max_qty="6",
            discounted="8.00",
        ),
        promotion(
            "1002",
            "קוטג' 1+1",
            [("7290000042442", 0)],
            min_qty="2",
            gift_count="1",
        ),
        promotion(
            "1003",
            "20% הנחה על שמן ושוקולד",
            [("7290011194246", 0), ("7290107932158", 0)],
            discount_type="2",
            rate="20",
        ),
        promotion(
            "1004",
            "חלב ב-5.90 בשעות הבוקר",
            [("7290004131074", 0)],
            discounted="5.90",
            start_hour="07:00:00",
            end_hour="12:00:00",
        ),
    ]


def promo_doc(
    chain: str,
    store: str,
    promos: list[str],
    *,
    id_case: str = "Id",
    root: str = "Root",
) -> str:
    return (
        f"<{root}>"
        + el(f"Chain{id_case}", chain)
        + el(f"SubChain{id_case}", "001")
        + el(f"Store{id_case}", store)
        + el("BikoretNo", 7)
        + el("DllVerNo", "8.0.1.3")
        + f'<Promotions Count="{len(promos)}">'
        + "".join(promos)
        + "</Promotions>"
        + f"</{root}>"
    )


# stores: (code, type, name, address, city, lat, lon)
def store_fields(store: tuple, store_id_tag: str = "StoreId") -> dict[str, object]:
    code, stype, name, address, city, *coords = store
    fields: dict[str, object] = {
        store_id_tag: code,
        "BikoretNo": 7,
        "StoreType": stype,
        "StoreName": name,
        "Address": address,
        "City": city,
        "ZipCode": "0000000",
    }
    if coords:
        fields["Latitude"], fields["Longitude"] = coords
    return fields


def subchains_doc(
    chain: str,
    chain_name: str,
    subchains: list[tuple[str, str, list[tuple]]],
    *,
    id_case: str = "Id",
    store_id_tag: str = "StoreId",
) -> str:
    body = ""
    for sub_id, sub_name, stores in subchains:
        body += (
            "<SubChain>"
            + el(f"SubChain{id_case}", sub_id)
            + el("SubChainName", sub_name)
            + "<Stores>"
            + "".join(row("Store", store_fields(s, store_id_tag)) for s in stores)
            + "</Stores></SubChain>"
        )
    return (
        "<Root>"
        + el(f"Chain{id_case}", chain)
        + el("ChainName", chain_name)
        + el("LastUpdateDate", "2026-10-06")
        + el("LastUpdateTime", "01:00:00")
        + f"<SubChains>{body}</SubChains>"
        + "</Root>"
    )


# --------------------------------------------------------------------------- chains


def build_shufersal() -> None:
    chain = "7290027600007"
    stores = [
        ("1", 1, "שופרסל שלי", "שופרסל שלי תל אביב - אבן גבירול", "אבן גבירול 101", "תל אביב", "32.0853", "34.7818"),
        ("29", 1, "שופרסל דיל", "שופרסל דיל ירושלים - תלפיות", "האומן 17", "ירושלים", "31.7520", "35.2110"),
        ("90", 1, "שופרסל ONLINE", "מרכז ליקוט מודיעין", "המלאכה 3", "מודיעין", "0", "0"),
        ("137", 1, "שופרסל אקספרס", "שופרסל אקספרס חיפה - מוריה", "מוריה 82", "חיפה", "32.7940", "34.9896"),
        ("260", 1, "BE", "BE באר שבע", "רגר 1", "באר שבע", "31.2518", "34.7913"),
    ]
    store_rows = "".join(
        row(
            "STORE",
            {
                "STOREID": s[0],
                "BIKORETNO": 4,
                "STORETYPE": s[1],
                "CHAINNAME": "שופרסל",
                "SUBCHAINID": i + 1,
                "SUBCHAINNAME": s[2],
                "STORENAME": s[3],
                "ADDRESS": s[4],
                "CITY": s[5],
                "ZIPCODE": "0000000",
                "LATITUDE": s[6],
                "LONGITUDE": s[7],
            },
        )
        for i, s in enumerate(stores)
    )
    stores_xml = (
        '<asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0"><asx:values>'
        + el("CHAINID", chain)
        + el("LASTUPDATEDATE", "20261006")
        + f"<STORES>{store_rows}</STORES></asx:values></asx:abap>"
    )
    f = "shufersal"
    write(f, f"Stores{chain}-000-202610060201.gz", gz(encode(stores_xml, "utf-8", declare="utf-8", bom=True)))
    write(f, f"PriceFull{chain}-001-202610060300.gz", gz(encode(price_doc(chain, "001", ITEMS, root="root"), "utf-8", declare="UTF-8")))
    write(f, f"PromoFull{chain}-001-202610060300.gz", gz(encode(promo_doc(chain, "001", standard_promos(), root="root"), "utf-8", declare="UTF-8")))
    # v2: same layout plus the provisional marker and a field the new model may add.
    v2 = price_doc(
        chain, "001", ITEMS[:3], root="root", extra_header=el("SchemaVersion", "2.0")
    ).replace("<ItemStatus>1</ItemStatus>", "<ItemStatus>1</ItemStatus><UniformPromoRef>0</UniformPromoRef>")
    write(f, f"PriceFull{chain}-001-202610070300.gz", gz(encode(v2, "utf-8", declare="UTF-8")))
    # unknown: a marker with an unrecognised major version.
    v3 = price_doc(chain, "001", ITEMS[:2], root="root", extra_header=el("SchemaVersion", "3.1"))
    write(f, f"PriceFull{chain}-001-202610080300.gz", gz(encode(v3, "utf-8", declare="UTF-8")))
    # corrupt: a truncated gzip download.
    good = gz(encode(price_doc(chain, "001", ITEMS, root="root"), "utf-8", declare="UTF-8"))
    write(f, f"PriceFull{chain}-001-202610090300.gz", good[: len(good) // 2])
    write_expected(
        f,
        {
            "chain_id": chain,
            "files": {
                f"Stores{chain}-000-202610060201.gz": {
                    "kind": "stores",
                    "schema": "v1",
                    "counts": {"stores": 5},
                    "online": ["90"],
                    "checks": {
                        "stores[0].store_code": "1",
                        "stores[0].name": "שופרסל שלי תל אביב - אבן גבירול",
                        "stores[0].city": "תל אביב",
                        "stores[0].lat": "32.0853",
                        "stores[2].lat": "None",
                        "stores[2].channel": "online",
                    },
                },
                f"PriceFull{chain}-001-202610060300.gz": {
                    "kind": "price_full",
                    "schema": "v1",
                    "counts": {"items": 8, "prices": 8},
                    "checks": {
                        "prices[0].store_code": "1",
                        "prices[0].price": "7.12",
                        "prices[0].observed_at": "2026-10-05 22:01:00+03:00",
                        "items[0].barcode": "7290004131074",
                        "items[0].raw_name": "חלב תנובה 3% בקרטון 1 ליטר",
                        "items[3].is_weighed": "True",
                        "items[3].barcode": "None",
                        "items[3].unit": "קילוגרמים",
                        "prices[3].unit_of_measure": "קילו",
                    },
                },
                f"PromoFull{chain}-001-202610060300.gz": {
                    "kind": "promo_full",
                    "schema": "v1",
                    "counts": {"promos": 4},
                    "checks": {
                        "promos[0].club_only": "True",
                        "promos[0].club_name": "מועדון לקוחות",
                        "promos[0].reward_type": "bundle",
                        "promos[0].reward_value": "8.00",
                        "promos[0].min_qty": "2",
                        "promos[0].max_qty": "6",
                        "promos[1].reward_type": "buy_x_get_y",
                        "promos[1].reward_value": "1",
                        "promos[1].club_only": "False",
                        "promos[2].reward_type": "percent",
                        "promos[2].item_codes": "['7290011194246', '7290107932158']",
                        "promos[3].reward_type": "price",
                        "promos[3].hours": "07:00-12:00",
                        "promos[3].starts_at": "2026-10-01 07:00:00+03:00",
                    },
                },
                f"PriceFull{chain}-001-202610070300.gz": {
                    "kind": "price_full",
                    "schema": "v2",
                    "counts": {"items": 3, "prices": 3},
                    "checks": {
                        "prices[0].price": "7.12",
                        "items[0].raw_name": "חלב תנובה 3% בקרטון 1 ליטר",
                    },
                },
                f"PriceFull{chain}-001-202610080300.gz": {"kind": "price_full", "error": "UnknownSchemaError"},
                f"PriceFull{chain}-001-202610090300.gz": {"kind": "price_full", "error": "AdapterError"},
            },
        },
    )


def build_ramilevy() -> None:
    chain = "7290058140886"
    f = "ramilevy"
    stores = subchains_doc(
        chain,
        "רמי לוי",
        [
            (
                "001",
                "רמי לוי",
                [
                    ("039", 1, "רמי לוי תלפיות", "יד חרוצים 10", "ירושלים", "31.7550", "35.2145"),
                    ("012", 1, "רמי לוי מודיעין", "ישפה 7", "מודיעין", "31.8980", "35.0100"),
                    ("331", 1, "רמי לוי מרכז לוגיסטי", "אזור תעשייה שילת", "שילת"),
                    ("055", 1, "רמי לוי חיפה - צ'ק פוסט", "ההסתדרות 54", "חיפה", "32.7900", "35.0300"),
                ],
            )
        ],
    )
    write(f, f"Stores{chain}-202610060100.xml", encode(stores, "utf-16-le", declare="utf-16", bom=True))
    write(f, f"PriceFull{chain}-039-202610060300.gz", gz(encode(price_doc(chain, "039", ITEMS, name_tag="ItemNm", price_delta="-0.20"), "utf-8", declare="utf-8", bom=True)))
    write(f, f"PromoFull{chain}-039-202610060300.gz", gz(encode(promo_doc(chain, "039", standard_promos()), "utf-8", declare="utf-8")))
    unknown = (
        "<Root>" + el("ChainId", chain) + el("StoreId", "039")
        + "<Catalogue><Entry><Code>1</Code></Entry></Catalogue></Root>"
    )
    write(f, f"PriceFull{chain}-039-202610080300.gz", gz(encode(unknown, "utf-8", declare="utf-8")))
    write_expected(
        f,
        {
            "chain_id": chain,
            "files": {
                f"Stores{chain}-202610060100.xml": {
                    "kind": "stores",
                    "schema": "v1",
                    "counts": {"stores": 4},
                    "online": ["331"],
                    "checks": {
                        "stores[0].store_code": "39",
                        "stores[0].name": "רמי לוי תלפיות",
                        "stores[2].lat": "None",
                        "stores[3].lon": "35.03",
                    },
                },
                f"PriceFull{chain}-039-202610060300.gz": {
                    "kind": "price_full",
                    "schema": "v1",
                    "counts": {"items": 8, "prices": 8},
                    "checks": {
                        "prices[0].store_code": "39",
                        "prices[0].price": "6.92",
                        "items[1].raw_name": "קוטג' 5% תנובה 250 גרם",
                        "items[1].quantity": "250.00",
                        "items[1].unit": "גרם",
                        "items[6].is_weighed": "True",
                    },
                },
                f"PromoFull{chain}-039-202610060300.gz": {
                    "kind": "promo_full",
                    "schema": "v1",
                    "counts": {"promos": 4},
                    "checks": {
                        "promos[0].store_code": "39",
                        "promos[0].club_only": "True",
                        "promos[1].reward_type": "buy_x_get_y",
                        "promos[3].ends_at": "2026-10-14 12:00:00+03:00",
                    },
                },
                f"PriceFull{chain}-039-202610080300.gz": {"kind": "price_full", "error": "UnknownSchemaError"},
            },
        },
    )


def build_osherad() -> None:
    chain = "7290103152017"
    f = "osherad"
    stores = subchains_doc(
        chain,
        "אושר עד",
        [
            (
                "001",
                "אושר עד",
                [
                    ("012", 1, "אושר עד בית שמש", "יגאל אלון 3", "בית שמש", "31.7470", "34.9880"),
                    ("003", 1, "אושר עד בני ברק", "ז'בוטינסקי 168", "בני ברק", "32.0930", "34.8390"),
                    ("021", 1, "אושר עד אשדוד", "הנמל 1", "אשדוד", "31.8040", "34.6550"),
                ],
            )
        ],
    )
    write(f, f"Stores{chain}-202610060100.xml", encode(stores, "utf-16-le", declare="utf-16", bom=True))
    write(f, f"PriceFull{chain}-012-202610060300.gz", gz(encode(price_doc(chain, "012", ITEMS[:6], name_tag="ItemNm", price_delta="-0.30"), "utf-8", declare="utf-8")))
    write(f, f"PromoFull{chain}-012-202610060300.gz", gz(encode(promo_doc(chain, "012", standard_promos()[:2]), "utf-8", declare="utf-8")))
    write(f, f"PromoFull{chain}-021-202610060300.gz", gz(encode(promo_doc(chain, "021", []), "utf-8", declare="utf-8")))
    write(f, f"PriceFull{chain}-021-202610060300.gz", gz(encode(price_doc(chain, "021", []), "utf-8", declare="utf-8")))
    write_expected(
        f,
        {
            "chain_id": chain,
            "files": {
                f"Stores{chain}-202610060100.xml": {
                    "kind": "stores",
                    "schema": "v1",
                    "counts": {"stores": 3},
                    "online": [],
                    "checks": {"stores[1].name": "אושר עד בני ברק", "stores[1].store_code": "3"},
                },
                f"PriceFull{chain}-012-202610060300.gz": {
                    "kind": "price_full",
                    "schema": "v1",
                    "counts": {"items": 6, "prices": 6},
                    "checks": {"prices[0].price": "6.82", "prices[3].price": "12.60", "items[3].is_weighed": "True"},
                },
                f"PromoFull{chain}-012-202610060300.gz": {
                    "kind": "promo_full",
                    "schema": "v1",
                    "counts": {"promos": 2},
                    "checks": {"promos[0].reward_type": "bundle", "promos[1].reward_type": "buy_x_get_y"},
                },
                f"PromoFull{chain}-021-202610060300.gz": {
                    "kind": "promo_full",
                    "schema": "v1",
                    "counts": {"promos": 0},
                    "checks": {},
                },
                f"PriceFull{chain}-021-202610060300.gz": {"kind": "price_full", "error": "AdapterError"},
            },
        },
    )


def build_yohananof() -> None:
    chain = "7290803800003"
    f = "yohananof"
    stores = subchains_doc(
        chain,
        "יוחננוף",
        [
            (
                "001",
                "יוחננוף",
                [
                    ("005", 1, "יוחננוף רחובות", "הרצל 200", "רחובות", "31.8940", "34.8110"),
                    ("017", 1, "יוחננוף ראשון לציון", "רוטשילד 30", "ראשון לציון", "31.9640", "34.8040"),
                    ("100", 2, "יוחננוף - מרכז ליקוט", "המדע 2", "יבנה"),
                ],
            )
        ],
    )
    write(f, f"Stores{chain}-202610060100.xml", encode(stores, "utf-8", declare="utf-8"))
    price = encode(price_doc(chain, "005", ITEMS, name_tag="ItemNm", price_delta="0.10"), "utf-8", declare="utf-8")
    # A Cerberus download that keeps the .gz name but is really a zip archive.
    write(f, f"PriceFull{chain}-005-202610060300.gz", zipped([(f"PriceFull{chain}-005-202610060300.xml", price)]))
    write(f, f"PromoFull{chain}-005-202610060300.gz", gz(encode(promo_doc(chain, "005", standard_promos()), "utf-8", declare="utf-8")))
    write_expected(
        f,
        {
            "chain_id": chain,
            "files": {
                f"Stores{chain}-202610060100.xml": {
                    "kind": "stores",
                    "schema": "v1",
                    "counts": {"stores": 3},
                    "online": ["100"],
                    "checks": {"stores[0].name": "יוחננוף רחובות", "stores[2].channel": "online"},
                },
                f"PriceFull{chain}-005-202610060300.gz": {
                    "kind": "price_full",
                    "schema": "v1",
                    "counts": {"items": 8, "prices": 8},
                    "checks": {"prices[0].store_code": "5", "prices[0].price": "7.22", "items[7].manufacturer": "עלית"},
                },
                f"PromoFull{chain}-005-202610060300.gz": {
                    "kind": "promo_full",
                    "schema": "v1",
                    "counts": {"promos": 4},
                    "checks": {"promos[2].reward_value": "20", "promos[2].reward_type": "percent"},
                },
            },
        },
    )


def build_victory() -> None:
    chain = "7290696200003"
    f = "victory"
    branches = "".join(
        row(
            "Branch",
            {
                "ChainID": chain,
                "SubChainID": 1,
                "StoreID": s[0],
                "BikoretNo": 8,
                "StoreType": 1,
                "ChainName": "ויקטורי",
                "SubChainName": "ויקטורי",
                "StoreName": s[1],
                "Address": s[2],
                "City": s[3],
                "ZIPCode": "0000000",
                "LastUpdateDate": "2026-10-06",
                "LastUpdateTime": "01:00:00",
            },
        )
        for s in [
            ("001", "ויקטורי באר יעקב", "הרצל 1", "באר יעקב"),
            ("007", "ויקטורי אשקלון", "בן גוריון 12", "אשקלון"),
            ("045", "ויקטורי אונליין", "", ""),
            ("052", "ויקטורי גדרה", "הבנים 4", "גדרה"),
        ]
    )
    stores_xml = f'<Store Date="06/10/2026" Time="01:00:00"><Branches>{branches}</Branches></Store>'
    write(f, f"Stores{chain}-000-202610060100.xml.gz", gz(encode(stores_xml, "windows-1255", declare="windows-1255")))
    prices = price_doc(
        chain, "001", ITEMS, root="Prices", id_case="ID", container="Products", row_tag="Product",
        big_id=True, price_delta="0.30",
    )
    write(f, f"PriceFull{chain}-001-202610060300.xml.gz", gz(encode(prices, "windows-1255", declare="windows-1255")))

    def sale(item: str, promo_id: str, desc: str, **kw: object) -> str:
        fields: dict[str, object] = {
            "PriceUpdateDate": "2026-09-30 18:00:00",
            "ItemCode": item,
            "ItemType": 1,
            "IsWeightedPromo": 0,
            "PromotionID": promo_id,
            "PromotionDescription": desc,
            "PromotionStartDate": "2026-10-01",
            "PromotionStartHour": "00:00",
            "PromotionEndDate": "2026-10-10",
            "PromotionEndHour": "23:59",
            "MinQty": kw.get("min_qty", "1.00"),
            "MaxQty": "0",
            "DiscountRate": kw.get("rate", ""),
            "DiscountType": kw.get("dtype", "1"),
            "MinPurchaseAmnt": "",
            "MinNoOfItemOfered": kw.get("min_qty", "1"),
            "DiscountedPrice": kw.get("discounted", ""),
            "DiscountedPricePerMida": "",
            "AdditionalIsCoupon": 0,
            "AdditionalGiftCount": kw.get("gift", 0),
            "AdditionalIsTotal": 0,
            "AdditionalMinBasketAmount": "",
            "Remarks": "",
            "ClubID": kw.get("club", 0),
        }
        return row("Sale", fields)

    sales = "".join(
        [
            sale("7290000066318", "55001", "חטיפים 3 ב-12 למועדון", min_qty="3", discounted="12.00", club=1),
            sale("7290107932158", "55001", "חטיפים 3 ב-12 למועדון", min_qty="3", discounted="12.00", club=1),
            sale("7290004131074", "55002", "חלב 1+1", min_qty="2", gift=1),
            sale("7290112337023", "55003", "לחם ב-6.90", discounted="6.90"),
        ]
    )
    promos_xml = (
        "<Promos>" + el("ChainID", chain) + el("SubChainID", 1) + el("StoreID", "001")
        + el("BikoretNo", 8) + f"<Sales>{sales}</Sales></Promos>"
    )
    write(f, f"PromoFull{chain}-001-202610060300.xml.gz", gz(encode(promos_xml, "windows-1255", declare="windows-1255")))
    # laibcatalog new source: regulation Items layout, UTF-8, ChainID casing.
    new_src = price_doc(chain, "007", ITEMS[:4], id_case="ID")
    write(f, f"PriceFull{chain}-007-202610060300.xml.gz", gz(encode(new_src, "utf-8", declare="utf-8")))
    write_expected(
        f,
        {
            "chain_id": chain,
            "files": {
                f"Stores{chain}-000-202610060100.xml.gz": {
                    "kind": "stores",
                    "schema": "v1",
                    "counts": {"stores": 4},
                    "online": ["45"],
                    "checks": {
                        "stores[0].name": "ויקטורי באר יעקב",
                        "stores[0].city": "באר יעקב",
                        "stores[2].address": "None",
                    },
                },
                f"PriceFull{chain}-001-202610060300.xml.gz": {
                    "kind": "price_full",
                    "schema": "v1",
                    "counts": {"items": 8, "prices": 8},
                    "checks": {
                        "prices[0].price": "7.42",
                        "items[0].raw_name": "חלב תנובה 3% בקרטון 1 ליטר",
                        "items[0].manufacturer": "תנובה",
                        "items[3].is_weighed": "True",
                        "prices[1].unit_of_measure": "100 גרם",
                        "prices[0].observed_at": "2026-10-05 22:10:00+03:00",
                    },
                },
                f"PromoFull{chain}-001-202610060300.xml.gz": {
                    "kind": "promo_full",
                    "schema": "v1",
                    "counts": {"promos": 3},
                    "checks": {
                        "promos[0].promo_id": "55001",
                        "promos[0].item_codes": "['7290000066318', '7290107932158']",
                        "promos[0].reward_type": "bundle",
                        "promos[0].club_only": "True",
                        "promos[1].reward_type": "buy_x_get_y",
                        "promos[2].reward_type": "price",
                        "promos[2].reward_value": "6.90",
                        "promos[2].ends_at": "2026-10-10 23:59:00+03:00",
                    },
                },
                f"PriceFull{chain}-007-202610060300.xml.gz": {
                    "kind": "price_full",
                    "schema": "v1",
                    "counts": {"items": 4, "prices": 4},
                    "checks": {"prices[0].store_code": "7", "prices[0].price": "7.12"},
                },
            },
        },
    )


def build_hazihinam() -> None:
    chain = "7290700100008"
    f = "hazihinam"
    stores = subchains_doc(
        chain,
        "חצי חינם",
        [
            (
                "000",
                "חצי חינם",
                [
                    ("207", 1, "חצי חינם חולון", "המרכבה 31", "חולון", "32.0100", "34.7790"),
                    ("201", 1, "חצי חינם הרצליה", "משכית 20", "הרצליה", "32.1650", "34.8100"),
                    ("299", 1, "חצי חינם אתר", "", ""),
                ],
            )
        ],
        id_case="ID",
        store_id_tag="StoreID",
    )
    # Declared ISO-8859-8 over UTF-8 content: a known mis-declaration the decoder must survive.
    write(f, f"Stores{chain}-000-000-20261006-010000.xml.gz", gz(encode(stores, "utf-8", declare="ISO-8859-8")))
    write(f, f"PriceFull{chain}-000-207-20261006-030000.xml.gz", gz(encode(price_doc(chain, "207", ITEMS, price_delta="-0.50"), "utf-8", declare="utf-8")))
    write(f, f"PromoFull{chain}-000-207-20261006-030000.xml.gz", gz(encode(promo_doc(chain, "207", standard_promos()), "utf-8", declare="utf-8")))
    bad = price_doc(chain, "201", ITEMS[:2]).replace("<ItemPrice>7.12</ItemPrice>", "<ItemPrice>abc</ItemPrice>")
    write(f, f"PriceFull{chain}-000-201-20261006-030000.xml.gz", gz(encode(bad, "utf-8", declare="utf-8")))
    write_expected(
        f,
        {
            "chain_id": chain,
            "files": {
                f"Stores{chain}-000-000-20261006-010000.xml.gz": {
                    "kind": "stores",
                    "schema": "v1",
                    "counts": {"stores": 3},
                    "online": ["299"],
                    "checks": {"stores[0].store_code": "207", "stores[0].name": "חצי חינם חולון"},
                },
                f"PriceFull{chain}-000-207-20261006-030000.xml.gz": {
                    "kind": "price_full",
                    "schema": "v1",
                    "counts": {"items": 8, "prices": 8},
                    "checks": {"prices[0].store_code": "207", "prices[0].price": "6.62", "prices[3].price": "12.40"},
                },
                f"PromoFull{chain}-000-207-20261006-030000.xml.gz": {
                    "kind": "promo_full",
                    "schema": "v1",
                    "counts": {"promos": 4},
                    "checks": {"promos[0].club_only": "True", "promos[1].reward_type": "buy_x_get_y"},
                },
                f"PriceFull{chain}-000-201-20261006-030000.xml.gz": {"kind": "price_full", "error": "AdapterError"},
            },
        },
    )


def build_tivtaam() -> None:
    chain = "7290873255550"
    f = "tivtaam"
    stores = subchains_doc(
        chain,
        "טיב טעם",
        [
            (
                "001",
                "טיב טעם",
                [
                    ("002", 1, "טיב טעם רמת גן", "ז'בוטינסקי 100", "רמת גן", "32.0870", "34.8130"),
                    ("014", 1, "טיב טעם חיפה", "ההסתדרות 150", "חיפה", "32.8000", "35.0400"),
                    ("080", 1, "טיב טעם - הזמנות", "מרכז הפצה ראשון לציון", "ראשון לציון"),
                ],
            )
        ],
    )
    write(f, f"Stores{chain}-000-202610060100.gz", gz(encode(stores, "utf-16-be", declare="utf-16", bom=True)))
    nds = price_doc(chain, "002", ITEMS, container="NewDataSet", row_tag="item", price_delta="1.00")
    write(f, f"PriceFull{chain}-002-202610060300.gz", gz(encode(nds, "utf-8", declare="utf-8")))
    write(f, f"PromoFull{chain}-002-202610060300.gz", gz(encode(promo_doc(chain, "002", standard_promos()), "utf-8", declare="utf-8")))
    write_expected(
        f,
        {
            "chain_id": chain,
            "files": {
                f"Stores{chain}-000-202610060100.gz": {
                    "kind": "stores",
                    "schema": "v1",
                    "counts": {"stores": 3},
                    "online": ["80"],
                    "checks": {"stores[1].name": "טיב טעם חיפה", "stores[1].lat": "32.8"},
                },
                f"PriceFull{chain}-002-202610060300.gz": {
                    "kind": "price_full",
                    "schema": "v1",
                    "counts": {"items": 8, "prices": 8},
                    "checks": {"prices[0].store_code": "2", "prices[0].price": "8.12", "items[6].raw_name": "בננה במשקל"},
                },
                f"PromoFull{chain}-002-202610060300.gz": {
                    "kind": "promo_full",
                    "schema": "v1",
                    "counts": {"promos": 4},
                    "checks": {"promos[3].hours": "07:00-12:00"},
                },
            },
        },
    )


def build_mega() -> None:
    chain = "7290055700007"
    f = "mega"
    stores = subchains_doc(
        chain,
        "קרפור",
        [
            (
                "001",
                "קרפור מרקט",
                [
                    ("2960", 1, "קרפור מרקט נווה שאנן", "חנה סנש 14", "חיפה", "32.7790", "35.0170"),
                    ("3012", 1, "קרפור היפר ראשון לציון", "משה בקר 20", "ראשון לציון", "31.9850", "34.7700"),
                ],
            ),
            ("002", "קרפור לוגיסטיקה", [("5000", 1, "קרפור מרכז ליקוט", "השחם 8", "פתח תקווה")]),
        ],
    )
    # windows-1255 bytes with no XML declaration at all.
    write(f, f"Stores{chain}-000-202610060100.gz", gz(encode(stores, "windows-1255")))
    write(f, f"PriceFull{chain}-2960-202610060300.gz", gz(encode(price_doc(chain, "2960", ITEMS, price_delta="0.40"), "utf-8", declare="utf-8")))
    write(f, f"PromoFull{chain}-2960-202610060300.gz", gz(encode(promo_doc(chain, "2960", standard_promos()), "utf-8", declare="utf-8")))
    # kind mismatch: named PriceFull but holds promotions.
    write(f, f"PriceFull{chain}-3012-202610060300.gz", gz(encode(promo_doc(chain, "3012", standard_promos()[:1]), "utf-8", declare="utf-8")))
    write_expected(
        f,
        {
            "chain_id": chain,
            "files": {
                f"Stores{chain}-000-202610060100.gz": {
                    "kind": "stores",
                    "schema": "v1",
                    "counts": {"stores": 3},
                    "online": ["5000"],
                    "checks": {"stores[0].store_code": "2960", "stores[2].name": "קרפור מרכז ליקוט"},
                },
                f"PriceFull{chain}-2960-202610060300.gz": {
                    "kind": "price_full",
                    "schema": "v1",
                    "counts": {"items": 8, "prices": 8},
                    "checks": {"prices[0].store_code": "2960", "prices[0].price": "7.52"},
                },
                f"PromoFull{chain}-2960-202610060300.gz": {
                    "kind": "promo_full",
                    "schema": "v1",
                    "counts": {"promos": 4},
                    "checks": {"promos[0].reward_type": "bundle"},
                },
                f"PriceFull{chain}-3012-202610060300.gz": {"kind": "price_full", "error": "AdapterError"},
            },
        },
    )


# --------------------------------------------------------------------------- xmlutil


def _big_id_promos(promos: list[str]) -> list[str]:
    """Promotions in the BigID spelling the laibcatalog new source uses upstream
    (``PromotionID``, ``ClubID``, ``PromotionUpdateTime``)."""
    return [
        p.replace("PromotionId>", "PromotionID>")
        .replace("ClubId>", "ClubID>")
        .replace("PromotionUpdateDate>", "PromotionUpdateTime>")
        for p in promos
    ]


def build_machsanei_hashuk() -> None:
    """Machsanei Hashuk: laibcatalog new source (upstream MAHSANI_ASHUK_NEW_SOURCE), two chain
    ids. Regulation Items/Promotions/SubChains layout with BigID (``ChainID``) casing, UTF-8,
    ``.xml.gz``. The second chain id publishes a legacy flat ``<Sales>`` promo delta, which the
    upstream converter still accepts as a fallback. Files appear after the 08:00 republish."""
    chain, alias = "7290661400001", "7290633800006"
    f = "machsanei_hashuk"
    stores = subchains_doc(
        chain,
        "מחסני השוק",
        [
            (
                "001",
                "מחסני השוק",
                [
                    ("003", 1, "מחסני השוק בני ברק", "רבי עקיבא 100", "בני ברק", "32.0840", "34.8340"),
                    ("012", 1, "מחסני השוק אשדוד", "הבנים 9", "אשדוד", "31.7990", "34.6480"),
                    ("090", 1, "מחסני השוק אונליין", "", ""),
                ],
            ),
            (
                "002",
                "מחסני השוק בשכונה",
                [("041", 1, "מחסני השוק בשכונה ירושלים", "מלכי ישראל 20", "ירושלים", "31.7890", "35.2150")],
            ),
        ],
        id_case="ID",
        store_id_tag="StoreID",
    )
    write(f, f"Stores{chain}-000-202610060810.xml.gz", gz(encode(stores, "utf-8", declare="utf-8", bom=True)))
    prices = price_doc(chain, "003", ITEMS, id_case="ID", price_delta="-0.20")
    write(f, f"PriceFull{chain}-003-202610060810.xml.gz", gz(encode(prices, "utf-8", declare="utf-8")))
    promos = promo_doc(chain, "003", _big_id_promos(standard_promos()[:3]), id_case="ID")
    write(f, f"PromoFull{chain}-003-202610060810.xml.gz", gz(encode(promos, "utf-8", declare="utf-8")))
    # hourly delta: two prices changed
    delta = price_doc(chain, "003", ITEMS[:2], id_case="ID", price_delta="-0.50")
    write(f, f"Price{chain}-003-202610061110.xml.gz", gz(encode(delta, "utf-8", declare="utf-8")))
    # legacy flat <Sales> promo delta under the second chain id (windows-1255)
    sales = "".join(
        row(
            "Sale",
            {
                "ItemCode": code,
                "ItemType": 1,
                "PromotionID": "77001",
                "PromotionDescription": "במבה וחטיף 2 ב-9",
                "PromotionStartDate": "2026-10-06",
                "PromotionStartHour": "08:00",
                "PromotionEndDate": "2026-10-12",
                "PromotionEndHour": "23:59",
                "MinQty": "2.00",
                "MaxQty": "0",
                "DiscountType": 1,
                "DiscountedPrice": "9.00",
                "AdditionalGiftCount": 0,
                "ClubID": 0,
            },
        )
        for code in ("7290000066318", "7290107932158")
    )
    legacy = (
        "<Promos>" + el("ChainID", alias) + el("SubChainID", 1) + el("StoreID", "003")
        + el("BikoretNo", 8) + f"<Sales>{sales}</Sales></Promos>"
    )
    write(f, f"Promo{alias}-003-202610061110.xml.gz", gz(encode(legacy, "windows-1255", declare="windows-1255")))
    write_expected(
        f,
        {
            "chain_id": chain,
            "files": {
                f"Stores{chain}-000-202610060810.xml.gz": {
                    "kind": "stores",
                    "schema": "v1",
                    "counts": {"stores": 4},
                    "online": ["90"],
                    "checks": {
                        "stores[0].store_code": "3",
                        "stores[0].name": "מחסני השוק בני ברק",
                        "stores[0].lat": "32.084",
                        "stores[2].address": "None",
                        "stores[2].lat": "None",
                        "stores[3].city": "ירושלים",
                    },
                },
                f"PriceFull{chain}-003-202610060810.xml.gz": {
                    "kind": "price_full",
                    "schema": "v1",
                    "counts": {"items": 8, "prices": 8},
                    "checks": {
                        "prices[0].store_code": "3",
                        "prices[0].price": "6.92",
                        "prices[3].price": "12.70",
                        "items[0].barcode": "7290004131074",
                        "items[0].manufacturer": "תנובה",
                        "items[3].barcode": "None",
                        "items[3].is_weighed": "True",
                        "prices[0].observed_at": "2026-10-05 22:01:00+03:00",
                    },
                },
                f"PromoFull{chain}-003-202610060810.xml.gz": {
                    "kind": "promo_full",
                    "schema": "v1",
                    "counts": {"promos": 3},
                    "checks": {
                        "promos[0].promo_id": "1001",
                        "promos[0].reward_type": "bundle",
                        "promos[0].club_only": "True",
                        "promos[1].reward_type": "buy_x_get_y",
                        "promos[2].reward_type": "percent",
                        "promos[2].reward_value": "20",
                        "promos[2].item_codes": "['7290011194246', '7290107932158']",
                    },
                },
                f"Price{chain}-003-202610061110.xml.gz": {
                    "kind": "price",
                    "schema": "v1",
                    "counts": {"items": 2, "prices": 2},
                    "checks": {"prices[0].price": "6.62", "prices[1].price": "5.40"},
                },
                f"Promo{alias}-003-202610061110.xml.gz": {
                    "kind": "promo",
                    "schema": "v1",
                    "counts": {"promos": 1},
                    "checks": {
                        "raw.chain_id": alias,
                        "promos[0].chain_id": alias,
                        "promos[0].promo_id": "77001",
                        "promos[0].item_codes": "['7290000066318', '7290107932158']",
                        "promos[0].reward_type": "bundle",
                        "promos[0].club_only": "False",
                    },
                },
            },
        },
    )


def build_king_store() -> None:
    """King Store: Bina portal (kingstore.binaprojects.com, upstream KING_STORE). Regulation
    Items/Promotions/SubChains layout, ``Id`` casing (upstream BaseFileConverter). Bina serves
    compressed content under names that do not end in ``.gz`` (upstream gzip_utils names King
    Store), so the PriceFull and delta are gzip and the PromoFull a zip, all named ``.xml``.
    PROVISIONAL until a real file is fetched."""
    chain = "7290058108879"
    f = "king_store"
    stores = subchains_doc(
        chain,
        "קינג סטור",
        [
            (
                "001",
                "קינג סטור",
                [
                    ("001", 1, "קינג סטור טייבה", "הראשי 1", "טייבה", "32.2660", "35.0100"),
                    ("002", 1, "קינג סטור טירה", "הראשי 5", "טירה", "32.2340", "34.9500"),
                    ("004", 1, "קינג סטור כפר קאסם", "הראשי 12", "כפר קאסם", "32.1140", "34.9760"),
                ],
            )
        ],
    )
    write(f, f"Stores{chain}-000-202610060500.xml", encode(stores, "utf-8", declare="utf-8"))
    write(f, f"PriceFull{chain}-001-202610060510.xml", gz(encode(price_doc(chain, "001", ITEMS[:7], price_delta="0.10"), "utf-8", declare="utf-8")))
    promo_xml = encode(promo_doc(chain, "001", standard_promos()), "utf-8", declare="utf-8")
    write(f, f"PromoFull{chain}-001-202610060510.xml", zipped([(f"PromoFull{chain}-001-202610060510.xml", promo_xml)]))
    write(f, f"Price{chain}-001-202610061200.xml", gz(encode(price_doc(chain, "001", ITEMS[:3], price_delta="0.40"), "utf-8", declare="utf-8")))
    # a promo delta with no rows is legitimate (no changes this hour)
    write(f, f"Promo{chain}-002-202610061200.xml", gz(encode(promo_doc(chain, "002", []), "utf-8", declare="utf-8")))
    # a truncated download must fail loudly
    good = gz(encode(price_doc(chain, "004", ITEMS), "utf-8", declare="utf-8"))
    write(f, f"PriceFull{chain}-004-202610060510.xml", good[: len(good) // 2])
    write_expected(
        f,
        {
            "chain_id": chain,
            "files": {
                f"Stores{chain}-000-202610060500.xml": {
                    "kind": "stores",
                    "schema": "v1",
                    "counts": {"stores": 3},
                    "online": [],
                    "checks": {
                        "stores[0].store_code": "1",
                        "stores[0].name": "קינג סטור טייבה",
                        "stores[2].city": "כפר קאסם",
                        "stores[2].lon": "34.976",
                    },
                },
                f"PriceFull{chain}-001-202610060510.xml": {
                    "kind": "price_full",
                    "schema": "v1",
                    "counts": {"items": 7, "prices": 7},
                    "checks": {
                        "prices[0].store_code": "1",
                        "prices[0].price": "7.22",
                        "items[0].raw_name": "חלב תנובה 3% בקרטון 1 ליטר",
                        "items[3].is_weighed": "True",
                        "prices[1].unit_of_measure": "100 גרם",
                    },
                },
                f"PromoFull{chain}-001-202610060510.xml": {
                    "kind": "promo_full",
                    "schema": "v1",
                    "counts": {"promos": 4},
                    "checks": {
                        "promos[0].reward_type": "bundle",
                        "promos[0].club_name": "מועדון לקוחות",
                        "promos[1].reward_type": "buy_x_get_y",
                        "promos[2].reward_type": "percent",
                        "promos[3].reward_type": "price",
                        "promos[3].hours": "07:00-12:00",
                    },
                },
                f"Price{chain}-001-202610061200.xml": {
                    "kind": "price",
                    "schema": "v1",
                    "counts": {"items": 3, "prices": 3},
                    "checks": {"prices[0].price": "7.52", "prices[2].price": "8.70"},
                },
                f"Promo{chain}-002-202610061200.xml": {
                    "kind": "promo",
                    "schema": "v1",
                    "counts": {},
                    "checks": {},
                },
                f"PriceFull{chain}-004-202610060510.xml": {"kind": "price_full", "error": "AdapterError"},
            },
        },
    )


def build_xmlutil() -> None:
    f = "xmlutil"
    body = (
        "<Root><ChainId>7290027600007</ChainId><Items Count=\"2\">"
        "<Item><ItemCode>1</ItemCode><ItemName>חלב 3%</ItemName></Item>"
        "<Item><ItemCode>2</ItemCode><ItemName>לחם אחיד</ItemName></Item>"
        "</Items></Root>"
    )
    utf8 = encode(body, "utf-8", declare="utf-8")
    write(f, "utf8.xml", utf8)
    write(f, "utf8_bom.xml", encode(body, "utf-8", declare="utf-8", bom=True))
    write(f, "utf16le_bom.xml", encode(body, "utf-16-le", declare="utf-16", bom=True))
    write(f, "utf16be_bom.xml", encode(body, "utf-16-be", declare="utf-16", bom=True))
    write(f, "utf16le_nobom.xml", encode(body, "utf-16-le", declare="utf-16"))
    write(f, "cp1255.xml", encode(body, "windows-1255", declare="windows-1255"))
    write(f, "cp1255_nodecl.xml", encode(body, "windows-1255"))
    write(f, "iso88598_decl_utf8.xml", encode(body, "utf-8", declare="ISO-8859-8"))
    write(f, "utf8.xml.gz", gz(utf8))
    write(f, "utf8.zip", zipped([("readme.txt", b"not xml"), ("data.xml", utf8)]))
    write(f, "zip_named.gz", zipped([("data.xml", utf8)]))
    write(f, "nested_zip_in_gzip.gz", gz(zipped([("data.xml", utf8)])))
    write(f, "truncated.gz", gz(utf8)[:20])
    write(f, "empty.gz", gz(b""))


def main() -> None:
    build_shufersal()
    build_ramilevy()
    build_osherad()
    build_yohananof()
    build_victory()
    build_hazihinam()
    build_tivtaam()
    build_mega()
    build_machsanei_hashuk()
    build_king_store()
    build_xmlutil()


if __name__ == "__main__":
    main()
