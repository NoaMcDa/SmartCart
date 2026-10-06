"""Read-only bridge to the pinned upstream libraries.

``il_supermarket_parsers`` (OpenIsraeliSupermarkets) encodes each chain's XML layout as
converter objects. We do not run those converters (they produce pandas frames and the project
is beta); we read their configuration as plain strings so a test can fail loudly when an
upstream version bump changes a chain's container elements. Nothing returned from here is an
upstream type.
"""

from __future__ import annotations

from typing import Any

UPSTREAM_GROUP_ATTRS: dict[str, tuple[str, ...]] = {
    "price": ("pricefull_parser", "price_parser"),
    "promo": ("promofull_parser", "promo_parser"),
    "stores": ("stores_parser",),
}


def _list_keys(converter: Any) -> set[str]:
    keys: set[str] = set()
    for attr in ("option_a", "option_b"):
        if getattr(converter, attr, None) is not None:
            keys |= _list_keys(getattr(converter, attr))
    for option in getattr(converter, "options", None) or ():
        keys |= _list_keys(option)
    list_key = getattr(converter, "list_key", None)
    if isinstance(list_key, str) and list_key:
        keys.add(list_key)
    return keys


def upstream_containers(parser_name: str) -> dict[str, set[str]]:
    """``{"price"|"promo"|"stores": {container element names}}`` for a ParserFactory name."""
    from smartcart_ingest.download import quiet_upstream_loggers

    quiet_upstream_loggers()
    from il_supermarket_parsers.parser_factory import ParserFactory

    converter = ParserFactory.get(parser_name)()
    return {
        group: set().union(*(_list_keys(getattr(converter, attr)) for attr in attrs))
        for group, attrs in UPSTREAM_GROUP_ATTRS.items()
    }


def upstream_versions() -> dict[str, str]:
    from importlib.metadata import version

    return {
        "il-supermarket-parser": version("il-supermarket-parser"),
        "il-supermarket-scraper": version("il-supermarket-scraper"),
    }
