import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// Mock fetch function globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Import after mocking
import ScatterReportPage from "@/app/scatter-report/page";

// Mock data
const mockScatterReportResponse = {
	groups: [
		{
			rootBin: "Finances Bin",
			violations: [
				{
					filePath: "/Users/test/Documents/RandomFolder/bill.pdf",
					fileName: "bill.pdf",
					currentBin: "RandomFolder",
					expectedBin: "Finances Bin",
					confidence: 0.95,
					reason: "File contains billing information",
					modelUsed: "llama3.1:8b-instruct-q8_0",
					suggestedSubpath: "Bills/2024",
					usedKeywordFallback: false,
				},
				{
					filePath: "/Users/test/Documents/Misc/invoice.pdf",
					fileName: "invoice.pdf",
					currentBin: "Misc",
					expectedBin: "Finances Bin",
					confidence: 0.88,
					reason: "Invoice detected by filename pattern",
					modelUsed: "llama3.1:8b-instruct-q8_0",
					suggestedSubpath: "Invoices",
					usedKeywordFallback: false,
				},
			],
			totalViolations: 2,
		},
		{
			rootBin: "VA",
			violations: [
				{
					filePath: "/Users/test/Documents/Random/va_letter.pdf",
					fileName: "va_letter.pdf",
					currentBin: "Random",
					expectedBin: "VA",
					confidence: 0.72,
					reason: "VA-related document detected",
					modelUsed: "",
					suggestedSubpath: "Correspondence",
					usedKeywordFallback: true,
				},
			],
			totalViolations: 1,
		},
	],
	totalViolations: 3,
	filesScanned: 150,
	filesInCorrectBin: 147,
	modelUsed: "llama3.1:8b-instruct-q8_0",
	usedKeywordFallback: false,
	scannedDirectory: "/Users/test/Documents",
	source: "queue" as const,
};

const mockEmptyResponse = {
	groups: [],
	totalViolations: 0,
	filesScanned: 100,
	filesInCorrectBin: 100,
	modelUsed: "llama3.1:8b-instruct-q8_0",
	usedKeywordFallback: false,
	scannedDirectory: "/Users/test/Documents",
	source: "queue" as const,
};

describe("ScatterReportPage", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("renders page title and description", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		// Title is always visible
		expect(screen.getByText("Scatter Report")).toBeInTheDocument();

		// Wait for data to load and description to appear
		await waitFor(() => {
			expect(
				screen.getByText(/Files that exist outside their correct taxonomy bin/)
			).toBeInTheDocument();
		});
	});

	it("shows loading state initially", () => {
		mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves

		render(<ScatterReportPage />);

		expect(screen.getByText("Loading scatter report...")).toBeInTheDocument();
	});

	it("fetches and displays scatter report with violations", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			// Look for group headers specifically (font-semibold class)
			const financesBinHeaders = screen.getAllByText("Finances Bin");
			expect(financesBinHeaders.length).toBeGreaterThan(0);
			const vaHeaders = screen.getAllByText("VA");
			expect(vaHeaders.length).toBeGreaterThan(0);
		});
	});

	it("displays summary stats", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			expect(screen.getByText("Total Violations")).toBeInTheDocument();
			expect(screen.getByText("3")).toBeInTheDocument(); // total violations
			expect(screen.getByText("Files Scanned")).toBeInTheDocument();
			expect(screen.getByText("150")).toBeInTheDocument(); // files scanned
			expect(screen.getByText("Files in Correct Bin")).toBeInTheDocument();
			expect(screen.getByText("147")).toBeInTheDocument(); // files in correct bin
			expect(screen.getByText("Source")).toBeInTheDocument();
			expect(screen.getByText("queue")).toBeInTheDocument();
		});
	});

	it("shows model info when available", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			expect(screen.getByText("Model Used:")).toBeInTheDocument();
			// Model name appears multiple times (header + violations)
			const modelElements = screen.getAllByText("llama3.1:8b-instruct-q8_0");
			expect(modelElements.length).toBeGreaterThan(0);
		});
	});

	it("shows keyword fallback badge when appropriate", async () => {
		const responseWithKeywordFallback = {
			...mockScatterReportResponse,
			usedKeywordFallback: true,
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => responseWithKeywordFallback,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			expect(screen.getByText("Keyword Fallback")).toBeInTheDocument();
		});
	});

	it("shows error message on fetch failure", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: false,
			status: 500,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			expect(screen.getByText(/HTTP error: 500/)).toBeInTheDocument();
			expect(screen.getByText("Try again")).toBeInTheDocument();
		});
	});

	it("retries fetch when Try again is clicked", async () => {
		mockFetch
			.mockResolvedValueOnce({
				ok: false,
				status: 500,
			})
			.mockResolvedValueOnce({
				ok: true,
				json: async () => mockScatterReportResponse,
			});

		render(<ScatterReportPage />);

		await waitFor(() => {
			expect(screen.getByText("Try again")).toBeInTheDocument();
		});

		fireEvent.click(screen.getByText("Try again"));

		await waitFor(() => {
			const financesBin = screen.getAllByText("Finances Bin");
			expect(financesBin.length).toBeGreaterThan(0);
		});
	});

	it("shows empty state when no violations", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockEmptyResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			expect(screen.getByText("No violations found")).toBeInTheDocument();
			expect(
				screen.getByText("All files appear to be in their correct taxonomy bins.")
			).toBeInTheDocument();
		});
	});

	it("displays violation details correctly", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			// File name
			expect(screen.getByText("bill.pdf")).toBeInTheDocument();
			// Current bin -> Expected bin path
			expect(screen.getByText("RandomFolder")).toBeInTheDocument();
			// Finances Bin appears multiple times - just verify it's present
			const financesBinElements = screen.getAllByText("Finances Bin");
			expect(financesBinElements.length).toBeGreaterThan(0);
			// Confidence badge - look for the percentage
			expect(screen.getByText("95%")).toBeInTheDocument();
			// Reason
			expect(
				screen.getByText("File contains billing information")
			).toBeInTheDocument();
		});
	});

	it("expands groups by default", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			// Both groups should be expanded and show violations
			expect(screen.getByText("bill.pdf")).toBeInTheDocument();
			expect(screen.getByText("invoice.pdf")).toBeInTheDocument();
			expect(screen.getByText("va_letter.pdf")).toBeInTheDocument();
		});
	});

	it("collapses group when header clicked", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			expect(screen.getByText("bill.pdf")).toBeInTheDocument();
		});

		// Click the group header to collapse - find the font-semibold one specifically
		const groupHeaders = screen.getAllByText("Finances Bin");
		const groupHeader = groupHeaders.find((el) =>
			el.classList.contains("font-semibold")
		);
		const clickableDiv = groupHeader?.closest("div.cursor-pointer");
		fireEvent.click(clickableDiv!);

		// Violations in that group should be hidden
		await waitFor(() => {
			expect(screen.queryByText("bill.pdf")).not.toBeInTheDocument();
		});

		// Other group should still be visible
		expect(screen.getByText("va_letter.pdf")).toBeInTheDocument();
	});

	it("selects violation when checkbox clicked", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			expect(screen.getByText("bill.pdf")).toBeInTheDocument();
		});

		// Click first violation checkbox
		const checkboxes = screen.getAllByRole("checkbox");
		fireEvent.click(checkboxes[0]);

		// Should show selection count
		await waitFor(() => {
			expect(screen.getByText("1 selected")).toBeInTheDocument();
		});
	});

	it("select all in group selects all violations in that group", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			expect(screen.getByText("bill.pdf")).toBeInTheDocument();
		});

		// Find and click "Select All" button for Finances Bin group
		const selectAllButtons = screen.getAllByRole("button", {
			name: /Select All/i,
		});
		fireEvent.click(selectAllButtons[0]);

		// Should show 2 selected (both violations in Finances Bin group)
		await waitFor(() => {
			expect(screen.getByText("2 selected")).toBeInTheDocument();
		});
	});

	it("select high confidence selects violations with confidence >= 0.95", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			expect(screen.getByText("bill.pdf")).toBeInTheDocument();
		});

		// Click "Select High Confidence" button
		fireEvent.click(screen.getByText(/Select High Confidence/));

		// Only one violation has confidence >= 0.95 (bill.pdf at 0.95)
		await waitFor(() => {
			expect(screen.getByText("1 selected")).toBeInTheDocument();
		});
	});

	it("shows back to dashboard link", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		// Wait for content to load
		await waitFor(() => {
			expect(screen.getByText("← Back to Dashboard")).toBeInTheDocument();
		});
	});

	it("shows violation count badges on groups", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			// Finances Bin has 2 violations
			expect(screen.getByText("2 violations")).toBeInTheDocument();
			// VA has 1 violation
			expect(screen.getByText("1 violation")).toBeInTheDocument();
		});
	});

	it("shows keyword badge for keyword fallback violations", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			// va_letter.pdf uses keyword fallback
			// Look for the Keyword badges - there should be at least one
			const keywordBadges = screen.getAllByText("Keyword");
			expect(keywordBadges.length).toBeGreaterThan(0);
		});
	});

	it("shows model badge for LLM-powered violations", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			// bill.pdf and invoice.pdf use LLM
			// Model badges should be visible
			const modelBadges = screen.getAllByText("llama3.1:8b-instruct-q8_0");
			// One in the header, two on violations
			expect(modelBadges.length).toBeGreaterThanOrEqual(1);
		});
	});

	it("displays confidence with appropriate color coding", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			// 95% should be green (high confidence)
			const highConfBadge = screen.getByText("95%");
			expect(highConfBadge.className).toContain("bg-green-100");

			// 88% should be yellow (medium confidence)
			const medConfBadge = screen.getByText("88%");
			expect(medConfBadge.className).toContain("bg-yellow-100");

			// 72% should be red (low confidence)
			const lowConfBadge = screen.getByText("72%");
			expect(lowConfBadge.className).toContain("bg-red-100");
		});
	});

	it("refresh button reloads from queue", async () => {
		mockFetch
			.mockResolvedValueOnce({
				ok: true,
				json: async () => mockScatterReportResponse,
			})
			.mockResolvedValueOnce({
				ok: true,
				json: async () => mockEmptyResponse,
			});

		render(<ScatterReportPage />);

		await waitFor(() => {
			const financesBin = screen.getAllByText("Finances Bin");
			expect(financesBin.length).toBeGreaterThan(0);
		});

		// Click refresh
		fireEvent.click(screen.getByText("Refresh from Queue"));

		await waitFor(() => {
			expect(screen.getByText("No violations found")).toBeInTheDocument();
		});
	});

	it("run scan button triggers new scan", async () => {
		const scanResponse = {
			...mockScatterReportResponse,
			source: "scan" as const,
			filesScanned: 500,
		};

		mockFetch
			.mockResolvedValueOnce({
				ok: true,
				json: async () => mockEmptyResponse,
			})
			.mockResolvedValueOnce({
				ok: true,
				json: async () => scanResponse,
			});

		render(<ScatterReportPage />);

		await waitFor(() => {
			expect(screen.getByText("No violations found")).toBeInTheDocument();
		});

		// Click "Run New Scan"
		fireEvent.click(screen.getByText("Run New Scan"));

		await waitFor(() => {
			const financesBin = screen.getAllByText("Finances Bin");
			expect(financesBin.length).toBeGreaterThan(0);
			expect(screen.getByText("500")).toBeInTheDocument(); // filesScanned
			expect(screen.getByText("scan")).toBeInTheDocument(); // source
		});
	});

	it("handles API error response", async () => {
		const errorResponse = {
			...mockEmptyResponse,
			error: "Queue directory does not exist",
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => errorResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			expect(
				screen.getByText("Queue directory does not exist")
			).toBeInTheDocument();
		});
	});

	it("shows suggested subpath in violation details", async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockScatterReportResponse,
		});

		render(<ScatterReportPage />);

		await waitFor(() => {
			// bill.pdf has suggestedSubpath: "Bills/2024"
			expect(screen.getByText(/\/Bills\/2024/)).toBeInTheDocument();
		});
	});
});
