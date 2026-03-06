import { NextRequest, NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";

const ICLOUD_BASE =
  process.env.NEXT_PUBLIC_ICLOUD_BASE_PATH ||
  "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs";
const OVERRIDES_PATH = path.join(
  ICLOUD_BASE,
  ".organizer",
  "agent",
  "learned_overrides.json"
);

/**
 * GET: Return all learned overrides.
 */
export async function GET() {
  try {
    let overrides: { pattern: string; correct_bin: string; hit_count: number; created_at: string }[] = [];
    try {
      const data = await fs.readFile(OVERRIDES_PATH, "utf-8");
      const parsed = JSON.parse(data);
      overrides = parsed.overrides || [];
    } catch {
      return NextResponse.json({
        success: true,
        overrides: [],
      });
    }

    return NextResponse.json({
      success: true,
      overrides,
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        message: "Failed to load overrides",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

/**
 * DELETE: Remove an override by pattern.
 * Body: { pattern: string }
 */
export async function DELETE(request: NextRequest) {
  try {
    const body = await request.json();
    const { pattern } = body as { pattern?: string };

    if (!pattern) {
      return NextResponse.json(
        { success: false, message: "pattern is required" },
        { status: 400 }
      );
    }

    let overrides: { overrides: { pattern: string }[]; updated_at: string } = {
      overrides: [],
      updated_at: "",
    };

    try {
      const data = await fs.readFile(OVERRIDES_PATH, "utf-8");
      overrides = JSON.parse(data);
    } catch {
      return NextResponse.json({
        success: true,
        message: "Override removed (file did not exist)",
      });
    }

    const before = overrides.overrides.length;
    overrides.overrides = overrides.overrides.filter((o) => o.pattern !== pattern);
    overrides.updated_at = new Date().toISOString();

    if (overrides.overrides.length < before) {
      await fs.writeFile(
        OVERRIDES_PATH,
        JSON.stringify(overrides, null, 2),
        "utf-8"
      );
    }

    return NextResponse.json({
      success: true,
      message: "Override removed",
      removed: before > overrides.overrides.length,
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        message: "Failed to remove override",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
