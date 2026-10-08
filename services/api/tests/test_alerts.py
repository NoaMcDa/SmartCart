"""Price-drop alerts (issue #23): CRUD under RLS, push subscriptions, the evaluation job.

Eggs (base unit "unit", 12 per pack): t-c1 12.90 = 1.075 per egg, with a club deal 9.90 = 0.825
for members of chain one's club; t-c2 13.50 = 1.125. Milk 3% near home (1 km): Tnuva 0.69 per
100 ml (exact), the private label 0.62 (any brand).
"""

from __future__ import annotations

import json
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from api_world import ORIGIN, World, add_price, make_token
from typer.testing import CliRunner

from smartcart_api import cli
from smartcart_api.alerts_job import evaluate_alerts
from smartcart_api.precompute import precompute_effective_prices
from smartcart_api.push import PushTarget, WebPushSender

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
D = Decimal


def h(user_id) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


class FakeSender:
    def __init__(self, statuses: dict[str, int] | None = None) -> None:
        self.statuses = statuses or {}
        self.sent: list[tuple[PushTarget, dict]] = []

    def __call__(self, target: PushTarget, payload: dict) -> int:
        self.sent.append((target, payload))
        return self.statuses.get(target.endpoint, 201)


@pytest.fixture
def w(db, world: World) -> World:
    precompute_effective_prices(db, chains=world.chains)
    return world


@pytest.fixture
def users(client, db) -> tuple[uuid.UUID, uuid.UUID]:
    a, b = uuid.uuid4(), uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s), (%s)", (a, b))
    for uid, clubs in ((a, []), (b, ["רשת אחת"])):
        r = client.put("/me/profile", headers=h(uid), json={
            "neighborhood_lat": ORIGIN[1], "neighborhood_lon": ORIGIN[0], "consent_location": True,
            "clubs": clubs,
        })
        assert r.status_code == 200, r.text
    return a, b


def alert(client, uid, canonical_id: int, threshold: str, **kw) -> dict:
    r = client.post("/me/alerts", headers=h(uid), json={
        "canonical_id": canonical_id, "threshold_unit_price": threshold, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def subscribe(client, uid, endpoint: str) -> None:
    r = client.post("/me/push-subscriptions", headers=h(uid), json={
        "endpoint": endpoint, "p256dh": "BPkey", "auth": "authkey", "user_agent": "test"})
    assert r.status_code == 201, r.text


def deliveries(db, alert_id: int) -> list[tuple]:
    return db.execute(
        "SELECT store_id, item_id, unit_price, channel FROM alert_deliveries WHERE alert_id = %s"
        " ORDER BY id", (alert_id,),
    ).fetchall()


# --- CRUD ----------------------------------------------------------------------------------------


def test_create_list_edit_pause_delete(client, db, w: World, users) -> None:
    a, b = users
    created = alert(client, a, w.canon["eggs"], "1.00", flex_level="exact", radius_m=3000)
    assert created["flex_level"] == "exact" and created["active"] and created["last_fired_at"] is None
    loc = db.execute("SELECT neighborhood_lat, neighborhood_lon FROM price_alerts WHERE id = %s",
                     (created["id"],)).fetchone()
    assert (float(loc[0]), float(loc[1])) == (round(ORIGIN[1], 3), round(ORIGIN[0], 3))
    assert [x["id"] for x in client.get("/me/alerts", headers=h(a)).json()] == [created["id"]]
    assert client.get("/me/alerts", headers=h(b)).json() == []  # RLS

    body = {"canonical_id": w.canon["eggs"], "threshold_unit_price": "0.90", "flex_level": "close",
            "radius_m": 5000, "active": False}
    r = client.put(f"/me/alerts/{created['id']}", headers=h(a), json=body)
    assert r.status_code == 200 and not r.json()["active"] and r.json()["flex_level"] == "close"
    assert client.put(f"/me/alerts/{created['id']}", headers=h(b), json=body).status_code == 404
    assert client.delete(f"/me/alerts/{created['id']}", headers=h(b)).status_code == 404
    assert client.delete(f"/me/alerts/{created['id']}", headers=h(a)).status_code == 204
    assert client.get("/me/alerts", headers=h(a)).json() == []


def test_alert_needs_location_product_and_respects_the_free_limit(client, db, w, users, monkeypatch) -> None:
    a, _ = users
    stranger = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (stranger,))
    body = {"canonical_id": w.canon["eggs"], "threshold_unit_price": "1.00"}
    assert client.post("/me/alerts", headers=h(stranger), json=body).status_code == 422
    assert client.post("/me/alerts", headers=h(a), json={**body, "canonical_id": 999999}).status_code == 404
    assert client.post("/me/alerts", headers=h(a), json={**body, "threshold_unit_price": 0}).status_code == 422
    assert client.post("/me/alerts", json=body).status_code == 401
    monkeypatch.setenv("API_ALERTS_FREE_LIMIT", "1")
    alert(client, a, w.canon["eggs"], "1.00")
    assert client.post("/me/alerts", headers=h(a), json=body).status_code == 403


def test_push_subscription_upsert_by_endpoint(client, db, users) -> None:
    a, b = users
    subscribe(client, a, "https://push.example/1")
    r = client.post("/me/push-subscriptions", headers=h(a), json={
        "endpoint": "https://push.example/1", "p256dh": "new", "auth": "new2"})
    assert r.status_code == 201
    rows = db.execute("SELECT user_id, p256dh FROM push_subscriptions").fetchall()
    assert rows == [(a, "new")]
    subscribe(client, b, "https://push.example/1")  # the device switched accounts
    assert db.execute("SELECT user_id FROM push_subscriptions").fetchall() == [(b,)]
    r = client.request("DELETE", "/me/push-subscriptions", headers=h(b),
                       params={"endpoint": "https://push.example/1"})
    assert r.status_code == 204
    assert db.execute("SELECT count(*) FROM push_subscriptions").fetchone()[0] == 0


# --- the job -------------------------------------------------------------------------------------


def test_club_promo_fires_only_for_members(client, db, w: World, users) -> None:
    a, b = users
    plain = alert(client, a, w.canon["eggs"], "1.00")
    member = alert(client, b, w.canon["eggs"], "1.00")
    subscribe(client, b, "https://push.example/b")
    sender = FakeSender()
    result = evaluate_alerts(db, sender)
    assert result.alerts_checked == 2 and result.fired == 1 and result.pushes_sent == 1
    assert deliveries(db, plain["id"]) == []
    (store, item, price, channel), = deliveries(db, member["id"])
    assert store == w.stores["home"] and item == w.items["eggs_c1"]
    assert price == D("0.8250") and channel == "push"
    target, payload = sender.sent[0]
    assert target.endpoint == "https://push.example/b"
    assert payload["url"] == f"/product/{w.canon['eggs']}" and payload["store_id"] == w.stores["home"]
    assert "המחיר הקובע הוא בקופה" in payload["body"] and "₪ 0.83" in payload["body"]
    assert "מועדון לקוחות" in payload["body"] and payload["price_valid_from"]


def test_push_payload_carries_the_arabic_product_name(client, db, w: World, users) -> None:
    a, _ = users
    db.execute("UPDATE canonical_products SET names_ar = %s WHERE id = %s",
               (["بيض", "بيض طازج"], w.canon["eggs"]))
    alert(client, a, w.canon["eggs"], "1.20")
    alert(client, a, w.canon["milk3"], "9.00")
    subscribe(client, a, "https://push.example/a")
    sender = FakeSender()
    assert evaluate_alerts(db, sender).fired == 2
    by_canonical = {p["canonical_id"]: p for _, p in sender.sent}
    assert by_canonical[w.canon["eggs"]]["product_ar"] == "بيض"
    assert by_canonical[w.canon["milk3"]]["product_ar"] is None
    assert by_canonical[w.canon["eggs"]]["title"].startswith("ירידת מחיר: ")  # Hebrew unchanged


def test_seeded_drop_fires_once_then_deduplicates(client, db, w: World, users) -> None:
    a, _ = users
    a_alert = alert(client, a, w.canon["eggs"], "0.95")
    subscribe(client, a, "https://push.example/a")
    sender = FakeSender()
    assert evaluate_alerts(db, sender).fired == 0
    # Store A drops the eggs to 10.80 (0.90 per egg).
    add_price(db, w.items["eggs_c1"], w.stores["a"], "10.80", None, None,
              datetime.now(UTC) - timedelta(hours=1))
    precompute_effective_prices(db, chains=w.chains)
    now = datetime.now(UTC)
    assert evaluate_alerts(db, sender, now=now).fired == 1
    assert deliveries(db, a_alert["id"]) == [(w.stores["a"], w.items["eggs_c1"], D("0.9000"), "push")]
    # Same day: not again. A day later, the same drop: not again either.
    assert evaluate_alerts(db, sender, now=now + timedelta(hours=1)).deduplicated == 1
    assert evaluate_alerts(db, sender, now=now + timedelta(hours=25)).fired == 0
    assert len(sender.sent) == 1
    # A further drop a day later notifies again.
    add_price(db, w.items["eggs_c1"], w.stores["a"], "9.60", None, None,
              datetime.now(UTC) - timedelta(minutes=30))
    precompute_effective_prices(db, chains=w.chains)
    assert evaluate_alerts(db, sender, now=now + timedelta(hours=26)).fired == 1
    assert deliveries(db, a_alert["id"])[-1][2] == D("0.8000") and len(sender.sent) == 2
    last = client.get("/me/alerts", headers=h(a)).json()[0]["last_fired_at"]
    assert last is not None


def test_flexibility_level_and_radius_are_respected(client, db, w: World, users) -> None:
    a, _ = users
    exact = alert(client, a, w.canon["milk3"], "0.65", flex_level="exact", radius_m=1500)
    anyb = alert(client, a, w.canon["milk3"], "0.65", flex_level="any_brand", radius_m=1500)
    wide = alert(client, a, w.canon["milk3"], "0.60", flex_level="exact", radius_m=2500)
    paused = alert(client, a, w.canon["milk3"], "5.00", active=False)
    result = evaluate_alerts(db, None)  # no VAPID keys: logged, not pushed
    assert result.alerts_checked == 3 and result.fired == 2 and result.pushes_sent == 0
    assert deliveries(db, exact["id"]) == []  # Tnuva at home is 0.69
    assert deliveries(db, anyb["id"]) == [(w.stores["home"], w.items["milk3_c1_private"], D("0.6200"), "log")]
    assert deliveries(db, wide["id"]) == [(w.stores["a"], w.items["milk3_c1_tnuva"], D("0.5900"), "log")]
    assert deliveries(db, paused["id"]) == []


def test_gone_subscriptions_are_removed(client, db, w: World, users) -> None:
    _, b = users
    alert(client, b, w.canon["eggs"], "1.00")
    for n in (1, 2, 3):
        subscribe(client, b, f"https://push.example/{n}")
    sender = FakeSender({"https://push.example/1": 410, "https://push.example/2": 500})
    result = evaluate_alerts(db, sender)
    assert result.pushes_sent == 1 and result.subscriptions_removed == 1 and result.push_failures == 1
    left = [r[0] for r in db.execute("SELECT endpoint FROM push_subscriptions ORDER BY id").fetchall()]
    assert left == ["https://push.example/2", "https://push.example/3"]


def test_cli_alerts_run(client, db, w: World, users, monkeypatch) -> None:
    _, b = users
    alert(client, b, w.canon["eggs"], "1.00")
    monkeypatch.setattr(cli, "_connect", lambda: nullcontext(db))
    for k in ("VAPID_PRIVATE_KEY", "VAPID_PUBLIC_KEY", "VAPID_SUBJECT"):
        monkeypatch.delenv(k, raising=False)
    out = CliRunner().invoke(cli.app, ["alerts-run"])
    assert out.exit_code == 0, out.output
    metrics = json.loads(out.stdout.strip().splitlines()[-1])
    assert metrics["fired"] == 1 and metrics["pushes_sent"] == 0


def test_web_push_sender(monkeypatch) -> None:
    for k in ("VAPID_PRIVATE_KEY", "VAPID_PUBLIC_KEY", "VAPID_SUBJECT"):
        monkeypatch.delenv(k, raising=False)
    assert WebPushSender.from_env() is None
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:team@example.com")
    sender = WebPushSender.from_env()
    assert sender is not None

    import pywebpush
    import requests

    calls: list[dict] = []

    def fake_webpush(**kw):
        calls.append(kw)
        if kw["subscription_info"]["endpoint"].endswith("gone"):
            resp = requests.Response()
            resp.status_code = 410
            raise pywebpush.WebPushException("gone", response=resp)
        resp = requests.Response()
        resp.status_code = 201
        return resp

    monkeypatch.setattr(pywebpush, "webpush", fake_webpush)
    target = PushTarget(1, "https://push.example/ok", "p", "a")
    assert sender(target, {"title": "ירידת מחיר"}) == 201
    assert calls[0]["vapid_private_key"] == "priv" and calls[0]["vapid_claims"] == {"sub": "mailto:team@example.com"}
    assert json.loads(calls[0]["data"]) == {"title": "ירידת מחיר"}
    assert calls[0]["subscription_info"]["keys"] == {"p256dh": "p", "auth": "a"}
    assert sender(PushTarget(2, "https://push.example/gone", "p", "a"), {}) == 410
