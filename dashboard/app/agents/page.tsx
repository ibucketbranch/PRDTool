"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";

interface AgentConfig {
	basePath: string;
	intervalSeconds: number;
	autoExecute: boolean;
	minAutoConfidence: number;
}

interface AgentState {
	lastCycleId: string;
	lastFinishedAt: string;
	lastStatus: string;
}

interface AgentCycleSummary {
	cycleId: string;
	finishedAt: string;
	plan: { totalGroups: number; groupsToConsolidate: number };
	queue: { proposalCount: number };
	execution: { movedFiles: number; failedFiles: number; status: string };
	emptyFolderPolicy: { kept: number; review: number; prune: number };
}

interface AgentInfo {
	id: string;
	name: string;
	type: string;
	status: "running" | "idle" | "stopped" | "error" | "unknown";
	config: AgentConfig | null;
	state: AgentState | null;
	lastCycle: AgentCycleSummary | null;
	cycleCount: number;
	error?: string;
}

interface ControlResult {
	success: boolean;
	action: string;
	agentId: string;
	message: string;
	error?: string;
	output?: string;
}

interface DiscoveredService {
	label: string;
	status: string;
	pid: number | null;
	known: boolean;
}

interface RunningProcess {
	pid: number;
	user: string;
	cpu: string;
	mem: string;
	command: string;
}

interface AuditResult {
	discoveredServices: DiscoveredService[];
	runningProcesses: RunningProcess[];
	unexpectedServices: DiscoveredService[];
	missingExpected: string[];
	healthy: boolean;
}

interface TaskHistoryEntry {
	timestamp: string;
	event: string;
	from_status: string;
	to_status: string;
	errors?: string[];
}

interface ReadyTask {
	task_id: string;
	status: "ready";
	last_dry_run_at: string | null;
	last_errors: string[];
	marked_ready_at: string | null;
	history: TaskHistoryEntry[];
}

interface ReadyTasksResponse {
	ready_tasks: ReadyTask[];
	total_count: number;
	timestamp: string;
	error?: string;
}

interface DriftRecord {
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

interface DriftGroup {
	rootBin: string;
	drifts: DriftRecord[];
	totalDrifts: number;
}

interface DriftReportResponse {
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

const BASE_PATH = process.env.NEXT_PUBLIC_ORGANIZER_BASE_PATH || "/Users/michaelvalderrama/Websites/PRDTool";

const STATUS_COLORS: Record<string, string> = {
	running: "bg-green-100 text-green-800",
	idle: "bg-blue-100 text-blue-800",
	stopped: "bg-neutral-100 text-neutral-600",
	error: "bg-red-100 text-red-800",
	unknown: "bg-yellow-100 text-yellow-800",
};

export default function AgentsPage() {
	const [agents, setAgents] = useState<AgentInfo[]>([]);
	const [loading, setLoading] = useState(true);
	const [actionInProgress, setActionInProgress] = useState<string | null>(null);
	const [actionResult, setActionResult] = useState<ControlResult | null>(null);
	const [audit, setAudit] = useState<AuditResult | null>(null);
	const [auditing, setAuditing] = useState(false);
	const [readyTasks, setReadyTasks] = useState<ReadyTask[]>([]);
	const [readyTasksLoading, setReadyTasksLoading] = useState(true);
	const [executingTask, setExecutingTask] = useState<string | null>(null);
	const [executeResult, setExecuteResult] = useState<{
		success: boolean;
		taskId: string;
		message: string;
		error?: string;
	} | null>(null);
	const [driftReport, setDriftReport] = useState<DriftReportResponse | null>(null);
	const [driftLoading, setDriftLoading] = useState(true);
	const [driftError, setDriftError] = useState<string | null>(null);

	const loadAgents = useCallback(async () => {
		try {
			const res = await fetch(`/api/agents?basePath=${encodeURIComponent(BASE_PATH)}`);
			const data = await res.json();
			if (data.agents) setAgents(data.agents);
		} catch (err) {
			console.error("Failed to load agents:", err);
		} finally {
			setLoading(false);
		}
	}, []);

	const loadReadyTasks = useCallback(async () => {
		try {
			const res = await fetch(
				`/api/agents/ready-tasks?basePath=${encodeURIComponent(BASE_PATH)}`
			);
			const data: ReadyTasksResponse = await res.json();
			if (data.ready_tasks) {
				setReadyTasks(data.ready_tasks);
			}
		} catch (err) {
			console.error("Failed to load ready tasks:", err);
		} finally {
			setReadyTasksLoading(false);
		}
	}, []);

	const loadDriftReport = useCallback(async () => {
		try {
			setDriftError(null);
			const res = await fetch(
				`/api/refile/drift-report?basePath=${encodeURIComponent(BASE_PATH)}`
			);
			const data: DriftReportResponse = await res.json();
			if (data.error) {
				setDriftError(data.error);
			}
			setDriftReport(data);
		} catch (err) {
			console.error("Failed to load drift report:", err);
			setDriftError(err instanceof Error ? err.message : "Failed to load drift report");
		} finally {
			setDriftLoading(false);
		}
	}, []);

	useEffect(() => {
		loadAgents();
		loadReadyTasks();
		loadDriftReport();
		const agentInterval = setInterval(loadAgents, 15_000);
		const taskInterval = setInterval(loadReadyTasks, 30_000);
		const driftInterval = setInterval(loadDriftReport, 30_000);
		return () => {
			clearInterval(agentInterval);
			clearInterval(taskInterval);
			clearInterval(driftInterval);
		};
	}, [loadAgents, loadReadyTasks, loadDriftReport]);

	const handleAction = async (agentId: string, action: string) => {
		setActionInProgress(`${agentId}:${action}`);
		setActionResult(null);
		try {
			const res = await fetch("/api/agents", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ basePath: BASE_PATH, agentId, action }),
			});
			const data: ControlResult = await res.json();
			setActionResult(data);
			if (data.success) setTimeout(loadAgents, 2000);
		} catch (err) {
			setActionResult({
				success: false,
				action,
				agentId,
				message: "Request failed",
				error: err instanceof Error ? err.message : String(err),
			});
		} finally {
			setActionInProgress(null);
		}
	};

	const handleAudit = async () => {
		setAuditing(true);
		try {
			const res = await fetch("/api/agents/audit");
			const data = await res.json();
			if (data.audit) setAudit(data.audit);
		} catch (err) {
			console.error("Audit failed:", err);
		} finally {
			setAuditing(false);
		}
	};

	const handleExecuteTask = async (taskId: string) => {
		setExecutingTask(taskId);
		setExecuteResult(null);
		try {
			// Get the first available agent to execute through
			const primaryAgent = agents.length > 0 ? agents[0] : null;
			if (!primaryAgent) {
				setExecuteResult({
					success: false,
					taskId,
					message: "No agent available to execute task",
					error: "No agents found",
				});
				return;
			}

			// Execute by triggering a run-once on the agent
			// The agent will process pending actions from the queue
			const res = await fetch("/api/agents", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					basePath: BASE_PATH,
					agentId: primaryAgent.id,
					action: "run-once",
				}),
			});
			const data: ControlResult = await res.json();

			if (data.success) {
				setExecuteResult({
					success: true,
					taskId,
					message: `Task ${taskId} execution triggered via agent ${primaryAgent.id}`,
				});
				// Reload ready tasks after execution
				setTimeout(() => {
					loadReadyTasks();
					loadAgents();
				}, 3000);
			} else {
				setExecuteResult({
					success: false,
					taskId,
					message: data.message,
					error: data.error,
				});
			}
		} catch (err) {
			setExecuteResult({
				success: false,
				taskId,
				message: "Failed to execute task",
				error: err instanceof Error ? err.message : String(err),
			});
		} finally {
			setExecutingTask(null);
		}
	};

	if (loading) {
		return (
			<main className="container mx-auto px-4 py-8">
				<h1 className="text-3xl font-bold mb-6">Agents</h1>
				<p className="text-neutral-600">Loading agents...</p>
			</main>
		);
	}

	return (
		<main className="container mx-auto px-4 py-8">
			<div className="mb-6">
				<Link
					href="/"
					className="text-sm text-blue-600 hover:text-blue-800 hover:underline mb-2 inline-block"
				>
					&larr; Back to Dashboard
				</Link>
				<h1 className="text-3xl font-bold">Agents</h1>
			</div>
			<p className="text-neutral-600 mb-8">
				View agent status, trigger manual cycles, and audit running services.
			</p>

			{/* Agent Cards */}
			{agents.length === 0 ? (
				<div className="bg-neutral-50 rounded-lg border border-neutral-200 p-6 mb-6">
					<p className="text-neutral-500">
						No agents found. Make sure the <code>.organizer/agent_config.json</code> file exists.
					</p>
				</div>
			) : (
				agents.map((agent) => (
					<div
						key={agent.id}
						className="bg-white rounded-lg border border-neutral-200 p-6 mb-6"
					>
						<div className="flex items-center justify-between mb-4">
							<div>
								<h2 className="text-xl font-semibold">{agent.name}</h2>
								<p className="text-sm text-neutral-500">ID: {agent.id}</p>
							</div>
							<span
								className={`px-3 py-1 rounded-full text-sm font-medium ${STATUS_COLORS[agent.status] || STATUS_COLORS.unknown}`}
							>
								{agent.status}
							</span>
						</div>

						{/* Stats row */}
						<div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
							<div className="bg-neutral-50 rounded p-3">
								<div className="text-xs text-neutral-500">Total Cycles</div>
								<div className="text-lg font-bold">{agent.cycleCount}</div>
							</div>
							<div className="bg-neutral-50 rounded p-3">
								<div className="text-xs text-neutral-500">Last Status</div>
								<div className="text-lg font-bold">
									{agent.state?.lastStatus || "—"}
								</div>
							</div>
							<div className="bg-neutral-50 rounded p-3">
								<div className="text-xs text-neutral-500">Last Cycle</div>
								<div className="text-sm font-medium">
									{agent.state?.lastFinishedAt
										? new Date(agent.state.lastFinishedAt).toLocaleString()
										: "—"}
								</div>
							</div>
							<div className="bg-neutral-50 rounded p-3">
								<div className="text-xs text-neutral-500">Interval</div>
								<div className="text-lg font-bold">
									{agent.config
										? `${Math.round(agent.config.intervalSeconds / 60)}m`
										: "—"}
								</div>
							</div>
						</div>

						{/* Last cycle summary */}
						{agent.lastCycle && (
							<div className="bg-neutral-50 rounded p-4 mb-4">
								<h3 className="text-sm font-semibold mb-2">
									Last Cycle Summary
								</h3>
								<div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
									<div>
										<span className="text-neutral-500">Groups:</span>{" "}
										{agent.lastCycle.plan.totalGroups}
									</div>
									<div>
										<span className="text-neutral-500">To consolidate:</span>{" "}
										{agent.lastCycle.plan.groupsToConsolidate}
									</div>
									<div>
										<span className="text-neutral-500">Proposals:</span>{" "}
										{agent.lastCycle.queue.proposalCount}
									</div>
									<div>
										<span className="text-neutral-500">Moved:</span>{" "}
										{agent.lastCycle.execution.movedFiles}
									</div>
									<div>
										<span className="text-neutral-500">Failed:</span>{" "}
										{agent.lastCycle.execution.failedFiles}
									</div>
								</div>
								<div className="grid grid-cols-3 gap-3 text-sm mt-2">
									<div>
										<span className="text-neutral-500">Empty kept:</span>{" "}
										{agent.lastCycle.emptyFolderPolicy.kept}
									</div>
									<div>
										<span className="text-neutral-500">Review:</span>{" "}
										{agent.lastCycle.emptyFolderPolicy.review}
									</div>
									<div>
										<span className="text-neutral-500">Prune:</span>{" "}
										{agent.lastCycle.emptyFolderPolicy.prune}
									</div>
								</div>
							</div>
						)}

						{/* Error display */}
						{agent.error && (
							<div className="bg-red-50 border border-red-200 rounded p-3 mb-4 text-sm text-red-700">
								{agent.error}
							</div>
						)}

						{/* Controls */}
						<div className="flex gap-3 flex-wrap">
							<button
								onClick={() => handleAction(agent.id, "run-once")}
								disabled={actionInProgress !== null}
								className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
									actionInProgress !== null
										? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
										: "bg-blue-600 text-white hover:bg-blue-700"
								}`}
							>
								{actionInProgress === `${agent.id}:run-once`
									? "Running..."
									: "Run Now"}
							</button>
							<button
								onClick={() => handleAction(agent.id, "start")}
								disabled={actionInProgress !== null}
								className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
									actionInProgress !== null
										? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
										: "bg-green-600 text-white hover:bg-green-700"
								}`}
							>
								{actionInProgress === `${agent.id}:start`
									? "Starting..."
									: "Start"}
							</button>
							<button
								onClick={() => handleAction(agent.id, "stop")}
								disabled={actionInProgress !== null}
								className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
									actionInProgress !== null
										? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
										: "bg-red-600 text-white hover:bg-red-700"
								}`}
							>
								{actionInProgress === `${agent.id}:stop`
									? "Stopping..."
									: "Stop"}
							</button>
							<button
								onClick={() => handleAction(agent.id, "restart")}
								disabled={actionInProgress !== null}
								className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
									actionInProgress !== null
										? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
										: "bg-orange-600 text-white hover:bg-orange-700"
								}`}
							>
								{actionInProgress === `${agent.id}:restart`
									? "Restarting..."
									: "Restart"}
							</button>
						</div>
					</div>
				))
			)}

			{/* Ready Tasks Panel */}
			<div className="bg-white rounded-lg border border-neutral-200 p-6 mb-6">
				<div className="flex items-center justify-between mb-4">
					<div>
						<h2 className="text-xl font-semibold">Ready Tasks</h2>
						<p className="text-sm text-neutral-500">
							Tasks that passed dry-run validation and are ready to execute
						</p>
					</div>
					<button
						onClick={loadReadyTasks}
						disabled={readyTasksLoading}
						className="px-3 py-1.5 rounded text-sm font-medium text-neutral-600 hover:bg-neutral-100 transition-colors"
					>
						{readyTasksLoading ? "Loading..." : "Refresh"}
					</button>
				</div>

				{readyTasksLoading ? (
					<p className="text-neutral-500 text-sm">Loading ready tasks...</p>
				) : readyTasks.length === 0 ? (
					<div className="bg-neutral-50 rounded-lg border border-neutral-200 p-6 text-center">
						<p className="text-neutral-500">
							No tasks are ready for execution. Run a dry-run validation to
							mark tasks as ready.
						</p>
						<p className="text-xs text-neutral-400 mt-2">
							Use <code>--dry-run --dry-run-task-id &lt;task_id&gt;</code> with
							the agent to validate tasks.
						</p>
					</div>
				) : (
					<div className="space-y-3">
						{readyTasks.map((task) => (
							<div
								key={task.task_id}
								className="flex items-center justify-between bg-neutral-50 rounded-lg p-4"
							>
								<div className="flex-1">
									<div className="flex items-center gap-2">
										<span className="font-medium font-mono text-sm">
											{task.task_id}
										</span>
										<span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">
											ready
										</span>
									</div>
									<div className="text-xs text-neutral-500 mt-1">
										{task.marked_ready_at && (
											<span>
												Ready since:{" "}
												{new Date(task.marked_ready_at).toLocaleString()}
											</span>
										)}
										{task.last_dry_run_at && !task.marked_ready_at && (
											<span>
												Last dry-run:{" "}
												{new Date(task.last_dry_run_at).toLocaleString()}
											</span>
										)}
									</div>
									{task.last_errors.length > 0 && (
										<details className="mt-2">
											<summary className="text-xs text-yellow-600 cursor-pointer">
												{task.last_errors.length} previous error(s)
											</summary>
											<ul className="text-xs text-neutral-600 mt-1 space-y-1 pl-3">
												{task.last_errors.slice(0, 5).map((err, idx) => (
													<li key={idx} className="truncate max-w-md">
														{err}
													</li>
												))}
											</ul>
										</details>
									)}
								</div>
								<button
									onClick={() => handleExecuteTask(task.task_id)}
									disabled={executingTask !== null || agents.length === 0}
									className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
										executingTask !== null || agents.length === 0
											? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
											: "bg-green-600 text-white hover:bg-green-700"
									}`}
								>
									{executingTask === task.task_id ? "Executing..." : "Execute"}
								</button>
							</div>
						))}
					</div>
				)}

				{/* Execution Result */}
				{executeResult && (
					<div
						className={`mt-4 rounded-lg border p-4 ${
							executeResult.success
								? "bg-green-50 border-green-200"
								: "bg-red-50 border-red-200"
						}`}
					>
						<p className="text-sm font-medium">
							{executeResult.success
								? "Execution Triggered"
								: "Execution Failed"}
						</p>
						<p className="text-sm mt-1">{executeResult.message}</p>
						{executeResult.error && (
							<p className="text-sm text-red-600 mt-1">
								Error: {executeResult.error}
							</p>
						)}
					</div>
				)}
			</div>

			{/* Drift Report Panel */}
			<div className="bg-white rounded-lg border border-neutral-200 p-6 mb-6">
				<div className="flex items-center justify-between mb-4">
					<div>
						<h2 className="text-xl font-semibold">Drift Report</h2>
						<p className="text-sm text-neutral-500">
							Files that have moved away from their filed locations
						</p>
					</div>
					<button
						onClick={loadDriftReport}
						disabled={driftLoading}
						className="px-3 py-1.5 rounded text-sm font-medium text-neutral-600 hover:bg-neutral-100 transition-colors"
					>
						{driftLoading ? "Loading..." : "Refresh"}
					</button>
				</div>

				{driftLoading ? (
					<p className="text-neutral-500 text-sm">Loading drift report...</p>
				) : driftError ? (
					<div className="bg-red-50 border border-red-200 rounded p-4 text-sm text-red-700">
						{driftError}
					</div>
				) : !driftReport || !driftReport.groups || driftReport.totalDrifts === 0 ? (
					<div className="bg-neutral-50 rounded-lg border border-neutral-200 p-6 text-center">
						<p className="text-neutral-500">
							No drifted files detected. All filed documents are in their expected locations.
						</p>
					</div>
				) : (
					<>
						{/* Summary stats */}
						<div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
							<div className="bg-neutral-50 rounded p-3">
								<div className="text-xs text-neutral-500">Total Drifts</div>
								<div className="text-lg font-bold">{driftReport.totalDrifts}</div>
							</div>
							<div className="bg-red-50 rounded p-3">
								<div className="text-xs text-red-600">Likely Accidental</div>
								<div className="text-lg font-bold text-red-700">
									{driftReport.accidentalCount}
								</div>
							</div>
							<div className="bg-yellow-50 rounded p-3">
								<div className="text-xs text-yellow-600">Likely Intentional</div>
								<div className="text-lg font-bold text-yellow-700">
									{driftReport.intentionalCount}
								</div>
							</div>
							<div className="bg-blue-50 rounded p-3">
								<div className="text-xs text-blue-600">Source</div>
								<div className="text-sm font-medium text-blue-700">
									{driftReport.source === "queue" ? "Pending Queue" : "Saved Report"}
								</div>
							</div>
						</div>

						{/* Model info */}
						{(driftReport.modelUsed || driftReport.usedKeywordFallback) && (
							<div className="text-xs text-neutral-500 mb-4">
								{driftReport.modelUsed && (
									<span>Model: {driftReport.modelUsed}</span>
								)}
								{driftReport.usedKeywordFallback && (
									<span className="ml-2 px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded">
										keyword fallback
									</span>
								)}
							</div>
						)}

						{/* Grouped drifts by root bin */}
						<div className="space-y-3">
							{driftReport.groups.map((group) => (
								<details
									key={group.rootBin}
									className="bg-neutral-50 rounded-lg border border-neutral-200"
								>
									<summary className="p-4 cursor-pointer hover:bg-neutral-100 rounded-lg">
										<div className="inline-flex items-center gap-2">
											<span className="font-medium">{group.rootBin}</span>
											<span className="px-2 py-0.5 bg-neutral-200 text-neutral-700 rounded text-xs">
												{group.totalDrifts} drift{group.totalDrifts !== 1 ? "s" : ""}
											</span>
										</div>
									</summary>
									<div className="p-4 pt-0 space-y-2">
										{group.drifts.map((drift, idx) => (
											<div
												key={`${drift.filePath}-${idx}`}
												className="bg-white rounded border border-neutral-200 p-3"
											>
												<div className="flex items-center justify-between mb-2">
													<span className="font-medium text-sm truncate max-w-md">
														{drift.fileName}
													</span>
													<div className="flex items-center gap-2">
														{drift.driftAssessment === "likely_accidental" && (
															<span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs font-medium">
																Accidental
															</span>
														)}
														{drift.driftAssessment === "likely_intentional" && (
															<span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs font-medium">
																Intentional
															</span>
														)}
														<span
															className={`px-2 py-0.5 rounded text-xs font-medium ${
																drift.priority === "high"
																	? "bg-red-100 text-red-800"
																	: drift.priority === "low"
																		? "bg-green-100 text-green-800"
																		: "bg-neutral-100 text-neutral-700"
															}`}
														>
															{drift.priority} priority
														</span>
													</div>
												</div>
												<div className="text-xs text-neutral-600 space-y-1">
													<div>
														<span className="text-neutral-500">Original:</span>{" "}
														<span className="font-mono truncate block max-w-full overflow-hidden">
															{drift.originalFiledPath}
														</span>
													</div>
													<div>
														<span className="text-neutral-500">Current:</span>{" "}
														<span className="font-mono truncate block max-w-full overflow-hidden">
															{drift.currentPath}
														</span>
													</div>
													{drift.suggestedDestination && (
														<div>
															<span className="text-neutral-500">Suggested:</span>{" "}
															<span className="font-mono truncate block max-w-full overflow-hidden text-blue-600">
																{drift.suggestedDestination}
															</span>
														</div>
													)}
												</div>
												{drift.reason && (
													<div className="mt-2 text-xs text-neutral-600 bg-neutral-50 rounded p-2">
														<span className="text-neutral-500 font-medium">
															LLM Reasoning:
														</span>{" "}
														{drift.reason}
													</div>
												)}
												<div className="mt-2 flex items-center gap-3 text-xs text-neutral-500">
													{drift.confidence > 0 && (
														<span>Confidence: {(drift.confidence * 100).toFixed(0)}%</span>
													)}
													{drift.modelUsed && <span>Model: {drift.modelUsed}</span>}
													{drift.detectedAt && (
														<span>
															Detected: {new Date(drift.detectedAt).toLocaleString()}
														</span>
													)}
												</div>
											</div>
										))}
									</div>
								</details>
							))}
						</div>
					</>
				)}
			</div>

			{/* Action Result */}
			{actionResult && (
				<div
					className={`rounded-lg border p-6 mb-6 ${
						actionResult.success
							? "bg-green-50 border-green-200"
							: "bg-red-50 border-red-200"
					}`}
				>
					<h3 className="font-semibold mb-2">
						{actionResult.success ? "Action Succeeded" : "Action Failed"}
					</h3>
					<p className="text-sm mb-2">{actionResult.message}</p>
					{actionResult.error && (
						<p className="text-sm text-red-600">
							<strong>Error:</strong> {actionResult.error}
						</p>
					)}
					{actionResult.output && (
						<details className="mt-3">
							<summary className="text-sm font-medium cursor-pointer">
								View Output
							</summary>
							<pre className="mt-2 text-xs bg-white p-3 rounded border overflow-auto max-h-40">
								{actionResult.output}
							</pre>
						</details>
					)}
				</div>
			)}

			{/* Audit Section */}
			<div className="bg-white rounded-lg border border-neutral-200 p-6">
				<div className="flex items-center justify-between mb-4">
					<h2 className="text-xl font-semibold">Agent Audit</h2>
					<button
						onClick={handleAudit}
						disabled={auditing}
						className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
							auditing
								? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
								: "bg-neutral-800 text-white hover:bg-neutral-900"
						}`}
					>
						{auditing ? "Auditing..." : "Audit Running Agents"}
					</button>
				</div>
				<p className="text-sm text-neutral-500 mb-4">
					Discover all <code>com.prdtool.*</code> launchd services and running
					organizer processes. Highlights mismatches between registered and
					actually running services.
				</p>

				{audit && (
					<div className="space-y-4">
						{/* Health badge */}
						<div
							className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${
								audit.healthy
									? "bg-green-100 text-green-800"
									: "bg-yellow-100 text-yellow-800"
							}`}
						>
							<span
								className={`w-2 h-2 rounded-full ${
									audit.healthy ? "bg-green-500" : "bg-yellow-500"
								}`}
							/>
							{audit.healthy ? "Healthy" : "Attention Needed"}
						</div>

						{/* Discovered services */}
						<div>
							<h3 className="text-sm font-semibold mb-2">
								Discovered Services ({audit.discoveredServices.length})
							</h3>
							{audit.discoveredServices.length === 0 ? (
								<p className="text-sm text-neutral-500">
									No com.prdtool.* services found in launchd.
								</p>
							) : (
								<div className="space-y-2">
									{audit.discoveredServices.map((svc) => (
										<div
											key={svc.label}
											className="flex items-center justify-between bg-neutral-50 rounded p-3 text-sm"
										>
											<div>
												<span className="font-mono">{svc.label}</span>
												{!svc.known && (
													<span className="ml-2 px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs">
														unexpected
													</span>
												)}
											</div>
											<div className="flex items-center gap-3">
												{svc.pid !== null && (
													<span className="text-neutral-500">
														PID {svc.pid}
													</span>
												)}
												<span
													className={`px-2 py-0.5 rounded text-xs font-medium ${
														svc.status === "running"
															? "bg-green-100 text-green-700"
															: "bg-neutral-200 text-neutral-600"
													}`}
												>
													{svc.status}
												</span>
											</div>
										</div>
									))}
								</div>
							)}
						</div>

						{/* Running processes */}
						<div>
							<h3 className="text-sm font-semibold mb-2">
								Running Processes ({audit.runningProcesses.length})
							</h3>
							{audit.runningProcesses.length === 0 ? (
								<p className="text-sm text-neutral-500">
									No organizer processes currently running.
								</p>
							) : (
								<div className="space-y-2">
									{audit.runningProcesses.map((proc) => (
										<div
											key={proc.pid}
											className="bg-neutral-50 rounded p-3 text-sm"
										>
											<div className="flex items-center gap-4 mb-1">
												<span className="font-medium">PID {proc.pid}</span>
												<span className="text-neutral-500">
													CPU: {proc.cpu}% | Mem: {proc.mem}%
												</span>
											</div>
											<div className="font-mono text-xs text-neutral-600 truncate">
												{proc.command}
											</div>
										</div>
									))}
								</div>
							)}
						</div>

						{/* Warnings */}
						{(audit.unexpectedServices.length > 0 ||
							audit.missingExpected.length > 0) && (
							<div className="bg-yellow-50 border border-yellow-200 rounded p-4">
								<h3 className="text-sm font-semibold text-yellow-800 mb-2">
									Warnings
								</h3>
								{audit.unexpectedServices.length > 0 && (
									<p className="text-sm text-yellow-700 mb-1">
										<strong>Unexpected services:</strong>{" "}
										{audit.unexpectedServices.map((s) => s.label).join(", ")}
									</p>
								)}
								{audit.missingExpected.length > 0 && (
									<p className="text-sm text-yellow-700">
										<strong>Missing expected:</strong>{" "}
										{audit.missingExpected.join(", ")}
									</p>
								)}
							</div>
						)}
					</div>
				)}
			</div>
		</main>
	);
}
