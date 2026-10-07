"""Mega / Carrefour (קרפור, formerly מגה; chain id 7290055700007).

Mega's own portal (PublishPrice engine, ``prices.mega.co.il``) was removed upstream on
2025-07-01 after the merger; the same chain id now publishes through the Yayno Bitan and
Carrefour PublishPrice web portal (``prices.carrefour.co.il``). It is not a Bina portal.
Regulation layout, four-digit store codes: ``PriceFull7290055700007-2960-202610060300.gz``.

Online record: a code in ``online_store_codes`` (a picking centre whose name carries no
keyword). The code is a SYNTHETIC placeholder until a real Stores file is checked.
"""

from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.adapters.base import register


@register
class MegaCarrefourAdapter(RegulationAdapter):
    chain_id = "7290055700007"
    display_name = "קרפור (מגה)"
    slug = "mega"
    portal = "web"
    upstream_parsers = ("YAYNO_BITAN_AND_CARREFOUR", "MEGA")
    upstream_scraper = "YAYNO_BITAN_AND_CARREFOUR"
    online_store_codes = frozenset({"5000"})  # SYNTHETIC placeholder, confirm from a real file
    has_online_record = True
