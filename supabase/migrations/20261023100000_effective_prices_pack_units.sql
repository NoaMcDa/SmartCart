-- effective_prices.pack_units: how many base units one shelf item holds (docs/optimizer.md, "Packs").
--
-- For a canonical counted in units (eggs, pitas, toilet paper) the precompute now prices an item at
-- `shelf price / units in the item`, reading the count from the name when the chain's own fields say
-- `1 יחידות` (a tray of 12 eggs at 14.20 is 1.1833 an egg, not 14.20). /compare needs the same count
-- to buy whole packs for the quantity asked: 12 eggs from a tray of 30 is one tray, from a pack of 6
-- two packs. NULL means the item does not state a count (or the canonical is a weight or a volume):
-- the quantity then counts shelf items, as before.
--
-- Additive: no row changes until the next precompute, and a NULL leaves a row priced as it was.
-- `noclub` (jsonb) gets the same key `pack_units` in each option from the precompute on; a missing
-- key reads as NULL.

ALTER TABLE effective_prices
  ADD COLUMN IF NOT EXISTS pack_units numeric CHECK (pack_units IS NULL OR pack_units > 0);
