import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import path from "path";
import {
  parseExecutionLog,
  extractTimestampFromFilename,
  scanExecutionLogs,
  getExecutionLog,
  getFileMovementHistory,
  getFolderMovementHistory,
  getSourceFoldersFromLogs,
  type ExecutionLog,
  type ExecutionLogSummary,
  type FileMovementHistoryEntry,
} from "@/lib/execution-logs";

describe("Execution Logs Library", () => {
  let tempDir: string;
  let organizerDir: string;

  beforeEach(() => {
    // Create a temporary directory for each test
    tempDir = mkdtempSync(path.join(tmpdir(), "execution-logs-test-"));
    organizerDir = path.join(tempDir, ".organizer");
    mkdirSync(organizerDir, { recursive: true });
  });

  afterEach(() => {
    // Clean up temporary directory
    rmSync(tempDir, { recursive: true, force: true });
  });

  // ============================================================================
  // Helper function tests
  // ============================================================================

  describe("extractTimestampFromFilename", () => {
    it("should extract timestamp from valid filename", () => {
      const result = extractTimestampFromFilename("execution_log_20240115_103045.json");
      expect(result).toBe("2024-01-15T10:30:45");
    });

    it("should return empty string for invalid filename", () => {
      expect(extractTimestampFromFilename("invalid.json")).toBe("");
      expect(extractTimestampFromFilename("execution_log.json")).toBe("");
      expect(extractTimestampFromFilename("")).toBe("");
    });

    it("should handle edge cases", () => {
      expect(extractTimestampFromFilename("execution_log_20251231_235959.json")).toBe(
        "2025-12-31T23:59:59"
      );
      expect(extractTimestampFromFilename("execution_log_20000101_000000.json")).toBe(
        "2000-01-01T00:00:00"
      );
    });
  });

  describe("parseExecutionLog", () => {
    it("should parse a minimal execution log", () => {
      const rawLog = {
        execution_summary: {
          timestamp: "2024-01-15 10:30:45",
          plan_file: "/path/to/plan.json",
          base_path: "/home/user",
          total_groups: 2,
          groups_completed: 2,
          groups_failed: 0,
          total_files_moved: 10,
          total_files_failed: 0,
          status: "success",
          stopped_early: false,
          error: "",
          content_aware: false,
        },
        group_entries: [],
        rollback: {
          total_moves_to_undo: 0,
          instructions: [],
        },
      };

      const result = parseExecutionLog(rawLog, "execution_log_20240115_103045.json");

      expect(result.summary.logFile).toBe("execution_log_20240115_103045.json");
      expect(result.summary.timestamp).toBe("2024-01-15 10:30:45");
      expect(result.summary.planFile).toBe("/path/to/plan.json");
      expect(result.summary.basePath).toBe("/home/user");
      expect(result.summary.totalGroups).toBe(2);
      expect(result.summary.groupsCompleted).toBe(2);
      expect(result.summary.groupsFailed).toBe(0);
      expect(result.summary.totalFilesMoved).toBe(10);
      expect(result.summary.status).toBe("success");
      expect(result.summary.contentAware).toBe(false);
    });

    it("should parse group entries with rollback instructions", () => {
      const rawLog = {
        execution_summary: {
          timestamp: "2024-01-15 10:30:45",
          plan_file: "/path/to/plan.json",
          base_path: "/home/user",
          total_groups: 1,
          groups_completed: 1,
          groups_failed: 0,
          total_files_moved: 2,
          total_files_failed: 0,
          status: "success",
          stopped_early: false,
          error: "",
          content_aware: true,
        },
        group_entries: [
          {
            group_name: "Resumes",
            target_folder: "/home/user/Documents/Resumes",
            folders_processed: 2,
            files_moved: 2,
            files_failed: 0,
            status: "success",
            error: "",
            folder_entries: [
              {
                source_folder: "/home/user/Resume",
                target_folder: "/home/user/Documents/Resumes",
                files_moved: 1,
                files_failed: 0,
                status: "success",
                error: "",
              },
            ],
            rollback_instructions: [
              {
                current_path: "/home/user/Documents/Resumes/resume.pdf",
                original_path: "/home/user/Resume/resume.pdf",
                command: 'mv "/home/user/Documents/Resumes/resume.pdf" "/home/user/Resume/resume.pdf"',
              },
            ],
            content_analysis: {
              group_name: "Resumes",
              should_consolidate: true,
              decision_summary: "Same AI category",
              confidence: 0.8,
              ai_categories: ["employment"],
              date_ranges: { "2024": "2024" },
              reasoning: ["Folder matches category"],
            },
          },
        ],
        rollback: {
          total_moves_to_undo: 1,
          instructions: [
            {
              current_path: "/home/user/Documents/Resumes/resume.pdf",
              original_path: "/home/user/Resume/resume.pdf",
              command: 'mv "/home/user/Documents/Resumes/resume.pdf" "/home/user/Resume/resume.pdf"',
            },
          ],
        },
        content_analysis: {
          content_aware_mode: true,
          groups_analyzed: 1,
          groups_to_consolidate: 1,
          groups_to_skip: 0,
          ai_categories_found: { employment: 2 },
          date_ranges_found: ["2024"],
        },
      };

      const result = parseExecutionLog(rawLog, "execution_log_20240115_103045.json");

      expect(result.summary.contentAware).toBe(true);
      expect(result.groupEntries).toHaveLength(1);
      expect(result.groupEntries[0].groupName).toBe("Resumes");
      expect(result.groupEntries[0].filesMoved).toBe(2);
      expect(result.groupEntries[0].folderEntries).toHaveLength(1);
      expect(result.groupEntries[0].rollbackInstructions).toHaveLength(1);
      expect(result.groupEntries[0].contentAnalysis?.shouldConsolidate).toBe(true);
      expect(result.rollback.totalMovesToUndo).toBe(1);
      expect(result.contentAnalysis?.contentAwareMode).toBe(true);
      expect(result.contentAnalysis?.groupsAnalyzed).toBe(1);
    });

    it("should handle missing optional fields", () => {
      const rawLog = {
        execution_summary: {},
        group_entries: [],
        rollback: {},
      };

      const result = parseExecutionLog(rawLog, "test.json");

      expect(result.summary.timestamp).toBe("");
      expect(result.summary.totalGroups).toBe(0);
      expect(result.summary.contentAware).toBe(false);
      expect(result.groupEntries).toHaveLength(0);
      expect(result.rollback.totalMovesToUndo).toBe(0);
      expect(result.contentAnalysis).toBeUndefined();
    });
  });

  // ============================================================================
  // scanExecutionLogs tests
  // ============================================================================

  describe("scanExecutionLogs", () => {
    it("should return empty array for non-existent directory", () => {
      const result = scanExecutionLogs("/non/existent/path");
      expect(result.logs).toHaveLength(0);
      expect(result.totalLogs).toBe(0);
    });

    it("should return empty array for empty directory", () => {
      const result = scanExecutionLogs(organizerDir);
      expect(result.logs).toHaveLength(0);
      expect(result.totalLogs).toBe(0);
    });

    it("should find and parse execution log files", () => {
      // Create test log files
      const log1 = {
        execution_summary: {
          timestamp: "2024-01-15 10:30:45",
          plan_file: "/plan1.json",
          base_path: "/home",
          total_groups: 2,
          groups_completed: 2,
          groups_failed: 0,
          total_files_moved: 5,
          total_files_failed: 0,
          status: "success",
          content_aware: false,
        },
        group_entries: [],
        rollback: { total_moves_to_undo: 0, instructions: [] },
      };

      const log2 = {
        execution_summary: {
          timestamp: "2024-01-16 14:00:00",
          plan_file: "/plan2.json",
          base_path: "/home",
          total_groups: 3,
          groups_completed: 2,
          groups_failed: 1,
          total_files_moved: 8,
          total_files_failed: 2,
          status: "partial",
          content_aware: true,
        },
        group_entries: [],
        rollback: { total_moves_to_undo: 0, instructions: [] },
      };

      writeFileSync(
        path.join(organizerDir, "execution_log_20240115_103045.json"),
        JSON.stringify(log1)
      );
      writeFileSync(
        path.join(organizerDir, "execution_log_20240116_140000.json"),
        JSON.stringify(log2)
      );

      const result = scanExecutionLogs(organizerDir);

      expect(result.logs).toHaveLength(2);
      expect(result.totalLogs).toBe(2);
      // Should be sorted by timestamp descending (most recent first)
      expect(result.logs[0].timestamp).toBe("2024-01-16 14:00:00");
      expect(result.logs[1].timestamp).toBe("2024-01-15 10:30:45");
    });

    it("should ignore non-log files", () => {
      // Create test files
      writeFileSync(
        path.join(organizerDir, "execution_log_20240115_103045.json"),
        JSON.stringify({
          execution_summary: { timestamp: "2024-01-15" },
          group_entries: [],
          rollback: {},
        })
      );
      writeFileSync(path.join(organizerDir, "other_file.json"), "{}");
      writeFileSync(path.join(organizerDir, "plan_backup.json"), "{}");

      const result = scanExecutionLogs(organizerDir);

      expect(result.logs).toHaveLength(1);
      expect(result.logs[0].logFile).toBe("execution_log_20240115_103045.json");
    });

    it("should skip invalid JSON files", () => {
      writeFileSync(
        path.join(organizerDir, "execution_log_20240115_103045.json"),
        "invalid json"
      );
      writeFileSync(
        path.join(organizerDir, "execution_log_20240116_140000.json"),
        JSON.stringify({
          execution_summary: { timestamp: "2024-01-16" },
          group_entries: [],
          rollback: {},
        })
      );

      const result = scanExecutionLogs(organizerDir);

      expect(result.logs).toHaveLength(1);
      expect(result.logs[0].timestamp).toBe("2024-01-16");
    });

    it("should return error for non-directory path", () => {
      const filePath = path.join(tempDir, "file.txt");
      writeFileSync(filePath, "test");

      const result = scanExecutionLogs(filePath);

      expect(result.logs).toHaveLength(0);
      expect(result.error).toBe("Not a directory");
    });
  });

  // ============================================================================
  // getExecutionLog tests
  // ============================================================================

  describe("getExecutionLog", () => {
    it("should return error for non-existent log file", () => {
      const result = getExecutionLog(organizerDir, "non_existent.json");
      expect(result.log).toBeNull();
      expect(result.error).toBe("Log file not found");
    });

    it("should return full log for valid file", () => {
      const logData = {
        execution_summary: {
          timestamp: "2024-01-15 10:30:45",
          plan_file: "/plan.json",
          base_path: "/home",
          total_groups: 2,
          groups_completed: 2,
          groups_failed: 0,
          total_files_moved: 5,
          total_files_failed: 0,
          status: "success",
        },
        group_entries: [
          {
            group_name: "Test",
            target_folder: "/target",
            folders_processed: 1,
            files_moved: 5,
            files_failed: 0,
            status: "success",
            error: "",
            folder_entries: [],
            rollback_instructions: [],
          },
        ],
        rollback: { total_moves_to_undo: 0, instructions: [] },
      };

      writeFileSync(
        path.join(organizerDir, "execution_log_20240115_103045.json"),
        JSON.stringify(logData)
      );

      const result = getExecutionLog(organizerDir, "execution_log_20240115_103045.json");

      expect(result.log).not.toBeNull();
      expect(result.log?.summary.totalFilesMoved).toBe(5);
      expect(result.log?.groupEntries).toHaveLength(1);
    });

    it("should return error for invalid JSON", () => {
      writeFileSync(
        path.join(organizerDir, "execution_log_20240115_103045.json"),
        "invalid json"
      );

      const result = getExecutionLog(organizerDir, "execution_log_20240115_103045.json");

      expect(result.log).toBeNull();
      expect(result.error).toBeDefined();
    });
  });

  // ============================================================================
  // getFileMovementHistory tests
  // ============================================================================

  describe("getFileMovementHistory", () => {
    it("should return empty array for no logs", () => {
      const result = getFileMovementHistory(organizerDir);
      expect(result.movements).toHaveLength(0);
      expect(result.totalMovements).toBe(0);
    });

    it("should extract file movements from logs", () => {
      const logData = {
        execution_summary: {
          timestamp: "2024-01-15 10:30:45",
          plan_file: "/plan.json",
          base_path: "/home",
          total_groups: 1,
          groups_completed: 1,
          groups_failed: 0,
          total_files_moved: 2,
          total_files_failed: 0,
          status: "success",
        },
        group_entries: [
          {
            group_name: "Resumes",
            target_folder: "/home/Documents/Resumes",
            folders_processed: 1,
            files_moved: 2,
            files_failed: 0,
            status: "success",
            error: "",
            folder_entries: [],
            rollback_instructions: [
              {
                current_path: "/home/Documents/Resumes/resume1.pdf",
                original_path: "/home/Resume/resume1.pdf",
                command: 'mv "/home/Documents/Resumes/resume1.pdf" "/home/Resume/resume1.pdf"',
              },
              {
                current_path: "/home/Documents/Resumes/resume2.pdf",
                original_path: "/home/CV/resume2.pdf",
                command: 'mv "/home/Documents/Resumes/resume2.pdf" "/home/CV/resume2.pdf"',
              },
            ],
          },
        ],
        rollback: { total_moves_to_undo: 2, instructions: [] },
      };

      writeFileSync(
        path.join(organizerDir, "execution_log_20240115_103045.json"),
        JSON.stringify(logData)
      );

      const result = getFileMovementHistory(organizerDir);

      expect(result.movements).toHaveLength(2);
      expect(result.totalMovements).toBe(2);

      // Check first movement
      expect(result.movements[0].fileName).toBe("resume1.pdf");
      expect(result.movements[0].originalPath).toBe("/home/Resume/resume1.pdf");
      expect(result.movements[0].currentPath).toBe("/home/Documents/Resumes/resume1.pdf");
      expect(result.movements[0].groupName).toBe("Resumes");
      expect(result.movements[0].sourceFolder).toBe("/home/Resume");
    });

    it("should combine movements from multiple logs", () => {
      const log1 = {
        execution_summary: {
          timestamp: "2024-01-15 10:00:00",
          status: "success",
        },
        group_entries: [
          {
            group_name: "Group1",
            target_folder: "/target1",
            rollback_instructions: [
              {
                current_path: "/target1/file1.pdf",
                original_path: "/source1/file1.pdf",
                command: "mv",
              },
            ],
          },
        ],
        rollback: {},
      };

      const log2 = {
        execution_summary: {
          timestamp: "2024-01-16 10:00:00",
          status: "success",
        },
        group_entries: [
          {
            group_name: "Group2",
            target_folder: "/target2",
            rollback_instructions: [
              {
                current_path: "/target2/file2.pdf",
                original_path: "/source2/file2.pdf",
                command: "mv",
              },
            ],
          },
        ],
        rollback: {},
      };

      writeFileSync(
        path.join(organizerDir, "execution_log_20240115_100000.json"),
        JSON.stringify(log1)
      );
      writeFileSync(
        path.join(organizerDir, "execution_log_20240116_100000.json"),
        JSON.stringify(log2)
      );

      const result = getFileMovementHistory(organizerDir);

      expect(result.movements).toHaveLength(2);
      // Should be sorted by timestamp descending
      expect(result.movements[0].groupName).toBe("Group2");
      expect(result.movements[1].groupName).toBe("Group1");
    });
  });

  // ============================================================================
  // getFolderMovementHistory tests
  // ============================================================================

  describe("getFolderMovementHistory", () => {
    it("should filter movements by folder path", () => {
      const logData = {
        execution_summary: {
          timestamp: "2024-01-15 10:30:45",
          status: "success",
        },
        group_entries: [
          {
            group_name: "Resumes",
            target_folder: "/home/Documents/Resumes",
            rollback_instructions: [
              {
                current_path: "/home/Documents/Resumes/resume1.pdf",
                original_path: "/home/Resume/resume1.pdf",
                command: "mv",
              },
              {
                current_path: "/home/Documents/Resumes/resume2.pdf",
                original_path: "/home/CV/resume2.pdf",
                command: "mv",
              },
              {
                current_path: "/home/Documents/Resumes/cv.pdf",
                original_path: "/home/Resume/cv.pdf",
                command: "mv",
              },
            ],
          },
        ],
        rollback: {},
      };

      writeFileSync(
        path.join(organizerDir, "execution_log_20240115_103045.json"),
        JSON.stringify(logData)
      );

      const result = getFolderMovementHistory(organizerDir, "/home/Resume");

      expect(result.movements).toHaveLength(2);
      expect(result.movements.every((m) => m.sourceFolder === "/home/Resume")).toBe(true);
    });

    it("should return empty array for folder with no movements", () => {
      const logData = {
        execution_summary: {
          timestamp: "2024-01-15 10:30:45",
          status: "success",
        },
        group_entries: [
          {
            group_name: "Test",
            target_folder: "/target",
            rollback_instructions: [
              {
                current_path: "/target/file.pdf",
                original_path: "/source/file.pdf",
                command: "mv",
              },
            ],
          },
        ],
        rollback: {},
      };

      writeFileSync(
        path.join(organizerDir, "execution_log_20240115_103045.json"),
        JSON.stringify(logData)
      );

      const result = getFolderMovementHistory(organizerDir, "/other/folder");

      expect(result.movements).toHaveLength(0);
    });
  });

  // ============================================================================
  // getSourceFoldersFromLogs tests
  // ============================================================================

  describe("getSourceFoldersFromLogs", () => {
    it("should return unique source folders", () => {
      const logData = {
        execution_summary: {
          timestamp: "2024-01-15 10:30:45",
          status: "success",
        },
        group_entries: [
          {
            group_name: "Test",
            target_folder: "/target",
            rollback_instructions: [
              {
                current_path: "/target/file1.pdf",
                original_path: "/source1/file1.pdf",
                command: "mv",
              },
              {
                current_path: "/target/file2.pdf",
                original_path: "/source1/file2.pdf",
                command: "mv",
              },
              {
                current_path: "/target/file3.pdf",
                original_path: "/source2/file3.pdf",
                command: "mv",
              },
            ],
          },
        ],
        rollback: {},
      };

      writeFileSync(
        path.join(organizerDir, "execution_log_20240115_103045.json"),
        JSON.stringify(logData)
      );

      const result = getSourceFoldersFromLogs(organizerDir);

      expect(result.folders).toHaveLength(2);
      expect(result.folders).toContain("/source1");
      expect(result.folders).toContain("/source2");
    });

    it("should return empty array for no logs", () => {
      const result = getSourceFoldersFromLogs(organizerDir);
      expect(result.folders).toHaveLength(0);
    });

    it("should return sorted folders", () => {
      const logData = {
        execution_summary: { timestamp: "2024-01-15", status: "success" },
        group_entries: [
          {
            group_name: "Test",
            target_folder: "/target",
            rollback_instructions: [
              { current_path: "/t/f.pdf", original_path: "/z/f.pdf", command: "mv" },
              { current_path: "/t/g.pdf", original_path: "/a/g.pdf", command: "mv" },
              { current_path: "/t/h.pdf", original_path: "/m/h.pdf", command: "mv" },
            ],
          },
        ],
        rollback: {},
      };

      writeFileSync(
        path.join(organizerDir, "execution_log_20240115_103045.json"),
        JSON.stringify(logData)
      );

      const result = getSourceFoldersFromLogs(organizerDir);

      expect(result.folders).toEqual(["/a", "/m", "/z"]);
    });
  });

  // ============================================================================
  // Type structure tests
  // ============================================================================

  describe("Type structures", () => {
    it("should have correct ExecutionLogSummary structure", () => {
      const summary: ExecutionLogSummary = {
        logFile: "test.json",
        timestamp: "2024-01-15",
        planFile: "/plan.json",
        basePath: "/home",
        totalGroups: 2,
        groupsCompleted: 2,
        groupsFailed: 0,
        totalFilesMoved: 10,
        totalFilesFailed: 0,
        status: "success",
        stoppedEarly: false,
        error: "",
        contentAware: true,
      };

      expect(summary.logFile).toBeDefined();
      expect(summary.contentAware).toBe(true);
    });

    it("should have correct FileMovementHistoryEntry structure", () => {
      const entry: FileMovementHistoryEntry = {
        fileName: "test.pdf",
        originalPath: "/old/test.pdf",
        currentPath: "/new/test.pdf",
        movedAt: "2024-01-15",
        groupName: "Test",
        sourceFolder: "/old",
        targetFolder: "/new",
        logFile: "execution_log.json",
      };

      expect(entry.fileName).toBeDefined();
      expect(entry.sourceFolder).toBeDefined();
      expect(entry.logFile).toBeDefined();
    });
  });
});
