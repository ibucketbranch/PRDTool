import { NextRequest, NextResponse } from "next/server";
import { readFileSync, existsSync } from "fs";
import path from "path";

// Default path to the PRD task status file
const DEFAULT_STATUS_FILE = ".organizer/agent/prd_task_status.json";

/**
 * Task history entry from PRDTaskStatusTracker
 */
export interface TaskHistoryEntry {
	timestamp: string;
	event: string;
	from_status: string;
	to_status: string;
	errors?: string[];
}

/**
 * Ready task data structure matching PRDTaskStatusTracker's TaskStatus
 */
export interface ReadyTask {
	task_id: string;
	status: "ready";
	last_dry_run_at: string | null;
	last_errors: string[];
	marked_ready_at: string | null;
	history: TaskHistoryEntry[];
}

/**
 * Response structure for ready-tasks endpoint
 */
export interface ReadyTasksResponse {
	ready_tasks: ReadyTask[];
	total_count: number;
	timestamp: string;
	error?: string;
}

/**
 * Raw task data from the JSON file
 */
interface RawTaskData {
	task_id: string;
	status: string;
	last_dry_run_at: string | null;
	last_errors: string[];
	marked_ready_at: string | null;
	history: TaskHistoryEntry[];
}

/**
 * Raw JSON structure from prd_task_status.json
 */
interface TaskStatusFile {
	updated_at: string;
	tasks: Record<string, RawTaskData>;
}

/**
 * GET /api/agents/ready-tasks
 * Returns tasks with status "ready" - these are the next sprint candidates.
 * Tasks are sorted by priority (phase order, then task order within phase).
 *
 * Query parameters:
 * - basePath: Base path where .organizer directory is located (required)
 */
export async function GET(
	request: NextRequest,
): Promise<NextResponse<ReadyTasksResponse>> {
	const timestamp = new Date().toISOString();
	const searchParams = request.nextUrl.searchParams;
	const basePath = searchParams.get("basePath");

	// Validate basePath
	if (!basePath) {
		return NextResponse.json(
			{
				ready_tasks: [],
				total_count: 0,
				timestamp,
				error: "basePath parameter is required",
			},
			{ status: 400 },
		);
	}

	// Construct path to status file
	const statusFilePath = path.join(basePath, DEFAULT_STATUS_FILE);

	// Check if file exists
	if (!existsSync(statusFilePath)) {
		// Return empty array if no status file exists (no tasks tracked yet)
		return NextResponse.json({
			ready_tasks: [],
			total_count: 0,
			timestamp,
		});
	}

	// Read and parse status file
	let statusData: TaskStatusFile;
	try {
		const fileContent = readFileSync(statusFilePath, "utf-8");
		statusData = JSON.parse(fileContent) as TaskStatusFile;
	} catch (err) {
		const errorMessage =
			err instanceof Error ? err.message : "Unknown error";
		return NextResponse.json(
			{
				ready_tasks: [],
				total_count: 0,
				timestamp,
				error: `Failed to read status file: ${errorMessage}`,
			},
			{ status: 500 },
		);
	}

	// Filter tasks with "ready" status
	const readyTasks: ReadyTask[] = [];
	const tasks = statusData.tasks || {};

	for (const [taskId, taskData] of Object.entries(tasks)) {
		if (taskData.status === "ready") {
			readyTasks.push({
				task_id: taskId,
				status: "ready",
				last_dry_run_at: taskData.last_dry_run_at,
				last_errors: taskData.last_errors || [],
				marked_ready_at: taskData.marked_ready_at,
				history: taskData.history || [],
			});
		}
	}

	// Sort by task_id for consistent ordering
	// Task IDs are expected to follow patterns like "phase11.1", "phase12.scatter_detector"
	readyTasks.sort((a, b) => {
		// Extract phase number and task order for sorting
		const parseTaskId = (id: string) => {
			const match = id.match(/phase(\d+)(?:\.(\d+|[\w_]+))?/i);
			if (match) {
				const phase = parseInt(match[1], 10);
				const task = match[2] ? match[2] : "0";
				// If task is numeric, pad it; otherwise use string comparison
				const taskNum = /^\d+$/.test(task)
					? parseInt(task, 10)
					: task;
				return { phase, task: taskNum };
			}
			return { phase: Infinity, task: id };
		};

		const parsedA = parseTaskId(a.task_id);
		const parsedB = parseTaskId(b.task_id);

		// Sort by phase first
		if (parsedA.phase !== parsedB.phase) {
			return parsedA.phase - parsedB.phase;
		}

		// Then by task (numeric or string)
		if (typeof parsedA.task === "number" && typeof parsedB.task === "number") {
			return parsedA.task - parsedB.task;
		}

		// Fall back to string comparison
		return String(parsedA.task).localeCompare(String(parsedB.task));
	});

	return NextResponse.json({
		ready_tasks: readyTasks,
		total_count: readyTasks.length,
		timestamp,
	});
}
