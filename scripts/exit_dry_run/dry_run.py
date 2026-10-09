"""Phase 0 exit dry run (issue #60): rehearse the exit report on the files we have today.

THIS IS NOT THE EXIT VALIDATION. The exit needs 14 consecutive nightly loads on the VPS. This
script loads what is committed, through the production path, into two throwaway databases:

* ``real``: the seven chains' real files of 2026-10-08 (``fixtures/<chain>/real/``);
* ``synthetic``: the ten chains' synthetic files of the demo, which include promos, store
  coordinates and deliberately broken files;

runs ``smartcart_ingest.report`` over each window, measures what the real files show (stores,
cities, coordinates, barcodes, publication times), and writes ``docs/phase-0-exit-dry-run.md``.

    scripts/exit_dry_run/run.sh                      # starts a throwaway Postgres, runs this, stops it
    DATABASE_URL=postgresql://admin@host/postgres \\
        uv run --no-sync python scripts/exit_dry_run/dry_run.py   # on a server that allows CREATE DATABASE

``DATABASE_URL`` is only the server (the script creates and drops ``exit_dry_run_real`` and
``exit_dry_run_synthetic`` on it); no other database is touched.
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from psycopg.conninfo import make_conninfo
from replay import REPO, FileOutcome, fixture_set, quiet_logs, replay

from smartcart_ingest import db as dbmod
from smartcart_ingest import report as rep

ISRAEL = ZoneInfo("Asia/Jerusalem")
REAL_DAY = date(2026, 10, 8)
SYNTH_START, SYNTH_END = date(2026, 10, 6), date(2026, 10, 9)
DB_REAL, DB_SYNTH = "exit_dry_run_real", "exit_dry_run_synthetic"
TEL_AVIV = (34.7818, 32.0853)  # lon, lat: a dense area, as docs/phase-0-exit-report.md suggests
OUT_DEFAULT = REPO / "docs" / "phase-0-exit-dry-run.md"

# Timers in infra/vps/smartcart-ingest-full.timer (Israel time).
FULL_PASSES = ((6, 0), (8, 30))


# --- databases ----------------------------------------------------------------------------------


def create_database(admin_dsn: str, name: str) -> str:
    """Drop and create ``name`` on the server, migrate it, and return its DSN."""
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{name}"')
    dsn = make_conninfo(admin_dsn, dbname=name)
    with dbmod.connect(dsn, autocommit=True) as conn:
        missing = {"postgis", "vector"} - dbmod.available_extensions(conn)
        dbmod.migrate(conn, skip_requires=missing)
    return dsn


def drop_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


# --- facts read from the real database ---------------------------------------------------------------


@dataclass
class ChainFacts:
    name: str
    chain_id: str
    stores_physical: int
    stores_online: int
    with_address: int
    city_is_code: int
    with_city: int
    with_coordinates: int
    items: int
    with_barcode: int
    weighed: int
    unknown_manufacturer: int
    price_events: int
    stores_with_prices: int
    max_name_len: int
    sample_stores: list[tuple[str, str, str | None, str | None]]
    city_zero: int
    city_counts: dict[str, int]


def chain_facts(conn: psycopg.Connection) -> list[ChainFacts]:
    has_geog = rep._has_geog(conn)
    coords = "count(*) FILTER (WHERE s.geog IS NOT NULL)" if has_geog else "0"
    out = []
    for chain_id, name in conn.execute("SELECT id, name FROM chains ORDER BY name").fetchall():
        sto = conn.execute(
            "SELECT count(*) FILTER (WHERE s.channel = 'physical'),"
            "       count(*) FILTER (WHERE s.channel = 'online'),"
            "       count(s.address), count(s.city),"
            "       count(*) FILTER (WHERE s.city ~ '^[0-9]+$'),"
            f"      {coords}"
            " FROM stores s WHERE s.chain_id = %s",
            (chain_id,),
        ).fetchone()
        itm = conn.execute(
            "SELECT count(*), count(barcode), count(*) FILTER (WHERE is_weighed),"
            "       count(*) FILTER (WHERE manufacturer IS NULL OR manufacturer = 'לא ידוע'),"
            "       COALESCE(max(length(raw_name)), 0)"
            " FROM items WHERE chain_id = %s",
            (chain_id,),
        ).fetchone()
        pr = conn.execute(
            "SELECT count(*), count(DISTINCT p.store_id) FROM prices p"
            " JOIN items i ON i.id = p.item_id WHERE i.chain_id = %s",
            (chain_id,),
        ).fetchone()
        sample = conn.execute(
            "SELECT store_code, name, city, address FROM stores WHERE chain_id = %s"
            " AND channel = 'physical' ORDER BY store_code::text LIMIT 2",
            (chain_id,),
        ).fetchall()
        counts = dict(conn.execute(
            "SELECT city, count(*) FROM stores WHERE chain_id = %s AND city ~ '^[0-9]+$'"
            " GROUP BY city", (chain_id,)).fetchall())  # fmt: skip
        out.append(ChainFacts(name, chain_id, sto[0], sto[1], sto[2], sto[4], sto[3], sto[5],
                              itm[0], itm[1], itm[2], itm[3], pr[0], pr[1], itm[4], sample,
                              counts.get('0', 0), counts))  # fmt: skip
    return out


def barcode_overlap(conn: psycopg.Connection) -> Counter[int]:
    """How many barcodes appear in exactly n chains (n -> count)."""
    rows = conn.execute(
        "SELECT n, count(*) FROM (SELECT barcode, count(DISTINCT chain_id) AS n FROM items"
        " WHERE barcode IS NOT NULL GROUP BY barcode) t GROUP BY n"
    ).fetchall()
    return Counter({n: c for n, c in rows})


def shared_barcodes(conn: psycopg.Connection, limit: int = 3, min_chains: int = 2) -> list[str]:
    rows = conn.execute(
        "SELECT barcode FROM items WHERE barcode IS NOT NULL GROUP BY barcode"
        " HAVING count(DISTINCT chain_id) >= %s ORDER BY count(DISTINCT chain_id) DESC, barcode"
        " LIMIT %s",
        (min_chains, limit),
    ).fetchall()
    return [r[0] for r in rows]


def price_spot_check(conn: psycopg.Connection, barcodes: list[str]) -> list[tuple]:
    """The current price of each barcode at every store that has a price for it."""
    return conn.execute(
        "SELECT i.barcode, i.raw_name, c.name, s.store_code, s.name, cp.price, cp.valid_from"
        " FROM items i JOIN chains c ON c.id = i.chain_id"
        " JOIN stores s ON s.chain_id = i.chain_id"
        " CROSS JOIN LATERAL current_price(i.id, s.id) cp"
        " WHERE i.barcode = ANY(%s) ORDER BY i.barcode, c.name",
        (barcodes,),
    ).fetchall()


def centroid(conn: psycopg.Connection) -> tuple[float, float] | None:
    if not rep._has_geog(conn):
        return None
    row = conn.execute(
        "SELECT avg(ST_X(geog::geometry)), avg(ST_Y(geog::geometry)) FROM stores"
        " WHERE geog IS NOT NULL AND channel = 'physical'"
    ).fetchone()
    return (float(row[0]), float(row[1])) if row and row[0] is not None else None


def server_facts(conn: psycopg.Connection) -> dict[str, str]:
    ext = dict(conn.execute("SELECT extname, extversion FROM pg_extension").fetchall())
    return {
        "postgres": conn.execute("SHOW server_version").fetchone()[0],
        "postgis": ext.get("postgis", "not installed"),
        "pgvector": ext.get("vector", "not installed"),
    }


def first_pass_that_sees(published: datetime) -> str:
    """The first full-sync pass (06:00, 08:30 Israel time) at or after publication that day."""
    local = published.astimezone(ISRAEL)
    for hour, minute in FULL_PASSES:
        if (local.hour, local.minute) <= (hour, minute):
            return f"{hour:02d}:{minute:02d}"
    return "next day 06:00"


# --- markdown ---------------------------------------------------------------------------------------


def md_table(header: list[str], rows: list[list[object]]) -> list[str]:
    def cell(x: object) -> str:
        return str("" if x is None else x).replace("|", "\\|").replace("\n", " ")

    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return out


def demote(markdown: str) -> str:
    """Headings one level down, so a pasted report sits under the dry run's own headings."""
    return "\n".join(
        ("#" + line) if line.startswith("#") else line for line in markdown.splitlines()
    )


def details(summary: str, body: str) -> list[str]:
    return [f"<details><summary>{summary}</summary>", "", body.strip("\n"), "", "</details>", ""]


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "n/a"


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=REPO,
            check=True,
        ).stdout.strip()  # fmt: skip
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def render(
    *,
    server: dict[str, str],
    real_outcomes: list[FileOutcome],
    real_alerts: list[dict],
    facts: list[ChainFacts],
    overlap: Counter[int],
    spot: list[tuple],
    spot_barcodes: list[str],
    real_report: rep.ExitReport,
    real_report_seen: rep.ExitReport,
    real_basket: list[dict],
    synth_outcomes: list[FileOutcome],
    synth_report: rep.ExitReport,
    synth_basket: list[dict],
    synth_basket_params: dict | None,
    synth_stores: tuple[int, int],
) -> str:
    L: list[str] = []
    add = L.append
    today = date.today().isoformat()
    n_files = len(real_outcomes)
    loaded = sum(1 for o in real_outcomes if o.status == "loaded")
    physical = sum(f.stores_physical for f in facts)
    online = sum(f.stores_online for f in facts)
    with_coords = sum(f.with_coordinates for f in facts)
    code_cities = sum(f.city_is_code for f in facts)
    zero = sum(f.city_zero for f in facts)
    with_city = sum(f.with_city for f in facts)
    real_chain_names = [f.name for f in facts]
    total_chains = len(rep.D13_CHAINS)
    present = [c for c in real_report.chains if c.successes]
    synth_promos = sum(s.total for s in synth_report.promo_stats)

    add("# Phase 0 exit dry run")
    add("")
    add(
        "> **This is not the exit validation.** It is a rehearsal of issue #60 on the files we have"
    )
    add(
        "> today: one real day of seven chains, trimmed to 200 price rows each, plus the synthetic set."
    )
    add(
        "> The exit needs fourteen consecutive nightly loads on the VPS (`phase-0-exit-report.md`),"
    )
    add(
        "> and `phase-0-exit-report.md` stays **NO-GO**. Nothing here may be pasted into it as evidence."
    )
    add("")
    add(
        f"Generated {today} from commit `{git_sha()}` by `scripts/exit_dry_run/run.sh` (re-run it to"
    )
    add("refresh this file; the evidence blocks below are the generator's own output, not typed).")
    add("Labels follow `docs/README.md`: **measured** is read from the databases of this run,")
    add("**estimate** is a judgement, **derived** is reasoning from a measured value and the repo.")
    add("")
    add("## 1. What was run")
    add("")
    add(f"- Server: PostgreSQL {server['postgres']}, PostGIS {server['postgis']}, pgvector "
        f"{server['pgvector']} on {platform.system()} (a throwaway cluster; migrations applied by "
        "`smartcart-ingest`'s own migrator).")  # fmt: skip
    add("- Path: the production one. A fake portal lists one file at a time; the real `Scheduler` "
        "downloads, hashes, tracks, archives, parses (chain adapter), runs the quality gates and "
        "loads in one transaction. Same method as `scripts/demo/load_fixtures.py` and the `gate` "
        "step of `scripts/unblock/portal_probe.py`. The scheduler's clock is replayed: one hour "
        "after each file's publication time, so the stale-date gate judges a file against its own "
        "day.")  # fmt: skip
    add(f"- Real set: {n_files} files of {len(facts)} chains "
        f"({', '.join(real_chain_names)}), published 2026-10-06 to 2026-10-08, fetched by the "
        "portal probe from a GitHub runner (the files are committed under "
        "`services/ingest/tests/fixtures/<chain>/real/`, with a `MANIFEST.json` each). "
        "Stores files are whole; each PriceFull is cut to its first 200 rows.")  # fmt: skip
    add("- Synthetic set: the ten chains' demo files (promos, coordinates, and deliberately broken "
        "files) over 2026-10-06 to 2026-10-09.")  # fmt: skip
    add("- Report: `python -m smartcart_ingest.report` (`build_exit_report` and `render_markdown`), "
        f"window {REAL_DAY} to {REAL_DAY} for the real database, {SYNTH_START} to {SYNTH_END} for "
        "the synthetic one.")  # fmt: skip
    add("")
    add("## 2. The real files, one real day per chain")
    add("")
    add(f"{loaded} of {n_files} real files reached `loaded`; {len(real_alerts)} alerts were raised "
        "(measured). `Pass` is the first full-sync pass of `infra/vps/smartcart-ingest-full.timer` "
        "(06:00 and 08:30 Israel time) that can see the file (derived).")  # fmt: skip
    add("")
    rows = []
    for o in sorted(real_outcomes, key=lambda o: (o.chain, o.published_at)):
        rows.append([
            o.chain, o.kind, f"`{o.file}`", f"{o.published_at.astimezone(ISRAEL):%Y-%m-%d %H:%M}",
            first_pass_that_sees(o.published_at) if o.kind != "stores" else "",
            o.schema or "?", o.status, ", ".join(o.gates) or "none",
        ])  # fmt: skip
    L += md_table(
        ["Chain", "Kind", "File", "Published (Israel)", "Pass", "Schema", "Status", "Gates failed"],
        rows,
    )
    add("")
    add("What the files contain (measured):")
    add("")
    rows = [[
        f.name, f.stores_physical, f.stores_online, f"{f.with_coordinates}",
        pct(f.city_is_code, f.with_city) if f.with_city else "n/a",
        f.items, pct(f.with_barcode, f.items), pct(f.weighed, f.items),
        pct(f.unknown_manufacturer, f.items), f.price_events, f.stores_with_prices,
        f.max_name_len,
    ] for f in facts]  # fmt: skip
    L += md_table(
        ["Chain", "Physical stores", "Online", "With coordinates", "City is a numeric code",
         "Items", "With barcode", "Weighed", "Manufacturer unknown", "Price events",
         "Stores with prices", "Longest item name"],
        rows,
    )  # fmt: skip
    add("")
    add(
        f"Totals: {physical} physical and {online} online stores, **{with_coords} with coordinates**; "
        f"{code_cities} of {with_city} stores have a numeric city. Sample stores:"
    )
    add("")
    for f in facts:
        for code, name, city, address in f.sample_stores:
            add(f"- {f.name}, store {code}: {name}; city `{city}`; address `{address}`")
    add("")
    add("## 3. The exit report generator on that day")
    add("")
    add(f"`build_exit_report` for {REAL_DAY} to {REAL_DAY} over the ten D13 chains, then over the "
        f"{len(present)} chains that have a real file. One day cannot meet a 14-day criterion, so "
        "the generator says \"not met\" by construction; what this run checks is that every "
        "section renders on real data and that the numbers are the ones the database holds.")  # fmt: skip
    add("")
    add(f"- Ten chains: success rate **{real_report.success_rate * 100:.1f}%** "
        f"({sum(c.successes for c in real_report.chains)} of "
        f"{len(real_report.chains) * real_report.window_days} chain-days), longest streak "
        f"{real_report.longest_streak} days.")  # fmt: skip
    add(
        f"- The {len(present)} chains with a real file: "
        f"**{real_report_seen.success_rate * 100:.1f}%**, streak {real_report_seen.longest_streak}."
    )
    missing = [c.chain.name for c in real_report.chains if not c.successes]
    add(f"- Chains with no loaded full file on the day: {', '.join(missing) or 'none'}.")
    add(f"- Stores: {real_report.physical_stores} physical, "
        f"{real_report.stores_with_coordinates} with coordinates, "
        f"{real_report.stores_missing_coordinates} listed as exceptions (the report prints the "
        f"first {rep.MAX_LISTED_STORES}).")  # fmt: skip
    add(f"- Promos: {sum(s.total for s in real_report.promo_stats)} parsed (the real set has no "
        "PromoFull file).")  # fmt: skip
    add("")
    L += details(
        "Generator output, real day, ten chains (verbatim)",
        demote(rep.render_markdown(real_report)),
    )
    add("Basket query on the real database (`supabase/queries/basket_radius.sql`):")
    add("")
    add("- Barcodes sold by more than one chain in this sample: "
        + ", ".join(f"{n} chain{'s' if n > 1 else ''}: {c}" for n, c in sorted(overlap.items()))
        + " (each chain's file is cut to 200 rows, so overlap here says little about the full "
        "catalogs; estimate).")  # fmt: skip
    if spot:
        add(
            f"- Prices do come back for real items (spot check with `current_price`, barcodes "
            f"{', '.join(f'`{b}`' for b in spot_barcodes)}):"
        )
        add("")
        L += md_table(["Barcode", "Item (as the chain names it)", "Chain", "Store", "Store name", "Price", "Valid from"],
                      [[b, n, c, sc, sn, p, f"{vf:%Y-%m-%d %H:%M}"] for b, n, c, sc, sn, p, vf in spot])  # fmt: skip
        add("")
    add(f"- Run for {len(spot_barcodes)} shared barcodes around Tel Aviv (lat {TEL_AVIV[1]}, "
        f"lon {TEL_AVIV[0]}), 5 km: **{len(real_basket)} stores returned**. No store has coordinates, so "
        "`stores_within` finds none. The query is not the blocker; the coordinates are.")  # fmt: skip
    add("")
    add("## 4. The synthetic set through the same report")
    add("")
    add("Sections 2 to 4 of the report need data the real set does not have (promos, coordinates, "
        "several days, failures). The synthetic set has them, so this shows what the finished "
        "report looks like. Synthetic data proves the generator, not the pipeline's behavior on "
        "chains (measured on fixtures written by us).")  # fmt: skip
    add("")
    bad = Counter(o.status for o in synth_outcomes)
    add(
        f"- Files: {len(synth_outcomes)}; "
        + ", ".join(f"{k} {v}" for k, v in sorted(bad.items()))
        + "."
    )
    add(f"- Window {SYNTH_START} to {SYNTH_END}: success rate **{synth_report.success_rate * 100:.1f}%**, "
        f"longest streak {synth_report.longest_streak} days, {len(synth_report.failed_files)} full "
        "files that did not load (listed by the generator with their reasons).")  # fmt: skip
    add(f"- Stores: {synth_stores[0]} physical, {synth_stores[1]} with coordinates.")
    add(
        f"- Promos parsed for the main chains: {synth_promos}; the sampler gives up to "
        f"{rep.PROMO_SAMPLE_SIZE} per chain with the raw description next to the structured fields."
    )
    if synth_basket_params is not None:
        add(f"- Basket: {len(synth_basket)} stores in {synth_basket_params['radius_m']:.0f} m of "
            f"({synth_basket_params['lat']:.4f}, {synth_basket_params['lon']:.4f}); "
            f"{sum(1 for b in synth_basket if b['is_complete'])} complete; missing items are listed "
            "per store, not dropped.")  # fmt: skip
    add("")
    L += details(
        "Generator output, synthetic window (verbatim)", demote(rep.render_markdown(synth_report))
    )
    add("## 5. Which criteria can pass, and which cannot yet")
    add("")
    add("Criteria are those of issue #60 and `phase-0-exit-report.md`.")
    add("")
    L += md_table(
        ["Criterion", "Dry run (measured)", "Can it pass yet?"],
        [
            ["1. More than 95% nightly loads over 14 consecutive days",
             f"1 day, {len(present)} of {total_chains} chains had a loaded full file "
             f"({real_report.success_rate * 100:.0f}%). On the {len(present)} chains with a real "
             f"file, {real_report_seen.success_rate * 100:.0f}% (one day, one file each, no nightly "
             "history).",
             "**No.** Needs 14 days of timers on the VPS (#14, #22), and a real file for Victory, "
             "Hazi Hinam and Machsanei Hashuk (not in the committed set)."],
            ["2. Every physical store has coordinates, or exceptions listed with reasons",
             f"{with_coords} of {physical} physical stores have coordinates. The city field is a "
             f"number for all {with_city} stores that have one ({zero} of them `0`); street "
             "addresses are present for most.",
             "**No.** Nothing in the repository geocodes stores (`stores.geog` is NULL until "
             "something fills it). Needs a decision on the method and a city-code table first."],
            ["3. Promo parsing demonstrated for the top chains, with a checked sample",
             f"0 real promos (no PromoFull in the real set). Synthetic: {synth_promos} promos "
             "parsed, the sampler and its table render.",
             "**No.** Needs real PromoFull files from the six main chains and a person to tick "
             "the sample against the raw descriptions."],
            ["4. Basket SQL over a radius, missing items reported",
             f"Runs on real prices (spot check above) but returns {len(real_basket)} stores "
             f"because no store has coordinates. Synthetic: {len(synth_basket)} stores with "
             "missing barcodes listed.",
             "**Partly.** The query and its sample output are done (`phase-0-exit-report.md` "
             "section 4); the real-data run waits for criterion 2."],
            ["Go or no-go", "Not decided on evidence.", "**NO-GO**, unchanged."],
        ],
    )  # fmt: skip
    add("")
    add("## 6. Findings from the real files")
    add("")
    add("Each is measured on the committed fixtures unless it says otherwise.")
    add("")
    all_codes: Counter[str] = Counter()
    for f in facts:
        all_codes.update({k: v for k, v in f.city_counts.items() if k != "0"})
    top = ", ".join(f"`{k}` ({v})" for k, v in all_codes.most_common(5))
    add(f"1. **Stores carry no coordinates, and the city is a number.** All {with_city} stores "
        f"with a city field hold a number, not a name: {zero} hold `0` (no city; the store name "
        f"usually names the place), the others a code, most often {top}. They look like Central "
        "Bureau of Statistics locality codes (3000 is Jerusalem and 7100 is Ashkelon, and the "
        "stores carrying them are there; estimate from the sample, confirm against the published "
        "code list). Geocoding needs the code turned into a name where there is one, and the "
        "store name and street address where there is not.")  # fmt: skip
    add("2. **A PriceFull is one store.** Each chain's real file is the prices of a single "
        f"store ({sum(f.stores_with_prices for f in facts)} stores with prices across "
        f"{len(facts)} chains), so a basket run on real data can price {sum(f.stores_with_prices for f in facts)} "
        "stores today. The nightly run must fetch every store's file; the size of that run (files "
        "and minutes per night) is unmeasured.")  # fmt: skip
    capped = [f for f in facts if f.max_name_len <= 24]
    add("3. **Item names are cut by the chains.** The longest name is "
        + ", ".join(f"{f.name} {f.max_name_len}" for f in facts)
        + f" characters; {len(capped)} of {len(facts)} chains stop at 24 or fewer"
        + (f" ({', '.join(f.name for f in capped)})" if capped else "")
        + ". Names alone will not carry matching (D4, D5): the barcode and the manufacturer "
        "field matter more.")  # fmt: skip
    add("4. **Barcode coverage differs a lot.** "
        + "; ".join(f"{f.name} {pct(f.with_barcode, f.items)}" for f in facts)
        + ". Items without a barcode can only be matched by name.")  # fmt: skip
    add("5. **Manufacturer is often \"לא ידוע\" or empty:** "
        + "; ".join(f"{f.name} {pct(f.unknown_manufacturer, f.items)}" for f in facts)
        + ". The private-label rules cannot lean on it.")  # fmt: skip
    pf = [o for o in real_outcomes if o.kind == "price_full"]
    late = [o.chain for o in pf if first_pass_that_sees(o.published_at) != "06:00"]
    early = [o.chain for o in pf if o.published_at.astimezone(ISRAEL).hour < 1]
    add(f"6. **Publication time decides which pass loads a file** (derived from the timers). "
        f"PriceFull files published after 06:00 Israel time: {', '.join(late) or 'none'}. They "
        "wait for the 08:30 pass, so a check at 06:00 would show them missing. Published in the "
        f"first hour of the day: {', '.join(early) or 'none'}; the report counts a file on the "
        "Israel date of `published_at`, so those belong to the date in their name.")  # fmt: skip
    add("7. **Two gates had nothing to compare against.** `price_jump` and `item_count_drop` need a "
        "previous load of the same store or file kind; on a first real day they cannot fire, so "
        "none of the gates' real-data behavior beyond `zero_price` and `stale_date` is shown. Day 2 "
        "of the real window is the first test of them.")  # fmt: skip
    add("8. **No promo file was fetched.** The probe's fixtures are Stores and PriceFull only. "
        "The promo parser has never read a real chain file in this repository. This is the largest "
        "unknown for criterion 3.")  # fmt: skip
    add("9. **Three D13 chains are missing from the real set** (Victory, Hazi Hinam, Machsanei "
        "Hashuk). The probe ran on a non-Israeli runner; the reason for each is in that probe "
        "run's report, not in this repository (to confirm).")  # fmt: skip
    add("")
    add("## 7. What the owner runs on the VPS later")
    add("")
    add("Everything here is written from the unit files in `infra/vps` and from "
        "`docs/infra-provisioning.md`; none of it has run on a VPS (the VPS does not exist yet). "
        "The order is that document's section 8.")  # fmt: skip
    add("")
    add("**Once, after #14 and #22 exist** (`infra-provisioning.md` sections 5.3 to 5.5):")
    add("")
    add("```bash")
    add("cd ~/SmartCart && sudo bash infra/vps/setup.sh")
    add("sudoedit /etc/smartcart/ingest.env        # DATABASE_URL, S3_* (see .env.example)")
    add("sudo systemctl start smartcart-ingest-full.timer smartcart-ingest-delta.timer")
    add("bash infra/smoke/check_israeli_ip.sh && bash infra/smoke/check_portals.sh")
    add("sudo systemctl start smartcart-ingest-full.service      # first full sync now")
    add("```")
    add("")
    add(
        "**Every day for 14 days** (a minute; the day is attributed by Israel date of `published_at`):"
    )
    add("")
    add("```bash")
    add("systemctl list-timers 'smartcart-*'")
    add(
        "sudo -u smartcart -H bash -c 'set -a; . /etc/smartcart/ingest.env; "
        "/opt/smartcart/.venv/bin/smartcart-ingest status'"
    )
    add("tail -n 100 /var/log/smartcart/ingest-full.log")
    add("```")
    add("")
    add("**Fix the gaps this dry run found, before the window closes:** a geocoding step for "
        "criterion 2 (none exists), real PromoFull files for criterion 3, and real files for the "
        "three missing chains. Decide the tie-break of D13 early (see the `--only-chains` note "
        "below).")  # fmt: skip
    add("")
    add("**After day 14** (`phase-0-exit-report.md`, \"How to regenerate\"). Replace START, END and "
        "the barcodes; the barcodes should be 10 to 20 products several chains sell (milk, eggs, "
        "bread, oil):")  # fmt: skip
    add("")
    add("```bash")
    add("START=<first day> END=<last day>     # YYYY-MM-DD, inclusive, at least 14 days")
    add("BARCODES=<comma-separated barcodes>")
    add('sudo -u smartcart -H env START="$START" END="$END" BARCODES="$BARCODES" bash -c \'')
    add("  set -a; . /etc/smartcart/ingest.env; cd /opt/smartcart")
    add('  .venv/bin/python -m smartcart_ingest.report --start "$START" --end "$END" \\')
    add('    --basket-barcodes "$BARCODES" --lon 34.7818 --lat 32.0853 --radius-m 3000 \\')
    add("    --out /var/lib/smartcart/phase-0-evidence.md'")
    add("cat /var/lib/smartcart/phase-0-evidence.md      # or copy it to your laptop with scp")
    add("```")
    add("")
    add("If the D13 tie-break drops King Store and Machsanei Hashuk, add this flag to the report "
        "command and say so in the report: `--only-chains \"Shufersal,Rami Levy,Victory,"
        "Yeinot Bitan and Carrefour,Hazi Hinam,Tiv Taam,Osher Ad,Yohananof\"`.")  # fmt: skip
    add("")
    add(
        "Then paste the generated sections into `docs/phase-0-exit-report.md`, tick the promo "
        "sample by hand, fill the exception plans, and make the go or no-go decision there."
    )
    add("")
    add("## 8. Reproduce this file")
    add("")
    add("```bash")
    add(
        "scripts/exit_dry_run/run.sh          # needs Postgres server binaries with PostGIS and pgvector"
    )
    add("```")
    add("")
    add("`run.sh` starts a throwaway cluster (or uses `DATABASE_URL` as a server), creates two "
        "databases, loads both file sets, runs the report over each window, writes this file, "
        "and removes the databases. Tests: `uv run --no-sync pytest scripts/exit_dry_run/tests -q`.")  # fmt: skip
    return "\n".join(L).rstrip() + "\n"


# --- main -------------------------------------------------------------------------------------------


def run(admin_dsn: str, out: Path, keep: bool = False) -> dict:
    quiet_logs()
    dsn_real = create_database(admin_dsn, DB_REAL)
    dsn_syn = create_database(admin_dsn, DB_SYNTH)
    try:
        real_outcomes, real_alerts = replay(dsn_real, fixture_set("real"))
        synth_outcomes, _ = replay(dsn_syn, fixture_set("synthetic"))

        with psycopg.connect(dsn_real) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            server = server_facts(conn)
            facts = chain_facts(conn)
            overlap = barcode_overlap(conn)
            shared = shared_barcodes(conn, 3, 2)
            spot = price_spot_check(conn, shared) if shared else []
            real_report = rep.build_exit_report(conn, REAL_DAY, REAL_DAY)
            names_seen = {c.chain.name for c in real_report.chains if c.successes}
            seen_specs = tuple(c for c in rep.D13_CHAINS if c.name in names_seen)
            real_report_seen = rep.build_exit_report(conn, REAL_DAY, REAL_DAY, chains=seen_specs)
            real_basket = rep.run_basket_query(conn, shared, TEL_AVIV[0], TEL_AVIV[1], 5000)
            real_report.basket_params = {"barcodes": shared, "lon": TEL_AVIV[0], "lat": TEL_AVIV[1],
                                         "radius_m": 5000.0, "include_online": False}  # fmt: skip
            real_report.basket_rows = real_basket

        with psycopg.connect(dsn_syn) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            synth_report = rep.build_exit_report(conn, SYNTH_START, SYNTH_END)
            center = centroid(conn)
            synth_codes = shared_barcodes(conn, 3, 2)
            params = None
            synth_basket: list[dict] = []
            if center and synth_codes:
                params = {"lon": center[0], "lat": center[1], "radius_m": 15000.0}
                synth_basket = rep.run_basket_query(
                    conn, synth_codes, center[0], center[1], 15000.0
                )
                synth_report.basket_params = {
                    "barcodes": synth_codes,
                    **params,
                    "include_online": False,
                }
                synth_report.basket_rows = synth_basket
            synth_stores = (synth_report.physical_stores, synth_report.stores_with_coordinates)

        text = render(
            server=server, real_outcomes=real_outcomes, real_alerts=real_alerts, facts=facts,
            overlap=overlap, spot=spot, spot_barcodes=shared, real_report=real_report,
            real_report_seen=real_report_seen, real_basket=real_basket,
            synth_outcomes=synth_outcomes, synth_report=synth_report, synth_basket=synth_basket,
            synth_basket_params=params, synth_stores=synth_stores,
        )  # fmt: skip
        out.write_text(text, encoding="utf-8")
        return {"out": str(out), "real_files": len(real_outcomes),
                "real_loaded": sum(1 for o in real_outcomes if o.status == "loaded"),
                "synthetic_files": len(synth_outcomes)}  # fmt: skip
    finally:
        if not keep:
            drop_database(admin_dsn, DB_REAL)
            drop_database(admin_dsn, DB_SYNTH)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--dsn", help="server DSN that may CREATE DATABASE (default $DATABASE_URL)")
    p.add_argument("--out", type=Path, default=OUT_DEFAULT)
    p.add_argument("--keep", action="store_true", help="keep the two databases for inspection")
    args = p.parse_args(argv)
    dsn = args.dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        print("no --dsn and DATABASE_URL is not set", file=sys.stderr)
        return 2
    result = run(dsn, args.out, args.keep)
    print(f"wrote {result['out']}: {result['real_loaded']} of {result['real_files']} real files "
          f"loaded, {result['synthetic_files']} synthetic files replayed")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
