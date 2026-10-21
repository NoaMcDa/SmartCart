"""Releasing a wrongly quarantined file by hand (#60, risk 4 of "Design risks left open").

A quarantine is permanent by design. The documented hand release set the file ``failed`` "so the
next listing retries it", which only works for a file the portal lists again: listings are per
calendar day, so a Stores file quarantined two days ago was never retried after the threshold was
fixed. The release now sets ``downloaded`` (the raw file is in the archive), which the next run
picks up whether or not the portal lists it.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from smartcart_ingest import tracking
from tests.fakes import NOW, encode, make_harness, statuses, store

pytestmark = pytest.mark.db

# The statements of docs/ingestion.md, "A quarantine is permanent".
RELEASE_SQL = (
    "UPDATE file_tracking SET status = 'downloaded', reason = 'released by hand'"
    " WHERE id = %s AND status = 'quarantined'"
)


def test_the_documented_release_loads_a_file_that_the_portal_no_longer_lists(db, tmp_path) -> None:
    tight = make_harness(db, tmp_path, stale_stores_max_age_hours=1)
    old = NOW - timedelta(hours=68)
    remote = tight.fetcher.add("stores", encode(stores=[store("1")]), at=old)
    assert tight.scheduler().run_full(["fake"]).chains[0].quarantined == 1
    assert statuses(db)[remote.name] == "quarantined"
    file_id = db.execute("SELECT id FROM file_tracking").fetchone()[0]

    # The threshold is fixed (the default now lets a 68 hour old Stores file through) and the
    # portal no longer lists the file (a new day: it is not in today's listing).
    fixed = make_harness(db, tmp_path)
    fixed.fetcher.clear()
    fixed.set_now(NOW + timedelta(days=2))
    assert db.execute(RELEASE_SQL, (file_id,)).rowcount == 1
    chain = fixed.scheduler().run_full(["fake"]).chains[0]
    assert chain.loaded == 1 and statuses(db)[remote.name] == "loaded"
    assert db.execute("SELECT count(*) FROM stores WHERE chain_id = 'fake'").fetchone()[0] == 1
    assert tracking.get(db, file_id).status == "loaded"


def test_the_release_does_not_touch_a_file_that_is_not_quarantined(db, tmp_path) -> None:
    h = make_harness(db, tmp_path)
    h.fetcher.add("stores", encode(stores=[store("1")]), at=NOW - timedelta(hours=2))
    h.scheduler().run_full(["fake"])
    file_id = db.execute("SELECT id FROM file_tracking").fetchone()[0]
    assert db.execute(RELEASE_SQL, (file_id,)).rowcount == 0
    assert tracking.get(db, file_id).status == "loaded"
