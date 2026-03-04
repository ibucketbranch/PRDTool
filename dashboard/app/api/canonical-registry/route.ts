/**
 * API endpoint for accessing the canonical registry
 *
 * GET /api/canonical-registry?basePath=X
 *   Returns the canonical registry entries
 *
 * POST /api/canonical-registry
 *   Assess a folder using the canonical registry
 *   Body: { basePath: string, folderName: string, dominantCategory?: string }
 */

import { NextRequest, NextResponse } from "next/server";
import path from "path";
import {
  loadCanonicalRegistry,
  assessFolderWithRegistry,
  PYTHON_CATEGORY_PATTERNS,
} from "@/lib/canonical-registry";

/**
 * GET /api/canonical-registry
 * Returns the canonical registry and category patterns
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const basePath = searchParams.get("basePath");

    if (!basePath) {
      return NextResponse.json(
        { error: "Missing required parameter: basePath" },
        { status: 400 }
      );
    }

    // Normalize path
    const normalizedPath = path.normalize(basePath);

    // Load the canonical registry
    const result = loadCanonicalRegistry(normalizedPath);

    return NextResponse.json({
      registry: result.registry,
      categoryPatterns: PYTHON_CATEGORY_PATTERNS,
      error: result.error,
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Internal server error" },
      { status: 500 }
    );
  }
}

/**
 * POST /api/canonical-registry
 * Assess a folder using the canonical registry
 */
export async function POST(request: NextRequest) {
  try {
    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return NextResponse.json(
        { error: "Invalid JSON body" },
        { status: 400 }
      );
    }

    const { basePath, folderName, dominantCategory } = body as {
      basePath?: string;
      folderName?: string;
      dominantCategory?: string;
    };

    // Validate required parameters
    if (!basePath) {
      return NextResponse.json(
        { error: "Missing required parameter: basePath" },
        { status: 400 }
      );
    }

    if (!folderName || typeof folderName !== "string") {
      return NextResponse.json(
        { error: "Missing or invalid parameter: folderName" },
        { status: 400 }
      );
    }

    // Normalize path
    const normalizedPath = path.normalize(basePath);

    // Load the canonical registry
    const registryResult = loadCanonicalRegistry(normalizedPath);

    // Assess the folder
    const assessment = assessFolderWithRegistry(
      folderName,
      registryResult.registry,
      dominantCategory || null
    );

    return NextResponse.json({
      folderName,
      assessment,
      registryAvailable: registryResult.registry !== null,
      registryError: registryResult.error,
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Internal server error" },
      { status: 500 }
    );
  }
}
