"use client";

import { cn } from "@/lib/utils";

export interface FileDNAResult {
  filename: string;
  path: string;
  tags: string[];
  hash: string;
  provenance: {
    origin: string;
    first_seen_at: string;
    routed_to: string;
    model_used: string;
  };
  related_files: string[];
  duplicate_status: {
    is_duplicate: boolean;
    duplicate_of: string | null;
    has_duplicates: boolean;
    duplicate_paths: string[];
  };
}

interface FileDNAResultCardProps {
  result: FileDNAResult;
  onPathClick?: (path: string) => void;
  className?: string;
}

/**
 * Format a date string for display
 */
function formatDate(dateStr: string): string {
  if (!dateStr) return "Unknown";
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

/**
 * Truncate a hash for display
 */
function truncateHash(hash: string): string {
  if (!hash) return "";
  if (hash.length <= 16) return hash;
  return `${hash.slice(0, 8)}...${hash.slice(-8)}`;
}

/**
 * Get the filename from a path
 */
function getFilename(path: string): string {
  return path.split("/").pop() || path;
}

export function FileDNAResultCard({
  result,
  onPathClick,
  className,
}: FileDNAResultCardProps) {
  const handlePathClick = (path: string) => {
    if (onPathClick) {
      onPathClick(path);
    }
  };

  const hasDuplicates =
    result.duplicate_status.is_duplicate ||
    result.duplicate_status.has_duplicates;
  const hasRelatedFiles = result.related_files.length > 0;

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
          {result.filename}
        </h3>
        <button
          onClick={() => handlePathClick(result.path)}
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline text-left break-all"
          title="Click to open in Finder"
        >
          {result.path}
        </button>
      </div>

      {/* Tags */}
      {result.tags.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1">
          {result.tags.slice(0, 8).map((tag, index) => (
            <span
              key={index}
              className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded"
            >
              {tag}
            </span>
          ))}
          {result.tags.length > 8 && (
            <span className="text-xs text-neutral-400">
              +{result.tags.length - 8} more
            </span>
          )}
        </div>
      )}

      {/* Provenance info */}
      <div className="mb-3 text-sm">
        <div className="flex flex-wrap gap-4">
          {result.provenance.origin && (
            <div>
              <span className="text-neutral-500">Origin: </span>
              <span className="font-medium text-neutral-700">
                {result.provenance.origin}
              </span>
            </div>
          )}
          {result.provenance.first_seen_at && (
            <div>
              <span className="text-neutral-500">First seen: </span>
              <span className="font-medium text-neutral-700">
                {formatDate(result.provenance.first_seen_at)}
              </span>
            </div>
          )}
          {result.provenance.model_used && (
            <div>
              <span className="text-neutral-500">Model: </span>
              <span className="font-medium text-neutral-700">
                {result.provenance.model_used}
              </span>
            </div>
          )}
        </div>
        {result.provenance.routed_to && (
          <div className="mt-1">
            <span className="text-neutral-500">Routed to: </span>
            <span className="font-medium text-neutral-700">
              {result.provenance.routed_to}
            </span>
          </div>
        )}
      </div>

      {/* Hash */}
      <div className="mb-3">
        <span className="text-xs text-neutral-500">Hash: </span>
        <code className="text-xs text-neutral-600 bg-neutral-100 px-1 py-0.5 rounded font-mono">
          {truncateHash(result.hash)}
        </code>
      </div>

      {/* Duplicate status */}
      {hasDuplicates && (
        <div className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded text-sm">
          {result.duplicate_status.is_duplicate && (
            <div className="text-amber-700">
              <span className="font-medium">Duplicate of: </span>
              <button
                onClick={() =>
                  handlePathClick(result.duplicate_status.duplicate_of || "")
                }
                className="text-amber-800 hover:underline break-all text-left"
              >
                {getFilename(result.duplicate_status.duplicate_of || "")}
              </button>
            </div>
          )}
          {result.duplicate_status.has_duplicates && (
            <div className="text-amber-700">
              <span className="font-medium">
                Has {result.duplicate_status.duplicate_paths.length} duplicate
                {result.duplicate_status.duplicate_paths.length !== 1
                  ? "s"
                  : ""}
                :
              </span>
              <ul className="mt-1 ml-4 list-disc">
                {result.duplicate_status.duplicate_paths
                  .slice(0, 3)
                  .map((path, index) => (
                    <li key={index}>
                      <button
                        onClick={() => handlePathClick(path)}
                        className="text-amber-800 hover:underline break-all text-left"
                      >
                        {getFilename(path)}
                      </button>
                    </li>
                  ))}
                {result.duplicate_status.duplicate_paths.length > 3 && (
                  <li className="text-amber-600">
                    +{result.duplicate_status.duplicate_paths.length - 3} more
                  </li>
                )}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Related files */}
      {hasRelatedFiles && (
        <div className="text-sm">
          <span className="text-neutral-500">Related files: </span>
          <div className="mt-1 flex flex-wrap gap-2">
            {result.related_files.slice(0, 3).map((path, index) => (
              <button
                key={index}
                onClick={() => handlePathClick(path)}
                className="px-2 py-0.5 text-xs bg-neutral-100 text-neutral-600 hover:bg-neutral-200 rounded"
              >
                {getFilename(path)}
              </button>
            ))}
            {result.related_files.length > 3 && (
              <span className="text-xs text-neutral-400">
                +{result.related_files.length - 3} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
