import { NextRequest, NextResponse } from "next/server";
import { existsSync, readdirSync, readFileSync } from "fs";
import path from "path";

// ============================================================================
// Types
// ============================================================================

/**
 * A drifted file - a file that has moved from its filed location.
 */
export interface DriftRecord {
	filePath: string;
	fileName: string;
	originalFiledPath: string;
	currentPath: string;
	filedBy: string;
	filedAt: string;
	detectedAt: string;
	sha256Hash: string;
	driftAssessment: "likely_intentional" | "likely_accidental" | "";
	reason: string;
	modelUsed: string;
	confidence: number;
	suggestedDestination: string;
	priority: "high" | "normal" | "low";
}

/**
 * Drift records grouped by priority and root bin.
 */
export interface DriftGroup {
	rootBin: string;
	drifts: DriftRecord[];
	totalDrifts: number;
}

/**
 * Response for GET /api/refile/drift-report
 */
export interface DriftReportResponse {
	groups: DriftGroup[];
	totalDrifts: number;
	accidentalCount: number;
	intentionalCount: number;
	filesChecked: number;
	filesStillInPlace: number;
	filesMissing: number;
	modelUsed: string;
	usedKeywordFallback: boolean;
	source: "queue" | "report";
	error?: string;
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
	priority?: string;
}

// ============================================================================
// Helper functions
// ============================================================================

/**
 * Parse drift record from queue action reasoning.
 */
function parseDriftFromAction(action: ProposedAction): DriftRecord {
	const reasoning = action.reasoning || [];

	// Extract data from reasoning array
	let assessment = "";
	let originalLocation = "";
	let currentLocation = "";
	let reason = "";
	let modelUsed = "";
	let suggestedDestination = "";

	for (const line of reasoning) {
		if (line.startsWith("assessment=")) {
			assessment = line.substring("assessment=".length);
		} else if (line.startsWith("original_location=")) {
			originalLocation = line.substring("original_location=".length);
		} else if (line.startsWith("current_location=")) {
			currentLocation = line.substring("current_location=".length);
		} else if (line.startsWith("reason=")) {
			reason = line.substring("reason=".length);
		} else if (line.startsWith("model=")) {
			modelUsed = line.substring("model=".length);
		} else if (line.startsWith("suggested_destination=")) {
			suggestedDestination = line.substring("suggested_destination=".length);
		}
	}

	// Map priority from action or derive from assessment
	let priority: "high" | "normal" | "low" = "normal";
	if (action.priority === "high" || assessment === "likely_accidental") {
		priority = "high";
	} else if (action.priority === "low" || assessment === "likely_intentional") {
		priority = "low";
	}

	const fileName = path.basename(action.source_folder);

	return {
		filePath: action.source_folder,
		fileName,
		originalFiledPath: originalLocation || action.target_folder,
		currentPath: currentLocation || action.source_folder,
		filedBy: "", // Not available in queue action
		filedAt: "", // Not available in queue action
		detectedAt: action.created_at,
		sha256Hash: "", // Not available in queue action
		driftAssessment: (assessment as DriftRecord["driftAssessment"]) || "",
		reason,
		modelUsed,
		confidence: action.confidence,
		suggestedDestination,
		priority,
	};
}

/**
 * Extract root bin from a file path.
 */
function extractRootBin(filePath: string): string {
	// Look for common bin patterns
	const parts = filePath.split(path.sep);

	// Find first directory that looks like a bin (contains "Bin" or is a known category)
	const knownBins = [
		"Finances Bin",
		"Work Bin",
		"VA",
		"Archive",
		"Documents",
		"Desktop",
		"Downloads",
	];

	for (const part of parts) {
		if (part.includes("Bin") || knownBins.includes(part)) {
			return part;
		}
	}

	// Fall back to parent directory
	return parts.length >= 2 ? parts[parts.length - 2] : "Unknown";
}

/**
 * Load drift records from queue files.
 */
function loadDriftRecordsFromQueue(
	queueDir: string,
): { drifts: DriftRecord[]; error?: string } {
	try {
		if (!existsSync(queueDir)) {
			return { drifts: [], error: "Queue directory does not exist" };
		}

		const files = readdirSync(queueDir);
		const pendingFiles = files
			.filter((f) => f.startsWith("pending_") && f.endsWith(".json"))
			.sort()
			.reverse();

		if (pendingFiles.length === 0) {
			return { drifts: [] };
		}

		const drifts: DriftRecord[] = [];

		// Look through all pending queue files for refile_drift actions
		for (const queueFile of pendingFiles) {
			const queuePath = path.join(queueDir, queueFile);
			try {
				const content = readFileSync(queuePath, "utf-8");
				const data = JSON.parse(content) as { actions?: ProposedAction[] };
				const actions = data.actions || [];

				for (const action of actions) {
					if (action.action_type === "refile_drift" && action.status === "pending") {
						drifts.push(parseDriftFromAction(action));
					}
				}
			} catch {
				// Skip invalid files
				continue;
			}
		}

		return { drifts };
	} catch (err) {
		return {
			drifts: [],
			error: err instanceof Error ? err.message : "Unknown error",
		};
	}
}

/**
 * Load drift records from saved drift report file.
 */
function loadDriftRecordsFromReport(
	reportPath: string,
): { drifts: DriftRecord[]; metadata: Partial<DriftReportResponse>; error?: string } {
	try {
		if (!existsSync(reportPath)) {
			return {
				drifts: [],
				metadata: {},
				error: "Drift report file does not exist",
			};
		}

		const content = readFileSync(reportPath, "utf-8");
		const data = JSON.parse(content) as {
			drift_records?: Array<{
				file_path: string;
				original_filed_path: string;
				current_path: string;
				filed_by: string;
				filed_at: string;
				detected_at: string;
				sha256_hash: string;
				drift_assessment: string;
				reason: string;
				model_used: string;
				confidence: number;
				suggested_destination: string;
			}>;
			files_checked?: number;
			files_still_in_place?: number;
			files_missing?: number;
			model_used?: string;
			used_keyword_fallback?: boolean;
		};

		const rawRecords = data.drift_records || [];
		const drifts: DriftRecord[] = rawRecords.map((r) => {
			// Determine priority from assessment
			let priority: "high" | "normal" | "low" = "normal";
			if (r.drift_assessment === "likely_accidental") {
				priority = "high";
			} else if (r.drift_assessment === "likely_intentional") {
				priority = "low";
			}

			return {
				filePath: r.file_path,
				fileName: path.basename(r.file_path),
				originalFiledPath: r.original_filed_path,
				currentPath: r.current_path,
				filedBy: r.filed_by,
				filedAt: r.filed_at,
				detectedAt: r.detected_at,
				sha256Hash: r.sha256_hash,
				driftAssessment: (r.drift_assessment as DriftRecord["driftAssessment"]) || "",
				reason: r.reason,
				modelUsed: r.model_used,
				confidence: r.confidence,
				suggestedDestination: r.suggested_destination,
				priority,
			};
		});

		const metadata: Partial<DriftReportResponse> = {
			filesChecked: data.files_checked || 0,
			filesStillInPlace: data.files_still_in_place || 0,
			filesMissing: data.files_missing || 0,
			modelUsed: data.model_used || "",
			usedKeywordFallback: data.used_keyword_fallback || false,
		};

		return { drifts, metadata };
	} catch (err) {
		return {
			drifts: [],
			metadata: {},
			error: err instanceof Error ? err.message : "Unknown error",
		};
	}
}

/**
 * Group drift records by root bin.
 */
function groupDriftsByBin(drifts: DriftRecord[]): DriftGroup[] {
	const groups = new Map<string, DriftRecord[]>();

	for (const drift of drifts) {
		const bin = extractRootBin(drift.originalFiledPath || drift.filePath);
		const existing = groups.get(bin) || [];
		existing.push(drift);
		groups.set(bin, existing);
	}

	return Array.from(groups.entries())
		.map(([rootBin, drifts]) => ({
			rootBin,
			drifts,
			totalDrifts: drifts.length,
		}))
		.sort((a, b) => b.totalDrifts - a.totalDrifts);
}

/**
 * Count drifts by assessment type.
 */
function countByAssessment(drifts: DriftRecord[]): { accidental: number; intentional: number } {
	let accidental = 0;
	let intentional = 0;

	for (const drift of drifts) {
		if (drift.driftAssessment === "likely_accidental") {
			accidental++;
		} else if (drift.driftAssessment === "likely_intentional") {
			intentional++;
		}
	}

	return { accidental, intentional };
}

// ============================================================================
// API Routes
// ============================================================================

/**
 * GET /api/refile/drift-report
 * Get drift records from queue or saved report file.
 *
 * Query parameters:
 * - basePath: string (required) - Base path where .organizer directory is located
 * - priority: "high" | "low" | "all" (default: "all") - Filter by priority
 * - rootBin: string (optional) - Filter by root bin
 *
 * Returns drifted files with LLM assessment, reason, model_used.
 * Filterable by priority and root bin.
 */
export async function GET(
	request: NextRequest,
): Promise<NextResponse<DriftReportResponse>> {
	const searchParams = request.nextUrl.searchParams;

	const basePath = searchParams.get("basePath");
	const priorityFilter = searchParams.get("priority") || "all";
	const rootBinFilter = searchParams.get("rootBin");

	// Validate basePath
	if (!basePath) {
		return NextResponse.json(
			{
				groups: [],
				totalDrifts: 0,
				accidentalCount: 0,
				intentionalCount: 0,
				filesChecked: 0,
				filesStillInPlace: 0,
				filesMissing: 0,
				modelUsed: "",
				usedKeywordFallback: false,
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
				totalDrifts: 0,
				accidentalCount: 0,
				intentionalCount: 0,
				filesChecked: 0,
				filesStillInPlace: 0,
				filesMissing: 0,
				modelUsed: "",
				usedKeywordFallback: false,
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
				totalDrifts: 0,
				accidentalCount: 0,
				intentionalCount: 0,
				filesChecked: 0,
				filesStillInPlace: 0,
				filesMissing: 0,
				modelUsed: "",
				usedKeywordFallback: false,
				source: "queue" as const,
				error: "basePath does not exist",
			},
			{ status: 404 },
		);
	}

	const organizerDir = path.join(normalizedBasePath, ".organizer");
	const queueDir = path.join(organizerDir, "agent", "queue");
	const reportPath = path.join(organizerDir, "agent", "drift_report.json");

	// Try loading from queue first, then fall back to saved report
	let drifts: DriftRecord[] = [];
	let source: "queue" | "report" = "queue";
	let metadata: Partial<DriftReportResponse> = {};
	let error: string | undefined;

	// First try queue
	const queueResult = loadDriftRecordsFromQueue(queueDir);
	if (queueResult.drifts.length > 0) {
		drifts = queueResult.drifts;
		source = "queue";
	} else if (existsSync(reportPath)) {
		// Fall back to saved report
		const reportResult = loadDriftRecordsFromReport(reportPath);
		if (reportResult.drifts.length > 0 || !reportResult.error) {
			drifts = reportResult.drifts;
			metadata = reportResult.metadata;
			source = "report";
		}
		if (reportResult.error && queueResult.error) {
			error = `Queue: ${queueResult.error}; Report: ${reportResult.error}`;
		}
	} else if (queueResult.error) {
		error = queueResult.error;
	}

	// Apply priority filter
	if (priorityFilter !== "all") {
		drifts = drifts.filter((d) => d.priority === priorityFilter);
	}

	// Apply root bin filter
	if (rootBinFilter) {
		drifts = drifts.filter((d) => {
			const bin = extractRootBin(d.originalFiledPath || d.filePath);
			return bin.toLowerCase().includes(rootBinFilter.toLowerCase());
		});
	}

	// Group and count
	const groups = groupDriftsByBin(drifts);
	const { accidental, intentional } = countByAssessment(drifts);

	// Determine model usage from drifts
	const modelUsed = metadata.modelUsed ||
		drifts
			.map((d) => d.modelUsed)
			.filter(Boolean)
			.filter((v, i, a) => a.indexOf(v) === i)
			.join(", ");
	const usedKeywordFallback = metadata.usedKeywordFallback ||
		drifts.some((d) => !d.modelUsed);

	return NextResponse.json({
		groups,
		totalDrifts: drifts.length,
		accidentalCount: accidental,
		intentionalCount: intentional,
		filesChecked: metadata.filesChecked || 0,
		filesStillInPlace: metadata.filesStillInPlace || 0,
		filesMissing: metadata.filesMissing || 0,
		modelUsed,
		usedKeywordFallback,
		source,
		error,
	});
}
