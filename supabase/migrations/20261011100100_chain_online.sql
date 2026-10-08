-- Cart handoff to chain online stores (issue #72). Each chain may carry the address of its own
-- public online store and of that store's public site search. The app only ever puts these in a
-- link the user's browser opens; nothing is fetched, scraped or automated (CLAUDE.md, docs/cart-transfer.md).
-- Ranking, savings and substitutions never read these columns (services/api/tests/test_api_handoff_independence.py).

ALTER TABLE chains
  ADD COLUMN online_url           text,
  ADD COLUMN search_url_template  text,
  ADD COLUMN online_referral      boolean NOT NULL DEFAULT false;

ALTER TABLE chains
  ADD CONSTRAINT chains_online_url_https
    CHECK (online_url IS NULL OR online_url ~ '^https://[^[:space:]]+$'),
  -- {q} is replaced by the URL-encoded item name in the browser; a template without it is useless.
  ADD CONSTRAINT chains_search_url_template_ok
    CHECK (search_url_template IS NULL
           OR (search_url_template ~ '^https://[^[:space:]]+$' AND position('{q}' IN search_url_template) > 0));

COMMENT ON COLUMN chains.online_url IS 'The chain''s own public online-store home page; a link only';
COMMENT ON COLUMN chains.search_url_template IS 'The chain''s public site-search URL with {q} for the query; a link only';
COMMENT ON COLUMN chains.online_referral IS 'True when links to this chain carry a referral; always labeled in the UI, never read by ranking';

-- Seed values. Chain rows are created by the ingest loader, usually after this migration runs, so the
-- addresses live in a small table and a trigger fills them into a new chain row. Existing rows are
-- updated below. Every address is UNVERIFIED (stated from the chains' public sites as widely known,
-- not checked against a live site from this repository): check before enabling a chain.
-- Chains not listed have no address; better NULL than wrong. See docs/cart-transfer.md.
CREATE TABLE chain_online_seed (
  chain_id             text PRIMARY KEY,
  online_url           text NOT NULL CHECK (online_url ~ '^https://[^[:space:]]+$'),
  search_url_template  text CHECK (search_url_template IS NULL
                                   OR (search_url_template ~ '^https://[^[:space:]]+$'
                                       AND position('{q}' IN search_url_template) > 0))
);
-- Reachable by the migration owner and the SECURITY DEFINER trigger only, not through PostgREST.
ALTER TABLE chain_online_seed ENABLE ROW LEVEL SECURITY;

INSERT INTO chain_online_seed (chain_id, online_url, search_url_template) VALUES
  ('7290027600007', 'https://www.shufersal.co.il/online/', 'https://www.shufersal.co.il/online/he/search?text={q}'),  -- Shufersal
  ('7290058140886', 'https://www.rami-levy.co.il/he/online', 'https://www.rami-levy.co.il/he/online/search?q={q}'),  -- Rami Levy
  ('7290803800003', 'https://yochananof.co.il/', NULL),                                                              -- Yochananof, home page only
  ('7290696200003', 'https://www.victoryonline.co.il/', NULL);                                                       -- Victory, home page only

CREATE FUNCTION chains_apply_online_seed() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF NEW.online_url IS NULL AND NEW.search_url_template IS NULL THEN
    SELECT s.online_url, s.search_url_template INTO NEW.online_url, NEW.search_url_template
      FROM chain_online_seed AS s WHERE s.chain_id = NEW.id;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER chains_apply_online_seed BEFORE INSERT ON chains
  FOR EACH ROW EXECUTE FUNCTION chains_apply_online_seed();

UPDATE chains AS c
   SET online_url = s.online_url, search_url_template = s.search_url_template
  FROM chain_online_seed AS s
 WHERE s.chain_id = c.id AND c.online_url IS NULL AND c.search_url_template IS NULL;
