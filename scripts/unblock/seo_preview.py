"""SEO pages and the basket index on real prices, as a validated preview (issues #35, #44).

Two parts, both used by ``.github/workflows/real-day.yml`` after the real day has loaded:

``export``  (imported by ``real_day.py``) runs ``smartcart-catalog export-seo`` and ``basket-index``
            on the real database into a scratch directory, then audits the files
            (``smartcart_catalog.seo_audit``). Nothing is written under ``apps/web``.
``web``     copies an export over ``apps/web/public/seo`` (a throw-away checkout on the runner; the
            committed synthetic snapshot is put back afterwards), builds the production web app
            with a placeholder origin (``https://preview.invalid``), runs the offline
            structured-data validation and the SEO unit tests against it, starts the built site and
            crawls every page the generator made (the checks of ``seo-check.yml``, over all pages
            instead of a sample, plus a scan of the visible text for broken numbers), and, with
            ``--e2e``, the Playwright preview spec (phone width, axe) in Chromium.

The export is a preview, never production data: it goes to a workflow artifact, not to git, and
the site URL ends in ``.invalid`` so the strict site-URL guard (``SEO_STRICT_SITE_URL``) refuses to
build it for a deploy. See docs/seo.md, "SEO on real prices", and docs/real-day-dry-run.md.

    uv run --no-sync python scripts/unblock/seo_preview.py web --export DIR --variant production --out DIR
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from _common import REPO, md_escape, venv_bin, write_text
from _common import run as run_cmd

WEB = REPO / "apps" / "web"
SEO_PUBLIC = WEB / "public" / "seo"
PREVIEW_ORIGIN = "https://preview.invalid"
STATIC_PAGES = ("/methodology", "/basket-index", "/accessibility")
CHECKOUT_LINE = "המחיר הקובע הוא בקופה"

# Text that means a number or a field was rendered wrong.
BROKEN_TEXT = re.compile(
    r"\bNaN\b|\bundefined\b|\bInfinity\b|\[object Object\]|(?<![\w.])null(?![\w.])"
)
ZERO_PRICE = re.compile(r"₪[\s ‎‏]*0(?:[.,]0+)?(?![\d.,])")


# --- export -----------------------------------------------------------------------------------------


def export_variant(env: dict, out_dir: Path, tag: str) -> dict:
    """``export-seo`` and ``basket-index`` into ``out_dir``, then the audit. Never raises: a stage
    that fails is recorded (the run is a measurement)."""
    sys.path.insert(0, str(REPO / "services" / "catalog"))
    cat = venv_bin("smartcart-catalog")
    month = datetime.now(UTC).strftime("%Y-%m")
    info: dict = {"tag": tag, "dir": str(out_dir), "month": month}
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    res = run_cmd([cat, "export-seo", "--out", str(out_dir)], env=env, check=False)
    info["export"] = {"exit": res.returncode, "seconds": round(res.seconds, 2),
                      "stdout": res.stdout[-800:]}  # fmt: skip
    if res.returncode != 0:
        info["error"] = f"export-seo exited {res.returncode}: {res.stderr[-300:]}"
        return info
    # Draft only (no --reviewed-by): the month can never be published from here. Its press report
    # goes beside the export, not into docs/reports.
    res = run_cmd([cat, "basket-index", "--month", month, "--out", str(out_dir),
                   "--reports", str(out_dir / "reports-draft")], env=env, check=False)  # fmt: skip
    info["basket_index"] = {"exit": res.returncode, "seconds": round(res.seconds, 2),
                            "stdout": res.stdout[-1500:]}  # fmt: skip
    try:
        from smartcart_catalog.seo_audit import audit_dir

        audit = audit_dir(out_dir)
        info["audit"] = {k: v for k, v in audit.items() if k != "findings"}
        info["findings"] = audit["findings"][:300]
        products = json.loads((out_dir / "products.json").read_text(encoding="utf-8"))
        info["priced_table"] = [
            {
                "slug": p["slug"], "unit": p["base_unit"], "page": p["has_page"],
                "chains": [
                    [c["chain_name"], c["median_unit_price"], c["min_unit_price"], c["stores"],
                     c["price_valid_from"][:10], c["is_estimated"]]
                    for c in p["prices"]
                ],
            }
            for p in products["products"]
            if p.get("prices")
        ]  # fmt: skip
        info["withheld_table"] = {
            p["slug"]: p["withheld"] for p in products["products"] if p.get("withheld")
        }
    except Exception as exc:  # noqa: BLE001 - recorded, not hidden
        info["error"] = f"audit failed: {exc!r}"
    return info


def render_export(info: dict | None, title: str) -> list[str]:
    """Markdown lines for one exported variant (used by the real-day report and the web job)."""
    if not info:
        return []
    out = [f"### SEO export, {title}", ""]
    if info.get("error"):
        out += [f"**Failed:** {md_escape(info['error'])}", ""]
        return out
    a = info["audit"]
    pages = a["pages"]
    out += [
        "| | |",
        "|---|---|",
        f"| Pages generated | {pages['total']} ({pages['category']} category, {pages['product']} product) |",
        f"| Canonicals priced / unpriced | {a['priced']} / {a['unpriced']} |",
        f"| Product pages priced / unpriced | {a['product_pages_priced']} / {a['product_pages_unpriced']} |",
        f"| Price cells (chain x product), of them estimated | {a['price_cells']}, {a['estimated_cells']} |",
        "| Chains per priced product | "
        + (
            ", ".join(f"{k} chain(s): {v}" for k, v in a["chains_per_priced_product"].items())
            or "-"
        )
        + " |",
        f"| Error-level findings | {a['errors']} |",
        "| Findings by code | "
        + (", ".join(f"{k} {v}" for k, v in a["by_code"].items()) or "none")
        + " |",
        "",
    ]
    basket = a.get("basket") or {}
    if basket.get("month"):
        out += [
            f"Basket index {basket['month']}: **{basket['status']}**, {basket['ranked']} of {basket['chains']} "
            f"chains rank (price every one of {basket['lines']} lines), spread {basket.get('spread_pct')}%.",
            "",
        ]
        if basket.get("lines_priced"):
            out += ["| Chain | Lines priced | Total |", "|---|---|---|"]
            totals = basket.get("totals") or {}
            for name, n in basket["lines_priced"].items():
                total = totals.get(name)
                out.append(
                    f"| {md_escape(name)} | {n} of {basket['lines']} | {'-' if total is None else f'{total:,.2f}'} |"
                )
            out.append("")
        if basket.get("checks"):
            out += ["| Level | Check | Message |", "|---|---|---|"]
            for c in basket["checks"]:
                out.append(f"| {c['level']} | {c['code']} | {md_escape(c['message'])[:300]} |")
            out.append("")
    findings = info.get("findings") or []
    if findings:
        out += ["| Code | Subject | Detail |", "|---|---|---|"]
        for f in findings[:80]:
            out.append(
                f"| {f['code']} | {md_escape(f['subject'])} | {md_escape(f['detail'])[:200]} |"
            )
        if len(findings) > 80:
            out.append(f"| ... | {len(findings) - 80} more | in the JSON |")
        out.append("")
    return out


# --- web: build, validate, crawl ------------------------------------------------------------------------


class Page(HTMLParser):
    """What a search engine and a reader see: head tags, JSON-LD, visible text."""

    def __init__(self) -> None:
        super().__init__()
        self.html: dict = {}
        self.canonical: str | None = None
        self.robots: list[str] = []
        self.title = ""
        self.h1 = 0
        self.times: list[str] = []
        self.jsonld: list[str] = []
        self.links: list[str] = []
        self.text: list[str] = []
        self._in_title = False
        self._in_ld = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.html = a
        elif tag == "link" and (a.get("rel") or "").lower() == "canonical":
            self.canonical = a.get("href")
        elif tag == "meta" and (a.get("name") or "").lower() in ("robots", "googlebot"):
            self.robots.append((a.get("content") or "").lower())
        elif tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "time" and a.get("datetime"):
            self.times.append(a["datetime"])
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "script":
            if (a.get("type") or "").lower() == "application/ld+json":
                self._in_ld = True
                self.jsonld.append("")
            else:
                self._skip += 1
        elif tag == "style":
            self._skip += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            if self._in_ld:
                self._in_ld = False
            elif self._skip:
                self._skip -= 1
        elif tag == "style" and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_ld:
            self.jsonld[-1] += data
        elif not self._skip:
            self.text.append(data)

    @property
    def visible(self) -> str:
        return " ".join(" ".join(self.text).split())


def fetch(url: str) -> tuple[int, dict, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "SmartCart-seo-preview/1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:  # noqa: S310 - localhost only
            return res.status, dict(res.headers), res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, {}, str(exc)


def urls_in(node, found: list[str]) -> list[str]:
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("url", "item") and isinstance(v, str):
                found.append(v)
            else:
                urls_in(v, found)
    elif isinstance(node, list):
        for v in node:
            urls_in(v, found)
    return found


def offers_in(node, found: list[float]) -> list[float]:
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "price" and isinstance(v, int | float):
                found.append(float(v))
            else:
                offers_in(v, found)
    elif isinstance(node, list):
        for v in node:
            offers_in(v, found)
    return found


def crawl(base: str, seo_dir: Path, origin: str, index_unpriced: bool) -> dict:
    """Fetch every generated page from the local server and check what the live ``seo-check``
    checks, for all pages, plus broken numbers, trust lines and agreement with the exported data."""
    rows: list[tuple[str, str, bool, str]] = []

    def record(area: str, check: str, ok: bool, detail: str = "") -> None:
        rows.append((area, check, ok, detail))

    categories = json.loads((seo_dir / "categories.json").read_text(encoding="utf-8"))
    products = json.loads((seo_dir / "products.json").read_text(encoding="utf-8"))
    cat_pages = [c for c in categories["categories"] if c["has_page"]]
    prod_pages = [p for p in products["products"] if p["has_page"]]
    indexable = lambda p: bool(p.get("prices")) or index_unpriced  # noqa: E731

    status, headers, body = fetch(f"{base}/robots.txt")
    record(
        "robots.txt",
        "status 200, text/plain",
        status == 200
        and "text/plain" in headers.get("Content-Type", headers.get("content-type", "")),
        f"{status}",
    )
    disallows = [
        ln.split(":", 1)[1].strip()
        for ln in body.splitlines()
        if ln.lower().startswith("disallow:")
    ]
    record("robots.txt", "does not block the whole site", "/" not in disallows)
    record(
        "robots.txt",
        "names the sitemap on the preview origin",
        f"Sitemap: {origin}/sitemap.xml" in body,
        body[-120:],
    )

    status, _, xml = fetch(f"{base}/sitemap.xml")
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml) if status == 200 else []
    record("sitemap.xml", "status 200", status == 200, f"{status}")
    record(
        "sitemap.xml", "every URL is on the preview origin", all(u.startswith(origin) for u in locs)
    )
    record("sitemap.xml", "no duplicate URLs", len(set(locs)) == len(locs))
    basket = json.loads((seo_dir / "basket-index.json").read_text(encoding="utf-8"))
    basket_draft = any(m.get("status") != "published" for m in basket.get("months", []))
    # a preview build that shows a draft month is noindex and so not in the sitemap
    expected = {
        f"{origin}{p}" for p in ("/", *STATIC_PAGES) if not (p == "/basket-index" and basket_draft)
    }
    expected |= {f"{origin}/c/{c['slug']}" for c in cat_pages}
    expected |= {f"{origin}/p/{p['slug']}" for p in prod_pages if indexable(p)}
    record("sitemap.xml", "lists exactly the indexable pages", set(locs) == expected,
           f"{len(locs)} listed, {len(expected)} expected, "
           f"missing {sorted(expected - set(locs))[:3]}, extra {sorted(set(locs) - expected)[:3]}")  # fmt: skip

    paths = [
        *STATIC_PAGES,
        *[f"/c/{c['slug']}" for c in cat_pages],
        *[f"/p/{p['slug']}" for p in prod_pages],
    ]
    by_slug = {p["slug"]: p for p in products["products"]}
    broken_text: list[str] = []
    zero_prices: list[str] = []
    html_sizes: list[int] = []
    for path in paths:
        status, headers, html = fetch(f"{base}{path}")
        record(path, "status 200", status == 200, f"{status}")
        if status != 200:
            continue
        html_sizes.append(len(html))
        pg = Page()
        pg.feed(html)
        record(
            path, 'lang="he" dir="rtl"', pg.html.get("lang") == "he" and pg.html.get("dir") == "rtl"
        )
        record(
            path,
            "a <title> and exactly one <h1>",
            bool(pg.title.strip()) and pg.h1 == 1,
            f"h1 {pg.h1}",
        )
        record(
            path,
            "canonical is this page on the preview origin",
            pg.canonical == f"{origin}{path}",
            f"{pg.canonical}",
        )
        product = by_slug.get(path[3:]) if path.startswith("/p/") else None
        should_index = (
            indexable(product)
            if product is not None
            else not (path == "/basket-index" and basket_draft)
        )
        noindex = any("noindex" in r for r in pg.robots)
        record(
            path,
            "robots meta matches the sitemap",
            noindex != should_index,
            f"noindex={noindex}, in sitemap={should_index}",
        )
        lds, bad = [], 0
        for raw in pg.jsonld:
            try:
                parsed = json.loads(raw)
            except ValueError:
                bad += 1
                continue
            lds.extend(parsed if isinstance(parsed, list) else [parsed])
        record(path, "JSON-LD present, parses, URLs on the preview origin",
               bool(pg.jsonld) and bad == 0 and all(u.startswith(origin) for u in urls_in(lds, [])))  # fmt: skip
        text = pg.visible
        record(
            path,
            f"says '{CHECKOUT_LINE}' and links the methodology",
            CHECKOUT_LINE in text and "/methodology" in pg.links,
        )
        if BROKEN_TEXT.search(text):
            broken_text.append(f"{path}: {BROKEN_TEXT.search(text).group(0)!r}")  # type: ignore[union-attr]
        if ZERO_PRICE.search(text):
            zero_prices.append(path)
        record(path, "a visible update date (<time datetime>)", bool(pg.times))
        if product is not None:
            prices = product.get("prices") or []
            ld_prices = sorted(
                offers_in([d.get("offers") for d in lds if d.get("@type") == "Product"], [])
            )
            expect = (
                sorted(c["median_unit_price"] for c in prices for _ in (0, 1)) if prices else []
            )
            # every Offer carries the price twice (the Offer and its UnitPriceSpecification)
            record(path, "JSON-LD offers equal the exported prices (and exist only with prices)",
                   ld_prices == expect, f"page {ld_prices[:4]}, export {expect[:4]}")  # fmt: skip
            for c in prices:
                if c["chain_name"] not in text:
                    record(path, f"chain {c['chain_name']} is on the page", False)
            if prices:
                record(path, "one update date per priced chain, as <time>", len(pg.times) >= len(prices),
                       f"{len(pg.times)} <time> for {len(prices)} chains")  # fmt: skip
    record(
        "all pages",
        "no NaN, undefined, Infinity or null in the visible text",
        not broken_text,
        "; ".join(broken_text[:5]),
    )
    record(
        "all pages",
        "no price of 0 shekels in the visible text",
        not zero_prices,
        ", ".join(zero_prices[:5]),
    )
    failed = [r for r in rows if not r[2]]
    return {
        "pages_fetched": len(paths),
        "sitemap_urls": len(locs),
        "checks": len(rows),
        "failed": [{"area": a, "check": c, "detail": d} for a, c, ok, d in failed],
        "largest_html_bytes": max(html_sizes, default=0),
        "median_html_bytes": sorted(html_sizes)[len(html_sizes) // 2] if html_sizes else 0,
    }


def npm(args: list[str], env: dict, timeout: int = 1800) -> subprocess.CompletedProcess:
    print("+ npm " + " ".join(args), file=sys.stderr, flush=True)
    return subprocess.run(["npm", *args], cwd=WEB, env={**os.environ, **env}, capture_output=True,
                          text=True, timeout=timeout)  # fmt: skip


def vitest_summary(path: Path) -> dict:
    if not path.exists():
        return {"error": "no vitest report was written"}
    doc = json.loads(path.read_text(encoding="utf-8"))
    failed = [
        {"file": Path(t["name"]).name, "test": a.get("fullName", "")[:160],
         "message": (a.get("failureMessages") or [""])[0][:400]}
        for t in doc.get("testResults", [])
        for a in t.get("assertionResults", [])
        if a.get("status") == "failed"
    ]  # fmt: skip
    return {"total": doc.get("numTotalTests"), "passed": doc.get("numPassedTests"),
            "failed": doc.get("numFailedTests"), "files": doc.get("numTotalTestSuites"),
            "failures": failed[:20]}  # fmt: skip


def web(args: argparse.Namespace) -> dict:
    export = args.export.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    res: dict = {"variant": args.variant, "origin": PREVIEW_ORIGIN,
                 "index_unpriced": args.index_unpriced, "steps": {}}  # fmt: skip
    env = {
        "NEXT_PUBLIC_SITE_URL": PREVIEW_ORIGIN,
        "NEXT_PUBLIC_INDEX_UNPRICED": "1" if args.index_unpriced else "0",
        # shows the draft basket-index month under its draft label; a build with this set cannot
        # pass the strict site-URL guard, so it cannot be deployed (apps/web/src/features/seo/config.ts)
        "SEO_PREVIEW_DRAFTS": "1",
        "NEXT_TELEMETRY_DISABLED": "1",
        "CI": "true",
    }
    # The unit tests assume the default settings (they run both values of the index setting and the
    # strict site-URL guard themselves), so they do not see the build's preview switches.
    test_env = {"NEXT_PUBLIC_SITE_URL": PREVIEW_ORIGIN, "CI": "true"}
    backup = Path(tempfile.mkdtemp(prefix="seo-snapshot-"))
    shutil.copytree(SEO_PUBLIC, backup / "seo")
    server: subprocess.Popen | None = None
    try:
        # the export replaces the committed snapshot for this build only
        shutil.rmtree(SEO_PUBLIC)
        shutil.copytree(export, SEO_PUBLIC, ignore=shutil.ignore_patterns("reports-draft"))
        t0 = time.monotonic()
        build = npm(["run", "build"], env)
        res["steps"]["build"] = {"exit": build.returncode, "seconds": round(time.monotonic() - t0, 1),
                                 "tail": (build.stdout + build.stderr)[-1200:]}  # fmt: skip
        if build.returncode != 0:
            return res
        report = out / f"vitest-{args.variant}.json"
        t0 = time.monotonic()
        vt = npm(["exec", "--", "vitest", "run", "tests/unit/structured-data.test.ts",
                  "tests/unit/structured-data-config.test.ts", "src/features/seo",
                  "--reporter=json", f"--outputFile={report}"], test_env)  # fmt: skip
        res["steps"]["vitest"] = {"exit": vt.returncode, "seconds": round(time.monotonic() - t0, 1),
                                  **vitest_summary(report)}  # fmt: skip
        port = args.port
        server = subprocess.Popen(
            ["node", "node_modules/next/dist/bin/next", "start", "-p", str(port)],
            cwd=WEB, env={**os.environ, **env}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )  # fmt: skip
        base = f"http://localhost:{port}"
        for _ in range(60):
            if fetch(f"{base}/robots.txt")[0] == 200:
                break
            time.sleep(1)
        t0 = time.monotonic()
        res["steps"]["crawl"] = {**crawl(base, SEO_PUBLIC, PREVIEW_ORIGIN, args.index_unpriced),
                                 "seconds": round(time.monotonic() - t0, 1)}  # fmt: skip
        if args.e2e:
            t0 = time.monotonic()
            e2e = npm(["exec", "--", "playwright", "test", "tests/e2e/seo-preview.spec.ts",
                       "--reporter=line"], {**env, "SEO_PREVIEW": "1",
                                            "E2E_PORT": str(port + 1)})  # fmt: skip
            res["steps"]["e2e"] = {"exit": e2e.returncode, "seconds": round(time.monotonic() - t0, 1),
                                   "tail": (e2e.stdout + e2e.stderr)[-1500:]}  # fmt: skip
    finally:
        if server is not None:
            try:
                os.killpg(server.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        shutil.rmtree(SEO_PUBLIC, ignore_errors=True)
        shutil.copytree(backup / "seo", SEO_PUBLIC)
        shutil.rmtree(backup, ignore_errors=True)
    return res


def render_web(res: dict) -> list[str]:
    out = [f"### Web build and checks, {res['variant']} export (origin `{res['origin']}`, "
           f"`NEXT_PUBLIC_INDEX_UNPRICED={'1' if res['index_unpriced'] else '0'}`)", ""]  # fmt: skip
    if res.get("error"):
        out += [f"**The preview step crashed:** `{md_escape(res['error'])}`", ""]
    s = res["steps"]
    b = s.get("build", {})
    out.append(
        f"- `next build`: {'passed' if b.get('exit') == 0 else '**FAILED**'} in {b.get('seconds')} s"
    )
    if b.get("exit") not in (0, None):
        out += ["", "```", b.get("tail", ""), "```"]
    v = s.get("vitest")
    if v:
        out.append(
            f"- Structured-data validation and SEO unit tests: {v.get('passed')} of {v.get('total')} passed, "
            f"**{v.get('failed')} failed** ({v.get('seconds')} s)"
        )
        for f in v.get("failures", []):
            out.append(
                f"  - {md_escape(f['file'])}: {md_escape(f['test'])}: {md_escape(f['message'])[:240]}"
            )
    c = s.get("crawl")
    if c:
        out.append(
            f"- Crawl of every generated page: {c['pages_fetched']} pages, {c['sitemap_urls']} URLs in the sitemap, "
            f"{c['checks']} checks, **{len(c['failed'])} failed**; HTML median {c['median_html_bytes']:,} B, "
            f"largest {c['largest_html_bytes']:,} B"
        )
        for f in c["failed"][:40]:
            out.append(
                f"  - `{f['area']}`: {md_escape(f['check'])} ({md_escape(f['detail'])[:200]})"
            )
        if len(c["failed"]) > 40:
            out.append(f"  - ... {len(c['failed']) - 40} more in the JSON")
    e = s.get("e2e")
    if e:
        out.append(
            f"- Playwright preview spec (390 px, axe): {'passed' if e['exit'] == 0 else '**FAILED**'} in {e['seconds']} s"
        )
        if e["exit"] != 0:
            out += ["", "```", e["tail"], "```"]
    out.append("")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("web", help="build the web app from an export and check the pages")
    w.add_argument("--export", type=Path, required=True)
    w.add_argument("--variant", required=True)
    w.add_argument("--out", type=Path, required=True)
    w.add_argument("--port", type=int, default=3210)
    w.add_argument("--index-unpriced", action="store_true",
                   help="NEXT_PUBLIC_INDEX_UNPRICED=1 (default 0: unpriced pages are noindex)")  # fmt: skip
    w.add_argument("--e2e", action="store_true", help="also run tests/e2e/seo-preview.spec.ts")
    args = ap.parse_args(argv)
    try:
        res = web(args)
    except Exception as exc:  # noqa: BLE001 - a measurement: record it and write what exists
        res = {"variant": args.variant, "origin": PREVIEW_ORIGIN,
               "index_unpriced": args.index_unpriced, "steps": {}, "error": repr(exc)}  # fmt: skip
    out = args.out
    write_text(
        out / f"seo-web-{args.variant}.json", json.dumps(res, ensure_ascii=False, indent=2) + "\n"
    )
    write_text(out / f"seo-web-{args.variant}.md", "\n".join(render_web(res)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
