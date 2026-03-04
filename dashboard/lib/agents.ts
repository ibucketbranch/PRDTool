/**
 * Agent utilities for Dashboard
 *
 * Provides functions to read agent state and configuration from the .organizer directory.
 * Also provides control functions for starting, stopping, and triggering agent cycles.
 */

import { readFileSync, existsSync, readdirSync } from "fs";
import { exec } from "child_process";
import path from "path";

// ============================================================================
// Types
// ============================================================================

/**
 * Agent status enum
 */
export type AgentStatus = "running" | "idle" | "stopped" | "error" | "unknown";

/**
 * Agent configuration
 */
export interface AgentConfig {
	basePath: string;
	threshold: number;
	maxDepth: number;
	contentAware: boolean;
	autoExecute: boolean;
	minAutoConfidence: number;
	intervalSeconds: number;
	maxActionsPerCycle: number;
	stateFile: string;
	plansDir: string;
	logsDir: string;
	queueDir: string;
}

/**
 * Agent state from state.json
 */
export interface AgentState {
	lastCycleId: string;
	lastFinishedAt: string;
	lastStatus: string;
	lastLog: string;
	updatedAt: string;
}

/**
 * Agent cycle summary from cycle log
 */
export interface AgentCycleSummary {
	cycleId: string;
	startedAt: string;
	finishedAt: string;
	config: {
		basePath: string;
		threshold: number;
		maxDepth: number;
		contentAware: boolean;
		autoExecute: boolean;
		minAutoConfidence: number;
	};
	plan: {
		path: string;
		totalGroups: number;
		groupsToConsolidate: number;
		groupsToSkip: number;
	};
	queue: {
		path: string;
		proposalCount: number;
	};
	execution: {
		autoExecuteEnabled: boolean;
		executedGroupCount: number;
		movedFiles: number;
		failedFiles: number;
		status: string;
	};
	emptyFolderPolicy: {
		kept: number;
		review: number;
		prune: number;
	};
}

/**
 * Agent information
 */
export interface AgentInfo {
	id: string;
	name: string;
	type: string;
	status: AgentStatus;
	config: AgentConfig | null;
	state: AgentState | null;
	lastCycle: AgentCycleSummary | null;
	cycleCount: number;
	error?: string;
}

/**
 * Result from getting agents
 */
export interface AgentsResult {
	agents: AgentInfo[];
	error?: string;
}

/**
 * Agent control action types
 */
export type AgentAction = "run-once" | "start" | "stop" | "restart";

/**
 * Result from agent control action
 */
export interface AgentControlResult {
	success: boolean;
	action: AgentAction;
	agentId: string;
	message: string;
	error?: string;
	output?: string;
}

// ============================================================================
// Helper functions
// ============================================================================

/**
 * Parse agent config from JSON file
 */
function parseAgentConfig(
	rawConfig: Record<string, unknown>,
): AgentConfig | null {
	try {
		return {
			basePath: String(rawConfig.base_path ?? ""),
			threshold: Number(rawConfig.threshold ?? 0.8),
			maxDepth: Number(rawConfig.max_depth ?? 4),
			contentAware: Boolean(rawConfig.content_aware ?? true),
			autoExecute: Boolean(rawConfig.auto_execute ?? false),
			minAutoConfidence: Number(rawConfig.min_auto_confidence ?? 0.95),
			intervalSeconds: Number(rawConfig.interval_seconds ?? 900),
			maxActionsPerCycle: Number(rawConfig.max_actions_per_cycle ?? 100),
			stateFile: String(rawConfig.state_file ?? ""),
			plansDir: String(rawConfig.plans_dir ?? ""),
			logsDir: String(rawConfig.logs_dir ?? ""),
			queueDir: String(rawConfig.queue_dir ?? ""),
		};
	} catch {
		return null;
	}
}

/**
 * Parse agent state from JSON file
 */
function parseAgentState(rawState: Record<string, unknown>): AgentState | null {
	try {
		return {
			lastCycleId: String(rawState.last_cycle_id ?? ""),
			lastFinishedAt: String(rawState.last_finished_at ?? ""),
			lastStatus: String(rawState.last_status ?? ""),
			lastLog: String(rawState.last_log ?? ""),
			updatedAt: String(rawState.updated_at ?? ""),
		};
	} catch {
		return null;
	}
}

/**
 * Parse cycle summary from JSON file
 */
function parseCycleSummary(
	rawCycle: Record<string, unknown>,
): AgentCycleSummary | null {
	try {
		const config = rawCycle.config as Record<string, unknown>;
		const plan = rawCycle.plan as Record<string, unknown>;
		const queue = rawCycle.queue as Record<string, unknown>;
		const execution = rawCycle.execution as Record<string, unknown>;
		const emptyFolderPolicy = rawCycle.empty_folder_policy as Record<
			string,
			unknown
		>;

		return {
			cycleId: String(rawCycle.cycle_id ?? ""),
			startedAt: String(rawCycle.started_at ?? ""),
			finishedAt: String(rawCycle.finished_at ?? ""),
			config: {
				basePath: String(config?.base_path ?? ""),
				threshold: Number(config?.threshold ?? 0),
				maxDepth: Number(config?.max_depth ?? 0),
				contentAware: Boolean(config?.content_aware ?? false),
				autoExecute: Boolean(config?.auto_execute ?? false),
				minAutoConfidence: Number(config?.min_auto_confidence ?? 0),
			},
			plan: {
				path: String(plan?.path ?? ""),
				totalGroups: Number(plan?.total_groups ?? 0),
				groupsToConsolidate: Number(plan?.groups_to_consolidate ?? 0),
				groupsToSkip: Number(plan?.groups_to_skip ?? 0),
			},
			queue: {
				path: String(queue?.path ?? ""),
				proposalCount: Number(queue?.proposal_count ?? 0),
			},
			execution: {
				autoExecuteEnabled: Boolean(execution?.auto_execute_enabled ?? false),
				executedGroupCount: Number(execution?.executed_group_count ?? 0),
				movedFiles: Number(execution?.moved_files ?? 0),
				failedFiles: Number(execution?.failed_files ?? 0),
				status: String(execution?.status ?? ""),
			},
			emptyFolderPolicy: {
				kept: Number(emptyFolderPolicy?.kept ?? 0),
				review: Number(emptyFolderPolicy?.review ?? 0),
				prune: Number(emptyFolderPolicy?.prune ?? 0),
			},
		};
	} catch {
		return null;
	}
}

/**
 * Determine agent status from state and config
 */
function determineAgentStatus(
	state: AgentState | null,
	config: AgentConfig | null,
): AgentStatus {
	if (!state || !config) {
		return "unknown";
	}

	// Check if the agent has run recently (within 2x interval)
	const lastFinished = new Date(state.lastFinishedAt).getTime();
	const now = Date.now();
	const intervalMs = config.intervalSeconds * 1000;
	const timeSinceLastRun = now - lastFinished;

	if (state.lastStatus === "error") {
		return "error";
	}

	// If last run was within 2x interval, consider it running/idle
	if (timeSinceLastRun < intervalMs * 2) {
		return "idle";
	}

	// If it's been too long since last run, consider it stopped
	return "stopped";
}

/**
 * Count cycle logs in a directory
 */
function countCycleLogs(logsDir: string): number {
	try {
		if (!existsSync(logsDir)) {
			return 0;
		}
		const files = readdirSync(logsDir);
		return files.filter((f) => f.match(/^cycle_\d+_\d+\.json$/)).length;
	} catch {
		return 0;
	}
}

/**
 * Get the latest cycle log
 */
function getLatestCycleLog(logsDir: string): AgentCycleSummary | null {
	try {
		if (!existsSync(logsDir)) {
			return null;
		}

		const files = readdirSync(logsDir);
		const cycleFiles = files
			.filter((f) => f.match(/^cycle_\d+_\d+\.json$/))
			.sort()
			.reverse();

		if (cycleFiles.length === 0) {
			return null;
		}

		const latestLogPath = path.join(logsDir, cycleFiles[0]);
		const content = readFileSync(latestLogPath, "utf-8");
		const rawCycle = JSON.parse(content) as Record<string, unknown>;
		return parseCycleSummary(rawCycle);
	} catch {
		return null;
	}
}

// ============================================================================
// Main functions
// ============================================================================

/**
 * Get all known agents with their status
 *
 * @param organizerDir - Path to the .organizer directory
 * @returns List of agent info
 */
export function getAgents(organizerDir: string): AgentsResult {
	try {
		const agents: AgentInfo[] = [];

		// Check for continuous organizer agent
		const agentConfigPath = path.join(organizerDir, "agent_config.json");

		if (existsSync(agentConfigPath)) {
			let config: AgentConfig | null = null;
			let state: AgentState | null = null;
			let lastCycle: AgentCycleSummary | null = null;
			let cycleCount = 0;
			let error: string | undefined;

			try {
				const configContent = readFileSync(agentConfigPath, "utf-8");
				const rawConfig = JSON.parse(configContent) as Record<string, unknown>;
				config = parseAgentConfig(rawConfig);
			} catch (err) {
				error = `Failed to read config: ${err instanceof Error ? err.message : "Unknown error"}`;
			}

			// Try to read state
			// Config paths are relative to the base project dir, not .organizer
			const baseDir = path.dirname(organizerDir);
			if (config) {
				const stateFilePath = config.stateFile
					? path.isAbsolute(config.stateFile)
						? config.stateFile
						: path.join(baseDir, config.stateFile)
					: path.join(organizerDir, "agent", "state.json");

				if (existsSync(stateFilePath)) {
					try {
						const stateContent = readFileSync(stateFilePath, "utf-8");
						const rawState = JSON.parse(stateContent) as Record<
							string,
							unknown
						>;
						state = parseAgentState(rawState);
					} catch (err) {
						error = `Failed to read state: ${err instanceof Error ? err.message : "Unknown error"}`;
					}
				}

				// Get cycle count and latest cycle
				const logsDir = config.logsDir
					? path.isAbsolute(config.logsDir)
						? config.logsDir
						: path.join(baseDir, config.logsDir)
					: path.join(organizerDir, "agent", "logs");

				cycleCount = countCycleLogs(logsDir);
				lastCycle = getLatestCycleLog(logsDir);
			}

			const agentInfo: AgentInfo = {
				id: "continuous-organizer",
				name: "Continuous Organizer Agent",
				type: "organizer",
				status: determineAgentStatus(state, config),
				config,
				state,
				lastCycle,
				cycleCount,
				error,
			};

			agents.push(agentInfo);
		}

		return { agents };
	} catch (err) {
		return {
			agents: [],
			error: err instanceof Error ? err.message : "Unknown error",
		};
	}
}

/**
 * Get a specific agent by ID
 *
 * @param organizerDir - Path to the .organizer directory
 * @param agentId - Agent ID
 * @returns Agent info or null
 */
export function getAgentById(
	organizerDir: string,
	agentId: string,
): { agent: AgentInfo | null; error?: string } {
	const result = getAgents(organizerDir);
	if (result.error) {
		return { agent: null, error: result.error };
	}

	const agent = result.agents.find((a) => a.id === agentId);
	if (!agent) {
		return { agent: null, error: `Agent not found: ${agentId}` };
	}

	return { agent };
}

// ============================================================================
// Agent control functions
// ============================================================================

/**
 * Command execution result
 */
export interface ExecResult {
	success: boolean;
	output: string;
	error?: string;
}

/**
 * Execute a shell command and return result
 * Exported for testing purposes
 */
export function execCommand(command: string): Promise<ExecResult> {
	return new Promise((resolve) => {
		exec(command, { timeout: 60000 }, (error, stdout, stderr) => {
			if (error) {
				resolve({
					success: false,
					output: stderr || stdout,
					error: error.message,
				});
			} else {
				resolve({
					success: true,
					output: stdout,
				});
			}
		});
	});
}

/**
 * Get the launchd service label for an agent
 */
function getLaunchdLabel(agentId: string): string {
	// Map agent IDs to launchd labels
	const labelMap: Record<string, string> = {
		"continuous-organizer": "com.prdtool.organizer.agent",
	};
	return labelMap[agentId] || `com.prdtool.${agentId}`;
}

/**
 * Trigger a single agent cycle (run-once)
 *
 * @param basePath - Base path where .organizer directory is located
 * @param agentId - Agent ID
 */
export async function runAgentOnce(
	basePath: string,
	agentId: string,
): Promise<AgentControlResult> {
	// Currently only continuous-organizer is supported
	if (agentId !== "continuous-organizer") {
		return {
			success: false,
			action: "run-once",
			agentId,
			message: `Agent not supported: ${agentId}`,
			error: `Unknown agent: ${agentId}`,
		};
	}

	// Run python3 -m organizer --agent-once with the base path
	const command = `cd "${basePath}" && python3 -m organizer --agent-once`;
	const result = await execCommand(command);

	return {
		success: result.success,
		action: "run-once",
		agentId,
		message: result.success
			? "Agent cycle triggered successfully"
			: "Failed to trigger agent cycle",
		error: result.error,
		output: result.output,
	};
}

/**
 * Start an agent via launchctl
 *
 * @param agentId - Agent ID
 */
export async function startAgent(agentId: string): Promise<AgentControlResult> {
	const label = getLaunchdLabel(agentId);
	const command = `launchctl start "${label}"`;
	const result = await execCommand(command);

	return {
		success: result.success,
		action: "start",
		agentId,
		message: result.success
			? `Agent ${agentId} started`
			: `Failed to start agent ${agentId}`,
		error: result.error,
		output: result.output,
	};
}

/**
 * Stop an agent via launchctl
 *
 * @param agentId - Agent ID
 */
export async function stopAgent(agentId: string): Promise<AgentControlResult> {
	const label = getLaunchdLabel(agentId);
	const command = `launchctl stop "${label}"`;
	const result = await execCommand(command);

	return {
		success: result.success,
		action: "stop",
		agentId,
		message: result.success
			? `Agent ${agentId} stopped`
			: `Failed to stop agent ${agentId}`,
		error: result.error,
		output: result.output,
	};
}

/**
 * Restart an agent via launchctl (stop + start)
 *
 * @param agentId - Agent ID
 */
export async function restartAgent(
	agentId: string,
): Promise<AgentControlResult> {
	// First stop
	const stopResult = await stopAgent(agentId);
	if (!stopResult.success) {
		// If stop fails, still try to start
		// launchctl stop may fail if service is not running
	}

	// Then start
	const startResult = await startAgent(agentId);

	return {
		success: startResult.success,
		action: "restart",
		agentId,
		message: startResult.success
			? `Agent ${agentId} restarted`
			: `Failed to restart agent ${agentId}`,
		error: startResult.error || stopResult.error,
		output: [stopResult.output, startResult.output].filter(Boolean).join("\n"),
	};
}

/**
 * Execute an agent control action
 *
 * @param basePath - Base path where .organizer directory is located
 * @param agentId - Agent ID
 * @param action - Action to perform
 */
export async function controlAgent(
	basePath: string,
	agentId: string,
	action: AgentAction,
): Promise<AgentControlResult> {
	switch (action) {
		case "run-once":
			return runAgentOnce(basePath, agentId);
		case "start":
			return startAgent(agentId);
		case "stop":
			return stopAgent(agentId);
		case "restart":
			return restartAgent(agentId);
		default:
			return {
				success: false,
				action: action,
				agentId,
				message: `Unknown action: ${action}`,
				error: `Invalid action: ${action}`,
			};
	}
}

// ============================================================================
// Audit types and functions
// ============================================================================

const KNOWN_LABELS = ["com.prdtool.organizer.agent"];

export interface DiscoveredService {
	label: string;
	status: "running" | "stopped" | "unknown";
	pid: number | null;
	known: boolean;
}

export interface RunningProcess {
	pid: number;
	user: string;
	cpu: string;
	mem: string;
	command: string;
}

export interface AuditResult {
	discoveredServices: DiscoveredService[];
	runningProcesses: RunningProcess[];
	unexpectedServices: DiscoveredService[];
	missingExpected: string[];
	healthy: boolean;
}

/**
 * Discover launchd services matching com.prdtool.* pattern.
 * Uses `launchctl print gui/<uid>` piped through grep.
 */
export async function discoverLaunchdServices(): Promise<DiscoveredService[]> {
	const uidResult = await execCommand("id -u");
	if (!uidResult.success) return [];
	const uid = uidResult.output.trim();

	const result = await execCommand(
		`launchctl print gui/${uid} 2>/dev/null | grep 'com.prdtool' || true`,
	);

	if (!result.output.trim()) return [];

	const serviceMap = new Map<string, DiscoveredService>();
	for (const line of result.output.trim().split("\n")) {
		const trimmed = line.trim();
		if (!trimmed) continue;

		const labelMatch = trimmed.match(/(com\.prdtool\.[a-z0-9_.]+)/);
		if (!labelMatch) continue;
		const label = labelMatch[1];

		const pidMatch = trimmed.match(/^\s*(\d+)/);
		const pid = pidMatch ? parseInt(pidMatch[1], 10) : null;

		const existing = serviceMap.get(label);
		if (existing) {
			if (pid !== null) existing.pid = pid;
			if (pid !== null) existing.status = "running";
		} else {
			serviceMap.set(label, {
				label,
				status: pid !== null ? "running" : "stopped",
				pid,
				known: KNOWN_LABELS.includes(label),
			});
		}
	}

	return Array.from(serviceMap.values());
}

/**
 * Discover running python3 organizer processes via `ps`.
 */
export async function discoverRunningProcesses(): Promise<RunningProcess[]> {
	const result = await execCommand(
		`ps aux | grep -i '[p]ython.*organizer' || true`,
	);

	if (!result.output.trim()) return [];

	const processes: RunningProcess[] = [];
	for (const line of result.output.trim().split("\n")) {
		const parts = line.trim().split(/\s+/);
		if (parts.length < 11) continue;

		processes.push({
			pid: parseInt(parts[1], 10),
			user: parts[0],
			cpu: parts[2],
			mem: parts[3],
			command: parts.slice(10).join(" "),
		});
	}

	return processes;
}

/**
 * Run a full system audit: discover launchd services and processes,
 * compare against known labels.
 */
export async function auditAgents(): Promise<AuditResult> {
	const [services, processes] = await Promise.all([
		discoverLaunchdServices(),
		discoverRunningProcesses(),
	]);

	const knownSet = new Set(KNOWN_LABELS);
	const unexpected = services.filter((s) => !knownSet.has(s.label));
	const foundLabels = new Set(services.map((s) => s.label));
	const missing = KNOWN_LABELS.filter((label) => !foundLabels.has(label));

	const healthy =
		unexpected.length === 0 &&
		missing.length === 0 &&
		services.some((s) => s.status === "running" || s.status === "stopped");

	return {
		discoveredServices: services,
		runningProcesses: processes,
		unexpectedServices: unexpected,
		missingExpected: missing,
		healthy,
	};
}
