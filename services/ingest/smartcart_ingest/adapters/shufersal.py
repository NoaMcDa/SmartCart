"""Shufersal (שופרסל): own portal prices.shufersal.co.il.

Files: ``PriceFull7290027600007-001-202610060300.gz``, ``PromoFull...``,
``Stores7290027600007-000-202610060201.gz``. Prices and promos use the regulation layout
(``<root>`` > ``<Items>`` > ``<Item>``). The Stores file is the SAP export layout
(``<asx:abap>`` > ``<asx:values>`` > ``<STORES>`` > ``<STORE>`` with upper-case fields); upstream
also accepts the newer ``SubChains`` layout, so both are allowed.

Online record: the ``ONLINE`` sub-chain (``SUBCHAINNAME`` contains ``ONLINE``) or a store
name containing ONLINE / אונליין. Provisional until checked against a real Stores file.
"""

from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.adapters.base import register


@register
class ShufersalAdapter(RegulationAdapter):
    chain_id = "7290027600007"
    display_name = "שופרסל"
    slug = "shufersal"
    portal = "shufersal"
    containers = frozenset({"Items", "Promotions", "STORES", "SubChains", "Stores"})
    upstream_parsers = ("SHUFERSAL",)
    upstream_scraper = "SHUFERSAL"
    online_subchain_markers = ("ONLINE", "אונליין")
    online_name_markers = ("ONLINE", "אונליין")
    has_online_record = True
