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

describe("AgentsPage - Drift Report Panel", () => {
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

	const mockEmptyReadyTasks = {
		ready_tasks: [],
		total_count: 0,
		timestamp: "2026-03-03T12:00:00.000Z",
	};

	const mockDriftReport = {
		groups: [
			{
				rootBin: "Finances Bin",
				drifts: [
					{
						filePath: "/test/Finances Bin/2024_tax_return.pdf",
						fileName: "2024_tax_return.pdf",
						originalFiledPath: "/test/Finances Bin/Taxes/2024_tax_return.pdf",
						currentPath: "/test/Desktop/2024_tax_return.pdf",
						filedBy: "agent",
						filedAt: "2026-03-01T10:00:00.000Z",
						detectedAt: "2026-03-03T10:00:00.000Z",
						sha256Hash: "abc123",
						driftAssessment: "likely_accidental" as const,
						reason: "File moved to Desktop, likely accidental drag-and-drop",
						modelUsed: "llama3.1:8b-instruct-q8_0",
						confidence: 0.92,
						suggestedDestination: "/test/Finances Bin/Taxes/2024_tax_return.pdf",
						priority: "high" as const,
					},
				],
				totalDrifts: 1,
			},
			{
				rootBin: "Work Bin",
				drifts: [
					{
						filePath: "/test/Work Bin/project_report.pdf",
						fileName: "project_report.pdf",
						originalFiledPath: "/test/Work Bin/Projects/project_report.pdf",
						currentPath: "/test/Work Bin/Archive/project_report.pdf",
						filedBy: "agent",
						filedAt: "2026-03-02T10:00:00.000Z",
						detectedAt: "2026-03-03T11:00:00.000Z",
						sha256Hash: "def456",
						driftAssessment: "likely_intentional" as const,
						reason: "File moved to Archive subfolder, appears intentional",
						modelUsed: "llama3.1:8b-instruct-q8_0",
						confidence: 0.85,
						suggestedDestination: "",
						priority: "low" as const,
					},
				],
				totalDrifts: 1,
			},
		],
		totalDrifts: 2,
		accidentalCount: 1,
		intentionalCount: 1,
		filesChecked: 100,
		filesStillInPlace: 98,
		filesMissing: 0,
		modelUsed: "llama3.1:8b-instruct-q8_0",
		usedKeywordFallback: false,
		source: "queue" as const,
	};

	const mockEmptyDriftReport = {
		groups: [],
		totalDrifts: 0,
		accidentalCount: 0,
		intentionalCount: 0,
		filesChecked: 50,
		filesStillInPlace: 50,
		filesMissing: 0,
		modelUsed: "",
		usedKeywordFallback: false,
		source: "queue" as const,
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
		it("renders the Drift Report panel header", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => Promise.resolve(mockDriftReport),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Drift Report")).toBeInTheDocument();
			});

			expect(
				screen.getByText(
					"Files that have moved away from their filed locations",
				),
			).toBeInTheDocument();
		});

		it("shows loading state while fetching drift report", async () => {
			// Create a promise that doesn't resolve immediately
			let resolveDriftReport: (value: unknown) => void;
			const driftReportPromise = new Promise((resolve) => {
				resolveDriftReport = resolve;
			});

			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => driftReportPromise as Promise<unknown>,
				},
			});

			render(<AgentsPage />);

			// Wait for agents to load first
			await waitFor(() => {
				expect(
					screen.getByText("Continuous Organizer Agent"),
				).toBeInTheDocument();
			});

			// Check for loading state in drift report panel
			expect(screen.getByText("Loading drift report...")).toBeInTheDocument();

			// Resolve drift report
			resolveDriftReport!(mockDriftReport);

			await waitFor(() => {
				expect(screen.getByText("Finances Bin")).toBeInTheDocument();
			});
		});

		it("displays empty state when no drifted files", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => Promise.resolve(mockEmptyDriftReport),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(
					screen.getByText(
						"No drifted files detected. All filed documents are in their expected locations.",
					),
				).toBeInTheDocument();
			});
		});

		it("displays error state when API returns error", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () =>
						Promise.resolve({
							...mockEmptyDriftReport,
							error: "Queue directory does not exist",
						}),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(
					screen.getByText("Queue directory does not exist"),
				).toBeInTheDocument();
			});
		});
	});

	// ============================================================================
	// Drift data display tests
	// ============================================================================

	describe("Drift data display", () => {
		it("displays summary statistics", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => Promise.resolve(mockDriftReport),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Total Drifts")).toBeInTheDocument();
			});

			// Check stats
			expect(screen.getByText("2")).toBeInTheDocument(); // total drifts
			expect(screen.getByText("Likely Accidental")).toBeInTheDocument();
			expect(screen.getByText("Likely Intentional")).toBeInTheDocument();
			expect(screen.getByText("Pending Queue")).toBeInTheDocument(); // source
		});

		it("displays model information", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => Promise.resolve(mockDriftReport),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				// There will be multiple elements with model info (summary + each drift)
				const modelElements = screen.getAllByText(/Model: llama3.1:8b-instruct-q8_0/);
				expect(modelElements.length).toBeGreaterThanOrEqual(1);
			});
		});

		it("displays keyword fallback badge when used", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () =>
						Promise.resolve({
							...mockDriftReport,
							usedKeywordFallback: true,
						}),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("keyword fallback")).toBeInTheDocument();
			});
		});

		it("displays drift groups sorted by count", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => Promise.resolve(mockDriftReport),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Finances Bin")).toBeInTheDocument();
			});

			expect(screen.getByText("Work Bin")).toBeInTheDocument();
			// Check for drift count badges
			expect(screen.getAllByText("1 drift").length).toBe(2);
		});
	});

	// ============================================================================
	// Drift details tests
	// ============================================================================

	describe("Drift details", () => {
		it("displays drift details when group is expanded", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => Promise.resolve(mockDriftReport),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Finances Bin")).toBeInTheDocument();
			});

			// Click to expand Finances Bin group
			fireEvent.click(screen.getByText("Finances Bin"));

			await waitFor(() => {
				expect(screen.getByText("2024_tax_return.pdf")).toBeInTheDocument();
			});

			// Check assessment badge
			expect(screen.getByText("Accidental")).toBeInTheDocument();
			// Check priority badge
			expect(screen.getByText("high priority")).toBeInTheDocument();
		});

		it("displays original and current paths", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => Promise.resolve(mockDriftReport),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Finances Bin")).toBeInTheDocument();
			});

			// Click to expand Finances Bin
			const financesBinSummary = screen.getByText("Finances Bin").closest("summary");
			if (financesBinSummary) {
				fireEvent.click(financesBinSummary);
			}

			// Multiple groups may be expanded, so use getAllByText
			await waitFor(() => {
				const originalLabels = screen.getAllByText("Original:");
				expect(originalLabels.length).toBeGreaterThanOrEqual(1);
			});

			const currentLabels = screen.getAllByText("Current:");
			expect(currentLabels.length).toBeGreaterThanOrEqual(1);
			// The original path appears in both "Original" and "Suggested" for accidental drifts
			const originalPathElements = screen.getAllByText("/test/Finances Bin/Taxes/2024_tax_return.pdf");
			expect(originalPathElements.length).toBeGreaterThanOrEqual(1);
			expect(
				screen.getByText("/test/Desktop/2024_tax_return.pdf"),
			).toBeInTheDocument();
		});

		it("displays suggested destination when available", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => Promise.resolve(mockDriftReport),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Finances Bin")).toBeInTheDocument();
			});

			// Click to expand
			fireEvent.click(screen.getByText("Finances Bin"));

			await waitFor(() => {
				expect(screen.getByText("Suggested:")).toBeInTheDocument();
			});
		});

		it("displays LLM reasoning", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => Promise.resolve(mockDriftReport),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Finances Bin")).toBeInTheDocument();
			});

			// Click to expand - use the summary element inside details
			const financesBinSummary = screen.getByText("Finances Bin").closest("summary");
			if (financesBinSummary) {
				fireEvent.click(financesBinSummary);
			}

			// The details element should now be open and show the reasoning
			await waitFor(() => {
				expect(
					screen.getByText("File moved to Desktop, likely accidental drag-and-drop"),
				).toBeInTheDocument();
			});
		});

		it("displays intentional drift with yellow badge", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => Promise.resolve(mockDriftReport),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Work Bin")).toBeInTheDocument();
			});

			// Click to expand Work Bin group
			fireEvent.click(screen.getByText("Work Bin"));

			await waitFor(() => {
				expect(screen.getByText("project_report.pdf")).toBeInTheDocument();
			});

			// Check intentional badge
			expect(screen.getByText("Intentional")).toBeInTheDocument();
			// Check low priority badge
			expect(screen.getByText("low priority")).toBeInTheDocument();
		});

		it("displays confidence and model info for each drift", async () => {
			mockFetch({
				"/api/agents?": { ok: true, json: () => Promise.resolve(mockAgents) },
				"/api/agents/ready-tasks": {
					ok: true,
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => Promise.resolve(mockDriftReport),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Finances Bin")).toBeInTheDocument();
			});

			// Click to expand
			fireEvent.click(screen.getByText("Finances Bin"));

			await waitFor(() => {
				expect(screen.getByText("Confidence: 92%")).toBeInTheDocument();
			});
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
					json: () => Promise.resolve(mockEmptyReadyTasks),
				},
				"/api/refile/drift-report": {
					ok: true,
					json: () => Promise.resolve(mockDriftReport),
				},
			});

			render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Drift Report")).toBeInTheDocument();
			});

			// There should be multiple refresh buttons (one for each panel)
			const refreshButtons = screen.getAllByText("Refresh");
			expect(refreshButtons.length).toBeGreaterThanOrEqual(1);
		});

		it("reloads drift report when refresh is clicked", async () => {
			let driftReportFetchCount = 0;

			global.fetch = vi.fn((url: string | URL | Request) => {
				const urlStr = url.toString();

				if (urlStr.includes("/api/refile/drift-report")) {
					driftReportFetchCount++;
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockDriftReport),
					});
				}

				if (urlStr.includes("/api/agents/ready-tasks")) {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockEmptyReadyTasks),
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
				expect(screen.getByText("Finances Bin")).toBeInTheDocument();
			});

			// Initial fetch count
			expect(driftReportFetchCount).toBe(1);

			// Find the Drift Report panel's refresh button
			// It's in the panel that contains "Drift Report" header
			const driftReportPanel = screen.getByText("Drift Report").closest("div");
			const refreshButton = driftReportPanel?.parentElement?.querySelector(
				"button",
			);

			if (refreshButton) {
				fireEvent.click(refreshButton);

				await waitFor(() => {
					expect(driftReportFetchCount).toBe(2);
				});
			}
		});
	});

	// ============================================================================
	// Auto-refresh tests
	// ============================================================================

	describe("Auto-refresh", () => {
		it("auto-refreshes drift report every 30 seconds", async () => {
			let driftReportFetchCount = 0;

			global.fetch = vi.fn((url: string | URL | Request) => {
				const urlStr = url.toString();

				if (urlStr.includes("/api/refile/drift-report")) {
					driftReportFetchCount++;
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockDriftReport),
					});
				}

				if (urlStr.includes("/api/agents/ready-tasks")) {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: () => Promise.resolve(mockEmptyReadyTasks),
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

			const { unmount } = render(<AgentsPage />);

			await waitFor(() => {
				expect(screen.getByText("Finances Bin")).toBeInTheDocument();
			});

			// Initial fetch
			expect(driftReportFetchCount).toBe(1);

			// Advance time by 30 seconds - wrap in act for state updates
			await vi.advanceTimersByTimeAsync(30_000);

			await waitFor(() => {
				expect(driftReportFetchCount).toBe(2);
			});

			// Cleanup to prevent act warnings
			unmount();
		});
	});
});
