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
synthetic file it replaces. The portal-probe workflow's ``commit_fixtures`` path instead commits
real files to ``tests/fixtures/<slug>/real/`` (PriceFull trimmed by ``trim_price_file``), next to
the synthetic ones; ``tests/test_adapters.py`` reads both locations.

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


# --- trimming a real PriceFull into a small regression fixture -------------------------------------


_PY_CODECS = {"utf-8": "utf-8", "utf-8-sig": "utf-8", "utf-16-le": "utf-16-le",
              "utf-16-be": "utf-16-be"}  # fmt: skip
_BOMS = {"utf-8-sig": b"\xef\xbb\xbf", "utf-16-le": b"\xff\xfe", "utf-16-be": b"\xfe\xff"}


def _rewrap(payload: bytes, container: str, original: bytes) -> bytes:
    """Put ``payload`` back into the outer container of ``original`` (gzip, zip or none)."""
    import gzip
    import io
    import zipfile

    if container == "gzip":
        return gzip.compress(payload, mtime=0)
    if container == "zip":
        with zipfile.ZipFile(io.BytesIO(original)) as zf:
            members = [m for m in zf.infolist() if not m.is_dir()]
            xml = [m for m in members if m.filename.lower().endswith(".xml")]
            name = (xml or members)[0].filename
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(name, payload)
        return buf.getvalue()
    return payload


def trim_price_file(data: bytes, max_items: int) -> tuple[bytes, int, int]:
    """Keep the first ``max_items`` rows of a price file and everything around them.

    The file is decoded and parsed exactly as the adapters do (``xmlutil``: containers by magic
    bytes, encoding detection, a parser that resolves no entities and fetches nothing), the
    rows are the elements of the price containers the adapters read (``Items/Item``,
    ``Products/Product``, ``NewDataSet/item``), and rows after the first ``max_items`` are
    removed. The header, the XML declaration as published, the source encoding (with its BOM)
    and the outer container are kept, and a numeric ``Count`` attribute on a container is set
    to the new row count, so the adapter reads the trimmed file the way it reads the original.
    Returns ``(trimmed bytes, rows before, rows after)``; an untrimmed file is returned as is.
    Raises ``ValueError`` when the bytes are not a price file. Only call it on a file the
    adapter has already parsed: downloaded files are untrusted data.
    """
    from lxml import etree

    from smartcart_ingest import xmlutil
    from smartcart_ingest.adapters._common import CONTAINERS

    try:
        payload, container = xmlutil.unwrap(data)
        encoding = xmlutil.detect_encoding(payload)
        utf8, _ = xmlutil.to_utf8(payload)
        parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
        root = etree.fromstring(utf8, parser=parser)
    except (xmlutil.XmlDecodeError, etree.XMLSyntaxError) as exc:
        raise ValueError(f"not a readable XML file: {exc}") from exc
    price_containers = {c: row for c, (group, row) in CONTAINERS.items() if group == "price"}
    rows: list = []
    for el in root.iter():
        name = xmlutil.localname(el)
        if name in price_containers:
            rows.extend(c for c in el if xmlutil.localname(c) == price_containers[name])
    if not rows:
        raise ValueError("no price rows (Items/Item, Products/Product, NewDataSet/item)")
    before = len(rows)
    if before <= max_items:
        return data, before, before
    for row in rows[max_items:]:
        row.getparent().remove(row)
    for el in root.iter():
        if xmlutil.localname(el) in price_containers:
            for key in el.attrib:
                if etree.QName(key).localname.lower() == "count" and el.attrib[key].isdigit():
                    el.attrib[key] = str(sum(1 for c in el if isinstance(c.tag, str)))
    codec = _PY_CODECS.get(encoding, encoding)
    bom = _BOMS.get(encoding, b"")
    if not (bom and payload.startswith(bom)):
        bom = b""
    head = payload[len(bom) : len(bom) + 400].decode(codec, errors="ignore").lstrip()
    decl = head[: head.index("?>") + 2] if head.startswith("<?xml") and "?>" in head else ""
    text = (decl + "\n" if decl else "") + etree.tostring(root, encoding="unicode")
    return _rewrap(bom + text.encode(codec), container, data), before, max_items


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
