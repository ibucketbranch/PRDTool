import { NextRequest, NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";

const ICLOUD_BASE =
  process.env.NEXT_PUBLIC_ICLOUD_BASE_PATH ||
  "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs";
const ENRICHMENT_CACHE_PATH = path.join(
  ICLOUD_BASE,
  ".organizer",
  "agent",
  "enrichment_cache.json"
);

interface FileEnrichment {
  document_type: string;
  date_references: string[];
  people: string[];
  organizations: string[];
  key_topics: string[];
  summary: string;
  suggested_tags: string[];
  confidence: number;
  model_used: string;
  used_keyword_fallback: boolean;
  enriched_at: string;
  duration_ms: number;
}

interface EnrichmentCacheEntry {
  file_hash: string;
  file_path: string;
  enrichment: FileEnrichment;
  cached_at: string;
}

interface EnrichmentCache {
  version: string;
  updated_at: string;
  entry_count: number;
  entries: EnrichmentCacheEntry[];
}

/**
 * GET: Get enrichment data.
 * Query params:
 *   - hash: Get enrichment by file hash
 *   - path: Get enrichment by file path
 *   - stats: If "true", return cache statistics only
 *
 * Returns enrichment data for a specific file, or cache stats.
 */
export async function GET(request: NextRequest) {
  try {
    const hashParam = request.nextUrl.searchParams.get("hash");
    const pathParam = request.nextUrl.searchParams.get("path");
    const statsParam = request.nextUrl.searchParams.get("stats");

    let cache: EnrichmentCache | null = null;
    try {
      const data = await fs.readFile(ENRICHMENT_CACHE_PATH, "utf-8");
      cache = JSON.parse(data) as EnrichmentCache;
    } catch {
      return NextResponse.json({
        success: true,
        enrichment: null,
        message: "Enrichment cache not found or empty",
      });
    }

    // Return stats if requested
    if (statsParam === "true") {
      const entries = cache.entries || [];

      // Calculate stats
      const llmEnriched = entries.filter(
        (e) => !e.enrichment.used_keyword_fallback
      ).length;
      const keywordFallback = entries.filter(
        (e) => e.enrichment.used_keyword_fallback
      ).length;
      const avgConfidence =
        entries.length > 0
          ? entries.reduce((sum, e) => sum + e.enrichment.confidence, 0) /
            entries.length
          : 0;

      // Count unique document types
      const docTypes = new Map<string, number>();
      for (const entry of entries) {
        const type = entry.enrichment.document_type || "unknown";
        docTypes.set(type, (docTypes.get(type) || 0) + 1);
      }

      // Count unique organizations
      const orgs = new Map<string, number>();
      for (const entry of entries) {
        for (const org of entry.enrichment.organizations) {
          orgs.set(org, (orgs.get(org) || 0) + 1);
        }
      }

      return NextResponse.json({
        success: true,
        stats: {
          total_entries: entries.length,
          llm_enriched: llmEnriched,
          keyword_fallback: keywordFallback,
          average_confidence: Math.round(avgConfidence * 100) / 100,
          updated_at: cache.updated_at,
          version: cache.version,
          document_types: Object.fromEntries(
            [...docTypes.entries()].sort((a, b) => b[1] - a[1]).slice(0, 20)
          ),
          top_organizations: Object.fromEntries(
            [...orgs.entries()].sort((a, b) => b[1] - a[1]).slice(0, 20)
          ),
        },
      });
    }

    // Get enrichment by hash
    if (hashParam) {
      const entry = (cache.entries || []).find(
        (e) => e.file_hash === hashParam
      );
      if (entry) {
        return NextResponse.json({
          success: true,
          enrichment: {
            file_hash: entry.file_hash,
            file_path: entry.file_path,
            filename: path.basename(entry.file_path),
            ...entry.enrichment,
            cached_at: entry.cached_at,
          },
        });
      }
      return NextResponse.json({
        success: true,
        enrichment: null,
        message: "No enrichment found for hash",
      });
    }

    // Get enrichment by path
    if (pathParam) {
      const entry = (cache.entries || []).find(
        (e) => e.file_path === pathParam
      );
      if (entry) {
        return NextResponse.json({
          success: true,
          enrichment: {
            file_hash: entry.file_hash,
            file_path: entry.file_path,
            filename: path.basename(entry.file_path),
            ...entry.enrichment,
            cached_at: entry.cached_at,
          },
        });
      }
      return NextResponse.json({
        success: true,
        enrichment: null,
        message: "No enrichment found for path",
      });
    }

    // No specific query - return summary
    return NextResponse.json({
      success: true,
      message: "Use ?hash=<hash>, ?path=<path>, or ?stats=true to query",
      entry_count: (cache.entries || []).length,
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        message: "Failed to read enrichment cache",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
