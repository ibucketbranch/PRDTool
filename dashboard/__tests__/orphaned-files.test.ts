import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";
import {
  getMissingFiles,
  getOriginalLocation,
  checkFileInDatabase,
  updateDocumentPath,
  removeDocumentFromDatabase,
  markDocumentInaccessible,
  suggestLocationForFile,
  resetSupabaseClient,
  FILE_TYPE_LOCATION_PATTERNS,
  FILENAME_CATEGORY_PATTERNS,
  detectCategoryFromFilename,
  findSimilarFilesByPattern,
  suggestLocationForFileEnhanced,
  suggestLocationsForFiles,
  type MissingFileInfo,
  type OrphanedFileInfo,
  type LocationSuggestion,
  type EnhancedLocationSuggestion,
} from "@/lib/supabase";

// Mock the Supabase client
const mockSupabaseClient = {
  from: vi.fn(),
};

vi.mock("@supabase/supabase-js", () => ({
  createClient: vi.fn(() => mockSupabaseClient),
}));

describe("Orphaned Files Supabase Functions", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetSupabaseClient();
  });

  describe("FILE_TYPE_LOCATION_PATTERNS", () => {
    it("should have patterns for common file types", () => {
      expect(FILE_TYPE_LOCATION_PATTERNS[".pdf"]).toEqual({
        folder: "Documents",
        reason: "PDF document",
      });
      expect(FILE_TYPE_LOCATION_PATTERNS[".plist"]).toEqual({
        folder: "Library/Preferences",
        reason: "Apple preference list file",
      });
      expect(FILE_TYPE_LOCATION_PATTERNS[".jpg"]).toEqual({
        folder: "Pictures",
        reason: "JPEG image",
      });
      expect(FILE_TYPE_LOCATION_PATTERNS[".mp4"]).toEqual({
        folder: "Movies",
        reason: "MP4 video",
      });
    });

    it("should have patterns for document types", () => {
      expect(FILE_TYPE_LOCATION_PATTERNS[".doc"]).toBeDefined();
      expect(FILE_TYPE_LOCATION_PATTERNS[".docx"]).toBeDefined();
      expect(FILE_TYPE_LOCATION_PATTERNS[".txt"]).toBeDefined();
      expect(FILE_TYPE_LOCATION_PATTERNS[".xls"]).toBeDefined();
      expect(FILE_TYPE_LOCATION_PATTERNS[".xlsx"]).toBeDefined();
    });
  });

  describe("suggestLocationForFile", () => {
    it("should suggest location based on file extension", () => {
      const result = suggestLocationForFile("/test/file.pdf");

      expect(result.suggestedPath).toBe("Documents");
      expect(result.matchType).toBe("file_type");
      expect(result.confidence).toBe(0.7);
    });

    it("should suggest Library/Preferences for .plist files", () => {
      const result = suggestLocationForFile("/test/com.apple.app.plist");

      expect(result.suggestedPath).toBe("Library/Preferences");
      expect(result.reason).toContain("Apple preference list file");
      expect(result.matchType).toBe("file_type");
    });

    it("should use basePath when provided", () => {
      const result = suggestLocationForFile("/test/file.pdf", "/Users/test");

      expect(result.suggestedPath).toBe("/Users/test/Documents");
    });

    it("should suggest Resumes folder for resume files", () => {
      const result = suggestLocationForFile("/test/my_resume.doc");

      expect(result.suggestedPath).toBe("Documents/Resumes");
      expect(result.matchType).toBe("filename_pattern");
      expect(result.confidence).toBe(0.8);
    });

    it("should suggest Taxes folder for tax files", () => {
      const result = suggestLocationForFile("/test/tax_return_2024.pdf");

      expect(result.suggestedPath).toBe("Documents/Taxes");
      expect(result.matchType).toBe("filename_pattern");
    });

    it("should suggest Bills folder for invoice files", () => {
      const result = suggestLocationForFile("/test/invoice_12345.pdf");

      expect(result.suggestedPath).toBe("Documents/Bills");
      expect(result.matchType).toBe("filename_pattern");
    });

    it("should suggest Contracts folder for contract files", () => {
      const result = suggestLocationForFile("/test/rental_agreement.pdf");

      expect(result.suggestedPath).toBe("Documents/Contracts");
      expect(result.matchType).toBe("filename_pattern");
    });

    it("should suggest Medical folder for medical files", () => {
      const result = suggestLocationForFile("/test/prescription.pdf");

      expect(result.suggestedPath).toBe("Documents/Medical");
      expect(result.matchType).toBe("filename_pattern");
    });

    it("should return default Documents for unknown files", () => {
      const result = suggestLocationForFile("/test/random_file.xyz");

      expect(result.suggestedPath).toBe("Documents");
      expect(result.confidence).toBe(0.3);
    });

    it("should handle files without extension", () => {
      const result = suggestLocationForFile("/test/noextension");

      expect(result.suggestedPath).toBe("Documents");
      expect(result.confidence).toBe(0.3);
    });
  });

  describe("getMissingFiles", () => {
    const mockDocuments = [
      { id: "doc1", file_name: "file1.pdf", current_path: "/path/file1.pdf", ai_category: "tax_document" },
      { id: "doc2", file_name: "file2.pdf", current_path: "/path/file2.pdf", ai_category: "employment" },
    ];

    const mockLocations = [
      { document_id: "doc1", path: "/original/file1.pdf", location_type: "primary", is_accessible: true, created_at: "2024-01-15T10:00:00Z" },
      { document_id: "doc2", path: "/old/file2.pdf", location_type: "previous", is_accessible: false, created_at: "2024-01-10T10:00:00Z" },
    ];

    it("should return all documents with their location info", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const inMock = vi.fn().mockResolvedValue({
        data: mockLocations,
        error: null,
      });

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return {
            select: vi.fn().mockResolvedValue({
              data: mockDocuments,
              error: null,
              count: mockDocuments.length,
            }),
          };
        }
        return { select: selectMock, in: inMock };
      });

      const result = await getMissingFiles();

      expect(result.missingFiles.length).toBe(2);
      expect(result.totalMissingFiles).toBe(2);
      expect(result.totalDocuments).toBe(2);
      expect(result.error).toBeUndefined();
    });

    it("should return empty array when no documents exist", async () => {
      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: [],
          error: null,
          count: 0,
        }),
      });

      const result = await getMissingFiles();

      expect(result.missingFiles).toEqual([]);
      expect(result.totalMissingFiles).toBe(0);
    });

    it("should handle database error for documents query", async () => {
      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: null,
          error: { message: "Database error" },
          count: 0,
        }),
      });

      const result = await getMissingFiles();

      expect(result.missingFiles).toEqual([]);
      expect(result.error).toBe("Database error");
    });

    it("should handle documents with embedded locations (optimized query)", async () => {
      // The optimized getMissingFiles uses a single query with embedded relation
      // so there's no separate "locations query" to fail
      const mockDocsWithLocations = [
        {
          id: "doc1",
          file_name: "file1.pdf",
          current_path: "/path/file1.pdf",
          ai_category: "tax",
          document_locations: [
            { path: "/original/file1.pdf", location_type: "primary", is_accessible: true, created_at: "2024-01-15T10:00:00Z" },
          ],
        },
      ];

      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: mockDocsWithLocations,
          error: null,
          count: 1,
        }),
      });

      const result = await getMissingFiles();

      expect(result.missingFiles.length).toBe(1);
      expect(result.error).toBeUndefined();
    });

    it("should populate originalPath and lastKnownLocation correctly", async () => {
      // Optimized: Single query with embedded document_locations
      const mockDocsWithLocations = [
        {
          id: "doc1",
          file_name: "file1.pdf",
          current_path: "/path/file1.pdf",
          ai_category: "tax",
          document_locations: [
            { path: "/original/file1.pdf", location_type: "primary", is_accessible: true, created_at: "2024-01-15T10:00:00Z" },
          ],
        },
        {
          id: "doc2",
          file_name: "file2.pdf",
          current_path: "/path/file2.pdf",
          ai_category: "invoice",
          document_locations: [
            { path: "/old/file2.pdf", location_type: "previous", is_accessible: false, created_at: "2024-01-14T10:00:00Z" },
          ],
        },
      ];

      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: mockDocsWithLocations,
          error: null,
          count: 2,
        }),
      });

      const result = await getMissingFiles();

      const doc1 = result.missingFiles.find((f) => f.documentId === "doc1");
      expect(doc1?.originalPath).toBe("/original/file1.pdf");
      expect(doc1?.lastKnownLocation).toBe("/original/file1.pdf");

      const doc2 = result.missingFiles.find((f) => f.documentId === "doc2");
      expect(doc2?.originalPath).toBe("/old/file2.pdf");
    });

    it("should handle exceptions gracefully", async () => {
      mockSupabaseClient.from.mockImplementation(() => {
        throw new Error("Connection failed");
      });

      const result = await getMissingFiles();

      expect(result.missingFiles).toEqual([]);
      expect(result.error).toBe("Connection failed");
    });
  });

  describe("getOriginalLocation", () => {
    it("should return original path from primary location", async () => {
      const mockLocations = [
        { path: "/current/file.pdf", location_type: "current", is_accessible: true, created_at: "2024-01-16T10:00:00Z" },
        { path: "/original/file.pdf", location_type: "primary", is_accessible: false, created_at: "2024-01-15T10:00:00Z" },
      ];

      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const orderMock = vi.fn().mockResolvedValue({
        data: mockLocations,
        error: null,
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        order: orderMock,
      });

      const result = await getOriginalLocation("doc1");

      expect(result.documentId).toBe("doc1");
      expect(result.originalPath).toBe("/original/file.pdf");
      expect(result.locationHistory.length).toBe(2);
      expect(result.error).toBeUndefined();
    });

    it("should use oldest previous location when no primary exists", async () => {
      const mockLocations = [
        { path: "/newer/file.pdf", location_type: "previous", is_accessible: false, created_at: "2024-01-16T10:00:00Z" },
        { path: "/oldest/file.pdf", location_type: "previous", is_accessible: false, created_at: "2024-01-10T10:00:00Z" },
      ];

      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const orderMock = vi.fn().mockResolvedValue({
        data: mockLocations,
        error: null,
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        order: orderMock,
      });

      const result = await getOriginalLocation("doc1");

      expect(result.originalPath).toBe("/oldest/file.pdf");
    });

    it("should return null when no locations exist", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const orderMock = vi.fn().mockResolvedValue({
        data: [],
        error: null,
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        order: orderMock,
      });

      const result = await getOriginalLocation("doc1");

      expect(result.originalPath).toBeNull();
      expect(result.locationHistory).toEqual([]);
    });

    it("should handle database error", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const orderMock = vi.fn().mockResolvedValue({
        data: null,
        error: { message: "Query failed" },
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        order: orderMock,
      });

      const result = await getOriginalLocation("doc1");

      expect(result.originalPath).toBeNull();
      expect(result.error).toBe("Query failed");
    });
  });

  describe("checkFileInDatabase", () => {
    it("should return exists=true when file is in documents table", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const limitMock = vi.fn().mockResolvedValue({
        data: [{ id: "doc1" }],
        error: null,
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        limit: limitMock,
      });

      const result = await checkFileInDatabase("/path/to/file.pdf");

      expect(result.exists).toBe(true);
      expect(result.documentId).toBe("doc1");
      expect(result.error).toBeUndefined();
    });

    it("should check document_locations when not found in documents", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const limitMock = vi.fn();

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          // First call: documents table - not found
          limitMock.mockResolvedValueOnce({
            data: [],
            error: null,
          });
        } else {
          // Second call: document_locations - found
          limitMock.mockResolvedValueOnce({
            data: [{ document_id: "doc2" }],
            error: null,
          });
        }
        return { select: selectMock, eq: eqMock, limit: limitMock };
      });

      const result = await checkFileInDatabase("/path/to/file.pdf");

      expect(result.exists).toBe(true);
      expect(result.documentId).toBe("doc2");
    });

    it("should return exists=false when file is not found anywhere", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const limitMock = vi.fn().mockResolvedValue({
        data: [],
        error: null,
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        limit: limitMock,
      });

      const result = await checkFileInDatabase("/nonexistent/file.pdf");

      expect(result.exists).toBe(false);
      expect(result.documentId).toBeNull();
    });

    it("should handle database error", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const limitMock = vi.fn().mockResolvedValue({
        data: null,
        error: { message: "Database error" },
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        limit: limitMock,
      });

      const result = await checkFileInDatabase("/path/to/file.pdf");

      expect(result.exists).toBe(false);
      expect(result.error).toBe("Database error");
    });
  });

  describe("updateDocumentPath", () => {
    it("should update document path and add to history", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const singleMock = vi.fn().mockResolvedValue({
        data: { current_path: "/old/path.pdf" },
        error: null,
      });
      const updateMock = vi.fn().mockReturnThis();
      const insertMock = vi.fn().mockResolvedValue({ error: null });

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          // Get current document
          return { select: selectMock, eq: eqMock, single: singleMock };
        } else if (callCount === 2) {
          // Update documents table
          return { update: updateMock, eq: vi.fn().mockResolvedValue({ error: null }) };
        } else {
          // Insert location history
          return { insert: insertMock };
        }
      });

      const result = await updateDocumentPath("doc1", "/new/path.pdf");

      expect(result.success).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it("should not add history when addToLocationHistory is false", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const singleMock = vi.fn().mockResolvedValue({
        data: { current_path: "/old/path.pdf" },
        error: null,
      });
      const updateMock = vi.fn().mockReturnThis();

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return { select: selectMock, eq: eqMock, single: singleMock };
        } else {
          return { update: updateMock, eq: vi.fn().mockResolvedValue({ error: null }) };
        }
      });

      const result = await updateDocumentPath("doc1", "/new/path.pdf", false);

      expect(result.success).toBe(true);
      // Should only have 2 calls (get + update), no insert calls
      expect(callCount).toBe(2);
    });

    it("should handle get document error", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const singleMock = vi.fn().mockResolvedValue({
        data: null,
        error: { message: "Document not found" },
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        single: singleMock,
      });

      const result = await updateDocumentPath("doc1", "/new/path.pdf");

      expect(result.success).toBe(false);
      expect(result.error).toBe("Document not found");
    });

    it("should handle update error", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const singleMock = vi.fn().mockResolvedValue({
        data: { current_path: "/old/path.pdf" },
        error: null,
      });
      const updateMock = vi.fn().mockReturnThis();

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return { select: selectMock, eq: eqMock, single: singleMock };
        } else {
          return { update: updateMock, eq: vi.fn().mockResolvedValue({ error: { message: "Update failed" } }) };
        }
      });

      const result = await updateDocumentPath("doc1", "/new/path.pdf");

      expect(result.success).toBe(false);
      expect(result.error).toBe("Update failed");
    });
  });

  describe("removeDocumentFromDatabase", () => {
    it("should delete document and its locations", async () => {
      const deleteMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({ error: null });

      mockSupabaseClient.from.mockReturnValue({
        delete: deleteMock,
        eq: eqMock,
      });

      const result = await removeDocumentFromDatabase("doc1");

      expect(result.success).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it("should handle location deletion error", async () => {
      const deleteMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({ error: { message: "Delete locations failed" } });

      mockSupabaseClient.from.mockReturnValue({
        delete: deleteMock,
        eq: eqMock,
      });

      const result = await removeDocumentFromDatabase("doc1");

      expect(result.success).toBe(false);
      expect(result.error).toContain("Failed to delete locations");
    });

    it("should handle document deletion error", async () => {
      const deleteMock = vi.fn().mockReturnThis();
      let callCount = 0;
      const eqMock = vi.fn().mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve({ error: null });
        } else {
          return Promise.resolve({ error: { message: "Delete document failed" } });
        }
      });

      mockSupabaseClient.from.mockReturnValue({
        delete: deleteMock,
        eq: eqMock,
      });

      const result = await removeDocumentFromDatabase("doc1");

      expect(result.success).toBe(false);
      expect(result.error).toContain("Failed to delete document");
    });
  });

  describe("markDocumentInaccessible", () => {
    it("should update is_accessible flag", async () => {
      const updateMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({ error: null });

      mockSupabaseClient.from.mockReturnValue({
        update: updateMock,
        eq: eqMock,
      });

      const result = await markDocumentInaccessible("doc1");

      expect(result.success).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it("should handle database error", async () => {
      const updateMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({ error: { message: "Update failed" } });

      mockSupabaseClient.from.mockReturnValue({
        update: updateMock,
        eq: eqMock,
      });

      const result = await markDocumentInaccessible("doc1");

      expect(result.success).toBe(false);
      expect(result.error).toBe("Update failed");
    });
  });
});

describe("Orphaned Files API Endpoint", () => {
  let GET: typeof import("@/app/api/orphaned/route").GET;
  let POST: typeof import("@/app/api/orphaned/route").POST;

  beforeEach(async () => {
    resetSupabaseClient();
    vi.clearAllMocks();

    const module = await import("@/app/api/orphaned/route");
    GET = module.GET;
    POST = module.POST;
  });

  afterEach(() => {
    resetSupabaseClient();
  });

  describe("GET /api/orphaned", () => {
    it("should return error when directory parameter is missing", async () => {
      const request = new NextRequest("http://localhost/api/orphaned", {
        method: "GET",
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Directory parameter is required");
    });

    it("should return error for relative paths", async () => {
      const request = new NextRequest(
        "http://localhost/api/orphaned?directory=relative/path",
        { method: "GET" }
      );

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Only absolute paths are allowed");
    });

    it("should return error for nonexistent directory", async () => {
      const request = new NextRequest(
        "http://localhost/api/orphaned?directory=/nonexistent/path/that/does/not/exist",
        { method: "GET" }
      );

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.error).toBe("Directory does not exist");
    });
  });

  describe("POST /api/orphaned (suggest location)", () => {
    it("should return error when filePath is missing", async () => {
      const request = new NextRequest("http://localhost/api/orphaned", {
        method: "POST",
        body: JSON.stringify({}),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("File path is required");
    });

    it("should return error for relative paths", async () => {
      const request = new NextRequest("http://localhost/api/orphaned", {
        method: "POST",
        body: JSON.stringify({ filePath: "relative/path.pdf" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Only absolute paths are allowed");
    });

    it("should return suggestion for valid file path", async () => {
      const request = new NextRequest("http://localhost/api/orphaned", {
        method: "POST",
        body: JSON.stringify({ filePath: "/test/my_resume.pdf" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.suggestedPath).toBeDefined();
      expect(data.reason).toBeDefined();
      expect(data.confidence).toBeGreaterThan(0);
    });

    it("should use basePath when provided", async () => {
      const request = new NextRequest("http://localhost/api/orphaned", {
        method: "POST",
        body: JSON.stringify({ filePath: "/test/file.pdf", basePath: "/Users/test" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.suggestedPath).toContain("/Users/test");
    });

    it("should handle invalid JSON body", async () => {
      const request = new NextRequest("http://localhost/api/orphaned", {
        method: "POST",
        body: "invalid json",
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Invalid JSON in request body");
    });
  });
});

describe("Missing Files API Endpoint", () => {
  let GET: typeof import("@/app/api/missing/route").GET;
  let POST: typeof import("@/app/api/missing/route").POST;

  beforeEach(async () => {
    resetSupabaseClient();
    vi.clearAllMocks();

    const module = await import("@/app/api/missing/route");
    GET = module.GET;
    POST = module.POST;
  });

  afterEach(() => {
    resetSupabaseClient();
  });

  describe("GET /api/missing", () => {
    it("should return missing files from database", async () => {
      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: [],
          error: null,
          count: 0,
        }),
      });

      const request = new NextRequest("http://localhost/api/missing", {
        method: "GET",
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.missingFiles).toBeDefined();
      expect(data.totalDocuments).toBeDefined();
    });

    it("should return 500 on database error", async () => {
      mockSupabaseClient.from.mockReturnValue({
        select: vi.fn().mockResolvedValue({
          data: null,
          error: { message: "Database error" },
          count: 0,
        }),
      });

      const request = new NextRequest("http://localhost/api/missing", {
        method: "GET",
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(500);
      expect(data.error).toBe("Database error");
    });
  });

  describe("POST /api/missing", () => {
    it("should return error when action is missing", async () => {
      const request = new NextRequest("http://localhost/api/missing", {
        method: "POST",
        body: JSON.stringify({ documentId: "doc1" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain("Action is required");
    });

    it("should return error when documentId is missing", async () => {
      const request = new NextRequest("http://localhost/api/missing", {
        method: "POST",
        body: JSON.stringify({ action: "get-original" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Document ID is required");
    });

    it("should return error for unknown action", async () => {
      const request = new NextRequest("http://localhost/api/missing", {
        method: "POST",
        body: JSON.stringify({ action: "invalid-action", documentId: "doc1" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain("Unknown action");
    });

    describe("action=get-original", () => {
      it("should return original location", async () => {
        const mockLocations = [
          { path: "/original/file.pdf", location_type: "primary", is_accessible: false, created_at: "2024-01-15T10:00:00Z" },
        ];

        const selectMock = vi.fn().mockReturnThis();
        const eqMock = vi.fn().mockReturnThis();
        const orderMock = vi.fn().mockResolvedValue({
          data: mockLocations,
          error: null,
        });

        mockSupabaseClient.from.mockReturnValue({
          select: selectMock,
          eq: eqMock,
          order: orderMock,
        });

        const request = new NextRequest("http://localhost/api/missing", {
          method: "POST",
          body: JSON.stringify({ action: "get-original", documentId: "doc1" }),
        });

        const response = await POST(request);
        const data = await response.json();

        expect(response.status).toBe(200);
        expect(data.originalPath).toBe("/original/file.pdf");
        expect(data.locationHistory.length).toBe(1);
      });
    });

    describe("action=update-path", () => {
      it("should return error when newPath is missing", async () => {
        const request = new NextRequest("http://localhost/api/missing", {
          method: "POST",
          body: JSON.stringify({ action: "update-path", documentId: "doc1" }),
        });

        const response = await POST(request);
        const data = await response.json();

        expect(response.status).toBe(400);
        expect(data.error).toBe("New path is required for update-path action");
      });

      it("should return error for relative newPath", async () => {
        const request = new NextRequest("http://localhost/api/missing", {
          method: "POST",
          body: JSON.stringify({
            action: "update-path",
            documentId: "doc1",
            newPath: "relative/path.pdf",
          }),
        });

        const response = await POST(request);
        const data = await response.json();

        expect(response.status).toBe(400);
        expect(data.error).toBe("Only absolute paths are allowed");
      });
    });

    describe("action=remove", () => {
      it("should remove document from database", async () => {
        const deleteMock = vi.fn().mockReturnThis();
        const eqMock = vi.fn().mockResolvedValue({ error: null });

        mockSupabaseClient.from.mockReturnValue({
          delete: deleteMock,
          eq: eqMock,
        });

        const request = new NextRequest("http://localhost/api/missing", {
          method: "POST",
          body: JSON.stringify({ action: "remove", documentId: "doc1" }),
        });

        const response = await POST(request);
        const data = await response.json();

        expect(response.status).toBe(200);
        expect(data.success).toBe(true);
      });
    });

    describe("action=mark-inaccessible", () => {
      it("should mark document as inaccessible", async () => {
        const updateMock = vi.fn().mockReturnThis();
        const eqMock = vi.fn().mockResolvedValue({ error: null });

        mockSupabaseClient.from.mockReturnValue({
          update: updateMock,
          eq: eqMock,
        });

        const request = new NextRequest("http://localhost/api/missing", {
          method: "POST",
          body: JSON.stringify({ action: "mark-inaccessible", documentId: "doc1" }),
        });

        const response = await POST(request);
        const data = await response.json();

        expect(response.status).toBe(200);
        expect(data.success).toBe(true);
      });
    });

    it("should handle invalid JSON body", async () => {
      const request = new NextRequest("http://localhost/api/missing", {
        method: "POST",
        body: "invalid json",
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Invalid JSON in request body");
    });
  });
});

describe("Orphaned Files Types", () => {
  it("should have correct MissingFileInfo structure", () => {
    const missingFile: MissingFileInfo = {
      documentId: "doc1",
      fileName: "test.pdf",
      currentPath: "/current/path/test.pdf",
      originalPath: "/original/path/test.pdf",
      aiCategory: "tax_document",
      lastKnownLocation: "/last/known/test.pdf",
      isAccessible: false,
    };

    expect(missingFile.documentId).toBe("doc1");
    expect(missingFile.fileName).toBe("test.pdf");
    expect(missingFile.currentPath).toBe("/current/path/test.pdf");
    expect(missingFile.originalPath).toBe("/original/path/test.pdf");
    expect(missingFile.aiCategory).toBe("tax_document");
    expect(missingFile.isAccessible).toBe(false);
  });

  it("should have correct OrphanedFileInfo structure", () => {
    const orphanedFile: OrphanedFileInfo = {
      filePath: "/path/to/file.pdf",
      fileName: "file.pdf",
      fileSize: 1024,
      lastModified: "2024-01-15T10:00:00Z",
      fileType: ".pdf",
      suggestedLocation: "/Documents/file.pdf",
      suggestedReason: "PDF document - typical location for .pdf files",
      confidence: 0.7,
    };

    expect(orphanedFile.filePath).toBe("/path/to/file.pdf");
    expect(orphanedFile.fileName).toBe("file.pdf");
    expect(orphanedFile.fileSize).toBe(1024);
    expect(orphanedFile.fileType).toBe(".pdf");
    expect(orphanedFile.confidence).toBe(0.7);
  });

  it("should have correct LocationSuggestion structure", () => {
    const suggestion: LocationSuggestion = {
      suggestedPath: "/Documents/Resumes",
      reason: "Filename suggests this is a resume/CV document",
      confidence: 0.8,
      matchType: "filename_pattern",
    };

    expect(suggestion.suggestedPath).toBe("/Documents/Resumes");
    expect(suggestion.matchType).toBe("filename_pattern");
    expect(suggestion.confidence).toBe(0.8);
  });

  it("should have correct EnhancedLocationSuggestion structure", () => {
    const suggestion: EnhancedLocationSuggestion = {
      suggestedPath: "/Documents/Resumes",
      reason: "Filename matches 'employment' category pattern",
      confidence: 0.8,
      matchType: "filename_pattern",
      fromDatabase: false,
      databaseDocumentId: null,
      detectedCategory: "employment",
      similarFilesCount: 0,
    };

    expect(suggestion.suggestedPath).toBe("/Documents/Resumes");
    expect(suggestion.matchType).toBe("filename_pattern");
    expect(suggestion.fromDatabase).toBe(false);
    expect(suggestion.detectedCategory).toBe("employment");
  });
});

// ============================================================================
// Enhanced Location Suggestion Logic Tests (PRD Phase 6)
// ============================================================================

describe("FILENAME_CATEGORY_PATTERNS", () => {
  it("should have patterns for employment category synced with Python", () => {
    const employment = FILENAME_CATEGORY_PATTERNS.employment;
    expect(employment).toBeDefined();
    expect(employment.patterns).toContain("resume");
    expect(employment.patterns).toContain("cv");
    expect(employment.patterns).toContain("cover letter");
    expect(employment.patterns).toContain("job application");
    expect(employment.folder).toBe("Resumes");
    expect(employment.parentFolder).toBe("Employment");
  });

  it("should have patterns for finances category synced with Python", () => {
    const finances = FILENAME_CATEGORY_PATTERNS.finances;
    expect(finances).toBeDefined();
    expect(finances.patterns).toContain("tax");
    expect(finances.patterns).toContain("invoice");
    expect(finances.patterns).toContain("receipt");
    expect(finances.patterns).toContain("bank");
    expect(finances.patterns).toContain("1099");
    expect(finances.patterns).toContain("w2");
    expect(finances.folder).toBe("Taxes");
    expect(finances.parentFolder).toBe("Finances Bin");
  });

  it("should have patterns for legal category synced with Python", () => {
    const legal = FILENAME_CATEGORY_PATTERNS.legal;
    expect(legal).toBeDefined();
    expect(legal.patterns).toContain("contract");
    expect(legal.patterns).toContain("agreement");
    expect(legal.patterns).toContain("lease");
    expect(legal.patterns).toContain("nda");
    expect(legal.folder).toBe("Contracts");
    expect(legal.parentFolder).toBe("Contracts");
  });

  it("should have patterns for health category synced with Python", () => {
    const health = FILENAME_CATEGORY_PATTERNS.health;
    expect(health).toBeDefined();
    expect(health.patterns).toContain("medical");
    expect(health.patterns).toContain("prescription");
    expect(health.patterns).toContain("hospital");
    expect(health.folder).toBe("Medical");
    expect(health.parentFolder).toBe("Health");
  });

  it("should have patterns for identity category synced with Python", () => {
    const identity = FILENAME_CATEGORY_PATTERNS.identity;
    expect(identity).toBeDefined();
    expect(identity.patterns).toContain("passport");
    expect(identity.patterns).toContain("driver");
    expect(identity.patterns).toContain("ssn");
    expect(identity.folder).toBe("Identity");
    expect(identity.parentFolder).toBe("Personal");
  });

  it("should have patterns for education category synced with Python", () => {
    const education = FILENAME_CATEGORY_PATTERNS.education;
    expect(education).toBeDefined();
    expect(education.patterns).toContain("diploma");
    expect(education.patterns).toContain("transcript");
    expect(education.patterns).toContain("certificate");
    expect(education.folder).toBe("Education");
    expect(education.parentFolder).toBe("Education");
  });
});

describe("detectCategoryFromFilename", () => {
  it("should detect employment category from resume filename", () => {
    const result = detectCategoryFromFilename("my_resume_2024.pdf");
    expect(result).not.toBeNull();
    expect(result?.category).toBe("employment");
    expect(result?.folder).toBe("Resumes");
    expect(result?.parentFolder).toBe("Employment");
  });

  it("should detect employment category from CV filename", () => {
    const result = detectCategoryFromFilename("professional_cv.docx");
    expect(result).not.toBeNull();
    expect(result?.category).toBe("employment");
  });

  it("should detect finances category from tax filename", () => {
    const result = detectCategoryFromFilename("tax_return_2023.pdf");
    expect(result).not.toBeNull();
    expect(result?.category).toBe("finances");
    expect(result?.folder).toBe("Taxes");
    expect(result?.parentFolder).toBe("Finances Bin");
  });

  it("should detect finances category from 1099 filename", () => {
    const result = detectCategoryFromFilename("1099_form_2024.pdf");
    expect(result).not.toBeNull();
    expect(result?.category).toBe("finances");
  });

  it("should detect finances category from W2 filename", () => {
    const result = detectCategoryFromFilename("w2_employer_2024.pdf");
    expect(result).not.toBeNull();
    expect(result?.category).toBe("finances");
  });

  it("should detect legal category from contract filename", () => {
    const result = detectCategoryFromFilename("rental_contract.pdf");
    expect(result).not.toBeNull();
    expect(result?.category).toBe("legal");
    expect(result?.folder).toBe("Contracts");
  });

  it("should detect legal category from lease filename", () => {
    const result = detectCategoryFromFilename("apartment_lease_2024.pdf");
    expect(result).not.toBeNull();
    expect(result?.category).toBe("legal");
  });

  it("should detect health category from medical filename", () => {
    const result = detectCategoryFromFilename("medical_records.pdf");
    expect(result).not.toBeNull();
    expect(result?.category).toBe("health");
    expect(result?.folder).toBe("Medical");
  });

  it("should detect health category from prescription filename", () => {
    const result = detectCategoryFromFilename("prescription_medication.pdf");
    expect(result).not.toBeNull();
    expect(result?.category).toBe("health");
  });

  it("should detect identity category from passport filename", () => {
    const result = detectCategoryFromFilename("passport_scan.pdf");
    expect(result).not.toBeNull();
    expect(result?.category).toBe("identity");
    expect(result?.folder).toBe("Identity");
  });

  it("should detect education category from diploma filename", () => {
    const result = detectCategoryFromFilename("diploma_2020.pdf");
    expect(result).not.toBeNull();
    expect(result?.category).toBe("education");
    expect(result?.folder).toBe("Education");
  });

  it("should return null for unrecognized filename", () => {
    const result = detectCategoryFromFilename("random_file_xyz.pdf");
    expect(result).toBeNull();
  });

  it("should be case insensitive", () => {
    const result = detectCategoryFromFilename("MY_RESUME_2024.PDF");
    expect(result).not.toBeNull();
    expect(result?.category).toBe("employment");
  });
});

describe("findSimilarFilesByPattern", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetSupabaseClient();
  });

  it("should find similar files based on filename pattern", async () => {
    const mockFiles = [
      { id: "doc1", file_name: "resume_2024.pdf", current_path: "/Employment/Resumes/resume_2024.pdf", ai_category: "employment", folder_hierarchy: ["Employment", "Resumes"] },
      { id: "doc2", file_name: "resume_2023.pdf", current_path: "/Employment/Resumes/resume_2023.pdf", ai_category: "employment", folder_hierarchy: ["Employment", "Resumes"] },
    ];

    const selectMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockReturnThis();
    const limitMock = vi.fn().mockResolvedValue({
      data: mockFiles,
      error: null,
    });

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      ilike: ilikeMock,
      limit: limitMock,
    });

    const result = await findSimilarFilesByPattern("my_resume.pdf");

    expect(result.similarFiles.length).toBe(2);
    expect(result.dominantFolderHierarchy).toEqual(["Employment", "Resumes"]);
    expect(result.error).toBeUndefined();
  });

  it("should return dominant folder hierarchy from multiple files", async () => {
    const mockFiles = [
      { id: "doc1", file_name: "tax_2024.pdf", current_path: "/Finances/Taxes/tax_2024.pdf", ai_category: "finances", folder_hierarchy: ["Finances Bin", "Taxes"] },
      { id: "doc2", file_name: "tax_2023.pdf", current_path: "/Finances/Taxes/tax_2023.pdf", ai_category: "finances", folder_hierarchy: ["Finances Bin", "Taxes"] },
      { id: "doc3", file_name: "tax_old.pdf", current_path: "/Other/tax_old.pdf", ai_category: "finances", folder_hierarchy: ["Other"] },
    ];

    const selectMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockReturnThis();
    const limitMock = vi.fn().mockResolvedValue({
      data: mockFiles,
      error: null,
    });

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      ilike: ilikeMock,
      limit: limitMock,
    });

    const result = await findSimilarFilesByPattern("tax_return.pdf");

    // Finances Bin/Taxes appears 2 times, Other appears 1 time
    expect(result.dominantFolderHierarchy).toEqual(["Finances Bin", "Taxes"]);
  });

  it("should return null hierarchy when no files found", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockReturnThis();
    const limitMock = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      ilike: ilikeMock,
      limit: limitMock,
    });

    const result = await findSimilarFilesByPattern("unique_file.pdf");

    expect(result.similarFiles).toEqual([]);
    expect(result.dominantFolderHierarchy).toBeNull();
  });

  it("should return empty result for filename with no meaningful terms", async () => {
    const result = await findSimilarFilesByPattern("a.pdf");

    expect(result.similarFiles).toEqual([]);
    expect(result.dominantFolderHierarchy).toBeNull();
  });

  it("should handle database error", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockReturnThis();
    const limitMock = vi.fn().mockResolvedValue({
      data: null,
      error: { message: "Database error" },
    });

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      ilike: ilikeMock,
      limit: limitMock,
    });

    const result = await findSimilarFilesByPattern("some_file.pdf");

    expect(result.similarFiles).toEqual([]);
    expect(result.dominantFolderHierarchy).toBeNull();
    expect(result.error).toBe("Database error");
  });

  it("should handle exception gracefully", async () => {
    mockSupabaseClient.from.mockImplementation(() => {
      throw new Error("Connection failed");
    });

    const result = await findSimilarFilesByPattern("some_file.pdf");

    expect(result.similarFiles).toEqual([]);
    expect(result.error).toBe("Connection failed");
  });
});

describe("suggestLocationForFileEnhanced", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetSupabaseClient();
  });

  it("should use database history when file exists in database", async () => {
    // Mock checkFileInDatabase - file exists
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const limitMock = vi.fn().mockResolvedValue({
      data: [{ id: "doc1" }],
      error: null,
    });
    const orderMock = vi.fn().mockResolvedValue({
      data: [
        { path: "/Original/Folder/file.pdf", location_type: "primary", is_accessible: true, created_at: "2024-01-15T10:00:00Z" },
      ],
      error: null,
    });

    let callCount = 0;
    mockSupabaseClient.from.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // checkFileInDatabase - documents table
        return { select: selectMock, eq: eqMock, limit: limitMock };
      } else if (callCount === 2) {
        // getOriginalLocation
        return { select: selectMock, eq: eqMock, order: orderMock };
      }
      return { select: selectMock, eq: eqMock, limit: limitMock };
    });

    const result = await suggestLocationForFileEnhanced("/test/file.pdf");

    expect(result.matchType).toBe("database_history");
    expect(result.fromDatabase).toBe(true);
    expect(result.databaseDocumentId).toBe("doc1");
    expect(result.confidence).toBe(0.95);
    expect(result.suggestedPath).toBe("/Original/Folder");
  });

  it("should use similar files hierarchy when file not in database but similar files exist", async () => {
    // Mock checkFileInDatabase - file not found
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const limitMock = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });

    // Mock findSimilarFilesByPattern - similar files found
    const ilikeMock = vi.fn().mockReturnThis();
    const limitMock2 = vi.fn().mockResolvedValue({
      data: [
        { id: "doc1", file_name: "resume_2024.pdf", current_path: "/Employment/Resumes/resume_2024.pdf", ai_category: "employment", folder_hierarchy: ["Employment", "Resumes"] },
        { id: "doc2", file_name: "resume_2023.pdf", current_path: "/Employment/Resumes/resume_2023.pdf", ai_category: "employment", folder_hierarchy: ["Employment", "Resumes"] },
      ],
      error: null,
    });

    let callCount = 0;
    mockSupabaseClient.from.mockImplementation(() => {
      callCount++;
      if (callCount <= 2) {
        // checkFileInDatabase calls
        return { select: selectMock, eq: eqMock, limit: limitMock };
      }
      // findSimilarFilesByPattern
      return { select: selectMock, ilike: ilikeMock, limit: limitMock2 };
    });

    const result = await suggestLocationForFileEnhanced("/test/resume_new.pdf");

    expect(result.matchType).toBe("similar_files");
    expect(result.fromDatabase).toBe(true);
    expect(result.confidence).toBe(0.85);
    expect(result.suggestedPath).toBe("Employment/Resumes");
    expect(result.detectedCategory).toBe("employment");
    expect(result.similarFilesCount).toBe(2);
  });

  it("should use filename pattern when no database matches", async () => {
    // Mock all database calls to return empty
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const limitMock = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });
    const ilikeMock = vi.fn().mockReturnThis();

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      eq: eqMock,
      limit: limitMock,
      ilike: ilikeMock,
    });

    const result = await suggestLocationForFileEnhanced("/test/my_tax_return_2024.pdf");

    expect(result.matchType).toBe("filename_pattern");
    expect(result.fromDatabase).toBe(false);
    expect(result.confidence).toBe(0.8);
    expect(result.detectedCategory).toBe("finances");
    expect(result.suggestedPath).toBe("Finances Bin/Taxes");
  });

  it("should use basePath when provided", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const limitMock = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });
    const ilikeMock = vi.fn().mockReturnThis();

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      eq: eqMock,
      limit: limitMock,
      ilike: ilikeMock,
    });

    const result = await suggestLocationForFileEnhanced("/test/my_resume.pdf", "/Users/test");

    expect(result.suggestedPath).toBe("/Users/test/Employment/Resumes");
  });

  it("should fall back to file type suggestion for unknown files", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const limitMock = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });
    const ilikeMock = vi.fn().mockReturnThis();

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      eq: eqMock,
      limit: limitMock,
      ilike: ilikeMock,
    });

    const result = await suggestLocationForFileEnhanced("/test/random_file.pdf");

    expect(result.matchType).toBe("file_type");
    expect(result.fromDatabase).toBe(false);
    expect(result.confidence).toBe(0.7);
    expect(result.suggestedPath).toBe("Documents");
  });

  it("should handle .plist files correctly", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const limitMock = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });
    const ilikeMock = vi.fn().mockReturnThis();

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      eq: eqMock,
      limit: limitMock,
      ilike: ilikeMock,
    });

    const result = await suggestLocationForFileEnhanced("/test/com.apple.finder.plist");

    expect(result.suggestedPath).toBe("Library/Preferences");
    expect(result.matchType).toBe("file_type");
  });
});

describe("suggestLocationsForFiles", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetSupabaseClient();
  });

  it("should process multiple files and return suggestions for each", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const limitMock = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });
    const ilikeMock = vi.fn().mockReturnThis();

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      eq: eqMock,
      limit: limitMock,
      ilike: ilikeMock,
    });

    const filePaths = [
      "/test/resume.pdf",
      "/test/tax_return.pdf",
      "/test/contract.pdf",
    ];

    const results = await suggestLocationsForFiles(filePaths);

    expect(results.size).toBe(3);
    expect(results.has("/test/resume.pdf")).toBe(true);
    expect(results.has("/test/tax_return.pdf")).toBe(true);
    expect(results.has("/test/contract.pdf")).toBe(true);

    const resumeSuggestion = results.get("/test/resume.pdf");
    expect(resumeSuggestion?.detectedCategory).toBe("employment");

    const taxSuggestion = results.get("/test/tax_return.pdf");
    expect(taxSuggestion?.detectedCategory).toBe("finances");

    const contractSuggestion = results.get("/test/contract.pdf");
    expect(contractSuggestion?.detectedCategory).toBe("legal");
  });

  it("should use basePath for all files", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const limitMock = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });
    const ilikeMock = vi.fn().mockReturnThis();

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      eq: eqMock,
      limit: limitMock,
      ilike: ilikeMock,
    });

    const filePaths = ["/test/resume.pdf"];
    const results = await suggestLocationsForFiles(filePaths, "/Users/test");

    const suggestion = results.get("/test/resume.pdf");
    expect(suggestion?.suggestedPath).toContain("/Users/test");
  });

  it("should handle empty file list", async () => {
    const results = await suggestLocationsForFiles([]);
    expect(results.size).toBe(0);
  });
});
