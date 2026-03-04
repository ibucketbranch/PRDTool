import { NextRequest, NextResponse } from "next/server";
import { getDocuments, DocumentListOptions } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;

  // Parse query parameters
  const category = searchParams.get("category") || undefined;
  const contextBin = searchParams.get("contextBin") || undefined;
  const search = searchParams.get("search") || undefined;

  const startYear = searchParams.get("startYear")
    ? parseInt(searchParams.get("startYear")!, 10)
    : undefined;
  const endYear = searchParams.get("endYear")
    ? parseInt(searchParams.get("endYear")!, 10)
    : undefined;

  const limit = searchParams.get("limit")
    ? parseInt(searchParams.get("limit")!, 10)
    : 20;
  const offset = searchParams.get("offset")
    ? parseInt(searchParams.get("offset")!, 10)
    : 0;

  const orderBy = searchParams.get("orderBy") || "created_at";
  const orderDirection =
    (searchParams.get("orderDirection") as "asc" | "desc") || "desc";

  // Validate year parameters
  if (startYear !== undefined && (isNaN(startYear) || startYear < 1900 || startYear > 2099)) {
    return NextResponse.json(
      { error: "Invalid startYear. Must be between 1900 and 2099." },
      { status: 400 }
    );
  }

  if (endYear !== undefined && (isNaN(endYear) || endYear < 1900 || endYear > 2099)) {
    return NextResponse.json(
      { error: "Invalid endYear. Must be between 1900 and 2099." },
      { status: 400 }
    );
  }

  if (startYear && endYear && startYear > endYear) {
    return NextResponse.json(
      { error: "startYear cannot be greater than endYear." },
      { status: 400 }
    );
  }

  const options: DocumentListOptions = {
    category,
    contextBin,
    startYear,
    endYear,
    search,
    limit,
    offset,
    orderBy,
    orderDirection,
  };

  const result = await getDocuments(options);

  if (result.error) {
    return NextResponse.json({ error: result.error }, { status: 500 });
  }

  return NextResponse.json({
    documents: result.documents,
    total: result.total,
    filteredTotal: result.filteredTotal,
    limit,
    offset,
  });
}
