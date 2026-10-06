"""Victory (ויקטורי): Matrix / laibcatalog portal, two chain ids.

Two layouts coexist upstream and both are accepted:

* legacy Matrix (BigID) layout: ``ChainID``/``StoreID`` casing, ``<Products>`` > ``<Product>``
  price rows, flat per-item ``<Sales>`` > ``<Sale>`` promo rows (grouped by PromotionID here),
  ``<Branches>`` > ``<Branch>`` stores, windows-1255 encoding;
* laibcatalog new source: regulation ``Items``/``Promotions``/``SubChains`` layout.

Files: ``PriceFull7290696200003-001-202610060300.xml.gz`` and friends.

Online record: a store name containing אונליין / משלוחים. Provisional.
"""

from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.adapters.base import register


@register
class VictoryAdapter(RegulationAdapter):
    chain_id = "7290696200003"
    chain_ids = ("7290058103393",)
    display_name = "ויקטורי"
    slug = "victory"
    portal = "matrix"
    containers = frozenset(
        {"Products", "Sales", "Branches", "Items", "Promotions", "SubChains", "Stores"}
    )
    upstream_parsers = ("VICTORY_NEW_SOURCE", "VICTORY")
    upstream_scraper = "VICTORY_NEW_SOURCE"
    online_name_markers = ("אונליין", "משלוחים")
    has_online_record = True
