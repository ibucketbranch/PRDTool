"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { StatCard } from "@/components/StatCard";
import { CategoryChart } from "@/components/CategoryChart";
import { DateDistributionChart } from "@/components/DateDistributionChart";
import { ContextBinChart } from "@/components/ContextBinChart";
import {
  StatisticsFilter,
  applyFiltersToCategories,
  applyFiltersToDateDistribution,
} from "@/components/StatisticsFilter";
import { StatisticsPageSkeleton, ErrorDisplay } from "@/components";
import { HELP_TEXT } from "@/components/Tooltip";
import type { FilterOptions } from "@/components/StatisticsFilter";
import type {
  CategoryCount,
  YearCount,
  ContextBinCount,
} from "@/lib/supabase";

interface StatisticsData {
  connected: boolean;
  documentCount: number;
  categories: CategoryCount[];
  dateDistribution: YearCount[];
  contextBins: ContextBinCount[];
  error?: string;
}

const DEFAULT_FILTERS: FilterOptions = {
  category: null,
  startYear: null,
  endYear: null,
};

export default function StatisticsPage() {
  const [data, setData] = useState<StatisticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterOptions>(DEFAULT_FILTERS);

  useEffect(() => {
    async function fetchStatistics() {
      try {
        const response = await fetch("/api/statistics");
        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }
        const result = await response.json();
        if (result.error) {
          setError(result.error);
        } else {
          setData(result);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load statistics");
      } finally {
        setLoading(false);
      }
    }

    fetchStatistics();
  }, []);

  // Apply filters to data
  const filteredData = useMemo(() => {
    if (!data) return null;

    const filteredCategories = applyFiltersToCategories(data.categories, filters);
    const filteredDateDistribution = applyFiltersToDateDistribution(
      data.dateDistribution,
      filters
    );

    // Calculate filtered document count
    const filteredDocumentCount = filteredCategories.reduce(
      (sum, cat) => sum + cat.count,
      0
    );

    return {
      ...data,
      categories: filteredCategories,
      dateDistribution: filteredDateDistribution,
      documentCount: filters.category ? filteredDocumentCount : data.documentCount,
    };
  }, [data, filters]);

  // Extract available filter options from data
  const availableCategories = useMemo(() => {
    if (!data) return [];
    return data.categories.map((c) => c.ai_category);
  }, [data]);

  const availableYears = useMemo(() => {
    if (!data) return [];
    return data.dateDistribution.map((d) => d.year);
  }, [data]);

  const handleCategoryClick = (category: string) => {
    // Toggle category filter: if same category clicked, clear it; otherwise set it
    if (filters.category === category) {
      setFilters({ ...filters, category: null });
    } else {
      setFilters({ ...filters, category });
    }
  };

  const handleYearClick = (year: number) => {
    // Toggle year filter: if same year clicked as both start and end, clear it
    // Otherwise set clicked year as both start and end year for single-year filter
    if (filters.startYear === year && filters.endYear === year) {
      setFilters({ ...filters, startYear: null, endYear: null });
    } else {
      setFilters({ ...filters, startYear: year, endYear: year });
    }
  };

  const handleBinClick = (bin: string) => {
    // Navigate directly to browse page with context bin filter
    window.location.href = `/browse?contextBin=${encodeURIComponent(bin)}`;
  };

  const handleFilterChange = (newFilters: FilterOptions) => {
    setFilters(newFilters);
  };

  const handleClearFilters = () => {
    setFilters(DEFAULT_FILTERS);
  };

  // Handler to refetch data
  const handleRetry = () => {
    setLoading(true);
    setError(null);
    fetch("/api/statistics")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP error: ${response.status}`);
        return response.json();
      })
      .then((result) => {
        if (result.error) {
          setError(result.error);
        } else {
          setData(result);
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load statistics");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  if (loading) {
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
        <h1 className="text-3xl font-bold mb-2">Statistics</h1>
        <p className="text-neutral-600 mb-8">
          Overview of your document organization
        </p>
        <StatisticsPageSkeleton />
      </main>
    );
  }

  if (error) {
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
        <h1 className="text-3xl font-bold mb-2">Statistics</h1>
        <p className="text-neutral-600 mb-8">
          Overview of your document organization
        </p>
        <ErrorDisplay
          message={error}
          onRetry={handleRetry}
          linkTo="/"
          linkText="Return to dashboard"
        />
      </main>
    );
  }

  if (!data || !filteredData) {
    return (
      <main className="container mx-auto px-4 py-8">
        <div className="text-neutral-500">No data available</div>
      </main>
    );
  }

  const totalCategories = filteredData.categories.length;
  const totalYears = filteredData.dateDistribution.length;
  const totalContextBins = data.contextBins.length;

  const hasActiveFilters =
    filters.category !== null ||
    filters.startYear !== null ||
    filters.endYear !== null;

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

      <h1 className="text-3xl font-bold mb-2">Statistics</h1>
      <p className="text-neutral-600 mb-8">
        Overview of your document organization
      </p>

      {/* Filters */}
      <StatisticsFilter
        categories={availableCategories}
        years={availableYears}
        filters={filters}
        onFilterChange={handleFilterChange}
        onClearFilters={handleClearFilters}
      />

      {/* Filter Status Message */}
      {hasActiveFilters && (
        <div className="mb-6 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <p className="text-sm text-blue-700">
              Showing filtered results.{" "}
              <button
                onClick={handleClearFilters}
                className="underline hover:no-underline"
              >
                Clear filters
              </button>{" "}
              to see all data.
            </p>
            <Link
              href={`/browse?${new URLSearchParams({
                ...(filters.category && { category: filters.category }),
                ...(filters.startYear && { startYear: filters.startYear.toString() }),
                ...(filters.endYear && { endYear: filters.endYear.toString() }),
              }).toString()}`}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors font-medium"
            >
              View Documents →
            </Link>
          </div>
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          title="Total Documents"
          value={filteredData.documentCount}
          description={hasActiveFilters ? "Matching filters" : "In the database"}
          helpText={HELP_TEXT.totalDocuments}
        />
        <StatCard
          title="Categories"
          value={totalCategories}
          description={hasActiveFilters ? "Matching filters" : "AI-assigned categories"}
          helpText={HELP_TEXT.categories}
        />
        <StatCard
          title="Years Covered"
          value={totalYears}
          description={hasActiveFilters ? "In date range" : "Date range in documents"}
          helpText={HELP_TEXT.dateDistribution}
        />
        <StatCard
          title="Context Bins"
          value={totalContextBins}
          description="Top-level folder groups"
          helpText={HELP_TEXT.contextBins}
        />
      </div>

      {/* Category Breakdown */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4">Category Breakdown</h2>
        <div className="bg-white border border-neutral-200 rounded-lg p-6">
          {filteredData.categories.length > 0 ? (
            <>
              <CategoryChart
                data={filteredData.categories}
                onCategoryClick={handleCategoryClick}
              />
              <p className="text-xs text-neutral-500 mt-4 text-center">
                Click a category to filter. Click again to clear.{" "}
                {filters.category && (
                  <Link
                    href={`/browse?category=${filters.category}`}
                    className="text-blue-600 hover:text-blue-800 underline"
                  >
                    View documents →
                  </Link>
                )}
              </p>
            </>
          ) : (
            <div className="text-center py-8 text-neutral-500">
              {hasActiveFilters
                ? "No categories match the current filters"
                : "No category data available"}
            </div>
          )}
        </div>
      </section>

      {/* Date Distribution */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4">Date Distribution</h2>
        <div className="bg-white border border-neutral-200 rounded-lg p-6">
          {filteredData.dateDistribution.length > 0 ? (
            <>
              <DateDistributionChart
                data={filteredData.dateDistribution}
                onYearClick={handleYearClick}
              />
              <p className="text-xs text-neutral-500 mt-4 text-center">
                Click a year to filter. Click again to clear.{" "}
                {(filters.startYear || filters.endYear) && (
                  <Link
                    href={`/browse?${new URLSearchParams({
                      ...(filters.startYear && { startYear: filters.startYear.toString() }),
                      ...(filters.endYear && { endYear: filters.endYear.toString() }),
                    }).toString()}`}
                    className="text-blue-600 hover:text-blue-800 underline"
                  >
                    View documents →
                  </Link>
                )}
              </p>
            </>
          ) : (
            <div className="text-center py-8 text-neutral-500">
              {hasActiveFilters
                ? "No dates match the current filters"
                : "No date distribution data available"}
            </div>
          )}
        </div>
      </section>

      {/* Context Bins */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4">Context Bins</h2>
        <div className="bg-white border border-neutral-200 rounded-lg p-6">
          {data.contextBins.length > 0 ? (
            <>
              <ContextBinChart
                data={data.contextBins}
                onBinClick={handleBinClick}
              />
              <p className="text-xs text-neutral-500 mt-4 text-center">
                Documents organized by top-level folder hierarchy. Click a bin to view documents.
              </p>
            </>
          ) : (
            <div className="text-center py-8 text-neutral-500">
              No context bin data available
            </div>
          )}
        </div>
      </section>

      {/* Connection Status */}
      <div className="text-sm text-neutral-500 text-center">
        {data.connected ? (
          <span className="text-green-600">Connected to database</span>
        ) : (
          <span className="text-red-600">Disconnected from database</span>
        )}
      </div>
    </main>
  );
}
