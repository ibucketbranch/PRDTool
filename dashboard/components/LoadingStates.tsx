"use client";

import { cn } from "@/lib/utils";

/**
 * Animated spinner component using Tailwind CSS
 */
interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function Spinner({ size = "md", className }: SpinnerProps) {
  const sizeClasses = {
    sm: "h-4 w-4 border-2",
    md: "h-6 w-6 border-2",
    lg: "h-8 w-8 border-3",
  };

  return (
    <div
      className={cn(
        "animate-spin rounded-full border-neutral-300 border-t-neutral-600",
        sizeClasses[size],
        className
      )}
      role="status"
      aria-label="Loading"
    >
      <span className="sr-only">Loading...</span>
    </div>
  );
}

/**
 * Skeleton component for loading placeholders
 */
interface SkeletonProps {
  className?: string;
  variant?: "text" | "rectangular" | "circular";
  width?: string | number;
  height?: string | number;
}

export function Skeleton({
  className,
  variant = "rectangular",
  width,
  height,
}: SkeletonProps) {
  const variantClasses = {
    text: "rounded",
    rectangular: "rounded-md",
    circular: "rounded-full",
  };

  const style: React.CSSProperties = {};
  if (width) style.width = typeof width === "number" ? `${width}px` : width;
  if (height) style.height = typeof height === "number" ? `${height}px` : height;

  return (
    <div
      className={cn(
        "animate-pulse bg-neutral-200",
        variantClasses[variant],
        className
      )}
      style={style}
      aria-hidden="true"
    />
  );
}

/**
 * Loading text with spinner
 */
interface LoadingTextProps {
  text?: string;
  className?: string;
}

export function LoadingText({ text = "Loading...", className }: LoadingTextProps) {
  return (
    <div className={cn("flex items-center gap-2 text-neutral-500", className)}>
      <Spinner size="sm" />
      <span>{text}</span>
    </div>
  );
}

/**
 * Full page loading state
 */
interface PageLoadingProps {
  text?: string;
}

export function PageLoading({ text = "Loading..." }: PageLoadingProps) {
  return (
    <div className="flex items-center justify-center min-h-64">
      <LoadingText text={text} />
    </div>
  );
}

/**
 * Skeleton for StatCard component
 */
export function StatCardSkeleton() {
  return (
    <div className="p-6 bg-neutral-50 rounded-lg border border-neutral-200">
      <Skeleton className="h-4 w-24 mb-3" />
      <Skeleton className="h-8 w-16 mb-2" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

/**
 * Grid of StatCard skeletons
 */
interface StatCardSkeletonGridProps {
  count?: number;
}

export function StatCardSkeletonGrid({ count = 4 }: StatCardSkeletonGridProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <StatCardSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Skeleton for chart components
 */
interface ChartSkeletonProps {
  height?: number;
}

export function ChartSkeleton({ height = 300 }: ChartSkeletonProps) {
  return (
    <div className="bg-white border border-neutral-200 rounded-lg p-6">
      <Skeleton className="w-full" height={height} />
    </div>
  );
}

/**
 * Skeleton for table rows
 */
interface TableRowSkeletonProps {
  columns?: number;
}

export function TableRowSkeleton({ columns = 5 }: TableRowSkeletonProps) {
  return (
    <tr className="border-b border-neutral-100">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-4 w-full" />
        </td>
      ))}
    </tr>
  );
}

/**
 * Skeleton for document table
 */
interface TableSkeletonProps {
  rows?: number;
  columns?: number;
}

export function TableSkeleton({ rows = 5, columns = 5 }: TableSkeletonProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead className="bg-neutral-50 border-b border-neutral-200">
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i} className="px-4 py-3 text-left">
                <Skeleton className="h-4 w-20" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <TableRowSkeleton key={i} columns={columns} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Skeleton for card list items (e.g., OrphanedFileCard, MissingFileCard)
 */
export function CardSkeleton() {
  return (
    <div className="p-4 border border-neutral-200 rounded-lg bg-white">
      <div className="flex items-start gap-3">
        <Skeleton variant="circular" width={20} height={20} />
        <div className="flex-1">
          <Skeleton className="h-5 w-48 mb-2" />
          <Skeleton className="h-4 w-full mb-2" />
          <Skeleton className="h-3 w-32" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-8 w-20" />
          <Skeleton className="h-8 w-20" />
        </div>
      </div>
    </div>
  );
}

/**
 * Skeleton for a list of cards
 */
interface CardListSkeletonProps {
  count?: number;
}

export function CardListSkeleton({ count = 3 }: CardListSkeletonProps) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Skeleton for search results
 */
export function SearchResultSkeleton() {
  return (
    <div className="p-4 border border-neutral-200 rounded-lg bg-white">
      <div className="flex items-start gap-3">
        <Skeleton variant="circular" width={32} height={32} />
        <div className="flex-1">
          <Skeleton className="h-5 w-64 mb-2" />
          <Skeleton className="h-4 w-full mb-2" />
          <Skeleton className="h-4 w-3/4 mb-3" />
          <div className="flex gap-2">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-5 w-20" />
            <Skeleton className="h-5 w-16" />
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Skeleton for search results list
 */
interface SearchResultsSkeletonProps {
  count?: number;
}

export function SearchResultsSkeleton({ count = 3 }: SearchResultsSkeletonProps) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <SearchResultSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Skeleton for empty folder card
 */
export function EmptyFolderCardSkeleton() {
  return (
    <div className="p-4 border border-neutral-200 rounded-lg bg-white">
      <div className="flex items-center gap-3">
        <Skeleton variant="rectangular" width={20} height={20} />
        <Skeleton variant="circular" width={24} height={24} />
        <div className="flex-1">
          <Skeleton className="h-5 w-48 mb-2" />
          <Skeleton className="h-4 w-full" />
        </div>
        <Skeleton className="h-6 w-24" />
        <div className="flex gap-2">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-8 w-20" />
        </div>
      </div>
    </div>
  );
}

/**
 * Skeleton for empty folders list
 */
interface EmptyFolderListSkeletonProps {
  count?: number;
}

export function EmptyFolderListSkeleton({ count = 3 }: EmptyFolderListSkeletonProps) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <EmptyFolderCardSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Statistics page loading skeleton
 */
export function StatisticsPageSkeleton() {
  return (
    <div className="space-y-8">
      <StatCardSkeletonGrid count={4} />
      <div>
        <Skeleton className="h-6 w-40 mb-4" />
        <ChartSkeleton height={300} />
      </div>
      <div>
        <Skeleton className="h-6 w-40 mb-4" />
        <ChartSkeleton height={250} />
      </div>
      <div>
        <Skeleton className="h-6 w-32 mb-4" />
        <ChartSkeleton height={200} />
      </div>
    </div>
  );
}

/**
 * Browse page loading skeleton
 */
export function BrowsePageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex gap-4 mb-6">
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-10 flex-1" />
      </div>
      <TableSkeleton rows={10} columns={5} />
    </div>
  );
}
