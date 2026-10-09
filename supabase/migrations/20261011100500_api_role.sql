-- The API's own database role (docs/deploy.md "Which role", docs/infra-provisioning.md section 3.1).
--
-- Until now the API connected as `postgres` (owner, bypasses row-level security). This migration adds
-- a LOGIN role, smartcart_api, that can do what the API does and nothing else:
--
--   * read the catalog and price tables;
--   * write events, search_misses, gap_reports, substitution_feedback (the anonymous-capable
--     routes) and flag a mapping for review (item_canonical.needs_review, nothing else);
--   * reach the user tables only by switching to smartcart_app (SET LOCAL ROLE, which every /me
--     route already does) so that the row-level security policies decide the rows. The role is
--     NOINHERIT, so smartcart_app's rights are not usable without that switch;
--   * no DDL, no write to chains, stores, items, prices, promos, canonical_products, taxonomy,
--     item_attributes, item_embeddings, file_tracking. The nightly precompute and the alerts job
--     write effective_prices and read every user's alerts: they keep running as the owner
--     (jobs.env), not as this role.
--
-- The role is created only when a password is provided, so a database that never serves the API
-- (a laptop, CI) does not get a login role with a known password. Provide it for the migrating
-- session with the libpq options variable, so that it never lands in a file or in the repo:
--
--   PGOPTIONS="-c smartcart.api_password=$SMARTCART_API_PASSWORD" smartcart-ingest migrate
--
-- Without it the migration only prints a NOTICE and creates the grants function below. If a role
-- named smartcart_api already exists (created by hand with \password), the migration grants it
-- what it needs and leaves its password alone. To grant later, or after new tables, as the owner:
--
--   SELECT smartcart_grant_api_role('smartcart_api');   -- idempotent
--
-- smartcart_grant_api_role(role) is also what the tests call on a throwaway role, so the grants
-- are tested with the statements production runs.

CREATE OR REPLACE FUNCTION smartcart_grant_api_role(p_role name)
RETURNS void
LANGUAGE plpgsql AS $fn$
DECLARE
  t text;
  r record;
  pname text;
  app_role text := 'smartcart_app';
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = p_role) THEN
    RAISE EXCEPTION 'role % does not exist', p_role;
  END IF;

  EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', p_role);

  -- Read: catalog, prices, matching.
  FOREACH t IN ARRAY ARRAY[
    'chains', 'stores', 'items', 'prices', 'promos', 'promo_items', 'effective_prices',
    'canonical_products', 'taxonomy', 'product_type_rules', 'item_canonical', 'item_attributes',
    'item_embeddings', 'file_tracking'
  ] LOOP
    IF to_regclass(t) IS NOT NULL THEN
      EXECUTE format('GRANT SELECT ON %I TO %I', t, p_role);
    END IF;
  END LOOP;

  -- A "not a good substitute" report flags the mapping for review, and only that column.
  EXECUTE format('GRANT UPDATE (needs_review) ON item_canonical TO %I', p_role);

  -- Write, outside the user tables.
  EXECUTE format('GRANT SELECT, INSERT ON events TO %I', p_role);
  EXECUTE format('GRANT UPDATE (user_id) ON events TO %I', p_role);            -- DELETE /me
  EXECUTE format('GRANT USAGE ON SEQUENCE events_id_seq TO %I', p_role);
  EXECUTE format('GRANT SELECT, INSERT, DELETE ON search_misses TO %I', p_role);
  EXECUTE format('GRANT USAGE ON SEQUENCE search_misses_id_seq TO %I', p_role);
  EXECUTE format('GRANT SELECT, INSERT ON gap_reports TO %I', p_role);
  EXECUTE format('GRANT UPDATE (user_id) ON gap_reports TO %I', p_role);        -- DELETE /me
  EXECUTE format('GRANT USAGE ON SEQUENCE gap_reports_id_seq TO %I', p_role);
  EXECUTE format('GRANT INSERT ON substitution_feedback TO %I', p_role);
  EXECUTE format('GRANT SELECT (id) ON substitution_feedback TO %I', p_role);   -- RETURNING id
  EXECUTE format('GRANT USAGE ON SEQUENCE substitution_feedback_id_seq TO %I', p_role);

  -- The few statements the API runs on the service connection, outside any user's RLS, on user
  -- tables, each limited to the columns it needs:
  --   POST /me/push-subscriptions   take over a push endpoint registered to another account;
  --   POST /me/lists/accept/{token} read a pending invite by the hash of its token, then set its
  --                                 member_id and accepted_at (the invitee cannot see it yet);
  --   DELETE /me                    remove a member's shares and items others added.
  EXECUTE format('GRANT SELECT (endpoint, user_id), DELETE ON push_subscriptions TO %I', p_role);
  EXECUTE format('GRANT SELECT (list_id, owner_id, member_id, expires_at, invite_token),'
                 ' UPDATE (member_id, accepted_at), DELETE ON list_shares TO %I', p_role);
  EXECUTE format('GRANT SELECT (user_id), DELETE ON list_items TO %I', p_role);

  -- Row-level security applies to this role too (it has no BYPASSRLS, and the user tables are
  -- FORCEd), so every table it touches as itself, not as a user, needs a policy that names it.
  -- Dropped and recreated so the function can run again. The column grants above are what limit
  -- these policies.
  FOR r IN SELECT * FROM (VALUES
      ('events', 'ALL'), ('search_misses', 'ALL'),
      ('substitution_feedback', 'INSERT'), ('substitution_feedback', 'SELECT'),
      ('push_subscriptions', 'SELECT'), ('push_subscriptions', 'DELETE'),
      ('list_shares', 'SELECT'), ('list_shares', 'UPDATE'), ('list_shares', 'DELETE'),
      ('list_items', 'SELECT'), ('list_items', 'DELETE')
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

  -- Supabase Auth: events and feedback store a user id only if the account exists, which is a
  -- read of auth.users (id), and the user tables' policies call auth.uid(). The auth schema is
  -- owned by Supabase, so a migrating role that may not grant on it only gets a notice.
  BEGIN
    EXECUTE format('GRANT USAGE ON SCHEMA auth TO %I', p_role);
    EXECUTE format('GRANT SELECT (id) ON auth.users TO %I', p_role);
    EXECUTE format('GRANT EXECUTE ON FUNCTION auth.uid() TO %I', p_role);
  EXCEPTION WHEN insufficient_privilege THEN
    RAISE NOTICE 'auth schema grants for % left to a role that may grant on it (see docs/deploy.md)', p_role;
  END;

  -- The user tables: only through smartcart_app. With INHERIT FALSE the membership gives SET ROLE
  -- and nothing else (Postgres 16 and later; the role is also created NOINHERIT for 15).
  IF current_setting('server_version_num')::int >= 160000 THEN
    EXECUTE format('GRANT %I TO %I WITH INHERIT FALSE, SET TRUE', app_role, p_role);
  ELSE
    EXECUTE format('GRANT %I TO %I', app_role, p_role);
  END IF;
END
$fn$;

REVOKE ALL ON FUNCTION smartcart_grant_api_role(name) FROM PUBLIC;
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON FUNCTION smartcart_grant_api_role(name) FROM %I', r);
    END IF;
  END LOOP;
END $$;

DO $$
DECLARE
  pw text := nullif(current_setting('smartcart.api_password', true), '');
BEGIN
  IF pw IS NOT NULL THEN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartcart_api') THEN
      EXECUTE format('ALTER ROLE smartcart_api LOGIN NOINHERIT PASSWORD %L', pw);
    ELSE
      EXECUTE format('CREATE ROLE smartcart_api LOGIN NOINHERIT PASSWORD %L', pw);
    END IF;
  ELSIF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartcart_api') THEN
    RAISE NOTICE 'smartcart_api not created: smartcart.api_password is not set. Run the migration '
                 'with PGOPTIONS="-c smartcart.api_password=..." or create the role and call '
                 'smartcart_grant_api_role(''smartcart_api'') (docs/deploy.md).';
    RETURN;
  END IF;
  PERFORM smartcart_grant_api_role('smartcart_api');
END $$;
