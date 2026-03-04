import { NextRequest, NextResponse } from "next/server";
import * as fs from "fs/promises";
import * as path from "path";

export interface RemoveFoldersRequest {
  folderPaths: string[];
}

export interface RemoveFoldersResponse {
  success: boolean;
  removed: number;
  failed: number;
  errors: Array<{ folderPath: string; error: string }>;
  error?: string;
}

/**
 * POST /api/empty-folders/remove
 * Remove empty folders from the filesystem
 *
 * Request body:
 * - folderPaths: string[] - Array of absolute folder paths to remove
 */
export async function POST(
  request: NextRequest
): Promise<NextResponse<RemoveFoldersResponse>> {
  try {
    const body: RemoveFoldersRequest = await request.json();
    const { folderPaths } = body;

    if (!folderPaths || !Array.isArray(folderPaths)) {
      return NextResponse.json(
        {
          success: false,
          removed: 0,
          failed: 0,
          errors: [],
          error: "folderPaths array is required",
        },
        { status: 400 }
      );
    }

    const errors: Array<{ folderPath: string; error: string }> = [];
    let removed = 0;

    for (const folderPath of folderPaths) {
      try {
        // Validate path
        if (!path.isAbsolute(folderPath)) {
          errors.push({
            folderPath,
            error: "Only absolute paths are allowed",
          });
          continue;
        }

        // Security check: Ensure path is within allowed directories
        // For now, we'll allow any absolute path, but you might want to restrict this
        const normalizedPath = path.normalize(folderPath);

        // Check if folder exists
        try {
          const stats = await fs.stat(normalizedPath);
          if (!stats.isDirectory()) {
            errors.push({
              folderPath,
              error: "Path is not a directory",
            });
            continue;
          }
        } catch (statError) {
          errors.push({
            folderPath,
            error: `Folder does not exist: ${statError instanceof Error ? statError.message : "Unknown error"}`,
          });
          continue;
        }

        // Check if folder is empty (ignore system/metadata files)
        const contents = await fs.readdir(normalizedPath);
        // Filter out system/metadata files
        const systemFiles = ['.DS_Store', '.DS_Store_1', '.localized', 'Thumbs.db', '.gitkeep'];
        const nonSystemFiles = contents.filter(item => !systemFiles.includes(item) && !item.startsWith('.DS_Store'));
        
        if (nonSystemFiles.length > 0) {
          // Check if remaining items are directories
          let hasRealFiles = false;
          for (const item of nonSystemFiles) {
            const itemPath = path.join(normalizedPath, item);
            try {
              const itemStats = await fs.stat(itemPath);
              if (itemStats.isFile()) {
                hasRealFiles = true;
                break;
              }
            } catch {
              // Skip if we can't stat
            }
          }
          
          if (hasRealFiles) {
            errors.push({
              folderPath,
              error: "Folder contains files (not just system metadata)",
            });
            continue;
          }
        }

        // Remove system files first (optional cleanup)
        for (const item of contents) {
          if (systemFiles.includes(item) || item.startsWith('.DS_Store')) {
            try {
              await fs.unlink(path.join(normalizedPath, item));
            } catch {
              // Ignore errors removing system files
            }
          }
        }

        // Remove the empty folder
        await fs.rmdir(normalizedPath);
        removed++;
      } catch (err) {
        errors.push({
          folderPath,
          error: err instanceof Error ? err.message : "Unknown error",
        });
      }
    }

    return NextResponse.json({
      success: errors.length === 0,
      removed,
      failed: errors.length,
      errors,
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        removed: 0,
        failed: 0,
        errors: [],
        error: error instanceof Error ? error.message : "Unknown error occurred",
      },
      { status: 500 }
    );
  }
}
