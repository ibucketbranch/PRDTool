/**
 * Tests for the enrichment API endpoint
 */

import { describe, it, expect, vi, beforeEach, Mock } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "../app/api/enrichment/route";
import fs from "fs/promises";

// Mock fs/promises
vi.mock("fs/promises");
const mockFs = fs as { readFile: Mock };

describe("/api/enrichment", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockCacheData = {
    version: "1.0",
    updated_at: "2024-03-20T10:00:00Z",
    entry_count: 2,
    entries: [
      {
        file_hash: "abc123",
        file_path: "/Users/test/Documents/verizon_bill.pdf",
        enrichment: {
          document_type: "utility_bill",
          date_references: ["March 2024"],
          people: [],
          organizations: ["Verizon"],
          key_topics: ["billing"],
          summary: "Verizon bill for March 2024",
          suggested_tags: ["utility"],
          confidence: 0.85,
          model_used: "qwen2.5-coder:14b",
          used_keyword_fallback: false,
          enriched_at: "2024-03-20T10:00:00Z",
          duration_ms: 1500,
        },
        cached_at: "2024-03-20T10:00:00Z",
      },
      {
        file_hash: "def456",
        file_path: "/Users/test/Documents/tax_return.pdf",
        enrichment: {
          document_type: "tax_return",
          date_references: ["2023"],
          people: ["John Doe"],
          organizations: ["IRS"],
          key_topics: ["taxes"],
          summary: "Tax return for 2023",
          suggested_tags: ["tax"],
          confidence: 0.92,
          model_used: "qwen2.5-coder:14b",
          used_keyword_fallback: false,
          enriched_at: "2024-04-15T10:00:00Z",
          duration_ms: 2000,
        },
        cached_at: "2024-04-15T10:00:00Z",
      },
    ],
  };

  const createMockRequest = (params: Record<string, string> = {}) => {
    const url = new URL("http://localhost:3000/api/enrichment");
    for (const [key, value] of Object.entries(params)) {
      url.searchParams.set(key, value);
    }
    return new NextRequest(url);
  };

  describe("GET /api/enrichment?stats=true", () => {
    it("should return cache statistics", async () => {
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockCacheData));

      const request = createMockRequest({ stats: "true" });
      const response = await GET(request);
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.stats).toBeDefined();
      expect(data.stats.total_entries).toBe(2);
      expect(data.stats.llm_enriched).toBe(2);
      expect(data.stats.keyword_fallback).toBe(0);
      expect(data.stats.average_confidence).toBeCloseTo(0.885, 1);
      expect(data.stats.document_types).toHaveProperty("utility_bill", 1);
      expect(data.stats.document_types).toHaveProperty("tax_return", 1);
      expect(data.stats.top_organizations).toHaveProperty("Verizon", 1);
      expect(data.stats.top_organizations).toHaveProperty("IRS", 1);
    });

    it("should handle empty cache", async () => {
      mockFs.readFile.mockResolvedValue(JSON.stringify({
        version: "1.0",
        updated_at: "2024-03-20T10:00:00Z",
        entry_count: 0,
        entries: [],
      }));

      const request = createMockRequest({ stats: "true" });
      const response = await GET(request);
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.stats.total_entries).toBe(0);
      expect(data.stats.average_confidence).toBe(0);
    });
  });

  describe("GET /api/enrichment?hash=<hash>", () => {
    it("should return enrichment by hash", async () => {
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockCacheData));

      const request = createMockRequest({ hash: "abc123" });
      const response = await GET(request);
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.enrichment).toBeDefined();
      expect(data.enrichment.file_hash).toBe("abc123");
      expect(data.enrichment.document_type).toBe("utility_bill");
      expect(data.enrichment.organizations).toContain("Verizon");
    });

    it("should return null for non-existent hash", async () => {
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockCacheData));

      const request = createMockRequest({ hash: "nonexistent" });
      const response = await GET(request);
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.enrichment).toBeNull();
      expect(data.message).toBe("No enrichment found for hash");
    });
  });

  describe("GET /api/enrichment?path=<path>", () => {
    it("should return enrichment by path", async () => {
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockCacheData));

      const request = createMockRequest({
        path: "/Users/test/Documents/tax_return.pdf",
      });
      const response = await GET(request);
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.enrichment).toBeDefined();
      expect(data.enrichment.file_hash).toBe("def456");
      expect(data.enrichment.document_type).toBe("tax_return");
      expect(data.enrichment.organizations).toContain("IRS");
    });

    it("should return null for non-existent path", async () => {
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockCacheData));

      const request = createMockRequest({
        path: "/Users/test/Documents/nonexistent.pdf",
      });
      const response = await GET(request);
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.enrichment).toBeNull();
      expect(data.message).toBe("No enrichment found for path");
    });
  });

  describe("GET /api/enrichment (no params)", () => {
    it("should return usage message", async () => {
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockCacheData));

      const request = createMockRequest();
      const response = await GET(request);
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.message).toContain("?hash=<hash>");
      expect(data.entry_count).toBe(2);
    });
  });

  describe("error handling", () => {
    it("should handle missing cache file", async () => {
      mockFs.readFile.mockRejectedValue(new Error("ENOENT: file not found"));

      const request = createMockRequest({ stats: "true" });
      const response = await GET(request);
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.enrichment).toBeNull();
      expect(data.message).toBe("Enrichment cache not found or empty");
    });

    it("should handle malformed JSON", async () => {
      mockFs.readFile.mockResolvedValue("invalid json");

      const request = createMockRequest({ hash: "abc123" });
      const response = await GET(request);
      const data = await response.json();

      // Should handle error gracefully
      expect(data.success).toBe(true);
      expect(data.enrichment).toBeNull();
    });
  });
});
