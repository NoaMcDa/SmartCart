-- effective_prices, what the nightly precompute needs beyond the phase 1 base table (issue #47).
-- Additive only: the primary key stays (canonical_id, store_id, flex_level).
--
--   effective_price  price of one pack (or one kg for weighed goods) after the promo, when the
--                    shopper buys promo_min_qty; equals shelf_price without a promo
--   promo_min_qty    quantity the promo needs (2 for 1+1, 3 for "3 for 20"); NULL without promo.
--                    /compare prices the remainder at the shelf price and offers "add N and save"
--   is_estimated     weighed goods (price per kg)
--   noclub           when the winning row needs a club the user may not have (club_required),
--                    the best option without any club promo, as
--                    {item_id, shelf_price, effective_price, effective_unit_price, uom, promo_id,
--                     promo_min_qty, price_valid_from, is_estimated}; NULL otherwise.
--                    /compare uses it for users who did not mark that club.

ALTER TABLE effective_prices
  ADD COLUMN effective_price numeric,
  ADD COLUMN promo_min_qty   numeric,
  ADD COLUMN is_estimated    boolean NOT NULL DEFAULT false,
  ADD COLUMN noclub          jsonb;

CREATE INDEX effective_prices_lookup_idx ON effective_prices (store_id, flex_level, canonical_id);
