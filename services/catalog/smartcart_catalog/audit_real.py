"""Machine audit of the rule pipeline on the real chain items (issues #2, #20, #33, #38).

``smartcart-catalog audit-real`` runs the full rule pipeline (normalize, ``RuleExtractor``, block,
hash-embedder retrieval, ``RuleJudge``; in memory, like the review packet) over every item of the
committed real price-file fixtures (``services/ingest/tests/fixtures/<chain>/real``) and writes
``data/audit/real-<date>.csv``: item name, chain, extracted attributes, the mapped canonical and
level, confidence, ``needs_review`` and the judge's reason.

The ``machine_verdict`` column is **not** produced by this module. It is read from
``data/audit/machine_verdicts.csv`` (one row per ``item key`` + ``canonical``: ``correct``,
``wrong`` or ``unsure`` and a one-line reason), written by reading each accepted mapping (name,
attributes and canonical). It is a machine audit, one reader and no second opinion: it is not a
gold set, and the precision it gives is an indication, not the product's precision. Real
precision needs the human-labeled gold set (issue #38, ``docs/matching.md``).

Precision here is ``correct / (correct + wrong)`` over the *accepted* mappings (the ones a user
would be shown without a review flag), per flexibility level; ``unsure`` rows are excluded and
counted separately. An accepted mapping with no verdict is reported as ``unlabeled``.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer

from smartcart_catalog.review_packet import (
    ItemMatch,
    SourceItem,
    load_real_items,
    match_items,
)
from smartcart_catalog.seed import Catalog, load_catalog

REPO = Path(__file__).resolve().parents[3]
AUDIT_DIR = REPO / "data" / "audit"
VERDICTS_NAME = "machine_verdicts.csv"

VERDICTS = ("correct", "wrong", "unsure")
LEVELS = ("exact", "any_brand", "close")

COLUMNS = (
    "chain", "item_key", "raw_name", "name_truncated", "product_type", "fat_pct", "state",
    "flavor", "base", "brand", "pack_size", "unit", "canonical_slug", "canonical_name_he",
    "level", "confidence", "needs_review", "served", "judge_reason", "machine_verdict",
    "machine_verdict_reason",
)  # fmt: skip

HEADER = (
    "# SmartCart machine audit of the rule pipeline on REAL chain items (issue #38 groundwork).",
    "# Items: the 200-row price files of seven chains committed as regression fixtures"
    " (services/ingest/tests/fixtures/<chain>/real).",
    "# Pipeline: normalize, RuleExtractor, block, hash embedder, RuleJudge (no API key, no database).",
    "# machine_verdict is a MACHINE AUDIT, not a gold set: one reader (Claude) judged each ACCEPTED"
    " (served, needs_review=False) mapping from the name, the extracted attributes and the"
    " canonical. No human labeled it.",
    "# Precision from this file is an indication only; real precision needs the human-labeled gold"
    " set (docs/matching.md, issue #38).",
    "# Lines starting with # are comments; skip them when reading the CSV.",
)


@dataclass(frozen=True)
class Verdict:
    verdict: str
    reason: str


@dataclass
class AuditRow:
    match: ItemMatch
    attrs: Any  # Attributes | None
    truncated: bool
    canonical_name_he: str
    verdict: Verdict | None = None

    @property
    def served(self) -> bool:
        return self.match.canonical_slug is not None and not self.match.needs_review

    @property
    def key(self) -> tuple[str, str]:
        return (self.match.item.key, self.match.canonical_slug or "")

    def as_dict(self) -> dict[str, str]:
        m, a = self.match, self.attrs

        def v(name: str) -> str:
            val = getattr(a, name, None) if a is not None else None
            return "" if val is None else str(val)

        return {
            "chain": m.item.chain_name,
            "item_key": m.item.key,
            "raw_name": m.item.raw_name,
            "name_truncated": "yes" if self.truncated else "",
            "product_type": v("product_type"),
            "fat_pct": v("fat_pct"),
            "state": v("state"),
            "flavor": v("flavor"),
            "base": v("base"),
            "brand": v("brand"),
            "pack_size": v("pack_size"),
            "unit": v("unit"),
            "canonical_slug": m.canonical_slug or "",
            "canonical_name_he": self.canonical_name_he,
            "level": m.level or "",
            "confidence": f"{m.confidence:.2f}",
            "needs_review": "yes" if (m.canonical_slug and m.needs_review) else "",
            "served": "yes" if self.served else "",
            "judge_reason": m.reason[:500],
            "machine_verdict": self.verdict.verdict if self.verdict else "",
            "machine_verdict_reason": self.verdict.reason if self.verdict else "",
        }


@dataclass
class LevelStats:
    correct: int = 0
    wrong: int = 0
    unsure: int = 0
    unlabeled: int = 0

    @property
    def labeled(self) -> int:
        return self.correct + self.wrong

    @property
    def served(self) -> int:
        return self.correct + self.wrong + self.unsure + self.unlabeled

    @property
    def precision(self) -> float | None:
        return self.correct / self.labeled if self.labeled else None


@dataclass
class AuditReport:
    rows: list[AuditRow]
    items: int = 0
    mapped: int = 0
    served: int = 0
    to_review: int = 0
    by_level: dict[str, LevelStats] = field(default_factory=dict)

    @property
    def overall(self) -> LevelStats:
        total = LevelStats()
        for s in self.by_level.values():
            total.correct += s.correct
            total.wrong += s.wrong
            total.unsure += s.unsure
            total.unlabeled += s.unlabeled
        return total


def load_verdicts(path: Path | None = None) -> dict[tuple[str, str], Verdict]:
    """``{(item key, canonical slug): Verdict}`` from ``data/audit/machine_verdicts.csv``."""
    path = path or AUDIT_DIR / VERDICTS_NAME
    if not path.exists():
        return {}
    out: dict[tuple[str, str], Verdict] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        lines = (ln for ln in fh if not ln.startswith("#"))
        for row in csv.DictReader(lines):
            verdict = row["verdict"].strip().lower()
            if verdict not in VERDICTS:
                raise ValueError(f"{path}: {row['item_key']}: verdict must be one of {VERDICTS}")
            out[(row["item_key"], row["canonical_slug"])] = Verdict(verdict, row["reason"].strip())
    return out


def run_audit(
    catalog: Catalog | None = None,
    items: Sequence[SourceItem] | None = None,
    verdicts: Mapping[tuple[str, str], Verdict] | None = None,
) -> AuditReport:
    """The rule pipeline over ``items`` (default: the real fixtures), with verdicts attached."""
    from smartcart_catalog.extract.rule import RuleExtractor
    from smartcart_catalog.models import ExtractionError
    from smartcart_catalog.normalize import is_truncated, normalize

    catalog = catalog or load_catalog()
    items = list(items) if items is not None else load_real_items()
    verdicts = verdicts if verdicts is not None else load_verdicts()
    matches = match_items(catalog, items)
    names = {c.slug: c.display_name_he for c in catalog.canonicals}

    extractor = RuleExtractor(catalog)
    normalized = [
        normalize(
            {
                "id": n, "chain_id": it.chain_id, "chain_name": it.chain_name,
                "item_code": it.item_code, "barcode": it.barcode, "raw_name": it.raw_name,
                "manufacturer": it.manufacturer, "quantity": it.quantity, "unit": it.unit,
                "is_weighed": it.is_weighed,
            },
            item_id=n,
        )
        for n, it in enumerate(items, start=1)
    ]  # fmt: skip
    attrs_all = extractor.extract(normalized)

    report = AuditReport(rows=[], items=len(items))
    for m, attrs in zip(matches, attrs_all, strict=True):
        attrs = None if isinstance(attrs, ExtractionError) else attrs
        row = AuditRow(m, attrs, is_truncated(m.item.chain_id, m.item.raw_name),
                       names.get(m.canonical_slug or "", ""))  # fmt: skip
        if m.canonical_slug:
            report.mapped += 1
            if row.served:
                report.served += 1
                row.verdict = verdicts.get(row.key)
                stats = report.by_level.setdefault(m.level or "?", LevelStats())
                if row.verdict is None:
                    stats.unlabeled += 1
                else:
                    setattr(stats, row.verdict.verdict, getattr(stats, row.verdict.verdict) + 1)
            else:
                report.to_review += 1
        report.rows.append(row)
    return report


def write_csv(report: AuditReport, path: Path) -> None:
    """The audit CSV: comment header, then one row per item (UTF-8 with BOM for Excel)."""
    buf = io.StringIO()
    for line in HEADER:
        buf.write(line + "\n")
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    for row in report.rows:
        w.writerow(row.as_dict())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(buf.getvalue(), encoding="utf-8-sig")


def relabel_csv(path: Path, verdicts: Mapping[tuple[str, str], Verdict]) -> AuditReport:
    """Re-apply ``verdicts`` to an audit CSV written earlier (the baseline of a before/after
    comparison), rewrite its verdict columns in place and return the per-level statistics.

    Only the verdict columns and the counts are recomputed; the rows are the file's own, so the
    pipeline that produced them does not have to exist any more."""
    lines = [
        ln for ln in path.read_text(encoding="utf-8-sig").splitlines() if not ln.startswith("#")
    ]
    rows = list(csv.DictReader(lines))
    report = AuditReport(rows=[], items=len(rows))
    for r in rows:
        v = None
        if r["canonical_slug"]:
            report.mapped += 1
            if r["served"]:
                report.served += 1
                v = verdicts.get((r["item_key"], r["canonical_slug"]))
                stats = report.by_level.setdefault(r["level"] or "?", LevelStats())
                if v is None:
                    stats.unlabeled += 1
                else:
                    setattr(stats, v.verdict, getattr(stats, v.verdict) + 1)
            else:
                report.to_review += 1
        r["machine_verdict"] = v.verdict if v else ""
        r["machine_verdict_reason"] = v.reason if v else ""
    buf = io.StringIO()
    for line in HEADER:
        buf.write(line + "\n")
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8-sig")
    return report


def format_summary(report: AuditReport) -> str:
    lines = [
        f"{report.items} real items: {report.mapped} mapped, {report.served} served"
        f" (accepted, no review flag), {report.to_review} mapped for review,"
        f" {report.items - report.mapped} unmapped",
        "machine audit (NOT a gold set): precision = correct / (correct + wrong), unsure excluded",
        f"{'level':<10} {'served':>6} {'correct':>8} {'wrong':>6} {'unsure':>7} {'unlabeled':>10}"
        f" {'precision':>10}",
    ]
    for level in (*LEVELS, *sorted(set(report.by_level) - set(LEVELS))):
        s = report.by_level.get(level)
        if s is None:
            continue
        lines.append(_stats_line(level, s))
    lines.append(_stats_line("all", report.overall))
    return "\n".join(lines)


def _stats_line(label: str, s: LevelStats) -> str:
    p = f"{s.precision:.3f}" if s.precision is not None else "n/a"
    return (f"{label:<10} {s.served:>6} {s.correct:>8} {s.wrong:>6} {s.unsure:>7}"
            f" {s.unlabeled:>10} {p:>10}")  # fmt: skip


def wrong_rows(rows: Iterable[AuditRow]) -> list[AuditRow]:
    return [r for r in rows if r.verdict and r.verdict.verdict == "wrong"]


def audit_real(
    out: Annotated[
        Path | None, typer.Option(help="Output CSV (default data/audit/real-<date>.csv).")
    ] = None,
    day: Annotated[str | None, typer.Option("--date", help="YYYY-MM-DD for the file name.")] = None,
    verdicts_file: Annotated[Path | None, typer.Option(help="Machine verdicts CSV.")] = None,
    show_wrong: Annotated[int, typer.Option(help="Print up to N accepted rows judged wrong.")] = 20,
    require_verdicts: Annotated[
        bool, typer.Option(help="Exit 1 if an accepted mapping has no verdict.")
    ] = False,
    relabel: Annotated[
        Path | None,
        typer.Option(
            help="Do not run the pipeline: re-apply the verdicts to this earlier audit CSV."
        ),
    ] = None,
) -> None:
    """Run the rule pipeline over every real item; write data/audit/real-<date>.csv."""
    if relabel is not None:
        typer.echo(format_summary(relabel_csv(relabel, load_verdicts(verdicts_file))))
        typer.echo(f"verdict columns rewritten: {relabel}")
        return
    stamp = day or date.today().isoformat()
    try:
        date.fromisoformat(stamp)
    except ValueError as exc:
        raise typer.BadParameter("--date must be YYYY-MM-DD") from exc
    report = run_audit(verdicts=load_verdicts(verdicts_file))
    if not report.items:
        typer.echo("no real items found (services/ingest/tests/fixtures/<chain>/real)", err=True)
        raise typer.Exit(1)
    path = out or AUDIT_DIR / f"real-{stamp}.csv"
    write_csv(report, path)
    typer.echo(format_summary(report))
    for r in wrong_rows(report.rows)[:show_wrong]:
        typer.echo(f"  wrong: {r.match.item.raw_name!r} -> {r.match.canonical_slug}"
                   f" [{r.match.level}]: {r.verdict.reason if r.verdict else ''}")  # fmt: skip
    typer.echo(f"written: {path}")
    missing = report.overall.unlabeled
    if missing:
        typer.echo(f"{missing} accepted mapping(s) have no verdict in {VERDICTS_NAME}", err=True)
        if require_verdicts:
            raise typer.Exit(1)


def register(app: typer.Typer) -> None:
    """Add ``audit-real`` to the catalog CLI."""
    app.command("audit-real")(audit_real)
