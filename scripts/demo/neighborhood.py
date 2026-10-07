"""The demo's second day: synthetic PriceFull and PromoFull files for three stores near Tel Aviv.

The adapters' regression fixtures (``services/ingest/tests/fixtures``) are one day of eight items
spread over ten chains and the whole country. They prove the adapters, but on their own they
cannot show three things the MVP is about: a price that changed (history), a cheaper close
substitute (the substitution card), and two nearby stores that are each cheaper on part of a list
(the split). This module writes one more day of files for three stores that are already in the
fixtures' Stores files, in the same chain dialects, with the same builders
(``build_synthetic.py``), into the demo's state directory. ``load_fixtures.py`` replays them after
the fixtures through the same gates.

The second day is yesterday in Israel (never earlier than 2026-10-07, the day after the
fixtures), and its PromoFull files republish the stores' day-1 promotions (same ids, so they
update the same rows) with a window around that day. Dating it relative to the run keeps the
price change inside the 90-day history and the promotions active whenever the demo runs; the
fixtures' own dates are fixed.

Everything here is SYNTHETIC and chosen for the demo: the prices are not observations, the
barcodes are made up (valid EAN-13 check digits, the ``7290000`` prefix) and the two extra items
are invented brands of real product types.

The demo location is 32.085, 34.820 (Ramat Gan, the rounded neighborhood point):

| Chain, store | Distance | Shape of its prices on day 2 |
|---|---|---|
| Tiv Taam 002, Ramat Gan | 0.7 km | snacks and oil cheap, dairy, bread and produce dear |
| Machsanei Hashuk 003, Bnei Brak | 1.3 km | dairy, bread and produce cheap, snacks and oil dear; a second milk brand and a 1 kg loaf (a close substitute for the 750 g standard loaf) |
| Shufersal 001, Tel Aviv (the demo's home store) | 3.6 km | up a little from day 1 |
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from types import ModuleType
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[2]
BUILDER = REPO / "services" / "ingest" / "tests" / "fixtures" / "build_synthetic.py"

ISRAEL = ZoneInfo("Asia/Jerusalem")
FIRST_DAY2 = date(2026, 10, 7)
# The builders hard-code day 1's update and promotion dates; they are replaced (see _redate).
DAY1_UPDATES = ("2026-10-05 22:01:00", "2026-10-05 22:10:00")
DAY1_PROMO_START, DAY1_PROMO_END, DAY1_PROMO_UPDATE = "2026-10-01", "2026-10-14", "2026-09-30"


def day2_default(now: datetime | None = None) -> date:
    """Yesterday in Israel, and never before the day after the fixtures."""
    today = (now or datetime.now(tz=ISRAEL)).astimezone(ISRAEL).date()
    return max(today - timedelta(days=1), FIRST_DAY2)


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


# Two invented items (made-up brand "שדות", valid check digits).
BREAD_1KG = ean13("729000010001")
MILK_OTHER = ean13("729000010002")

# Day-1 item codes from build_synthetic.ITEMS, by a short key.
CODES = {
    "milk": "7290004131074",
    "cottage": "7290000042442",
    "bread": "7290112337023",
    "cherry": "2000123",
    "bamba": "7290000066318",
    "oil": "7290011194246",
    "banana": "2000456",
    "chocolate": "7290107932158",
}

EXTRA_ITEMS = {
    # code: (type, name, manufacturer, unit_qty, quantity, weighed, uom, per-uom divisor)
    BREAD_1KG: (1, 'לחם אחיד פרוס שדות 1 ק"ג', "שדות", "גרם", "1000.00", 0, "100 גרם", 10),
    MILK_OTHER: (1, "חלב טרי 3% שדות בקרטון 1 ליטר", "שדות", "ליטר", "1.00", 0, "ליטר", 1),
}

# Shelf prices of the second day, per store (ILS). Synthetic, chosen for the demo.
PRICES: dict[str, dict[str, str]] = {
    "shufersal": {
        "milk": "7.45", "cottage": "6.30", "bread": "8.30", "cherry": "13.90",
        "bamba": "4.90", "oil": "12.90", "banana": "9.90", "chocolate": "7.90",
    },
    "machsanei_hashuk": {
        "milk": "4.90", "cottage": "4.40", "bread": "6.90", "cherry": "5.90",
        "bamba": "8.90", "oil": "18.90", "banana": "3.90", "chocolate": "12.90",
        BREAD_1KG: "5.90", MILK_OTHER: "4.60",
    },
    "tivtaam": {
        "milk": "8.90", "cottage": "7.90", "bread": "10.90", "cherry": "19.90",
        "bamba": "1.90", "oil": "6.90", "banana": "14.90", "chocolate": "3.90",
    },
}  # fmt: skip


def _items(mod: ModuleType, prices: dict[str, str]) -> list[tuple]:
    """Item tuples in ``build_synthetic.ITEMS`` layout with this store's prices."""
    by_code = {row[0]: row for row in mod.ITEMS}
    out = []
    for key, price in prices.items():
        code = CODES.get(key, key)
        if code in by_code:
            row = by_code[code]
            ratio = float(row[9]) / float(row[8])  # keep the published unit price consistent
            out.append((*row[:8], price, f"{float(price) * ratio:.2f}"))
        else:
            itype, name, manu, unit_qty, qty, weighed, uom, divisor = EXTRA_ITEMS[code]
            uom_price = f"{float(price) / divisor:.2f}"
            out.append((code, itype, name, manu, unit_qty, qty, weighed, uom, price, uom_price))
    return out


def _redate(xml: str, day2: date) -> str:
    """Day-1 dates to day 2: prices updated at 09:30, promotions from six days before to 13 days
    after, last updated the day before."""
    for stamp in DAY1_UPDATES:
        xml = xml.replace(stamp, f"{day2.isoformat()} 09:30:00")
    xml = xml.replace(DAY1_PROMO_START, (day2 - timedelta(days=6)).isoformat())
    xml = xml.replace(DAY1_PROMO_END, (day2 + timedelta(days=13)).isoformat())
    return xml.replace(DAY1_PROMO_UPDATE, (day2 - timedelta(days=1)).isoformat())


def build(out_dir: Path, day2: date | None = None) -> list[Path]:
    """Write the second-day files under ``out_dir/<slug>/`` (replacing what is there) and return
    their paths. Publication time is 10:00 Israel time on ``day2``."""
    mod = _builder()
    day2 = day2 or day2_default()
    stamp = f"{day2:%Y%m%d}1000"
    shutil.rmtree(out_dir, ignore_errors=True)
    written: list[Path] = []

    def put(slug: str, name: str, xml: str, declare: str) -> None:
        path = out_dir / slug / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(mod.gz(mod.encode(_redate(xml, day2), "utf-8", declare=declare)))
        written.append(path)

    promos = mod.standard_promos()

    chain = "7290027600007"  # Shufersal: SAP-style lowercase root, as in build_shufersal
    put(
        "shufersal",
        f"PriceFull{chain}-001-{stamp}.gz",
        mod.price_doc(chain, "001", _items(mod, PRICES["shufersal"]), root="root"),
        "UTF-8",
    )
    put(
        "shufersal",
        f"PromoFull{chain}-001-{stamp}.gz",
        mod.promo_doc(chain, "001", promos, root="root"),
        "UTF-8",
    )

    chain = "7290661400001"  # Machsanei Hashuk: BigID casing, .xml.gz, as in build_machsanei_hashuk
    put(
        "machsanei_hashuk",
        f"PriceFull{chain}-003-{stamp}.xml.gz",
        mod.price_doc(chain, "003", _items(mod, PRICES["machsanei_hashuk"]), id_case="ID"),
        "utf-8",
    )
    put(
        "machsanei_hashuk",
        f"PromoFull{chain}-003-{stamp}.xml.gz",
        mod.promo_doc(chain, "003", mod._big_id_promos(promos[:3]), id_case="ID"),
        "utf-8",
    )

    chain = "7290873255550"  # Tiv Taam: NewDataSet container, as in build_tivtaam
    put(
        "tivtaam",
        f"PriceFull{chain}-002-{stamp}.gz",
        mod.price_doc(
            chain, "002", _items(mod, PRICES["tivtaam"]), container="NewDataSet", row_tag="item"
        ),
        "utf-8",
    )
    put("tivtaam", f"PromoFull{chain}-002-{stamp}.gz", mod.promo_doc(chain, "002", promos), "utf-8")
    return written


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("neighborhood")
    for p in build(target):
        print(p)
