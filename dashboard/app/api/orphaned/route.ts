import { NextRequest, NextResponse } from "next/server";
import { existsSync } from "fs";
import path from "path";
import {
  checkFileInDatabase,
  suggestLocationForFile,
  type OrphanedFileInfo,
  type OrphanedFilesResult,
} from "@/lib/supabase";
import {
  scanFolderForFiles,
  ALL_SCAN_EXTENSIONS,
} from "@/lib/file-system-utils";

export interface OrphanedFilesResponse extends OrphanedFilesResult {
  scannedFiles: number;
  filesInDatabase: number;
}

/**
 * GET /api/orphaned
 * Find files on disk not in database (orphaned files)
 *
 * Query parameters:
 * - directory: string (required) - absolute path to scan
 * - recursive: "true" | "false" (default: "true") - scan subdirectories
 * - maxDepth: number (default: 5) - maximum depth for recursive scan
 * - suggestLocations: "true" | "false" (default: "true") - suggest locations for orphaned files
 */
export async function GET(
  request: NextRequest
): Promise<NextResponse<OrphanedFilesResponse>> {
  const searchParams = request.nextUrl.searchParams;

  const directory = searchParams.get("directory");
  const recursive = searchParams.get("recursive") !== "false";
  const maxDepth = parseInt(searchParams.get("maxDepth") || "5", 10);
  const suggestLocations = searchParams.get("suggestLocations") !== "false";

  // Validate directory parameter
  if (!directory) {
    return NextResponse.json(
      {
        orphanedFiles: [],
        totalOrphanedFiles: 0,
        scannedDirectory: "",
        scannedFiles: 0,
        filesInDatabase: 0,
        error: "Directory parameter is required",
      },
      { status: 400 }
    );
  }

  // Normalize and validate path
  const normalizedPath = path.normalize(directory);

  if (!path.isAbsolute(normalizedPath)) {
    return NextResponse.json(
      {
        orphanedFiles: [],
        totalOrphanedFiles: 0,
        scannedDirectory: normalizedPath,
        scannedFiles: 0,
        filesInDatabase: 0,
        error: "Only absolute paths are allowed",
      },
      { status: 400 }
    );
  }

  // Check if directory exists
  if (!existsSync(normalizedPath)) {
    return NextResponse.json(
      {
        orphanedFiles: [],
        totalOrphanedFiles: 0,
        scannedDirectory: normalizedPath,
        scannedFiles: 0,
        filesInDatabase: 0,
        error: "Directory does not exist",
      },
      { status: 404 }
    );
  }

  try {
    // Scan directory for files
    // Use integrated scanFolderForFiles function (mirrors organizer/content_analyzer.py)
    const scannedFiles = scanFolderForFiles(normalizedPath, {
      extensions: ALL_SCAN_EXTENSIONS,
      recursive,
      maxDepth,
      includeHidden: false,
    });

    let filesInDatabase = 0;
    const orphanedFiles: OrphanedFileInfo[] = [];

    // Check each file against the database
    for (const file of scannedFiles) {
      const dbCheck = await checkFileInDatabase(file.path);

      if (dbCheck.error) {
        // Skip files with database errors, but continue scanning
        continue;
      }

      if (dbCheck.exists) {
        filesInDatabase++;
        file.inDatabase = true;
      } else {
        // File is orphaned - not in database
        let suggestedLocation: string | null = null;
        let suggestedReason: string | null = null;
        let confidence = 0;

        if (suggestLocations) {
          const suggestion = suggestLocationForFile(file.path, normalizedPath);
          suggestedLocation = suggestion.suggestedPath;
          suggestedReason = suggestion.reason;
          confidence = suggestion.confidence;
        }

        orphanedFiles.push({
          filePath: file.path,
          fileName: file.filename,
          fileSize: file.sizeBytes,
          lastModified: file.modifiedTime,
          fileType: file.extension || "unknown",
          suggestedLocation,
          suggestedReason,
          confidence,
        });
      }
    }

    return NextResponse.json({
      orphanedFiles,
      totalOrphanedFiles: orphanedFiles.length,
      scannedDirectory: normalizedPath,
      scannedFiles: scannedFiles.length,
      filesInDatabase,
    });
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error occurred";

    return NextResponse.json(
      {
        orphanedFiles: [],
        totalOrphanedFiles: 0,
        scannedDirectory: normalizedPath,
        scannedFiles: 0,
        filesInDatabase: 0,
        error: errorMessage,
      },
      { status: 500 }
    );
  }
}

export interface SuggestLocationRequest {
  filePath: string;
  basePath?: string;
}

export interface SuggestLocationResponse {
  filePath: string;
  suggestedPath: string;
  reason: string;
  confidence: number;
  matchType: string;
  error?: string;
}

/**
 * POST /api/orphaned
 * Suggest a location for an orphaned file
 *
 * Request body:
 * - filePath: string (required) - path to the file
 * - basePath: string (optional) - base path for suggested location
 */
export async function POST(
  request: NextRequest
): Promise<NextResponse<SuggestLocationResponse>> {
  try {
    const body = await request.json();
    const { filePath, basePath } = body as SuggestLocationRequest;

    // Validate file path
    if (!filePath || typeof filePath !== "string") {
      return NextResponse.json(
        {
          filePath: "",
          suggestedPath: "",
          reason: "",
          confidence: 0,
          matchType: "",
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
          filePath: normalizedPath,
          suggestedPath: "",
          reason: "",
          confidence: 0,
          matchType: "",
          error: "Only absolute paths are allowed",
        },
        { status: 400 }
      );
    }

    // Get suggestion
    const suggestion = suggestLocationForFile(normalizedPath, basePath || "");

    return NextResponse.json({
      filePath: normalizedPath,
      suggestedPath: suggestion.suggestedPath,
      reason: suggestion.reason,
      confidence: suggestion.confidence,
      matchType: suggestion.matchType,
    });
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error occurred";

    // Check if it's a JSON parse error
    if (errorMessage.includes("JSON")) {
      return NextResponse.json(
        {
          filePath: "",
          suggestedPath: "",
          reason: "",
          confidence: 0,
          matchType: "",
          error: "Invalid JSON in request body",
        },
        { status: 400 }
      );
    }

    return NextResponse.json(
      {
        filePath: "",
        suggestedPath: "",
        reason: "",
        confidence: 0,
        matchType: "",
        error: errorMessage,
      },
      { status: 500 }
    );
  }
}
