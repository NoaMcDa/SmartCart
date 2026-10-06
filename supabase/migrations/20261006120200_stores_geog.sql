-- Store location and radius search (issue #27).
-- requires: postgis
--
-- Kept apart from schema_v1 only so a developer without PostGIS can still run the plain-SQL
-- tests; CI, Supabase and docker compose apply it, so the schema is identical everywhere.

ALTER TABLE stores ADD COLUMN geog geography(Point, 4326);
CREATE INDEX stores_geog_gist ON stores USING gist (geog);

COMMENT ON COLUMN stores.geog IS 'Store location, WGS 84. NULL until geocoded.';

-- Stores within p_radius_m meters of (p_lon, p_lat), nearest first. Uses stores_geog_gist.
CREATE OR REPLACE FUNCTION stores_within(
  p_lon       double precision,
  p_lat       double precision,
  p_radius_m  double precision
) RETURNS TABLE (store_id bigint, chain_id text, channel text, distance_m double precision)
LANGUAGE sql STABLE AS $$
  SELECT s.id, s.chain_id, s.channel,
         ST_Distance(s.geog, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography)
  FROM stores AS s
  WHERE ST_DWithin(s.geog, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography, p_radius_m)
  ORDER BY 4
$$;
