"""Price-drop alert evaluation (issue #23): ``smartcart-api alerts-run``, after each precompute.

For every active alert with a location:

1. Candidates: ``effective_prices`` rows of the alert's canonical at its flexibility level (so an
   item outside that level never qualifies), at physical stores within ``radius_m`` of the
   alert's neighborhood (PostGIS ``ST_DWithin`` on ``stores.geog``).
2. Clubs: each row goes through ``basket.gate_club`` with the clubs in the user's profile, the
   same rule as /compare: a club-only promo counts only for a member of that club.
3. The alert fires on the lowest effective unit price at or below ``threshold_unit_price``.
4. De-duplication: an alert fires at most once per 24 hours (``last_fired_at``), and never twice
   for the same drop: when its last delivery was the same item at the same store, it fires again
   only if the price went lower than what was delivered.
5. Delivery: an ``alert_deliveries`` row (channel ``push`` when a sender and at least one
   subscription exist, else ``log``), ``last_fired_at`` set, and one web push per subscription of
   the user. Subscriptions answered with 404 or 410 are deleted (permission revoked, app
   removed). Other failures are counted and left for the next run.

The notification carries the product, the store, the price with its update time, "המחיר הקובע
הוא בקופה" and a deep link to the product page (``/product/{canonical_id}``).

The job runs on the service connection: it reads every user's alerts, so the role must bypass
row-level security (the Supabase ``postgres`` or ``service_role`` connection). The caller commits.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import structlog

from smartcart_api.basket import _Choice, gate_club, money
from smartcart_api.push import GONE, PushSender, PushTarget

log = structlog.get_logger("smartcart_api.alerts_job")

DEDUP_WINDOW = timedelta(hours=24)
DISCLAIMER_HE = "המחיר הקובע הוא בקופה."
UNIT_HE = {"100g": "ל-100 גרם", "100ml": 'ל-100 מ"ל', "unit": "ליחידה", "kg": 'לק"ג'}


@dataclass
class AlertRunResult:
    alerts_checked: int = 0
    fired: int = 0
    deduplicated: int = 0
    pushes_sent: int = 0
    push_failures: int = 0
    subscriptions_removed: int = 0
    seconds: float = 0.0

    def metrics(self) -> dict:
        return {**asdict(self), "seconds": round(self.seconds, 3)}


@dataclass(frozen=True)
class Hit:
    store_id: int
    store_name: str
    chain_name: str
    item_id: int
    item_name: str
    unit_price: Decimal
    uom: str
    price_valid_from: datetime
    club_name: str | None


_ALERTS_SQL = """
SELECT a.id, a.user_id, a.canonical_id, a.threshold_unit_price, a.flex_level, a.radius_m,
       a.neighborhood_lat::float8, a.neighborhood_lon::float8, a.last_fired_at,
       COALESCE(pr.clubs, '{}'), cp.display_name_he, cp.names_ar[1]
FROM price_alerts AS a
JOIN canonical_products AS cp ON cp.id = a.canonical_id
LEFT JOIN profiles AS pr ON pr.user_id = a.user_id
WHERE a.active AND a.neighborhood_lat IS NOT NULL AND a.neighborhood_lon IS NOT NULL
ORDER BY a.id
"""

_CANDIDATES_SQL = """
SELECT ep.store_id, ep.item_id, ep.shelf_price, COALESCE(ep.effective_price, ep.shelf_price),
       ep.effective_unit_price, ep.uom, ep.promo_id, ep.promo_min_qty, ep.club_required,
       ep.club_name, ep.price_valid_from, ep.is_estimated, ep.noclub,
       s.name, c.name, c.club_names, i.raw_name
FROM effective_prices AS ep
JOIN stores AS s ON s.id = ep.store_id
JOIN chains AS c ON c.id = s.chain_id
JOIN items AS i ON i.id = ep.item_id
WHERE ep.canonical_id = %(cid)s AND ep.flex_level = %(flex)s AND s.channel = 'physical'
  AND ST_DWithin(s.geog, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography, %(radius)s)
"""


def best_hit(
    conn: psycopg.Connection, canonical_id: int, flex: str, lon: float, lat: float,
    radius_m: int, clubs: list[str], threshold: Decimal,
) -> Hit | None:
    """The lowest effective unit price at or below ``threshold`` for this user, or None."""
    best: Hit | None = None
    for r in conn.execute(
        _CANDIDATES_SQL,
        {"cid": canonical_id, "flex": flex, "lon": lon, "lat": lat, "radius": radius_m},
    ).fetchall():
        c = _Choice(r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11])
        pick, _offer = gate_club(c, r[12], clubs, (r[14], list(r[15] or [])))
        if pick is None or pick.effective_unit_price > threshold:
            continue
        if best is None or (pick.effective_unit_price, r[0]) < (best.unit_price, best.store_id):
            best = Hit(
                store_id=r[0], store_name=r[13], chain_name=r[14], item_id=pick.item_id,
                item_name=r[16] if pick.item_id == r[1] else _item_name(conn, pick.item_id),
                unit_price=pick.effective_unit_price, uom=pick.uom,
                price_valid_from=pick.price_valid_from,
                club_name=pick.club_name if pick.club_required else None,
            )
    return best


def _item_name(conn: psycopg.Connection, item_id: int) -> str:
    row = conn.execute("SELECT raw_name FROM items WHERE id = %s", (item_id,)).fetchone()
    return row[0] if row else ""


def payload(
    alert_id: int, canonical_id: int, product: str, hit: Hit, product_ar: str | None = None
) -> dict:
    price = f"₪ {money(hit.unit_price)}"
    updated = hit.price_valid_from.astimezone(UTC).strftime("%d.%m.%Y %H:%M")
    club = f" (מבצע מועדון: {hit.club_name})" if hit.club_name else ""
    return {
        "title": f"ירידת מחיר: {product}",
        "body": (
            f"{hit.item_name} ב{hit.chain_name} {hit.store_name}: {price} "
            f"{UNIT_HE.get(hit.uom, hit.uom)}{club}. עודכן {updated} UTC. {DISCLAIMER_HE}"
        ),
        "url": f"/product/{canonical_id}",
        "tag": f"alert-{alert_id}",
        "alert_id": alert_id,
        "canonical_id": canonical_id,
        "product_ar": product_ar,
        "store_id": hit.store_id,
        "item_id": hit.item_id,
        "unit_price": str(hit.unit_price),
        "uom": hit.uom,
        "price_valid_from": hit.price_valid_from.isoformat(),
        "disclaimer_he": DISCLAIMER_HE,
    }


def evaluate_alerts(
    conn: psycopg.Connection, sender: PushSender | None, now: datetime | None = None
) -> AlertRunResult:
    """Evaluate every active alert once; see the module docstring."""
    now = now or datetime.now(UTC)
    started = time.monotonic()
    result = AlertRunResult()
    for (alert_id, user_id, cid, threshold, flex, radius, lat, lon, last_fired, clubs,
         product, product_ar) in conn.execute(_ALERTS_SQL).fetchall():
        result.alerts_checked += 1
        if last_fired is not None and now - last_fired < DEDUP_WINDOW:
            result.deduplicated += 1
            continue
        hit = best_hit(conn, cid, flex, lon, lat, radius, list(clubs), threshold)
        if hit is None:
            continue
        last = conn.execute(
            "SELECT store_id, item_id, unit_price FROM alert_deliveries WHERE alert_id = %s"
            " ORDER BY delivered_at DESC, id DESC LIMIT 1",
            (alert_id,),
        ).fetchone()
        if last is not None and (last[0], last[1]) == (hit.store_id, hit.item_id) and hit.unit_price >= last[2]:
            result.deduplicated += 1  # the drop that was already notified
            continue
        targets = [
            PushTarget(*r)
            for r in conn.execute(
                "SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = %s"
                " ORDER BY id",
                (user_id,),
            ).fetchall()
        ]
        channel = "push" if sender is not None and targets else "log"
        conn.execute(
            "INSERT INTO alert_deliveries (alert_id, store_id, item_id, unit_price, channel,"
            " delivered_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (alert_id, hit.store_id, hit.item_id, hit.unit_price, channel, now),
        )
        conn.execute("UPDATE price_alerts SET last_fired_at = %s WHERE id = %s", (now, alert_id))
        result.fired += 1
        if channel != "push":
            continue
        body = payload(alert_id, cid, product, hit, product_ar)
        for t in targets:
            status = sender(t, body)
            if 200 <= status < 300:
                result.pushes_sent += 1
            elif status in GONE:
                conn.execute("DELETE FROM push_subscriptions WHERE id = %s", (t.id,))
                result.subscriptions_removed += 1
            else:
                result.push_failures += 1
    result.seconds = time.monotonic() - started
    log.info("alerts evaluated", **result.metrics())
    return result
