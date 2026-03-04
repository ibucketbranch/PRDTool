"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { MissingFileInfo, OriginalLocationResult } from "@/lib/supabase";

export interface MissingFileCardProps {
  file: MissingFileInfo;
  originalLocation: OriginalLocationResult | null;
  isSelected: boolean;
  isLoading: boolean;
  onSelect: (documentId: string, selected: boolean) => void;
  onGetOriginal: (documentId: string) => void;
  onRestore: (documentId: string, targetPath: string) => void;
  onUpdatePath: (documentId: string, newPath: string) => void;
  onRemove: (documentId: string) => void;
  onMarkInaccessible: (documentId: string) => void;
  onPathClick: (path: string) => void;
  className?: string;
}

/**
 * Format a date string for display
 */
function formatDate(dateStr: string | null): string {
  if (!dateStr) return "-";
  try {
    return new Date(dateStr).toLocaleDateString();
  } catch {
    return dateStr;
  }
}

/**
 * Truncate path for display
 */
function truncatePath(path: string, maxLength: number = 60): string {
  if (path.length <= maxLength) return path;
  const start = path.slice(0, 25);
  const end = path.slice(-32);
  return `${start}...${end}`;
}

/**
 * Get location type badge
 */
function getLocationTypeBadge(locationType: string): {
  color: string;
  text: string;
} {
  switch (locationType) {
    case "primary":
      return { color: "bg-green-100 text-green-700", text: "Primary" };
    case "previous":
      return { color: "bg-yellow-100 text-yellow-700", text: "Previous" };
    case "current":
      return { color: "bg-blue-100 text-blue-700", text: "Current" };
    default:
      return { color: "bg-neutral-100 text-neutral-600", text: locationType };
  }
}

export function MissingFileCard({
  file,
  originalLocation,
  isSelected,
  isLoading,
  onSelect,
  onGetOriginal,
  onRestore,
  onUpdatePath,
  onRemove,
  onMarkInaccessible,
  onPathClick,
  className,
}: MissingFileCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showUpdatePath, setShowUpdatePath] = useState(false);
  const [newPath, setNewPath] = useState("");

  const hasOriginalPath = originalLocation?.originalPath;
  const hasLocationHistory = originalLocation?.locationHistory && originalLocation.locationHistory.length > 0;

  return (
    <div
      className={cn(
        "border rounded-lg p-4 transition-colors",
        isSelected ? "border-blue-500 bg-blue-50" : "border-neutral-200 bg-white",
        className
      )}
    >
      {/* Header Row */}
      <div className="flex items-start gap-3">
        {/* Selection Checkbox */}
        <input
          type="checkbox"
          checked={isSelected}
          onChange={(e) => onSelect(file.documentId, e.target.checked)}
          className="mt-1 h-4 w-4 rounded border-neutral-300 text-blue-600 focus:ring-blue-500"
          aria-label={`Select ${file.fileName}`}
        />

        {/* File Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {/* File Name */}
            <h3 className="font-semibold text-neutral-800">{file.fileName}</h3>

            {/* Category Badge */}
            {file.aiCategory && (
              <span className="text-xs px-2 py-0.5 rounded bg-purple-100 text-purple-700">
                {file.aiCategory}
              </span>
            )}

            {/* Accessibility Badge */}
            <span
              className={cn(
                "text-xs px-2 py-0.5 rounded",
                file.isAccessible
                  ? "bg-green-100 text-green-700"
                  : "bg-red-100 text-red-700"
              )}
            >
              {file.isAccessible ? "Accessible" : "Missing"}
            </span>
          </div>

          {/* Current Path (missing) */}
          <div className="mt-1">
            <span className="text-xs text-neutral-500">Missing at: </span>
            <button
              onClick={() => onPathClick(file.currentPath)}
              className="text-sm text-red-600 hover:text-red-800 hover:underline text-left line-through"
              title={file.currentPath}
            >
              {truncatePath(file.currentPath)}
            </button>
          </div>

          {/* Original Path (if available) */}
          {file.originalPath && (
            <div className="mt-1">
              <span className="text-xs text-neutral-500">Original: </span>
              <button
                onClick={() => onPathClick(file.originalPath!)}
                className="text-sm text-blue-600 hover:text-blue-800 hover:underline text-left"
                title={file.originalPath}
              >
                {truncatePath(file.originalPath)}
              </button>
            </div>
          )}

          {/* Last Known Location */}
          {file.lastKnownLocation && file.lastKnownLocation !== file.originalPath && (
            <div className="mt-1">
              <span className="text-xs text-neutral-500">Last known: </span>
              <button
                onClick={() => onPathClick(file.lastKnownLocation!)}
                className="text-sm text-neutral-600 hover:text-neutral-800 hover:underline text-left"
                title={file.lastKnownLocation}
              >
                {truncatePath(file.lastKnownLocation)}
              </button>
            </div>
          )}

          {/* Location History (collapsible) */}
          {hasLocationHistory && (
            <div className="mt-3">
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="text-sm text-neutral-500 hover:text-neutral-700 flex items-center gap-1"
              >
                <svg
                  className={cn("w-4 h-4 transition-transform", isExpanded && "rotate-90")}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                {isExpanded ? "Hide" : "Show"} location history ({originalLocation!.locationHistory.length})
              </button>

              {isExpanded && (
                <div className="mt-2 space-y-2">
                  {originalLocation!.locationHistory.map((loc, idx) => {
                    const badge = getLocationTypeBadge(loc.locationType);
                    return (
                      <div
                        key={idx}
                        className="text-sm bg-neutral-50 rounded p-2 border border-neutral-100"
                      >
                        <div className="flex items-center gap-2">
                          <span className={cn("text-xs px-1.5 py-0.5 rounded", badge.color)}>
                            {badge.text}
                          </span>
                          <span
                            className={cn(
                              "text-xs",
                              loc.isAccessible ? "text-green-600" : "text-red-600"
                            )}
                          >
                            {loc.isAccessible ? "Accessible" : "Inaccessible"}
                          </span>
                        </div>
                        <button
                          onClick={() => onPathClick(loc.path)}
                          className="text-blue-600 hover:underline text-left mt-1 block"
                          title={loc.path}
                        >
                          {truncatePath(loc.path, 50)}
                        </button>
                        <div className="text-xs text-neutral-400 mt-1">
                          {formatDate(loc.createdAt)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Update Path Form */}
          {showUpdatePath && (
            <div className="mt-3 p-3 bg-neutral-50 rounded-lg border border-neutral-200">
              <label className="text-sm text-neutral-600 block mb-2">
                Enter new path:
              </label>
              <input
                type="text"
                value={newPath}
                onChange={(e) => setNewPath(e.target.value)}
                placeholder="/path/to/file"
                className="w-full px-3 py-2 text-sm border border-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <div className="flex gap-2 mt-2">
                <button
                  onClick={() => {
                    if (newPath.trim()) {
                      onUpdatePath(file.documentId, newPath.trim());
                      setShowUpdatePath(false);
                      setNewPath("");
                    }
                  }}
                  disabled={!newPath.trim() || isLoading}
                  className={cn(
                    "px-3 py-1.5 text-sm rounded transition-colors",
                    !newPath.trim() || isLoading
                      ? "bg-blue-200 text-blue-400 cursor-not-allowed"
                      : "bg-blue-600 text-white hover:bg-blue-700"
                  )}
                >
                  Update
                </button>
                <button
                  onClick={() => {
                    setShowUpdatePath(false);
                    setNewPath("");
                  }}
                  className="px-3 py-1.5 text-sm text-neutral-600 hover:text-neutral-800"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col gap-2">
          {!originalLocation && (
            <button
              onClick={() => onGetOriginal(file.documentId)}
              disabled={isLoading}
              className={cn(
                "px-3 py-1.5 text-sm rounded border transition-colors",
                isLoading
                  ? "bg-neutral-100 text-neutral-400 border-neutral-200 cursor-not-allowed"
                  : "bg-white text-neutral-700 border-neutral-300 hover:bg-neutral-50"
              )}
            >
              {isLoading ? "Loading..." : "Get Original"}
            </button>
          )}

          {hasOriginalPath && (
            <button
              onClick={() => onRestore(file.documentId, originalLocation!.originalPath!)}
              disabled={isLoading}
              className={cn(
                "px-3 py-1.5 text-sm rounded transition-colors",
                isLoading
                  ? "bg-green-200 text-green-400 cursor-not-allowed"
                  : "bg-green-600 text-white hover:bg-green-700"
              )}
            >
              Restore to Original
            </button>
          )}

          <button
            onClick={() => setShowUpdatePath(!showUpdatePath)}
            disabled={isLoading}
            className={cn(
              "px-3 py-1.5 text-sm rounded border transition-colors",
              isLoading
                ? "bg-neutral-100 text-neutral-400 border-neutral-200 cursor-not-allowed"
                : "bg-white text-neutral-700 border-neutral-300 hover:bg-neutral-50"
            )}
          >
            Update Path
          </button>

          <button
            onClick={() => onMarkInaccessible(file.documentId)}
            disabled={isLoading}
            className={cn(
              "px-3 py-1.5 text-sm rounded border transition-colors",
              isLoading
                ? "bg-yellow-100 text-yellow-400 border-yellow-200 cursor-not-allowed"
                : "bg-yellow-50 text-yellow-700 border-yellow-300 hover:bg-yellow-100"
            )}
          >
            Mark Inaccessible
          </button>

          <button
            onClick={() => onRemove(file.documentId)}
            disabled={isLoading}
            className={cn(
              "px-3 py-1.5 text-sm rounded transition-colors",
              isLoading
                ? "bg-red-200 text-red-400 cursor-not-allowed"
                : "bg-red-600 text-white hover:bg-red-700"
            )}
          >
            Remove from DB
          </button>
        </div>
      </div>
    </div>
  );
}
