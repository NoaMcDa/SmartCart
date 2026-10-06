"""Configuration: the phase 0 chain list (docs/decisions.md D13) and the connection string.

No Streamlit import here, so it is testable on its own.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

STALE_AFTER_HOURS = 24


@dataclass(frozen=True)
class ExpectedChain:
    """One of the ten D13 chains. Some chains publish under more than one chain id."""

    name: str
    chain_ids: tuple[str, ...]
    main: bool  # chains 1 to 6 in D13 get hourly deltas


# docs/decisions.md D13, in table order. Ids are the upstream scraper identifiers.
PHASE0_CHAINS: tuple[ExpectedChain, ...] = (
    ExpectedChain("Shufersal", ("7290027600007",), True),
    ExpectedChain("Rami Levy", ("7290058140886",), True),
    ExpectedChain("Victory", ("7290696200003", "7290058103393"), True),
    ExpectedChain("Yeinot Bitan and Carrefour", ("7290055700007",), True),
    ExpectedChain("Hazi Hinam", ("7290700100008",), True),
    ExpectedChain("Tiv Taam", ("7290873255550",), True),
    ExpectedChain("Osher Ad", ("7290103152017",), False),
    ExpectedChain("Yohananof", ("7290803800003",), False),
    ExpectedChain("Machsanei Hashuk", ("7290661400001", "7290633800006"), False),
    ExpectedChain("King Store", ("7290058108879",), False),
)


@dataclass(frozen=True)
class Connection:
    dsn: str
    warning: str | None  # shown in the UI when not using the read-only variable


def resolve_dsn(env: Mapping[str, str] | None = None) -> Connection | None:
    """DATABASE_URL_READONLY, else DATABASE_URL with a warning, else None."""
    env = os.environ if env is None else env
    readonly = (env.get("DATABASE_URL_READONLY") or "").strip()
    if readonly:
        return Connection(readonly, None)
    fallback = (env.get("DATABASE_URL") or "").strip()
    if fallback:
        return Connection(
            fallback,
            "DATABASE_URL_READONLY is not set, so the dashboard is using DATABASE_URL. Use the "
            "smartcart_readonly role (docs/infra-provisioning.md section 3.1). The dashboard "
            "never writes and opens its connection read-only, but the credentials themselves "
            "should not be able to write either.",
        )
    return None
