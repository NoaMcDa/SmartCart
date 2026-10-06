"""Tiv Taam (טיב טעם): Cerberus portal (user TivTaam).

Price files come in two layouts (upstream picks by the presence of ``<Items>``): the
regulation ``<Items>`` > ``<Item>`` layout, and a .NET DataSet export ``<NewDataSet>`` with
lower-case ``<item>`` rows and an inline ``xs:schema``. Both are accepted. Stores use
``SubChains`` nesting.

Online record: a distribution-centre address (``מרכז הפצה``) or a name with משלוחים.
Provisional.
"""

from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.adapters.base import register


@register
class TivTaamAdapter(RegulationAdapter):
    chain_id = "7290873255550"
    display_name = "טיב טעם"
    slug = "tivtaam"
    portal = "cerberus"
    containers = frozenset({"Items", "NewDataSet", "Promotions", "SubChains", "Stores"})
    upstream_parsers = ("TIV_TAAM",)
    upstream_scraper = "TIV_TAAM"
    online_name_markers = ("משלוחים",)
    online_address_markers = ("מרכז הפצה",)
    has_online_record = True
