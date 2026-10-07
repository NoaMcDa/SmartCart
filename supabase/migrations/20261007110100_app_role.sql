-- The database role the API switches to for requests that touch user tables (issue #64).
--
-- The API connects with the service connection string (table owner on Supabase, superuser
-- locally); both bypass row-level security. For a signed-in request it runs, inside the request
-- transaction, SET LOCAL ROLE smartcart_app plus set_config('request.jwt.claim.sub', <user id>),
-- so the RLS policies on profiles, lists, list_items and preferences apply exactly as they do for
-- PostgREST. smartcart_app is NOLOGIN, not a superuser and has no BYPASSRLS. The RLS tests run
-- through the same role, so they never skip for a superuser connection.
--
-- On Supabase the role also inherits `authenticated` (when the migrating role may grant it),
-- which carries USAGE on the auth schema that auth.uid() lives in.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartcart_app') THEN
    CREATE ROLE smartcart_app NOLOGIN;
  END IF;
  -- The connecting role must be allowed to SET ROLE to it. On Postgres 16+ a CREATEROLE
  -- creator gets ADMIN on the new role but not SET, so grant SET explicitly.
  IF current_setting('server_version_num')::int >= 160000 THEN
    EXECUTE format('GRANT smartcart_app TO %I WITH INHERIT FALSE, SET TRUE', current_user);
  ELSE
    EXECUTE format('GRANT smartcart_app TO %I', current_user);
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO smartcart_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON profiles, lists, list_items, preferences TO smartcart_app;
GRANT USAGE, SELECT ON SEQUENCE lists_id_seq, list_items_id_seq TO smartcart_app;
-- Read access to what the /me routes join against.
GRANT SELECT ON canonical_products, taxonomy, stores, chains TO smartcart_app;

DO $$
BEGIN
  BEGIN
    GRANT USAGE ON SCHEMA auth TO smartcart_app;
    GRANT EXECUTE ON FUNCTION auth.uid() TO smartcart_app;
  EXCEPTION WHEN insufficient_privilege THEN
    RAISE NOTICE 'auth schema grants left to the authenticated role';
  END;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    BEGIN
      GRANT authenticated TO smartcart_app;
    EXCEPTION WHEN insufficient_privilege OR invalid_grant_operation THEN
      RAISE NOTICE 'could not grant authenticated to smartcart_app';
    END;
    -- PostgREST serves the same tables as `authenticated`; RLS still decides the rows.
    GRANT SELECT, INSERT, UPDATE, DELETE ON profiles, lists, list_items, preferences TO authenticated;
    GRANT USAGE, SELECT ON SEQUENCE lists_id_seq, list_items_id_seq TO authenticated;
  END IF;
END $$;
