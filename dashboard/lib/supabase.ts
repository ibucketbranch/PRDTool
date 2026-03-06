import { createClient, SupabaseClient } from "@supabase/supabase-js";

// Import canonical registry integration
import {
  loadCanonicalRegistry,
  assessFolderWithRegistry,
  type CanonicalRegistry,
} from "./canonical-registry";

// Import execution logs integration
import {
  getFileMovementHistory,
} from "./execution-logs";

// Import enrichment search utilities
import {
  searchEnrichmentCache,
  getEnrichmentMapByPath,
  type FileEnrichment,
} from "./enrichment-search";

// Database types based on the PRD schema
export interface Document {
  id: string;
  file_name: string;
  current_path: string;
  ai_category: string | null;
  ai_subcategories: string[] | null;
  ai_summary: string | null;
  entities: DocumentEntities | null;
  key_dates: string[] | null;
  folder_hierarchy: string[] | null;
  file_modified_at: string | null;
  pdf_modified_date: string | null;
  created_at: string;
  updated_at: string;
  // Enrichment data (populated from cache, not from database)
  enrichment?: FileEnrichment | null;
  enrichment_match_reasons?: string[];
  enrichment_match_score?: number;
}

export interface DocumentEntities {
  people?: string[];
  organizations?: string[];
  amounts?: string[];
  [key: string]: string[] | undefined;
}

export interface DocumentLocation {
  id: string;
  document_id: string;
  location_path: string;
  location_type: "primary" | "previous" | "current";
  is_accessible: boolean;
  discovered_at: string;
}

export interface CategoryCount {
  ai_category: string;
  count: number;
}

export interface YearCount {
  year: number;
  count: number;
}

export interface ContextBinCount {
  context_bin: string;
  count: number;
}

export interface StatisticsResult {
  categories: CategoryCount[];
  dateDistribution: YearCount[];
  contextBins: ContextBinCount[];
  minYear?: number;
  maxYear?: number;
  error?: string;
}

// Supabase client singleton
let supabaseClient: SupabaseClient | null = null;

export function getSupabaseClient(): SupabaseClient {
  if (supabaseClient) {
    return supabaseClient;
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseKey) {
    throw new Error(
      "Missing Supabase environment variables. " +
        "Please set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY"
    );
  }

  supabaseClient = createClient(supabaseUrl, supabaseKey);
  return supabaseClient;
}

// ============================================================================
// Statistics Cache - Performance Optimization
// ============================================================================

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

interface StatisticsCache {
  statistics: CacheEntry<StatisticsResult> | null;
}

const cache: StatisticsCache = {
  statistics: null,
};

// Cache TTL in milliseconds (default: 30 seconds)
const STATISTICS_CACHE_TTL = 30 * 1000;

/**
 * Check if a cache entry is still valid
 */
function isCacheValid<T>(entry: CacheEntry<T> | null, ttl: number): boolean {
  if (!entry) return false;
  return Date.now() - entry.timestamp < ttl;
}

/**
 * Clear the statistics cache (useful after data modifications)
 */
export function clearStatisticsCache(): void {
  cache.statistics = null;
}

// Test connection and return basic info
export async function testConnection(): Promise<{
  connected: boolean;
  documentCount: number;
  error?: string;
}> {
  try {
    const supabase = getSupabaseClient();
    const { count, error } = await supabase
      .from("documents")
      .select("*", { count: "exact", head: true });

    if (error) {
      return {
        connected: false,
        documentCount: 0,
        error: error.message,
      };
    }

    return {
      connected: true,
      documentCount: count ?? 0,
    };
  } catch (err) {
    return {
      connected: false,
      documentCount: 0,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

// Document list filter options
export interface DocumentListOptions {
  category?: string;
  contextBin?: string;
  startYear?: number;
  endYear?: number;
  search?: string;
  limit?: number;
  offset?: number;
  orderBy?: string;
  orderDirection?: "asc" | "desc";
}

// Document list result
export interface DocumentListResult {
  documents: Document[];
  total: number;
  filteredTotal: number;
  error?: string;
}

// Get all documents with optional filters (enhanced for Document Browser)
// Optimized: Uses streaming approach for large datasets
export async function getDocuments(
  options?: DocumentListOptions
): Promise<DocumentListResult> {
  try {
    const supabase = getSupabaseClient();

    // Optimization: If no context bin or date range filters, we can use server-side pagination
    const needsClientSideFiltering = !!(options?.contextBin || options?.startYear || options?.endYear);

    if (!needsClientSideFiltering) {
      // Optimized path: Pure server-side filtering and pagination
      return await getDocumentsServerSide(supabase, options);
    }

    // Fallback: Need client-side filtering for array columns
    // Optimization: Only fetch required columns for filtering, then fetch full docs for page
    return await getDocumentsWithClientFiltering(supabase, options);
  } catch (err) {
    return {
      documents: [],
      total: 0,
      filteredTotal: 0,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Server-side pagination when no array column filtering is needed
 * Much more efficient for large datasets
 */
async function getDocumentsServerSide(
  supabase: SupabaseClient,
  options?: DocumentListOptions
): Promise<DocumentListResult> {
  // Build base query with server-side pagination
  let query = supabase.from("documents").select("*", { count: "exact" });

  // Apply category filter
  if (options?.category) {
    query = query.eq("ai_category", options.category);
  }

  // Apply keyword search across multiple fields
  if (options?.search) {
    const searchTerm = options.search;
    query = query.or(
      `file_name.ilike.%${searchTerm}%,` +
        `ai_category.ilike.%${searchTerm}%,` +
        `ai_summary.ilike.%${searchTerm}%,` +
        `current_path.ilike.%${searchTerm}%`
    );
  }

  // Apply sorting
  if (options?.orderBy) {
    query = query.order(options.orderBy, {
      ascending: options.orderDirection === "asc",
    });
  } else {
    query = query.order("created_at", { ascending: false });
  }

  // Apply server-side pagination
  const offset = options?.offset ?? 0;
  const limit = options?.limit ?? 20;
  query = query.range(offset, offset + limit - 1);

  const { data, count, error } = await query;

  if (error) {
    return { documents: [], total: 0, filteredTotal: 0, error: error.message };
  }

  return {
    documents: (data || []) as Document[],
    total: count ?? 0,
    filteredTotal: count ?? 0, // Same as total when no client-side filtering
  };
}

/**
 * Client-side filtering for array column operations (context bins, date ranges)
 * Optimization: Fetch only IDs matching criteria, then fetch full documents
 */
async function getDocumentsWithClientFiltering(
  supabase: SupabaseClient,
  options?: DocumentListOptions
): Promise<DocumentListResult> {
  // Step 1: Fetch minimal data for filtering (only columns needed for filter decisions)
  // Include file_modified_at and created_at for filename date extraction
  let filterQuery = supabase
    .from("documents")
    .select("id, ai_category, folder_hierarchy, key_dates, file_name, ai_summary, current_path, file_modified_at, created_at");

  // Apply category filter (can be done server-side)
  if (options?.category) {
    filterQuery = filterQuery.eq("ai_category", options.category);
  }

  // Apply keyword search
  if (options?.search) {
    const searchTerm = options.search;
    filterQuery = filterQuery.or(
      `file_name.ilike.%${searchTerm}%,` +
        `ai_category.ilike.%${searchTerm}%,` +
        `ai_summary.ilike.%${searchTerm}%,` +
        `current_path.ilike.%${searchTerm}%`
    );
  }

  const { data: filterData, error: filterError, count: totalCount } = await filterQuery;

  if (filterError) {
    return { documents: [], total: 0, filteredTotal: 0, error: filterError.message };
  }

  // Step 2: Apply client-side filters to get matching IDs
  let filteredDocs = (filterData || []) as Array<{
    id: string;
    ai_category: string | null;
    folder_hierarchy: string[] | null;
    key_dates: string[] | null;
    file_name: string;
    file_modified_at: string | null;
    created_at: string;
  }>;

  if (options?.contextBin) {
    filteredDocs = filterDocsByContextBin(filteredDocs, options.contextBin);
  }

  if (options?.startYear || options?.endYear) {
    filteredDocs = filterDocsByDateRange(
      filteredDocs,
      options.startYear,
      options.endYear
    );
  }

  const filteredTotal = filteredDocs.length;

  // Step 3: Apply pagination to get page IDs
  const offset = options?.offset ?? 0;
  const limit = options?.limit ?? 20;
  const pageIds = filteredDocs
    .slice(offset, offset + limit)
    .map(d => d.id);

  if (pageIds.length === 0) {
    return {
      documents: [],
      total: totalCount ?? 0,
      filteredTotal,
    };
  }

  // Step 4: Fetch full documents only for the current page
  let pageQuery = supabase
    .from("documents")
    .select("*")
    .in("id", pageIds);

  // Apply sorting
  if (options?.orderBy) {
    pageQuery = pageQuery.order(options.orderBy, {
      ascending: options.orderDirection === "asc",
    });
  } else {
    pageQuery = pageQuery.order("created_at", { ascending: false });
  }

  const { data: pageData, error: pageError } = await pageQuery;

  if (pageError) {
    return { documents: [], total: 0, filteredTotal: 0, error: pageError.message };
  }

  return {
    documents: (pageData || []) as Document[],
    total: totalCount ?? 0,
    filteredTotal,
  };
}

/**
 * Filter documents by context bin (for minimal data structure)
 */
function filterDocsByContextBin<T extends { folder_hierarchy: string[] | null }>(
  documents: T[],
  contextBin: string
): T[] {
  const binLower = contextBin.toLowerCase();

  return documents.filter((doc) => {
    // Extract meaningful context bin using shared logic
    const docContextBin = getContextBinFromHierarchy(doc.folder_hierarchy);
    return docContextBin.toLowerCase() === binLower;
  });
}

/**
 * Filter documents by date range (for minimal data structure)
 */
function filterDocsByDateRange<T extends { 
  key_dates: string[] | null;
  file_name?: string;
  file_modified_at?: string | null;
  created_at?: string;
}>(
  documents: T[],
  startYear?: number,
  endYear?: number
): T[] {
  if (!startYear && !endYear) return documents;

  return documents.filter((doc) => {
    // Get best date (prioritizes filename date)
    const bestDate = getBestDateForFiltering(
      doc.file_modified_at || null,
      doc.file_name || "",
      doc.created_at || ""
    );

    if (bestDate) {
      const docYear = extractYearFromDate(bestDate);
      if (docYear) {
        const afterStart = !startYear || docYear >= startYear;
        const beforeEnd = !endYear || docYear <= endYear;
        return afterStart && beforeEnd;
      }
    }
    
    // Final fallback: Use key_dates if no other date available
    if (doc.key_dates && Array.isArray(doc.key_dates)) {
      for (const dateStr of doc.key_dates) {
        const docYear = extractYearFromDate(dateStr);
        if (docYear) {
          const afterStart = !startYear || docYear >= startYear;
          const beforeEnd = !endYear || docYear <= endYear;
          if (afterStart && beforeEnd) {
            return true;
          }
        }
      }
    }

    return false;
  });
}

/**
 * Filter documents by context bin (top-level folder_hierarchy)
 */
function filterByContextBin(
  documents: Document[],
  contextBin: string
): Document[] {
  const binLower = contextBin.toLowerCase();

  return documents.filter((doc) => {
    // Extract meaningful context bin using shared logic
    const docContextBin = getContextBinFromHierarchy(doc.folder_hierarchy);
    return docContextBin.toLowerCase() === binLower;
  });
}

/**
 * Filter documents by date range (checks key_dates array)
 */
function filterByDateRange(
  documents: Document[],
  startYear?: number,
  endYear?: number
): Document[] {
  if (!startYear && !endYear) return documents;

  return documents.filter((doc) => {
    // Get best date (prioritizes filename date)
    const bestDate = getBestDateForFiltering(
      doc.file_modified_at,
      doc.file_name,
      doc.created_at
    );

    if (bestDate) {
      const docYear = extractYearFromDate(bestDate);
      if (docYear) {
        const afterStart = !startYear || docYear >= startYear;
        const beforeEnd = !endYear || docYear <= endYear;
        return afterStart && beforeEnd;
      }
    }
    
    // Final fallback: Use key_dates if no other date available
    if (doc.key_dates && Array.isArray(doc.key_dates)) {
      // Check if any key_date falls within the range
      for (const dateStr of doc.key_dates) {
        const docYear = extractYearFromDate(dateStr);
        if (docYear) {
          const afterStart = !startYear || docYear >= startYear;
          const beforeEnd = !endYear || docYear <= endYear;
          if (afterStart && beforeEnd) {
            return true;
          }
        }
      }
    }

    return false;
  });
}

// Get category statistics, optionally filtered by year range
export async function getCategoryStats(
  startYear?: number,
  endYear?: number
): Promise<{
  categories: CategoryCount[];
  error?: string;
}> {
  try {
    const supabase = getSupabaseClient();
    
    // Fetch documents with date fields for filtering
    const query = supabase
      .from("documents")
      .select("ai_category, file_modified_at, created_at, key_dates, file_name");

    const { data: docs, error: docsError } = await query;

    if (docsError) {
      return { categories: [], error: docsError.message };
    }

    // Filter by year range if provided
    let filteredDocs = docs || [];
    if (startYear || endYear) {
      filteredDocs = filterByDateRange(
        filteredDocs.map(doc => ({
          ...doc,
          file_modified_at: doc.file_modified_at as string | null,
          created_at: doc.created_at as string,
          key_dates: doc.key_dates as string[] | null,
          file_name: doc.file_name as string,
        })) as Document[],
        startYear,
        endYear
      );
    }

    // Group by category manually
    const counts: Record<string, number> = {};
    for (const doc of filteredDocs) {
      const cat = doc.ai_category || "uncategorized";
      counts[cat] = (counts[cat] || 0) + 1;
    }

    const categories = Object.entries(counts)
      .map(([ai_category, count]) => ({ ai_category, count }))
      .sort((a, b) => b.count - a.count);

    return { categories };
  } catch (err) {
    return {
      categories: [],
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

// Search documents using Full-Text Search (FTS) for queries >= 3 chars
// Falls back to ilike for short queries where FTS is less effective
export async function searchDocuments(
  query: string,
  limit: number = 20,
  offset: number = 0
): Promise<{
  documents: Document[];
  error?: string;
}> {
  try {
    const supabase = getSupabaseClient();
    const trimmedQuery = query.trim();

    // For short queries (< 3 chars), use ilike fallback
    // FTS is less useful for very short terms
    if (trimmedQuery.length < 3) {
      const { data, error } = await supabase
        .from("documents")
        .select("*")
        .or(
          `file_name.ilike.%${trimmedQuery}%,` +
            `ai_category.ilike.%${trimmedQuery}%,` +
            `ai_summary.ilike.%${trimmedQuery}%,` +
            `current_path.ilike.%${trimmedQuery}%`
        )
        .range(offset, offset + limit - 1)
        .limit(limit);

      if (error) {
        return { documents: [], error: error.message };
      }

      return { documents: data as Document[] };
    }

    // Use FTS for queries >= 3 chars
    // This leverages the GIN index for stemming and relevance ranking
    const { data, error } = await supabase.rpc("search_documents_fts", {
      search_query: trimmedQuery,
      result_limit: limit,
      result_offset: offset,
    });

    if (error) {
      // Fallback to ilike if FTS fails (e.g., function not deployed yet)
      console.warn("FTS search failed, falling back to ilike:", error.message);
      const { data: fallbackData, error: fallbackError } = await supabase
        .from("documents")
        .select("*")
        .or(
          `file_name.ilike.%${trimmedQuery}%,` +
            `ai_category.ilike.%${trimmedQuery}%,` +
            `ai_summary.ilike.%${trimmedQuery}%,` +
            `current_path.ilike.%${trimmedQuery}%`
        )
        .range(offset, offset + limit - 1)
        .limit(limit);

      if (fallbackError) {
        return { documents: [], error: fallbackError.message };
      }

      return { documents: fallbackData as Document[] };
    }

    // Map RPC result to Document type (RPC returns with rank column)
    const documents: Document[] = (data || []).map(
      (row: {
        id: string;
        file_name: string;
        current_path: string;
        ai_category: string | null;
        ai_subcategories: string[] | null;
        ai_summary: string | null;
        entities: DocumentEntities | null;
        key_dates: string[] | null;
        folder_hierarchy: string[] | null;
        file_modified_at: string | null;
        pdf_modified_date: string | null;
        created_at: string;
        updated_at: string;
        rank?: number;
      }) => ({
        id: row.id,
        file_name: row.file_name,
        current_path: row.current_path,
        ai_category: row.ai_category,
        ai_subcategories: row.ai_subcategories,
        ai_summary: row.ai_summary,
        entities: row.entities,
        key_dates: row.key_dates,
        folder_hierarchy: row.folder_hierarchy,
        file_modified_at: row.file_modified_at,
        pdf_modified_date: row.pdf_modified_date,
        created_at: row.created_at,
        updated_at: row.updated_at,
      })
    );

    return { documents };
  } catch (err) {
    return {
      documents: [],
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

// Reset client for testing
export function resetSupabaseClient(): void {
  supabaseClient = null;
}

// Get date distribution (documents grouped by year)
export async function getDateDistribution(): Promise<{
  dateDistribution: YearCount[];
  error?: string;
}> {
  try {
    const supabase = getSupabaseClient();

    // Get all documents with key_dates
    const { data, error } = await supabase
      .from("documents")
      .select("key_dates");

    if (error) {
      return { dateDistribution: [], error: error.message };
    }

    // Extract years from key_dates arrays and count
    const yearCounts: Record<number, number> = {};
    for (const doc of data || []) {
      const keyDates = doc.key_dates as string[] | null;
      if (keyDates && Array.isArray(keyDates)) {
        const yearsInDoc = new Set<number>();
        for (const dateStr of keyDates) {
          const year = extractYearFromDate(dateStr);
          if (year) {
            yearsInDoc.add(year);
          }
        }
        // Count each unique year once per document
        for (const year of yearsInDoc) {
          yearCounts[year] = (yearCounts[year] || 0) + 1;
        }
      }
    }

    const dateDistribution = Object.entries(yearCounts)
      .map(([year, count]) => ({ year: parseInt(year), count }))
      .sort((a, b) => b.year - a.year); // Most recent first

    return { dateDistribution };
  } catch (err) {
    return {
      dateDistribution: [],
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

// Helper function to extract year from various date formats
function extractYearFromDate(dateStr: string): number | null {
  if (!dateStr) return null;

  // Try ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:mm:ss)
  const isoMatch = dateStr.match(/^(\d{4})-\d{2}-\d{2}/);
  if (isoMatch) {
    return parseInt(isoMatch[1]);
  }

  // Try US format (MM/DD/YYYY or MM-DD-YYYY)
  const usMatch = dateStr.match(/\d{1,2}[-/]\d{1,2}[-/](\d{4})/);
  if (usMatch) {
    return parseInt(usMatch[1]);
  }

  // Try extracting any 4-digit year (1900-2099)
  const yearMatch = dateStr.match(/(19|20)\d{2}/);
  if (yearMatch) {
    return parseInt(yearMatch[0]);
  }

  return null;
}

/**
 * Extract date from filename (e.g., "112023" -> Nov 2023, "2022-11-18" -> Nov 18, 2022)
 * Returns ISO date string or null if no date found
 */
function extractDateFromFilename(filename: string): string | null {
  if (!filename) return null;

  // Pattern 1: YYYY-MM-DD (e.g., "eStmt_2022-11-18.pdf")
  const isoMatch = filename.match(/(\d{4}-\d{2}-\d{2})/);
  if (isoMatch) {
    return isoMatch[1];
  }

  // Pattern 2: MMDDYYYY or MMYYYY (e.g., "112023" -> Nov 2023, "CoinBase_112023.pdf")
  const mmddyyyyMatch = filename.match(/(\d{1,2})(\d{4})/);
  if (mmddyyyyMatch) {
    const month = parseInt(mmddyyyyMatch[1]);
    const year = parseInt(mmddyyyyMatch[2]);
    if (month >= 1 && month <= 12 && year >= 1900 && year <= 2099) {
      // Return first day of that month
      return `${year}-${String(month).padStart(2, "0")}-01`;
    }
  }

  // Pattern 3: MonthYYYY (e.g., "Aug2010", "Aug2010BoAStatement.pdf")
  const monthNames = [
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec"
  ];
  const monthMatch = filename.match(/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{4})/i);
  if (monthMatch) {
    const monthName = monthMatch[1].toLowerCase();
    const year = parseInt(monthMatch[2]);
    const month = monthNames.indexOf(monthName) + 1;
    if (month > 0 && year >= 1900 && year <= 2099) {
      return `${year}-${String(month).padStart(2, "0")}-01`;
    }
  }

  // Pattern 4: YYYYMMDD (e.g., "20221118")
  const yyyymmddMatch = filename.match(/(\d{4})(\d{2})(\d{2})/);
  if (yyyymmddMatch) {
    const year = parseInt(yyyymmddMatch[1]);
    const month = parseInt(yyyymmddMatch[2]);
    const day = parseInt(yyyymmddMatch[3]);
    if (year >= 1900 && year <= 2099 && month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    }
  }

  return null;
}

/**
 * Get best date for filtering - prefers filename date if available
 */
function getBestDateForFiltering(
  fileModifiedAt: string | null,
  filename: string,
  createdAt: string
): string | null {
  // Extract date from filename first (most accurate for document date)
  const filenameDate = extractDateFromFilename(filename);
  if (filenameDate) {
    return filenameDate;
  }

  // Fallback to file_modified_at if available
  if (fileModifiedAt) {
    // Check if it's a suspicious future date (beyond current year + 1)
    const modifiedYear = new Date(fileModifiedAt).getFullYear();
    const currentYear = new Date().getFullYear();
    // If it's more than 1 year in the future, skip it
    if (modifiedYear > currentYear + 1) {
      // Use created_at instead
      return createdAt;
    }
    return fileModifiedAt;
  }

  // Final fallback to created_at
  return createdAt;
}

// Helper function to extract context bin from hierarchy (shared logic)
function getContextBinFromHierarchy(hierarchy: string[] | null): string {
  if (!hierarchy || !Array.isArray(hierarchy) || hierarchy.length === 0) {
    return "uncategorized";
  }

  // System paths to skip (including user home directory names)
  const systemPaths = new Set([
    "/",
    "Users",
    "Library",
    "System",
    "Applications",
    "Volumes",
    "private",
    "var",
    "usr",
    "bin",
    "sbin",
    "etc",
    "tmp",
    "opt",
    "home",
  ]);

  // Look for meaningful organizational folders
  // Skip system paths and user home directories
  for (let i = 0; i < hierarchy.length; i++) {
    const folder = hierarchy[i];
    if (!folder) continue;

    const folderLower = folder.toLowerCase();
    
    // Skip system paths
    if (systemPaths.has(folder) || systemPaths.has(folderLower)) {
      continue;
    }

    // Skip if it looks like a user home directory (common patterns)
    // User names are typically after "Users" in the path
    if (i > 0 && hierarchy[i - 1]?.toLowerCase() === "users") {
      continue; // Skip the username itself
    }

    // Look for meaningful organizational folders
    if (
      folderLower.includes("documents") ||
      folderLower.includes("desktop") ||
      folderLower.includes("downloads") ||
      folderLower.includes("icloud") ||
      folderLower.includes("dropbox") ||
      folderLower.includes("onedrive") ||
      folderLower.includes("google drive") ||
      folderLower.includes("personal") ||
      folderLower.includes("work") ||
      folderLower.includes("archive") ||
      folderLower.includes("mobile documents") ||
      folderLower.includes("com~apple~clouddocs") ||
      folderLower.includes("bin") && !systemPaths.has(folderLower) // "Personal Bin", "Work Bin", etc.
    ) {
      return folder; // Return the original case
    }
  }

  // If no meaningful folder found, look for the deepest non-system folder
  // This handles cases where the meaningful folder is deeper in the hierarchy
  for (let i = hierarchy.length - 1; i >= 0; i--) {
    const folder = hierarchy[i];
    if (!folder) continue;

    const folderLower = folder.toLowerCase();
    
    // Skip system paths
    if (systemPaths.has(folder) || systemPaths.has(folderLower)) {
      continue;
    }

    // Skip if it looks like a user home directory
    if (i > 0 && hierarchy[i - 1]?.toLowerCase() === "users") {
      continue;
    }

    // Use the deepest non-system folder as fallback
    if (folder.length > 1) {
      return folder;
    }
  }

  return "uncategorized";
}

// Get context bin counts (from folder_hierarchy), optionally filtered by year range
export async function getContextBinCounts(
  startYear?: number,
  endYear?: number
): Promise<{
  contextBins: ContextBinCount[];
  error?: string;
}> {
  try {
    const supabase = getSupabaseClient();

    // Fetch documents with date fields for filtering
    const query = supabase
      .from("documents")
      .select("folder_hierarchy, file_modified_at, created_at, key_dates, file_name");

    const { data: docs, error: docsError } = await query;

    if (docsError) {
      return { contextBins: [], error: docsError.message };
    }

    // Filter by year range if provided
    let filteredDocs = docs || [];
    if (startYear || endYear) {
      filteredDocs = filterByDateRange(
        filteredDocs.map(doc => ({
          ...doc,
          file_modified_at: doc.file_modified_at as string | null,
          created_at: doc.created_at as string,
          key_dates: doc.key_dates as string[] | null,
          file_name: doc.file_name as string,
        })) as Document[],
        startYear,
        endYear
      );
    }

    // Extract context bins from folder_hierarchy arrays using shared extraction logic
    const binCounts: Record<string, number> = {};
    for (const doc of filteredDocs) {
      const hierarchy = doc.folder_hierarchy as string[] | null;
      const contextBin = getContextBinFromHierarchy(hierarchy);
      binCounts[contextBin] = (binCounts[contextBin] || 0) + 1;
    }

    const contextBins = Object.entries(binCounts)
      .map(([context_bin, count]) => ({ context_bin, count }))
      .sort((a, b) => b.count - a.count);

    return { contextBins };
  } catch (err) {
    return {
      contextBins: [],
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

// Get all statistics combined with caching
export async function getStatistics(bypassCache: boolean = false): Promise<StatisticsResult> {
  // Check cache first (unless bypassing)
  if (!bypassCache && isCacheValid(cache.statistics, STATISTICS_CACHE_TTL)) {
    return cache.statistics!.data;
  }

  // Optimized: Fetch all required data in a single query where possible
  const result = await getStatisticsOptimized();

  // Update cache
  if (!result.error) {
    cache.statistics = {
      data: result,
      timestamp: Date.now(),
    };
  }

  return result;
}

/**
 * Optimized statistics retrieval - fetches minimal data in fewer queries
 * Instead of fetching all documents 3 times, we fetch once and compute all stats
 */
async function getStatisticsOptimized(): Promise<StatisticsResult> {
  try {
    const supabase = getSupabaseClient();

    // Single optimized query: fetch only the columns we need for statistics
    // This is much more efficient than 3 separate full-document queries
    const { data, error } = await supabase
      .from("documents")
      .select("ai_category, key_dates, folder_hierarchy, file_modified_at, created_at");

    if (error) {
      return {
        categories: [],
        dateDistribution: [],
        contextBins: [],
        error: error.message,
      };
    }

    // Process all statistics from the single result set
    const categoryCounts: Record<string, number> = {};
    const yearCounts: Record<number, number> = {};
    const binCounts: Record<string, number> = {};
    const yearsFromModifiedDate: number[] = [];

    for (const doc of data || []) {
      // Category counts
      const cat = doc.ai_category || "uncategorized";
      categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;

      // Year counts (from file_modified_at - primary source for year filtering)
      const fileModifiedAt = doc.file_modified_at as string | null;
      if (fileModifiedAt) {
        const year = extractYearFromDate(fileModifiedAt);
        if (year) {
          yearsFromModifiedDate.push(year);
          yearCounts[year] = (yearCounts[year] || 0) + 1;
        }
      } else {
        // Fallback: Try created_at if file_modified_at is not available
        // (since most existing docs don't have file_modified_at yet)
        const createdAt = (doc as any).created_at as string | null;
        if (createdAt) {
          const year = extractYearFromDate(createdAt);
          if (year) {
            yearsFromModifiedDate.push(year);
            yearCounts[year] = (yearCounts[year] || 0) + 1;
          }
        } else {
          // Final fallback to key_dates
          const keyDates = doc.key_dates as string[] | null;
          if (keyDates && Array.isArray(keyDates)) {
            const yearsInDoc = new Set<number>();
            for (const dateStr of keyDates) {
              const year = extractYearFromDate(dateStr);
              if (year) {
                yearsInDoc.add(year);
              }
            }
            for (const year of yearsInDoc) {
              yearCounts[year] = (yearCounts[year] || 0) + 1;
            }
          }
        }
      }

      // Context bin counts (from folder_hierarchy) using shared extraction logic
      const hierarchy = doc.folder_hierarchy as string[] | null;
      const contextBin = getContextBinFromHierarchy(hierarchy);
      binCounts[contextBin] = (binCounts[contextBin] || 0) + 1;
    }

    // Calculate min and max years from file_modified_at
    let minYear: number | undefined;
    let maxYear: number | undefined;
    if (yearsFromModifiedDate.length > 0) {
      minYear = Math.min(...yearsFromModifiedDate);
      maxYear = Math.max(...yearsFromModifiedDate);
    }

    // Convert to arrays and sort
    const categories = Object.entries(categoryCounts)
      .map(([ai_category, count]) => ({ ai_category, count }))
      .sort((a, b) => b.count - a.count);

    const dateDistribution = Object.entries(yearCounts)
      .map(([year, count]) => ({ year: parseInt(year), count }))
      .sort((a, b) => b.year - a.year);

    const contextBins = Object.entries(binCounts)
      .map(([context_bin, count]) => ({ context_bin, count }))
      .sort((a, b) => b.count - a.count);

    return {
      categories,
      dateDistribution,
      contextBins,
      minYear,
      maxYear,
    };
  } catch (err) {
    return {
      categories: [],
      dateDistribution: [],
      contextBins: [],
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

// Natural language search with parsed query filters and enrichment data
// Uses FTS (full-text search) for text terms and JSONB queries for organization filtering
export async function naturalLanguageSearch(
  parsedQuery: {
    originalQuery: string;
    searchTerms: string[];
    category: string | null;
    years: number[];
    organizations: string[];
  },
  limit: number = 20,
  offset: number = 0
): Promise<{
  documents: Document[];
  enrichmentMatches?: number;
  error?: string;
}> {
  try {
    const supabase = getSupabaseClient();

    // Combine all search terms (searchTerms + organizations) for FTS
    const allSearchTerms = [
      ...parsedQuery.searchTerms,
      ...parsedQuery.organizations,
    ].filter((t) => t.trim().length > 0);

    // Run database search and enrichment search in parallel
    const [dbResult, enrichmentResults, enrichmentMap] = await Promise.all([
      // Database search using FTS RPC function
      (async () => {
        // Use FTS if we have search terms >= 3 chars total
        const combinedTermsLength = allSearchTerms.join(" ").trim().length;
        const shouldUseFTS = combinedTermsLength >= 3;

        if (shouldUseFTS) {
          const { data, error } = await supabase.rpc(
            "natural_language_search_fts",
            {
              search_terms: allSearchTerms.length > 0 ? allSearchTerms : null,
              category_filter: parsedQuery.category || null,
              organization_filters:
                parsedQuery.organizations.length > 0
                  ? parsedQuery.organizations
                  : null,
              result_limit: limit * 2,
              result_offset: offset,
            }
          );

          if (error) {
            console.warn(
              "FTS natural language search failed, falling back to ilike:",
              error.message
            );
            return fallbackToIlikeSearch(
              supabase,
              parsedQuery,
              allSearchTerms,
              limit,
              offset
            );
          }

          // If category filter produced 0 results, retry without it so
          // FTS text matching can still surface relevant documents.
          if (
            (data === null || data.length === 0) &&
            parsedQuery.category &&
            allSearchTerms.length > 0
          ) {
            const { data: retryData, error: retryError } = await supabase.rpc(
              "natural_language_search_fts",
              {
                search_terms: allSearchTerms,
                category_filter: null,
                organization_filters:
                  parsedQuery.organizations.length > 0
                    ? parsedQuery.organizations
                    : null,
                result_limit: limit * 2,
                result_offset: offset,
              }
            );

            if (!retryError && retryData && retryData.length > 0) {
              return { data: retryData, error: null, usedFTS: true };
            }
          }

          return {
            data: data || [],
            error: null,
            usedFTS: true,
          };
        } else {
          // For short/empty queries, use ilike fallback
          return fallbackToIlikeSearch(
            supabase,
            parsedQuery,
            allSearchTerms,
            limit,
            offset
          );
        }
      })(),
      // Enrichment cache search
      searchEnrichmentCache(parsedQuery.originalQuery, parsedQuery, limit),
      // Get enrichment map for attaching to database results
      getEnrichmentMapByPath(),
    ]);

    const { data, error, usedFTS } = dbResult as {
      data: (Document & { rank?: number })[];
      error: { message: string } | null;
      usedFTS?: boolean;
    };

    if (error) {
      return { documents: [], error: error.message };
    }

    // Map documents, stripping rank field from RPC results
    let documents: Document[] = (data || []).map((row) => {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { rank, ...doc } = row as Document & { rank?: number };
      return doc;
    });

    // Post-filter by years if specified (since key_dates is an array)
    // Note: This still needs to be done client-side as key_dates array filtering is complex
    if (parsedQuery.years.length > 0) {
      documents = filterByYears(documents, parsedQuery.years);
    }

    // Organization filtering is now done in SQL when using FTS
    // Only post-filter if we fell back to ilike
    if (!usedFTS && parsedQuery.organizations.length > 0) {
      documents = filterByOrganizations(documents, parsedQuery.organizations);
    }

    // Attach enrichment data to database documents
    for (const doc of documents) {
      const enrichment = enrichmentMap.get(doc.current_path);
      if (enrichment) {
        doc.enrichment = enrichment;
      }
    }

    // Merge enrichment-only results (files in cache but not found by DB query)
    const dbPaths = new Set(documents.map((d) => d.current_path));
    const enrichmentOnlyResults = enrichmentResults.filter(
      (er) => !dbPaths.has(er.file_path)
    );

    // If we have enrichment-only matches, try to find them in DB by path
    if (enrichmentOnlyResults.length > 0) {
      const enrichmentPaths = enrichmentOnlyResults.map((er) => er.file_path);

      // Query database for these specific paths
      const { data: enrichmentDocs, error: enrichError } = await supabase
        .from("documents")
        .select("*")
        .in("current_path", enrichmentPaths);

      if (!enrichError && enrichmentDocs) {
        // Attach enrichment data and match info to these documents
        for (const doc of enrichmentDocs as Document[]) {
          const matchResult = enrichmentResults.find(
            (er) => er.file_path === doc.current_path
          );
          if (matchResult) {
            doc.enrichment = matchResult.enrichment;
            doc.enrichment_match_reasons = matchResult.match_reasons;
            doc.enrichment_match_score = matchResult.match_score;
          }
        }

        // Add enrichment-sourced documents to results
        documents = [...documents, ...(enrichmentDocs as Document[])];
      }
    }

    // Sort: prioritize documents with enrichment matches, then by enrichment score
    // FTS results are already sorted by relevance rank, but enrichment matches should still be prioritized
    documents.sort((a, b) => {
      const scoreA = a.enrichment_match_score || 0;
      const scoreB = b.enrichment_match_score || 0;
      return scoreB - scoreA;
    });

    // Apply final limit
    documents = documents.slice(0, limit);

    return {
      documents,
      enrichmentMatches: enrichmentResults.length,
    };
  } catch (err) {
    return {
      documents: [],
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Fallback to ilike-based search when FTS is not available or for short queries
 */
async function fallbackToIlikeSearch(
  supabase: SupabaseClient,
  parsedQuery: {
    originalQuery: string;
    searchTerms: string[];
    category: string | null;
    years: number[];
    organizations: string[];
  },
  allSearchTerms: string[],
  limit: number,
  offset: number = 0
): Promise<{
  data: Document[];
  error: { message: string } | null;
  usedFTS: boolean;
}> {
  const buildIlikeQuery = (withCategory: boolean) => {
    let q = supabase.from("documents").select("*");

    if (withCategory && parsedQuery.category) {
      q = q.eq("ai_category", parsedQuery.category);
    }

    const textConditions: string[] = [];

    for (const org of parsedQuery.organizations) {
      textConditions.push(`ai_summary.ilike.%${org}%`);
      textConditions.push(`file_name.ilike.%${org}%`);
      textConditions.push(`current_path.ilike.%${org}%`);
    }

    for (const term of parsedQuery.searchTerms) {
      textConditions.push(`ai_summary.ilike.%${term}%`);
      textConditions.push(`file_name.ilike.%${term}%`);
      textConditions.push(`ai_category.ilike.%${term}%`);
    }

    if (!parsedQuery.category && parsedQuery.originalQuery) {
      textConditions.push(
        `ai_category.ilike.%${parsedQuery.originalQuery.split(" ").join("%")}%`
      );
    }

    if (textConditions.length > 0) {
      q = q.or(textConditions.join(","));
    }

    q = q.range(offset, offset + limit * 2 - 1).limit(limit * 2);
    return q;
  };

  let query = buildIlikeQuery(true);

  const { data, error } = await query;

  // If category filter produced 0 results, retry without it
  if (
    !error &&
    (data === null || data.length === 0) &&
    parsedQuery.category &&
    allSearchTerms.length > 0
  ) {
    const retryQuery = buildIlikeQuery(false);
    const { data: retryData, error: retryError } = await retryQuery;
    return {
      data: (retryData || []) as Document[],
      error: retryError ? { message: retryError.message } : null,
      usedFTS: false,
    };
  }

  return {
    data: (data || []) as Document[],
    error: error ? { message: error.message } : null,
    usedFTS: false,
  };
}

/**
 * Filter documents by years - checks key_dates array
 */
function filterByYears(documents: Document[], years: number[]): Document[] {
  if (years.length === 0) return documents;

  return documents.filter((doc) => {
    if (!doc.key_dates || !Array.isArray(doc.key_dates)) {
      return false;
    }

    // Check if any key_date matches any of the requested years
    for (const dateStr of doc.key_dates) {
      const docYear = extractYearFromDate(dateStr);
      if (docYear && years.includes(docYear)) {
        return true;
      }
    }

    return false;
  });
}

/**
 * Filter documents by organizations - checks entities JSONB and text fields
 */
function filterByOrganizations(
  documents: Document[],
  organizations: string[]
): Document[] {
  if (organizations.length === 0) return documents;

  const orgsLower = organizations.map((o) => o.toLowerCase());

  return documents.filter((doc) => {
    // Check entities.organizations
    if (doc.entities?.organizations) {
      for (const docOrg of doc.entities.organizations) {
        if (orgsLower.some((o) => docOrg.toLowerCase().includes(o))) {
          return true;
        }
      }
    }

    // Check in ai_summary
    if (doc.ai_summary) {
      const summaryLower = doc.ai_summary.toLowerCase();
      if (orgsLower.some((o) => summaryLower.includes(o))) {
        return true;
      }
    }

    // Check in file_name
    if (doc.file_name) {
      const nameLower = doc.file_name.toLowerCase();
      if (orgsLower.some((o) => nameLower.includes(o))) {
        return true;
      }
    }

    return false;
  });
}

// Empty folder types
export interface EmptyFolderInfo {
  folderPath: string;
  originalFileCount: number;
  movedFiles: MovedFileInfo[];
  isEmpty: boolean;
  lastMoveDate: string | null;
}

export interface MovedFileInfo {
  documentId: string;
  fileName: string;
  originalPath: string;
  currentPath: string;
  movedAt: string;
}

export interface EmptyFoldersResult {
  emptyFolders: EmptyFolderInfo[];
  totalEmptyFolders: number;
  error?: string;
}

export interface FolderHistoryResult {
  folderPath: string;
  files: MovedFileInfo[];
  originalFileCount: number;
  error?: string;
}

/**
 * Get folders that had files moved from them (empty folders after consolidation)
 * Queries document_locations table for entries with location_type='previous'
 *
 * Optimized: Uses a single query with embedded document relation
 */
export async function getEmptyFolders(): Promise<EmptyFoldersResult> {
  try {
    const supabase = getSupabaseClient();

    // Optimized: Single query fetching previous locations with document info
    // This replaces 2 separate queries with a single joined query
    const { data: previousLocationsWithDocs, error: locError } = await supabase
      .from("document_locations")
      .select(`
        id,
        document_id,
        location_path,
        location_type,
        is_accessible,
        discovered_at,
        documents (
          id,
          file_name,
          current_path
        )
      `)
      .eq("location_type", "previous");

    if (locError) {
      return { emptyFolders: [], totalEmptyFolders: 0, error: locError.message };
    }

    if (!previousLocationsWithDocs || previousLocationsWithDocs.length === 0) {
      return { emptyFolders: [], totalEmptyFolders: 0 };
    }

    // Group by folder path (directory of the previous file location)
    const folderMap = new Map<string, MovedFileInfo[]>();

    for (const loc of previousLocationsWithDocs) {
      // Extract folder path from file path
      const folderPath = extractFolderPath(loc.location_path);
      if (!folderPath) continue;

      // Get document info from the joined data (documents is an array from Supabase join)
      const documents = (loc.documents || []) as Array<{ id: string; file_name: string; current_path: string }>;
      const docInfo = documents.length > 0 ? documents[0] : null;

      const movedFile: MovedFileInfo = {
        documentId: loc.document_id,
        fileName: docInfo?.file_name || extractFileName(loc.location_path),
        originalPath: loc.location_path,
        currentPath: docInfo?.current_path || "",
        movedAt: loc.discovered_at,
      };

      if (!folderMap.has(folderPath)) {
        folderMap.set(folderPath, []);
      }
      folderMap.get(folderPath)!.push(movedFile);
    }

    // Build empty folder info array
    const emptyFolders: EmptyFolderInfo[] = [];

    for (const [folderPath, movedFiles] of folderMap.entries()) {
      // Sort by moved date descending
      movedFiles.sort(
        (a, b) => new Date(b.movedAt).getTime() - new Date(a.movedAt).getTime()
      );

      const lastMoveDate =
        movedFiles.length > 0 ? movedFiles[0].movedAt : null;

      emptyFolders.push({
        folderPath,
        originalFileCount: movedFiles.length,
        movedFiles,
        isEmpty: true, // Will be verified by filesystem check in API route
        lastMoveDate,
      });
    }

    // Sort by original file count descending
    emptyFolders.sort((a, b) => b.originalFileCount - a.originalFileCount);

    return {
      emptyFolders,
      totalEmptyFolders: emptyFolders.length,
    };
  } catch (err) {
    return {
      emptyFolders: [],
      totalEmptyFolders: 0,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Get history of files that were moved from a specific folder
 */
export async function getFolderHistory(
  folderPath: string
): Promise<FolderHistoryResult> {
  try {
    const supabase = getSupabaseClient();

    // Get document_locations where path starts with the folder path
    const { data: previousLocations, error: locError } = await supabase
      .from("document_locations")
      .select("id, document_id, location_path, location_type, is_accessible, discovered_at")
      .eq("location_type", "previous")
      .ilike("location_path", `${folderPath}%`);

    if (locError) {
      return { folderPath, files: [], originalFileCount: 0, error: locError.message };
    }

    if (!previousLocations || previousLocations.length === 0) {
      return { folderPath, files: [], originalFileCount: 0 };
    }

    // Filter to only files directly in this folder (not in subfolders)
    const filesInFolder = previousLocations.filter((loc) => {
      const locFolder = extractFolderPath(loc.location_path);
      return locFolder === folderPath;
    });

    // Get document IDs
    const documentIds = filesInFolder.map((loc) => loc.document_id);

    // Get current paths for moved documents
    const { data: documents, error: docError } = await supabase
      .from("documents")
      .select("id, file_name, current_path")
      .in("id", documentIds);

    if (docError) {
      return { folderPath, files: [], originalFileCount: 0, error: docError.message };
    }

    // Create a map of document_id to current info
    const docMap = new Map(
      (documents || []).map((doc) => [
        doc.id,
        { fileName: doc.file_name, currentPath: doc.current_path },
      ])
    );

    // Build moved file info array
    const files: MovedFileInfo[] = filesInFolder.map((loc) => {
      const docInfo = docMap.get(loc.document_id);
      return {
        documentId: loc.document_id,
        fileName: docInfo?.fileName || extractFileName(loc.location_path),
        originalPath: loc.location_path,
        currentPath: docInfo?.currentPath || "",
        movedAt: loc.discovered_at,
      };
    });

    // Sort by moved date descending
    files.sort(
      (a, b) => new Date(b.movedAt).getTime() - new Date(a.movedAt).getTime()
    );

    return {
      folderPath,
      files,
      originalFileCount: files.length,
    };
  } catch (err) {
    return {
      folderPath,
      files: [],
      originalFileCount: 0,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Extract folder path from a file path
 */
function extractFolderPath(filePath: string): string {
  if (!filePath) return "";
  const lastSlash = filePath.lastIndexOf("/");
  if (lastSlash === -1) return "";
  return filePath.substring(0, lastSlash);
}

/**
 * Extract file name from a file path
 */
function extractFileName(filePath: string): string {
  if (!filePath) return "";
  const lastSlash = filePath.lastIndexOf("/");
  if (lastSlash === -1) return filePath;
  return filePath.substring(lastSlash + 1);
}

// ============================================================================
// Folder Assessment Logic
// ============================================================================

/**
 * Category patterns for matching folder names to AI categories
 * Maps category keywords to their corresponding AI category names
 *
 * NOTE: This is synchronized with PYTHON_CATEGORY_PATTERNS from canonical-registry.ts
 * which mirrors organizer/category_mapper.py CONSOLIDATION_CATEGORIES
 */
export const CATEGORY_PATTERNS: Record<string, string[]> = {
  // Employment (synced with Python)
  employment: ["resume", "resumes", "cv", "cover letter", "cover_letter", "coverletter", "job", "application", "job application", "employment", "career", "interview"],
  // Finances (synced with Python)
  finances: ["tax", "taxes", "tax return", "tax_return", "taxreturn", "invoice", "invoices", "receipt", "receipts", "budget", "financial", "finance", "bank", "banking", "statement", "expense", "expenses"],
  utility_bill: ["utility", "utilities", "verizon", "att", "comcast", "electric", "gas", "water", "internet", "phone"],
  tax_document: ["tax", "taxes", "1099", "w2", "w-2", "irs", "return", "returns"],
  bank_statement: ["bank", "statement", "statements", "checking", "savings", "account"],
  invoice: ["invoice", "invoices", "billing"],
  // Legal (synced with Python)
  legal: ["contract", "contracts", "agreement", "agreements", "deed", "deeds", "legal", "lease", "nda", "terms", "policy", "policies", "license", "licenses"],
  contract: ["contract", "contracts", "agreement", "agreements"],
  // Health (synced with Python)
  health: ["medical", "doctor", "prescription", "prescriptions", "health", "hospital", "insurance", "dental", "vision", "lab", "test result", "vaccination", "immunization"],
  medical_record: ["medical", "health", "doctor", "hospital", "lab", "dental", "prescription"],
  // Identity (synced with Python)
  identity: ["passport", "id", "identification", "license", "driver", "ssn", "social security", "birth certificate", "citizenship", "visa"],
  // Education (synced with Python)
  education: ["diploma", "degree", "transcript", "certificate", "certification", "school", "college", "university", "academic", "graduation"],
  // VA/Veterans
  va_claims: ["va", "veteran", "veterans", "vba", "vha", "disability", "claim", "claims", "dd214", "dd-214", "military"],
  // Insurance
  insurance: ["insurance", "policy", "policies", "coverage", "claim", "claims"],
};

/**
 * Canonical folder names for each category
 * Synchronized with PYTHON_CATEGORY_PATTERNS canonicalFolder values
 */
export const CANONICAL_FOLDERS: Record<string, string> = {
  employment: "Resumes",
  finances: "Taxes",  // Updated to match Python
  utility_bill: "Bills",
  tax_document: "Taxes",
  bank_statement: "Bank Statements",
  invoice: "Invoices",
  legal: "Contracts",  // Updated to match Python
  contract: "Contracts",
  health: "Medical",
  medical_record: "Medical Records",
  identity: "Identity",  // Updated to match Python
  education: "Education",
  va_claims: "VA Claims",
  insurance: "Insurance",
};

/**
 * Folder assessment result
 */
export interface FolderAssessment {
  folderPath: string;
  folderName: string;
  isCorrectLocation: boolean;
  isDuplicate: boolean;
  assessment: "correct" | "incorrect" | "duplicate" | "unknown";
  confidence: number; // 0.0 to 1.0
  reasoning: string[];
  suggestedAction: "restore" | "remove" | "keep" | "review";
  // Analysis details
  movedFilesCategories: string[];
  dominantCategory: string | null;
  categoryMatch: boolean;
  folderHierarchyMatch: boolean;
  canonicalMatch: boolean;
  similarCanonicalFolder: string | null;
  // Integration with existing systems (Phase 5 completion)
  canonicalRegistryMatch: boolean;
  executionLogMatch: boolean;
  executionLogMovements: number;
}

export interface FolderAssessmentResult {
  assessment: FolderAssessment;
  movedFiles: MovedFileInfo[];
  error?: string;
}

/**
 * Normalize a folder name for comparison
 * - Lowercase
 * - Remove underscores, hyphens, extra spaces
 * - Remove trailing numbers (e.g., _1, _2023)
 */
export function normalizeFolderName(name: string): string {
  if (!name) return "";

  let normalized = name.toLowerCase();

  // Remove trailing numbers (e.g., _1, _2023, -2)
  normalized = normalized.replace(/[_-]?\d+$/, "");

  // Replace underscores and hyphens with spaces
  normalized = normalized.replace(/[_-]/g, " ");

  // Remove extra spaces
  normalized = normalized.replace(/\s+/g, " ").trim();

  return normalized;
}

/**
 * Calculate similarity score between two strings (0.0 to 1.0)
 * Uses a simple character-based comparison
 */
export function getSimilarityScore(str1: string, str2: string): number {
  const s1 = normalizeFolderName(str1);
  const s2 = normalizeFolderName(str2);

  if (s1 === s2) return 1.0;
  if (!s1 || !s2) return 0.0;

  // Check if one contains the other
  if (s1.includes(s2) || s2.includes(s1)) {
    return 0.85;
  }

  // Character-level similarity (Dice coefficient)
  const bigrams1 = new Set<string>();
  const bigrams2 = new Set<string>();

  for (let i = 0; i < s1.length - 1; i++) {
    bigrams1.add(s1.slice(i, i + 2));
  }
  for (let i = 0; i < s2.length - 1; i++) {
    bigrams2.add(s2.slice(i, i + 2));
  }

  let intersection = 0;
  for (const bigram of bigrams1) {
    if (bigrams2.has(bigram)) {
      intersection++;
    }
  }

  return (2 * intersection) / (bigrams1.size + bigrams2.size);
}

/**
 * Check if a folder name matches a category
 */
export function doesFolderMatchCategory(
  folderName: string,
  category: string
): boolean {
  const normalizedFolder = normalizeFolderName(folderName);
  const patterns = CATEGORY_PATTERNS[category] || [];

  for (const pattern of patterns) {
    if (normalizedFolder.includes(pattern)) {
      return true;
    }
  }

  // Also check if folder name directly matches the category name
  const normalizedCategory = normalizeFolderName(category);
  return normalizedFolder.includes(normalizedCategory) ||
         normalizedCategory.includes(normalizedFolder);
}

/**
 * Detect category from folder name
 */
export function detectCategoryFromFolderName(folderName: string): string | null {
  const normalizedFolder = normalizeFolderName(folderName);

  // Check each category's patterns
  for (const [category, patterns] of Object.entries(CATEGORY_PATTERNS)) {
    for (const pattern of patterns) {
      if (normalizedFolder.includes(pattern)) {
        return category;
      }
    }
  }

  return null;
}

/**
 * Find the most similar canonical folder name
 */
export function findSimilarCanonicalFolder(
  folderName: string,
  threshold: number = 0.7
): { folder: string; category: string; score: number } | null {
  const normalizedFolder = normalizeFolderName(folderName);
  let bestMatch: { folder: string; category: string; score: number } | null = null;

  for (const [category, canonicalName] of Object.entries(CANONICAL_FOLDERS)) {
    const score = getSimilarityScore(normalizedFolder, canonicalName);
    if (score >= threshold && (!bestMatch || score > bestMatch.score)) {
      bestMatch = { folder: canonicalName, category, score };
    }
  }

  return bestMatch;
}

/**
 * Get the dominant category from a list of AI categories
 */
export function getDominantCategory(categories: string[]): string | null {
  if (!categories || categories.length === 0) return null;

  // Count occurrences
  const counts: Record<string, number> = {};
  for (const cat of categories) {
    if (cat) {
      counts[cat] = (counts[cat] || 0) + 1;
    }
  }

  // Find the most common
  let dominant: string | null = null;
  let maxCount = 0;
  for (const [cat, count] of Object.entries(counts)) {
    if (count > maxCount) {
      maxCount = count;
      dominant = cat;
    }
  }

  return dominant;
}

/**
 * Assess whether a folder was in the correct location
 *
 * This function integrates with existing systems:
 * 1. Uses execution logs to track file movements
 * 2. Queries document_locations for file history
 * 3. Uses canonical_registry to check folder names
 * 4. Uses category mapping to assess folder correctness
 *
 * @param folderPath - The path of the empty folder
 * @param organizerBasePath - Optional base path for .organizer directory (for canonical registry and execution logs)
 * @returns Assessment result with reasoning
 */
export async function assessFolderLocation(
  folderPath: string,
  organizerBasePath?: string
): Promise<FolderAssessmentResult> {
  try {
    const supabase = getSupabaseClient();

    // Get the folder name from the path
    const pathParts = folderPath.split("/").filter(Boolean);
    const folderName = pathParts[pathParts.length - 1] || "";

    // Get files that were moved from this folder (from document_locations table)
    const historyResult = await getFolderHistory(folderPath);
    if (historyResult.error) {
      return {
        assessment: createDefaultAssessment(folderPath, folderName),
        movedFiles: [],
        error: historyResult.error,
      };
    }

    const movedFiles = historyResult.files;

    // Integration: Check execution logs for file movements
    let executionLogMovements = 0;
    let executionLogMatch = false;
    if (organizerBasePath) {
      const execLogHistory = getFileMovementHistory(
        `${organizerBasePath}/.organizer`,
        folderPath
      );
      executionLogMovements = execLogHistory.totalMovements;
      if (executionLogMovements > 0) {
        executionLogMatch = true;
      }
    }

    // Integration: Load canonical registry
    let canonicalRegistry: CanonicalRegistry | null = null;
    let canonicalRegistryMatch = false;
    if (organizerBasePath) {
      const registryResult = loadCanonicalRegistry(organizerBasePath);
      canonicalRegistry = registryResult.registry;
    }

    if (movedFiles.length === 0 && executionLogMovements === 0) {
      // No files were moved from this folder - unknown assessment
      const assessment: FolderAssessment = {
        folderPath,
        folderName,
        isCorrectLocation: false,
        isDuplicate: false,
        assessment: "unknown",
        confidence: 0.0,
        reasoning: ["No file movement history found for this folder (checked document_locations and execution logs)"],
        suggestedAction: "review",
        movedFilesCategories: [],
        dominantCategory: null,
        categoryMatch: false,
        folderHierarchyMatch: false,
        canonicalMatch: false,
        similarCanonicalFolder: null,
        canonicalRegistryMatch: false,
        executionLogMatch: false,
        executionLogMovements: 0,
      };
      return { assessment, movedFiles };
    }

    // Get AI categories and folder_hierarchy for moved documents
    const documentIds = movedFiles.map((f) => f.documentId);
    const { data: documents, error: docError } = await supabase
      .from("documents")
      .select("id, ai_category, folder_hierarchy")
      .in("id", documentIds);

    if (docError) {
      return {
        assessment: createDefaultAssessment(folderPath, folderName),
        movedFiles,
        error: docError.message,
      };
    }

    // Extract categories and hierarchies
    const categories: string[] = [];
    const hierarchies: string[][] = [];

    for (const doc of documents || []) {
      if (doc.ai_category) {
        categories.push(doc.ai_category);
      }
      if (doc.folder_hierarchy && Array.isArray(doc.folder_hierarchy)) {
        hierarchies.push(doc.folder_hierarchy);
      }
    }

    // Perform assessment
    const reasoning: string[] = [];
    let confidence = 0.0;
    let isCorrectLocation = false;
    let isDuplicate = false;

    // Integration: Add execution log info to reasoning
    if (executionLogMatch) {
      reasoning.push(
        `Execution logs show ${executionLogMovements} file(s) moved from this folder`
      );
      confidence += 0.1; // Small boost for having execution log evidence
    }

    // 1. Check if folder name matches dominant AI category
    const dominantCategory = getDominantCategory(categories);
    const categoryMatch = dominantCategory
      ? doesFolderMatchCategory(folderName, dominantCategory)
      : false;

    if (categoryMatch && dominantCategory) {
      reasoning.push(
        `Folder name "${folderName}" matches AI category "${dominantCategory}"`
      );
      confidence += 0.4;
      isCorrectLocation = true;
    } else if (dominantCategory) {
      reasoning.push(
        `Folder name "${folderName}" does NOT match dominant AI category "${dominantCategory}"`
      );
    }

    // 2. Check if folder matches folder_hierarchy patterns
    let folderHierarchyMatch = false;
    if (hierarchies.length > 0) {
      // Check if folder name appears in any hierarchy
      for (const hierarchy of hierarchies) {
        if (hierarchy.some((h) =>
          normalizeFolderName(h) === normalizeFolderName(folderName) ||
          getSimilarityScore(h, folderName) > 0.8
        )) {
          folderHierarchyMatch = true;
          break;
        }
      }

      if (folderHierarchyMatch) {
        reasoning.push(
          `Folder name "${folderName}" matches folder_hierarchy patterns`
        );
        confidence += 0.3;
        isCorrectLocation = true;
      } else {
        reasoning.push(
          `Folder name "${folderName}" does NOT match folder_hierarchy patterns`
        );
      }
    }

    // 3. Integration: Check canonical registry from .organizer/canonical_folders.json
    if (canonicalRegistry) {
      const registryAssessment = assessFolderWithRegistry(
        folderName,
        canonicalRegistry,
        dominantCategory
      );

      if (registryAssessment.isInRegistry) {
        canonicalRegistryMatch = true;
        reasoning.push(...registryAssessment.reasoning);
        confidence += registryAssessment.confidence;
        if (registryAssessment.matchesCategory) {
          isCorrectLocation = true;
        }
      } else {
        reasoning.push(`Folder "${folderName}" not found in canonical registry (.organizer/canonical_folders.json)`);
      }
    }

    // 4. Check canonical registry / similar canonical folders (fallback using TypeScript patterns)
    const similarCanonical = findSimilarCanonicalFolder(folderName);
    let canonicalMatch = false;

    if (similarCanonical) {
      if (similarCanonical.score > 0.95) {
        // Exact or near-exact match to canonical
        canonicalMatch = true;
        reasoning.push(
          `Folder name "${folderName}" matches canonical pattern "${similarCanonical.folder}"`
        );
        confidence += 0.3;
        isCorrectLocation = true;
      } else if (similarCanonical.score > 0.7) {
        // Similar to canonical - potential duplicate
        isDuplicate = true;
        reasoning.push(
          `Folder name "${folderName}" is similar to canonical "${similarCanonical.folder}" (score: ${similarCanonical.score.toFixed(2)}) - potential duplicate`
        );
        confidence += 0.2;
      }
    }

    // 5. Check if folder name contains category-specific patterns (using Python-aligned patterns)
    const detectedCategory = detectCategoryFromFolderName(folderName);
    if (detectedCategory && !categoryMatch) {
      if (detectedCategory === dominantCategory) {
        reasoning.push(
          `Folder name contains patterns for category "${detectedCategory}" (Python-aligned)`
        );
        confidence += 0.1;
        isCorrectLocation = true;
      } else if (dominantCategory) {
        reasoning.push(
          `Folder name suggests category "${detectedCategory}" but files are "${dominantCategory}" - MISMATCH`
        );
        isDuplicate = true;
      }
    }

    // Determine final assessment
    let assessment: "correct" | "incorrect" | "duplicate" | "unknown";
    let suggestedAction: "restore" | "remove" | "keep" | "review";

    if (confidence >= 0.6 && isCorrectLocation && !isDuplicate) {
      assessment = "correct";
      suggestedAction = "restore";
      reasoning.push("ASSESSMENT: Folder was in CORRECT location");
    } else if (isDuplicate) {
      assessment = "duplicate";
      suggestedAction = "remove";
      reasoning.push("ASSESSMENT: Folder appears to be a DUPLICATE or misnamed");
    } else if (confidence >= 0.3) {
      assessment = "incorrect";
      suggestedAction = "remove";
      reasoning.push("ASSESSMENT: Folder was in INCORRECT location");
    } else {
      assessment = "unknown";
      suggestedAction = "review";
      reasoning.push("ASSESSMENT: Unable to determine - manual review recommended");
    }

    // Cap confidence at 1.0
    confidence = Math.min(confidence, 1.0);

    const folderAssessment: FolderAssessment = {
      folderPath,
      folderName,
      isCorrectLocation,
      isDuplicate,
      assessment,
      confidence,
      reasoning,
      suggestedAction,
      movedFilesCategories: categories,
      dominantCategory,
      categoryMatch,
      folderHierarchyMatch,
      canonicalMatch,
      similarCanonicalFolder: similarCanonical?.folder || null,
      // Integration with existing systems
      canonicalRegistryMatch,
      executionLogMatch,
      executionLogMovements,
    };

    return { assessment: folderAssessment, movedFiles };
  } catch (err) {
    const pathParts = folderPath.split("/").filter(Boolean);
    const folderName = pathParts[pathParts.length - 1] || "";
    return {
      assessment: createDefaultAssessment(folderPath, folderName),
      movedFiles: [],
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Create a default assessment for error cases
 */
function createDefaultAssessment(
  folderPath: string,
  folderName: string
): FolderAssessment {
  return {
    folderPath,
    folderName,
    isCorrectLocation: false,
    isDuplicate: false,
    assessment: "unknown",
    confidence: 0.0,
    reasoning: ["Unable to assess folder"],
    suggestedAction: "review",
    movedFilesCategories: [],
    dominantCategory: null,
    categoryMatch: false,
    folderHierarchyMatch: false,
    canonicalMatch: false,
    similarCanonicalFolder: null,
    canonicalRegistryMatch: false,
    executionLogMatch: false,
    executionLogMovements: 0,
  };
}

// ============================================================================
// Orphaned Files Detection & Restoration (Phase 6)
// ============================================================================

/**
 * Information about an orphaned file (exists on disk but not in database)
 */
export interface OrphanedFileInfo {
  filePath: string;
  fileName: string;
  fileSize: number;
  lastModified: string;
  fileType: string;
  suggestedLocation: string | null;
  suggestedReason: string | null;
  confidence: number;
}

/**
 * Information about a missing file (in database but path doesn't exist)
 */
export interface MissingFileInfo {
  documentId: string;
  fileName: string;
  currentPath: string;
  originalPath: string | null;
  aiCategory: string | null;
  lastKnownLocation: string | null;
  isAccessible: boolean;
}

/**
 * Result of scanning for orphaned files
 */
export interface OrphanedFilesResult {
  orphanedFiles: OrphanedFileInfo[];
  totalOrphanedFiles: number;
  scannedDirectory: string;
  error?: string;
}

/**
 * Result of scanning for missing files
 */
export interface MissingFilesResult {
  missingFiles: MissingFileInfo[];
  totalMissingFiles: number;
  totalDocuments: number;
  error?: string;
}

/**
 * Location suggestion result
 */
export interface LocationSuggestion {
  suggestedPath: string;
  reason: string;
  confidence: number;
  matchType: "file_type" | "filename_pattern" | "content_analysis" | "similar_files" | "database_history";
}

/**
 * Result of getting original location from document_locations table
 */
export interface OriginalLocationResult {
  documentId: string;
  originalPath: string | null;
  locationHistory: {
    path: string;
    locationType: string;
    createdAt: string;
    isAccessible: boolean;
  }[];
  error?: string;
}

/**
 * File type to suggested folder mapping
 * Maps file extensions to typical folder locations
 */
export const FILE_TYPE_LOCATION_PATTERNS: Record<string, { folder: string; reason: string }> = {
  // Apple preference files
  ".plist": { folder: "Library/Preferences", reason: "Apple preference list file" },
  // Documents
  ".pdf": { folder: "Documents", reason: "PDF document" },
  ".doc": { folder: "Documents", reason: "Word document" },
  ".docx": { folder: "Documents", reason: "Word document" },
  ".txt": { folder: "Documents", reason: "Text document" },
  ".rtf": { folder: "Documents", reason: "Rich text document" },
  // Spreadsheets
  ".xls": { folder: "Documents/Spreadsheets", reason: "Excel spreadsheet" },
  ".xlsx": { folder: "Documents/Spreadsheets", reason: "Excel spreadsheet" },
  ".csv": { folder: "Documents/Data", reason: "CSV data file" },
  // Images
  ".jpg": { folder: "Pictures", reason: "JPEG image" },
  ".jpeg": { folder: "Pictures", reason: "JPEG image" },
  ".png": { folder: "Pictures", reason: "PNG image" },
  ".gif": { folder: "Pictures", reason: "GIF image" },
  ".heic": { folder: "Pictures", reason: "HEIC image" },
  // Videos
  ".mp4": { folder: "Movies", reason: "MP4 video" },
  ".mov": { folder: "Movies", reason: "QuickTime video" },
  ".avi": { folder: "Movies", reason: "AVI video" },
  // Audio
  ".mp3": { folder: "Music", reason: "MP3 audio" },
  ".m4a": { folder: "Music", reason: "M4A audio" },
  ".wav": { folder: "Music", reason: "WAV audio" },
  // Archives
  ".zip": { folder: "Downloads", reason: "ZIP archive" },
  ".tar": { folder: "Downloads", reason: "TAR archive" },
  ".gz": { folder: "Downloads", reason: "Gzip archive" },
};

/**
 * Get missing files from the database (files in DB but path doesn't exist on disk)
 * This function queries the database and marks which files have inaccessible paths
 *
 * Optimized: Uses a single query with embedded relation to avoid N+1 queries
 */
export async function getMissingFiles(): Promise<MissingFilesResult> {
  try {
    const supabase = getSupabaseClient();

    // Optimized: Single query fetching documents with their locations via foreign key
    // This replaces 2 separate queries with a single joined query
    const { data: documentsWithLocations, error: docError, count } = await supabase
      .from("documents")
      .select(`
        id,
        file_name,
        current_path,
        ai_category,
        document_locations (
          location_path,
          location_type,
          is_accessible,
          discovered_at
        )
      `, { count: "exact" });

    if (docError) {
      return {
        missingFiles: [],
        totalMissingFiles: 0,
        totalDocuments: 0,
        error: docError.message,
      };
    }

    if (!documentsWithLocations || documentsWithLocations.length === 0) {
      return {
        missingFiles: [],
        totalMissingFiles: 0,
        totalDocuments: count ?? 0,
      };
    }

    // Build missing files list from the joined data
    // Note: We return all documents - the actual filesystem check will be done in the API route
    const missingFiles: MissingFileInfo[] = documentsWithLocations.map((doc) => {
      const docLocations = (doc.document_locations || []) as Array<{
        location_path: string;
        location_type: string;
        is_accessible: boolean;
        discovered_at: string;
      }>;

      // Find original path (primary or previous type)
      const originalLoc = docLocations.find(
        (loc) => loc.location_type === "primary" || loc.location_type === "previous"
      );

      // Find last known accessible location
      const lastKnownLoc = docLocations
        .filter((loc) => loc.is_accessible)
        .sort((a, b) => new Date(b.discovered_at).getTime() - new Date(a.discovered_at).getTime())[0];

      return {
        documentId: doc.id,
        fileName: doc.file_name,
        currentPath: doc.current_path,
        originalPath: originalLoc?.location_path || null,
        aiCategory: doc.ai_category,
        lastKnownLocation: lastKnownLoc?.location_path || null,
        isAccessible: true, // Will be updated by filesystem check in API route
      };
    });

    return {
      missingFiles,
      totalMissingFiles: missingFiles.length,
      totalDocuments: count ?? documentsWithLocations.length,
    };
  } catch (err) {
    return {
      missingFiles: [],
      totalMissingFiles: 0,
      totalDocuments: 0,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Get original path for a document from document_locations table
 */
export async function getOriginalLocation(
  documentId: string
): Promise<OriginalLocationResult> {
  try {
    const supabase = getSupabaseClient();

    // Get all locations for this document
    const { data: locations, error } = await supabase
      .from("document_locations")
      .select("location_path, location_type, is_accessible, discovered_at")
      .eq("document_id", documentId)
      .order("discovered_at", { ascending: false });

    if (error) {
      return {
        documentId,
        originalPath: null,
        locationHistory: [],
        error: error.message,
      };
    }

    // Build location history
    const locationHistory = (locations || []).map((loc) => ({
      path: loc.location_path,
      locationType: loc.location_type,
      createdAt: loc.discovered_at,
      isAccessible: loc.is_accessible,
    }));

    // Find original path (primary type takes precedence, then oldest previous)
    let originalPath: string | null = null;
    const primaryLoc = locations?.find((loc) => loc.location_type === "primary");
    if (primaryLoc) {
      originalPath = primaryLoc.location_path;
    } else {
      // Get oldest previous location
      const previousLocs = (locations || []).filter(
        (loc) => loc.location_type === "previous"
      );
      if (previousLocs.length > 0) {
        previousLocs.sort(
          (a, b) => new Date(a.discovered_at).getTime() - new Date(b.discovered_at).getTime()
        );
        originalPath = previousLocs[0].location_path;
      }
    }

    return {
      documentId,
      originalPath,
      locationHistory,
    };
  } catch (err) {
    return {
      documentId,
      originalPath: null,
      locationHistory: [],
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Suggest a location for an orphaned file based on file type and patterns
 */
export function suggestLocationForFile(
  filePath: string,
  basePath: string = ""
): LocationSuggestion {
  const fileName = extractFileName(filePath);
  const extension = fileName.includes(".")
    ? "." + fileName.split(".").pop()!.toLowerCase()
    : "";

  // Check filename patterns FIRST (higher confidence than file type alone)
  const lowerFileName = fileName.toLowerCase();

  // Resume patterns
  if (
    lowerFileName.includes("resume") ||
    lowerFileName.includes("cv") ||
    lowerFileName.includes("curriculum")
  ) {
    return {
      suggestedPath: basePath ? `${basePath}/Documents/Resumes` : "Documents/Resumes",
      reason: "Filename suggests this is a resume/CV document",
      confidence: 0.8,
      matchType: "filename_pattern",
    };
  }

  // Tax patterns
  if (
    lowerFileName.includes("tax") ||
    lowerFileName.includes("1099") ||
    lowerFileName.includes("w2") ||
    lowerFileName.includes("w-2")
  ) {
    return {
      suggestedPath: basePath ? `${basePath}/Documents/Taxes` : "Documents/Taxes",
      reason: "Filename suggests this is a tax document",
      confidence: 0.8,
      matchType: "filename_pattern",
    };
  }

  // Invoice/bill patterns
  if (
    lowerFileName.includes("invoice") ||
    lowerFileName.includes("bill") ||
    lowerFileName.includes("receipt")
  ) {
    return {
      suggestedPath: basePath ? `${basePath}/Documents/Bills` : "Documents/Bills",
      reason: "Filename suggests this is an invoice or bill",
      confidence: 0.7,
      matchType: "filename_pattern",
    };
  }

  // Contract patterns
  if (
    lowerFileName.includes("contract") ||
    lowerFileName.includes("agreement") ||
    lowerFileName.includes("lease")
  ) {
    return {
      suggestedPath: basePath ? `${basePath}/Documents/Contracts` : "Documents/Contracts",
      reason: "Filename suggests this is a contract or agreement",
      confidence: 0.7,
      matchType: "filename_pattern",
    };
  }

  // Medical patterns
  if (
    lowerFileName.includes("medical") ||
    lowerFileName.includes("health") ||
    lowerFileName.includes("doctor") ||
    lowerFileName.includes("prescription")
  ) {
    return {
      suggestedPath: basePath ? `${basePath}/Documents/Medical` : "Documents/Medical",
      reason: "Filename suggests this is a medical document",
      confidence: 0.7,
      matchType: "filename_pattern",
    };
  }

  // Check file type patterns (after filename patterns for lower priority)
  if (extension && FILE_TYPE_LOCATION_PATTERNS[extension]) {
    const pattern = FILE_TYPE_LOCATION_PATTERNS[extension];
    const suggestedPath = basePath
      ? `${basePath}/${pattern.folder}`
      : pattern.folder;

    return {
      suggestedPath,
      reason: `${pattern.reason} - typical location for ${extension} files`,
      confidence: 0.7,
      matchType: "file_type",
    };
  }

  // Default: Documents folder
  return {
    suggestedPath: basePath ? `${basePath}/Documents` : "Documents",
    reason: "Default location for unrecognized files",
    confidence: 0.3,
    matchType: "file_type",
  };
}

/**
 * Check if a document exists in the database by file path or hash
 */
export async function checkFileInDatabase(
  filePath: string
): Promise<{ exists: boolean; documentId: string | null; error?: string }> {
  try {
    const supabase = getSupabaseClient();

    // Check by current_path
    const { data, error } = await supabase
      .from("documents")
      .select("id")
      .eq("current_path", filePath)
      .limit(1);

    if (error) {
      return { exists: false, documentId: null, error: error.message };
    }

    if (data && data.length > 0) {
      return { exists: true, documentId: data[0].id };
    }

    // Also check document_locations for the path
    const { data: locData, error: locError } = await supabase
      .from("document_locations")
      .select("document_id")
      .eq("path", filePath)
      .limit(1);

    if (locError) {
      return { exists: false, documentId: null, error: locError.message };
    }

    if (locData && locData.length > 0) {
      return { exists: true, documentId: locData[0].document_id };
    }

    return { exists: false, documentId: null };
  } catch (err) {
    return {
      exists: false,
      documentId: null,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Update document path in database (for restoring or updating location)
 */
export async function updateDocumentPath(
  documentId: string,
  newPath: string,
  addToLocationHistory: boolean = true
): Promise<{ success: boolean; error?: string }> {
  try {
    const supabase = getSupabaseClient();

    // Get current document to capture old path
    const { data: currentDoc, error: getError } = await supabase
      .from("documents")
      .select("current_path")
      .eq("id", documentId)
      .single();

    if (getError) {
      return { success: false, error: getError.message };
    }

    const oldPath = currentDoc?.current_path;

    // Update documents table
    const { error: updateError } = await supabase
      .from("documents")
      .update({ current_path: newPath, updated_at: new Date().toISOString() })
      .eq("id", documentId);

    if (updateError) {
      return { success: false, error: updateError.message };
    }

      // Add to location history if requested
      if (addToLocationHistory && oldPath && oldPath !== newPath) {
        // Mark old path as previous
        const { error: locError } = await supabase.from("document_locations").insert({
          document_id: documentId,
          location_path: oldPath,
          location_type: "previous",
          is_accessible: false,
        });

        if (locError) {
          // Log but don't fail - the main update succeeded
          console.error("Failed to add location history:", locError.message);
        }

        // Add new path as current
        const { error: newLocError } = await supabase.from("document_locations").insert({
          document_id: documentId,
          location_path: newPath,
          location_type: "current",
          is_accessible: true,
        });

      if (newLocError) {
        console.error("Failed to add new location:", newLocError.message);
      }
    }

    return { success: true };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Remove a document from the database
 */
export async function removeDocumentFromDatabase(
  documentId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const supabase = getSupabaseClient();

    // First, delete from document_locations
    const { error: locError } = await supabase
      .from("document_locations")
      .delete()
      .eq("document_id", documentId);

    if (locError) {
      return { success: false, error: `Failed to delete locations: ${locError.message}` };
    }

    // Then delete from documents
    const { error: docError } = await supabase
      .from("documents")
      .delete()
      .eq("id", documentId);

    if (docError) {
      return { success: false, error: `Failed to delete document: ${docError.message}` };
    }

    return { success: true };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Mark a document location as inaccessible
 */
export async function markDocumentInaccessible(
  documentId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const supabase = getSupabaseClient();

    // Update is_accessible flag for all locations of this document
    const { error } = await supabase
      .from("document_locations")
      .update({ is_accessible: false })
      .eq("document_id", documentId);

    if (error) {
      return { success: false, error: error.message };
    }

    return { success: true };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

// ============================================================================
// Enhanced Location Suggestion Logic (PRD Phase 6 - location suggestion)
// ============================================================================

/**
 * Filename patterns mapping to category and suggested folder
 * Synchronized with Python's organizer/category_mapper.py CONSOLIDATION_CATEGORIES
 */
export const FILENAME_CATEGORY_PATTERNS: Record<
  string,
  { patterns: string[]; folder: string; parentFolder: string }
> = {
  employment: {
    patterns: [
      "resume",
      "resumes",
      "cv",
      "cover letter",
      "cover_letter",
      "coverletter",
      "job",
      "application",
      "job application",
      "employment",
      "career",
      "interview",
    ],
    folder: "Resumes",
    parentFolder: "Employment",
  },
  finances: {
    patterns: [
      "tax",
      "taxes",
      "tax return",
      "tax_return",
      "taxreturn",
      "1099",
      "w2",
      "w-2",
      "invoice",
      "invoices",
      "receipt",
      "receipts",
      "budget",
      "financial",
      "finance",
      "bank",
      "banking",
      "statement",
      "expense",
      "expenses",
    ],
    folder: "Taxes",
    parentFolder: "Finances Bin",
  },
  legal: {
    patterns: [
      "contract",
      "contracts",
      "agreement",
      "agreements",
      "deed",
      "deeds",
      "legal",
      "lease",
      "nda",
      "terms",
      "policy",
      "policies",
      "license",
      "licenses",
    ],
    folder: "Contracts",
    parentFolder: "Contracts",
  },
  health: {
    patterns: [
      "medical",
      "doctor",
      "prescription",
      "prescriptions",
      "health",
      "hospital",
      "insurance",
      "dental",
      "vision",
      "lab",
      "test result",
      "vaccination",
      "immunization",
    ],
    folder: "Medical",
    parentFolder: "Health",
  },
  identity: {
    patterns: [
      "passport",
      "identification",
      "driver",
      "ssn",
      "social security",
      "birth certificate",
      "citizenship",
      "visa",
    ],
    folder: "Identity",
    parentFolder: "Personal",
  },
  education: {
    patterns: [
      "diploma",
      "degree",
      "transcript",
      "certificate",
      "certification",
      "school",
      "college",
      "university",
      "academic",
      "graduation",
    ],
    folder: "Education",
    parentFolder: "Education",
  },
};

/**
 * Result of enhanced location suggestion
 */
export interface EnhancedLocationSuggestion extends LocationSuggestion {
  /** If true, the suggestion came from database history */
  fromDatabase: boolean;
  /** If matched in database, the document ID */
  databaseDocumentId: string | null;
  /** Category detected from filename or similar files */
  detectedCategory: string | null;
  /** Similar files found that informed the suggestion */
  similarFilesCount: number;
}

/**
 * Detect category from filename using patterns synchronized with Python
 */
export function detectCategoryFromFilename(fileName: string): {
  category: string;
  folder: string;
  parentFolder: string;
} | null {
  const lowerFileName = fileName.toLowerCase();

  for (const [category, info] of Object.entries(FILENAME_CATEGORY_PATTERNS)) {
    for (const pattern of info.patterns) {
      if (lowerFileName.includes(pattern)) {
        return {
          category,
          folder: info.folder,
          parentFolder: info.parentFolder,
        };
      }
    }
  }

  return null;
}

/**
 * Find similar files in the database based on filename pattern
 * Returns folder_hierarchy patterns from similar documents
 */
export async function findSimilarFilesByPattern(
  fileName: string,
  limit: number = 10
): Promise<{
  similarFiles: Array<{
    id: string;
    file_name: string;
    current_path: string;
    ai_category: string | null;
    folder_hierarchy: string[] | null;
  }>;
  dominantFolderHierarchy: string[] | null;
  error?: string;
}> {
  try {
    const supabase = getSupabaseClient();

    // Extract base name without extension for pattern matching
    const baseName = fileName.replace(/\.[^.]+$/, "").toLowerCase();

    // Get the first few words for fuzzy matching
    const searchTerms = baseName
      .split(/[_\-\s]+/)
      .filter((t) => t.length > 2)
      .slice(0, 3);

    if (searchTerms.length === 0) {
      return { similarFiles: [], dominantFolderHierarchy: null };
    }

    // Build search query - search for files with similar names
    let query = supabase
      .from("documents")
      .select("id, file_name, current_path, ai_category, folder_hierarchy");

    // Search using the first meaningful term
    const searchTerm = searchTerms[0];
    query = query.ilike("file_name", `%${searchTerm}%`);

    const { data, error } = await query.limit(limit);

    if (error) {
      return { similarFiles: [], dominantFolderHierarchy: null, error: error.message };
    }

    const similarFiles = (data || []) as Array<{
      id: string;
      file_name: string;
      current_path: string;
      ai_category: string | null;
      folder_hierarchy: string[] | null;
    }>;

    // Find the most common folder_hierarchy pattern
    const hierarchyCounts = new Map<string, { count: number; hierarchy: string[] }>();
    for (const file of similarFiles) {
      if (file.folder_hierarchy && file.folder_hierarchy.length > 0) {
        const key = file.folder_hierarchy.join("/");
        const existing = hierarchyCounts.get(key);
        if (existing) {
          existing.count++;
        } else {
          hierarchyCounts.set(key, { count: 1, hierarchy: file.folder_hierarchy });
        }
      }
    }

    // Get the most common hierarchy
    let dominantFolderHierarchy: string[] | null = null;
    let maxCount = 0;
    for (const { count, hierarchy } of hierarchyCounts.values()) {
      if (count > maxCount) {
        maxCount = count;
        dominantFolderHierarchy = hierarchy;
      }
    }

    return { similarFiles, dominantFolderHierarchy };
  } catch (err) {
    return {
      similarFiles: [],
      dominantFolderHierarchy: null,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Build suggested path from folder hierarchy
 */
function buildPathFromHierarchy(
  folderHierarchy: string[],
  basePath: string
): string {
  if (folderHierarchy.length === 0) {
    return basePath ? `${basePath}/Documents` : "Documents";
  }

  const hierarchyPath = folderHierarchy.join("/");
  return basePath ? `${basePath}/${hierarchyPath}` : hierarchyPath;
}

/**
 * Enhanced location suggestion that checks database history first
 *
 * This function implements the PRD requirements:
 * 1. Check if file hash/path exists in database → use document_locations for original path
 * 2. Check folder_hierarchy patterns for similar files
 * 3. Use existing category mapping from organizer/category_mapper.py (via FILENAME_CATEGORY_PATTERNS)
 * 4. Fall back to file type and filename pattern suggestions
 */
export async function suggestLocationForFileEnhanced(
  filePath: string,
  basePath: string = ""
): Promise<EnhancedLocationSuggestion> {
  const fileName = extractFileName(filePath);

  // Step 1: Check if file already exists in database
  const dbCheck = await checkFileInDatabase(filePath);

  if (dbCheck.exists && dbCheck.documentId) {
    // File is in database - get its original location
    const originalLocation = await getOriginalLocation(dbCheck.documentId);

    if (originalLocation.originalPath) {
      // Use the original location from database
      const originalFolder = extractFolderPath(originalLocation.originalPath);
      return {
        suggestedPath: originalFolder || (basePath ? `${basePath}/Documents` : "Documents"),
        reason: "File found in database - restoring to original location",
        confidence: 0.95,
        matchType: "database_history",
        fromDatabase: true,
        databaseDocumentId: dbCheck.documentId,
        detectedCategory: null,
        similarFilesCount: 0,
      };
    }
  }

  // Step 2: Check folder_hierarchy patterns from similar files in database
  const similarResult = await findSimilarFilesByPattern(fileName);

  if (similarResult.dominantFolderHierarchy) {
    // Use the folder hierarchy from similar files
    const suggestedPath = buildPathFromHierarchy(
      similarResult.dominantFolderHierarchy,
      basePath
    );

    // Try to detect category from similar files
    let detectedCategory: string | null = null;
    for (const file of similarResult.similarFiles) {
      if (file.ai_category) {
        detectedCategory = file.ai_category;
        break;
      }
    }

    return {
      suggestedPath,
      reason: `Based on ${similarResult.similarFiles.length} similar files in database with same folder pattern`,
      confidence: 0.85,
      matchType: "similar_files",
      fromDatabase: true,
      databaseDocumentId: null,
      detectedCategory,
      similarFilesCount: similarResult.similarFiles.length,
    };
  }

  // Step 3: Use filename pattern detection (synchronized with Python category_mapper.py)
  const categoryMatch = detectCategoryFromFilename(fileName);

  if (categoryMatch) {
    const suggestedPath = basePath
      ? `${basePath}/${categoryMatch.parentFolder}/${categoryMatch.folder}`
      : `${categoryMatch.parentFolder}/${categoryMatch.folder}`;

    return {
      suggestedPath,
      reason: `Filename matches "${categoryMatch.category}" category pattern (synced with Python organizer)`,
      confidence: 0.8,
      matchType: "filename_pattern",
      fromDatabase: false,
      databaseDocumentId: null,
      detectedCategory: categoryMatch.category,
      similarFilesCount: 0,
    };
  }

  // Step 4: Fall back to basic file type suggestion
  const basicSuggestion = suggestLocationForFile(filePath, basePath);

  return {
    ...basicSuggestion,
    fromDatabase: false,
    databaseDocumentId: null,
    detectedCategory: null,
    similarFilesCount: 0,
  };
}

/**
 * Batch suggest locations for multiple orphaned files
 * More efficient than calling suggestLocationForFileEnhanced for each file
 */
export async function suggestLocationsForFiles(
  filePaths: string[],
  basePath: string = ""
): Promise<Map<string, EnhancedLocationSuggestion>> {
  const results = new Map<string, EnhancedLocationSuggestion>();

  // Process files in parallel with a concurrency limit
  const concurrencyLimit = 5;
  const chunks: string[][] = [];

  for (let i = 0; i < filePaths.length; i += concurrencyLimit) {
    chunks.push(filePaths.slice(i, i + concurrencyLimit));
  }

  for (const chunk of chunks) {
    const promises = chunk.map(async (filePath) => {
      const suggestion = await suggestLocationForFileEnhanced(filePath, basePath);
      return { filePath, suggestion };
    });

    const chunkResults = await Promise.all(promises);
    for (const { filePath, suggestion } of chunkResults) {
      results.set(filePath, suggestion);
    }
  }

  return results;
}

// Export helpers for testing
export {
  extractYearFromDate,
  filterByYears,
  filterByOrganizations,
  filterByContextBin,
  filterByDateRange,
  extractFolderPath,
  extractFileName,
};
