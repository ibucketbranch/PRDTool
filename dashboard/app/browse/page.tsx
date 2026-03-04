"use client";

import { useState, useEffect, useCallback, useMemo, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  DocumentBrowserFilter,
  DEFAULT_DOCUMENT_FILTERS,
  DocumentTable,
  Pagination,
  BrowsePageSkeleton,
  ErrorDisplay,
} from "@/components";
import type { DocumentFilterOptions, SortField, SortDirection } from "@/components";
import type { Document } from "@/lib/supabase";
import { openInFinder, copyToClipboard } from "@/lib/utils";

interface DocumentsResponse {
  documents: Document[];
  total: number;
  filteredTotal: number;
  limit: number;
  offset: number;
  error?: string;
}

interface StatisticsData {
  categories: { ai_category: string; count: number }[];
  dateDistribution: { year: number; count: number }[];
  contextBins: { context_bin: string; count: number }[];
  minYear?: number;
  maxYear?: number;
}

function BrowsePageContent() {
  const searchParams = useSearchParams();

  // Initialize filters from URL params
  const initialFilters = useMemo((): DocumentFilterOptions => {
    const category = searchParams.get("category");
    const contextBin = searchParams.get("contextBin");
    const year = searchParams.get("year");

    return {
      ...DEFAULT_DOCUMENT_FILTERS,
      category: category || null,
      contextBin: contextBin || null,
      startYear: year ? parseInt(year) : null,
      endYear: year ? parseInt(year) : null,
    };
  }, [searchParams]);

  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [filteredTotal, setFilteredTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [filters, setFilters] = useState<DocumentFilterOptions>(initialFilters);

  // Sort state
  const [sortField, setSortField] = useState<SortField>("file_modified_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);

  // Statistics for filter dropdowns
  const [statistics, setStatistics] = useState<StatisticsData | null>(null);
  const [filteredCategories, setFilteredCategories] = useState<string[]>([]);
  const [filteredContextBins, setFilteredContextBins] = useState<string[]>([]);

  // Fetch statistics for filter dropdowns
  useEffect(() => {
    async function fetchStatistics() {
      try {
        const response = await fetch("/api/statistics");
        if (!response.ok) return;
        const data = await response.json();
        setStatistics(data);
      } catch {
        // Silently fail - filter dropdowns will be empty
      }
    }
    fetchStatistics();
  }, []);

  // Fetch categories and context bins filtered by year range
  useEffect(() => {
    async function fetchFilteredOptions() {
      if (filters.startYear === null && filters.endYear === null) {
        // No year filter, use all options from statistics
        if (statistics) {
          setFilteredCategories(statistics.categories.map(c => c.ai_category));
          setFilteredContextBins(statistics.contextBins.map(b => b.context_bin));
        }
        return;
      }

      try {
        const params = new URLSearchParams();
        if (filters.startYear !== null) {
          params.set("startYear", filters.startYear.toString());
        }
        if (filters.endYear !== null) {
          params.set("endYear", filters.endYear.toString());
        }
        
        const response = await fetch(`/api/statistics?${params.toString()}`);
        if (!response.ok) return;
        const data = await response.json();
        
        if (data.categories) {
          const categoryNames = data.categories.map((c: { ai_category: string }) => c.ai_category);
          setFilteredCategories(categoryNames);
          
          // Clear category filter if selected category is not in filtered list
          if (filters.category && !categoryNames.includes(filters.category)) {
            setFilters(prev => ({ ...prev, category: null }));
          }
        }
        
        if (data.contextBins) {
          const contextBinNames = data.contextBins.map((b: { context_bin: string }) => b.context_bin);
          setFilteredContextBins(contextBinNames);
          
          // Clear context bin filter if selected bin is not in filtered list
          if (filters.contextBin && !contextBinNames.includes(filters.contextBin)) {
            setFilters(prev => ({ ...prev, contextBin: null }));
          }
        }
      } catch (err) {
        console.error("Failed to fetch filtered options:", err);
      }
    }
    fetchFilteredOptions();
  }, [filters.startYear, filters.endYear, statistics]);

  // Fetch documents
  const fetchDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();

      // Add filters
      if (filters.category) params.set("category", filters.category);
      if (filters.contextBin) params.set("contextBin", filters.contextBin);
      if (filters.startYear) params.set("startYear", filters.startYear.toString());
      if (filters.endYear) params.set("endYear", filters.endYear.toString());
      if (filters.search) params.set("search", filters.search);

      // Add sorting
      params.set("orderBy", sortField);
      params.set("orderDirection", sortDirection);

      // Add pagination
      params.set("limit", itemsPerPage.toString());
      params.set("offset", ((currentPage - 1) * itemsPerPage).toString());

      const response = await fetch(`/api/documents?${params.toString()}`);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error: ${response.status}`);
      }

      const result: DocumentsResponse = await response.json();

      if (result.error) {
        setError(result.error);
        setDocuments([]);
        setTotal(0);
        setFilteredTotal(0);
      } else {
        setDocuments(result.documents);
        setTotal(result.total);
        setFilteredTotal(result.filteredTotal);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch documents");
      setDocuments([]);
      setTotal(0);
      setFilteredTotal(0);
    } finally {
      setIsLoading(false);
    }
  }, [filters, sortField, sortDirection, currentPage, itemsPerPage]);

  // Fetch when dependencies change
  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [filters, itemsPerPage]);

  // Handlers
  const handleFilterChange = (newFilters: DocumentFilterOptions) => {
    setFilters(newFilters);
  };

  const handleClearFilters = () => {
    setFilters(DEFAULT_DOCUMENT_FILTERS);
  };

  const handleSortChange = (field: SortField) => {
    if (field === sortField) {
      // Toggle direction if same field
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      // New field, default to descending
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handleItemsPerPageChange = (newItemsPerPage: number) => {
    setItemsPerPage(newItemsPerPage);
  };

  const handlePathClick = useCallback(async (path: string) => {
    // Try to open file in Finder (macOS)
    const result = await openInFinder(path);

    if (result.success) {
      // File was successfully revealed in Finder
      return;
    }

    // Fallback: copy path to clipboard and show message
    const copied = await copyToClipboard(path);
    if (copied) {
      alert(`Could not open in Finder. Path copied to clipboard:\n${path}\n\nReason: ${result.error || result.message}`);
    } else {
      alert(`File path:\n${path}\n\nCould not open in Finder: ${result.error || result.message}`);
    }
  }, []);

  // Calculate total pages
  const totalPages = Math.ceil(filteredTotal / itemsPerPage);

  // Extract categories, context bins, and years from statistics
  // Use filtered categories when year range is selected, otherwise use all categories
  const categories = useMemo(() => {
    if (filteredCategories.length > 0) {
      return filteredCategories;
    }
    return statistics?.categories.map((c) => c.ai_category) || [];
  }, [filteredCategories, statistics]);

  // Use filtered context bins when year range is selected, otherwise use all context bins
  const contextBins = useMemo(() => {
    if (filteredContextBins.length > 0) {
      return filteredContextBins;
    }
    return statistics?.contextBins.map((b) => b.context_bin) || [];
  }, [filteredContextBins, statistics]);

  const years = useMemo(() => {
    if (!statistics) return [];
    
    // Generate year range from minYear to maxYear (from file_modified_at)
    if (statistics.minYear !== undefined && statistics.maxYear !== undefined) {
      const yearRange: number[] = [];
      for (let year = statistics.minYear; year <= statistics.maxYear; year++) {
        yearRange.push(year);
      }
      return yearRange;
    }
    
    // Fallback to dateDistribution if min/max not available
    return statistics.dateDistribution.map((d) => d.year);
  }, [statistics]);

  return (
    <main className="container mx-auto px-4 py-8">
      <div className="mb-6">
        <Link
          href="/"
          className="text-sm text-neutral-500 hover:text-neutral-700 transition-colors"
        >
          &larr; Back to Dashboard
        </Link>
      </div>

      <h1 className="text-3xl font-bold mb-2">Document Browser</h1>
      <p className="text-neutral-600 mb-6">
        Browse and filter all documents in your organization system
      </p>

      {/* Filters */}
      <DocumentBrowserFilter
        categories={categories}
        contextBins={contextBins}
        years={years}
        filters={filters}
        onFilterChange={handleFilterChange}
        onClearFilters={handleClearFilters}
      />

      {/* Results Summary */}
      <div className="mb-4 flex items-center justify-between">
        <p className="text-neutral-600">
          {isLoading ? (
            "Loading documents..."
          ) : error ? (
            <span className="text-red-600">Error loading documents</span>
          ) : (
            <>
              Found <span className="font-semibold">{filteredTotal}</span> document
              {filteredTotal !== 1 ? "s" : ""}
              {filteredTotal !== total && (
                <span className="text-neutral-400">
                  {" "}
                  (filtered from {total} total)
                </span>
              )}
            </>
          )}
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <ErrorDisplay
          message={error}
          onRetry={fetchDocuments}
          className="mb-6"
        />
      )}

      {/* Loading State */}
      {isLoading && <BrowsePageSkeleton />}

      {/* Document Table */}
      {!isLoading && !error && (
        <>
          <div className="bg-white border border-neutral-200 rounded-lg">
            <DocumentTable
              documents={documents}
              sortField={sortField}
              sortDirection={sortDirection}
              onSortChange={handleSortChange}
              onPathClick={handlePathClick}
            />
          </div>

          {/* Pagination */}
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            totalItems={filteredTotal}
            itemsPerPage={itemsPerPage}
            onPageChange={handlePageChange}
            onItemsPerPageChange={handleItemsPerPageChange}
          />
        </>
      )}
    </main>
  );
}

export default function BrowsePage() {
  return (
    <Suspense fallback={<BrowsePageSkeleton />}>
      <BrowsePageContent />
    </Suspense>
  );
}
