"use client";

import { useState, useEffect, FormEvent } from "react";
import { cn } from "@/lib/utils";
import { HelpTooltip, HELP_TEXT } from "./Tooltip";

// Example queries from the PRD
export const EXAMPLE_QUERIES = [
  "Show me a file that is a verizon bill from 2024?",
  "Find all tax documents from 2023",
  "Show me VA claims documents",
  "Find invoices from Amazon",
  "Show me documents from 2025",
  "Find all bank statements",
  "Show me contracts",
];

// Rotation interval for placeholder examples (in milliseconds)
const PLACEHOLDER_ROTATION_INTERVAL = 4000;

interface SearchInputProps {
  onSearch: (query: string) => void;
  isLoading?: boolean;
  initialQuery?: string;
  className?: string;
}

export function SearchInput({
  onSearch,
  isLoading = false,
  initialQuery = "",
  className,
}: SearchInputProps) {
  const [query, setQuery] = useState(initialQuery);
  const [placeholderIndex, setPlaceholderIndex] = useState(0);

  // Rotate through example queries in the placeholder
  useEffect(() => {
    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % EXAMPLE_QUERIES.length);
    }, PLACEHOLDER_ROTATION_INTERVAL);

    return () => clearInterval(interval);
  }, []);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
    }
  };

  const handleExampleClick = (example: string) => {
    setQuery(example);
    onSearch(example);
  };

  return (
    <div className={cn("space-y-4", className)}>
      {/* Mobile: stacked layout, Desktop: side by side */}
      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Try: "${EXAMPLE_QUERIES[placeholderIndex]}"`}
          className="flex-1 px-4 py-3 border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-neutral-800 placeholder:text-neutral-400 text-base"
          disabled={isLoading}
          aria-label="Search query"
        />
        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium w-full sm:w-auto"
        >
          {isLoading ? "Searching..." : "Search"}
        </button>
      </form>

      <div className="space-y-2">
        <div className="flex items-center gap-1">
          <p className="text-sm text-neutral-500">Try an example query:</p>
          <HelpTooltip text={HELP_TEXT.searchExamples} size={14} />
        </div>
        {/* Mobile: horizontal scroll, Desktop: wrap */}
        <div className="flex gap-2 overflow-x-auto pb-2 sm:flex-wrap sm:overflow-visible sm:pb-0 -mx-4 px-4 sm:mx-0 sm:px-0">
          {EXAMPLE_QUERIES.map((example, index) => (
            <button
              key={index}
              onClick={() => handleExampleClick(example)}
              disabled={isLoading}
              className="px-3 py-1.5 text-sm bg-neutral-100 text-neutral-700 rounded-full hover:bg-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap flex-shrink-0"
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
