import { NextRequest, NextResponse } from "next/server";
import { readdirSync, existsSync, statSync } from "fs";
import path from "path";
import {
  getEmptyFolders,
  getFolderHistory,
  EmptyFolderInfo,
} from "@/lib/supabase";

export interface EmptyFoldersResponse {
  emptyFolders: EmptyFolderInfo[];
  totalEmptyFolders: number;
  verifiedEmpty: number;
  notEmpty: number;
  notFound: number;
  error?: string;
}

/**
 * Check if a folder is empty on the filesystem
 * Returns: "empty" | "not_empty" | "not_found"
 */
function checkFolderStatus(
  folderPath: string
): "empty" | "not_empty" | "not_found" {
  try {
    if (!existsSync(folderPath)) {
      return "not_found";
    }

    const stats = statSync(folderPath);
    if (!stats.isDirectory()) {
      return "not_found";
    }

    const contents = readdirSync(folderPath);
    // Filter out hidden files like .DS_Store
    const visibleContents = contents.filter((item) => !item.startsWith("."));

    return visibleContents.length === 0 ? "empty" : "not_empty";
  } catch {
    return "not_found";
  }
}

/**
 * GET /api/empty-folders
 * Find empty folders after consolidation
 *
 * Query parameters:
 * - verifyFilesystem: "true" | "false" (default: "true")
 *   If true, checks filesystem to verify if folders are actually empty
 * - onlyEmpty: "true" | "false" (default: "false")
 *   If true, only returns folders that are verified empty on filesystem
 */
export async function GET(
  request: NextRequest
): Promise<NextResponse<EmptyFoldersResponse>> {
  const searchParams = request.nextUrl.searchParams;

  const verifyFilesystem = searchParams.get("verifyFilesystem") !== "false";
  const onlyEmpty = searchParams.get("onlyEmpty") === "true";

  // Get empty folders from database
  const result = await getEmptyFolders();

  if (result.error) {
    return NextResponse.json(
      {
        emptyFolders: [],
        totalEmptyFolders: 0,
        verifiedEmpty: 0,
        notEmpty: 0,
        notFound: 0,
        error: result.error,
      },
      { status: 500 }
    );
  }

  let emptyFolders = result.emptyFolders;
  let verifiedEmpty = 0;
  let notEmpty = 0;
  let notFound = 0;

  // Verify filesystem status if requested
  if (verifyFilesystem) {
    emptyFolders = emptyFolders.map((folder) => {
      const status = checkFolderStatus(folder.folderPath);

      if (status === "empty") {
        verifiedEmpty++;
        return { ...folder, isEmpty: true };
      } else if (status === "not_empty") {
        notEmpty++;
        return { ...folder, isEmpty: false };
      } else {
        notFound++;
        return { ...folder, isEmpty: false };
      }
    });

    // Filter to only empty folders if requested
    if (onlyEmpty) {
      emptyFolders = emptyFolders.filter((folder) => folder.isEmpty);
    }
  }

  return NextResponse.json({
    emptyFolders,
    totalEmptyFolders: emptyFolders.length,
    verifiedEmpty,
    notEmpty,
    notFound,
  });
}

export interface FolderHistoryResponse {
  folderPath: string;
  files: {
    documentId: string;
    fileName: string;
    originalPath: string;
    currentPath: string;
    movedAt: string;
  }[];
  originalFileCount: number;
  folderStatus: "empty" | "not_empty" | "not_found";
  error?: string;
}

/**
 * POST /api/empty-folders
 * Get history for a specific folder
 *
 * Request body:
 * - folderPath: string (required) - absolute path to the folder
 */
export async function POST(
  request: NextRequest
): Promise<NextResponse<FolderHistoryResponse>> {
  try {
    const body = await request.json();
    const { folderPath } = body;

    // Validate folder path
    if (!folderPath || typeof folderPath !== "string") {
      return NextResponse.json(
        {
          folderPath: "",
          files: [],
          originalFileCount: 0,
          folderStatus: "not_found",
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
          folderPath: normalizedPath,
          files: [],
          originalFileCount: 0,
          folderStatus: "not_found",
          error: "Only absolute paths are allowed",
        },
        { status: 400 }
      );
    }

    // Get folder history from database
    const result = await getFolderHistory(normalizedPath);

    if (result.error) {
      return NextResponse.json(
        {
          folderPath: normalizedPath,
          files: [],
          originalFileCount: 0,
          folderStatus: "not_found",
          error: result.error,
        },
        { status: 500 }
      );
    }

    // Check filesystem status
    const folderStatus = checkFolderStatus(normalizedPath);

    return NextResponse.json({
      folderPath: normalizedPath,
      files: result.files,
      originalFileCount: result.originalFileCount,
      folderStatus,
    });
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error occurred";

    return NextResponse.json(
      {
        folderPath: "",
        files: [],
        originalFileCount: 0,
        folderStatus: "not_found",
        error: errorMessage,
      },
      { status: 500 }
    );
  }
}
