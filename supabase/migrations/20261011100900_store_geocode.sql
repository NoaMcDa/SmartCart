-- Store coordinates for transparency data that carries none (docs/geocoding.md, issues #1, #60).
-- requires: postgis
--
-- The seven real chains publish a CBS locality code and an address but no coordinates, so
-- stores.geog is filled by the ingest loader from (1) data/geo/store_geocodes.csv (address or
-- street precision), else (2) the centroid of the store's locality (data/geo/localities.csv),
-- else it stays NULL. These two columns say which of those a row came from, so a client can show a
-- locality-precision store as approximate and a later, better source can replace a worse one.

ALTER TABLE stores
  ADD COLUMN geo_precision text,
  ADD COLUMN geo_source    text;

ALTER TABLE stores
  ADD CONSTRAINT stores_geo_precision_ok
    CHECK (geo_precision IS NULL OR geo_precision IN ('address', 'street', 'locality')),
  -- a precision without a location (or the reverse) is a bug in whatever wrote it
  ADD CONSTRAINT stores_geo_precision_needs_geog
    CHECK ((geog IS NULL) = (geo_precision IS NULL));

COMMENT ON COLUMN stores.geo_precision IS
  'How exact stores.geog is: address (house), street, or locality (centroid of the CBS locality, approximate). NULL only while geog is NULL.';
COMMENT ON COLUMN stores.geo_source IS
  'Where stores.geog came from: chain (published in the Stores file), nominatim (OpenStreetMap, © OpenStreetMap contributors, ODbL), cbs-locality:<code>, cbs-name-match.';

-- Writers that predate these columns (a Stores file with lat/lon, test fixtures, manual fixes) set
-- geog alone. Such a point is taken as published by the chain; clearing geog clears the labels.
-- The ingest loader sets all three columns itself, so this only fills a gap.
CREATE FUNCTION stores_geo_labels() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  g jsonb := to_jsonb(NEW) -> 'geog';
BEGIN
  -- Read through jsonb so the function still works on a database where geog was dropped.
  IF g IS NULL THEN
    RETURN NEW;
  ELSIF g = 'null'::jsonb THEN
    NEW.geo_precision := NULL;
    NEW.geo_source := NULL;
  ELSIF NEW.geo_precision IS NULL THEN
    NEW.geo_precision := 'address';
    NEW.geo_source := coalesce(NEW.geo_source, 'chain');
  END IF;
  RETURN NEW;
END
$$;

CREATE TRIGGER stores_geo_labels BEFORE INSERT OR UPDATE ON stores
  FOR EACH ROW EXECUTE FUNCTION stores_geo_labels();

-- Coordinates that existed before this migration came from the chains' own Stores files.
UPDATE stores SET geo_precision = 'address', geo_source = 'chain' WHERE geog IS NOT NULL;

-- (geo_precision is NULL exactly when geog is, see the constraint; the view reads it so that it
-- does not stop a database from dropping geog.)
-- Physical stores the loader could not place: the phase 0 exit criterion "coordinates for every
-- store" is met when this view is empty or every row has a documented reason.
CREATE VIEW stores_missing_geo WITH (security_invoker = true) AS
SELECT s.id, s.chain_id, s.store_code, s.name, s.city, s.address,
       CASE
         WHEN s.city IS NULL OR s.city !~ '^0*[1-9][0-9]*$' THEN 'city code unknown (0 or missing)'
         ELSE 'city code not in the locality table'
       END AS reason
FROM stores AS s
WHERE s.channel = 'physical' AND s.geo_precision IS NULL
ORDER BY s.chain_id, s.store_code;

COMMENT ON VIEW stores_missing_geo IS
  'Physical stores with no location. The ingest loader fills stores.geog from data/geo; see docs/geocoding.md.';
