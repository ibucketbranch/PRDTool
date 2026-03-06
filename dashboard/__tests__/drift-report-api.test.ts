import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import path from "path";
import { GET } from "@/app/api/refile/drift-report/route";

describe("Drift Report API", () => {
	let tempDir: string;
	let organizerDir: string;
	let queueDir: string;
	let agentDir: string;

	beforeEach(() => {
		// Create a temporary directory for each test
		tempDir = mkdtempSync(path.join(tmpdir(), "drift-report-api-test-"));
		organizerDir = path.join(tempDir, ".organizer");
		agentDir = path.join(organizerDir, "agent");
		queueDir = path.join(agentDir, "queue");
		mkdirSync(queueDir, { recursive: true });
	});

	afterEach(() => {
		// Clean up temporary directory
		rmSync(tempDir, { recursive: true, force: true });
	});

	// Helper to create a NextRequest with query params
	function createRequest(params: Record<string, string>): NextRequest {
		const url = new URL("http://localhost/api/refile/drift-report");
		for (const [key, value] of Object.entries(params)) {
			url.searchParams.set(key, value);
		}
		return new NextRequest(url);
	}

	// Helper to create a queue file with refile_drift actions
	function createQueueFile(
		cycleId: string,
		actions: Array<{
			source: string;
			target: string;
			originalLocation: string;
			currentLocation: string;
			assessment: string;
			confidence: number;
			reason: string;
			modelUsed?: string;
			suggestedDestination?: string;
			priority?: string;
		}>,
	): void {
		const queueActions = actions.map((action, index) => ({
			action_id: `${cycleId}:refile_drift:${index + 1}`,
			created_at: new Date().toISOString(),
			source_folder: action.source,
			target_folder: action.target,
			group_name: "refile_drift",
			confidence: action.confidence,
			reasoning: [
				`assessment=${action.assessment}`,
				`original_location=${action.originalLocation}`,
				`current_location=${action.currentLocation}`,
				`reason=${action.reason}`,
				...(action.modelUsed ? [`model=${action.modelUsed}`] : []),
				...(action.suggestedDestination ? [`suggested_destination=${action.suggestedDestination}`] : []),
			],
			action_type: "refile_drift",
			status: "pending",
			priority: action.priority,
		}));

		writeFileSync(
			path.join(queueDir, `pending_${cycleId}.json`),
			JSON.stringify({ actions: queueActions }),
		);
	}

	// Helper to create a saved drift report file
	function createDriftReportFile(
		drifts: Array<{
			filePath: string;
			originalFiledPath: string;
			currentPath: string;
			driftAssessment: string;
			confidence: number;
			reason: string;
			modelUsed?: string;
			suggestedDestination?: string;
		}>,
		metadata?: {
			filesChecked?: number;
			filesStillInPlace?: number;
			filesMissing?: number;
			modelUsed?: string;
			usedKeywordFallback?: boolean;
		},
	): void {
		const report = {
			drift_records: drifts.map((d) => ({
				file_path: d.filePath,
				original_filed_path: d.originalFiledPath,
				current_path: d.currentPath,
				filed_by: "test",
				filed_at: new Date().toISOString(),
				detected_at: new Date().toISOString(),
				sha256_hash: "abc123",
				drift_assessment: d.driftAssessment,
				reason: d.reason,
				model_used: d.modelUsed || "",
				confidence: d.confidence,
				suggested_destination: d.suggestedDestination || "",
			})),
			files_checked: metadata?.filesChecked || 0,
			files_still_in_place: metadata?.filesStillInPlace || 0,
			files_missing: metadata?.filesMissing || 0,
			model_used: metadata?.modelUsed || "",
			used_keyword_fallback: metadata?.usedKeywordFallback || false,
		};

		writeFileSync(
			path.join(agentDir, "drift_report.json"),
			JSON.stringify(report),
		);
	}

	// Helper to create a queue file with mixed actions
	function createMixedQueueFile(cycleId: string): void {
		const actions = [
			{
				action_id: `${cycleId}:refile_drift:1`,
				created_at: new Date().toISOString(),
				source_folder: "/test/Desktop/tax_2024.pdf",
				target_folder: "/test/Finances Bin/Taxes/tax_2024.pdf",
				group_name: "refile_drift",
				confidence: 0.85,
				reasoning: [
					"assessment=likely_accidental",
					"original_location=/test/Finances Bin/Taxes/tax_2024.pdf",
					"current_location=/test/Desktop/tax_2024.pdf",
					"reason=File moved to Desktop - likely accidental drag-drop",
					"model=llama3.1:8b",
				],
				action_type: "refile_drift",
				status: "pending",
				priority: "high",
			},
			{
				action_id: `${cycleId}:scatter:1`,
				created_at: new Date().toISOString(),
				source_folder: "/test/source/folder1",
				target_folder: "/test/target/folder1",
				group_name: "scatter_fix",
				confidence: 0.9,
				reasoning: ["current_bin=Work", "expected_bin=Finances"],
				action_type: "scatter_fix",
				status: "pending",
			},
			{
				action_id: `${cycleId}:refile_drift:2`,
				created_at: new Date().toISOString(),
				source_folder: "/test/Work Bin/Projects/bill.pdf",
				target_folder: "/test/Finances Bin/Bills/bill.pdf",
				group_name: "refile_drift",
				confidence: 0.72,
				reasoning: [
					"assessment=likely_intentional",
					"original_location=/test/Finances Bin/Bills/bill.pdf",
					"current_location=/test/Work Bin/Projects/bill.pdf",
					"reason=File moved to valid taxonomy path - likely intentional reorganization",
				],
				action_type: "refile_drift",
				status: "pending",
				priority: "low",
			},
		];

		writeFileSync(
			path.join(queueDir, `pending_${cycleId}.json`),
			JSON.stringify({ actions }),
		);
	}

	// ============================================================================
	// GET /api/refile/drift-report - Parameter validation tests
	// ============================================================================

	describe("GET - Parameter validation", () => {
		it("should return 400 if basePath is missing", async () => {
			const request = createRequest({});
			const response = await GET(request);

			expect(response.status).toBe(400);
			const data = await response.json();
			expect(data.error).toBe("basePath parameter is required");
			expect(data.groups).toHaveLength(0);
		});

		it("should return 400 if basePath is not absolute", async () => {
			const request = createRequest({ basePath: "relative/path" });
			const response = await GET(request);

			expect(response.status).toBe(400);
			const data = await response.json();
			expect(data.error).toBe("basePath must be an absolute path");
		});

		it("should return 404 if basePath does not exist", async () => {
			const request = createRequest({ basePath: "/nonexistent/path" });
			const response = await GET(request);

			expect(response.status).toBe(404);
			const data = await response.json();
			expect(data.error).toBe("basePath does not exist");
		});
	});

	// ============================================================================
	// GET /api/refile/drift-report - Queue reading tests
	// ============================================================================

	describe("GET - Reading from queue", () => {
		it("should return empty groups when queue directory is empty", async () => {
			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.groups).toHaveLength(0);
			expect(data.totalDrifts).toBe(0);
			expect(data.source).toBe("queue");
		});

		it("should return drift records from queue file", async () => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/Desktop/tax_2024.pdf",
					target: "/test/Finances Bin/Taxes/tax_2024.pdf",
					originalLocation: "/test/Finances Bin/Taxes/tax_2024.pdf",
					currentLocation: "/test/Desktop/tax_2024.pdf",
					assessment: "likely_accidental",
					confidence: 0.85,
					reason: "File moved to Desktop - likely accidental drag-drop",
					modelUsed: "llama3.1:8b",
					priority: "high",
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.totalDrifts).toBe(1);
			expect(data.groups).toHaveLength(1);
			expect(data.groups[0].drifts).toHaveLength(1);
			expect(data.groups[0].drifts[0].filePath).toBe("/test/Desktop/tax_2024.pdf");
			expect(data.groups[0].drifts[0].driftAssessment).toBe("likely_accidental");
			expect(data.groups[0].drifts[0].confidence).toBe(0.85);
			expect(data.groups[0].drifts[0].reason).toBe("File moved to Desktop - likely accidental drag-drop");
			expect(data.groups[0].drifts[0].modelUsed).toBe("llama3.1:8b");
			expect(data.groups[0].drifts[0].priority).toBe("high");
		});

		it("should only return refile_drift actions, not other action types", async () => {
			createMixedQueueFile("20260303_120000");

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			// Should only have 2 refile_drift actions, not the scatter_fix action
			expect(data.totalDrifts).toBe(2);
		});

		it("should count accidental and intentional drifts correctly", async () => {
			createMixedQueueFile("20260303_120000");

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.accidentalCount).toBe(1);
			expect(data.intentionalCount).toBe(1);
		});

		it("should group drifts by root bin", async () => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/Desktop/tax_2024.pdf",
					target: "/test/Finances Bin/Taxes/tax_2024.pdf",
					originalLocation: "/test/Finances Bin/Taxes/tax_2024.pdf",
					currentLocation: "/test/Desktop/tax_2024.pdf",
					assessment: "likely_accidental",
					confidence: 0.85,
					reason: "Accidental",
					priority: "high",
				},
				{
					source: "/test/Downloads/invoice.pdf",
					target: "/test/Finances Bin/Invoices/invoice.pdf",
					originalLocation: "/test/Finances Bin/Invoices/invoice.pdf",
					currentLocation: "/test/Downloads/invoice.pdf",
					assessment: "likely_accidental",
					confidence: 0.80,
					reason: "Accidental",
					priority: "high",
				},
				{
					source: "/test/Work Bin/Projects/va_doc.pdf",
					target: "/test/VA/Claims/va_doc.pdf",
					originalLocation: "/test/VA/Claims/va_doc.pdf",
					currentLocation: "/test/Work Bin/Projects/va_doc.pdf",
					assessment: "likely_intentional",
					confidence: 0.75,
					reason: "Intentional",
					priority: "low",
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.totalDrifts).toBe(3);
			// Groups based on original filed path bins
			expect(data.groups.length).toBeGreaterThanOrEqual(1);
		});
	});

	// ============================================================================
	// GET /api/refile/drift-report - Priority filtering tests
	// ============================================================================

	describe("GET - Priority filtering", () => {
		beforeEach(() => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/Desktop/tax_2024.pdf",
					target: "/test/Finances Bin/Taxes/tax_2024.pdf",
					originalLocation: "/test/Finances Bin/Taxes/tax_2024.pdf",
					currentLocation: "/test/Desktop/tax_2024.pdf",
					assessment: "likely_accidental",
					confidence: 0.85,
					reason: "Accidental",
					priority: "high",
				},
				{
					source: "/test/Work Bin/Projects/bill.pdf",
					target: "/test/Finances Bin/Bills/bill.pdf",
					originalLocation: "/test/Finances Bin/Bills/bill.pdf",
					currentLocation: "/test/Work Bin/Projects/bill.pdf",
					assessment: "likely_intentional",
					confidence: 0.72,
					reason: "Intentional",
					priority: "low",
				},
			]);
		});

		it("should filter by high priority", async () => {
			const request = createRequest({ basePath: tempDir, priority: "high" });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.totalDrifts).toBe(1);
			expect(data.groups[0].drifts[0].priority).toBe("high");
		});

		it("should filter by low priority", async () => {
			const request = createRequest({ basePath: tempDir, priority: "low" });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.totalDrifts).toBe(1);
			expect(data.groups[0].drifts[0].priority).toBe("low");
		});

		it("should return all drifts when priority=all", async () => {
			const request = createRequest({ basePath: tempDir, priority: "all" });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.totalDrifts).toBe(2);
		});
	});

	// ============================================================================
	// GET /api/refile/drift-report - Root bin filtering tests
	// ============================================================================

	describe("GET - Root bin filtering", () => {
		beforeEach(() => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/Desktop/tax_2024.pdf",
					target: "/test/Finances Bin/Taxes/tax_2024.pdf",
					originalLocation: "/test/Finances Bin/Taxes/tax_2024.pdf",
					currentLocation: "/test/Desktop/tax_2024.pdf",
					assessment: "likely_accidental",
					confidence: 0.85,
					reason: "Accidental",
					priority: "high",
				},
				{
					source: "/test/Desktop/va_claim.pdf",
					target: "/test/VA/Claims/va_claim.pdf",
					originalLocation: "/test/VA/Claims/va_claim.pdf",
					currentLocation: "/test/Desktop/va_claim.pdf",
					assessment: "likely_accidental",
					confidence: 0.90,
					reason: "Accidental",
					priority: "high",
				},
			]);
		});

		it("should filter by root bin (case insensitive)", async () => {
			const request = createRequest({ basePath: tempDir, rootBin: "finances" });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.totalDrifts).toBe(1);
			expect(data.groups[0].drifts[0].originalFiledPath).toContain("Finances Bin");
		});

		it("should filter by VA bin", async () => {
			const request = createRequest({ basePath: tempDir, rootBin: "VA" });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.totalDrifts).toBe(1);
			expect(data.groups[0].drifts[0].originalFiledPath).toContain("VA");
		});
	});

	// ============================================================================
	// GET /api/refile/drift-report - Saved report fallback tests
	// ============================================================================

	describe("GET - Saved report fallback", () => {
		it("should fall back to saved drift report when queue is empty", async () => {
			// No queue file created, but create a saved drift report
			createDriftReportFile(
				[
					{
						filePath: "/test/Desktop/saved_drift.pdf",
						originalFiledPath: "/test/Finances Bin/saved_drift.pdf",
						currentPath: "/test/Desktop/saved_drift.pdf",
						driftAssessment: "likely_accidental",
						confidence: 0.88,
						reason: "Saved drift from report file",
						modelUsed: "qwen2.5:14b",
					},
				],
				{
					filesChecked: 100,
					filesStillInPlace: 95,
					filesMissing: 2,
					modelUsed: "qwen2.5:14b",
					usedKeywordFallback: false,
				},
			);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.source).toBe("report");
			expect(data.totalDrifts).toBe(1);
			expect(data.groups[0].drifts[0].filePath).toBe("/test/Desktop/saved_drift.pdf");
			expect(data.filesChecked).toBe(100);
			expect(data.filesStillInPlace).toBe(95);
			expect(data.filesMissing).toBe(2);
		});

		it("should prefer queue over saved report", async () => {
			// Create both queue file and saved report
			createQueueFile("20260303_120000", [
				{
					source: "/test/Desktop/queue_drift.pdf",
					target: "/test/Finances Bin/queue_drift.pdf",
					originalLocation: "/test/Finances Bin/queue_drift.pdf",
					currentLocation: "/test/Desktop/queue_drift.pdf",
					assessment: "likely_accidental",
					confidence: 0.85,
					reason: "From queue",
					priority: "high",
				},
			]);

			createDriftReportFile([
				{
					filePath: "/test/Desktop/saved_drift.pdf",
					originalFiledPath: "/test/Finances Bin/saved_drift.pdf",
					currentPath: "/test/Desktop/saved_drift.pdf",
					driftAssessment: "likely_accidental",
					confidence: 0.88,
					reason: "From report",
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.source).toBe("queue");
			expect(data.groups[0].drifts[0].filePath).toBe("/test/Desktop/queue_drift.pdf");
		});
	});

	// ============================================================================
	// GET /api/refile/drift-report - Queue error handling
	// ============================================================================

	describe("GET - Error handling", () => {
		it("should return success with empty data when queue directory does not exist", async () => {
			// Remove the queue directory
			rmSync(queueDir, { recursive: true, force: true });

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			// Should return 200 with empty data since queue doesn't exist
			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.groups).toHaveLength(0);
		});

		it("should skip invalid JSON files in queue", async () => {
			// Create a valid queue file
			createQueueFile("20260303_120000", [
				{
					source: "/test/Desktop/valid.pdf",
					target: "/test/Finances Bin/valid.pdf",
					originalLocation: "/test/Finances Bin/valid.pdf",
					currentLocation: "/test/Desktop/valid.pdf",
					assessment: "likely_accidental",
					confidence: 0.85,
					reason: "Valid",
					priority: "high",
				},
			]);

			// Create an invalid JSON file
			writeFileSync(
				path.join(queueDir, "pending_20260303_110000.json"),
				"invalid json",
			);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			// Should still return the valid drift record
			expect(data.totalDrifts).toBe(1);
		});
	});

	// ============================================================================
	// Response structure tests
	// ============================================================================

	describe("Response structure", () => {
		it("should return proper response structure from queue", async () => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/Desktop/file.pdf",
					target: "/test/Finances Bin/file.pdf",
					originalLocation: "/test/Finances Bin/file.pdf",
					currentLocation: "/test/Desktop/file.pdf",
					assessment: "likely_accidental",
					confidence: 0.85,
					reason: "Test",
					priority: "high",
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();

			// Check all required fields are present
			expect(data).toHaveProperty("groups");
			expect(data).toHaveProperty("totalDrifts");
			expect(data).toHaveProperty("accidentalCount");
			expect(data).toHaveProperty("intentionalCount");
			expect(data).toHaveProperty("filesChecked");
			expect(data).toHaveProperty("filesStillInPlace");
			expect(data).toHaveProperty("filesMissing");
			expect(data).toHaveProperty("modelUsed");
			expect(data).toHaveProperty("usedKeywordFallback");
			expect(data).toHaveProperty("source");

			// Verify source is "queue"
			expect(data.source).toBe("queue");
		});

		it("should return proper drift record structure", async () => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/Desktop/tax_2024.pdf",
					target: "/test/Finances Bin/Taxes/tax_2024.pdf",
					originalLocation: "/test/Finances Bin/Taxes/tax_2024.pdf",
					currentLocation: "/test/Desktop/tax_2024.pdf",
					assessment: "likely_accidental",
					confidence: 0.85,
					reason: "File moved to Desktop",
					modelUsed: "llama3.1:8b",
					suggestedDestination: "/test/Finances Bin/Taxes/tax_2024.pdf",
					priority: "high",
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();

			const drift = data.groups[0].drifts[0];

			// Check all drift fields are present
			expect(drift).toHaveProperty("filePath");
			expect(drift).toHaveProperty("fileName");
			expect(drift).toHaveProperty("originalFiledPath");
			expect(drift).toHaveProperty("currentPath");
			expect(drift).toHaveProperty("driftAssessment");
			expect(drift).toHaveProperty("reason");
			expect(drift).toHaveProperty("modelUsed");
			expect(drift).toHaveProperty("confidence");
			expect(drift).toHaveProperty("suggestedDestination");
			expect(drift).toHaveProperty("priority");

			// Verify values
			expect(drift.filePath).toBe("/test/Desktop/tax_2024.pdf");
			expect(drift.fileName).toBe("tax_2024.pdf");
			expect(drift.driftAssessment).toBe("likely_accidental");
			expect(drift.priority).toBe("high");
			expect(drift.modelUsed).toBe("llama3.1:8b");
		});
	});

	// ============================================================================
	// Model usage and keyword fallback detection tests
	// ============================================================================

	describe("Model usage detection", () => {
		it("should detect model usage from drift records", async () => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/Desktop/tax.pdf",
					target: "/test/Finances Bin/tax.pdf",
					originalLocation: "/test/Finances Bin/tax.pdf",
					currentLocation: "/test/Desktop/tax.pdf",
					assessment: "likely_accidental",
					confidence: 0.85,
					reason: "Test",
					modelUsed: "llama3.1:8b",
					priority: "high",
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.modelUsed).toBe("llama3.1:8b");
		});

		it("should detect keyword fallback when model not used", async () => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/Desktop/tax.pdf",
					target: "/test/Finances Bin/tax.pdf",
					originalLocation: "/test/Finances Bin/tax.pdf",
					currentLocation: "/test/Desktop/tax.pdf",
					assessment: "likely_accidental",
					confidence: 0.7,
					reason: "Keyword fallback: Desktop path indicates accidental",
					// No modelUsed
					priority: "high",
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.usedKeywordFallback).toBe(true);
		});
	});
});
