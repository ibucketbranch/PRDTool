import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// Mock fetch function globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Import after mocking
import LearnedRulesPage from "@/app/learned-rules/page";

// Mock data
const mockLearnedRulesResponse = {
	status: {
		active: true,
		rule_count: 3,
		enabled_rule_count: 2,
		last_scan_date: "2026-03-05T10:00:00Z",
		rules_path: "/test/.organizer/agent/learned_routing_rules.json",
		structure_path: "/test/.organizer/agent/learned_structure.json",
	},
	structure: {
		version: "1.0",
		root_path: "/test",
		max_depth: 4,
		total_folders: 5,
		total_files: 25,
		total_size_bytes: 1024000,
		folders: [
			{
				path: "/test/Documents",
				name: "Documents",
				depth: 1,
				file_count: 10,
				subfolder_count: 2,
				total_size_bytes: 500000,
				file_types: { ".pdf": 8, ".doc": 2 },
				sample_filenames: ["invoice.pdf", "contract.pdf"],
				naming_patterns: ["YYYY_*"],
				has_date_structure: false,
				scanned_at: "2026-03-05T10:00:00Z",
			},
			{
				path: "/test/Finances",
				name: "Finances",
				depth: 1,
				file_count: 15,
				subfolder_count: 3,
				total_size_bytes: 524000,
				file_types: { ".pdf": 12, ".csv": 3 },
				sample_filenames: ["tax_2024.pdf", "bank_statement.pdf"],
				naming_patterns: ["YYYY-MM-DD_*"],
				has_date_structure: true,
				scanned_at: "2026-03-05T10:00:00Z",
			},
		],
		strategy_description:
			"This folder structure uses category-based organization with date subfolders.",
		model_used: "qwen2.5-coder:14b",
		analyzed_at: "2026-03-05T10:00:00Z",
	},
	rules: [
		{
			pattern: "tax",
			destination: "/Finances/Taxes",
			confidence: 0.9,
			pattern_type: "keyword",
			source_folder: "/test",
			reasoning: "Tax-related documents should go to Taxes folder",
			enabled: true,
			hit_count: 5,
			created_at: "2026-03-05T10:00:00Z",
		},
		{
			pattern: "invoice",
			destination: "/Finances/Invoices",
			confidence: 0.85,
			pattern_type: "keyword",
			source_folder: "/test",
			reasoning: "Invoice documents go to Invoices folder",
			enabled: true,
			hit_count: 3,
			created_at: "2026-03-05T10:00:00Z",
		},
		{
			pattern: "receipt",
			destination: "/Finances/Receipts",
			confidence: 0.75,
			pattern_type: "keyword",
			source_folder: "/test",
			reasoning: "Receipt documents go to Receipts folder",
			enabled: false,
			hit_count: 0,
			created_at: "2026-03-05T10:00:00Z",
		},
	],
	domainContext: {
		detected_domain: "personal",
		confidence: 0.85,
		evidence: [
			"Found personal documents folder",
			"Detected family photos directory",
		],
		model_used: "qwen2.5-coder:14b",
		detected_at: "2026-03-05T10:00:00Z",
	},
	timestamp: "2026-03-05T10:30:00Z",
};

const mockEmptyResponse = {
	status: {
		active: false,
		rule_count: 0,
		enabled_rule_count: 0,
		last_scan_date: null,
		rules_path: "/test/.organizer/agent/learned_routing_rules.json",
		structure_path: "/test/.organizer/agent/learned_structure.json",
	},
	structure: null,
	rules: [],
	domainContext: null,
	timestamp: "2026-03-05T10:30:00Z",
};

describe("LearnedRulesPage", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("renders page title and description", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockLearnedRulesResponse,
		});

		render(<LearnedRulesPage />);

		expect(screen.getByText("Learned Rules")).toBeInTheDocument();

		await waitFor(() => {
			expect(
				screen.getByText(/View the learned folder structure/)
			).toBeInTheDocument();
		});
	});

	it("shows loading state initially", () => {
		mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves

		render(<LearnedRulesPage />);

		expect(screen.getByText("Loading learned rules data...")).toBeInTheDocument();
	});

	it("fetches and displays status overview", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockLearnedRulesResponse,
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			// Use getAllByText since "Status" appears multiple times
			const statusElements = screen.getAllByText("Status");
			expect(statusElements.length).toBeGreaterThan(0);
			expect(screen.getByText("Active")).toBeInTheDocument();
			expect(screen.getByText("Total Rules")).toBeInTheDocument();
			expect(screen.getByText("3")).toBeInTheDocument(); // total rules
			expect(screen.getByText("Enabled Rules")).toBeInTheDocument();
			expect(screen.getByText("2")).toBeInTheDocument(); // enabled rules
		});
	});

	it("displays strategy description when available", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockLearnedRulesResponse,
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(screen.getByText("Organizational Strategy")).toBeInTheDocument();
			expect(
				screen.getByText(/category-based organization/)
			).toBeInTheDocument();
		});
	});

	it("displays domain context when available", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockLearnedRulesResponse,
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(screen.getByText("Detected Domain")).toBeInTheDocument();
			expect(screen.getByText("personal")).toBeInTheDocument();
			expect(screen.getByText("85% confidence")).toBeInTheDocument();
			expect(screen.getByText("Evidence")).toBeInTheDocument();
		});
	});

	it("displays folder structure tree", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockLearnedRulesResponse,
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(screen.getByText("Learned Structure")).toBeInTheDocument();
			expect(screen.getByText("Documents")).toBeInTheDocument();
			expect(screen.getByText("Finances")).toBeInTheDocument();
		});
	});

	it("displays routing rules", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockLearnedRulesResponse,
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(screen.getByText("Routing Rules")).toBeInTheDocument();
			expect(screen.getByText("tax")).toBeInTheDocument();
			expect(screen.getByText("invoice")).toBeInTheDocument();
			expect(screen.getByText("receipt")).toBeInTheDocument();
		});
	});

	it("shows inactive status when no rules exist", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockEmptyResponse,
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(screen.getByText("Inactive")).toBeInTheDocument();
			// Multiple "0" elements exist (Total Rules and Enabled Rules)
			const zeroElements = screen.getAllByText("0");
			expect(zeroElements.length).toBe(2);
		});
	});

	it("shows message when no structure data available", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockEmptyResponse,
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(
				screen.getByText(/No folder structure data available/)
			).toBeInTheDocument();
		});
	});

	it("shows message when no rules exist", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockEmptyResponse,
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(
				screen.getByText(/No routing rules learned yet/)
			).toBeInTheDocument();
		});
	});

	it("handles rule filter change", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockLearnedRulesResponse,
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(screen.getByText("tax")).toBeInTheDocument();
		});

		// Find the filter dropdown and change it
		const filterDropdown = screen.getByRole("combobox");
		fireEvent.change(filterDropdown, { target: { value: "enabled" } });

		// Should still show enabled rules
		expect(screen.getByText("tax")).toBeInTheDocument();
		expect(screen.getByText("invoice")).toBeInTheDocument();
		// Receipt is disabled, should not be visible
		expect(screen.queryByText("receipt")).not.toBeInTheDocument();
	});

	it("handles rule toggle action", async () => {
		mockFetch
			.mockResolvedValueOnce({
				ok: true,
				json: async () => mockLearnedRulesResponse,
			})
			.mockResolvedValueOnce({
				ok: true,
				json: async () => ({
					success: true,
					action: "toggle-rule",
					pattern: "tax",
					enabled: false,
				}),
			})
			.mockResolvedValueOnce({
				ok: true,
				json: async () => ({
					...mockLearnedRulesResponse,
					rules: mockLearnedRulesResponse.rules.map((r) =>
						r.pattern === "tax" ? { ...r, enabled: false } : r
					),
				}),
			});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(screen.getByText("tax")).toBeInTheDocument();
		});

		// Find the disable button for the tax rule
		const disableButtons = screen.getAllByText("Disable");
		expect(disableButtons.length).toBeGreaterThan(0);

		// Click the first disable button
		fireEvent.click(disableButtons[0]);

		// Verify POST request was made
		await waitFor(() => {
			expect(mockFetch).toHaveBeenCalledWith("/api/learned-rules", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: expect.stringContaining("toggle-rule"),
			});
		});
	});

	it("handles rescan action", async () => {
		mockFetch
			.mockResolvedValueOnce({
				ok: true,
				json: async () => mockLearnedRulesResponse,
			})
			.mockResolvedValueOnce({
				ok: true,
				json: async () => ({
					success: true,
					action: "rescan",
					output: "Scan completed",
				}),
			})
			.mockResolvedValueOnce({
				ok: true,
				json: async () => mockLearnedRulesResponse,
			});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(screen.getByText("Re-scan Structure")).toBeInTheDocument();
		});

		const rescanButton = screen.getByText("Re-scan Structure");
		fireEvent.click(rescanButton);

		// Verify POST request was made with rescan action
		await waitFor(() => {
			expect(mockFetch).toHaveBeenCalledWith("/api/learned-rules", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: expect.stringContaining("rescan"),
			});
		});
	});

	it("displays error message when API returns error", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => ({
				...mockEmptyResponse,
				error: "Failed to read learned rules",
			}),
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(
				screen.getByText("Failed to read learned rules")
			).toBeInTheDocument();
		});
	});

	it("displays back to dashboard link", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockLearnedRulesResponse,
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			// The link contains "← Back to Dashboard" so use a partial match
			const backLink = screen.getByText(/Back to Dashboard/);
			expect(backLink).toBeInTheDocument();
			expect(backLink.closest("a")).toHaveAttribute("href", "/");
		});
	});

	it("shows date-based badge for folders with date structure", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockLearnedRulesResponse,
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(screen.getByText("date-based")).toBeInTheDocument();
		});
	});

	it("shows rule hit count when available", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockLearnedRulesResponse,
		});

		render(<LearnedRulesPage />);

		await waitFor(() => {
			expect(screen.getByText("5 hits")).toBeInTheDocument(); // tax rule has 5 hits
			expect(screen.getByText("3 hits")).toBeInTheDocument(); // invoice rule has 3 hits
		});
	});
});
