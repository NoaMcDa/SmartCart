"""Hazi Hinam (חצי חינם): own web portal (shop.hazi-hinam.co.il/Prices).

Files use the five-part name ``Promo7290700100008-000-207-20261006-030000.xml.gz``
(chain-subchain-store-date-time). Regulation layout; Stores uses ``StoreID`` casing inside
``SubChains`` nesting.

Online record: a store name containing ``אתר`` (the web shop), or a code in
``online_store_codes``. The code is a SYNTHETIC placeholder until a real Stores file is checked.
"""

from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.adapters.base import register


@register
class HaziHinamAdapter(RegulationAdapter):
    chain_id = "7290700100008"
    display_name = "חצי חינם"
    slug = "hazihinam"
    portal = "web"
    upstream_parsers = ("HAZI_HINAM",)
    upstream_scraper = "HAZI_HINAM"
    online_name_markers = ("אתר",)
    online_store_codes = frozenset({"299"})  # SYNTHETIC placeholder, confirm from a real file
    has_online_record = True
