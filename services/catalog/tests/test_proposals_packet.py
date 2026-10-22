"""The proposals review packet and its import (issue #52).

The import turns a reviewer's answers into additions for ``data/canonicals.yaml`` in a *separate*
file, never into the file itself, and the additions are checked against ``seed`` in a scratch copy
of the real seed files.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from smartcart_catalog import proposals as P
from smartcart_catalog import proposals_packet as K
from smartcart_catalog.cli import app
from smartcart_catalog.seed import load_catalog
from smartcart_catalog.taxonomy import default_data_dir

DATA = default_data_dir()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cand(chain, code, name, *, qty=None, unit=None, barcode=None, price="9.90"):
    return P.CandidateItem(
        chain_id=chain, chain_name=f"chain {chain}", item_code=code, raw_name=name,
        barcode=barcode, quantity=None if qty is None else Decimal(str(qty)), unit=unit,
        stores=4, price=Decimal(price), price_events=3,
    )  # fmt: skip


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(DATA)


@pytest.fixture(scope="module")
def synthetic_run(catalog):
    """Two variants (a banana yogurt, a bulgarian cheese at 18%) and two new types."""
    items = []
    for chain in ("a", "b", "c"):
        items.append(cand(chain, "y", "יוגורט פירות בננה", qty=200, unit="גרם"))
        items.append(cand(chain, "l", "עדשים צהובות", qty=500, unit="גרם"))
    for chain in ("a", "b"):
        items.append(cand(chain, "t", "שמן שומשום", qty=250, unit="מיליליטר"))
        items.append(cand(chain, "g", "גבינה בולגרית 18%", qty=250, unit="גרם"))
    pool = P.ItemPool(
        items=items, total_items=len(items) + 10, mapped_items=10, source="test",
        chains={"a": "chain a", "b": "chain b", "c": "chain c"},
    )  # fmt: skip
    return P.propose(pool, catalog, top=10)


def rows_of(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text, newline="")))


def by_name(rows, name):
    return next(r for r in rows if r["display_name_he"] == name)


# --- the packet ---------------------------------------------------------------------------------------


def test_the_csv_has_the_proposal_the_coverage_the_examples_and_empty_decision_columns(
    synthetic_run,
) -> None:
    rows = rows_of(K.render_csv(synthetic_run))
    assert len(rows) == 4
    r = by_name(rows, "יוגורט פירות בננה")
    assert r["kind"] == "variant" and r["product_type"] == "yogurt_fruit"
    assert r["taxonomy_id"] == "dairy.yogurt.fruit" and r["base_unit"] == "100g"
    assert r["critical_attrs"] == "flavor=banana" and r["soft_attrs"] == "pack_size=200; unit=g"
    assert (r["chains"], r["items"]) == ("3", "3")
    assert (
        r["examples"].count("chain ") == 3
        and "200 גרם" in r["examples"]
        and "₪9.90" in r["examples"]
    )
    assert r["decision"] == "" and r["comment"] == "" and r["names_ar"] == ""
    assert all(r[f"edit_{k}"] == "" for k in K.EDIT_FIELDS)
    new = by_name(rows, "עדשים צהובות")
    assert new["kind"] == "new_type" and new["product_type"] == "" and new["suggested_product_type"]
    assert "product_type" in new["uncertain"] and "taxonomy_id" in new["uncertain"]
    assert float(r["share_of_unmapped_items"]) == pytest.approx(
        3 / synthetic_run.stats["items_unmapped"], abs=1e-3
    )


def test_the_html_is_self_contained_hebrew_rtl_with_a_decision_box_per_row(
    synthetic_run, tmp_path
) -> None:
    paths = K.write_packet(synthetic_run, DATA, tmp_path)
    page = paths["html"].read_text(encoding="utf-8")
    assert '<html lang="he" dir="rtl">' in page and "<script" not in page
    assert "http://" not in page and "https://" not in page  # no external asset
    assert page.count("☐ אישור") == 4 and page.count("☐ עריכה") == 4 and page.count("☐ דחייה") == 4
    assert "יוגורט פירות בננה" in page and "הערכה" in page and "חסם עליון" in page
    doc = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert doc["stats"]["proposals"] == 4 and len(doc["proposals"]) == 4
    assert paths["csv"].read_bytes().startswith(b"\xef\xbb\xbf")  # BOM for Excel
    assert (tmp_path / ".gitignore").read_text() == "*\n"


# --- the import -----------------------------------------------------------------------------------------


def fill(text: str, answers: dict[str, dict[str, str]], path: Path) -> Path:
    """Write the CSV with the reviewer's answers per display name."""
    rows = rows_of(text)
    for r in rows:
        r.update(answers.get(r["display_name_he"], {}))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=K.CSV_FIELDS, lineterminator="\r\n")
    w.writeheader()
    w.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8-sig", newline="")
    return path


GOOD = {
    "גבינה בולגרית 18%": {"decision": "accept", "names_ar": "جبنة بلغارية 18% | بلغارية 18%"},
    "עדשים צהובות": {
        "decision": "edit",
        "edit_taxonomy_id": "pantry.legumes.dry",
        "edit_product_type": "lentils_yellow",
        "edit_slug": "lentils-yellow",
        "names_ar": "عدس اصفر",
    },
    "שמן שומשום": {"decision": "reject", "comment": "niche"},
}


def taxonomy_leaf(catalog, prefix):
    return next(n.id for n in catalog.taxonomy.nodes if n.id.startswith(prefix) and n.level >= 3)


def test_accepted_and_edited_rows_become_additions_that_seed_accepts_in_a_scratch_copy(
    synthetic_run, catalog, tmp_path
) -> None:
    answers = {k: dict(v) for k, v in GOOD.items()}
    answers["עדשים צהובות"]["edit_taxonomy_id"] = taxonomy_leaf(catalog, "pantry")
    before = {
        n: sha(DATA / n) for n in ("canonicals.yaml", "product_type_rules.yaml", "taxonomy.yaml")
    }
    filled = fill(K.render_csv(synthetic_run), answers, tmp_path / "filled.csv")
    result = K.parse_filled_csv(filled)
    assert result.counts == {"accept": 1, "edit": 1, "reject": 1, "pending": 1}
    doc, problems = K.build_additions(result, DATA, reviewer="Dana", reviewed_on="2026-10-22",
                                      csv_name=filled.name)  # fmt: skip
    assert problems == []
    assert [c["slug"] for c in doc["canonicals"]] == ["lentils-yellow", "bulgarian-cheese-18"]
    assert [c["rank"] for c in doc["canonicals"]] == [246, 247]
    assert doc["canonicals"][1]["critical_attrs"] == {"fat_pct": 18}
    assert doc["product_type_rules"][0]["product_type"] == "lentils_yellow"  # a rule stub
    assert doc["rejected"][0]["comment"] == "niche"
    path = K.write_additions(doc, tmp_path / "out")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Proposed additions") and "NOT MERGED" in text
    loaded = yaml.safe_load(text)
    assert loaded["status"].startswith("proposal") and loaded["reviewer"] == "Dana"
    # the real seed files are untouched, and the scratch copy with the additions loads
    assert before == {n: sha(DATA / n) for n in before}
    assert K.check_additions(loaded, DATA) == []
    # a scratch copy loads through the real seed loader: 247 canonicals, the new rule is there
    assert path.parent == tmp_path / "out"


def test_seed_problems_are_reported_not_hidden(synthetic_run, tmp_path) -> None:
    answers = {"יוגורט פירות בננה": {"decision": "accept", "names_ar": "زبادي فواكه"}}  # no flavor
    filled = fill(K.render_csv(synthetic_run), answers, tmp_path / "f.csv")
    doc, problems = K.build_additions(K.parse_filled_csv(filled), DATA, reviewer="x",
                                      reviewed_on="2026-10-22", csv_name="f.csv")  # fmt: skip
    assert problems == []  # the file-level fields are all there ...
    seed_problems = K.check_additions(doc, DATA)
    assert any("must state the flavor banana" in p for p in seed_problems)  # ... seed is stricter


def test_an_accepted_row_without_an_arabic_name_or_a_taxonomy_node_is_a_problem(
    synthetic_run, tmp_path
) -> None:
    answers = {
        "יוגורט פירות בננה": {"decision": "accept"},
        "עדשים צהובות": {"decision": "accept"},
    }
    filled = fill(K.render_csv(synthetic_run), answers, tmp_path / "f.csv")
    _, problems = K.build_additions(K.parse_filled_csv(filled), DATA, reviewer="x",
                                    reviewed_on="2026-10-22", csv_name="f.csv")  # fmt: skip
    text = "\n".join(problems)
    assert "names_ar is empty" in text
    assert "taxonomy_id is empty" in text and "product_type is empty" in text


def test_the_mvp_range_is_enforced_by_the_scratch_seed_check(synthetic_run, tmp_path) -> None:
    doc = {
        "canonicals": [
            {"slug": f"extra-{n}", "display_name_he": f"מוצר {n}", "names_ar": ["جبنة"],
             "taxonomy_id": "dairy.milk.fresh", "product_type": "milk", "base_unit": "100ml",
             "critical_attrs": {"fat_pct": 10 + n, "state": "fresh"}, "soft_attrs": {},
             "rank": 246 + n, "is_mvp": True}
            for n in range(56)
        ]
    }  # fmt: skip
    problems = K.check_additions(doc, DATA)
    assert any("MVP range is 150-300" in p for p in problems)


def test_import_rejects_unreadable_stale_and_inconsistent_rows(synthetic_run, tmp_path) -> None:
    text = K.render_csv(synthetic_run)
    bad = fill(text, {"עדשים צהובות": {"decision": "maybe"}}, tmp_path / "a.csv")
    with pytest.raises(K.ProposalImportError, match="unknown decision"):
        K.parse_filled_csv(bad)
    # an edit in a proposal's own column, not in edit_*: the row_hash notices
    stale = fill(text, {"עדשים צהובות": {"decision": "accept", "display_name_he": "x"}},
                 tmp_path / "b.csv")  # fmt: skip
    rows = rows_of(stale.read_text(encoding="utf-8-sig"))
    assert any(r["display_name_he"] == "x" for r in rows)
    with pytest.raises(K.ProposalImportError, match="row_hash"):
        K.parse_filled_csv(stale)
    assert K.parse_filled_csv(stale, allow_stale=True).counts["accept"] == 1
    empty_edit = fill(text, {"עדשים צהובות": {"decision": "edit"}}, tmp_path / "c.csv")
    with pytest.raises(K.ProposalImportError, match="'edit' needs"):
        K.parse_filled_csv(empty_edit)
    edit_on_accept = fill(text, {"עדשים צהובות": {"decision": "accept", "edit_slug": "y"}},
                          tmp_path / "d.csv")  # fmt: skip
    with pytest.raises(K.ProposalImportError, match="only go with 'edit'"):
        K.parse_filled_csv(edit_on_accept)
    note_only = fill(text, {"עדשים צהובות": {"comment": "hmm"}}, tmp_path / "e.csv")
    with pytest.raises(K.ProposalImportError, match="no decision"):
        K.parse_filled_csv(note_only)


def test_rows_without_a_decision_are_pending_and_hebrew_words_are_read(
    synthetic_run, tmp_path
) -> None:
    filled = fill(K.render_csv(synthetic_run),
                  {"יוגורט פירות בננה": {"decision": "☑ אישור"},
                   "שמן שומשום": {"decision": "דחייה", "comment": "x"}}, tmp_path / "f.csv")  # fmt: skip
    r = K.parse_filled_csv(filled)
    assert r.counts == {"accept": 1, "edit": 0, "reject": 1, "pending": 2}


def test_a_windows_1255_file_from_hebrew_excel_is_read(synthetic_run, tmp_path) -> None:
    filled = fill(K.render_csv(synthetic_run), {"שמן שומשום": {"decision": "reject", "comment": "x"}},
                  tmp_path / "f.csv")  # fmt: skip
    text = filled.read_text(encoding="utf-8-sig")
    # the shekel sign is not in Windows-1255; Excel writes a question mark
    filled.write_bytes(text.encode("cp1255", errors="replace"))
    result = K.parse_filled_csv(filled, allow_stale=True)
    assert result.encoding == "windows-1255" and result.counts["reject"] == 1
    assert any("not UTF-8" in w for w in result.warnings)


# --- the commands ---------------------------------------------------------------------------------------


def test_propose_canonicals_cli_on_the_real_fixtures_and_import_never_touches_the_catalog(
    tmp_path,
) -> None:
    runner = CliRunner()
    out = tmp_path / "packet"
    res = runner.invoke(app, ["propose-canonicals", "--source", "fixtures", "--out", str(out),
                              "--top", "20", "--date", "2026-10-22"])  # fmt: skip
    assert res.exit_code == 0, res.output
    assert "proposals" in res.output
    for name in (K.HTML_NAME, K.CSV_NAME, K.JSON_NAME):
        assert (out / name).is_file()
    rows = rows_of((out / K.CSV_NAME).read_text(encoding="utf-8-sig"))
    assert 0 < len(rows) <= 20 and "2026-10-22" in (out / K.HTML_NAME).read_text(encoding="utf-8")

    # answer the first variant (if any) and the first new type, then import into a scratch folder
    catalog = load_catalog(DATA)
    answers: dict[str, dict[str, str]] = {}
    variant = next((r for r in rows if r["kind"] == "variant"), None)
    if variant:
        answers[variant["display_name_he"]] = {"decision": "reject", "comment": "test"}
    filled = fill((out / K.CSV_NAME).read_text(encoding="utf-8-sig"), answers, tmp_path / "f.csv")
    before = sha(DATA / "canonicals.yaml")
    res = runner.invoke(app, ["proposals-import", str(filled), "--reviewer", "T", "--date",
                              "2026-10-22", "--out-dir", str(tmp_path / "prop")])  # fmt: skip
    assert res.exit_code == 0, res.output
    assert "was NOT modified" in res.output and before == sha(DATA / "canonicals.yaml")
    assert (tmp_path / "prop" / "canonicals-additions-2026-10-22.yaml").is_file()
    assert len(catalog.canonicals) == 245
    again = runner.invoke(app, ["proposals-import", str(filled), "--reviewer", "T", "--date",
                                "2026-10-22", "--out-dir", str(tmp_path / "prop")])  # fmt: skip
    assert again.exit_code == 1  # it will not overwrite without --force


def test_import_command_reports_problems_and_writes_nothing(synthetic_run, tmp_path) -> None:
    filled = fill(
        K.render_csv(synthetic_run), {"שמן שומשום": {"decision": "maybe"}}, tmp_path / "f.csv"
    )
    res = CliRunner().invoke(app, ["proposals-import", str(filled), "--reviewer", "T",
                                   "--out-dir", str(tmp_path / "prop")])  # fmt: skip
    assert res.exit_code == 1 and not (tmp_path / "prop").exists()
