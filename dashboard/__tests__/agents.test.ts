import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import path from "path";
import {
	getAgents,
	getAgentById,
	controlAgent,
	runAgentOnce,
	type AgentConfig,
	type AgentState,
	type AgentCycleSummary,
} from "@/lib/agents";

describe("Agents Library", () => {
	let tempDir: string;
	let organizerDir: string;
	let agentDir: string;
	let logsDir: string;

	beforeEach(() => {
		// Create a temporary directory for each test
		tempDir = mkdtempSync(path.join(tmpdir(), "agents-lib-test-"));
		organizerDir = path.join(tempDir, ".organizer");
		agentDir = path.join(organizerDir, "agent");
		logsDir = path.join(agentDir, "logs");
		mkdirSync(logsDir, { recursive: true });
	});

	afterEach(() => {
		// Clean up temporary directory
		rmSync(tempDir, { recursive: true, force: true });
	});

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
	function createCycleLog(
		cycleId: string,
		data?: Record<string, unknown>,
	): void {
		const defaultData = {
			cycle_id: cycleId,
			started_at: "2026-02-21T10:00:00.000Z",
			finished_at: "2026-02-21T10:01:00.000Z",
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
	// getAgents tests
	// ============================================================================

	describe("getAgents", () => {
		it("should return empty array when organizer dir does not exist", () => {
			const result = getAgents("/non/existent/path");
			expect(result.agents).toHaveLength(0);
			expect(result.error).toBeUndefined();
		});

		it("should return empty array when no agent config exists", () => {
			const result = getAgents(organizerDir);
			expect(result.agents).toHaveLength(0);
			expect(result.error).toBeUndefined();
		});

		it("should return agent when config exists", () => {
			createAgentConfig();
			const result = getAgents(organizerDir);

			expect(result.agents).toHaveLength(1);
			expect(result.agents[0].id).toBe("continuous-organizer");
			expect(result.agents[0].name).toBe("Continuous Organizer Agent");
			expect(result.agents[0].type).toBe("organizer");
		});

		it("should parse config correctly", () => {
			createAgentConfig({
				base_path: "/custom/path",
				threshold: 0.9,
				max_depth: 5,
				content_aware: false,
				auto_execute: true,
				min_auto_confidence: 0.99,
				interval_seconds: 600,
				max_actions_per_cycle: 50,
				state_file: "custom/state.json",
				plans_dir: "custom/plans",
				logs_dir: "custom/logs",
				queue_dir: "custom/queue",
			});

			const result = getAgents(organizerDir);
			const config = result.agents[0].config as AgentConfig;

			expect(config.basePath).toBe("/custom/path");
			expect(config.threshold).toBe(0.9);
			expect(config.maxDepth).toBe(5);
			expect(config.contentAware).toBe(false);
			expect(config.autoExecute).toBe(true);
			expect(config.minAutoConfidence).toBe(0.99);
			expect(config.intervalSeconds).toBe(600);
			expect(config.maxActionsPerCycle).toBe(50);
		});

		it("should parse state correctly", () => {
			createAgentConfig();
			createAgentState({
				last_cycle_id: "test_cycle",
				last_finished_at: "2026-02-21T12:00:00.000Z",
				last_status: "success",
				last_log: "/path/to/log.json",
				updated_at: "2026-02-21T12:00:00.000Z",
			});

			const result = getAgents(organizerDir);
			const state = result.agents[0].state as AgentState;

			expect(state.lastCycleId).toBe("test_cycle");
			expect(state.lastFinishedAt).toBe("2026-02-21T12:00:00.000Z");
			expect(state.lastStatus).toBe("success");
			expect(state.lastLog).toBe("/path/to/log.json");
		});

		it("should parse cycle summary correctly", () => {
			createAgentConfig();
			createCycleLog("20260221_120000", {
				cycle_id: "20260221_120000",
				started_at: "2026-02-21T12:00:00.000Z",
				finished_at: "2026-02-21T12:01:00.000Z",
				config: {
					base_path: "/test",
					threshold: 0.8,
					max_depth: 4,
					content_aware: true,
					auto_execute: false,
					min_auto_confidence: 0.95,
				},
				plan: {
					path: "/test/plan.json",
					total_groups: 100,
					groups_to_consolidate: 80,
					groups_to_skip: 20,
				},
				queue: {
					path: "/test/queue.json",
					proposal_count: 50,
				},
				execution: {
					auto_execute_enabled: true,
					executed_group_count: 10,
					moved_files: 25,
					failed_files: 2,
					status: "partial",
				},
				empty_folder_policy: {
					kept: 10,
					review: 5,
					prune: 3,
				},
			});

			const result = getAgents(organizerDir);
			const cycle = result.agents[0].lastCycle as AgentCycleSummary;

			expect(cycle.cycleId).toBe("20260221_120000");
			expect(cycle.plan.totalGroups).toBe(100);
			expect(cycle.plan.groupsToConsolidate).toBe(80);
			expect(cycle.queue.proposalCount).toBe(50);
			expect(cycle.execution.movedFiles).toBe(25);
			expect(cycle.execution.failedFiles).toBe(2);
			expect(cycle.emptyFolderPolicy.kept).toBe(10);
		});

		it("should handle missing config fields gracefully", () => {
			createAgentConfig({}); // Empty config

			const result = getAgents(organizerDir);
			const config = result.agents[0].config as AgentConfig;

			// Should use defaults
			expect(config.basePath).toBe("");
			expect(config.threshold).toBe(0.8);
			expect(config.maxDepth).toBe(4);
		});
	});

	// ============================================================================
	// getAgentById tests
	// ============================================================================

	describe("getAgentById", () => {
		it("should return agent by ID", () => {
			createAgentConfig();
			const result = getAgentById(organizerDir, "continuous-organizer");

			expect(result.agent).not.toBeNull();
			expect(result.agent?.id).toBe("continuous-organizer");
			expect(result.error).toBeUndefined();
		});

		it("should return error for non-existent agent", () => {
			createAgentConfig();
			const result = getAgentById(organizerDir, "non-existent-agent");

			expect(result.agent).toBeNull();
			expect(result.error).toBe("Agent not found: non-existent-agent");
		});

		it("should return error when no agents exist", () => {
			const result = getAgentById(organizerDir, "continuous-organizer");

			expect(result.agent).toBeNull();
			expect(result.error).toBe("Agent not found: continuous-organizer");
		});
	});

	// ============================================================================
	// Edge cases
	// ============================================================================

	describe("Edge cases", () => {
		it("should handle invalid JSON in config", () => {
			writeFileSync(
				path.join(organizerDir, "agent_config.json"),
				"not valid json",
			);

			const result = getAgents(organizerDir);

			expect(result.agents).toHaveLength(1);
			expect(result.agents[0].config).toBeNull();
			expect(result.agents[0].error).toContain("Failed to read config");
		});

		it("should handle invalid JSON in state", () => {
			createAgentConfig();
			writeFileSync(path.join(agentDir, "state.json"), "not valid json");

			const result = getAgents(organizerDir);

			expect(result.agents).toHaveLength(1);
			expect(result.agents[0].state).toBeNull();
			expect(result.agents[0].error).toContain("Failed to read state");
		});

		it("should handle invalid JSON in cycle log", () => {
			createAgentConfig();
			writeFileSync(
				path.join(logsDir, "cycle_20260221_120000.json"),
				"not valid json",
			);

			const result = getAgents(organizerDir);

			// Should still work, just no lastCycle
			expect(result.agents).toHaveLength(1);
			expect(result.agents[0].lastCycle).toBeNull();
		});

		it("should count only cycle_ prefixed logs", () => {
			createAgentConfig();
			createCycleLog("20260221_100000");
			createCycleLog("20260221_110000");
			// Create non-cycle files
			writeFileSync(path.join(logsDir, "launchd_stdout.log"), "stdout");
			writeFileSync(path.join(logsDir, "launchd_stderr.log"), "stderr");
			writeFileSync(path.join(logsDir, "other.json"), "{}");

			const result = getAgents(organizerDir);

			expect(result.agents[0].cycleCount).toBe(2);
		});

		it("should get latest cycle log based on filename", () => {
			createAgentConfig();
			createCycleLog("20260221_100000", { cycle_id: "20260221_100000" });
			createCycleLog("20260221_120000", { cycle_id: "20260221_120000" });
			createCycleLog("20260221_110000", { cycle_id: "20260221_110000" });

			const result = getAgents(organizerDir);

			// Should return 20260221_120000 as it's lexicographically last
			expect(result.agents[0].lastCycle?.cycleId).toBe("20260221_120000");
		});
	});

	// ============================================================================
	// Agent control tests
	// ============================================================================
	// Note: Control functions that call exec internally require integration tests.
	// The API endpoints are tested in agents-api.test.ts.

	describe("Agent control functions", () => {
		describe("runAgentOnce", () => {
			it("should return error for unsupported agent", async () => {
				const result = await runAgentOnce("/test/path", "unknown-agent");

				expect(result.success).toBe(false);
				expect(result.error).toContain("Unknown agent");
			});
		});

		describe("controlAgent", () => {
			it("should return error for invalid action", async () => {
				const result = await controlAgent(
					"/test/path",
					"continuous-organizer",
					"invalid" as any,
				);

				expect(result.success).toBe(false);
				expect(result.error).toContain("Invalid action");
			});
		});
	});
});
