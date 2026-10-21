-- Shared lists without last-write-wins (docs/web-review-2026-10.md, "per-item writes").
--
-- list_items gets `updated_at`, the version of one item. The per-item API routes
-- (PATCH / DELETE /me/lists/{id}/items/{item_id}) take it back as a precondition and answer 409
-- with the current row when somebody else changed the item since the caller read it; the client
-- merges (apps/web/src/features/share/listSync.ts).
--
-- The value is written only by the trigger, never by the caller, because the data API
-- (PostgREST, role `authenticated`) can UPDATE list_items and a forged value would defeat the
-- precondition:
--   * INSERT: the time of the insert (clock_timestamp(), not now(): now() is the start of the
--     transaction, and a transaction that started earlier but commits later would carry an older
--     version than one a client has already read).
--   * UPDATE that changes nothing (a PATCH with the same values, a PUT of an unchanged item):
--     the old value, so a no-op neither moves the version nor makes a conflict for the others.
--   * any other UPDATE: the current time, and always later than the old value even if the clock
--     moved back, so a version is never reused for different content.
-- The column is not in any GRANT list: grants on list_items are table-wide (see
-- 20261021120100_data_api_lockdown.sql), so the data API privilege matrix does not change.

ALTER TABLE list_items ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE OR REPLACE FUNCTION list_items_touch() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    NEW.updated_at := clock_timestamp();
  ELSIF (to_jsonb(NEW) - 'updated_at') IS NOT DISTINCT FROM (to_jsonb(OLD) - 'updated_at') THEN
    NEW.updated_at := OLD.updated_at;
  ELSE
    NEW.updated_at := greatest(clock_timestamp(), OLD.updated_at + interval '1 microsecond');
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS list_items_touch ON list_items;
CREATE TRIGGER list_items_touch BEFORE INSERT OR UPDATE ON list_items
  FOR EACH ROW EXECUTE FUNCTION list_items_touch();
