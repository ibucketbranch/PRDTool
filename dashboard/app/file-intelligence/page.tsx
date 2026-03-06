"use client";

import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { StatCard } from "@/components/StatCard";
import { FileDNAResultCard } from "@/components/FileDNAResultCard";
import {
  SearchResultsSkeleton,
  ErrorDisplay,
  EmptyState,
  StatCardSkeletonGrid,
} from "@/components";
import { openInFinder, copyToClipboard } from "@/lib/utils";
import type { FileDNAResult } from "@/components/FileDNAResultCard";

interface FileDNAStats {
  totalTracked: number;
  duplicateGroups: number;
  duplicateFiles: number;
}

interface DuplicateGroup {
  hash: string;
  files: string[];
  count: number;
}

type FilterType = "all" | "duplicates" | "with_tags";

export default function FileIntelligencePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [results, setResults] = useState<FileDNAResult[]>([]);
  const [stats, setStats] = useState<FileDNAStats | null>(null);
  const [duplicateGroups, setDuplicateGroups] = useState<DuplicateGroup[]>([]);
  const [wastedBytes, setWastedBytes] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterType>("all");
  const [hasSearched, setHasSearched] = useState(false);

  // Fetch stats on mount
  useEffect(() => {
    async function fetchStats() {
      setIsLoadingStats(true);
      setStatsError(null);
      try {
        // Fetch DNA stats
        const statsResponse = await fetch("/api/file-dna/stats");
        if (!statsResponse.ok) {
          throw new Error("Failed to fetch stats");
        }
        const statsData = await statsResponse.json();
        setStats({
          totalTracked: statsData.totalTracked || 0,
          duplicateGroups: statsData.duplicateGroups || 0,
          duplicateFiles: statsData.duplicateFiles || 0,
        });

        // Fetch duplicate groups for overview
        const dupeResponse = await fetch("/api/file-dna/duplicates");
        if (dupeResponse.ok) {
          const dupeData = await dupeResponse.json();
          setDuplicateGroups(dupeData.groups || []);
          setWastedBytes(dupeData.wastedBytes || 0);
        }
      } catch (err) {
        setStatsError(
          err instanceof Error ? err.message : "Failed to load statistics"
        );
      } finally {
        setIsLoadingStats(false);
      }
    }

    fetchStats();
  }, []);

  const handleSearch = useCallback(
    async (query: string) => {
      if (!query.trim()) {
        setResults([]);
        setHasSearched(false);
        return;
      }

      setIsLoading(true);
      setError(null);
      setHasSearched(true);

      try {
        const params = new URLSearchParams();
        params.set("search", query);

        const response = await fetch(`/api/file-dna?${params.toString()}`);

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.message || `HTTP error: ${response.status}`);
        }

        const data = await response.json();

        if (!data.success) {
          throw new Error(data.message || "Failed to search file DNA");
        }

        setResults(data.results || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to search");
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSearch(searchQuery);
    }
  };

  const handlePathClick = useCallback(async (path: string) => {
    const result = await openInFinder(path);

    if (result.success) {
      return;
    }

    const copied = await copyToClipboard(path);
    if (copied) {
      alert(
        `Could not open in Finder. Path copied to clipboard:\n${path}\n\nReason: ${result.error || result.message}`
      );
    } else {
      alert(
        `File path:\n${path}\n\nCould not open in Finder: ${result.error || result.message}`
      );
    }
  }, []);

  // Filter results based on selected filter
  const filteredResults = results.filter((r) => {
    if (filter === "duplicates") {
      return (
        r.duplicate_status.is_duplicate || r.duplicate_status.has_duplicates
      );
    }
    if (filter === "with_tags") {
      return r.tags.length > 0;
    }
    return true;
  });

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  return (
    <main className="container mx-auto px-4 py-8">
      <div className="mb-6">
        <Link
          href="/"
          className="text-sm text-neutral-500 hover:text-neutral-700 transition-colors"
        >
          &larr; Back to Dashboard
        </Link>
      </div>

      <h1 className="text-3xl font-bold mb-2">File Intelligence</h1>
      <p className="text-neutral-600 mb-8">
        Search file DNA, view provenance, find duplicates, and explore
        relationships between files.
      </p>

      {/* Stats Section */}
      {isLoadingStats && (
        <div className="mb-8">
          <StatCardSkeletonGrid count={4} />
        </div>
      )}

      {statsError && (
        <div className="mb-8">
          <ErrorDisplay
            message={statsError}
            severity="warning"
            className="mb-4"
          />
        </div>
      )}

      {stats && !isLoadingStats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            title="Files Tracked"
            value={stats.totalTracked}
            description="Files with DNA recorded"
          />
          <StatCard
            title="Duplicate Groups"
            value={stats.duplicateGroups}
            description="Groups of identical files"
          />
          <StatCard
            title="Duplicate Files"
            value={stats.duplicateFiles}
            description="Total duplicate copies"
          />
          <StatCard
            title="Wasted Space"
            value={formatBytes(wastedBytes)}
            description="Space used by duplicates"
          />
        </div>
      )}

      {/* Duplicate Groups Summary */}
      {duplicateGroups.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Duplicate Groups</h2>
          <div className="bg-white border border-neutral-200 rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {duplicateGroups.slice(0, 6).map((group, index) => (
                <div
                  key={index}
                  className="p-3 bg-amber-50 border border-amber-200 rounded text-sm"
                >
                  <div className="font-medium text-amber-800 mb-1">
                    {group.count} copies
                  </div>
                  <div className="text-amber-700">
                    {group.files.slice(0, 2).map((file, i) => (
                      <button
                        key={i}
                        onClick={() => handlePathClick(file)}
                        className="block truncate hover:underline text-left w-full"
                        title={file}
                      >
                        {file.split("/").pop()}
                      </button>
                    ))}
                    {group.files.length > 2 && (
                      <span className="text-amber-600 text-xs">
                        +{group.files.length - 2} more
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
            {duplicateGroups.length > 6 && (
              <p className="mt-3 text-sm text-neutral-500 text-center">
                Showing 6 of {duplicateGroups.length} duplicate groups
              </p>
            )}
          </div>
        </section>
      )}

      {/* Search Section */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-4">DNA Search</h2>
        <div className="flex gap-4 mb-4">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search by filename, tag, or content..."
            className="flex-1 px-4 py-2 border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={() => handleSearch(searchQuery)}
            disabled={isLoading}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? "Searching..." : "Search"}
          </button>
        </div>

        {/* Filter tabs */}
        {hasSearched && results.length > 0 && (
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setFilter("all")}
              className={`px-3 py-1 text-sm rounded ${
                filter === "all"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
              }`}
            >
              All ({results.length})
            </button>
            <button
              onClick={() => setFilter("duplicates")}
              className={`px-3 py-1 text-sm rounded ${
                filter === "duplicates"
                  ? "bg-amber-100 text-amber-700"
                  : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
              }`}
            >
              Duplicates (
              {
                results.filter(
                  (r) =>
                    r.duplicate_status.is_duplicate ||
                    r.duplicate_status.has_duplicates
                ).length
              }
              )
            </button>
            <button
              onClick={() => setFilter("with_tags")}
              className={`px-3 py-1 text-sm rounded ${
                filter === "with_tags"
                  ? "bg-green-100 text-green-700"
                  : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
              }`}
            >
              With Tags ({results.filter((r) => r.tags.length > 0).length})
            </button>
          </div>
        )}
      </section>

      {/* Loading State */}
      {isLoading && <SearchResultsSkeleton count={3} />}

      {/* Error Message */}
      {error && !isLoading && (
        <ErrorDisplay message={error} className="mb-6" />
      )}

      {/* Search Results */}
      {!isLoading && !error && hasSearched && (
        <div>
          {/* Results Count */}
          <div className="mb-4">
            <p className="text-neutral-600">
              Found <span className="font-semibold">{filteredResults.length}</span>{" "}
              file{filteredResults.length !== 1 ? "s" : ""}
              {filter !== "all" && ` (filtered from ${results.length})`}
            </p>
          </div>

          {/* Results List */}
          {filteredResults.length > 0 ? (
            <div className="space-y-4">
              {filteredResults.map((result, index) => (
                <FileDNAResultCard
                  key={`${result.hash}-${index}`}
                  result={result}
                  onPathClick={handlePathClick}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No files found"
              message={
                filter !== "all"
                  ? "Try changing the filter or searching for different terms"
                  : "Try a different search query"
              }
              className="bg-neutral-50 rounded-lg border border-neutral-200"
            />
          )}
        </div>
      )}

      {/* Initial State */}
      {!hasSearched && !isLoading && !error && (
        <EmptyState
          title="Search for files by DNA"
          message="Enter a filename, tag, or keyword to search the file DNA registry"
          className="bg-neutral-50 rounded-lg border border-neutral-200"
        />
      )}
    </main>
  );
}
