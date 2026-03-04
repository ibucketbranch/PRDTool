/**
 * Execution log utilities for Dashboard Phase 5
 *
 * Provides functions to read and parse execution logs from the .organizer directory.
 * These logs track file movements during folder consolidation operations.
 */

import { readdirSync, readFileSync, existsSync, statSync } from "fs";
import path from "path";

// ============================================================================
// Types
// ============================================================================

/**
 * A single file move record from an execution log
 */
export interface FileMoveRecord {
  currentPath: string;
  originalPath: string;
  command: string;
}

/**
 * A folder move entry from an execution log
 */
export interface FolderMoveEntry {
  sourceFolder: string;
  targetFolder: string;
  filesMoved: number;
  filesFailed: number;
  status: string;
  error: string;
}

/**
 * Content analysis entry from an execution log
 */
export interface ContentAnalysisLogEntry {
  groupName: string;
  shouldConsolidate: boolean;
  decisionSummary: string;
  confidence: number;
  aiCategories: string[];
  dateRanges: Record<string, string>;
  reasoning: string[];
}

/**
 * A group entry from an execution log
 */
export interface GroupLogEntry {
  groupName: string;
  targetFolder: string;
  foldersProcessed: number;
  filesMoved: number;
  filesFailed: number;
  status: string;
  error: string;
  folderEntries: FolderMoveEntry[];
  rollbackInstructions: FileMoveRecord[];
  contentAnalysis?: ContentAnalysisLogEntry;
}

/**
 * Summary of an execution log
 */
export interface ExecutionLogSummary {
  logFile: string;
  timestamp: string;
  planFile: string;
  basePath: string;
  totalGroups: number;
  groupsCompleted: number;
  groupsFailed: number;
  totalFilesMoved: number;
  totalFilesFailed: number;
  status: string;
  stoppedEarly: boolean;
  error: string;
  contentAware: boolean;
}

/**
 * Full execution log data
 */
export interface ExecutionLog {
  summary: ExecutionLogSummary;
  groupEntries: GroupLogEntry[];
  rollback: {
    totalMovesToUndo: number;
    instructions: FileMoveRecord[];
  };
  contentAnalysis?: {
    contentAwareMode: boolean;
    groupsAnalyzed: number;
    groupsToConsolidate: number;
    groupsToSkip: number;
    aiCategoriesFound: Record<string, number>;
    dateRangesFound: string[];
  };
}

/**
 * File movement history entry (combining execution logs and database)
 */
export interface FileMovementHistoryEntry {
  fileName: string;
  originalPath: string;
  currentPath: string;
  movedAt: string;
  groupName: string;
  sourceFolder: string;
  targetFolder: string;
  logFile: string;
}

/**
 * Result from scanning execution logs
 */
export interface ExecutionLogsResult {
  logs: ExecutionLogSummary[];
  totalLogs: number;
  error?: string;
}

/**
 * Result from getting file movement history
 */
export interface FileMovementHistoryResult {
  movements: FileMovementHistoryEntry[];
  totalMovements: number;
  error?: string;
}

// ============================================================================
// Helper functions
// ============================================================================

/**
 * Parse a raw execution log JSON into our typed structure
 */
export function parseExecutionLog(
  rawLog: Record<string, unknown>,
  logFile: string
): ExecutionLog {
  const executionSummary = rawLog.execution_summary as Record<string, unknown>;
  const groupEntriesRaw = rawLog.group_entries as Record<string, unknown>[];
  const rollbackRaw = rawLog.rollback as Record<string, unknown>;
  const contentAnalysisRaw = rawLog.content_analysis as
    | Record<string, unknown>
    | undefined;

  // Parse execution summary
  const summary: ExecutionLogSummary = {
    logFile,
    timestamp: String(executionSummary?.timestamp ?? ""),
    planFile: String(executionSummary?.plan_file ?? ""),
    basePath: String(executionSummary?.base_path ?? ""),
    totalGroups: Number(executionSummary?.total_groups ?? 0),
    groupsCompleted: Number(executionSummary?.groups_completed ?? 0),
    groupsFailed: Number(executionSummary?.groups_failed ?? 0),
    totalFilesMoved: Number(executionSummary?.total_files_moved ?? 0),
    totalFilesFailed: Number(executionSummary?.total_files_failed ?? 0),
    status: String(executionSummary?.status ?? ""),
    stoppedEarly: Boolean(executionSummary?.stopped_early ?? false),
    error: String(executionSummary?.error ?? ""),
    contentAware: Boolean(executionSummary?.content_aware ?? false),
  };

  // Parse group entries
  const groupEntries: GroupLogEntry[] = (groupEntriesRaw || []).map(
    (entry) => {
      const folderEntriesRaw = entry.folder_entries as Record<string, unknown>[];
      const rollbackInstructionsRaw = entry.rollback_instructions as Record<
        string,
        unknown
      >[];
      const contentAnalysisEntryRaw = entry.content_analysis as
        | Record<string, unknown>
        | undefined;

      const folderEntries: FolderMoveEntry[] = (folderEntriesRaw || []).map(
        (fe) => ({
          sourceFolder: String(fe.source_folder ?? ""),
          targetFolder: String(fe.target_folder ?? ""),
          filesMoved: Number(fe.files_moved ?? 0),
          filesFailed: Number(fe.files_failed ?? 0),
          status: String(fe.status ?? ""),
          error: String(fe.error ?? ""),
        })
      );

      const rollbackInstructions: FileMoveRecord[] = (
        rollbackInstructionsRaw || []
      ).map((ri) => ({
        currentPath: String(ri.current_path ?? ""),
        originalPath: String(ri.original_path ?? ""),
        command: String(ri.command ?? ""),
      }));

      let contentAnalysis: ContentAnalysisLogEntry | undefined;
      if (contentAnalysisEntryRaw) {
        contentAnalysis = {
          groupName: String(contentAnalysisEntryRaw.group_name ?? ""),
          shouldConsolidate: Boolean(
            contentAnalysisEntryRaw.should_consolidate ?? false
          ),
          decisionSummary: String(contentAnalysisEntryRaw.decision_summary ?? ""),
          confidence: Number(contentAnalysisEntryRaw.confidence ?? 0),
          aiCategories: (contentAnalysisEntryRaw.ai_categories as string[]) || [],
          dateRanges:
            (contentAnalysisEntryRaw.date_ranges as Record<string, string>) || {},
          reasoning: (contentAnalysisEntryRaw.reasoning as string[]) || [],
        };
      }

      return {
        groupName: String(entry.group_name ?? ""),
        targetFolder: String(entry.target_folder ?? ""),
        foldersProcessed: Number(entry.folders_processed ?? 0),
        filesMoved: Number(entry.files_moved ?? 0),
        filesFailed: Number(entry.files_failed ?? 0),
        status: String(entry.status ?? ""),
        error: String(entry.error ?? ""),
        folderEntries,
        rollbackInstructions,
        contentAnalysis,
      };
    }
  );

  // Parse rollback
  const rollbackInstructionsRaw = rollbackRaw?.instructions as
    | Record<string, unknown>[]
    | undefined;
  const rollback = {
    totalMovesToUndo: Number(rollbackRaw?.total_moves_to_undo ?? 0),
    instructions: (rollbackInstructionsRaw || []).map((ri) => ({
      currentPath: String(ri.current_path ?? ""),
      originalPath: String(ri.original_path ?? ""),
      command: String(ri.command ?? ""),
    })),
  };

  // Parse content analysis summary
  let contentAnalysis:
    | {
        contentAwareMode: boolean;
        groupsAnalyzed: number;
        groupsToConsolidate: number;
        groupsToSkip: number;
        aiCategoriesFound: Record<string, number>;
        dateRangesFound: string[];
      }
    | undefined;

  if (contentAnalysisRaw) {
    contentAnalysis = {
      contentAwareMode: Boolean(contentAnalysisRaw.content_aware_mode ?? false),
      groupsAnalyzed: Number(contentAnalysisRaw.groups_analyzed ?? 0),
      groupsToConsolidate: Number(contentAnalysisRaw.groups_to_consolidate ?? 0),
      groupsToSkip: Number(contentAnalysisRaw.groups_to_skip ?? 0),
      aiCategoriesFound:
        (contentAnalysisRaw.ai_categories_found as Record<string, number>) || {},
      dateRangesFound:
        (contentAnalysisRaw.date_ranges_found as string[]) || [],
    };
  }

  return {
    summary,
    groupEntries,
    rollback,
    contentAnalysis,
  };
}

/**
 * Extract timestamp from execution log filename
 * Format: execution_log_YYYYMMDD_HHMMSS.json
 */
export function extractTimestampFromFilename(filename: string): string {
  const match = filename.match(/execution_log_(\d{8}_\d{6})\.json$/);
  if (!match) return "";

  const dateStr = match[1];
  // Convert YYYYMMDD_HHMMSS to ISO format
  const year = dateStr.slice(0, 4);
  const month = dateStr.slice(4, 6);
  const day = dateStr.slice(6, 8);
  const hour = dateStr.slice(9, 11);
  const min = dateStr.slice(11, 13);
  const sec = dateStr.slice(13, 15);

  return `${year}-${month}-${day}T${hour}:${min}:${sec}`;
}

// ============================================================================
// Main functions
// ============================================================================

/**
 * Scan a directory for execution log files
 *
 * @param organizerDir - Path to the .organizer directory
 * @returns List of execution log summaries
 */
export function scanExecutionLogs(organizerDir: string): ExecutionLogsResult {
  try {
    if (!existsSync(organizerDir)) {
      return { logs: [], totalLogs: 0 };
    }

    const stats = statSync(organizerDir);
    if (!stats.isDirectory()) {
      return { logs: [], totalLogs: 0, error: "Not a directory" };
    }

    // Find all execution log files
    const files = readdirSync(organizerDir);
    const logFiles = files.filter((f) => f.match(/^execution_log_\d+_\d+\.json$/));

    const logs: ExecutionLogSummary[] = [];

    for (const logFile of logFiles) {
      const logPath = path.join(organizerDir, logFile);
      try {
        const content = readFileSync(logPath, "utf-8");
        const rawLog = JSON.parse(content) as Record<string, unknown>;
        const parsed = parseExecutionLog(rawLog, logFile);
        logs.push(parsed.summary);
      } catch {
        // Skip invalid log files
        continue;
      }
    }

    // Sort by timestamp descending (most recent first)
    logs.sort((a, b) => b.timestamp.localeCompare(a.timestamp));

    return { logs, totalLogs: logs.length };
  } catch (err) {
    return {
      logs: [],
      totalLogs: 0,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Get a specific execution log by filename
 *
 * @param organizerDir - Path to the .organizer directory
 * @param logFile - Name of the log file
 * @returns Full execution log data
 */
export function getExecutionLog(
  organizerDir: string,
  logFile: string
): { log: ExecutionLog | null; error?: string } {
  try {
    const logPath = path.join(organizerDir, logFile);

    if (!existsSync(logPath)) {
      return { log: null, error: "Log file not found" };
    }

    const content = readFileSync(logPath, "utf-8");
    const rawLog = JSON.parse(content) as Record<string, unknown>;
    const parsed = parseExecutionLog(rawLog, logFile);

    return { log: parsed };
  } catch (err) {
    return {
      log: null,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Get file movement history from execution logs
 * Returns all file movements across all execution logs
 *
 * @param organizerDir - Path to the .organizer directory
 * @param folderPath - Optional: filter to movements from a specific folder
 * @returns List of file movement entries
 */
export function getFileMovementHistory(
  organizerDir: string,
  folderPath?: string
): FileMovementHistoryResult {
  try {
    const logsResult = scanExecutionLogs(organizerDir);
    if (logsResult.error) {
      return { movements: [], totalMovements: 0, error: logsResult.error };
    }

    const movements: FileMovementHistoryEntry[] = [];

    for (const logSummary of logsResult.logs) {
      const logResult = getExecutionLog(organizerDir, logSummary.logFile);
      if (!logResult.log) continue;

      const log = logResult.log;

      for (const groupEntry of log.groupEntries) {
        // Get rollback instructions (which contain the actual file moves)
        for (const instruction of groupEntry.rollbackInstructions) {
          // If folderPath filter is provided, check if original path is in that folder
          if (folderPath) {
            const originalFolder = path.dirname(instruction.originalPath);
            if (originalFolder !== folderPath) continue;
          }

          const fileName = path.basename(instruction.originalPath);

          movements.push({
            fileName,
            originalPath: instruction.originalPath,
            currentPath: instruction.currentPath,
            movedAt: log.summary.timestamp,
            groupName: groupEntry.groupName,
            sourceFolder: path.dirname(instruction.originalPath),
            targetFolder: groupEntry.targetFolder,
            logFile: log.summary.logFile,
          });
        }
      }
    }

    // Sort by movedAt descending (most recent first)
    movements.sort((a, b) => b.movedAt.localeCompare(a.movedAt));

    return { movements, totalMovements: movements.length };
  } catch (err) {
    return {
      movements: [],
      totalMovements: 0,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Get movement history for files from a specific folder
 * Combines data from execution logs
 *
 * @param organizerDir - Path to the .organizer directory
 * @param folderPath - The folder path to get history for
 * @returns File movement history for the folder
 */
export function getFolderMovementHistory(
  organizerDir: string,
  folderPath: string
): FileMovementHistoryResult {
  return getFileMovementHistory(organizerDir, folderPath);
}

/**
 * Get all unique source folders that had files moved
 *
 * @param organizerDir - Path to the .organizer directory
 * @returns List of unique folder paths
 */
export function getSourceFoldersFromLogs(
  organizerDir: string
): { folders: string[]; error?: string } {
  try {
    const historyResult = getFileMovementHistory(organizerDir);
    if (historyResult.error) {
      return { folders: [], error: historyResult.error };
    }

    const foldersSet = new Set<string>();
    for (const movement of historyResult.movements) {
      foldersSet.add(movement.sourceFolder);
    }

    const folders = Array.from(foldersSet).sort();
    return { folders };
  } catch (err) {
    return {
      folders: [],
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}
