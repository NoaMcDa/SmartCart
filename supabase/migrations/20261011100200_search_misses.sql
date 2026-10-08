-- Search misses: the demand signal for catalog expansion (issue #52, docs/catalog.md section 9).
--
-- One row each time a query found nothing the parser would accept: GET /search returned no hit
-- above the parser floor (0.35), or a parse-list / recipe row came back not_found or unresolved
-- (the photo route calls the same helper later). The catalog backlog
-- (supabase/queries/catalog_backlog.sql) ranks these by frequency to decide which canonical
-- products to add next.
--
-- Privacy by design (decision D11): there is no user id, no session id, no IP and no raw text. The
-- API stores only the normalized query (lower case, no punctuation, at most 120 characters) and
-- drops anything that looks like a phone number, an e-mail address, a link or a long run of digits
-- before it gets here (smartcart_api.misses). The time is rounded down to the hour, so a row cannot
-- be matched to a request log by the second. Rows older than 180 days are deleted by the insert
-- path itself and by purge_search_misses().
--
--   query_norm       the normalized query, 1 to 120 characters
--   source           where the miss came from
--   best_confidence  confidence of the best hit that was found but not accepted; NULL when the
--                    search found nothing at all
--   seen_at          hour of the miss

CREATE TABLE search_misses (
  id               bigserial PRIMARY KEY,
  query_norm       text NOT NULL CHECK (char_length(query_norm) BETWEEN 1 AND 120),
  source           text NOT NULL CHECK (source IN ('search', 'parse_list', 'parse_recipe', 'parse_image')),
  best_confidence  numeric CHECK (best_confidence BETWEEN 0 AND 1),
  seen_at          timestamptz NOT NULL DEFAULT date_trunc('hour', now())
);
CREATE INDEX search_misses_seen_idx ON search_misses (seen_at);
CREATE INDEX search_misses_query_idx ON search_misses (query_norm, seen_at);

-- Nothing here is for the browser: row-level security on with no policy for the data-API roles, no
-- grants. The service connection (table owner) writes and reads; the least-privilege API role
-- gets INSERT, SELECT and DELETE plus one policy (20261011100500).
ALTER TABLE search_misses ENABLE ROW LEVEL SECURITY;

-- Retention: delete rows older than p_days (default 180). Returns how many it deleted. The API
-- calls the same statement on every insert, batch by batch, so a database that is written to
-- never needs a scheduled job; call this from cron to purge a quiet one.
CREATE OR REPLACE FUNCTION purge_search_misses(p_days integer DEFAULT 180)
RETURNS bigint
LANGUAGE sql AS $$
  WITH gone AS (
    DELETE FROM search_misses
    WHERE seen_at < now() - make_interval(days => p_days)
    RETURNING 1
  )
  SELECT count(*) FROM gone
$$;

REVOKE ALL ON FUNCTION purge_search_misses(integer) FROM PUBLIC;

DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON search_misses FROM %I', r);
      EXECUTE format('REVOKE ALL ON SEQUENCE search_misses_id_seq FROM %I', r);
      EXECUTE format('REVOKE ALL ON FUNCTION purge_search_misses(integer) FROM %I', r);
    END IF;
  END LOOP;
END $$;
