-- Report-a-gap (D10 trust signal): a user says the shown price or availability was wrong.
-- Written by POST /feedback/gap; read by the data-quality review. user_id is null for anonymous
-- reports. No location is stored here.

CREATE TABLE gap_reports (
  id            bigserial PRIMARY KEY,
  store_id      bigint NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
  item_id       bigint REFERENCES items (id) ON DELETE SET NULL,
  canonical_id  bigint REFERENCES canonical_products (id) ON DELETE SET NULL,
  shown_price   numeric CHECK (shown_price >= 0),
  actual_price  numeric CHECK (actual_price >= 0),
  note          text CHECK (char_length(note) <= 500),
  user_id       uuid,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX gap_reports_store_idx ON gap_reports (store_id, created_at DESC);
CREATE INDEX gap_reports_item_idx ON gap_reports (item_id) WHERE item_id IS NOT NULL;
