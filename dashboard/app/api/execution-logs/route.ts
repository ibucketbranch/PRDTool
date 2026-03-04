import { NextRequest, NextResponse } from "next/server";
import path from "path";
import {
  scanExecutionLogs,
  getExecutionLog,
  getFileMovementHistory,
  getFolderMovementHistory,
  ExecutionLogSummary,
  ExecutionLog,
  FileMovementHistoryEntry,
} from "@/lib/execution-logs";

// Default organizer directory path (can be overridden via query param)
const DEFAULT_ORGANIZER_DIR = ".organizer";

export interface ExecutionLogsResponse {
  logs: ExecutionLogSummary[];
  totalLogs: number;
  error?: string;
}

export interface ExecutionLogResponse {
  log: ExecutionLog | null;
  error?: string;
}

export interface FileMovementHistoryResponse {
  movements: FileMovementHistoryEntry[];
  totalMovements: number;
  error?: string;
}

/**
 * GET /api/execution-logs
 * Get execution logs or file movement history
 *
 * Query parameters:
 * - basePath: Base path where .organizer directory is located (required)
 * - action: "list" | "get" | "history" | "folder-history" (default: "list")
 * - logFile: Log file name (required when action="get")
 * - folderPath: Folder path (required when action="folder-history")
 */
export async function GET(
  request: NextRequest
): Promise<
  NextResponse<
    ExecutionLogsResponse | ExecutionLogResponse | FileMovementHistoryResponse
  >
> {
  const searchParams = request.nextUrl.searchParams;

  const basePath = searchParams.get("basePath");
  const action = searchParams.get("action") || "list";
  const logFile = searchParams.get("logFile");
  const folderPath = searchParams.get("folderPath");

  // Validate basePath
  if (!basePath) {
    return NextResponse.json(
      {
        logs: [],
        totalLogs: 0,
        error: "basePath parameter is required",
      },
      { status: 400 }
    );
  }

  // Construct organizer directory path
  const organizerDir = path.join(basePath, DEFAULT_ORGANIZER_DIR);

  switch (action) {
    case "list": {
      // List all execution logs
      const result = scanExecutionLogs(organizerDir);
      if (result.error) {
        return NextResponse.json(
          {
            logs: [],
            totalLogs: 0,
            error: result.error,
          },
          { status: 500 }
        );
      }
      return NextResponse.json({
        logs: result.logs,
        totalLogs: result.totalLogs,
      });
    }

    case "get": {
      // Get a specific execution log
      if (!logFile) {
        return NextResponse.json(
          {
            log: null,
            error: "logFile parameter is required when action=get",
          },
          { status: 400 }
        );
      }

      // Validate logFile name to prevent path traversal
      if (logFile.includes("/") || logFile.includes("\\") || logFile.includes("..")) {
        return NextResponse.json(
          {
            log: null,
            error: "Invalid log file name",
          },
          { status: 400 }
        );
      }

      const result = getExecutionLog(organizerDir, logFile);
      if (result.error) {
        const status = result.error === "Log file not found" ? 404 : 500;
        return NextResponse.json(
          {
            log: null,
            error: result.error,
          },
          { status }
        );
      }
      return NextResponse.json({
        log: result.log,
      });
    }

    case "history": {
      // Get all file movement history
      const result = getFileMovementHistory(organizerDir);
      if (result.error) {
        return NextResponse.json(
          {
            movements: [],
            totalMovements: 0,
            error: result.error,
          },
          { status: 500 }
        );
      }
      return NextResponse.json({
        movements: result.movements,
        totalMovements: result.totalMovements,
      });
    }

    case "folder-history": {
      // Get file movement history for a specific folder
      if (!folderPath) {
        return NextResponse.json(
          {
            movements: [],
            totalMovements: 0,
            error: "folderPath parameter is required when action=folder-history",
          },
          { status: 400 }
        );
      }

      // Validate folderPath is absolute
      if (!path.isAbsolute(folderPath)) {
        return NextResponse.json(
          {
            movements: [],
            totalMovements: 0,
            error: "folderPath must be an absolute path",
          },
          { status: 400 }
        );
      }

      const result = getFolderMovementHistory(organizerDir, folderPath);
      if (result.error) {
        return NextResponse.json(
          {
            movements: [],
            totalMovements: 0,
            error: result.error,
          },
          { status: 500 }
        );
      }
      return NextResponse.json({
        movements: result.movements,
        totalMovements: result.totalMovements,
      });
    }

    default:
      return NextResponse.json(
        {
          logs: [],
          totalLogs: 0,
          error: `Unknown action: ${action}. Valid actions: list, get, history, folder-history`,
        },
        { status: 400 }
      );
  }
}
