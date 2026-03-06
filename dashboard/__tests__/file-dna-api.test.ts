/**
 * Tests for file-dna API endpoint
 *
 * Tests the GET /api/file-dna endpoint which provides:
 * - Search by keyword, hash, or tag
 * - Provenance information (origin, first_seen_at, routed_to)
 * - Related files detection
 * - Duplicate status
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "../app/api/file-dna/route";
import fs from "fs/promises";
import path from "path";

// Mock the fs module
vi.mock("fs/promises");

const mockDNAEntries = [
  {
    file_path: "/test/documents/tax_2024.pdf",
    sha256_hash: "abc123def456",
    content_summary: "Tax return for year 2024",
    auto_tags: ["tax_doc", "2024", "IRS"],
    origin: "inbox",
    first_seen_at: "2024-01-15T10:30:00.000Z",
    routed_to: "/test/Finances Bin/Taxes/2024/",
    duplicate_of: "",
    model_used: "llama3.1:8b-instruct-q8_0",
  },
  {
    file_path: "/test/documents/tax_2024_copy.pdf",
    sha256_hash: "abc123def456", // Same hash = duplicate
    content_summary: "Tax return for year 2024",
    auto_tags: ["tax_doc", "2024", "IRS"],
    origin: "scan",
    first_seen_at: "2024-01-20T14:00:00.000Z",
    routed_to: "",
    duplicate_of: "/test/documents/tax_2024.pdf",
    model_used: "llama3.1:8b-instruct-q8_0",
  },
  {
    file_path: "/test/documents/resume.pdf",
    sha256_hash: "unique123hash",
    content_summary: "John Doe resume software engineer",
    auto_tags: ["resume", "employment", "software"],
    origin: "import",
    first_seen_at: "2024-02-01T09:00:00.000Z",
    routed_to: "/test/Employment/Resumes/",
    duplicate_of: "",
    model_used: "",
  },
  {
    file_path: "/test/documents/w2_2024.pdf",
    sha256_hash: "w2hash2024",
    content_summary: "W2 form for 2024",
    auto_tags: ["tax_doc", "2024", "w2"],
    origin: "inbox",
    first_seen_at: "2024-01-25T11:00:00.000Z",
    routed_to: "/test/Finances Bin/Taxes/2024/",
    duplicate_of: "",
    model_used: "llama3.1:8b-instruct-q8_0",
  },
  {
    file_path: "/test/documents/verizon_bill.pdf",
    sha256_hash: "verizonhash123",
    content_summary: "Verizon wireless bill March 2024",
    auto_tags: ["bill", "verizon", "2024"],
    origin: "inbox",
    first_seen_at: "2024-03-05T16:00:00.000Z",
    routed_to: "/test/Finances Bin/Bills/",
    duplicate_of: "",
    model_used: "llama3.1:8b-instruct-q8_0",
  },
];

describe("GET /api/file-dna", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe("when DNA registry exists", () => {
    beforeEach(() => {
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({
          version: "1.0",
          updated_at: "2024-03-05T12:00:00.000Z",
          entry_count: mockDNAEntries.length,
          entries: mockDNAEntries,
        })
      );
    });

    it("returns all entries when no search params provided", async () => {
      const request = new NextRequest("http://localhost/api/file-dna");
      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.results.length).toBe(mockDNAEntries.length);
      expect(data.total).toBe(mockDNAEntries.length);
    });

    it("searches by keyword in filename", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=resume"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.results.length).toBe(1);
      expect(data.results[0].filename).toBe("resume.pdf");
    });

    it("searches by keyword in tags", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=tax_doc"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.results.length).toBe(3); // tax_2024, tax_2024_copy, w2_2024
    });

    it("searches by keyword in content_summary", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=verizon"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.results.length).toBe(1);
      expect(data.results[0].filename).toBe("verizon_bill.pdf");
    });

    it("searches by exact hash", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?hash=abc123def456"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.results.length).toBe(2); // Both duplicates
      expect(data.results[0].hash).toBe("abc123def456");
      expect(data.results[1].hash).toBe("abc123def456");
    });

    it("searches by exact tag", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?tag=verizon"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.results.length).toBe(1);
      expect(data.results[0].tags).toContain("verizon");
    });

    it("returns empty results for non-matching search", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=nonexistent"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.results.length).toBe(0);
      expect(data.total).toBe(0);
    });
  });

  describe("provenance information", () => {
    beforeEach(() => {
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({
          version: "1.0",
          entries: mockDNAEntries,
        })
      );
    });

    it("includes origin in provenance", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=tax_2024.pdf"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results[0].provenance.origin).toBe("inbox");
    });

    it("includes first_seen_at in provenance", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=tax_2024.pdf"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results[0].provenance.first_seen_at).toBe(
        "2024-01-15T10:30:00.000Z"
      );
    });

    it("includes routed_to in provenance", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=tax_2024.pdf"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results[0].provenance.routed_to).toBe(
        "/test/Finances Bin/Taxes/2024/"
      );
    });

    it("includes model_used in provenance", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=tax_2024.pdf"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results[0].provenance.model_used).toBe(
        "llama3.1:8b-instruct-q8_0"
      );
    });

    it("handles empty provenance fields", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=resume"
      );
      const response = await GET(request);
      const data = await response.json();

      // Resume has empty model_used
      expect(data.results[0].provenance.model_used).toBe("");
    });
  });

  describe("related files detection", () => {
    beforeEach(() => {
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({
          version: "1.0",
          entries: mockDNAEntries,
        })
      );
    });

    it("finds related files with overlapping tags", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=tax_2024.pdf"
      );
      const response = await GET(request);
      const data = await response.json();

      // tax_2024.pdf should have w2_2024.pdf as related (both have tax_doc and 2024)
      expect(data.results[0].related_files.length).toBeGreaterThan(0);
      // Should include either w2_2024.pdf or tax_2024_copy.pdf as related
      const relatedPaths = data.results[0].related_files;
      expect(
        relatedPaths.some(
          (p: string) =>
            p.includes("w2_2024.pdf") || p.includes("tax_2024_copy.pdf")
        )
      ).toBe(true);
    });

    it("limits related files to 5", async () => {
      // Create entries with many tag overlaps
      const manyEntries = [];
      for (let i = 0; i < 10; i++) {
        manyEntries.push({
          file_path: `/test/doc_${i}.pdf`,
          sha256_hash: `hash${i}`,
          auto_tags: ["common_tag1", "common_tag2", `unique_${i}`],
          origin: "scan",
        });
      }

      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({ entries: manyEntries })
      );

      const request = new NextRequest(
        "http://localhost/api/file-dna?search=doc_0"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results[0].related_files.length).toBeLessThanOrEqual(5);
    });

    it("returns empty related_files when no overlap", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=resume"
      );
      const response = await GET(request);
      const data = await response.json();

      // Resume has unique tags, no 2+ tag overlap with others
      expect(data.results[0].related_files.length).toBe(0);
    });
  });

  describe("duplicate status", () => {
    beforeEach(() => {
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({
          version: "1.0",
          entries: mockDNAEntries,
        })
      );
    });

    it("detects when file is marked as duplicate", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=tax_2024_copy"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results[0].duplicate_status.is_duplicate).toBe(true);
      expect(data.results[0].duplicate_status.duplicate_of).toBe(
        "/test/documents/tax_2024.pdf"
      );
    });

    it("detects when file has duplicates", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=tax_2024.pdf"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results[0].duplicate_status.has_duplicates).toBe(true);
      expect(data.results[0].duplicate_status.duplicate_paths).toContain(
        "/test/documents/tax_2024_copy.pdf"
      );
    });

    it("returns empty duplicate info for unique files", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=resume"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results[0].duplicate_status.is_duplicate).toBe(false);
      expect(data.results[0].duplicate_status.duplicate_of).toBeNull();
      expect(data.results[0].duplicate_status.has_duplicates).toBe(false);
      expect(data.results[0].duplicate_status.duplicate_paths).toHaveLength(0);
    });
  });

  describe("when DNA registry does not exist", () => {
    it("returns empty results", async () => {
      vi.mocked(fs.readFile).mockRejectedValue(
        new Error("ENOENT: no such file or directory")
      );

      const request = new NextRequest("http://localhost/api/file-dna");
      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.results).toEqual([]);
      expect(data.total).toBe(0);
    });
  });

  describe("error handling", () => {
    it("handles invalid JSON in registry file", async () => {
      vi.mocked(fs.readFile).mockResolvedValue("invalid json{");

      const request = new NextRequest("http://localhost/api/file-dna");
      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.results).toEqual([]);
    });

    it("handles missing entries array in registry", async () => {
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({ version: "1.0" })
      );

      const request = new NextRequest("http://localhost/api/file-dna");
      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.results).toEqual([]);
      expect(data.total).toBe(0);
    });
  });

  describe("result format", () => {
    beforeEach(() => {
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({
          version: "1.0",
          entries: mockDNAEntries,
        })
      );
    });

    it("extracts filename from path", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=tax_2024.pdf"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results[0].filename).toBe("tax_2024.pdf");
    });

    it("includes full path", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=tax_2024.pdf"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results[0].path).toBe("/test/documents/tax_2024.pdf");
    });

    it("includes tags array", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=tax_2024.pdf"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results[0].tags).toEqual(["tax_doc", "2024", "IRS"]);
    });

    it("includes hash", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=tax_2024.pdf"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results[0].hash).toBe("abc123def456");
    });

    it("limits results to 50", async () => {
      // Create 100 entries
      const manyEntries = [];
      for (let i = 0; i < 100; i++) {
        manyEntries.push({
          file_path: `/test/doc_${i}.pdf`,
          sha256_hash: `hash${i}`,
          auto_tags: ["common"],
          origin: "scan",
        });
      }

      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({ entries: manyEntries })
      );

      const request = new NextRequest(
        "http://localhost/api/file-dna?search=doc"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results.length).toBe(50);
      expect(data.total).toBe(100);
    });
  });

  describe("case-insensitive search", () => {
    beforeEach(() => {
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({
          version: "1.0",
          entries: mockDNAEntries,
        })
      );
    });

    it("searches case-insensitively in filename", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=RESUME"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results.length).toBe(1);
      expect(data.results[0].filename).toBe("resume.pdf");
    });

    it("searches case-insensitively in tags", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?search=TAX_DOC"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results.length).toBe(3);
    });

    it("matches tag case-insensitively", async () => {
      const request = new NextRequest(
        "http://localhost/api/file-dna?tag=VERIZON"
      );
      const response = await GET(request);
      const data = await response.json();

      expect(data.results.length).toBe(1);
    });
  });
});
