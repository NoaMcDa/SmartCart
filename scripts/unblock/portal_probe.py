"""Probe the ten D13 transparency portals, fetch one Stores, one PriceFull and one PromoFull
file per chain, and run every fetched file through the adapter, the quality gates and the loader
(issues #32, #47, #53, #57, #60). What ``.github/workflows/portal-probe.yml`` runs.

    # 1. network: reachability, Cerberus login, downloads (no database)
    uv run --no-sync python scripts/unblock/portal_probe.py probe --out probe/
    # 2. database: the real Scheduler path (download tracking, adapter, gates, loader)
    DATABASE_URL=... uv run --no-sync python scripts/unblock/portal_probe.py gate \\
        --files probe/files --probe probe/probe.json --out probe-report.md --json-out probe.json

``gate`` without ``--probe`` takes any directory laid out as ``<slug>/<portal filename>``, so
``--files services/ingest/tests/fixtures`` runs the synthetic fixtures through the same path
(that is how this script is tested without portal access; those files are past the stale-date
limit, so the gate column shows the gate working).

Only the legally mandated transparency portals are contacted, and downloads go through the
pinned upstream scraper via ``smartcart_ingest.adapters.fetch_fixtures``, never a chain's online
store. Downloaded files are untrusted data: they are read only by the chain adapters, inside
the same Scheduler path the VPS uses (no bypass of the gates). The probe is a measurement: it
exits 0 whatever the portals answer, and non-zero only when the script itself cannot run.
"""

from __future__ import annotations

import argparse
import ftplib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from _common import REPO, git_sha, md_escape, write_text

ISRAEL = ZoneInfo("Asia/Jerusalem")
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
CERBERUS_HOST = "url.retail.publishedprices.co.il"
KINDS = ("stores", "price_full", "promo_full")


@dataclass(frozen=True)
class Portal:
    slug: str
    name: str
    url: str
    ftp_user: str | None = None  # Cerberus: FTP over TLS, empty password (upstream scrapers)


# The ten D13 chains. URLs and Cerberus users are the ones il_supermarket_scarper 1.0.15 uses
# (scrappers/*.py), the same hosts as infra/smoke/check_portals.sh.
PORTALS: tuple[Portal, ...] = (
    Portal("shufersal", "Shufersal", "https://prices.shufersal.co.il/"),
    Portal("ramilevy", "Rami Levy", f"https://{CERBERUS_HOST}/", "RamiLevi"),
    Portal("victory", "Victory", "https://laibcatalog.co.il/"),
    Portal("mega", "Yeinot Bitan and Carrefour", "https://prices.carrefour.co.il/"),
    Portal("hazihinam", "Hazi Hinam", "https://shop.hazi-hinam.co.il/Prices"),
    Portal("tivtaam", "Tiv Taam", f"https://{CERBERUS_HOST}/", "TivTaam"),
    Portal("osherad", "Osher Ad", f"https://{CERBERUS_HOST}/", "osherad"),
    Portal("yohananof", "Yohananof", f"https://{CERBERUS_HOST}/", "yohananof"),
    Portal("machsanei_hashuk", "Machsanei Hashuk", "https://laibcatalog.co.il/"),
    Portal("king_store", "King Store", "http://kingstore.binaprojects.com/"),
)
BY_SLUG = {p.slug: p for p in PORTALS}


# --- network probes ---------------------------------------------------------------------------------


def classify(code: int) -> str:
    """Same buckets as check_portals.sh."""
    if code == 0:
        return "UNREACHABLE"
    if code in (403, 429):
        return "BLOCKED?"
    if 200 <= code < 400:
        return "OK"
    if code >= 500:
        return "ERROR"
    return "REACHABLE"


def http_status(url: str, timeout: float) -> int:
    """HTTP status of ``url`` (0 when the connection fails). HEAD first, then a one-byte GET,
    because some portals answer HEAD with 403, 405 or 501."""

    def once(method: str) -> int:
        headers = {"User-Agent": UA}
        if method == "GET":
            headers["Range"] = "bytes=0-0"
        req = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed URLs
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code
        except (urllib.error.URLError, OSError, ValueError):
            return 0

    code = once("HEAD")
    if code in (0, 403, 405, 501):
        code = once("GET")
    return code


def _ftp_try(host: str, user: str, timeout: float, context: ssl.SSLContext | None) -> str | None:
    """None when the FTP-over-TLS login works with ``context``, else the error."""
    try:
        # ftplib.FTP_TLS(host, user, passwd) connects, sends AUTH TLS and logs in, as upstream.
        ftp = ftplib.FTP_TLS(host, user, "", timeout=timeout, context=context)
        try:
            ftp.voidcmd("NOOP")  # upstream sends no PROT P either; it lists over the clear channel
        finally:
            try:
                ftp.quit()
            except (ftplib.Error, OSError):
                ftp.close()
    except (ftplib.Error, OSError, EOFError) as exc:
        return f"{type(exc).__name__}: {str(exc)[:160]}"
    return None


def ftp_login(host: str, user: str, timeout: float) -> str:
    """``ok`` when the Cerberus login works the way the upstream scraper logs in, otherwise
    ``failed: <reason>``. Lists nothing.

    Upstream (``il_supermarket_scarper.utils.network.connection._open_ftp_tls``) opens
    ``ftplib.FTP_TLS(host, user, password)`` with no context, which makes ftplib use
    ``ssl._create_stdlib_context()``, an unverified context: the certificate is neither checked
    against a CA nor against the host name. The portal's certificate does not match
    ``url.retail.publishedprices.co.il`` (seen from a GitHub runner, 2026-10-08), so a verifying
    client fails where the scraper succeeds. The login check therefore uses upstream's mode, and
    a second, verifying handshake only annotates the result."""
    err = _ftp_try(host, user, timeout, None)
    if err:
        return f"failed: {err}"
    if _ftp_try(host, user, timeout, ssl.create_default_context()):
        return "ok (certificate not verified, as upstream; it fails verification)"
    return "ok"


def fetch_one(
    slug: str,
    kind: str,
    work: Path,
    files: Path,
    timeout: float,
    store: int | None = None,
    candidates: int = 1,
) -> dict:
    """One file of ``kind`` for the chain through ``fetch_fixtures`` in a subprocess (so a hung
    portal is killed), moved to ``files/<slug>/``. ``store`` asks for that store's file only,
    ``candidates`` keeps the largest of that many. Returns the manifest entry."""
    out = work / f"{slug}-{kind}"
    shutil.rmtree(out, ignore_errors=True)
    cmd = [sys.executable, "-m", "smartcart_ingest.adapters.fetch_fixtures", slug,
           "--kind", kind, "--out", str(out), "--timeout", str(timeout)]  # fmt: skip
    if store:
        cmd += ["--store", str(store)]
    if candidates > 1:
        cmd += ["--candidates", str(candidates)]
    started = time.monotonic()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 60, cwd=REPO)
        log = (res.stdout + res.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        return {"kind": kind, "error": f"timed out after {timeout + 60:.0f}s"}
    entry: dict = {"kind": kind, "error": "no manifest written"}
    manifest = out / "manifest.json"
    if manifest.exists():
        entries = json.loads(manifest.read_text(encoding="utf-8")).get(slug) or []
        entry = entries[0] if entries else entry
    entry["seconds"] = round(time.monotonic() - started, 1)
    if "file" in entry:
        src = out / slug / entry["file"]
        dest = files / slug
        dest.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), dest / entry["file"])
    elif "error" in entry:
        entry["log_tail"] = log[-600:]
    return entry


PROMO_CANDIDATES = 10
"""PromoFull files downloaded per chain; the largest is kept (a store's file can hold one promotion
or thousands, and the first one listed is arbitrary)."""


def fetch_chain(
    slug: str,
    work: Path,
    files: Path,
    timeout: float,
    fetch=fetch_one,  # noqa: ANN001
) -> dict:
    """The chain's Stores, PromoFull and PriceFull files, in the order of ``KINDS`` in the result.

    The PromoFull comes first (the largest of ``PROMO_CANDIDATES``) and the PriceFull is then
    asked for **the same store** (the store code in the promo file's name): a promotion's prices
    can only be checked against the shelf prices of its own store, and the first PriceFull the
    portal lists is usually another store's (Shufersal, Yohananof). When that store has no
    PriceFull the first one listed is taken and the entry says so (``same_store`` false)."""
    got: dict[str, dict] = {"stores": fetch(slug, "stores", work, files, timeout)}
    promo = got["promo_full"] = fetch(
        slug, "promo_full", work, files, timeout, candidates=PROMO_CANDIDATES
    )
    store = None
    code = str(promo.get("store_code") or "")
    if "file" in promo and code.isdigit() and int(code) > 0:
        store = int(code)
    price = fetch(slug, "price_full", work, files, timeout, store=store) if store else {}
    if store and "file" in price:
        price["same_store"] = True
    else:
        price = fetch(slug, "price_full", work, files, timeout)
        price["same_store"] = False
        if store:
            price["wanted_store"] = store
    got["price_full"] = price
    ordered = {kind: got[kind] for kind in KINDS}
    for kind, entry in ordered.items():
        print(f"  {kind:10} {json.dumps(entry, ensure_ascii=False)}", flush=True)
    return ordered


def probe(out: Path, slugs: Sequence[str], timeout: float, skip_downloads: bool) -> dict:
    files = out / "files"
    work = out / "work"
    files.mkdir(parents=True, exist_ok=True)
    result: dict = {
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "runner": os.environ.get("RUNNER_NAME") or os.uname().nodename,
        "chains": {},
    }
    ftp_cache: dict[str, str] = {}
    for slug in slugs:
        portal = BY_SLUG[slug]
        code = http_status(portal.url, timeout=20)
        row: dict = {
            "name": portal.name,
            "portal_url": portal.url,
            "http_status": code,
            "reachable": classify(code),
            "login": "n/a",
            "downloads": {},
        }
        if portal.ftp_user:
            if portal.ftp_user not in ftp_cache:
                ftp_cache[portal.ftp_user] = ftp_login(CERBERUS_HOST, portal.ftp_user, timeout=30)
            row["login"] = ftp_cache[portal.ftp_user]
        print(f"{slug:18} http {code:<3} {row['reachable']:<11} login {row['login']}", flush=True)
        if not skip_downloads:
            row["downloads"] = fetch_chain(slug, work, files, timeout)
        result["chains"][slug] = row
    shutil.rmtree(work, ignore_errors=True)
    result["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    (out / "probe.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


# --- gates: the real Scheduler path -------------------------------------------------------------------


@dataclass
class _OneFile:
    chain_id: str
    name: str
    kind: str
    data: bytes


class OneFileFetcher:
    """A portal that lists exactly the one file being processed (cf. scripts/demo)."""

    def __init__(self) -> None:
        self.current: _OneFile | None = None

    def list_files(self, chain_id, kinds=None, since=None):  # noqa: ANN001 - Fetcher protocol
        from smartcart_ingest.download import RemoteFile

        f = self.current
        if f is None or f.chain_id != chain_id or (kinds and f.kind not in kinds):
            return []
        return [RemoteFile(chain_id=chain_id, name=f.name, kind=f.kind)]  # type: ignore[arg-type]

    def fetch(self, remote) -> bytes:  # noqa: ANN001
        assert self.current is not None and remote.name == self.current.name
        return self.current.data


class _Sink:
    def __init__(self) -> None:
        self.alerts: list = []

    def send(self, alert) -> None:  # noqa: ANN001
        self.alerts.append(alert)


def pick_files(files: Path, slug: str, adapter) -> dict[str, Path]:  # noqa: ANN001
    """The newest Stores, PriceFull and PromoFull file under ``files/<slug>`` (by the adapter's
    filename parser; names it does not recognise are ignored)."""
    best: dict[str, tuple[datetime, Path]] = {}
    folder = files / slug
    if not folder.is_dir():
        return {}
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        try:
            info = adapter.parse_filename(path.name)
        except Exception:  # noqa: BLE001 - not a portal file (expected.json, a README)
            continue
        if info.kind not in KINDS:
            continue
        when = info.published_at or datetime.min.replace(tzinfo=ISRAEL)
        if info.kind not in best or when > best[info.kind][0]:
            best[info.kind] = (when, path)
    return {k: v[1] for k, v in best.items()}


_PROFILE_SKIP = frozenset({
    "promotionid", "promotiondescription", "promotionupdatedate", "confidence",
    "confidence_reasons", "additional_restrictions",
})  # fmt: skip
"""Raw promo fields whose values are ids, free text or per-promo numbers: not histogrammed."""
_PROFILE_MAX_DISTINCT = 12


def _fmt_value(value: object) -> str:
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return str(value)


def _shelf_check(groups: list, shelf: dict, check: Counter, bad: list, pid: str | None) -> None:
    """Count, for a trigger group (``RewardType`` 0) and a reward group with a rate, the items
    whose shelf price is known: trigger price = shelf, reward price = shelf x (1 - rate)."""
    from decimal import Decimal

    def num(v: str | None) -> Decimal | None:
        try:
            return Decimal(v) if v else None
        except Exception:  # noqa: BLE001
            return None

    trig = [g for g in groups if {i.get("rewardtype") for i in g[1]} == {"0"}]
    rew = [g for g in groups if g not in trig]
    if len(trig) != 1 or len(rew) != 1:
        return
    mates = {i.get("itemcode"): i for i in trig[0][1]}
    for item in rew[0][1]:
        code = item.get("itemcode")
        base, mate = shelf.get(code), mates.get(code)
        rate, price = num(item.get("discountrate")), num(item.get("discountedprice"))
        if base is None or mate is None or rate is None or price is None:
            continue
        check["items_with_shelf"] += 1
        want = Decimal(str(base)) * (1 - rate / 100)
        ok_reward = abs(want - price) <= Decimal("0.02")
        check["reward_equals_shelf_x_rate"] += ok_reward
        tprice = num(mate.get("discountedprice"))
        if tprice is not None:
            check["trigger_priced"] += 1
            check["trigger_equals_shelf"] += abs(Decimal(str(base)) - tprice) <= Decimal("0.02")
        if not ok_reward or (
            tprice is not None and abs(Decimal(str(base)) - tprice) > Decimal("0.02")
        ):
            bad.append({"promo": pid, "item": code, "shelf": str(base), "trigger": str(tprice),
                        "rate": str(rate), "reward": str(price)})  # fmt: skip


def _single_check(items: list, shelf: dict, check: Counter, bad: list, pid: str | None) -> None:
    """Count, for the items of a one-group promotion whose shelf price is known, whether the
    price per unit (``DiscountedPrice / MinQty``) is ``shelf x (1 - DiscountRate / 100)``, and
    whether it is below the shelf price. Weighed items and all-zeros "any item" rows are left
    out (their quantity is a step, not a pack)."""
    from decimal import Decimal

    def num(v: str | None) -> Decimal | None:
        try:
            return Decimal(v) if v else None
        except Exception:  # noqa: BLE001
            return None

    for item in items:
        code = item.get("itemcode")
        base = shelf.get(code)
        qty, rate = num(item.get("minqty")), num(item.get("discountrate"))
        price = num(item.get("discountedprice"))
        if (base is None or item.get("bisweighted") == "1" or set(code or "0") == {"0"}
                or qty is None or qty <= 0 or rate is None or price is None):  # fmt: skip
            continue
        base = Decimal(str(base))
        unit = price / qty
        check["single_items_with_shelf"] += 1
        gap = abs(base * (1 - rate / 100) - unit)
        check["single_unit_equals_shelf_x_rate"] += gap <= Decimal("0.02")
        # A whole-percent rate is a rounded number: the price may be off by up to half a point.
        within = gap <= base * Decimal("0.005") + Decimal("0.02")
        check["single_unit_within_rate_rounding"] += within
        check["single_unit_below_shelf"] += unit < base
        if not within:
            bad.append({"promo": pid, "item": code, "shelf": str(base), "min_qty": str(qty),
                        "rate": str(rate), "price": str(price)})  # fmt: skip


def promo_shapes(
    data: bytes, examples: int = 3, limit_items: int = 3, shelf: dict | None = None
) -> dict:
    """The shapes of the real promotions that are not a plain single-group price, bundle or
    percent (#47): more than one group, a weekday restriction. Per promotion a signature is
    built from what the file says (days, coupon, per group the reward types, item counts, quantity
    and rate, and how the groups' item sets relate); the result is a histogram of signatures, a
    few promotions in full per signature, and the ``PromotionDays`` values against descriptions
    so the day numbering can be read off. With ``shelf`` (item code -> price, from the same
    store's PriceFull) every two-group promotion whose reward group carries a rate is checked: the
    trigger item's ``DiscountedPrice`` against the shelf price and the reward item's price against
    ``shelf x (1 - rate / 100)`` (``shelf_check``). Pure; copies text and numbers, executes
    nothing."""
    from smartcart_ingest import xmlutil
    from smartcart_ingest.adapters._common import ALL_ROW_TAGS, CONTAINERS, containers_in

    decoded = xmlutil.decode(data)
    root = xmlutil.read_header(decoded.data, ALL_ROW_TAGS)
    row_tags = {r for c, (g, r) in CONTAINERS.items() if g == "promo" and c in containers_in(root)}
    full_week = set("1234567")
    sigs: Counter[str] = Counter()
    shown: dict[str, list] = {}
    days_seen: Counter[str] = Counter()
    day_examples: dict[str, list] = {}
    check: Counter[str] = Counter()
    check_bad: list = []
    for row in xmlutil.iter_rows(decoded.data, row_tags):
        f = xmlutil.scalar_children(row)
        days = f.get("promotiondays", "").replace(" ", "")
        days_seen[days or "(empty)"] += 1
        restricted = bool(days) and set(days.split(",")) != full_week
        if restricted:
            bucket = day_examples.setdefault(days, [])
            if len(bucket) < 6:
                bucket.append({
                    "id": f.get("promotionid"), "description": f.get("promotiondescription", "")[:80],
                    "start": f.get("promotionstartdatetime"), "end": f.get("promotionenddatetime"),
                })  # fmt: skip
        groups = []
        for el in row.iter():
            if xmlutil.localname(el) == "Group":
                gf = xmlutil.scalar_children(el)
                items = [xmlutil.scalar_children(i) for i in el.iter()
                         if xmlutil.localname(i) == "PromotionItem"]  # fmt: skip
                groups.append((gf, items))
        if shelf and len(groups) == 1:
            _single_check(groups[0][1], shelf, check, check_bad, f.get("promotionid"))
        if len(groups) == 1 and not restricted:
            continue
        if shelf and len(groups) == 2:
            _shelf_check(groups, shelf, check, check_bad, f.get("promotionid"))
        sets = [{i.get("itemcode") for i in items} for _, items in groups]
        if len(sets) < 2:
            relation = "-"
        elif all(s == sets[0] for s in sets):
            relation = "same_items"
        elif any(s <= t for s in sets for t in sets if s is not t):
            relation = "nested_items"
        else:
            relation = "different_items"
        parts = []
        for gf, items in groups:
            kinds = sorted({i.get("rewardtype", "?") for i in items})
            qty = sorted({i.get("minqty", "?").rstrip("0").rstrip(".") for i in items})[:3]
            rate = sorted({i.get("discountrate", "") for i in items} - {""})[:3]
            wild = any(set(i.get("itemcode", "")) == {"0"} for i in items)
            parts.append(
                f"[rt={'/'.join(kinds)} q={'/'.join(qty)} r={'/'.join(rate) or '-'}"
                f"{' WILD' if wild else ''}{' MINBUY' if gf.get('minpurchaseamount') else ''}"
                f"{' W' if any(i.get('bisweighted') == '1' for i in items) else ''}]"
            )
        sig = (
            f"groups={len(groups)} {relation} days={'restricted' if restricted else 'all'}"
            f" coupon={f.get('additionaliscoupon', '')} " + "".join(parts)
        )
        sigs[sig] += 1
        bucket = shown.setdefault(sig, [])
        if len(bucket) < examples:
            bucket.append({
                "id": f.get("promotionid"), "description": f.get("promotiondescription", "")[:80],
                "days": days, "min_offered": f.get("minnoofitemoffered"),
                "redemption_limit": f.get("redemptionlimit"), "gift": f.get("isgiftitem"),
                "allow_multiple": f.get("allowmultiplediscounts"),
                "groups": [{
                    "min_purchase": gf.get("minpurchaseamount"), "type": gf.get("discounttype"),
                    "n": len(items),
                    "items": [{k: v for k, v in i.items()
                               if k in ("itemcode", "rewardtype", "minqty", "maxqty",
                                        "discountrate", "discountedprice",
                                        "discountedpricepermida") and v}
                              for i in items[:limit_items]],
                } for gf, items in groups],
            })  # fmt: skip
    return {
        "signatures": dict(sigs.most_common()),
        "examples": shown,
        "days": dict(days_seen.most_common()),
        "day_examples": day_examples,
        "shelf_check": {**check, "mismatches": check_bad[:8]} if shelf else None,
    }


CLUB_TEXT_CHARS = 3000
"""A ClubID text longer than this is cut in the log line (its full length is kept); the JSON the
probe uploads holds it whole."""
CLUB_LINE_CHARS = 6000
"""``PROMO_CLUBS`` lines are cut into parts of about this many characters."""


def _club_atoms(value: str) -> list[str]:
    """The club names a ClubID value mentions, for a count per name: the names of an expression
    and, for ``<n> - <label>``, the label split at ``&`` and ``|`` too (Shufersal joins its card
    clubs in one label). Only a measurement; the mapping never splits a label."""
    from smartcart_ingest.adapters.clubs import value_names

    atoms: list[str] = []
    for name in value_names(value):
        for part in re.split(r"[&|]", name):
            part = " ".join(part.split())
            if part and part not in atoms:
                atoms.append(part)
    return atoms


def club_histogram(parsed) -> dict:  # noqa: ANN001
    """Every distinct ``ClubID`` text of the promotions (``raw['club_ids']``, as the file wrote it,
    trimmed) with the number of promotions that carry it and the rule the chain's club table makes
    of it today, and a count per club name. Pure."""
    from smartcart_ingest.adapters.clubs import resolve_value

    chain = parsed.raw.chain_id
    values: Counter[str] = Counter()
    names: Counter[str] = Counter()
    without = 0
    for promo in parsed.promos:
        ids = [str(v).strip() for v in promo.raw.get("club_ids") or [] if str(v).strip()]
        without += not ids
        for value in ids:
            values[value] += 1
            for atom in _club_atoms(value):
                names[atom] += 1
    return {
        "promos": len(parsed.promos),
        "without_club_id": without,
        "distinct_values": len(values),
        "distinct_names": len(names),
        "values": [
            {
                "text": text,
                "n": n,
                "rule": resolve_value(chain, text) if not text.startswith("0") else "everyone",
            }  # fmt: skip
            for text, n in values.most_common()
        ],
        "names": [[name, n] for name, n in names.most_common()],
    }


def promo_profile(parsed, data: bytes, shelf: dict | None = None) -> dict:  # noqa: ANN001
    """What a real PromoFull holds, as the adapter read it: reward types, club ids, a value
    histogram of every raw field with few distinct values (``RewardType``, ``DiscountType``,
    ``MinQty``, ``AllowMultipleDiscounts`` ...), date windows against the file's publication
    time, the stores promos name, items per promotion, the confidence rubric's reasons, the
    element layout of the file (``promo_layout``) and a few sample promotions. Pure: no
    database, no execution of anything from the file."""
    from statistics import median

    from smartcart_ingest.adapters.fetch_fixtures import promo_layout

    promos = parsed.promos
    published = parsed.raw.published_at
    raw_values: dict[str, Counter] = {}
    for promo in promos:
        for key, value in promo.raw.items():
            if key in _PROFILE_SKIP or isinstance(value, dict):
                continue
            raw_values.setdefault(key, Counter())[_fmt_value(value)] += 1
    fields: dict[str, object] = {}
    for key, counter in sorted(raw_values.items()):
        if len(counter) <= _PROFILE_MAX_DISTINCT:
            fields[key] = dict(counter.most_common())
        else:
            fields[key] = {"distinct": len(counter), "examples": list(counter)[:3]}
    restrictions: dict[str, Counter] = {}
    for promo in promos:
        for key, value in (promo.raw.get("additional_restrictions") or {}).items():
            restrictions.setdefault(key, Counter())[str(value)] += 1
    per_item = [len(p.item_codes) for p in promos]
    by_reward: dict[str, list] = {}
    for promo in promos:
        by_reward.setdefault(promo.reward_type, []).append(promo)
    samples = []
    for reward, group in sorted(by_reward.items()):
        for promo in group[:2]:
            samples.append({
                "promo_id": promo.promo_id, "store": promo.store_code,
                "description": promo.description[:90], "reward_type": reward,
                "reward_value": str(promo.reward_value), "min_qty": str(promo.min_qty),
                "max_qty": str(promo.max_qty), "club": promo.club_name, "items": len(promo.item_codes),
                "starts_at": promo.starts_at.isoformat(timespec="minutes") if promo.starts_at else None,
                "ends_at": promo.ends_at.isoformat(timespec="minutes") if promo.ends_at else None,
                "hours": promo.hours, "confidence": promo.raw.get("confidence"),
                "raw": {k: v for k, v in promo.raw.items()
                        if k not in ("promotiondescription", "confidence_reasons")},
            })  # fmt: skip
    try:
        layout = promo_layout(data)
    except ValueError as exc:
        layout = {"error": str(exc)[:200]}
    try:
        shapes = promo_shapes(data, shelf=shelf)
    except Exception as exc:  # noqa: BLE001 - extra; never fail the probe
        shapes = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    return {
        "promos": len(promos),
        "stores": sorted({p.store_code for p in promos})[:20],
        "reward_types": dict(Counter(p.reward_type for p in promos)),
        "club_only": sum(1 for p in promos if p.club_only),
        "club_names": dict(Counter(p.club_name for p in promos if p.club_only).most_common(6)),
        "layouts": dict(Counter(p.raw.get("layout", "nested/flat") for p in promos)),
        "unapplied": dict(Counter(p.raw["unapplied"] for p in promos if p.raw.get("unapplied"))),
        "confidence": dict(Counter(p.raw.get("confidence") for p in promos)),
        "confidence_reasons": dict(Counter(r for p in promos
                                           for r in p.raw.get("confidence_reasons", []))),
        "with_end_date": sum(1 for p in promos if p.ends_at),
        "expired_at_publication": sum(1 for p in promos if p.ends_at and p.ends_at < published),
        "not_started_at_publication": sum(1 for p in promos
                                          if p.starts_at and p.starts_at > published),
        "with_hours": sum(1 for p in promos if p.hours),
        "items_per_promo": {"min": min(per_item), "median": median(per_item),
                            "max": max(per_item), "empty": per_item.count(0)} if per_item else {},
        "clubs": club_histogram(parsed),
        "fields": fields,
        "additional_restrictions": {k: dict(v.most_common(8)) for k, v in restrictions.items()},
        "layout": {k: v for k, v in layout.items() if k != "samples"},
        "layout_samples": layout.get("samples", []),
        "samples": samples,
        "shapes": shapes,
    }  # fmt: skip


def _shelf_prices(
    adapter,
    parsed,
    price_path: Path | None,  # noqa: ANN001
) -> tuple[dict | None, dict]:
    """``(item code -> shelf price, info)`` from the chain's PriceFull, only when it is the promo
    file's store (a promo file is per store; another store's shelf prices prove nothing). ``info``
    says which stores the two files are for and whether the shelf check could run."""
    info: dict = {"checked": False}
    if price_path is None:
        return None, {**info, "why": "no PriceFull"}
    try:
        data = price_path.read_bytes()
        priced = adapter.parse(adapter.raw_file_for(price_path.name, data), data)
    except Exception as exc:  # noqa: BLE001 - extra; never fail the probe
        return None, {**info, "why": f"PriceFull unreadable: {type(exc).__name__}"}
    stores = {p.store_code for p in parsed.promos}
    price_stores = {p.store_code for p in priced.prices}
    info = {"checked": False, "promo_stores": sorted(stores)[:5],
            "price_stores": sorted(price_stores)[:5], "price_rows": len(priced.prices)}  # fmt: skip
    if not priced.prices or price_stores != stores:
        return None, {**info, "why": "the PriceFull is for another store than the PromoFull"}
    return {p.item_code: p.price for p in priced.prices}, {**info, "checked": True}


def parse_summary(adapter, path: Path, price_path: Path | None = None) -> dict:  # noqa: ANN001
    """What the adapter reads from the file, outside any database. Errors are reported."""
    data = path.read_bytes()
    try:
        parsed = adapter.parse(adapter.raw_file_for(path.name, data), data)
    except Exception as exc:  # noqa: BLE001 - an adapter failure is a result here
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    out: dict = {
        "schema": parsed.raw.schema_version,
        "stores": len(parsed.stores),
        "online_stores": sum(1 for s in parsed.stores if s.channel == "online"),
        "items": len(parsed.items),
        "prices": len(parsed.prices),
    }
    if parsed.raw.kind in ("promo_full", "promo"):
        out["promos"] = len(parsed.promos)
        out["promo_item_codes"] = sum(len(p.item_codes) for p in parsed.promos)
        out["reward_types"] = dict(Counter(p.reward_type for p in parsed.promos))
        out["club_only"] = sum(1 for p in parsed.promos if p.club_only)
        out["unapplied"] = dict(Counter(p.raw["unapplied"] for p in parsed.promos
                                        if p.raw.get("unapplied")))  # fmt: skip
        if parsed.promos:
            try:
                shelf, shelf_info = _shelf_prices(adapter, parsed, price_path)
                out["profile"] = promo_profile(parsed, data, shelf)
                out["profile"]["shelf"] = shelf_info
            except Exception as exc:  # noqa: BLE001 - the profile is extra; never fail the probe
                out["profile_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return out


def result_line(slug: str, kind: str, entry: dict) -> str:
    """One untruncated log line per file: what the adapter read and what the gates decided."""
    p, g = entry.get("parse", {}), entry.get("gate", {})
    fields = {
        "chain": slug,
        "kind": kind,
        "file": entry.get("file"),
        "bytes": entry.get("bytes"),
        "published_at": entry.get("published_at"),
        "schema": p.get("schema") or g.get("schema"),
        "stores": p.get("stores"),
        "online_stores": p.get("online_stores"),
        "items": p.get("items"),
        "prices": p.get("prices"),
        "promos": p.get("promos"),
        "promo_item_codes": p.get("promo_item_codes"),
        "reward_types": p.get("reward_types") or None,
        "unapplied": p.get("unapplied") or None,
        "club_only": p.get("club_only"),
        "promos_loaded": entry.get("db", {}).get("promos"),
        "promo_items_linked": entry.get("db", {}).get("promo_items"),
        "parse_error": p.get("error"),
        "status": g.get("status"),
        "gates": ",".join(g.get("gates") or []) or None,
        "reason": g.get("reason") or g.get("error"),
    }
    return "RESULT " + json.dumps({k: v for k, v in fields.items() if v is not None},
                                  ensure_ascii=False)  # fmt: skip


SCHEMAS = ("v1", "v2", "unknown", "unreadable")


def schema_counts(results: dict) -> dict:
    """Files per detected schema for one chain (#57), from each entry's ``schema_check`` (the
    adapter's ``inspect_schema``, which sees the file before any gate): how many were ``v1``,
    ``v2``, ``unknown`` (a schema the adapter refuses) or ``unreadable`` (not XML at all), the
    schema per kind, the version fields the headers declared and the union of header field
    names. ``not_v1`` lists the files that are not v1, with the adapter's reason: the first
    real new-model file shows up here the day it appears."""
    counted: Counter = Counter()
    by_kind: dict[str, str] = {}
    declared: dict[str, set[str]] = {}
    header_fields: set[str] = set()
    namespaces: set[str] = set()
    not_v1: list[dict] = []
    for kind, entry in results.items():
        check = entry.get("schema_check") if isinstance(entry, dict) else None
        if not check:
            continue
        schema = check.get("schema") if check.get("schema") in SCHEMAS else "unreadable"
        counted[schema] += 1
        by_kind[kind] = schema
        sig = check.get("signature") or {}
        header_fields |= set(sig.get("header_fields") or [])
        namespaces |= set(sig.get("namespaces") or [])
        for name, value in (sig.get("declared_versions") or {}).items():
            declared.setdefault(name, set()).add(value)
        if schema != "v1":
            not_v1.append({"kind": kind, "file": entry.get("file"), "schema": schema,
                           "reason": check.get("reason") or check.get("error")})  # fmt: skip
    return {
        "files": sum(counted.values()),
        **{name: counted[name] for name in SCHEMAS},
        "by_kind": by_kind,
        "declared_versions": {k: sorted(v) for k, v in sorted(declared.items())},
        "namespaces": sorted(namespaces),
        "header_fields": sorted(header_fields),
        "not_v1": not_v1,
    }


def schema_line(slug: str, counts: dict) -> str:
    """One untruncated ``SCHEMA`` log line per chain: files per detected schema."""
    fields = {"chain": slug,
              **{k: counts.get(k) for k in ("files", *SCHEMAS)},
              "declared_versions": counts.get("declared_versions") or None,
              "namespaces": counts.get("namespaces") or None,
              "not_v1": counts.get("not_v1") or None}  # fmt: skip
    return "SCHEMA " + json.dumps({k: v for k, v in fields.items() if v is not None},
                                  ensure_ascii=False)  # fmt: skip


def schema_total_line(per_chain: dict[str, dict]) -> str:
    """``SCHEMA_TOTAL``: the same counts over every chain, plus the chains that are not all v1."""
    total = {name: sum(c.get(name, 0) for c in per_chain.values()) for name in ("files", *SCHEMAS)}
    mixed = sorted(slug for slug, c in per_chain.items() if c.get("files", 0) != c.get("v1", 0))
    return "SCHEMA_TOTAL " + json.dumps({**total, "chains_not_all_v1": mixed},
                                        ensure_ascii=False)  # fmt: skip


def _schema_section(gate_result: dict, slugs: Sequence[str]) -> list[str]:
    """The report table of ``schema_counts`` (empty when the gate result predates it)."""
    per_chain = gate_result.get("schema_counts") or {}
    rows = []
    flagged: list[str] = []
    for slug in slugs:
        c = per_chain.get(slug)
        if not c:
            continue
        declared = "; ".join(f"{k}={'/'.join(v)}" for k, v in
                             (c.get("declared_versions") or {}).items())  # fmt: skip
        notes = "; ".join(f"{n['kind']}: {n['schema']}" + (f" ({n['reason']})" if n.get("reason")
                                                           else "") for n in c.get("not_v1", []))  # fmt: skip
        if c.get("v2") or c.get("unknown"):  # a corrupt download is not a new model
            flagged.append(BY_SLUG[slug].name if slug in BY_SLUG else slug)
        cells = [BY_SLUG[slug].name if slug in BY_SLUG else slug, c.get("files", 0),
                 *(c.get(k, 0) for k in SCHEMAS), declared or "-", notes or "-"]  # fmt: skip
        rows.append("| " + " | ".join(md_escape(str(x)) for x in cells) + " |")
    if not rows:
        return []
    lines = ["", "### Files per detected schema (#57)", ""]
    if flagged:
        lines += [
            "**A file that is not `v1` appeared for: " + ", ".join(flagged) + ".** Keep it (it "
            "is untrusted data: it is in the `portal-probe-files` artifact, 7 days; do not open it outside the adapter), read the reason below and "
            'follow `docs/adapters.md`, "Schema versions", to turn it into the first '
            "new-model fixture.",
            "",
        ]
    lines += [
        "| chain | files | v1 | v2 | unknown | unreadable | declared versions | not v1 |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
    ]
    return lines


def _logs_to_stderr() -> None:
    """Pipeline logs (structlog) at warning level on stderr, so stdout carries the report."""
    import logging

    import structlog

    structlog.configure(
        processors=[structlog.processors.add_log_level, structlog.processors.KeyValueRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        logger_factory=lambda *a: structlog.PrintLogger(file=sys.stderr),
    )


def _promo_rows_loaded(conn, file_id: int) -> dict:  # noqa: ANN001
    """What the loader wrote for one PromoFull: promotions, and the promotion-to-item links
    (the file's item codes the chain's PriceFull rows know; the rest are skipped and counted)."""
    promos = conn.execute("SELECT count(*) FROM promos WHERE file_id = %s", (file_id,)).fetchone()
    links = conn.execute(
        "SELECT count(*) FROM promo_items pi JOIN promos p ON p.id = pi.promo_id"
        " WHERE p.file_id = %s",
        (file_id,),
    ).fetchone()
    return {"promos": promos[0], "promo_items": links[0]}


def club_lines(slug: str, clubs: dict | None) -> list[str]:
    """``PROMO_CLUBS`` log lines for one PromoFull: a head (counts), then every distinct ClubID
    text with its promotion count and the rule the table makes of it, then every club name with
    its count, each in parts of at most about ``CLUB_LINE_CHARS`` characters (one text longer than
    ``CLUB_TEXT_CHARS`` is cut and carries its length). The texts are copied verbatim."""
    if not clubs:
        return []
    head = {k: v for k, v in clubs.items() if k not in ("values", "names")}
    lines = ["PROMO_CLUBS " + json.dumps({"chain": slug, **head}, ensure_ascii=False)]

    def parts(what: str, rows: list) -> None:
        chunks: list[list] = [[]]
        size = 0
        for row in rows:
            row = dict(row) if isinstance(row, dict) else list(row)
            text = row["text"] if isinstance(row, dict) else row[0]
            if len(text) > CLUB_TEXT_CHARS:
                cut = text[:CLUB_TEXT_CHARS]
                if isinstance(row, dict):
                    row["text"], row["length"] = cut, len(text)
                else:
                    row[0] = cut
            if isinstance(row, dict) and row.get("rule") and len(row["rule"]) > 300:
                row["rule"] = row["rule"][:300] + "..."
            width = len(json.dumps(row, ensure_ascii=False))
            if chunks[-1] and size + width > CLUB_LINE_CHARS:
                chunks.append([])
                size = 0
            chunks[-1].append(row)
            size += width
        for i, chunk in enumerate(chunks if rows else []):
            lines.append("PROMO_CLUBS " + json.dumps(
                {"chain": slug, what: chunk, "part": f"{i + 1}/{len(chunks)}"},
                ensure_ascii=False))  # fmt: skip

    parts("values", clubs.get("values") or [])
    parts("names", clubs.get("names") or [])
    return lines


def _print_club_lines(slug: str, clubs: dict | None) -> None:
    for line in club_lines(slug, clubs):
        print(line, file=sys.stderr, flush=True)


def _print_promo_profile(slug: str, entry: dict) -> None:
    """The promo profile as separate untruncated log lines (histogram, layout, samples), so a
    reader without the artifacts can see what the real file holds."""
    profile = entry.get("parse", {}).get("profile")
    if not profile:
        return
    head = {k: v for k, v in profile.items()
            if k not in ("samples", "layout_samples", "layout", "shapes", "clubs")}  # fmt: skip
    _print_club_lines(slug, profile.get("clubs"))
    for tag, body in (("PROMO_PROFILE", head), ("PROMO_LAYOUT", profile["layout"])):
        print(f"{tag} " + json.dumps({"chain": slug, **body}, ensure_ascii=False),
              file=sys.stderr, flush=True)  # fmt: skip
    shapes = profile.get("shapes") or {}
    if shapes:
        print("PROMO_SHAPES " + json.dumps({"chain": slug, "signatures": shapes.get("signatures"),
                                            "days": shapes.get("days"), "error": shapes.get("error"),
                                            "shelf_check": shapes.get("shelf_check")},
                                           ensure_ascii=False), file=sys.stderr, flush=True)  # fmt: skip
        for sig, found in (shapes.get("examples") or {}).items():
            print("PROMO_SHAPE_EXAMPLE " + json.dumps({"chain": slug, "signature": sig,
                                                       "examples": found}, ensure_ascii=False),
                  file=sys.stderr, flush=True)  # fmt: skip
        if shapes.get("day_examples"):
            print("PROMO_DAYS " + json.dumps({"chain": slug, "examples": shapes["day_examples"]},
                                             ensure_ascii=False), file=sys.stderr, flush=True)  # fmt: skip
    for i, sample in enumerate(profile.get("layout_samples", [])):
        print("PROMO_RAW " + json.dumps({"chain": slug, "n": i, "promotion": sample},
                                        ensure_ascii=False), file=sys.stderr, flush=True)  # fmt: skip
    for sample in profile.get("samples", []):
        print("PROMO_SAMPLE " + json.dumps({"chain": slug, **sample}, ensure_ascii=False),
              file=sys.stderr, flush=True)  # fmt: skip


def gate(files: Path, slugs: Sequence[str], now: datetime | None) -> dict:
    """Run each chain's picked files through ``Scheduler.run_full`` (Stores first), with the
    real clock unless ``now`` is given, and read the outcome back from ``file_tracking``."""
    import hashlib
    import tempfile

    from smartcart_ingest import db as dbmod
    from smartcart_ingest.adapters import REGISTRY
    from smartcart_ingest.alerts import Alerter
    from smartcart_ingest.rawstore import LocalRawStore
    from smartcart_ingest.scheduler import Scheduler
    from smartcart_ingest.settings import load_settings

    _logs_to_stderr()
    adapters = {getattr(cls, "slug", None): cls for cls in REGISTRY.values()}
    fetcher = OneFileFetcher()
    sink = _Sink()
    out: dict = {}
    counts: dict[str, dict] = {}
    clock = (lambda: now) if now else (lambda: datetime.now(tz=ISRAEL))
    raw_dir = Path(tempfile.mkdtemp(prefix="portal-probe-raw-"))
    try:
        with dbmod.connect(autocommit=True) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            sched = Scheduler(conn, fetcher, LocalRawStore(raw_dir), Alerter([sink]),
                              load_settings(), now=clock, sleep=lambda s: None)  # fmt: skip
            for slug in slugs:
                cls = adapters.get(slug)
                if cls is None:
                    out[slug] = {"error": "no adapter registered"}
                    continue
                adapter = cls()
                results: dict = {}
                picked = pick_files(files, slug, adapter)
                for kind, path in sorted(picked.items(),
                                         key=lambda kv: KINDS.index(kv[0])):  # fmt: skip
                    data = path.read_bytes()
                    info = adapter.parse_filename(path.name)
                    entry = {
                        "file": path.name,
                        "bytes": len(data),
                        "published_at": (
                            info.published_at.isoformat(timespec="minutes")
                            if info.published_at
                            else None
                        ),
                        "parse": parse_summary(adapter, path, picked.get("price_full")),
                        "schema_check": adapter.inspect_schema(data),
                    }
                    fetcher.current = _OneFile(adapter.chain_id, path.name, kind, data)
                    report = sched.run_full([adapter.chain_id]).chains[0]
                    fetcher.current = None
                    row = conn.execute(
                        "SELECT id, status, reason, schema_version FROM file_tracking"
                        " WHERE sha256 = %s",
                        (hashlib.sha256(data).hexdigest(),),
                    ).fetchone()
                    if row is None:
                        entry["gate"] = {"status": "not tracked", "error": report.error}
                    else:
                        gates = [g for (g,) in conn.execute(
                            "SELECT gate FROM quarantine_events WHERE file_id = %s ORDER BY id",
                            (row[0],),
                        ).fetchall()]  # fmt: skip
                        entry["gate"] = {"status": row[1], "reason": row[2], "gates": gates,
                                         "schema": row[3]}  # fmt: skip
                        if kind == "promo_full" and row[1] == "loaded":
                            entry["db"] = _promo_rows_loaded(conn, row[0])
                    results[kind] = entry
                    print(result_line(slug, kind, entry), file=sys.stderr, flush=True)
                    _print_promo_profile(slug, entry)
                out[slug] = results
                counts[slug] = schema_counts(results)
                print(schema_line(slug, counts[slug]), file=sys.stderr, flush=True)
    finally:
        shutil.rmtree(raw_dir, ignore_errors=True)
    print(schema_total_line(counts), file=sys.stderr, flush=True)
    return {"files": out, "schema_counts": counts,
            "alerts": [{"chain_id": a.chain_id, "kind": a.kind,
                        "message": a.message} for a in sink.alerts]}  # fmt: skip


# --- report --------------------------------------------------------------------------------------------


def _size(n: int | None) -> str:
    if n is None:
        return "-"
    if n < 1024:
        return f"{n} B"
    return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{n / 1024:.0f} KB"


_KIND_NAMES = {"stores": "Stores", "price_full": "PriceFull", "promo_full": "PromoFull"}


def _download_cell(entry: dict | None, gated: dict | None) -> str:
    if gated:
        return f"`{gated['file']}` {_size(gated['bytes'])}, {gated.get('published_at') or '?'}"
    if entry and entry.get("error"):
        return "no: " + str(entry["error"])[:80]
    return "-"


def _parsed_cell(kind: str, gated: dict | None) -> str:
    if not gated:
        return ""
    p = gated["parse"]
    if "error" in p:
        return f"{_KIND_NAMES[kind]}: parse error"
    if kind == "stores":
        return f"{p['stores']} stores ({p['online_stores']} online)"
    if kind == "promo_full":
        return f"{p.get('promos', 0)} promos ({p.get('club_only', 0)} club-only)"
    return f"{p['items']} items, {p['prices']} prices"


def _gate_cell(gated: dict | None) -> str:
    if not gated:
        return ""
    g = gated["gate"]
    status = g.get("status", "?")
    if status == "quarantined" and g.get("gates"):
        return f"quarantined ({', '.join(g['gates'])})"
    if status == "failed":
        return f"failed ({str(g.get('reason') or '')[:60]})"
    return status


def _promo_section(files: dict, slugs: Sequence[str]) -> list[str]:
    """One row per chain whose PromoFull the adapter read: what the real promos look like."""
    rows = []
    for slug in slugs:
        entry = files.get(slug, {}).get("promo_full") if isinstance(files.get(slug), dict) else None
        if not entry or "error" in entry["parse"]:
            continue
        p = entry["parse"]
        prof = p.get("profile") or {}
        conf = prof.get("confidence") or {}
        low = sum(n for score, n in conf.items() if score is not None and float(score) < 1.0)
        unknown = p.get("promo_item_codes", 0) - (entry.get("db") or {}).get("promo_items", 0)
        loaded = entry.get("db") or {}
        reward = ", ".join(f"{k} {v}" for k, v in sorted((p.get("reward_types") or {}).items()))
        unapplied = ", ".join(f"{k} {v}" for k, v in sorted((p.get("unapplied") or {}).items()))
        cells = [
            BY_SLUG[slug].name if slug in BY_SLUG else slug,
            str(p.get("promos", 0)),
            reward or "-",
            unapplied or "-",
            str(p.get("club_only", 0)),
            f"{prof.get('expired_at_publication', '-')} / {prof.get('not_started_at_publication', '-')}",
            f"{low} of {prof.get('promos', 0)}",
            (
                f"{loaded['promos']} promos, {loaded['promo_items']} of {p.get('promo_item_codes')} item "
                f"links ({unknown} unknown items skipped)"
                if loaded
                else "-"
            ),
        ]
        rows.append("| " + " | ".join(md_escape(c) for c in cells) + " |")
    if not rows:
        return []
    return [
        "",
        "### PromoFull files as the adapter read them",
        "",
        "| chain | promos | reward type (adapter) | read but not applied (reason) | club-only"
        " | expired / not started at publication | confidence below 1.0 | loaded |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
    ]


def reachability(row: dict) -> str:
    """What the "portal reachable" column says for one chain. The HTTP root check alone misleads:
    the four Cerberus chains share an FTP-over-TLS host whose HTTPS root does not answer (status 0)
    although the login passes and files download, and King Store's root answers 403 while its
    files download. So when the root does not answer well, a file that was actually downloaded
    (or, with no download, a passing FTP login) wins and the root status is kept in brackets."""
    root = f"{row.get('reachable')} ({row.get('http_status')})"
    if row.get("reachable") in ("OK", "REACHABLE"):
        return root
    downloads = row.get("downloads") or {}
    got = sum(1 for d in downloads.values() if d.get("file"))
    if got:
        return (
            f"OK (files downloaded: {got} of {len(downloads)}; HTTP root {row.get('http_status')})"
        )
    if str(row.get("login", "")).startswith("ok"):
        return f"OK (FTP login passes; HTTP root {row.get('http_status')})"
    return root


def _shelf_section(files: dict, slugs: Sequence[str]) -> list[str]:
    """One row per chain: whether the PromoFull's prices were checked against the PriceFull of
    the same store, and the counts (one-group promotions, then trigger/reward pairs)."""
    rows = []
    for slug in slugs:
        entry = files.get(slug, {}).get("promo_full") if isinstance(files.get(slug), dict) else None
        prof = ((entry or {}).get("parse") or {}).get("profile")
        if not prof:
            continue
        info = prof.get("shelf") or {}
        check = ((prof.get("shapes") or {}).get("shelf_check")) or {}
        name = BY_SLUG[slug].name if slug in BY_SLUG else slug
        promo_store = ",".join(info.get("promo_stores") or []) or "-"
        price_store = ",".join(info.get("price_stores") or []) or "-"
        if not info.get("checked"):
            why = "not checked: " + str(info.get("why") or "no shelf prices")
            cells = [name, promo_store, price_store, why, "", ""]
        else:
            n = check.get("single_items_with_shelf", 0)
            pairs = check.get("items_with_shelf", 0)
            single = (
                f"{check.get('single_unit_equals_shelf_x_rate', 0)} of {n} equal shelf x "
                f"(1 - rate), {check.get('single_unit_within_rate_rounding', 0)} within the "
                f"rate's rounding, {check.get('single_unit_below_shelf', 0)} below shelf"
            )
            pair = (
                f"{check.get('reward_equals_shelf_x_rate', 0)} of {pairs} rewards equal shelf x "
                f"(1 - rate); {check.get('trigger_equals_shelf', 0)} of "
                f"{check.get('trigger_priced', 0)} priced triggers equal shelf"
                if pairs
                else "no pair with a shelf price"
            )
            cells = [name, promo_store, price_store, "same store", single, pair]
        rows.append("| " + " | ".join(md_escape(c) for c in cells) + " |")
    if not rows:
        return []
    return [
        "",
        "### Promo prices against the same store's shelf prices",
        "",
        "| chain | PromoFull store | PriceFull store | shelf check | one-group promotions"
        " (`DiscountedPrice / MinQty`, not weighed) | trigger and reward pairs |",
        "|---|---|---|---|---|---|",
        *rows,
    ]


def render(probe_result: dict | None, gate_result: dict, slugs: Sequence[str]) -> str:
    chains = (probe_result or {}).get("chains", {})
    files = gate_result["files"]
    lines = [
        "## Transparency portal probe",
        "",
        (
            f"From a GitHub-hosted runner (`{probe_result.get('runner')}`, not an Israeli IP), "
            f"{probe_result.get('started_at')} to {probe_result.get('finished_at')} UTC. "
            "A portal that answers here but blocks cloud ranges elsewhere, or the reverse, is "
            "exactly what this measures; the VPS (#22) is still the production path."
            if probe_result
            else "Offline run: files from a local directory, no portal contacted."
        ),
        "",
        "| chain | portal reachable | login | Stores file | PriceFull file | PromoFull file | parsed"
        " | gate result (Stores; PriceFull; PromoFull) | schema |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for slug in slugs:
        c = chains.get(slug, {})
        g = files.get(slug, {}) if isinstance(files.get(slug), dict) else {}
        st, pf, pr = g.get("stores"), g.get("price_full"), g.get("promo_full")
        downloads = c.get("downloads", {})
        reach = reachability(c) if c else "not probed"
        # The adapter's own reading first: a quarantined Stores file keeps schema 'unknown'.
        schemas = sorted({x["parse"].get("schema") or x["gate"].get("schema") or "?"
                          for x in (st, pf, pr) if x})  # fmt: skip
        parsed = "; ".join(
            x
            for x in (_parsed_cell("stores", st), _parsed_cell("price_full", pf),
                      _parsed_cell("promo_full", pr))
            if x
        )  # fmt: skip
        gates = "; ".join(x for x in (_gate_cell(st), _gate_cell(pf), _gate_cell(pr)) if x)
        cells = [
            BY_SLUG[slug].name if slug in BY_SLUG else slug,
            reach,
            c.get("login", "n/a") if c else "-",
            _download_cell(downloads.get("stores"), st),
            _download_cell(downloads.get("price_full"), pf),
            _download_cell(downloads.get("promo_full"), pr),
            parsed or "-",
            gates or "-",
            ", ".join(schemas) or "-",
        ]
        lines.append("| " + " | ".join(md_escape(x) for x in cells) + " |")
    lines += _schema_section(gate_result, slugs)
    lines += _promo_section(files, slugs)
    lines += _shelf_section(files, slugs)
    lines += [
        "",
        "Gate result is the `file_tracking` status after the real Scheduler path (adapter, quality "
        "gates, loader) in a throwaway Postgres: `loaded`, `quarantined (<gates>)` or `failed`. "
        "A PriceFull of a store with no earlier load cannot trip the item-count or price-jump "
        "gates; stale date and zero price still apply. Schema is what the adapter detected "
        "(`v2` relies on the provisional marker, #57).",
        "",
    ]
    errors = [
        (slug, kind, d)
        for slug in slugs
        for kind, d in chains.get(slug, {}).get("downloads", {}).items()
        if d.get("error")
    ]
    if errors:
        lines += [f"<details><summary>Download errors ({len(errors)})</summary>", ""]
        for slug, kind, d in errors:
            tail = [ln for ln in str(d.get("log_tail", "")).splitlines() if ln.strip()][-2:]
            lines.append(f"- `{slug}` {kind}: {md_escape(d['error'])}"
                         + (f" — `{md_escape(' / '.join(tail))[:300]}`" if tail else ""))  # fmt: skip
        lines += ["", "</details>", ""]
    alerts = gate_result.get("alerts") or []
    if alerts:
        lines += ["<details><summary>Alerts raised during the gate run "
                  f"({len(alerts)})</summary>", ""]  # fmt: skip
        lines += [f"- `{a['chain_id']}` {a['kind']}: {md_escape(a['message'])}" for a in alerts]
        lines += ["", "</details>", ""]
    lines.append(f"Commit `{git_sha()}`.")
    return "\n".join(lines) + "\n"


# --- real fixtures ---------------------------------------------------------------------------------------


def full_file_facts(parse: dict) -> dict:
    """What the **whole** PromoFull held (the committed fixture keeps only the first promotions):
    its promotion count, every distinct ClubID text with its count and the rule the club table made
    of it, and the same-store shelf check. Copied from the gate step's profile."""
    profile = parse.get("profile") or {}
    shapes = profile.get("shapes") or {}
    return {
        "promos": parse.get("promos"),
        "clubs": profile.get("clubs"),
        "shelf": profile.get("shelf"),
        "shelf_check": shapes.get("shelf_check"),
    }


def build_fixtures(
    files: Path, gate_json: dict, out: Path, max_items: int, max_promos: int = 100
) -> dict[str, list]:
    """Write ``out/<slug>/real/`` for every file the adapter parsed in the gate step: Stores
    files whole, PriceFull files trimmed to their first ``max_items`` rows
    (``fetch_fixtures.trim_price_file``), PromoFull files trimmed to their first ``max_promos``
    promotions, each kept whole with all its items (``trim_promo_file``), each re-parsed
    through the adapter, and a ``MANIFEST.json`` per chain. Files the adapter rejected are not
    written. Returns the manifests by slug."""
    import hashlib

    from smartcart_ingest.adapters.fetch_fixtures import (
        adapters_by_slug,
        trim_price_file,
        trim_promo_file,
    )

    adapters = adapters_by_slug()
    downloads = {
        slug: row.get("downloads", {})
        for slug, row in ((gate_json.get("probe") or {}).get("chains") or {}).items()
    }
    manifests: dict[str, list] = {}
    for slug, kinds in sorted((gate_json.get("files") or {}).items()):
        if slug not in adapters or not isinstance(kinds, dict):
            continue
        adapter = adapters[slug]()
        entries = []
        for kind in KINDS:
            entry = kinds.get(kind)
            if not entry or "error" in entry.get("parse", {"error": "missing"}):
                continue
            src = files / slug / entry["file"]
            data = src.read_bytes()
            record: dict = {
                "file": entry["file"],
                "kind": kind,
                "source_file": entry["file"],
                "sha256_original": hashlib.sha256(data).hexdigest(),
                "bytes_original": len(data),
                "published_at": entry.get("published_at"),
                "fetched_at": downloads.get(slug, {}).get(kind, {}).get("fetched_at"),
                "schema": entry["parse"].get("schema"),
                "gate": {k: entry.get("gate", {}).get(k) for k in ("status", "gates", "reason")},
            }
            if kind == "promo_full":
                record["full_file"] = full_file_facts(entry["parse"])
            if kind == "price_full":
                record["same_store_as_promo"] = (
                    downloads.get(slug, {}).get(kind, {}).get("same_store")
                )
            try:
                if kind == "price_full":
                    body, before, after = trim_price_file(data, max_items)
                    record["items_original"], record["items_trimmed"] = before, after
                elif kind == "promo_full":
                    body, before, after = trim_promo_file(data, max_promos)
                    record["promos_original"], record["promos_trimmed"] = before, after
                else:
                    body = data
                    record["stores"] = entry["parse"].get("stores")
                parsed = adapter.parse(adapter.raw_file_for(src.name, body), body)
            except Exception as exc:  # noqa: BLE001 - a file that does not trim cleanly is skipped
                print(f"FIXTURE skipped {slug}/{src.name}: {type(exc).__name__}: {exc}",
                      file=sys.stderr)  # fmt: skip
                continue
            if kind == "price_full" and len(parsed.prices) != record["items_trimmed"]:
                print(f"FIXTURE note {slug}/{src.name}: {len(parsed.prices)} prices parsed from "
                      f"{record['items_trimmed']} rows", file=sys.stderr)  # fmt: skip
            if kind == "promo_full" and len(parsed.promos) != record["promos_trimmed"]:
                print(f"FIXTURE note {slug}/{src.name}: {len(parsed.promos)} promos parsed from "
                      f"{record['promos_trimmed']} promotions", file=sys.stderr)  # fmt: skip
            record["sha256"] = hashlib.sha256(body).hexdigest()
            record["bytes"] = len(body)
            record["parsed"] = {"stores": len(parsed.stores), "items": len(parsed.items),
                                "prices": len(parsed.prices),
                                "promos": len(parsed.promos)}  # fmt: skip
            dest = out / slug / "real"
            dest.mkdir(parents=True, exist_ok=True)
            (dest / src.name).write_bytes(body)
            entries.append(record)
            shown = {k: v for k, v in record.items() if k != "full_file"}
            print("FIXTURE " + json.dumps({"chain": slug, **shown}, ensure_ascii=False),
                  file=sys.stderr)  # fmt: skip
        if entries:
            (out / slug / "real" / "MANIFEST.json").write_text(
                json.dumps({"chain_id": adapter.chain_id, "max_items": max_items,
                            "max_promos": max_promos, "files": entries}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )  # fmt: skip
            manifests[slug] = entries
    return manifests


# --- main ----------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe", help="reachability, login and downloads (network, no database)")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--chain", action="append", choices=list(BY_SLUG), help="default: all ten")
    p.add_argument("--timeout", type=float, default=180, help="seconds per download")
    p.add_argument("--skip-downloads", action="store_true")
    g = sub.add_parser("gate", help="run the files through the adapters and gates (database)")
    g.add_argument("--files", type=Path, required=True, help="directory of <slug>/<file>")
    g.add_argument("--probe", type=Path, default=None, help="probe.json from the probe step")
    g.add_argument("--chain", action="append", choices=list(BY_SLUG), help="default: all ten")
    g.add_argument("--now", default=None,
                   help="ISO time for the gates' clock (tests only; default: the real clock)")  # fmt: skip
    g.add_argument("--out", type=Path, default=None, help="Markdown table (default stdout)")
    g.add_argument("--json-out", type=Path, default=None)
    f = sub.add_parser("fixtures", help="write <slug>/real/ regression fixtures (no database)")
    f.add_argument("--files", type=Path, required=True, help="directory of <slug>/<file>")
    f.add_argument("--gate-json", type=Path, required=True, help="--json-out of the gate step")
    f.add_argument("--out", type=Path, required=True, help="e.g. a copy of tests/fixtures")
    f.add_argument("--max-items", type=int, default=200, help="rows kept per PriceFull")
    f.add_argument("--max-promos", type=int, default=100, help="promotions kept per PromoFull")
    args = ap.parse_args(argv)
    slugs = args.chain if getattr(args, "chain", None) else [p.slug for p in PORTALS]

    if args.cmd == "probe":
        probe(args.out, slugs, args.timeout, args.skip_downloads)
        return 0
    if args.cmd == "fixtures":
        gate_json = json.loads(args.gate_json.read_text(encoding="utf-8"))
        made = build_fixtures(args.files, gate_json, args.out, args.max_items, args.max_promos)
        print(f"fixtures written for {len(made)} chain(s): {', '.join(made) or 'none'}")
        return 0

    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    now = datetime.fromisoformat(args.now) if args.now else None
    if now is not None and now.tzinfo is None:
        now = now.replace(tzinfo=ISRAEL)
    probe_result = None
    if args.probe and args.probe.exists():
        probe_result = json.loads(args.probe.read_text(encoding="utf-8"))
    result = gate(args.files, slugs, now)
    write_text(args.out, render(probe_result, result, slugs))
    if args.json_out:
        write_text(args.json_out, json.dumps({"probe": probe_result, **result},
                                             ensure_ascii=False, indent=2) + "\n")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
