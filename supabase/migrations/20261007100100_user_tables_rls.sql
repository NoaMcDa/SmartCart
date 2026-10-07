-- Phase 1 user tables under row-level security (issue #64, #30).
--
-- On Supabase, auth.users and auth.uid() exist. Locally and in a plain Postgres they do not, so a
-- minimal stand-in is created only when absent (never replaced), which keeps one schema everywhere
-- and lets RLS tests run anywhere by setting request.jwt.claim.sub.

CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (
  id          uuid PRIMARY KEY,
  email       text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'auth' AND p.proname = 'uid'
  ) THEN
    CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $f$
      SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
    $f$;
  END IF;
END $$;

CREATE TABLE profiles (
  user_id           uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  home_store_id     bigint REFERENCES stores (id),
  radius_m          integer NOT NULL DEFAULT 5000 CHECK (radius_m BETWEEN 500 AND 15000),
  neighborhood_lat  numeric(6, 3),       -- rounded to 3 decimals (about 100 m) by trigger
  neighborhood_lon  numeric(6, 3),
  travel_mode       text NOT NULL DEFAULT 'car' CHECK (travel_mode IN ('car', 'walk_transit', 'delivery')),
  cost_per_km       numeric NOT NULL DEFAULT 1.2,
  extra_stop_value  numeric NOT NULL DEFAULT 25 CHECK (extra_stop_value BETWEEN 0 AND 50),
  max_stores        smallint NOT NULL DEFAULT 2 CHECK (max_stores BETWEEN 1 AND 3),
  clubs             text[] NOT NULL DEFAULT '{}',
  diet_flags        text[] NOT NULL DEFAULT '{}',
  kosher_level      text,
  flex_defaults     jsonb NOT NULL DEFAULT '{}'::jsonb,   -- {taxonomy_id: flex_level}
  theme             text NOT NULL DEFAULT 'system' CHECK (theme IN ('system', 'light', 'dark')),
  consent_location  boolean NOT NULL DEFAULT false,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION round_profile_location() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.neighborhood_lat := round(NEW.neighborhood_lat::numeric, 3);
  NEW.neighborhood_lon := round(NEW.neighborhood_lon::numeric, 3);
  RETURN NEW;
END $$;
CREATE TRIGGER profiles_round_location BEFORE INSERT OR UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION round_profile_location();
CREATE TRIGGER profiles_set_updated_at BEFORE UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE lists (
  id            bigserial PRIMARY KEY,
  user_id       uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  name          text NOT NULL,
  is_recurring  boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX lists_user_idx ON lists (user_id);
CREATE TRIGGER lists_set_updated_at BEFORE UPDATE ON lists
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE list_items (
  id            bigserial PRIMARY KEY,
  list_id       bigint NOT NULL REFERENCES lists (id) ON DELETE CASCADE,
  user_id       uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  canonical_id  bigint REFERENCES canonical_products (id),
  input_text    text,
  quantity      numeric NOT NULL DEFAULT 1 CHECK (quantity > 0),
  flex_level    text NOT NULL DEFAULT 'any_brand' CHECK (flex_level IN ('exact', 'any_brand', 'close')),
  confirmed     boolean NOT NULL DEFAULT true,
  sort          integer NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX list_items_list_idx ON list_items (list_id, sort);

CREATE TABLE preferences (
  user_id     uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  data        jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE profiles    ENABLE ROW LEVEL SECURITY;
ALTER TABLE lists       ENABLE ROW LEVEL SECURITY;
ALTER TABLE list_items  ENABLE ROW LEVEL SECURITY;
ALTER TABLE preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles    FORCE ROW LEVEL SECURITY;
ALTER TABLE lists       FORCE ROW LEVEL SECURITY;
ALTER TABLE list_items  FORCE ROW LEVEL SECURITY;
ALTER TABLE preferences FORCE ROW LEVEL SECURITY;

CREATE POLICY profiles_own    ON profiles    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY lists_own       ON lists       USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY list_items_own  ON list_items  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY preferences_own ON preferences USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
-- With no policy for anonymous callers (auth.uid() IS NULL) every row is denied.
