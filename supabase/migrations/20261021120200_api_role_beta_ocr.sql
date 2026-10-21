-- Security review: the API role could not do what the closed-beta and photo routes do (finding S9).
--
-- docs/deploy.md has the API connect as `smartcart_api` (20261011100500_api_role.sql), a login role
-- that is deliberately not the table owner. That migration predates the beta (20261011100700) and
-- ocr_usage (20261011100000, but missing from its grant list) tables, and these are row-level-secured
-- with no policy for anyone, relying on "the service connection is the table owner and bypasses RLS".
-- As smartcart_api none of them is reachable: POST /beta/join, POST /beta/feedback and the OCR cap
-- check of POST /parse-image would answer 500 in production while every test (superuser connection)
-- passes. It fails closed, but the beta cannot open like that.
--
-- smartcart_grant_api_role(role) is wrapped, not rewritten: the first version keeps its name with a
-- _v1 suffix and still does everything it did, then this one adds the private tables, each limited
-- to the columns and the commands the routes use:
--   beta_invites   SELECT, and UPDATE of `uses`      POST /beta/join (lookup FOR UPDATE, count a use)
--   beta_members   SELECT (user_id, segment), INSERT POST /beta/join, POST /beta/feedback
--   beta_feedback  INSERT                            POST /beta/feedback (no user id is stored)
--   ocr_usage      SELECT, INSERT, UPDATE            POST /parse-image (the monthly cap counters)
-- and the policies that name the role (the tables have row-level security on and no policy, so a
-- grant alone shows nothing). Nothing is granted to anon, authenticated or smartcart_app here.

ALTER FUNCTION smartcart_grant_api_role(name) RENAME TO smartcart_grant_api_role_v1;

CREATE OR REPLACE FUNCTION smartcart_grant_api_role(p_role name)
RETURNS void
LANGUAGE plpgsql AS $fn$
DECLARE
  r record;
  pname text;
BEGIN
  PERFORM smartcart_grant_api_role_v1(p_role);

  EXECUTE format('GRANT SELECT (code, segment, max_uses, uses, expires_at), UPDATE (uses)'
                 ' ON beta_invites TO %I', p_role);
  EXECUTE format('GRANT SELECT (user_id, segment), INSERT (user_id, code, segment)'
                 ' ON beta_members TO %I', p_role);
  EXECUTE format('GRANT INSERT (segment, rating, body) ON beta_feedback TO %I', p_role);
  EXECUTE format('GRANT USAGE ON SEQUENCE beta_feedback_id_seq TO %I', p_role);
  EXECUTE format('GRANT SELECT, INSERT, UPDATE ON ocr_usage TO %I', p_role);

  FOR r IN SELECT * FROM (VALUES
      ('beta_invites', 'SELECT'), ('beta_invites', 'UPDATE'),
      ('beta_members', 'SELECT'), ('beta_members', 'INSERT'),
      ('beta_feedback', 'INSERT'),
      ('ocr_usage', 'ALL')
    ) AS v (tbl, cmd)
  LOOP
    pname := left(r.tbl || '_api_' || lower(r.cmd) || '_' || p_role, 63);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', pname, r.tbl);
    EXECUTE format('CREATE POLICY %I ON %I FOR %s TO %I %s', pname, r.tbl, r.cmd, p_role,
      CASE r.cmd WHEN 'INSERT' THEN 'WITH CHECK (true)'
                 WHEN 'UPDATE' THEN 'USING (true) WITH CHECK (true)'
                 WHEN 'ALL'    THEN 'USING (true) WITH CHECK (true)'
                 ELSE 'USING (true)' END);
  END LOOP;
END
$fn$;

REVOKE ALL ON FUNCTION smartcart_grant_api_role(name) FROM PUBLIC;
REVOKE ALL ON FUNCTION smartcart_grant_api_role_v1(name) FROM PUBLIC;
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON FUNCTION smartcart_grant_api_role(name) FROM %I', r);
      EXECUTE format('REVOKE ALL ON FUNCTION smartcart_grant_api_role_v1(name) FROM %I', r);
    END IF;
  END LOOP;
END $$;

-- Apply it to the real role when it exists (the first migration only created it when a password
-- was given); a database without it is left alone.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartcart_api') THEN
    PERFORM smartcart_grant_api_role('smartcart_api');
  END IF;
END $$;
