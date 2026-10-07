"""Smoke test of the running demo API (``scripts/demo/up.sh``), over HTTP.

Walks the MVP path the web app takes and asserts the product rules on real responses:

1. ``/health``;
2. ``/parse-list`` with a Hebrew list: every row resolves, quantities and weights are read;
3. ``/search``;
4. ``/compare`` with a home store: every price carries an update timestamp, every store a
   ``prices_updated_at``, the disclaimer is there, and the saving is versus the home store only;
5. ``/optimize`` with ``solver = heuristic`` and ``milp``: the hero number (net saving versus the
   home store) is computed on the recommended plan and equals basket saving minus travel minus the
   extra stop; the split is recommended for the demo list;
6. a close substitute is labeled (``is_substitute``, confidence, attribute tags);
7. ``/items/barcode/{ean}`` for a fixture barcode, with prices and timestamps;
8. ``/history/{canonical_id}`` at the home store: a series with the day-2 price change;
9. signed in with a demo token: ``PUT /me/profile`` and an alert created, listed and deleted;
   without a token ``/me/alerts`` answers 401.

Exits 1 on the first failed check and prints what was checked. Stdlib only, so it runs with any
Python 3.12.

    uv run python scripts/demo/smoke.py [--base-url http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_user  # noqa: E402

# The demo shopper: the rounded neighborhood point in Ramat Gan, 5 km, home chain Shufersal.
LAT, LON, RADIUS_M = 32.085, 34.820, 5000
SHUFERSAL = "7290027600007"
DEMO_LIST = (
    "3 חלב טרי 3%, 2 קוטג' 5%, לחם אחיד, 2 ק\"ג עגבניות שרי, 6 במבה, 2 שמן קנולה,"
    ' 2 ק"ג בננות, 4 שוקולד מריר'
)
MILK_BARCODE = "7290004131074"  # build_synthetic.ITEMS[0], sold by every fixture chain
DISCLAIMER = "המחיר הקובע הוא בקופה."


class SmokeFailure(AssertionError):
    pass


class Client:
    def __init__(self, base: str, token: str | None = None) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def call(self, method: str, path: str, body: Any = None, auth: bool = False) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"accept": "application/json"}
        if data is not None:
            headers["content-type"] = "application/json"
        if auth and self.token:
            headers["authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                raw = res.read()
                return res.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw)
            except ValueError:
                return exc.code, raw.decode(errors="replace")

    def ok(self, method: str, path: str, body: Any = None, auth: bool = False) -> Any:
        status, data = self.call(method, path, body, auth)
        check(200 <= status < 300, f"{method} {path} answered {status}: {str(data)[:300]}")
        return data


CHECKS: list[str] = []


def check(cond: bool, message: str) -> None:
    if not cond:
        raise SmokeFailure(message)


def passed(message: str) -> None:
    CHECKS.append(message)
    print(f"  ok  {message}")


def dec(value: Any) -> Decimal:
    return Decimal(str(value))


def basket_from(rows: list[dict], flex: dict[int, str] | None = None) -> list[dict]:
    flex = flex or {}
    return [
        {
            "canonical_id": r["canonical"]["canonical_id"],
            "quantity": r["quantity"],
            "flex_level": flex.get(r["canonical"]["canonical_id"], r["flex_level"]),
        }
        for r in rows
    ]


def check_lines_timestamped(stores: list[dict]) -> int:
    lines = 0
    for s in stores:
        check(bool(s.get("prices_updated_at")), f"store {s['store_id']} has no prices_updated_at")
        for line in s["items"]:
            check(
                bool(line.get("price_valid_from")),
                f"line {line['item_id']} at store {s['store_id']} has no price_valid_from",
            )
            lines += 1
    return lines


def check_plan_breakdown(plan: dict, label: str) -> Decimal:
    b = plan.get("breakdown")
    check(b is not None, f"{label}: no breakdown although a home store was given")
    net = dec(b["net_saving"])
    expected = dec(b["basket_saving"]) - dec(b["travel_cost"]) - dec(b["extra_stop_cost"])
    check(net == expected, f"{label}: net_saving {net} != basket - travel - extra stop {expected}")
    for part in plan["stores"]:
        check_lines_timestamped([part["store"]])
    return net


def run(base: str) -> None:
    api = Client(base, demo_user.mint_token())

    print("health")
    health = api.ok("GET", "/health")
    check(health.get("status") == "ok", f"/health: {health}")
    passed(f"/health ok, API {health['version']}")

    print("parse-list")
    parsed = api.ok("POST", "/parse-list", {"text": DEMO_LIST})
    rows = parsed["rows"]
    check(len(rows) == 8, f"/parse-list: expected 8 rows, got {len(rows)}")
    for r in rows:
        check(
            not r["not_found"] and r["canonical"], f"/parse-list: not resolved: {r['input_text']}"
        )
        check(not r["needs_confirmation"], f"/parse-list: needs confirmation: {r['input_text']}")
    by_name = {r["canonical"]["display_name_he"]: r for r in rows}
    check(dec(by_name["חלב טרי 3%"]["quantity"]) == 3, "/parse-list: milk quantity is not 3")
    tomatoes = by_name["עגבניות שרי"]
    check(tomatoes["unit"] == "kg" and dec(tomatoes["quantity"]) == 2, "/parse-list: 2 kg tomatoes")
    passed(f"/parse-list resolved {len(rows)} Hebrew rows with quantities and weights")

    print("search")
    hits = api.ok("GET", "/search?q=" + urllib.request.quote("קוטג") + "&limit=5")["hits"]
    check(any(h["canonical"]["display_name_he"] == "קוטג' 5%" for h in hits), f"/search: {hits}")
    passed("/search finds קוטג' 5%")

    home = api.ok("GET", f"/stores/nearest?chain_id={SHUFERSAL}&lon={LON}&lat={LAT}")
    home_id = home["store_id"]
    passed(f"/stores/nearest: home store {home['store_name']} ({home['distance_m']} m)")

    location = {"lat": LAT, "lon": LON, "radius_m": RADIUS_M}
    basket = basket_from(rows)

    print("compare")
    cmp = api.ok(
        "POST", "/compare", {"items": basket, "location": location, "home_store_id": home_id}
    )
    stores = cmp["stores"]
    check(len(stores) >= 3, f"/compare: expected at least 3 stores, got {len(stores)}")
    check(cmp["disclaimer_he"] == DISCLAIMER, f"/compare: disclaimer {cmp['disclaimer_he']!r}")
    check(cmp["home_store_id"] == home_id, "/compare: home store not echoed")
    check(cmp["home_store_total"] is not None, "/compare: no home_store_total")
    lines = check_lines_timestamped(stores)
    home_row = next(s for s in stores if s["store_id"] == home_id)
    check(dec(home_row["saving_vs_home"]) == 0, "/compare: the home store saves against itself")
    for s in stores:
        check(s["saving_vs_home"] is not None, f"/compare: store {s['store_id']} has no saving")
        check(not s["missing"], f"/compare: store {s['store_name']} misses {s['missing']}")
    passed(f"/compare: {len(stores)} stores, {lines} lines, every price timestamped, disclaimer")

    print("optimize")
    req = {
        "items": basket,
        "location": location,
        "home_store_id": home_id,
        "travel": {"mode": "car", "cost_per_km": 1.2, "extra_stop_value": 25},
    }
    for solver in ("heuristic", "milp"):
        opt = api.ok("POST", "/optimize", {**req, "solver": solver})
        check(opt["solver"] == solver, f"/optimize: asked for {solver}, ran {opt['solver']}")
        check(opt["disclaimer_he"] == DISCLAIMER, "/optimize: disclaimer missing")
        check(opt["minimum_effort"] is not None, f"/optimize {solver}: no minimum-effort plan")
        check(opt["split"] is not None, f"/optimize {solver}: no split for the demo list")
        recommended = [p for p in (opt["single"], opt["split"]) if p and p["recommended"]]
        check(len(recommended) == 1, f"/optimize {solver}: {len(recommended)} recommended plans")
        hero = check_plan_breakdown(recommended[0], f"{solver} {recommended[0]['kind']}")
        check_plan_breakdown(opt["single"], f"{solver} single")
        me = check_plan_breakdown(opt["minimum_effort"], f"{solver} minimum_effort")
        check(me == 0, f"/optimize {solver}: the home store saves {me} against itself")
        check(hero > 0, f"/optimize {solver}: hero number {hero} is not a saving")
        names = " + ".join(p["store"]["store_name"] for p in recommended[0]["stores"])
        passed(f"/optimize {solver}: recommended {recommended[0]['kind']} ({names}), "
               f"net saving vs home ₪{hero}")  # fmt: skip

    print("substitutes")
    bread = by_name["לחם אחיד"]["canonical"]["canonical_id"]
    cmp_close = api.ok(
        "POST",
        "/compare",
        {"items": basket_from(rows, {bread: "close"}), "location": location,
         "home_store_id": home_id},
    )  # fmt: skip
    subs = [line for s in cmp_close["stores"] for line in s["items"] if line["is_substitute"]]
    check(bool(subs), "/compare at close: no substitute line for the bread")
    for line in subs:
        check(line["confidence"] is not None, f"substitute {line['item_id']} has no confidence")
        check(bool(line["tags"]), f"substitute {line['item_id']} has no attribute tags")
        check(bool(line["price_valid_from"]), f"substitute {line['item_id']} has no timestamp")
    passed(f"close level: {len(subs)} substitute line(s), labeled with confidence and tags")

    print("barcode")
    scan = api.ok(
        "GET",
        f"/items/barcode/{MILK_BARCODE}?lon={LON}&lat={LAT}&radius_m={RADIUS_M}&store_id={home_id}",
    )
    check(scan["found"], f"/items/barcode: {MILK_BARCODE} not found")
    check(scan["disclaimer_he"] == DISCLAIMER, "/items/barcode: disclaimer missing")
    for key in ("here", "cheapest_nearby"):
        check(scan[key] is not None, f"/items/barcode: no {key}")
        check(bool(scan[key]["price_valid_from"]), f"/items/barcode: {key} has no timestamp")
    if scan["cheaper_substitute"]:
        check(scan["cheaper_substitute"]["is_substitute"], "barcode: substitute not labeled")
    passed(f"/items/barcode/{MILK_BARCODE}: here ₪{scan['here']['shelf_price']}, "
           f"cheapest nearby ₪{scan['cheapest_nearby']['shelf_price']}")  # fmt: skip

    print("history")
    milk = by_name["חלב טרי 3%"]["canonical"]["canonical_id"]
    hist = api.ok("GET", f"/history/{milk}?store_id={home_id}&days=90")
    points = hist["points"]
    check(len(points) >= 2, f"/history: {len(points)} points")
    shelf = {dec(p["shelf_price"]) for p in points if p["shelf_price"] is not None}
    check(len(shelf) >= 2, f"/history: no price change in the series ({shelf})")
    passed(f"/history/{milk}: {len(points)} daily points, shelf prices {sorted(shelf)}")

    print("signed in")
    status, _ = api.call("GET", "/me/alerts")
    check(status == 401, f"/me/alerts without a token answered {status}, expected 401")
    api.ok(
        "PUT",
        "/me/profile",
        {"home_store_id": home_id, "radius_m": RADIUS_M, "neighborhood_lat": LAT,
         "neighborhood_lon": LON, "consent_location": True},
        auth=True,
    )  # fmt: skip
    alert = api.ok(
        "POST",
        "/me/alerts",
        {"canonical_id": milk, "threshold_unit_price": "0.50", "flex_level": "any_brand"},
        auth=True,
    )
    listed = api.ok("GET", "/me/alerts", auth=True)
    check(any(a["id"] == alert["id"] for a in listed), "/me/alerts: created alert not listed")
    status, _ = api.call("DELETE", f"/me/alerts/{alert['id']}", auth=True)
    check(status in (200, 204), f"DELETE /me/alerts answered {status}")
    passed("signed in: profile saved, alert created, listed and deleted; 401 without a token")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test of the running demo API.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DEMO_API_BASE_URL")
        or f"http://127.0.0.1:{os.environ.get('DEMO_API_PORT', '8000')}",
    )
    args = parser.parse_args()
    print(f"smoke test against {args.base_url}")
    try:
        run(args.base_url)
    except SmokeFailure as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, ConnectionError) as exc:
        print(f"FAILED: cannot reach the API at {args.base_url}: {exc}", file=sys.stderr)
        return 1
    print(f"smoke test passed: {len(CHECKS)} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
