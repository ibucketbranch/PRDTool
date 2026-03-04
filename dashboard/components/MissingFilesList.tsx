"use client";

import { cn } from "@/lib/utils";
import { MissingFileCard } from "./MissingFileCard";
import type { MissingFileInfo, OriginalLocationResult } from "@/lib/supabase";

export interface MissingFilesListProps {
  files: MissingFileInfo[];
  originalLocations: Map<string, OriginalLocationResult>;
  selectedFiles: Set<string>;
  loadingFiles: Set<string>;
  onSelectFile: (documentId: string, selected: boolean) => void;
  onSelectAll: (selected: boolean) => void;
  onGetOriginal: (documentId: string) => void;
  onRestoreFile: (documentId: string, targetPath: string) => void;
  onUpdatePath: (documentId: string, newPath: string) => void;
  onRemoveFile: (documentId: string) => void;
  onMarkInaccessible: (documentId: string) => void;
  onPathClick: (path: string) => void;
  className?: string;
}

/**
 * Filter options for missing files list
 */
export type MissingFileFilterType = "all" | "with_original" | "without_original" | "by_category";

export interface MissingFilesFilterProps {
  filter: MissingFileFilterType;
  onFilterChange: (filter: MissingFileFilterType) => void;
  counts: {
    all: number;
    withOriginal: number;
    withoutOriginal: number;
  };
  categories?: string[];
  selectedCategory?: string;
  onCategoryChange?: (category: string | undefined) => void;
}

export function MissingFilesFilter({
  filter,
  onFilterChange,
  counts,
  categories,
  selectedCategory,
  onCategoryChange,
}: MissingFilesFilterProps) {
  const filters: { value: MissingFileFilterType; label: string; count: number }[] = [
    { value: "all", label: "All", count: counts.all },
    { value: "with_original", label: "Has Original", count: counts.withOriginal },
    { value: "without_original", label: "No Original", count: counts.withoutOriginal },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {filters.map((f) => (
          <button
            key={f.value}
            onClick={() => onFilterChange(f.value)}
            className={cn(
              "px-3 py-1.5 text-sm rounded-full transition-colors",
              filter === f.value
                ? "bg-blue-600 text-white"
                : "bg-neutral-100 text-neutral-700 hover:bg-neutral-200"
            )}
          >
            {f.label} ({f.count})
          </button>
        ))}
      </div>

      {/* Category Filter */}
      {categories && categories.length > 0 && onCategoryChange && (
        <div className="flex items-center gap-2">
          <label className="text-sm text-neutral-600">Category:</label>
          <select
            value={selectedCategory || ""}
            onChange={(e) => onCategoryChange(e.target.value || undefined)}
            className="px-2 py-1 text-sm border border-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}

/**
 * Bulk action bar for selected missing files
 */
export interface MissingFilesBulkActionsBarProps {
  selectedCount: number;
  onGetOriginalAll: () => void;
  onRestoreAll: () => void;
  onRemoveAll: () => void;
  onMarkInaccessibleAll: () => void;
  onClearSelection: () => void;
  isLoading: boolean;
}

export function MissingFilesBulkActionsBar({
  selectedCount,
  onGetOriginalAll,
  onRestoreAll,
  onRemoveAll,
  onMarkInaccessibleAll,
  onClearSelection,
  isLoading,
}: MissingFilesBulkActionsBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div className="flex items-center justify-between bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
      <div className="text-sm text-blue-700">
        <span className="font-semibold">{selectedCount}</span> file
        {selectedCount !== 1 ? "s" : ""} selected
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onGetOriginalAll}
          disabled={isLoading}
          className={cn(
            "px-3 py-1.5 text-sm rounded transition-colors",
            isLoading
              ? "bg-neutral-200 text-neutral-400 cursor-not-allowed"
              : "bg-white text-neutral-700 border border-neutral-300 hover:bg-neutral-50"
          )}
        >
          Get Originals
        </button>
        <button
          onClick={onRestoreAll}
          disabled={isLoading}
          className={cn(
            "px-3 py-1.5 text-sm rounded transition-colors",
            isLoading
              ? "bg-green-200 text-green-400 cursor-not-allowed"
              : "bg-green-600 text-white hover:bg-green-700"
          )}
        >
          Restore All
        </button>
        <button
          onClick={onMarkInaccessibleAll}
          disabled={isLoading}
          className={cn(
            "px-3 py-1.5 text-sm rounded transition-colors",
            isLoading
              ? "bg-yellow-200 text-yellow-400 cursor-not-allowed"
              : "bg-yellow-500 text-white hover:bg-yellow-600"
          )}
        >
          Mark Inaccessible
        </button>
        <button
          onClick={onRemoveAll}
          disabled={isLoading}
          className={cn(
            "px-3 py-1.5 text-sm rounded transition-colors",
            isLoading
              ? "bg-red-200 text-red-400 cursor-not-allowed"
              : "bg-red-600 text-white hover:bg-red-700"
          )}
        >
          Remove All
        </button>
        <button
          onClick={onClearSelection}
          className="px-3 py-1.5 text-sm text-neutral-600 hover:text-neutral-800"
        >
          Clear selection
        </button>
      </div>
    </div>
  );
}

export function MissingFilesList({
  files,
  originalLocations,
  selectedFiles,
  loadingFiles,
  onSelectFile,
  onSelectAll,
  onGetOriginal,
  onRestoreFile,
  onUpdatePath,
  onRemoveFile,
  onMarkInaccessible,
  onPathClick,
  className,
}: MissingFilesListProps) {
  if (files.length === 0) {
    return (
      <div className={cn("text-center py-12 bg-neutral-50 rounded-lg border border-neutral-200", className)}>
        <p className="text-neutral-500 mb-2">No missing files found</p>
        <p className="text-sm text-neutral-400">
          Files tracked in the database but not found at their recorded paths will appear here
        </p>
      </div>
    );
  }

  const allSelected = files.every((f) => selectedFiles.has(f.documentId));
  const someSelected = files.some((f) => selectedFiles.has(f.documentId));

  return (
    <div className={cn("space-y-4", className)}>
      {/* Select All Header */}
      <div className="flex items-center gap-3 pb-2 border-b border-neutral-200">
        <input
          type="checkbox"
          checked={allSelected}
          ref={(el) => {
            if (el) {
              el.indeterminate = someSelected && !allSelected;
            }
          }}
          onChange={(e) => onSelectAll(e.target.checked)}
          className="h-4 w-4 rounded border-neutral-300 text-blue-600 focus:ring-blue-500"
          aria-label="Select all files"
        />
        <span className="text-sm text-neutral-600">
          {allSelected
            ? "Deselect all"
            : someSelected
            ? `${selectedFiles.size} selected`
            : "Select all"}
        </span>
      </div>

      {/* File Cards */}
      {files.map((file) => (
        <MissingFileCard
          key={file.documentId}
          file={file}
          originalLocation={originalLocations.get(file.documentId) || null}
          isSelected={selectedFiles.has(file.documentId)}
          isLoading={loadingFiles.has(file.documentId)}
          onSelect={onSelectFile}
          onGetOriginal={onGetOriginal}
          onRestore={onRestoreFile}
          onUpdatePath={onUpdatePath}
          onRemove={onRemoveFile}
          onMarkInaccessible={onMarkInaccessible}
          onPathClick={onPathClick}
        />
      ))}
    </div>
  );
}
