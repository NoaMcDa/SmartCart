"""Canonical review packet and sign-off import (issue #15), on a small seeded catalog.

The catalog under test is a handful of real entries of ``data/canonicals.yaml`` (with their real
taxonomy and product type rules), renumbered, so the tests are about the packet and not about
the content of the 245. One test at the end builds the packet from the real files.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from smartcart_catalog import review_packet as rp
from smartcart_catalog import seed as seedmod
from smartcart_catalog.cli import app
from smartcart_catalog.seed import default_data_dir, load_catalog, seed_all

SLUGS = ("milk-fresh-3", "milk-fresh-1", "cottage-5", "soy-drink", "almond-drink", "tomato")


@pytest.fixture
def small_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A data dir with the real taxonomy and six canonicals, ranks 1..6."""
    real = default_data_dir()
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(real / "taxonomy.yaml", data / "taxonomy.yaml")
    canon = yaml.safe_load((real / "canonicals.yaml").read_text(encoding="utf-8"))
    by_slug = {c["slug"]: dict(c) for c in canon["canonicals"]}
    entries = []
    for rank, slug in enumerate(SLUGS, start=1):
        e = dict(by_slug[slug])
        e["rank"] = rank
        entries.append(e)
    types = {e["product_type"] for e in entries}
    rules = yaml.safe_load((real / "product_type_rules.yaml").read_text(encoding="utf-8"))
    rules["rules"] = [r for r in rules["rules"] if r["product_type"] in types]
    (data / "product_type_rules.yaml").write_text(
        yaml.safe_dump(rules, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (data / "canonicals.yaml").write_text(
        yaml.safe_dump({"version": 1, "canonicals": entries}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(seedmod, "MIN_CANONICALS", 1)
    monkeypatch.setenv("CATALOG_DATA_DIR", str(data))
    return data


@pytest.fixture
def catalog(small_data: Path):
    return load_catalog(small_data)


def item(name: str, chain: str = "שופרסל", source: str = "real", **kw) -> rp.SourceItem:
    return rp.SourceItem(key=f"{source}:{name}", chain_id=kw.pop("chain_id", "7290027600007"),
                         chain_name=chain, raw_name=name, source=source, **kw)  # fmt: skip


# --- the rule pipeline in memory ------------------------------------------------------------------


def test_match_items_respects_critical_attributes(catalog) -> None:
    matches = {
        m.item.raw_name: m
        for m in rp.match_items(
            catalog,
            [
                item("חלב טרי 3% תנובה 1 ליטר"),
                item("חלב טרי 1% תנובה 1 ליטר"),
                item("משקה סויה אלפרו 1 ליטר"),
                item("משקה שקדים אלפרו 1 ליטר"),
            ],
        )
    }
    assert matches["חלב טרי 3% תנובה 1 ליטר"].canonical_slug == "milk-fresh-3"
    assert matches["חלב טרי 1% תנובה 1 ליטר"].canonical_slug == "milk-fresh-1"
    assert matches["משקה סויה אלפרו 1 ליטר"].canonical_slug == "soy-drink"
    assert matches["משקה שקדים אלפרו 1 ליטר"].canonical_slug == "almond-drink"


def test_match_items_never_crosses_milk_percentages(catalog) -> None:
    (m,) = rp.match_items(catalog, [item("חלב טרי 2% תנובה 1 ליטר")])
    assert m.canonical_slug not in ("milk-fresh-3", "milk-fresh-1")


def test_unmapped_item_has_no_slug(catalog) -> None:
    (m,) = rp.match_items(catalog, [item("מטהר אוויר לבית")])
    assert m.canonical_slug is None and m.level is None


# --- picking examples -----------------------------------------------------------------------------


def _ex(name, chain="א", source="real", level="any_brand", conf=0.95, review=False):
    return rp.Example(name, chain, source, level, conf, review)


def test_pick_examples_limits_and_prefers_real_then_accepted_then_other_chains() -> None:
    found = [
        _ex("synthetic one", source="gold"),
        _ex("review one", "ב", review=True),
        _ex("accepted a1", "א"),
        _ex("accepted a2", "א", conf=0.94),
        _ex("accepted b1", "ב"),
        _ex("accepted c1", "ג"),
        _ex("close d1", "ד", level="close"),
    ]
    picked = rp.pick_examples(found, 5)
    assert len(picked) == 5
    assert all(e.source == "real" for e in picked)  # real fills the five before gold is needed
    assert [e.name for e in picked[:3]] == ["accepted a1", "accepted b1", "accepted c1"]
    assert "synthetic one" not in {e.name for e in picked}
    assert len({e.name for e in picked}) == 5


def test_collect_examples_fills_with_synthetic_and_labels_each(catalog, tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / "gold_pairs.csv").write_text(
        "item_key,item_text,barcode,is_weighed,canonical_slug,label,category,note\n"
        "g1,חלב טרי 3% שטראוס 1 ליטר,7290000000001,False,milk-fresh-3,exact,dairy,x\n"
        "g2,קוטג' 5% גד 250 גרם,7290000000002,False,cottage-5,exact,dairy,x\n",
        encoding="utf-8",
    )
    report = rp.collect_examples(catalog, ["gold"], gold_dir=gold)
    assert report.sources_used == ["gold"]
    assert report.items_seen == {"gold": 2}
    assert {e.source for v in report.by_slug.values() for e in v} == {"gold"}
    assert report.by_slug["milk-fresh-3"][0].name == "חלב טרי 3% שטראוס 1 ליטר"


def test_unknown_source_is_an_error(catalog) -> None:
    with pytest.raises(ValueError, match="unknown examples source"):
        rp.collect_examples(catalog, ["scraped"])


# --- the packet files -----------------------------------------------------------------------------


class _Structure(HTMLParser):
    """Well-formedness of the tags that matter, and any reference to the outside."""

    VOID = {"meta", "br", "link", "input", "img", "hr"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.external: list[str] = []
        self.tags: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        for k, v in attrs:
            if k in ("src", "href", "srcset", "data") and v and not v.startswith("#"):
                self.external.append(f"{tag} {k}={v}")
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack and self.stack[-1] == tag, f"</{tag}> closes {self.stack[-3:]}"
        self.stack.pop()


@pytest.fixture
def packet(small_data: Path, tmp_path: Path):
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / "gold_pairs.csv").write_text(
        "item_key,item_text,barcode,is_weighed,canonical_slug,label,category,note\n"
        "g1,חלב טרי 3% שטראוס 1 ליטר,7290000000001,False,milk-fresh-3,exact,dairy,x\n"
        "g2,קוטג' 5% גד 250 גרם,7290000000002,False,cottage-5,exact,dairy,x\n"
        "g3,חלב טרי 3% <i>x</i> & y 1 ליטר,,False,milk-fresh-3,exact,dairy,x\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    result = rp.build_packet(small_data, out, sources=["gold"], gold_dir=gold)
    return out, result


def test_packet_writes_html_and_csv(packet) -> None:
    out, result = packet
    assert result["rows"] == len(SLUGS)
    assert (out / rp.HTML_NAME).exists() and (out / rp.CSV_NAME).exists()
    assert (out / ".gitignore").read_text() == "*\n"


def test_html_is_self_contained_rtl_and_printable(packet) -> None:
    out, _ = packet
    text = (out / rp.HTML_NAME).read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>")
    assert '<html lang="he" dir="rtl">' in text
    assert "<script" not in text.lower()
    assert "@import" not in text and "url(" not in text
    assert "http://" not in text and "https://" not in text
    assert "Heebo" not in text and "font-family: system-ui" in text
    assert "@media print" in text and "size: A4 landscape" in text
    parser = _Structure()
    parser.feed(text)
    assert parser.stack == []
    assert parser.external == []
    assert parser.tags.count("tr") - parser.tags.count("table") == len(SLUGS)  # one header row each
    for slug in SLUGS:
        assert f'id="c-{slug}"' in text


def test_html_rows_carry_every_required_field(packet) -> None:
    out, _ = packet
    text = (out / rp.HTML_NAME).read_text(encoding="utf-8")
    assert text.count("☐ תקין (OK)") == len(SLUGS)
    assert text.count("☐ שינוי (change)") == len(SLUGS)
    assert text.count("☐ הסרה (remove)") == len(SLUGS)
    # the rank is marked as an estimate on every row
    assert text.count('<span class="tag est">הערכה</span>') == len(SLUGS)
    assert "<b>אחוז שומן:</b> <bdi>3</bdi> <code>fat_pct</code>" in text
    assert "<b>גודל אריזה:</b> <bdi>1000 ml</bdi> <code>pack_size, unit</code>" in text
    assert "<b>קריטי:</b>" in text and "<b>רך:</b>" in text
    assert "ל-100 מ״ל" in text and "ל-100 גרם" in text
    assert "מחלקות" in text  # table of contents
    # the synthetic example is labeled as synthetic, and its markup is escaped
    assert "סינתטי (סט הזהב)" in text
    assert "&lt;i&gt;x&lt;/i&gt; &amp; y" in text and "<i>x</i>" not in text
    # the base of a plant drink is a critical attribute on the page
    assert "בסיס (סויה/שקדים/שיבולת)" in text


def test_html_groups_by_taxonomy(packet) -> None:
    out, _ = packet
    text = (out / rp.HTML_NAME).read_text(encoding="utf-8")
    assert text.count("<h2 ") == 3  # dairy, produce, beverages
    assert "מוצרי חלב וביצים" in text and "פירות וירקות" in text
    # departments follow taxonomy order: dairy before produce
    assert text.index("מוצרי חלב וביצים</h2>") < text.index("פירות וירקות</h2>")


def test_csv_has_empty_decision_columns_and_a_bom(packet, small_data: Path) -> None:
    out, _ = packet
    raw = (out / rp.CSV_NAME).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    assert [r["slug"] for r in rows] == list(SLUGS)
    assert all(r["decision"] == "" and r["comment"] == "" for r in rows)
    assert all(r["proposed_critical_attrs"] == "" for r in rows)
    assert list(rows[0]) == list(rp.CSV_FIELDS)
    soy = next(r for r in rows if r["slug"] == "soy-drink")
    assert soy["critical_attrs"] == "base=soy" and soy["critical_keys"] == "base"
    assert rows[0]["rank_estimate"] == "1" and rows[0]["tier_estimate"] == ""
    milk = rows[0]
    assert milk["examples"].startswith("חלב טרי 3% שטראוס 1 ליטר [")
    assert "סינתטי (סט הזהב)" in milk["examples"]
    entries = {e["slug"]: e for e in rp.raw_entries(small_data)}
    assert milk["row_hash"] == rp.entry_hash(entries["milk-fresh-3"])


def test_tiers_follow_the_documented_sizes() -> None:
    assert [rp.tier_of(r, 245) for r in (1, 24, 25, 78, 79, 155, 156, 230, 231, 245)] == [
        1, 1, 2, 2, 3, 3, 4, 4, 5, 5,
    ]  # fmt: skip
    assert rp.tier_of(3, 6) is None


def test_examples_option_none_gives_a_packet_without_examples(small_data: Path, tmp_path: Path) -> None:
    result = rp.build_packet(small_data, tmp_path / "o", sources=["none"])
    assert result["summary"] == {"total": 6, "with_real": 0, "synthetic_only": 0, "without": 6}
    assert "אין דוגמה בקבצים שנבדקו" in (tmp_path / "o" / rp.HTML_NAME).read_text("utf-8")


# --- importing a filled CSV -----------------------------------------------------------------------


def filled(packet_out: Path, tmp_path: Path, edits: dict[str, dict[str, str]], *,
           drop: tuple[str, ...] = (), extra: list[dict[str, str]] | None = None,
           encoding: str = "utf-8-sig", delimiter: str = ",", name: str = "filled.csv") -> Path:  # fmt: skip
    rows = list(csv.DictReader(io.StringIO((packet_out / rp.CSV_NAME).read_text("utf-8-sig"))))
    out_rows = []
    for r in rows:
        if r["slug"] in drop:
            continue
        r.update(edits.get(r["slug"], {"decision": "OK"}))
        out_rows.append(r)
    out_rows.extend(extra or [])
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=rp.CSV_FIELDS, delimiter=delimiter, lineterminator="\r\n")
    w.writeheader()
    for r in out_rows:
        w.writerow({k: r.get(k, "") for k in rp.CSV_FIELDS})
    path = tmp_path / name
    path.write_bytes(buf.getvalue().encode(encoding))
    return path


def entries_of(data: Path):
    return rp.raw_entries(data)


def test_import_accepts_a_complete_review(packet, small_data, tmp_path) -> None:
    out, _ = packet
    path = filled(out, tmp_path, {
        "cottage-5": {"decision": "change", "comment": "most cottage is 5% but also 3%"},
        "tomato": {"decision": "remove", "comment": "too generic"},
    })  # fmt: skip
    result = rp.parse_filled_csv(path, entries_of(small_data))
    assert result.counts == {"ok": 4, "change": 1, "remove": 1, "add": 0, "pending": 0}
    assert result.stale == [] and result.encoding == "utf-8"


def test_import_reads_hebrew_decisions_and_checkbox_marks(packet, small_data, tmp_path) -> None:
    out, _ = packet
    path = filled(out, tmp_path, {
        "milk-fresh-3": {"decision": "תקין"},
        "milk-fresh-1": {"decision": "☑ OK"},
        "cottage-5": {"decision": "שינוי", "comment": "fat"},
        "soy-drink": {"decision": "להסיר", "comment": "plant drinks later"},
        "almond-drink": {"decision": "ok"},
        "tomato": {"decision": "Yes"},
    })  # fmt: skip
    result = rp.parse_filled_csv(path, entries_of(small_data))
    assert {d.slug: d.decision for d in result.decisions} == {
        "milk-fresh-3": "ok", "milk-fresh-1": "ok", "cottage-5": "change",
        "soy-drink": "remove", "almond-drink": "ok", "tomato": "ok",
    }  # fmt: skip


def test_import_reports_every_problem_together(packet, small_data, tmp_path) -> None:
    out, _ = packet
    path = filled(
        out,
        tmp_path,
        {
            "milk-fresh-3": {"decision": "maybe"},
            "milk-fresh-1": {"decision": "change"},  # no comment
            "cottage-5": {"decision": "OK", "proposed_rank": "2"},  # proposal without change
            "soy-drink": {"decision": "change", "proposed_critical_attrs": "colour=red"},
            "almond-drink": {"decision": "change", "proposed_base_unit": "litre", "comment": "x"},
            "tomato": {"decision": "OK"},
        },
        extra=[{"slug": "no-such-product", "decision": "OK"}],
    )
    with pytest.raises(rp.ReviewImportError) as err:
        rp.parse_filled_csv(path, entries_of(small_data))
    text = str(err.value)
    for needle in ("unknown decision 'maybe'", "milk-fresh-1): 'change' needs a comment",
                   "proposed_* values only go with 'change'", "unknown attribute 'colour'",
                   "proposed_base_unit 'litre'", "'no-such-product' is not in data/canonicals.yaml"):  # fmt: skip
        assert needle in text


def test_import_requires_every_canonical_unless_partial(packet, small_data, tmp_path) -> None:
    out, _ = packet
    path = filled(out, tmp_path, {"tomato": {"decision": ""}})
    with pytest.raises(rp.ReviewImportError, match="1 canonical.*no decision: tomato"):
        rp.parse_filled_csv(path, entries_of(small_data))
    result = rp.parse_filled_csv(path, entries_of(small_data), allow_partial=True)
    assert result.pending == ["tomato"] and result.counts["pending"] == 1


def test_a_note_without_a_decision_is_an_error(packet, small_data, tmp_path) -> None:
    out, _ = packet
    path = filled(out, tmp_path, {"tomato": {"decision": "", "comment": "hmm"}})
    with pytest.raises(rp.ReviewImportError, match="tomato\\): a comment or proposal but no decision"):
        rp.parse_filled_csv(path, entries_of(small_data), allow_partial=True)


def test_import_rejects_duplicates_and_missing_rows(packet, small_data, tmp_path) -> None:
    out, _ = packet
    dup = filled(out, tmp_path, {}, extra=[{"slug": "tomato", "decision": "OK"}])
    with pytest.raises(rp.ReviewImportError, match="tomato appears twice"):
        rp.parse_filled_csv(dup, entries_of(small_data))
    gone = filled(out, tmp_path, {}, drop=("cottage-5",), name="gone.csv")
    with pytest.raises(rp.ReviewImportError, match="cottage-5"):
        rp.parse_filled_csv(gone, entries_of(small_data))


def test_import_detects_a_stale_packet(packet, small_data, tmp_path) -> None:
    out, _ = packet
    path = filled(out, tmp_path, {})
    doc = yaml.safe_load((small_data / "canonicals.yaml").read_text(encoding="utf-8"))
    doc["canonicals"][0]["critical_attrs"]["fat_pct"] = 2
    (small_data / "canonicals.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(rp.ReviewImportError, match="changed in data/canonicals.yaml"):
        rp.parse_filled_csv(path, entries_of(small_data))
    result = rp.parse_filled_csv(path, entries_of(small_data), allow_stale=True)
    assert result.stale == ["milk-fresh-3"]


def test_import_reads_hebrew_excel_exports(packet, small_data, tmp_path) -> None:
    out, _ = packet
    # Excel "CSV" on Hebrew Windows: windows-1255, and some locales write semicolons
    path = filled(out, tmp_path, {"milk-fresh-1": {"decision": "שינוי", "comment": "בדיקה"}},
                  encoding="cp1255", delimiter=";")  # fmt: skip
    result = rp.parse_filled_csv(path, entries_of(small_data))
    assert result.encoding == "windows-1255"
    assert any("not UTF-8" in w for w in result.warnings)
    assert any("delimiter" in w for w in result.warnings)
    change = next(d for d in result.decisions if d.decision == "change")
    assert change.comment == "בדיקה"


def test_import_rejects_a_csv_without_the_decision_columns(small_data, tmp_path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("slug,remarks\nmilk-fresh-3,fine\n", encoding="utf-8")
    with pytest.raises(rp.ReviewImportError, match="missing column"):
        rp.parse_filled_csv(path, entries_of(small_data))


def test_add_rows_become_additions(packet, small_data, tmp_path) -> None:
    out, _ = packet
    path = filled(out, tmp_path, {}, extra=[
        {"slug": "", "decision": "add", "display_name_he": "מוצרלה מגורדת", "comment": "weekly"},
    ])  # fmt: skip
    result = rp.parse_filled_csv(path, entries_of(small_data))
    assert [(a.proposed["display_name_he"], a.comment) for a in result.additions] == [
        ("מוצרלה מגורדת", "weekly")
    ]
    bad = filled(out, tmp_path, {}, extra=[{"slug": "", "decision": "add", "comment": "no name"}],
                 name="bad.csv")  # fmt: skip
    with pytest.raises(rp.ReviewImportError, match="needs display_name_he"):
        rp.parse_filled_csv(bad, entries_of(small_data))


# --- sign-off file and the implied diff -----------------------------------------------------------


def test_parse_attrs_cell() -> None:
    assert rp.parse_attrs_cell("fat_pct=2.5; state=fresh") == {"fat_pct": 2.5, "state": "fresh"}
    assert rp.parse_attrs_cell("{}") == {} and rp.parse_attrs_cell("none") == {}
    assert rp.parse_attrs_cell("fat_pct=9") == {"fat_pct": 9}
    with pytest.raises(ValueError, match="key=value"):
        rp.parse_attrs_cell("fat 9")
    with pytest.raises(ValueError, match="no value"):
        rp.parse_attrs_cell("fat_pct=")


def test_signoff_file_and_overwrite_protection(packet, small_data, tmp_path) -> None:
    out, _ = packet
    path = filled(out, tmp_path, {"tomato": {"decision": "change", "comment": "split red/cherry"}})
    result = rp.parse_filled_csv(path, entries_of(small_data))
    doc = rp.signoff_document(result, reviewer="דנה כהן", reviewed_on="2026-10-20", note="n",
                              canonicals_path=small_data / "canonicals.yaml", total=6,
                              csv_name="filled.csv")  # fmt: skip
    written = rp.write_signoff(doc, tmp_path / "signoff")
    assert written.name == "canonicals-2026-10-20.yaml"
    loaded = yaml.safe_load(written.read_text(encoding="utf-8"))
    assert loaded["reviewer"] == "דנה כהן" and loaded["reviewed_on"] == "2026-10-20"
    assert loaded["status"] == "complete" and loaded["pending"] == []
    assert loaded["summary"] == {"ok": 5, "change": 1, "remove": 0, "add": 0, "pending": 0}
    assert loaded["source"]["canonicals_sha256_12"] == hashlib.sha256(
        (small_data / "canonicals.yaml").read_bytes()
    ).hexdigest()[:12]
    assert loaded["decisions"][-1] == {"slug": "tomato", "decision": "change",
                                       "comment": "split red/cherry"}  # fmt: skip
    with pytest.raises(FileExistsError):
        rp.write_signoff(doc, tmp_path / "signoff")
    rp.write_signoff(doc, tmp_path / "signoff", force=True)


def test_the_empty_template_has_the_writers_keys(packet, small_data, tmp_path) -> None:
    out, _ = packet
    result = rp.parse_filled_csv(filled(out, tmp_path, {}), entries_of(small_data))
    doc = rp.signoff_document(result, reviewer="x", reviewed_on="2026-10-20", note="",
                              canonicals_path=small_data / "canonicals.yaml", total=6,
                              csv_name="f.csv")  # fmt: skip
    template = yaml.safe_load((default_data_dir() / "signoff" / "template.yaml").read_text("utf-8"))
    assert list(template) == list(doc)
    assert list(template["source"]) == list(doc["source"])
    assert list(template["summary"]) == list(doc["summary"])


def test_diff_for_a_removal_renumbers_ranks_and_flags_validation(
    packet, small_data, catalog, tmp_path
) -> None:
    out, _ = packet
    path = filled(out, tmp_path, {"tomato": {"decision": "remove", "comment": "x"}})
    result = rp.parse_filled_csv(path, entries_of(small_data))
    report = rp.implied_diff(catalog, entries_of(small_data), result)
    assert "-- slug: tomato" in report.diff
    assert report.changed_entries == 1
    # `tomato` is the last rank, so nothing is renumbered; its product type has no canonical left
    assert any("product types left without a canonical" in p for p in report.problems)


def test_diff_for_a_change_shows_only_that_entry(packet, small_data, catalog, tmp_path) -> None:
    out, _ = packet
    path = filled(out, tmp_path, {"cottage-5": {
        "decision": "change", "comment": "most common is 3%", "proposed_critical_attrs": "fat_pct=3",
        "proposed_display_name_he": "קוטג' 3%", "proposed_soft_attrs": "pack_size=250; unit=g",
    }})  # fmt: skip
    result = rp.parse_filled_csv(path, entries_of(small_data))
    before = (small_data / "canonicals.yaml").read_bytes()
    report = rp.implied_diff(catalog, entries_of(small_data), result)
    assert "-  display_name_he: קוטג' 5%" in report.diff
    assert "+  display_name_he: קוטג' 3%" in report.diff
    assert "-  critical_attrs: {fat_pct: 5}" in report.diff
    assert "+  critical_attrs: {fat_pct: 3}" in report.diff
    assert "milk-fresh-3" not in report.diff
    # A critical-attribute change must reach the Arabic names too (#73): the seed validation flags
    # every Arabic name that still states the old fat percentage, and nothing else.
    assert report.problems
    assert all(
        p.startswith("cottage-5: names_ar ") and p.endswith("must state the fat percentage 3%")
        for p in report.problems
    ), report.problems
    assert (small_data / "canonicals.yaml").read_bytes() == before  # never applied


def test_rank_moves_and_removals_renumber_without_gaps(small_data) -> None:
    entries = entries_of(small_data)
    decisions = [
        rp.Decision("milk-fresh-1", "remove", "x"),
        rp.Decision("tomato", "change", "", proposed={"rank": 1}),
    ]
    after = rp.apply_decisions(entries, decisions)
    assert [(e["slug"], e["rank"]) for e in after] == [
        ("tomato", 1), ("milk-fresh-3", 2), ("cottage-5", 3), ("soy-drink", 4), ("almond-drink", 5),
    ]  # fmt: skip


def test_a_change_that_breaks_the_critical_keys_is_reported(packet, small_data, catalog, tmp_path) -> None:
    out, _ = packet
    path = filled(out, tmp_path, {"cottage-5": {
        "decision": "change", "comment": "x", "proposed_critical_attrs": "fat_pct=5; state=fresh",
    }})  # fmt: skip
    result = rp.parse_filled_csv(path, entries_of(small_data))
    report = rp.implied_diff(catalog, entries_of(small_data), result)
    assert any("critical_attrs" in p and "cottage-5" in p for p in report.problems)


def test_changes_without_a_proposal_and_additions_are_follow_ups(
    packet, small_data, catalog, tmp_path
) -> None:
    out, _ = packet
    path = filled(out, tmp_path, {"cottage-5": {"decision": "change", "comment": "split by fat"}},
                  extra=[{"slug": "", "decision": "add", "display_name_he": "מוצרלה",
                          "comment": "pizza"}])  # fmt: skip
    result = rp.parse_filled_csv(path, entries_of(small_data))
    report = rp.implied_diff(catalog, entries_of(small_data), result)
    assert report.diff == ""
    assert any(line.startswith("change cottage-5: needs a manual edit - split by fat")
               for line in report.follow_ups)  # fmt: skip
    assert any("מוצרלה" in line for line in report.follow_ups)


# --- the command line -----------------------------------------------------------------------------


def test_cli_round_trip(small_data: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "dist" / "review"
    res = runner.invoke(app, ["review-packet", "--out", str(out), "--examples", "none"])
    assert res.exit_code == 0, res.output
    assert "6 canonicals written" in res.output
    filled_csv = filled(out, tmp_path, {"tomato": {"decision": "remove", "comment": "x"}})
    before = (small_data / "canonicals.yaml").read_bytes()
    res = runner.invoke(app, ["review-import", str(filled_csv), "--reviewer", "Dana",
                              "--date", "2026-10-21", "--patch-out", str(tmp_path / "p.diff")])  # fmt: skip
    assert res.exit_code == 0, res.output
    signoff = small_data / "signoff" / "canonicals-2026-10-21.yaml"
    assert signoff.exists()
    assert "NOT applied" in res.output and "-- slug: tomato" in res.output
    assert (tmp_path / "p.diff").read_text().startswith("---")
    assert (small_data / "canonicals.yaml").read_bytes() == before
    again = runner.invoke(app, ["review-import", str(filled_csv), "--reviewer", "Dana",
                                "--date", "2026-10-21"])  # fmt: skip
    assert again.exit_code == 1 and "--force" in again.output


def test_cli_import_exit_code_and_nothing_written_on_problems(small_data: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "o"
    runner.invoke(app, ["review-packet", "--out", str(out), "--examples", "none"])
    blank = out / rp.CSV_NAME  # nothing decided
    res = runner.invoke(app, ["review-import", str(blank), "--reviewer", "Dana"])
    assert res.exit_code == 1
    assert "have no decision" in res.output
    assert not (small_data / "signoff").exists()


def test_cli_unknown_examples_source(small_data: Path, tmp_path: Path) -> None:
    res = CliRunner().invoke(app, ["review-packet", "--out", str(tmp_path), "--examples", "web"])
    assert res.exit_code == 2 and "unknown examples source" in res.output


# --- database: the in-memory pipeline equals the one the CLI runs ---------------------------------


@pytest.mark.pgvector
def test_in_memory_matching_equals_the_database_pipeline(db, catalog) -> None:
    from smartcart_catalog.embed import HashEmbedder, embed_canonicals, embed_items
    from smartcart_catalog.extract.queue import run_extraction
    from smartcart_catalog.extract.rule import RuleExtractor
    from smartcart_catalog.judge import RuleJudge
    from smartcart_catalog.match import run_matching

    # (name, item code, is_weighed flag): the code matters, a short numeric one reads as weighed
    names = [
        ("חלב טרי 3% תנובה 1 ליטר", "m1", False),
        ("חלב טרי 1% תנובה 1 ליטר", "m2", False),
        ("חלב 2% שטראוס", "m3", False),
        ("קוטג' תנובה 5% 250 גרם", "c1", False),
        ("קוטג' 9% 250 גרם", "c2", False),
        ("משקה סויה אלפרו 1 ליטר", "s1", False),
        ("משקה שקדים בטעם וניל 1 ליטר", "s2", False),
        ("עגבניות שרי", "t1", True),
        ("עגבניה", "15255", False),  # PLU-style code: normalization treats it as weighed
        ("נקטר ספרינג עגבניות", "t3", False),
        ("מטהר אוויר", "z1", False),
    ]
    seed_all(db, catalog)
    db.execute("INSERT INTO chains (id, name, portal) VALUES ('c1', 'שופרסל', 'other')")
    ids = {}
    for name, code, weighed in names:
        ids[name] = db.execute(
            "INSERT INTO items (chain_id, item_code, raw_name, is_weighed)"
            " VALUES ('c1', %s, %s, %s) RETURNING id", (code, name, weighed)
        ).fetchone()[0]
    run_extraction(db, RuleExtractor(catalog), record_run=False)
    embedder = HashEmbedder()
    embed_canonicals(db, embedder)
    embed_items(db, embedder)
    results = {r.decision.item_id: r.decision for r in run_matching(db, RuleJudge())}

    slug_of = dict(db.execute("SELECT id, slug FROM canonical_products").fetchall())
    src = [rp.SourceItem(key=name, chain_id="c1", chain_name="שופרסל", raw_name=name,
                         source="real", is_weighed=weighed, item_code=code)
           for name, code, weighed in names]  # fmt: skip
    for m in rp.match_items(catalog, src):
        d = results[ids[m.item.raw_name]]
        db_slug = slug_of[d.canonical_id] if d.canonical_id else None
        assert (m.canonical_slug, m.level, m.needs_review) == (db_slug, d.flex_level, d.needs_review), m
        if d.canonical_id:
            assert m.confidence == pytest.approx(d.confidence, abs=0.005)


def test_examples_from_db_rows(db, catalog) -> None:
    seed_all(db, catalog)
    db.execute("INSERT INTO chains (id, name, portal) VALUES ('c1', 'שופרסל', 'other')")
    db.execute("INSERT INTO chains (id, name, portal) VALUES ('gold', 'gold', 'other')")
    cid = db.execute("SELECT id FROM canonical_products WHERE slug = 'milk-fresh-3'").fetchone()[0]
    for n, (chain, name, rejected) in enumerate([
        ("c1", "חלב תנובה 3%", False), ("c1", "חלב מחוק 3%", True), ("gold", "חלב זהב 3%", False),
    ]):  # fmt: skip
        iid = db.execute("INSERT INTO items (chain_id, item_code, raw_name) VALUES (%s, %s, %s)"
                         " RETURNING id", (chain, f"x{n}", name)).fetchone()[0]  # fmt: skip
        db.execute(
            "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source,"
            " needs_review, human_rejected) VALUES (%s, %s, 'any_brand', 0.95, 'rule', false, %s)",
            (iid, cid, rejected),
        )
    found = rp.examples_from_db(db)
    assert [(e.name, e.chain, e.source) for e in found["milk-fresh-3"]] == [
        ("חלב תנובה 3%", "שופרסל", "db")
    ]


# --- the real files -------------------------------------------------------------------------------


def test_real_catalog_packet_from_the_real_fixtures(tmp_path: Path) -> None:
    real_items = rp.load_real_items()
    if not real_items:
        pytest.skip("the real fixtures are not in this checkout")
    result = rp.build_packet(default_data_dir(), tmp_path)
    assert result["rows"] == 245
    assert result["items_seen"]["real"] == len(real_items) >= 1000
    s = result["summary"]
    assert s["with_real"] > 50 and s["with_real"] + s["synthetic_only"] + s["without"] == 245
    text = (tmp_path / rp.HTML_NAME).read_text(encoding="utf-8")
    assert "קובץ אמיתי של רשת" in text and "שכבה 1 (הערכה)" in text and "שכבה 5 (הערכה)" in text
    rows = list(csv.DictReader(io.StringIO((tmp_path / rp.CSV_NAME).read_text("utf-8-sig"))))
    assert len(rows) == 245 and rows[0]["slug"] == "milk-fresh-3" and rows[0]["tier_estimate"] == "1"
    assert max(len(r["examples"].split(" | ")) for r in rows) <= 5
    json.dumps(result["summary"])
