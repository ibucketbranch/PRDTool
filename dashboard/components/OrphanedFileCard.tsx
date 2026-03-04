"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Tooltip, HELP_TEXT } from "./Tooltip";
import type { OrphanedFileInfo, EnhancedLocationSuggestion } from "@/lib/supabase";

export interface OrphanedFileCardProps {
  file: OrphanedFileInfo;
  suggestion: EnhancedLocationSuggestion | null;
  isSelected: boolean;
  isLoading: boolean;
  onSelect: (filePath: string, selected: boolean) => void;
  onAnalyze: (filePath: string) => void;
  onMove: (filePath: string, targetPath: string) => void;
  onPathClick: (path: string) => void;
  className?: string;
}

/**
 * Format file size for display
 */
function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
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
 * Get the confidence badge color based on confidence level
 */
function getConfidenceBadge(confidence: number): {
  color: string;
  text: string;
  tooltip: string;
} {
  if (confidence >= 0.85) {
    return {
      color: "bg-green-100 text-green-700",
      text: "High confidence",
      tooltip: "Very likely this is the correct location (85%+ match)",
    };
  } else if (confidence >= 0.7) {
    return {
      color: "bg-yellow-100 text-yellow-700",
      text: "Medium confidence",
      tooltip: "Likely the correct location (70-85% match)",
    };
  } else if (confidence >= 0.5) {
    return {
      color: "bg-orange-100 text-orange-700",
      text: "Low confidence",
      tooltip: "May be the correct location (50-70% match)",
    };
  }
  return {
    color: "bg-neutral-100 text-neutral-600",
    text: "Very low",
    tooltip: "Uncertain about this location (below 50% match)",
  };
}

/**
 * Get the match type badge
 */
function getMatchTypeBadge(matchType: string): {
  color: string;
  text: string;
  icon: string;
  tooltip: string;
} {
  switch (matchType) {
    case "database_history":
      return {
        color: "bg-green-100 text-green-700",
        text: "From database",
        icon: "📚",
        tooltip: HELP_TEXT.matchType.database_history,
      };
    case "similar_files":
      return {
        color: "bg-blue-100 text-blue-700",
        text: "Similar files",
        icon: "🔗",
        tooltip: HELP_TEXT.matchType.similar_files,
      };
    case "filename_pattern":
      return {
        color: "bg-purple-100 text-purple-700",
        text: "Filename pattern",
        icon: "📝",
        tooltip: HELP_TEXT.matchType.filename_pattern,
      };
    case "file_type":
      return {
        color: "bg-neutral-100 text-neutral-600",
        text: "File type",
        icon: "📄",
        tooltip: HELP_TEXT.matchType.file_type,
      };
    default:
      return {
        color: "bg-neutral-100 text-neutral-600",
        text: matchType,
        icon: "?",
        tooltip: "Unknown match type",
      };
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
 * Extract file name from path
 */
function getFileName(path: string): string {
  const parts = path.split("/").filter(Boolean);
  return parts[parts.length - 1] || path;
}

export function OrphanedFileCard({
  file,
  suggestion,
  isSelected,
  isLoading,
  onSelect,
  onAnalyze,
  onMove,
  onPathClick,
  className,
}: OrphanedFileCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const confidenceBadge = suggestion ? getConfidenceBadge(suggestion.confidence) : null;
  const matchTypeBadge = suggestion ? getMatchTypeBadge(suggestion.matchType) : null;
  const fileName = file.fileName || getFileName(file.filePath);

  return (
    <div
      className={cn(
        "border rounded-lg p-3 sm:p-4 transition-colors",
        isSelected ? "border-blue-500 bg-blue-50" : "border-neutral-200 bg-white",
        className
      )}
    >
      {/* Header Row - flex-col on mobile, flex-row on desktop */}
      <div className="flex flex-col sm:flex-row sm:items-start gap-3">
        {/* Selection Checkbox + File Info (wrapped on mobile) */}
        <div className="flex items-start gap-3 flex-1 min-w-0">
          {/* Selection Checkbox */}
          <input
            type="checkbox"
            checked={isSelected}
            onChange={(e) => onSelect(file.filePath, e.target.checked)}
            className="mt-1 h-4 w-4 rounded border-neutral-300 text-blue-600 focus:ring-blue-500 flex-shrink-0"
            aria-label={`Select ${fileName}`}
          />

          {/* File Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {/* File Name */}
              <h3 className="font-semibold text-neutral-800 text-sm sm:text-base break-words">{fileName}</h3>

              {/* File Type Badge */}
              <span className="text-xs px-2 py-0.5 rounded bg-neutral-100 text-neutral-600">
                {file.fileType || "unknown"}
              </span>

              {/* Confidence Badge */}
              {confidenceBadge && (
                <Tooltip content={confidenceBadge.tooltip} position="top">
                  <span className={cn("text-xs px-2 py-0.5 rounded cursor-help", confidenceBadge.color)}>
                    {confidenceBadge.text}
                  </span>
                </Tooltip>
              )}
            </div>

            {/* Current Path */}
            <div className="mt-1">
              <span className="text-xs text-neutral-500">Current: </span>
              <button
                onClick={() => onPathClick(file.filePath)}
                className="text-xs sm:text-sm text-blue-600 hover:text-blue-800 hover:underline text-left break-all"
                title={file.filePath}
              >
                {truncatePath(file.filePath, 40)}
              </button>
            </div>

            {/* Stats */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs sm:text-sm text-neutral-600">
              <span>Size: {formatFileSize(file.fileSize)}</span>
              {file.lastModified && (
                <span>Modified: {formatDate(file.lastModified)}</span>
              )}
            </div>

            {/* Suggestion Details */}
            {suggestion && (
              <div className="mt-3 p-2 sm:p-3 bg-neutral-50 rounded-lg border border-neutral-100">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  {matchTypeBadge && (
                    <Tooltip content={matchTypeBadge.tooltip} position="top">
                      <span className={cn("text-xs px-2 py-0.5 rounded flex items-center gap-1 cursor-help", matchTypeBadge.color)}>
                        <span>{matchTypeBadge.icon}</span>
                        {matchTypeBadge.text}
                      </span>
                    </Tooltip>
                  )}
                  {suggestion.fromDatabase && (
                    <span className="text-xs text-green-600">Found in database</span>
                  )}
                </div>

                {/* Suggested Path */}
                <div className="text-xs sm:text-sm">
                  <span className="text-neutral-500">Suggested: </span>
                  <button
                    onClick={() => onPathClick(suggestion.suggestedPath)}
                    className="text-blue-600 hover:text-blue-800 hover:underline break-all"
                    title={suggestion.suggestedPath}
                  >
                    {truncatePath(suggestion.suggestedPath, 35)}
                  </button>
                </div>

                {/* Reason */}
                <div className="text-xs text-neutral-500 mt-1">
                  {suggestion.reason}
                </div>

                {/* Additional Details (collapsible) */}
                {(suggestion.detectedCategory || suggestion.similarFilesCount > 0) && (
                  <div className="mt-2">
                    <button
                      onClick={() => setIsExpanded(!isExpanded)}
                      className="text-xs text-neutral-500 hover:text-neutral-700 flex items-center gap-1"
                    >
                      <svg
                        className={cn("w-3 h-3 transition-transform", isExpanded && "rotate-90")}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                      {isExpanded ? "Hide" : "Show"} details
                    </button>

                    {isExpanded && (
                      <div className="mt-2 text-xs text-neutral-600 space-y-1">
                        {suggestion.detectedCategory && (
                          <div>
                            Category: <span className="font-medium">{suggestion.detectedCategory}</span>
                          </div>
                        )}
                        {suggestion.similarFilesCount > 0 && (
                          <div>
                            Similar files: <span className="font-medium">{suggestion.similarFilesCount}</span>
                          </div>
                        )}
                        {suggestion.databaseDocumentId && (
                          <div>
                            Document ID: <span className="font-mono text-xs break-all">{suggestion.databaseDocumentId}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Action Buttons - full width on mobile, column on desktop */}
        <div className="flex flex-row sm:flex-col gap-2 mt-2 sm:mt-0 flex-shrink-0">
          {!suggestion && (
            <button
              onClick={() => onAnalyze(file.filePath)}
              disabled={isLoading}
              className={cn(
                "px-3 py-1.5 text-sm rounded border transition-colors flex-1 sm:flex-none whitespace-nowrap",
                isLoading
                  ? "bg-neutral-100 text-neutral-400 border-neutral-200 cursor-not-allowed"
                  : "bg-white text-neutral-700 border-neutral-300 hover:bg-neutral-50"
              )}
            >
              {isLoading ? "Analyzing..." : "Analyze"}
            </button>
          )}

          {suggestion && (
            <button
              onClick={() => onMove(file.filePath, suggestion.suggestedPath)}
              disabled={isLoading}
              className={cn(
                "px-3 py-1.5 text-sm rounded transition-colors flex-1 sm:flex-none whitespace-nowrap",
                isLoading
                  ? "bg-green-200 text-green-400 cursor-not-allowed"
                  : "bg-green-600 text-white hover:bg-green-700"
              )}
            >
              Move to Suggested
            </button>
          )}

          <button
            onClick={() => onAnalyze(file.filePath)}
            disabled={isLoading}
            className={cn(
              "px-3 py-1.5 text-sm rounded border transition-colors flex-1 sm:flex-none whitespace-nowrap",
              isLoading
                ? "bg-neutral-100 text-neutral-400 border-neutral-200 cursor-not-allowed"
                : "bg-white text-neutral-700 border-neutral-300 hover:bg-neutral-50"
            )}
          >
            Re-analyze
          </button>
        </div>
      </div>
    </div>
  );
}
