"""Per-chain adapters. Import a chain module to register it; use get_adapter(chain_id)."""

from smartcart_ingest.adapters.base import REGISTRY, ChainAdapter, get_adapter, register

__all__ = ["REGISTRY", "ChainAdapter", "get_adapter", "register"]
