-- Phase 2 and phase 1 follow-ups: price alerts, push subscriptions, shared lists, catalog contract
-- columns (issues #23, #34, #90, #92).

-- --- catalog contract gaps (#92) ---------------------------------------------------------------
ALTER TABLE item_canonical ADD COLUMN IF NOT EXISTS reason text;
ALTER TABLE item_canonical ADD COLUMN IF NOT EXISTS human_rejected boolean NOT NULL DEFAULT false;
ALTER TABLE canonical_products ADD COLUMN IF NOT EXISTS embedding_model text;
ALTER TABLE canonical_products ADD COLUMN IF NOT EXISTS reference_barcodes text[] NOT NULL DEFAULT '{}';
CREATE INDEX IF NOT EXISTS canonical_products_reference_barcodes_gin
  ON canonical_products USING gin (reference_barcodes);
ALTER TABLE substitution_feedback ADD COLUMN IF NOT EXISTS list_item_id bigint;
ALTER TABLE substitution_feedback ADD COLUMN IF NOT EXISTS flex_level text
  CHECK (flex_level IN ('exact', 'any_brand', 'close'));
ALTER TABLE substitution_feedback ADD COLUMN IF NOT EXISTS match_confidence numeric;
ALTER TABLE substitution_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE substitution_feedback FORCE ROW LEVEL SECURITY;
CREATE POLICY substitution_feedback_own ON substitution_feedback
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid() OR user_id IS NULL);

-- --- price alerts and web push (#23) -----------------------------------------------------------
CREATE TABLE price_alerts (
  id                    bigserial PRIMARY KEY,
  user_id               uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  canonical_id          bigint NOT NULL REFERENCES canonical_products (id) ON DELETE CASCADE,
  threshold_unit_price  numeric NOT NULL CHECK (threshold_unit_price > 0),
  flex_level            text NOT NULL DEFAULT 'any_brand' CHECK (flex_level IN ('exact', 'any_brand', 'close')),
  radius_m              integer NOT NULL DEFAULT 5000 CHECK (radius_m BETWEEN 500 AND 15000),
  neighborhood_lat      numeric(6, 3),
  neighborhood_lon      numeric(6, 3),
  active                boolean NOT NULL DEFAULT true,
  last_fired_at         timestamptz,
  created_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX price_alerts_active_idx ON price_alerts (canonical_id) WHERE active;
CREATE INDEX price_alerts_user_idx ON price_alerts (user_id);

CREATE TABLE push_subscriptions (
  id          bigserial PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  endpoint    text NOT NULL UNIQUE,
  p256dh      text NOT NULL,
  auth        text NOT NULL,
  user_agent  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX push_subscriptions_user_idx ON push_subscriptions (user_id);

CREATE TABLE alert_deliveries (
  id            bigserial PRIMARY KEY,
  alert_id      bigint NOT NULL REFERENCES price_alerts (id) ON DELETE CASCADE,
  store_id      bigint REFERENCES stores (id),
  item_id       bigint REFERENCES items (id),
  unit_price    numeric NOT NULL,
  channel       text NOT NULL DEFAULT 'push' CHECK (channel IN ('push', 'log')),
  delivered_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX alert_deliveries_alert_idx ON alert_deliveries (alert_id, delivered_at DESC);

ALTER TABLE price_alerts       ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_alerts       FORCE ROW LEVEL SECURITY;
ALTER TABLE push_subscriptions FORCE ROW LEVEL SECURITY;
CREATE POLICY price_alerts_own       ON price_alerts       USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY push_subscriptions_own ON push_subscriptions USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- --- shared lists (#34) ------------------------------------------------------------------------
CREATE TABLE list_shares (
  list_id       bigint NOT NULL REFERENCES lists (id) ON DELETE CASCADE,
  owner_id      uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  member_id     uuid REFERENCES auth.users (id) ON DELETE CASCADE,   -- null until the invite is accepted
  role          text NOT NULL DEFAULT 'editor' CHECK (role IN ('editor', 'viewer')),
  invite_token  text NOT NULL UNIQUE,
  accepted_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (list_id, invite_token)
);
CREATE INDEX list_shares_member_idx ON list_shares (member_id) WHERE member_id IS NOT NULL;

-- A member sees the lists shared with them; editors may change items; owners keep full control.
CREATE OR REPLACE FUNCTION is_list_member(p_list_id bigint, p_min_role text DEFAULT 'viewer')
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM list_shares s
    WHERE s.list_id = p_list_id AND s.member_id = auth.uid() AND s.accepted_at IS NOT NULL
      AND (p_min_role = 'viewer' OR s.role = 'editor')
  )
$$;

DROP POLICY IF EXISTS lists_own ON lists;
CREATE POLICY lists_own    ON lists USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY lists_shared ON lists FOR SELECT USING (is_list_member(id, 'viewer'));

DROP POLICY IF EXISTS list_items_own ON list_items;
CREATE POLICY list_items_own ON list_items USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY list_items_shared_read  ON list_items FOR SELECT USING (is_list_member(list_id, 'viewer'));
CREATE POLICY list_items_shared_write ON list_items FOR ALL
  USING (is_list_member(list_id, 'editor')) WITH CHECK (is_list_member(list_id, 'editor'));

ALTER TABLE list_shares ENABLE ROW LEVEL SECURITY;
ALTER TABLE list_shares FORCE ROW LEVEL SECURITY;
CREATE POLICY list_shares_owner  ON list_shares USING (owner_id = auth.uid()) WITH CHECK (owner_id = auth.uid());
CREATE POLICY list_shares_member ON list_shares FOR SELECT USING (member_id = auth.uid());

-- Supabase Realtime: publish list changes where the publication exists (no-op elsewhere).
DO $$
DECLARE t text;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
    FOREACH t IN ARRAY ARRAY['lists', 'list_items'] LOOP
      IF NOT EXISTS (SELECT 1 FROM pg_publication_tables WHERE pubname = 'supabase_realtime' AND tablename = t) THEN
        EXECUTE format('ALTER PUBLICATION supabase_realtime ADD TABLE %I', t);
      END IF;
    END LOOP;
  END IF;
END $$;

-- --- grants for the API role and Supabase's authenticated role ---------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON price_alerts, push_subscriptions, list_shares, substitution_feedback TO smartcart_app;
GRANT SELECT, INSERT ON alert_deliveries TO smartcart_app;
GRANT USAGE, SELECT ON SEQUENCE price_alerts_id_seq, push_subscriptions_id_seq, alert_deliveries_id_seq, substitution_feedback_id_seq TO smartcart_app;
GRANT SELECT ON items, prices, promos, promo_items, effective_prices, item_canonical, item_attributes TO smartcart_app;
GRANT EXECUTE ON FUNCTION is_list_member(bigint, text) TO smartcart_app;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON price_alerts, push_subscriptions, list_shares TO authenticated;
    GRANT USAGE, SELECT ON SEQUENCE price_alerts_id_seq, push_subscriptions_id_seq TO authenticated;
    GRANT EXECUTE ON FUNCTION is_list_member(bigint, text) TO authenticated;
  END IF;
END $$;
