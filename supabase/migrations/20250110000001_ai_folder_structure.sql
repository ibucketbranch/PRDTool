-- Add AI-suggested folder structure column
-- This stores the intelligent folder structure proposed by AI (learned from examples)
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS suggested_folder_structure TEXT;

COMMENT ON COLUMN documents.suggested_folder_structure IS 'AI-generated folder structure (learned from examples like "Work Bin/Employment/Resumes/PersonName") - intelligently proposed by AI based on filename, path, content, and entities';

CREATE INDEX IF NOT EXISTS idx_documents_suggested_folder_structure ON documents(suggested_folder_structure) WHERE suggested_folder_structure IS NOT NULL;
