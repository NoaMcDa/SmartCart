-- Phase 3 (issue #70): monthly grocery budget and spend tracking, per user, under row-level
-- security. Spend is the user's own record of a shopping trip (a list marked as purchased, or a
-- total they typed); it is never sold, shared or sent to analytics (D10, D11). DELETE /me
-- removes every row (services/api/smartcart_api/routes/me_delete.py), and the auth.users
-- cascade removes them on Supabase too.

ALTER TABLE profiles
  ADD COLUMN monthly_budget numeric(10, 2) CHECK (monthly_budget IS NULL OR monthly_budget >= 0);

CREATE TABLE spend_entries (
  id          bigserial PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  date        date NOT NULL,
  store_id    bigint NOT NULL REFERENCES stores (id),
  store_name  text NOT NULL CHECK (char_length(store_name) BETWEEN 1 AND 200),
  total       numeric(10, 2) NOT NULL CHECK (total >= 0),
  item_count  integer NOT NULL CHECK (item_count BETWEEN 0 AND 1000),
  plan        text NOT NULL CHECK (plan IN ('single', 'split')),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX spend_entries_user_date_idx ON spend_entries (user_id, date);

ALTER TABLE spend_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE spend_entries FORCE ROW LEVEL SECURITY;
CREATE POLICY spend_entries_own ON spend_entries
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
-- With no policy for anonymous callers (auth.uid() IS NULL) every row is denied.

GRANT SELECT, INSERT, UPDATE, DELETE ON spend_entries TO smartcart_app;
GRANT USAGE, SELECT ON SEQUENCE spend_entries_id_seq TO smartcart_app;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON spend_entries TO authenticated;
    GRANT USAGE, SELECT ON SEQUENCE spend_entries_id_seq TO authenticated;
  END IF;
END $$;
