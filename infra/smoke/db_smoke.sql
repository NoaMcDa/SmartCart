-- Database smoke test for the SmartCart Supabase project (issue #14).
--
-- Run:   psql "$DATABASE_URL_DIRECT" -f infra/smoke/db_smoke.sql
-- Needs: the postgis and vector extensions enabled (see docs/infra-provisioning.md).
-- Safe:  read-only, creates nothing, changes nothing.
--
-- Expected output, in order:
--   1. a list of extensions that includes postgis and vector;
--   2. a distance of about 54,000 metres (Tel Aviv to Jerusalem, geodesic on WGS84);
--   3. a cosine distance of about 0.0085 between the vectors [1,2,3] and [1,2,4];
--   4. the final row "smoke ok".
-- Any failed assertion stops the script with an error (ON_ERROR_STOP).

\set ON_ERROR_STOP on
set search_path = public, extensions;

-- 1. Which extensions are installed. The acceptance check for the issue.
select extname, extversion
from pg_extension
order by extname;

-- 2. PostGIS: distance in metres between two points. geography(Point, 4326) takes lon, lat.
select round(
  st_distance(
    st_setsrid(st_makepoint(34.7818, 32.0853), 4326)::geography,   -- Tel Aviv
    st_setsrid(st_makepoint(35.2137, 31.7683), 4326)::geography    -- Jerusalem
  )::numeric
) as distance_m;

-- 3. pgvector: cosine distance (operator <=>) between two 3-dimensional vectors.
select '[1,2,3]'::vector(3) <=> '[1,2,4]'::vector(3) as cosine_distance;

-- 4. Assertions, so a wrong result fails loudly instead of passing by eye.
do $$
declare
  d numeric;
  c double precision;
begin
  if not exists (select 1 from pg_extension where extname = 'postgis') then
    raise exception 'postgis is not enabled';
  end if;
  if not exists (select 1 from pg_extension where extname = 'vector') then
    raise exception 'vector (pgvector) is not enabled';
  end if;

  d := st_distance(
    st_setsrid(st_makepoint(34.7818, 32.0853), 4326)::geography,
    st_setsrid(st_makepoint(35.2137, 31.7683), 4326)::geography
  );
  if d not between 50000 and 58000 then
    raise exception 'unexpected Tel Aviv to Jerusalem distance: % m', d;
  end if;

  c := '[1,2,3]'::vector(3) <=> '[1,2,4]'::vector(3);
  if c not between 0.0080 and 0.0090 then
    raise exception 'unexpected cosine distance: %', c;
  end if;
end
$$;

select 'smoke ok' as result;
