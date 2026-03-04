"use client";

import { useState, useMemo } from "react";

export interface DocumentFilterOptions {
  category: string | null;
  contextBin: string | null;
  startYear: number | null;
  endYear: number | null;
  search: string;
}

interface DocumentBrowserFilterProps {
  categories: string[];
  contextBins: string[];
  years: number[];
  filters: DocumentFilterOptions;
  onFilterChange: (filters: DocumentFilterOptions) => void;
  onClearFilters: () => void;
}

export const DEFAULT_DOCUMENT_FILTERS: DocumentFilterOptions = {
  category: null,
  contextBin: null,
  startYear: null,
  endYear: null,
  search: "",
};

export function DocumentBrowserFilter({
  categories,
  contextBins,
  years,
  filters,
  onFilterChange,
  onClearFilters,
}: DocumentBrowserFilterProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const hasActiveFilters =
    filters.category !== null ||
    filters.contextBin !== null ||
    filters.startYear !== null ||
    filters.endYear !== null ||
    filters.search !== "";

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    onFilterChange({
      ...filters,
      category: value === "" ? null : value,
    });
  };

  const handleContextBinChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    onFilterChange({
      ...filters,
      contextBin: value === "" ? null : value,
    });
  };

  const handleStartYearChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    const newStartYear = value === "" ? null : parseInt(value);
    
    // If start year is set and end year is before it, clear end year
    let newEndYear = filters.endYear;
    if (newStartYear !== null && filters.endYear !== null && filters.endYear < newStartYear) {
      newEndYear = null;
    }
    
    onFilterChange({
      ...filters,
      startYear: newStartYear,
      endYear: newEndYear,
    });
  };

  const handleEndYearChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    const newEndYear = value === "" ? null : parseInt(value);
    
    // Validate: end year must be >= start year
    if (newEndYear !== null && filters.startYear !== null && newEndYear < filters.startYear) {
      // If invalid, don't update - keep current end year or clear it
      return;
    }
    
    onFilterChange({
      ...filters,
      endYear: newEndYear,
    });
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFilterChange({
      ...filters,
      search: e.target.value,
    });
  };

  // Sort years ascending for dropdown
  const sortedYears = [...years].sort((a, b) => a - b);
  
  // Filter end year options based on start year
  const availableEndYears = useMemo(() => {
    if (filters.startYear) {
      return sortedYears.filter(year => year >= filters.startYear!);
    }
    return sortedYears;
  }, [sortedYears, filters.startYear]);

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
          aria-controls="document-filter-panel"
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
        <div id="document-filter-panel" className="mt-4 space-y-4">
          {/* Search Input */}
          <div>
            <label
              htmlFor="search-filter"
              className="block text-sm font-medium text-neutral-600 mb-1"
            >
              Search
            </label>
            <input
              id="search-filter"
              type="text"
              value={filters.search}
              onChange={handleSearchChange}
              placeholder="Search by name, path, or summary..."
              className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Category Filter */}
            <div>
              <label
                htmlFor="category-filter"
                className="block text-sm font-medium text-neutral-600 mb-1"
              >
                Category
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

            {/* Context Bin Filter */}
            <div>
              <label
                htmlFor="context-bin-filter"
                className="block text-sm font-medium text-neutral-600 mb-1"
              >
                Context Bin
              </label>
              <select
                id="context-bin-filter"
                value={filters.contextBin ?? ""}
                onChange={handleContextBinChange}
                className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">All Context Bins</option>
                {contextBins.map((bin) => (
                  <option key={bin} value={bin}>
                    {formatCategoryName(bin)}
                  </option>
                ))}
              </select>
            </div>

            {/* Start Year Filter */}
            <div>
              <label
                htmlFor="start-year-filter"
                className="block text-sm font-medium text-neutral-600 mb-1"
              >
                Start Year
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
                disabled={filters.startYear !== null && availableEndYears.length === 0}
              >
                <option value="">Any</option>
                {availableEndYears.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
              {filters.startYear !== null && filters.endYear !== null && filters.endYear < filters.startYear && (
                <p className="text-xs text-red-600 mt-1">
                  End year must be {filters.startYear} or later
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Active Filters Display */}
      {hasActiveFilters && !isExpanded && (
        <div className="mt-3 flex flex-wrap gap-2">
          {filters.search && (
            <FilterTag
              label={`Search: "${filters.search}"`}
              onRemove={() => onFilterChange({ ...filters, search: "" })}
            />
          )}
          {filters.category && (
            <FilterTag
              label={`Category: ${formatCategoryName(filters.category)}`}
              onRemove={() => onFilterChange({ ...filters, category: null })}
            />
          )}
          {filters.contextBin && (
            <FilterTag
              label={`Context: ${formatCategoryName(filters.contextBin)}`}
              onRemove={() => onFilterChange({ ...filters, contextBin: null })}
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
