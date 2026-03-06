"use client";

import { useState, useCallback, useRef } from "react";
import Link from "next/link";
import { SearchInput, EXAMPLE_QUERIES } from "@/components/SearchInput";
import { SearchResultCard } from "@/components/SearchResultCard";
import { SearchResultsSkeleton, ErrorDisplay, EmptyState } from "@/components";
import { HelpTooltip, HELP_TEXT } from "@/components/Tooltip";
import type { Document } from "@/lib/supabase";
import { openInFinder, copyToClipboard } from "@/lib/utils";

const PAGE_SIZE = 20;

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
  limit: number;
  offset: number;
  hasMore: boolean;
  error?: string;
}

export default function SearchPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [searchMeta, setSearchMeta] = useState<Omit<SearchResponse, "documents"> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const currentQueryRef = useRef<string>("");
  const currentOffsetRef = useRef<number>(0);

  const fetchResults = useCallback(async (query: string, offset: number = 0, append: boolean = false) => {
    if (append) {
      setIsLoadingMore(true);
    } else {
      setIsLoading(true);
      setDocuments([]);
    }
    setError(null);

    try {
      const response = await fetch(
        `/api/search?q=${encodeURIComponent(query)}&mode=natural&limit=${PAGE_SIZE}&offset=${offset}`
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error: ${response.status}`);
      }

      const result: SearchResponse = await response.json();

      if (result.error) {
        setError(result.error);
        if (!append) {
          setDocuments([]);
          setSearchMeta(null);
        }
      } else {
        if (append) {
          setDocuments(prev => [...prev, ...result.documents]);
        } else {
          setDocuments(result.documents);
          currentQueryRef.current = query;
        }
        currentOffsetRef.current = offset + result.documents.length;
        setHasMore(result.hasMore);
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { documents: _, ...meta } = result;
        setSearchMeta(meta);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to search documents");
      if (!append) {
        setDocuments([]);
        setSearchMeta(null);
      }
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, []);

  const handleSearch = useCallback(async (query: string) => {
    currentOffsetRef.current = 0;
    await fetchResults(query, 0, false);
  }, [fetchResults]);

  const handleLoadMore = useCallback(async () => {
    if (!currentQueryRef.current || isLoadingMore) return;
    await fetchResults(currentQueryRef.current, currentOffsetRef.current, true);
  }, [fetchResults, isLoadingMore]);

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

  const totalDisplayed = documents.length;

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

      {/* Loading State (initial search) */}
      {isLoading && <SearchResultsSkeleton count={3} />}

      {/* Error Message */}
      {error && !isLoading && (
        <ErrorDisplay
          message={error}
          className="mb-6"
        />
      )}

      {/* Search Results */}
      {searchMeta && !isLoading && (
        <div>
          {/* Search Description */}
          {searchMeta.searchDescription && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-blue-700">{searchMeta.searchDescription}</p>
            </div>
          )}

          {/* Results Count */}
          <div className="mb-4 flex items-center justify-between">
            <p className="text-neutral-600">
              Showing <span className="font-semibold">{totalDisplayed}</span> document{totalDisplayed !== 1 ? "s" : ""}
              {hasMore && " (more available)"}
            </p>
            {searchMeta.parsed && (
              <div className="flex gap-2 text-xs">
                {searchMeta.parsed.category && (
                  <span className="px-2 py-1 bg-green-100 text-green-700 rounded">
                    Category: {searchMeta.parsed.category}
                  </span>
                )}
                {searchMeta.parsed.years.length > 0 && (
                  <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded">
                    Years: {searchMeta.parsed.years.join(", ")}
                  </span>
                )}
                {searchMeta.parsed.organizations.length > 0 && (
                  <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded">
                    Org: {searchMeta.parsed.organizations.join(", ")}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Results List */}
          {documents.length > 0 ? (
            <div className="space-y-4">
              {documents.map((doc) => (
                <SearchResultCard
                  key={doc.id}
                  document={doc}
                  onPathClick={handlePathClick}
                />
              ))}

              {/* Load More Button */}
              {hasMore && (
                <div className="flex justify-center pt-4">
                  <button
                    onClick={handleLoadMore}
                    disabled={isLoadingMore}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed transition-colors"
                  >
                    {isLoadingMore ? "Loading..." : "Load More"}
                  </button>
                </div>
              )}

              {/* Loading indicator for Load More */}
              {isLoadingMore && (
                <SearchResultsSkeleton count={2} />
              )}
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
      {!searchMeta && !error && !isLoading && (
        <EmptyState
          title="Enter a search query to find documents"
          message='Use natural language like "Find tax documents from 2023"'
          className="bg-neutral-50 rounded-lg border border-neutral-200"
        />
      )}
    </main>
  );
}
