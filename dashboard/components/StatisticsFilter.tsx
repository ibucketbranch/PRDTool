"use client";

import { useState } from "react";
import { HelpTooltip, HELP_TEXT } from "./Tooltip";

export interface FilterOptions {
  category: string | null;
  startYear: number | null;
  endYear: number | null;
}

interface StatisticsFilterProps {
  categories: string[];
  years: number[];
  filters: FilterOptions;
  onFilterChange: (filters: FilterOptions) => void;
  onClearFilters: () => void;
}

export function StatisticsFilter({
  categories,
  years,
  filters,
  onFilterChange,
  onClearFilters,
}: StatisticsFilterProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const hasActiveFilters =
    filters.category !== null ||
    filters.startYear !== null ||
    filters.endYear !== null;

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    onFilterChange({
      ...filters,
      category: value === "" ? null : value,
    });
  };

  const handleStartYearChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    onFilterChange({
      ...filters,
      startYear: value === "" ? null : parseInt(value),
    });
  };

  const handleEndYearChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    onFilterChange({
      ...filters,
      endYear: value === "" ? null : parseInt(value),
    });
  };

  // Sort years ascending for dropdown
  const sortedYears = [...years].sort((a, b) => a - b);

  // Format category name for display
  const formatCategoryName = (name: string): string => {
    if (!name || name === "uncategorized") return "Uncategorized";
    return name
      .replace(/[-_]/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  return (
    <div className="bg-white border border-neutral-200 rounded-lg p-4 mb-6">
      <div className="flex items-center justify-between">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 text-neutral-700 hover:text-neutral-900 font-medium"
          aria-expanded={isExpanded}
          aria-controls="filter-panel"
        >
          <svg
            className={`w-4 h-4 transition-transform ${isExpanded ? "rotate-90" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 5l7 7-7 7"
            />
          </svg>
          Filters
          {hasActiveFilters && (
            <span className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded-full">
              Active
            </span>
          )}
        </button>

        {hasActiveFilters && (
          <button
            onClick={onClearFilters}
            className="text-sm text-neutral-500 hover:text-neutral-700 underline"
          >
            Clear all
          </button>
        )}
      </div>

      {isExpanded && (
        <div id="filter-panel" className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Category Filter */}
          <div>
            <label
              htmlFor="category-filter"
              className="flex items-center gap-1 text-sm font-medium text-neutral-600 mb-1"
            >
              Category
              <HelpTooltip text={HELP_TEXT.categoryFilter} size={14} />
            </label>
            <select
              id="category-filter"
              value={filters.category ?? ""}
              onChange={handleCategoryChange}
              className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {formatCategoryName(cat)}
                </option>
              ))}
            </select>
          </div>

          {/* Start Year Filter */}
          <div>
            <label
              htmlFor="start-year-filter"
              className="flex items-center gap-1 text-sm font-medium text-neutral-600 mb-1"
            >
              Start Year
              <HelpTooltip text={HELP_TEXT.yearRangeFilter} size={14} />
            </label>
            <select
              id="start-year-filter"
              value={filters.startYear ?? ""}
              onChange={handleStartYearChange}
              className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">Any</option>
              {sortedYears.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>

          {/* End Year Filter */}
          <div>
            <label
              htmlFor="end-year-filter"
              className="block text-sm font-medium text-neutral-600 mb-1"
            >
              End Year
            </label>
            <select
              id="end-year-filter"
              value={filters.endYear ?? ""}
              onChange={handleEndYearChange}
              className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">Any</option>
              {sortedYears.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Active Filters Display */}
      {hasActiveFilters && !isExpanded && (
        <div className="mt-3 flex flex-wrap gap-2">
          {filters.category && (
            <FilterTag
              label={`Category: ${formatCategoryName(filters.category)}`}
              onRemove={() => onFilterChange({ ...filters, category: null })}
            />
          )}
          {filters.startYear && (
            <FilterTag
              label={`From: ${filters.startYear}`}
              onRemove={() => onFilterChange({ ...filters, startYear: null })}
            />
          )}
          {filters.endYear && (
            <FilterTag
              label={`To: ${filters.endYear}`}
              onRemove={() => onFilterChange({ ...filters, endYear: null })}
            />
          )}
        </div>
      )}
    </div>
  );
}

interface FilterTagProps {
  label: string;
  onRemove: () => void;
}

function FilterTag({ label, onRemove }: FilterTagProps) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 text-sm rounded-md">
      {label}
      <button
        onClick={onRemove}
        className="hover:bg-blue-100 rounded p-0.5"
        aria-label={`Remove ${label} filter`}
      >
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </span>
  );
}

// Utility function to apply filters to statistics data
export function applyFiltersToCategories(
  categories: { ai_category: string; count: number }[],
  filters: FilterOptions
): { ai_category: string; count: number }[] {
  if (!filters.category) return categories;
  return categories.filter((c) => c.ai_category === filters.category);
}

export function applyFiltersToDateDistribution(
  dateDistribution: { year: number; count: number }[],
  filters: FilterOptions
): { year: number; count: number }[] {
  return dateDistribution.filter((d) => {
    if (filters.startYear && d.year < filters.startYear) return false;
    if (filters.endYear && d.year > filters.endYear) return false;
    return true;
  });
}
