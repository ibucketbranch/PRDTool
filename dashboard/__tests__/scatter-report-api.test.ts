import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import path from "path";
import { GET, POST } from "@/app/api/scatter-report/route";

describe("Scatter Report API", () => {
	let tempDir: string;
	let organizerDir: string;
	let queueDir: string;

	beforeEach(() => {
		// Create a temporary directory for each test
		tempDir = mkdtempSync(path.join(tmpdir(), "scatter-report-api-test-"));
		organizerDir = path.join(tempDir, ".organizer");
		queueDir = path.join(organizerDir, "agent", "queue");
		mkdirSync(queueDir, { recursive: true });
	});

	afterEach(() => {
		// Clean up temporary directory
		rmSync(tempDir, { recursive: true, force: true });
	});

	// Helper to create a NextRequest with query params
	function createRequest(params: Record<string, string>): NextRequest {
		const url = new URL("http://localhost/api/scatter-report");
		for (const [key, value] of Object.entries(params)) {
			url.searchParams.set(key, value);
		}
		return new NextRequest(url);
	}

	// Helper to create a POST request
	function createPostRequest(body: unknown): NextRequest {
		return new NextRequest("http://localhost/api/scatter-report", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify(body),
		});
	}

	// Helper to create a queue file with scatter_fix actions
	function createQueueFile(
		cycleId: string,
		actions: Array<{
			source: string;
			target: string;
			currentBin: string;
			expectedBin: string;
			confidence: number;
			reason: string;
			modelUsed?: string;
			keywordFallback?: boolean;
		}>,
	): void {
		const queueActions = actions.map((action, index) => ({
			action_id: `${cycleId}:scatter:${index + 1}`,
			created_at: new Date().toISOString(),
			source_folder: action.source,
			target_folder: action.target,
			group_name: "scatter_fix",
			confidence: action.confidence,
			reasoning: [
				`current_bin=${action.currentBin}`,
				`expected_bin=${action.expectedBin}`,
				`reason=${action.reason}`,
				...(action.modelUsed ? [`model=${action.modelUsed}`] : []),
				...(action.keywordFallback ? ["method=keyword_fallback"] : []),
			],
			action_type: "scatter_fix",
			status: "pending",
		}));

		writeFileSync(
			path.join(queueDir, `pending_${cycleId}.json`),
			JSON.stringify({ actions: queueActions }),
		);
	}

	// Helper to create a queue file with mixed actions
	function createMixedQueueFile(cycleId: string): void {
		const actions = [
			{
				action_id: `${cycleId}:scatter:1`,
				created_at: new Date().toISOString(),
				source_folder: "/test/Work Bin/tax_2024.pdf",
				target_folder: "/test/Finances Bin/Taxes/2024/tax_2024.pdf",
				group_name: "scatter_fix",
				confidence: 0.85,
				reasoning: [
					"current_bin=Work Bin",
					"expected_bin=Finances Bin",
					"reason=Tax document belongs in Finances",
					"model=llama3.1:8b",
				],
				action_type: "scatter_fix",
				status: "pending",
			},
			{
				action_id: `${cycleId}:move:1`,
				created_at: new Date().toISOString(),
				source_folder: "/test/source/folder1",
				target_folder: "/test/target/folder1",
				group_name: "folder_consolidation",
				confidence: 0.9,
				reasoning: ["Similar folder names"],
				action_type: "move",
				status: "pending",
			},
			{
				action_id: `${cycleId}:scatter:2`,
				created_at: new Date().toISOString(),
				source_folder: "/test/VA/bill_verizon.pdf",
				target_folder: "/test/Finances Bin/Bills/verizon/bill_verizon.pdf",
				group_name: "scatter_fix",
				confidence: 0.92,
				reasoning: [
					"current_bin=VA",
					"expected_bin=Finances Bin",
					"reason=Utility bill belongs in Finances",
				],
				action_type: "scatter_fix",
				status: "pending",
			},
		];

		writeFileSync(
			path.join(queueDir, `pending_${cycleId}.json`),
			JSON.stringify({ actions }),
		);
	}

	// ============================================================================
	// GET /api/scatter-report - Parameter validation tests
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
	// GET /api/scatter-report - Queue reading tests
	// ============================================================================

	describe("GET - Reading from queue", () => {
		it("should return empty groups when queue directory is empty", async () => {
			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.groups).toHaveLength(0);
			expect(data.totalViolations).toBe(0);
			expect(data.source).toBe("queue");
		});

		it("should return scatter violations from queue file", async () => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/Work Bin/tax_2024.pdf",
					target: "/test/Finances Bin/Taxes/2024/tax_2024.pdf",
					currentBin: "Work Bin",
					expectedBin: "Finances Bin",
					confidence: 0.85,
					reason: "Tax document belongs in Finances",
					modelUsed: "llama3.1:8b",
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.totalViolations).toBe(1);
			expect(data.groups).toHaveLength(1);
			expect(data.groups[0].rootBin).toBe("Work Bin");
			expect(data.groups[0].violations).toHaveLength(1);
			expect(data.groups[0].violations[0].filePath).toBe("/test/Work Bin/tax_2024.pdf");
			expect(data.groups[0].violations[0].currentBin).toBe("Work Bin");
			expect(data.groups[0].violations[0].expectedBin).toBe("Finances Bin");
			expect(data.groups[0].violations[0].confidence).toBe(0.85);
			expect(data.groups[0].violations[0].reason).toBe("Tax document belongs in Finances");
			expect(data.groups[0].violations[0].modelUsed).toBe("llama3.1:8b");
		});

		it("should only return scatter_fix actions, not other action types", async () => {
			createMixedQueueFile("20260303_120000");

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			// Should only have 2 scatter_fix actions, not the move action
			expect(data.totalViolations).toBe(2);
		});

		it("should group violations by root bin", async () => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/Work Bin/tax_2024.pdf",
					target: "/test/Finances Bin/Taxes/2024/tax_2024.pdf",
					currentBin: "Work Bin",
					expectedBin: "Finances Bin",
					confidence: 0.85,
					reason: "Tax document",
				},
				{
					source: "/test/Work Bin/invoice_2024.pdf",
					target: "/test/Finances Bin/Invoices/invoice_2024.pdf",
					currentBin: "Work Bin",
					expectedBin: "Finances Bin",
					confidence: 0.80,
					reason: "Invoice",
				},
				{
					source: "/test/VA/bill.pdf",
					target: "/test/Finances Bin/Bills/bill.pdf",
					currentBin: "VA",
					expectedBin: "Finances Bin",
					confidence: 0.75,
					reason: "Bill",
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.totalViolations).toBe(3);
			expect(data.groups).toHaveLength(2); // Work Bin and VA

			// Groups should be sorted by total violations (descending)
			const workBinGroup = data.groups.find(
				(g: { rootBin: string }) => g.rootBin === "Work Bin",
			);
			const vaGroup = data.groups.find(
				(g: { rootBin: string }) => g.rootBin === "VA",
			);

			expect(workBinGroup?.totalViolations).toBe(2);
			expect(vaGroup?.totalViolations).toBe(1);
		});

		it("should detect keyword fallback usage", async () => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/Work Bin/tax_2024.pdf",
					target: "/test/Finances Bin/Taxes/tax_2024.pdf",
					currentBin: "Work Bin",
					expectedBin: "Finances Bin",
					confidence: 0.7,
					reason: "Tax keyword found",
					keywordFallback: true,
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.usedKeywordFallback).toBe(true);
			expect(data.groups[0].violations[0].usedKeywordFallback).toBe(true);
		});

		it("should read from most recent queue file", async () => {
			// Create older queue file
			createQueueFile("20260303_100000", [
				{
					source: "/test/old.pdf",
					target: "/test/Finances Bin/old.pdf",
					currentBin: "Work Bin",
					expectedBin: "Finances Bin",
					confidence: 0.5,
					reason: "Old",
				},
			]);

			// Create newer queue file
			createQueueFile("20260303_120000", [
				{
					source: "/test/new.pdf",
					target: "/test/Finances Bin/new.pdf",
					currentBin: "Work Bin",
					expectedBin: "Finances Bin",
					confidence: 0.9,
					reason: "New",
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			// Should include violations from both files
			expect(data.totalViolations).toBe(2);
		});
	});

	// ============================================================================
	// GET /api/scatter-report - Queue error handling
	// ============================================================================

	describe("GET - Queue error handling", () => {
		it("should return error when queue directory does not exist", async () => {
			// Remove the queue directory
			rmSync(queueDir, { recursive: true, force: true });

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(500);
			const data = await response.json();
			expect(data.error).toBe("Queue directory does not exist");
		});

		it("should skip invalid JSON files in queue", async () => {
			// Create a valid queue file
			createQueueFile("20260303_120000", [
				{
					source: "/test/valid.pdf",
					target: "/test/Finances Bin/valid.pdf",
					currentBin: "Work Bin",
					expectedBin: "Finances Bin",
					confidence: 0.85,
					reason: "Valid",
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
			// Should still return the valid violation
			expect(data.totalViolations).toBe(1);
		});
	});

	// ============================================================================
	// POST /api/scatter-report - Parameter validation tests
	// ============================================================================

	describe("POST - Parameter validation", () => {
		it("should return 400 for invalid JSON body", async () => {
			const request = new NextRequest("http://localhost/api/scatter-report", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: "invalid json",
			});

			const response = await POST(request);

			expect(response.status).toBe(400);
			const data = await response.json();
			expect(data.error).toBe("Invalid JSON in request body");
		});

		it("should return 400 if basePath is missing", async () => {
			const request = createPostRequest({});
			const response = await POST(request);

			expect(response.status).toBe(400);
			const data = await response.json();
			expect(data.error).toBe("basePath is required");
		});

		it("should return 400 if basePath is not absolute", async () => {
			const request = createPostRequest({ basePath: "relative/path" });
			const response = await POST(request);

			expect(response.status).toBe(400);
			const data = await response.json();
			expect(data.error).toBe("basePath must be an absolute path");
		});

		it("should return 404 if basePath does not exist", async () => {
			const request = createPostRequest({ basePath: "/nonexistent/path" });
			const response = await POST(request);

			expect(response.status).toBe(404);
			const data = await response.json();
			expect(data.error).toBe("basePath does not exist");
		});
	});

	// ============================================================================
	// Response structure tests
	// ============================================================================

	describe("Response structure", () => {
		it("should return proper response structure from queue", async () => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/file.pdf",
					target: "/test/Finances Bin/file.pdf",
					currentBin: "Work Bin",
					expectedBin: "Finances Bin",
					confidence: 0.85,
					reason: "Test",
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();

			// Check all required fields are present
			expect(data).toHaveProperty("groups");
			expect(data).toHaveProperty("totalViolations");
			expect(data).toHaveProperty("filesScanned");
			expect(data).toHaveProperty("filesInCorrectBin");
			expect(data).toHaveProperty("modelUsed");
			expect(data).toHaveProperty("usedKeywordFallback");
			expect(data).toHaveProperty("scannedDirectory");
			expect(data).toHaveProperty("source");

			// Verify source is "queue"
			expect(data.source).toBe("queue");
		});

		it("should return proper violation structure", async () => {
			createQueueFile("20260303_120000", [
				{
					source: "/test/Work Bin/tax_2024.pdf",
					target: "/test/Finances Bin/Taxes/2024/tax_2024.pdf",
					currentBin: "Work Bin",
					expectedBin: "Finances Bin",
					confidence: 0.85,
					reason: "Tax document",
					modelUsed: "llama3.1:8b",
				},
			]);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();

			const violation = data.groups[0].violations[0];

			// Check all violation fields are present
			expect(violation).toHaveProperty("filePath");
			expect(violation).toHaveProperty("fileName");
			expect(violation).toHaveProperty("currentBin");
			expect(violation).toHaveProperty("expectedBin");
			expect(violation).toHaveProperty("confidence");
			expect(violation).toHaveProperty("reason");
			expect(violation).toHaveProperty("modelUsed");
			expect(violation).toHaveProperty("suggestedSubpath");
			expect(violation).toHaveProperty("usedKeywordFallback");

			// Verify values
			expect(violation.filePath).toBe("/test/Work Bin/tax_2024.pdf");
			expect(violation.fileName).toBe("tax_2024.pdf");
		});
	});
});
