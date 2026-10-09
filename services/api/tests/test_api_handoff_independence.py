"""Issue #72: ranking and savings are independent of the cart handoff and of any referral.

The cart handoff (``GET /chains/online``, the ``CART_HANDOFF_CHAINS`` flag, the ``online_*`` chain
columns) is a link to the chain's own public site. ``/compare`` and ``/optimize`` must return
byte-identical bodies with the flag set or unset and with referral flags on or off, and no ranking
module may read the handoff columns or setting. A failure here means the money motive leaked into
the ranking (D10, D12).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from api_world import World, add_store

from smartcart_api.precompute import precompute_effective_prices
from smartcart_api.routes import compare as compare_route
from smartcart_api.routes import optimize as optimize_route
from smartcart_api.settings import get_settings

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]

FROZEN = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
PKG = Path(__file__).resolve().parents[1] / "smartcart_api"


class _Clock(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return FROZEN


@pytest.fixture
def w(db: psycopg.Connection, world: World, monkeypatch: pytest.MonkeyPatch) -> World:
    for n, km in enumerate((2.5, 3.0)):
        world.stores[f"c1_{n}"] = add_store(db, "t-c1", f"X{n}", km)
    world.stores["c2_0"] = add_store(db, "t-c2", "Y0", 3.2)
    precompute_effective_prices(db, chains=world.chains)
    # `generated_at` is the only field that changes between two identical requests.
    monkeypatch.setattr(compare_route, "datetime", _Clock)
    monkeypatch.setattr(optimize_route, "datetime", _Clock)
    return world


def basket(w: World) -> list[dict]:
    return [
        {"canonical_id": w.canon["milk3"], "quantity": 2},
        {"canonical_id": w.canon["paste"], "quantity": 1},
        {"canonical_id": w.canon["salmon"], "quantity": 1},
        {"canonical_id": w.canon["bread"], "quantity": 3},
        {"canonical_id": w.canon["eggs"], "quantity": 1},
    ]


def bodies(client, w: World) -> tuple[bytes, bytes]:
    common = {"items": basket(w), "location": w.location}
    c = client.post("/compare", json=common)
    o = client.post(
        "/optimize",
        json={**common, "home_store_id": w.stores["home"], "min_split_saving": 1},
    )
    assert c.status_code == 200, c.text
    assert o.status_code == 200, o.text
    return c.content, o.content


def configure(
    db: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
    *,
    flag: str | None,
    urls: bool,
    referral: bool,
) -> None:
    if flag is None:
        monkeypatch.delenv("CART_HANDOFF_CHAINS", raising=False)
    else:
        monkeypatch.setenv("CART_HANDOFF_CHAINS", flag)
    get_settings.cache_clear()
    db.execute(
        "UPDATE chains SET online_url = %s, search_url_template = %s, online_referral = %s"
        " WHERE id LIKE 't-c%%'",
        (
            "https://shop.example/" if urls else None,
            "https://shop.example/s?q={q}" if urls else None,
            referral,
        ),
    )


def test_compare_and_optimize_are_byte_identical_whatever_the_handoff_says(
    client, db: psycopg.Connection, w: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(db, monkeypatch, flag=None, urls=False, referral=False)
    baseline = bodies(client, w)
    assert b"shop.example" not in baseline[0] + baseline[1]

    for flag in (None, "t-c1", "t-c2", "t-c1,t-c2"):
        for urls in (False, True):
            for referral in (False, True):
                configure(db, monkeypatch, flag=flag, urls=urls, referral=referral)
                assert bodies(client, w) == baseline, (flag, urls, referral)


def test_a_referral_on_the_cheaper_chain_cannot_change_the_recommendation(
    client, db: psycopg.Connection, w: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Referral on only one chain, enabled, with addresses: the winner is the same as without."""
    configure(db, monkeypatch, flag=None, urls=False, referral=False)
    winner = lambda: client.post(  # noqa: E731
        "/optimize", json={"items": basket(w), "location": w.location}
    ).json()["single"]["stores"][0]["store"]["store_id"]
    before = winner()
    for chain in ("t-c1", "t-c2"):
        configure(db, monkeypatch, flag=chain, urls=True, referral=False)
        db.execute("UPDATE chains SET online_referral = true WHERE id = %s", (chain,))
        assert winner() == before


# The ranking inputs. These modules decide which stores are shown, in which order, at what price
# and what is saved; none may read the handoff columns, the flag or the chains route.
RANKING_MODULES = (
    "basket.py",
    "precompute.py",
    "milp.py",
    "swaps.py",
    "search.py",
    "routes/compare.py",
    "routes/optimize.py",
    "routes/swaps.py",
)
HANDOFF_TERMS = re.compile(
    r"online_url|search_url_template|online_referral|referral|cart_handoff|CART_HANDOFF|routes\.chains|chain_online",
    re.IGNORECASE,
)


@pytest.mark.parametrize("module", RANKING_MODULES)
def test_ranking_modules_never_mention_handoff_data(module: str) -> None:
    text = (PKG / module).read_text(encoding="utf-8")
    assert not HANDOFF_TERMS.search(text), f"{module} reads handoff data"


def test_no_ranking_query_selects_every_chain_column() -> None:
    """``SELECT * FROM chains`` would pull the handoff columns into ranking code."""
    for module in RANKING_MODULES:
        text = (PKG / module).read_text(encoding="utf-8")
        assert not re.search(
            r"SELECT\s+\*\s+FROM\s+chains|chains\.\*|\bc\.\*", text, re.IGNORECASE
        ), module
