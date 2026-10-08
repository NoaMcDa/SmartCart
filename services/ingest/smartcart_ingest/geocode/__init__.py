"""Store coordinates for transparency data that carries none (docs/geocoding.md).

* ``itm``: ITM (EPSG:2039) to WGS 84 conversion, standard library only.
* ``localities``: the CBS locality table (code to centroid) and its parsing from data.gov.il.
* ``nominatim``: a rate-limited, caching OpenStreetMap Nominatim client.
* ``stores``: address geocoding that keeps a result only when it is in the store's own city.
* ``resolve``: the order the loader uses (geocode row, locality centroid, nothing).
* ``sources``: the stores to work on (real Stores fixtures or a database) and coverage counts.
"""

from smartcart_ingest.geocode.resolve import GeoIndex, GeoPoint, StoreGeocode, load_index

__all__ = ["GeoIndex", "GeoPoint", "StoreGeocode", "load_index"]
