"""Regression tests on the real PromoFull files the Portal probe committed (issue #47).

Seven chains' files, fetched on a GitHub runner on 2026-10-21 through the pinned upstream scraper
and trimmed to 100 promotions (evenly spaced over the file, each kept whole with all its items):
``fixtures/<chain>/real/PromoFull*``. They are untrusted data; only the chain adapters read them
(the shelf-price test below also reads the XML for the published ``DiscountRate``, with the same
``xmlutil`` the adapters use). Victory, Machsanei Hashuk and Hazi Hinam are not here: their
portals did not answer from the runner (docs/ingestion.md).

What these files showed, and what is verified here (docs/adapters.md, "Promotions in real files"):

* every file uses the grouped layout (``Groups/Group/PromotionItems/PromotionItem``), which the
  adapters read before this change as 100 % reward "other" with no items;
* ``DiscountedPrice`` is the total for ``MinQty`` units and ``DiscountRate`` the percentage off the
  store's shelf price, checked against the same store's PriceFull (``test_the_reading_...``);
* the club, date-time, coupon and basket-condition rules.

The per-chain numbers are literal: they change only when the fixtures or a reading rule does.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from lxml import etree

from smartcart_ingest import xmlutil
from smartcart_ingest.adapters._common import UNAPPLIED_REASONS
from tests.test_adapters import FIXTURES, chain_adapters, parse_fixture

D = Decimal

# chain slug -> what the adapter reads from the committed file.
EXPECTED: dict[str, dict] = {
    "king_store": {
        "file": "PromoFull7290058108879-000-340-20261021-040448.gz",
        "store": "340", "promos": 100, "item_codes": 243, "club_only": 21,
        "rewards": {"bundle": 52, "price": 48}, "unapplied": {},
        "pinned": {  # promo id -> (reward type, value, min qty, club only)
            "587746944": ("bundle", D("89.90"), D("2"), False),  # 2 kg of minced beef for 89.90
            "587746718": ("price", D("99.90"), D("1"), True),  # lamb chops, 99.90 a kg, club
        },
    },
    "mega": {
        "file": "PromoFull7290055700007-001-002-20261021-051128.gz",
        "store": "2", "promos": 100, "item_codes": 377, "club_only": 0,
        "rewards": {"bundle": 37, "other": 7, "percent": 1, "price": 55},
        "unapplied": {"basket_condition": 3, "coupon_required": 4},
        "pinned": {
            "0011451390": ("bundle", D("23.00"), D("2"), False),
            "0011443073": ("percent", D("50.00"), D("1"), False),
        },
    },
    "osherad": {
        "file": "PromoFull7290103152017-001-001-20261021-080047.gz",
        "store": "1", "promos": 100, "item_codes": 371, "club_only": 0,
        "rewards": {"bundle": 90, "other": 1, "price": 9},
        "unapplied": {"reward_value_unusable": 1},
        "pinned": {
            "0000158433": ("bundle", D("10.00"), D("3"), False),
            "0001114875": ("price", D("3799.00"), D("1"), False),
        },
    },
    "ramilevy": {
        "file": "PromoFull7290058140886-001-001-20261021-001146.gz",
        "store": "1", "promos": 100, "item_codes": 348, "club_only": 2,
        "rewards": {"bundle": 32, "other": 19, "price": 49},
        "unapplied": {"basket_condition": 5, "coupon_required": 14},
        "pinned": {
            "0001422642": ("price", D("11.90"), D("1"), False),
            "0001426839": ("bundle", D("33.00"), D("3"), False),
        },
    },
    "shufersal": {
        # Store 39, the PriceFull of the same store beside it (the first fixtures were store 310's
        # promotions and store 36's prices, so the shelf prices could not be checked).
        "file": "PromoFull7290027600007-001-039-20261021-043100.gz",
        "store": "39", "promos": 100, "item_codes": 256, "club_only": 0,
        "rewards": {"bundle": 52, "buy_x_get_y": 1, "other": 10, "price": 37},
        "unapplied": {"basket_condition": 1, "coupon_required": 9},  # one "1+1" is applied
        "pinned": {
            "4632222": ("bundle", D("20.00"), D("2"), False),  # "2ב20"
            "4632244": ("price", D("25.90"), D("1"), False),
        },
    },
    "tivtaam": {
        "file": "PromoFull7290873255550-000-002-20261021-004004.gz",
        "store": "2", "promos": 100, "item_codes": 229, "club_only": 59,
        # item_codes was 233: two "second at 50 %" promotions list 2 reward-only items each, which
        # are no longer linked (they need a trigger of another item).
        "rewards": {"bundle": 36, "buy_x_get_y": 2, "other": 2, "price": 60},
        "unapplied": {"club_in_description": 1, "reward_value_unusable": 1},
        "pinned": {
            "289904": ("bundle", D("12.90"), D("2"), True),  # "water 2 for 12.9, club"
            "314977": ("price", D("159.90"), D("1"), True),
        },
    },
    "yohananof": {
        # Store 5 (the PriceFull of the same store beside it; the first fixtures were store 9's
        # promotions and store 1's prices). The staff club is 11 of this store's 1241 promotions,
        # none of them among the 100 kept.
        "file": "PromoFull7290803800003-000-005-20261022-004040.gz",
        "store": "5", "promos": 100, "item_codes": 372, "club_only": 0,
        "rewards": {"bundle": 69, "buy_x_get_y": 1, "other": 6, "price": 24},
        "unapplied": {"basket_condition": 1, "coupon_required": 3, "packaging_credit": 1,
                      "reward_value_unusable": 1},  # fmt: skip
        "pinned": {
            "361475": ("price", D("12.90"), D("1"), False),
            "325337": ("bundle", D("30.40"), D("1.90"), False),  # "2 kg for 32": 1.9 kg for 30.40
        },
    },
}  # fmt: skip


def _real(slug: str) -> Path:
    return FIXTURES / slug / "real" / EXPECTED[slug]["file"]


def _parsed(slug: str):
    return parse_fixture(chain_adapters()[slug](), _real(slug))


def test_every_chain_with_a_real_promo_fixture_is_covered() -> None:
    on_disk = {p.parent.parent.name for p in FIXTURES.glob("*/real/PromoFull*")}
    assert on_disk == set(EXPECTED)
    for slug in EXPECTED:
        assert _real(slug).is_file(), slug


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_the_real_file_is_read_as_the_grouped_layout(slug: str) -> None:
    exp = EXPECTED[slug]
    parsed = _parsed(slug)
    promos = parsed.promos
    assert parsed.raw.schema_version == "v1"  # no SchemaVersion marker in any real promo file
    assert len(promos) == exp["promos"]
    assert {p.store_code for p in promos} == {exp["store"]}  # the file's store, per-store promos
    assert sum(len(p.item_codes) for p in promos) == exp["item_codes"]
    assert dict(sorted(Counter(p.reward_type for p in promos).items())) == exp["rewards"]
    unapplied = Counter(p.raw["unapplied"] for p in promos if p.raw["unapplied"])
    assert dict(sorted(unapplied.items())) == exp["unapplied"]
    assert set(unapplied) <= set(UNAPPLIED_REASONS)
    assert sum(p.club_only for p in promos) == exp["club_only"]
    assert {p.raw["layout"] for p in promos} == {"grouped"}
    # Before the grouped layout was read: reward "other" and no item code, on every promotion.
    assert all(p.item_codes for p in promos), "a promotion without an item"
    assert sum(p.reward_type != "other" for p in promos) >= 0.5 * len(promos)


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_pinned_real_promotions(slug: str) -> None:
    by_id = {p.promo_id: p for p in _parsed(slug).promos}
    for promo_id, (reward, value, min_qty, club_only) in EXPECTED[slug]["pinned"].items():
        p = by_id[promo_id]
        assert (p.reward_type, p.reward_value, p.min_qty, p.club_only) == (
            reward, value, min_qty, club_only
        ), (slug, promo_id, p.description)  # fmt: skip
        assert p.raw["confidence"] == 1.0 and p.raw["unapplied"] is None


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_real_promotions_have_a_window_and_no_daily_hours(slug: str) -> None:
    promos = _parsed(slug).promos
    assert all(p.starts_at and p.ends_at for p in promos), "a promotion without a date window"
    assert all(p.starts_at < p.ends_at for p in promos)
    assert all(p.hours is None for p in promos)  # Start/EndHour only repeat the date-time's time
    published = _parsed(slug).raw.published_at
    assert not [p for p in promos if p.starts_at > published], "starts after the file was written"


def test_only_king_store_publishes_promotions_that_ended_before_the_file() -> None:
    """The adapter keeps ``ends_at`` as published; King Store writes its end dates at 00:00, and
    11 of its 100 promotions end before the file's publication time (kept, read literally)."""
    expired = {}
    for slug in EXPECTED:
        parsed = _parsed(slug)
        expired[slug] = sum(1 for p in parsed.promos if p.ends_at < parsed.raw.published_at)
    assert expired == {"king_store": 11, "mega": 0, "osherad": 0, "ramilevy": 0, "shufersal": 0,
                       "tivtaam": 0, "yohananof": 0}  # fmt: skip


def test_club_values_of_the_real_files() -> None:
    names = {slug: Counter(p.club_name for p in _parsed(slug).promos if p.club_only)
             for slug in EXPECTED}  # fmt: skip
    # Tiv Taam: "1 - המועדון החדש" is one named club; "0 - כלל הלקוחות" is everyone.
    assert names["tivtaam"] == {"המועדון החדש": 59}
    assert not names["yohananof"] and not names["shufersal"]  # the kept promotions are "everyone"
    assert not names["osherad"] and not names["mega"]
    # Expressions are resolved against the chain's club table (chain_clubs.json) into a rule over
    # club labels: the 18 King Store customer groups keep the three that are clubs a person can
    # belong to, Rami Levy's "A|B & C|D" keeps its AND (test_club_rules.py has the membership).
    assert names["king_store"] == {
        "מועדון לקוחות | לקוחות סיטונאים | עובדי קינגסטור": 18,
        "לקוחות סיטונאים": 3,
    }
    assert names["ramilevy"] == {
        "(מועדון רמי לוי | מועדון לקוחות אשראי) & (ישראכרט מגנטי | תווי זיכוי מימוש)": 1,
        "מועדון חברתי | מועדון רמי לוי | מועדון לקוחות אשראי | מועדון נטען | לקוחות ארנק": 1,
    }
    assert all(len(n) <= 120 for slug in names for n in names[slug])
    for slug in ("king_store", "ramilevy"):
        promos = [p for p in _parsed(slug).promos if p.club_only]
        assert promos and all(p.raw["club_ids"] for p in promos)


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_coupons_and_basket_conditions_are_never_applied(slug: str) -> None:
    for p in _parsed(slug).promos:
        if p.raw["unapplied"]:
            assert (p.reward_type, p.reward_value) == ("other", None)
            assert p.raw["confidence"] == 0.1
        if p.raw.get("min_purchase_amount"):
            assert p.raw["unapplied"] in ("basket_condition", "coupon_required")
        if p.raw.get("additionaliscoupon") == "1":
            assert p.raw["unapplied"] == "coupon_required"


def _published_rates(slug: str) -> dict[tuple[str, str], tuple[Decimal, Decimal, Decimal, bool]]:
    """(promo id, item code) -> (MinQty, DiscountedPrice, DiscountRate, weighed, per kg) read from
    the file's XML, for items with a rate."""
    decoded = xmlutil.decode(_real(slug).read_bytes())
    root = etree.fromstring(
        decoded.data, parser=etree.XMLParser(resolve_entities=False, no_network=True)
    )
    out = {}
    for promo in root.iter("Promotion"):
        pid = xmlutil.scalar_children(promo).get("promotionid")
        for it in promo.iter("PromotionItem"):
            f = xmlutil.scalar_children(it)
            if (
                f.get("rewardtype") in ("1", "3", "10")
                and f.get("discountrate")
                and f.get("minqty")
            ):
                out[(pid, f["itemcode"])] = (
                    D(f["minqty"]), D(f["discountedprice"]), D(f["discountrate"]),
                    f.get("bisweighted") == "1", D(f.get("discountedpricepermida") or "0"),
                )  # fmt: skip
    return out


def test_the_reading_reproduces_the_published_discount_rate_on_the_shelf_price() -> None:
    """The semantics check against real data: for the items whose shelf price is in the same
    store's PriceFull fixture, the per-unit price the adapter's reading gives equals the shelf
    price times (1 - DiscountRate), which is how the chain computed the rate."""
    checked = 0
    per_chain: Counter = Counter()
    for slug in (
        "king_store",
        "osherad",
        "ramilevy",
        "tivtaam",
        "shufersal",
        "yohananof",
    ):  # same store as the PriceFull
        adapter = chain_adapters()[slug]()
        price_file = next((FIXTURES / slug / "real").glob("PriceFull*"))
        shelf = {p.item_code: p.price for p in parse_fixture(adapter, price_file).prices}
        rates = _published_rates(slug)
        for promo in _parsed(slug).promos:
            if promo.reward_type not in ("price", "bundle"):
                continue
            for code in promo.item_codes:
                if code not in shelf or (promo.promo_id, code) not in rates:
                    continue
                qty, total, rate, weighed, per_kg = rates[(promo.promo_id, code)]
                assert shelf[code] > 0
                unit = (
                    promo.reward_value / promo.min_qty
                    if promo.reward_type == "bundle"
                    else promo.reward_value
                )
                want = shelf[code] * (1 - rate / 100)
                # Tiv Taam publishes whole percents: up to half a percent of the shelf price off.
                assert abs(unit - want) <= shelf[code] * D("0.006") + D("0.02"), (
                    slug,
                    promo.promo_id,
                    code,
                    unit,
                    want,
                )
                checked += 1
                per_chain[slug] += 1
    assert checked >= 15, checked
    # Shufersal's PriceFull is now for the promotions' store (one of the 200 kept rows is on
    # promotion; Yohananof has none): the whole files are checked in the manifests, below.
    assert per_chain["shufersal"] >= 1, per_chain


def _manifest_full_file(slug: str) -> dict:
    import json

    manifest = json.loads((FIXTURES / slug / "real" / "MANIFEST.json").read_text("utf-8"))
    return next(f for f in manifest["files"] if f["kind"] == "promo_full")["full_file"]


@pytest.mark.parametrize(
    ("slug", "promos", "single", "within", "pairs"),
    [("shufersal", 1408, 2251, 2172, 61), ("yohananof", 1241, 2108, 2108, 70)],
)
def test_the_manifest_records_the_shelf_check_of_the_whole_file(
    slug: str, promos: int, single: int, within: int, pairs: int
) -> None:
    """The probe checked the whole PromoFull against the PriceFull of the same store (run
    39681477048, 2026-10-21): the prices are below the shelf price on every item, equal to the
    shelf price times (1 - rate) to the rate's whole-percent rounding on 96 to 100 %, and every
    "buy X get Y" reward and trigger price matches. The numbers are in the committed manifest."""
    full = _manifest_full_file(slug)
    assert full["promos"] == promos
    assert full["shelf"]["checked"] is True
    assert full["shelf"]["promo_stores"] == full["shelf"]["price_stores"]
    check = full["shelf_check"]
    assert check["single_items_with_shelf"] == single
    assert check["single_unit_below_shelf"] == single
    assert check["single_unit_within_rate_rounding"] == within
    assert check["items_with_shelf"] == check["reward_equals_shelf_x_rate"] == pairs
    assert check["trigger_priced"] == check["trigger_equals_shelf"] == pairs


def test_the_scheduler_loads_every_real_promo_file_with_its_items(db, tmp_path) -> None:
    """Through the real path (adapter, gates, loader): the promotions are written and linked to
    the items of the chain's PriceFull fixture that they name."""
    from datetime import timedelta

    from smartcart_ingest.alerts import Alerter
    from smartcart_ingest.rawstore import LocalRawStore
    from smartcart_ingest.scheduler import Scheduler
    from smartcart_ingest.settings import Settings
    from tests.fakes import FakeFetcher, RecordingSink

    slug = "king_store"
    adapter = chain_adapters()[slug]()
    real = FIXTURES / slug / "real"
    fetcher = FakeFetcher()
    published = []
    for path in sorted(real.glob("*")):
        if path.name == "MANIFEST.json":
            continue
        info = adapter.parse_filename(path.name)
        published.append(info.published_at)
        fetcher.add(info.kind, path.read_bytes(), chain_id=adapter.chain_id, name=path.name)
    now = max(published) + timedelta(hours=1)
    sched = Scheduler(db, fetcher, LocalRawStore(tmp_path), Alerter([RecordingSink()]), Settings(),
                      adapter_for=lambda c: chain_adapters()[slug](), now=lambda: now,
                      sleep=lambda s: None)  # fmt: skip
    assert sched.run_full([adapter.chain_id]).chains[0].error is None
    promos = db.execute(
        "SELECT count(*), count(*) FILTER (WHERE reward_type <> 'other') FROM promos"
        " WHERE chain_id = %s", (adapter.chain_id,),
    ).fetchone()  # fmt: skip
    assert promos == (100, 100)
    linked = db.execute(
        "SELECT count(*) FROM promo_items pi JOIN promos p ON p.id = pi.promo_id"
        " WHERE p.chain_id = %s", (adapter.chain_id,),
    ).fetchone()[0]  # fmt: skip
    assert 0 < linked <= EXPECTED[slug]["item_codes"]  # only items the chain has priced


# (applied, unapplied) of the 100 committed promotions per chain, before and after the two-group
# "buy X, get Y at P % off" reading (docs/adapters.md): the promotions that moved are the "1+1"
# and "השני ב 50%" ones that were `multi_group`.
APPLIED_BEFORE_AND_NOW = {
    "king_store": ((100, 0), (100, 0)),
    "mega": ((93, 7), (93, 7)),
    "osherad": ((99, 1), (99, 1)),
    "ramilevy": ((81, 19), (81, 19)),
    "shufersal": ((89, 11), (90, 10)),  # one "1+1"
    "tivtaam": ((96, 4), (98, 2)),  # two "second at 50 %"; "1+1 מועדון" stays (club_in_description)
    "yohananof": ((93, 7), (94, 6)),  # one "1+1"
}


@pytest.mark.parametrize("slug", sorted(APPLIED_BEFORE_AND_NOW))
def test_how_many_real_promotions_are_applied_now(slug: str) -> None:
    promos = _parsed(slug).promos
    applied = sum(p.reward_type != "other" for p in promos)
    before, now = APPLIED_BEFORE_AND_NOW[slug]
    assert (applied, len(promos) - applied) == now
    pairs = [p for p in promos if p.raw.get("shape") == "pair"]
    assert len(pairs) == now[0] - before[0]
    for p in pairs:
        assert p.reward_type == "buy_x_get_y" and p.raw["unapplied"] is None
        assert p.raw["get_percent"] in ("50", "100") and p.raw["confidence"] in (0.9, 1.0)
        assert p.min_qty == D(1) and p.reward_value == D(1) and p.item_codes


def test_no_real_promotion_is_weekday_restricted() -> None:
    """None of the promotions in the fixtures, nor in the full files of the probe's run 39660333324
    (9972 promotions of seven chains; only Osher Ad's two list all seven days), has a PromotionDays
    other than empty or all seven. The day numbering is therefore not known, and such a promotion
    stays unapplied (``weekday_restricted``, tested on an inline file in test_promo_grouped.py)."""
    for slug in EXPECTED:
        assert all(p.raw["unapplied"] != "weekday_restricted" for p in _parsed(slug).promos)
