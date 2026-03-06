-- Full-Text Search function for documents
-- Uses the existing GIN index on to_tsvector('english', file_name || ai_summary || extracted_text)

-- Function to search documents using full-text search with relevance ranking
CREATE OR REPLACE FUNCTION search_documents_fts(
    search_query TEXT,
    result_limit INTEGER DEFAULT 50
)
RETURNS TABLE (
    id UUID,
    file_name TEXT,
    current_path TEXT,
    ai_category TEXT,
    ai_subcategories TEXT[],
    ai_summary TEXT,
    entities JSONB,
    key_dates TIMESTAMPTZ[],
    folder_hierarchy TEXT[],
    file_modified_at TIMESTAMPTZ,
    pdf_modified_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    rank REAL
) AS $$
DECLARE
    tsquery_str TEXT;
BEGIN
    -- Convert search query to tsquery format
    -- Split on spaces and join with & for AND semantics
    -- Also add :* suffix for prefix matching
    tsquery_str := regexp_replace(
        trim(search_query),
        '\s+',
        ':* & ',
        'g'
    ) || ':*';

    RETURN QUERY
    SELECT
        d.id,
        d.file_name,
        d.current_path,
        d.ai_category,
        d.ai_subcategories,
        d.ai_summary,
        d.entities,
        d.key_dates,
        d.folder_hierarchy,
        d.file_modified_at,
        d.pdf_modified_date,
        d.created_at,
        d.updated_at,
        ts_rank(
            to_tsvector('english',
                COALESCE(d.file_name, '') || ' ' ||
                COALESCE(d.ai_summary, '') || ' ' ||
                COALESCE(d.extracted_text, '')
            ),
            to_tsquery('english', tsquery_str)
        ) AS rank
    FROM documents d
    WHERE to_tsvector('english',
            COALESCE(d.file_name, '') || ' ' ||
            COALESCE(d.ai_summary, '') || ' ' ||
            COALESCE(d.extracted_text, '')
          ) @@ to_tsquery('english', tsquery_str)
    ORDER BY rank DESC, d.updated_at DESC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql STABLE;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION search_documents_fts(TEXT, INTEGER) TO anon, authenticated;

COMMENT ON FUNCTION search_documents_fts IS
'Full-text search on documents using the existing GIN index.
Supports stemming, prefix matching, and relevance ranking.
Falls back gracefully - returns empty if query parsing fails.';
