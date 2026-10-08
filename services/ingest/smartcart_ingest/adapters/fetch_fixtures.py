"""Download one REAL transparency file per chain and kind, to replace the synthetic fixtures.

The chain portals are not reachable from the development container (at least one blocks cloud
IP ranges), so the checked-in fixtures are synthetic. Run this on a machine with portal access,
normally the Israeli-IP ingestion VPS:

    uv run python -m smartcart_ingest.adapters.fetch_fixtures            # every chain
    uv run python -m smartcart_ingest.adapters.fetch_fixtures shufersal ramilevy
    uv run python -m smartcart_ingest.adapters.fetch_fixtures --list     # plan only, no network
    uv run python -m smartcart_ingest.adapters.fetch_fixtures machsanei_hashuk king_store
    uv run python -m smartcart_ingest.adapters.fetch_fixtures --kind stores --kind price_full \
        --timeout 300 --out /tmp/probe          # what scripts/unblock/portal_probe.py fetches

Every registered chain is fetched through its adapter's ``upstream_scraper``. The laibcatalog
chains (victory, machsanei_hashuk) list no files overnight until about 08:00 Israel time, and
machsanei_hashuk none on Saturdays either, so run it later in the day.

Files land in ``services/ingest/tests/fixtures/real/<slug>/`` under their portal filename, raw
(still gzip/zip, never re-encoded), next to a ``manifest.json`` with sha256, size and the parse
result from our adapter. ``tests/test_adapters.py`` parses everything under ``fixtures/real``
automatically. To promote a real file to a regression fixture, move it into the chain folder
and add its literal counts and field values to that folder's ``expected.json``; then delete the
synthetic file it replaces.

Only the legally mandated transparency portals are contacted, through the pinned upstream
scraper. Never point this at a chain's online store.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from smartcart_ingest.adapters import REGISTRY
from smartcart_ingest.adapters._common import RegulationAdapter, parse_filename
from smartcart_ingest.adapters.base import AdapterError

KIND_FILTERS = {
    "stores": "STORE_FILE",
    "price_full": "PRICE_FULL_FILE",
    "promo_full": "PROMO_FULL_FILE",
}
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "real"


def adapters_by_slug() -> dict[str, type[RegulationAdapter]]:
    return {
        cls.slug: cls
        for cls in REGISTRY.values()
        if isinstance(cls, type) and issubclass(cls, RegulationAdapter) and cls.upstream_scraper
    }


def plan(
    slugs: list[str] | None = None, kinds: list[str] | None = None
) -> list[tuple[str, str, str]]:
    """``[(slug, upstream scraper name, kind)]`` without touching the network. ``kinds``
    limits the plan to those file kinds (keys of ``KIND_FILTERS``), kept in that table's order."""
    available = adapters_by_slug()
    chosen = slugs or sorted(available)
    unknown = sorted(set(chosen) - set(available))
    if unknown:
        raise SystemExit(f"unknown chain slug(s): {', '.join(unknown)}")
    bad_kinds = sorted(set(kinds or ()) - set(KIND_FILTERS))
    if bad_kinds:
        raise SystemExit(f"unknown kind(s): {', '.join(bad_kinds)}; expected {list(KIND_FILTERS)}")
    wanted = [k for k in KIND_FILTERS if not kinds or k in kinds]
    return [
        (slug, available[slug].upstream_scraper or "", kind) for slug in chosen for kind in wanted
    ]


async def _download(scraper_name: str, kind: str, workdir: Path) -> list[Path]:
    from smartcart_ingest.download import quiet_upstream_loggers

    quiet_upstream_loggers()
    from il_supermarket_scarper import FileTypesFilters, ScraperFactory
    from il_supermarket_scarper.utils import DiskFileOutput

    scraper_cls = ScraperFactory[scraper_name].value
    scraper = scraper_cls(file_output=DiskFileOutput(str(workdir / "files"), extract_gz=False))
    file_type = FileTypesFilters[KIND_FILTERS[kind]].name
    async for _result in scraper.scrape(limit=1, files_types=[file_type]):
        pass
    return sorted(p for p in (workdir / "files").rglob("*") if p.is_file())


def fetch(
    slug: str, scraper_name: str, kind: str, out_dir: Path, timeout: float | None = None
) -> dict:
    """Download one file of ``kind`` for the chain into ``out_dir/<slug>/`` and describe it.
    ``timeout`` (seconds) bounds the upstream scrape; when it expires ``TimeoutError`` is
    raised (``main`` records it as that chain's error and carries on)."""
    adapter = adapters_by_slug()[slug]()
    target = out_dir / slug
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        files = asyncio.run(asyncio.wait_for(_download(scraper_name, kind, Path(tmp)), timeout))
        for path in files:
            try:
                info = parse_filename(path.name)
            except ValueError:
                continue
            if info.kind != kind:
                continue
            data = path.read_bytes()
            dest = target / path.name
            shutil.copyfile(path, dest)
            entry: dict = {
                "file": path.name,
                "kind": kind,
                "store_code": info.store_code,
                "published_at": (
                    info.published_at.isoformat(timespec="minutes") if info.published_at else None
                ),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "scraper": scraper_name,
            }
            try:
                parsed = adapter.parse(adapter.raw_file_for(path.name, data), data)
                entry["parse"] = {
                    "schema": parsed.raw.schema_version,
                    "stores": len(parsed.stores),
                    "online_stores": sorted(s.store_code for s in parsed.stores if s.channel == "online"),
                    "items": len(parsed.items),
                    "prices": len(parsed.prices),
                    "promos": len(parsed.promos),
                }
            except AdapterError as exc:
                entry["parse_error"] = f"{type(exc).__name__}: {exc}"
            return entry
    return {"kind": kind, "scraper": scraper_name, "error": "no file downloaded"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("chains", nargs="*", help="chain slugs (default: all registered)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--list", action="store_true", help="print the plan and exit")
    parser.add_argument("--kind", action="append", choices=list(KIND_FILTERS),
                        help="only this file kind (repeatable; default: all three)")  # fmt: skip
    parser.add_argument("--timeout", type=float, default=None,
                        help="seconds allowed per download (default: no limit)")  # fmt: skip
    args = parser.parse_args(argv)

    steps = plan(args.chains or None, args.kind)
    if args.list:
        for slug, scraper, kind in steps:
            print(f"{slug:16} {scraper:28} {kind}")
        return 0

    manifest: dict[str, list[dict]] = {}
    failures = 0
    for slug, scraper, kind in steps:
        print(f"fetching {slug} {kind} via {scraper} ...", flush=True)
        try:
            entry = fetch(slug, scraper, kind, args.out, timeout=args.timeout)
        except Exception as exc:  # noqa: BLE001 - report every chain, keep going
            entry = {"kind": kind, "scraper": scraper, "error": f"{type(exc).__name__}: {exc}"}
        failures += int("error" in entry or "parse_error" in entry)
        manifest.setdefault(slug, []).append(entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
