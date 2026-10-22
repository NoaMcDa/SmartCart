"""The review packet for canonical proposals, and the import of the reviewer's answers (issue #52).

``smartcart-catalog propose-canonicals`` (this module's ``propose_canonicals``) runs
``proposals.propose`` over the unmapped items of the database (or the committed real fixtures with
``--source fixtures``) and writes, like ``review_packet.py`` does for the existing list:

* ``canonical-proposals.html``: one self-contained page (right to left, system fonts, no script,
  printable): per proposal the proposed definition with the uncertain fields marked, the coverage
  gain (chains, stores, items, barcodes), up to two real items per chain (name, barcode, size,
  price) and an accept / edit / reject box;
* ``canonical-proposals.csv``: the same rows, with empty ``decision`` and ``comment`` columns and
  ``edit_*`` columns for the reviewer's corrections (UTF-8 with a BOM for Excel);
* ``canonical-proposals.json``: the proposals and the run's numbers (what was excluded and why), for
  engineers.

``smartcart-catalog proposals-import FILLED.csv --reviewer NAME`` validates the filled CSV and
writes ``data/proposals/canonicals-additions-<date>.yaml``: the accepted and edited rows as
additions for ``data/canonicals.yaml`` (and, for a product type the rules file does not have, a
rule stub), plus the rejected ones for the record. **It never edits ``data/canonicals.yaml``** (nor
the rules or the taxonomy): a reviewer's sign-off is issue #15's job, and the additions are applied
by hand. It then checks, in a scratch copy of ``data/``, whether ``seed`` would accept the result
and prints every problem (an Arabic name is missing, the MVP range of 150 to 300 would be
exceeded, the taxonomy node does not exist ...).

Nothing here is a measured precision: a proposal is a machine suggestion from item names.
"""

from __future__ import annotations

import csv
import io
import json
import re
import shutil
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from smartcart_catalog import proposals as engine
from smartcart_catalog.proposals import Proposal, ProposalRun, proposal_hash
from smartcart_catalog.review_packet import (
    _CSS,
    BASE_UNIT_HE,
    KEY_HE,
    _e,
    _sniff_delimiter,
    attrs_text,
    parse_attrs_cell,
    read_csv_text,
    sha_of_file,
)
from smartcart_catalog.seed import SeedError, load_catalog

HTML_NAME = "canonical-proposals.html"
CSV_NAME = "canonical-proposals.csv"
JSON_NAME = "canonical-proposals.json"

KIND_HE = {
    "variant": "וריאנט בסוג מוצר קיים",
    "new_type": "סוג מוצר חדש",
}

CSV_FIELDS = (
    "rank", "proposal_id", "kind", "priority_estimate", "display_name_he", "slug", "taxonomy_id",
    "taxonomy_candidates", "product_type", "suggested_product_type", "base_unit",
    "critical_attrs", "soft_attrs", "uncertain",
    "chains", "stores", "items", "skus", "shared_barcodes", "price_events", "search_misses",
    "share_of_unmapped_items", "chain_names", "examples", "row_hash",
    "decision", "comment", "edit_display_name_he", "edit_slug", "edit_taxonomy_id",
    "edit_product_type", "edit_base_unit", "edit_critical_attrs", "edit_soft_attrs", "names_ar",
)  # fmt: skip
EDIT_FIELDS = (
    "display_name_he",
    "slug",
    "taxonomy_id",
    "product_type",
    "base_unit",
    "critical_attrs",
    "soft_attrs",
)

DECISIONS = ("accept", "edit", "reject")
_DECISION_WORDS: dict[str, str] = {
    "accept": "accept", "ok": "accept", "yes": "accept", "y": "accept", "approve": "accept",
    "approved": "accept", "✓": "accept", "v": "accept",
    "אישור": "accept", "אשר": "accept", "מאושר": "accept", "תקין": "accept", "כן": "accept",
    "edit": "edit", "change": "edit", "fix": "edit", "עריכה": "edit", "שינוי": "edit",
    "לערוך": "edit", "תיקון": "edit",
    "reject": "reject", "no": "reject", "n": "reject", "remove": "reject", "drop": "reject",
    "דחייה": "reject", "דחיה": "reject", "דחה": "reject", "הסרה": "reject", "לא": "reject",
}  # fmt: skip


def decision_word(word: str) -> str | None:
    key = re.sub(r"[☐☑☒\[\]()]", "", word.strip().lower().rstrip(".")).strip()
    return _DECISION_WORDS.get(key)


# --- examples text ------------------------------------------------------------------------------------


def example_text(e: engine.ExampleItem) -> str:
    parts = [p for p in (e.barcode or "", e.size, f"₪{e.price}" if e.price else "") if p]
    shared = "; ברקוד בכמה רשתות" if e.shared else ""
    return f"{e.chain}: {e.name} [{'; '.join(parts)}{shared}]"


# --- CSV ----------------------------------------------------------------------------------------------


def render_csv(run: ProposalRun) -> str:
    """The packet as CSV text (write it as ``utf-8-sig`` so Excel reads the Hebrew)."""
    unmapped = max(run.stats.get("items_unmapped", 0), 1)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\r\n")
    w.writeheader()
    for p in run.proposals:
        w.writerow({
            "rank": p.rank,
            "proposal_id": p.proposal_id,
            "kind": p.kind,
            "priority_estimate": f"{p.priority:.3f}",
            "display_name_he": p.display_name_he,
            "slug": p.slug,
            "taxonomy_id": p.taxonomy_id or "",
            "taxonomy_candidates": "; ".join(f"{t} ({s:g})" for t, s in p.taxonomy_candidates),
            "product_type": p.product_type or "",
            "suggested_product_type": p.suggested_product_type if not p.product_type else "",
            "base_unit": p.base_unit or "",
            "critical_attrs": attrs_text(p.critical_attrs),
            "soft_attrs": attrs_text(p.soft_attrs),
            "uncertain": " | ".join(p.uncertain),
            "chains": p.chains,
            "stores": p.stores,
            "items": p.items,
            "skus": p.skus,
            "shared_barcodes": p.shared_barcodes,
            "price_events": p.price_events,
            "search_misses": p.miss_hits,
            "share_of_unmapped_items": f"{p.items / unmapped:.4f}",
            "chain_names": ", ".join(p.chain_names),
            "examples": " | ".join(example_text(e) for e in p.examples),
            "row_hash": p.row_hash,
            **{k: "" for k in ("decision", "comment", "names_ar")},
            **{f"edit_{k}": "" for k in EDIT_FIELDS},
        })  # fmt: skip
    return buf.getvalue()


# --- HTML ---------------------------------------------------------------------------------------------

_EXTRA_CSS = """
td.cov { white-space: nowrap; font-size: 13px; }
td.cov b { font-weight: 700; }
.unc { color: #8a0019; font-size: 12px; margin: 2px 0; display: block; }
.kind-variant { border-color: #1a4a8a; color: #12366a; }
.kind-new_type { border-color: #8a5a00; color: #6a4500; border-style: dashed; }
ul.ex .meta2 { color: #555; font-size: 12px; }
td.decision { width: 170px; }
"""


def _ltr(text: str) -> str:
    return f'<span dir="ltr">{_e(text)}</span>'


def _attr_lines(attrs: Mapping[str, Any], *, suggested: bool = False) -> str:
    if not attrs:
        return '<span class="none">אין</span>'
    lines = []
    for k, v in attrs.items():
        if k == "unit" and "pack_size" in attrs:
            continue
        value = f"{v} {attrs['unit']}" if k == "pack_size" and "unit" in attrs else v
        lines.append(
            f'<span class="kv"><b>{_e(KEY_HE.get(k, k))}:</b> <bdi>{_e(value)}</bdi>'
            f" <code>{_e(k)}</code></span>"
        )
    return "".join(lines)


def _examples_html(p: Proposal) -> str:
    items = []
    for e in p.examples:
        tag = '<span class="tag src-real">ברקוד בכמה רשתות</span>' if e.shared else ""
        bits = [b for b in (e.barcode or "", e.size) if b]
        price = f"₪ {e.price}" if e.price else ""
        items.append(
            f'<li><span dir="auto">{_e(e.name)}</span><br>'
            f'<span class="tag">{_e(e.chain)}</span>{tag}'
            f'<span class="meta2"> {_ltr(" · ".join(bits))} {_ltr(price) if price else ""}</span></li>'
        )
    return f'<ul class="ex">{"".join(items)}</ul>'


def _row_html(p: Proposal, unmapped: int) -> str:
    kind = f'<span class="tag kind-{_e(p.kind)}">{_e(KIND_HE[p.kind])}</span>'
    unc = "".join(f'<span class="unc">⚠ {_e(u)}</span>' for u in p.uncertain)
    tax = (
        _e(p.taxonomy_id)
        if p.taxonomy_id
        else '<span class="unc">לא נבחר</span>'
        + (
            "<br>" + ", ".join(f"<code>{_e(t)}</code> ({s:g})" for t, s in p.taxonomy_candidates)
            if p.taxonomy_candidates
            else ""
        )
    )
    ptype = (
        f"<code>{_e(p.product_type)}</code>"
        if p.product_type
        else f'<span class="unc">חדש; הצעת שם: <code>{_e(p.suggested_product_type)}</code></span>'
    )
    return (
        f'<tr id="p-{_e(p.proposal_id)}">'
        f'<td class="num"><b>{p.rank}</b><br><span class="tag est">הערכה</span><br>'
        f'<span class="muted">{p.priority:.2f}</span></td>'
        f'<td><span class="name" dir="auto">{_e(p.display_name_he)}</span><br>'
        f'<span class="slug">{_e(p.slug)}</span> {kind}<br>'
        f'<span class="muted">צומת: {tax}</span><br>'
        f'<span class="muted">סוג מוצר: {ptype}</span><br>'
        f'<span class="muted">{_e(BASE_UNIT_HE.get(p.base_unit or "", p.base_unit or "?"))}</span> '
        f"<code>{_e(p.base_unit or '?')}</code></td>"
        f"<td><b>קריטי:</b>{_attr_lines(p.critical_attrs)}<b>רך:</b>{_attr_lines(p.soft_attrs)}"
        f"{unc}</td>"
        f'<td class="cov"><b>{p.chains}</b> רשתות<br><b>{p.stores}</b> חנויות<br>'
        f"<b>{p.items}</b> פריטים ({p.items / unmapped:.1%} מהלא-ממופים)<br>"
        f"<b>{p.skus}</b> מוצרים, <b>{p.shared_barcodes}</b> בברקוד משותף<br>"
        f"{p.price_events} אירועי מחיר, {p.miss_hits} חיפושים שלא נמצאו<br>"
        f'<span class="muted">{_e(", ".join(p.chain_names))}</span></td>'
        f"<td>{_examples_html(p)}</td>"
        '<td class="decision"><span class="opt">☐ אישור (accept)</span>'
        '<span class="opt">☐ עריכה (edit)</span><span class="opt">☐ דחייה (reject)</span>'
        '<span class="line"></span><span class="line"></span></td>'
        "</tr>"
    )


@dataclass(frozen=True)
class PacketMeta:
    generated_on: str
    canonicals_sha: str


def render_html(run: ProposalRun, meta: PacketMeta) -> str:
    st = run.stats
    unmapped = max(st.get("items_unmapped", 0), 1)
    rows = "".join(_row_html(p, unmapped) for p in run.proposals)
    gaps = st.get("matching_gaps", {})
    kinds = st.get("kinds", {})
    head = (
        "<thead><tr><th>דירוג<br>(הערכה)</th><th>מוצר מוצע</th><th>הגדרה מוצעת</th>"
        "<th>הרחבת הכיסוי<br>(חסם עליון)</th><th>פריטים אמיתיים (עד שניים לרשת)</th>"
        "<th>החלטה</th></tr></thead>"
    )
    return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>הצעות למוצרים קנוניים חדשים · SmartCart</title>
<style>{_CSS}{_EXTRA_CSS}</style>
</head>
<body>
<main>
<header>
<h1>הצעות למוצרים קנוניים חדשים</h1>
<p class="meta">נוצר ב-{_e(meta.generated_on)} מפריטים אמיתיים שלא שויכו לאף מוצר קנוני
({_e(st.get("source", ""))}, מצב הנתונים: {_e(st.get("as_of") or "קבצים מצורפים")}) ·
<code>data/canonicals.yaml</code> טביעת אצבע <code>{_e(meta.canonicals_sha)}</code> · מזהה #52</p>
</header>

<div class="box warn">
<h3>מה זה, ומה זה לא</h3>
<ul>
<li>זו <b>הצעה של מכונה</b> מתוך שמות פריטים של רשתות, לא רשימה מאומתת. שום מספר כאן אינו דיוק מדוד.
כל הצעה דורשת החלטת אדם; שום דבר לא נכנס אוטומטית ל-<code>data/canonicals.yaml</code> (#15).</li>
<li><b>דיוק לפני כיסוי</b>: מוצעות רק קבוצות שנמכרות בשתי רשתות לפחות, ושערך שאף פריט לא מציין נשאר
ריק ומסומן ⚠, לא מנוחש.</li>
<li>עמודת <b>הרחבת הכיסוי</b> היא חסם עליון: כמה פריטים וחנויות היו מקבלים מוצר קנוני אילו אושר,
אבל השיוך עצמו עדיין נקבע על ידי כללי ההתאמה (<code>docs/matching.md</code>) ובדיקת ערכת הזהב.</li>
<li>הדירוג הוא <b>הערכה</b>: מרכיבים נמדדים (רשתות, חנויות, ברקודים משותפים, אירועי מחיר, חיפושים
שלא נמצאו) ומשקל סל לפי מחלקה, במשקלים שנקבעו בשיקול דעת (<code>docs/catalog.md</code> סעיף 10).</li>
</ul>
</div>

<div class="box">
<h3>המספרים של הריצה</h3>
<ul>
<li>{st.get("items_total", 0):,} פריטים נטענו, {st.get("items_mapped", 0):,} שויכו,
{st.get("items_unmapped", 0):,} לא שויכו ({st.get("products", 0):,} מוצרים לפי ברקוד,
{st.get("groups", 0):,} קבוצות).</li>
<li>{st.get("proposals", 0)} הצעות: {kinds.get("variant", 0)} וריאנטים בסוג מוצר קיים,
{kinds.get("new_type", 0)} עם סוג מוצר חדש. מכסות {st.get("proposal_items", 0):,} פריטים.</li>
<li>לא הוצעו: {gaps.get("groups", 0)} קבוצות ({gaps.get("items", 0):,} פריטים) שכבר יש להן מוצר
קנוני עם אותם ערכים קריטיים (שאלת התאמה, לא פער בקטלוג);
{st.get("missing_critical", {}).get("groups", 0)} קבוצות שערך קריטי שלהן לא נאמר בשמות,
{st.get("unspecific_critical", {}).get("groups", 0)} שערך קריטי שלהן כללי מדי (&quot;אחר&quot;);
{st.get("below_min_chains", {}).get("groups", 0)} קבוצות של רשת אחת בלבד.</li>
</ul>
</div>

<div class="box">
<h3>מה מבקשים ממך</h3>
<p>לכל שורה לסמן אחת מהשלוש: <b>אישור</b> (ההגדרה נכונה כפי שהיא), <b>עריכה</b> (לתקן בעמודות
<code>edit_*</code> של ה-CSV) או <b>דחייה</b>. לכל שורה שאושרה צריך גם שם בערבית (<code>names_ar</code>,
1 עד 3 שמות) כי לא ניתן לגזור אותו משמות הרשתות. סוג מוצר חדש דורש מכם לבחור צומת בטקסונומיה ולהחליט
אילו מאפיינים קריטיים.</p>
</div>

<table>
{head}
<tbody>
{rows}
</tbody>
</table>

<p class="muted" style="margin-top:14px">שם הסוקרת/ת: ______________________ &nbsp; תאריך: ______________ &nbsp; חתימה: ______________</p>
</main>
</body>
</html>
"""


# --- JSON ---------------------------------------------------------------------------------------------


def proposal_as_dict(p: Proposal) -> dict[str, Any]:
    d = {k: getattr(p, k) for k in p.__dataclass_fields__ if k != "examples"}
    d["examples"] = [vars(e) for e in p.examples]
    d["taxonomy_candidates"] = [list(t) for t in p.taxonomy_candidates]
    return d


def render_json(run: ProposalRun, meta: PacketMeta) -> str:
    doc = {
        "generated_on": meta.generated_on,
        "canonicals_sha": meta.canonicals_sha,
        "stats": run.stats,
        "proposals": [proposal_as_dict(p) for p in run.proposals],
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, default=str) + "\n"


def write_packet(
    run: ProposalRun, data_dir: Path, out_dir: Path, *, generated_on: date | None = None
) -> dict[str, Path]:
    """Write the HTML, the CSV and the JSON into ``out_dir``."""
    meta = PacketMeta(
        generated_on=(generated_on or date.today()).isoformat(),
        canonicals_sha=sha_of_file(data_dir / "canonicals.yaml"),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"html": out_dir / HTML_NAME, "csv": out_dir / CSV_NAME, "json": out_dir / JSON_NAME}
    paths["html"].write_text(render_html(run, meta), encoding="utf-8")
    paths["csv"].write_text(render_csv(run), encoding="utf-8-sig", newline="")
    paths["json"].write_text(render_json(run, meta), encoding="utf-8")
    guard = out_dir / ".gitignore"
    if not guard.exists():
        guard.write_text("*\n", encoding="utf-8")
    return paths


# --- import -----------------------------------------------------------------------------------------------


class ProposalImportError(ValueError):
    """The filled CSV cannot be turned into additions. The message lists every problem."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


@dataclass
class Row:
    line: int
    proposal_id: str
    decision: str
    comment: str
    fields: dict[str, Any]
    """The definition after the reviewer's edits (accept keeps the proposal's)."""
    names_ar: list[str]
    original: dict[str, Any]
    barcodes: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    rows: list[Row]
    pending: list[str]
    warnings: list[str]
    encoding: str

    @property
    def counts(self) -> dict[str, int]:
        c = Counter(r.decision for r in self.rows)
        return {**{d: c[d] for d in DECISIONS}, "pending": len(self.pending)}


_BASE_UNITS = ("100g", "100ml", "unit", "kg")


def _split_names(cell: str) -> list[str]:
    return [n.strip() for n in re.split(r"[|;\n]", cell) if n.strip()]


def _original_fields(row: Mapping[str, str], problems: list[str], where: str) -> dict[str, Any]:
    """The proposal as the packet printed it, to recompute ``row_hash``."""
    out: dict[str, Any] = {
        "slug": row.get("slug", ""),
        "display_name_he": row.get("display_name_he", ""),
        "taxonomy_id": row.get("taxonomy_id") or None,
        "product_type": row.get("product_type") or None,
        "base_unit": row.get("base_unit") or None,
    }
    for key in ("critical_attrs", "soft_attrs"):
        try:
            out[key] = parse_attrs_cell(row.get(key, "") or "{}")
        except ValueError as exc:
            problems.append(f"{where}: {key} cannot be read ({exc})")
            out[key] = {}
    return out


def parse_filled_csv(path: Path, *, allow_stale: bool = False) -> ImportResult:
    """Validate a filled proposals CSV. Problems are raised together as ``ProposalImportError``:
    missing columns, an unreadable decision, a duplicated proposal, a changed proposal column
    (edit in the ``edit_*`` columns), an ``edit`` row without a correction or a comment, and a
    bad ``edit_*`` cell. A row with no decision is pending (a reviewer may stop early)."""
    text, encoding = read_csv_text(path)
    delimiter = _sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)
    fields = [f.strip() for f in (reader.fieldnames or [])]
    reader.fieldnames = fields
    missing = [f for f in ("proposal_id", "slug", "decision", "row_hash") if f not in fields]
    if missing:
        raise ProposalImportError([f"missing column(s): {', '.join(missing)} (found: {fields})"])
    problems: list[str] = []
    warnings: list[str] = []
    if encoding != "utf-8":
        warnings.append("the file was not UTF-8; read as Windows-1255 (Hebrew Excel 'CSV')")
    if delimiter != ",":
        warnings.append(f"the delimiter is {delimiter!r}, not a comma (read as is)")

    rows: list[Row] = []
    pending: list[str] = []
    seen: dict[str, int] = {}
    stale: list[str] = []
    for line, raw in enumerate(reader, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw.items()}
        pid = row.get("proposal_id", "")
        if not pid and not row.get("decision"):
            continue
        where = f"line {line} ({pid or 'no id'})"
        if not pid:
            problems.append(f"{where}: a decision without a proposal_id")
            continue
        if pid in seen:
            problems.append(f"{where}: appears twice (first on line {seen[pid]})")
            continue
        seen[pid] = line
        word = row.get("decision", "")
        decision = decision_word(word) if word else None
        if word and decision is None:
            problems.append(f"{where}: unknown decision {word!r}; use accept, edit or reject")
            continue
        edits_given = any(row.get(f"edit_{k}") for k in EDIT_FIELDS)
        if decision is None:
            if row.get("comment") or edits_given or row.get("names_ar"):
                problems.append(f"{where}: a comment, an edit or a name but no decision")
            else:
                pending.append(pid)
            continue
        original = _original_fields(row, problems, where)
        if row.get("row_hash") and row["row_hash"] != proposal_hash(original):
            stale.append(pid)
        if decision == "edit" and not (edits_given or row.get("names_ar") or row.get("comment")):
            problems.append(f"{where}: 'edit' needs an edit_* value, names_ar or a comment")
        if decision in ("accept", "reject") and edits_given:
            problems.append(f"{where}: edit_* values only go with 'edit'")
        if decision == "reject" and not row.get("comment"):
            warnings.append(f"{where}: a rejection without a comment (a reason helps the next run)")
        merged = dict(original)
        if decision == "edit":
            for key in EDIT_FIELDS:
                cell = row.get(f"edit_{key}", "")
                if not cell:
                    continue
                if key in ("critical_attrs", "soft_attrs"):
                    try:
                        merged[key] = parse_attrs_cell(cell)
                    except ValueError as exc:
                        problems.append(f"{where}: edit_{key}: {exc}")
                else:
                    merged[key] = cell
        rows.append(Row(line, pid, decision, row.get("comment", ""), merged,
                        _split_names(row.get("names_ar", "")), original))  # fmt: skip
    if stale and not allow_stale:
        problems.append(
            f"{len(stale)} row(s) have a proposal column that differs from the packet's"
            f" row_hash (first: {', '.join(stale[:5])}). Correct a proposal in its edit_* column"
            " (never in the proposal's own column), or pass --allow-stale"
        )
    if problems:
        raise ProposalImportError(problems)
    return ImportResult(rows, pending, warnings, encoding)


# -- building the additions and checking them against seed -------------------------------------------------


def _entry(row: Row, rank: int) -> dict[str, Any]:
    f = row.fields
    entry: dict[str, Any] = {
        "slug": f["slug"],
        "display_name_he": f["display_name_he"],
        "names_ar": row.names_ar,
        "taxonomy_id": f["taxonomy_id"],
        "product_type": f["product_type"],
        "base_unit": f["base_unit"],
        "critical_attrs": f["critical_attrs"],
        "soft_attrs": f["soft_attrs"],
        "rank": rank,
        "is_mvp": True,
    }
    return entry


def _rule_stub(row: Row) -> dict[str, Any]:
    """A rule for a product type the rules file does not have: its critical keys are the
    reviewer's critical attributes, its soft keys the usual pack size and brand, and its keyword
    the product's own name. A starting point for the reviewer, never applied by this command."""
    f = row.fields
    return {
        "product_type": f["product_type"],
        "critical_keys": list(f["critical_attrs"]),
        "soft_keys": ["pack_size", "brand"],
        "keywords": [f["display_name_he"]],
    }


def build_additions(
    result: ImportResult,
    data_dir: Path,
    *,
    reviewer: str,
    reviewed_on: str,
    csv_name: str,
) -> tuple[dict[str, Any], list[str]]:
    """``(document, problems)``: the additions for ``data/canonicals.yaml`` as a YAML-able mapping,
    and what stops them from being valid (read from the files, before the seed check)."""
    catalog = load_catalog(data_dir)
    rules = set(catalog.rules)
    slugs = {c.slug for c in catalog.canonicals}
    problems: list[str] = []
    accepted = [r for r in result.rows if r.decision in ("accept", "edit")]
    start = len(catalog.canonicals) + 1
    canonicals: list[dict[str, Any]] = []
    new_rules: dict[str, dict[str, Any]] = {}
    for n, r in enumerate(accepted):
        f = r.fields
        where = f"line {r.line} ({r.proposal_id}, {f.get('slug') or 'no slug'})"
        for key in ("display_name_he", "slug", "taxonomy_id", "product_type", "base_unit"):
            if not f.get(key):
                problems.append(f"{where}: {key} is empty; fill edit_{key}")
        if f.get("base_unit") and f["base_unit"] not in _BASE_UNITS:
            problems.append(f"{where}: base_unit {f['base_unit']!r} is not one of {_BASE_UNITS}")
        if f.get("slug") in slugs:
            problems.append(f"{where}: slug {f['slug']} already exists in data/canonicals.yaml")
        if not r.names_ar:
            problems.append(f"{where}: names_ar is empty (1 to 3 Arabic names are required)")
        canonicals.append(_entry(r, start + n))
        pt = f.get("product_type")
        if pt and pt not in rules and pt not in new_rules:
            new_rules[pt] = _rule_stub(r)
        elif pt in new_rules:
            problems.append(
                f"{where}: new product type {pt} is also used by another row; two canonicals of"
                " a new type need distinct critical attributes, decide that with the rule"
            )
    counts = result.counts
    doc: dict[str, Any] = {
        "version": 1,
        "status": "proposal, not merged (issue #52; a reviewer's sign-off is issue #15)",
        "reviewer": reviewer,
        "reviewed_on": reviewed_on,
        "source_packet": csv_name,
        "base_canonicals_sha": sha_of_file(data_dir / "canonicals.yaml"),
        "counts": counts,
        "product_type_rules": list(new_rules.values()),
        "canonicals": canonicals,
        "rejected": [
            {"proposal_id": r.proposal_id, "name": r.original.get("display_name_he", ""),
             "comment": r.comment}
            for r in result.rows if r.decision == "reject"
        ],
    }  # fmt: skip
    if not doc["product_type_rules"]:
        del doc["product_type_rules"]
    return doc, problems


def check_additions(doc: Mapping[str, Any], data_dir: Path) -> list[str]:
    """Would ``seed`` accept ``data/`` with these additions? The check runs on a scratch copy of the
    three seed files; the real ones are never touched. Returns every problem (empty = valid)."""
    with tempfile.TemporaryDirectory(prefix="proposals-check-") as tmp:
        scratch = Path(tmp)
        for name in ("taxonomy.yaml", "product_type_rules.yaml", "canonicals.yaml"):
            shutil.copy(data_dir / name, scratch / name)
        rules = yaml.safe_load((scratch / "product_type_rules.yaml").read_text(encoding="utf-8"))
        rules["rules"] = [*rules["rules"], *doc.get("product_type_rules", [])]
        (scratch / "product_type_rules.yaml").write_text(
            yaml.safe_dump(rules, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8"
        )
        canon = yaml.safe_load((scratch / "canonicals.yaml").read_text(encoding="utf-8"))
        canon["canonicals"] = [*canon["canonicals"], *doc.get("canonicals", [])]
        (scratch / "canonicals.yaml").write_text(
            yaml.safe_dump(canon, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8"
        )
        try:
            load_catalog(scratch)
        except SeedError as exc:
            return [ln.strip() for ln in str(exc).splitlines() if ln.strip()]
        except Exception as exc:  # noqa: BLE001 - taxonomy errors and the like
            return [str(exc)]
    return []


_HEADER = """\
# Proposed additions to data/canonicals.yaml (issue #52). NOT MERGED.
#
# Written by `smartcart-catalog proposals-import` from a reviewer's answers; nothing here has been
# applied to data/canonicals.yaml, data/product_type_rules.yaml or data/taxonomy.yaml. A person
# applies it (append `canonicals` to canonicals.yaml with ranks 1..N kept, append
# `product_type_rules` to product_type_rules.yaml, and add a taxonomy node when one is missing),
# then runs `smartcart-catalog seed --check`, `seed`, `extract`, `embed`, `judge` and
# `evaluate --fail-below 0.98`, and commits the sign-off (issue #15).
# Arabic names (`names_ar`) come from the reviewer: they cannot be derived from chain data.
"""


def write_additions(doc: Mapping[str, Any], out_dir: Path, *, force: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"canonicals-additions-{doc['reviewed_on']}.yaml"
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; pass --force to overwrite it")
    body = yaml.safe_dump(dict(doc), allow_unicode=True, sort_keys=False, width=100)
    path.write_text(_HEADER + body, encoding="utf-8")
    return path


# --- commands ---------------------------------------------------------------------------------------------


def propose_canonicals(
    out: Annotated[Path, typer.Option(help="Where to write the packet.")] = Path("dist/proposals"),
    top: Annotated[int, typer.Option(help="How many proposals to write.")] = engine.TOP,
    source: Annotated[
        str,
        typer.Option(
            help="db (the items of $DATABASE_URL) or fixtures (the committed real files)."
        ),
    ] = "db",
    min_chains: Annotated[
        int, typer.Option(help="A group must be sold by at least this many chains.")
    ] = engine.MIN_CHAINS,
    min_cohesion: Annotated[
        float, typer.Option(help="Drop groups whose names are less alike than this (0 to 1).")
    ] = engine.MIN_COHESION,
    near_duplicate: Annotated[
        float, typer.Option(help="Hash-embedding cosine at which two untyped names are merged.")
    ] = engine.NEAR_DUPLICATE,
    per_chain: Annotated[
        int, typer.Option(help="Example items shown per chain.")
    ] = engine.EXAMPLES_PER_CHAIN,
    generated_on: Annotated[
        str | None, typer.Option("--date", help="YYYY-MM-DD for the page.")
    ] = None,
) -> None:
    """Propose new canonical products from the unmapped items, and write the review packet.

    Read-only on the database. A proposal is a suggestion for a reviewer; nothing edits
    data/canonicals.yaml (docs/catalog.md section 10)."""
    from smartcart_catalog.settings import load_settings

    day: date | None = None
    if generated_on:
        try:
            day = date.fromisoformat(generated_on)
        except ValueError as exc:
            raise typer.BadParameter("--date must be YYYY-MM-DD") from exc
    if source not in ("db", "fixtures"):
        raise typer.BadParameter("--source must be db or fixtures")
    settings = load_settings()
    catalog = load_catalog(settings.catalog_data_dir)
    if source == "fixtures":
        pool = engine.items_from_fixtures(catalog)
    else:
        from smartcart_catalog.cli import open_connection

        with open_connection(settings) as conn:
            pool = engine.items_from_db(conn)
            conn.rollback()
    run = engine.propose(
        pool, catalog, top=top, min_chains=min_chains, min_cohesion=min_cohesion,
        near_duplicate=near_duplicate, per_chain=per_chain,
        progress=lambda m: typer.echo(m, err=True),
    )  # fmt: skip
    paths = write_packet(run, settings.catalog_data_dir, out, generated_on=day)
    s = run.stats
    typer.echo(
        f"{s['items_total']} items, {s['items_mapped']} mapped, {s['items_unmapped']} unmapped;"
        f" {s['products']} products by barcode, {s['groups']} groups"
    )
    typer.echo(
        f"{s['proposals']} proposals ({s['kinds']}) covering {s['proposal_items']} unmapped items;"
        f" not proposed: {s['matching_gaps']['groups']} groups already have a canonical"
        f" ({s['matching_gaps']['items']} items), {s['missing_critical']['groups']} lack a"
        f" critical value, {s['below_min_chains']['groups']} sold by one chain"
    )
    for path in paths.values():
        typer.echo(f"  {path}")
    for p in run.proposals[:10]:
        typer.echo(f"  {p.rank:>3}. {p.display_name_he}  [{p.chains} chains, {p.stores} stores,"
                   f" {p.items} items, {p.kind}]")  # fmt: skip


def proposals_import(
    csv_file: Annotated[
        Path, typer.Argument(help="The filled proposals CSV.", exists=True, dir_okay=False)
    ],
    reviewer: Annotated[str, typer.Option(help="Reviewer's name, recorded in the file.")],
    reviewed_on: Annotated[
        str | None, typer.Option("--date", help="YYYY-MM-DD (default: today).")
    ] = None,
    out_dir: Annotated[Path | None, typer.Option(help="Default: <data dir>/proposals.")] = None,
    allow_stale: Annotated[
        bool, typer.Option(help="Accept rows whose proposal columns were changed.")
    ] = False,
    force: Annotated[bool, typer.Option(help="Overwrite an existing additions file.")] = False,
) -> None:
    """Validate a filled proposals CSV, write data/proposals/canonicals-additions-<date>.yaml and
    check the result against seed in a scratch copy. data/canonicals.yaml is never modified."""
    from smartcart_catalog.settings import load_settings

    if not reviewer.strip():
        raise typer.BadParameter("--reviewer must not be empty")
    day = reviewed_on or date.today().isoformat()
    try:
        date.fromisoformat(day)
    except ValueError as exc:
        raise typer.BadParameter("--date must be YYYY-MM-DD") from exc
    data_dir = load_settings().catalog_data_dir
    try:
        result = parse_filled_csv(csv_file, allow_stale=allow_stale)
    except ProposalImportError as exc:
        typer.echo(f"{csv_file}: {len(exc.problems)} problem(s), nothing written", err=True)
        for p in exc.problems:
            typer.echo(f"  - {p}", err=True)
        raise typer.Exit(1) from exc
    doc, problems = build_additions(result, data_dir, reviewer=reviewer.strip(),
                                    reviewed_on=day, csv_name=csv_file.name)  # fmt: skip
    problems += check_additions(doc, data_dir) if doc["canonicals"] else []
    for w in result.warnings:
        typer.echo(f"warning: {w}", err=True)
    try:
        path = write_additions(doc, out_dir or data_dir / "proposals", force=force)
    except FileExistsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    c = result.counts
    typer.echo(f"additions written: {path} ({c['accept']} accepted, {c['edit']} edited,"
               f" {c['reject']} rejected, {c['pending']} pending)")  # fmt: skip
    typer.echo("data/canonicals.yaml was NOT modified.")
    if problems:
        typer.echo("\nApplied to a scratch copy, `seed` would NOT accept this yet:")
        for p in dict.fromkeys(problems):
            typer.echo(f"  - {p}")
    else:
        typer.echo("\nApplied to a scratch copy of data/, `seed` accepts it.")


def register(parent: typer.Typer) -> None:
    """Add ``propose-canonicals`` and ``proposals-import`` to the catalog CLI."""
    parent.command("propose-canonicals")(propose_canonicals)
    parent.command("proposals-import")(proposals_import)


if __name__ == "__main__":
    standalone = typer.Typer(add_completion=False, no_args_is_help=True)
    register(standalone)
    standalone()
