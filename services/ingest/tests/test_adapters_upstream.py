"""Cross-check our per-chain dialects against the pinned upstream parser configuration.

If an upstream version bump changes a chain's container elements, this fails and names the
chain, so the adapter (and its fixture) is updated deliberately rather than breaking in
production.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from smartcart_ingest.adapters import REGISTRY
from smartcart_ingest.adapters._common import CONTAINERS, RegulationAdapter
from smartcart_ingest.adapters._upstream import upstream_containers, upstream_versions

ADAPTERS = {
    cls.slug: cls for cls in REGISTRY.values() if isinstance(cls, type) and issubclass(cls, RegulationAdapter)
}

# Upstream container names we deliberately read differently. Each needs a reason.
DIVERGENCES: dict[tuple[str, str], str] = {
    ("VICTORY", "Store"): (
        "legacy Victory converter reads rows under <Store>; we read the BigID <Branches>/<Branch> "
        "layout and the new-source SubChains layout. Confirm against a real legacy file."
    ),
}

PACKAGE = Path(__file__).parents[1] / "smartcart_ingest"


def test_upstream_versions_are_pinned() -> None:
    versions = upstream_versions()
    assert versions["il-supermarket-parser"] == "1.0.12"
    assert versions["il-supermarket-scraper"].startswith("1.")


@pytest.mark.parametrize("slug", sorted(ADAPTERS))
def test_dialect_covers_upstream_containers(slug: str) -> None:
    cls = ADAPTERS[slug]
    assert cls.upstream_parsers, f"{slug} must name its upstream parser"
    for parser in cls.upstream_parsers:
        for group, keys in upstream_containers(parser).items():
            for key in keys:
                if (parser, key) in DIVERGENCES:
                    continue
                assert key in CONTAINERS, f"{slug}/{parser}: unknown upstream container {key}"
                assert CONTAINERS[key][0] == group, f"{slug}/{parser}: {key} is not a {group} container"
                assert key in cls.containers, f"{slug}/{parser}: {key} missing from dialect"


def test_no_upstream_imports_outside_adapters() -> None:
    """Upstream modules may only be imported inside the adapters package."""
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        if "adapters" in path.relative_to(PACKAGE).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(n.startswith(("il_supermarket_parsers", "il_supermarket_scarper")) for n in names):
                offenders.append(str(path))
    assert offenders == []


def test_fetch_plan_uses_real_upstream_scrapers() -> None:
    from il_supermarket_scarper import ScraperFactory

    from smartcart_ingest.adapters.fetch_fixtures import KIND_FILTERS, plan

    steps = plan()
    assert {slug for slug, _, _ in steps} == set(ADAPTERS)
    assert len(steps) == len(ADAPTERS) * len(KIND_FILTERS)
    for _slug, scraper, _kind in steps:
        assert scraper in ScraperFactory.__members__
