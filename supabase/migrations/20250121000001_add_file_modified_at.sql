-- Add filesystem modification date column to documents table
-- This stores the actual file modification time from the filesystem (st_mtime)
-- which is more accurate than PDF metadata dates for tracking file changes

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS file_modified_at TIMESTAMPTZ;

-- Add index for efficient sorting/filtering by modification date
CREATE INDEX IF NOT EXISTS idx_documents_file_modified_at 
ON documents(file_modified_at DESC);

COMMENT ON COLUMN documents.file_modified_at IS 'Filesystem modification time (st_mtime) - when the file was last modified on disk';
