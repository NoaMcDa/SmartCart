"""Price-drop alerts and web push subscriptions (issue #23), under row-level security.

* ``GET/POST /me/alerts``, ``PUT/DELETE /me/alerts/{id}``: an alert is a canonical product, a
  flexibility level, a threshold on the effective unit price (per the canonical's base unit) and
  a radius. ``active = false`` pauses it. The alert takes the neighborhood location from the
  user's profile when it is created or edited (stored rounded to 3 decimals, D11); without a
  consented location the API answers 422, because an alert without a place could never fire.
* Free tier: at most ``API_ALERTS_FREE_LIMIT`` alerts per user (default 10, a config value;
  unlimited alerts are a paid-tier feature, D12). Creating one more answers 403.
* ``POST /me/push-subscriptions``: upsert by endpoint. A browser endpoint belongs to one user: if
  another user had registered the same endpoint (a shared device that switched accounts), that
  row is removed first on the service connection. ``DELETE /me/push-subscriptions`` with the
  endpoint unsubscribes.
* Evaluation and delivery: ``smartcart_api.alerts_job`` (``smartcart-api alerts-run``).
"""

from __future__ import annotations

import os
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from psycopg.rows import dict_row

from smartcart_api import schemas
from smartcart_api.auth import User, current_user, user_conn
from smartcart_api.db import get_conn
from smartcart_api.routes.me_delete import as_user

router = APIRouter(prefix="/me", tags=["alerts"])
UserConn = Annotated[tuple[User, psycopg.Connection], Depends(user_conn, scope="function")]

_COLS = (
    "id, canonical_id, threshold_unit_price, flex_level, radius_m, active, last_fired_at,"
    " created_at"
)


def free_limit() -> int:
    try:
        return max(0, int(os.environ.get("API_ALERTS_FREE_LIMIT", "10")))
    except ValueError:
        return 10


def _location(conn: psycopg.Connection, user: User) -> tuple:
    row = conn.execute(
        "SELECT neighborhood_lat, neighborhood_lon FROM profiles"
        " WHERE user_id = %s AND consent_location",
        (user.id,),
    ).fetchone()
    if row is None or row[0] is None or row[1] is None:
        raise HTTPException(
            status_code=422,
            detail="an alert needs the neighborhood location in the profile (with consent_location)",
        )
    return row


def _check_canonical(conn: psycopg.Connection, canonical_id: int) -> None:
    if (
        conn.execute("SELECT 1 FROM canonical_products WHERE id = %s", (canonical_id,)).fetchone()
        is None
    ):
        raise HTTPException(status_code=404, detail="canonical product not found")


@router.get("/alerts", response_model=list[schemas.PriceAlert])
def list_alerts(uc: UserConn) -> list[schemas.PriceAlert]:
    user, conn = uc
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            f"SELECT {_COLS} FROM price_alerts WHERE user_id = %s ORDER BY created_at, id",
            (user.id,),
        ).fetchall()
    return [schemas.PriceAlert(**r) for r in rows]


@router.post("/alerts", response_model=schemas.PriceAlert, status_code=201)
def create_alert(body: schemas.PriceAlertIn, uc: UserConn) -> schemas.PriceAlert:
    user, conn = uc
    _check_canonical(conn, body.canonical_id)
    count = conn.execute(
        "SELECT count(*) FROM price_alerts WHERE user_id = %s", (user.id,)
    ).fetchone()[0]
    if count >= free_limit():
        raise HTTPException(status_code=403, detail=f"the free tier allows {free_limit()} alerts")
    lat, lon = _location(conn, user)
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            "INSERT INTO price_alerts (user_id, canonical_id, threshold_unit_price, flex_level,"
            " radius_m, active, neighborhood_lat, neighborhood_lon)"
            " VALUES (%s, %s, %s, %s, %s, %s, round(%s::numeric, 3), round(%s::numeric, 3))"
            f" RETURNING {_COLS}",
            (
                user.id,
                body.canonical_id,
                body.threshold_unit_price,
                body.flex_level,
                body.radius_m,
                body.active,
                lat,
                lon,
            ),
        ).fetchone()
    return schemas.PriceAlert(**row)


@router.put("/alerts/{alert_id}", response_model=schemas.PriceAlert)
def update_alert(alert_id: int, body: schemas.PriceAlertIn, uc: UserConn) -> schemas.PriceAlert:
    """Edit or pause (``active = false``) an alert. Editing re-arms it (``last_fired_at`` reset)
    when the threshold, level or product changes."""
    user, conn = uc
    _check_canonical(conn, body.canonical_id)
    lat, lon = _location(conn, user)
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            "UPDATE price_alerts SET canonical_id = %(cid)s, threshold_unit_price = %(th)s,"
            " flex_level = %(flex)s, radius_m = %(radius)s, active = %(active)s,"
            " neighborhood_lat = round(%(lat)s::numeric, 3), neighborhood_lon = round(%(lon)s::numeric, 3),"
            " last_fired_at = CASE WHEN canonical_id = %(cid)s AND threshold_unit_price = %(th)s"
            "   AND flex_level = %(flex)s THEN last_fired_at END"
            f" WHERE id = %(id)s AND user_id = %(uid)s RETURNING {_COLS}",
            {
                "cid": body.canonical_id,
                "th": body.threshold_unit_price,
                "flex": body.flex_level,
                "radius": body.radius_m,
                "active": body.active,
                "lat": lat,
                "lon": lon,
                "id": alert_id,
                "uid": user.id,
            },
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return schemas.PriceAlert(**row)


@router.delete("/alerts/{alert_id}", status_code=204)
def delete_alert(alert_id: int, uc: UserConn) -> Response:
    user, conn = uc
    deleted = conn.execute(
        "DELETE FROM price_alerts WHERE id = %s AND user_id = %s", (alert_id, user.id)
    ).rowcount
    if not deleted:
        raise HTTPException(status_code=404, detail="alert not found")
    return Response(status_code=204)


@router.post("/push-subscriptions", response_model=schemas.Ack, status_code=201)
def add_push_subscription(
    body: schemas.PushSubscriptionIn,
    user: Annotated[User, Depends(current_user)],
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
) -> schemas.Ack:
    # Service connection: the endpoint may be registered to another account on this device.
    conn.execute(
        "DELETE FROM push_subscriptions WHERE endpoint = %s AND user_id <> %s",
        (body.endpoint, user.id),
    )
    with as_user(conn, user):
        sub_id = conn.execute(
            "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, user_agent)"
            " VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (endpoint) DO UPDATE SET p256dh = EXCLUDED.p256dh,"
            "   auth = EXCLUDED.auth, user_agent = EXCLUDED.user_agent"
            " RETURNING id",
            (user.id, body.endpoint, body.p256dh, body.auth, body.user_agent),
        ).fetchone()[0]
    return schemas.Ack(ok=True, id=sub_id)


@router.delete("/push-subscriptions", status_code=204)
def delete_push_subscription(
    uc: UserConn, endpoint: Annotated[str, Query(max_length=2000)]
) -> Response:
    """Unsubscribe this device (the browser's push endpoint)."""
    user, conn = uc
    conn.execute(
        "DELETE FROM push_subscriptions WHERE endpoint = %s AND user_id = %s", (endpoint, user.id)
    )
    return Response(status_code=204)
