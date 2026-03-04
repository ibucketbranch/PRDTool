"use client";

import { cn } from "@/lib/utils";
import type { Document } from "@/lib/supabase";

interface SearchResultCardProps {
  document: Document;
  onPathClick?: (path: string) => void;
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
  if (!keyDates || keyDates.length === 0) return "No dates";
  // Show first 3 dates max
  const displayDates = keyDates.slice(0, 3);
  const suffix = keyDates.length > 3 ? ` (+${keyDates.length - 3} more)` : "";
  return displayDates.join(", ") + suffix;
}

/**
 * Format entities for display
 */
function formatEntities(
  entities: Document["entities"]
): { label: string; values: string[] }[] {
  if (!entities) return [];

  const result: { label: string; values: string[] }[] = [];

  if (entities.people && entities.people.length > 0) {
    result.push({ label: "People", values: entities.people });
  }
  if (entities.organizations && entities.organizations.length > 0) {
    result.push({ label: "Organizations", values: entities.organizations });
  }
  if (entities.amounts && entities.amounts.length > 0) {
    result.push({ label: "Amounts", values: entities.amounts });
  }

  return result;
}

export function SearchResultCard({
  document,
  onPathClick,
  className,
}: SearchResultCardProps) {
  const entities = formatEntities(document.entities);

  const handlePathClick = () => {
    if (onPathClick) {
      onPathClick(document.current_path);
    }
  };

  return (
    <div
      className={cn(
        "p-4 bg-white border border-neutral-200 rounded-lg hover:border-neutral-300 transition-colors",
        className
      )}
    >
      {/* File name and path */}
      <div className="mb-3">
        <h3 className="text-lg font-semibold text-neutral-800 mb-1">
          {document.file_name}
        </h3>
        <button
          onClick={handlePathClick}
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline text-left break-all"
          title="Click to open in Finder"
        >
          {document.current_path}
        </button>
      </div>

      {/* Category and date */}
      <div className="flex flex-wrap gap-4 mb-3 text-sm">
        <div>
          <span className="text-neutral-500">Category: </span>
          <span className="font-medium text-neutral-700">
            {formatCategoryName(document.ai_category)}
          </span>
        </div>
        <div>
          <span className="text-neutral-500">Date: </span>
          <span className="font-medium text-neutral-700">
            {formatDates(document.key_dates)}
          </span>
        </div>
      </div>

      {/* AI Summary */}
      {document.ai_summary && (
        <div className="mb-3">
          <p className="text-sm text-neutral-600 line-clamp-2">
            {document.ai_summary}
          </p>
        </div>
      )}

      {/* Entities */}
      {entities.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {entities.map((entityGroup, index) => (
            <div key={index} className="flex items-center gap-1">
              <span className="text-xs text-neutral-500">{entityGroup.label}:</span>
              {entityGroup.values.slice(0, 3).map((value, vIndex) => (
                <span
                  key={vIndex}
                  className="px-2 py-0.5 text-xs bg-neutral-100 text-neutral-700 rounded"
                >
                  {value}
                </span>
              ))}
              {entityGroup.values.length > 3 && (
                <span className="text-xs text-neutral-400">
                  +{entityGroup.values.length - 3}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
