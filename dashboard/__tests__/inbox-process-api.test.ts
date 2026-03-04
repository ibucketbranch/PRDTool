/**
 * Tests for /api/inbox-process endpoint
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "@/app/api/inbox-process/route";
import * as fs from "fs/promises";

// Mock fs module
vi.mock("fs/promises", () => ({
  access: vi.fn(),
  readdir: vi.fn(),
}));

// Mock child_process
vi.mock("child_process", () => ({
  default: {
    exec: vi.fn(),
    spawn: vi.fn(),
  },
  exec: vi.fn(),
  spawn: vi.fn(),
}));

describe("/api/inbox-process", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("GET - Check inbox status", () => {
    it("should return inbox status with file counts", async () => {
      // Mock file system
      (fs.access as any).mockResolvedValue(undefined);
      (fs.readdir as any)
        .mockResolvedValueOnce(["file1.pdf", "file2.docx", "file3.txt"]) // Inbox
        .mockResolvedValueOnce(["processed1.pdf"]) // Processed
        .mockResolvedValueOnce(["error1.pdf", "error_log.txt"]); // Errors

      const request = new NextRequest("http://localhost/api/inbox-process");
      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.inbox?.fileCount).toBe(3);
      expect(data.processed?.count).toBe(1);
      expect(data.errors?.count).toBe(1); // Should exclude .txt error logs
    });

    it("should return 404 if inbox doesn't exist", async () => {
      (fs.access as any).mockRejectedValue(new Error("Not found"));

      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.success).toBe(false);
    });
  });

  describe("POST - Process inbox", () => {
    it("should validate action parameter", async () => {
      const request = new NextRequest(
        "http://localhost/api/inbox-process?action=invalid"
      );

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.message).toContain("Invalid action");
    });

    it("should accept process action", async () => {
      const request = new NextRequest(
        "http://localhost/api/inbox-process?action=process&dryRun=true"
      );

      // Mock spawn to return success
      const { spawn } = await import("child_process");
      const mockChild = {
        stdout: { on: vi.fn() },
        stderr: { on: vi.fn() },
        on: vi.fn((event, callback) => {
          if (event === "close") {
            setTimeout(() => callback(0), 10); // Simulate success
          }
        }),
      };
      (spawn as any).mockReturnValue(mockChild);

      const response = await POST(request);
      const data = await response.json();

      // Should attempt to process
      expect(spawn).toHaveBeenCalled();
    });

    it("should accept finalize action", async () => {
      const request = new NextRequest(
        "http://localhost/api/inbox-process?action=finalize&dryRun=true"
      );

      const { spawn } = await import("child_process");
      const mockChild = {
        stdout: { on: vi.fn() },
        stderr: { on: vi.fn() },
        on: vi.fn((event, callback) => {
          if (event === "close") {
            setTimeout(() => callback(0), 10);
          }
        }),
      };
      (spawn as any).mockReturnValue(mockChild);

      const response = await POST(request);

      expect(spawn).toHaveBeenCalled();
      const args = (spawn as any).mock.calls[0];
      expect(args[1]).toContain("--finalize");
    });

    it("should accept retry-errors action", async () => {
      const request = new NextRequest(
        "http://localhost/api/inbox-process?action=retry-errors&dryRun=true"
      );

      const { spawn } = await import("child_process");
      const mockChild = {
        stdout: { on: vi.fn() },
        stderr: { on: vi.fn() },
        on: vi.fn((event, callback) => {
          if (event === "close") {
            setTimeout(() => callback(0), 10);
          }
        }),
      };
      (spawn as any).mockReturnValue(mockChild);

      const response = await POST(request);

      expect(spawn).toHaveBeenCalled();
      const args = (spawn as any).mock.calls[0];
      expect(args[1]).toContain("--retry-errors");
    });
  });
});
