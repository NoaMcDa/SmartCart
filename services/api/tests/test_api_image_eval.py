"""The OCR evaluation tooling (scripts/ocr, issues #61, #68), tested locally with the FakeProvider:
the renderer is deterministic and writes consistent ground truth, the scoring counts what it says,
and a whole evaluation over images that carry their own text (``--embed-truth``) scores the
structurer and the catalog resolver without Tesseract. Real OCR numbers come from the
``ocr-eval`` workflow."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image

from smartcart_api.ocr.image import prepare
from smartcart_api.ocr.providers import FakeProvider
from smartcart_catalog.receipt import Receipt, ReceiptItem

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts" / "ocr"
sys.path.insert(0, str(SCRIPTS))

import evaluate  # noqa: E402
import render  # noqa: E402
import score  # noqa: E402

D = Decimal


@pytest.fixture(scope="module")
def images(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("ocr-eval")
    assert render.generate(out, receipts=12, lists=6, seed=3, font=None, embed_truth=True) == 18
    return out


# --- renderer ---------------------------------------------------------------------------------


def test_visual_order_keeps_numbers_left_to_right() -> None:
    assert render.visual("שלום") == "םולש"
    assert render.visual("חלב 3%") == "3% בלח"
    assert render.visual("קוטג' 250 גרם") == "םרג 250 'גטוק"
    assert render.visual("") == ""


def test_the_same_seed_gives_the_same_truth(tmp_path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    render.generate(a, 3, 2, 11, None, False)
    render.generate(b, 3, 2, 11, None, False)
    for f in sorted(a.glob("*.json")):
        assert f.read_text(encoding="utf-8") == (b / f.name).read_text(encoding="utf-8")
    render.generate(tmp_path / "c", 3, 2, 12, None, False)
    assert (tmp_path / "c" / "receipt_001.json").read_text() != (a / "receipt_001.json").read_text()


def test_receipt_truth_adds_up_and_names_real_canonicals(images) -> None:
    names = {p.name for p in render.load_products()}
    for path in sorted(images.glob("receipt_*.json")):
        t = json.loads(path.read_text(encoding="utf-8"))
        assert t["synthetic"] is True and t["chain_id"] in render.CHAIN_HEADERS
        assert 4 <= len(t["items"]) <= 11
        assert all(i["canonical"] in names for i in t["items"])
        subtotal = sum(D(i["price"]) for i in t["items"]) + sum(D(d) for d in t["discounts"])
        assert D(t["total"]) - subtotal in (D(0), D("0.30")), path.name  # 0.30: a bottle deposit


def test_images_are_real_pictures_with_ink(images) -> None:
    for kind in ("receipt", "list"):
        im = Image.open(next(images.glob(f"{kind}_*.png")))
        assert im.mode == "RGB" and 400 < im.width < 900 and im.height > 300


def test_pictures_without_embedded_truth_carry_no_text_chunk(tmp_path) -> None:
    render.generate(tmp_path, 1, 1, 5, None, False)
    assert "sc-ocr" not in Image.open(tmp_path / "receipt_001.png").info
    assert FakeProvider().read(prepare((tmp_path / "list_001.png").read_bytes()), "list").lines == []


def test_embedded_truth_is_what_the_fake_provider_reads(images) -> None:
    t = json.loads((images / "list_001.json").read_text(encoding="utf-8"))
    lines = FakeProvider().read(prepare((images / "list_001.png").read_bytes()), "list").lines
    assert lines == t["lines"]


# --- scoring ----------------------------------------------------------------------------------


def _item(text, qty=None, price="1.00") -> ReceiptItem:
    return ReceiptItem(text=text, raw=text, quantity=None if qty is None else D(qty), price=D(price))


def test_score_receipt_counts_each_field() -> None:
    truth = {
        "chain_id": "7290027600007", "total": "30.00",
        "items": [
            {"printed": "חל' תנובה 3%", "canonical": "x", "quantity": "1", "price": "8.90"},
            {"printed": "לחם אחיד", "canonical": "y", "quantity": "2", "price": "14.00"},
            {"printed": "במבה", "canonical": "z", "quantity": "1", "price": "7.10"},
        ],
    }
    receipt = Receipt(
        chain_id="7290027600007", total=D("30.00"),
        items=[_item("חלב תנובה 3%", None, "8.90"), _item("לחם אחד", "2", "14.50"), _item("שקית", None, "0.30")],
    )
    t = score.score_receipt(truth, receipt)
    assert (t.hit["item text"], t.total["item text"]) == (1, 3)  # the abbreviation is normalized; "לחם אחד" is not exact
    assert (t.hit["quantity"], t.total["quantity"]) == (2, 3)  # milk (none = 1) and bread; bamba unread
    assert (t.hit["price"], t.total["price"]) == (1, 3)  # only the milk
    assert (t.hit["total"], t.hit["chain"]) == (1, 1)
    assert (t.hit["item recall (aligned)"], t.total["item recall (aligned)"]) == (2, 3)
    assert (t.hit["item precision (aligned)"], t.total["item precision (aligned)"]) == (2, 3)


def test_score_receipt_wrong_total_and_chain() -> None:
    truth = {"chain_id": "7290027600007", "total": "30.00", "items": []}
    t = score.score_receipt(truth, Receipt(chain_id=None, total=D("30.01")))
    assert (t.hit["total"], t.hit["chain"]) == (0, 0) and t.total["total"] == t.total["chain"] == 1


def test_score_list_lines_and_rows() -> None:
    truth = {
        "items": [{"written": "2 חלב טרי 3%", "canonical": "חלב טרי 3%"}, {"written": "לחם אחיד", "canonical": "לחם אחיד"}],
        "distractors": ["להתקשר לדני"],
    }
    assert score.score_list_lines(truth, ["2 חלב טרי 3%", "לחם אחד"]).hit["list line read"] == 1
    rows = [
        {"name": "חלב טרי 3%", "input_text": "2 חלב טרי 3%", "needs_confirmation": False, "candidates": []},
        {"name": "קמח לבן", "input_text": "להתקשר לדני", "needs_confirmation": True, "candidates": ["לחם אחיד"]},
    ]
    t = score.score_rows(truth, rows)
    assert (t.hit["catalog recall"], t.total["catalog recall"]) == (1, 2)
    assert (t.hit["catalog recall (top or candidate)"], t.total["catalog recall (top or candidate)"]) == (2, 2)
    assert (t.hit["auto-accepted row precision"], t.total["auto-accepted row precision"]) == (1, 1)
    assert (t.hit["all-row precision"], t.total["all-row precision"]) == (1, 2)
    assert (t.hit["distractors kept out of rows"], t.total["distractors kept out of rows"]) == (0, 1)


def test_tally_rate_and_merge() -> None:
    a, b = score.Tally(), score.Tally()
    a.add("price", True)
    b.add("price", False)
    a.merge(b)
    assert a.rate("price") == 0.5 and a.rate("nothing") is None


# --- a whole evaluation with the fake provider ------------------------------------------------


@pytest.mark.db
def test_evaluation_with_perfect_reading_scores_the_structurer_and_the_catalog(images, db) -> None:
    evaluate.prepare_db(db)
    res = evaluate.evaluate(images, "fake", db, None)
    receipts, lists = res["_tallies"]
    assert res["images"] == {"receipt": 12, "list": 6} and res["failures"] == 0 and res["provider"] == "fake"
    # Perfect OCR text: what is left is the structurer's own accuracy on these layouts.
    assert receipts.rate("chain") == 1.0
    assert receipts.rate("total") == 1.0
    assert receipts.rate("item text") >= 0.95
    assert receipts.rate("quantity") >= 0.95
    assert receipts.rate("price") >= 0.95
    assert receipts.rate("item precision (aligned)") >= 0.95
    assert lists.rate("list line read") == 1.0
    assert lists.rate("catalog recall (top or candidate)") >= 0.8
    # The D5 metric: a row that is not flagged for confirmation is the right product.
    assert lists.rate("auto-accepted row precision") == 1.0
    assert lists.rate("distractors kept out of rows") == 1.0
    text = evaluate.report(res, True)
    assert "SYNTHETIC" in text and "not an accuracy estimate" in text
    assert "| chain |" in text and "| list line read |" in text
