"use client";

import { useState, useRef, useEffect, ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface TooltipProps {
  /** The content to display in the tooltip */
  content: ReactNode;
  /** The element that triggers the tooltip (usually an icon or button) */
  children: ReactNode;
  /** Position of the tooltip relative to the trigger */
  position?: "top" | "bottom" | "left" | "right";
  /** Additional class names for the tooltip container */
  className?: string;
  /** Delay in milliseconds before showing the tooltip */
  delay?: number;
  /** Maximum width of the tooltip */
  maxWidth?: number;
}

/**
 * A reusable tooltip component for displaying help text on hover.
 * Supports multiple positions and auto-positioning to stay within viewport.
 */
export function Tooltip({
  content,
  children,
  position = "top",
  className,
  delay = 200,
  maxWidth = 280,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [actualPosition, setActualPosition] = useState(position);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLDivElement>(null);

  // Adjust position if tooltip would overflow viewport
  useEffect(() => {
    if (isVisible && tooltipRef.current && triggerRef.current) {
      const tooltipRect = tooltipRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      let newPosition = position;

      // Check if tooltip overflows and adjust position
      if (position === "top" && tooltipRect.top < 0) {
        newPosition = "bottom";
      } else if (position === "bottom" && tooltipRect.bottom > viewportHeight) {
        newPosition = "top";
      } else if (position === "left" && tooltipRect.left < 0) {
        newPosition = "right";
      } else if (position === "right" && tooltipRect.right > viewportWidth) {
        newPosition = "left";
      }

      if (newPosition !== actualPosition) {
        setActualPosition(newPosition);
      }
    }
  }, [isVisible, position, actualPosition]);

  const handleMouseEnter = () => {
    timeoutRef.current = setTimeout(() => {
      setIsVisible(true);
    }, delay);
  };

  const handleMouseLeave = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setIsVisible(false);
    setActualPosition(position);
  };

  const handleFocus = () => {
    setIsVisible(true);
  };

  const handleBlur = () => {
    setIsVisible(false);
  };

  const positionClasses = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  const arrowClasses = {
    top: "top-full left-1/2 -translate-x-1/2 border-t-neutral-800 border-x-transparent border-b-transparent",
    bottom: "bottom-full left-1/2 -translate-x-1/2 border-b-neutral-800 border-x-transparent border-t-transparent",
    left: "left-full top-1/2 -translate-y-1/2 border-l-neutral-800 border-y-transparent border-r-transparent",
    right: "right-full top-1/2 -translate-y-1/2 border-r-neutral-800 border-y-transparent border-l-transparent",
  };

  return (
    <div
      ref={triggerRef}
      className={cn("relative inline-flex", className)}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleFocus}
      onBlur={handleBlur}
    >
      {children}
      {isVisible && (
        <div
          ref={tooltipRef}
          role="tooltip"
          className={cn(
            "absolute z-50 px-3 py-2 text-sm text-white bg-neutral-800 rounded-lg shadow-lg",
            "animate-in fade-in-0 zoom-in-95 duration-150",
            positionClasses[actualPosition]
          )}
          style={{ maxWidth }}
        >
          {content}
          {/* Arrow */}
          <div
            className={cn(
              "absolute w-0 h-0 border-4",
              arrowClasses[actualPosition]
            )}
          />
        </div>
      )}
    </div>
  );
}

/**
 * An info icon with tooltip, commonly used for help text.
 */
export interface HelpTooltipProps {
  /** The help text to display */
  text: string;
  /** Size of the icon in pixels */
  size?: number;
  /** Position of the tooltip */
  position?: "top" | "bottom" | "left" | "right";
  /** Additional class names */
  className?: string;
}

export function HelpTooltip({
  text,
  size = 16,
  position = "top",
  className,
}: HelpTooltipProps) {
  return (
    <Tooltip content={text} position={position} className={className}>
      <button
        type="button"
        className="inline-flex items-center justify-center text-neutral-400 hover:text-neutral-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded-full"
        aria-label="Help"
      >
        <svg
          width={size}
          height={size}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
          <path d="M12 17h.01" />
        </svg>
      </button>
    </Tooltip>
  );
}

/**
 * Help text constants for consistent messaging across the app
 */
export const HELP_TEXT = {
  // Statistics page
  totalDocuments: "Total number of documents indexed in the database",
  categories: "Documents are automatically categorized by AI based on their content",
  dateDistribution: "Shows when documents were created or modified, based on dates extracted from content",
  contextBins: "Folder hierarchy groupings that organize documents by their location",

  // Filter controls
  categoryFilter: "Filter documents by their AI-assigned category",
  yearRangeFilter: "Filter documents by the year they were created or contain",
  contextBinFilter: "Filter documents by their folder location grouping",
  searchFilter: "Search within document names and content",

  // Search page
  naturalLanguageSearch: "Ask questions about your documents in plain English. The search understands dates, organizations, categories, and more.",
  searchExamples: "Click an example query to try it, or type your own question",

  // Document browser
  sortableColumns: "Click column headers to sort. Click again to reverse order.",
  pathClick: "Click to reveal this file in Finder (macOS)",

  // Orphaned files
  orphanedFiles: "Files that exist on disk but are not tracked in the database",
  missingFiles: "Files tracked in the database but no longer found on disk",
  confidenceScore: "How confident the system is about the suggested location (based on file patterns and database history)",
  matchType: {
    database_history: "Suggestion based on the file's previous known location in the database",
    similar_files: "Suggestion based on where similar files are stored",
    filename_pattern: "Suggestion based on the file name pattern (e.g., invoice_, tax_)",
    file_type: "Suggestion based on the file extension (e.g., .pdf, .plist)",
  },
  analyzeSuggestion: "Analyze this file to determine the best location based on its content and similar files",
  moveSuggestion: "Move this file to the suggested location",

  // Empty folders
  emptyFolders: "Folders that are now empty after files were moved or deleted",
  folderAssessment: "Whether the original folder location was correct or was a duplicate/misnamed folder",
  restoreFiles: "Move files back to this folder",
  removeFolder: "Delete this empty folder from the file system",

  // Charts
  chartInteraction: "Click on a bar to filter the data by that category",

  // General
  pagination: "Navigate between pages of results",
  bulkSelect: "Select multiple items to perform batch operations",
} as const;
