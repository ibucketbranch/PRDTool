import { NextRequest, NextResponse } from "next/server";
import { searchDocuments, naturalLanguageSearch } from "@/lib/supabase";
import {
  parseNaturalLanguageQuery,
  buildSearchDescription,
} from "@/lib/nlp-search";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = searchParams.get("q");
  const mode = searchParams.get("mode") || "natural"; // "natural" or "simple"

  if (!query) {
    return NextResponse.json(
      { error: "Query parameter 'q' is required" },
      { status: 400 }
    );
  }

  // Use simple search for backward compatibility if requested
  if (mode === "simple") {
    const result = await searchDocuments(query);

    if (result.error) {
      return NextResponse.json({ error: result.error }, { status: 500 });
    }

    return NextResponse.json({
      query,
      mode: "simple",
      documents: result.documents,
      count: result.documents.length,
    });
  }

  // Natural language search (default)
  const parsedQuery = parseNaturalLanguageQuery(query);
  const searchDescription = buildSearchDescription(parsedQuery);

  const result = await naturalLanguageSearch(parsedQuery);

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
  });
}
