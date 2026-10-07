from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest
from anthropic.types.beta import BetaMessage

from smartcart_catalog.judge import (
    ACCEPT_THRESHOLD,
    REVIEW_CAP,
    REVIEW_THRESHOLD,
    VERDICT_SCHEMA,
    LLMJudge,
    RuleJudge,
    looser,
    route,
)
from smartcart_catalog.models import (
    Attributes,
    Candidate,
    CanonicalProduct,
    Judge,
    NormalizedItem,
    ProductTypeRule,
)

RULES = {
    "milk": ProductTypeRule(product_type="milk", critical_keys=("fat_pct", "state"),
                            soft_keys=("pack_size", "brand")),
    "salmon": ProductTypeRule(product_type="salmon", critical_keys=("state",),
                              soft_keys=("pack_size", "brand")),
    "soy_drink": ProductTypeRule(product_type="soy_drink", critical_keys=(),
                                 soft_keys=("pack_size", "flavor", "brand")),
    "almond_drink": ProductTypeRule(product_type="almond_drink", critical_keys=(),
                                    soft_keys=("pack_size", "flavor", "brand")),
    "cottage": ProductTypeRule(product_type="cottage", critical_keys=("fat_pct",),
                               soft_keys=("pack_size", "brand")),
}  # fmt: skip


def canon(
    cid: int, slug: str, ptype: str, crit: dict, soft: dict, name: str = ""
) -> CanonicalProduct:
    return CanonicalProduct(id=cid, taxonomy_id="x.y", slug=slug, display_name_he=name or slug,
                            product_type=ptype, base_unit="100ml", critical_attrs=crit,
                            soft_attrs=soft)  # fmt: skip


MILK3 = canon(1, "milk-3", "milk", {"fat_pct": 3, "state": "fresh"},
              {"pack_size": 1, "unit": "l", "barcodes": ["7290000000017"]})  # fmt: skip
MILK1 = canon(2, "milk-1", "milk", {"fat_pct": 1, "state": "fresh"}, {"pack_size": 1, "unit": "l"})
SALMON_FRESH = canon(3, "salmon-fresh", "salmon", {"state": "fresh"}, {})
SALMON_FROZEN = canon(4, "salmon-frozen", "salmon", {"state": "frozen"}, {})
SOY = canon(5, "soy", "soy_drink", {}, {"pack_size": 1, "unit": "l"})
ALMOND = canon(6, "almond", "almond_drink", {}, {"pack_size": 1, "unit": "l"})
COTTAGE_250 = canon(7, "cottage-5-250", "cottage", {"fat_pct": 5}, {"pack_size": 250, "unit": "g"})
COTTAGE_500 = canon(8, "cottage-5-500", "cottage", {"fat_pct": 5}, {"pack_size": 500, "unit": "g"})


def item(name: str = "x", iid: int = 100) -> NormalizedItem:
    return NormalizedItem(item_id=iid, clean_name=name)


def cand(c: CanonicalProduct, sim: float) -> Candidate:
    return Candidate(canonical_id=c.id, similarity=sim, canonical=c)


def milk_attrs(
    fat: str | None = "3", state: str | None = "fresh", size="1", unit="l"
) -> Attributes:
    return Attributes(product_type="milk", fat_pct=Decimal(fat) if fat else None, state=state,
                      pack_size=Decimal(size) if size else None, unit=unit)  # fmt: skip


def test_rule_judge_implements_protocol() -> None:
    assert isinstance(RuleJudge(), Judge)
    assert isinstance(LLMJudge(client=object()), Judge)


def test_bands() -> None:
    assert route(0.95) == "accept" and route(ACCEPT_THRESHOLD) == "accept"
    assert route(0.89) == "review" and route(REVIEW_THRESHOLD) == "review"
    assert route(0.59) == "reject"
    assert looser("any_brand", "close") == "close" and looser("exact", "any_brand") == "any_brand"


# --- hard rules: never at any_brand -------------------------------------------------------------


def test_3pct_never_matches_1pct_milk_even_when_more_similar() -> None:
    attrs = milk_attrs(fat="3")
    # The 1% canonical is (wrongly) the nearest neighbour: embeddings barely separate them.
    d = RuleJudge().judge(item(), attrs, [cand(MILK1, 0.99), cand(MILK3, 0.70)], RULES)
    assert d.canonical_id == MILK3.id
    only_wrong = RuleJudge().judge(item(), attrs, [cand(MILK1, 0.99)], RULES)
    assert only_wrong.canonical_id is None and only_wrong.flex_level is None
    assert "fat_pct 3 vs 1" in only_wrong.reason


def test_fresh_never_matches_frozen_salmon() -> None:
    attrs = Attributes(product_type="salmon", state="frozen")
    d = RuleJudge().judge(item(), attrs, [cand(SALMON_FRESH, 0.97)], RULES)
    assert d.canonical_id is None and "state frozen vs fresh" in d.reason
    d2 = RuleJudge().judge(item(), Attributes(product_type="salmon", state="fresh"),
                           [cand(SALMON_FROZEN, 0.97)], RULES)  # fmt: skip
    assert d2.canonical_id is None


def test_soy_never_matches_almond_drink() -> None:
    attrs = Attributes(product_type="soy_drink", pack_size=Decimal(1), unit="l")
    d = RuleJudge().judge(item(), attrs, [cand(ALMOND, 0.95)], RULES)
    assert d.canonical_id is None and "product_type soy_drink vs almond_drink" in d.reason
    ok = RuleJudge().judge(item(), attrs, [cand(ALMOND, 0.95), cand(SOY, 0.80)], RULES)
    assert ok.canonical_id == SOY.id and ok.flex_level == "any_brand"


@pytest.mark.parametrize("sim", [0.5, 0.8, 0.99, 1.0])
def test_critical_mismatch_never_any_brand_at_any_similarity(sim: float) -> None:
    for attrs, wrong in [
        (milk_attrs(fat="1"), MILK3),
        (Attributes(product_type="salmon", state="fresh"), SALMON_FROZEN),
        (Attributes(product_type="almond_drink"), SOY),
    ]:
        assessments = RuleJudge().assess_all(item(), attrs, [cand(wrong, sim)], RULES)
        assert not assessments[0].eligible and assessments[0].flex_level is None
        d = RuleJudge().judge(item(), attrs, [cand(wrong, sim)], RULES)
        assert d.flex_level != "any_brand" and d.canonical_id is None


# --- soft attributes, exact, confidence ---------------------------------------------------------


def test_soft_pack_size_mismatch_is_close_only() -> None:
    attrs = Attributes(product_type="cottage", fat_pct=Decimal(5), pack_size=Decimal(500), unit="g")
    d = RuleJudge().judge(item(), attrs, [cand(COTTAGE_250, 0.9)], RULES)
    assert d.canonical_id == COTTAGE_250.id and d.flex_level == "close"
    assert "pack_size 500 vs 250" in d.reason
    # With both canonicals present the tighter level wins.
    d2 = RuleJudge().judge(item(), attrs, [cand(COTTAGE_250, 0.95), cand(COTTAGE_500, 0.90)], RULES)
    assert d2.canonical_id == COTTAGE_500.id and d2.flex_level == "any_brand"


def test_pack_size_compared_across_units() -> None:
    attrs = milk_attrs(size="1000", unit="ml")
    d = RuleJudge().judge(item(), attrs, [cand(MILK3, 0.9)], RULES)
    assert d.flex_level == "any_brand"


def test_brand_never_demotes_any_brand() -> None:
    attrs = milk_attrs().model_copy(update={"brand": "טרה"})
    c = canon(9, "milk-3b", "milk", {"fat_pct": 3, "state": "fresh"},
              {"pack_size": 1, "unit": "l", "brand": "תנובה"})  # fmt: skip
    assert RuleJudge().judge(item(), attrs, [cand(c, 0.9)], RULES).flex_level == "any_brand"


def test_exact_when_barcode_equal() -> None:
    d = RuleJudge().judge(item(), Attributes(), [cand(MILK3, 0.3)], RULES, barcode="7290000000017")
    assert d.flex_level == "exact" and d.confidence == 1.0 and not d.needs_review
    assert d.source == "rule"
    via_map = RuleJudge(barcodes={100: "7290000000017"}).judge(item(), Attributes(),
                                                               [cand(MILK3, 0.3)], RULES)  # fmt: skip
    assert via_map.flex_level == "exact"


def test_high_similarity_and_all_critical_verified_is_auto_accepted() -> None:
    d = RuleJudge().judge(item(), milk_attrs(), [cand(MILK3, 0.80)], RULES)
    assert d.confidence >= ACCEPT_THRESHOLD and not d.needs_review
    assert d.flex_level == "any_brand" and d.source == "rule"
    assert "critical match" in d.reason


def test_unknown_critical_value_goes_to_review_never_auto_accept() -> None:
    d = RuleJudge().judge(item(), milk_attrs(fat=None), [cand(MILK3, 1.0)], RULES)
    assert d.canonical_id == MILK3.id and d.needs_review
    assert d.confidence <= REVIEW_CAP and "critical unknown fat_pct" in d.reason


def test_low_similarity_is_rejected_and_medium_reviewed() -> None:
    attrs = Attributes(product_type="salmon")  # state unknown
    low = RuleJudge().judge(item(), attrs, [cand(SALMON_FRESH, 0.1)], RULES)
    assert low.canonical_id is None and low.confidence < REVIEW_THRESHOLD
    mid = RuleJudge().judge(item(), Attributes(product_type="salmon", state="fresh"),
                            [cand(SALMON_FRESH, 0.40)], RULES)  # fmt: skip
    assert mid.canonical_id == SALMON_FRESH.id and mid.needs_review
    assert REVIEW_THRESHOLD <= mid.confidence < ACCEPT_THRESHOLD


def test_ambiguous_candidates_go_to_review() -> None:
    twin = canon(10, "milk-3-twin", "milk", {"fat_pct": 3, "state": "fresh"},
                 {"pack_size": 1, "unit": "l"})  # fmt: skip
    d = RuleJudge().judge(item(), milk_attrs(), [cand(MILK3, 0.90), cand(twin, 0.90)], RULES)
    assert d.needs_review and "ambiguous" in d.reason


def test_missing_rule_caps_confidence() -> None:
    c = canon(11, "mystery", "mystery_type", {}, {})
    d = RuleJudge().judge(item(), Attributes(product_type="mystery_type"), [cand(c, 1.0)], RULES)
    assert d.needs_review and "no product_type_rules row" in d.reason


def test_no_candidates() -> None:
    d = RuleJudge().judge(item(), milk_attrs(), [], RULES)
    assert d.canonical_id is None and d.confidence == 0 and "no candidates" in d.reason


# --- LLM judge with recorded responses (never the network) --------------------------------------


def recorded(text: str | None, stop_reason: str = "end_turn") -> BetaMessage:
    """A Messages API response in the recorded shape (``BetaMessage``)."""
    content: list[dict[str, Any]] = [{"type": "thinking", "thinking": "", "signature": "sig"}]
    if text is not None:
        content.append({"type": "text", "text": text})
    data: dict[str, Any] = {
        "id": "msg_recorded", "type": "message", "role": "assistant",
        "model": "claude-sonnet-5-5", "content": content, "stop_reason": stop_reason,
        "stop_sequence": None, "usage": {"input_tokens": 812, "output_tokens": 64},
    }  # fmt: skip
    if stop_reason == "refusal":
        data["content"] = []
        data["stop_details"] = {"type": "refusal", "category": None, "explanation": "declined"}
    return BetaMessage.model_validate(data)


class ReplayClient:
    """Stands in for ``anthropic.Anthropic``: records requests, replays responses."""

    def __init__(self, *responses: BetaMessage) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.beta = self
        self.messages = self

    def create(self, **kwargs: Any) -> BetaMessage:
        self.requests.append(kwargs)
        return self.responses.pop(0)


def verdict(cid: int | None, level: str | None, conf: float, reason: str = "same product") -> str:
    return json.dumps({"canonical_id": cid, "flex_level": level, "confidence": conf,
                       "reason": reason})  # fmt: skip


def test_llm_judge_request_shape_and_accept() -> None:
    client = ReplayClient(recorded(verdict(MILK3.id, "any_brand", 0.96)))
    judge = LLMJudge(client)
    d = judge.judge(item("חלב טרי 3% 1 ליטר"), milk_attrs(), [cand(MILK3, 0.8), cand(MILK1, 0.85)],
                    RULES)  # fmt: skip
    assert d.canonical_id == MILK3.id and d.flex_level == "any_brand" and not d.needs_review
    assert d.source == "model"
    req = client.requests[0]
    assert req["model"] == "claude-sonnet-5-5"
    assert req["output_config"]["format"] == {"type": "json_schema", "schema": VERDICT_SCHEMA}
    assert req["fallbacks"] == "default" and req["betas"] == ["server-side-fallback-2026-07-01"]
    prompt = json.loads(req["messages"][0]["content"])
    # The vetoed 1% canonical is never shown to the model.
    assert [c["canonical_id"] for c in prompt["candidates"]] == [MILK3.id]
    assert "barcodes" not in prompt["candidates"][0]["soft_attrs"]


def test_llm_cannot_pick_a_vetoed_candidate() -> None:
    client = ReplayClient(recorded(verdict(MILK1.id, "any_brand", 0.99)))
    d = LLMJudge(client).judge(item(), milk_attrs(fat="3"), [cand(MILK1, 0.9), cand(MILK3, 0.8)],
                               RULES)  # fmt: skip
    assert d.canonical_id is None and "not an eligible candidate" in d.reason


def test_llm_cannot_tighten_the_rule_level() -> None:
    attrs = Attributes(product_type="cottage", fat_pct=Decimal(5), pack_size=Decimal(500), unit="g")
    client = ReplayClient(recorded(verdict(COTTAGE_250.id, "any_brand", 0.95)))
    d = LLMJudge(client).judge(item(), attrs, [cand(COTTAGE_250, 0.9)], RULES)
    assert d.flex_level == "close"


def test_llm_medium_confidence_and_unknown_critical_go_to_review() -> None:
    client = ReplayClient(recorded(verdict(MILK3.id, "any_brand", 0.75)),
                          recorded(verdict(MILK3.id, "any_brand", 0.99)))  # fmt: skip
    judge = LLMJudge(client)
    assert judge.judge(item(), milk_attrs(), [cand(MILK3, 0.8)], RULES).needs_review
    unknown = judge.judge(item(), milk_attrs(fat=None), [cand(MILK3, 0.8)], RULES)
    assert unknown.needs_review and unknown.confidence <= REVIEW_CAP


def test_llm_none_refusal_and_invalid_output() -> None:
    client = ReplayClient(recorded(verdict(None, None, 0.9, "no candidate fits")),
                          recorded(None, stop_reason="refusal"), recorded("not json"))  # fmt: skip
    judge = LLMJudge(client)
    for expected in ("model chose none", "refusal", "invalid model output"):
        d = judge.judge(item(), milk_attrs(), [cand(MILK3, 0.8)], RULES)
        assert d.canonical_id is None and expected in d.reason


def test_llm_skips_the_call_for_barcode_and_vetoed_only() -> None:
    client = ReplayClient()
    judge = LLMJudge(client)
    exact = judge.judge(item(), milk_attrs(), [cand(MILK3, 0.5)], RULES, barcode="7290000000017")
    assert exact.flex_level == "exact"
    vetoed = judge.judge(item(), milk_attrs(fat="1"), [cand(MILK3, 0.9)], RULES)
    assert vetoed.canonical_id is None
    assert client.requests == []


def test_llm_judge_never_builds_a_real_client_when_one_is_given(monkeypatch) -> None:
    import anthropic

    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("network client created in a test")

    monkeypatch.setattr(anthropic, "Anthropic", boom)
    client = ReplayClient(recorded(verdict(MILK3.id, "any_brand", 0.95)))
    assert LLMJudge(client).judge(item(), milk_attrs(), [cand(MILK3, 0.8)], RULES).canonical_id
