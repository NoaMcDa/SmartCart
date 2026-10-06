"""Sales-channel tagging for store records (issue #53).

Online prices differ from in-store prices (verified in the research), so every store row is
tagged ``physical`` or ``online`` and comparisons filter to physical stores by default.

The decision is layered, first match wins:

1. **Declared by the source.** The adapter already set ``channel="online"`` while parsing,
   from a source field that is not part of ``StoreRecord`` (the regulation's ``StoreType``
   of 2, or a sub-chain name such as Shufersal's ``ONLINE`` sub-chain).
2. **Chain rule.** ``adapter.online_store_rule(store)``: name, address or store-code patterns
   documented per chain in ``docs/adapters.md``.
3. **Shared fallback heuristic.** Store name, city or address contains one of
   :data:`ONLINE_KEYWORDS`, or the store code is in the adapter's ``online_store_codes``.

Everything else is ``physical``.
"""

from __future__ import annotations

from collections.abc import Iterable

from smartcart_ingest.adapters.base import ChainAdapter
from smartcart_ingest.models import StoreRecord

ONLINE_KEYWORDS: tuple[str, ...] = ("אונליין", "און ליין", "online", "משלוחים", "אינטרנט")
"""Matched case-insensitively against name, city and address."""


def heuristic_is_online(store: StoreRecord, online_store_codes: Iterable[str] = ()) -> bool:
    """The chain-independent fallback: a keyword in name/city/address, or a known code."""
    haystack = " ".join(filter(None, (store.name, store.city, store.address))).casefold()
    if any(keyword.casefold() in haystack for keyword in ONLINE_KEYWORDS):
        return True
    return store.store_code in set(online_store_codes)


def tag_channel(adapter: ChainAdapter, store: StoreRecord) -> StoreRecord:
    """Return ``store`` with ``channel`` set to ``online`` or ``physical``. Never mutates."""
    if store.channel == "online":
        return store
    codes = getattr(adapter, "online_store_codes", frozenset())
    online = adapter.online_store_rule(store) or heuristic_is_online(store, codes)
    channel = "online" if online else "physical"
    if channel == store.channel:
        return store
    return store.model_copy(update={"channel": channel})


def tag_all(adapter: ChainAdapter, stores: Iterable[StoreRecord]) -> list[StoreRecord]:
    return [tag_channel(adapter, store) for store in stores]
