"""Yochananof (מ. יוחננוף ובניו): Cerberus portal (user yohananof).

Files: ``PriceFull7290803800003-005-202610060300.gz`` and friends. Some Cerberus downloads
keep the ``.gz`` name but are zip archives; ``xmlutil.unwrap`` detects the container by magic
bytes, never by extension. Regulation layout, ``SubChains`` nesting.

Online record: ``StoreType`` 2 (declared by the source) or a name with משלוחים / אונליין.
Provisional.
"""

from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.adapters.base import register


@register
class YohananofAdapter(RegulationAdapter):
    chain_id = "7290803800003"
    display_name = "יוחננוף"
    slug = "yohananof"
    portal = "cerberus"
    upstream_parsers = ("YOHANANOF",)
    upstream_scraper = "YOHANANOF"
    online_name_markers = ("משלוחים", "אונליין")
    has_online_record = True
