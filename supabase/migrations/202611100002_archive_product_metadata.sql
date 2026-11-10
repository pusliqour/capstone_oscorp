-- Preserve the archive's full catalog metadata without inventing application accounts.
alter table jiran_archive_lab.products
 add column is_common boolean,
 add column expiry_date date,
 add column unit_quantity text,
 add column source_store_id text;
