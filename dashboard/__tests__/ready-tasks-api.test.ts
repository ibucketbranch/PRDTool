import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import path from "path";
import { GET } from "@/app/api/agents/ready-tasks/route";

describe("Ready Tasks API", () => {
	let tempDir: string;
	let organizerDir: string;
	let agentDir: string;

	beforeEach(() => {
		// Create a temporary directory for each test
		tempDir = mkdtempSync(path.join(tmpdir(), "ready-tasks-api-test-"));
		organizerDir = path.join(tempDir, ".organizer");
		agentDir = path.join(organizerDir, "agent");
		mkdirSync(agentDir, { recursive: true });
	});

	afterEach(() => {
		// Clean up temporary directory
		rmSync(tempDir, { recursive: true, force: true });
	});

	// Helper to create a NextRequest with query params
	function createRequest(params: Record<string, string>): NextRequest {
		const url = new URL("http://localhost/api/agents/ready-tasks");
		for (const [key, value] of Object.entries(params)) {
			url.searchParams.set(key, value);
		}
		return new NextRequest(url);
	}

	// Helper to create task status file
	function createTaskStatusFile(tasks: Record<string, unknown>): void {
		const statusData = {
			updated_at: new Date().toISOString(),
			tasks,
		};
		writeFileSync(
			path.join(agentDir, "prd_task_status.json"),
			JSON.stringify(statusData),
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
			expect(data.ready_tasks).toHaveLength(0);
			expect(data.total_count).toBe(0);
		});

		it("should include timestamp in response", async () => {
			const request = createRequest({});
			const response = await GET(request);

			const data = await response.json();
			expect(data.timestamp).toBeDefined();
			// Check timestamp is a valid ISO string
			expect(new Date(data.timestamp).toISOString()).toBe(data.timestamp);
		});
	});

	// ============================================================================
	// Empty/missing file tests
	// ============================================================================

	describe("Missing status file", () => {
		it("should return empty array when status file does not exist", async () => {
			// Don't create status file
			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(0);
			expect(data.total_count).toBe(0);
			expect(data.error).toBeUndefined();
		});

		it("should return empty array when basePath does not exist", async () => {
			const request = createRequest({ basePath: "/non/existent/path" });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(0);
			expect(data.total_count).toBe(0);
		});
	});

	// ============================================================================
	// Ready tasks filtering tests
	// ============================================================================

	describe("Ready tasks filtering", () => {
		it("should return only tasks with ready status", async () => {
			createTaskStatusFile({
				"phase11.1": {
					task_id: "phase11.1",
					status: "ready",
					last_dry_run_at: "2026-03-03T10:00:00.000Z",
					last_errors: [],
					marked_ready_at: "2026-03-03T10:01:00.000Z",
					history: [],
				},
				"phase11.2": {
					task_id: "phase11.2",
					status: "dry_run_pass",
					last_dry_run_at: "2026-03-03T10:00:00.000Z",
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
				"phase11.3": {
					task_id: "phase11.3",
					status: "dry_run_fail",
					last_dry_run_at: "2026-03-03T10:00:00.000Z",
					last_errors: ["Error 1"],
					marked_ready_at: null,
					history: [],
				},
				"phase12.1": {
					task_id: "phase12.1",
					status: "ready",
					last_dry_run_at: "2026-03-03T11:00:00.000Z",
					last_errors: [],
					marked_ready_at: "2026-03-03T11:01:00.000Z",
					history: [],
				},
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(2);
			expect(data.total_count).toBe(2);

			// Should only contain ready tasks
			const taskIds = data.ready_tasks.map(
				(t: { task_id: string }) => t.task_id,
			);
			expect(taskIds).toContain("phase11.1");
			expect(taskIds).toContain("phase12.1");
			expect(taskIds).not.toContain("phase11.2");
			expect(taskIds).not.toContain("phase11.3");
		});

		it("should return empty array when no tasks have ready status", async () => {
			createTaskStatusFile({
				"phase11.1": {
					task_id: "phase11.1",
					status: "untested",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
				"phase11.2": {
					task_id: "phase11.2",
					status: "dry_run_fail",
					last_dry_run_at: "2026-03-03T10:00:00.000Z",
					last_errors: ["Error 1"],
					marked_ready_at: null,
					history: [],
				},
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(0);
			expect(data.total_count).toBe(0);
		});

		it("should return empty array when tasks object is empty", async () => {
			createTaskStatusFile({});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(0);
			expect(data.total_count).toBe(0);
		});
	});

	// ============================================================================
	// Task data structure tests
	// ============================================================================

	describe("Task data structure", () => {
		it("should include all required fields in ready tasks", async () => {
			createTaskStatusFile({
				"phase11.1": {
					task_id: "phase11.1",
					status: "ready",
					last_dry_run_at: "2026-03-03T10:00:00.000Z",
					last_errors: [],
					marked_ready_at: "2026-03-03T10:01:00.000Z",
					history: [
						{
							timestamp: "2026-03-03T10:00:00.000Z",
							event: "dry_run_pass",
							from_status: "untested",
							to_status: "dry_run_pass",
						},
						{
							timestamp: "2026-03-03T10:01:00.000Z",
							event: "marked_ready",
							from_status: "dry_run_pass",
							to_status: "ready",
						},
					],
				},
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(1);

			const task = data.ready_tasks[0];
			expect(task.task_id).toBe("phase11.1");
			expect(task.status).toBe("ready");
			expect(task.last_dry_run_at).toBe("2026-03-03T10:00:00.000Z");
			expect(task.last_errors).toEqual([]);
			expect(task.marked_ready_at).toBe("2026-03-03T10:01:00.000Z");
			expect(task.history).toHaveLength(2);
			expect(task.history[0].event).toBe("dry_run_pass");
			expect(task.history[1].event).toBe("marked_ready");
		});

		it("should handle tasks with null dates", async () => {
			createTaskStatusFile({
				"phase11.1": {
					task_id: "phase11.1",
					status: "ready",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(1);

			const task = data.ready_tasks[0];
			expect(task.last_dry_run_at).toBeNull();
			expect(task.marked_ready_at).toBeNull();
		});

		it("should handle missing optional fields", async () => {
			createTaskStatusFile({
				"phase11.1": {
					task_id: "phase11.1",
					status: "ready",
				},
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(1);

			const task = data.ready_tasks[0];
			expect(task.last_errors).toEqual([]);
			expect(task.history).toEqual([]);
		});
	});

	// ============================================================================
	// Sorting tests
	// ============================================================================

	describe("Task sorting", () => {
		it("should sort tasks by phase order", async () => {
			createTaskStatusFile({
				"phase15.1": {
					task_id: "phase15.1",
					status: "ready",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
				"phase11.1": {
					task_id: "phase11.1",
					status: "ready",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
				"phase12.1": {
					task_id: "phase12.1",
					status: "ready",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(3);

			// Should be sorted by phase
			expect(data.ready_tasks[0].task_id).toBe("phase11.1");
			expect(data.ready_tasks[1].task_id).toBe("phase12.1");
			expect(data.ready_tasks[2].task_id).toBe("phase15.1");
		});

		it("should sort tasks by task order within phase", async () => {
			createTaskStatusFile({
				"phase11.3": {
					task_id: "phase11.3",
					status: "ready",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
				"phase11.1": {
					task_id: "phase11.1",
					status: "ready",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
				"phase11.2": {
					task_id: "phase11.2",
					status: "ready",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(3);

			// Should be sorted by task number within phase
			expect(data.ready_tasks[0].task_id).toBe("phase11.1");
			expect(data.ready_tasks[1].task_id).toBe("phase11.2");
			expect(data.ready_tasks[2].task_id).toBe("phase11.3");
		});

		it("should handle non-numeric task identifiers", async () => {
			createTaskStatusFile({
				"phase12.scatter_detector": {
					task_id: "phase12.scatter_detector",
					status: "ready",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
				"phase12.lock_bins": {
					task_id: "phase12.lock_bins",
					status: "ready",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(2);

			// Should sort alphabetically for non-numeric task ids
			expect(data.ready_tasks[0].task_id).toBe("phase12.lock_bins");
			expect(data.ready_tasks[1].task_id).toBe("phase12.scatter_detector");
		});

		it("should handle mixed numeric and non-numeric task identifiers", async () => {
			createTaskStatusFile({
				"phase11.2": {
					task_id: "phase11.2",
					status: "ready",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
				"phase11.1": {
					task_id: "phase11.1",
					status: "ready",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
				"phase12.scatter": {
					task_id: "phase12.scatter",
					status: "ready",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(3);

			// Phase 11 tasks first, then phase 12
			expect(data.ready_tasks[0].task_id).toBe("phase11.1");
			expect(data.ready_tasks[1].task_id).toBe("phase11.2");
			expect(data.ready_tasks[2].task_id).toBe("phase12.scatter");
		});
	});

	// ============================================================================
	// Error handling tests
	// ============================================================================

	describe("Error handling", () => {
		it("should return 500 for invalid JSON in status file", async () => {
			writeFileSync(
				path.join(agentDir, "prd_task_status.json"),
				"invalid json",
			);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(500);
			const data = await response.json();
			expect(data.error).toContain("Failed to read status file");
			expect(data.ready_tasks).toHaveLength(0);
			expect(data.total_count).toBe(0);
		});

		it("should handle file with missing tasks key", async () => {
			writeFileSync(
				path.join(agentDir, "prd_task_status.json"),
				JSON.stringify({ updated_at: new Date().toISOString() }),
			);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.ready_tasks).toHaveLength(0);
			expect(data.total_count).toBe(0);
		});
	});

	// ============================================================================
	// Integration-style tests
	// ============================================================================

	describe("Full lifecycle scenarios", () => {
		it("should correctly identify ready tasks from full lifecycle data", async () => {
			createTaskStatusFile({
				"phase11.dry_run_validator": {
					task_id: "phase11.dry_run_validator",
					status: "ready",
					last_dry_run_at: "2026-03-03T09:00:00.000Z",
					last_errors: [],
					marked_ready_at: "2026-03-03T09:01:00.000Z",
					history: [
						{
							timestamp: "2026-03-03T08:00:00.000Z",
							event: "dry_run_fail",
							from_status: "untested",
							to_status: "dry_run_fail",
							errors: ["pytest failed"],
						},
						{
							timestamp: "2026-03-03T09:00:00.000Z",
							event: "dry_run_pass",
							from_status: "dry_run_fail",
							to_status: "dry_run_pass",
						},
						{
							timestamp: "2026-03-03T09:01:00.000Z",
							event: "marked_ready",
							from_status: "dry_run_pass",
							to_status: "ready",
						},
					],
				},
				"phase11.cli_flag": {
					task_id: "phase11.cli_flag",
					status: "ready",
					last_dry_run_at: "2026-03-03T10:00:00.000Z",
					last_errors: [],
					marked_ready_at: "2026-03-03T10:01:00.000Z",
					history: [
						{
							timestamp: "2026-03-03T10:00:00.000Z",
							event: "dry_run_pass",
							from_status: "untested",
							to_status: "dry_run_pass",
						},
						{
							timestamp: "2026-03-03T10:01:00.000Z",
							event: "marked_ready",
							from_status: "dry_run_pass",
							to_status: "ready",
						},
					],
				},
				"phase11.ready_endpoint": {
					task_id: "phase11.ready_endpoint",
					status: "dry_run_pass",
					last_dry_run_at: "2026-03-03T11:00:00.000Z",
					last_errors: [],
					marked_ready_at: null,
					history: [
						{
							timestamp: "2026-03-03T11:00:00.000Z",
							event: "dry_run_pass",
							from_status: "untested",
							to_status: "dry_run_pass",
						},
					],
				},
				"phase12.scatter_detector": {
					task_id: "phase12.scatter_detector",
					status: "untested",
					last_dry_run_at: null,
					last_errors: [],
					marked_ready_at: null,
					history: [],
				},
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();

			// Should only return the 2 ready tasks
			expect(data.ready_tasks).toHaveLength(2);
			expect(data.total_count).toBe(2);

			// Should be sorted by task order
			expect(data.ready_tasks[0].task_id).toBe("phase11.cli_flag");
			expect(data.ready_tasks[1].task_id).toBe("phase11.dry_run_validator");

			// Each should have full history
			expect(data.ready_tasks[0].history).toHaveLength(2);
			expect(data.ready_tasks[1].history).toHaveLength(3);
		});
	});
});
