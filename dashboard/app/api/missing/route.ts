import { NextRequest, NextResponse } from "next/server";
import path from "path";
import {
  getMissingFiles,
  getOriginalLocation,
  updateDocumentPath,
  removeDocumentFromDatabase,
  markDocumentInaccessible,
  type MissingFilesResult,
} from "@/lib/supabase";
import { verifyFileAccessible as verifyFileAccessibleFn } from "@/lib/file-system-utils";

/**
 * Check if a file exists and is accessible
 * Uses integrated verifyFileAccessible from file-system-utils
 * (mirrors organizer/post_verification.py verify_file_accessible)
 */
function verifyFileAccessible(filePath: string): boolean {
  const result = verifyFileAccessibleFn(filePath);
  return result.exists && result.accessible;
}

export interface MissingFilesResponse extends MissingFilesResult {
  verifiedMissing: number;
  stillAccessible: number;
}

/**
 * GET /api/missing
 * Find files in database with missing paths (files that no longer exist on disk)
 *
 * Query parameters:
 * - verifyFilesystem: "true" | "false" (default: "true")
 *   If true, checks filesystem to verify if files are actually missing
 * - onlyMissing: "true" | "false" (default: "false")
 *   If true, only returns files that are verified missing on filesystem
 */
export async function GET(
  request: NextRequest
): Promise<NextResponse<MissingFilesResponse>> {
  const searchParams = request.nextUrl.searchParams;

  const verifyFilesystem = searchParams.get("verifyFilesystem") !== "false";
  const onlyMissing = searchParams.get("onlyMissing") === "true";

  // Get all documents from database
  const result = await getMissingFiles();

  if (result.error) {
    return NextResponse.json(
      {
        missingFiles: [],
        totalMissingFiles: 0,
        totalDocuments: 0,
        verifiedMissing: 0,
        stillAccessible: 0,
        error: result.error,
      },
      { status: 500 }
    );
  }

  let missingFiles = result.missingFiles;
  let verifiedMissing = 0;
  let stillAccessible = 0;

  // Verify filesystem status if requested
  if (verifyFilesystem) {
    missingFiles = missingFiles.map((file) => {
      const accessible = verifyFileAccessible(file.currentPath);

      if (accessible) {
        stillAccessible++;
        return { ...file, isAccessible: true };
      } else {
        verifiedMissing++;
        return { ...file, isAccessible: false };
      }
    });

    // Filter to only missing files if requested
    if (onlyMissing) {
      missingFiles = missingFiles.filter((file) => !file.isAccessible);
    }
  }

  return NextResponse.json({
    missingFiles,
    totalMissingFiles: verifyFilesystem ? verifiedMissing : result.totalMissingFiles,
    totalDocuments: result.totalDocuments,
    verifiedMissing,
    stillAccessible,
  });
}

export interface GetOriginalRequest {
  documentId: string;
}

export interface GetOriginalResponse {
  documentId: string;
  originalPath: string | null;
  locationHistory: {
    path: string;
    locationType: string;
    createdAt: string;
    isAccessible: boolean;
  }[];
  error?: string;
}

export interface UpdatePathRequest {
  documentId: string;
  newPath: string;
  addToHistory?: boolean;
}

export interface UpdatePathResponse {
  success: boolean;
  documentId: string;
  newPath: string;
  error?: string;
}

export interface RemoveDocumentRequest {
  documentId: string;
}

export interface RemoveDocumentResponse {
  success: boolean;
  documentId: string;
  error?: string;
}

/**
 * POST /api/missing
 * Handle various operations for missing files
 *
 * Request body:
 * - action: "get-original" | "update-path" | "remove" | "mark-inaccessible"
 * - documentId: string (required for all actions)
 * - newPath: string (required for update-path)
 * - addToHistory: boolean (optional for update-path, default: true)
 */
export async function POST(
  request: NextRequest
): Promise<NextResponse<GetOriginalResponse | UpdatePathResponse | RemoveDocumentResponse>> {
  try {
    const body = await request.json();
    const { action, documentId, newPath, addToHistory = true } = body;

    // Validate action
    if (!action || typeof action !== "string") {
      return NextResponse.json(
        {
          success: false,
          documentId: "",
          error: "Action is required (get-original, update-path, remove, mark-inaccessible)",
        },
        { status: 400 }
      );
    }

    // Validate documentId
    if (!documentId || typeof documentId !== "string") {
      return NextResponse.json(
        {
          success: false,
          documentId: "",
          error: "Document ID is required",
        },
        { status: 400 }
      );
    }

    switch (action) {
      case "get-original": {
        const result = await getOriginalLocation(documentId);

        if (result.error) {
          return NextResponse.json(
            {
              documentId,
              originalPath: null,
              locationHistory: [],
              error: result.error,
            },
            { status: 500 }
          );
        }

        return NextResponse.json({
          documentId,
          originalPath: result.originalPath,
          locationHistory: result.locationHistory,
        });
      }

      case "update-path": {
        // Validate newPath
        if (!newPath || typeof newPath !== "string") {
          return NextResponse.json(
            {
              success: false,
              documentId,
              newPath: "",
              error: "New path is required for update-path action",
            },
            { status: 400 }
          );
        }

        // Normalize and validate path
        const normalizedPath = path.normalize(newPath);

        if (!path.isAbsolute(normalizedPath)) {
          return NextResponse.json(
            {
              success: false,
              documentId,
              newPath: normalizedPath,
              error: "Only absolute paths are allowed",
            },
            { status: 400 }
          );
        }

        const result = await updateDocumentPath(documentId, normalizedPath, addToHistory);

        if (result.error) {
          return NextResponse.json(
            {
              success: false,
              documentId,
              newPath: normalizedPath,
              error: result.error,
            },
            { status: 500 }
          );
        }

        return NextResponse.json({
          success: true,
          documentId,
          newPath: normalizedPath,
        });
      }

      case "remove": {
        const result = await removeDocumentFromDatabase(documentId);

        if (result.error) {
          return NextResponse.json(
            {
              success: false,
              documentId,
              error: result.error,
            },
            { status: 500 }
          );
        }

        return NextResponse.json({
          success: true,
          documentId,
        });
      }

      case "mark-inaccessible": {
        const result = await markDocumentInaccessible(documentId);

        if (result.error) {
          return NextResponse.json(
            {
              success: false,
              documentId,
              error: result.error,
            },
            { status: 500 }
          );
        }

        return NextResponse.json({
          success: true,
          documentId,
        });
      }

      default:
        return NextResponse.json(
          {
            success: false,
            documentId,
            error: `Unknown action: ${action}. Valid actions are: get-original, update-path, remove, mark-inaccessible`,
          },
          { status: 400 }
        );
    }
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error occurred";

    // Check if it's a JSON parse error
    if (errorMessage.includes("JSON")) {
      return NextResponse.json(
        {
          success: false,
          documentId: "",
          error: "Invalid JSON in request body",
        },
        { status: 400 }
      );
    }

    return NextResponse.json(
      {
        success: false,
        documentId: "",
        error: errorMessage,
      },
      { status: 500 }
    );
  }
}
