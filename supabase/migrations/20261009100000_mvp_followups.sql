-- MVP completion follow-ups (issues #101, #102, #16).
-- requires: vector
--
-- 1. list_shares.id: a stable id per invite or membership, so the owner can revoke a pending
--    invite (whose token only the invitee has; the table keeps a SHA-256 of it) or remove a
--    member with DELETE /me/lists/{list_id}/shares/{share_id}.
-- 2. list_items.checked: ticked off in the store (shared lists). The list_items RLS policies are
--    unchanged: the owner and editors may update it, viewers may not.
-- 3. substitution_feedback.source: where a verdict came from, the substitution card or the
--    smart-cart swap (apply = accepted, undo = kept_original, dismiss = not_good).
-- 4. Report-a-gap as a data-quality signal (#16): gap_report_pressure(since, until) summarises
--    gap_reports per (chain, store), quality_gap_reports_7d is that summary over the last 7 days.
--    The ingest quality gates read it for a soft "gap-report pressure" warning, and the internal
--    dashboard shows it. Nothing here is personal: counts per store only.
-- 5. quality_warnings: soft ingest warnings (never quarantine a file), one row per warning.
--
-- requires vector only because substitution_feedback and gap_reports depend on the catalog
-- migration (20261007100000_catalog_v1.sql), which does.

-- --- 1. list_shares.id -------------------------------------------------------------------------
ALTER TABLE list_shares ADD COLUMN IF NOT EXISTS id bigint GENERATED ALWAYS AS IDENTITY;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'list_shares_id_key') THEN
    ALTER TABLE list_shares ADD CONSTRAINT list_shares_id_key UNIQUE (id);
  END IF;
END $$;

-- --- 2. list_items.checked ---------------------------------------------------------------------
ALTER TABLE list_items ADD COLUMN IF NOT EXISTS checked boolean NOT NULL DEFAULT false;

-- --- 3. substitution_feedback.source -----------------------------------------------------------
ALTER TABLE substitution_feedback ADD COLUMN IF NOT EXISTS source text NOT NULL
  DEFAULT 'substitution_card' CHECK (source IN ('substitution_card', 'swap'));

-- --- 4. gap-report pressure --------------------------------------------------------------------
-- One row per store with at least one report in [p_since, p_until) (created_at).
--
--   reports           every report
--   price_mismatches  confirmed price mismatches: the report carries both the price we showed
--                     and the price the user saw at the shelf, and they differ by at least one
--                     agora. Counted once per reporter and product, so one person reporting the
--                     same product twice counts once; each anonymous report counts on its own.
--   wrong_product     reports tagged '#reason=wrong_product' in the note (the web app's tail)
--   promo_wrong       reports tagged '#reason=promo_wrong'
--   reporters         distinct signed-in reporters, plus one per anonymous report
--   last_report_at    newest report in the window
CREATE OR REPLACE FUNCTION gap_report_pressure(
  p_since timestamptz DEFAULT now() - interval '7 days',
  p_until timestamptz DEFAULT now()
)
RETURNS TABLE (
  chain_id          text,
  store_id          bigint,
  store_code        text,
  store_name        text,
  reports           bigint,
  price_mismatches  bigint,
  wrong_product     bigint,
  promo_wrong       bigint,
  reporters         bigint,
  last_report_at    timestamptz
)
LANGUAGE sql STABLE SET search_path = public AS $$
  SELECT s.chain_id,
         s.id,
         s.store_code,
         s.name,
         count(*),
         count(DISTINCT coalesce(g.user_id::text, 'anon:' || g.id::text) || '/'
                        || coalesce('i' || g.item_id::text, 'c' || g.canonical_id::text,
                                    'r' || g.id::text))
           FILTER (WHERE g.shown_price IS NOT NULL AND g.actual_price IS NOT NULL
                     AND abs(g.shown_price - g.actual_price) >= 0.01),
         count(*) FILTER (WHERE g.note ~ '#reason=wrong_product\M'),
         count(*) FILTER (WHERE g.note ~ '#reason=promo_wrong\M'),
         count(DISTINCT coalesce(g.user_id::text, 'anon:' || g.id::text)),
         max(g.created_at)
  FROM gap_reports AS g
  JOIN stores AS s ON s.id = g.store_id
  WHERE g.created_at >= p_since AND g.created_at < p_until
  GROUP BY s.chain_id, s.id, s.store_code, s.name
$$;

-- The last 7 days up to now; 'infinity' so a report written in the current transaction counts.
CREATE OR REPLACE VIEW quality_gap_reports_7d WITH (security_invoker = true) AS
SELECT * FROM gap_report_pressure(now() - interval '7 days', 'infinity')
ORDER BY price_mismatches DESC, reports DESC, chain_id, store_code;

-- --- 5. quality_warnings -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quality_warnings (
  id          bigserial PRIMARY KEY,
  file_id     bigint REFERENCES file_tracking (id) ON DELETE SET NULL,
  chain_id    text NOT NULL,
  store_code  text,
  warning     text NOT NULL,
  detail      text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS quality_warnings_store_idx
  ON quality_warnings (chain_id, store_code, warning, created_at DESC);

-- --- grants ------------------------------------------------------------------------------------
-- Internal data: not for the browser roles. The ingest and read-only dashboard roles (created by
-- hand, docs/infra-provisioning.md) get what they need when they exist.
REVOKE ALL ON FUNCTION gap_report_pressure(timestamptz, timestamptz) FROM PUBLIC;
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON quality_warnings, quality_gap_reports_7d FROM %I', r);
      EXECUTE format('REVOKE ALL ON SEQUENCE quality_warnings_id_seq FROM %I', r);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartcart_ingest') THEN
    GRANT EXECUTE ON FUNCTION gap_report_pressure(timestamptz, timestamptz) TO smartcart_ingest;
    GRANT SELECT, INSERT ON quality_warnings TO smartcart_ingest;
    GRANT USAGE, SELECT ON SEQUENCE quality_warnings_id_seq TO smartcart_ingest;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartcart_readonly') THEN
    GRANT EXECUTE ON FUNCTION gap_report_pressure(timestamptz, timestamptz) TO smartcart_readonly;
    GRANT SELECT ON quality_warnings, quality_gap_reports_7d, gap_reports TO smartcart_readonly;
  END IF;
END $$;
