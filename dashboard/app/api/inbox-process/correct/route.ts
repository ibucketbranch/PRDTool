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

interface CorrectBody {
  filename: string;
  wrong_bin: string;
  correct_bin: string;
}

interface LearnedOverride {
  pattern?: string;
  correct_bin?: string;
  source?: string;
  created_at?: string;
  hit_count?: number;
}

/**
 * POST: Record a user correction (wrong_bin -> correct_bin) as a learned override.
 * Extracts a pattern from the filename for future matching.
 */
export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as CorrectBody;
    const { filename, wrong_bin, correct_bin } = body;

    if (!filename || !correct_bin) {
      return NextResponse.json(
        { success: false, message: "filename and correct_bin are required" },
        { status: 400 }
      );
    }

    // Extract pattern from filename (stem without extension, or key part)
    const stem = path.basename(filename, path.extname(filename));
    const pattern = stem.length > 0 ? stem : filename;

    const override = {
      pattern,
      correct_bin,
      source: "user_correction",
      created_at: new Date().toISOString(),
      hit_count: 0,
    };

    let overrides: { overrides: LearnedOverride[]; updated_at: string } = {
      overrides: [],
      updated_at: "",
    };

    try {
      const data = await fs.readFile(OVERRIDES_PATH, "utf-8");
      overrides = JSON.parse(data) as typeof overrides;
    } catch {
      await fs.mkdir(path.dirname(OVERRIDES_PATH), { recursive: true });
    }

    overrides.overrides = overrides.overrides.filter(
      (o) => o.pattern !== pattern
    );
    overrides.overrides.push(override);
    overrides.updated_at = new Date().toISOString();

    await fs.writeFile(
      OVERRIDES_PATH,
      JSON.stringify(overrides, null, 2),
      "utf-8"
    );

    return NextResponse.json({
      success: true,
      message: "Override recorded",
      override: { pattern, correct_bin },
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        message: "Failed to record correction",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
