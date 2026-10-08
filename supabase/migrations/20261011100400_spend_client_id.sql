-- Idempotent spend entries (issue #70 follow-up).
--
-- The browser makes a random uuid per entry and sends it as client_id with POST /me/spend. A retry
-- (a lost response, a double tap, an offline queue replayed twice) carries the same id, and the API
-- returns the stored row instead of inserting a duplicate. Unique per user, so two people can never
-- collide, and only where the id is present: entries from clients that send none stay as before.
-- Row-level security is unchanged (spend_entries_own).

ALTER TABLE spend_entries ADD COLUMN IF NOT EXISTS client_id uuid;

CREATE UNIQUE INDEX IF NOT EXISTS spend_entries_user_client_uidx
  ON spend_entries (user_id, client_id) WHERE client_id IS NOT NULL;
