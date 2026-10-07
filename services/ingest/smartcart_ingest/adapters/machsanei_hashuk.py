"""Machsanei Hashuk (מחסני השוק): laibcatalog JSON API, two chain ids (issue #81).

Upstream (il_supermarket_scarper 1.0.15, ``scrappers/machsani_ashuk.py``): the active scraper is
``MahsaniAShukNewSource``, a ``_LaibcatalogApiScraper`` (``ApiWebEngine``) on
``https://laibcatalog.co.il`` (``/webapi/api/getfiles?edi=<chain id>``), chain ids
7290661400001 and 7290633800006. The older Matrix ASPX scraper (``MahsaniAShuk``) is deprecated
upstream. laibcatalog blocks cloud IP ranges, so fetching needs the Israeli-IP VPS, and its
listing is empty overnight until the morning republish (about 08:00) and on Saturdays
(``scraper_stability.MahsaniAshukNewSource``).

Portal: ``matrix``, the same value as Victory, which publishes through the same laibcatalog host
and engine. The upstream engine class is ``ApiWebEngine``; if the ``portal`` column ever needs
to tell the laibcatalog API from the legacy Matrix site, both chains move together.

Layout (il_supermarket_parsers 1.0.12, ``parsers/mahsani_a_shuk.py``): the new source uses the
regulation ``Items`` / ``Promotions`` / ``SubChains`` containers with BigID casing (``ChainID``,
``StoreID``, ``PromotionID``); its promo converter falls back to the flat ``<Sales>`` rows of the
legacy BigID layout, and the deprecated converter reads ``Products`` / ``Sales`` / ``Branches``.
All of these are accepted. Files: ``PriceFull7290661400001-003-202610060810.xml.gz``.

Online record: a store name containing אונליין / משלוחים, or a code in ``online_store_codes``.
PROVISIONAL: the code is a synthetic placeholder until a real Stores file is checked.
"""

from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.adapters.base import register


@register
class MachsaneiHashukAdapter(RegulationAdapter):
    chain_id = "7290661400001"
    chain_ids = ("7290633800006",)
    aliases = ("7290633800006",)
    display_name = "מחסני השוק"
    slug = "machsanei_hashuk"
    portal = "matrix"
    containers = frozenset(
        {"Items", "Promotions", "SubChains", "Stores", "Products", "Sales", "Branches"}
    )
    upstream_parsers = ("MAHSANI_ASHUK_NEW_SOURCE", "MAHSANI_ASHUK")
    upstream_scraper = "MAHSANI_ASHUK_NEW_SOURCE"
    online_name_markers = ("אונליין", "משלוחים")
    online_store_codes = frozenset({"90"})  # SYNTHETIC placeholder, confirm from a real file
    has_online_record = True
