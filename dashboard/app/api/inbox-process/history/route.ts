import { NextRequest, NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";

const ICLOUD_BASE =
  process.env.NEXT_PUBLIC_ICLOUD_BASE_PATH ||
  "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs";
const HISTORY_PATH = path.join(
  ICLOUD_BASE,
  ".organizer",
  "agent",
  "routing_history.json"
);

/**
 * Routing record with explainability fields.
 */
interface RoutingRecord {
  filename: string;
  destination_bin: string;
  routed_at: string;
  confidence: number;
  status: string;
  matched_keywords?: string[];
  // Explainability fields (Phase 16.4)
  reason?: string;
  model_used?: string;
  used_keyword_fallback?: boolean;
}

/**
 * GET: Return last N routing records from history.
 * Query param: limit (default 50)
 *
 * Response includes explainability fields:
 * - reason: LLM's natural language explanation for the routing decision
 * - model_used: Name of the LLM model that made the decision
 * - used_keyword_fallback: Whether keyword-based routing was used instead of LLM
 */
export async function GET(request: NextRequest) {
  try {
    const limit = Math.min(
      parseInt(request.nextUrl.searchParams.get("limit") || "50", 10),
      200
    );

    let records: RoutingRecord[] = [];
    try {
      const data = await fs.readFile(HISTORY_PATH, "utf-8");
      const parsed = JSON.parse(data);
      records = parsed.records || [];
    } catch {
      return NextResponse.json({
        success: true,
        history: [],
        total: 0,
      });
    }

    // Get the most recent records and reverse to show newest first
    const recent = records.slice(-limit).reverse();

    // Transform to camelCase for frontend consistency
    const transformed = recent.map((r) => ({
      filename: r.filename,
      destinationBin: r.destination_bin,
      routedAt: r.routed_at,
      confidence: r.confidence,
      status: r.status,
      matchedKeywords: r.matched_keywords || [],
      // Explainability fields
      reason: r.reason || "",
      modelUsed: r.model_used || "",
      usedKeywordFallback: r.used_keyword_fallback ?? true, // Default to true for legacy records
    }));

    return NextResponse.json({
      success: true,
      history: transformed,
      total: records.length,
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        message: "Failed to load routing history",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
