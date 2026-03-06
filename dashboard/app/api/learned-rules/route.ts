import { NextRequest, NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";
import * as fs from "fs/promises";
import * as path from "path";

const execAsync = promisify(exec);

// Default paths (can be overridden via query params)
const DEFAULT_STRUCTURE_PATH = ".organizer/agent/learned_structure.json";
const DEFAULT_RULES_PATH = ".organizer/agent/learned_routing_rules.json";

interface FolderNode {
	path: string;
	name: string;
	depth: number;
	file_count: number;
	subfolder_count: number;
	total_size_bytes: number;
	file_types: Record<string, number>;
	sample_filenames: string[];
	naming_patterns: string[];
	has_date_structure: boolean;
	scanned_at: string;
}

interface StructureSnapshot {
	version: string;
	root_path: string;
	max_depth: number;
	total_folders: number;
	total_files: number;
	total_size_bytes: number;
	folders: FolderNode[];
	strategy_description: string;
	model_used: string;
	analyzed_at: string;
}

interface StoredRule {
	pattern: string;
	destination: string;
	confidence: number;
	pattern_type: string;
	source_folder: string;
	reasoning: string;
	enabled: boolean;
	hit_count: number;
	created_at: string;
}

interface RulesData {
	version: string;
	rules: StoredRule[];
	updated_at: string;
}

interface DomainContext {
	detected_domain: string;
	confidence: number;
	evidence: string[];
	model_used: string;
	detected_at: string;
}

interface LearnedRulesStatus {
	active: boolean;
	rule_count: number;
	enabled_rule_count: number;
	last_scan_date: string | null;
	rules_path: string;
	structure_path: string;
}

export async function GET(request: NextRequest) {
	const searchParams = request.nextUrl.searchParams;
	const basePath =
		searchParams.get("basePath") ||
		process.env.NEXT_PUBLIC_ORGANIZER_BASE_PATH ||
		process.cwd();

	try {
		const structurePath = path.join(basePath, DEFAULT_STRUCTURE_PATH);
		const rulesPath = path.join(basePath, DEFAULT_RULES_PATH);

		// Load structure snapshot
		let structure: StructureSnapshot | null = null;
		try {
			const structureContent = await fs.readFile(structurePath, "utf-8");
			structure = JSON.parse(structureContent);
		} catch {
			// Structure file doesn't exist or is invalid
		}

		// Load routing rules
		let rules: RulesData | null = null;
		try {
			const rulesContent = await fs.readFile(rulesPath, "utf-8");
			rules = JSON.parse(rulesContent);
		} catch {
			// Rules file doesn't exist or is invalid
		}

		// Load domain context (if available from structure analysis)
		let domainContext: DomainContext | null = null;
		const domainPath = path.join(
			basePath,
			".organizer/agent/domain_context.json"
		);
		try {
			const domainContent = await fs.readFile(domainPath, "utf-8");
			domainContext = JSON.parse(domainContent);
		} catch {
			// Domain context file doesn't exist
		}

		// Calculate status
		const rulesList = rules?.rules || [];
		const enabledRules = rulesList.filter((r) => r.enabled);

		const status: LearnedRulesStatus = {
			active: rulesList.length > 0 && enabledRules.length > 0,
			rule_count: rulesList.length,
			enabled_rule_count: enabledRules.length,
			last_scan_date: structure?.analyzed_at || null,
			rules_path: rulesPath,
			structure_path: structurePath,
		};

		return NextResponse.json({
			status,
			structure,
			rules: rulesList,
			domainContext,
			timestamp: new Date().toISOString(),
		});
	} catch (error) {
		return NextResponse.json(
			{
				error: error instanceof Error ? error.message : "Unknown error",
				status: null,
				structure: null,
				rules: [],
				domainContext: null,
			},
			{ status: 500 }
		);
	}
}

export async function POST(request: NextRequest) {
	const body = await request.json();
	const { action, basePath: bodyBasePath, pattern } = body;

	const basePath =
		bodyBasePath ||
		process.env.NEXT_PUBLIC_ORGANIZER_BASE_PATH ||
		process.cwd();

	try {
		switch (action) {
			case "rescan": {
				// Trigger a structure rescan via CLI
				const scanPath = body.scanPath || basePath;
				const { stdout, stderr } = await execAsync(
					`cd "${basePath}" && python3 -m organizer --learn-structure "${scanPath}"`,
					{ timeout: 120000 }
				);
				return NextResponse.json({
					success: true,
					action: "rescan",
					output: stdout,
					error: stderr || null,
				});
			}

			case "confirm": {
				// Activate learned rules via CLI
				const { stdout, stderr } = await execAsync(
					`cd "${basePath}" && python3 -m organizer --learn-confirm`,
					{ timeout: 30000 }
				);
				return NextResponse.json({
					success: true,
					action: "confirm",
					output: stdout,
					error: stderr || null,
				});
			}

			case "toggle-rule": {
				// Enable or disable a specific rule
				if (!pattern) {
					return NextResponse.json(
						{ success: false, error: "Pattern is required" },
						{ status: 400 }
					);
				}

				const rulesPath = path.join(basePath, DEFAULT_RULES_PATH);
				const rulesContent = await fs.readFile(rulesPath, "utf-8");
				const rulesData: RulesData = JSON.parse(rulesContent);

				const rule = rulesData.rules.find((r) => r.pattern === pattern);
				if (!rule) {
					return NextResponse.json(
						{ success: false, error: "Rule not found" },
						{ status: 404 }
					);
				}

				// Toggle the enabled state
				rule.enabled = !rule.enabled;
				rulesData.updated_at = new Date().toISOString();

				await fs.writeFile(
					rulesPath,
					JSON.stringify(rulesData, null, 2),
					"utf-8"
				);

				return NextResponse.json({
					success: true,
					action: "toggle-rule",
					pattern,
					enabled: rule.enabled,
				});
			}

			default:
				return NextResponse.json(
					{ success: false, error: `Unknown action: ${action}` },
					{ status: 400 }
				);
		}
	} catch (error) {
		return NextResponse.json(
			{
				success: false,
				action,
				error: error instanceof Error ? error.message : "Unknown error",
			},
			{ status: 500 }
		);
	}
}
