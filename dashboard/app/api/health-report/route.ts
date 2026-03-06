import { NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";

const ICLOUD_BASE =
  process.env.NEXT_PUBLIC_ICLOUD_BASE_PATH ||
  "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs";

/**
 * GET: Aggregate file health report.
 */
export async function GET() {
  try {
    const dnaPath = path.join(ICLOUD_BASE, ".organizer", "agent", "file_dna.json");
    const historyPath = path.join(ICLOUD_BASE, ".organizer", "agent", "routing_history.json");
    const inboxPath = path.join(ICLOUD_BASE, "In-Box");

    let totalTracked = 0;
    let duplicateGroups = 0;
    let duplicateFiles = 0;
    let wastedBytes = 0;
    let filesRoutedThisMonth = 0;
    let healthScore = 100;

    try {
      const dnaData = await fs.readFile(dnaPath, "utf-8");
      const dna = JSON.parse(dnaData);
      const entries = dna.entries || [];
      totalTracked = entries.length;

      const hashCounts: Record<string, number> = {};
      for (const e of entries) {
        if (e.sha256_hash) {
          hashCounts[e.sha256_hash] = (hashCounts[e.sha256_hash] || 0) + 1;
        }
      }
      for (const count of Object.values(hashCounts)) {
        if (count > 1) {
          duplicateGroups++;
          duplicateFiles += count - 1;
        }
      }
    } catch {
      // No DNA file
    }

    try {
      const historyData = await fs.readFile(historyPath, "utf-8");
      const history = JSON.parse(historyData);
      const records = history.records || [];
      const now = new Date();
      const thisMonth = now.getMonth();
      const thisYear = now.getFullYear();
      filesRoutedThisMonth = records.filter((r: { routed_at?: string }) => {
        if (!r.routed_at) return false;
        const d = new Date(r.routed_at);
        return d.getMonth() === thisMonth && d.getFullYear() === thisYear;
      }).length;
    } catch {
      // No history
    }

    let inboxPending = 0;
    try {
      const files = await fs.readdir(inboxPath);
      const exts = [".pdf", ".txt", ".docx", ".xlsx", ".pptx", ".rtf"];
      inboxPending = files.filter((f) =>
        exts.includes(path.extname(f).toLowerCase())
      ).length;
    } catch {
      // No inbox
    }

    const duplicatePct = totalTracked > 0 ? (duplicateFiles / totalTracked) * 100 : 0;
    const inboxPct = totalTracked > 0 ? (inboxPending / Math.max(totalTracked, 1)) * 100 : 0;
    healthScore = Math.round(
      100 - duplicatePct * 0.3 - inboxPct * 0.3 - (totalTracked === 0 ? 20 : 0)
    );
    healthScore = Math.max(0, Math.min(100, healthScore));

    const storageCostPerGB = 0.023;
    const wastedGB = wastedBytes / (1024 * 1024 * 1024);
    const storageSavedDollarsPerMonth = wastedGB * storageCostPerGB;

    return NextResponse.json({
      success: true,
      total_files_tracked: totalTracked,
      duplicates_found: duplicateFiles,
      duplicate_groups: duplicateGroups,
      wasted_storage_bytes: wastedBytes,
      files_routed_this_month: filesRoutedThisMonth,
      inbox_pending: inboxPending,
      health_score: healthScore,
      storage_saved_dollars_per_month: Math.round(storageSavedDollarsPerMonth * 100) / 100,
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        message: "Failed to generate health report",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
