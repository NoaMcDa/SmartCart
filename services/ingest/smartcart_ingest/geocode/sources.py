"""Where the stores to geocode come from: the real Stores fixtures, or a database."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from smartcart_ingest.geocode.resolve import GeoIndex
from smartcart_ingest.geocode.stores import StoreInput

MANIFEST_NAMES = {"MANIFEST.json", "manifest.json"}


def default_fixtures_root() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def stores_from_fixtures(root: Path | None = None) -> list[StoreInput]:
    """Physical stores of every ``<chain>/real/Stores*`` file under ``root``, parsed by the chain
    adapters (the same code path as the loader). Online stores are left out. When a store appears
    in several files the newest file wins."""
    from smartcart_ingest.adapters import REGISTRY

    root = root or default_fixtures_root()
    by_slug = {cls.slug: cls for cls in set(REGISTRY.values()) if hasattr(cls, "slug")}
    found: dict[tuple[str, str], StoreInput] = {}
    for chain_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        real = chain_dir / "real"
        adapter_cls = by_slug.get(chain_dir.name)
        if adapter_cls is None or not real.is_dir():
            continue
        adapter = adapter_cls()
        for path in sorted(real.iterdir()):
            if not path.is_file() or path.name in MANIFEST_NAMES:
                continue
            if adapter.detect_kind(path.name) != "stores":
                continue
            data = path.read_bytes()
            raw = adapter.raw_file_for(path.name, data, path=str(path))
            for s in adapter.parse(raw, data).stores:
                if s.channel != "physical":
                    continue
                found[(s.chain_id, s.store_code)] = StoreInput(
                    s.chain_id, s.store_code, s.name, s.address, s.city
                )
    return sorted(found.values(), key=lambda s: (s.chain_id, s.store_code))


def stores_from_database(dsn: str) -> list[StoreInput]:
    import psycopg

    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            "SELECT chain_id, store_code, name, address, city FROM stores"
            " WHERE channel = 'physical' ORDER BY chain_id, store_code"
        ).fetchall()
    return [StoreInput(*row) for row in rows]


def coverage(stores: list[StoreInput], index: GeoIndex) -> Counter[str]:
    """How many of ``stores`` the resolver would place, by precision (``none`` for the rest)."""
    counts: Counter[str] = Counter()
    for s in stores:
        point = index.resolve(s.chain_id, s.store_code, s.city)
        counts[point.precision if point else "none"] += 1
    return counts
