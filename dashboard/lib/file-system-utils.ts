/**
 * File System Utilities for Dashboard Phase 6
 *
 * This module provides file system operations that integrate with the
 * Python organizer module patterns (organizer/post_verification.py,
 * organizer/content_analyzer.py).
 *
 * Integration points:
 * - verify_file_accessible() pattern from organizer/post_verification.py
 * - scan_folder_for_files() pattern from organizer/content_analyzer.py
 * - SUPPORTED_EXTENSIONS synced with organizer/content_analyzer.py
 */

import { existsSync, statSync, readdirSync } from "fs";
import path from "path";

/**
 * Supported file extensions for document processing.
 * Synchronized with organizer/content_analyzer.py SUPPORTED_EXTENSIONS
 */
export const SUPPORTED_EXTENSIONS = new Set([
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

/**
 * Additional extensions to scan (beyond document processing)
 */
export const ADDITIONAL_SCAN_EXTENSIONS = new Set([
  ".heic",
  ".mp4",
  ".mov",
  ".avi",
  ".mp3",
  ".m4a",
  ".wav",
  ".plist",
  ".zip",
  ".tar",
  ".gz",
]);

/**
 * All extensions to scan for orphaned files
 */
export const ALL_SCAN_EXTENSIONS = new Set([
  ...SUPPORTED_EXTENSIONS,
  ...ADDITIONAL_SCAN_EXTENSIONS,
]);

/**
 * Result of verifying file accessibility.
 * Mirrors organizer/post_verification.py FileVerificationResult
 */
export interface FileVerificationResult {
  filePath: string;
  exists: boolean;
  accessible: boolean;
  error: string;
}

/**
 * Verify that a single file exists and is accessible.
 * Mirrors organizer/post_verification.py verify_file_accessible()
 *
 * @param filePath - Path to the file to verify
 * @returns FileVerificationResult with accessibility status
 */
export function verifyFileAccessible(filePath: string): FileVerificationResult {
  try {
    if (!existsSync(filePath)) {
      return {
        filePath,
        exists: false,
        accessible: false,
        error: "File does not exist",
      };
    }

    // Try to read file metadata to verify accessibility
    statSync(filePath);

    return {
      filePath,
      exists: true,
      accessible: true,
      error: "",
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";

    if (errorMessage.includes("EACCES") || errorMessage.includes("permission")) {
      return {
        filePath,
        exists: true,
        accessible: false,
        error: `Permission denied: ${errorMessage}`,
      };
    }

    return {
      filePath,
      exists: false,
      accessible: false,
      error: `OS error: ${errorMessage}`,
    };
  }
}

/**
 * Batch verify multiple files for accessibility.
 *
 * @param filePaths - Array of file paths to verify
 * @returns Array of FileVerificationResult
 */
export function verifyFilesAccessible(filePaths: string[]): FileVerificationResult[] {
  return filePaths.map((filePath) => verifyFileAccessible(filePath));
}

/**
 * File information returned from scanning.
 * Mirrors organizer/content_analyzer.py FileInfo
 */
export interface FileInfo {
  path: string;
  filename: string;
  extension: string;
  sizeBytes: number;
  modifiedTime: string;
  inDatabase: boolean;
}

/**
 * Options for scanning a folder.
 */
export interface ScanFolderOptions {
  /** File extensions to include. If null, includes all supported extensions */
  extensions?: Set<string> | null;
  /** Whether to scan subdirectories recursively. Default: true */
  recursive?: boolean;
  /** Maximum depth for recursive scanning. Default: 10 */
  maxDepth?: number;
  /** Whether to include hidden files. Default: false */
  includeHidden?: boolean;
}

/**
 * Scan a folder for files, optionally filtering by extension.
 * Mirrors organizer/content_analyzer.py scan_folder_for_files()
 *
 * This is the first step in the document-first approach: find all actual files
 * on disk before checking the database.
 *
 * @param folderPath - Path to the folder to scan
 * @param options - Scan options
 * @returns Array of FileInfo objects for files found in the folder
 */
export function scanFolderForFiles(
  folderPath: string,
  options: ScanFolderOptions = {}
): FileInfo[] {
  const {
    extensions = ALL_SCAN_EXTENSIONS,
    recursive = true,
    maxDepth = 10,
    includeHidden = false,
  } = options;

  const resolvedPath = path.resolve(folderPath);
  const files: FileInfo[] = [];

  if (!existsSync(resolvedPath)) {
    return files;
  }

  // Check if it's a directory
  try {
    const stats = statSync(resolvedPath);
    if (!stats.isDirectory()) {
      return files;
    }
  } catch {
    return files;
  }

  function scanDir(dirPath: string, currentDepth: number) {
    if (currentDepth > maxDepth) {
      return;
    }

    try {
      const entries = readdirSync(dirPath, { withFileTypes: true });

      for (const entry of entries) {
        // Skip hidden files/directories unless explicitly included
        if (!includeHidden && entry.name.startsWith(".")) {
          continue;
        }

        const fullPath = path.join(dirPath, entry.name);

        if (entry.isDirectory() && recursive) {
          scanDir(fullPath, currentDepth + 1);
        } else if (entry.isFile()) {
          const ext = path.extname(entry.name).toLowerCase();

          // Include file if extensions is null (include all) or extension is in set
          if (extensions === null || extensions.has(ext)) {
            try {
              const stats = statSync(fullPath);
              files.push({
                path: fullPath,
                filename: entry.name,
                extension: ext,
                sizeBytes: stats.size,
                modifiedTime: stats.mtime.toISOString(),
                inDatabase: false, // Will be set by caller after checking database
              });
            } catch {
              // Skip files that can't be accessed
            }
          }
        }
      }
    } catch {
      // Skip directories that can't be read
    }
  }

  scanDir(resolvedPath, 0);

  return files;
}

/**
 * Result of scanning a folder with database comparison.
 */
export interface ScanWithDatabaseResult {
  /** All files found in the folder */
  allFiles: FileInfo[];
  /** Files that are in the database */
  filesInDatabase: FileInfo[];
  /** Files that are NOT in the database (orphaned) */
  orphanedFiles: FileInfo[];
  /** Total count of scanned files */
  totalScanned: number;
  /** Count of files in database */
  inDatabaseCount: number;
  /** Count of orphaned files */
  orphanedCount: number;
}

/**
 * Check if a file extension is supported for document processing.
 *
 * @param extension - File extension (including the dot, e.g., ".pdf")
 * @returns True if the extension is supported for processing
 */
export function isProcessableExtension(extension: string): boolean {
  return SUPPORTED_EXTENSIONS.has(extension.toLowerCase());
}

/**
 * Get human-readable file size.
 *
 * @param bytes - File size in bytes
 * @returns Formatted file size string
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 Bytes";

  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

/**
 * Extract file type category from extension.
 *
 * @param extension - File extension (including the dot)
 * @returns File type category string
 */
export function getFileTypeCategory(extension: string): string {
  const ext = extension.toLowerCase();

  // Documents
  if ([".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"].includes(ext)) {
    return "document";
  }

  // Spreadsheets
  if ([".xls", ".xlsx", ".csv"].includes(ext)) {
    return "spreadsheet";
  }

  // Presentations
  if ([".ppt", ".pptx"].includes(ext)) {
    return "presentation";
  }

  // Images
  if ([".png", ".jpg", ".jpeg", ".gif", ".tiff", ".bmp", ".heic"].includes(ext)) {
    return "image";
  }

  // Videos
  if ([".mp4", ".mov", ".avi"].includes(ext)) {
    return "video";
  }

  // Audio
  if ([".mp3", ".m4a", ".wav"].includes(ext)) {
    return "audio";
  }

  // Archives
  if ([".zip", ".tar", ".gz"].includes(ext)) {
    return "archive";
  }

  // System/config
  if ([".plist"].includes(ext)) {
    return "config";
  }

  return "other";
}

/**
 * Verification summary for multiple files.
 */
export interface VerificationSummary {
  totalFiles: number;
  filesAtTarget: number;
  filesMissing: number;
  filesInaccessible: number;
  status: "verified" | "partial" | "failed";
  details: FileVerificationResult[];
  errors: string[];
}

/**
 * Generate a verification summary for multiple files.
 * Similar to organizer/post_verification.py verify_files_at_new_locations()
 *
 * @param filePaths - Array of file paths to verify
 * @returns VerificationSummary with details
 */
export function generateVerificationSummary(filePaths: string[]): VerificationSummary {
  const details = verifyFilesAccessible(filePaths);
  const errors: string[] = [];

  let filesAtTarget = 0;
  let filesMissing = 0;
  let filesInaccessible = 0;

  for (const result of details) {
    if (result.exists && result.accessible) {
      filesAtTarget++;
    } else if (result.exists && !result.accessible) {
      filesInaccessible++;
      errors.push(`File inaccessible at ${result.filePath}: ${result.error}`);
    } else {
      filesMissing++;
      errors.push(`File missing at ${result.filePath}: ${result.error}`);
    }
  }

  let status: "verified" | "partial" | "failed";
  if (filesMissing > 0 || filesInaccessible > 0) {
    status = filesAtTarget > 0 ? "partial" : "failed";
  } else {
    status = "verified";
  }

  return {
    totalFiles: filePaths.length,
    filesAtTarget,
    filesMissing,
    filesInaccessible,
    status,
    details,
    errors,
  };
}
