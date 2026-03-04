"use client";

import { cn } from "@/lib/utils";
import { Tooltip, HELP_TEXT } from "./Tooltip";
import type { Document } from "@/lib/supabase";

export type SortField = "file_name" | "ai_category" | "current_path" | "file_modified_at";
export type SortDirection = "asc" | "desc";

interface DocumentTableProps {
  documents: Document[];
  sortField: SortField;
  sortDirection: SortDirection;
  onSortChange: (field: SortField) => void;
  onPathClick: (path: string) => void;
  className?: string;
}

/**
 * Format category name for display (snake_case to Title Case)
 */
function formatCategoryName(category: string | null): string {
  if (!category) return "Uncategorized";
  return category
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Extract and format dates from key_dates array
 */
function formatDates(keyDates: string[] | null): string {
  if (!keyDates || keyDates.length === 0) return "-";
  // Show first 2 dates max
  const displayDates = keyDates.slice(0, 2);
  const suffix = keyDates.length > 2 ? ` (+${keyDates.length - 2})` : "";
  return displayDates.join(", ") + suffix;
}

/**
 * Truncate path for display
 */
function truncatePath(path: string, maxLength: number = 50): string {
  if (path.length <= maxLength) return path;
  const start = path.slice(0, 20);
  const end = path.slice(-27);
  return `${start}...${end}`;
}

/**
 * Truncate path for mobile display (shorter)
 */
function truncatePathMobile(path: string): string {
  if (path.length <= 30) return path;
  const start = path.slice(0, 12);
  const end = path.slice(-15);
  return `${start}...${end}`;
}

/**
 * Get context bin from folder_hierarchy
 */
function getContextBin(folderHierarchy: string[] | null): string {
  if (!folderHierarchy || folderHierarchy.length === 0) return "-";
  return folderHierarchy[0];
}

/**
 * Extract date from filename (e.g., "112023" -> Nov 2023, "2022-11-18" -> Nov 18, 2022)
 * Returns ISO date string or null if no date found
 */
function extractDateFromFilename(filename: string): string | null {
  if (!filename) return null;

  // Pattern 1: YYYY-MM-DD (e.g., "eStmt_2022-11-18.pdf")
  const isoMatch = filename.match(/(\d{4}-\d{2}-\d{2})/);
  if (isoMatch) {
    return isoMatch[1];
  }

  // Pattern 2: MMDDYYYY or MMYYYY (e.g., "112023" -> Nov 2023, "CoinBase_112023.pdf")
  const mmddyyyyMatch = filename.match(/(\d{1,2})(\d{4})/);
  if (mmddyyyyMatch) {
    const month = parseInt(mmddyyyyMatch[1]);
    const year = parseInt(mmddyyyyMatch[2]);
    if (month >= 1 && month <= 12 && year >= 1900 && year <= 2099) {
      // Return first day of that month
      return `${year}-${String(month).padStart(2, "0")}-01`;
    }
  }

  // Pattern 3: MonthYYYY (e.g., "Aug2010", "Aug2010BoAStatement.pdf")
  const monthNames = [
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec"
  ];
  const monthMatch = filename.match(/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{4})/i);
  if (monthMatch) {
    const monthName = monthMatch[1].toLowerCase();
    const year = parseInt(monthMatch[2]);
    const month = monthNames.indexOf(monthName) + 1;
    if (month > 0 && year >= 1900 && year <= 2099) {
      return `${year}-${String(month).padStart(2, "0")}-01`;
    }
  }

  // Pattern 4: YYYYMMDD (e.g., "20221118")
  const yyyymmddMatch = filename.match(/(\d{4})(\d{2})(\d{2})/);
  if (yyyymmddMatch) {
    const year = parseInt(yyyymmddMatch[1]);
    const month = parseInt(yyyymmddMatch[2]);
    const day = parseInt(yyyymmddMatch[3]);
    if (year >= 1900 && year <= 2099 && month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    }
  }

  return null;
}

/**
 * Get best date to display - prefers filename date if available and reasonable
 */
function getBestModifiedDate(
  fileModifiedAt: string | null,
  filename: string,
  createdAt: string
): string | null {
  // Extract date from filename
  const filenameDate = extractDateFromFilename(filename);
  
  if (filenameDate) {
    // Use filename date as it's most accurate for document date
    return filenameDate;
  }

  // Fallback to file_modified_at if available
  if (fileModifiedAt) {
    // Check if it's a suspicious future date (beyond current year + 1)
    const modifiedYear = new Date(fileModifiedAt).getFullYear();
    const currentYear = new Date().getFullYear();
    // If it's more than 1 year in the future, it's probably wrong
    if (modifiedYear > currentYear + 1) {
      // Use created_at instead
      return createdAt;
    }
    return fileModifiedAt;
  }

  // Final fallback to created_at
  return createdAt;
}

interface SortHeaderProps {
  label: string;
  field: SortField;
  currentField: SortField;
  direction: SortDirection;
  onSort: (field: SortField) => void;
}

function SortHeader({ label, field, currentField, direction, onSort }: SortHeaderProps) {
  const isActive = currentField === field;

  return (
    <button
      onClick={() => onSort(field)}
      className={cn(
        "flex items-center gap-1 text-left font-medium text-neutral-600 hover:text-neutral-900",
        isActive && "text-neutral-900"
      )}
    >
      {label}
      {isActive && (
        <svg
          className={cn("w-4 h-4 transition-transform", direction === "desc" && "rotate-180")}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
        </svg>
      )}
    </button>
  );
}

/**
 * Sort button for mobile card view
 */
interface MobileSortButtonProps {
  sortField: SortField;
  sortDirection: SortDirection;
  onSortChange: (field: SortField) => void;
}

function MobileSortButton({ sortField, sortDirection, onSortChange }: MobileSortButtonProps) {
  const sortOptions: { field: SortField; label: string }[] = [
    { field: "file_name", label: "Name" },
    { field: "ai_category", label: "Category" },
    { field: "file_modified_at", label: "Modified" },
    { field: "current_path", label: "Path" },
  ];

  const currentSort = sortOptions.find((o) => o.field === sortField);

  return (
    <div className="flex items-center gap-2 mb-4">
      <span className="text-sm text-neutral-500">Sort by:</span>
      <select
        value={sortField}
        onChange={(e) => onSortChange(e.target.value as SortField)}
        className="text-sm border border-neutral-300 rounded px-2 py-1 bg-white"
        aria-label="Sort field"
      >
        {sortOptions.map((opt) => (
          <option key={opt.field} value={opt.field}>
            {opt.label}
          </option>
        ))}
      </select>
      <button
        onClick={() => onSortChange(sortField)}
        className="p-1 hover:bg-neutral-100 rounded"
        aria-label={`Sort ${sortDirection === "asc" ? "descending" : "ascending"}`}
      >
        <svg
          className={cn("w-4 h-4 transition-transform", sortDirection === "desc" && "rotate-180")}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
        </svg>
      </button>
      {currentSort && (
        <span className="text-xs text-neutral-400">
          ({sortDirection === "asc" ? "A-Z" : "Z-A"})
        </span>
      )}
    </div>
  );
}

/**
 * Mobile card component for a single document
 */
interface DocumentCardProps {
  doc: Document;
  onPathClick: (path: string) => void;
}

function DocumentCard({ doc, onPathClick }: DocumentCardProps) {
  return (
    <div className="border border-neutral-200 rounded-lg p-4 bg-white hover:bg-neutral-50 transition-colors">
      {/* File Name */}
      <div className="font-medium text-neutral-800 mb-2 break-words">
        {doc.file_name}
      </div>

      {/* Category Badge */}
      <div className="mb-2">
        <span className="inline-flex px-2 py-1 text-xs bg-neutral-100 text-neutral-700 rounded">
          {formatCategoryName(doc.ai_category)}
        </span>
      </div>

      {/* Path */}
      <div className="mb-2">
        <span className="text-xs text-neutral-500 block">Path:</span>
        <button
          onClick={() => onPathClick(doc.current_path)}
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline text-left break-all"
          title={doc.current_path}
        >
          {truncatePathMobile(doc.current_path)}
        </button>
      </div>

      {/* Meta Info */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500">
        {doc.key_dates && doc.key_dates.length > 0 && (
          <span>Dates: {formatDates(doc.key_dates)}</span>
        )}
        {getContextBin(doc.folder_hierarchy) !== "-" && (
          <span>Bin: {getContextBin(doc.folder_hierarchy)}</span>
        )}
        <span>
          Modified:{" "}
          {(() => {
            const bestDate = getBestModifiedDate(
              doc.file_modified_at,
              doc.file_name,
              doc.created_at
            );
            return bestDate
              ? new Date(bestDate).toLocaleDateString()
              : "-";
          })()}
        </span>
      </div>
    </div>
  );
}

export function DocumentTable({
  documents,
  sortField,
  sortDirection,
  onSortChange,
  onPathClick,
  className,
}: DocumentTableProps) {
  if (documents.length === 0) {
    return (
      <div className={cn("text-center py-12 bg-neutral-50 rounded-lg border border-neutral-200", className)}>
        <p className="text-neutral-500 mb-2">No documents found</p>
        <p className="text-sm text-neutral-400">
          Try adjusting your filters or search criteria
        </p>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Mobile Card View */}
      <div className="block md:hidden">
        <MobileSortButton
          sortField={sortField}
          sortDirection={sortDirection}
          onSortChange={onSortChange}
        />
        <div className="space-y-3">
          {documents.map((doc) => (
            <DocumentCard key={doc.id} doc={doc} onPathClick={onPathClick} />
          ))}
        </div>
      </div>

      {/* Desktop Table View */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-neutral-200 bg-neutral-50">
              <th className="text-left p-3 text-sm">
                <SortHeader
                  label="Name"
                  field="file_name"
                  currentField={sortField}
                  direction={sortDirection}
                  onSort={onSortChange}
                />
              </th>
              <th className="text-left p-3 text-sm">
                <SortHeader
                  label="Path"
                  field="current_path"
                  currentField={sortField}
                  direction={sortDirection}
                  onSort={onSortChange}
                />
              </th>
              <th className="text-left p-3 text-sm">
                <SortHeader
                  label="Category"
                  field="ai_category"
                  currentField={sortField}
                  direction={sortDirection}
                  onSort={onSortChange}
                />
              </th>
              <th className="text-left p-3 text-sm font-medium text-neutral-600">
                Dates
              </th>
              <th className="text-left p-3 text-sm font-medium text-neutral-600">
                Context Bin
              </th>
              <th className="text-left p-3 text-sm">
                <SortHeader
                  label="Modified"
                  field="file_modified_at"
                  currentField={sortField}
                  direction={sortDirection}
                  onSort={onSortChange}
                />
              </th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr
                key={doc.id}
                className="border-b border-neutral-100 hover:bg-neutral-50 transition-colors"
              >
                <td className="p-3">
                  <div className="font-medium text-neutral-800 text-sm">
                    {doc.file_name}
                  </div>
                </td>
                <td className="p-3">
                  <Tooltip content={HELP_TEXT.pathClick} position="top">
                    <button
                      onClick={() => onPathClick(doc.current_path)}
                      className="text-sm text-blue-600 hover:text-blue-800 hover:underline text-left"
                      title={doc.current_path}
                    >
                      {truncatePath(doc.current_path)}
                    </button>
                  </Tooltip>
                </td>
                <td className="p-3">
                  <span className="inline-flex px-2 py-1 text-xs bg-neutral-100 text-neutral-700 rounded">
                    {formatCategoryName(doc.ai_category)}
                  </span>
                </td>
                <td className="p-3 text-sm text-neutral-600">
                  {formatDates(doc.key_dates)}
                </td>
                <td className="p-3 text-sm text-neutral-600">
                  {getContextBin(doc.folder_hierarchy)}
                </td>
                <td className="p-3 text-sm text-neutral-500">
                  {(() => {
                    const bestDate = getBestModifiedDate(
                      doc.file_modified_at,
                      doc.file_name,
                      doc.created_at
                    );
                    return bestDate
                      ? new Date(bestDate).toLocaleDateString()
                      : "-";
                  })()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
