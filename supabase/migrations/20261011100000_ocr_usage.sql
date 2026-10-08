-- Monthly OCR usage for POST /parse-image (issues #61, #68): the counters behind the spending cap.
--
-- One row per calendar month (UTC) and provider. There is deliberately no user id, session id or
-- image reference: the cap is a global brake on cost, and receipts and handwritten lists are
-- processed in memory and never stored (D11). The API adds one image and the estimated cost after
-- each successful read and refuses with 429 once OCR_MONTHLY_IMAGE_CAP or OCR_MONTHLY_USD_CAP
-- would be exceeded (docs/ocr.md). est_cost_usd is an estimate from usage tokens, not the bill.
--
-- Nothing here is readable through the Supabase data API: row-level security is on with no policy
-- and the roles of the data API have no grants. The API's service connection owns the table.

CREATE TABLE ocr_usage (
  month         date NOT NULL CHECK (month = date_trunc('month', month)::date),
  provider      text NOT NULL CHECK (provider IN ('fake', 'tesseract', 'claude')),
  images        integer NOT NULL DEFAULT 0 CHECK (images >= 0),
  est_cost_usd  numeric(12, 4) NOT NULL DEFAULT 0 CHECK (est_cost_usd >= 0),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (month, provider)
);

ALTER TABLE ocr_usage ENABLE ROW LEVEL SECURITY;
-- No policy: anon and authenticated callers see and write nothing.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    REVOKE ALL ON ocr_usage FROM anon;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    REVOKE ALL ON ocr_usage FROM authenticated;
  END IF;
END $$;
