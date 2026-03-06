import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync } from "fs";
import { tmpdir } from "os";
import path from "path";
import { GET, POST } from "@/app/api/learned-rules/route";

describe("Learned Rules API", () => {
	let tempDir: string;
	let organizerDir: string;
	let agentDir: string;

	beforeEach(() => {
		// Create a temporary directory for each test
		tempDir = mkdtempSync(path.join(tmpdir(), "learned-rules-api-test-"));
		organizerDir = path.join(tempDir, ".organizer");
		agentDir = path.join(organizerDir, "agent");
		mkdirSync(agentDir, { recursive: true });
	});

	afterEach(() => {
		// Clean up temporary directory
		rmSync(tempDir, { recursive: true, force: true });
	});

	// Helper to create a NextRequest with query params
	function createGetRequest(params: Record<string, string>): NextRequest {
		const url = new URL("http://localhost/api/learned-rules");
		for (const [key, value] of Object.entries(params)) {
			url.searchParams.set(key, value);
		}
		return new NextRequest(url);
	}

	// Helper to create a POST request
	function createPostRequest(body: unknown): NextRequest {
		return new NextRequest("http://localhost/api/learned-rules", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify(body),
		});
	}

	// Helper to create a structure snapshot file
	function createStructureSnapshot(
		folders: Array<{
			path: string;
			name: string;
			depth: number;
			file_count: number;
		}>,
		strategy?: string,
	): void {
		const snapshot = {
			version: "1.0",
			root_path: tempDir,
			max_depth: 4,
			total_folders: folders.length,
			total_files: folders.reduce((sum, f) => sum + f.file_count, 0),
			total_size_bytes: 1000000,
			folders: folders.map((f) => ({
				...f,
				subfolder_count: 0,
				total_size_bytes: 10000,
				file_types: { ".pdf": f.file_count },
				sample_filenames: ["file1.pdf", "file2.pdf"],
				naming_patterns: [],
				has_date_structure: false,
				scanned_at: new Date().toISOString(),
			})),
			strategy_description: strategy || "",
			model_used: strategy ? "qwen2.5-coder:14b" : "",
			analyzed_at: new Date().toISOString(),
		};

		writeFileSync(
			path.join(agentDir, "learned_structure.json"),
			JSON.stringify(snapshot, null, 2),
		);
	}

	// Helper to create routing rules file
	function createRoutingRules(
		rules: Array<{
			pattern: string;
			destination: string;
			confidence?: number;
			enabled?: boolean;
		}>,
	): void {
		const rulesData = {
			version: "1.0",
			rules: rules.map((r) => ({
				pattern: r.pattern,
				destination: r.destination,
				confidence: r.confidence ?? 0.85,
				pattern_type: "keyword",
				source_folder: tempDir,
				reasoning: "Test rule",
				enabled: r.enabled ?? true,
				hit_count: 0,
				created_at: new Date().toISOString(),
			})),
			updated_at: new Date().toISOString(),
		};

		writeFileSync(
			path.join(agentDir, "learned_routing_rules.json"),
			JSON.stringify(rulesData, null, 2),
		);
	}

	// Helper to create domain context file
	function createDomainContext(
		domain: string,
		confidence: number,
		evidence: string[],
	): void {
		const domainData = {
			detected_domain: domain,
			confidence,
			evidence,
			model_used: "qwen2.5-coder:14b",
			detected_at: new Date().toISOString(),
		};

		writeFileSync(
			path.join(agentDir, "domain_context.json"),
			JSON.stringify(domainData, null, 2),
		);
	}

	// ============================================================================
	// GET /api/learned-rules - Basic tests
	// ============================================================================

	describe("GET - Basic functionality", () => {
		it("should return empty data when no files exist", async () => {
			const request = createGetRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.status).not.toBeNull();
			expect(data.status.active).toBe(false);
			expect(data.status.rule_count).toBe(0);
			expect(data.structure).toBeNull();
			expect(data.rules).toHaveLength(0);
			expect(data.domainContext).toBeNull();
		});

		it("should return structure snapshot when file exists", async () => {
			createStructureSnapshot(
				[
					{ path: `${tempDir}/Documents`, name: "Documents", depth: 1, file_count: 10 },
					{ path: `${tempDir}/Finances`, name: "Finances", depth: 1, file_count: 5 },
				],
				"This folder uses category-based organization.",
			);

			const request = createGetRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.structure).not.toBeNull();
			expect(data.structure.total_folders).toBe(2);
			expect(data.structure.strategy_description).toBe(
				"This folder uses category-based organization.",
			);
			expect(data.structure.folders).toHaveLength(2);
		});

		it("should return routing rules when file exists", async () => {
			createRoutingRules([
				{ pattern: "tax", destination: "/Finances/Taxes", confidence: 0.9 },
				{ pattern: "invoice", destination: "/Finances/Invoices", confidence: 0.85 },
			]);

			const request = createGetRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.rules).toHaveLength(2);
			expect(data.status.rule_count).toBe(2);
			expect(data.status.enabled_rule_count).toBe(2);
			expect(data.status.active).toBe(true);
		});

		it("should return domain context when file exists", async () => {
			createDomainContext("personal", 0.85, [
				"Found personal folder",
				"Detected photos directory",
			]);

			const request = createGetRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.domainContext).not.toBeNull();
			expect(data.domainContext.detected_domain).toBe("personal");
			expect(data.domainContext.confidence).toBe(0.85);
			expect(data.domainContext.evidence).toHaveLength(2);
		});
	});

	// ============================================================================
	// GET /api/learned-rules - Status calculation tests
	// ============================================================================

	describe("GET - Status calculation", () => {
		it("should calculate active status correctly with enabled rules", async () => {
			createRoutingRules([
				{ pattern: "tax", destination: "/Finances/Taxes", enabled: true },
				{ pattern: "invoice", destination: "/Finances/Invoices", enabled: true },
				{ pattern: "receipt", destination: "/Finances/Receipts", enabled: false },
			]);

			const request = createGetRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.status.active).toBe(true);
			expect(data.status.rule_count).toBe(3);
			expect(data.status.enabled_rule_count).toBe(2);
		});

		it("should be inactive when all rules are disabled", async () => {
			createRoutingRules([
				{ pattern: "tax", destination: "/Finances/Taxes", enabled: false },
				{ pattern: "invoice", destination: "/Finances/Invoices", enabled: false },
			]);

			const request = createGetRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.status.active).toBe(false);
			expect(data.status.rule_count).toBe(2);
			expect(data.status.enabled_rule_count).toBe(0);
		});

		it("should include last scan date from structure", async () => {
			const analyzedAt = new Date().toISOString();
			createStructureSnapshot(
				[{ path: `${tempDir}/Docs`, name: "Docs", depth: 1, file_count: 5 }],
				"Test strategy",
			);

			const request = createGetRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.status.last_scan_date).not.toBeNull();
		});
	});

	// ============================================================================
	// GET /api/learned-rules - Error handling tests
	// ============================================================================

	describe("GET - Error handling", () => {
		it("should handle invalid JSON in structure file", async () => {
			writeFileSync(
				path.join(agentDir, "learned_structure.json"),
				"invalid json",
			);

			const request = createGetRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			// Should return null structure but not error
			expect(data.structure).toBeNull();
		});

		it("should handle invalid JSON in rules file", async () => {
			writeFileSync(
				path.join(agentDir, "learned_routing_rules.json"),
				"invalid json",
			);

			const request = createGetRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			// Should return empty rules but not error
			expect(data.rules).toHaveLength(0);
		});
	});

	// ============================================================================
	// POST /api/learned-rules - Toggle rule action
	// ============================================================================

	describe("POST - toggle-rule action", () => {
		it("should toggle rule from enabled to disabled", async () => {
			createRoutingRules([
				{ pattern: "tax", destination: "/Finances/Taxes", enabled: true },
			]);

			const request = createPostRequest({
				action: "toggle-rule",
				basePath: tempDir,
				pattern: "tax",
			});
			const response = await POST(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.success).toBe(true);
			expect(data.enabled).toBe(false);

			// Verify the file was updated
			const rulesContent = readFileSync(
				path.join(agentDir, "learned_routing_rules.json"),
				"utf-8",
			);
			const rules = JSON.parse(rulesContent);
			expect(rules.rules[0].enabled).toBe(false);
		});

		it("should toggle rule from disabled to enabled", async () => {
			createRoutingRules([
				{ pattern: "tax", destination: "/Finances/Taxes", enabled: false },
			]);

			const request = createPostRequest({
				action: "toggle-rule",
				basePath: tempDir,
				pattern: "tax",
			});
			const response = await POST(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			expect(data.success).toBe(true);
			expect(data.enabled).toBe(true);
		});

		it("should return 404 for non-existent pattern", async () => {
			createRoutingRules([
				{ pattern: "tax", destination: "/Finances/Taxes", enabled: true },
			]);

			const request = createPostRequest({
				action: "toggle-rule",
				basePath: tempDir,
				pattern: "nonexistent",
			});
			const response = await POST(request);

			expect(response.status).toBe(404);
			const data = await response.json();
			expect(data.error).toBe("Rule not found");
		});

		it("should return 400 if pattern is missing", async () => {
			createRoutingRules([
				{ pattern: "tax", destination: "/Finances/Taxes", enabled: true },
			]);

			const request = createPostRequest({
				action: "toggle-rule",
				basePath: tempDir,
			});
			const response = await POST(request);

			expect(response.status).toBe(400);
			const data = await response.json();
			expect(data.error).toBe("Pattern is required");
		});
	});

	// ============================================================================
	// POST /api/learned-rules - Unknown action
	// ============================================================================

	describe("POST - Unknown action", () => {
		it("should return 400 for unknown action", async () => {
			const request = createPostRequest({
				action: "unknown-action",
				basePath: tempDir,
			});
			const response = await POST(request);

			expect(response.status).toBe(400);
			const data = await response.json();
			expect(data.error).toContain("Unknown action");
		});
	});

	// ============================================================================
	// Response structure tests
	// ============================================================================

	describe("Response structure", () => {
		it("should return all expected fields in response", async () => {
			createStructureSnapshot(
				[{ path: `${tempDir}/Docs`, name: "Docs", depth: 1, file_count: 5 }],
				"Test strategy",
			);
			createRoutingRules([
				{ pattern: "tax", destination: "/Finances/Taxes" },
			]);
			createDomainContext("personal", 0.85, ["Test evidence"]);

			const request = createGetRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();

			// Check all expected fields
			expect(data).toHaveProperty("status");
			expect(data).toHaveProperty("structure");
			expect(data).toHaveProperty("rules");
			expect(data).toHaveProperty("domainContext");
			expect(data).toHaveProperty("timestamp");

			// Check status fields
			expect(data.status).toHaveProperty("active");
			expect(data.status).toHaveProperty("rule_count");
			expect(data.status).toHaveProperty("enabled_rule_count");
			expect(data.status).toHaveProperty("last_scan_date");
			expect(data.status).toHaveProperty("rules_path");
			expect(data.status).toHaveProperty("structure_path");
		});

		it("should return proper rule structure", async () => {
			createRoutingRules([
				{ pattern: "tax", destination: "/Finances/Taxes", confidence: 0.9 },
			]);

			const request = createGetRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			const rule = data.rules[0];

			// Check all rule fields
			expect(rule).toHaveProperty("pattern");
			expect(rule).toHaveProperty("destination");
			expect(rule).toHaveProperty("confidence");
			expect(rule).toHaveProperty("pattern_type");
			expect(rule).toHaveProperty("source_folder");
			expect(rule).toHaveProperty("reasoning");
			expect(rule).toHaveProperty("enabled");
			expect(rule).toHaveProperty("hit_count");
			expect(rule).toHaveProperty("created_at");
		});

		it("should return proper folder node structure", async () => {
			createStructureSnapshot([
				{
					path: `${tempDir}/Documents`,
					name: "Documents",
					depth: 1,
					file_count: 10,
				},
			]);

			const request = createGetRequest({ basePath: tempDir });
			const response = await GET(request);

			expect(response.status).toBe(200);
			const data = await response.json();
			const folder = data.structure.folders[0];

			// Check all folder fields
			expect(folder).toHaveProperty("path");
			expect(folder).toHaveProperty("name");
			expect(folder).toHaveProperty("depth");
			expect(folder).toHaveProperty("file_count");
			expect(folder).toHaveProperty("subfolder_count");
			expect(folder).toHaveProperty("total_size_bytes");
			expect(folder).toHaveProperty("file_types");
			expect(folder).toHaveProperty("sample_filenames");
			expect(folder).toHaveProperty("naming_patterns");
			expect(folder).toHaveProperty("has_date_structure");
			expect(folder).toHaveProperty("scanned_at");
		});
	});
});
