import { NextRequest, NextResponse } from "next/server";
import { searchDocuments, naturalLanguageSearch } from "@/lib/supabase";
import {
  parseNaturalLanguageQuery,
  buildSearchDescription,
} from "@/lib/nlp-search";

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 100;

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = searchParams.get("q");
  const mode = searchParams.get("mode") || "natural"; // "natural" or "simple"
  const limitParam = searchParams.get("limit");
  const offsetParam = searchParams.get("offset");

  // Parse and validate limit/offset
  const limit = Math.min(
    Math.max(1, parseInt(limitParam || String(DEFAULT_LIMIT), 10) || DEFAULT_LIMIT),
    MAX_LIMIT
  );
  const offset = Math.max(0, parseInt(offsetParam || "0", 10) || 0);

  if (!query) {
    return NextResponse.json(
      { error: "Query parameter 'q' is required" },
      { status: 400 }
    );
  }

  // Use simple search for backward compatibility if requested
  if (mode === "simple") {
    const result = await searchDocuments(query, limit, offset);

    if (result.error) {
      return NextResponse.json({ error: result.error }, { status: 500 });
    }

    return NextResponse.json({
      query,
      mode: "simple",
      documents: result.documents,
      count: result.documents.length,
      limit,
      offset,
      hasMore: result.documents.length === limit,
    });
  }

  // Natural language search (default)
  const parsedQuery = parseNaturalLanguageQuery(query);
  const searchDescription = buildSearchDescription(parsedQuery);

  const result = await naturalLanguageSearch(parsedQuery, limit, offset);

  if (result.error) {
    return NextResponse.json({ error: result.error }, { status: 500 });
  }

  return NextResponse.json({
    query,
    mode: "natural",
    parsed: {
      category: parsedQuery.category,
      years: parsedQuery.years,
      organizations: parsedQuery.organizations,
      searchTerms: parsedQuery.searchTerms,
      isNaturalLanguage: parsedQuery.isNaturalLanguage,
    },
    searchDescription,
    documents: result.documents,
    count: result.documents.length,
    limit,
    offset,
    hasMore: result.documents.length === limit,
    enrichmentMatches: result.enrichmentMatches,
  });
}
