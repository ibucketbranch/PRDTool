"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface DupGroup {
  hash: string;
  canonical_path: string;
  duplicates: string[];
  total_wasted_bytes: number;
}

interface DedupResult {
  success: boolean;
  groups?: DupGroup[];
  wasted_bytes?: number;
  total_duplicate_groups?: number;
}

export default function DedupPage() {
  const [result, setResult] = useState<DedupResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch("/api/dedup");
        const data = await res.json();
        setResult(data);
      } catch {
        setResult({ success: false });
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <main className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-6">Duplicate Files</h1>
        <p className="text-neutral-600">Scanning for duplicates...</p>
      </main>
    );
  }

  const groups = result?.groups ?? [];
  const wastedBytes = result?.wasted_bytes ?? 0;
  const wastedMB = (wastedBytes / (1024 * 1024)).toFixed(1);

  return (
    <main className="container mx-auto px-4 py-8">
      <div className="mb-6">
        <Link
          href="/"
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline mb-2 inline-block"
        >
          ← Back to Dashboard
        </Link>
        <h1 className="text-3xl font-bold">Duplicate Files</h1>
        <p className="text-neutral-600 mt-2">
          Exact duplicates detected by SHA-256 hash. Wasted storage: {wastedMB} MB
        </p>
      </div>

      {result?.success ? (
        <div className="space-y-6">
          <div className="bg-white rounded-lg border border-neutral-200 p-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-sm text-neutral-600">Duplicate Groups</div>
                <div className="text-2xl font-bold">{groups.length}</div>
              </div>
              <div>
                <div className="text-sm text-neutral-600">Wasted Storage</div>
                <div className="text-2xl font-bold text-amber-600">{wastedMB} MB</div>
              </div>
            </div>
          </div>

          {groups.length === 0 ? (
            <p className="text-neutral-600">No duplicate groups found.</p>
          ) : (
            <div className="space-y-4">
              {groups.slice(0, 20).map((g, i) => (
                <div
                  key={i}
                  className="bg-white rounded-lg border border-neutral-200 p-4"
                >
                  <div className="text-sm font-medium text-neutral-700 mb-2">
                    Canonical: {g.canonical_path.split("/").pop()}
                  </div>
                  <div className="text-xs text-neutral-500 mb-2">
                    {(g.total_wasted_bytes / 1024).toFixed(1)} KB wasted
                  </div>
                  <ul className="text-sm text-neutral-600 space-y-1">
                    {g.duplicates.map((d, j) => (
                      <li key={j} className="truncate">
                        Duplicate: {d.split("/").pop()}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {groups.length > 20 && (
                <p className="text-sm text-neutral-500">
                  Showing first 20 of {groups.length} groups.
                </p>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <p className="text-red-700">Failed to load duplicate report.</p>
        </div>
      )}
    </main>
  );
}
