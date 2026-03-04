import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";

// Mock the Supabase client
const mockSupabaseClient = {
  from: vi.fn(),
};

vi.mock("@supabase/supabase-js", () => ({
  createClient: vi.fn(() => mockSupabaseClient),
}));

import { resetSupabaseClient } from "@/lib/supabase";

describe("Orphaned Files Integration API", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetSupabaseClient();
  });

  describe("POST /api/orphaned/analyze - validation tests", () => {
    it("should return 400 if file path is missing", async () => {
      const { POST } = await import("@/app/api/orphaned/analyze/route");

      const request = new NextRequest("http://localhost/api/orphaned/analyze", {
        method: "POST",
        body: JSON.stringify({}),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("File path is required");
    });

    it("should return 400 for relative file path", async () => {
      const { POST } = await import("@/app/api/orphaned/analyze/route");

      const request = new NextRequest("http://localhost/api/orphaned/analyze", {
        method: "POST",
        body: JSON.stringify({ filePath: "relative/path/file.pdf" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Only absolute paths are allowed");
    });

    it("should return 400 for invalid JSON", async () => {
      const { POST } = await import("@/app/api/orphaned/analyze/route");

      const request = new NextRequest("http://localhost/api/orphaned/analyze", {
        method: "POST",
        body: "not valid json",
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain("Invalid JSON");
    });

    it("should return 400 if file path is not a string", async () => {
      const { POST } = await import("@/app/api/orphaned/analyze/route");

      const request = new NextRequest("http://localhost/api/orphaned/analyze", {
        method: "POST",
        body: JSON.stringify({ filePath: 123 }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("File path is required");
    });
  });

  describe("POST /api/orphaned/move - validation tests", () => {
    it("should return 400 if source path is missing", async () => {
      const { POST } = await import("@/app/api/orphaned/move/route");

      const request = new NextRequest("http://localhost/api/orphaned/move", {
        method: "POST",
        body: JSON.stringify({ destinationPath: "/dest/path.pdf" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Source path is required");
    });

    it("should return 400 if destination path is missing", async () => {
      const { POST } = await import("@/app/api/orphaned/move/route");

      const request = new NextRequest("http://localhost/api/orphaned/move", {
        method: "POST",
        body: JSON.stringify({ sourcePath: "/source/path.pdf" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Destination path is required");
    });

    it("should return 400 for relative source path", async () => {
      const { POST } = await import("@/app/api/orphaned/move/route");

      const request = new NextRequest("http://localhost/api/orphaned/move", {
        method: "POST",
        body: JSON.stringify({
          sourcePath: "relative/source.pdf",
          destinationPath: "/dest/path.pdf",
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Source path must be absolute");
    });

    it("should return 400 for relative destination path", async () => {
      const { POST } = await import("@/app/api/orphaned/move/route");

      const request = new NextRequest("http://localhost/api/orphaned/move", {
        method: "POST",
        body: JSON.stringify({
          sourcePath: "/source/path.pdf",
          destinationPath: "relative/dest.pdf",
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Destination path must be absolute");
    });

    it("should return 400 for invalid JSON", async () => {
      const { POST } = await import("@/app/api/orphaned/move/route");

      const request = new NextRequest("http://localhost/api/orphaned/move", {
        method: "POST",
        body: "not valid json",
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain("Invalid JSON");
    });

    it("should return 400 if source path is not a string", async () => {
      const { POST } = await import("@/app/api/orphaned/move/route");

      const request = new NextRequest("http://localhost/api/orphaned/move", {
        method: "POST",
        body: JSON.stringify({
          sourcePath: 123,
          destinationPath: "/dest/path.pdf",
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Source path is required");
    });
  });

  describe("POST /api/missing/restore - validation tests", () => {
    it("should return 400 if document ID is missing", async () => {
      const { POST } = await import("@/app/api/missing/restore/route");

      const request = new NextRequest("http://localhost/api/missing/restore", {
        method: "POST",
        body: JSON.stringify({}),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Document ID is required");
    });

    it("should return 400 for invalid JSON", async () => {
      const { POST } = await import("@/app/api/missing/restore/route");

      const request = new NextRequest("http://localhost/api/missing/restore", {
        method: "POST",
        body: "not valid json",
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain("Invalid JSON");
    });

    it("should return 400 if document ID is not a string", async () => {
      const { POST } = await import("@/app/api/missing/restore/route");

      const request = new NextRequest("http://localhost/api/missing/restore", {
        method: "POST",
        body: JSON.stringify({ documentId: 123 }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Document ID is required");
    });

    it("should return 404 if document not found", async () => {
      mockSupabaseClient.from.mockImplementation(() => ({
        select: () => ({
          eq: () => ({
            single: () => Promise.resolve({ data: null, error: { message: "Not found" } }),
          }),
        }),
      }));

      const { POST } = await import("@/app/api/missing/restore/route");

      const request = new NextRequest("http://localhost/api/missing/restore", {
        method: "POST",
        body: JSON.stringify({ documentId: "nonexistent-id" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.error).toContain("Document not found");
    });

    it("should return 400 for relative custom path", async () => {
      mockSupabaseClient.from.mockImplementation(() => ({
        select: () => ({
          eq: () => ({
            single: () => Promise.resolve({
              data: { id: "doc-id", file_name: "file.pdf", current_path: "/old/path.pdf" },
              error: null,
            }),
          }),
        }),
      }));

      const { POST } = await import("@/app/api/missing/restore/route");

      const request = new NextRequest("http://localhost/api/missing/restore", {
        method: "POST",
        body: JSON.stringify({
          documentId: "doc-id",
          customPath: "relative/path.pdf",
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Custom path must be absolute");
    });

    it("should return 404 if no original path found in location history", async () => {
      mockSupabaseClient.from.mockImplementation((table: string) => {
        if (table === "documents") {
          return {
            select: () => ({
              eq: () => ({
                single: () => Promise.resolve({
                  data: { id: "doc-id", file_name: "file.pdf", current_path: "/old/path.pdf" },
                  error: null,
                }),
              }),
            }),
          };
        }
        if (table === "document_locations") {
          return {
            select: () => ({
              eq: () => ({
                order: () => Promise.resolve({ data: [], error: null }),
              }),
            }),
          };
        }
        return {};
      });

      const { POST } = await import("@/app/api/missing/restore/route");

      const request = new NextRequest("http://localhost/api/missing/restore", {
        method: "POST",
        body: JSON.stringify({ documentId: "doc-id" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.error).toBe("No original path found in location history");
    });
  });
});

// Note: Complex filesystem mocking tests are in separate integration test files
// that run with actual filesystem access. The tests above cover the API validation logic.
