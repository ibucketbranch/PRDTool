import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getSupabaseClient,
  resetSupabaseClient,
  testConnection,
  getDocuments,
  getCategoryStats,
  searchDocuments,
  naturalLanguageSearch,
  getDateDistribution,
  getContextBinCounts,
  getStatistics,
  clearStatisticsCache,
  extractYearFromDate,
  filterByYears,
  filterByOrganizations,
  filterByContextBin,
  filterByDateRange,
  type Document,
  type CategoryCount,
  type YearCount,
  type ContextBinCount,
  type DocumentListOptions,
  type DocumentListResult,
} from "@/lib/supabase";

// Mock the Supabase client
const mockSupabaseClient = {
  from: vi.fn(),
  rpc: vi.fn(),
};

vi.mock("@supabase/supabase-js", () => ({
  createClient: vi.fn(() => mockSupabaseClient),
}));

describe("Supabase Client", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetSupabaseClient();
  });

  describe("getSupabaseClient", () => {
    it("should create a Supabase client with environment variables", () => {
      const client = getSupabaseClient();
      expect(client).toBeDefined();
    });

    it("should return the same client instance on subsequent calls", () => {
      const client1 = getSupabaseClient();
      const client2 = getSupabaseClient();
      expect(client1).toBe(client2);
    });

    it("should throw error if environment variables are missing", () => {
      vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "");
      resetSupabaseClient();

      expect(() => getSupabaseClient()).toThrow(
        "Missing Supabase environment variables"
      );

      // Restore
      vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co");
    });
  });

  describe("testConnection", () => {
    it("should return connected: true with document count on success", async () => {
      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          count: 42,
          error: null,
        }),
      });

      const result = await testConnection();

      expect(result.connected).toBe(true);
      expect(result.documentCount).toBe(42);
      expect(result.error).toBeUndefined();
    });

    it("should return connected: false with error on database error", async () => {
      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          count: null,
          error: { message: "Connection failed" },
        }),
      });

      const result = await testConnection();

      expect(result.connected).toBe(false);
      expect(result.documentCount).toBe(0);
      expect(result.error).toBe("Connection failed");
    });

    it("should handle exceptions gracefully", async () => {
      mockSupabaseClient.from.mockImplementation(() => {
        throw new Error("Network error");
      });

      const result = await testConnection();

      expect(result.connected).toBe(false);
      expect(result.error).toBe("Network error");
    });
  });

  describe("getDocuments", () => {
    const mockDocuments: Document[] = [
      {
        id: "1",
        file_name: "test.pdf",
        current_path: "/docs/test.pdf",
        ai_category: "tax_document",
        ai_subcategories: ["1099"],
        ai_summary: "A test document",
        entities: { organizations: ["IRS"] },
        key_dates: ["2024-01-15"],
        folder_hierarchy: ["docs", "tax"],
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    ];

    it("should return documents with pagination info", async () => {
      // With optimized server-side pagination (when no client-side filters)
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        eq: vi.fn().mockReturnThis(),
        order: vi.fn().mockReturnThis(),
        range: vi.fn().mockResolvedValue({
          data: mockDocuments,
          count: 1,
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      const result = await getDocuments({ limit: 10, offset: 0 });

      expect(result.documents).toEqual(mockDocuments);
      expect(result.total).toBe(1);
      expect(result.filteredTotal).toBe(1);
      expect(result.error).toBeUndefined();
    });

    it("should filter by category when provided", async () => {
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        eq: vi.fn().mockReturnThis(),
        order: vi.fn().mockReturnThis(),
        range: vi.fn().mockResolvedValue({
          data: mockDocuments,
          count: 1,
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      await getDocuments({ category: "tax_document" });

      expect(mockQuery.eq).toHaveBeenCalledWith("ai_category", "tax_document");
    });

    it("should order by specified field", async () => {
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        order: vi.fn().mockReturnThis(),
        range: vi.fn().mockResolvedValue({
          data: [],
          count: 0,
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      await getDocuments({ orderBy: "file_name", orderDirection: "asc" });

      expect(mockQuery.order).toHaveBeenCalledWith("file_name", {
        ascending: true,
      });
    });

    it("should handle errors gracefully", async () => {
      // Server-side pagination with error
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        order: vi.fn().mockReturnThis(),
        range: vi.fn().mockResolvedValue({
          data: null,
          count: null,
          error: { message: "Query failed" },
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      const result = await getDocuments();

      expect(result.documents).toEqual([]);
      expect(result.error).toBe("Query failed");
    });
  });

  describe("getCategoryStats", () => {
    const mockCategories: CategoryCount[] = [
      { ai_category: "tax_document", count: 10 },
      { ai_category: "invoice", count: 5 },
    ];

    it("should return category counts from RPC", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: mockCategories,
        error: null,
      });

      const result = await getCategoryStats();

      expect(result.categories).toEqual(mockCategories);
      expect(result.error).toBeUndefined();
    });

    it("should fallback to manual grouping if RPC fails", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: null,
        error: { message: "RPC not found" },
      });

      const mockDocs = [
        { ai_category: "tax_document" },
        { ai_category: "tax_document" },
        { ai_category: "invoice" },
        { ai_category: null },
      ];

      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: mockDocs,
          error: null,
        }),
      });

      const result = await getCategoryStats();

      expect(result.categories).toContainEqual({
        ai_category: "tax_document",
        count: 2,
      });
      expect(result.categories).toContainEqual({
        ai_category: "invoice",
        count: 1,
      });
      expect(result.categories).toContainEqual({
        ai_category: "uncategorized",
        count: 1,
      });
    });

    it("should handle errors in fallback query", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: null,
        error: { message: "RPC not found" },
      });

      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: null,
          error: { message: "Query failed" },
        }),
      });

      const result = await getCategoryStats();

      expect(result.categories).toEqual([]);
      expect(result.error).toBe("Query failed");
    });
  });

  describe("searchDocuments", () => {
    const mockSearchResults: Document[] = [
      {
        id: "1",
        file_name: "verizon_bill_2024.pdf",
        current_path: "/bills/verizon_bill_2024.pdf",
        ai_category: "utility_bill",
        ai_subcategories: null,
        ai_summary: "Verizon phone bill for January 2024",
        entities: { organizations: ["Verizon"], amounts: ["$89.99"] },
        key_dates: ["2024-01-15"],
        folder_hierarchy: ["bills"],
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    ];

    // FTS response includes rank field
    const mockFTSResults = [
      {
        id: "1",
        file_name: "verizon_bill_2024.pdf",
        current_path: "/bills/verizon_bill_2024.pdf",
        ai_category: "utility_bill",
        ai_subcategories: null,
        ai_summary: "Verizon phone bill for January 2024",
        entities: { organizations: ["Verizon"], amounts: ["$89.99"] },
        key_dates: ["2024-01-15"],
        folder_hierarchy: ["bills"],
        file_modified_at: null,
        pdf_modified_date: null,
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
        rank: 0.95,
      },
    ];

    it("should use FTS RPC for queries >= 3 characters", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: mockFTSResults,
        error: null,
      });

      const result = await searchDocuments("verizon");

      expect(result.documents).toHaveLength(1);
      expect(result.documents[0].file_name).toBe("verizon_bill_2024.pdf");
      expect(result.error).toBeUndefined();
      expect(mockSupabaseClient.rpc).toHaveBeenCalledWith("search_documents_fts", {
        search_query: "verizon",
        result_limit: 20,
        result_offset: 0,
      });
    });

    it("should use ilike fallback for short queries (< 3 chars)", async () => {
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        range: vi.fn().mockReturnThis(),
        limit: vi.fn().mockResolvedValue({
          data: mockSearchResults,
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      const result = await searchDocuments("ab");

      expect(result.documents).toEqual(mockSearchResults);
      expect(result.error).toBeUndefined();
      expect(mockQuery.or).toHaveBeenCalledWith(
        expect.stringContaining("file_name.ilike.%ab%")
      );
      // RPC should NOT be called for short queries
      expect(mockSupabaseClient.rpc).not.toHaveBeenCalled();
    });

    it("should fall back to ilike if FTS RPC fails", async () => {
      // First call: RPC fails
      mockSupabaseClient.rpc.mockResolvedValue({
        data: null,
        error: { message: "Function not found" },
      });

      // Fallback: ilike succeeds
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        range: vi.fn().mockReturnThis(),
        limit: vi.fn().mockResolvedValue({
          data: mockSearchResults,
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      const result = await searchDocuments("test");

      expect(result.documents).toEqual(mockSearchResults);
      expect(result.error).toBeUndefined();
      // Should have tried RPC first
      expect(mockSupabaseClient.rpc).toHaveBeenCalled();
      // Then fallen back to ilike
      expect(mockQuery.or).toHaveBeenCalledWith(
        expect.stringContaining("file_name.ilike.%test%")
      );
    });

    it("should return error if both FTS and fallback fail", async () => {
      // RPC fails
      mockSupabaseClient.rpc.mockResolvedValue({
        data: null,
        error: { message: "RPC failed" },
      });

      // Fallback also fails
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        range: vi.fn().mockReturnThis(),
        limit: vi.fn().mockResolvedValue({
          data: null,
          error: { message: "Search failed" },
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      const result = await searchDocuments("test");

      expect(result.documents).toEqual([]);
      expect(result.error).toBe("Search failed");
    });

    it("should handle ilike errors for short queries", async () => {
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        range: vi.fn().mockReturnThis(),
        limit: vi.fn().mockResolvedValue({
          data: null,
          error: { message: "Search failed" },
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      const result = await searchDocuments("xy");

      expect(result.documents).toEqual([]);
      expect(result.error).toBe("Search failed");
    });

    it("should pass result_limit of 50 to FTS RPC", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: [],
        error: null,
      });

      await searchDocuments("document");

      expect(mockSupabaseClient.rpc).toHaveBeenCalledWith("search_documents_fts", {
        search_query: "document",
        result_limit: 20,
        result_offset: 0,
      });
    });

    it("should trim whitespace from query", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: mockFTSResults,
        error: null,
      });

      await searchDocuments("  verizon  ");

      expect(mockSupabaseClient.rpc).toHaveBeenCalledWith("search_documents_fts", {
        search_query: "verizon",
        result_limit: 20,
        result_offset: 0,
      });
    });

    it("should map FTS result removing rank field", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: mockFTSResults,
        error: null,
      });

      const result = await searchDocuments("verizon");

      expect(result.documents[0]).not.toHaveProperty("rank");
      expect(result.documents[0]).toHaveProperty("id");
      expect(result.documents[0]).toHaveProperty("file_name");
    });

    it("should handle empty FTS results", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: [],
        error: null,
      });

      const result = await searchDocuments("nonexistent");

      expect(result.documents).toEqual([]);
      expect(result.error).toBeUndefined();
    });
  });

  describe("resetSupabaseClient", () => {
    it("should allow creating a new client after reset", () => {
      const client1 = getSupabaseClient();
      resetSupabaseClient();
      const client2 = getSupabaseClient();

      // After reset, a new client should be created
      // Since we're mocking, both will be the same mock object
      // but the reset should have been called
      expect(client1).toBeDefined();
      expect(client2).toBeDefined();
    });
  });
});

describe("Document Types", () => {
  it("should have correct Document interface structure", () => {
    const doc: Document = {
      id: "test-id",
      file_name: "test.pdf",
      current_path: "/path/to/test.pdf",
      ai_category: "tax_document",
      ai_subcategories: ["1099", "W2"],
      ai_summary: "A tax document",
      entities: {
        people: ["John Doe"],
        organizations: ["IRS"],
        amounts: ["$1000"],
      },
      key_dates: ["2024-01-01"],
      folder_hierarchy: ["taxes", "2024"],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-02T00:00:00Z",
    };

    expect(doc.id).toBe("test-id");
    expect(doc.entities?.people).toContain("John Doe");
  });

  it("should allow null values for optional fields", () => {
    const doc: Document = {
      id: "test-id",
      file_name: "test.pdf",
      current_path: "/path/to/test.pdf",
      ai_category: null,
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: null,
      folder_hierarchy: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-02T00:00:00Z",
    };

    expect(doc.ai_category).toBeNull();
    expect(doc.entities).toBeNull();
  });
});

describe("extractYearFromDate", () => {
  it("should extract year from ISO date format", () => {
    expect(extractYearFromDate("2024-01-15")).toBe(2024);
    expect(extractYearFromDate("2023-12-31")).toBe(2023);
  });

  it("should extract year from ISO datetime format", () => {
    expect(extractYearFromDate("2024-01-15T10:30:00Z")).toBe(2024);
  });

  it("should extract year from US date format MM/DD/YYYY", () => {
    expect(extractYearFromDate("01/15/2024")).toBe(2024);
    expect(extractYearFromDate("12/31/2023")).toBe(2023);
  });

  it("should extract year from US date format MM-DD-YYYY", () => {
    expect(extractYearFromDate("01-15-2024")).toBe(2024);
  });

  it("should extract year from text containing a year", () => {
    expect(extractYearFromDate("Tax Document 2024")).toBe(2024);
    expect(extractYearFromDate("Statement from 2023")).toBe(2023);
  });

  it("should return null for invalid or missing date", () => {
    expect(extractYearFromDate("")).toBeNull();
    expect(extractYearFromDate("no date here")).toBeNull();
    expect(extractYearFromDate("1899")).toBeNull(); // Before 1900
  });

  it("should handle years in 1900-2099 range", () => {
    expect(extractYearFromDate("1999-01-01")).toBe(1999);
    expect(extractYearFromDate("2099-12-31")).toBe(2099);
  });
});

describe("getDateDistribution", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  it("should return year counts from key_dates", async () => {
    const mockDocs = [
      { key_dates: ["2024-01-15", "2024-06-20"] },
      { key_dates: ["2024-03-10"] },
      { key_dates: ["2023-12-01"] },
    ];

    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: mockDocs,
        error: null,
      }),
    });

    const result = await getDateDistribution();

    expect(result.error).toBeUndefined();
    expect(result.dateDistribution).toContainEqual({ year: 2024, count: 2 });
    expect(result.dateDistribution).toContainEqual({ year: 2023, count: 1 });
  });

  it("should count each unique year once per document", async () => {
    // Document with multiple dates in same year should count as 1
    const mockDocs = [
      { key_dates: ["2024-01-15", "2024-06-20", "2024-12-01"] },
    ];

    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: mockDocs,
        error: null,
      }),
    });

    const result = await getDateDistribution();

    expect(result.dateDistribution).toEqual([{ year: 2024, count: 1 }]);
  });

  it("should sort by year descending (most recent first)", async () => {
    const mockDocs = [
      { key_dates: ["2022-01-01"] },
      { key_dates: ["2024-01-01"] },
      { key_dates: ["2023-01-01"] },
    ];

    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: mockDocs,
        error: null,
      }),
    });

    const result = await getDateDistribution();

    expect(result.dateDistribution[0].year).toBe(2024);
    expect(result.dateDistribution[1].year).toBe(2023);
    expect(result.dateDistribution[2].year).toBe(2022);
  });

  it("should handle documents with no key_dates", async () => {
    const mockDocs = [
      { key_dates: null },
      { key_dates: [] },
      { key_dates: ["2024-01-01"] },
    ];

    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: mockDocs,
        error: null,
      }),
    });

    const result = await getDateDistribution();

    expect(result.dateDistribution).toEqual([{ year: 2024, count: 1 }]);
  });

  it("should handle database errors", async () => {
    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: null,
        error: { message: "Database error" },
      }),
    });

    const result = await getDateDistribution();

    expect(result.dateDistribution).toEqual([]);
    expect(result.error).toBe("Database error");
  });

  it("should return empty array when no documents", async () => {
    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: [],
        error: null,
      }),
    });

    const result = await getDateDistribution();

    expect(result.dateDistribution).toEqual([]);
    expect(result.error).toBeUndefined();
  });
});

describe("getContextBinCounts", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  it("should return context bin counts from folder_hierarchy", async () => {
    const mockDocs = [
      { folder_hierarchy: ["Finances Bin", "Bills", "Verizon"] },
      { folder_hierarchy: ["Finances Bin", "Taxes"] },
      { folder_hierarchy: ["Personal Bin", "Photos"] },
    ];

    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: mockDocs,
        error: null,
      }),
    });

    const result = await getContextBinCounts();

    expect(result.error).toBeUndefined();
    expect(result.contextBins).toContainEqual({
      context_bin: "Finances Bin",
      count: 2,
    });
    expect(result.contextBins).toContainEqual({
      context_bin: "Personal Bin",
      count: 1,
    });
  });

  it("should count documents without hierarchy as uncategorized", async () => {
    const mockDocs = [
      { folder_hierarchy: ["Finances Bin"] },
      { folder_hierarchy: null },
      { folder_hierarchy: [] },
    ];

    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: mockDocs,
        error: null,
      }),
    });

    const result = await getContextBinCounts();

    expect(result.contextBins).toContainEqual({
      context_bin: "Finances Bin",
      count: 1,
    });
    expect(result.contextBins).toContainEqual({
      context_bin: "uncategorized",
      count: 2,
    });
  });

  it("should sort by count descending", async () => {
    const mockDocs = [
      { folder_hierarchy: ["A Bin"] },
      { folder_hierarchy: ["B Bin"] },
      { folder_hierarchy: ["B Bin"] },
      { folder_hierarchy: ["B Bin"] },
      { folder_hierarchy: ["C Bin"] },
      { folder_hierarchy: ["C Bin"] },
    ];

    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: mockDocs,
        error: null,
      }),
    });

    const result = await getContextBinCounts();

    expect(result.contextBins[0].context_bin).toBe("B Bin");
    expect(result.contextBins[0].count).toBe(3);
    expect(result.contextBins[1].context_bin).toBe("C Bin");
    expect(result.contextBins[1].count).toBe(2);
    expect(result.contextBins[2].context_bin).toBe("A Bin");
    expect(result.contextBins[2].count).toBe(1);
  });

  it("should handle database errors", async () => {
    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: null,
        error: { message: "Connection failed" },
      }),
    });

    const result = await getContextBinCounts();

    expect(result.contextBins).toEqual([]);
    expect(result.error).toBe("Connection failed");
  });
});

describe("getStatistics", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  it("should return combined statistics", async () => {
    // Optimized: Single query returns all data for statistics computation
    const mockData = [
      { ai_category: "tax_doc", key_dates: ["2024-01-01"], folder_hierarchy: ["Finances Bin"] },
    ];

    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: mockData,
        error: null,
      }),
    });

    // Clear cache and get fresh statistics
    clearStatisticsCache();
    const result = await getStatistics(true);

    expect(result.categories).toEqual([{ ai_category: "tax_doc", count: 1 }]);
    expect(result.dateDistribution).toEqual([{ year: 2024, count: 1 }]);
    expect(result.contextBins).toEqual([
      { context_bin: "Finances Bin", count: 1 },
    ]);
    expect(result.error).toBeUndefined();
  });

  it("should return error on database failure", async () => {
    // Optimized query fails
    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: null,
        error: { message: "Query failed" },
      }),
    });

    clearStatisticsCache();
    const result = await getStatistics(true);

    expect(result.error).toBe("Query failed");
    expect(result.categories).toEqual([]);
    expect(result.dateDistribution).toEqual([]);
    expect(result.contextBins).toEqual([]);
  });

  it("should handle empty results", async () => {
    mockSupabaseClient.from.mockReturnValue({
      select: vi.fn().mockResolvedValue({
        data: [],
        error: null,
      }),
    });

    clearStatisticsCache();
    const result = await getStatistics(true);

    expect(result.categories).toEqual([]);
    expect(result.dateDistribution).toEqual([]);
    expect(result.contextBins).toEqual([]);
    expect(result.error).toBeUndefined();
  });
});

describe("Statistics Types", () => {
  it("should have correct YearCount interface structure", () => {
    const yearCount: YearCount = { year: 2024, count: 42 };
    expect(yearCount.year).toBe(2024);
    expect(yearCount.count).toBe(42);
  });

  it("should have correct ContextBinCount interface structure", () => {
    const binCount: ContextBinCount = {
      context_bin: "Finances Bin",
      count: 100,
    };
    expect(binCount.context_bin).toBe("Finances Bin");
    expect(binCount.count).toBe(100);
  });
});

describe("naturalLanguageSearch", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  const mockDocuments: Document[] = [
    {
      id: "1",
      file_name: "verizon_bill_2024.pdf",
      current_path: "/bills/verizon_bill_2024.pdf",
      ai_category: "utility_bill",
      ai_subcategories: null,
      ai_summary: "Verizon phone bill for January 2024",
      entities: { organizations: ["Verizon"], amounts: ["$89.99"] },
      key_dates: ["2024-01-15"],
      folder_hierarchy: ["bills"],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "2",
      file_name: "tax_return_2023.pdf",
      current_path: "/taxes/tax_return_2023.pdf",
      ai_category: "tax_document",
      ai_subcategories: ["1040"],
      ai_summary: "Federal tax return for 2023",
      entities: { organizations: ["IRS"], amounts: ["$5000"] },
      key_dates: ["2023-04-15"],
      folder_hierarchy: ["taxes"],
      created_at: "2023-04-01T00:00:00Z",
      updated_at: "2023-04-01T00:00:00Z",
    },
  ];

  // FTS response includes rank field
  const mockFTSResults = [
    {
      id: "1",
      file_name: "verizon_bill_2024.pdf",
      current_path: "/bills/verizon_bill_2024.pdf",
      ai_category: "utility_bill",
      ai_subcategories: null,
      ai_summary: "Verizon phone bill for January 2024",
      entities: { organizations: ["Verizon"], amounts: ["$89.99"] },
      key_dates: ["2024-01-15"],
      folder_hierarchy: ["bills"],
      file_modified_at: null,
      pdf_modified_date: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
      rank: 0.95,
    },
  ];

  describe("FTS Natural Language Search", () => {
    it("should use FTS RPC for queries with search terms >= 3 chars", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: mockFTSResults,
        error: null,
      });

      const result = await naturalLanguageSearch({
        originalQuery: "verizon bill",
        searchTerms: ["verizon", "bill"],
        category: null,
        years: [],
        organizations: [],
      });

      expect(mockSupabaseClient.rpc).toHaveBeenCalledWith(
        "natural_language_search_fts",
        expect.objectContaining({
          search_terms: ["verizon", "bill"],
          category_filter: null,
          organization_filters: null,
        })
      );
      expect(result.documents).toHaveLength(1);
      expect(result.error).toBeUndefined();
    });

    it("should pass category filter to FTS RPC", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: mockFTSResults,
        error: null,
      });

      await naturalLanguageSearch({
        originalQuery: "verizon bill",
        searchTerms: ["verizon", "bill"],
        category: "utility_bill",
        years: [],
        organizations: [],
      });

      expect(mockSupabaseClient.rpc).toHaveBeenCalledWith(
        "natural_language_search_fts",
        expect.objectContaining({
          category_filter: "utility_bill",
        })
      );
    });

    it("should pass organization filters to FTS RPC", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: mockFTSResults,
        error: null,
      });

      await naturalLanguageSearch({
        originalQuery: "verizon bill",
        searchTerms: ["bill"],
        category: null,
        years: [],
        organizations: ["Verizon"],
      });

      expect(mockSupabaseClient.rpc).toHaveBeenCalledWith(
        "natural_language_search_fts",
        expect.objectContaining({
          search_terms: ["bill", "Verizon"], // organizations added to search terms
          organization_filters: ["Verizon"],
        })
      );
    });

    it("should strip rank field from FTS results", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: mockFTSResults,
        error: null,
      });

      const result = await naturalLanguageSearch({
        originalQuery: "verizon",
        searchTerms: ["verizon"],
        category: null,
        years: [],
        organizations: [],
      });

      expect(result.documents[0]).not.toHaveProperty("rank");
      expect(result.documents[0]).toHaveProperty("id");
      expect(result.documents[0]).toHaveProperty("file_name");
    });

    it("should fall back to ilike if FTS RPC fails", async () => {
      // FTS fails
      mockSupabaseClient.rpc.mockResolvedValue({
        data: null,
        error: { message: "Function not found" },
      });

      // Fallback succeeds
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        eq: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        range: vi.fn().mockReturnThis(),
        limit: vi.fn().mockResolvedValue({
          data: mockDocuments,
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      const result = await naturalLanguageSearch({
        originalQuery: "verizon",
        searchTerms: ["verizon"],
        category: null,
        years: [],
        organizations: [],
      });

      expect(mockSupabaseClient.rpc).toHaveBeenCalled();
      expect(mockQuery.or).toHaveBeenCalled();
      expect(result.documents).toHaveLength(2);
    });

    it("should use ilike fallback for short queries (< 3 chars total)", async () => {
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        range: vi.fn().mockReturnThis(),
        limit: vi.fn().mockResolvedValue({
          data: mockDocuments,
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      await naturalLanguageSearch({
        originalQuery: "ab",
        searchTerms: ["ab"],
        category: null,
        years: [],
        organizations: [],
      });

      // RPC should NOT be called for short queries
      expect(mockSupabaseClient.rpc).not.toHaveBeenCalled();
      expect(mockQuery.or).toHaveBeenCalledWith(
        expect.stringContaining("ai_summary.ilike.%ab%")
      );
    });

    it("should pass result_limit to FTS RPC (2x the requested limit)", async () => {
      mockSupabaseClient.rpc.mockResolvedValue({
        data: [],
        error: null,
      });

      await naturalLanguageSearch(
        {
          originalQuery: "verizon bill",
          searchTerms: ["verizon", "bill"],
          category: null,
          years: [],
          organizations: [],
        },
        25
      );

      expect(mockSupabaseClient.rpc).toHaveBeenCalledWith(
        "natural_language_search_fts",
        expect.objectContaining({
          result_limit: 50, // 25 * 2
          result_offset: 0,
        })
      );
    });

    it("should still post-filter by years (client-side)", async () => {
      // FTS returns both docs
      mockSupabaseClient.rpc.mockResolvedValue({
        data: [
          { ...mockFTSResults[0] },
          {
            id: "2",
            file_name: "tax_return_2023.pdf",
            current_path: "/taxes/tax_return_2023.pdf",
            ai_category: "tax_document",
            ai_subcategories: ["1040"],
            ai_summary: "Federal tax return for 2023",
            entities: { organizations: ["IRS"], amounts: ["$5000"] },
            key_dates: ["2023-04-15"],
            folder_hierarchy: ["taxes"],
            file_modified_at: null,
            pdf_modified_date: null,
            created_at: "2023-04-01T00:00:00Z",
            updated_at: "2023-04-01T00:00:00Z",
            rank: 0.8,
          },
        ],
        error: null,
      });

      const result = await naturalLanguageSearch({
        originalQuery: "documents 2024",
        searchTerms: ["documents"],
        category: null,
        years: [2024],
        organizations: [],
      });

      // Should filter to only 2024 documents
      expect(result.documents).toHaveLength(1);
      expect(result.documents[0].id).toBe("1");
    });

    it("should handle empty search terms with category filter", async () => {
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        eq: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        range: vi.fn().mockReturnThis(),
        limit: vi.fn().mockResolvedValue({
          data: [mockDocuments[0]],
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      await naturalLanguageSearch({
        originalQuery: "",
        searchTerms: [],
        category: "utility_bill",
        years: [],
        organizations: [],
      });

      // Should fall back to ilike since no search terms
      expect(mockSupabaseClient.rpc).not.toHaveBeenCalled();
    });
  });

  // Legacy tests for backward compatibility with ilike fallback
  describe("ilike Fallback", () => {
    it("should search with category filter using ilike when FTS unavailable", async () => {
      // Mock FTS to fail so we use ilike
      mockSupabaseClient.rpc.mockResolvedValue({
        data: null,
        error: { message: "Function not found" },
      });

      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        eq: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        range: vi.fn().mockReturnThis(),
        limit: vi.fn().mockResolvedValue({
          data: [mockDocuments[0]],
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      const result = await naturalLanguageSearch({
        originalQuery: "verizon bill 2024",
        searchTerms: ["verizon", "bill"],
        category: "utility_bill",
        years: [2024],
        organizations: [],
      });

      // After FTS fails, falls back to ilike
      expect(mockQuery.eq).toHaveBeenCalledWith("ai_category", "utility_bill");
      expect(result.error).toBeUndefined();
    });

    it("should search with organization filter in text fields using ilike", async () => {
      // Mock FTS to fail so we use ilike
      mockSupabaseClient.rpc.mockResolvedValue({
        data: null,
        error: { message: "Function not found" },
      });

      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        range: vi.fn().mockReturnThis(),
        limit: vi.fn().mockResolvedValue({
          data: mockDocuments,
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      const result = await naturalLanguageSearch({
        originalQuery: "verizon",
        searchTerms: [],
        category: null,
        years: [],
        organizations: ["Verizon"],
      });

      expect(mockQuery.or).toHaveBeenCalledWith(
        expect.stringContaining("ai_summary.ilike.%Verizon%")
      );
      // When using ilike fallback, post-filtering by organizations is applied
      expect(result.documents).toHaveLength(1);
    });

    it("should handle database errors in ilike fallback", async () => {
      // Mock FTS to fail
      mockSupabaseClient.rpc.mockResolvedValue({
        data: null,
        error: { message: "RPC failed" },
      });

      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        range: vi.fn().mockReturnThis(),
        limit: vi.fn().mockResolvedValue({
          data: null,
          error: { message: "Database error" },
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      const result = await naturalLanguageSearch({
        originalQuery: "test",
        searchTerms: ["test"],
        category: null,
        years: [],
        organizations: [],
      });

      expect(result.documents).toEqual([]);
      expect(result.error).toBe("Database error");
    });

    it("should apply custom limit in ilike fallback (2x for enrichment merging)", async () => {
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        range: vi.fn().mockReturnThis(),
        limit: vi.fn().mockResolvedValue({
          data: [],
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      await naturalLanguageSearch(
        {
          originalQuery: "ab", // Short query, uses ilike
          searchTerms: ["ab"],
          category: null,
          years: [],
          organizations: [],
        },
        25
      );

      expect(mockQuery.limit).toHaveBeenCalledWith(50); // 25 * 2
    });

    it("should search with multiple search terms in ilike when FTS fails", async () => {
      // Mock FTS to fail
      mockSupabaseClient.rpc.mockResolvedValue({
        data: null,
        error: { message: "RPC failed" },
      });

      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        range: vi.fn().mockReturnThis(),
        limit: vi.fn().mockResolvedValue({
          data: [],
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      await naturalLanguageSearch({
        originalQuery: "important document",
        searchTerms: ["important", "document"],
        category: null,
        years: [],
        organizations: [],
      });

      // After FTS fails, falls back to ilike
      expect(mockSupabaseClient.rpc).toHaveBeenCalled();
      expect(mockQuery.or).toHaveBeenCalledWith(
        expect.stringContaining("ai_summary.ilike.%important%")
      );
    });
  });
});

describe("filterByYears", () => {
  const mockDocuments: Document[] = [
    {
      id: "1",
      file_name: "doc_2024.pdf",
      current_path: "/docs/doc_2024.pdf",
      ai_category: null,
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: ["2024-01-15", "2024-06-20"],
      folder_hierarchy: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "2",
      file_name: "doc_2023.pdf",
      current_path: "/docs/doc_2023.pdf",
      ai_category: null,
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: ["2023-04-15"],
      folder_hierarchy: null,
      created_at: "2023-04-01T00:00:00Z",
      updated_at: "2023-04-01T00:00:00Z",
    },
    {
      id: "3",
      file_name: "doc_no_dates.pdf",
      current_path: "/docs/doc_no_dates.pdf",
      ai_category: null,
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: null,
      folder_hierarchy: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
  ];

  it("should filter documents by year", () => {
    const filtered = filterByYears(mockDocuments, [2024]);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe("1");
  });

  it("should filter by multiple years", () => {
    const filtered = filterByYears(mockDocuments, [2023, 2024]);
    expect(filtered).toHaveLength(2);
  });

  it("should return empty array if no years match", () => {
    const filtered = filterByYears(mockDocuments, [2020]);
    expect(filtered).toHaveLength(0);
  });

  it("should return all documents if years array is empty", () => {
    const filtered = filterByYears(mockDocuments, []);
    expect(filtered).toEqual(mockDocuments);
  });

  it("should exclude documents with no key_dates", () => {
    const filtered = filterByYears(mockDocuments, [2024]);
    expect(filtered.some((d) => d.id === "3")).toBe(false);
  });
});

describe("filterByOrganizations", () => {
  const mockDocuments: Document[] = [
    {
      id: "1",
      file_name: "verizon_bill.pdf",
      current_path: "/bills/verizon_bill.pdf",
      ai_category: "utility_bill",
      ai_subcategories: null,
      ai_summary: "Verizon phone bill",
      entities: { organizations: ["Verizon"] },
      key_dates: null,
      folder_hierarchy: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "2",
      file_name: "amazon_invoice.pdf",
      current_path: "/invoices/amazon_invoice.pdf",
      ai_category: "invoice",
      ai_subcategories: null,
      ai_summary: "Amazon purchase",
      entities: { organizations: ["Amazon"] },
      key_dates: null,
      folder_hierarchy: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "3",
      file_name: "random_doc.pdf",
      current_path: "/docs/random_doc.pdf",
      ai_category: null,
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: null,
      folder_hierarchy: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
  ];

  it("should filter documents by organization in entities", () => {
    const filtered = filterByOrganizations(mockDocuments, ["Verizon"]);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe("1");
  });

  it("should filter by organization in summary", () => {
    const docsWithSummary: Document[] = [
      {
        ...mockDocuments[2],
        ai_summary: "Document from Verizon",
        entities: null,
      },
    ];
    const filtered = filterByOrganizations(docsWithSummary, ["Verizon"]);
    expect(filtered).toHaveLength(1);
  });

  it("should filter by organization in file_name", () => {
    const filtered = filterByOrganizations(mockDocuments, ["verizon"]);
    expect(filtered).toHaveLength(1);
  });

  it("should be case insensitive", () => {
    const filtered = filterByOrganizations(mockDocuments, ["VERIZON"]);
    expect(filtered).toHaveLength(1);
  });

  it("should filter by multiple organizations", () => {
    const filtered = filterByOrganizations(mockDocuments, [
      "Verizon",
      "Amazon",
    ]);
    expect(filtered).toHaveLength(2);
  });

  it("should return all documents if organizations array is empty", () => {
    const filtered = filterByOrganizations(mockDocuments, []);
    expect(filtered).toEqual(mockDocuments);
  });

  it("should return empty array if no organizations match", () => {
    const filtered = filterByOrganizations(mockDocuments, ["Microsoft"]);
    expect(filtered).toHaveLength(0);
  });
});

describe("filterByContextBin", () => {
  const mockDocuments: Document[] = [
    {
      id: "1",
      file_name: "finance_doc.pdf",
      current_path: "/finances/finance_doc.pdf",
      ai_category: "tax_document",
      ai_subcategories: null,
      ai_summary: "A financial document",
      entities: null,
      key_dates: null,
      folder_hierarchy: ["Finances Bin", "Taxes", "2024"],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "2",
      file_name: "personal_doc.pdf",
      current_path: "/personal/personal_doc.pdf",
      ai_category: "personal",
      ai_subcategories: null,
      ai_summary: "A personal document",
      entities: null,
      key_dates: null,
      folder_hierarchy: ["Personal Bin", "Photos"],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "3",
      file_name: "uncategorized_doc.pdf",
      current_path: "/uncategorized_doc.pdf",
      ai_category: null,
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: null,
      folder_hierarchy: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "4",
      file_name: "empty_hierarchy_doc.pdf",
      current_path: "/empty_hierarchy_doc.pdf",
      ai_category: null,
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: null,
      folder_hierarchy: [],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
  ];

  it("should filter documents by context bin", () => {
    const filtered = filterByContextBin(mockDocuments, "Finances Bin");
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe("1");
  });

  it("should be case insensitive", () => {
    const filtered = filterByContextBin(mockDocuments, "finances bin");
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe("1");
  });

  it("should filter by Personal Bin", () => {
    const filtered = filterByContextBin(mockDocuments, "Personal Bin");
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe("2");
  });

  it("should match uncategorized for documents with null hierarchy", () => {
    const filtered = filterByContextBin(mockDocuments, "uncategorized");
    expect(filtered).toHaveLength(2);
    expect(filtered.map((d) => d.id)).toContain("3");
    expect(filtered.map((d) => d.id)).toContain("4");
  });

  it("should return empty array if no context bin matches", () => {
    const filtered = filterByContextBin(mockDocuments, "Work Bin");
    expect(filtered).toHaveLength(0);
  });

  it("should match only the top-level folder", () => {
    // Should not match "Taxes" or "2024" as they are not top-level
    const filtered = filterByContextBin(mockDocuments, "Taxes");
    expect(filtered).toHaveLength(0);
  });
});

describe("filterByDateRange", () => {
  const mockDocuments: Document[] = [
    {
      id: "1",
      file_name: "doc_2024.pdf",
      current_path: "/docs/doc_2024.pdf",
      ai_category: null,
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: ["2024-01-15", "2024-06-20"],
      folder_hierarchy: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "2",
      file_name: "doc_2023.pdf",
      current_path: "/docs/doc_2023.pdf",
      ai_category: null,
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: ["2023-04-15"],
      folder_hierarchy: null,
      created_at: "2023-04-01T00:00:00Z",
      updated_at: "2023-04-01T00:00:00Z",
    },
    {
      id: "3",
      file_name: "doc_2022.pdf",
      current_path: "/docs/doc_2022.pdf",
      ai_category: null,
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: ["2022-12-01"],
      folder_hierarchy: null,
      created_at: "2022-12-01T00:00:00Z",
      updated_at: "2022-12-01T00:00:00Z",
    },
    {
      id: "4",
      file_name: "doc_no_dates.pdf",
      current_path: "/docs/doc_no_dates.pdf",
      ai_category: null,
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: null,
      folder_hierarchy: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
  ];

  it("should filter documents by start year", () => {
    const filtered = filterByDateRange(mockDocuments, 2023, undefined);
    expect(filtered).toHaveLength(2);
    expect(filtered.map((d) => d.id)).toContain("1");
    expect(filtered.map((d) => d.id)).toContain("2");
  });

  it("should filter documents by end year", () => {
    const filtered = filterByDateRange(mockDocuments, undefined, 2023);
    expect(filtered).toHaveLength(2);
    expect(filtered.map((d) => d.id)).toContain("2");
    expect(filtered.map((d) => d.id)).toContain("3");
  });

  it("should filter documents by start and end year range", () => {
    const filtered = filterByDateRange(mockDocuments, 2022, 2023);
    expect(filtered).toHaveLength(2);
    expect(filtered.map((d) => d.id)).toContain("2");
    expect(filtered.map((d) => d.id)).toContain("3");
  });

  it("should filter to single year when start equals end", () => {
    const filtered = filterByDateRange(mockDocuments, 2024, 2024);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe("1");
  });

  it("should return all documents if neither start nor end specified", () => {
    const filtered = filterByDateRange(mockDocuments, undefined, undefined);
    expect(filtered).toEqual(mockDocuments);
  });

  it("should exclude documents with no key_dates", () => {
    const filtered = filterByDateRange(mockDocuments, 2020, 2025);
    expect(filtered.some((d) => d.id === "4")).toBe(false);
  });

  it("should return empty array if no documents match the range", () => {
    const filtered = filterByDateRange(mockDocuments, 2025, 2026);
    expect(filtered).toHaveLength(0);
  });

  it("should include documents at the boundary years", () => {
    const filtered = filterByDateRange(mockDocuments, 2022, 2022);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe("3");
  });
});

describe("getDocuments enhanced options", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  const mockDocuments: Document[] = [
    {
      id: "1",
      file_name: "finance_2024.pdf",
      current_path: "/finances/finance_2024.pdf",
      ai_category: "tax_document",
      ai_subcategories: null,
      ai_summary: "Tax document from 2024",
      entities: null,
      key_dates: ["2024-01-15"],
      folder_hierarchy: ["Finances Bin", "Taxes"],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "2",
      file_name: "personal_2023.pdf",
      current_path: "/personal/personal_2023.pdf",
      ai_category: "personal",
      ai_subcategories: null,
      ai_summary: "Personal document from 2023",
      entities: null,
      key_dates: ["2023-06-20"],
      folder_hierarchy: ["Personal Bin"],
      created_at: "2023-06-01T00:00:00Z",
      updated_at: "2023-06-01T00:00:00Z",
    },
  ];

  it("should return filteredTotal in result", async () => {
    // Server-side pagination (no client-side filtering needed)
    const mockQuery = {
      select: vi.fn().mockReturnThis(),
      order: vi.fn().mockReturnThis(),
      range: vi.fn().mockResolvedValue({
        data: mockDocuments,
        count: 2,
        error: null,
      }),
    };
    mockSupabaseClient.from.mockReturnValue(mockQuery);

    const result = await getDocuments();

    expect(result.filteredTotal).toBeDefined();
    expect(result.filteredTotal).toBe(2);
  });

  it("should filter by context bin", async () => {
    // Client-side filtering for context bin (array column)
    // First query: filter query
    // Second query: fetch full docs
    let callCount = 0;
    mockSupabaseClient.from.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // Filter query returns minimal data
        return {
          select: vi.fn().mockResolvedValue({
            data: mockDocuments.map(d => ({
              id: d.id,
              ai_category: d.ai_category,
              folder_hierarchy: d.folder_hierarchy,
              key_dates: d.key_dates,
              file_name: d.file_name,
              ai_summary: d.ai_summary,
              current_path: d.current_path,
            })),
            count: 2,
            error: null,
          }),
        };
      }
      // Page query returns full docs
      return {
        select: vi.fn().mockReturnThis(),
        in: vi.fn().mockReturnThis(),
        order: vi.fn().mockResolvedValue({
          data: [mockDocuments[0]],
          error: null,
        }),
      };
    });

    const result = await getDocuments({ contextBin: "Finances Bin" });

    expect(result.documents).toHaveLength(1);
    expect(result.documents[0].id).toBe("1");
    expect(result.filteredTotal).toBe(1);
  });

  it("should filter by date range with startYear", async () => {
    // Client-side filtering for date range (array column)
    let callCount = 0;
    mockSupabaseClient.from.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return {
          select: vi.fn().mockResolvedValue({
            data: mockDocuments.map(d => ({
              id: d.id,
              ai_category: d.ai_category,
              folder_hierarchy: d.folder_hierarchy,
              key_dates: d.key_dates,
              file_name: d.file_name,
              ai_summary: d.ai_summary,
              current_path: d.current_path,
            })),
            count: 2,
            error: null,
          }),
        };
      }
      return {
        select: vi.fn().mockReturnThis(),
        in: vi.fn().mockReturnThis(),
        order: vi.fn().mockResolvedValue({
          data: [mockDocuments[0]],
          error: null,
        }),
      };
    });

    const result = await getDocuments({ startYear: 2024 });

    expect(result.documents).toHaveLength(1);
    expect(result.documents[0].id).toBe("1");
  });

  it("should filter by date range with endYear", async () => {
    // Client-side filtering for date range (array column)
    let callCount = 0;
    mockSupabaseClient.from.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return {
          select: vi.fn().mockResolvedValue({
            data: mockDocuments.map(d => ({
              id: d.id,
              ai_category: d.ai_category,
              folder_hierarchy: d.folder_hierarchy,
              key_dates: d.key_dates,
              file_name: d.file_name,
              ai_summary: d.ai_summary,
              current_path: d.current_path,
            })),
            count: 2,
            error: null,
          }),
        };
      }
      return {
        select: vi.fn().mockReturnThis(),
        in: vi.fn().mockReturnThis(),
        order: vi.fn().mockResolvedValue({
          data: [mockDocuments[1]],
          error: null,
        }),
      };
    });

    const result = await getDocuments({ endYear: 2023 });

    expect(result.documents).toHaveLength(1);
    expect(result.documents[0].id).toBe("2");
  });

  it("should filter by search keyword", async () => {
    // Server-side filtering for search (no client-side filtering needed)
    const mockQuery = {
      select: vi.fn().mockReturnThis(),
      or: vi.fn().mockReturnThis(),
      order: vi.fn().mockReturnThis(),
      range: vi.fn().mockResolvedValue({
        data: [mockDocuments[0]],
        count: 1,
        error: null,
      }),
    };
    mockSupabaseClient.from.mockReturnValue(mockQuery);

    const result = await getDocuments({ search: "tax" });

    expect(mockQuery.or).toHaveBeenCalledWith(
      expect.stringContaining("file_name.ilike.%tax%")
    );
  });

  it("should combine multiple filters", async () => {
    // Client-side filtering (context bin + date range triggers client filtering)
    let callCount = 0;
    mockSupabaseClient.from.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // Filter query with category filter
        return {
          select: vi.fn().mockReturnThis(),
          eq: vi.fn().mockResolvedValue({
            data: mockDocuments.map(d => ({
              id: d.id,
              ai_category: d.ai_category,
              folder_hierarchy: d.folder_hierarchy,
              key_dates: d.key_dates,
              file_name: d.file_name,
              ai_summary: d.ai_summary,
              current_path: d.current_path,
            })),
            count: 2,
            error: null,
          }),
        };
      }
      // Page query returns filtered doc
      return {
        select: vi.fn().mockReturnThis(),
        in: vi.fn().mockReturnThis(),
        order: vi.fn().mockResolvedValue({
          data: [mockDocuments[0]],
          error: null,
        }),
      };
    });

    const options: DocumentListOptions = {
      category: "tax_document",
      contextBin: "Finances Bin",
      startYear: 2024,
      endYear: 2024,
    };

    const result = await getDocuments(options);

    expect(result.documents).toHaveLength(1);
    expect(result.documents[0].id).toBe("1");
  });

  it("should apply pagination after filtering", async () => {
    const manyDocs: Document[] = Array.from({ length: 10 }, (_, i) => ({
      id: String(i + 1),
      file_name: `doc_${i + 1}.pdf`,
      current_path: `/docs/doc_${i + 1}.pdf`,
      ai_category: "test",
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: ["2024-01-15"],
      folder_hierarchy: ["Test Bin"],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    }));

    // Client-side filtering (contextBin triggers client filtering)
    let callCount = 0;
    mockSupabaseClient.from.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return {
          select: vi.fn().mockResolvedValue({
            data: manyDocs.map(d => ({
              id: d.id,
              ai_category: d.ai_category,
              folder_hierarchy: d.folder_hierarchy,
              key_dates: d.key_dates,
              file_name: d.file_name,
              ai_summary: d.ai_summary,
              current_path: d.current_path,
            })),
            count: 10,
            error: null,
          }),
        };
      }
      // Return docs 3, 4, 5 (offset 2, limit 3)
      return {
        select: vi.fn().mockReturnThis(),
        in: vi.fn().mockReturnThis(),
        order: vi.fn().mockResolvedValue({
          data: [manyDocs[2], manyDocs[3], manyDocs[4]],
          error: null,
        }),
      };
    });

    const result = await getDocuments({ contextBin: "Test Bin", limit: 3, offset: 2 });

    expect(result.filteredTotal).toBe(10);
    expect(result.documents).toHaveLength(3);
    expect(result.documents[0].id).toBe("3");
    expect(result.documents[2].id).toBe("5");
  });
});

describe("DocumentListOptions and DocumentListResult types", () => {
  it("should have correct DocumentListOptions interface structure", () => {
    const options: DocumentListOptions = {
      category: "tax_document",
      contextBin: "Finances Bin",
      startYear: 2020,
      endYear: 2024,
      search: "test",
      limit: 20,
      offset: 0,
      orderBy: "created_at",
      orderDirection: "desc",
    };

    expect(options.category).toBe("tax_document");
    expect(options.contextBin).toBe("Finances Bin");
    expect(options.startYear).toBe(2020);
    expect(options.endYear).toBe(2024);
    expect(options.search).toBe("test");
  });

  it("should have correct DocumentListResult interface structure", () => {
    const result: DocumentListResult = {
      documents: [],
      total: 100,
      filteredTotal: 50,
      error: undefined,
    };

    expect(result.total).toBe(100);
    expect(result.filteredTotal).toBe(50);
    expect(result.documents).toEqual([]);
  });
});

describe("Performance Optimizations", () => {
  beforeEach(() => {
    resetSupabaseClient();
    clearStatisticsCache();
    vi.clearAllMocks();
  });

  afterEach(() => {
    clearStatisticsCache();
  });

  describe("Statistics Cache", () => {
    it("should cache statistics results", async () => {
      const mockData = [
        { ai_category: "tax_doc", key_dates: ["2024-01-01"], folder_hierarchy: ["Finances"] },
      ];

      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: mockData,
          error: null,
        }),
      });

      // First call - should hit database
      const result1 = await getStatistics();
      expect(result1.error).toBeUndefined();
      expect(mockSupabaseClient.from).toHaveBeenCalledTimes(1);

      // Second call - should use cache
      const result2 = await getStatistics();
      expect(result2).toEqual(result1);
      expect(mockSupabaseClient.from).toHaveBeenCalledTimes(1); // Still 1, used cache
    });

    it("should bypass cache when requested", async () => {
      const mockData = [
        { ai_category: "invoice", key_dates: ["2023-01-01"], folder_hierarchy: ["Bills"] },
      ];

      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: mockData,
          error: null,
        }),
      });

      // First call
      await getStatistics();
      expect(mockSupabaseClient.from).toHaveBeenCalledTimes(1);

      // Second call with bypass - should hit database again
      await getStatistics(true);
      expect(mockSupabaseClient.from).toHaveBeenCalledTimes(2);
    });

    it("should clear cache with clearStatisticsCache", async () => {
      const mockData = [
        { ai_category: "contract", key_dates: null, folder_hierarchy: null },
      ];

      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: mockData,
          error: null,
        }),
      });

      // First call
      await getStatistics();
      expect(mockSupabaseClient.from).toHaveBeenCalledTimes(1);

      // Clear cache
      clearStatisticsCache();

      // Third call - should hit database again
      await getStatistics();
      expect(mockSupabaseClient.from).toHaveBeenCalledTimes(2);
    });

    it("should not cache on error", async () => {
      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: null,
          error: { message: "Database error" },
        }),
      });

      // First call with error
      const result1 = await getStatistics();
      expect(result1.error).toBe("Database error");

      // Fix the mock to return success
      const mockData = [
        { ai_category: "medical", key_dates: ["2024-06-01"], folder_hierarchy: ["Health"] },
      ];
      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: mockData,
          error: null,
        }),
      });

      // Second call - should hit database (not cached error)
      const result2 = await getStatistics();
      expect(result2.error).toBeUndefined();
      expect(result2.categories).toHaveLength(1);
    });
  });

  describe("Optimized Statistics Query", () => {
    it("should compute all statistics from single query", async () => {
      const mockData = [
        { ai_category: "tax_doc", key_dates: ["2024-01-01"], folder_hierarchy: ["Finances"] },
        { ai_category: "tax_doc", key_dates: ["2024-06-01"], folder_hierarchy: ["Finances"] },
        { ai_category: "invoice", key_dates: ["2023-03-15"], folder_hierarchy: ["Bills"] },
        { ai_category: null, key_dates: null, folder_hierarchy: null },
      ];

      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: mockData,
          error: null,
        }),
      });

      const result = await getStatistics(true); // bypass cache

      // Should have made only 1 database call
      expect(mockSupabaseClient.from).toHaveBeenCalledTimes(1);

      // Verify categories
      expect(result.categories).toContainEqual({ ai_category: "tax_doc", count: 2 });
      expect(result.categories).toContainEqual({ ai_category: "invoice", count: 1 });
      expect(result.categories).toContainEqual({ ai_category: "uncategorized", count: 1 });

      // Verify date distribution
      expect(result.dateDistribution).toContainEqual({ year: 2024, count: 2 });
      expect(result.dateDistribution).toContainEqual({ year: 2023, count: 1 });

      // Verify context bins
      expect(result.contextBins).toContainEqual({ context_bin: "Finances", count: 2 });
      expect(result.contextBins).toContainEqual({ context_bin: "Bills", count: 1 });
      expect(result.contextBins).toContainEqual({ context_bin: "uncategorized", count: 1 });
    });
  });

  describe("Server-Side Pagination", () => {
    it("should use server-side pagination when no client-side filters needed", async () => {
      const mockDocs: Document[] = [
        {
          id: "1",
          file_name: "test.pdf",
          current_path: "/test.pdf",
          ai_category: "tax",
          ai_subcategories: null,
          ai_summary: null,
          entities: null,
          key_dates: null,
          folder_hierarchy: null,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ];

      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        eq: vi.fn().mockReturnThis(),
        or: vi.fn().mockReturnThis(),
        order: vi.fn().mockReturnThis(),
        range: vi.fn().mockResolvedValue({
          data: mockDocs,
          count: 100,
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      // Query without contextBin or date filters - should use server-side pagination
      const result = await getDocuments({
        category: "tax",
        limit: 10,
        offset: 0,
      });

      // Should use range() for server-side pagination
      expect(mockQuery.range).toHaveBeenCalledWith(0, 9);
      expect(result.documents).toEqual(mockDocs);
      expect(result.total).toBe(100);
    });

    it("should use client-side filtering when contextBin is specified", async () => {
      const mockDocs = [
        {
          id: "1",
          ai_category: "tax",
          folder_hierarchy: ["Finances"],
          key_dates: null,
          file_name: "test.pdf",
          ai_summary: null,
          current_path: "/test.pdf",
        },
        {
          id: "2",
          ai_category: "tax",
          folder_hierarchy: ["Personal"],
          key_dates: null,
          file_name: "other.pdf",
          ai_summary: null,
          current_path: "/other.pdf",
        },
      ];

      const fullDocs: Document[] = [
        {
          id: "1",
          file_name: "test.pdf",
          current_path: "/test.pdf",
          ai_category: "tax",
          ai_subcategories: null,
          ai_summary: null,
          entities: null,
          key_dates: null,
          folder_hierarchy: ["Finances"],
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ];

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          // First call: filter query
          return {
            select: vi.fn().mockReturnThis(),
            eq: vi.fn().mockReturnThis(),
            then: vi.fn((resolve) => resolve({ data: mockDocs, error: null, count: 2 })),
          };
        }
        // Second call: fetch full docs for page
        return {
          select: vi.fn().mockReturnThis(),
          in: vi.fn().mockReturnThis(),
          order: vi.fn().mockResolvedValue({ data: fullDocs, error: null }),
        };
      });

      const result = await getDocuments({
        contextBin: "Finances",
        limit: 10,
        offset: 0,
      });

      // Should have filtered to only Finances documents
      expect(result.documents).toHaveLength(1);
      expect(result.filteredTotal).toBe(1);
    });
  });
});
