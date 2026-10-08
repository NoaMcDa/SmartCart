"""The monthly cap on photo reads: images and estimated dollars, no user id (issue #61, #68).

``ocr_usage(month, provider, images, est_cost_usd)`` holds one row per calendar month (UTC) and
provider. A request is refused with 429 when reading one more image would pass either cap; the
counters grow after a successful read, by the measured estimate. Two requests that pass the check
at the same moment can both be served, so the cap can be exceeded by the number of concurrent
requests; it is a spending brake, not an exact meter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import psycopg
from fastapi import HTTPException

from smartcart_api.ocr import config


@dataclass(frozen=True)
class Usage:
    images: int
    est_cost_usd: Decimal


def month_start(now: datetime | None = None) -> date:
    n = now or datetime.now(UTC)
    return date(n.year, n.month, 1)


def current(conn: psycopg.Connection, month: date | None = None) -> Usage:
    row = conn.execute(
        "SELECT COALESCE(sum(images), 0), COALESCE(sum(est_cost_usd), 0)"
        " FROM ocr_usage WHERE month = %s",
        (month or month_start(),),
    ).fetchone()
    return Usage(int(row[0]), Decimal(row[1]))


def check_cap(conn: psycopg.Connection, expected_usd: Decimal) -> None:
    """Raise 429 when one more image (costing ``expected_usd``) would pass a cap."""
    used = current(conn)
    if used.images + 1 > config.image_cap():
        raise HTTPException(status_code=429, detail="the monthly photo reading limit was reached")
    if used.est_cost_usd + expected_usd > config.usd_cap():
        raise HTTPException(status_code=429, detail="the monthly photo reading budget was reached")


def record(conn: psycopg.Connection, provider: str, est_cost_usd: float | Decimal) -> None:
    conn.execute(
        "INSERT INTO ocr_usage (month, provider, images, est_cost_usd) VALUES (%s, %s, 1, %s)"
        " ON CONFLICT (month, provider) DO UPDATE"
        " SET images = ocr_usage.images + 1,"
        "     est_cost_usd = ocr_usage.est_cost_usd + EXCLUDED.est_cost_usd,"
        "     updated_at = now()",
        (month_start(), provider, Decimal(str(est_cost_usd))),
    )
