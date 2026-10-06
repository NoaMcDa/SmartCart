"""Per-chain adapters. Import a chain module to register it; use get_adapter(chain_id)."""

from smartcart_ingest.adapters.base import REGISTRY, ChainAdapter, get_adapter, register

__all__ = ["REGISTRY", "ChainAdapter", "get_adapter", "register"]

# Importing the chain modules registers their adapters.
from smartcart_ingest.adapters import (  # noqa: E402, F401
    hazihinam,
    mega,
    osherad,
    ramilevy,
    shufersal,
    tivtaam,
    victory,
    yohananof,
)
