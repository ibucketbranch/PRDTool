import { NextRequest, NextResponse } from "next/server";
import path from "path";
import {
  assessFolderLocation,
  FolderAssessment,
  MovedFileInfo,
} from "@/lib/supabase";

export interface FolderAssessmentResponse {
  assessment: FolderAssessment | null;
  movedFiles: MovedFileInfo[];
  error?: string;
}

/**
 * POST /api/empty-folders/assess
 * Assess whether a folder was in the correct location
 *
 * Request body:
 * - folderPath: string (required) - absolute path to the folder to assess
 *
 * Response:
 * - assessment: FolderAssessment object with:
 *   - folderPath: Original folder path
 *   - folderName: Just the folder name
 *   - isCorrectLocation: Whether folder was in correct location
 *   - isDuplicate: Whether folder appears to be a duplicate
 *   - assessment: "correct" | "incorrect" | "duplicate" | "unknown"
 *   - confidence: 0.0 to 1.0
 *   - reasoning: Array of reasoning steps
 *   - suggestedAction: "restore" | "remove" | "keep" | "review"
 *   - movedFilesCategories: AI categories of moved files
 *   - dominantCategory: Most common category
 *   - categoryMatch: Whether folder name matches dominant category
 *   - folderHierarchyMatch: Whether folder matches hierarchy patterns
 *   - canonicalMatch: Whether folder is canonical
 *   - similarCanonicalFolder: Similar canonical folder if found
 * - movedFiles: Array of files that were moved from this folder
 * - error: Error message if assessment failed
 */
export async function POST(
  request: NextRequest
): Promise<NextResponse<FolderAssessmentResponse>> {
  try {
    const body = await request.json();
    const { folderPath } = body;

    // Validate folder path
    if (!folderPath || typeof folderPath !== "string") {
      return NextResponse.json(
        {
          assessment: null,
          movedFiles: [],
          error: "Folder path is required",
        },
        { status: 400 }
      );
    }

    // Normalize and validate path
    const normalizedPath = path.normalize(folderPath);

    if (!path.isAbsolute(normalizedPath)) {
      return NextResponse.json(
        {
          assessment: null,
          movedFiles: [],
          error: "Only absolute paths are allowed",
        },
        { status: 400 }
      );
    }

    // Perform assessment
    const result = await assessFolderLocation(normalizedPath);

    if (result.error) {
      return NextResponse.json(
        {
          assessment: result.assessment,
          movedFiles: result.movedFiles,
          error: result.error,
        },
        { status: 500 }
      );
    }

    return NextResponse.json({
      assessment: result.assessment,
      movedFiles: result.movedFiles,
    });
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error occurred";

    // Handle JSON parse errors
    if (errorMessage.includes("JSON")) {
      return NextResponse.json(
        {
          assessment: null,
          movedFiles: [],
          error: "Invalid JSON in request body",
        },
        { status: 400 }
      );
    }

    return NextResponse.json(
      {
        assessment: null,
        movedFiles: [],
        error: errorMessage,
      },
      { status: 500 }
    );
  }
}
