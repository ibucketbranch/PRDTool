import { NextRequest, NextResponse } from "next/server";
import { existsSync, readdirSync, readFileSync } from "fs";
import path from "path";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

// ============================================================================
// Types
// ============================================================================

/**
 * A scatter violation - a file that exists outside its correct taxonomy bin.
 */
export interface ScatterViolation {
	filePath: string;
	fileName: string;
	currentBin: string;
	expectedBin: string;
	confidence: number;
	reason: string;
	modelUsed: string;
	suggestedSubpath: string;
	usedKeywordFallback: boolean;
}

/**
 * Scatter violations grouped by root bin.
 */
export interface ScatterViolationGroup {
	rootBin: string;
	violations: ScatterViolation[];
	totalViolations: number;
}

/**
 * Response for GET /api/scatter-report
 */
export interface ScatterReportResponse {
	groups: ScatterViolationGroup[];
	totalViolations: number;
	filesScanned: number;
	filesInCorrectBin: number;
	modelUsed: string;
	usedKeywordFallback: boolean;
	scannedDirectory: string;
	source: "queue" | "scan";
	error?: string;
}

/**
 * Request body for POST /api/scatter-report (trigger new scan)
 */
export interface ScatterScanRequest {
	basePath: string;
	directory?: string;
	maxFiles?: number;
}

/**
 * ProposedAction from the queue file (matching Python dataclass).
 */
interface ProposedAction {
	action_id: string;
	created_at: string;
	source_folder: string;
	target_folder: string;
	group_name: string;
	confidence: number;
	reasoning: string[];
	action_type: string;
	status: string;
}

// ============================================================================
// Helper functions
// ============================================================================

/**
 * Parse scatter violation from queue action reasoning.
 */
function parseViolationFromAction(action: ProposedAction): ScatterViolation {
	const reasoning = action.reasoning || [];

	// Extract data from reasoning array
	let currentBin = "";
	let expectedBin = "";
	let reason = "";
	let modelUsed = "";
	let usedKeywordFallback = false;

	for (const line of reasoning) {
		if (line.startsWith("current_bin=")) {
			currentBin = line.substring("current_bin=".length);
		} else if (line.startsWith("expected_bin=")) {
			expectedBin = line.substring("expected_bin=".length);
		} else if (line.startsWith("reason=")) {
			reason = line.substring("reason=".length);
		} else if (line.startsWith("model=")) {
			modelUsed = line.substring("model=".length);
		} else if (line === "method=keyword_fallback") {
			usedKeywordFallback = true;
		}
	}

	// Extract suggested subpath from target_folder
	const sourceFileName = path.basename(action.source_folder);
	const targetDir = path.dirname(action.target_folder);
	const suggestedSubpath = targetDir.includes(expectedBin)
		? targetDir.substring(targetDir.indexOf(expectedBin) + expectedBin.length + 1)
		: "";

	return {
		filePath: action.source_folder,
		fileName: sourceFileName,
		currentBin,
		expectedBin,
		confidence: action.confidence,
		reason,
		modelUsed,
		suggestedSubpath,
		usedKeywordFallback,
	};
}

/**
 * Load scatter violations from queue files.
 */
function loadScatterViolationsFromQueue(
	queueDir: string,
): { violations: ScatterViolation[]; error?: string } {
	try {
		if (!existsSync(queueDir)) {
			return { violations: [], error: "Queue directory does not exist" };
		}

		const files = readdirSync(queueDir);
		const pendingFiles = files
			.filter((f) => f.startsWith("pending_") && f.endsWith(".json"))
			.sort()
			.reverse();

		if (pendingFiles.length === 0) {
			return { violations: [] };
		}

		const violations: ScatterViolation[] = [];

		// Look through all pending queue files for scatter_fix actions
		for (const queueFile of pendingFiles) {
			const queuePath = path.join(queueDir, queueFile);
			try {
				const content = readFileSync(queuePath, "utf-8");
				const data = JSON.parse(content) as { actions?: ProposedAction[] };
				const actions = data.actions || [];

				for (const action of actions) {
					if (action.action_type === "scatter_fix" && action.status === "pending") {
						violations.push(parseViolationFromAction(action));
					}
				}
			} catch {
				// Skip invalid files
				continue;
			}
		}

		return { violations };
	} catch (err) {
		return {
			violations: [],
			error: err instanceof Error ? err.message : "Unknown error",
		};
	}
}

/**
 * Group violations by root bin.
 */
function groupViolationsByBin(violations: ScatterViolation[]): ScatterViolationGroup[] {
	const groups = new Map<string, ScatterViolation[]>();

	for (const violation of violations) {
		const bin = violation.currentBin || "Unknown";
		const existing = groups.get(bin) || [];
		existing.push(violation);
		groups.set(bin, existing);
	}

	return Array.from(groups.entries())
		.map(([rootBin, violations]) => ({
			rootBin,
			violations,
			totalViolations: violations.length,
		}))
		.sort((a, b) => b.totalViolations - a.totalViolations);
}

/**
 * Run scatter detection via Python and return the result.
 */
async function runScatterDetection(
	basePath: string,
	directory?: string,
	maxFiles?: number,
): Promise<ScatterReportResponse> {
	const scanDir = directory || basePath;
	const maxFilesArg = maxFiles || 500;

	// Build Python command to run scatter detection
	const pythonCode = `
import json
import sys
sys.path.insert(0, '${basePath}')
from organizer.scatter_detector import detect_scatter

result = detect_scatter(
    base_path='${scanDir}',
    max_files=${maxFilesArg},
)
print(json.dumps(result.to_dict()))
`;

	try {
		const { stdout, stderr } = await execAsync(`cd "${basePath}" && python3 -c "${pythonCode.replace(/"/g, '\\"').replace(/\n/g, '\\n')}"`, {
			timeout: 120000,
		});

		if (stderr && !stdout) {
			return {
				groups: [],
				totalViolations: 0,
				filesScanned: 0,
				filesInCorrectBin: 0,
				modelUsed: "",
				usedKeywordFallback: true,
				scannedDirectory: scanDir,
				source: "scan",
				error: stderr,
			};
		}

		const data = JSON.parse(stdout.trim()) as {
			violations: Array<{
				file_path: string;
				current_bin: string;
				expected_bin: string;
				confidence: number;
				reason: string;
				model_used: string;
				suggested_subpath: string;
				used_keyword_fallback: boolean;
			}>;
			files_scanned: number;
			files_in_correct_bin: number;
			model_used: string;
			used_keyword_fallback: boolean;
		};

		// Convert snake_case to camelCase
		const violations: ScatterViolation[] = data.violations.map((v) => ({
			filePath: v.file_path,
			fileName: path.basename(v.file_path),
			currentBin: v.current_bin,
			expectedBin: v.expected_bin,
			confidence: v.confidence,
			reason: v.reason,
			modelUsed: v.model_used,
			suggestedSubpath: v.suggested_subpath,
			usedKeywordFallback: v.used_keyword_fallback,
		}));

		const groups = groupViolationsByBin(violations);

		return {
			groups,
			totalViolations: violations.length,
			filesScanned: data.files_scanned,
			filesInCorrectBin: data.files_in_correct_bin,
			modelUsed: data.model_used,
			usedKeywordFallback: data.used_keyword_fallback,
			scannedDirectory: scanDir,
			source: "scan",
		};
	} catch (err) {
		return {
			groups: [],
			totalViolations: 0,
			filesScanned: 0,
			filesInCorrectBin: 0,
			modelUsed: "",
			usedKeywordFallback: true,
			scannedDirectory: scanDir,
			source: "scan",
			error: err instanceof Error ? err.message : "Unknown error",
		};
	}
}

// ============================================================================
// API Routes
// ============================================================================

/**
 * GET /api/scatter-report
 * Get scatter violations from queue or run a new scan.
 *
 * Query parameters:
 * - basePath: string (required) - Base path where .organizer directory is located
 * - scan: "true" | "false" (default: "false") - Run a new scan instead of reading queue
 * - directory: string (optional) - Directory to scan (defaults to basePath)
 * - maxFiles: number (default: 500) - Maximum files to scan
 */
export async function GET(
	request: NextRequest,
): Promise<NextResponse<ScatterReportResponse>> {
	const searchParams = request.nextUrl.searchParams;

	const basePath = searchParams.get("basePath");
	const scan = searchParams.get("scan") === "true";
	const directory = searchParams.get("directory");
	const maxFiles = parseInt(searchParams.get("maxFiles") || "500", 10);

	// Validate basePath
	if (!basePath) {
		return NextResponse.json(
			{
				groups: [],
				totalViolations: 0,
				filesScanned: 0,
				filesInCorrectBin: 0,
				modelUsed: "",
				usedKeywordFallback: false,
				scannedDirectory: "",
				source: "queue" as const,
				error: "basePath parameter is required",
			},
			{ status: 400 },
		);
	}

	// Normalize path
	const normalizedBasePath = path.normalize(basePath);

	if (!path.isAbsolute(normalizedBasePath)) {
		return NextResponse.json(
			{
				groups: [],
				totalViolations: 0,
				filesScanned: 0,
				filesInCorrectBin: 0,
				modelUsed: "",
				usedKeywordFallback: false,
				scannedDirectory: "",
				source: "queue" as const,
				error: "basePath must be an absolute path",
			},
			{ status: 400 },
		);
	}

	if (!existsSync(normalizedBasePath)) {
		return NextResponse.json(
			{
				groups: [],
				totalViolations: 0,
				filesScanned: 0,
				filesInCorrectBin: 0,
				modelUsed: "",
				usedKeywordFallback: false,
				scannedDirectory: normalizedBasePath,
				source: "queue" as const,
				error: "basePath does not exist",
			},
			{ status: 404 },
		);
	}

	// If scan=true, run scatter detection
	if (scan) {
		const result = await runScatterDetection(
			normalizedBasePath,
			directory || undefined,
			maxFiles,
		);
		const statusCode = result.error ? 500 : 200;
		return NextResponse.json(result, { status: statusCode });
	}

	// Otherwise, read from queue
	const organizerDir = path.join(normalizedBasePath, ".organizer");
	const queueDir = path.join(organizerDir, "agent", "queue");

	const { violations, error } = loadScatterViolationsFromQueue(queueDir);

	if (error && violations.length === 0) {
		return NextResponse.json(
			{
				groups: [],
				totalViolations: 0,
				filesScanned: 0,
				filesInCorrectBin: 0,
				modelUsed: "",
				usedKeywordFallback: false,
				scannedDirectory: normalizedBasePath,
				source: "queue" as const,
				error,
			},
			{ status: 500 },
		);
	}

	const groups = groupViolationsByBin(violations);

	// Determine model usage from violations
	const modelUsed = violations
		.map((v) => v.modelUsed)
		.filter(Boolean)
		.join(", ");
	const usedKeywordFallback = violations.some((v) => v.usedKeywordFallback);

	return NextResponse.json({
		groups,
		totalViolations: violations.length,
		filesScanned: 0, // Not available from queue
		filesInCorrectBin: 0, // Not available from queue
		modelUsed,
		usedKeywordFallback,
		scannedDirectory: normalizedBasePath,
		source: "queue" as const,
	});
}

/**
 * POST /api/scatter-report
 * Trigger a new scatter detection scan.
 *
 * Request body:
 * - basePath: string (required) - Base path where .organizer directory is located
 * - directory: string (optional) - Directory to scan (defaults to basePath)
 * - maxFiles: number (default: 500) - Maximum files to scan
 */
export async function POST(
	request: NextRequest,
): Promise<NextResponse<ScatterReportResponse>> {
	let body: ScatterScanRequest;

	try {
		body = await request.json();
	} catch {
		return NextResponse.json(
			{
				groups: [],
				totalViolations: 0,
				filesScanned: 0,
				filesInCorrectBin: 0,
				modelUsed: "",
				usedKeywordFallback: false,
				scannedDirectory: "",
				source: "scan" as const,
				error: "Invalid JSON in request body",
			},
			{ status: 400 },
		);
	}

	const { basePath, directory, maxFiles } = body;

	// Validate basePath
	if (!basePath || typeof basePath !== "string") {
		return NextResponse.json(
			{
				groups: [],
				totalViolations: 0,
				filesScanned: 0,
				filesInCorrectBin: 0,
				modelUsed: "",
				usedKeywordFallback: false,
				scannedDirectory: "",
				source: "scan" as const,
				error: "basePath is required",
			},
			{ status: 400 },
		);
	}

	// Normalize path
	const normalizedBasePath = path.normalize(basePath);

	if (!path.isAbsolute(normalizedBasePath)) {
		return NextResponse.json(
			{
				groups: [],
				totalViolations: 0,
				filesScanned: 0,
				filesInCorrectBin: 0,
				modelUsed: "",
				usedKeywordFallback: false,
				scannedDirectory: normalizedBasePath,
				source: "scan" as const,
				error: "basePath must be an absolute path",
			},
			{ status: 400 },
		);
	}

	if (!existsSync(normalizedBasePath)) {
		return NextResponse.json(
			{
				groups: [],
				totalViolations: 0,
				filesScanned: 0,
				filesInCorrectBin: 0,
				modelUsed: "",
				usedKeywordFallback: false,
				scannedDirectory: normalizedBasePath,
				source: "scan" as const,
				error: "basePath does not exist",
			},
			{ status: 404 },
		);
	}

	// Run scatter detection
	const result = await runScatterDetection(
		normalizedBasePath,
		directory || undefined,
		maxFiles || 500,
	);

	const statusCode = result.error ? 500 : 200;
	return NextResponse.json(result, { status: statusCode });
}
