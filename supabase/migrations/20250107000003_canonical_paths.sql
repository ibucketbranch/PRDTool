-- Add canonical path planning fields for rename workflow
ALTER TABLE documents
    ADD COLUMN canonical_folder TEXT,
    ADD COLUMN canonical_filename TEXT,
    ADD COLUMN rename_status TEXT DEFAULT 'unplanned',
    ADD COLUMN rename_notes TEXT,
    ADD COLUMN last_reviewed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_documents_rename_status ON documents(rename_status);
