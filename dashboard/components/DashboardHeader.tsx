"use client";

import Link from "next/link";
import { GlobalSearchBar } from "./GlobalSearchBar";

export function DashboardHeader() {
  return (
    <header className="sticky top-0 z-40 bg-white border-b border-neutral-200">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-14 gap-4">
          {/* Logo/Home Link */}
          <Link
            href="/"
            className="flex-shrink-0 text-lg font-semibold text-neutral-800 hover:text-neutral-600 transition-colors"
          >
            Organizer
          </Link>

          {/* Global Search Bar - Centered */}
          <div className="flex-1 max-w-md mx-auto">
            <GlobalSearchBar />
          </div>

          {/* Navigation Links (optional - kept minimal for now) */}
          <nav className="hidden sm:flex items-center gap-4 flex-shrink-0">
            <Link
              href="/search"
              className="text-sm text-neutral-600 hover:text-neutral-800 transition-colors"
            >
              Search
            </Link>
            <Link
              href="/browse"
              className="text-sm text-neutral-600 hover:text-neutral-800 transition-colors"
            >
              Browse
            </Link>
            <Link
              href="/agents"
              className="text-sm text-neutral-600 hover:text-neutral-800 transition-colors"
            >
              Agents
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
}
