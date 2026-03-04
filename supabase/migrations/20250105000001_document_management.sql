-- Document Management System Schema
-- Handles both conversation PDFs and general document organization

-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Main documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- File identification
    file_hash TEXT UNIQUE NOT NULL, -- SHA256 for duplicate detection
    file_name TEXT NOT NULL,
    file_size_bytes BIGINT,
    file_type TEXT DEFAULT 'pdf',
    
    -- Location tracking
    current_path TEXT NOT NULL, -- Full absolute path
    folder_hierarchy TEXT[], -- Array: ['Documents', 'Personal', 'Cars', 'Tesla']
    suggested_path TEXT, -- AI-suggested better location
    path_confidence NUMERIC, -- 0-1: confidence in current path appropriateness
    last_verified_at TIMESTAMPTZ, -- Last time we verified file still exists
    
    -- Document mode (dual-mode system)
    document_mode TEXT NOT NULL, -- 'conversation' or 'document'
    is_conversation BOOLEAN DEFAULT FALSE,
    
    -- PDF metadata
    pdf_title TEXT,
    pdf_author TEXT,
    pdf_subject TEXT,
    pdf_keywords TEXT[],
    page_count INTEGER,
    pdf_created_date TIMESTAMPTZ,
    pdf_modified_date TIMESTAMPTZ,
    
    -- Content
    extracted_text TEXT, -- Full text content
    text_preview TEXT, -- First ~500 chars for quick preview
    
    -- AI-generated metadata
    ai_summary TEXT, -- AI-generated summary of content
    ai_category TEXT, -- Primary category (e.g., 'vehicle_registration', 'tax_document', 'invoice')
    ai_subcategories TEXT[], -- Additional categories
    confidence_score NUMERIC, -- 0-1: AI confidence in categorization
    
    -- Extracted entities (for search)
    entities JSONB, -- {people: [], organizations: [], dates: [], amounts: [], vehicles: []}
    key_dates TIMESTAMPTZ[], -- Important dates found in document
    
    -- Vector embedding for semantic search
    content_embedding vector(1536), -- OpenAI ada-002 embedding dimension
    
    -- Organization metadata
    project_collection TEXT, -- Logical grouping (e.g., '2024_Taxes', 'Tesla_Model3')
    tags TEXT[], -- User-defined or AI-suggested tags
    importance_score INTEGER DEFAULT 0, -- 0-10: importance/priority
    access_frequency INTEGER DEFAULT 0, -- How often accessed
    last_accessed_at TIMESTAMPTZ,
    
    -- Processing status
    processing_status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    ocr_required BOOLEAN DEFAULT FALSE,
    ocr_completed BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    indexed_at TIMESTAMPTZ
);

-- Alternate locations table (for duplicates)
CREATE TABLE document_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    location_path TEXT NOT NULL,
    location_type TEXT, -- 'primary', 'backup', 'cloud', 'archive', 'duplicate'
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    verified_at TIMESTAMPTZ,
    is_accessible BOOLEAN DEFAULT TRUE,
    notes TEXT
);

-- Categories taxonomy table
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_name TEXT UNIQUE NOT NULL,
    parent_category_id UUID REFERENCES categories(id),
    description TEXT,
    suggested_folder_path TEXT, -- Suggested folder structure for this category
    icon TEXT, -- For UI
    color TEXT, -- For UI
    document_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document-category mapping (many-to-many)
CREATE TABLE document_categories (
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    category_id UUID REFERENCES categories(id) ON DELETE CASCADE,
    confidence NUMERIC, -- How confident are we this category applies
    is_primary BOOLEAN DEFAULT FALSE,
    assigned_by TEXT, -- 'ai', 'user', 'rule'
    PRIMARY KEY (document_id, category_id)
);

-- Folder structure analysis table
CREATE TABLE folder_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    folder_path TEXT NOT NULL,
    parent_folder TEXT,
    depth INTEGER, -- Depth in hierarchy
    document_count INTEGER DEFAULT 0,
    
    -- Analysis results
    primary_categories TEXT[], -- Main categories found in this folder
    category_diversity NUMERIC, -- 0-1: how mixed the categories are
    is_well_organized BOOLEAN,
    organization_score NUMERIC, -- 0-100: how well organized
    
    -- Suggestions
    suggested_rename TEXT,
    suggested_restructure JSONB, -- Detailed restructuring suggestions
    misplaced_document_count INTEGER DEFAULT 0,
    
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Search queries log (learn from user searches)
CREATE TABLE search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    query_type TEXT, -- 'natural_language', 'category', 'tag', 'entity'
    extracted_entities JSONB, -- Entities extracted from query
    results_count INTEGER,
    top_result_id UUID REFERENCES documents(id),
    user_clicked_result_id UUID REFERENCES documents(id), -- Which result did user actually select
    search_duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Reorganization suggestions table
CREATE TABLE reorganization_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suggestion_type TEXT, -- 'move_file', 'rename_folder', 'create_hierarchy', 'merge_folders'
    priority INTEGER, -- 1-10
    
    -- Current state
    current_path TEXT,
    affected_documents UUID[],
    
    -- Suggested state
    suggested_path TEXT,
    suggested_action TEXT,
    reasoning TEXT, -- Why this suggestion
    
    -- Metadata
    confidence NUMERIC,
    estimated_improvement NUMERIC, -- Expected organization score improvement
    status TEXT DEFAULT 'pending', -- 'pending', 'accepted', 'rejected', 'applied'
    applied_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_documents_hash ON documents(file_hash);
CREATE INDEX idx_documents_path ON documents(current_path);
CREATE INDEX idx_documents_mode ON documents(document_mode);
CREATE INDEX idx_documents_category ON documents(ai_category);
CREATE INDEX idx_documents_tags ON documents USING GIN(tags);
CREATE INDEX idx_documents_entities ON documents USING GIN(entities);
CREATE INDEX idx_documents_hierarchy ON documents USING GIN(folder_hierarchy);
CREATE INDEX idx_documents_embedding ON documents USING ivfflat (content_embedding vector_cosine_ops);
CREATE INDEX idx_document_locations_path ON document_locations(location_path);
CREATE INDEX idx_folder_analysis_path ON folder_analysis(folder_path);
CREATE INDEX idx_search_queries_created ON search_queries(created_at DESC);

-- Full text search index
CREATE INDEX idx_documents_text_search ON documents USING GIN(to_tsvector('english', 
    COALESCE(file_name, '') || ' ' || 
    COALESCE(ai_summary, '') || ' ' || 
    COALESCE(extracted_text, '')
));

-- Enable Row Level Security
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE folder_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE reorganization_suggestions ENABLE ROW LEVEL SECURITY;

-- Policies (allow all for local development)
CREATE POLICY "Allow all operations" ON documents FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON document_locations FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON categories FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON document_categories FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON folder_analysis FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON search_queries FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON reorganization_suggestions FOR ALL USING (true);

-- Useful views

-- View for quick document search results
CREATE VIEW document_search_view AS
SELECT 
    d.id,
    d.file_name,
    d.current_path,
    d.ai_summary,
    d.ai_category,
    d.tags,
    d.text_preview,
    d.page_count,
    d.entities,
    d.importance_score,
    d.confidence_score,
    array_agg(DISTINCT c.category_name) as categories,
    d.last_accessed_at,
    d.created_at
FROM documents d
LEFT JOIN document_categories dc ON d.id = dc.document_id
LEFT JOIN categories c ON dc.category_id = c.id
GROUP BY d.id;

-- View for folder organization overview
CREATE VIEW folder_organization_overview AS
SELECT 
    fa.folder_path,
    fa.document_count,
    fa.primary_categories,
    fa.organization_score,
    fa.is_well_organized,
    COUNT(rs.id) as pending_suggestions,
    fa.analyzed_at
FROM folder_analysis fa
LEFT JOIN reorganization_suggestions rs ON fa.folder_path = rs.current_path 
    AND rs.status = 'pending'
GROUP BY fa.id, fa.folder_path, fa.document_count, fa.primary_categories, 
    fa.organization_score, fa.is_well_organized, fa.analyzed_at
ORDER BY fa.organization_score ASC;

-- View for duplicate documents
CREATE VIEW duplicate_documents AS
SELECT 
    d.file_hash,
    d.file_name,
    COUNT(dl.id) + 1 as location_count,
    array_agg(DISTINCT dl.location_path) as all_locations,
    d.file_size_bytes,
    d.ai_summary
FROM documents d
LEFT JOIN document_locations dl ON d.id = dl.document_id
GROUP BY d.file_hash, d.file_name, d.file_size_bytes, d.ai_summary
HAVING COUNT(dl.id) > 0
ORDER BY location_count DESC;

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION update_document_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_document_timestamp
BEFORE UPDATE ON documents
FOR EACH ROW
EXECUTE FUNCTION update_document_timestamp();

-- Function to update category document count
CREATE OR REPLACE FUNCTION update_category_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE categories 
        SET document_count = document_count + 1 
        WHERE id = NEW.category_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE categories 
        SET document_count = document_count - 1 
        WHERE id = OLD.category_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_category_count_trigger
AFTER INSERT OR DELETE ON document_categories
FOR EACH ROW
EXECUTE FUNCTION update_category_count();

-- Insert some common categories
INSERT INTO categories (category_name, description, suggested_folder_path) VALUES
('vehicle_registration', 'Vehicle registration documents', 'Documents/Vehicles/{Vehicle}/Registration'),
('vehicle_insurance', 'Vehicle insurance policies and documents', 'Documents/Vehicles/{Vehicle}/Insurance'),
('vehicle_maintenance', 'Vehicle service and maintenance records', 'Documents/Vehicles/{Vehicle}/Maintenance'),
('tax_document', 'Tax returns and related documents', 'Documents/Financial/Taxes/{Year}'),
('invoice', 'Bills and invoices', 'Documents/Financial/Invoices/{Year}'),
('receipt', 'Purchase receipts', 'Documents/Financial/Receipts/{Year}'),
('contract', 'Legal contracts and agreements', 'Documents/Legal/Contracts'),
('medical_record', 'Medical records and health documents', 'Documents/Personal/Medical'),
('insurance_policy', 'Insurance policies', 'Documents/Financial/Insurance'),
('bank_statement', 'Bank and financial statements', 'Documents/Financial/Statements/{Year}'),
('utility_bill', 'Utility bills and statements', 'Documents/Financial/Utilities/{Year}'),
('property_document', 'Property and real estate documents', 'Documents/Legal/Property'),
('education', 'Educational documents and certificates', 'Documents/Personal/Education'),
('employment', 'Employment and work-related documents', 'Documents/Professional/Employment'),
('correspondence', 'Letters and official correspondence', 'Documents/Correspondence');
