"""Tesseract reading (issues #61, #68): the root causes the first runner evaluation exposed.

* The synthetic receipts were drawn with a font that has no digits (Noto Sans Hebrew): Tesseract
  read empty boxes as "0" and "o". That was the renderer (tested in test_api_image_eval.py).
* Real Tesseract behaviour, recorded in ``fixtures/tesseract_*.tsv`` (Tesseract 5.3.4, the ``heb``
  and ``eng`` fast models, on the synthetic images): the Hebrew model misreads digits that the
  English model reads right, and plain text output does not keep the order of a Hebrew line.
  ``ocr/layout.py`` rebuilds lines from word boxes and merges two passes; ``TesseractProvider``
  runs them. No binary is needed here: the TSV is the recorded output.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from smartcart_api.ocr import layout, providers
from smartcart_api.ocr.layout import Word
from smartcart_api.ocr.providers import TesseractProvider, prepare_for_ocr
from smartcart_catalog.receipt import parse_receipt

FIX = Path(__file__).parent / "fixtures"


def tsv(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def w(text, left, top=100, width=60, height=26, conf=92.0, line=(1, 1, 1)) -> Word:
    return Word(left, top, width, height, conf, text, line)


# --- parsing ----------------------------------------------------------------------------------


def test_parse_tsv_keeps_words_with_boxes() -> None:
    words = layout.parse_tsv(tsv("tesseract_receipt_heb_eng.tsv"))
    assert len(words) == 51
    assert words[0].text == "טיב" and words[0].width > 0 and words[0].line == (1, 1, 1)
    assert all(x.text and x.conf >= layout.MIN_CONF for x in words)


def test_parse_tsv_drops_noise_marks_and_non_word_rows() -> None:
    raw = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "4\t1\t1\t1\t1\t0\t10\t10\t90\t20\t-1\t\n"
        "5\t1\t1\t1\t1\t1\t10\t10\t40\t20\t95.5\t‏חלב‎\n"
        "5\t1\t1\t1\t1\t2\t60\t10\t40\t20\t3.0\tnoise\n"
        "5\t1\t1\t1\t1\t3\t90\t10\t40\t20\t90\t  \n"
        "5\tx\n"
    )
    assert [x.text for x in layout.parse_tsv(raw)] == ["חלב"]


# --- order ------------------------------------------------------------------------------------


def test_a_hebrew_line_is_read_from_the_right_edge() -> None:
    # Tesseract printed these left to right ("נוזל לניקוי רצפות" came back reversed)
    line = [w("רצפות", 100), w("לניקוי", 200), w("נוזל", 300)]
    assert [x.text for x in layout.order_rtl(line)] == ["נוזל", "לניקוי", "רצפות"]


def test_list_lines_use_boxes_not_the_printed_order() -> None:
    words = [
        w("חמוצים", 100, line=(1, 1, 1)), w("מלפפונים", 200, line=(1, 1, 1)), w("2", 330, line=(1, 1, 1)),
        w("אדום", 120, top=180, line=(1, 1, 2)), w("פלפל", 220, top=180, line=(1, 1, 2)),
    ]
    assert layout.list_lines(words) == ["2 מלפפונים חמוצים", "פלפל אדום"]


def test_list_lines_drop_latin_garbage_but_keep_numbers_and_size_letters() -> None:
    words = [w("Au", 10), w("הולדת", 100), w("L", 60), w("2", 400), w("By", 30)]
    assert layout.list_lines(words) == ["2 הולדת L"]


def test_recorded_list_is_rebuilt_in_logical_order() -> None:
    lines = layout.list_lines(layout.parse_tsv(tsv("tesseract_list_heb_eng.tsv")))
    assert lines[:3] == ["יוגורט תות", "2 נייך אפייה", "ביצי חופש L"]
    assert "ללכת לבנק" in lines and "קפה נמס" in lines


# --- the two-pass merge -----------------------------------------------------------------------


def merged(a: str, b: str) -> list[str]:
    return layout.merge_receipt(layout.parse_tsv(tsv(a)), layout.parse_tsv(tsv(b)))


def test_recorded_receipt_prices_come_from_the_english_pass() -> None:
    assert merged("tesseract_receipt_heb_eng.tsv", "tesseract_receipt_eng.tsv") == [
        "טיב טעם", "סניף: נתניה", "ח.פ 562992312", "חשבונית מס מספר 95319",
        "תאריך 02/10/2026 שעה 09:52", "מטבוחה 1.5 ל' 12.35", "גב' טרה לבנה 3% 56.38", "X2 28.19",
        "פיתות 11.55", "תירס שטראוס קפוא 500 גרם 14.64", "7.32X2", "נאגטס עוף 26.32",
        'סה"כ פריטים 5', 'סה"כ 121.24', "לתשלום 121.24", 'מע"מ 18% 18.49', "אשראי ויזה ****1234",
        "תודה ולהתראות",
    ]


def test_recorded_receipt_structures_into_the_printed_items() -> None:
    r = parse_receipt(merged("tesseract_receipt3_heb_eng.tsv", "tesseract_receipt3_eng.tsv"))
    assert (r.chain_id, r.total) == ("7290803800003", r.total) and str(r.total) == "128.30"
    got = [(i.text, str(i.quantity), str(i.price)) for i in r.items]
    assert got == [
        ("גרעינים 1.5 ליטר", "None", "8.68"),
        ("עדשים שטראוס כתומות 500 גרם", "None", "22.36"),
        ("בירה לאגר 250 גרם", "None", "8.46"),
        ("מגבונים יטבתה לחים", "None", "7.64"),
        ("אקונומיקה", "2", "58.64"),
        ("אורז דנונה עגול 1.5 ליטר", "None", "22.22"),
    ]


def test_a_second_pass_number_replaces_the_first_passes_misreading() -> None:
    a = [w("חלב", 800, line=(1, 1, 1)), w("12335", 50, conf=60, line=(1, 1, 1))]
    b = [w("12.35", 50, conf=95)]
    assert layout.merge_receipt(a, b) == ["חלב 12.35"]


def test_the_first_pass_keeps_a_number_it_is_much_surer_about() -> None:
    # B read "71.5" over "1.5 ל'" with conf 15: the English model is guessing at Hebrew letters
    a = [w("גרעינים", 900), w("1.5", 830, width=46, conf=93), w("ל'", 798, width=23)]
    b = [w("71.5", 798, width=82, conf=15)]
    assert layout.merge_receipt(a, b) == ["גרעינים 1.5 ל'"]


def test_digits_the_english_pass_invents_over_hebrew_are_ignored() -> None:
    a = [w("סבון", 900), w("יטבתה", 800)]
    assert layout.merge_receipt(a, [w("1120", 895, conf=80)]) == ["סבון יטבתה"]  # over a Hebrew word
    junk = [w("סבון", 900), w("DON", 700, conf=40)]
    assert layout.merge_receipt(junk, [w("1120", 700, conf=80)]) == ["סבון"]  # over Latin garbage


def test_a_price_the_english_pass_finds_alone_joins_its_row_or_starts_one() -> None:
    a = [w("חסה", 900, top=100, line=(1, 1, 1))]
    same_row = [w("27.93", 50, top=102, width=80, conf=90)]
    assert layout.merge_receipt(a, same_row) == ["חסה 27.93"]
    below = [w("2", 880, top=300, conf=90), w("X", 800, top=300, conf=90), w("5.67", 700, top=300, width=70, conf=90)]
    lines = layout.merge_receipt(a, below)
    assert lines == ["חסה", "X 5.67"]  # the price and the sign start a line; the bare "2" is noise
    assert layout.merge_receipt(a, [w("5", 100, top=300)]) == ["חסה"]  # a lone digit is noise


def test_first_pass_numbers_the_second_pass_missed_are_kept() -> None:
    a = [w("לחם", 900), w("7.50", 50, conf=94)]
    assert layout.merge_receipt(a, []) == ["לחם 7.50"]


def test_size_letters_are_kept_and_latin_garbage_is_not() -> None:
    a = [w("ביצים", 900), w("XL", 840, width=30), w("MESS)", 700, conf=50)]
    assert layout.merge_receipt(a, []) == ["ביצים XL"]


def test_lines_come_out_top_to_bottom() -> None:
    a = [w("ב", 900, top=300, line=(1, 1, 2)), w("א", 900, top=100, line=(1, 1, 1))]
    assert layout.merge_receipt(a, []) == ["א", "ב"]


# --- the provider -----------------------------------------------------------------------------


class FakeTesseract:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append({"cmd": cmd, **kwargs})
        from types import SimpleNamespace

        name = {
            ("heb+eng", "4"): "tesseract_receipt_heb_eng.tsv",
            ("eng", "4"): "tesseract_receipt_eng.tsv",
            ("heb+eng", "6"): "tesseract_list_heb_eng.tsv",
        }[(cmd[cmd.index("-l") + 1], cmd[cmd.index("--psm") + 1])]
        return SimpleNamespace(returncode=0, stdout=tsv(name).encode(), stderr=b"")


@pytest.fixture
def fake_tesseract(monkeypatch):
    run = FakeTesseract()
    monkeypatch.setattr(providers.shutil, "which", lambda name: "/usr/bin/tesseract")
    monkeypatch.setattr(providers.subprocess, "run", run)
    return run


def test_a_receipt_is_read_twice_and_a_list_once(fake_tesseract) -> None:
    img = Image.new("RGB", (700, 700), "white")
    result = TesseractProvider().read(img, "receipt")
    langs_psm = [(c["cmd"][c["cmd"].index("-l") + 1], c["cmd"][c["cmd"].index("--psm") + 1]) for c in fake_tesseract.calls]
    assert langs_psm == [("heb+eng", "4"), ("eng", "4")]
    assert "מטבוחה 1.5 ל' 12.35" in result.lines and result.provider == "tesseract"
    fake_tesseract.calls.clear()
    lst = TesseractProvider().read(img, "list")
    assert [(c["cmd"][c["cmd"].index("-l") + 1]) for c in fake_tesseract.calls] == ["heb+eng"]
    assert lst.lines[0] == "יוגורט תות"


def test_tesseract_gets_the_image_on_stdin_and_asks_for_tsv(fake_tesseract) -> None:
    TesseractProvider().read(Image.new("RGB", (700, 700), "white"), "receipt")
    for call in fake_tesseract.calls:
        assert call["cmd"][:4] == ["/usr/bin/tesseract", "stdin", "stdout", "-l"]
        assert call["cmd"][-1] == "tsv" and "--dpi" in call["cmd"]
        assert call["input"][:8] == b"\x89PNG\r\n\x1a\n"  # in memory, through a pipe
        assert call["capture_output"] is True


# --- preprocessing ----------------------------------------------------------------------------


def test_small_images_are_enlarged_and_stretched_never_shrunk() -> None:
    small = Image.new("RGB", (700, 600), (120, 120, 120))
    out = prepare_for_ocr(small)
    assert out.mode == "L" and out.width == 1050 and out.height == 900
    tiny = prepare_for_ocr(Image.new("RGB", (300, 200), "white"))
    assert tiny.width == 600  # capped at 2x
    big = prepare_for_ocr(Image.new("RGB", (2400, 1800), "white"))
    assert big.size == (2400, 1800)


def test_contrast_is_stretched() -> None:
    dull = Image.new("RGB", (1100, 40), (180, 180, 180))
    for x in range(1100):
        for y in range(10):
            dull.putpixel((x, y), (90, 90, 90))
    lo, hi = prepare_for_ocr(dull).getextrema()
    assert lo < 10 and hi > 245
