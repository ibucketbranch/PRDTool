-- Add pagination support to FTS search functions

-- Update search_documents_fts to support offset for pagination
CREATE OR REPLACE FUNCTION search_documents_fts(
    search_query TEXT,
    result_limit INTEGER DEFAULT 20,
    result_offset INTEGER DEFAULT 0
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
    LIMIT result_limit
    OFFSET result_offset;
END;
$$ LANGUAGE plpgsql STABLE;

-- Grant execute permission (update for new signature)
GRANT EXECUTE ON FUNCTION search_documents_fts(TEXT, INTEGER, INTEGER) TO anon, authenticated;

COMMENT ON FUNCTION search_documents_fts(TEXT, INTEGER, INTEGER) IS
'Full-text search on documents using the existing GIN index.
Supports stemming, prefix matching, relevance ranking, and pagination via offset.';


-- Update natural_language_search_fts to support offset for pagination
CREATE OR REPLACE FUNCTION natural_language_search_fts(
    search_terms TEXT[] DEFAULT NULL,
    category_filter TEXT DEFAULT NULL,
    organization_filters TEXT[] DEFAULT NULL,
    result_limit INTEGER DEFAULT 20,
    result_offset INTEGER DEFAULT 0
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
    -- Build tsquery from search terms if provided
    IF search_terms IS NOT NULL AND array_length(search_terms, 1) > 0 THEN
        -- Join terms with & for AND semantics, add :* for prefix matching
        tsquery_str := array_to_string(
            ARRAY(
                SELECT term || ':*'
                FROM unnest(search_terms) AS term
                WHERE trim(term) != ''
            ),
            ' & '
        );
    END IF;

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
        CASE
            WHEN tsquery_str IS NOT NULL AND tsquery_str != '' THEN
                ts_rank(
                    to_tsvector('english',
                        COALESCE(d.file_name, '') || ' ' ||
                        COALESCE(d.ai_summary, '') || ' ' ||
                        COALESCE(d.extracted_text, '')
                    ),
                    to_tsquery('english', tsquery_str)
                )
            ELSE 1.0
        END AS rank
    FROM documents d
    WHERE
        -- FTS filter (if search terms provided)
        (
            tsquery_str IS NULL
            OR tsquery_str = ''
            OR to_tsvector('english',
                COALESCE(d.file_name, '') || ' ' ||
                COALESCE(d.ai_summary, '') || ' ' ||
                COALESCE(d.extracted_text, '')
            ) @@ to_tsquery('english', tsquery_str)
        )
        -- Category filter
        AND (
            category_filter IS NULL
            OR d.ai_category ILIKE '%' || category_filter || '%'
        )
        -- Organization filter (check if any org matches entities->organizations)
        AND (
            organization_filters IS NULL
            OR array_length(organization_filters, 1) IS NULL
            OR EXISTS (
                SELECT 1
                FROM jsonb_array_elements_text(COALESCE(d.entities->'organizations', '[]'::jsonb)) AS org
                WHERE EXISTS (
                    SELECT 1
                    FROM unnest(organization_filters) AS filter_org
                    WHERE org ILIKE '%' || filter_org || '%'
                )
            )
        )
    ORDER BY rank DESC, d.updated_at DESC
    LIMIT result_limit
    OFFSET result_offset;
END;
$$ LANGUAGE plpgsql STABLE;

-- Grant execute permission (update for new signature)
GRANT EXECUTE ON FUNCTION natural_language_search_fts(TEXT[], TEXT, TEXT[], INTEGER, INTEGER) TO anon, authenticated;

COMMENT ON FUNCTION natural_language_search_fts(TEXT[], TEXT, TEXT[], INTEGER, INTEGER) IS
'Natural language search on documents with FTS, category and organization filters.
Supports stemming, relevance ranking, and pagination via offset.';
