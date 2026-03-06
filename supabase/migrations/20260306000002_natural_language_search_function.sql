-- Natural Language Search function for documents
-- Uses FTS for text terms and JSONB queries for organization filtering
-- Leverages the existing GIN indexes on entities and text search vector

-- Function to perform natural language search with FTS and organization filtering
CREATE OR REPLACE FUNCTION natural_language_search_fts(
    search_terms TEXT[],           -- Array of text terms to search
    category_filter TEXT DEFAULT NULL,
    organization_filters TEXT[] DEFAULT NULL,
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
    combined_terms TEXT;
BEGIN
    -- Build tsquery from search terms
    -- Join terms with & for AND semantics, add :* for prefix matching
    IF array_length(search_terms, 1) > 0 THEN
        combined_terms := array_to_string(search_terms, ' ');
        tsquery_str := regexp_replace(
            trim(combined_terms),
            '\s+',
            ':* & ',
            'g'
        ) || ':*';
    ELSE
        tsquery_str := NULL;
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
            WHEN tsquery_str IS NOT NULL THEN
                ts_rank(
                    to_tsvector('english',
                        COALESCE(d.file_name, '') || ' ' ||
                        COALESCE(d.ai_summary, '') || ' ' ||
                        COALESCE(d.extracted_text, '')
                    ),
                    to_tsquery('english', tsquery_str)
                )
            ELSE 0.5  -- Default rank when no text search
        END AS rank
    FROM documents d
    WHERE
        -- Category filter (exact match)
        (category_filter IS NULL OR d.ai_category = category_filter)
        -- Text search using FTS when terms provided
        AND (
            tsquery_str IS NULL
            OR to_tsvector('english',
                COALESCE(d.file_name, '') || ' ' ||
                COALESCE(d.ai_summary, '') || ' ' ||
                COALESCE(d.extracted_text, '')
            ) @@ to_tsquery('english', tsquery_str)
        )
        -- Organization filter using JSONB containment
        -- Check if any of the filter orgs match entities.organizations array (case-insensitive)
        AND (
            organization_filters IS NULL
            OR array_length(organization_filters, 1) IS NULL
            OR EXISTS (
                SELECT 1
                FROM jsonb_array_elements_text(COALESCE(d.entities->'organizations', '[]'::jsonb)) AS org_elem
                WHERE EXISTS (
                    SELECT 1
                    FROM unnest(organization_filters) AS filter_org
                    WHERE LOWER(org_elem) LIKE '%' || LOWER(filter_org) || '%'
                )
            )
        )
    ORDER BY rank DESC, d.updated_at DESC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql STABLE;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION natural_language_search_fts(TEXT[], TEXT, TEXT[], INTEGER) TO anon, authenticated;

COMMENT ON FUNCTION natural_language_search_fts IS
'Natural language search on documents using FTS for text terms and JSONB queries for organizations.
Supports stemming, prefix matching, relevance ranking, and organization filtering.
Category filter is exact match, organization filter checks entities.organizations array.';
