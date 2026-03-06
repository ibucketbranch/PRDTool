import { NextRequest, NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";

const ICLOUD_BASE =
  process.env.NEXT_PUBLIC_ICLOUD_BASE_PATH ||
  "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs";
const DNA_PATH = path.join(ICLOUD_BASE, ".organizer", "agent", "file_dna.json");

interface DNAEntry {
  file_path: string;
  sha256_hash: string;
  content_summary?: string;
  auto_tags?: string[];
  origin?: string;
  routed_to?: string;
}

/**
 * GET: Search file DNA by keyword.
 * Query params: search (keyword), hash (sha256)
 */
export async function GET(request: NextRequest) {
  try {
    const search = request.nextUrl.searchParams.get("search");
    const hashParam = request.nextUrl.searchParams.get("hash");

    let entries: DNAEntry[] = [];
    try {
      const data = await fs.readFile(DNA_PATH, "utf-8");
      const parsed = JSON.parse(data);
      entries = parsed.entries || [];
    } catch {
      return NextResponse.json({
        success: true,
        results: [],
        total: 0,
      });
    }

    if (hashParam) {
      entries = entries.filter((e) => e.sha256_hash === hashParam);
    } else if (search) {
      const q = search.toLowerCase();
      entries = entries.filter(
        (e) =>
          e.auto_tags?.some((t) => t.toLowerCase().includes(q)) ||
          e.content_summary?.toLowerCase().includes(q) ||
          path.basename(e.file_path).toLowerCase().includes(q)
      );
    }

    const results = entries.slice(0, 50).map((e) => ({
      filename: path.basename(e.file_path),
      path: e.file_path,
      tags: e.auto_tags || [],
      hash: e.sha256_hash,
    }));

    return NextResponse.json({
      success: true,
      results,
      total: entries.length,
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        message: "Failed to search file DNA",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
