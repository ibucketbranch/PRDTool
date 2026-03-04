"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { EmptyFolderInfo, FolderAssessment, MovedFileInfo } from "@/lib/supabase";

export interface EmptyFolderCardProps {
  folder: EmptyFolderInfo;
  assessment: FolderAssessment | null;
  isSelected: boolean;
  isLoading: boolean;
  isKept?: boolean;
  onSelect: (folderPath: string, selected: boolean) => void;
  onAssess: (folderPath: string) => void;
  onRestore: (folderPath: string) => void;
  onRemove: (folderPath: string) => void;
  onKeep: (folderPath: string) => void;
  onUnkeep?: (folderPath: string) => void;
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
 * Get the assessment badge color and text
 */
function getAssessmentBadge(assessment: FolderAssessment | null): {
  color: string;
  text: string;
  icon: string;
} {
  if (!assessment) {
    return { color: "bg-neutral-100 text-neutral-600", text: "Not assessed", icon: "?" };
  }

  switch (assessment.assessment) {
    case "correct":
      return { color: "bg-green-100 text-green-700", text: "Correct Location", icon: "✓" };
    case "incorrect":
      return { color: "bg-red-100 text-red-700", text: "Incorrect Location", icon: "✗" };
    case "duplicate":
      return { color: "bg-yellow-100 text-yellow-700", text: "Duplicate/Misnamed", icon: "⚠" };
    default:
      return { color: "bg-neutral-100 text-neutral-600", text: "Unknown", icon: "?" };
  }
}

/**
 * Get the suggested action badge
 */
function getSuggestedActionBadge(assessment: FolderAssessment | null): {
  color: string;
  text: string;
} | null {
  if (!assessment) return null;

  switch (assessment.suggestedAction) {
    case "restore":
      return { color: "text-green-600", text: "Suggested: Restore files" };
    case "remove":
      return { color: "text-red-600", text: "Suggested: Remove folder" };
    case "keep":
      return { color: "text-blue-600", text: "Suggested: Keep folder" };
    case "review":
      return { color: "text-yellow-600", text: "Suggested: Manual review" };
    default:
      return null;
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
 * Extract folder name from path
 */
function getFolderName(path: string): string {
  const parts = path.split("/").filter(Boolean);
  return parts[parts.length - 1] || path;
}

export function EmptyFolderCard({
  folder,
  assessment,
  isSelected,
  isLoading,
  isKept = false,
  onSelect,
  onAssess,
  onRestore,
  onRemove,
  onKeep,
  onUnkeep,
  onPathClick,
  className,
}: EmptyFolderCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const assessmentBadge = getAssessmentBadge(assessment);
  const suggestedAction = getSuggestedActionBadge(assessment);
  const folderName = getFolderName(folder.folderPath);

  // Determine filesystem status badge
  const filesystemBadge = folder.isEmpty
    ? { color: "bg-green-100 text-green-700", text: "Empty" }
    : { color: "bg-yellow-100 text-yellow-700", text: "Not Empty" };

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
          onChange={(e) => onSelect(folder.folderPath, e.target.checked)}
          className="mt-1 h-4 w-4 rounded border-neutral-300 text-blue-600 focus:ring-blue-500"
          aria-label={`Select ${folderName}`}
        />

        {/* Folder Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {/* Folder Name */}
            <h3 className="font-semibold text-neutral-800">{folderName}</h3>
            
            {/* Kept Badge */}
            {isKept && (
              <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-700 border border-blue-200">
                ✓ Kept
              </span>
            )}

            {/* Filesystem Status */}
            <span className={cn("text-xs px-2 py-0.5 rounded", filesystemBadge.color)}>
              {filesystemBadge.text}
            </span>

            {/* Assessment Badge */}
            <span className={cn("text-xs px-2 py-0.5 rounded flex items-center gap-1", assessmentBadge.color)}>
              <span>{assessmentBadge.icon}</span>
              {assessmentBadge.text}
            </span>
          </div>

          {/* Path */}
          <button
            onClick={() => onPathClick(folder.folderPath)}
            className="text-sm text-blue-600 hover:text-blue-800 hover:underline text-left mt-1"
            title={folder.folderPath}
          >
            {truncatePath(folder.folderPath)}
          </button>

          {/* Stats */}
          <div className="flex items-center gap-4 mt-2 text-sm text-neutral-600">
            <span>
              <span className="font-medium">{folder.originalFileCount}</span> file
              {folder.originalFileCount !== 1 ? "s" : ""} moved
            </span>
            {folder.lastMoveDate && (
              <span>Last moved: {formatDate(folder.lastMoveDate)}</span>
            )}
            {assessment?.dominantCategory && (
              <span>
                Category:{" "}
                <span className="font-medium">{assessment.dominantCategory}</span>
              </span>
            )}
          </div>

          {/* Suggested Action */}
          {suggestedAction && (
            <div className={cn("text-sm mt-1", suggestedAction.color)}>
              {suggestedAction.text}
            </div>
          )}

          {/* Assessment Reasoning (collapsed by default) */}
          {assessment && assessment.reasoning.length > 0 && (
            <div className="mt-2">
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
                {isExpanded ? "Hide" : "Show"} reasoning ({assessment.reasoning.length})
              </button>

              {isExpanded && (
                <ul className="mt-2 ml-5 text-sm text-neutral-600 list-disc space-y-1">
                  {assessment.reasoning.map((reason, idx) => (
                    <li key={idx}>{reason}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Moved Files (collapsed by default) */}
          {folder.movedFiles.length > 0 && (
            <MovedFilesList
              files={folder.movedFiles}
              onPathClick={onPathClick}
            />
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col gap-2">
          {!assessment && (
            <button
              onClick={() => onAssess(folder.folderPath)}
              disabled={isLoading}
              className={cn(
                "px-3 py-1.5 text-sm rounded border transition-colors",
                isLoading
                  ? "bg-neutral-100 text-neutral-400 border-neutral-200 cursor-not-allowed"
                  : "bg-white text-neutral-700 border-neutral-300 hover:bg-neutral-50"
              )}
            >
              {isLoading ? "Assessing..." : "Assess"}
            </button>
          )}

          {assessment?.suggestedAction === "restore" && (
            <button
              onClick={() => onRestore(folder.folderPath)}
              disabled={isLoading}
              className={cn(
                "px-3 py-1.5 text-sm rounded transition-colors",
                isLoading
                  ? "bg-green-200 text-green-400 cursor-not-allowed"
                  : "bg-green-600 text-white hover:bg-green-700"
              )}
            >
              Restore Files
            </button>
          )}

          {(assessment?.suggestedAction === "remove" ||
            assessment?.suggestedAction === "review") && (
            <button
              onClick={() => onRemove(folder.folderPath)}
              disabled={isLoading}
              className={cn(
                "px-3 py-1.5 text-sm rounded transition-colors",
                isLoading
                  ? "bg-red-200 text-red-400 cursor-not-allowed"
                  : "bg-red-600 text-white hover:bg-red-700"
              )}
            >
              Remove Folder
            </button>
          )}

          {isKept ? (
            <button
              onClick={() => onUnkeep?.(folder.folderPath)}
              disabled={isLoading}
              className={cn(
                "px-3 py-1.5 text-sm rounded border transition-colors",
                isLoading
                  ? "bg-neutral-100 text-neutral-400 border-neutral-200 cursor-not-allowed"
                  : "bg-blue-50 text-blue-700 border-blue-300 hover:bg-blue-100"
              )}
            >
              Unkeep
            </button>
          ) : (
            <button
              onClick={() => onKeep(folder.folderPath)}
              disabled={isLoading}
              className={cn(
                "px-3 py-1.5 text-sm rounded border transition-colors",
                isLoading
                  ? "bg-neutral-100 text-neutral-400 border-neutral-200 cursor-not-allowed"
                  : "bg-white text-neutral-700 border-neutral-300 hover:bg-neutral-50"
              )}
            >
              Keep Folder
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Component to display moved files with collapse/expand
 */
interface MovedFilesListProps {
  files: MovedFileInfo[];
  onPathClick: (path: string) => void;
}

function MovedFilesList({ files, onPathClick }: MovedFilesListProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const displayFiles = isExpanded ? files : files.slice(0, 3);
  const hasMore = files.length > 3;

  return (
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
        {isExpanded ? "Hide" : "Show"} moved files ({files.length})
      </button>

      {isExpanded && (
        <div className="mt-2 space-y-2">
          {displayFiles.map((file, index) => (
            <div
              key={`${file.documentId}-${file.originalPath}-${index}`}
              className="text-sm bg-neutral-50 rounded p-2 border border-neutral-100"
            >
              <div className="font-medium text-neutral-700">{file.fileName}</div>
              <div className="text-neutral-500 text-xs mt-1">
                <span>From: </span>
                <button
                  onClick={() => onPathClick(file.originalPath)}
                  className="text-blue-600 hover:underline"
                  title={file.originalPath}
                >
                  {truncatePath(file.originalPath, 40)}
                </button>
              </div>
              <div className="text-neutral-500 text-xs">
                <span>To: </span>
                <button
                  onClick={() => onPathClick(file.currentPath)}
                  className="text-blue-600 hover:underline"
                  title={file.currentPath}
                >
                  {truncatePath(file.currentPath, 40)}
                </button>
              </div>
              <div className="text-neutral-400 text-xs">
                Moved: {formatDate(file.movedAt)}
              </div>
            </div>
          ))}

          {hasMore && !isExpanded && (
            <button
              onClick={() => setIsExpanded(true)}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Show {files.length - 3} more files
            </button>
          )}
        </div>
      )}
    </div>
  );
}
