/**
 * Tests for /api/inbox-process/history endpoint
 *
 * Phase 16.4: Explainability fields in routing history
 */

import { describe, it, expect, beforeEach, vi, Mock } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/inbox-process/history/route";
import fs from "fs/promises";

// Mock fs/promises
vi.mock("fs/promises");
const mockFs = fs as { readFile: Mock };

describe("/api/inbox-process/history", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("GET - Return routing history", () => {
    it("should return empty history when file does not exist", async () => {
      mockFs.readFile.mockRejectedValue(new Error("ENOENT"));

      const request = new NextRequest(
        "http://localhost/api/inbox-process/history"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.history).toEqual([]);
      expect(data.total).toBe(0);
    });

    it("should return records in reverse chronological order", async () => {
      const mockHistory = {
        records: [
          {
            filename: "file1.pdf",
            destination_bin: "Bin1",
            routed_at: "2024-01-01T10:00:00",
            confidence: 0.9,
            status: "executed",
          },
          {
            filename: "file2.pdf",
            destination_bin: "Bin2",
            routed_at: "2024-01-02T10:00:00",
            confidence: 0.95,
            status: "executed",
          },
        ],
      };
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockHistory));

      const request = new NextRequest(
        "http://localhost/api/inbox-process/history"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.history.length).toBe(2);
      // Most recent first
      expect(data.history[0].filename).toBe("file2.pdf");
      expect(data.history[1].filename).toBe("file1.pdf");
    });

    it("should respect limit parameter", async () => {
      const mockHistory = {
        records: Array.from({ length: 10 }, (_, i) => ({
          filename: `file${i}.pdf`,
          destination_bin: "Test",
          routed_at: `2024-01-${i + 1}T10:00:00`,
          confidence: 0.9,
          status: "executed",
        })),
      };
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockHistory));

      const request = new NextRequest(
        "http://localhost/api/inbox-process/history?limit=3"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.history.length).toBe(3);
      expect(data.total).toBe(10);
    });

    it("should cap limit at 200", async () => {
      const mockHistory = {
        records: Array.from({ length: 250 }, (_, i) => ({
          filename: `file${i}.pdf`,
          destination_bin: "Test",
          routed_at: `2024-01-01T${i}:00:00`,
          confidence: 0.9,
          status: "executed",
        })),
      };
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockHistory));

      const request = new NextRequest(
        "http://localhost/api/inbox-process/history?limit=500"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.history.length).toBe(200);
    });

    it("should transform snake_case to camelCase", async () => {
      const mockHistory = {
        records: [
          {
            filename: "test.pdf",
            destination_bin: "Finances Bin/Taxes",
            routed_at: "2024-03-15T14:30:00",
            confidence: 0.92,
            status: "executed",
            matched_keywords: ["tax"],
          },
        ],
      };
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockHistory));

      const request = new NextRequest(
        "http://localhost/api/inbox-process/history"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.history[0].destinationBin).toBe("Finances Bin/Taxes");
      expect(data.history[0].routedAt).toBe("2024-03-15T14:30:00");
      expect(data.history[0].matchedKeywords).toEqual(["tax"]);
    });

    // =============================================================================
    // Phase 16.4: Explainability Fields Tests
    // =============================================================================

    it("should include explainability fields with LLM classification", async () => {
      const mockHistory = {
        records: [
          {
            filename: "tax_return.pdf",
            destination_bin: "Finances Bin/Taxes",
            routed_at: "2024-03-15T14:30:00",
            confidence: 0.94,
            status: "executed",
            matched_keywords: ["llm:llama3.1:8b-instruct-q8_0"],
            reason: "Content analysis detected IRS form 1040",
            model_used: "llama3.1:8b-instruct-q8_0",
            used_keyword_fallback: false,
          },
        ],
      };
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockHistory));

      const request = new NextRequest(
        "http://localhost/api/inbox-process/history"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.history[0].reason).toBe(
        "Content analysis detected IRS form 1040"
      );
      expect(data.history[0].modelUsed).toBe("llama3.1:8b-instruct-q8_0");
      expect(data.history[0].usedKeywordFallback).toBe(false);
    });

    it("should include explainability fields with keyword fallback", async () => {
      const mockHistory = {
        records: [
          {
            filename: "bank_statement.pdf",
            destination_bin: "Finances Bin/Banking",
            routed_at: "2024-03-15T14:30:00",
            confidence: 0.92,
            status: "executed",
            matched_keywords: ["bank", "statement"],
            reason: "",
            model_used: "",
            used_keyword_fallback: true,
          },
        ],
      };
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockHistory));

      const request = new NextRequest(
        "http://localhost/api/inbox-process/history"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.history[0].reason).toBe("");
      expect(data.history[0].modelUsed).toBe("");
      expect(data.history[0].usedKeywordFallback).toBe(true);
    });

    it("should handle legacy records without explainability fields", async () => {
      // Simulate legacy data that doesn't have the new fields
      const mockHistory = {
        records: [
          {
            filename: "old_file.pdf",
            destination_bin: "Archive",
            routed_at: "2023-01-01T10:00:00",
            confidence: 0.85,
            status: "executed",
            matched_keywords: ["archive"],
            // No reason, model_used, or used_keyword_fallback
          },
        ],
      };
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockHistory));

      const request = new NextRequest(
        "http://localhost/api/inbox-process/history"
      );
      const response = await GET(request);
      const data = await response.json();

      // Should have default values for missing fields
      expect(data.history[0].reason).toBe("");
      expect(data.history[0].modelUsed).toBe("");
      // Legacy records default to true (keyword was the only method before LLM)
      expect(data.history[0].usedKeywordFallback).toBe(true);
    });

    it("should include explainability in multiple records", async () => {
      const mockHistory = {
        records: [
          {
            filename: "llm_classified.pdf",
            destination_bin: "Work Bin/Projects",
            routed_at: "2024-03-15T10:00:00",
            confidence: 0.91,
            status: "executed",
            reason: "Classified as project document based on content",
            model_used: "qwen2.5-coder:14b",
            used_keyword_fallback: false,
          },
          {
            filename: "keyword_matched.pdf",
            destination_bin: "Finances Bin/Invoices",
            routed_at: "2024-03-15T11:00:00",
            confidence: 0.92,
            status: "executed",
            matched_keywords: ["invoice"],
            used_keyword_fallback: true,
          },
          {
            filename: "escalated.pdf",
            destination_bin: "Legal Bin/Contracts",
            routed_at: "2024-03-15T12:00:00",
            confidence: 0.88,
            status: "executed",
            reason: "Escalated from T1 to T2 for complex legal document",
            model_used: "qwen2.5-coder:14b",
            used_keyword_fallback: false,
          },
        ],
      };
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockHistory));

      const request = new NextRequest(
        "http://localhost/api/inbox-process/history"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.history.length).toBe(3);

      // Most recent first (escalated)
      expect(data.history[0].modelUsed).toBe("qwen2.5-coder:14b");
      expect(data.history[0].usedKeywordFallback).toBe(false);

      // Keyword matched
      expect(data.history[1].usedKeywordFallback).toBe(true);
      expect(data.history[1].modelUsed).toBe("");

      // LLM classified
      expect(data.history[2].reason).toBe(
        "Classified as project document based on content"
      );
    });

    it("should handle error gracefully", async () => {
      mockFs.readFile.mockRejectedValue(new Error("Permission denied"));

      const request = new NextRequest(
        "http://localhost/api/inbox-process/history"
      );
      const response = await GET(request);
      const data = await response.json();

      // Should return empty history on error, not crash
      expect(data.success).toBe(true);
      expect(data.history).toEqual([]);
    });
  });
});
