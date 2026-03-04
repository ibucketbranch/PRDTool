import { NextRequest, NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";
import { existsSync } from "fs";
import path from "path";

const execAsync = promisify(exec);

export interface OpenInFinderRequest {
  path: string;
}

export interface OpenInFinderResponse {
  success: boolean;
  message: string;
  path?: string;
  error?: string;
}

/**
 * POST /api/open-in-finder
 * Opens a file in macOS Finder using `open -R` command
 * This reveals the file in Finder and selects it
 */
export async function POST(
  request: NextRequest
): Promise<NextResponse<OpenInFinderResponse>> {
  // Check if running on macOS
  if (process.platform !== "darwin") {
    return NextResponse.json(
      {
        success: false,
        message: "This feature is only available on macOS",
        error: `Unsupported platform: ${process.platform}`,
      },
      { status: 400 }
    );
  }

  try {
    const body = (await request.json()) as OpenInFinderRequest;
    const { path: filePath } = body;

    // Validate path is provided
    if (!filePath || typeof filePath !== "string") {
      return NextResponse.json(
        {
          success: false,
          message: "File path is required",
          error: "Missing or invalid path parameter",
        },
        { status: 400 }
      );
    }

    // Sanitize and validate the path
    const normalizedPath = path.normalize(filePath);

    // Security check: Prevent path traversal attacks
    // Only allow absolute paths
    if (!path.isAbsolute(normalizedPath)) {
      return NextResponse.json(
        {
          success: false,
          message: "Invalid file path",
          error: "Only absolute paths are allowed",
        },
        { status: 400 }
      );
    }

    // Check if file exists
    if (!existsSync(normalizedPath)) {
      return NextResponse.json(
        {
          success: false,
          message: "File not found",
          path: normalizedPath,
          error: "The specified file does not exist",
        },
        { status: 404 }
      );
    }

    // Execute the `open -R` command to reveal file in Finder
    // -R flag reveals the file in Finder and selects it
    // Escape the path properly for shell execution
    const escapedPath = normalizedPath.replace(/'/g, "'\\''");
    await execAsync(`open -R '${escapedPath}'`);

    return NextResponse.json({
      success: true,
      message: "File revealed in Finder",
      path: normalizedPath,
    });
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error occurred";

    return NextResponse.json(
      {
        success: false,
        message: "Failed to open file in Finder",
        error: errorMessage,
      },
      { status: 500 }
    );
  }
}
