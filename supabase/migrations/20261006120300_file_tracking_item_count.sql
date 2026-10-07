-- Record count of each loaded file, used by the item-count-drop quality gate.
-- Until this column existed the loader kept the count in reason as "items=<n>"; the code
-- switches to the column automatically (see smartcart_ingest/tracking.py).
alter table file_tracking add column if not exists item_count integer;
comment on column file_tracking.item_count is 'Number of records in the file at load time (null until loaded).';
