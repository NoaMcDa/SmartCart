"""Synthetic receipts and handwritten-style lists with ground truth (issues #61, #68).

    uv run --no-sync python scripts/ocr/render.py --out DIR [--receipts 40] [--lists 20]
        [--seed 7] [--font PATH] [--embed-truth]

Each image ``receipt_007.png`` / ``list_003.png`` gets ``receipt_007.json`` / ``list_003.json``
next to it with the ground truth (see ``make_receipt`` and ``make_list`` for the fields).

What this is and is not. Everything is SYNTHETIC: the products come from the repo's own canonical
catalog, the layouts are an approximation of an Israeli till receipt, and the "handwriting" is a
printed font drawn word by word with random rotation, baseline jitter, ink colour, blur and noise.
Numbers measured on these images say that the pipeline works end to end and where it breaks on
clean-ish input; they do not estimate accuracy on real receipts or real handwriting. Real photos
need to be collected with consent before any such claim (docs/ocr.md).

Hebrew is drawn in visual order by ``visual()`` (a small reordering that keeps numbers and Latin
runs left-to-right) with Pillow's basic layout engine (never raqm, which would reorder it again).

``--embed-truth`` stores the logical text of each line in the PNG (chunk ``sc-ocr``): the
FakeProvider reads it back, which tests the whole evaluation without Tesseract. Never use it for a
real evaluation.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

D = Decimal

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/noto/NotoSansHebrew-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansHebrew[wdth,wght].ttf",
    "/usr/share/fonts/opentype/noto/NotoSansHebrew-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSerifHebrew-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # has Hebrew; the local self-test font
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
)

CITIES = ["רמת אביב", "הרצליה", "נתניה", "באר שבע", "חיפה", "ראשון לציון", "פתח תקווה", "רחובות"]
BRANDS = ["תנובה", "טרה", "שטראוס", "אסם", "עלית", "יטבתה", "דנונה", "סוגת"]
SIZES = ["1 ל'", "500 גרם", "250 גרם", "1.5 ל'", "750 מל", "400 גרם", "1 ק\"ג"]
ABBREVIATIONS = {
    "חלב": "חל'", "גבינה": "גב'", "שמנת": "שמנ'", "יוגורט": "יוג'", "ביצים": "ביצ'",
    "עגבניות": "עגב'", "מלפפונים": "מלפ'", "שוקולד": "שוק'", 'תפוחי אדמה': 'תפו"א',
}
DISTRACTORS = ["להתקשר לדני", "לא לשכוח מתנה", "ללכת לבנק", "תור לרופא ביום ג", "יום הולדת לנועה"]
CHAIN_HEADERS = {
    "7290027600007": 'שופרסל דיל בע"מ', "7290058140886": 'רמי לוי שיווק השקמה בע"מ',
    "7290696200003": "ויקטורי", "7290055700007": "יינות ביתן", "7290700100008": "חצי חינם",
    "7290873255550": "טיב טעם", "7290103152017": "אושר עד", "7290803800003": "יוחננוף",
    "7290661400001": "מחסני השוק", "7290058108879": "קינג סטור",
}


LATIN_CANDIDATES = (
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
)
_HEBREW_LETTERS = re.compile("([א-ת]+)")


def has_glyphs(path: str, chars: str, size: int = 32) -> bool:
    """True when the font draws every char (a missing glyph is the same box as U+FFFF)."""
    font = ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.BASIC)
    missing = bytes(font.getmask("￿"))
    return all(bytes(font.getmask(c)) != missing for c in chars)


def find_latin_font(hebrew_path: str) -> str:
    """Digits, Latin letters and punctuation. Noto Sans Hebrew has none of them (they were drawn
    as empty boxes, which Tesseract read as 0 and o: the first runner evaluation measured that),
    so they come from a second font on the same baseline."""
    need = "0123456789.,%-:'\"/*XxAa"
    if has_glyphs(hebrew_path, need):
        return hebrew_path
    for path in LATIN_CANDIDATES:
        if Path(path).exists() and has_glyphs(path, need):
            return path
    raise SystemExit("no font with digits found: install fonts-dejavu-core or fonts-noto-core")


class Face:
    """A Hebrew font plus a Latin/digit font drawn on one baseline, run by run."""

    def __init__(self, hebrew_path: str, size: int) -> None:
        kw = {"layout_engine": ImageFont.Layout.BASIC}
        self.he = ImageFont.truetype(hebrew_path, size, **kw)
        self.latin = ImageFont.truetype(find_latin_font(hebrew_path), size, **kw)
        self.baseline = int(size * 0.95)

    def _runs(self, text: str):
        for i, part in enumerate(_HEBREW_LETTERS.split(text)):
            if part:
                yield (self.he if i % 2 else self.latin), part

    def length(self, draw: ImageDraw.ImageDraw, text: str) -> float:
        return sum(draw.textlength(part, font=f) for f, part in self._runs(text))

    def text(self, draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, fill, **kw) -> None:
        x, y = xy
        for f, part in self._runs(text):
            draw.text((x, y + self.baseline), part, font=f, fill=fill, anchor="ls", **kw)
            x += draw.textlength(part, font=f)


def find_font(explicit: str | None = None) -> str:
    candidates = [explicit] if explicit else list(FONT_CANDIDATES)
    if not explicit:  # any Noto Sans Hebrew the package installed, whatever its file name
        candidates[4:4] = sorted(str(p) for p in Path("/usr/share/fonts").glob("**/NotoSansHebrew*"))
    for path in candidates:
        if path and Path(path).exists():
            return path
    raise SystemExit("no Hebrew font found: install fonts-noto-core or pass --font PATH")


_RUN = re.compile(r"[0-9A-Za-z][0-9A-Za-z.,%/:\-]*|[^0-9A-Za-z]+")


def visual(text: str) -> str:
    """Logical Hebrew to the left-to-right order a font renderer draws it in."""
    out = []
    for token in reversed(text.split(" ")):
        parts = _RUN.findall(token)
        out.append("".join(p if re.match(r"[0-9A-Za-z]", p) else p[::-1] for p in reversed(parts)))
    return " ".join(out)


def money(x: Decimal | float | int) -> Decimal:
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


# --- catalog ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Product:
    name: str
    weighed: bool


def load_products() -> list[Product]:
    from smartcart_catalog.seed import load_catalog

    out = []
    for c in load_catalog().canonicals:
        if "(" in c.display_name_he or len(c.display_name_he) > 26:
            continue
        out.append(Product(c.display_name_he, c.base_unit == "kg"))
    return out


# --- receipts ---------------------------------------------------------------------------------


def printed_name(rng: random.Random, name: str) -> str:
    """The canonical's name as a till prints it: sometimes abbreviated, with a brand and a size."""
    words = name.split(" ")
    for full, short in ABBREVIATIONS.items():
        if name == full or name.startswith(full + " "):
            if rng.random() < 0.3:
                words = [short, *name[len(full):].split()]
            break
    if rng.random() < 0.5 and len(words) > 1:
        words.insert(1, rng.choice(BRANDS))
    if rng.random() < 0.4:
        words.append(rng.choice(SIZES))
    return " ".join(w for w in words if w)


def make_receipt(rng: random.Random, products: list[Product]) -> tuple[list[str], dict]:
    """(printed lines in logical order, ground truth)."""
    chain_id = rng.choice(list(CHAIN_HEADERS))
    branch = rng.choice(CITIES)
    lines = [
        CHAIN_HEADERS[chain_id],
        f"סניף: {branch}",
        f"ח.פ 5{rng.randint(10000000, 99999999)}",
        f"חשבונית מס מספר {rng.randint(10000, 99999)}",
        f"תאריך {rng.randint(1, 28):02d}/10/2026 שעה {rng.randint(8, 21):02d}:{rng.randint(0, 59):02d}",
        "",
    ]
    truth_items = []
    chosen = rng.sample(products, rng.randint(4, 11))
    total = D(0)
    for p in chosen:
        raw = printed_name(rng, p.name)
        if p.weighed:
            weight = D(rng.randint(180, 2400)) / 1000
            unit_price = D(rng.randint(400, 2400)) / 100
            price = money(weight * unit_price)
            lines += [raw, f'{weight:.3f} ק"ג X {unit_price:.2f} {price:.2f}']
            qty, unit = weight, "kg"
        else:
            qty_n = rng.choice([1, 1, 1, 1, 2, 2, 3])
            unit_price = D(rng.randint(250, 3500)) / 100
            price = money(qty_n * unit_price)
            if qty_n == 1:
                lines.append(f"{raw} {price:.2f}")
            elif rng.random() < 0.5:
                lines += [raw, f"{qty_n} X {unit_price:.2f} {price:.2f}"]
            else:
                lines += [f"{raw} {price:.2f}", f"{qty_n} X {unit_price:.2f}"]
            qty, unit = D(qty_n), None
        total += price
        truth_items.append(
            {"printed": raw, "canonical": p.name, "quantity": str(qty), "unit": unit, "price": str(price)}
        )
    discounts = []
    if rng.random() < 0.35:
        d = money(D(rng.randint(100, 600)) / 100)
        lines.append(f"הנחת מועדון -{d:.2f}")
        total -= d
        discounts.append(str(-d))
    if rng.random() < 0.15:
        lines.append("פיקדון על בקבוקים 0.30")
        total += D("0.30")
    lines += [f"סה\"כ פריטים {len(chosen)}", f"סה\"כ {total:.2f}", f"לתשלום {total:.2f}",
              f"מע\"מ 18% {money(total * D(18) / D(118)):.2f}", "אשראי ויזה ****1234", "תודה ולהתראות"]
    truth = {
        "kind": "receipt", "chain_id": chain_id, "branch": branch, "total": str(money(total)),
        "items": truth_items, "discounts": discounts, "lines": [ln for ln in lines if ln],
    }
    return lines, truth


# --- lists ------------------------------------------------------------------------------------


def make_list(rng: random.Random, products: list[Product]) -> tuple[list[str], dict]:
    chosen = rng.sample(products, rng.randint(4, 10))
    lines, items = [], []
    for p in chosen:
        qty = rng.choice([1, 1, 1, 2, 3])
        text = f"{qty} {p.name}" if qty > 1 else p.name
        lines.append(text)
        items.append({"written": text, "canonical": p.name, "quantity": qty})
    distractors = rng.sample(DISTRACTORS, rng.choice([0, 0, 1, 2]))
    for d in distractors:
        lines.insert(rng.randint(0, len(lines)), d)
    return lines, {"kind": "list", "lines": lines, "items": items, "distractors": distractors}


# --- drawing ----------------------------------------------------------------------------------


def _noise_and_blur(img: Image.Image, rng: random.Random, blur: tuple[float, float]) -> Image.Image:
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(*blur)))
    noise = Image.effect_noise(img.size, rng.uniform(4, 14)).convert("RGB")
    return Image.blend(img, noise, rng.uniform(0.03, 0.10))


def draw_receipt(lines: list[str], font_path: str, rng: random.Random) -> Image.Image:
    size = rng.randint(22, 28)
    font = Face(font_path, size)
    pitch, margin, width = int(size * 1.45), 28, rng.randint(620, 720)
    img = Image.new("RGB", (width, pitch * (len(lines) + 2) + margin), (250, 248, 240))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        y = margin + i * pitch
        if not line:
            continue
        # the price (a trailing 2-decimal number) is set at the left edge, the name at the right
        m = re.match(r"^(.*?)(?:\s+(-?\d+\.\d{2}))$", line)
        if m and re.search(r"[א-ת]", m.group(1)) and not line.startswith(("סה", "לתשלום", "מע")):
            name, price = m.groups()
            font.text(draw, (margin, y), price, (20, 20, 20))
            vis = visual(name)
            w = font.length(draw, vis)
            font.text(draw, (width - margin - w, y), vis, (20, 20, 20))
        elif re.match(r"^(סה|לתשלום|מע)", line):
            m2 = re.match(r"^(.*?)\s+(\S+)$", line)
            name, price = m2.groups() if m2 else (line, "")
            font.text(draw, (margin, y), price, (20, 20, 20))
            vis = visual(name)
            w = font.length(draw, vis)
            font.text(draw, (width - margin - w, y), vis, (20, 20, 20))
        else:
            vis = visual(line)
            w = font.length(draw, vis)
            font.text(draw, (width - margin - w, y), vis, (20, 20, 20))
    img = img.rotate(rng.uniform(-1.5, 1.5), expand=True, fillcolor=(235, 235, 230),
                     resample=Image.Resampling.BICUBIC)
    return _noise_and_blur(img, rng, (0.0, 0.7))


def draw_list(lines: list[str], font_path: str, rng: random.Random) -> Image.Image:
    base = rng.randint(34, 44)
    width, pitch, margin = 640, int(base * 1.9), 40
    img = Image.new("RGB", (width, pitch * (len(lines) + 1) + margin), (252, 250, 243))
    draw = ImageDraw.Draw(img)
    ink = (rng.randint(10, 40), rng.randint(20, 50), rng.randint(70, 130))
    for i in range(len(lines) + 1):  # ruled paper
        y = margin + (i + 1) * pitch - 6
        draw.line([(20, y), (width - 20, y)], fill=(190, 205, 225), width=1)
    for i, line in enumerate(lines):
        x = width - margin
        for word in line.split(" "):  # the first word at the right edge, moving left
            font = Face(font_path, base + rng.randint(-4, 5))
            vis = visual(word)
            w = int(font.length(draw, vis)) + 8
            tile = Image.new("RGBA", (w + 24, base * 2), (0, 0, 0, 0))
            font.text(ImageDraw.Draw(tile), (12, 0), vis, ink + (255,),
                      stroke_width=rng.choice([0, 0, 1]), stroke_fill=ink + (255,))
            tile = tile.rotate(rng.uniform(-5, 5), expand=True, resample=Image.Resampling.BICUBIC)
            x -= tile.width - 16
            y = margin + i * pitch + rng.randint(-5, 5)
            img.paste(tile, (x, y), tile)
            x -= rng.randint(6, 16)
    img = img.rotate(rng.uniform(-3, 3), expand=True, fillcolor=(235, 235, 230),
                     resample=Image.Resampling.BICUBIC)
    return _noise_and_blur(img, rng, (0.4, 1.0))


# --- main -------------------------------------------------------------------------------------


def generate(out: Path, receipts: int, lists: int, seed: int, font: str | None, embed_truth: bool) -> int:
    from smartcart_api.ocr.providers import png_with_text

    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    font_path = find_font(font)
    products = load_products()
    plan = [("receipt", i) for i in range(1, receipts + 1)] + [("list", i) for i in range(1, lists + 1)]
    for kind, i in plan:
        lines, truth = (make_receipt if kind == "receipt" else make_list)(rng, products)
        img = (draw_receipt if kind == "receipt" else draw_list)(lines, font_path, rng)
        stem = f"{kind}_{i:03d}"
        truth["file"] = f"{stem}.png"
        truth["synthetic"] = True
        if embed_truth:
            (out / f"{stem}.png").write_bytes(png_with_text([ln for ln in lines if ln], img))
        else:
            img.save(out / f"{stem}.png")
        (out / f"{stem}.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(plan)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--receipts", type=int, default=40)
    ap.add_argument("--lists", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--font", help="a Hebrew TTF (default: Noto Sans Hebrew, else DejaVu Sans)")
    ap.add_argument("--embed-truth", action="store_true", help="self-test only: put the text in the PNG")
    args = ap.parse_args(argv)
    n = generate(args.out, args.receipts, args.lists, args.seed, args.font, args.embed_truth)
    print(f"wrote {n} synthetic images with ground truth to {args.out} (seed {args.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
