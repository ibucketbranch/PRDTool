-- File Processing Status Tracking
-- Track all files processed, including corrupted/empty ones

CREATE TABLE file_processing_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size_bytes BIGINT,
    file_type TEXT, -- pdf, txt, json, etc.
    status TEXT NOT NULL, -- 'pending', 'processing', 'completed', 'failed', 'corrupted', 'empty', 'skipped'
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    processing_duration_seconds INTEGER,
    
    -- Extraction results
    pages_processed INTEGER,
    messages_extracted INTEGER,
    participants_found INTEGER,
    date_range_start TIMESTAMPTZ,
    date_range_end TIMESTAMPTZ,
    
    -- Analysis results reference
    conversation_data_id UUID, -- Reference to parsed conversation
    analysis_completed BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    notes TEXT,
    tags TEXT[], -- e.g., ['corrupted', 'low_quality', 'important', etc.]
    priority INTEGER DEFAULT 0, -- For reprocessing queue
    retry_count INTEGER DEFAULT 0,
    last_retry_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_file_status ON file_processing_status(status);
CREATE INDEX idx_file_name ON file_processing_status(file_name);
CREATE INDEX idx_file_path ON file_processing_status(file_path);
CREATE INDEX idx_created_at ON file_processing_status(created_at);
CREATE INDEX idx_priority ON file_processing_status(priority DESC);
CREATE INDEX idx_tags ON file_processing_status USING GIN(tags);

-- Enable RLS
ALTER TABLE file_processing_status ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all operations" ON file_processing_status FOR ALL USING (true);

-- View for quick status overview
CREATE VIEW processing_summary AS
SELECT 
    status,
    COUNT(*) as file_count,
    SUM(file_size_bytes) as total_size_bytes,
    SUM(messages_extracted) as total_messages,
    AVG(processing_duration_seconds) as avg_duration_seconds,
    MAX(completed_at) as last_processed
FROM file_processing_status
GROUP BY status;

-- View for files needing review
CREATE VIEW files_needing_review AS
SELECT 
    id,
    file_name,
    file_path,
    status,
    error_message,
    notes,
    tags,
    priority,
    retry_count,
    created_at
FROM file_processing_status
WHERE status IN ('failed', 'corrupted', 'empty', 'skipped')
ORDER BY priority DESC, created_at DESC;

-- View for successfully processed files
CREATE VIEW processed_files AS
SELECT 
    id,
    file_name,
    file_path,
    file_size_bytes,
    pages_processed,
    messages_extracted,
    participants_found,
    date_range_start,
    date_range_end,
    processing_duration_seconds,
    analysis_completed,
    completed_at
FROM file_processing_status
WHERE status = 'completed'
ORDER BY completed_at DESC;
