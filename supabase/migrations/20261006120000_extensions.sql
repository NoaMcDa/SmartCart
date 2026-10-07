-- Extensions for SmartCart (decision D3).
-- requires: postgis, vector
--
-- postgis: stores.geog and radius queries. vector (pgvector): semantic matching of canonical
-- products (phase 1). pg_trgm: fuzzy text search on item names (phase 1 search work).
--
-- No schema is named, so a fresh database gets them in the first schema on the search_path
-- (public). On hosted Supabase, an extension already enabled from the dashboard lives in the
-- `extensions` schema, which is on the default search_path, and IF NOT EXISTS leaves it there.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
