import { NextRequest, NextResponse } from "next/server";
import { statSync, openSync, readSync, closeSync } from "fs";
import path from "path";
import { createHash } from "crypto";
import {
  suggestLocationForFileEnhanced,
  getSupabaseClient,
  type EnhancedLocationSuggestion,
} from "@/lib/supabase";
import {
  verifyFileAccessible,
  isProcessableExtension,
  getFileTypeCategory,
  type FileVerificationResult,
} from "@/lib/file-system-utils";

/**
 * Analyzed file information including AI-suggested category and location
 */
export interface AnalyzedFileInfo {
  filePath: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  fileTypeCategory: string;
  modifiedTime: string;
  isProcessable: boolean;
  verification: FileVerificationResult;
  suggestion: EnhancedLocationSuggestion;
  contentHash?: string;
  addedToDatabase?: boolean;
  documentId?: string;
  error?: string;
}

/**
 * Request body for analyze endpoint
 */
export interface AnalyzeOrphanedRequest {
  filePath: string;
  basePath?: string;
  addToDatabase?: boolean;
  computeHash?: boolean;
}

/**
 * Response for analyze endpoint
 */
export interface AnalyzeOrphanedResponse {
  analysis: AnalyzedFileInfo | null;
  error?: string;
}

/**
 * Compute SHA-256 hash of file content
 */
function computeFileHash(filePath: string, maxBytes: number = 10 * 1024 * 1024): string | null {
  try {
    const stats = statSync(filePath);
    const size = Math.min(stats.size, maxBytes);

    // Read file content (limited to maxBytes for large files)
    const fd = openSync(filePath, "r");
    const buffer = Buffer.alloc(size);
    readSync(fd, buffer, 0, size, 0);
    closeSync(fd);

    const hash = createHash("sha256");
    hash.update(buffer);
    return hash.digest("hex");
  } catch {
    return null;
  }
}

/**
 * POST /api/orphaned/analyze
 * Analyze an orphaned file - get suggestions, optionally add to database
 *
 * This endpoint integrates with the Python organizer patterns:
 * - Uses verify_file_accessible() pattern
 * - Uses DocumentProcessor-like analysis for file metadata
 * - Suggests location using enhanced logic (database history, similar files, filename patterns)
 *
 * Request body:
 * - filePath: string (required) - absolute path to the file
 * - basePath: string (optional) - base path for suggested location
 * - addToDatabase: boolean (optional) - if true, adds file to database
 * - computeHash: boolean (optional) - if true, computes SHA-256 hash
 */
export async function POST(
  request: NextRequest
): Promise<NextResponse<AnalyzeOrphanedResponse>> {
  try {
    const body = await request.json();
    const { filePath, basePath, addToDatabase = false, computeHash = false } =
      body as AnalyzeOrphanedRequest;

    // Validate file path
    if (!filePath || typeof filePath !== "string") {
      return NextResponse.json(
        {
          analysis: null,
          error: "File path is required",
        },
        { status: 400 }
      );
    }

    // Normalize path
    const normalizedPath = path.normalize(filePath);

    if (!path.isAbsolute(normalizedPath)) {
      return NextResponse.json(
        {
          analysis: null,
          error: "Only absolute paths are allowed",
        },
        { status: 400 }
      );
    }

    // Verify file exists and is accessible using integrated pattern
    const verification = verifyFileAccessible(normalizedPath);

    if (!verification.exists || !verification.accessible) {
      return NextResponse.json(
        {
          analysis: null,
          error: `File not accessible: ${verification.error}`,
        },
        { status: 404 }
      );
    }

    // Get file metadata
    const stats = statSync(normalizedPath);
    const fileName = path.basename(normalizedPath);
    const extension = path.extname(fileName).toLowerCase();

    // Get enhanced location suggestion
    const suggestion = await suggestLocationForFileEnhanced(
      normalizedPath,
      basePath || ""
    );

    // Build analysis result
    const analysis: AnalyzedFileInfo = {
      filePath: normalizedPath,
      fileName,
      fileSize: stats.size,
      fileType: extension || "unknown",
      fileTypeCategory: getFileTypeCategory(extension),
      modifiedTime: stats.mtime.toISOString(),
      isProcessable: isProcessableExtension(extension),
      verification,
      suggestion,
    };

    // Compute hash if requested
    if (computeHash) {
      const hash = computeFileHash(normalizedPath);
      if (hash) {
        analysis.contentHash = hash;
      }
    }

    // Add to database if requested
    if (addToDatabase) {
      try {
        const supabase = getSupabaseClient();

        // Check if file already exists in database
        const { data: existing } = await supabase
          .from("documents")
          .select("id")
          .eq("current_path", normalizedPath)
          .limit(1);

        if (existing && existing.length > 0) {
          // File already in database
          analysis.addedToDatabase = false;
          analysis.documentId = existing[0].id;
        } else {
          // Insert new document
          // Note: AI analysis (ai_category, ai_summary, entities) would need
          // integration with a document processor service in production.
          // For now, we create a basic entry that can be enhanced later.
          const { data: inserted, error: insertError } = await supabase
            .from("documents")
            .insert({
              file_name: fileName,
              current_path: normalizedPath,
              ai_category: suggestion.detectedCategory,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            })
            .select("id")
            .single();

          if (insertError) {
            analysis.error = `Failed to add to database: ${insertError.message}`;
            analysis.addedToDatabase = false;
          } else if (inserted) {
            analysis.addedToDatabase = true;
            analysis.documentId = inserted.id;

            // Also add to document_locations
            await supabase.from("document_locations").insert({
              document_id: inserted.id,
              path: normalizedPath,
              location_type: "primary",
              is_accessible: true,
              created_at: new Date().toISOString(),
            });
          }
        }
      } catch (err) {
        analysis.error =
          err instanceof Error ? err.message : "Failed to add to database";
        analysis.addedToDatabase = false;
      }
    }

    return NextResponse.json({ analysis });
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error occurred";

    // Check if it's a JSON parse error
    if (errorMessage.includes("JSON")) {
      return NextResponse.json(
        {
          analysis: null,
          error: "Invalid JSON in request body",
        },
        { status: 400 }
      );
    }

    return NextResponse.json(
      {
        analysis: null,
        error: errorMessage,
      },
      { status: 500 }
    );
  }
}
