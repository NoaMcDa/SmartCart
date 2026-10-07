"""Osher Ad (אושר עד, מרב-מזון כל): Cerberus portal (user osherad).

Files: ``PriceFull7290103152017-012-202610060300.gz``, ``PromoFull...gz``,
``Stores7290103152017-202610060100.xml``. Regulation layout, ``SubChains`` nesting.

Online record: none known. The chain is listed as having no online record until a real Stores
file shows otherwise; the shared heuristic in ``channel.py`` still runs on every store.
"""

from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.adapters.base import register


@register
class OsherAdAdapter(RegulationAdapter):
    chain_id = "7290103152017"
    display_name = "אושר עד"
    slug = "osherad"
    portal = "cerberus"
    upstream_parsers = ("OSHER_AD",)
    upstream_scraper = "OSHER_AD"
    has_online_record = False
