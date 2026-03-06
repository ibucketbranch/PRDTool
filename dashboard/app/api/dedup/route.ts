import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";

const PROJECT_ROOT =
  process.env.NEXT_PUBLIC_ORGANIZER_BASE_PATH ||
  "/Users/michaelvalderrama/Websites/PRDTool";
const ICLOUD_BASE =
  process.env.NEXT_PUBLIC_ICLOUD_BASE_PATH ||
  "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs";

/**
 * GET: Run dedup scan and return duplicate groups.
 * Query params: action=report (default) | quarantine (moves dupes to Archive/Quarantined-Duplicates)
 */
export async function GET(request: NextRequest) {
  try {
    const action = request.nextUrl.searchParams.get("action") || "report";

    const result = await new Promise<{
      groups: { hash: string; canonical_path: string; duplicates: string[]; total_wasted_bytes: number }[];
      wasted_bytes: number;
    }>((resolve, reject) => {
      const script = `
import json
import os
import sys
sys.path.insert(0, os.environ.get("PYTHONPATH", "."))
from organizer.dedup_engine import DedupEngine

base = os.environ.get("DEDUP_BASE_PATH", ".")
engine = DedupEngine(base)
engine.scan(max_files=10000)
groups = []
for g in engine.get_groups():
    groups.append({
        "hash": g.sha256_hash,
        "canonical_path": g.canonical_path,
        "duplicates": g.duplicates,
        "total_wasted_bytes": g.total_wasted_bytes,
    })
print(json.dumps({"groups": groups, "wasted_bytes": engine.report_wasted_storage()}))
`;
      const child = spawn("python3", ["-c", script], {
        cwd: PROJECT_ROOT,
        env: {
          ...process.env,
          PYTHONPATH: PROJECT_ROOT,
          DEDUP_BASE_PATH: ICLOUD_BASE,
        },
      });

      let stdout = "";
      let stderr = "";
      child.stdout?.on("data", (d) => (stdout += d.toString()));
      child.stderr?.on("data", (d) => (stderr += d.toString()));

      child.on("close", (code) => {
        if (code !== 0) {
          reject(new Error(stderr || "Dedup scan failed"));
          return;
        }
        try {
          resolve(JSON.parse(stdout));
        } catch {
          reject(new Error("Invalid dedup output"));
        }
      });

      child.on("error", reject);
    });

    if (action === "quarantine") {
      return NextResponse.json({
        success: true,
        message: "Quarantine not yet implemented. Use report to view duplicates.",
        groups: result.groups,
        wasted_bytes: result.wasted_bytes,
      });
    }

    return NextResponse.json({
      success: true,
      groups: result.groups,
      wasted_bytes: result.wasted_bytes,
      total_duplicate_groups: result.groups.length,
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        message: "Failed to run dedup scan",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
