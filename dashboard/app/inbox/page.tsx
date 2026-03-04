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

export default function InboxPage() {
  const [status, setStatus] = useState<InboxStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [dryRun, setDryRun] = useState(true);

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

  useEffect(() => {
    loadStatus();
  }, []);

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

      {/* Status Card */}
      {status && status.success && (
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

      {/* Controls */}
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
