"""The probe's per-chain schema counter (#57; no network, no database).

uv run pytest scripts/unblock/tests -q

The counter exists so that the first real file in the authority's new reporting model is noticed
the day it appears: ``SCHEMA`` log lines per chain, one ``SCHEMA_TOTAL`` line, and a report
table that says which files were not ``v1`` and why.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import portal_probe  # noqa: E402

FIXTURES = REPO / "services" / "ingest" / "tests" / "fixtures"


def _entry(slug: str, path: Path) -> dict:
    from smartcart_ingest.adapters.fetch_fixtures import adapters_by_slug

    adapter = adapters_by_slug()[slug]()
    return {"file": path.name, "schema_check": adapter.inspect_schema(path.read_bytes())}


def _results(slug: str, folder: Path, prefixes: dict[str, str]) -> dict:
    """``{kind: entry}`` for the file of ``folder`` whose name starts with each prefix."""
    return {
        kind: _entry(slug, next(folder.glob(prefix + "*"))) for kind, prefix in prefixes.items()
    }


REAL = {"stores": "Stores", "price_full": "PriceFull", "promo_full": "PromoFull"}


def test_real_files_count_as_v1_for_every_chain() -> None:
    for slug_dir in sorted(FIXTURES.glob("*/real")):
        slug = slug_dir.parent.name
        counts = portal_probe.schema_counts(_results(slug, slug_dir, REAL))
        assert counts["files"] == 3 and counts["v1"] == 3, slug
        assert (counts["v2"], counts["unknown"], counts["unreadable"]) == (0, 0, 0), slug
        assert counts["not_v1"] == [] and counts["declared_versions"] == {}, slug
        assert counts["by_kind"] == {"stores": "v1", "price_full": "v1", "promo_full": "v1"}
        assert "chainid" in counts["header_fields"]


def test_synthetic_v2_unknown_and_corrupt_files_are_counted_separately() -> None:
    folder = FIXTURES / "shufersal"
    results = {
        "stores": _entry("shufersal", next(folder.glob("Stores*"))),
        "v2": _entry("shufersal", folder / "PriceFull7290027600007-001-202610070300.gz"),
        "unknown": _entry("shufersal", folder / "PriceFull7290027600007-001-202610080300.gz"),
        "corrupt": _entry("shufersal", folder / "PriceFull7290027600007-001-202610090300.gz"),
    }
    counts = portal_probe.schema_counts(results)
    assert (counts["files"], counts["v1"], counts["v2"]) == (4, 1, 1)
    assert (counts["unknown"], counts["unreadable"]) == (1, 1)
    assert counts["declared_versions"] == {"dllverno": ["8.0.1.3"], "schemaversion": ["2.0", "3.1"]}
    bad = {n["kind"]: n for n in counts["not_v1"]}
    assert set(bad) == {"v2", "unknown", "corrupt"}
    assert "SchemaVersion='3.1'" in bad["unknown"]["reason"]
    assert bad["v2"]["reason"] == "SchemaVersion=2.0"


def test_schema_line_is_one_json_line_per_chain() -> None:
    folder = FIXTURES / "ramilevy" / "real"
    counts = portal_probe.schema_counts(_results("ramilevy", folder, REAL))
    line = portal_probe.schema_line("ramilevy", counts)
    assert line.startswith("SCHEMA {") and "\n" not in line
    payload = json.loads(line.removeprefix("SCHEMA "))
    assert payload == {"chain": "ramilevy", "files": 3, "v1": 3, "v2": 0, "unknown": 0,
                       "unreadable": 0}  # fmt: skip


def test_total_line_names_the_chains_that_are_not_all_v1() -> None:
    per_chain = {
        "a": {"files": 3, "v1": 3, "v2": 0, "unknown": 0, "unreadable": 0},
        "b": {"files": 3, "v1": 2, "v2": 1, "unknown": 0, "unreadable": 0},
        "c": {"files": 2, "v1": 0, "v2": 0, "unknown": 1, "unreadable": 1},
    }
    payload = json.loads(portal_probe.schema_total_line(per_chain).removeprefix("SCHEMA_TOTAL "))
    assert payload == {"files": 8, "v1": 5, "v2": 1, "unknown": 1, "unreadable": 1,
                       "chains_not_all_v1": ["b", "c"]}  # fmt: skip


def test_report_table_flags_a_file_that_is_not_v1() -> None:
    folder = FIXTURES / "shufersal"
    results = {
        "price_full": _entry("shufersal", folder / "PriceFull7290027600007-001-202610080300.gz"),
    }
    gate = {"files": {"shufersal": {}}, "alerts": [],
            "schema_counts": {"shufersal": portal_probe.schema_counts(results)}}  # fmt: skip
    md = portal_probe.render(None, gate, ["shufersal"])
    assert "### Files per detected schema (#57)" in md
    assert "**A file that is not `v1` appeared for: Shufersal.**" in md
    assert "| Shufersal | 1 | 0 | 0 | 1 | 0 |" in md
    assert "price_full: unknown" in md and "SchemaVersion=" in md


def test_report_table_is_quiet_when_everything_is_v1() -> None:
    folder = FIXTURES / "osherad" / "real"
    gate = {"files": {"osherad": {}}, "alerts": [],
            "schema_counts": {"osherad": portal_probe.schema_counts(
                _results("osherad", folder, REAL))}}  # fmt: skip
    md = portal_probe.render(None, gate, ["osherad"])
    assert "| Osher Ad | 3 | 3 | 0 | 0 | 0 | - | - |" in md
    assert "appeared for" not in md


def test_report_without_counts_is_unchanged() -> None:
    """A gate result written before the counter existed still renders."""
    md = portal_probe.render(None, {"files": {}, "alerts": []}, ["shufersal"])
    assert "Files per detected schema" not in md


def test_a_corrupt_download_is_listed_but_not_flagged_as_a_new_model() -> None:
    folder = FIXTURES / "shufersal"
    results = {
        "price_full": _entry("shufersal", folder / "PriceFull7290027600007-001-202610090300.gz"),
    }
    gate = {
        "files": {"shufersal": {}},
        "alerts": [],
        "schema_counts": {"shufersal": portal_probe.schema_counts(results)},
    }
    md = portal_probe.render(None, gate, ["shufersal"])
    assert "price_full: unreadable" in md and "appeared for" not in md
