"use client";

import { cn } from "@/lib/utils";
import { EmptyFolderCard } from "./EmptyFolderCard";
import type { EmptyFolderInfo, FolderAssessment } from "@/lib/supabase";

export interface EmptyFoldersListProps {
  folders: EmptyFolderInfo[];
  assessments: Map<string, FolderAssessment>;
  selectedFolders: Set<string>;
  loadingFolders: Set<string>;
  keptFolders?: Set<string>;
  onSelectFolder: (folderPath: string, selected: boolean) => void;
  onSelectAll: (selected: boolean) => void;
  onAssessFolder: (folderPath: string) => void;
  onRestoreFolder: (folderPath: string) => void;
  onRemoveFolder: (folderPath: string) => void;
  onKeepFolder: (folderPath: string) => void;
  onUnkeepFolder?: (folderPath: string) => void;
  onPathClick: (path: string) => void;
  className?: string;
}

/**
 * Filter options for empty folders list
 */
export type EmptyFolderFilterType = "all" | "empty" | "not_empty" | "assessed" | "unassessed";

export interface EmptyFoldersFilterProps {
  filter: EmptyFolderFilterType;
  onFilterChange: (filter: EmptyFolderFilterType) => void;
  counts: {
    all: number;
    empty: number;
    notEmpty: number;
    assessed: number;
    unassessed: number;
  };
}

export function EmptyFoldersFilter({
  filter,
  onFilterChange,
  counts,
}: EmptyFoldersFilterProps) {
  const filters: { value: EmptyFolderFilterType; label: string; count: number }[] = [
    { value: "all", label: "All", count: counts.all },
    { value: "empty", label: "Empty", count: counts.empty },
    { value: "not_empty", label: "Not Empty", count: counts.notEmpty },
    { value: "assessed", label: "Assessed", count: counts.assessed },
    { value: "unassessed", label: "Unassessed", count: counts.unassessed },
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
 * Bulk action bar for selected folders
 */
export interface BulkActionsBarProps {
  selectedCount: number;
  onRemoveAll: () => void;
  onRestoreAll: () => void;
  onAssessAll: () => void;
  onClearSelection: () => void;
  isLoading: boolean;
}

export function BulkActionsBar({
  selectedCount,
  onRemoveAll,
  onRestoreAll,
  onAssessAll,
  onClearSelection,
  isLoading,
}: BulkActionsBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 gap-3">
      <div className="text-sm text-blue-700">
        <span className="font-semibold">{selectedCount}</span> folder
        {selectedCount !== 1 ? "s" : ""} selected
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={onAssessAll}
          disabled={isLoading}
          className={cn(
            "px-3 py-1.5 text-sm rounded transition-colors flex-1 sm:flex-none",
            isLoading
              ? "bg-neutral-200 text-neutral-400 cursor-not-allowed"
              : "bg-white text-neutral-700 border border-neutral-300 hover:bg-neutral-50"
          )}
        >
          Assess All
        </button>
        <button
          onClick={onRestoreAll}
          disabled={isLoading}
          className={cn(
            "px-3 py-1.5 text-sm rounded transition-colors flex-1 sm:flex-none",
            isLoading
              ? "bg-green-200 text-green-400 cursor-not-allowed"
              : "bg-green-600 text-white hover:bg-green-700"
          )}
        >
          Restore All
        </button>
        <button
          onClick={onRemoveAll}
          disabled={isLoading}
          className={cn(
            "px-3 py-1.5 text-sm rounded transition-colors flex-1 sm:flex-none",
            isLoading
              ? "bg-red-200 text-red-400 cursor-not-allowed"
              : "bg-red-600 text-white hover:bg-red-700"
          )}
        >
          Remove All
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

export function EmptyFoldersList({
  folders,
  assessments,
  selectedFolders,
  loadingFolders,
  keptFolders = new Set(),
  onSelectFolder,
  onSelectAll,
  onAssessFolder,
  onRestoreFolder,
  onRemoveFolder,
  onKeepFolder,
  onUnkeepFolder,
  onPathClick,
  className,
}: EmptyFoldersListProps) {
  if (folders.length === 0) {
    return (
      <div className={cn("text-center py-12 bg-neutral-50 rounded-lg border border-neutral-200", className)}>
        <p className="text-neutral-500 mb-2">No empty folders found</p>
        <p className="text-sm text-neutral-400">
          Folders that had files moved during consolidation will appear here
        </p>
      </div>
    );
  }

  const allSelected = folders.every((f) => selectedFolders.has(f.folderPath));
  const someSelected = folders.some((f) => selectedFolders.has(f.folderPath));

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
          aria-label="Select all folders"
        />
        <span className="text-sm text-neutral-600">
          {allSelected
            ? "Deselect all"
            : someSelected
            ? `${selectedFolders.size} selected`
            : "Select all"}
        </span>
      </div>

      {/* Folder Cards */}
      {folders.map((folder) => (
        <EmptyFolderCard
          key={folder.folderPath}
          folder={folder}
          assessment={assessments.get(folder.folderPath) || null}
          isSelected={selectedFolders.has(folder.folderPath)}
          isLoading={loadingFolders.has(folder.folderPath)}
          isKept={keptFolders.has(folder.folderPath)}
          onSelect={onSelectFolder}
          onAssess={onAssessFolder}
          onRestore={onRestoreFolder}
          onRemove={onRemoveFolder}
          onKeep={onKeepFolder}
          onUnkeep={onUnkeepFolder}
          onPathClick={onPathClick}
        />
      ))}
    </div>
  );
}
