"""file_tracking state machine (issue #37)."""

from __future__ import annotations

import hashlib
from datetime import date, datetime

import pytest

from smartcart_ingest import tracking
from smartcart_ingest.models import RawFile
from tests.fakes import ISRAEL, NOW


def _raw(n: int, kind="price_full", store="1", at: datetime = NOW, chain="fake") -> RawFile:
    return RawFile(
        chain_id=chain,
        store_code=None if kind == "stores" else store,
        kind=kind,
        published_at=at,
        sha256=hashlib.sha256(f"file-{n}".encode()).hexdigest(),
        path=f"raw/{chain}/{n}",
    )


# --- no database -------------------------------------------------------------------------------


def test_full_kind_for_maps_each_delta_to_its_full() -> None:
    assert tracking.full_kind_for("price") == "price_full"
    assert tracking.full_kind_for("promo") == "promo_full"
    with pytest.raises(ValueError):
        tracking.full_kind_for("price_full")


def test_israel_day_uses_israel_time() -> None:
    # 21:30 UTC on Oct 6 is 00:30 on Oct 7 in Israel (UTC+3 in October).
    assert tracking.israel_day(datetime.fromisoformat("2026-10-06T21:30:00+00:00")) == date(
        2026, 10, 7
    )
    assert tracking.israel_day(datetime.fromisoformat("2026-10-06T20:30:00+00:00")) == date(
        2026, 10, 6
    )


def test_strip_retry() -> None:
    assert tracking.strip_retry(None) == ""
    assert tracking.strip_retry("retry after: retry after: parse failed: x") == "parse failed: x"


# --- database ----------------------------------------------------------------------------------


@pytest.mark.db
def test_register_is_keyed_by_hash(db) -> None:
    row, created = tracking.register(db, _raw(1))
    assert created and row.status == "seen" and row.kind == "price_full"
    again, created_again = tracking.register(db, _raw(1))
    assert not created_again and again.id == row.id
    assert db.execute("SELECT count(*) FROM file_tracking").fetchone()[0] >= 1


@pytest.mark.db
def test_happy_path_transitions(db) -> None:
    row, _ = tracking.register(db, _raw(2))
    row = tracking.mark_downloaded(db, row.id, "raw/fake/2")
    assert row.status == "downloaded"
    row = tracking.mark_loading(db, row.id)
    row = tracking.mark_loaded(db, row.id, item_count=42, schema_version="v1")
    assert (row.status, row.reason, row.schema_version) == ("loaded", "items=42", "v1")


@pytest.mark.db
@pytest.mark.parametrize(
    ("path", "bad"),
    [
        ([], "loaded"),  # seen -> loaded skips the download and the load
        ([], "quarantined"),
        (["downloaded"], "loaded"),  # must pass through loading
        (["downloaded", "loading", "loaded"], "failed"),  # loaded is terminal
        (["downloaded", "loading", "loaded"], "downloaded"),
    ],
)
def test_guarded_transitions_refuse_illegal_moves(db, path, bad) -> None:
    row, _ = tracking.register(db, _raw(3))
    for status in path:
        row = tracking.transition(
            db, row.id, status, path="raw/x" if status == "downloaded" else None
        )
    with pytest.raises(tracking.InvalidTransition) as exc:
        tracking.transition(db, row.id, bad)
    assert exc.value.current == row.status
    assert tracking.get(db, row.id).status == row.status


@pytest.mark.db
def test_quarantine_writes_one_event_per_gate(db) -> None:
    row, _ = tracking.register(db, _raw(4))
    tracking.mark_downloaded(db, row.id, "raw/fake/4")
    tracking.mark_loading(db, row.id)
    q = tracking.record_quarantine(db, row.id, [("zero_price", "1 price"), ("stale_date", "old")])
    assert q.status == "quarantined"
    assert "zero_price" in q.reason and "stale_date" in q.reason
    gates = db.execute(
        "SELECT gate FROM quarantine_events WHERE file_id = %s ORDER BY gate", (row.id,)
    ).fetchall()
    assert [g[0] for g in gates] == ["stale_date", "zero_price"]
    with pytest.raises(tracking.InvalidTransition):
        tracking.mark_loading(db, row.id)  # quarantined is terminal


def _loaded(db, n, **kw) -> tracking.TrackedFile:
    row, _ = tracking.register(db, _raw(n, **kw))
    tracking.mark_downloaded(db, row.id, f"raw/fake/{n}")
    tracking.mark_loading(db, row.id)
    return tracking.mark_loaded(db, row.id, item_count=10 * n)


@pytest.mark.db
def test_is_full_loaded_matches_store_kind_and_israel_day(db) -> None:
    day = date(2026, 10, 6)
    assert not tracking.is_full_loaded(db, "fake", "1", day, "price_full")
    # Published 23:30 Israel on Oct 6 (20:30 UTC) counts for Oct 6, not Oct 7.
    _loaded(db, 5, at=datetime(2026, 10, 6, 23, 30, tzinfo=ISRAEL))
    assert tracking.is_full_loaded(db, "fake", "1", day, "price_full")
    assert not tracking.is_full_loaded(db, "fake", "1", date(2026, 10, 7), "price_full")
    assert not tracking.is_full_loaded(db, "fake", "2", day, "price_full")
    assert not tracking.is_full_loaded(db, "fake", "1", day, "promo_full")
    assert not tracking.is_full_loaded(db, "other", "1", day, "price_full")


@pytest.mark.db
def test_is_full_loaded_ignores_files_not_loaded(db) -> None:
    row, _ = tracking.register(db, _raw(6))
    tracking.mark_downloaded(db, row.id, "raw/fake/6")
    assert not tracking.is_full_loaded(db, "fake", "1", NOW.date(), "price_full")


@pytest.mark.db
def test_previous_full_count_reads_the_latest_earlier_loaded_file(db) -> None:
    _loaded(db, 1, at=datetime(2026, 10, 4, 6, tzinfo=ISRAEL))
    _loaded(db, 2, at=datetime(2026, 10, 5, 6, tzinfo=ISRAEL))
    later = _loaded(db, 3, at=datetime(2026, 10, 6, 6, tzinfo=ISRAEL))
    before = datetime(2026, 10, 6, 6, tzinfo=ISRAEL)
    assert tracking.previous_full_count(db, "fake", "1", "price_full", before) == 20
    assert (
        tracking.previous_full_count(
            db, "fake", "1", "price_full", datetime(2026, 10, 7, tzinfo=ISRAEL), later.id
        )
        == 20
    )
    assert tracking.previous_full_count(db, "fake", "9", "price_full", before) is None


@pytest.mark.db
def test_recover_interrupted_fails_files_left_loading(db) -> None:
    row, _ = tracking.register(db, _raw(7))
    tracking.mark_downloaded(db, row.id, "raw/fake/7")
    tracking.mark_loading(db, row.id)
    assert tracking.recover_interrupted(db, "fake") == 1
    after = tracking.get(db, row.id)
    assert after.status == "failed" and "interrupted" in after.reason
    # A failed file can be retried.
    assert tracking.mark_downloaded(db, row.id, "raw/fake/7").status == "downloaded"


@pytest.mark.db
def test_open_files_and_counts(db) -> None:
    a, _ = tracking.register(db, _raw(8, kind="price"))
    tracking.mark_downloaded(db, a.id, "raw/fake/8")
    b, _ = tracking.register(db, _raw(9, kind="promo"))
    tracking.mark_downloaded(db, b.id, "raw/fake/9")
    tracking.mark_held(db, b.id, "waiting")
    _loaded(db, 10)
    assert {f.id for f in tracking.open_files(db, "fake")} == {a.id, b.id}
    counts = {(c, s): n for c, s, n in tracking.status_counts(db)}
    assert counts[("fake", "downloaded")] == 1
    assert counts[("fake", "held")] == 1
    assert counts[("fake", "loaded")] == 1
