"""Turn Tesseract word boxes (TSV) into text lines in logical order. Pure, no I/O.

Two things went wrong when Tesseract's plain text output was used (measured on the first runner
evaluation, then locally with Tesseract 5.3.4 and the ``heb`` and ``eng`` fast models):

1. **Digits.** The ``heb`` model reads digits badly next to Hebrew (``12.35`` came back as
   ``12335``, ``164`` for ``14.64``, ``OOO00`` for a price). The ``eng`` model reads the same
   numbers right 96 % of the time (131 of 136 prices and weights in 14 synthetic receipts, against
   76 % for ``heb+eng``) but turns Hebrew into Latin garbage. So a receipt is read twice and
   merged by position: the words with Hebrew letters come from ``heb+eng``, the numbers from
   ``eng`` (``merge_receipt``).
2. **Word order.** The plain output puts the words of a line in visual left-to-right order for
   some lines and in logical order for others, so "נוזל לניקוי רצפות" came back reversed. The
   boxes say where each word is, so the order is rebuilt from geometry: a Hebrew line reads from
   the right edge to the left (``order_rtl``), whatever order Tesseract printed. Letters inside a
   word, and the digits of a number, are already in logical order in the TSV.

Receipts: Tesseract's own line grouping is kept (it handles a slightly skewed page and puts the
price at the far left on the same line as its name); numbers from the second pass are attached
to the line of the first-pass word they overlap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEBREW = re.compile(r"[א-ת]")
# digits with the punctuation of a price, a weight, a percentage or a multiplication sign
_NUMERIC = re.compile(r"^[(\[]?[-+]?[\d.,:%/xX×*+\-]*\d[\d.,:%/xX×*+\-]*[)\]]?$")
_MULT = re.compile(r"^[xX×*]$")
_PRICEISH = re.compile(r"\d+[.,]\d{2,3}")
_SIZE_LETTER = re.compile(
    r"^(?:XXL|XL|L|M|S)$"
)  # egg sizes and the like: real Latin on a Hebrew receipt
MIN_CONF = 10.0  # percent; below it a word is noise
CONF_MARGIN = 20.0  # the first pass keeps a number only when it is this much surer


@dataclass(frozen=True)
class Word:
    left: int
    top: int
    width: int
    height: int
    conf: float
    text: str
    line: tuple[int, int, int] = (0, 0, 0)  # block, paragraph, line as Tesseract numbered them

    @property
    def cx(self) -> float:
        return self.left + self.width / 2

    @property
    def cy(self) -> float:
        return self.top + self.height / 2

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def is_numeric(self) -> bool:
        return bool(_NUMERIC.match(self.text)) or bool(_MULT.match(self.text))

    @property
    def is_size_letter(self) -> bool:
        return bool(_SIZE_LETTER.match(self.text))

    @property
    def has_hebrew(self) -> bool:
        return bool(_HEBREW.search(self.text))


def parse_tsv(tsv: str) -> list[Word]:
    """Word rows (level 5) of Tesseract's TSV output; noise and empty words are dropped."""
    words: list[Word] = []
    for row in tsv.splitlines()[1:]:
        cols = row.split("\t", 11)
        if len(cols) < 12 or cols[0] != "5":
            continue
        text = cols[11].strip().translate(_BIDI)
        try:
            conf = float(cols[10])
            word = Word(
                int(cols[6]),
                int(cols[7]),
                int(cols[8]),
                int(cols[9]),
                conf,
                text,
                (int(cols[2]), int(cols[3]), int(cols[4])),
            )
        except ValueError:
            continue
        if text and conf >= MIN_CONF:
            words.append(word)
    return words


_BIDI = dict.fromkeys(
    [0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069]
)


def order_rtl(words: list[Word]) -> list[Word]:
    """Right edge first: the reading order of a Hebrew line, from the boxes."""
    return sorted(words, key=lambda w: -w.cx)


def _keep_text(w: Word) -> bool:
    """A word of a line: Hebrew, a number or a size letter (L, XL). Latin garbage (Tesseract's
    reading of a Hebrew word in the ``eng`` part of ``heb+eng``) is dropped."""
    return w.has_hebrew or w.is_numeric or w.is_size_letter


def list_lines(words: list[Word]) -> list[str]:
    """Lines of a list photo: Tesseract's lines, each read right to left."""
    lines: dict[tuple[int, int, int], list[Word]] = {}
    for w in words:
        if _keep_text(w):
            lines.setdefault(w.line, []).append(w)
    ordered = sorted(lines.values(), key=lambda ws: sum(w.cy for w in ws) / len(ws))
    return [" ".join(w.text for w in order_rtl(ws)) for ws in ordered]


def _iou(a: Word, b: Word) -> float:
    w = min(a.right, b.right) - max(a.left, b.left)
    h = min(a.bottom, b.bottom) - max(a.top, b.top)
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / (a.width * a.height + b.width * b.height - inter)


def merge_receipt(text_words: list[Word], number_words: list[Word]) -> list[str]:
    """Lines of a receipt: Hebrew words from the ``heb+eng`` pass, numbers from the ``eng`` pass.

    * A number of the second pass joins the line of the first-pass word it overlaps most (the
      same printed token, read by both passes). The first pass's own reading of that token is
      dropped: it is the unreliable one.
    * A number the first pass read where the second pass found nothing is kept.
    * A price or weight with no first-pass word under it starts a line of its own (the detail
      line ``2 X 5.90 11.80`` often looks like that); other stray numbers are dropped.
    """
    lines: dict[tuple[int, int, int], list[Word]] = {}
    for w in text_words:
        if w.has_hebrew or w.is_size_letter:
            lines.setdefault(w.line, []).append(w)
    numbers = [n for n in number_words if n.is_numeric]
    used: list[Word] = []  # second-pass numbers that were taken
    stray: list[Word] = []
    for n in numbers:
        under = [w for w in text_words if _iou(n, w) > 0.15]
        if any(w.has_hebrew for w in under):
            continue  # the first pass read Hebrew here: digits from the second pass are noise
        if under:
            first = [w for w in under if w.is_numeric]
            if first and max(w.conf for w in first) > n.conf + CONF_MARGIN:
                continue  # the first pass is clearly surer about this token: keep its reading
            if not first and not (_PRICEISH.search(n.text) or _MULT.match(n.text)):
                continue  # only a price or a sign may replace a first-pass non-word (``1120``
                # read from a Hebrew word is the second pass hallucinating digits)
            best = max(under, key=lambda w: _iou(n, w))
            lines.setdefault(best.line, []).append(n)
            used.append(n)
        elif _PRICEISH.search(n.text) or _MULT.match(n.text):
            stray.append(n)
    for w in text_words:  # first-pass numbers the second pass did not replace
        if w.is_numeric and not w.has_hebrew and not any(_iou(w, n) > 0.15 for n in used):
            lines.setdefault(w.line, []).append(w)
    rows = list(lines.values())
    for n in stray:  # no first-pass word under it: the row it sits on, else a line of its own
        host = _same_row(rows, n)
        if host is not None:
            host.append(n)
        else:
            rows.append([n])
    rows.sort(key=lambda ws: sum(w.cy for w in ws) / len(ws))
    return [" ".join(w.text for w in order_rtl(ws)) for ws in rows if ws]


def _same_row(rows: list[list[Word]], n: Word) -> list[Word] | None:
    """The line whose words sit at the height of ``n`` (within half a word height)."""
    best, best_d = None, n.height * 0.5
    for ws in rows:
        near = min(ws, key=lambda w: abs(w.cy - n.cy))
        d = abs(near.cy - n.cy)
        if d < best_d:
            best, best_d = ws, d
    return best
