import { NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";

const ICLOUD_BASE =
  process.env.NEXT_PUBLIC_ICLOUD_BASE_PATH ||
  "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs";
const DNA_PATH = path.join(ICLOUD_BASE, ".organizer", "agent", "file_dna.json");

/**
 * GET: Return file DNA stats (total tracked, duplicates, etc).
 */
export async function GET() {
  try {
    let entries: { sha256_hash?: string }[] = [];
    try {
      const data = await fs.readFile(DNA_PATH, "utf-8");
      const parsed = JSON.parse(data);
      entries = parsed.entries || [];
    } catch {
      return NextResponse.json({
        success: true,
        totalTracked: 0,
        duplicateGroups: 0,
        duplicateFiles: 0,
        wastedBytes: 0,
      });
    }

    const hashCounts: Record<string, number> = {};
    for (const e of entries) {
      if (e.sha256_hash) {
        hashCounts[e.sha256_hash] = (hashCounts[e.sha256_hash] || 0) + 1;
      }
    }

    let duplicateGroups = 0;
    let duplicateFiles = 0;
    for (const count of Object.values(hashCounts)) {
      if (count > 1) {
        duplicateGroups++;
        duplicateFiles += count - 1;
      }
    }

    return NextResponse.json({
      success: true,
      totalTracked: entries.length,
      duplicateGroups,
      duplicateFiles,
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        message: "Failed to get stats",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
