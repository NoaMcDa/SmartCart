-- Two follow-ups of the per-item list routes (docs/web-review-2026-10.md, docs/api.md):
--
-- 1. `list_items.client_id`: an idempotency key for adding one item. The browser makes a random
--    uuid per add (the offline queue keeps it with the queued add) and sends it with
--    POST /me/lists/{id}/items. A replay (the response was lost and the queue sent the add again)
--    carries the same id, and the API answers with the stored row (200) instead of inserting a
--    second item (201). Unique per list, and only where the id is present: items written by
--    clients that send none, and every item written before this migration, stay as they were.
--    Same shape as spend_entries.client_id (20261011100400_spend_client_id.sql). Row-level
--    security and the data API grants are unchanged (grants on list_items are table-wide).
--
-- 2. The list's own `updated_at` follows its items. Inserting, changing or deleting an item moves
--    `lists.updated_at` (to now()), so a list somebody just added a milk to sorts first in
--    GET /me/lists and its "updated" label is right. An UPDATE of an item that changes nothing
--    does not (the same rule as the item's own version). The trigger function is SECURITY DEFINER
--    because an editor, who may change items but not the list row, is exactly who writes them: the
--    UPDATE of `lists` must not depend on the editor's row-level security. Its search_path is the
--    schema the migration runs in (public in production, a throwaway schema in the migration
--    tests), never a caller's.

ALTER TABLE list_items ADD COLUMN IF NOT EXISTS client_id uuid;

CREATE UNIQUE INDEX IF NOT EXISTS list_items_list_client_uidx
  ON list_items (list_id, client_id) WHERE client_id IS NOT NULL;

DO $mig$
DECLARE
  s text := current_schema();
BEGIN
  EXECUTE format($fn$
    CREATE OR REPLACE FUNCTION %1$I.list_items_touch_list() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = %1$I, pg_temp AS $body$
    BEGIN
      IF TG_OP = 'INSERT' THEN
        UPDATE lists SET updated_at = now() WHERE id = NEW.list_id AND updated_at < now();
      ELSIF TG_OP = 'DELETE' THEN
        UPDATE lists SET updated_at = now() WHERE id = OLD.list_id AND updated_at < now();
      ELSIF to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD) THEN
        UPDATE lists SET updated_at = now()
         WHERE id IN (NEW.list_id, OLD.list_id) AND updated_at < now();
      END IF;
      RETURN NULL;
    END
    $body$
  $fn$, s);
END
$mig$;

DROP TRIGGER IF EXISTS list_items_touch_list ON list_items;
CREATE TRIGGER list_items_touch_list AFTER INSERT OR UPDATE OR DELETE ON list_items
  FOR EACH ROW EXECUTE FUNCTION list_items_touch_list();
