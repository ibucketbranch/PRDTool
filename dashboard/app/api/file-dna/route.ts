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
  first_seen_at?: string;
  routed_to?: string;
  duplicate_of?: string;
  model_used?: string;
}

interface FileDNAResult {
  filename: string;
  path: string;
  tags: string[];
  hash: string;
  provenance: {
    origin: string;
    first_seen_at: string;
    routed_to: string;
    model_used: string;
  };
  related_files: string[];
  duplicate_status: {
    is_duplicate: boolean;
    duplicate_of: string | null;
    has_duplicates: boolean;
    duplicate_paths: string[];
  };
}

/**
 * GET: Search file DNA by keyword, hash, or tag.
 * Query params:
 *   - search: keyword to search in filename, tags, content (case-insensitive)
 *   - hash: exact SHA-256 hash match
 *   - tag: exact tag match (case-insensitive)
 *
 * Returns provenance, related files, and duplicate status for each result.
 */
export async function GET(request: NextRequest) {
  try {
    const search = request.nextUrl.searchParams.get("search");
    const hashParam = request.nextUrl.searchParams.get("hash");
    const tagParam = request.nextUrl.searchParams.get("tag");

    let allEntries: DNAEntry[] = [];
    try {
      const data = await fs.readFile(DNA_PATH, "utf-8");
      const parsed = JSON.parse(data);
      allEntries = parsed.entries || [];
    } catch {
      return NextResponse.json({
        success: true,
        results: [],
        total: 0,
      });
    }

    // Build hash-to-paths index for duplicate detection
    const hashToPaths: Map<string, string[]> = new Map();
    for (const e of allEntries) {
      if (e.sha256_hash) {
        const paths = hashToPaths.get(e.sha256_hash) || [];
        paths.push(e.file_path);
        hashToPaths.set(e.sha256_hash, paths);
      }
    }

    // Filter entries based on search params
    let filteredEntries = allEntries;

    if (hashParam) {
      filteredEntries = allEntries.filter((e) => e.sha256_hash === hashParam);
    } else if (tagParam) {
      const tagLower = tagParam.toLowerCase();
      filteredEntries = allEntries.filter((e) =>
        e.auto_tags?.some((t) => t.toLowerCase() === tagLower)
      );
    } else if (search) {
      const q = search.toLowerCase();
      filteredEntries = allEntries.filter(
        (e) =>
          e.auto_tags?.some((t) => t.toLowerCase().includes(q)) ||
          e.content_summary?.toLowerCase().includes(q) ||
          path.basename(e.file_path).toLowerCase().includes(q) ||
          e.file_path.toLowerCase().includes(q)
      );
    }

    // Build results with provenance, related files, and duplicate status
    const results: FileDNAResult[] = filteredEntries.slice(0, 50).map((e) => {
      // Find duplicate files (same hash, different paths)
      const duplicatePaths = (hashToPaths.get(e.sha256_hash) || []).filter(
        (p) => p !== e.file_path
      );
      const hasDuplicates = duplicatePaths.length > 0;

      // Find related files (files with overlapping tags)
      const relatedFiles: string[] = [];
      if (e.auto_tags && e.auto_tags.length > 0) {
        for (const other of allEntries) {
          if (other.file_path === e.file_path) continue;
          if (relatedFiles.length >= 5) break; // Limit related files

          // Check for tag overlap
          const tagOverlap = (other.auto_tags || []).filter((t) =>
            e.auto_tags!.some(
              (et) => et.toLowerCase() === t.toLowerCase()
            )
          );
          if (tagOverlap.length >= 2) {
            relatedFiles.push(other.file_path);
          }
        }
      }

      return {
        filename: path.basename(e.file_path),
        path: e.file_path,
        tags: e.auto_tags || [],
        hash: e.sha256_hash,
        provenance: {
          origin: e.origin || "",
          first_seen_at: e.first_seen_at || "",
          routed_to: e.routed_to || "",
          model_used: e.model_used || "",
        },
        related_files: relatedFiles,
        duplicate_status: {
          is_duplicate: !!e.duplicate_of,
          duplicate_of: e.duplicate_of || null,
          has_duplicates: hasDuplicates,
          duplicate_paths: duplicatePaths,
        },
      };
    });

    return NextResponse.json({
      success: true,
      results,
      total: filteredEntries.length,
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
