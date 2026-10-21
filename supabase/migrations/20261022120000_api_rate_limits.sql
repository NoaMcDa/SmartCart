-- Rate limits shared by every API process (docs/security-review.md R3).
--
-- smartcart_api/ratelimit.py counted in the memory of each process, so N workers or replicas allowed
-- N times the limit. With API_RATE_LIMIT_BACKEND=postgres the counters live here: one row per
-- (route class, client, window length, window), a fixed window, incremented by one atomic
-- INSERT ... ON CONFLICT DO UPDATE ... RETURNING that the API runs once per request.
--
--   bucket          route class and how the client is keyed: 'search:principal', 'beta-join:ip'
--   client_key      'u:<user id>' or 'ip:<address>'
--   window_seconds  60 or 3600 (the windows of ratelimit.py)
--   window_start    start of the window, epoch seconds, a multiple of window_seconds
--   window_end      window_start + window_seconds: what the cleanup deletes by
--   hits            requests counted in that window (a refused request counts too)
--
-- Windows are cut from the database's clock, so replicas with drifting clocks still agree. Expired
-- rows are deleted by the API itself (a bounded DELETE, at most every few minutes per process,
-- under an advisory lock) and can be deleted by hand: DELETE FROM api_rate_limits WHERE window_end < extract(epoch FROM now());
--
-- The table holds client addresses (personal data) for at most an hour plus the cleanup interval.
-- Nothing in the data API reaches it: no grant to anon or authenticated, row-level security on, and
-- a policy only for the API role (smartcart_grant_api_role, below). The migration works in
-- current_schema(), like the others: every name is unqualified.
--
-- hits is not indexed and the primary key never changes, so the update is a HOT update; the
-- fillfactor leaves room on the page for it.

CREATE TABLE IF NOT EXISTS api_rate_limits (
  bucket         text   NOT NULL,
  client_key     text   NOT NULL,
  window_seconds integer NOT NULL CHECK (window_seconds > 0),
  window_start   bigint NOT NULL,
  window_end     bigint NOT NULL,
  hits           integer NOT NULL DEFAULT 1 CHECK (hits > 0),
  PRIMARY KEY (bucket, client_key, window_seconds, window_start)
) WITH (fillfactor = 70);

CREATE INDEX IF NOT EXISTS api_rate_limits_window_end_idx ON api_rate_limits (window_end);

ALTER TABLE api_rate_limits ENABLE ROW LEVEL SECURITY;

-- Nobody but the owner has anything on it unless granted below. (On Supabase the data API roles
-- also lose the default privileges, see 20261021120100_data_api_lockdown.sql; this is belt and braces.)
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON api_rate_limits FROM %I', r);
    END IF;
  END LOOP;
END $$;
REVOKE ALL ON api_rate_limits FROM PUBLIC;

-- The API role gets what the limiter runs and nothing else: the upsert (INSERT of a row, UPDATE of
-- hits, SELECT for the conflict check and RETURNING) and the cleanup DELETE. The grants function is
-- wrapped, not rewritten, as 20261021120200 did: the previous version is kept under another name.
ALTER FUNCTION smartcart_grant_api_role(name) RENAME TO smartcart_grant_api_role_pre_rate_limits;

CREATE OR REPLACE FUNCTION smartcart_grant_api_role(p_role name)
RETURNS void
LANGUAGE plpgsql AS $fn$
DECLARE
  pname text;
BEGIN
  PERFORM smartcart_grant_api_role_pre_rate_limits(p_role);

  EXECUTE format('GRANT SELECT, INSERT, UPDATE (hits), DELETE ON api_rate_limits TO %I', p_role);
  pname := left('api_rate_limits_api_all_' || p_role, 63);
  EXECUTE format('DROP POLICY IF EXISTS %I ON api_rate_limits', pname);
  EXECUTE format('CREATE POLICY %I ON api_rate_limits FOR ALL TO %I USING (true) WITH CHECK (true)',
                 pname, p_role);
END
$fn$;

REVOKE ALL ON FUNCTION smartcart_grant_api_role(name) FROM PUBLIC;
REVOKE ALL ON FUNCTION smartcart_grant_api_role_pre_rate_limits(name) FROM PUBLIC;
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON FUNCTION smartcart_grant_api_role(name) FROM %I', r);
      EXECUTE format('REVOKE ALL ON FUNCTION smartcart_grant_api_role_pre_rate_limits(name) FROM %I', r);
    END IF;
  END LOOP;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartcart_api') THEN
    PERFORM smartcart_grant_api_role('smartcart_api');
  END IF;
END $$;
