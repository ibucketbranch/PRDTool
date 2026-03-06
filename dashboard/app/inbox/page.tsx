"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface InboxStatus {
  success: boolean;
  inbox?: {
    path: string;
    fileCount: number;
    files: string[];
  };
  processed?: {
    count: number;
    path: string;
  };
  errors?: {
    count: number;
    path: string;
  };
  message?: string;
}

interface ProcessResult {
  success: boolean;
  message: string;
  stats?: {
    total: number;
    processed: number;
    failed: number;
  };
  action?: string;
  dryRun?: boolean;
  output?: string;
  error?: string;
}

interface RoutingRecord {
  filename: string;
  destinationBin: string;
  routedAt: string;
  confidence: number;
  status: string;
  matchedKeywords: string[];
  // Explainability fields (Phase 16.4)
  reason: string;
  modelUsed: string;
  usedKeywordFallback: boolean;
}

interface LearnedOverride {
  pattern: string;
  correct_bin: string;
  hit_count: number;
  created_at: string;
}

type TabId = "status" | "activity" | "overrides";

export default function InboxPage() {
  const [status, setStatus] = useState<InboxStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>("status");
  const [history, setHistory] = useState<RoutingRecord[]>([]);
  const [overrides, setOverrides] = useState<LearnedOverride[]>([]);
  const [correctModal, setCorrectModal] = useState<{ filename: string; wrong_bin: string } | null>(null);
  const [correctBin, setCorrectBin] = useState("");

  // Load inbox status
  const loadStatus = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/inbox-process");
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      console.error("Failed to load inbox status:", error);
      setStatus({
        success: false,
        message: "Failed to load inbox status",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async () => {
    try {
      const res = await fetch("/api/inbox-process/history?limit=50");
      const data = await res.json();
      if (data.success) setHistory(data.history || []);
    } catch {
      setHistory([]);
    }
  };

  const loadOverrides = async () => {
    try {
      const res = await fetch("/api/inbox-process/overrides");
      const data = await res.json();
      if (data.success) setOverrides(data.overrides || []);
    } catch {
      setOverrides([]);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  useEffect(() => {
    if (activeTab === "activity") loadHistory();
    if (activeTab === "overrides") loadOverrides();
  }, [activeTab]);

  const handleCorrect = async () => {
    if (!correctModal || !correctBin.trim()) return;
    try {
      const res = await fetch("/api/inbox-process/correct", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: correctModal.filename,
          wrong_bin: correctModal.wrong_bin,
          correct_bin: correctBin.trim(),
        }),
      });
      const data = await res.json();
      if (data.success) {
        setCorrectModal(null);
        setCorrectBin("");
        loadOverrides();
        loadHistory();
      } else {
        setResult({ success: false, message: data.message || "Failed to record correction" });
      }
    } catch (e) {
      setResult({ success: false, message: "Failed to record correction", error: String(e) });
    }
  };

  const handleDeleteOverride = async (pattern: string) => {
    if (!confirm(`Remove override for "${pattern}"?`)) return;
    try {
      const res = await fetch("/api/inbox-process/overrides", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pattern }),
      });
      const data = await res.json();
      if (data.success) loadOverrides();
    } catch {
      setResult({ success: false, message: "Failed to remove override" });
    }
  };

  // Process inbox
  const handleProcess = async (action: "process" | "finalize" | "retry-errors") => {
    setProcessing(true);
    setResult(null);
    
    try {
      // Use AbortController for timeout handling
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 11 * 60 * 1000); // 11 minutes (slightly longer than API timeout)
      
      const response = await fetch(
        `/api/inbox-process?action=${action}&dryRun=${dryRun}`,
        {
          method: "POST",
          signal: controller.signal,
        }
      );
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setResult(data);
      
      // Reload status after processing
      if (data.success && !dryRun) {
        setTimeout(() => {
          loadStatus();
        }, 1000);
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        setResult({
          success: false,
          message: "Processing timed out. The operation may still be running in the background.",
          error: "Request timeout after 11 minutes",
        });
      } else {
        setResult({
          success: false,
          message: "Failed to process inbox",
          error: error instanceof Error ? error.message : String(error),
        });
      }
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return (
      <main className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-6">Inbox Processor</h1>
        <p className="text-neutral-600">Loading inbox status...</p>
      </main>
    );
  }

  return (
    <main className="container mx-auto px-4 py-8">
      <div className="mb-6">
        <Link
          href="/"
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline mb-2 inline-block"
        >
          ← Back to Dashboard
        </Link>
        <h1 className="text-3xl font-bold">Inbox Processor</h1>
      </div>
      <p className="text-neutral-600 mb-8">
        Process new files from your In-Box folder. Files are moved to staging first, then finalized to their permanent location.
      </p>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-neutral-200">
        {(["status", "activity", "overrides"] as TabId[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 font-medium border-b-2 -mb-px transition-colors ${
              activeTab === tab
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-neutral-600 hover:text-neutral-900"
            }`}
          >
            {tab === "status" && "Status"}
            {tab === "activity" && "Recent Activity"}
            {tab === "overrides" && "Learned Overrides"}
          </button>
        ))}
      </div>

      {/* Status Tab */}
      {activeTab === "status" && status && status.success && (
        <div className="bg-white rounded-lg border border-neutral-200 p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Inbox Status</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-blue-50 rounded p-4">
              <div className="text-sm text-blue-600 mb-1">In-Box Files</div>
              <div className="text-2xl font-bold text-blue-900">
                {status.inbox?.fileCount || 0}
              </div>
              {status.inbox && status.inbox.files.length > 0 && (
                <div className="text-xs text-blue-600 mt-2">
                  {status.inbox.files.slice(0, 3).join(", ")}
                  {status.inbox.files.length > 3 && "..."}
                </div>
              )}
            </div>
            <div className="bg-green-50 rounded p-4">
              <div className="text-sm text-green-600 mb-1">Processed (Staging)</div>
              <div className="text-2xl font-bold text-green-900">
                {status.processed?.count || 0}
              </div>
              <div className="text-xs text-green-600 mt-2">
                Ready to finalize
              </div>
            </div>
            <div className="bg-red-50 rounded p-4">
              <div className="text-sm text-red-600 mb-1">Processing Errors</div>
              <div className="text-2xl font-bold text-red-900">
                {status.errors?.count || 0}
              </div>
              <div className="text-xs text-red-600 mt-2">
                Need review
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Recent Activity Tab */}
      {activeTab === "activity" && (
        <div className="bg-white rounded-lg border border-neutral-200 p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Recent Routing Activity</h2>
          {history.length === 0 ? (
            <p className="text-neutral-600">No routing history yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2">Filename</th>
                    <th className="text-left py-2">Destination</th>
                    <th className="text-left py-2">Confidence</th>
                    <th className="text-left py-2">Model</th>
                    <th className="text-left py-2">Date</th>
                    <th className="text-left py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((r, i) => (
                    <tr key={i} className="border-b border-neutral-100 group">
                      <td className="py-2">
                        <div>{r.filename}</div>
                        {/* Show LLM reasoning if available */}
                        {r.reason && (
                          <div className="text-xs text-neutral-500 mt-1 max-w-xs truncate" title={r.reason}>
                            {r.reason}
                          </div>
                        )}
                      </td>
                      <td className="py-2">{r.destinationBin}</td>
                      <td className="py-2">{(r.confidence * 100).toFixed(0)}%</td>
                      <td className="py-2">
                        {r.usedKeywordFallback ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800">
                            Keyword
                          </span>
                        ) : r.modelUsed ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800" title={r.modelUsed}>
                            {r.modelUsed.split(":")[0]}
                          </span>
                        ) : (
                          <span className="text-neutral-400 text-xs">-</span>
                        )}
                      </td>
                      <td className="py-2 text-neutral-600">{r.routedAt?.slice(0, 19)}</td>
                      <td className="py-2">
                        <button
                          onClick={() => setCorrectModal({ filename: r.filename, wrong_bin: r.destinationBin })}
                          className="text-blue-600 hover:underline text-xs"
                        >
                          Correct
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Learned Overrides Tab */}
      {activeTab === "overrides" && (
        <div className="bg-white rounded-lg border border-neutral-200 p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Learned Overrides</h2>
          <p className="text-neutral-600 text-sm mb-4">
            User corrections that override default routing. These take priority over built-in rules.
          </p>
          {overrides.length === 0 ? (
            <p className="text-neutral-600">No overrides yet. Use &quot;Correct&quot; on a routing to add one.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2">Pattern</th>
                    <th className="text-left py-2">Correct Bin</th>
                    <th className="text-left py-2">Hits</th>
                    <th className="text-left py-2">Created</th>
                    <th className="text-left py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {overrides.map((o, i) => (
                    <tr key={i} className="border-b border-neutral-100">
                      <td className="py-2">{o.pattern}</td>
                      <td className="py-2">{o.correct_bin}</td>
                      <td className="py-2">{o.hit_count}</td>
                      <td className="py-2 text-neutral-600">{o.created_at?.slice(0, 10)}</td>
                      <td className="py-2">
                        <button
                          onClick={() => handleDeleteOverride(o.pattern)}
                          className="text-red-600 hover:underline text-xs"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Correct Modal */}
      {correctModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-2">Correct Routing</h3>
            <p className="text-sm text-neutral-600 mb-4">
              File <strong>{correctModal.filename}</strong> was routed to <strong>{correctModal.wrong_bin}</strong>.
              Enter the correct destination:
            </p>
            <input
              type="text"
              value={correctBin}
              onChange={(e) => setCorrectBin(e.target.value)}
              placeholder="e.g. Finances Bin/Taxes"
              className="w-full border border-neutral-300 rounded px-3 py-2 mb-4"
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => { setCorrectModal(null); setCorrectBin(""); }}
                className="px-4 py-2 border border-neutral-300 rounded hover:bg-neutral-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCorrect}
                disabled={!correctBin.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                Save Correction
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Controls - only on status tab */}
      {activeTab === "status" && (
      <div className="bg-white rounded-lg border border-neutral-200 p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4">Process Inbox</h2>
        
        {/* Dry Run Toggle */}
        <div className="mb-4 flex items-center gap-3">
          <input
            type="checkbox"
            id="dryRun"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            className="w-4 h-4"
          />
          <label htmlFor="dryRun" className="text-sm text-neutral-700">
            Dry-run mode (preview only, no files moved)
          </label>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-4 flex-wrap">
          <button
            onClick={() => handleProcess("process")}
            disabled={processing || (status?.inbox?.fileCount || 0) === 0}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              processing || (status?.inbox?.fileCount || 0) === 0
                ? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            {processing ? (
              <span className="flex items-center gap-2">
                <span className="animate-spin">⏳</span>
                Processing... (this may take several minutes)
              </span>
            ) : (
              "Process Inbox → Staging"
            )}
          </button>
          
          <button
            onClick={() => handleProcess("finalize")}
            disabled={processing || (status?.processed?.count || 0) === 0}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              processing || (status?.processed?.count || 0) === 0
                ? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                : "bg-green-600 text-white hover:bg-green-700"
            }`}
          >
            {processing ? (
              <span className="flex items-center gap-2">
                <span className="animate-spin">⏳</span>
                Finalizing... (this may take several minutes)
              </span>
            ) : (
              "Finalize Staging → Final Location"
            )}
          </button>
          
          <button
            onClick={() => handleProcess("retry-errors")}
            disabled={processing || (status?.errors?.count || 0) === 0}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              processing || (status?.errors?.count || 0) === 0
                ? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                : "bg-orange-600 text-white hover:bg-orange-700"
            }`}
          >
            {processing ? (
              <span className="flex items-center gap-2">
                <span className="animate-spin">⏳</span>
                Retrying... (this may take several minutes)
              </span>
            ) : (
              `Retry ${status?.errors?.count || 0} Failed Files`
            )}
          </button>
        </div>

        <p className="text-xs text-neutral-500 mt-4">
          <strong>Step 1:</strong> Process Inbox moves files from In-Box to Processed (staging) folder.<br />
          <strong>Step 2:</strong> Finalize moves files from Processed to their permanent organized location.
        </p>
      </div>
      )}

      {/* Results */}
      {result && (
        <div
          className={`rounded-lg border p-6 ${
            result.success
              ? "bg-green-50 border-green-200"
              : "bg-red-50 border-red-200"
          }`}
        >
          <h3 className="font-semibold mb-2">
            {result.success ? "✅ Success" : "❌ Error"}
          </h3>
          <p className="text-sm mb-4">{result.message}</p>
          
          {result.stats && (
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div>
                <div className="text-xs text-neutral-600">Total</div>
                <div className="text-lg font-bold">{result.stats.total}</div>
              </div>
              <div>
                <div className="text-xs text-neutral-600">Processed</div>
                <div className="text-lg font-bold text-green-600">
                  {result.stats.processed}
                </div>
              </div>
              <div>
                <div className="text-xs text-neutral-600">Failed</div>
                <div className="text-lg font-bold text-red-600">
                  {result.stats.failed}
                </div>
              </div>
            </div>
          )}

          {result.output && (
            <details className="mt-4">
              <summary className="text-sm font-medium cursor-pointer">
                View Output
              </summary>
              <pre className="mt-2 text-xs bg-white p-3 rounded border overflow-auto max-h-60">
                {result.output}
              </pre>
            </details>
          )}

          {result.error && (
            <div className="mt-4 text-sm text-red-600">
              <strong>Error:</strong> {result.error}
            </div>
          )}
        </div>
      )}

      {/* Error State */}
      {status && !status.success && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <h3 className="font-semibold text-red-900 mb-2">Error</h3>
          <p className="text-sm text-red-700">{status.message}</p>
        </div>
      )}
    </main>
  );
}
