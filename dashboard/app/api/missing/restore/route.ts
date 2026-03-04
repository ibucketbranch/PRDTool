import { NextRequest, NextResponse } from "next/server";
import { existsSync, mkdirSync, renameSync, copyFileSync, unlinkSync } from "fs";
import path from "path";
import {
  getOriginalLocation,
  updateDocumentPath,
  getSupabaseClient,
} from "@/lib/supabase";
import {
  verifyFileAccessible,
  type FileVerificationResult,
} from "@/lib/file-system-utils";

/**
 * Request body for restore endpoint
 */
export interface RestoreMissingRequest {
  documentId: string;
  customPath?: string;
  createDirectory?: boolean;
}

/**
 * Response for restore endpoint
 */
export interface RestoreMissingResponse {
  success: boolean;
  documentId: string;
  sourcePath: string;
  restoredPath: string;
  usedOriginalPath: boolean;
  sourceVerification?: FileVerificationResult;
  destinationVerification?: FileVerificationResult;
  databaseUpdated: boolean;
  error?: string;
}

/**
 * POST /api/missing/restore
 * Restore a missing file to its original location or a custom path
 *
 * This endpoint integrates with the Python organizer patterns:
 * - Uses verify_file_accessible() pattern for pre/post verification
 * - Queries document_locations table for original path history
 * - Updates document path after successful restore
 *
 * Request body:
 * - documentId: string (required) - document ID to restore
 * - customPath: string (optional) - use this path instead of original
 * - createDirectory: boolean (optional, default: true) - create parent directory if needed
 */
export async function POST(
  request: NextRequest
): Promise<NextResponse<RestoreMissingResponse>> {
  try {
    const body = await request.json();
    const { documentId, customPath, createDirectory = true } =
      body as RestoreMissingRequest;

    // Validate document ID
    if (!documentId || typeof documentId !== "string") {
      return NextResponse.json(
        {
          success: false,
          documentId: "",
          sourcePath: "",
          restoredPath: "",
          usedOriginalPath: false,
          databaseUpdated: false,
          error: "Document ID is required",
        },
        { status: 400 }
      );
    }

    // Get document info
    const supabase = getSupabaseClient();
    const { data: document, error: docError } = await supabase
      .from("documents")
      .select("id, file_name, current_path")
      .eq("id", documentId)
      .single();

    if (docError || !document) {
      return NextResponse.json(
        {
          success: false,
          documentId,
          sourcePath: "",
          restoredPath: "",
          usedOriginalPath: false,
          databaseUpdated: false,
          error: `Document not found: ${docError?.message || "Unknown error"}`,
        },
        { status: 404 }
      );
    }

    const currentPath = document.current_path;

    // Determine target path
    let targetPath: string;
    let usedOriginalPath = false;

    if (customPath) {
      // Use custom path
      targetPath = path.normalize(customPath);

      if (!path.isAbsolute(targetPath)) {
        return NextResponse.json(
          {
            success: false,
            documentId,
            sourcePath: currentPath,
            restoredPath: "",
            usedOriginalPath: false,
            databaseUpdated: false,
            error: "Custom path must be absolute",
          },
          { status: 400 }
        );
      }
    } else {
      // Get original location from document_locations
      const originalResult = await getOriginalLocation(documentId);

      if (originalResult.error) {
        return NextResponse.json(
          {
            success: false,
            documentId,
            sourcePath: currentPath,
            restoredPath: "",
            usedOriginalPath: false,
            databaseUpdated: false,
            error: `Failed to get original location: ${originalResult.error}`,
          },
          { status: 500 }
        );
      }

      if (!originalResult.originalPath) {
        return NextResponse.json(
          {
            success: false,
            documentId,
            sourcePath: currentPath,
            restoredPath: "",
            usedOriginalPath: false,
            databaseUpdated: false,
            error: "No original path found in location history",
          },
          { status: 404 }
        );
      }

      targetPath = originalResult.originalPath;
      usedOriginalPath = true;
    }

    // Verify source file exists (this is the "missing" file we're restoring from)
    // Note: For missing files, the current_path doesn't exist, but we need to find
    // where the file actually is. This endpoint assumes the file exists somewhere
    // that can be moved to the target location.
    const sourceVerification = verifyFileAccessible(currentPath);

    // If source doesn't exist at current_path, we can't restore it
    if (!sourceVerification.exists) {
      return NextResponse.json(
        {
          success: false,
          documentId,
          sourcePath: currentPath,
          restoredPath: targetPath,
          usedOriginalPath,
          sourceVerification,
          databaseUpdated: false,
          error: "Source file does not exist at recorded path - cannot restore",
        },
        { status: 404 }
      );
    }

    // Check if target already exists
    if (existsSync(targetPath) && targetPath !== currentPath) {
      return NextResponse.json(
        {
          success: false,
          documentId,
          sourcePath: currentPath,
          restoredPath: targetPath,
          usedOriginalPath,
          sourceVerification,
          databaseUpdated: false,
          error: "Target path already has a file",
        },
        { status: 409 }
      );
    }

    // If source and target are the same, just update verification status
    if (targetPath === currentPath) {
      // File is already at target - just verify and update database
      const destVerification = verifyFileAccessible(targetPath);

      if (destVerification.exists && destVerification.accessible) {
        // Update location accessibility in database
        await supabase
          .from("document_locations")
          .update({ is_accessible: true })
          .eq("document_id", documentId)
          .eq("path", targetPath);

        return NextResponse.json({
          success: true,
          documentId,
          sourcePath: currentPath,
          restoredPath: targetPath,
          usedOriginalPath,
          sourceVerification,
          destinationVerification: destVerification,
          databaseUpdated: true,
        });
      }
    }

    // Create target directory if needed
    const targetDir = path.dirname(targetPath);
    if (!existsSync(targetDir)) {
      if (createDirectory) {
        try {
          mkdirSync(targetDir, { recursive: true });
        } catch (err) {
          return NextResponse.json(
            {
              success: false,
              documentId,
              sourcePath: currentPath,
              restoredPath: targetPath,
              usedOriginalPath,
              sourceVerification,
              databaseUpdated: false,
              error: `Failed to create target directory: ${err instanceof Error ? err.message : "Unknown error"}`,
            },
            { status: 500 }
          );
        }
      } else {
        return NextResponse.json(
          {
            success: false,
            documentId,
            sourcePath: currentPath,
            restoredPath: targetPath,
            usedOriginalPath,
            sourceVerification,
            databaseUpdated: false,
            error: "Target directory does not exist",
          },
          { status: 400 }
        );
      }
    }

    // Move the file
    try {
      // Try rename first (faster, same filesystem)
      try {
        renameSync(currentPath, targetPath);
      } catch {
        // Fallback to copy + delete (cross-filesystem)
        copyFileSync(currentPath, targetPath);
        unlinkSync(currentPath);
      }
    } catch (err) {
      return NextResponse.json(
        {
          success: false,
          documentId,
          sourcePath: currentPath,
          restoredPath: targetPath,
          usedOriginalPath,
          sourceVerification,
          databaseUpdated: false,
          error: `Failed to move file: ${err instanceof Error ? err.message : "Unknown error"}`,
        },
        { status: 500 }
      );
    }

    // Verify file at destination
    const destinationVerification = verifyFileAccessible(targetPath);

    if (!destinationVerification.exists || !destinationVerification.accessible) {
      return NextResponse.json(
        {
          success: false,
          documentId,
          sourcePath: currentPath,
          restoredPath: targetPath,
          usedOriginalPath,
          sourceVerification,
          destinationVerification,
          databaseUpdated: false,
          error: "File restore may have failed - destination not accessible",
        },
        { status: 500 }
      );
    }

    // Update database
    const updateResult = await updateDocumentPath(documentId, targetPath, true);

    return NextResponse.json({
      success: true,
      documentId,
      sourcePath: currentPath,
      restoredPath: targetPath,
      usedOriginalPath,
      sourceVerification,
      destinationVerification,
      databaseUpdated: updateResult.success,
    });
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error occurred";

    // Check if it's a JSON parse error
    if (errorMessage.includes("JSON")) {
      return NextResponse.json(
        {
          success: false,
          documentId: "",
          sourcePath: "",
          restoredPath: "",
          usedOriginalPath: false,
          databaseUpdated: false,
          error: "Invalid JSON in request body",
        },
        { status: 400 }
      );
    }

    return NextResponse.json(
      {
        success: false,
        documentId: "",
        sourcePath: "",
        restoredPath: "",
        usedOriginalPath: false,
        databaseUpdated: false,
        error: errorMessage,
      },
      { status: 500 }
    );
  }
}
