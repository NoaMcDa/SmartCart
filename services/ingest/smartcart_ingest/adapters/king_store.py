"""King Store (קינג סטור): Bina portal (issue #81).

Upstream (il_supermarket_scarper 1.0.15, ``scrappers/king_store.py``, ``engines/bina.py``):
``KingStore(Bina)`` with ``url_perfix="kingstore"``, so the listing is
``http://kingstore.binaprojects.com/MainIO_Hok.aspx`` (plain HTTP, ASPX returning JSON) and a
file is resolved through ``Download.aspx?FileNm=<name>`` to its ``SPath``. Chain id
7290058108879. Upstream notes (``utils/files/gzip_utils.py``) that King Store returns
gzip-compressed content under names that do not end in ``.gz``; ``xmlutil.unwrap`` detects
gzip and zip by magic bytes, never by extension, so this needs no special case.

Layout (il_supermarket_parsers 1.0.12, ``KingStoreFileConverter`` in ``parsers/other.py``): the
plain ``BaseFileConverter``, i.e. the regulation ``Items`` / ``Promotions`` /
``SubChains`` > ``Stores`` containers with ``Id`` casing (``ChainId``, ``StoreId``,
``PromotionId``). Files: ``PriceFull7290058108879-001-202610060510.xml``.

Online record: none known; King Store is not known to run an online shop, so only the shared
heuristic runs. PROVISIONAL until a real Stores file is checked.
"""

from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.adapters.base import register


@register
class KingStoreAdapter(RegulationAdapter):
    chain_id = "7290058108879"
    display_name = "קינג סטור"
    slug = "king_store"
    portal = "bina"
    upstream_parsers = ("KING_STORE",)
    upstream_scraper = "KING_STORE"
    has_online_record = False
