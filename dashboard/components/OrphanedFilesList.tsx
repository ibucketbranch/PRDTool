"use client";

import { cn } from "@/lib/utils";
import { OrphanedFileCard } from "./OrphanedFileCard";
import { HelpTooltip, HELP_TEXT } from "./Tooltip";
import type { OrphanedFileInfo, EnhancedLocationSuggestion } from "@/lib/supabase";

export interface OrphanedFilesListProps {
  files: OrphanedFileInfo[];
  suggestions: Map<string, EnhancedLocationSuggestion>;
  selectedFiles: Set<string>;
  loadingFiles: Set<string>;
  onSelectFile: (filePath: string, selected: boolean) => void;
  onSelectAll: (selected: boolean) => void;
  onAnalyzeFile: (filePath: string) => void;
  onMoveFile: (filePath: string, targetPath: string) => void;
  onPathClick: (path: string) => void;
  className?: string;
}

/**
 * Filter options for orphaned files list
 */
export type OrphanedFileFilterType = "all" | "with_suggestion" | "without_suggestion" | "high_confidence" | "low_confidence";

export interface OrphanedFilesFilterProps {
  filter: OrphanedFileFilterType;
  onFilterChange: (filter: OrphanedFileFilterType) => void;
  counts: {
    all: number;
    withSuggestion: number;
    withoutSuggestion: number;
    highConfidence: number;
    lowConfidence: number;
  };
}

export function OrphanedFilesFilter({
  filter,
  onFilterChange,
  counts,
}: OrphanedFilesFilterProps) {
  const filters: { value: OrphanedFileFilterType; label: string; count: number }[] = [
    { value: "all", label: "All", count: counts.all },
    { value: "with_suggestion", label: "With Suggestion", count: counts.withSuggestion },
    { value: "without_suggestion", label: "Needs Analysis", count: counts.withoutSuggestion },
    { value: "high_confidence", label: "High Confidence", count: counts.highConfidence },
    { value: "low_confidence", label: "Low Confidence", count: counts.lowConfidence },
  ];

  return (
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
  );
}

/**
 * Bulk action bar for selected orphaned files
 */
export interface OrphanedFilesBulkActionsBarProps {
  selectedCount: number;
  onAnalyzeAll: () => void;
  onMoveAll: () => void;
  onClearSelection: () => void;
  isLoading: boolean;
}

export function OrphanedFilesBulkActionsBar({
  selectedCount,
  onAnalyzeAll,
  onMoveAll,
  onClearSelection,
  isLoading,
}: OrphanedFilesBulkActionsBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 gap-3">
      <div className="text-sm text-blue-700">
        <span className="font-semibold">{selectedCount}</span> file
        {selectedCount !== 1 ? "s" : ""} selected
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={onAnalyzeAll}
          disabled={isLoading}
          className={cn(
            "px-3 py-1.5 text-sm rounded transition-colors flex-1 sm:flex-none",
            isLoading
              ? "bg-neutral-200 text-neutral-400 cursor-not-allowed"
              : "bg-white text-neutral-700 border border-neutral-300 hover:bg-neutral-50"
          )}
        >
          Analyze All
        </button>
        <button
          onClick={onMoveAll}
          disabled={isLoading}
          className={cn(
            "px-3 py-1.5 text-sm rounded transition-colors flex-1 sm:flex-none",
            isLoading
              ? "bg-green-200 text-green-400 cursor-not-allowed"
              : "bg-green-600 text-white hover:bg-green-700"
          )}
        >
          Move All to Suggested
        </button>
        <button
          onClick={onClearSelection}
          className="px-3 py-1.5 text-sm text-neutral-600 hover:text-neutral-800 w-full sm:w-auto text-center"
        >
          Clear selection
        </button>
      </div>
    </div>
  );
}

export function OrphanedFilesList({
  files,
  suggestions,
  selectedFiles,
  loadingFiles,
  onSelectFile,
  onSelectAll,
  onAnalyzeFile,
  onMoveFile,
  onPathClick,
  className,
}: OrphanedFilesListProps) {
  if (files.length === 0) {
    return (
      <div className={cn("text-center py-12 bg-neutral-50 rounded-lg border border-neutral-200", className)}>
        <p className="text-neutral-500 mb-2">No orphaned files found</p>
        <p className="text-sm text-neutral-400">
          Files that exist on disk but are not tracked in the database will appear here
        </p>
      </div>
    );
  }

  const allSelected = files.every((f) => selectedFiles.has(f.filePath));
  const someSelected = files.some((f) => selectedFiles.has(f.filePath));

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
        <HelpTooltip text={HELP_TEXT.bulkSelect} size={14} />
      </div>

      {/* File Cards */}
      {files.map((file) => (
        <OrphanedFileCard
          key={file.filePath}
          file={file}
          suggestion={suggestions.get(file.filePath) || null}
          isSelected={selectedFiles.has(file.filePath)}
          isLoading={loadingFiles.has(file.filePath)}
          onSelect={onSelectFile}
          onAnalyze={onAnalyzeFile}
          onMove={onMoveFile}
          onPathClick={onPathClick}
        />
      ))}
    </div>
  );
}
