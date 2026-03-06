"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDebounce } from "@/hooks";
import { cn } from "@/lib/utils";

interface DocumentResult {
  id: string;
  file_name: string;
  ai_category?: string;
  current_path?: string;
}

interface FileDNAResult {
  filename: string;
  path: string;
  tags: string[];
}

interface SearchResults {
  documents: DocumentResult[];
  fileDNA: FileDNAResult[];
  documentsTotal: number;
  fileDNATotal: number;
}

const MIN_SEARCH_LENGTH = 2;
const DEBOUNCE_DELAY = 300;
const MAX_PREVIEW_RESULTS = 3;

export function GlobalSearchBar({ className }: { className?: string }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<SearchResults | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const debouncedQuery = useDebounce(query, DEBOUNCE_DELAY);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Cmd/Ctrl + K to focus search
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        inputRef.current?.focus();
        setIsOpen(true);
      }
      // Escape to close
      if (event.key === "Escape") {
        setIsOpen(false);
        inputRef.current?.blur();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Fetch results when debounced query changes
  const fetchResults = useCallback(async (searchQuery: string) => {
    if (searchQuery.length < MIN_SEARCH_LENGTH) {
      setResults(null);
      return;
    }

    setIsLoading(true);
    try {
      // Fetch both documents and file DNA in parallel
      const [documentsRes, fileDNARes] = await Promise.all([
        fetch(
          `/api/search?q=${encodeURIComponent(searchQuery)}&mode=natural&limit=${MAX_PREVIEW_RESULTS}`
        ),
        fetch(
          `/api/file-dna?search=${encodeURIComponent(searchQuery)}`
        ),
      ]);

      const [documentsData, fileDNAData] = await Promise.all([
        documentsRes.json(),
        fileDNARes.json(),
      ]);

      setResults({
        documents: documentsData.documents || [],
        fileDNA: (fileDNAData.results || []).slice(0, MAX_PREVIEW_RESULTS),
        documentsTotal: documentsData.count || 0,
        fileDNATotal: fileDNAData.total || 0,
      });
    } catch {
      setResults(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchResults(debouncedQuery);
  }, [debouncedQuery, fetchResults]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    if (e.target.value.length >= MIN_SEARCH_LENGTH) {
      setIsOpen(true);
    }
  };

  const handleInputFocus = () => {
    if (query.length >= MIN_SEARCH_LENGTH && results) {
      setIsOpen(true);
    }
  };

  const navigateToSearch = () => {
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
      setIsOpen(false);
    }
  };

  const navigateToFileDNA = () => {
    router.push(`/file-intelligence?search=${encodeURIComponent(query.trim())}`);
    setIsOpen(false);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      navigateToSearch();
    }
  };

  const hasResults =
    results &&
    (results.documents.length > 0 || results.fileDNA.length > 0);
  const showDropdown = isOpen && (hasResults || isLoading || query.length >= MIN_SEARCH_LENGTH);

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {/* Search Input */}
      <div className="relative">
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          onKeyDown={handleKeyPress}
          placeholder="Search documents..."
          aria-label="Global search"
          className="w-full pl-9 pr-16 py-2 text-sm border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white placeholder:text-neutral-400"
        />
        <kbd className="absolute right-3 top-1/2 -translate-y-1/2 hidden sm:inline-flex items-center gap-1 px-1.5 py-0.5 text-xs text-neutral-400 bg-neutral-100 rounded border border-neutral-200">
          <span className="text-[10px]">⌘</span>K
        </kbd>
      </div>

      {/* Dropdown Results */}
      {showDropdown && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-lg shadow-lg border border-neutral-200 overflow-hidden z-50 max-h-[400px] overflow-y-auto">
          {isLoading && (
            <div className="px-4 py-3 text-sm text-neutral-500">
              Searching...
            </div>
          )}

          {!isLoading && !hasResults && query.length >= MIN_SEARCH_LENGTH && (
            <div className="px-4 py-3 text-sm text-neutral-500">
              No results found for &quot;{query}&quot;
            </div>
          )}

          {!isLoading && hasResults && (
            <>
              {/* Documents Section */}
              {results.documents.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-neutral-50 border-b border-neutral-100">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-neutral-500 uppercase tracking-wide">
                        Documents
                      </span>
                      {results.documentsTotal > MAX_PREVIEW_RESULTS && (
                        <span className="text-xs text-neutral-400">
                          +{results.documentsTotal - MAX_PREVIEW_RESULTS} more
                        </span>
                      )}
                    </div>
                  </div>
                  <ul>
                    {results.documents.map((doc) => (
                      <li key={doc.id}>
                        <button
                          onClick={() => {
                            router.push(`/search?q=${encodeURIComponent(doc.file_name)}`);
                            setIsOpen(false);
                          }}
                          className="w-full px-4 py-2 text-left hover:bg-neutral-50 focus:bg-neutral-50 focus:outline-none"
                        >
                          <div className="text-sm font-medium text-neutral-800 truncate">
                            {doc.file_name}
                          </div>
                          {doc.ai_category && (
                            <div className="text-xs text-neutral-500 truncate">
                              {doc.ai_category}
                            </div>
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                  <button
                    onClick={navigateToSearch}
                    className="w-full px-4 py-2 text-sm text-blue-600 hover:bg-blue-50 text-left font-medium border-t border-neutral-100"
                  >
                    View all document results
                  </button>
                </div>
              )}

              {/* File DNA Section */}
              {results.fileDNA.length > 0 && (
                <div className={results.documents.length > 0 ? "border-t border-neutral-200" : ""}>
                  <div className="px-4 py-2 bg-neutral-50 border-b border-neutral-100">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-neutral-500 uppercase tracking-wide">
                        File DNA
                      </span>
                      {results.fileDNATotal > MAX_PREVIEW_RESULTS && (
                        <span className="text-xs text-neutral-400">
                          +{results.fileDNATotal - MAX_PREVIEW_RESULTS} more
                        </span>
                      )}
                    </div>
                  </div>
                  <ul>
                    {results.fileDNA.map((file, index) => (
                      <li key={`${file.path}-${index}`}>
                        <button
                          onClick={() => {
                            router.push(`/file-intelligence?search=${encodeURIComponent(file.filename)}`);
                            setIsOpen(false);
                          }}
                          className="w-full px-4 py-2 text-left hover:bg-neutral-50 focus:bg-neutral-50 focus:outline-none"
                        >
                          <div className="text-sm font-medium text-neutral-800 truncate">
                            {file.filename}
                          </div>
                          {file.tags.length > 0 && (
                            <div className="text-xs text-neutral-500 truncate">
                              Tags: {file.tags.slice(0, 3).join(", ")}
                              {file.tags.length > 3 && "..."}
                            </div>
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                  <button
                    onClick={navigateToFileDNA}
                    className="w-full px-4 py-2 text-sm text-blue-600 hover:bg-blue-50 text-left font-medium border-t border-neutral-100"
                  >
                    View all File DNA results
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
