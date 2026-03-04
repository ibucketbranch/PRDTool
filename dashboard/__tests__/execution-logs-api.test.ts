import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import path from "path";
import { GET } from "@/app/api/execution-logs/route";

describe("Execution Logs API", () => {
  let tempDir: string;
  let organizerDir: string;

  beforeEach(() => {
    // Create a temporary directory for each test
    tempDir = mkdtempSync(path.join(tmpdir(), "execution-logs-api-test-"));
    organizerDir = path.join(tempDir, ".organizer");
    mkdirSync(organizerDir, { recursive: true });
  });

  afterEach(() => {
    // Clean up temporary directory
    rmSync(tempDir, { recursive: true, force: true });
  });

  // Helper to create a NextRequest with query params
  function createRequest(
    params: Record<string, string>
  ): NextRequest {
    const url = new URL("http://localhost/api/execution-logs");
    for (const [key, value] of Object.entries(params)) {
      url.searchParams.set(key, value);
    }
    return new NextRequest(url);
  }

  // Helper to create a sample log file
  function createSampleLogFile(
    filename: string,
    data?: Record<string, unknown>
  ): void {
    const defaultData = {
      execution_summary: {
        timestamp: "2024-01-15 10:30:45",
        plan_file: "/plan.json",
        base_path: tempDir,
        total_groups: 2,
        groups_completed: 2,
        groups_failed: 0,
        total_files_moved: 5,
        total_files_failed: 0,
        status: "success",
        stopped_early: false,
        error: "",
        content_aware: false,
      },
      group_entries: [],
      rollback: { total_moves_to_undo: 0, instructions: [] },
    };

    writeFileSync(
      path.join(organizerDir, filename),
      JSON.stringify(data || defaultData)
    );
  }

  // ============================================================================
  // Validation tests
  // ============================================================================

  describe("Parameter validation", () => {
    it("should return 400 if basePath is missing", async () => {
      const request = createRequest({});
      const response = await GET(request);

      expect(response.status).toBe(400);
      const data = await response.json();
      expect(data.error).toBe("basePath parameter is required");
    });

    it("should return 400 for unknown action", async () => {
      const request = createRequest({
        basePath: tempDir,
        action: "unknown",
      });
      const response = await GET(request);

      expect(response.status).toBe(400);
      const data = await response.json();
      expect(data.error).toContain("Unknown action");
    });
  });

  // ============================================================================
  // action=list tests
  // ============================================================================

  describe("action=list", () => {
    it("should return empty array for no logs", async () => {
      const request = createRequest({
        basePath: tempDir,
        action: "list",
      });
      const response = await GET(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.logs).toHaveLength(0);
      expect(data.totalLogs).toBe(0);
    });

    it("should return logs when they exist", async () => {
      createSampleLogFile("execution_log_20240115_103045.json");
      createSampleLogFile("execution_log_20240116_140000.json", {
        execution_summary: {
          timestamp: "2024-01-16 14:00:00",
          status: "success",
        },
        group_entries: [],
        rollback: {},
      });

      const request = createRequest({
        basePath: tempDir,
        action: "list",
      });
      const response = await GET(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.logs).toHaveLength(2);
      expect(data.totalLogs).toBe(2);
    });

    it("should default to list action", async () => {
      createSampleLogFile("execution_log_20240115_103045.json");

      const request = createRequest({
        basePath: tempDir,
      });
      const response = await GET(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.logs).toHaveLength(1);
    });
  });

  // ============================================================================
  // action=get tests
  // ============================================================================

  describe("action=get", () => {
    it("should return 400 if logFile is missing", async () => {
      const request = createRequest({
        basePath: tempDir,
        action: "get",
      });
      const response = await GET(request);

      expect(response.status).toBe(400);
      const data = await response.json();
      expect(data.error).toBe("logFile parameter is required when action=get");
    });

    it("should return 400 for path traversal attempt", async () => {
      const request = createRequest({
        basePath: tempDir,
        action: "get",
        logFile: "../../../etc/passwd",
      });
      const response = await GET(request);

      expect(response.status).toBe(400);
      const data = await response.json();
      expect(data.error).toBe("Invalid log file name");
    });

    it("should return 404 for non-existent log file", async () => {
      const request = createRequest({
        basePath: tempDir,
        action: "get",
        logFile: "non_existent.json",
      });
      const response = await GET(request);

      expect(response.status).toBe(404);
      const data = await response.json();
      expect(data.error).toBe("Log file not found");
    });

    it("should return full log for valid file", async () => {
      const logData = {
        execution_summary: {
          timestamp: "2024-01-15 10:30:45",
          plan_file: "/plan.json",
          base_path: tempDir,
          total_groups: 2,
          groups_completed: 2,
          groups_failed: 0,
          total_files_moved: 10,
          total_files_failed: 0,
          status: "success",
        },
        group_entries: [
          {
            group_name: "TestGroup",
            target_folder: "/target",
            folders_processed: 1,
            files_moved: 10,
            files_failed: 0,
            status: "success",
            error: "",
            folder_entries: [],
            rollback_instructions: [],
          },
        ],
        rollback: { total_moves_to_undo: 0, instructions: [] },
      };

      createSampleLogFile("execution_log_20240115_103045.json", logData);

      const request = createRequest({
        basePath: tempDir,
        action: "get",
        logFile: "execution_log_20240115_103045.json",
      });
      const response = await GET(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.log).not.toBeNull();
      expect(data.log.summary.totalFilesMoved).toBe(10);
      expect(data.log.groupEntries).toHaveLength(1);
      expect(data.log.groupEntries[0].groupName).toBe("TestGroup");
    });
  });

  // ============================================================================
  // action=history tests
  // ============================================================================

  describe("action=history", () => {
    it("should return empty array for no movements", async () => {
      createSampleLogFile("execution_log_20240115_103045.json");

      const request = createRequest({
        basePath: tempDir,
        action: "history",
      });
      const response = await GET(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.movements).toHaveLength(0);
      expect(data.totalMovements).toBe(0);
    });

    it("should return file movements from logs", async () => {
      const logData = {
        execution_summary: {
          timestamp: "2024-01-15 10:30:45",
          status: "success",
        },
        group_entries: [
          {
            group_name: "Resumes",
            target_folder: "/target/Resumes",
            folders_processed: 1,
            files_moved: 2,
            files_failed: 0,
            status: "success",
            error: "",
            folder_entries: [],
            rollback_instructions: [
              {
                current_path: "/target/Resumes/resume1.pdf",
                original_path: "/source/Resume/resume1.pdf",
                command: "mv",
              },
              {
                current_path: "/target/Resumes/resume2.pdf",
                original_path: "/source/CV/resume2.pdf",
                command: "mv",
              },
            ],
          },
        ],
        rollback: { total_moves_to_undo: 2, instructions: [] },
      };

      createSampleLogFile("execution_log_20240115_103045.json", logData);

      const request = createRequest({
        basePath: tempDir,
        action: "history",
      });
      const response = await GET(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.movements).toHaveLength(2);
      expect(data.totalMovements).toBe(2);
      expect(data.movements[0].fileName).toBe("resume1.pdf");
    });
  });

  // ============================================================================
  // action=folder-history tests
  // ============================================================================

  describe("action=folder-history", () => {
    it("should return 400 if folderPath is missing", async () => {
      const request = createRequest({
        basePath: tempDir,
        action: "folder-history",
      });
      const response = await GET(request);

      expect(response.status).toBe(400);
      const data = await response.json();
      expect(data.error).toBe(
        "folderPath parameter is required when action=folder-history"
      );
    });

    it("should return 400 for relative folderPath", async () => {
      const request = createRequest({
        basePath: tempDir,
        action: "folder-history",
        folderPath: "relative/path",
      });
      const response = await GET(request);

      expect(response.status).toBe(400);
      const data = await response.json();
      expect(data.error).toBe("folderPath must be an absolute path");
    });

    it("should return filtered movements for folder", async () => {
      const logData = {
        execution_summary: {
          timestamp: "2024-01-15 10:30:45",
          status: "success",
        },
        group_entries: [
          {
            group_name: "Resumes",
            target_folder: "/target/Resumes",
            rollback_instructions: [
              {
                current_path: "/target/Resumes/resume1.pdf",
                original_path: "/source/Resume/resume1.pdf",
                command: "mv",
              },
              {
                current_path: "/target/Resumes/resume2.pdf",
                original_path: "/source/CV/resume2.pdf",
                command: "mv",
              },
              {
                current_path: "/target/Resumes/cv.pdf",
                original_path: "/source/Resume/cv.pdf",
                command: "mv",
              },
            ],
          },
        ],
        rollback: {},
      };

      createSampleLogFile("execution_log_20240115_103045.json", logData);

      const request = createRequest({
        basePath: tempDir,
        action: "folder-history",
        folderPath: "/source/Resume",
      });
      const response = await GET(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.movements).toHaveLength(2);
      expect(data.movements.every((m: { sourceFolder: string }) => m.sourceFolder === "/source/Resume")).toBe(
        true
      );
    });

    it("should return empty array for folder with no movements", async () => {
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

      createSampleLogFile("execution_log_20240115_103045.json", logData);

      const request = createRequest({
        basePath: tempDir,
        action: "folder-history",
        folderPath: "/other/folder",
      });
      const response = await GET(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.movements).toHaveLength(0);
    });
  });

  // ============================================================================
  // Error handling tests
  // ============================================================================

  describe("Error handling", () => {
    it("should handle non-existent basePath gracefully for list", async () => {
      const request = createRequest({
        basePath: "/non/existent/path",
        action: "list",
      });
      const response = await GET(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.logs).toHaveLength(0);
      expect(data.totalLogs).toBe(0);
    });

    it("should handle invalid JSON in log file", async () => {
      writeFileSync(
        path.join(organizerDir, "execution_log_20240115_103045.json"),
        "invalid json"
      );

      const request = createRequest({
        basePath: tempDir,
        action: "get",
        logFile: "execution_log_20240115_103045.json",
      });
      const response = await GET(request);

      expect(response.status).toBe(500);
      const data = await response.json();
      expect(data.error).toBeDefined();
    });
  });
});
