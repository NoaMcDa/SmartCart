"""Scaled synthetic load test: build a larger world, load it through the real pipeline into a
throwaway Postgres, and time the nightly jobs and the API routes.

    uv run python scripts/loadtest/run.py              # about 300 stores, 5,000 items, 90 days
    uv run python scripts/loadtest/run.py --small      # the CI-sized run (about 20 s)
    uv run python scripts/loadtest/run.py --keep       # leave the database and API running

Steps, each timed:

1. ``world.py`` writes the transparency files with the fixture builders (see its docstring).
2. A throwaway cluster (``scripts/demo/pg.py``, own state directory and port; or
   ``--database-url``), ``smartcart-ingest migrate``, ``smartcart-catalog seed``.
3. Every file replayed through ``Scheduler`` -> download -> adapter -> quality gates ->
   ``loader.load``, in publication order per chain, with the scheduler's clock one hour after the
   file's publication (as ``scripts/demo/load_fixtures.py`` does), chains in parallel processes.
4. ``smartcart-catalog normalize``, ``extract --extractor rule``, ``embed --target all --embedder
   hash``; then the world's answer key through ``review_app.accept`` (the review step's function,
   reviewer ``loadtest-answer-key``) in place of the judge.
5. ``smartcart-api precompute`` (as of now).
6. Synthetic users with profiles and price alerts (``--alerts``), then ``smartcart-api serve``
   (``WEB_CONCURRENCY`` workers) and, over HTTP, one request at a time: ``/search`` for 50
   queries, ``/compare``, ``/optimize`` heuristic and MILP (K = 2) for the same ``--baskets``
   baskets of ``--basket-items`` items within 5 km of points in Gush Dan, each with a home store;
   then ``/compare`` from ``--concurrency`` clients at once for throughput.
7. ``smartcart-api alerts-run --dry-run``.

Prints a JSON report on stdout (and ``--out FILE``) and a Markdown table on stderr. Everything is
SYNTHETIC: the numbers size the machine and catch regressions; they say nothing about real data.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import random
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from typing import Any

import psycopg

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts" / "demo"))

import world  # noqa: E402

GUSH_DAN_POINTS = [(lat, lon, spread) for _, lat, lon, spread in world.GUSH_DAN]


# --- helpers -----------------------------------------------------------------------------------


def log(msg: str) -> None:
    print(f"==> {msg}", file=sys.stderr, flush=True)


def run_cli(args: list[str], env: dict[str, str], name: str) -> tuple[float, str]:
    """Run a workspace CLI from the repo's .venv; return (seconds, stdout)."""
    exe = REPO / ".venv" / "bin" / args[0]
    t0 = time.perf_counter()
    res = subprocess.run([str(exe), *args[1:]], env=env, capture_output=True, text=True, cwd=REPO)
    dt = time.perf_counter() - t0
    if res.returncode != 0:
        sys.stderr.write(res.stdout[-2000:] + res.stderr[-4000:])
        raise SystemExit(f"{name} failed ({res.returncode})")
    return dt, res.stdout


def pct(values: list[float], q: float) -> float:
    """Nearest-rank percentile."""
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(q / 100 * len(s) + 0.5)) - 1))
    return s[k]


def summary_ms(values: list[float]) -> dict[str, float]:
    ms = [v * 1000 for v in values]
    return {
        "n": len(ms),
        "p50_ms": round(statistics.median(ms), 1),
        "p95_ms": round(pct(ms, 95), 1),
        "max_ms": round(max(ms), 1),
        "mean_ms": round(statistics.fmean(ms), 1),
    }


class Http:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, body: Any = None) -> tuple[int, Any, float]:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"accept": "application/json"}
        if data is not None:
            headers["content-type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                raw = res.read()
                status = res.status
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
        dt = time.perf_counter() - t0
        try:
            payload = json.loads(raw) if raw else None
        except ValueError:
            payload = raw.decode(errors="replace")
        return status, payload, dt


# --- load: the replay, one process per chain -------------------------------------------------


def _load_chain(dsn: str, world_dir: str, raw_dir: str, slug: str) -> dict[str, Any]:
    import load_fixtures as lf

    from smartcart_ingest import db as dbmod
    from smartcart_ingest.adapters import get_adapter
    from smartcart_ingest.adapters.base import AdapterError
    from smartcart_ingest.alerts import Alerter
    from smartcart_ingest.rawstore import LocalRawStore
    from smartcart_ingest.scheduler import DELTA_KINDS, Scheduler
    from smartcart_ingest.settings import load_settings

    lf._quiet_logs()
    chain = next(c for c in world.CHAINS if c.slug == slug)
    adapter = get_adapter(chain.chain_id)
    files = []
    for path in sorted((Path(world_dir) / slug).iterdir()):
        try:
            info = adapter.parse_filename(path.name)
        except AdapterError:
            continue
        files.append(lf.FixtureFile(chain.chain_id, slug, path, info.kind, info.published_at))
    files.sort(key=lambda f: (f.published_at, lf.KIND_ORDER[f.kind], f.path.name))

    sink = lf.CollectSink()
    fetcher = lf.OneFileFetcher()
    clock: dict[str, Any] = {}
    t0 = time.perf_counter()
    with dbmod.connect(dsn, autocommit=True) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        sched = Scheduler(
            conn,
            fetcher,
            LocalRawStore(Path(raw_dir)),
            Alerter([sink]),
            load_settings(),
            adapter_for=get_adapter,
            now=lambda: clock["now"],
            sleep=lambda s: None,
        )
        for f in files:
            fetcher.current = f
            clock["now"] = f.published_at + timedelta(hours=1)
            if f.kind in DELTA_KINDS:
                sched.run_delta([f.chain_id])
            else:
                sched.run_full([f.chain_id])
        status = lf.chain_status(conn, chain.chain_id)
    return {
        "slug": slug,
        "files": len(files),
        "seconds": round(time.perf_counter() - t0, 2),
        "status": status,
        "alerts": [a.kind for a in sink.alerts],
    }


def load_world(dsn: str, world_dir: Path, raw_dir: Path, jobs: int) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    slugs = [c.slug for c in world.CHAINS]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        results = list(
            pool.map(
                _load_chain,
                [dsn] * len(slugs),
                [str(world_dir)] * len(slugs),
                [str(raw_dir)] * len(slugs),
                slugs,
            )  # fmt: skip
        )
    totals: dict[str, int] = {}
    for r in results:
        for k, v in r["status"].items():
            totals[k] = totals.get(k, 0) + v
    return {"seconds": round(time.perf_counter() - t0, 1), "file_tracking": totals,
            "per_chain": results}  # fmt: skip


# --- steps -------------------------------------------------------------------------------------


def map_answer_key(dsn: str, world_dir: Path) -> dict[str, Any]:
    from smartcart_catalog import review_app

    key = json.loads((world_dir / "answer_key.json").read_text(encoding="utf-8"))
    t0 = time.perf_counter()
    accepted = missing = 0
    with psycopg.connect(dsn) as conn:
        canon = dict(conn.execute("SELECT slug, id FROM canonical_products").fetchall())
        items = {
            f"{c}:{code}": i
            for i, c, code in conn.execute("SELECT id, chain_id, item_code FROM items").fetchall()
        }
        for ref, truth in key.items():
            item_id = items.get(ref)
            if item_id is None:
                missing += 1  # an item no store stocked never reached a file
                continue
            review_app.accept(conn, item_id, canon[truth["canonical"]], "loadtest-answer-key",
                              truth["level"])  # fmt: skip
            accepted += 1
        conn.commit()
    return {"seconds": round(time.perf_counter() - t0, 1), "accepted": accepted,
            "not_in_any_file": missing}  # fmt: skip


def counts(dsn: str) -> dict[str, int]:
    sql = {
        "chains": "SELECT count(*) FROM chains",
        "stores": "SELECT count(*) FROM stores",
        "stores_with_location": "SELECT count(*) FROM stores WHERE geog IS NOT NULL",
        "items": "SELECT count(*) FROM items",
        "item_canonical": "SELECT count(*) FROM item_canonical",
        "canonicals_mapped": "SELECT count(DISTINCT canonical_id) FROM item_canonical",
        "price_events": "SELECT count(*) FROM prices",
        "price_event_days": "SELECT count(DISTINCT valid_from::date) FROM prices",
        "promos": "SELECT count(*) FROM promos",
        "promo_items": "SELECT count(*) FROM promo_items",
        "effective_prices": "SELECT count(*) FROM effective_prices",
    }
    with psycopg.connect(dsn) as conn:
        return {k: conn.execute(q).fetchone()[0] for k, q in sql.items()}


def make_alerts(dsn: str, n_users: int, per_user: int, rng: random.Random) -> int:
    with psycopg.connect(dsn) as conn:
        medians = conn.execute(
            "SELECT canonical_id, percentile_cont(0.5) WITHIN GROUP (ORDER BY effective_unit_price)"
            " FROM effective_prices WHERE flex_level = 'any_brand' GROUP BY canonical_id"
        ).fetchall()
        rows = 0
        for _ in range(n_users):
            uid = uuid.uuid4()
            lat, lon, spread = rng.choice(GUSH_DAN_POINTS)
            lat, lon = lat + rng.uniform(-spread, spread), lon + rng.uniform(-spread, spread)
            conn.execute("INSERT INTO auth.users (id, email) VALUES (%s, %s)",
                         (uid, f"{uid.hex[:12]}@loadtest.invalid"))  # fmt: skip
            conn.execute(
                "INSERT INTO profiles (user_id, neighborhood_lat, neighborhood_lon, consent_location)"
                " VALUES (%s, %s, %s, true)",
                (uid, lat, lon),
            )
            for canonical_id, median in rng.sample(medians, per_user):
                conn.execute(
                    "INSERT INTO price_alerts (user_id, canonical_id, threshold_unit_price,"
                    " radius_m, neighborhood_lat, neighborhood_lon) VALUES (%s, %s, %s, 5000, %s, %s)",
                    (uid, canonical_id, round(float(median) * rng.uniform(0.8, 1.1), 2), lat, lon),
                )
                rows += 1
        conn.commit()
    return rows


def baskets(dsn: str, n: int, size: int, rng: random.Random) -> list[dict[str, Any]]:
    with psycopg.connect(dsn) as conn:
        canon = conn.execute(
            "SELECT c.id, c.base_unit FROM canonical_products c"
            " WHERE EXISTS (SELECT 1 FROM effective_prices e WHERE e.canonical_id = c.id)"
            " ORDER BY c.id"
        ).fetchall()
        chains = [r[0] for r in conn.execute("SELECT id FROM chains ORDER BY 1").fetchall()]
        out = []
        for _ in range(n):
            lat, lon, spread = rng.choice(GUSH_DAN_POINTS)
            lat, lon = lat + rng.uniform(-spread, spread), lon + rng.uniform(-spread, spread)
            home = conn.execute(
                "SELECT id FROM stores WHERE chain_id = %s AND geog IS NOT NULL"
                " ORDER BY geog <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography LIMIT 1",
                (rng.choice(chains), lon, lat),
            ).fetchone()
            items = []
            for cid, base_unit in rng.sample(canon, min(size, len(canon))):
                qty = round(rng.uniform(0.5, 2.0), 1) if base_unit == "kg" else rng.randint(1, 3)
                items.append({"canonical_id": cid, "quantity": qty,
                              "flex_level": "close" if rng.random() < 0.2 else "any_brand"})  # fmt: skip
            out.append({
                "items": items,
                "location": {"lat": round(lat, 3), "lon": round(lon, 3), "radius_m": 5000},
                "home_store_id": home[0] if home else None,
            })  # fmt: skip
    return out


def search_queries(dsn: str, n: int, rng: random.Random) -> list[str]:
    with psycopg.connect(dsn) as conn:
        names = [r[0] for r in conn.execute(
            "SELECT display_name_he FROM canonical_products ORDER BY id").fetchall()]  # fmt: skip
    out = []
    for i in range(n):
        name = rng.choice(names)
        words = name.split()
        mode = i % 4
        if mode == 0:
            q = name
        elif mode == 1:
            q = words[0]
        elif mode == 2 and len(words[0]) > 2:  # a doubled letter: a typo
            j = rng.randrange(1, len(words[0]))
            q = words[0][:j] + words[0][j - 1] + words[0][j:]
        else:
            q = words[0][:3]
        out.append(q)
    return out


def start_api(dsn: str, port: int, workers: int, log_path: Path) -> subprocess.Popen:
    env = {**os.environ, "DATABASE_URL": dsn, "WEB_CONCURRENCY": str(workers),
           "API_POOL_MAX": "10"}  # fmt: skip
    exe = REPO / ".venv" / "bin" / "smartcart-api"
    http = Http(f"http://127.0.0.1:{port}")
    try:
        http.call("GET", "/health")
    except OSError:
        pass  # nothing listens there: good
    else:
        raise SystemExit(f"port {port} already answers; stop that server or pass --api-port")
    fh = open(log_path, "w")  # noqa: SIM115 - closed when the process is stopped
    proc = subprocess.Popen(
        [str(exe), "serve", "--host", "127.0.0.1", "--port", str(port)],
        env=env, stdout=fh, stderr=subprocess.STDOUT, cwd=tempfile.gettempdir(),
        start_new_session=True,
    )  # fmt: skip
    for _ in range(300):
        if proc.poll() is not None:
            raise SystemExit(f"the API exited; see {log_path}")
        try:
            if http.call("GET", "/health")[0] == 200:
                return proc
        except OSError:
            pass
        time.sleep(0.1)
    raise SystemExit(f"the API did not start; see {log_path}")


def stop_api(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=20)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        os.killpg(proc.pid, signal.SIGKILL)


def bench_routes(http: Http, bks: list[dict], queries: list[str], concurrency: int,
                 throughput_requests: int) -> dict[str, Any]:  # fmt: skip
    out: dict[str, Any] = {}

    def must(status: int, payload: Any, what: str) -> Any:
        if status != 200:
            raise SystemExit(f"{what}: HTTP {status}: {str(payload)[:500]}")
        return payload

    # Warm-up: imports, pool connections, OR-Tools.
    for b in bks[:6]:  # enough requests to reach every worker process
        http.call("POST", "/compare", b)
        http.call("POST", "/optimize", {**b, "solver": "milp", "max_stores": 2})

    t = []
    for q in queries:
        s, p, dt = http.call("GET", "/search?" + urllib.parse.urlencode({"q": q, "limit": 10}))
        must(s, p, f"/search {q}")
        t.append(dt)
    out["search"] = summary_ms(t)

    t, stores, found = [], [], []
    for b in bks:
        s, p, dt = http.call("POST", "/compare", b)
        must(s, p, "/compare")
        t.append(dt)
        stores.append(len(p["stores"]))
        if p["stores"]:
            found.append(p["stores"][0]["found_count"])
    out["compare"] = {**summary_ms(t), "stores_in_radius_median": statistics.median(stores),
                      "stores_in_radius_max": max(stores),
                      "best_store_found_median": statistics.median(found) if found else 0}  # fmt: skip

    for solver in ("heuristic", "milp"):
        t, solvers, subsets, splits = [], [], [], 0
        for b in bks:
            body = {**b, "solver": solver, "max_stores": 2}
            s, p, dt = http.call("POST", "/optimize", body)
            must(s, p, f"/optimize {solver}")
            t.append(dt)
            solvers.append(p.get("solver"))
            subsets.append(p.get("subsets_evaluated") or 0)
            splits += 1 if p.get("split") else 0
        out[f"optimize_{solver}"] = {
            **summary_ms(t),
            "solver_answered": {k: solvers.count(k) for k in set(solvers)},
            "subsets_evaluated_median": statistics.median(subsets),
            "baskets_with_a_split": splits,
        }

    # Throughput: /compare from several clients at once.
    lock = threading.Lock()
    lat: list[float] = []
    errors = 0

    def one(i: int) -> None:
        nonlocal errors
        s, _, dt = http.call("POST", "/compare", bks[i % len(bks)])
        with lock:
            lat.append(dt)
            if s != 200:
                errors += 1

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        list(pool.map(one, range(throughput_requests)))
    wall = time.perf_counter() - t0
    out["compare_concurrent"] = {**summary_ms(lat), "concurrency": concurrency,
                                 "requests": throughput_requests, "errors": errors,
                                 "requests_per_s": round(throughput_requests / wall, 1)}  # fmt: skip
    return out


def markdown(report: dict[str, Any]) -> str:
    r, c, s = report["routes"], report["counts"], report["steps"]
    lines = [
        f"World: {c['stores']} stores ({c['stores_with_location']} with a location), "
        f"{c['items']} items mapped to {c['canonicals_mapped']} canonicals, "
        f"{c['price_events']} price events over {c['price_event_days']} days, "
        f"{c['promos']} promotions, {c['effective_prices']} effective-price rows.",
        "",
        "| Step | Time |",
        "|---|---|",
    ]
    for k, v in s.items():
        lines.append(f"| {k} | {v} s |")
    lines += ["", "| Route | n | p50 | p95 | max |", "|---|---|---|---|---|"]
    for k in ("search", "compare", "optimize_heuristic", "optimize_milp", "compare_concurrent"):
        v = r[k]
        lines.append(f"| {k} | {v['n']} | {v['p50_ms']} ms | {v['p95_ms']} ms | {v['max_ms']} ms |")
    lines.append(f"\n/compare from {r['compare_concurrent']['concurrency']} clients: "
                 f"{r['compare_concurrent']['requests_per_s']} requests/s")  # fmt: skip
    return "\n".join(lines)


# --- main --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--small", action="store_true", help="CI-sized: 30 stores, 1,200 items, 30 days")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--state-dir", type=Path,
                   default=Path(os.environ.get("SMARTCART_LOADTEST_DIR")
                                or Path(tempfile.gettempdir()) / "smartcart-loadtest"))  # fmt: skip
    p.add_argument(
        "--database-url",
        default=None,
        help="use this (empty, migratable) database instead of a throwaway cluster",
    )
    p.add_argument("--pg-port", type=int, default=54339)
    p.add_argument("--api-port", type=int, default=8020)
    p.add_argument("--workers", type=int, default=2, help="API worker processes (WEB_CONCURRENCY)")
    p.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1),
                   help="chains loaded in parallel")  # fmt: skip
    p.add_argument("--baskets", type=int, default=None)
    p.add_argument("--basket-items", type=int, default=None)
    p.add_argument("--queries", type=int, default=50)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--alerts-users", type=int, default=None)
    p.add_argument("--stores-per-chain", type=int, default=None, help="override the world's shape")
    p.add_argument("--days", type=int, default=None, help="override the price history length")
    p.add_argument("--every", type=int, default=None, help="days between publication days")
    p.add_argument("--keep", action="store_true", help="leave the database (and API) running")
    p.add_argument("--out", type=Path, default=None, help="also write the JSON report here")
    a = p.parse_args(argv)

    shape = world.SMALL if a.small else world.Shape()
    overrides = {k: v for k, v in (("stores_per_chain", a.stores_per_chain), ("days", a.days),
                                   ("delta_every_days", a.every)) if v}  # fmt: skip
    shape = dataclasses.replace(shape, **overrides)
    n_baskets = a.baskets or (10 if a.small else 50)
    basket_items = a.basket_items or (10 if a.small else 25)
    n_users = a.alerts_users if a.alerts_users is not None else (50 if a.small else 500)
    rng = random.Random(a.seed)
    state = a.state_dir
    state.mkdir(parents=True, exist_ok=True)
    steps: dict[str, float] = {}
    t_all = time.perf_counter()

    log("world (fixture builders)")
    t0 = time.perf_counter()
    world_summary = world.build(state / "world", shape, a.seed)
    steps["world files written"] = round(time.perf_counter() - t0, 1)

    env = {**os.environ, "SMARTCART_DEMO_DIR": str(state), "DEMO_PG_PORT": str(a.pg_port)}
    if a.database_url:
        dsn = a.database_url
    else:
        log(f"throwaway Postgres on port {a.pg_port}")
        # A fresh cluster every run: an earlier, interrupted run may have left one behind.
        subprocess.run([sys.executable, str(REPO / "scripts/demo/pg.py"), "stop"], env=env,
                       capture_output=True)  # fmt: skip
        res = subprocess.run([sys.executable, str(REPO / "scripts/demo/pg.py"), "start"], env=env,
                             capture_output=True, text=True, check=True)  # fmt: skip
        dsn = res.stdout.strip()
    env["DATABASE_URL"] = dsn
    env["PGTZ"] = "UTC"

    log("migrate, seed")
    steps["migrate"] = round(run_cli(["smartcart-ingest", "migrate"], env, "migrate")[0], 1)
    steps["catalog seed"] = round(run_cli(["smartcart-catalog", "seed"], env, "seed")[0], 1)

    log(f"load {world_summary['files']} files through the gates ({a.jobs} chains at a time)")
    load = load_world(dsn, state / "world", state / "raw", a.jobs)
    steps["load (adapters, gates, loader)"] = load["seconds"]
    if load["file_tracking"].get("failed") or load["file_tracking"].get("quarantined"):
        log(f"WARNING: not every file loaded: {load['file_tracking']}")

    log("catalog: normalize, rule extraction, hash embeddings, answer-key review")
    steps["normalize"] = round(run_cli(["smartcart-catalog", "normalize", "--show", "0"], env,
                                       "normalize")[0], 1)  # fmt: skip
    steps["extract (rule)"] = round(run_cli(["smartcart-catalog", "extract", "--extractor", "rule"],
                                            env, "extract")[0], 1)  # fmt: skip
    steps["embed (hash)"] = round(run_cli(["smartcart-catalog", "embed", "--target", "all",
                                           "--embedder", "hash"], env, "embed")[0], 1)  # fmt: skip
    mapping = map_answer_key(dsn, state / "world")
    steps["review (answer key)"] = mapping["seconds"]

    log("precompute")
    dt, out = run_cli(["smartcart-api", "precompute"], env, "precompute")
    steps["precompute"] = round(dt, 1)
    precompute_metrics = json.loads(out.strip().splitlines()[-1])

    log(f"{n_users} users with 2 alerts each")
    alerts_rows = make_alerts(dsn, n_users, 2, rng)

    log(f"API on 127.0.0.1:{a.api_port} with {a.workers} workers")
    proc = start_api(dsn, a.api_port, a.workers, state / "api.log")
    try:
        bks = baskets(dsn, n_baskets, basket_items, rng)
        queries = search_queries(dsn, a.queries, rng)
        log(f"routes: {len(queries)} searches, {len(bks)} baskets x {basket_items} items")
        routes = bench_routes(Http(f"http://127.0.0.1:{a.api_port}"), bks, queries,
                              a.concurrency, max(40, 4 * a.concurrency))  # fmt: skip
    finally:
        if not a.keep:
            stop_api(proc)

    log("alerts job")
    dt, out = run_cli(["smartcart-api", "alerts-run", "--dry-run"], env, "alerts-run")
    steps["alerts-run (dry run)"] = round(dt, 1)
    alerts_metrics = json.loads(out.strip().splitlines()[-1])

    report = {
        "shape": "small" if a.small else "default",
        "world": world_summary,
        "counts": counts(dsn),
        "load": {k: v for k, v in load.items() if k != "per_chain"},
        "load_per_chain": [
            {k: r[k] for k in ("slug", "files", "seconds", "status")} for r in load["per_chain"]
        ],  # fmt: skip
        "mapping": mapping,
        "precompute": precompute_metrics,
        "alerts": {"alerts": alerts_rows, **alerts_metrics},
        "routes": routes,
        "steps": steps,
        "api_workers": a.workers,
        "machine": {"cpus": os.cpu_count(), "load_avg": [round(x, 2) for x in os.getloadavg()]},
        "total_seconds": round(time.perf_counter() - t_all, 1),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(text)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
    print(markdown(report), file=sys.stderr)

    if not a.keep and not a.database_url:
        subprocess.run([sys.executable, str(REPO / "scripts/demo/pg.py"), "stop"], env=env,
                       capture_output=True)  # fmt: skip
        shutil.rmtree(state, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
