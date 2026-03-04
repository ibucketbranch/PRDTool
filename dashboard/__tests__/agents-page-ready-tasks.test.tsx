import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

// Mock next/link
vi.mock("next/link", () => ({
	default: ({
		children,
		href,
	}: {
		children: React.ReactNode;
		href: string;
	}) => <a href={href}>{children}</a>,
}));

import AgentsPage from "@/app/agents/page";

// Helper to mock fetch with custom response
function mockFetch(
	handlers: Record<string, { ok: boolean; json?: () => Promise<unknown> }>,
) {
	global.fetch = vi.fn((url: string | URL | Request) => {
		const urlStr = url.toString();

		for (const [pattern, response] of Object.entries(handlers)) {
			if (urlStr.includes(pattern)) {
				return Promise.resolve({
					ok: response.ok,
					status: response.ok ? 200 : 500,
					json: response.json ?? (() => Promise.resolve({})),
				});
			}
		}

		// Default response
		return Promise.resolve({
			ok: true,
			status: 200,
			json: () => Promise.resolve({}),
		});
	}) as unknown as typeof fetch;
}

describe("AgentsPage - Ready Tasks Panel", () => {
	const mockAgents = {
		agents: [
			{
				id: "continuous-organizer",
				name: "Continuous Organizer Agent",
				type: "organizer",
				status: "idle",
				config: {
					basePath: "/test/path",
					intervalSeconds: 900,
					autoExecute: false,
					minAutoConfidence: 0.95,
				},
				state: {
					lastCycleId: "20260303_100000",
					lastFinishedAt: "2026-03-03T10:00:00.000Z",
					lastStatus: "completed",
				},
				lastCycle: null,
				cycleCount: 5,
			},
		],
	};

	const mockReadyTasks = {
		ready_tasks: [
			{
				task_id: "phase11.1",
				status: "ready",
				last_dry_run_at: "2026-03-03T10:00:00.000Z",
				last_errors: [],
				marked_ready_at: "2026-03-03T10:01:00.000Z",
				history: [],
			},
			{
				task_id: "phase11.2",
				status: "ready",
				last_dry_run_at: "2026-03-03T11:00:00.000Z",
				last_errors: [],
				marked_ready_at: "2026-03-03T11:01:00.000Z",
				history: [],
			},
		],
		total_count: 2,
		timestamp: "2026-03-03T12:00:00.000Z",
	};

	beforeEach(() => {
		vi.resetAllMocks();
		vi.useFakeTimers({ shouldAdvanceTime: true });
	});

	afterEach(() => {
		vi.restoreAllMocks();
		vi.useRealTimers();
	});

	// ============================================================================
	// Rendering tests
	// ============================================================================

	describe("Panel rendering", () => {
		it("renders the Ready Tasks panel header", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockReadyTasks),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Ready Tasks")).toBeInTheDocument();
			});

			expect(
				screen.getByText(
					"Tasks that passed dry-run validation and are ready to execute",
				),
			).toBeInTheDocument();
		});

		it("shows loading state while fetching ready tasks", async () => {
			// Create a promise that doesn't resolve immediately
			let resolveReadyTasks: (value: unknown) => void;
			const readyTasksPromise = new Promise((resolve) => {
				resolveReadyTasks = resolve;
			});

			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => readyTasksPromise as Promise<unknown>,
				},
			});

			render(<AgentsPage />);

			// Wait for agents to load first
			await waitFor(() => {
				expect(
					screen.getByText("Continuous Organizer Agent"),
				).toBeInTheDocument();
			});

			// Check for loading state in ready tasks panel
			expect(screen.getByText("Loading...")).toBeInTheDocument();

			// Resolve ready tasks
			resolveReadyTasks!(mockReadyTasks);

			await waitFor(() => {
				expect(screen.getByText("phase11.1")).toBeInTheDocument();
			});
		});

		it("displays ready tasks when data is loaded", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockReadyTasks),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("phase11.1")).toBeInTheDocument();
			});

			expect(screen.getByText("phase11.2")).toBeInTheDocument();
			// Both should show "ready" badge
			const readyBadges = screen.getAllByText("ready");
			expect(readyBadges.length).toBe(2);
		});

		it("displays empty state when no ready tasks", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () =>
						Promise.resolve({
							ready_tasks: [],
							total_count: 0,
							timestamp: "2026-03-03T12:00:00.000Z",
						}),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(
					screen.getByText(
						"No tasks are ready for execution. Run a dry-run validation to mark tasks as ready.",
					),
				).toBeInTheDocument();
			});

			expect(screen.getByText(/--dry-run --dry-run-task-id/)).toBeInTheDocument();
		});
	});

	// ============================================================================
	// Task display tests
	// ============================================================================

	describe("Task display", () => {
		it("displays task marked_ready_at timestamp", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockReadyTasks),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("phase11.1")).toBeInTheDocument();
			});

			// Check that "Ready since:" text appears
			expect(screen.getAllByText(/Ready since:/)[0]).toBeInTheDocument();
		});

		it("displays previous errors in expandable section", async () => {
			const tasksWithErrors = {
				ready_tasks: [
					{
						task_id: "phase11.1",
						status: "ready",
						last_dry_run_at: "2026-03-03T10:00:00.000Z",
						last_errors: ["Error 1: test failed", "Error 2: lint failed"],
						marked_ready_at: "2026-03-03T10:01:00.000Z",
						history: [],
					},
				],
				total_count: 1,
				timestamp: "2026-03-03T12:00:00.000Z",
			};

			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(tasksWithErrors),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("phase11.1")).toBeInTheDocument();
			});

			// Should show "2 previous error(s)"
			expect(screen.getByText("2 previous error(s)")).toBeInTheDocument();

			// Click to expand
			fireEvent.click(screen.getByText("2 previous error(s)"));

			// Should show the errors
			await waitFor(() => {
				expect(screen.getByText("Error 1: test failed")).toBeInTheDocument();
			});
		});
	});

	// ============================================================================
	// Execute button tests
	// ============================================================================

	describe("Execute button", () => {
		it("renders Execute button for each ready task", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockReadyTasks),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("phase11.1")).toBeInTheDocument();
			});

			const executeButtons = screen.getAllByText("Execute");
			expect(executeButtons.length).toBe(2);
		});

		it("disables Execute button when no agents available", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve({ agents: [] }) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockReadyTasks),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("phase11.1")).toBeInTheDocument();
			});

			const executeButtons = screen.getAllByText("Execute");
			executeButtons.forEach((button) => {
				expect(button).toBeDisabled();
			});
		});

		it("triggers execution when Execute button is clicked", async () => {
			let postCalled = false;
			let postBody: unknown = null;

			global.fetch = vi.fn((url: string | URL | Request, options?: RequestInit) => {
				const urlStr = url.toString();

				if (options?.method === "POST") {
					postCalled = true;
					postBody = JSON.parse(options.body as string);
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () =>
							Promise.resolve({
								success: true,
								action: "run-once",
								agentId: "continuous-organizer",
								message: "Cycle completed",
							}),
					});
				}

				if (urlStr.includes("/api/agents?")) {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockAgents),
					});
				}

				if (urlStr.includes("/api/agents/ready-tasks")) {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockReadyTasks),
					});
				}

				return Promise.resolve({
					ok: true,
					status: 200,
					json: () => Promise.resolve({}),
				});
			}) as unknown as typeof fetch;

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("phase11.1")).toBeInTheDocument();
			});

			// Click Execute on first task
			const executeButtons = screen.getAllByText("Execute");
			fireEvent.click(executeButtons[0]);

			await waitFor(() => {
				expect(postCalled).toBe(true);
			});

			expect(postBody).toEqual({
				basePath: expect.stringContaining("PRDTool"),
				agentId: "continuous-organizer",
				action: "run-once",
			});
		});

		it("shows executing state during execution", async () => {
			let resolvePost: (value: unknown) => void;
			const postPromise = new Promise((resolve) => {
				resolvePost = resolve;
			});

			global.fetch = vi.fn((url: string | URL | Request, options?: RequestInit) => {
				const urlStr = url.toString();

				if (options?.method === "POST") {
					return postPromise.then(() => ({
						ok: true,
						status: 200,
						json: () =>
							Promise.resolve({
								success: true,
								action: "run-once",
								agentId: "continuous-organizer",
								message: "Cycle completed",
							}),
					}));
				}

				if (urlStr.includes("/api/agents?")) {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockAgents),
					});
				}

				if (urlStr.includes("/api/agents/ready-tasks")) {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockReadyTasks),
					});
				}

				return Promise.resolve({
					ok: true,
					status: 200,
					json: () => Promise.resolve({}),
				});
			}) as unknown as typeof fetch;

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("phase11.1")).toBeInTheDocument();
			});

			// Click Execute
			const executeButtons = screen.getAllByText("Execute");
			fireEvent.click(executeButtons[0]);

			// Should show "Executing..." state
			await waitFor(() => {
				expect(screen.getByText("Executing...")).toBeInTheDocument();
			});

			// Resolve the POST
			resolvePost!({});

			// Should go back to "Execute"
			await waitFor(() => {
				expect(screen.queryByText("Executing...")).not.toBeInTheDocument();
			});
		});

		it("shows success message after execution", async () => {
			global.fetch = vi.fn((url: string | URL | Request, options?: RequestInit) => {
				const urlStr = url.toString();

				if (options?.method === "POST") {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () =>
							Promise.resolve({
								success: true,
								action: "run-once",
								agentId: "continuous-organizer",
								message: "Cycle completed",
							}),
					});
				}

				if (urlStr.includes("/api/agents?")) {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockAgents),
					});
				}

				if (urlStr.includes("/api/agents/ready-tasks")) {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockReadyTasks),
					});
				}

				return Promise.resolve({
					ok: true,
					status: 200,
					json: () => Promise.resolve({}),
				});
			}) as unknown as typeof fetch;

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("phase11.1")).toBeInTheDocument();
			});

			// Click Execute
			const executeButtons = screen.getAllByText("Execute");
			fireEvent.click(executeButtons[0]);

			// Should show success message
			await waitFor(() => {
				expect(screen.getByText("Execution Triggered")).toBeInTheDocument();
			});

			expect(
				screen.getByText(/Task phase11.1 execution triggered via agent/),
			).toBeInTheDocument();
		});

		it("shows error message when execution fails", async () => {
			global.fetch = vi.fn((url: string | URL | Request, options?: RequestInit) => {
				const urlStr = url.toString();

				if (options?.method === "POST") {
					return Promise.resolve({
						ok: false,
						status: 500,
						json: () =>
							Promise.resolve({
								success: false,
								action: "run-once",
								agentId: "continuous-organizer",
								message: "Agent failed",
								error: "Something went wrong",
							}),
					});
				}

				if (urlStr.includes("/api/agents?")) {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockAgents),
					});
				}

				if (urlStr.includes("/api/agents/ready-tasks")) {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockReadyTasks),
					});
				}

				return Promise.resolve({
					ok: true,
					status: 200,
					json: () => Promise.resolve({}),
				});
			}) as unknown as typeof fetch;

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("phase11.1")).toBeInTheDocument();
			});

			// Click Execute
			const executeButtons = screen.getAllByText("Execute");
			fireEvent.click(executeButtons[0]);

			// Should show error message
			await waitFor(() => {
				expect(screen.getByText("Execution Failed")).toBeInTheDocument();
			});

			expect(screen.getByText(/Error: Something went wrong/)).toBeInTheDocument();
		});
	});

	// ============================================================================
	// Refresh button tests
	// ============================================================================

	describe("Refresh button", () => {
		it("renders refresh button in panel header", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockReadyTasks),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Refresh")).toBeInTheDocument();
			});
		});

		it("reloads ready tasks when refresh is clicked", async () => {
			let readyTasksFetchCount = 0;

			global.fetch = vi.fn((url: string | URL | Request) => {
				const urlStr = url.toString();

				if (urlStr.includes("/api/agents/ready-tasks")) {
					readyTasksFetchCount++;
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockReadyTasks),
					});
				}

				if (urlStr.includes("/api/agents?")) {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockAgents),
					});
				}

				return Promise.resolve({
					ok: true,
					status: 200,
					json: () => Promise.resolve({}),
				});
			}) as unknown as typeof fetch;

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("phase11.1")).toBeInTheDocument();
			});

			// Initial fetch count
			expect(readyTasksFetchCount).toBe(1);

			// Click refresh
			fireEvent.click(screen.getByText("Refresh"));

			await waitFor(() => {
				expect(readyTasksFetchCount).toBe(2);
			});
		});
	});
});
