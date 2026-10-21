-- Security review: what the Supabase data API (PostgREST) may touch (docs/security-review.md, finding S2).
--
-- On Supabase the roles PostgREST serves requests as are `anon` (anyone holding the project's public
-- anon key, which ships in the web bundle) and `authenticated` (a signed-in user). Supabase's default
-- privileges give both of them ALL on every table, view and sequence created in `public`. Row-level
-- security is what protects a table from them, and these tables have none, because only the API (a
-- different role) was ever meant to read or write them:
--
--   prices, promos, promo_items, items, item_canonical, effective_prices, canonical_products, chains,
--   stores, taxonomy, gap_reports, alert_deliveries, file_tracking, quarantine_events, gold_pairs,
--   match_runs, schema_migrations, ... and the views created before their own REVOKEs.
--
-- So with the anon key anyone could have changed a price, repointed an item to another canonical
-- product, deleted the catalog or read every gap report's free-text note and user id, with a plain
-- HTTPS request to /rest/v1/<table>. The earlier migrations revoked the grants table by table for
-- events, ocr_usage and the beta tables only.
--
-- This migration closes it for every table at once, and for the ones created later:
--   1. revoke everything on every table and sequence of `public` from anon and authenticated;
--   2. give `authenticated` back exactly what the web app uses through PostgREST. That is one
--      table: list_items, which members of a shared list read, edit and follow in Realtime
--      (apps/web/src/features/share/useSharedList.ts; row-level security decides the rows, the
--      policies call the SECURITY DEFINER helpers owns_list / is_list_member). Everything else the
--      app does goes through the API, which has its own checks (consent for a location, limits,
--      ranges); the docs listed PostgREST for profiles, lists, preferences and more, but the code
--      never used it, so those grants are not given back. A later feature that needs one adds one
--      GRANT in its own migration;
--   3. stop the default privileges from granting new tables to those roles again.
-- `anon` gets nothing. The API's own roles (smartcart_api, smartcart_app) and service_role are not
-- touched. test_api_security_data_api.py asserts the resulting privilege matrix.

DO $$
DECLARE
  r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      CONTINUE;  -- a plain Postgres (a laptop): no data API roles, nothing to do
    END IF;
    EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', r);
    EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', r);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', r);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', r);
    -- Supabase's own default privileges are declared for supabase_admin as well; the migrating role
    -- may not be allowed to change those.
    BEGIN
      EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public REVOKE ALL ON TABLES FROM %I', r);
      EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', r);
    EXCEPTION WHEN insufficient_privilege OR undefined_object THEN
      RAISE NOTICE 'default privileges of supabase_admin left as they are (run as supabase_admin to change them)';
    END;
  END LOOP;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    -- Row-level security is on, and FORCEd; list_items_read / _insert / _update / _delete decide
    -- the rows (the owner and the accepted members of the list, by role).
    GRANT SELECT, INSERT, UPDATE, DELETE ON list_items TO authenticated;
    GRANT USAGE, SELECT ON SEQUENCE list_items_id_seq TO authenticated;
  END IF;
END $$;
