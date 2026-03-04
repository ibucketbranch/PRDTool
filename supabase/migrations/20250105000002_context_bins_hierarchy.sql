-- Enhanced Document Management with Context Bins and Hierarchical Categories
-- Migration to add context bin tracking and parent-child category relationships

-- Add context_bin field to documents table
ALTER TABLE documents ADD COLUMN context_bin TEXT;

-- Add comment explaining the field
COMMENT ON COLUMN documents.context_bin IS 'High-level organizational bin (e.g., Personal Bin, Work Bin, Family Bin, Finances Bin)';

-- Create index for context_bin searches
CREATE INDEX idx_documents_context_bin ON documents(context_bin);

-- Add parent_category_id to support hierarchical categories (if not already exists)
-- This was in the original schema but let's ensure it's properly set up
ALTER TABLE categories ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 0;
COMMENT ON COLUMN categories.level IS 'Hierarchy level: 0=root, 1=category, 2=subcategory';

-- Create index for category hierarchy
CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_category_id);
CREATE INDEX IF NOT EXISTS idx_categories_level ON categories(level);

-- Add context_bin field to folder_analysis
ALTER TABLE folder_analysis ADD COLUMN context_bin TEXT;
CREATE INDEX idx_folder_analysis_context_bin ON folder_analysis(context_bin);

-- Insert hierarchical parent categories
INSERT INTO categories (category_name, description, level, suggested_folder_path) VALUES
-- Root level categories (level 0)
('financial', 'Financial documents and records', 0, 'Documents/Financial'),
('vehicles', 'Vehicle-related documents', 0, 'Documents/Vehicles'),
('personal', 'Personal documents', 0, 'Documents/Personal'),
('legal', 'Legal documents and contracts', 0, 'Documents/Legal'),
('medical', 'Medical and health records', 0, 'Documents/Personal/Medical'),
('professional', 'Work and career documents', 0, 'Documents/Professional'),
('family', 'Family member documents', 0, 'Documents/Family'),
('property', 'Property and real estate', 0, 'Documents/Legal/Property'),
('education', 'Educational documents', 0, 'Documents/Personal/Education')
ON CONFLICT (category_name) DO NOTHING;

-- Update existing categories to be children of parent categories
UPDATE categories SET parent_category_id = (SELECT id FROM categories WHERE category_name = 'vehicles'), level = 1
WHERE category_name IN ('vehicle_registration', 'vehicle_insurance', 'vehicle_maintenance');

UPDATE categories SET parent_category_id = (SELECT id FROM categories WHERE category_name = 'financial'), level = 1
WHERE category_name IN ('tax_document', 'invoice', 'receipt', 'bank_statement', 'utility_bill');

UPDATE categories SET parent_category_id = (SELECT id FROM categories WHERE category_name = 'legal'), level = 1
WHERE category_name IN ('contract', 'property_document');

UPDATE categories SET parent_category_id = (SELECT id FROM categories WHERE category_name = 'medical'), level = 1
WHERE category_name IN ('medical_record');

UPDATE categories SET parent_category_id = (SELECT id FROM categories WHERE category_name = 'personal'), level = 1
WHERE category_name IN ('insurance_policy', 'correspondence');

UPDATE categories SET parent_category_id = (SELECT id FROM categories WHERE category_name = 'professional'), level = 1
WHERE category_name IN ('employment');

UPDATE categories SET parent_category_id = (SELECT id FROM categories WHERE category_name = 'education'), level = 1
WHERE category_name IN ('education');

-- Add more specific subcategories
INSERT INTO categories (category_name, parent_category_id, description, level, suggested_folder_path) VALUES
-- Medical subcategories
('medical_insurance', (SELECT id FROM categories WHERE category_name = 'medical'), 'Medical insurance documents', 2, 'Documents/Personal/Medical/Insurance'),
('medical_prescription', (SELECT id FROM categories WHERE category_name = 'medical'), 'Prescriptions and medications', 2, 'Documents/Personal/Medical/Prescriptions'),
('medical_test_results', (SELECT id FROM categories WHERE category_name = 'medical'), 'Lab and test results', 2, 'Documents/Personal/Medical/Test_Results'),

-- Financial subcategories
('credit_report', (SELECT id FROM categories WHERE category_name = 'financial'), 'Credit reports and scores', 2, 'Documents/Financial/Credit'),
('investment', (SELECT id FROM categories WHERE category_name = 'financial'), 'Investment documents', 2, 'Documents/Financial/Investments'),
('retirement', (SELECT id FROM categories WHERE category_name = 'financial'), 'Retirement accounts (401k, IRA)', 2, 'Documents/Financial/Retirement'),

-- Legal subcategories  
('divorce', (SELECT id FROM categories WHERE category_name = 'legal'), 'Divorce documents', 2, 'Documents/Legal/Divorce'),
('court_documents', (SELECT id FROM categories WHERE category_name = 'legal'), 'Court records and filings', 2, 'Documents/Legal/Court'),
('power_of_attorney', (SELECT id FROM categories WHERE category_name = 'legal'), 'Power of attorney documents', 2, 'Documents/Legal/POA'),

-- Personal subcategories
('identification', (SELECT id FROM categories WHERE category_name = 'personal'), 'ID cards, passports, etc.', 2, 'Documents/Personal/Identification'),
('travel', (SELECT id FROM categories WHERE category_name = 'personal'), 'Travel documents', 2, 'Documents/Personal/Travel'),
('memberships', (SELECT id FROM categories WHERE category_name = 'personal'), 'Membership cards and documents', 2, 'Documents/Personal/Memberships')
ON CONFLICT DO NOTHING;

-- Create view for category hierarchy
CREATE OR REPLACE VIEW category_hierarchy AS
WITH RECURSIVE cat_tree AS (
    -- Base case: root categories
    SELECT 
        id,
        category_name,
        parent_category_id,
        description,
        level,
        category_name::TEXT as full_path,
        ARRAY[category_name] as path_array
    FROM categories
    WHERE parent_category_id IS NULL
    
    UNION ALL
    
    -- Recursive case: child categories
    SELECT 
        c.id,
        c.category_name,
        c.parent_category_id,
        c.description,
        c.level,
        ct.full_path || ' > ' || c.category_name as full_path,
        ct.path_array || c.category_name as path_array
    FROM categories c
    INNER JOIN cat_tree ct ON c.parent_category_id = ct.id
)
SELECT * FROM cat_tree ORDER BY full_path;

-- Create view for documents with bin and category hierarchy
CREATE OR REPLACE VIEW documents_with_context AS
SELECT 
    d.id,
    d.file_name,
    d.current_path,
    d.context_bin,
    d.ai_category,
    d.ai_summary,
    d.confidence_score,
    d.tags,
    ch.full_path as category_path,
    ch.level as category_level,
    d.entities,
    d.importance_score,
    d.created_at,
    d.last_accessed_at
FROM documents d
LEFT JOIN categories c ON d.ai_category = c.category_name
LEFT JOIN category_hierarchy ch ON c.id = ch.id
ORDER BY d.created_at DESC;

-- Add common context bins as reference data
CREATE TABLE IF NOT EXISTS context_bins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bin_name TEXT UNIQUE NOT NULL,
    description TEXT,
    icon TEXT,
    color TEXT,
    sort_order INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert standard bins based on user's structure
INSERT INTO context_bins (bin_name, description, icon, sort_order) VALUES
('Personal Bin', 'Personal documents and records', '👤', 1),
('Work Bin', 'Professional and work-related documents', '💼', 2),
('Family Bin', 'Family member documents', '👨‍👩‍👧‍👦', 3),
('Finances Bin', 'Financial records and statements', '💰', 4),
('Legal Bin', 'Legal documents and contracts', '⚖️', 5),
('Projects Bin', 'Project-related documents', '📁', 6),
('NetV', 'NetV specific documents', '📺', 7),
('LEOPard', 'LEOPard documents', '🐆', 8),
('USAA Visa', 'USAA Visa documents', '💳', 9)
ON CONFLICT (bin_name) DO NOTHING;

-- Enable RLS on new table
ALTER TABLE context_bins ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all operations" ON context_bins FOR ALL USING (true);

-- Add function to auto-detect context bin from path
CREATE OR REPLACE FUNCTION extract_context_bin(file_path TEXT)
RETURNS TEXT AS $$
DECLARE
    bin_name TEXT;
BEGIN
    -- Try to match against known bin names in path
    SELECT cb.bin_name INTO bin_name
    FROM context_bins cb
    WHERE file_path ILIKE '%' || cb.bin_name || '%'
    ORDER BY LENGTH(cb.bin_name) DESC
    LIMIT 1;
    
    -- If no match, try common folder patterns
    IF bin_name IS NULL THEN
        CASE
            WHEN file_path ILIKE '%personal%' THEN bin_name := 'Personal Bin';
            WHEN file_path ILIKE '%work%' OR file_path ILIKE '%professional%' THEN bin_name := 'Work Bin';
            WHEN file_path ILIKE '%family%' THEN bin_name := 'Family Bin';
            WHEN file_path ILIKE '%finance%' OR file_path ILIKE '%financial%' THEN bin_name := 'Finances Bin';
            WHEN file_path ILIKE '%legal%' THEN bin_name := 'Legal Bin';
            WHEN file_path ILIKE '%project%' THEN bin_name := 'Projects Bin';
            ELSE bin_name := NULL;
        END CASE;
    END IF;
    
    RETURN bin_name;
END;
$$ LANGUAGE plpgsql;

-- Update existing documents to populate context_bin
UPDATE documents 
SET context_bin = extract_context_bin(current_path)
WHERE context_bin IS NULL;

-- Create statistics view by bin
CREATE OR REPLACE VIEW bin_statistics AS
SELECT 
    context_bin,
    COUNT(*) as document_count,
    COUNT(DISTINCT ai_category) as category_count,
    AVG(confidence_score) as avg_confidence,
    AVG(importance_score) as avg_importance,
    MAX(created_at) as last_added
FROM documents
WHERE context_bin IS NOT NULL
GROUP BY context_bin
ORDER BY document_count DESC;

-- Add trigger to auto-populate context_bin on insert
CREATE OR REPLACE FUNCTION auto_populate_context_bin()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.context_bin IS NULL THEN
        NEW.context_bin := extract_context_bin(NEW.current_path);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_context_bin_on_insert
BEFORE INSERT ON documents
FOR EACH ROW
EXECUTE FUNCTION auto_populate_context_bin();
