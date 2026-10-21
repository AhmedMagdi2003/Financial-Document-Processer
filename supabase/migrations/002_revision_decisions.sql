-- Upgrade only for installations made before content rejection was added.
-- scripts.setup_db detects missing columns and applies this additive change.
-- A fresh 001_initial.sql already contains these columns; do not apply both blindly.
ALTER TABLE content_revisions ADD COLUMN decision VARCHAR(20) NOT NULL DEFAULT 'draft';
ALTER TABLE content_revisions ADD COLUMN decision_reason TEXT;
UPDATE content_revisions SET decision='approved' WHERE approved_at IS NOT NULL;
