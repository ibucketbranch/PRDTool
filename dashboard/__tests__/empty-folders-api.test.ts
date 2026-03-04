import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";
import {
  getEmptyFolders,
  getFolderHistory,
  resetSupabaseClient,
  extractFolderPath,
  extractFileName,
  normalizeFolderName,
  getSimilarityScore,
  doesFolderMatchCategory,
  detectCategoryFromFolderName,
  findSimilarCanonicalFolder,
  getDominantCategory,
  assessFolderLocation,
  CATEGORY_PATTERNS,
  CANONICAL_FOLDERS,
  type EmptyFolderInfo,
  type MovedFileInfo,
  type FolderAssessment,
} from "@/lib/supabase";

// Mock the Supabase client
const mockSupabaseClient = {
  from: vi.fn(),
};

vi.mock("@supabase/supabase-js", () => ({
  createClient: vi.fn(() => mockSupabaseClient),
}));

describe("Empty Folders Supabase Functions", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetSupabaseClient();
  });

  describe("extractFolderPath", () => {
    it("should extract folder path from file path", () => {
      expect(extractFolderPath("/Users/test/Documents/file.pdf")).toBe(
        "/Users/test/Documents"
      );
    });

    it("should return empty string for empty path", () => {
      expect(extractFolderPath("")).toBe("");
    });

    it("should return empty string for filename only", () => {
      expect(extractFolderPath("file.pdf")).toBe("");
    });

    it("should handle root level files", () => {
      expect(extractFolderPath("/file.pdf")).toBe("");
    });

    it("should handle deeply nested paths", () => {
      expect(extractFolderPath("/a/b/c/d/e/file.pdf")).toBe("/a/b/c/d/e");
    });
  });

  describe("extractFileName", () => {
    it("should extract file name from path", () => {
      expect(extractFileName("/Users/test/Documents/file.pdf")).toBe("file.pdf");
    });

    it("should return empty string for empty path", () => {
      expect(extractFileName("")).toBe("");
    });

    it("should return filename if no path separators", () => {
      expect(extractFileName("file.pdf")).toBe("file.pdf");
    });

    it("should handle deeply nested paths", () => {
      expect(extractFileName("/a/b/c/file.pdf")).toBe("file.pdf");
    });
  });

  describe("getEmptyFolders", () => {
    const mockPreviousLocations = [
      {
        id: "loc1",
        document_id: "doc1",
        path: "/old/folder/file1.pdf",
        location_type: "previous",
        is_accessible: false,
        created_at: "2024-01-15T10:00:00Z",
      },
      {
        id: "loc2",
        document_id: "doc2",
        path: "/old/folder/file2.pdf",
        location_type: "previous",
        is_accessible: false,
        created_at: "2024-01-16T10:00:00Z",
      },
      {
        id: "loc3",
        document_id: "doc3",
        path: "/another/folder/file3.pdf",
        location_type: "previous",
        is_accessible: false,
        created_at: "2024-01-17T10:00:00Z",
      },
    ];

    const mockDocuments = [
      { id: "doc1", file_name: "file1.pdf", current_path: "/new/location/file1.pdf" },
      { id: "doc2", file_name: "file2.pdf", current_path: "/new/location/file2.pdf" },
      { id: "doc3", file_name: "file3.pdf", current_path: "/new/location/file3.pdf" },
    ];

    it("should return empty array when no previous locations exist", async () => {
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        eq: vi.fn().mockResolvedValue({
          data: [],
          error: null,
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      const result = await getEmptyFolders();

      expect(result.emptyFolders).toEqual([]);
      expect(result.totalEmptyFolders).toBe(0);
      expect(result.error).toBeUndefined();
    });

    it("should group files by folder and return empty folder info", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({
        data: mockPreviousLocations,
        error: null,
      });
      const inMock = vi.fn().mockResolvedValue({
        data: mockDocuments,
        error: null,
      });

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return { select: selectMock, eq: eqMock };
        }
        return { select: selectMock, in: inMock };
      });

      const result = await getEmptyFolders();

      expect(result.emptyFolders.length).toBe(2);
      expect(result.totalEmptyFolders).toBe(2);

      // Should be sorted by original file count descending
      const folder1 = result.emptyFolders.find(
        (f) => f.folderPath === "/old/folder"
      );
      expect(folder1).toBeDefined();
      expect(folder1?.originalFileCount).toBe(2);
      expect(folder1?.movedFiles.length).toBe(2);

      const folder2 = result.emptyFolders.find(
        (f) => f.folderPath === "/another/folder"
      );
      expect(folder2).toBeDefined();
      expect(folder2?.originalFileCount).toBe(1);
    });

    it("should handle database error for locations query", async () => {
      const mockQuery = {
        select: vi.fn().mockReturnThis(),
        eq: vi.fn().mockResolvedValue({
          data: null,
          error: { message: "Database error" },
        }),
      };
      mockSupabaseClient.from.mockReturnValue(mockQuery);

      const result = await getEmptyFolders();

      expect(result.emptyFolders).toEqual([]);
      expect(result.error).toBe("Database error");
    });

    it("should handle embedded documents in optimized query", async () => {
      // Optimized getEmptyFolders uses a single query with embedded document relation
      // so there's no separate "documents query" to fail
      const mockLocationsWithDocs = [
        {
          id: "loc1",
          document_id: "doc1",
          path: "/old/folder1/file1.pdf",
          location_type: "previous",
          is_accessible: false,
          created_at: "2024-01-15T10:00:00Z",
          documents: { id: "doc1", file_name: "file1.pdf", current_path: "/new/file1.pdf" },
        },
      ];

      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({
        data: mockLocationsWithDocs,
        error: null,
      });

      mockSupabaseClient.from.mockReturnValue({ select: selectMock, eq: eqMock });

      const result = await getEmptyFolders();

      expect(result.emptyFolders.length).toBe(1);
      expect(result.error).toBeUndefined();
    });

    it("should sort moved files by date descending", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({
        data: mockPreviousLocations,
        error: null,
      });
      const inMock = vi.fn().mockResolvedValue({
        data: mockDocuments,
        error: null,
      });

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return { select: selectMock, eq: eqMock };
        }
        return { select: selectMock, in: inMock };
      });

      const result = await getEmptyFolders();

      const folder1 = result.emptyFolders.find(
        (f) => f.folderPath === "/old/folder"
      );
      // file2 was moved more recently (2024-01-16) than file1 (2024-01-15)
      expect(folder1?.movedFiles[0].fileName).toBe("file2.pdf");
      expect(folder1?.movedFiles[1].fileName).toBe("file1.pdf");
    });

    it("should set lastMoveDate to most recent move", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({
        data: mockPreviousLocations,
        error: null,
      });
      const inMock = vi.fn().mockResolvedValue({
        data: mockDocuments,
        error: null,
      });

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return { select: selectMock, eq: eqMock };
        }
        return { select: selectMock, in: inMock };
      });

      const result = await getEmptyFolders();

      const folder1 = result.emptyFolders.find(
        (f) => f.folderPath === "/old/folder"
      );
      expect(folder1?.lastMoveDate).toBe("2024-01-16T10:00:00Z");
    });

    it("should handle exceptions gracefully", async () => {
      mockSupabaseClient.from.mockImplementation(() => {
        throw new Error("Connection failed");
      });

      const result = await getEmptyFolders();

      expect(result.emptyFolders).toEqual([]);
      expect(result.error).toBe("Connection failed");
    });
  });

  describe("getFolderHistory", () => {
    const mockPreviousLocations = [
      {
        id: "loc1",
        document_id: "doc1",
        path: "/test/folder/file1.pdf",
        location_type: "previous",
        is_accessible: false,
        created_at: "2024-01-15T10:00:00Z",
      },
      {
        id: "loc2",
        document_id: "doc2",
        path: "/test/folder/file2.pdf",
        location_type: "previous",
        is_accessible: false,
        created_at: "2024-01-16T10:00:00Z",
      },
    ];

    const mockDocuments = [
      { id: "doc1", file_name: "file1.pdf", current_path: "/new/location/file1.pdf" },
      { id: "doc2", file_name: "file2.pdf", current_path: "/new/location/file2.pdf" },
    ];

    it("should return files from specified folder", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const ilikeMock = vi.fn().mockResolvedValue({
        data: mockPreviousLocations,
        error: null,
      });
      const inMock = vi.fn().mockResolvedValue({
        data: mockDocuments,
        error: null,
      });

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return { select: selectMock, eq: eqMock, ilike: ilikeMock };
        }
        return { select: selectMock, in: inMock };
      });

      const result = await getFolderHistory("/test/folder");

      expect(result.folderPath).toBe("/test/folder");
      expect(result.files.length).toBe(2);
      expect(result.originalFileCount).toBe(2);
      expect(result.error).toBeUndefined();
    });

    it("should return empty array for folder with no history", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const ilikeMock = vi.fn().mockResolvedValue({
        data: [],
        error: null,
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        ilike: ilikeMock,
      });

      const result = await getFolderHistory("/empty/folder");

      expect(result.folderPath).toBe("/empty/folder");
      expect(result.files).toEqual([]);
      expect(result.originalFileCount).toBe(0);
    });

    it("should handle database error", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const ilikeMock = vi.fn().mockResolvedValue({
        data: null,
        error: { message: "Query failed" },
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        ilike: ilikeMock,
      });

      const result = await getFolderHistory("/test/folder");

      expect(result.files).toEqual([]);
      expect(result.error).toBe("Query failed");
    });

    it("should exclude files from subfolders", async () => {
      const locationsWithSubfolder = [
        ...mockPreviousLocations,
        {
          id: "loc3",
          document_id: "doc3",
          path: "/test/folder/subfolder/file3.pdf",
          location_type: "previous",
          is_accessible: false,
          created_at: "2024-01-17T10:00:00Z",
        },
      ];

      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const ilikeMock = vi.fn().mockResolvedValue({
        data: locationsWithSubfolder,
        error: null,
      });
      const inMock = vi.fn().mockResolvedValue({
        data: mockDocuments,
        error: null,
      });

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return { select: selectMock, eq: eqMock, ilike: ilikeMock };
        }
        return { select: selectMock, in: inMock };
      });

      const result = await getFolderHistory("/test/folder");

      // Should only include files directly in /test/folder, not in subfolder
      expect(result.files.length).toBe(2);
      expect(result.files.every((f) => !f.originalPath.includes("subfolder"))).toBe(
        true
      );
    });

    it("should sort files by moved date descending", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const ilikeMock = vi.fn().mockResolvedValue({
        data: mockPreviousLocations,
        error: null,
      });
      const inMock = vi.fn().mockResolvedValue({
        data: mockDocuments,
        error: null,
      });

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return { select: selectMock, eq: eqMock, ilike: ilikeMock };
        }
        return { select: selectMock, in: inMock };
      });

      const result = await getFolderHistory("/test/folder");

      // file2 was moved more recently
      expect(result.files[0].fileName).toBe("file2.pdf");
      expect(result.files[1].fileName).toBe("file1.pdf");
    });

    it("should handle exceptions gracefully", async () => {
      mockSupabaseClient.from.mockImplementation(() => {
        throw new Error("Connection error");
      });

      const result = await getFolderHistory("/test/folder");

      expect(result.files).toEqual([]);
      expect(result.error).toBe("Connection error");
    });
  });
});

describe("Empty Folders API Endpoint", () => {
  // Import after mocking
  let GET: typeof import("@/app/api/empty-folders/route").GET;
  let POST: typeof import("@/app/api/empty-folders/route").POST;

  beforeEach(async () => {
    resetSupabaseClient();
    vi.clearAllMocks();

    // Dynamic import to get fresh module
    const module = await import("@/app/api/empty-folders/route");
    GET = module.GET;
    POST = module.POST;
  });

  afterEach(() => {
    resetSupabaseClient();
  });

  describe("GET /api/empty-folders", () => {
    it("should return empty folders from database", async () => {
      const mockPreviousLocations = [
        {
          id: "loc1",
          document_id: "doc1",
          path: "/nonexistent/folder/file1.pdf",
          location_type: "previous",
          is_accessible: false,
          created_at: "2024-01-15T10:00:00Z",
        },
      ];

      const mockDocuments = [
        { id: "doc1", file_name: "file1.pdf", current_path: "/new/file1.pdf" },
      ];

      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({
        data: mockPreviousLocations,
        error: null,
      });
      const inMock = vi.fn().mockResolvedValue({
        data: mockDocuments,
        error: null,
      });

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return { select: selectMock, eq: eqMock };
        }
        return { select: selectMock, in: inMock };
      });

      const request = new NextRequest("http://localhost/api/empty-folders", {
        method: "GET",
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.emptyFolders).toBeDefined();
      expect(data.totalEmptyFolders).toBeDefined();
    });

    it("should verify filesystem status by default", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({
        data: [],
        error: null,
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
      });

      const request = new NextRequest("http://localhost/api/empty-folders", {
        method: "GET",
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.verifiedEmpty).toBeDefined();
      expect(data.notEmpty).toBeDefined();
      expect(data.notFound).toBeDefined();
    });

    it("should skip filesystem verification when verifyFilesystem=false", async () => {
      const mockPreviousLocations = [
        {
          id: "loc1",
          document_id: "doc1",
          path: "/test/folder/file1.pdf",
          location_type: "previous",
          is_accessible: false,
          created_at: "2024-01-15T10:00:00Z",
        },
      ];

      const mockDocuments = [
        { id: "doc1", file_name: "file1.pdf", current_path: "/new/file1.pdf" },
      ];

      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({
        data: mockPreviousLocations,
        error: null,
      });
      const inMock = vi.fn().mockResolvedValue({
        data: mockDocuments,
        error: null,
      });

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return { select: selectMock, eq: eqMock };
        }
        return { select: selectMock, in: inMock };
      });

      const request = new NextRequest(
        "http://localhost/api/empty-folders?verifyFilesystem=false",
        { method: "GET" }
      );

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      // When verifyFilesystem is false, counts should be 0
      expect(data.verifiedEmpty).toBe(0);
      expect(data.notEmpty).toBe(0);
      expect(data.notFound).toBe(0);
    });

    it("should return 500 on database error", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({
        data: null,
        error: { message: "Database connection failed" },
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
      });

      const request = new NextRequest("http://localhost/api/empty-folders", {
        method: "GET",
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(500);
      expect(data.error).toBe("Database connection failed");
    });

    it("should filter to only empty folders when onlyEmpty=true", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockResolvedValue({
        data: [],
        error: null,
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
      });

      const request = new NextRequest(
        "http://localhost/api/empty-folders?onlyEmpty=true",
        { method: "GET" }
      );

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      // All returned folders should be empty
      data.emptyFolders.forEach((folder: EmptyFolderInfo) => {
        expect(folder.isEmpty).toBe(true);
      });
    });
  });

  describe("POST /api/empty-folders", () => {
    it("should return folder history for valid path", async () => {
      const mockPreviousLocations = [
        {
          id: "loc1",
          document_id: "doc1",
          path: "/test/folder/file1.pdf",
          location_type: "previous",
          is_accessible: false,
          created_at: "2024-01-15T10:00:00Z",
        },
      ];

      const mockDocuments = [
        { id: "doc1", file_name: "file1.pdf", current_path: "/new/file1.pdf" },
      ];

      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const ilikeMock = vi.fn().mockResolvedValue({
        data: mockPreviousLocations,
        error: null,
      });
      const inMock = vi.fn().mockResolvedValue({
        data: mockDocuments,
        error: null,
      });

      let callCount = 0;
      mockSupabaseClient.from.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return { select: selectMock, eq: eqMock, ilike: ilikeMock };
        }
        return { select: selectMock, in: inMock };
      });

      const request = new NextRequest("http://localhost/api/empty-folders", {
        method: "POST",
        body: JSON.stringify({ folderPath: "/test/folder" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.folderPath).toBe("/test/folder");
      expect(data.files).toBeDefined();
      expect(data.originalFileCount).toBeDefined();
      expect(data.folderStatus).toBeDefined();
    });

    it("should return error when folderPath is missing", async () => {
      const request = new NextRequest("http://localhost/api/empty-folders", {
        method: "POST",
        body: JSON.stringify({}),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Folder path is required");
    });

    it("should return error when folderPath is not a string", async () => {
      const request = new NextRequest("http://localhost/api/empty-folders", {
        method: "POST",
        body: JSON.stringify({ folderPath: 123 }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Folder path is required");
    });

    it("should return error for relative paths", async () => {
      const request = new NextRequest("http://localhost/api/empty-folders", {
        method: "POST",
        body: JSON.stringify({ folderPath: "relative/path" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe("Only absolute paths are allowed");
    });

    it("should normalize path", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const ilikeMock = vi.fn().mockResolvedValue({
        data: [],
        error: null,
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        ilike: ilikeMock,
      });

      const request = new NextRequest("http://localhost/api/empty-folders", {
        method: "POST",
        body: JSON.stringify({ folderPath: "/test/../test/folder" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.folderPath).toBe("/test/folder");
    });

    it("should return not_found status for nonexistent folder", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const ilikeMock = vi.fn().mockResolvedValue({
        data: [],
        error: null,
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        ilike: ilikeMock,
      });

      const request = new NextRequest("http://localhost/api/empty-folders", {
        method: "POST",
        body: JSON.stringify({ folderPath: "/nonexistent/path/that/does/not/exist" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.folderStatus).toBe("not_found");
    });

    it("should return 500 on database error", async () => {
      const selectMock = vi.fn().mockReturnThis();
      const eqMock = vi.fn().mockReturnThis();
      const ilikeMock = vi.fn().mockResolvedValue({
        data: null,
        error: { message: "Database error" },
      });

      mockSupabaseClient.from.mockReturnValue({
        select: selectMock,
        eq: eqMock,
        ilike: ilikeMock,
      });

      const request = new NextRequest("http://localhost/api/empty-folders", {
        method: "POST",
        body: JSON.stringify({ folderPath: "/test/folder" }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(500);
      expect(data.error).toBe("Database error");
    });

    it("should handle invalid JSON body", async () => {
      const request = new NextRequest("http://localhost/api/empty-folders", {
        method: "POST",
        body: "invalid json",
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(500);
      expect(data.error).toBeDefined();
    });
  });
});

describe("Empty Folders Types", () => {
  it("should have correct EmptyFolderInfo structure", () => {
    const folderInfo: EmptyFolderInfo = {
      folderPath: "/test/folder",
      originalFileCount: 5,
      movedFiles: [],
      isEmpty: true,
      lastMoveDate: "2024-01-15T10:00:00Z",
    };

    expect(folderInfo.folderPath).toBe("/test/folder");
    expect(folderInfo.originalFileCount).toBe(5);
    expect(folderInfo.movedFiles).toEqual([]);
    expect(folderInfo.isEmpty).toBe(true);
    expect(folderInfo.lastMoveDate).toBe("2024-01-15T10:00:00Z");
  });

  it("should have correct MovedFileInfo structure", () => {
    const movedFile: MovedFileInfo = {
      documentId: "doc1",
      fileName: "test.pdf",
      originalPath: "/old/path/test.pdf",
      currentPath: "/new/path/test.pdf",
      movedAt: "2024-01-15T10:00:00Z",
    };

    expect(movedFile.documentId).toBe("doc1");
    expect(movedFile.fileName).toBe("test.pdf");
    expect(movedFile.originalPath).toBe("/old/path/test.pdf");
    expect(movedFile.currentPath).toBe("/new/path/test.pdf");
    expect(movedFile.movedAt).toBe("2024-01-15T10:00:00Z");
  });
});

// ============================================================================
// Folder Assessment Logic Tests
// ============================================================================

describe("Folder Assessment Helper Functions", () => {
  describe("normalizeFolderName", () => {
    it("should convert to lowercase", () => {
      expect(normalizeFolderName("RESUMES")).toBe("resumes");
      expect(normalizeFolderName("Tax_Documents")).toBe("tax documents");
    });

    it("should remove trailing numbers", () => {
      expect(normalizeFolderName("Resumes_1")).toBe("resumes");
      expect(normalizeFolderName("Tax-2023")).toBe("tax");
      expect(normalizeFolderName("Documents_123")).toBe("documents");
    });

    it("should replace underscores and hyphens with spaces", () => {
      expect(normalizeFolderName("tax_documents")).toBe("tax documents");
      expect(normalizeFolderName("va-claims")).toBe("va claims");
    });

    it("should handle empty string", () => {
      expect(normalizeFolderName("")).toBe("");
    });

    it("should trim extra spaces", () => {
      expect(normalizeFolderName("  Tax   Documents  ")).toBe("tax documents");
    });
  });

  describe("getSimilarityScore", () => {
    it("should return 1.0 for identical strings", () => {
      expect(getSimilarityScore("Resumes", "Resumes")).toBe(1.0);
      expect(getSimilarityScore("resume", "Resume")).toBe(1.0);
    });

    it("should return 0.0 for empty strings", () => {
      expect(getSimilarityScore("", "test")).toBe(0.0);
      expect(getSimilarityScore("test", "")).toBe(0.0);
    });

    it("should return 0.85 when one contains the other", () => {
      expect(getSimilarityScore("Tax", "Tax Documents")).toBe(0.85);
      expect(getSimilarityScore("Resume", "Resume Folder")).toBe(0.85);
    });

    it("should return lower score for dissimilar strings", () => {
      const score = getSimilarityScore("Resumes", "Contracts");
      expect(score).toBeLessThan(0.5);
    });

    it("should return higher score for similar strings", () => {
      const score = getSimilarityScore("Resume", "Resumes");
      expect(score).toBeGreaterThan(0.8);
    });
  });

  describe("doesFolderMatchCategory", () => {
    it("should match folder name to employment category", () => {
      // "resumes" contains "resume" pattern
      expect(doesFolderMatchCategory("Resumes", "employment")).toBe(true);
      expect(doesFolderMatchCategory("CV", "employment")).toBe(true);
      expect(doesFolderMatchCategory("Job_Applications", "employment")).toBe(true);
    });

    it("should match folder name to tax category", () => {
      // "taxes" contains "tax" pattern
      expect(doesFolderMatchCategory("Taxes", "tax_document")).toBe(true);
      expect(doesFolderMatchCategory("Tax_2023", "tax_document")).toBe(true);
      expect(doesFolderMatchCategory("1099_Forms", "tax_document")).toBe(true);
    });

    it("should match folder name to VA claims category", () => {
      expect(doesFolderMatchCategory("VA_Claims", "va_claims")).toBe(true);
      expect(doesFolderMatchCategory("Veteran_Documents", "va_claims")).toBe(true);
      // "dd214" is in the va_claims patterns
      expect(doesFolderMatchCategory("DD214_Documents", "va_claims")).toBe(true);
    });

    it("should not match unrelated folder to category", () => {
      expect(doesFolderMatchCategory("Photos", "employment")).toBe(false);
      expect(doesFolderMatchCategory("Random", "tax_document")).toBe(false);
    });

    it("should handle unknown category", () => {
      expect(doesFolderMatchCategory("Resumes", "unknown_category")).toBe(false);
    });
  });

  describe("detectCategoryFromFolderName", () => {
    it("should detect employment category from resume folder", () => {
      // "resumes" contains "resume" pattern from employment category
      expect(detectCategoryFromFolderName("Resumes")).toBe("employment");
      expect(detectCategoryFromFolderName("My_Resume")).toBe("employment");
    });

    it("should detect finances category from tax folder", () => {
      // finances category comes first and contains "tax" pattern
      expect(detectCategoryFromFolderName("Taxes")).toBe("finances");
      expect(detectCategoryFromFolderName("Tax_Returns")).toBe("finances");
    });

    it("should detect VA claims from veteran folder", () => {
      expect(detectCategoryFromFolderName("VA_Claims")).toBe("va_claims");
      expect(detectCategoryFromFolderName("Veteran_Benefits")).toBe("va_claims");
    });

    it("should return null for unrecognized folder", () => {
      expect(detectCategoryFromFolderName("Random_Stuff")).toBeNull();
      expect(detectCategoryFromFolderName("Photos")).toBeNull();
    });
  });

  describe("findSimilarCanonicalFolder", () => {
    it("should find exact match to canonical folder", () => {
      const result = findSimilarCanonicalFolder("Resumes");
      expect(result).not.toBeNull();
      expect(result?.folder).toBe("Resumes");
      expect(result?.category).toBe("employment");
      expect(result?.score).toBe(1.0);
    });

    it("should find similar canonical folder", () => {
      const result = findSimilarCanonicalFolder("Resume");
      expect(result).not.toBeNull();
      expect(result?.folder).toBe("Resumes");
      expect(result?.score).toBeGreaterThan(0.7);
    });

    it("should return null for unrelated folder", () => {
      const result = findSimilarCanonicalFolder("Random_Stuff");
      expect(result).toBeNull();
    });

    it("should respect custom threshold", () => {
      // "xyz" has very low similarity to any canonical folder
      const result = findSimilarCanonicalFolder("xyz", 0.9);
      expect(result).toBeNull(); // Below 0.9 threshold
    });
  });

  describe("getDominantCategory", () => {
    it("should return most common category", () => {
      expect(getDominantCategory(["tax_document", "tax_document", "invoice"])).toBe("tax_document");
      expect(getDominantCategory(["employment", "employment", "employment"])).toBe("employment");
    });

    it("should return null for empty array", () => {
      expect(getDominantCategory([])).toBeNull();
    });

    it("should handle single category", () => {
      expect(getDominantCategory(["va_claims"])).toBe("va_claims");
    });

    it("should handle null values in array", () => {
      expect(getDominantCategory(["tax_document", null as unknown as string, "tax_document"])).toBe("tax_document");
    });
  });
});

describe("Category Patterns and Canonical Folders", () => {
  it("should have patterns for all common categories", () => {
    expect(CATEGORY_PATTERNS.employment).toContain("resume");
    expect(CATEGORY_PATTERNS.tax_document).toContain("tax");
    expect(CATEGORY_PATTERNS.va_claims).toContain("va");
    expect(CATEGORY_PATTERNS.health).toContain("medical");
    expect(CATEGORY_PATTERNS.legal).toContain("contract");
  });

  it("should have canonical folders for all categories", () => {
    expect(CANONICAL_FOLDERS.employment).toBe("Resumes");
    expect(CANONICAL_FOLDERS.tax_document).toBe("Taxes");
    expect(CANONICAL_FOLDERS.va_claims).toBe("VA Claims");
    expect(CANONICAL_FOLDERS.health).toBe("Medical");
    expect(CANONICAL_FOLDERS.contract).toBe("Contracts");
  });
});

describe("assessFolderLocation", () => {
  beforeEach(() => {
    resetSupabaseClient();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetSupabaseClient();
  });

  it("should return unknown assessment when no files were moved", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      eq: eqMock,
      ilike: ilikeMock,
    });

    const result = await assessFolderLocation("/test/Resumes");

    expect(result.assessment.assessment).toBe("unknown");
    expect(result.assessment.confidence).toBe(0.0);
    expect(result.assessment.suggestedAction).toBe("review");
    expect(result.movedFiles).toEqual([]);
  });

  it("should assess folder as correct when category matches", async () => {
    const mockPreviousLocations = [
      {
        id: "loc1",
        document_id: "doc1",
        path: "/old/Resumes/resume.pdf",
        location_type: "previous",
        is_accessible: false,
        created_at: "2024-01-15T10:00:00Z",
      },
    ];

    const mockDocumentsHistory = [
      { id: "doc1", file_name: "resume.pdf", current_path: "/new/resume.pdf" },
    ];

    const mockDocumentsWithCategory = [
      { id: "doc1", ai_category: "employment", folder_hierarchy: ["Employment", "Resumes"] },
    ];

    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockResolvedValue({
      data: mockPreviousLocations,
      error: null,
    });

    let callCount = 0;
    mockSupabaseClient.from.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // getFolderHistory - document_locations query
        return { select: selectMock, eq: eqMock, ilike: ilikeMock };
      } else if (callCount === 2) {
        // getFolderHistory - documents query for current paths
        return {
          select: selectMock,
          in: vi.fn().mockResolvedValue({ data: mockDocumentsHistory, error: null }),
        };
      } else {
        // assessFolderLocation - documents query for AI categories
        return {
          select: selectMock,
          in: vi.fn().mockResolvedValue({ data: mockDocumentsWithCategory, error: null }),
        };
      }
    });

    const result = await assessFolderLocation("/old/Resumes");

    expect(result.assessment.folderName).toBe("Resumes");
    expect(result.assessment.categoryMatch).toBe(true);
    expect(result.assessment.dominantCategory).toBe("employment");
    expect(result.assessment.isCorrectLocation).toBe(true);
    expect(result.assessment.assessment).toBe("correct");
    expect(result.assessment.suggestedAction).toBe("restore");
  });

  it("should assess folder as duplicate when similar to canonical", async () => {
    const mockPreviousLocations = [
      {
        id: "loc1",
        document_id: "doc1",
        path: "/old/Resumees/resume.pdf",
        location_type: "previous",
        is_accessible: false,
        created_at: "2024-01-15T10:00:00Z",
      },
    ];

    const mockDocumentsHistory = [
      { id: "doc1", file_name: "resume.pdf", current_path: "/new/resume.pdf" },
    ];

    const mockDocumentsWithCategory = [
      { id: "doc1", ai_category: "medical_record", folder_hierarchy: [] },
    ];

    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockResolvedValue({
      data: mockPreviousLocations,
      error: null,
    });
    const inMock = vi.fn();

    let callCount = 0;
    mockSupabaseClient.from.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return { select: selectMock, eq: eqMock, ilike: ilikeMock };
      } else if (callCount === 2) {
        inMock.mockResolvedValue({ data: mockDocumentsHistory, error: null });
        return { select: selectMock, in: inMock };
      } else {
        inMock.mockResolvedValue({ data: mockDocumentsWithCategory, error: null });
        return { select: selectMock, in: inMock };
      }
    });

    const result = await assessFolderLocation("/old/Resumees");

    // Folder name "Resumees" is similar to canonical "Resumes" but files are medical
    // This indicates a mismatch/duplicate
    expect(result.assessment.folderName).toBe("Resumees");
    expect(result.assessment.similarCanonicalFolder).toBe("Resumes");
  });

  it("should handle database error gracefully", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockResolvedValue({
      data: null,
      error: { message: "Database connection failed" },
    });

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      eq: eqMock,
      ilike: ilikeMock,
    });

    const result = await assessFolderLocation("/test/folder");

    expect(result.error).toBe("Database connection failed");
    expect(result.assessment.assessment).toBe("unknown");
  });

  it("should handle exceptions gracefully", async () => {
    mockSupabaseClient.from.mockImplementation(() => {
      throw new Error("Connection timeout");
    });

    const result = await assessFolderLocation("/test/folder");

    expect(result.error).toBe("Connection timeout");
    expect(result.assessment.assessment).toBe("unknown");
    expect(result.assessment.suggestedAction).toBe("review");
  });

  it("should extract folder name from path correctly", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      eq: eqMock,
      ilike: ilikeMock,
    });

    const result = await assessFolderLocation("/Users/test/Documents/MyResumes");

    expect(result.assessment.folderPath).toBe("/Users/test/Documents/MyResumes");
    expect(result.assessment.folderName).toBe("MyResumes");
  });

  it("should detect folder hierarchy match", async () => {
    const mockPreviousLocations = [
      {
        id: "loc1",
        document_id: "doc1",
        path: "/Employment/resume.pdf",
        location_type: "previous",
        is_accessible: false,
        created_at: "2024-01-15T10:00:00Z",
      },
    ];

    const mockDocumentsHistory = [
      { id: "doc1", file_name: "resume.pdf", current_path: "/new/resume.pdf" },
    ];

    const mockDocumentsWithCategory = [
      { id: "doc1", ai_category: "employment", folder_hierarchy: ["Employment", "Resumes"] },
    ];

    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockResolvedValue({
      data: mockPreviousLocations,
      error: null,
    });
    const inMock = vi.fn();

    let callCount = 0;
    mockSupabaseClient.from.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return { select: selectMock, eq: eqMock, ilike: ilikeMock };
      } else if (callCount === 2) {
        inMock.mockResolvedValue({ data: mockDocumentsHistory, error: null });
        return { select: selectMock, in: inMock };
      } else {
        inMock.mockResolvedValue({ data: mockDocumentsWithCategory, error: null });
        return { select: selectMock, in: inMock };
      }
    });

    const result = await assessFolderLocation("/Employment");

    expect(result.assessment.folderHierarchyMatch).toBe(true);
  });
});

describe("FolderAssessment Types", () => {
  it("should have correct FolderAssessment structure", () => {
    const assessment: FolderAssessment = {
      folderPath: "/test/Resumes",
      folderName: "Resumes",
      isCorrectLocation: true,
      isDuplicate: false,
      assessment: "correct",
      confidence: 0.8,
      reasoning: ["Folder name matches AI category"],
      suggestedAction: "restore",
      movedFilesCategories: ["employment"],
      dominantCategory: "employment",
      categoryMatch: true,
      folderHierarchyMatch: false,
      canonicalMatch: true,
      similarCanonicalFolder: "Resumes",
      canonicalRegistryMatch: false,
      executionLogMatch: false,
      executionLogMovements: 0,
    };

    expect(assessment.folderPath).toBe("/test/Resumes");
    expect(assessment.assessment).toBe("correct");
    expect(assessment.suggestedAction).toBe("restore");
    expect(assessment.confidence).toBe(0.8);
  });
});

describe("Folder Assessment API Endpoint", () => {
  let POST: typeof import("@/app/api/empty-folders/assess/route").POST;

  beforeEach(async () => {
    resetSupabaseClient();
    vi.clearAllMocks();

    const module = await import("@/app/api/empty-folders/assess/route");
    POST = module.POST;
  });

  afterEach(() => {
    resetSupabaseClient();
  });

  it("should return assessment for valid folder path", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      eq: eqMock,
      ilike: ilikeMock,
    });

    const request = new NextRequest("http://localhost/api/empty-folders/assess", {
      method: "POST",
      body: JSON.stringify({ folderPath: "/test/Resumes" }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.assessment).toBeDefined();
    expect(data.assessment.folderPath).toBe("/test/Resumes");
    expect(data.assessment.folderName).toBe("Resumes");
  });

  it("should return error when folderPath is missing", async () => {
    const request = new NextRequest("http://localhost/api/empty-folders/assess", {
      method: "POST",
      body: JSON.stringify({}),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.error).toBe("Folder path is required");
    expect(data.assessment).toBeNull();
  });

  it("should return error when folderPath is not a string", async () => {
    const request = new NextRequest("http://localhost/api/empty-folders/assess", {
      method: "POST",
      body: JSON.stringify({ folderPath: 123 }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.error).toBe("Folder path is required");
  });

  it("should return error for relative paths", async () => {
    const request = new NextRequest("http://localhost/api/empty-folders/assess", {
      method: "POST",
      body: JSON.stringify({ folderPath: "relative/path" }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.error).toBe("Only absolute paths are allowed");
  });

  it("should normalize path before assessment", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      eq: eqMock,
      ilike: ilikeMock,
    });

    const request = new NextRequest("http://localhost/api/empty-folders/assess", {
      method: "POST",
      body: JSON.stringify({ folderPath: "/test/../test/Resumes" }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.assessment.folderPath).toBe("/test/Resumes");
  });

  it("should handle invalid JSON body", async () => {
    const request = new NextRequest("http://localhost/api/empty-folders/assess", {
      method: "POST",
      body: "invalid json",
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.error).toBe("Invalid JSON in request body");
  });

  it("should return 500 on database error", async () => {
    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockResolvedValue({
      data: null,
      error: { message: "Database error" },
    });

    mockSupabaseClient.from.mockReturnValue({
      select: selectMock,
      eq: eqMock,
      ilike: ilikeMock,
    });

    const request = new NextRequest("http://localhost/api/empty-folders/assess", {
      method: "POST",
      body: JSON.stringify({ folderPath: "/test/folder" }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(500);
    expect(data.error).toBe("Database error");
  });

  it("should return moved files with assessment", async () => {
    const mockPreviousLocations = [
      {
        id: "loc1",
        document_id: "doc1",
        path: "/test/Resumes/resume.pdf",
        location_type: "previous",
        is_accessible: false,
        created_at: "2024-01-15T10:00:00Z",
      },
    ];

    const mockDocumentsHistory = [
      { id: "doc1", file_name: "resume.pdf", current_path: "/new/resume.pdf" },
    ];

    const mockDocumentsWithCategory = [
      { id: "doc1", ai_category: "employment", folder_hierarchy: [] },
    ];

    const selectMock = vi.fn().mockReturnThis();
    const eqMock = vi.fn().mockReturnThis();
    const ilikeMock = vi.fn().mockResolvedValue({
      data: mockPreviousLocations,
      error: null,
    });
    const inMock = vi.fn();

    let callCount = 0;
    mockSupabaseClient.from.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return { select: selectMock, eq: eqMock, ilike: ilikeMock };
      } else if (callCount === 2) {
        inMock.mockResolvedValue({ data: mockDocumentsHistory, error: null });
        return { select: selectMock, in: inMock };
      } else {
        inMock.mockResolvedValue({ data: mockDocumentsWithCategory, error: null });
        return { select: selectMock, in: inMock };
      }
    });

    const request = new NextRequest("http://localhost/api/empty-folders/assess", {
      method: "POST",
      body: JSON.stringify({ folderPath: "/test/Resumes" }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.movedFiles).toBeDefined();
    expect(data.movedFiles.length).toBe(1);
    expect(data.movedFiles[0].fileName).toBe("resume.pdf");
  });
});
