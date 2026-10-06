"""Rami Levy (רמי לוי שיווק השקמה): Cerberus portal (url.retail.publishedprices.co.il, user RamiLevi).

Files: ``PriceFull7290058140886-039-202610060300.gz``, ``PromoFull...gz`` and a plain
``Stores7290058140886-202610060100.xml`` (no store segment). Regulation layout with
``SubChains`` > ``SubChain`` > ``Stores`` > ``Store`` nesting.

Online record: ``StoreType`` 2 (declared), a store name containing ``אינטרנט``, or a code in
``online_store_codes``. The code below is a SYNTHETIC placeholder; replace it with the real
code once a real Stores file is fetched.
"""

from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.adapters.base import register


@register
class RamiLevyAdapter(RegulationAdapter):
    chain_id = "7290058140886"
    display_name = "רמי לוי"
    slug = "ramilevy"
    portal = "cerberus"
    upstream_parsers = ("RAMI_LEVY",)
    upstream_scraper = "RAMI_LEVY"
    online_name_markers = ("אינטרנט",)
    online_store_codes = frozenset({"331"})  # SYNTHETIC placeholder, confirm from a real file
    has_online_record = True
