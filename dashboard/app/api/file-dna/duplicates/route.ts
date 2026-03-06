import { NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";

const ICLOUD_BASE =
  process.env.NEXT_PUBLIC_ICLOUD_BASE_PATH ||
  "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs";
const DNA_PATH = path.join(ICLOUD_BASE, ".organizer", "agent", "file_dna.json");

interface DNAEntry {
  file_path: string;
  sha256_hash: string;
}

/**
 * GET: Return duplicate groups (files with same SHA-256 hash).
 */
export async function GET() {
  try {
    let entries: DNAEntry[] = [];
    try {
      const data = await fs.readFile(DNA_PATH, "utf-8");
      const parsed = JSON.parse(data);
      entries = parsed.entries || [];
    } catch {
      return NextResponse.json({
        success: true,
        groups: [],
        totalDuplicates: 0,
        wastedBytes: 0,
      });
    }

    const hashToPaths: Record<string, string[]> = {};
    for (const e of entries) {
      if (!e.sha256_hash) continue;
      if (!hashToPaths[e.sha256_hash]) hashToPaths[e.sha256_hash] = [];
      hashToPaths[e.sha256_hash].push(e.file_path);
    }

    const groups: { hash: string; files: string[]; count: number }[] = [];
    let wastedBytes = 0;

    for (const [h, paths] of Object.entries(hashToPaths)) {
      if (paths.length < 2) continue;
      const dupes = paths.slice(1);
      let bytes = 0;
      try {
        for (const p of dupes) {
          const stat = await fs.stat(p);
          bytes += stat.size;
        }
      } catch {
        // ignore
      }
      wastedBytes += bytes;
      groups.push({
        hash: h,
        files: paths,
        count: paths.length,
      });
    }

    return NextResponse.json({
      success: true,
      groups,
      totalDuplicates: groups.reduce((s, g) => s + g.count - 1, 0),
      wastedBytes,
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        message: "Failed to get duplicates",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
