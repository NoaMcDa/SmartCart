"""Adapter contract.

An adapter isolates one chain's portal and XML dialect (encoding, zip/gzip, <Item>/<Product>,
field names, schema version) from the internal model in smartcart_ingest.models. Nothing outside
this package may import il_supermarket_scarper or il_supermarket_parsers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from smartcart_ingest.models import (
    FileKind,
    ParsedFile,
    Portal,
    RawFile,
    SchemaVersion,
    StoreRecord,
)


class AdapterError(Exception):
    """Raised by an adapter when a file cannot be parsed. Always names the chain."""

    def __init__(self, chain_id: str, message: str) -> None:
        self.chain_id = chain_id
        super().__init__(f"[{chain_id}] {message}")


class UnknownSchemaError(AdapterError):
    """The file's schema is neither v1 nor v2. The loader must not load it and must alert."""


class ChainAdapter(ABC):
    chain_id: ClassVar[str]
    display_name: ClassVar[str]
    portal: ClassVar[Portal]
    aliases: ClassVar[tuple[str, ...]] = ()
    """Other chain ids this adapter serves (a chain that publishes under two ids)."""

    @abstractmethod
    def detect_kind(self, filename: str) -> FileKind:
        """Map a portal filename (e.g. PriceFull7290027600007-001-202610060600.gz) to a FileKind."""

    @abstractmethod
    def detect_schema(self, xml_root: Any) -> SchemaVersion:
        """Return v1, v2 or unknown for this file.

        The caller may pass a partially built root (the header plus the first row) when it
        streams large files, so only inspect the root element, its attributes and header
        children; never rely on the full row set being present.
        """

    @abstractmethod
    def parse(self, raw: RawFile, data: bytes) -> ParsedFile:
        """Decode (encoding, zip, gzip), parse, and map to internal records.

        Must raise UnknownSchemaError when detect_schema returns "unknown" and AdapterError on
        any other failure. Must never return an empty ParsedFile silently for a non-empty file.
        """

    def online_store_rule(self, store: StoreRecord) -> bool:
        """True when this store row is the chain's online/delivery channel. Default: no rule."""
        return False


REGISTRY: dict[str, type[ChainAdapter]] = {}


def register(cls: type[ChainAdapter]) -> type[ChainAdapter]:
    """Class decorator: registers an adapter under its chain_id."""
    for cid in (cls.chain_id, *cls.aliases):
        if cid in REGISTRY:
            raise ValueError(f"adapter already registered for {cid}")
    for cid in (cls.chain_id, *cls.aliases):
        REGISTRY[cid] = cls
    return cls


def get_adapter(chain_id: str) -> ChainAdapter:
    try:
        return REGISTRY[chain_id]()
    except KeyError as exc:
        raise KeyError(f"no adapter registered for chain {chain_id!r}") from exc
