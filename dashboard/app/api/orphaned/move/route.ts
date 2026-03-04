import { NextRequest, NextResponse } from "next/server";
import { existsSync, mkdirSync, renameSync, copyFileSync, unlinkSync } from "fs";
import path from "path";
import {
  verifyFileAccessible,
  type FileVerificationResult,
} from "@/lib/file-system-utils";
import { getSupabaseClient, updateDocumentPath } from "@/lib/supabase";

/**
 * Request body for move endpoint
 */
export interface MoveOrphanedRequest {
  sourcePath: string;
  destinationPath: string;
  createDirectory?: boolean;
  updateDatabase?: boolean;
  documentId?: string;
}

/**
 * Response for move endpoint
 */
export interface MoveOrphanedResponse {
  success: boolean;
  sourcePath: string;
  destinationPath: string;
  sourceVerification?: FileVerificationResult;
  destinationVerification?: FileVerificationResult;
  databaseUpdated?: boolean;
  error?: string;
}

/**
 * POST /api/orphaned/move
 * Move an orphaned file to a suggested/specified location
 *
 * This endpoint integrates with the Python organizer patterns:
 * - Uses verify_file_accessible() pattern for pre/post verification
 * - Updates document_locations table for moved files
 *
 * Request body:
 * - sourcePath: string (required) - current file path
 * - destinationPath: string (required) - target file path
 * - createDirectory: boolean (optional, default: true) - create parent directory if needed
 * - updateDatabase: boolean (optional, default: true) - update database path if file is tracked
 * - documentId: string (optional) - document ID if known
 */
export async function POST(
  request: NextRequest
): Promise<NextResponse<MoveOrphanedResponse>> {
  try {
    const body = await request.json();
    const {
      sourcePath,
      destinationPath,
      createDirectory = true,
      updateDatabase = true,
      documentId,
    } = body as MoveOrphanedRequest;

    // Validate source path
    if (!sourcePath || typeof sourcePath !== "string") {
      return NextResponse.json(
        {
          success: false,
          sourcePath: "",
          destinationPath: "",
          error: "Source path is required",
        },
        { status: 400 }
      );
    }

    // Validate destination path
    if (!destinationPath || typeof destinationPath !== "string") {
      return NextResponse.json(
        {
          success: false,
          sourcePath,
          destinationPath: "",
          error: "Destination path is required",
        },
        { status: 400 }
      );
    }

    // Normalize paths
    const normalizedSource = path.normalize(sourcePath);
    const normalizedDest = path.normalize(destinationPath);

    if (!path.isAbsolute(normalizedSource)) {
      return NextResponse.json(
        {
          success: false,
          sourcePath: normalizedSource,
          destinationPath: normalizedDest,
          error: "Source path must be absolute",
        },
        { status: 400 }
      );
    }

    if (!path.isAbsolute(normalizedDest)) {
      return NextResponse.json(
        {
          success: false,
          sourcePath: normalizedSource,
          destinationPath: normalizedDest,
          error: "Destination path must be absolute",
        },
        { status: 400 }
      );
    }

    // Verify source file exists and is accessible
    const sourceVerification = verifyFileAccessible(normalizedSource);

    if (!sourceVerification.exists || !sourceVerification.accessible) {
      return NextResponse.json(
        {
          success: false,
          sourcePath: normalizedSource,
          destinationPath: normalizedDest,
          sourceVerification,
          error: `Source file not accessible: ${sourceVerification.error}`,
        },
        { status: 404 }
      );
    }

    // Check if destination already exists
    if (existsSync(normalizedDest)) {
      return NextResponse.json(
        {
          success: false,
          sourcePath: normalizedSource,
          destinationPath: normalizedDest,
          sourceVerification,
          error: "Destination file already exists",
        },
        { status: 409 }
      );
    }

    // Create destination directory if needed
    const destDir = path.dirname(normalizedDest);
    if (!existsSync(destDir)) {
      if (createDirectory) {
        try {
          mkdirSync(destDir, { recursive: true });
        } catch (err) {
          return NextResponse.json(
            {
              success: false,
              sourcePath: normalizedSource,
              destinationPath: normalizedDest,
              sourceVerification,
              error: `Failed to create destination directory: ${err instanceof Error ? err.message : "Unknown error"}`,
            },
            { status: 500 }
          );
        }
      } else {
        return NextResponse.json(
          {
            success: false,
            sourcePath: normalizedSource,
            destinationPath: normalizedDest,
            sourceVerification,
            error: "Destination directory does not exist",
          },
          { status: 400 }
        );
      }
    }

    // Move the file
    try {
      // Try rename first (faster, same filesystem)
      try {
        renameSync(normalizedSource, normalizedDest);
      } catch {
        // Fallback to copy + delete (cross-filesystem)
        copyFileSync(normalizedSource, normalizedDest);
        unlinkSync(normalizedSource);
      }
    } catch (err) {
      return NextResponse.json(
        {
          success: false,
          sourcePath: normalizedSource,
          destinationPath: normalizedDest,
          sourceVerification,
          error: `Failed to move file: ${err instanceof Error ? err.message : "Unknown error"}`,
        },
        { status: 500 }
      );
    }

    // Verify file at destination
    const destinationVerification = verifyFileAccessible(normalizedDest);

    if (!destinationVerification.exists || !destinationVerification.accessible) {
      return NextResponse.json(
        {
          success: false,
          sourcePath: normalizedSource,
          destinationPath: normalizedDest,
          sourceVerification,
          destinationVerification,
          error: "File move may have failed - destination not accessible",
        },
        { status: 500 }
      );
    }

    // Update database if requested and file is tracked
    let databaseUpdated = false;

    if (updateDatabase) {
      try {
        const supabase = getSupabaseClient();

        // Find document by path or ID
        let docId = documentId;

        if (!docId) {
          // Try to find by source path
          const { data: doc } = await supabase
            .from("documents")
            .select("id")
            .eq("current_path", normalizedSource)
            .limit(1);

          if (doc && doc.length > 0) {
            docId = doc[0].id;
          } else {
            // Also check document_locations
            const { data: loc } = await supabase
              .from("document_locations")
              .select("document_id")
              .eq("path", normalizedSource)
              .limit(1);

            if (loc && loc.length > 0) {
              docId = loc[0].document_id;
            }
          }
        }

        if (docId) {
          const result = await updateDocumentPath(docId, normalizedDest, true);
          databaseUpdated = result.success;
        }
      } catch {
        // Don't fail the move operation if database update fails
        databaseUpdated = false;
      }
    }

    return NextResponse.json({
      success: true,
      sourcePath: normalizedSource,
      destinationPath: normalizedDest,
      sourceVerification,
      destinationVerification,
      databaseUpdated,
    });
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error occurred";

    // Check if it's a JSON parse error
    if (errorMessage.includes("JSON")) {
      return NextResponse.json(
        {
          success: false,
          sourcePath: "",
          destinationPath: "",
          error: "Invalid JSON in request body",
        },
        { status: 400 }
      );
    }

    return NextResponse.json(
      {
        success: false,
        sourcePath: "",
        destinationPath: "",
        error: errorMessage,
      },
      { status: 500 }
    );
  }
}
