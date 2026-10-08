"""A scaled SYNTHETIC world of transparency files for the load test (``scripts/loadtest/run.py``).

Written with the adapters' own fixture builders (``services/ingest/tests/fixtures/
build_synthetic.py``: ``subchains_doc``, ``price_doc``, ``promotion``, ``promo_doc``, ``encode``,
``gz``, ``zipped``), in each chain's dialect as the regression fixtures write it, so every file
takes the production path through the adapters, the quality gates and the loader. Nothing here is
an observation: prices, stores, brands and barcodes are generated from a fixed seed.

Default shape (``--small`` is the CI-sized variant, see ``run.py``):

| Thing | Default | How |
|---|---|---|
| Stores | 300, 30 per chain over the ten D13 chains | 45 % in Gush Dan (so a 5 km radius holds tens of stores), the rest in eight other cities |
| Items | 5,000 rows, 500 per chain, mapped to the 245 canonicals | per non-weighed canonical two brands at the canonical pack size (``any_brand``) and, for some, a third pack size (``close``); one weighed item per kg canonical; national brands share a barcode across chains |
| Price history | 90 days | a publication day per store every 7 days from day -90: the day's PriceFull (about 4 % of the store's items changed by up to 10 % since the last one), then a Price delta with about 2 % more (a delta is held until its store's full file of that day loads, so a delta day needs a full file) |
| Promotions | about 20 % of each store's items | a PromoFull per store yesterday, valid from 6 days before to 13 days after: unit price, percent, 1+1 / 2+1, "N for X", 15 % club-only |

    uv run python scripts/loadtest/world.py OUT_DIR [--small] [--seed 7]

Writes ``OUT_DIR/<slug>/<file>`` and ``OUT_DIR/answer_key.json``: for every (chain id, item
code) the canonical slug and flexibility level it was generated from, which ``run.py`` feeds to the
review step (``review_app.accept``) in place of the judge, as ``scripts/demo/review.py`` does.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from types import ModuleType
from zoneinfo import ZoneInfo

import yaml

REPO = Path(__file__).resolve().parents[2]
BUILDER = REPO / "services" / "ingest" / "tests" / "fixtures" / "build_synthetic.py"
CANONICALS = REPO / "data" / "canonicals.yaml"
ISRAEL = ZoneInfo("Asia/Jerusalem")

# Dates the builders hard-code; replaced per file (see _redate).
BUILDER_PRICE_DATES = ("2026-10-05 22:01:00", "2026-10-05 22:10:00")
BUILDER_PROMO_UPDATE = "2026-09-30 18:00:00"

BRANDS = ["שדות", "גבעה", "נוף הגליל", "אלון", "תמר", "רימון", "דקל", "ארז", "כרמל", "יערה"]

# Cities: (name, lat, lon, spread in degrees). Gush Dan first; its weight is set in build().
GUSH_DAN = [
    ("תל אביב", 32.075, 34.785, 0.020),
    ("רמת גן", 32.082, 34.815, 0.012),
    ("גבעתיים", 32.071, 34.810, 0.006),
    ("בני ברק", 32.087, 34.835, 0.008),
    ("חולון", 32.015, 34.780, 0.012),
    ("בת ים", 32.020, 34.750, 0.008),
    ("פתח תקווה", 32.090, 34.880, 0.015),
    ("הרצליה", 32.165, 34.835, 0.012),
]
ELSEWHERE = [
    ("ירושלים", 31.775, 35.210, 0.030),
    ("חיפה", 32.800, 35.000, 0.025),
    ("באר שבע", 31.250, 34.790, 0.020),
    ("אשדוד", 31.800, 34.650, 0.015),
    ("נתניה", 32.320, 34.860, 0.015),
    ("ראשון לציון", 31.970, 34.790, 0.015),
    ("רחובות", 31.895, 34.810, 0.010),
    ("מודיעין", 31.900, 35.010, 0.010),
]


@dataclass(frozen=True)
class Chain:
    slug: str
    chain_id: str
    name: str
    stores: str  # "sap" (Shufersal) or "subchains"
    stores_name: str
    stores_encoding: tuple[str, str | None, bool]  # codec, declared name, BOM
    file_name: str  # price and promo files, {kind}{chain}-{store}-{stamp}
    wrap: str  # gz, zip
    price_kw: dict = field(default_factory=dict)
    promo_kw: dict = field(default_factory=dict)
    subchains_kw: dict = field(default_factory=dict)
    big_id_promos: bool = False
    hyphen_stamp: bool = False  # Hazi Hinam: YYYYMMDD-HHMMSS


# Each chain's dialect, as its build_<slug>() fixture writes it (Victory uses its laibcatalog new
# source layout, the one with store coordinates).
CHAINS = [
    Chain("shufersal", "7290027600007", "שופרסל", "sap", "Stores{c}-000-{t}.gz",
          ("utf-8", "utf-8", True), "{k}{c}-{s}-{t}.gz", "gz",
          price_kw={"root": "root"}, promo_kw={"root": "root"}),
    Chain("ramilevy", "7290058140886", "רמי לוי", "subchains", "Stores{c}-{t}.xml",
          ("utf-16-le", "utf-16", True), "{k}{c}-{s}-{t}.gz", "gz",
          price_kw={"name_tag": "ItemNm"}),
    Chain("osherad", "7290103152017", "אושר עד", "subchains", "Stores{c}-{t}.xml",
          ("utf-16-le", "utf-16", True), "{k}{c}-{s}-{t}.gz", "gz",
          price_kw={"name_tag": "ItemNm"}),
    Chain("yohananof", "7290803800003", "יוחננוף", "subchains", "Stores{c}-{t}.xml",
          ("utf-8", "utf-8", False), "{k}{c}-{s}-{t}.gz", "zip",
          price_kw={"name_tag": "ItemNm"}),
    Chain("victory", "7290696200003", "ויקטורי", "subchains", "Stores{c}-000-{t}.xml.gz",
          ("utf-8", "utf-8", False), "{k}{c}-{s}-{t}.xml.gz", "gz",
          price_kw={"id_case": "ID"}, promo_kw={"id_case": "ID"},
          subchains_kw={"id_case": "ID", "store_id_tag": "StoreID"}, big_id_promos=True),
    Chain("hazihinam", "7290700100008", "חצי חינם", "subchains", "Stores{c}-000-000-{t}.xml.gz",
          ("utf-8", "utf-8", False), "{k}{c}-000-{s}-{t}.xml.gz", "gz",
          subchains_kw={"id_case": "ID", "store_id_tag": "StoreID"}, hyphen_stamp=True),
    Chain("tivtaam", "7290873255550", "טיב טעם", "subchains", "Stores{c}-000-{t}.gz",
          ("utf-16-be", "utf-16", True), "{k}{c}-{s}-{t}.gz", "gz",
          price_kw={"container": "NewDataSet", "row_tag": "item"}),
    Chain("mega", "7290055700007", "קרפור", "subchains", "Stores{c}-000-{t}.gz",
          ("windows-1255", None, False), "{k}{c}-{s}-{t}.gz", "gz"),
    Chain("machsanei_hashuk", "7290661400001", "מחסני השוק", "subchains",
          "Stores{c}-000-{t}.xml.gz", ("utf-8", "utf-8", True), "{k}{c}-{s}-{t}.xml.gz", "gz",
          price_kw={"id_case": "ID"}, promo_kw={"id_case": "ID"},
          subchains_kw={"id_case": "ID", "store_id_tag": "StoreID"}, big_id_promos=True),
    Chain("king_store", "7290058108879", "קינג סטור", "subchains", "Stores{c}-000-{t}.xml",
          ("utf-8", "utf-8", False), "{k}{c}-{s}-{t}.xml", "gz"),
]  # fmt: skip


@dataclass(frozen=True)
class Shape:
    stores_per_chain: int = 30
    items_per_chain: int = 500
    canonicals: int = 0  # 0 = all
    days: int = 90
    delta_every_days: int = 7
    delta_share: float = 0.04
    promo_share: float = 0.20
    gush_dan_share: float = 0.45
    stock_share: float = 0.92


SMALL = Shape(stores_per_chain=3, items_per_chain=120, canonicals=60, days=30,
              delta_every_days=10)  # fmt: skip


@dataclass(frozen=True)
class Product:
    code: str
    canonical: str
    level: str  # any_brand or close
    name: str
    brand: str
    weighed: bool
    unit_qty: str
    quantity: str
    uom: str
    uom_divisor: float  # shelf price / divisor = published unit price
    price: float  # reference shelf price


def _builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("smartcart_build_synthetic", BUILDER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {BUILDER}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ean13(first12: str) -> str:
    digits = [int(c) for c in first12]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits))
    return first12 + str((10 - total % 10) % 10)


def _price(x: float) -> float:
    """Shelf prices end in .90 above 5 shekels, otherwise in tenths."""
    if x >= 5:
        return max(round(x) - 0.10, 0.9)
    return max(round(x, 1), 0.5)


def _size_fields(base_unit: str, pack: float) -> tuple[str, str, str, float, str]:
    """(UnitQty, Quantity, UnitOfMeasure, divisor, size text in the name)."""
    if base_unit == "100ml":
        text = f"{pack / 1000:g} ליטר" if pack >= 1000 else f'{pack:g} מ"ל'
        return "מיליליטר", f"{pack:.2f}", '100 מ"ל', pack / 100, text
    if base_unit == "unit":
        return "יחידה", f"{pack:.2f}", "יחידה", pack, f"{pack:g} יחידות"
    text = f'{pack / 1000:g} ק"ג' if pack >= 1000 else f"{pack:g} גרם"
    return "גרם", f"{pack:.2f}", "100 גרם", pack / 100, text


def products(canonicals: list[dict], rng: random.Random) -> tuple[list[Product], dict]:
    """The national pool: per non-weighed canonical three brands at the canonical pack size and
    one other pack size; weighed canonicals get per-chain items in ``chain_items``."""
    pool: list[Product] = []
    weighed: list[dict] = []
    serial = 0
    for c in canonicals:
        if c["base_unit"] == "kg":
            weighed.append(c)
            continue
        soft = c.get("soft_attrs") or {}
        pack = float(soft.get("pack_size") or (1 if c["base_unit"] == "unit" else 500))
        ref = rng.uniform(4, 40)  # reference shelf price of the canonical pack
        variants = [(pack, "any_brand")] * 3 + [
            (pack * rng.choice([0.5, 1.5, 2.0]) if c["base_unit"] != "unit" else pack * 2, "close")
        ]
        for i, (size, level) in enumerate(variants):
            serial += 1
            brand = BRANDS[(serial + i) % len(BRANDS)]
            unit_qty, qty, uom, div, text = _size_fields(c["base_unit"], size)
            pool.append(
                Product(
                    code=ean13(f"729{serial:09d}"),
                    canonical=c["slug"],
                    level=level,
                    name=f"{c['display_name_he']} {brand} {text}",
                    brand=brand,
                    weighed=False,
                    unit_qty=unit_qty,
                    quantity=qty,
                    uom=uom,
                    uom_divisor=div,
                    price=ref * (size / pack) ** 0.9 * rng.uniform(0.85, 1.2),
                )
            )
    return pool, {"weighed": weighed}


def chain_items(
    chain_index: int, pool: list[Product], weighed: list[dict], shape: Shape, rng: random.Random
) -> list[Product]:
    """The chain's assortment: every weighed canonical, two any-brand products per canonical,
    then close variants until ``items_per_chain``."""
    out: list[Product] = []
    for j, c in enumerate(weighed):
        out.append(
            Product(
                code=f"2{chain_index:02d}{j:04d}",
                canonical=c["slug"],
                level="any_brand",
                name=f"{c['display_name_he']} במשקל",
                brand="לא ידוע",
                weighed=True,
                unit_qty="קילוגרמים",
                quantity="1.00",
                uom="קילו",
                uom_divisor=1.0,
                price=rng.uniform(4, 30),
            )
        )
    by_canon: dict[str, list[Product]] = {}
    for p in pool:
        by_canon.setdefault(p.canonical, []).append(p)
    closes = []
    for _slug, ps in by_canon.items():
        brands = [p for p in ps if p.level == "any_brand"]
        out.extend(rng.sample(brands, 2))
        closes.extend(p for p in ps if p.level == "close")
    rng.shuffle(closes)
    room = max(shape.items_per_chain - len(out), 0)
    out.extend(closes[:room])
    return out[: shape.items_per_chain] if len(out) > shape.items_per_chain else out


@dataclass
class StoreSpec:
    code: str
    name: str
    city: str
    lat: float
    lon: float


def stores_for(chain: Chain, shape: Shape, rng: random.Random) -> list[StoreSpec]:
    out = []
    for i in range(shape.stores_per_chain):
        cities = GUSH_DAN if rng.random() < shape.gush_dan_share else ELSEWHERE
        city, lat, lon, spread = rng.choice(cities)
        out.append(
            StoreSpec(
                code=f"{101 + i:03d}",
                name=f"{chain.name} {city} {i + 1}",
                city=city,
                lat=round(lat + rng.uniform(-spread, spread), 4),
                lon=round(lon + rng.uniform(-spread, spread), 4),
            )
        )
    return out


def _stamp(chain: Chain, at: datetime) -> str:
    return at.strftime("%Y%m%d-%H%M%S") if chain.hyphen_stamp else at.strftime("%Y%m%d%H%M")


def _redate(xml: str, at: datetime) -> str:
    when = at.strftime("%Y-%m-%d %H:%M:%S")
    for stamp in BUILDER_PRICE_DATES:
        xml = xml.replace(stamp, when)
    return xml.replace(BUILDER_PROMO_UPDATE, when)


class Writer:
    def __init__(self, mod: ModuleType, out: Path) -> None:
        self.mod = mod
        self.out = out
        self.count = 0

    def put(self, chain: Chain, name: str, xml: str, *, stores: bool = False) -> None:
        if stores:  # the chain's Stores encoding; compressed only when the name says so
            codec, declare, bom = chain.stores_encoding
            data = self.mod.encode(xml, codec, declare=declare, bom=bom)
            if name.endswith(".gz"):
                data = self.mod.gz(data)
        else:  # price and promo files: UTF-8, in the chain's container
            data = self.mod.encode(xml, "utf-8", declare="utf-8")
            if chain.wrap == "zip":  # a zip archive under a .gz name (Yohananof's Cerberus)
                data = self.mod.zipped([(name.split(".", 1)[0] + ".xml", data)])
            else:  # gzip, also under King Store's .xml names
                data = self.mod.gz(data)
        path = self.out / chain.slug / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.count += 1


def stores_xml(mod: ModuleType, chain: Chain, stores: list[StoreSpec]) -> str:
    if chain.stores == "sap":
        rows = "".join(
            mod.row("STORE", {
                "STOREID": s.code, "BIKORETNO": 4, "STORETYPE": 1, "CHAINNAME": chain.name,
                "SUBCHAINID": 1, "SUBCHAINNAME": chain.name, "STORENAME": s.name,
                "ADDRESS": f"רחוב {i + 1}", "CITY": s.city, "ZIPCODE": "0000000",
                "LATITUDE": s.lat, "LONGITUDE": s.lon,
            })
            for i, s in enumerate(stores)
        )  # fmt: skip
        return (
            '<asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0"><asx:values>'
            + mod.el("CHAINID", chain.chain_id)
            + mod.el("LASTUPDATEDATE", "20261006")
            + f"<STORES>{rows}</STORES></asx:values></asx:abap>"
        )
    tuples = [
        (s.code, 1, s.name, f"רחוב {i + 1}", s.city, f"{s.lat}", f"{s.lon}")
        for i, s in enumerate(stores)
    ]
    return mod.subchains_doc(
        chain.chain_id, chain.name, [("001", chain.name, tuples)], **chain.subchains_kw
    )


def item_tuple(p: Product, price: float) -> tuple:
    uom_price = price / p.uom_divisor if p.uom_divisor else price
    return (
        p.code, 0 if p.weighed else 1, p.name, p.brand, p.unit_qty, p.quantity,
        1 if p.weighed else 0, p.uom, f"{price:.2f}", f"{uom_price:.2f}",
    )  # fmt: skip


def promotions(
    mod: ModuleType,
    stocked: list[Product],
    prices: dict[str, float],
    share: float,
    start: date,
    end: date,
    rng: random.Random,
) -> list[str]:
    """About ``share`` of the store's items in promotions of one or two items each."""
    chosen = [p for p in stocked if not p.weighed and rng.random() < share]
    out = []
    i = 0
    pid = 5000
    while i < len(chosen):
        group = chosen[i : i + (2 if rng.random() < 0.3 else 1)]
        i += len(group)
        pid += 1
        items = [(p.code, 0) for p in group]
        shelf = max(prices[p.code] for p in group)
        club = "1" if rng.random() < 0.15 else "0"
        kind = rng.random()
        kw: dict = {"club": club, "start": start.isoformat(), "end": end.isoformat()}
        if kind < 0.40:
            desc = f"ב-{shelf * 0.85:.2f}"
            kw.update(discounted=f"{shelf * 0.85:.2f}")
        elif kind < 0.65:
            rate = rng.choice([10, 15, 20, 25])
            desc = f"{rate}% הנחה"
            kw.update(discount_type="2", rate=str(rate))
        elif kind < 0.85:
            buy = rng.choice([1, 2])
            desc = f"{buy}+1"
            kw.update(min_qty=str(buy + 1), gift_count="1")
        else:
            n = rng.choice([2, 3])
            total = shelf * n * 0.85
            desc = f"{n} ב-{total:.2f}"
            kw.update(min_qty=str(n), discounted=f"{total:.2f}")
        out.append(mod.promotion(str(pid), desc, items, **kw))
    return out


def store_files(
    writer: Writer,
    chain: Chain,
    s: StoreSpec,
    assortment: list[Product],
    chain_level: float,
    shape: Shape,
    seed: int,
    day0: datetime,
    today: date,
    totals: dict[str, int],
) -> None:
    """One store's price history and promotions."""
    mod = writer.mod
    srng = random.Random(f"{seed}-{chain.slug}-{s.code}")
    store_level = chain_level * srng.uniform(0.97, 1.03)
    stocked = [p for p in assortment if srng.random() < shape.stock_share]
    prices = {p.code: _price(p.price * store_level * srng.uniform(0.95, 1.05)) for p in stocked}

    def name(kind: str, when: datetime) -> str:
        return chain.file_name.format(k=kind, c=chain.chain_id, s=s.code, t=_stamp(chain, when))

    def change(share: float) -> list[Product]:
        moved = [p for p in stocked if srng.random() < share]
        for p in moved:
            prices[p.code] = _price(prices[p.code] * srng.uniform(0.9, 1.1))
        return moved

    def price_file(kind: str, when: datetime, rows: list[Product], observed: datetime) -> None:
        doc = mod.price_doc(chain.chain_id, s.code, [item_tuple(p, prices[p.code]) for p in rows],
                            **chain.price_kw)  # fmt: skip
        writer.put(chain, name(kind, when), _redate(doc, observed))

    # A publication day every `delta_every_days`: the day's PriceFull at 03:00 (a delta is held
    # until its store's full file of that day is loaded, so a delta day needs one), then a Price
    # delta at 11:00 with a few more changes. Between publication days nothing is published; the
    # loader keeps only change events either way.
    for day in range(0, shape.days, shape.delta_every_days):
        full_at = day0.replace(hour=3) + timedelta(days=day)
        if day:
            change(shape.delta_share)
        price_file("PriceFull", full_at, stocked, full_at - timedelta(hours=2))
        totals["price_records"] += len(stocked)
        if not day:
            continue
        when = full_at.replace(hour=11)
        moved = change(shape.delta_share / 2)
        if moved:
            price_file("Price", when, moved, when - timedelta(hours=1))
            totals["delta_records"] += len(moved)

    promo_at = datetime.combine(today - timedelta(days=1), datetime.min.time(), ISRAEL)
    promo_at = promo_at.replace(hour=8)
    promos = promotions(mod, stocked, prices, shape.promo_share,
                        today - timedelta(days=6), today + timedelta(days=13), srng)  # fmt: skip
    if chain.big_id_promos:
        promos = mod._big_id_promos(promos)
    doc = mod.promo_doc(chain.chain_id, s.code, promos, **chain.promo_kw)
    writer.put(chain, name("PromoFull", promo_at), _redate(doc, promo_at - timedelta(hours=1)))
    totals["promotions"] += len(promos)


def build(out: Path, shape: Shape | None = None, seed: int = 7, today: date | None = None) -> dict:
    """Write the world under ``out`` and return a summary (counts and the replay window)."""
    shape = shape or Shape()
    mod = _builder()
    rng = random.Random(seed)
    today = today or datetime.now(tz=ISRAEL).date()
    day0 = today - timedelta(days=shape.days)
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    writer = Writer(mod, out)

    canonicals = yaml.safe_load(CANONICALS.read_text(encoding="utf-8"))["canonicals"]
    canonicals.sort(key=lambda c: c.get("rank") or 10_000)
    if shape.canonicals:
        canonicals = canonicals[: shape.canonicals]
    pool, extra = products(canonicals, rng)

    answer: dict[str, dict[str, str]] = {}
    totals = {"stores": 0, "items": 0, "price_records": 0, "delta_records": 0, "promotions": 0}
    for ci, chain in enumerate(CHAINS):
        crng = random.Random(f"{seed}-{chain.slug}")
        level = crng.uniform(0.92, 1.08)
        assortment = chain_items(ci, pool, extra["weighed"], shape, crng)
        totals["items"] += len(assortment)
        for p in assortment:
            answer[f"{chain.chain_id}:{p.code}"] = {"canonical": p.canonical, "level": p.level}
        stores = stores_for(chain, shape, crng)
        totals["stores"] += len(stores)

        at = datetime.combine(day0, datetime.min.time(), ISRAEL).replace(hour=1)
        writer.put(
            chain,
            chain.stores_name.format(c=chain.chain_id, t=_stamp(chain, at)),
            stores_xml(mod, chain, stores),
            stores=True,
        )
        for s in stores:
            store_files(writer, chain, s, assortment, level, shape, seed, at, today, totals)

    (out / "answer_key.json").write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
    return {
        **totals,
        "files": writer.count,
        "canonicals": len(canonicals),
        "chains": len(CHAINS),
        "day0": day0.isoformat(),
        "today": today.isoformat(),
        "seed": seed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--small", action="store_true", help="the CI-sized world")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    summary = build(args.out, SMALL if args.small else Shape(), args.seed)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
