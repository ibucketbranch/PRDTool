"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { SearchInput, EXAMPLE_QUERIES } from "@/components/SearchInput";
import { SearchResultCard } from "@/components/SearchResultCard";
import { SearchResultsSkeleton, ErrorDisplay, EmptyState } from "@/components";
import { HelpTooltip, HELP_TEXT } from "@/components/Tooltip";
import type { Document } from "@/lib/supabase";
import { openInFinder, copyToClipboard } from "@/lib/utils";

interface SearchResponse {
  query: string;
  mode: string;
  parsed?: {
    category: string | null;
    years: number[];
    organizations: string[];
    searchTerms: string[];
    isNaturalLanguage: boolean;
  };
  searchDescription?: string;
  documents: Document[];
  count: number;
  error?: string;
}

export default function SearchPage() {
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = useCallback(async (query: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `/api/search?q=${encodeURIComponent(query)}&mode=natural`
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error: ${response.status}`);
      }

      const result: SearchResponse = await response.json();

      if (result.error) {
        setError(result.error);
        setSearchResult(null);
      } else {
        setSearchResult(result);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to search documents");
      setSearchResult(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

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

      <div className="flex items-center gap-2 mb-2">
        <h1 className="text-3xl font-bold">Natural Language Search</h1>
        <HelpTooltip text={HELP_TEXT.naturalLanguageSearch} size={20} position="right" />
      </div>
      <p className="text-neutral-600 mb-8">
        Search for documents using natural language queries like &quot;{EXAMPLE_QUERIES[0]}&quot;
      </p>

      {/* Search Input */}
      <SearchInput
        onSearch={handleSearch}
        isLoading={isLoading}
        className="mb-8"
      />

      {/* Loading State */}
      {isLoading && <SearchResultsSkeleton count={3} />}

      {/* Error Message */}
      {error && !isLoading && (
        <ErrorDisplay
          message={error}
          className="mb-6"
        />
      )}

      {/* Search Results */}
      {searchResult && !isLoading && (
        <div>
          {/* Search Description */}
          {searchResult.searchDescription && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-blue-700">{searchResult.searchDescription}</p>
            </div>
          )}

          {/* Results Count */}
          <div className="mb-4 flex items-center justify-between">
            <p className="text-neutral-600">
              Found <span className="font-semibold">{searchResult.count}</span>{" "}
              document{searchResult.count !== 1 ? "s" : ""}
            </p>
            {searchResult.parsed && (
              <div className="flex gap-2 text-xs">
                {searchResult.parsed.category && (
                  <span className="px-2 py-1 bg-green-100 text-green-700 rounded">
                    Category: {searchResult.parsed.category}
                  </span>
                )}
                {searchResult.parsed.years.length > 0 && (
                  <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded">
                    Years: {searchResult.parsed.years.join(", ")}
                  </span>
                )}
                {searchResult.parsed.organizations.length > 0 && (
                  <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded">
                    Org: {searchResult.parsed.organizations.join(", ")}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Results List */}
          {searchResult.documents.length > 0 ? (
            <div className="space-y-4">
              {searchResult.documents.map((doc) => (
                <SearchResultCard
                  key={doc.id}
                  document={doc}
                  onPathClick={handlePathClick}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No documents found"
              message="Try a different search query or use one of the example queries above"
              className="bg-neutral-50 rounded-lg border border-neutral-200"
            />
          )}
        </div>
      )}

      {/* Initial State */}
      {!searchResult && !error && !isLoading && (
        <EmptyState
          title="Enter a search query to find documents"
          message='Use natural language like "Find tax documents from 2023"'
          className="bg-neutral-50 rounded-lg border border-neutral-200"
        />
      )}
    </main>
  );
}
