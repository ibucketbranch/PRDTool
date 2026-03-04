import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import path from "path";
import { GET, POST } from "@/app/api/agents/route";

describe("Agents API", () => {
	let tempDir: string;
	let organizerDir: string;
	let agentDir: string;
	let logsDir: string;

	beforeEach(() => {
		// Create a temporary directory for each test
		tempDir = mkdtempSync(path.join(tmpdir(), "agents-api-test-"));
		organizerDir = path.join(tempDir, ".organizer");
		agentDir = path.join(organizerDir, "agent");
		logsDir = path.join(agentDir, "logs");
		mkdirSync(logsDir, { recursive: true });
	});

	afterEach(() => {
		// Clean up temporary directory
		rmSync(tempDir, { recursive: true, force: true });
	});

	// Helper to create a NextRequest with query params
	function createRequest(params: Record<string, string>): NextRequest {
		const url = new URL("http://localhost/api/agents");
		for (const [key, value] of Object.entries(params)) {
			url.searchParams.set(key, value);
		}
		return new NextRequest(url);
	}

	// Helper to create agent config file
	function createAgentConfig(config?: Record<string, unknown>): void {
		const defaultConfig = {
			base_path: "/test/path",
			threshold: 0.8,
			max_depth: 4,
			content_aware: true,
			auto_execute: false,
			min_auto_confidence: 0.95,
			interval_seconds: 900,
			max_actions_per_cycle: 100,
			state_file: "agent/state.json",
			plans_dir: "agent/plans",
			logs_dir: "agent/logs",
			queue_dir: "agent/queue",
		};

		writeFileSync(
			path.join(organizerDir, "agent_config.json"),
			JSON.stringify(config || defaultConfig),
		);
	}

	// Helper to create agent state file
	function createAgentState(state?: Record<string, unknown>): void {
		const defaultState = {
			last_cycle_id: "20260221_184129",
			last_finished_at: new Date().toISOString(),
			last_status: "skipped",
			last_log: path.join(logsDir, "cycle_20260221_184129.json"),
			updated_at: new Date().toISOString(),
		};

		writeFileSync(
			path.join(agentDir, "state.json"),
			JSON.stringify(state || defaultState),
		);
	}

	// Helper to create a cycle log file
	function createCycleLog(cycleId: string, data?: Record<string, unknown>): void {
		const defaultData = {
			cycle_id: cycleId,
			started_at: new Date().toISOString(),
			finished_at: new Date().toISOString(),
			config: {
				base_path: "/test/path",
				threshold: 0.8,
				max_depth: 4,
				content_aware: true,
				auto_execute: false,
				min_auto_confidence: 0.95,
			},
			plan: {
				path: `/test/plans/plan_${cycleId}.json`,
				total_groups: 10,
				groups_to_consolidate: 8,
				groups_to_skip: 2,
			},
			queue: {
				path: `/test/queue/pending_${cycleId}.json`,
				proposal_count: 5,
			},
			execution: {
				auto_execute_enabled: false,
				executed_group_count: 0,
				moved_files: 0,
				failed_files: 0,
				status: "skipped",
			},
			empty_folder_policy: {
				kept: 4,
				review: 0,
				prune: 0,
			},
		};

		writeFileSync(
			path.join(logsDir, `cycle_${cycleId}.json`),
			JSON.stringify(data || defaultData),
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
			expect(data.agents).toHaveLength(0);
		});
	});

	// ============================================================================
	// Basic functionality tests
	// ============================================================================

	describe("Agent listing", () => {
		it("should return empty array when no agents exist", async () => {
			// Remove the agent_config.json (it doesn't exist yet)
			rmSync(organizerDir, { recursive: true, force: true });
			mkdirSync(organizerDir, { recursive: true });

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents).toHaveLength(0);
		});

		it("should return agent when config exists", async () => {
			createAgentConfig();

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents).toHaveLength(1);
			expect(data.agents[0].id).toBe("continuous-organizer");
			expect(data.agents[0].name).toBe("Continuous Organizer Agent");
			expect(data.agents[0].type).toBe("organizer");
		});

		it("should include agent config in response", async () => {
			createAgentConfig({
				base_path: "/custom/path",
				threshold: 0.9,
				auto_execute: true,
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents[0].config).not.toBeNull();
			expect(data.agents[0].config.basePath).toBe("/custom/path");
			expect(data.agents[0].config.threshold).toBe(0.9);
			expect(data.agents[0].config.autoExecute).toBe(true);
		});
	});

	// ============================================================================
	// Agent state tests
	// ============================================================================

	describe("Agent state", () => {
		it("should include agent state when state file exists", async () => {
			createAgentConfig();
			createAgentState({
				last_cycle_id: "20260221_120000",
				last_finished_at: "2026-02-21T12:00:00.000Z",
				last_status: "success",
				last_log: "/test/logs/cycle_20260221_120000.json",
				updated_at: "2026-02-21T12:00:00.000Z",
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents[0].state).not.toBeNull();
			expect(data.agents[0].state.lastCycleId).toBe("20260221_120000");
			expect(data.agents[0].state.lastStatus).toBe("success");
		});

		it("should have null state when state file does not exist", async () => {
			createAgentConfig();

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents[0].state).toBeNull();
		});
	});

	// ============================================================================
	// Agent status tests
	// ============================================================================

	describe("Agent status determination", () => {
		it("should return 'unknown' status when no state", async () => {
			createAgentConfig();

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents[0].status).toBe("unknown");
		});

		it("should return 'error' status when last status was error", async () => {
			createAgentConfig();
			createAgentState({
				last_cycle_id: "20260221_120000",
				last_finished_at: new Date().toISOString(),
				last_status: "error",
				last_log: "/test/logs/cycle.json",
				updated_at: new Date().toISOString(),
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents[0].status).toBe("error");
		});

		it("should return 'idle' status when recently run", async () => {
			createAgentConfig({
				interval_seconds: 900,
				state_file: "agent/state.json",
			});
			createAgentState({
				last_cycle_id: "20260221_120000",
				last_finished_at: new Date().toISOString(), // Just now
				last_status: "skipped",
				last_log: "/test/logs/cycle.json",
				updated_at: new Date().toISOString(),
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents[0].status).toBe("idle");
		});

		it("should return 'stopped' status when not run recently", async () => {
			createAgentConfig({
				interval_seconds: 60, // 1 minute interval
				state_file: "agent/state.json",
			});
			// Last run was 10 minutes ago (well past 2x interval)
			const oldTime = new Date(Date.now() - 10 * 60 * 1000).toISOString();
			createAgentState({
				last_cycle_id: "20260221_120000",
				last_finished_at: oldTime,
				last_status: "skipped",
				last_log: "/test/logs/cycle.json",
				updated_at: oldTime,
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents[0].status).toBe("stopped");
		});
	});

	// ============================================================================
	// Cycle log tests
	// ============================================================================

	describe("Cycle log handling", () => {
		it("should count cycle logs", async () => {
			createAgentConfig();
			createCycleLog("20260221_100000");
			createCycleLog("20260221_110000");
			createCycleLog("20260221_120000");

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents[0].cycleCount).toBe(3);
		});

		it("should include latest cycle summary", async () => {
			createAgentConfig();
			createCycleLog("20260221_100000", {
				cycle_id: "20260221_100000",
				started_at: "2026-02-21T10:00:00.000Z",
				finished_at: "2026-02-21T10:01:00.000Z",
				config: { base_path: "/old" },
				plan: { total_groups: 5 },
				queue: { proposal_count: 2 },
				execution: { status: "skipped" },
				empty_folder_policy: {},
			});
			createCycleLog("20260221_120000", {
				cycle_id: "20260221_120000",
				started_at: "2026-02-21T12:00:00.000Z",
				finished_at: "2026-02-21T12:01:00.000Z",
				config: { base_path: "/new" },
				plan: { total_groups: 10 },
				queue: { proposal_count: 5 },
				execution: { status: "success" },
				empty_folder_policy: {},
			});

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents[0].lastCycle).not.toBeNull();
			// Should return the latest cycle (20260221_120000)
			expect(data.agents[0].lastCycle.cycleId).toBe("20260221_120000");
			expect(data.agents[0].lastCycle.plan.totalGroups).toBe(10);
		});

		it("should have null lastCycle when no cycles exist", async () => {
			createAgentConfig();

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents[0].lastCycle).toBeNull();
			expect(data.agents[0].cycleCount).toBe(0);
		});
	});

	// ============================================================================
	// Error handling tests
	// ============================================================================

	describe("Error handling", () => {
		it("should handle non-existent basePath gracefully", async () => {
			const request = createRequest({ basePath: "/non/existent/path" });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents).toHaveLength(0);
		});

		it("should handle invalid JSON in config file", async () => {
			writeFileSync(
				path.join(organizerDir, "agent_config.json"),
				"invalid json",
			);

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents).toHaveLength(1);
			expect(data.agents[0].error).toBeDefined();
			expect(data.agents[0].config).toBeNull();
		});

		it("should handle invalid JSON in state file", async () => {
			createAgentConfig();
			writeFileSync(path.join(agentDir, "state.json"), "invalid json");

			const request = createRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.agents).toHaveLength(1);
			expect(data.agents[0].error).toBeDefined();
			expect(data.agents[0].state).toBeNull();
		});
	});
});

// ============================================================================
// POST /api/agents tests
// ============================================================================

describe("Agents API - POST", () => {
	let tempDir: string;
	let organizerDir: string;
	let agentDir: string;
	let logsDir: string;

	beforeEach(() => {
		// Create a temporary directory for each test
		tempDir = mkdtempSync(path.join(tmpdir(), "agents-api-post-test-"));
		organizerDir = path.join(tempDir, ".organizer");
		agentDir = path.join(organizerDir, "agent");
		logsDir = path.join(agentDir, "logs");
		mkdirSync(logsDir, { recursive: true });
	});

	afterEach(() => {
		// Clean up temporary directory
		rmSync(tempDir, { recursive: true, force: true });
	});

	// Helper to create a POST request
	function createPostRequest(body: unknown): NextRequest {
		return new NextRequest("http://localhost/api/agents", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify(body),
		});
	}

	// Helper to create agent config file
	function createAgentConfig(config?: Record<string, unknown>): void {
		const defaultConfig = {
			base_path: "/test/path",
			threshold: 0.8,
			max_depth: 4,
			content_aware: true,
			auto_execute: false,
			min_auto_confidence: 0.95,
			interval_seconds: 900,
			max_actions_per_cycle: 100,
			state_file: "agent/state.json",
			plans_dir: "agent/plans",
			logs_dir: "agent/logs",
			queue_dir: "agent/queue",
		};

		writeFileSync(
			path.join(organizerDir, "agent_config.json"),
			JSON.stringify(config || defaultConfig),
		);
	}

	// ============================================================================
	// Validation tests
	// ============================================================================

	describe("Parameter validation", () => {
		it("should return 400 for invalid JSON body", async () => {
			const request = new NextRequest("http://localhost/api/agents", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: "invalid json",
			});

			const response = await POST(request);

			expect(response.status).toBe(400);
			const data = await response.json();
			expect(data.success).toBe(false);
			expect(data.error).toBe("Invalid JSON");
		});

		it("should return 400 if basePath is missing", async () => {
			const request = createPostRequest({
				agentId: "continuous-organizer",
				action: "run-once",
			});

			const response = await POST(request);

			expect(response.status).toBe(400);
			const data = await response.json();
			expect(data.success).toBe(false);
			expect(data.message).toContain("basePath");
		});

		it("should return 400 if agentId is missing", async () => {
			const request = createPostRequest({
				basePath: tempDir,
				action: "run-once",
			});

			const response = await POST(request);

			expect(response.status).toBe(400);
			const data = await response.json();
			expect(data.success).toBe(false);
			expect(data.message).toContain("agentId");
		});

		it("should return 400 if action is missing", async () => {
			const request = createPostRequest({
				basePath: tempDir,
				agentId: "continuous-organizer",
			});

			const response = await POST(request);

			expect(response.status).toBe(400);
			const data = await response.json();
			expect(data.success).toBe(false);
			expect(data.message).toContain("Invalid action");
		});

		it("should return 400 for invalid action", async () => {
			const request = createPostRequest({
				basePath: tempDir,
				agentId: "continuous-organizer",
				action: "invalid-action",
			});

			const response = await POST(request);

			expect(response.status).toBe(400);
			const data = await response.json();
			expect(data.success).toBe(false);
			expect(data.message).toContain("Invalid action");
			expect(data.message).toContain("run-once");
			expect(data.message).toContain("start");
			expect(data.message).toContain("stop");
			expect(data.message).toContain("restart");
		});
	});

	// ============================================================================
	// Agent not found tests
	// ============================================================================

	describe("Agent existence check", () => {
		it("should return 404 if agent does not exist", async () => {
			// No agent config created
			const request = createPostRequest({
				basePath: tempDir,
				agentId: "continuous-organizer",
				action: "run-once",
			});

			const response = await POST(request);

			expect(response.status).toBe(404);
			const data = await response.json();
			expect(data.success).toBe(false);
			expect(data.message).toContain("Agent not found");
		});

		it("should return 404 for non-existent agent ID", async () => {
			createAgentConfig();

			const request = createPostRequest({
				basePath: tempDir,
				agentId: "unknown-agent",
				action: "run-once",
			});

			const response = await POST(request);

			expect(response.status).toBe(404);
			const data = await response.json();
			expect(data.success).toBe(false);
			expect(data.message).toContain("Agent not found");
		});
	});

	// ============================================================================
	// Action execution tests
	// ============================================================================
	// Note: Full execution tests require integration testing with exec.
	// These tests verify the API routes and validates proper routing.

	describe("Action execution", () => {
		beforeEach(() => {
			createAgentConfig();
		});

		it("should return proper action in response for run-once", async () => {
			const request = createPostRequest({
				basePath: tempDir,
				agentId: "continuous-organizer",
				action: "run-once",
			});

			const response = await POST(request);
			const data = await response.json();

			// Regardless of exec result, the action should be correct
			expect(data.action).toBe("run-once");
			expect(data.agentId).toBe("continuous-organizer");
		});

		it("should return proper action in response for start", async () => {
			const request = createPostRequest({
				basePath: tempDir,
				agentId: "continuous-organizer",
				action: "start",
			});

			const response = await POST(request);
			const data = await response.json();

			expect(data.action).toBe("start");
			expect(data.agentId).toBe("continuous-organizer");
		});

		it("should return proper action in response for stop", async () => {
			const request = createPostRequest({
				basePath: tempDir,
				agentId: "continuous-organizer",
				action: "stop",
			});

			const response = await POST(request);
			const data = await response.json();

			expect(data.action).toBe("stop");
			expect(data.agentId).toBe("continuous-organizer");
		});

		it("should return proper action in response for restart", async () => {
			const request = createPostRequest({
				basePath: tempDir,
				agentId: "continuous-organizer",
				action: "restart",
			});

			const response = await POST(request);
			const data = await response.json();

			expect(data.action).toBe("restart");
			expect(data.agentId).toBe("continuous-organizer");
		});
	});
});
