"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  EmptyFoldersList,
  EmptyFoldersFilter,
  BulkActionsBar,
  EmptyFolderListSkeleton,
  ErrorDisplay,
  StatCardSkeleton,
} from "@/components";
import type { EmptyFolderFilterType } from "@/components";
import type { EmptyFolderInfo, FolderAssessment } from "@/lib/supabase";
import { openInFinder, copyToClipboard } from "@/lib/utils";

interface EmptyFoldersResponse {
  emptyFolders: EmptyFolderInfo[];
  totalEmptyFolders: number;
  verifiedEmpty: number;
  notEmpty: number;
  notFound: number;
  error?: string;
}

interface AssessmentResponse {
  assessment: FolderAssessment | null;
  movedFiles: { documentId: string; fileName: string; originalPath: string; currentPath: string; movedAt: string }[];
  error?: string;
}

export default function EmptyFoldersPage() {
  // Data state
  const [folders, setFolders] = useState<EmptyFolderInfo[]>([]);
  const [assessments, setAssessments] = useState<Map<string, FolderAssessment>>(new Map());
  const [keptFolders, setKeptFolders] = useState<Set<string>>(new Set());

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<EmptyFolderFilterType>("all");
  const [selectedFolders, setSelectedFolders] = useState<Set<string>>(new Set());
  const [loadingFolders, setLoadingFolders] = useState<Set<string>>(new Set());

  // Stats for filter counts
  const [stats, setStats] = useState({
    verifiedEmpty: 0,
    notEmpty: 0,
    notFound: 0,
  });

  // Fetch empty folders
  const fetchFolders = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/empty-folders?verifyFilesystem=true");

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error: ${response.status}`);
      }

      const result: EmptyFoldersResponse = await response.json();

      if (result.error) {
        setError(result.error);
        setFolders([]);
      } else {
        setFolders(result.emptyFolders);
        setStats({
          verifiedEmpty: result.verifiedEmpty,
          notEmpty: result.notEmpty,
          notFound: result.notFound,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch empty folders");
      setFolders([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load kept folders from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem("keptEmptyFolders");
      if (stored) {
        const kept = JSON.parse(stored) as string[];
        setKeptFolders(new Set(kept));
      }
    } catch {
      // Ignore localStorage errors
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchFolders();
  }, [fetchFolders]);

  // Assess a single folder
  const assessFolder = useCallback(async (folderPath: string) => {
    setLoadingFolders((prev) => new Set(prev).add(folderPath));

    try {
      const response = await fetch("/api/empty-folders/assess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folderPath }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error: ${response.status}`);
      }

      const result: AssessmentResponse = await response.json();

      if (result.error) {
        throw new Error(result.error);
      }

      if (result.assessment) {
        setAssessments((prev) => {
          const newMap = new Map(prev);
          newMap.set(folderPath, result.assessment!);
          return newMap;
        });
      }
    } catch (err) {
      console.error(`Failed to assess folder ${folderPath}:`, err);
      alert(`Failed to assess folder: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setLoadingFolders((prev) => {
        const newSet = new Set(prev);
        newSet.delete(folderPath);
        return newSet;
      });
    }
  }, []);

  // Placeholder handlers for restore/remove/keep (these would need actual API endpoints)
  const handleRestore = useCallback((folderPath: string) => {
    alert(`Restore functionality for "${folderPath}" is not yet implemented.\n\nThis would move files back to their original locations.`);
  }, []);

  const handleRemove = useCallback(async (folderPath: string) => {
    if (!confirm(`Are you sure you want to remove the folder "${folderPath}"?\n\nThis action cannot be undone.`)) {
      return;
    }

    setLoadingFolders((prev) => new Set(prev).add(folderPath));

    try {
      const response = await fetch("/api/empty-folders/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folderPaths: [folderPath] }),
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        const errorMsg = result.errors?.[0]?.error || result.error || "Failed to remove folder";
        throw new Error(errorMsg);
      }

      // Refresh the folder list
      await fetchFolders();
      
      // Remove from selection if selected
      setSelectedFolders((prev) => {
        const newSet = new Set(prev);
        newSet.delete(folderPath);
        return newSet;
      });
    } catch (err) {
      alert(`Failed to remove folder: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setLoadingFolders((prev) => {
        const newSet = new Set(prev);
        newSet.delete(folderPath);
        return newSet;
      });
    }
  }, [fetchFolders]);

  const handleKeep = useCallback((folderPath: string) => {
    // Mark folder as kept
    setKeptFolders((prev) => {
      const newSet = new Set(prev);
      newSet.add(folderPath);
      
      // Persist to localStorage
      try {
        localStorage.setItem("keptEmptyFolders", JSON.stringify(Array.from(newSet)));
      } catch {
        // Ignore localStorage errors
      }
      
      return newSet;
    });
    
    // Remove from selection if selected
    setSelectedFolders((prev) => {
      const newSet = new Set(prev);
      newSet.delete(folderPath);
      return newSet;
    });
    
    // Show feedback
    const folderName = folderPath.split("/").pop() || folderPath;
    alert(`✓ Folder "${folderName}" marked as kept.\n\nThe folder will remain for future use and won't be suggested for removal.`);
  }, []);
  
  const handleUnkeep = useCallback((folderPath: string) => {
    // Remove kept status
    setKeptFolders((prev) => {
      const newSet = new Set(prev);
      newSet.delete(folderPath);
      
      // Update localStorage
      try {
        localStorage.setItem("keptEmptyFolders", JSON.stringify(Array.from(newSet)));
      } catch {
        // Ignore localStorage errors
      }
      
      return newSet;
    });
  }, []);

  // Path click handler
  const handlePathClick = useCallback(async (path: string) => {
    const result = await openInFinder(path);

    if (result.success) {
      return;
    }

    // Fallback: copy path to clipboard
    const copied = await copyToClipboard(path);
    if (copied) {
      alert(`Could not open in Finder. Path copied to clipboard:\n${path}\n\nReason: ${result.error || result.message}`);
    } else {
      alert(`File path:\n${path}\n\nCould not open in Finder: ${result.error || result.message}`);
    }
  }, []);

  // Apply filter to folders (must be before handleSelectAll which uses it)
  const filteredFolders = useMemo(() => {
    switch (filter) {
      case "empty":
        return folders.filter((f) => f.isEmpty);
      case "not_empty":
        return folders.filter((f) => !f.isEmpty);
      case "assessed":
        return folders.filter((f) => assessments.has(f.folderPath));
      case "unassessed":
        return folders.filter((f) => !assessments.has(f.folderPath));
      default:
        return folders;
    }
  }, [folders, filter, assessments]);

  // Selection handlers
  const handleSelectFolder = useCallback((folderPath: string, selected: boolean) => {
    setSelectedFolders((prev) => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(folderPath);
      } else {
        newSet.delete(folderPath);
      }
      return newSet;
    });
  }, []);

  const handleSelectAll = useCallback(
    (selected: boolean) => {
      if (selected) {
        setSelectedFolders(new Set(filteredFolders.map((f) => f.folderPath)));
      } else {
        setSelectedFolders(new Set());
      }
    },
    [filteredFolders]
  );

  // Bulk action handlers
  const handleBulkAssess = useCallback(async () => {
    const foldersToAssess = Array.from(selectedFolders).filter(
      (path) => !assessments.has(path)
    );

    for (const folderPath of foldersToAssess) {
      await assessFolder(folderPath);
    }
  }, [selectedFolders, assessments, assessFolder]);

  const handleBulkRemove = useCallback(async () => {
    if (selectedFolders.size === 0) return;

    if (!confirm(`Are you sure you want to remove ${selectedFolders.size} folder(s)?\n\nThis action cannot be undone.`)) {
      return;
    }

    const foldersToRemove = Array.from(selectedFolders);
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/empty-folders/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folderPaths: foldersToRemove }),
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        const errorMsg = result.error || `Failed to remove ${result.failed} folder(s)`;
        const errorDetails = result.errors?.map((e: any) => `- ${e.folderPath}: ${e.error}`).join("\n") || "";
        throw new Error(`${errorMsg}\n\n${errorDetails}`);
      }

      // Refresh the folder list
      await fetchFolders();
      
      // Clear selection
      setSelectedFolders(new Set());

      // Show success message
      alert(`Successfully removed ${result.removed} folder(s).${result.failed > 0 ? `\n\nFailed to remove ${result.failed} folder(s).` : ""}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove folders");
    } finally {
      setIsLoading(false);
    }
  }, [selectedFolders, fetchFolders]);

  const handleBulkRestore = useCallback(() => {
    if (selectedFolders.size === 0) return;

    alert(`Bulk restore functionality is not yet implemented.\n\nThis would restore files to ${selectedFolders.size} folders.`);
  }, [selectedFolders]);

  const handleClearSelection = useCallback(() => {
    setSelectedFolders(new Set());
  }, []);

  // Calculate filter counts
  const filterCounts = useMemo(() => {
    return {
      all: folders.length,
      empty: folders.filter((f) => f.isEmpty).length,
      notEmpty: folders.filter((f) => !f.isEmpty).length,
      assessed: folders.filter((f) => assessments.has(f.folderPath)).length,
      unassessed: folders.filter((f) => !assessments.has(f.folderPath)).length,
    };
  }, [folders, assessments]);

  // Check if any bulk action is loading
  const isBulkLoading = loadingFolders.size > 0;

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

      <h1 className="text-3xl font-bold mb-2">Empty Folders</h1>
      <p className="text-neutral-600 mb-6">
        Manage folders that became empty after file consolidation. Assess each folder to determine if files should be restored or if the folder should be removed.
      </p>

      {/* Error Message */}
      {error && !isLoading && (
        <ErrorDisplay
          message={error}
          onRetry={fetchFolders}
          className="mb-6"
        />
      )}

      {/* Loading State */}
      {isLoading && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </div>
          <EmptyFolderListSkeleton count={5} />
        </>
      )}

      {/* Content */}
      {!isLoading && !error && (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white border border-neutral-200 rounded-lg p-4">
              <div className="text-2xl font-bold text-neutral-800">{folders.length}</div>
              <div className="text-sm text-neutral-600">Total Folders</div>
            </div>
            <div className="bg-white border border-neutral-200 rounded-lg p-4">
              <div className="text-2xl font-bold text-green-600">{stats.verifiedEmpty}</div>
              <div className="text-sm text-neutral-600">Verified Empty</div>
            </div>
            <div className="bg-white border border-neutral-200 rounded-lg p-4">
              <div className="text-2xl font-bold text-yellow-600">{stats.notEmpty}</div>
              <div className="text-sm text-neutral-600">Not Empty</div>
            </div>
            <div className="bg-white border border-neutral-200 rounded-lg p-4">
              <div className="text-2xl font-bold text-blue-600">{filterCounts.assessed}</div>
              <div className="text-sm text-neutral-600">Assessed</div>
            </div>
          </div>

          {/* Filter Tabs */}
          <div className="mb-4">
            <EmptyFoldersFilter
              filter={filter}
              onFilterChange={setFilter}
              counts={filterCounts}
            />
          </div>

          {/* Bulk Actions Bar */}
          <BulkActionsBar
            selectedCount={selectedFolders.size}
            onAssessAll={handleBulkAssess}
            onRestoreAll={handleBulkRestore}
            onRemoveAll={handleBulkRemove}
            onClearSelection={handleClearSelection}
            isLoading={isBulkLoading}
          />

          {/* Results Count */}
          <div className="mb-4 text-sm text-neutral-600">
            Showing <span className="font-semibold">{filteredFolders.length}</span> folder
            {filteredFolders.length !== 1 ? "s" : ""}
            {filteredFolders.length !== folders.length && (
              <span className="text-neutral-400"> (filtered from {folders.length} total)</span>
            )}
          </div>

          {/* Folders List */}
          <EmptyFoldersList
            folders={filteredFolders}
            assessments={assessments}
            selectedFolders={selectedFolders}
            loadingFolders={loadingFolders}
            keptFolders={keptFolders}
            onSelectFolder={handleSelectFolder}
            onSelectAll={handleSelectAll}
            onAssessFolder={assessFolder}
            onRestoreFolder={handleRestore}
            onRemoveFolder={handleRemove}
            onKeepFolder={handleKeep}
            onUnkeepFolder={handleUnkeep}
            onPathClick={handlePathClick}
          />
        </>
      )}
    </main>
  );
}
