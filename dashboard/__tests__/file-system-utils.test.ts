import { describe, it, expect } from "vitest";
import {
  SUPPORTED_EXTENSIONS,
  ADDITIONAL_SCAN_EXTENSIONS,
  ALL_SCAN_EXTENSIONS,
  isProcessableExtension,
  formatFileSize,
  getFileTypeCategory,
  type FileVerificationResult,
  type FileInfo,
  type ScanFolderOptions,
  type VerificationSummary,
} from "@/lib/file-system-utils";

/**
 * Tests for File System Utils Integration Module
 *
 * This module provides file system operations that integrate with the
 * Python organizer module patterns. Tests focus on pure functions that
 * don't require filesystem mocking.
 *
 * Integration points tested:
 * - SUPPORTED_EXTENSIONS synced with organizer/content_analyzer.py
 * - Utility functions for file categorization
 */

describe("File System Utils Integration Module", () => {
  describe("SUPPORTED_EXTENSIONS", () => {
    it("should contain document extensions synced with organizer/content_analyzer.py", () => {
      expect(SUPPORTED_EXTENSIONS.has(".pdf")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".doc")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".docx")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".txt")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".rtf")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".odt")).toBe(true);
    });

    it("should contain spreadsheet extensions", () => {
      expect(SUPPORTED_EXTENSIONS.has(".xls")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".xlsx")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".csv")).toBe(true);
    });

    it("should contain presentation extensions", () => {
      expect(SUPPORTED_EXTENSIONS.has(".ppt")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".pptx")).toBe(true);
    });

    it("should contain image extensions", () => {
      expect(SUPPORTED_EXTENSIONS.has(".png")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".jpg")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".jpeg")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".gif")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".tiff")).toBe(true);
      expect(SUPPORTED_EXTENSIONS.has(".bmp")).toBe(true);
    });

    it("should have the correct count of supported extensions", () => {
      // From organizer/content_analyzer.py: 17 extensions
      // (pdf, doc, docx, txt, rtf, odt, xls, xlsx, csv, ppt, pptx, png, jpg, jpeg, gif, tiff, bmp)
      expect(SUPPORTED_EXTENSIONS.size).toBe(17);
    });
  });

  describe("ADDITIONAL_SCAN_EXTENSIONS", () => {
    it("should contain media and archive extensions", () => {
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".heic")).toBe(true);
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".mp4")).toBe(true);
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".mov")).toBe(true);
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".mp3")).toBe(true);
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".plist")).toBe(true);
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".zip")).toBe(true);
    });

    it("should contain video extensions", () => {
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".mp4")).toBe(true);
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".mov")).toBe(true);
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".avi")).toBe(true);
    });

    it("should contain audio extensions", () => {
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".mp3")).toBe(true);
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".m4a")).toBe(true);
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".wav")).toBe(true);
    });

    it("should contain archive extensions", () => {
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".zip")).toBe(true);
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".tar")).toBe(true);
      expect(ADDITIONAL_SCAN_EXTENSIONS.has(".gz")).toBe(true);
    });
  });

  describe("ALL_SCAN_EXTENSIONS", () => {
    it("should be union of SUPPORTED_EXTENSIONS and ADDITIONAL_SCAN_EXTENSIONS", () => {
      // Check some from SUPPORTED_EXTENSIONS
      expect(ALL_SCAN_EXTENSIONS.has(".pdf")).toBe(true);
      expect(ALL_SCAN_EXTENSIONS.has(".docx")).toBe(true);

      // Check some from ADDITIONAL_SCAN_EXTENSIONS
      expect(ALL_SCAN_EXTENSIONS.has(".heic")).toBe(true);
      expect(ALL_SCAN_EXTENSIONS.has(".plist")).toBe(true);

      // Total should be sum of both (no overlap)
      const expectedSize = SUPPORTED_EXTENSIONS.size + ADDITIONAL_SCAN_EXTENSIONS.size;
      expect(ALL_SCAN_EXTENSIONS.size).toBe(expectedSize);
    });

    it("should include all processable and scannable extensions", () => {
      // All SUPPORTED should be in ALL
      for (const ext of SUPPORTED_EXTENSIONS) {
        expect(ALL_SCAN_EXTENSIONS.has(ext)).toBe(true);
      }

      // All ADDITIONAL should be in ALL
      for (const ext of ADDITIONAL_SCAN_EXTENSIONS) {
        expect(ALL_SCAN_EXTENSIONS.has(ext)).toBe(true);
      }
    });
  });

  describe("isProcessableExtension", () => {
    it("should return true for processable document extensions", () => {
      expect(isProcessableExtension(".pdf")).toBe(true);
      expect(isProcessableExtension(".doc")).toBe(true);
      expect(isProcessableExtension(".docx")).toBe(true);
      expect(isProcessableExtension(".txt")).toBe(true);
    });

    it("should return true for processable image extensions", () => {
      expect(isProcessableExtension(".png")).toBe(true);
      expect(isProcessableExtension(".jpg")).toBe(true);
      expect(isProcessableExtension(".jpeg")).toBe(true);
    });

    it("should return false for non-processable extensions", () => {
      expect(isProcessableExtension(".plist")).toBe(false);
      expect(isProcessableExtension(".zip")).toBe(false);
      expect(isProcessableExtension(".mp4")).toBe(false);
      expect(isProcessableExtension(".xyz")).toBe(false);
    });

    it("should be case insensitive", () => {
      expect(isProcessableExtension(".PDF")).toBe(true);
      expect(isProcessableExtension(".Pdf")).toBe(true);
      expect(isProcessableExtension(".PNG")).toBe(true);
    });

    it("should handle empty string", () => {
      expect(isProcessableExtension("")).toBe(false);
    });
  });

  describe("formatFileSize", () => {
    it("should format 0 bytes correctly", () => {
      expect(formatFileSize(0)).toBe("0 Bytes");
    });

    it("should format bytes correctly", () => {
      expect(formatFileSize(500)).toBe("500 Bytes");
      expect(formatFileSize(1023)).toBe("1023 Bytes");
    });

    it("should format KB correctly", () => {
      expect(formatFileSize(1024)).toBe("1 KB");
      expect(formatFileSize(1536)).toBe("1.5 KB");
      expect(formatFileSize(10240)).toBe("10 KB");
    });

    it("should format MB correctly", () => {
      expect(formatFileSize(1048576)).toBe("1 MB");
      expect(formatFileSize(1572864)).toBe("1.5 MB");
      expect(formatFileSize(10485760)).toBe("10 MB");
    });

    it("should format GB correctly", () => {
      expect(formatFileSize(1073741824)).toBe("1 GB");
      expect(formatFileSize(1610612736)).toBe("1.5 GB");
    });

    it("should format TB correctly", () => {
      expect(formatFileSize(1099511627776)).toBe("1 TB");
    });
  });

  describe("getFileTypeCategory", () => {
    it("should categorize documents", () => {
      expect(getFileTypeCategory(".pdf")).toBe("document");
      expect(getFileTypeCategory(".doc")).toBe("document");
      expect(getFileTypeCategory(".docx")).toBe("document");
      expect(getFileTypeCategory(".txt")).toBe("document");
      expect(getFileTypeCategory(".rtf")).toBe("document");
      expect(getFileTypeCategory(".odt")).toBe("document");
    });

    it("should categorize spreadsheets", () => {
      expect(getFileTypeCategory(".xls")).toBe("spreadsheet");
      expect(getFileTypeCategory(".xlsx")).toBe("spreadsheet");
      expect(getFileTypeCategory(".csv")).toBe("spreadsheet");
    });

    it("should categorize presentations", () => {
      expect(getFileTypeCategory(".ppt")).toBe("presentation");
      expect(getFileTypeCategory(".pptx")).toBe("presentation");
    });

    it("should categorize images", () => {
      expect(getFileTypeCategory(".png")).toBe("image");
      expect(getFileTypeCategory(".jpg")).toBe("image");
      expect(getFileTypeCategory(".jpeg")).toBe("image");
      expect(getFileTypeCategory(".gif")).toBe("image");
      expect(getFileTypeCategory(".heic")).toBe("image");
      expect(getFileTypeCategory(".tiff")).toBe("image");
      expect(getFileTypeCategory(".bmp")).toBe("image");
    });

    it("should categorize videos", () => {
      expect(getFileTypeCategory(".mp4")).toBe("video");
      expect(getFileTypeCategory(".mov")).toBe("video");
      expect(getFileTypeCategory(".avi")).toBe("video");
    });

    it("should categorize audio", () => {
      expect(getFileTypeCategory(".mp3")).toBe("audio");
      expect(getFileTypeCategory(".m4a")).toBe("audio");
      expect(getFileTypeCategory(".wav")).toBe("audio");
    });

    it("should categorize archives", () => {
      expect(getFileTypeCategory(".zip")).toBe("archive");
      expect(getFileTypeCategory(".tar")).toBe("archive");
      expect(getFileTypeCategory(".gz")).toBe("archive");
    });

    it("should categorize config files", () => {
      expect(getFileTypeCategory(".plist")).toBe("config");
    });

    it("should return other for unknown extensions", () => {
      expect(getFileTypeCategory(".xyz")).toBe("other");
      expect(getFileTypeCategory(".unknown")).toBe("other");
      expect(getFileTypeCategory("")).toBe("other");
    });
  });

  describe("Type interfaces", () => {
    it("FileVerificationResult should have correct structure", () => {
      const result: FileVerificationResult = {
        filePath: "/test/file.pdf",
        exists: true,
        accessible: true,
        error: "",
      };

      expect(result.filePath).toBeDefined();
      expect(result.exists).toBeDefined();
      expect(result.accessible).toBeDefined();
      expect(result.error).toBeDefined();
    });

    it("FileInfo should have correct structure", () => {
      const fileInfo: FileInfo = {
        path: "/test/file.pdf",
        filename: "file.pdf",
        extension: ".pdf",
        sizeBytes: 1000,
        modifiedTime: "2024-01-01T00:00:00.000Z",
        inDatabase: false,
      };

      expect(fileInfo.path).toBeDefined();
      expect(fileInfo.filename).toBeDefined();
      expect(fileInfo.extension).toBeDefined();
      expect(fileInfo.sizeBytes).toBeDefined();
      expect(fileInfo.modifiedTime).toBeDefined();
      expect(fileInfo.inDatabase).toBeDefined();
    });

    it("ScanFolderOptions should have correct structure", () => {
      const options: ScanFolderOptions = {
        extensions: new Set([".pdf"]),
        recursive: true,
        maxDepth: 5,
        includeHidden: false,
      };

      expect(options.extensions).toBeDefined();
      expect(options.recursive).toBeDefined();
      expect(options.maxDepth).toBeDefined();
      expect(options.includeHidden).toBeDefined();
    });

    it("VerificationSummary should have correct structure", () => {
      const summary: VerificationSummary = {
        totalFiles: 10,
        filesAtTarget: 8,
        filesMissing: 1,
        filesInaccessible: 1,
        status: "partial",
        details: [],
        errors: ["Some error"],
      };

      expect(summary.totalFiles).toBeDefined();
      expect(summary.filesAtTarget).toBeDefined();
      expect(summary.filesMissing).toBeDefined();
      expect(summary.filesInaccessible).toBeDefined();
      expect(summary.status).toBeDefined();
      expect(summary.details).toBeDefined();
      expect(summary.errors).toBeDefined();
    });

    it("VerificationSummary status should be valid enum", () => {
      const verified: VerificationSummary = {
        totalFiles: 1,
        filesAtTarget: 1,
        filesMissing: 0,
        filesInaccessible: 0,
        status: "verified",
        details: [],
        errors: [],
      };
      expect(verified.status).toBe("verified");

      const partial: VerificationSummary = {
        totalFiles: 2,
        filesAtTarget: 1,
        filesMissing: 1,
        filesInaccessible: 0,
        status: "partial",
        details: [],
        errors: [],
      };
      expect(partial.status).toBe("partial");

      const failed: VerificationSummary = {
        totalFiles: 1,
        filesAtTarget: 0,
        filesMissing: 1,
        filesInaccessible: 0,
        status: "failed",
        details: [],
        errors: [],
      };
      expect(failed.status).toBe("failed");
    });
  });

  describe("Extension constants sync with Python organizer", () => {
    it("SUPPORTED_EXTENSIONS should match organizer/content_analyzer.py SUPPORTED_EXTENSIONS", () => {
      // These are the exact extensions from organizer/content_analyzer.py
      const pythonSupportedExtensions = new Set([
        ".pdf",
        ".doc",
        ".docx",
        ".txt",
        ".rtf",
        ".odt",
        ".xls",
        ".xlsx",
        ".csv",
        ".ppt",
        ".pptx",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".tiff",
        ".bmp",
      ]);

      // All Python extensions should be in our set
      for (const ext of pythonSupportedExtensions) {
        expect(SUPPORTED_EXTENSIONS.has(ext)).toBe(true);
      }

      // Our set should have same size
      expect(SUPPORTED_EXTENSIONS.size).toBe(pythonSupportedExtensions.size);
    });
  });
});

// Note: Tests for verifyFileAccessible, scanFolderForFiles, and generateVerificationSummary
// require actual filesystem access. These should be tested via integration tests.
