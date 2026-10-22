"""Tests for the exit window record schema (issue #60). No network, no database.

uv run pytest scripts/exit_window/tests -q
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "unblock"))

import exit_window_testkit as kit  # noqa: E402
import portal_probe  # noqa: E402
import window_record as wr  # noqa: E402


def test_a_generated_record_follows_the_schema() -> None:
    rec = kit.make_record("2026-10-22")
    assert wr.validate_record(rec) is rec
    assert len(rec["chains"]) == 10
    assert all(c["full_loaded"] and c["failure"] is None for c in rec["chains"].values())


def test_the_ten_slugs_are_the_probe_portals_and_the_d13_names() -> None:
    assert kit.SLUGS == {p.slug: p.name for p in portal_probe.PORTALS}


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r.update(schema_version=2), "schema_version"),
        (lambda r: r.update(kind="other"), "kind"),
        (lambda r: r.update(date="2026-02-30"), "calendar date"),
        (lambda r: r.update(date="22-10-2026"), "YYYY-MM-DD"),
        (lambda r: r.update(chains={}), "non-empty"),
        (lambda r: r.update(chains={"Bad Slug": {}}), "bad slug"),
        (lambda r: r["run"].update(clock="mock"), "clock"),
        (lambda r: r["run"].update(runner_ip_country=None), "runner_ip_country"),
        (lambda r: r["run"].update(duration_seconds=-1), "duration_seconds"),
        (lambda r: r["run"].update(started_at="yesterday"), "started_at"),
        (lambda r: r.update(alerts=[{"kind": "x"}]), "alert"),
        (lambda r: r["chains"]["mega"]["files"].pop("promo_full"), "files needs"),
        (lambda r: r["chains"]["mega"]["files"]["stores"].update(loaded=False), "loaded disagrees"),
        (lambda r: r["chains"]["mega"]["files"]["stores"].update(status="weird"), "status"),
        (lambda r: r["chains"]["mega"]["files"]["stores"].update(items=True), "items"),
        (
            lambda r: r["chains"]["mega"]["files"]["stores"].update(published_at="noon"),
            "published_at",
        ),
        (lambda r: r["chains"]["mega"].update(full_loaded=False), "full_loaded"),
        (lambda r: r["chains"]["mega"].update(failure="x"), "failure"),
        (lambda r: r["chains"]["mega"].update(downloaded=1), "downloaded disagrees"),
        (lambda r: r["chains"]["mega"]["stores"].update(physical=-1), "stores.physical"),
        (lambda r: r["chains"]["mega"].update(promos_by_reward={"price": "x"}), "promos_by_reward"),
        (lambda r: r["chains"]["mega"]["portal"].update(http_status="200"), "http_status"),
    ],
)
def test_the_schema_rejects(mutate, message: str) -> None:  # noqa: ANN001
    rec = copy.deepcopy(kit.make_record("2026-10-22"))
    mutate(rec)
    with pytest.raises(wr.RecordError, match=message):
        wr.validate_record(rec)


def test_a_record_that_is_not_an_object_is_rejected() -> None:
    for bad in (None, [], "x", 3):
        with pytest.raises(wr.RecordError):
            wr.validate_record(bad)


def test_a_not_downloaded_file_cannot_name_a_file() -> None:
    rec = kit.make_record("2026-10-22", {"victory": "unreachable"})
    rec["chains"]["victory"]["files"]["stores"]["file"] = "Stores.gz"
    with pytest.raises(wr.RecordError, match="no file name"):
        wr.validate_record(rec)


def test_counters_and_failure_for_each_outcome() -> None:
    rec = kit.make_record(
        "2026-10-22",
        {
            "shufersal": "stale",
            "victory": "unreachable",
            "tivtaam": "failed",
            "king_store": "stores_only",
        },  # fmt: skip
    )
    wr.validate_record(rec)
    chains = rec["chains"]

    ok = chains["osherad"]
    assert (ok["listed"], ok["downloaded"], ok["loaded"], ok["quarantined"], ok["failed"]) == (
        3, 3, 3, 0, 0,
    )  # fmt: skip

    stale = chains["shufersal"]
    assert (stale["downloaded"], stale["loaded"], stale["quarantined"]) == (3, 1, 2)
    assert not stale["full_loaded"]  # the Stores file loaded, but it is not a full file
    assert "price_full: quarantined (stale_date)" in stale["failure"]
    assert "promo_full: quarantined (stale_date)" in stale["failure"]

    gone = chains["victory"]
    assert (gone["listed"], gone["downloaded"], gone["loaded"]) == (0, 0, 0)
    assert gone["failure"].startswith("portal unreachable from the runner (http 0)")
    assert "TimeoutError" in gone["failure"]
    assert len(gone["download_errors"]) == 3

    failed = chains["tivtaam"]
    assert failed["failed"] == 2 and "failed (parse error: boom)" in failed["failure"]

    stores_only = chains["king_store"]
    assert stores_only["loaded"] == 1 and not stores_only["full_loaded"]
    # nothing was listed for the full kinds, which the record states as False, not unknown
    assert stores_only["files"]["price_full"]["listed"] is False
    assert "no file downloaded" in stores_only["failure"]
    assert not stores_only["failure"].startswith("portal")  # the portal answered


def test_a_loaded_promo_file_alone_is_a_successful_full_load() -> None:
    # The criterion's definition (smartcart_ingest.report): price_full OR promo_full loaded.
    files = {
        "stores": kit.file_entry("loaded"),
        "price_full": kit.file_entry("quarantined", gates=("zero_price",)),
        "promo_full": kit.file_entry("loaded", promos=5),
    }
    chain = wr.finish_chain("Osher Ad", ["7290103152017"], {"http_status": 200, "reachable": "OK",
                            "login": "ok"}, files, {"physical": 1, "with_coordinates": 0}, {})  # fmt: skip
    assert chain["full_loaded"] and chain["failure"] is None


def test_download_error_listed_distinguishes_nothing_listed_from_unknown() -> None:
    assert wr.download_error_listed("no file downloaded") is False
    assert wr.download_error_listed("no file downloaded for store 12") is False
    assert wr.download_error_listed("timed out after 240s") is None
    assert wr.download_error_listed(None) is None


def test_empty_file_is_valid_inside_a_chain_and_has_no_file() -> None:
    f = wr.empty_file("boom")
    assert f["status"] == wr.STATUS_NOT_DOWNLOADED and not f["downloaded"] and f["file"] is None
    assert f["download_error"] == "boom"


def test_the_day_summary_is_labelled_and_counts_chains() -> None:
    rec = kit.make_record("2026-10-22", {"victory": "unreachable"}, country="DE")
    text = wr.render_day_summary(rec)
    assert "runner rehearsal, not the VPS window" in text
    assert "Runner IP country: **DE**" in text
    assert "9 of 10 chains had a loaded full file." in text
    assert "| Victory | UNREACHABLE (0) | no file | no file | no file | NO |" in text
