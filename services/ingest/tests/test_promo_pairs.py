"""Two-group promotions read as "buy one, get one at a percentage off" ("1+1", "the second at 50 %"),
on small inline files.

Verified on the real files of Shufersal, Tiv Taam and Yohananof (2026-10-21, docs/adapters.md,
"Promotions in real files"; ``test_real_promos.py`` pins the real counts): a trigger group of
``RewardType`` 0 items priced at the shelf price, and a reward group of ``RewardType`` 1 (rate 100,
price 0) or 10 (rate 50, half price), both ``MinQty`` 1. Here each rule has a minimal file; a
regression names the rule. Nothing in these files is from a chain, they only have the shape.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from smartcart_ingest.adapters._common import UNAPPLIED_REASONS
from tests.test_promo_grouped import group, item, only, promo

D = Decimal
A, B, C = "7290000000001", "7290000000002", "7290000000003"


def trigger(code: str, price: str, qty: str = "1.00") -> str:
    """The trigger group's item: RewardType 0, DiscountedPrice = the shelf price."""
    return item(code, reward="0", qty=qty, price=price)


def free(code: str, qty: str = "1.00") -> str:
    return item(code, reward="1", qty=qty, rate="100", price="0.00")


def half(code: str, price: str, qty: str = "1.00", rate: str = "50") -> str:
    return item(code, reward="10", qty=qty, rate=rate, price=price)


def pair(trig: list[str], rew: list[str], **kw):
    return only(promo("1", group(*trig), group(*rew, gid="2"), **kw))


def test_one_plus_one_is_buy_one_get_one_free() -> None:
    p = pair([trigger(A, "18.90")], [free(A)], desc="סטיקס 1+1 מתנה")
    assert (p.reward_type, p.reward_value, p.min_qty) == ("buy_x_get_y", D(1), D(1))
    assert p.raw["get_percent"] == "100" and p.raw["shape"] == "pair"
    assert p.raw["unapplied"] is None and p.raw["confidence"] == 1.0
    assert p.item_codes == [A] and p.max_qty is None


def test_the_second_at_fifty_percent() -> None:
    p = pair([trigger(A, "19.90")], [half(A, "9.95")], desc="קפה השני ב 50%")
    assert (p.reward_type, p.reward_value, p.min_qty) == ("buy_x_get_y", D(1), D(1))
    assert p.raw["get_percent"] == "50" and p.raw["confidence"] == 1.0


def test_the_groups_may_come_in_either_order() -> None:
    p = only(promo("1", group(half(A, "9.95")), group(trigger(A, "19.90"), gid="2"),
                   desc="השני ב 50%"))  # fmt: skip
    assert (p.reward_type, p.raw["get_percent"]) == ("buy_x_get_y", "50")


def test_many_items_link_only_those_in_both_groups() -> None:
    """Tiv Taam's brand promotions list 2 more items in the reward group than in the trigger group:
    those need a trigger of another item, so they are not linked; the rest pair with themselves."""
    p = pair(
        [trigger(A, "19.90"), trigger(B, "30.00")],
        [half(A, "9.95"), half(B, "15.00"), half(C, "8.00")],
        desc="אקופרינד השני ב 50%",
    )
    assert p.reward_type == "buy_x_get_y" and p.item_codes == [A, B]
    assert p.raw["reward_only_items"] == 1
    assert p.raw["confidence"] == 0.9 and p.raw["confidence_reasons"] == ["mixed_items_unverified"]


def test_a_missing_trigger_price_does_not_stop_the_pair() -> None:
    """Rami Levy and Mega publish the trigger group without a price: the reward group's rate and
    price are then the whole reading (nothing to cross-check them against)."""
    p = pair([trigger(A, "")], [half(A, "9.45")], desc="טבלאות שוקולד השני ב-50%")
    assert (p.reward_type, p.raw["get_percent"], p.raw["confidence"]) == ("buy_x_get_y", "50", 1.0)


def test_two_plus_one_the_cheapest_free() -> None:
    """Rami Levy and Shufersal "2+1 הזול מבניהם": buy 2, the third free. Quantities above 1 are
    read only for a free reward (nothing to price)."""
    p = pair([trigger(A, "", qty="2.00")], [free(A)], desc="צלחות רטרו 2+1 הזול מבניהם")
    assert (p.reward_type, p.min_qty, p.reward_value) == ("buy_x_get_y", D(2), D(1))
    assert p.raw["get_percent"] == "100" and p.raw["confidence"] == 1.0


@pytest.mark.parametrize(
    ("trig", "rew", "reason"),
    [
        # the reward price is not the trigger price less the rate: not the reading we verified
        ([trigger(A, "19.90")], [half(A, "9.00")], "reward_values_differ"),
        # a free reward that is not free
        (
            [trigger(A, "19.90")],
            [item(A, reward="1", rate="100", price="3.00")],
            "reward_values_differ",
        ),
        # two rates in one promotion
        (
            [trigger(A, "20.00"), trigger(B, "10.00")],
            [half(A, "10.00"), half(B, "7.50", rate="25")],
            "reward_values_differ",
        ),
        # a rate that is not a discount, a negative price
        ([trigger(A, "19.90")], [half(A, "9.95", rate="150")], "reward_value_unusable"),
        ([trigger(A, "19.90")], [half(A, "-1", rate="50")], "reward_value_unusable"),
        # no rate at all: a reward by price only ("1+3" in Yohananof's files) is not read
        ([trigger(A, "19.90")], [half(A, "9.95", rate="")], "multi_group"),
        # a percentage off is read for 1 and 1 only: other quantities carry prices of unknown meaning
        ([trigger(A, "19.90", qty="2")], [half(A, "9.95")], "multi_group"),
        ([trigger(A, "19.90")], [half(A, "19.90", qty="2")], "multi_group"),
        ([trigger(A, "19.90", qty="1.5")], [free(A)], "multi_group"),
        ([trigger(A, "", qty="11")], [free(A)], "multi_group"),  # beyond what was ever seen
        # nothing in common between the groups
        ([trigger(A, "19.90")], [half(B, "9.95")], "multi_group"),
        # a weighed item: the quantity is a step, not a pack
        ([item(A, reward="0", qty="1", price="19.90", weighed="1")], [free(A)], "multi_group"),
        # a reward type that is not a reward
        ([trigger(A, "19.90")], [item(A, reward="6", rate="50", price="9.95")], "multi_group"),
    ],
)
def test_what_the_file_does_not_prove_is_left_unapplied(trig, rew, reason) -> None:
    p = pair(trig, rew)
    assert (p.reward_type, p.reward_value, p.raw["unapplied"]) == ("other", None, reason)
    assert p.raw["confidence"] == 0.1 and p.raw["confidence_reasons"] == [reason]
    assert reason in UNAPPLIED_REASONS and "shape" not in p.raw


def test_two_trigger_groups_or_two_reward_groups_are_not_a_pair() -> None:
    two_triggers = only(promo("1", group(trigger(A, "10.00")), group(trigger(A, "10.00"), gid="2")))
    assert two_triggers.raw["unapplied"] == "multi_group"
    three = only(promo("2", group(trigger(A, "10.00")), group(free(A), gid="2"),
                       group(free(A), gid="3")))  # fmt: skip
    assert three.raw["unapplied"] == "multi_group"


def test_a_redemption_limit_is_not_applied_anywhere_so_the_promotion_is_not_either() -> None:
    xml = promo("1", group(trigger(A, "10.00")), group(free(A), gid="2"))
    p = only(xml.replace("<RedemptionLimit/>", "<RedemptionLimit>2</RedemptionLimit>"))
    assert p.raw["unapplied"] == "redemption_limited"
    zero = only(xml.replace("<RedemptionLimit/>", "<RedemptionLimit>0</RedemptionLimit>"))
    assert zero.reward_type == "buy_x_get_y"  # 0 is no limit (every real "1+1" says 0)


def test_a_description_that_names_a_club_while_clubid_says_everyone_is_left_alone() -> None:
    """The one Tiv Taam "חמאה 1+1 מועדון" has ClubID "0 - כלל הלקוחות": club-only or not, the file
    does not say, and showing it to everyone could be wrong."""
    p = pair([trigger(A, "24.90")], [free(A)], desc="חמאה 1+1 מועדון", club="0 - כלל הלקוחות")
    assert p.raw["unapplied"] == "club_in_description" and p.reward_type == "other"
    member = pair([trigger(A, "24.90")], [free(A)], desc="חמאה 1+1 מועדון", club="1 - המועדון החדש")
    assert member.reward_type == "buy_x_get_y" and member.club_only


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [({"coupon": "1"}, "coupon_required"), ({"days": "1,2"}, "weekday_restricted")],
)
def test_coupons_and_weekdays_apply_to_a_pair_too(kwargs: dict, reason: str) -> None:
    p = pair([trigger(A, "10.00")], [free(A)], **kwargs)
    assert (p.reward_type, p.raw["unapplied"]) == ("other", reason)


def test_a_basket_condition_is_not_a_pair() -> None:
    p = only(promo("1", group(item("0000000000000", reward="0", price=""), min_purchase="75.00"),
                   group(half(A, "9.95"), gid="2")))  # fmt: skip
    assert p.raw["unapplied"] == "basket_condition"


@pytest.mark.parametrize(
    ("desc", "reward"),
    [
        ("חלב 3% השני ב 50%", "half"),  # a fat percentage in the name is not a discount
        ("מוצר השני בחצי", "half"),  # no number to contradict
        ("מוצר 1+1", "free"),
        ("מוצר", "free"),
    ],
)
def test_a_description_that_agrees_keeps_full_confidence(desc, reward) -> None:
    rewards = {"half": half(A, "9.95"), "free": free(A)}
    p = pair([trigger(A, "19.90" if reward == "half" else "9.95")], [rewards[reward]], desc=desc)
    assert p.reward_type == "buy_x_get_y" and p.raw["confidence"] == 1.0


@pytest.mark.parametrize(
    ("desc", "reward"),
    [
        ("מוצר 2+1", "free"),  # the file says 1 and 1
        ("מוצר 1+1", "half"),  # "1+1" is free, the file says 50 %
        ("מוצר השני ב 30%", "half"),
        ("מוצר השני ב 50%", "free"),
        ("מוצרי נובי ב35% הנחה", "half"),  # Yohananof: description 35 %, file rate 65 (price 35 %)
    ],
)
def test_a_description_that_contradicts_the_fields_is_not_applied(desc, reward) -> None:
    """Pairs are new: where the words and the numbers disagree, no saving is shown."""
    rewards = {"half": half(A, "9.95"), "free": free(A)}
    p = pair([trigger(A, "19.90" if reward == "half" else "9.95")], [rewards[reward]], desc=desc)
    assert (p.reward_type, p.raw["unapplied"]) == ("other", "pair_description_disagrees")
    assert p.raw["confidence"] == 0.1
