"""The grouped promotion layout the real PromoFull files use (``Groups/Group/PromotionItems/
PromotionItem``), club values and date-times, on small inline files.

The layout and the readings were verified on real files fetched by the Portal probe on 2026-10-21
(docs/adapters.md, "Promotions in real files"); ``test_real_promos.py`` checks them against the
committed real fixtures. Here each rule has a minimal file of its own, so a regression names the
rule. Nothing in these files is from a chain; they only have the shape.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from smartcart_ingest.adapters._common import (
    UNAPPLIED_REASONS,
    Club,
    parse_club,
    promo_parse_confidence,
    resolve_clubs,
)
from smartcart_ingest.adapters.shufersal import ShufersalAdapter

D = Decimal
ISRAEL = ZoneInfo("Asia/Jerusalem")
FILE = "PromoFull7290027600007-001-116-20261021-043100.xml"


def item(code="7290000000001", reward="3", qty="1", rate="", price="", per_mida="", weighed="0"):
    return (
        f"<PromotionItem><ItemCode>{code}</ItemCode><ItemType>1</ItemType>"
        f"<RewardType>{reward}</RewardType><MinQty>{qty}</MinQty><MaxQty/>"
        f"<DiscountRate>{rate}</DiscountRate><DiscountedPrice>{price}</DiscountedPrice>"
        f"<DiscountedPricePerMida>{per_mida}</DiscountedPricePerMida>"
        f"<bIsWeighted>{weighed}</bIsWeighted></PromotionItem>"
    )


def group(*items, gid="1", min_purchase="", discount_type=""):
    return (
        f"<Group><GroupID>{gid}</GroupID><MinPurchaseAmount>{min_purchase}</MinPurchaseAmount>"
        f"<DiscountType>{discount_type}</DiscountType><PromotionItems>{''.join(items)}"
        "</PromotionItems></Group>"
    )


def promo(
    pid,
    *groups,
    desc="מוצר",
    club="0",
    coupon="0",
    days="",
    start="2026-10-20T00:00:00.000",
    end="2026-10-30T23:59:00.000",
    start_hour="",
    end_hour="",
):
    return (
        f"<Promotion><PromotionUpdateTime>2026-10-19T10:00:00.000</PromotionUpdateTime>"
        f"<AllowMultipleDiscounts>0</AllowMultipleDiscounts><PromotionID>{pid}</PromotionID>"
        f"<PromotionDescription>{desc}</PromotionDescription>"
        f"<PromotionStartDateTime>{start}</PromotionStartDateTime>"
        f"<PromotionEndDateTime>{end}</PromotionEndDateTime>"
        f"<PromotionStartHour>{start_hour}</PromotionStartHour>"
        f"<PromotionEndHour>{end_hour}</PromotionEndHour><PromotionDays>{days}</PromotionDays>"
        f"<RedemptionLimit/><MinNoOfItemOffered>10</MinNoOfItemOffered><ClubID>{club}</ClubID>"
        f"<IsGiftItem/><AdditionalIsCoupon>{coupon}</AdditionalIsCoupon>"
        f"<AdditionalRestrictions/><Remarks/><Groups>{''.join(groups)}</Groups></Promotion>"
    )


def parse(*promos):
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?><Root><ChainID>7290027600007</ChainID>'
        "<SubChainID>001</SubChainID><StoreID>116</StoreID><BikoretNo>0</BikoretNo>"
        f"<Promotions>{''.join(promos)}</Promotions></Root>"
    ).encode()
    adapter = ShufersalAdapter()
    return adapter.parse(adapter.raw_file_for(FILE, xml), xml)


def only(*promos):
    parsed = parse(*promos)
    assert len(parsed.promos) == len(promos)
    return parsed.promos[0] if len(promos) == 1 else parsed.promos


# --------------------------------------------------------------------------- rewards


def test_rewardtype_3_is_the_price_of_one_unit() -> None:
    p = only(promo("1", group(item(reward="3", qty="1", rate="14.39", price="11.90"))))
    assert (p.reward_type, p.reward_value, p.min_qty) == ("price", D("11.90"), D(1))
    assert p.raw["confidence"] == 1.0 and p.raw["unapplied"] is None
    assert p.raw["layout"] == "grouped" and p.store_code == "116"


@pytest.mark.parametrize("reward", ["1", "3", "10"])
def test_discounted_price_is_the_total_for_min_qty(reward: str) -> None:
    """Verified on shelf prices: 2 for 19.90 with a 22.87 % discount is a 12.90 shelf price."""
    p = only(promo("1", group(item(reward=reward, qty="2", rate="22.87", price="19.90"))))
    assert (p.reward_type, p.reward_value, p.min_qty) == ("bundle", D("19.90"), D(2))


def test_weighed_item_uses_the_price_per_kg() -> None:
    per_kg = only(promo("1", group(item(qty="0.1", price="49.90", per_mida="49.90", weighed="1"))))
    assert (per_kg.reward_type, per_kg.reward_value, per_kg.min_qty) == ("price", D("49.90"), D(1))
    # "2 kg for 89.90": the bundle total, 44.95 a kg.
    two_kg = only(promo("2", group(item("7", "1", "2", "24.96", "89.90", "44.95", "1"))))
    assert (two_kg.reward_type, two_kg.reward_value, two_kg.min_qty) == ("bundle", D("89.90"), D(2))
    # "500 g for 25" (published MinQty 0.5, per kg 50): a per-kg price, not 25 a kg.
    half = only(promo("3", group(item(reward="3", qty="0.5", price="25.00", per_mida="50.00",
                                      weighed="1"))))  # fmt: skip
    assert (half.reward_type, half.reward_value) == ("price", D("50.00"))


def test_rewardtype_2_is_a_percentage_in_percent_units() -> None:
    p = only(promo("1", group(item(reward="2", rate="60.00", price="75.60"))))
    assert (p.reward_type, p.reward_value, p.min_qty) == ("percent", D("60.00"), D(1))


def test_percent_with_weighed_and_unit_items_is_one_reading() -> None:
    """The brand-wide 5 % promotion mixes MinQty 1.00 and 0.01 (weighed items)."""
    p = only(promo("1", group(item(reward="2", qty="1.00", rate="5", price="13.21"),
                              item("7290000000002", reward="2", qty="0.01", rate="5",
                                   price="6.56", weighed="1"))))  # fmt: skip
    assert (p.reward_type, p.reward_value) == ("percent", D("5"))
    assert p.item_codes == ["7290000000001", "7290000000002"]


@pytest.mark.parametrize("rate", ["100", "", "0", "250"])
def test_a_percentage_that_is_not_a_discount_is_not_applied(rate: str) -> None:
    p = only(promo("1", group(item(reward="2", rate=rate, price="0.00"))))
    assert (p.reward_type, p.raw["unapplied"]) == ("other", "reward_value_unusable")


# --------------------------------------------------------------------------- not applied


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"coupon": "1"}, "coupon_required"),
        ({"days": "1,2,3"}, "weekday_restricted"),
        ({"days": "6,7"}, "weekday_restricted"),
    ],
)
def test_promotion_level_conditions_are_read_but_not_applied(kwargs: dict, reason: str) -> None:
    p = only(promo("1", group(item(qty="1", price="11.90", rate="10")), **kwargs))
    assert (p.reward_type, p.reward_value, p.raw["unapplied"]) == ("other", None, reason)
    assert p.raw["confidence"] == 0.1 and p.raw["confidence_reasons"] == [reason]
    assert p.item_codes == ["7290000000001"]  # still linked to its item


@pytest.mark.parametrize("desc", ["זיכוי אריזה ירקות דלעת", "קיזוז אריזה ג.עופר פילה אמנון"])
def test_a_packaging_credit_is_not_a_discount(desc: str) -> None:
    p = only(promo("1", group(item(reward="10", qty="0.5", rate="1", price="14.51")), desc=desc))
    assert (p.reward_type, p.raw["unapplied"]) == ("other", "packaging_credit")


def test_every_weekday_is_no_restriction() -> None:
    p = only(promo("1", group(item(price="11.90")), days="1,2,3,4,5,6,7"))
    assert p.reward_type == "price"


def test_a_minimum_purchase_amount_is_a_basket_condition() -> None:
    p = only(promo("1", group(item("0000000000000", reward="0", price=""), min_purchase="99.00"),
                   group(item(price="69.90"), gid="2")))  # fmt: skip
    assert p.raw["unapplied"] == "basket_condition" and p.raw["min_purchase_amount"] == "99.00"
    assert p.item_codes == ["7290000000001"]  # the all-zeros item is "any item", not a product
    assert [g["items"] for g in p.raw["groups"]] == [1, 1]


def test_a_minimum_purchase_in_the_reward_group_itself_is_a_basket_condition() -> None:
    p = only(promo("1", group(item(reward="10", qty="0.01", price="39.90", weighed="1"),
                              min_purchase="75.00")))  # fmt: skip
    assert p.raw["unapplied"] == "basket_condition"


def test_two_groups_that_are_not_a_pair_are_not_applied() -> None:
    """The trigger and the reward are different products: whatever the store does at the till, a
    per-item price cannot show it (the same-item pairs are read, test_promo_pairs.py)."""
    p = only(promo("1", group(item(reward="0", qty="3", price="7.90")),
                   group(item("7290000000002", reward="1", qty="1", rate="100", price="0.00"),
                         gid="2")))  # fmt: skip
    assert p.raw["unapplied"] == "multi_group"


def test_items_that_disagree_are_not_applied() -> None:
    p = only(promo("1", group(item(price="11.90"), item("7290000000002", price="12.90"))))
    assert p.raw["unapplied"] == "reward_values_differ"


def test_unknown_reward_types_are_not_applied() -> None:
    for reward in ("0", "6", "99"):
        p = only(promo("1", group(item(reward=reward, price="1.00"))))
        assert p.raw["unapplied"] == "reward_type_unhandled", reward
    assert set(UNAPPLIED_REASONS) >= {"coupon_required", "basket_condition", "multi_group"}


def test_a_malformed_number_in_an_item_is_missing_not_a_file_error() -> None:
    p = only(promo("1", group(item(price="abc"))))
    assert p.raw["unapplied"] == "reward_value_unusable"


# --------------------------------------------------------------------------- dates and clubs


def test_date_time_fields_give_the_window_and_the_hours_only_repeat_them() -> None:
    p = only(promo("1", group(item(price="11.90")), start="2026-10-04T00:01:00.000",
                   end="2026-10-30T23:59:00.000", start_hour="00:01:00.000",
                   end_hour="23:59:00.000"))  # fmt: skip
    assert p.starts_at == datetime(2026, 10, 4, 0, 1, tzinfo=ISRAEL)
    assert p.ends_at == datetime(2026, 10, 30, 23, 59, tzinfo=ISRAEL)
    assert p.hours is None  # not a daily window


def test_a_missing_end_leaves_the_window_open_and_lowers_confidence() -> None:
    p = only(promo("1", group(item(price="11.90")), end=""))
    assert p.ends_at is None
    assert p.raw["confidence"] == 0.9 and p.raw["confidence_reasons"] == ["end_date_missing"]


@pytest.mark.parametrize("value", ["", "0", "0 - כלל הלקוחות", " 0 "])
def test_club_zero_is_every_customer(value: str) -> None:
    assert parse_club(value) == Club(True, None)
    assert resolve_clubs([value]) == (False, None, None)


def test_a_numbered_club_takes_its_label() -> None:
    assert parse_club("1 - המועדון החדש") == Club(False, "המועדון החדש")
    assert parse_club("1") == Club(False, "מועדון לקוחות")
    assert parse_club("7") == Club(False, "club 7")
    p = only(promo("1", group(item(price="11.90")), club="1 - המועדון החדש"))
    assert (p.club_only, p.club_name) == (True, "המועדון החדש")


def test_a_club_expression_lists_its_alternatives() -> None:
    mega = "(2=מועדון קרפור אשראי|2=מועדון אפליקציה)"
    assert parse_club(mega) == Club(False, "מועדון קרפור אשראי | מועדון אפליקציה", True)
    king = '("לקוחות הקפה=3" | "מועדון לקוחות=3")'
    assert parse_club(king) == Club(False, "לקוחות הקפה | מועדון לקוחות", True)
    rami = "((2=מועדון לקוחות אשראי))&(3=תווי זיכוי|3=מולטיפס)"
    assert parse_club(rami).name == "מועדון לקוחות אשראי | תווי זיכוי | מולטיפס"
    p = only(promo("1", group(item(price="11.90")), club=mega))
    assert (p.club_only, p.club_name) == (True, "מועדון קרפור אשראי | מועדון אפליקציה")
    assert p.raw["club_expression"] == mega and p.raw["club_ids"] == [mega]


def test_a_long_expression_is_shortened_but_kept_in_raw() -> None:
    names = [f"קבוצה {i}" for i in range(30)]
    expr = "(" + "|".join(f'"{n}=3"' for n in names) + ")"
    club = parse_club(expr)
    assert club.name == "קבוצה 0 | קבוצה 1 | קבוצה 2 | +27"
    assert only(promo("1", group(item(price="11.90")), club=expr)).raw["club_expression"] == expr


# --------------------------------------------------------------------------- confidence


def test_a_percent_that_is_a_product_attribute_is_not_a_disagreement() -> None:
    """Real descriptions: 3.6 % milk fat, 100 % juice, 25 % cream cheese."""
    for text in ("חלב 3.6% בבקבוק 2 ב 15.90", "מיץ ענבים 100% ב11.90", "גבינת שמנת 25% 230 גרם"):
        got = promo_parse_confidence("bundle", min_qty=D(2), gift_count=None, description=text,
                                     ends_at=datetime(2026, 10, 30), reward_value=D("15.90"))  # fmt: skip
        assert got == (1.0, []), text


def test_n_for_p_in_the_description_must_match_the_fields() -> None:
    kwargs = {"min_qty": D(3), "gift_count": None, "ends_at": datetime(2026, 10, 30)}
    ok = promo_parse_confidence("bundle", description="בירה 3 ב 25.90", reward_value=D("25.90"),
                                **kwargs)  # fmt: skip
    assert ok == (1.0, [])
    bad = promo_parse_confidence("bundle", description="בירה 3 ב 25.9", reward_value=D("25.00"),
                                 **kwargs)  # fmt: skip
    assert bad == (0.7, ["description_disagrees"])
    wrong_price = promo_parse_confidence(
        "bundle", description="בירה 2 ב 30", reward_value=D("25"), **kwargs
    )
    assert wrong_price == (0.7, ["description_disagrees"])
    # The price is the published one; the "26" is part of a product name.
    name_number = promo_parse_confidence(
        "bundle", description="יין פורטה 26 ב 90", reward_value=D("90"), **kwargs
    )
    assert name_number == (1.0, [])
    # A weighed "2 for 120" is 1.9 kg for 114 in the fields: the same price per unit.
    weighed = promo_parse_confidence(
        "bundle", description="בשר טחון 2 ב 120", min_qty=D("1.9"), gift_count=None,
        ends_at=datetime(2026, 10, 30), reward_value=D("114"),
    )  # fmt: skip
    assert weighed == (1.0, [])


def test_a_very_long_club_label_is_shortened() -> None:
    label = "מועדון לקוחות & " * 30
    club = parse_club(f"3 - {label}")
    assert club.name is not None and len(club.name) <= 120 and club.name.endswith("\u2026")
    p = only(promo("1", group(item(price="11.90")), club=f"3 - {label}".replace("&", "&amp;")))
    assert p.raw["club_ids"] == [f"3 - {label}".strip()]
