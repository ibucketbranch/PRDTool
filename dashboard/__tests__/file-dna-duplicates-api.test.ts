/**
 * Tests for file-dna/duplicates API endpoint
 *
 * Tests the GET /api/file-dna/duplicates endpoint which provides:
 * - Duplicate groups (files with same SHA-256 hash)
 * - File count per group
 * - Wasted bytes calculation
 * - Total duplicates count
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { GET } from "../app/api/file-dna/duplicates/route";
import fs from "fs/promises";

// Mock the fs module
vi.mock("fs/promises");

const mockDNAEntries = [
  {
    file_path: "/test/documents/tax_2024.pdf",
    sha256_hash: "abc123def456",
  },
  {
    file_path: "/test/documents/tax_2024_copy.pdf",
    sha256_hash: "abc123def456", // Same hash = duplicate
  },
  {
    file_path: "/test/documents/resume.pdf",
    sha256_hash: "unique123hash",
  },
  {
    file_path: "/test/documents/w2_2024.pdf",
    sha256_hash: "w2hash2024",
  },
  {
    file_path: "/test/documents/photo1.jpg",
    sha256_hash: "photohash123",
  },
  {
    file_path: "/test/documents/photo1_backup.jpg",
    sha256_hash: "photohash123", // Same hash = duplicate
  },
  {
    file_path: "/test/documents/photo1_another.jpg",
    sha256_hash: "photohash123", // Same hash = duplicate (3 total)
  },
];

describe("GET /api/file-dna/duplicates", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe("when DNA registry exists with duplicates", () => {
    beforeEach(() => {
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({
          version: "1.0",
          updated_at: "2024-03-05T12:00:00.000Z",
          entry_count: mockDNAEntries.length,
          entries: mockDNAEntries,
        })
      );
      // Mock fs.stat for file sizes
      vi.mocked(fs.stat).mockResolvedValue({ size: 1024 } as fs.Stats);
    });

    it("returns success true", async () => {
      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
    });

    it("returns duplicate groups", async () => {
      const response = await GET();
      const data = await response.json();

      expect(data.groups).toBeDefined();
      expect(Array.isArray(data.groups)).toBe(true);
      expect(data.groups.length).toBe(2); // abc123def456 and photohash123
    });

    it("includes correct hash in each group", async () => {
      const response = await GET();
      const data = await response.json();

      const hashes = data.groups.map((g: { hash: string }) => g.hash);
      expect(hashes).toContain("abc123def456");
      expect(hashes).toContain("photohash123");
    });

    it("includes correct file paths in each group", async () => {
      const response = await GET();
      const data = await response.json();

      const taxGroup = data.groups.find(
        (g: { hash: string }) => g.hash === "abc123def456"
      );
      expect(taxGroup.files).toContain("/test/documents/tax_2024.pdf");
      expect(taxGroup.files).toContain("/test/documents/tax_2024_copy.pdf");
    });

    it("includes correct count per group", async () => {
      const response = await GET();
      const data = await response.json();

      const taxGroup = data.groups.find(
        (g: { hash: string }) => g.hash === "abc123def456"
      );
      expect(taxGroup.count).toBe(2);

      const photoGroup = data.groups.find(
        (g: { hash: string }) => g.hash === "photohash123"
      );
      expect(photoGroup.count).toBe(3);
    });

    it("calculates total duplicates correctly", async () => {
      const response = await GET();
      const data = await response.json();

      // Group 1: 2 files (1 duplicate), Group 2: 3 files (2 duplicates) = 3 total
      expect(data.totalDuplicates).toBe(3);
    });

    it("calculates wasted bytes", async () => {
      const response = await GET();
      const data = await response.json();

      // Each duplicate file is 1024 bytes, 3 duplicates = 3072 bytes
      expect(data.wastedBytes).toBe(3072);
    });

    it("excludes unique files from groups", async () => {
      const response = await GET();
      const data = await response.json();

      const hashes = data.groups.map((g: { hash: string }) => g.hash);
      expect(hashes).not.toContain("unique123hash");
      expect(hashes).not.toContain("w2hash2024");
    });
  });

  describe("when DNA registry exists with no duplicates", () => {
    beforeEach(() => {
      const uniqueEntries = [
        { file_path: "/test/file1.pdf", sha256_hash: "hash1" },
        { file_path: "/test/file2.pdf", sha256_hash: "hash2" },
        { file_path: "/test/file3.pdf", sha256_hash: "hash3" },
      ];
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({ entries: uniqueEntries })
      );
    });

    it("returns empty groups array", async () => {
      const response = await GET();
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.groups).toEqual([]);
    });

    it("returns zero totalDuplicates", async () => {
      const response = await GET();
      const data = await response.json();

      expect(data.totalDuplicates).toBe(0);
    });

    it("returns zero wastedBytes", async () => {
      const response = await GET();
      const data = await response.json();

      expect(data.wastedBytes).toBe(0);
    });
  });

  describe("when DNA registry does not exist", () => {
    beforeEach(() => {
      vi.mocked(fs.readFile).mockRejectedValue(
        new Error("ENOENT: no such file or directory")
      );
    });

    it("returns success true", async () => {
      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
    });

    it("returns empty groups", async () => {
      const response = await GET();
      const data = await response.json();

      expect(data.groups).toEqual([]);
    });

    it("returns zero totalDuplicates", async () => {
      const response = await GET();
      const data = await response.json();

      expect(data.totalDuplicates).toBe(0);
    });

    it("returns zero wastedBytes", async () => {
      const response = await GET();
      const data = await response.json();

      expect(data.wastedBytes).toBe(0);
    });
  });

  describe("when entries have no hash", () => {
    beforeEach(() => {
      const entriesWithMissingHash = [
        { file_path: "/test/file1.pdf", sha256_hash: "hash1" },
        { file_path: "/test/file2.pdf" }, // No hash
        { file_path: "/test/file3.pdf", sha256_hash: "" }, // Empty hash
        { file_path: "/test/file4.pdf", sha256_hash: "hash1" }, // Duplicate
      ];
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({ entries: entriesWithMissingHash })
      );
      vi.mocked(fs.stat).mockResolvedValue({ size: 512 } as fs.Stats);
    });

    it("skips entries without hash", async () => {
      const response = await GET();
      const data = await response.json();

      expect(data.groups.length).toBe(1);
      expect(data.groups[0].count).toBe(2);
    });
  });

  describe("when fs.stat fails for some files", () => {
    beforeEach(() => {
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({
          entries: [
            { file_path: "/test/file1.pdf", sha256_hash: "samehash" },
            { file_path: "/test/file2.pdf", sha256_hash: "samehash" },
          ],
        })
      );
      vi.mocked(fs.stat).mockRejectedValue(
        new Error("ENOENT: file not found")
      );
    });

    it("handles stat errors gracefully", async () => {
      const response = await GET();
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.groups.length).toBe(1);
      // wastedBytes should be 0 since stat failed
      expect(data.wastedBytes).toBe(0);
    });
  });

  describe("error handling", () => {
    it("handles invalid JSON in registry file", async () => {
      vi.mocked(fs.readFile).mockResolvedValue("invalid json{");

      const response = await GET();
      const data = await response.json();

      // Should return empty results rather than error
      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.groups).toEqual([]);
    });

    it("handles missing entries array in registry", async () => {
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({ version: "1.0" })
      );

      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.groups).toEqual([]);
    });
  });

  describe("response format", () => {
    beforeEach(() => {
      vi.mocked(fs.readFile).mockResolvedValue(
        JSON.stringify({
          entries: [
            { file_path: "/test/a.pdf", sha256_hash: "hash1" },
            { file_path: "/test/b.pdf", sha256_hash: "hash1" },
          ],
        })
      );
      vi.mocked(fs.stat).mockResolvedValue({ size: 2048 } as fs.Stats);
    });

    it("includes all expected fields in response", async () => {
      const response = await GET();
      const data = await response.json();

      expect(data).toHaveProperty("success");
      expect(data).toHaveProperty("groups");
      expect(data).toHaveProperty("totalDuplicates");
      expect(data).toHaveProperty("wastedBytes");
    });

    it("groups have correct structure", async () => {
      const response = await GET();
      const data = await response.json();

      const group = data.groups[0];
      expect(group).toHaveProperty("hash");
      expect(group).toHaveProperty("files");
      expect(group).toHaveProperty("count");
      expect(Array.isArray(group.files)).toBe(true);
    });
  });
});
