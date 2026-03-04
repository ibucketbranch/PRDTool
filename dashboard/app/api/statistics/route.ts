import { NextRequest, NextResponse } from "next/server";
import { getStatistics, getCategoryStats, getContextBinCounts, testConnection } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  
  // Check if year range filtering is requested for categories
  const startYear = searchParams.get("startYear")
    ? parseInt(searchParams.get("startYear")!, 10)
    : undefined;
  const endYear = searchParams.get("endYear")
    ? parseInt(searchParams.get("endYear")!, 10)
    : undefined;

  // If year range is provided, return filtered categories and context bins
  if (startYear !== undefined || endYear !== undefined) {
    const [categoryResult, contextBinResult] = await Promise.all([
      getCategoryStats(startYear, endYear),
      getContextBinCounts(startYear, endYear),
    ]);
    
    if (categoryResult.error) {
      return NextResponse.json({ error: categoryResult.error }, { status: 500 });
    }
    if (contextBinResult.error) {
      return NextResponse.json({ error: contextBinResult.error }, { status: 500 });
    }
    
    return NextResponse.json({ 
      categories: categoryResult.categories,
      contextBins: contextBinResult.contextBins,
    });
  }

  // Otherwise, return full statistics
  // First test the connection
  const connectionTest = await testConnection();

  if (!connectionTest.connected) {
    return NextResponse.json(
      {
        error: connectionTest.error || "Failed to connect to database",
        connected: false,
      },
      { status: 500 }
    );
  }

  // Get all statistics (categories, date distribution, context bins)
  const stats = await getStatistics();

  if (stats.error) {
    return NextResponse.json({ error: stats.error }, { status: 500 });
  }

  return NextResponse.json({
    connected: true,
    documentCount: connectionTest.documentCount,
    categories: stats.categories,
    dateDistribution: stats.dateDistribution,
    contextBins: stats.contextBins,
    minYear: stats.minYear,
    maxYear: stats.maxYear,
  });
}
