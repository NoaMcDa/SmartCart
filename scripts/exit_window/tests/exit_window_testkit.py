"""Fixture records for the exit window tests: ten D13 chains, one day, chosen outcomes per chain.

Not a test file (no ``test_`` prefix); imported by the three test modules next to it.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import window_record as wr  # noqa: E402

from smartcart_ingest.report import D13_CHAINS  # noqa: E402

# slug -> (D13 name, chain ids); the same ten as scripts/unblock/portal_probe.py PORTALS
# (a test pins that).
SLUGS = {
    "shufersal": "Shufersal",
    "ramilevy": "Rami Levy",
    "victory": "Victory",
    "mega": "Yeinot Bitan and Carrefour",
    "hazihinam": "Hazi Hinam",
    "tivtaam": "Tiv Taam",
    "osherad": "Osher Ad",
    "yohananof": "Yohananof",
    "machsanei_hashuk": "Machsanei Hashuk",
    "king_store": "King Store",
}
IDS = {spec.name: list(spec.chain_ids) for spec in D13_CHAINS}


def file_entry(status: str = "loaded", *, published: str | None = "2026-10-22T05:10+03:00",
               gates: tuple[str, ...] = (), reason: str | None = None,
               error: str | None = None, age: float | None = 3.5, items: int | None = 1200,
               promos: int | None = None) -> dict:  # fmt: skip
    f = wr.empty_file(error, wr.download_error_listed(error))
    if status == wr.STATUS_NOT_DOWNLOADED:
        return f
    f.update(
        listed=True, downloaded=True, file="PriceFull-x.gz", bytes=2048, published_at=published,
        age_hours=age, status=status, loaded=status == "loaded",
        quarantined=status == "quarantined", failed=status == "failed", gates=list(gates),
        reason=reason, schema="v1", stores=1, items=items, prices=items, promos=promos,
        download_seconds=4.2, load_seconds=1.1,
    )  # fmt: skip
    return f


def chain_entry(name: str, mode: str = "loaded", *, hour: int = 5) -> dict:
    """``mode``: loaded, stale (full files quarantined by stale_date), unreachable (no file at
    all), failed (full files failed in the loader), stores_only (Stores loaded, no full file)."""
    pub = f"2026-10-22T{hour:02d}:10+03:00"
    portal = {"http_status": 200, "reachable": "OK", "login": "n/a"}
    stores = file_entry("loaded", published=None, age=None, items=0)
    if mode == "loaded":
        files = {"stores": stores, "price_full": file_entry("loaded", published=pub),
                 "promo_full": file_entry("loaded", published=pub, items=0, promos=40)}  # fmt: skip
    elif mode == "stale":
        stale = dict(published=pub, gates=("stale_date",), reason="stale_date: 40.0 h old",
                     age=40.0)  # fmt: skip
        files = {"stores": stores, "price_full": file_entry("quarantined", **stale),
                 "promo_full": file_entry("quarantined", **stale)}  # fmt: skip
    elif mode == "failed":
        files = {"stores": stores,
                 "price_full": file_entry("failed", published=pub, reason="parse error: boom"),
                 "promo_full": file_entry("failed", published=pub, reason="parse error: boom")}  # fmt: skip
    elif mode == "stores_only":
        none = file_entry(wr.STATUS_NOT_DOWNLOADED, error="no file downloaded")
        files = {"stores": stores, "price_full": none, "promo_full": dict(none)}
    elif mode == "unreachable":
        portal = {"http_status": 0, "reachable": "UNREACHABLE", "login": "n/a"}
        err = "TimeoutError: connection timed out"
        files = {k: file_entry(wr.STATUS_NOT_DOWNLOADED, error=err) for k in wr.KINDS}
    else:
        raise ValueError(mode)
    promos = {"price": 30, "other": 10} if files["promo_full"]["loaded"] else {}
    return wr.finish_chain(name, IDS[name], portal, files,
                           {"physical": 50, "with_coordinates": 40}, promos)  # fmt: skip


def make_record(day: str, modes: dict[str, str] | None = None, *, country: str = "US",
                skip: tuple[str, ...] = ()) -> dict:  # fmt: skip
    """A valid record for ``day``; ``modes`` maps slug to a chain mode (default: all loaded);
    ``skip`` leaves chains out of the record (a run limited to other chains)."""
    modes = modes or {}
    return {
        "schema_version": wr.SCHEMA_VERSION,
        "kind": wr.RECORD_KIND,
        "date": day,
        "label": wr.LABEL,
        "run": {
            "source": "portal", "clock": "real", "event": "schedule", "ref": "main",
            "commit": "abcdef012345", "run_id": "1", "run_url": "https://example.test/runs/1",
            "started_at": f"{day}T06:47:00+00:00", "finished_at": f"{day}T07:10:00+00:00",
            "duration_seconds": 1380.0, "download_seconds": 1200.0, "load_seconds": 60.0,
            "runner_ip_country": country,
        },
        "chains": {
            slug: chain_entry(name, modes.get(slug, "loaded"))
            for slug, name in SLUGS.items()
            if slug not in skip
        },
        "alerts": [],
    }  # fmt: skip


def days(start: str, n: int) -> list[str]:
    first = date.fromisoformat(start)
    return [(first + timedelta(days=i)).isoformat() for i in range(n)]
