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
 * GET: Return last N routing records from history.
 * Query param: limit (default 50)
 */
export async function GET(request: NextRequest) {
  try {
    const limit = Math.min(
      parseInt(request.nextUrl.searchParams.get("limit") || "50", 10),
      200
    );

    let records: unknown[] = [];
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

    const recent = (records as { filename: string; destination_bin: string; routed_at: string; confidence: number; status: string }[])
      .slice(-limit)
      .reverse();

    return NextResponse.json({
      success: true,
      history: recent,
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
