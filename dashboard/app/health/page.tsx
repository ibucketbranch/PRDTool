"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface HealthReport {
  success: boolean;
  total_files_tracked?: number;
  duplicates_found?: number;
  duplicate_groups?: number;
  wasted_storage_bytes?: number;
  files_routed_this_month?: number;
  inbox_pending?: number;
  health_score?: number;
  storage_saved_dollars_per_month?: number;
}

export default function HealthPage() {
  const [report, setReport] = useState<HealthReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch("/api/health-report");
        const data = await res.json();
        setReport(data);
      } catch {
        setReport({ success: false });
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <main className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-6">File Health</h1>
        <p className="text-neutral-600">Loading...</p>
      </main>
    );
  }

  const score = report?.health_score ?? 0;
  const scoreColor =
    score >= 80 ? "text-green-600" : score >= 50 ? "text-amber-600" : "text-red-600";

  return (
    <main className="container mx-auto px-4 py-8">
      <div className="mb-6">
        <Link
          href="/"
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline mb-2 inline-block"
        >
          ← Back to Dashboard
        </Link>
        <h1 className="text-3xl font-bold">File Health Report</h1>
      </div>

      {report?.success ? (
        <div className="space-y-6">
          <div className="bg-white rounded-lg border border-neutral-200 p-6">
            <h2 className="text-xl font-semibold mb-4">Health Score</h2>
            <div className={`text-5xl font-bold ${scoreColor}`}>
              {score}/100
            </div>
            <p className="text-sm text-neutral-600 mt-2">
              Based on duplicates, inbox backlog, and tracking coverage.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="bg-white rounded-lg border border-neutral-200 p-4">
              <div className="text-sm text-neutral-600 mb-1">Files Tracked</div>
              <div className="text-2xl font-bold">
                {report.total_files_tracked ?? 0}
              </div>
            </div>
            <div className="bg-white rounded-lg border border-neutral-200 p-4">
              <div className="text-sm text-neutral-600 mb-1">Duplicates Found</div>
              <div className="text-2xl font-bold text-amber-600">
                {report.duplicates_found ?? 0}
              </div>
            </div>
            <div className="bg-white rounded-lg border border-neutral-200 p-4">
              <div className="text-sm text-neutral-600 mb-1">Routed This Month</div>
              <div className="text-2xl font-bold text-green-600">
                {report.files_routed_this_month ?? 0}
              </div>
            </div>
            <div className="bg-white rounded-lg border border-neutral-200 p-4">
              <div className="text-sm text-neutral-600 mb-1">Inbox Pending</div>
              <div className="text-2xl font-bold">
                {report.inbox_pending ?? 0}
              </div>
            </div>
            <div className="bg-white rounded-lg border border-neutral-200 p-4">
              <div className="text-sm text-neutral-600 mb-1">Storage Wasted</div>
              <div className="text-2xl font-bold">
                {((report.wasted_storage_bytes ?? 0) / (1024 * 1024)).toFixed(1)} MB
              </div>
            </div>
            <div className="bg-white rounded-lg border border-neutral-200 p-4">
              <div className="text-sm text-neutral-600 mb-1">Est. Monthly Cost</div>
              <div className="text-2xl font-bold">
                ${report.storage_saved_dollars_per_month?.toFixed(2) ?? "0.00"}
              </div>
              <p className="text-xs text-neutral-500 mt-1">
                Duplicate storage cost equivalent
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <p className="text-red-700">Failed to load health report.</p>
        </div>
      )}
    </main>
  );
}
