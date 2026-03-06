/**
 * Enrichment Search Utilities
 *
 * Searches the local enrichment cache to power natural language search.
 * The enrichment cache contains LLM-extracted metadata like organizations,
 * date references, people, topics, and summaries.
 */

import path from "path";
import fs from "fs/promises";

const ICLOUD_BASE =
  process.env.NEXT_PUBLIC_ICLOUD_BASE_PATH ||
  "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs";
const ENRICHMENT_CACHE_PATH = path.join(
  ICLOUD_BASE,
  ".organizer",
  "agent",
  "enrichment_cache.json"
);

/**
 * Enrichment data extracted from file content.
 */
export interface FileEnrichment {
  document_type: string;
  date_references: string[];
  people: string[];
  organizations: string[];
  key_topics: string[];
  summary: string;
  suggested_tags: string[];
  confidence: number;
  model_used: string;
  used_keyword_fallback: boolean;
  enriched_at: string;
  duration_ms: number;
}

/**
 * Cache entry containing enrichment and file metadata.
 */
export interface EnrichmentCacheEntry {
  file_hash: string;
  file_path: string;
  enrichment: FileEnrichment;
  cached_at: string;
}

/**
 * The full enrichment cache structure.
 */
export interface EnrichmentCache {
  version: string;
  updated_at: string;
  entry_count: number;
  entries: EnrichmentCacheEntry[];
}

/**
 * Search result with enrichment match details.
 */
export interface EnrichmentSearchResult {
  file_path: string;
  file_hash: string;
  filename: string;
  enrichment: FileEnrichment;
  match_reasons: string[];
  match_score: number;
}

/**
 * Load the enrichment cache from disk.
 */
export async function loadEnrichmentCache(): Promise<EnrichmentCache | null> {
  try {
    const data = await fs.readFile(ENRICHMENT_CACHE_PATH, "utf-8");
    return JSON.parse(data) as EnrichmentCache;
  } catch {
    return null;
  }
}

/**
 * Check if a query term matches a list of strings (case-insensitive).
 */
function matchesAny(query: string, items: string[]): boolean {
  if (!query || query.length === 0) {
    return false;
  }
  const queryLower = query.toLowerCase();
  return items.some((item) => item.toLowerCase().includes(queryLower));
}

/**
 * Check if enrichment matches a search query.
 * Returns match reasons and a score for ranking.
 */
export function matchEnrichment(
  enrichment: FileEnrichment,
  query: string,
  parsedQuery?: {
    years: number[];
    organizations: string[];
    searchTerms: string[];
    category: string | null;
  }
): { matches: boolean; reasons: string[]; score: number } {
  const reasons: string[] = [];
  let score = 0;
  const queryLower = query.toLowerCase();

  // Early return for empty/no query with no parsed filters
  const hasFilters = parsedQuery && (
    parsedQuery.years.length > 0 ||
    parsedQuery.organizations.length > 0 ||
    parsedQuery.searchTerms.length > 0 ||
    parsedQuery.category !== null
  );
  if (!query || query.trim().length === 0) {
    if (!hasFilters) {
      return { matches: false, reasons: [], score: 0 };
    }
  }

  // Check organizations (high weight)
  if (parsedQuery?.organizations && parsedQuery.organizations.length > 0) {
    for (const org of parsedQuery.organizations) {
      if (matchesAny(org, enrichment.organizations)) {
        reasons.push(`organization: ${org}`);
        score += 10;
      }
    }
  }

  // Check date references (high weight)
  if (parsedQuery?.years && parsedQuery.years.length > 0) {
    for (const year of parsedQuery.years) {
      const yearStr = year.toString();
      if (enrichment.date_references.some((d) => d.includes(yearStr))) {
        reasons.push(`date: ${year}`);
        score += 8;
      }
    }
  }

  // Check document type against category (high weight)
  if (parsedQuery?.category) {
    // Normalize both for comparison (underscores/spaces, case)
    const categoryNormalized = parsedQuery.category.toLowerCase().replace(/_/g, "");
    const docTypeNormalized = enrichment.document_type.toLowerCase().replace(/_/g, "");
    if (
      docTypeNormalized.includes(categoryNormalized) ||
      categoryNormalized.includes(docTypeNormalized) ||
      // Also check exact match with underscore
      enrichment.document_type.toLowerCase() === parsedQuery.category.toLowerCase()
    ) {
      reasons.push(`document_type: ${enrichment.document_type}`);
      score += 7;
    }
  }

  // Check summary (medium weight)
  if (enrichment.summary && queryLower) {
    const summaryLower = enrichment.summary.toLowerCase();
    // Check for query terms in summary
    const terms = queryLower.split(/\s+/).filter((t) => t.length > 2);
    let termMatches = 0;
    for (const term of terms) {
      if (summaryLower.includes(term)) {
        termMatches++;
      }
    }
    if (termMatches >= 2 || (terms.length === 1 && termMatches === 1)) {
      reasons.push("summary match");
      score += 5;
    }
  }

  // Check key topics (medium weight)
  if (parsedQuery?.searchTerms && parsedQuery.searchTerms.length > 0) {
    for (const term of parsedQuery.searchTerms) {
      if (matchesAny(term, enrichment.key_topics)) {
        reasons.push(`topic: ${term}`);
        score += 4;
      }
    }
  }

  // Check people (medium weight)
  if (enrichment.people.length > 0) {
    const words = queryLower.split(/\s+/);
    for (const person of enrichment.people) {
      const personLower = person.toLowerCase();
      if (words.some((w) => personLower.includes(w) && w.length > 2)) {
        reasons.push(`person: ${person}`);
        score += 4;
      }
    }
  }

  // Check suggested tags (low weight)
  if (matchesAny(queryLower, enrichment.suggested_tags)) {
    reasons.push("tag match");
    score += 2;
  }

  // Direct text search in summary, document_type, organizations, topics
  if (reasons.length === 0 && queryLower.length > 2) {
    if (enrichment.summary.toLowerCase().includes(queryLower)) {
      reasons.push("text in summary");
      score += 3;
    }
    if (enrichment.document_type.toLowerCase().includes(queryLower)) {
      reasons.push("text in document_type");
      score += 3;
    }
    if (matchesAny(queryLower, enrichment.organizations)) {
      reasons.push("text in organizations");
      score += 3;
    }
    if (matchesAny(queryLower, enrichment.key_topics)) {
      reasons.push("text in topics");
      score += 2;
    }
  }

  return {
    matches: reasons.length > 0,
    reasons,
    score,
  };
}

/**
 * Search the enrichment cache for matching files.
 *
 * @param query - The search query string
 * @param parsedQuery - Optional parsed query with extracted entities
 * @param limit - Maximum results to return
 * @returns Array of matching enrichment results, sorted by score
 */
export async function searchEnrichmentCache(
  query: string,
  parsedQuery?: {
    years: number[];
    organizations: string[];
    searchTerms: string[];
    category: string | null;
  },
  limit: number = 50
): Promise<EnrichmentSearchResult[]> {
  const cache = await loadEnrichmentCache();
  if (!cache || !cache.entries) {
    return [];
  }

  const results: EnrichmentSearchResult[] = [];

  for (const entry of cache.entries) {
    const match = matchEnrichment(entry.enrichment, query, parsedQuery);
    if (match.matches) {
      results.push({
        file_path: entry.file_path,
        file_hash: entry.file_hash,
        filename: path.basename(entry.file_path),
        enrichment: entry.enrichment,
        match_reasons: match.reasons,
        match_score: match.score,
      });
    }
  }

  // Sort by score descending
  results.sort((a, b) => b.match_score - a.match_score);

  return results.slice(0, limit);
}

/**
 * Get enrichment for a specific file by hash.
 */
export async function getEnrichmentByHash(
  fileHash: string
): Promise<FileEnrichment | null> {
  const cache = await loadEnrichmentCache();
  if (!cache || !cache.entries) {
    return null;
  }

  const entry = cache.entries.find((e) => e.file_hash === fileHash);
  return entry?.enrichment || null;
}

/**
 * Get enrichment for a specific file by path.
 */
export async function getEnrichmentByPath(
  filePath: string
): Promise<FileEnrichment | null> {
  const cache = await loadEnrichmentCache();
  if (!cache || !cache.entries) {
    return null;
  }

  const entry = cache.entries.find((e) => e.file_path === filePath);
  return entry?.enrichment || null;
}

/**
 * Get all enrichments as a map keyed by file hash.
 */
export async function getEnrichmentMap(): Promise<Map<string, FileEnrichment>> {
  const cache = await loadEnrichmentCache();
  const map = new Map<string, FileEnrichment>();

  if (cache?.entries) {
    for (const entry of cache.entries) {
      map.set(entry.file_hash, entry.enrichment);
    }
  }

  return map;
}

/**
 * Get all enrichments as a map keyed by file path.
 */
export async function getEnrichmentMapByPath(): Promise<
  Map<string, FileEnrichment>
> {
  const cache = await loadEnrichmentCache();
  const map = new Map<string, FileEnrichment>();

  if (cache?.entries) {
    for (const entry of cache.entries) {
      map.set(entry.file_path, entry.enrichment);
    }
  }

  return map;
}
