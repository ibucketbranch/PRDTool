"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";

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

interface LearnedRulesResponse {
	status: LearnedRulesStatus | null;
	structure: StructureSnapshot | null;
	rules: StoredRule[];
	domainContext: DomainContext | null;
	error?: string;
}

const BASE_PATH =
	process.env.NEXT_PUBLIC_ORGANIZER_BASE_PATH ||
	"/Users/michaelvalderrama/Websites/PRDTool";

const CONFIDENCE_COLORS: Record<string, string> = {
	high: "bg-green-100 text-green-800",
	medium: "bg-yellow-100 text-yellow-800",
	low: "bg-red-100 text-red-800",
};

function getConfidenceLevel(confidence: number): "high" | "medium" | "low" {
	if (confidence >= 0.8) return "high";
	if (confidence >= 0.5) return "medium";
	return "low";
}

function formatBytes(bytes: number): string {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	if (bytes < 1024 * 1024 * 1024)
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

interface FolderTreeProps {
	folders: FolderNode[];
	maxDepth?: number;
}

function FolderTree({ folders, maxDepth = 3 }: FolderTreeProps) {
	const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());

	// Build a tree structure from flat folder list
	const sortedFolders = [...folders]
		.filter((f) => f.depth <= maxDepth)
		.sort((a, b) => {
			// Sort by path to ensure parent comes before children
			return a.path.localeCompare(b.path);
		});

	const toggleExpand = (path: string) => {
		const newExpanded = new Set(expandedPaths);
		if (newExpanded.has(path)) {
			newExpanded.delete(path);
		} else {
			newExpanded.add(path);
		}
		setExpandedPaths(newExpanded);
	};

	// Get visible folders based on expanded state
	const getVisibleFolders = (): FolderNode[] => {
		const visible: FolderNode[] = [];
		const expandedParents = new Set<string>();

		// Start with root (depth 0)
		expandedParents.add("");

		for (const folder of sortedFolders) {
			// Check if parent is expanded or if this is a top-level folder
			const parentPath = folder.path.substring(
				0,
				folder.path.lastIndexOf("/")
			);
			const isTopLevel = folder.depth <= 1;

			if (isTopLevel || expandedPaths.has(parentPath)) {
				visible.push(folder);
				if (expandedPaths.has(folder.path)) {
					expandedParents.add(folder.path);
				}
			}
		}

		return visible;
	};

	const visibleFolders = getVisibleFolders();

	if (folders.length === 0) {
		return (
			<div className="text-neutral-500 text-sm p-4">
				No folder structure data available. Run a structure scan first.
			</div>
		);
	}

	return (
		<div className="space-y-1">
			{visibleFolders.map((folder) => {
				const hasChildren = sortedFolders.some(
					(f) =>
						f.path.startsWith(folder.path + "/") &&
						f.depth === folder.depth + 1
				);
				const isExpanded = expandedPaths.has(folder.path);
				const indent = folder.depth * 20;

				return (
					<div
						key={folder.path}
						className="bg-neutral-50 rounded border border-neutral-200 hover:border-neutral-300 transition-colors"
						style={{ marginLeft: `${indent}px` }}
					>
						<div className="p-2 flex items-center justify-between">
							<div className="flex items-center gap-2 flex-1 min-w-0">
								{hasChildren ? (
									<button
										onClick={() => toggleExpand(folder.path)}
										className="w-5 h-5 flex items-center justify-center text-neutral-500 hover:text-neutral-700"
									>
										{isExpanded ? (
											<svg
												className="w-4 h-4"
												fill="none"
												stroke="currentColor"
												viewBox="0 0 24 24"
											>
												<path
													strokeLinecap="round"
													strokeLinejoin="round"
													strokeWidth={2}
													d="M19 9l-7 7-7-7"
												/>
											</svg>
										) : (
											<svg
												className="w-4 h-4"
												fill="none"
												stroke="currentColor"
												viewBox="0 0 24 24"
											>
												<path
													strokeLinecap="round"
													strokeLinejoin="round"
													strokeWidth={2}
													d="M9 5l7 7-7 7"
												/>
											</svg>
										)}
									</button>
								) : (
									<span className="w-5" />
								)}
								<span className="font-medium text-sm truncate">
									{folder.name}
								</span>
								{folder.has_date_structure && (
									<span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
										date-based
									</span>
								)}
							</div>
							<div className="flex items-center gap-3 text-xs text-neutral-500 flex-shrink-0">
								<span>{folder.file_count} files</span>
								{folder.subfolder_count > 0 && (
									<span>{folder.subfolder_count} folders</span>
								)}
								<span>{formatBytes(folder.total_size_bytes)}</span>
							</div>
						</div>
						{isExpanded && folder.sample_filenames.length > 0 && (
							<div className="px-2 pb-2 ml-7">
								<div className="text-xs text-neutral-500">
									<span className="font-medium">Sample files:</span>{" "}
									{folder.sample_filenames.slice(0, 5).join(", ")}
									{folder.sample_filenames.length > 5 && "..."}
								</div>
								{folder.naming_patterns.length > 0 && (
									<div className="text-xs text-neutral-500 mt-1">
										<span className="font-medium">Patterns:</span>{" "}
										{folder.naming_patterns.join(", ")}
									</div>
								)}
								{Object.keys(folder.file_types).length > 0 && (
									<div className="text-xs text-neutral-500 mt-1">
										<span className="font-medium">Types:</span>{" "}
										{Object.entries(folder.file_types)
											.sort((a, b) => b[1] - a[1])
											.slice(0, 5)
											.map(([ext, count]) => `${ext} (${count})`)
											.join(", ")}
									</div>
								)}
							</div>
						)}
					</div>
				);
			})}
		</div>
	);
}

export default function LearnedRulesPage() {
	const [data, setData] = useState<LearnedRulesResponse | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [actionInProgress, setActionInProgress] = useState<string | null>(null);
	const [actionResult, setActionResult] = useState<{
		success: boolean;
		message: string;
	} | null>(null);
	const [rulesFilter, setRulesFilter] = useState<"all" | "enabled" | "disabled">(
		"all"
	);

	const loadData = useCallback(async () => {
		try {
			setError(null);
			const res = await fetch(
				`/api/learned-rules?basePath=${encodeURIComponent(BASE_PATH)}`
			);
			const result: LearnedRulesResponse = await res.json();
			if (result.error) {
				setError(result.error);
			}
			setData(result);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load data");
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		loadData();
	}, [loadData]);

	const handleRescan = async () => {
		setActionInProgress("rescan");
		setActionResult(null);
		try {
			const res = await fetch("/api/learned-rules", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ action: "rescan", basePath: BASE_PATH }),
			});
			const result = await res.json();
			if (result.success) {
				setActionResult({
					success: true,
					message: "Structure rescan completed successfully",
				});
				await loadData();
			} else {
				setActionResult({
					success: false,
					message: result.error || "Rescan failed",
				});
			}
		} catch (err) {
			setActionResult({
				success: false,
				message: err instanceof Error ? err.message : "Rescan failed",
			});
		} finally {
			setActionInProgress(null);
		}
	};

	const handleToggleRule = async (pattern: string) => {
		setActionInProgress(`toggle:${pattern}`);
		try {
			const res = await fetch("/api/learned-rules", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					action: "toggle-rule",
					basePath: BASE_PATH,
					pattern,
				}),
			});
			const result = await res.json();
			if (result.success) {
				await loadData();
			}
		} catch (err) {
			console.error("Failed to toggle rule:", err);
		} finally {
			setActionInProgress(null);
		}
	};

	const filteredRules =
		data?.rules.filter((rule) => {
			if (rulesFilter === "enabled") return rule.enabled;
			if (rulesFilter === "disabled") return !rule.enabled;
			return true;
		}) || [];

	if (loading) {
		return (
			<main className="container mx-auto px-4 py-8">
				<h1 className="text-3xl font-bold mb-6">Learned Rules</h1>
				<p className="text-neutral-600">Loading learned rules data...</p>
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
				<h1 className="text-3xl font-bold">Learned Rules</h1>
			</div>
			<p className="text-neutral-600 mb-8">
				View the learned folder structure, routing rules, and detected domain.
				Learned rules take priority over built-in taxonomy.
			</p>

			{error && (
				<div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
					{error}
				</div>
			)}

			{/* Status Overview */}
			<div className="bg-white rounded-lg border border-neutral-200 p-6 mb-6">
				<div className="flex items-center justify-between mb-4">
					<h2 className="text-xl font-semibold">Status</h2>
					<button
						onClick={handleRescan}
						disabled={actionInProgress !== null}
						className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
							actionInProgress !== null
								? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
								: "bg-blue-600 text-white hover:bg-blue-700"
						}`}
					>
						{actionInProgress === "rescan" ? "Scanning..." : "Re-scan Structure"}
					</button>
				</div>

				{actionResult && (
					<div
						className={`mb-4 p-3 rounded-lg border ${
							actionResult.success
								? "bg-green-50 border-green-200 text-green-700"
								: "bg-red-50 border-red-200 text-red-700"
						}`}
					>
						{actionResult.message}
					</div>
				)}

				<div className="grid grid-cols-2 md:grid-cols-4 gap-4">
					<div className="bg-neutral-50 rounded p-4">
						<div className="text-xs text-neutral-500 mb-1">Status</div>
						<div className="flex items-center gap-2">
							<span
								className={`w-2 h-2 rounded-full ${
									data?.status?.active ? "bg-green-500" : "bg-neutral-400"
								}`}
							/>
							<span className="font-semibold">
								{data?.status?.active ? "Active" : "Inactive"}
							</span>
						</div>
					</div>
					<div className="bg-neutral-50 rounded p-4">
						<div className="text-xs text-neutral-500 mb-1">Total Rules</div>
						<div className="text-2xl font-bold">
							{data?.status?.rule_count ?? 0}
						</div>
					</div>
					<div className="bg-neutral-50 rounded p-4">
						<div className="text-xs text-neutral-500 mb-1">Enabled Rules</div>
						<div className="text-2xl font-bold text-green-700">
							{data?.status?.enabled_rule_count ?? 0}
						</div>
					</div>
					<div className="bg-neutral-50 rounded p-4">
						<div className="text-xs text-neutral-500 mb-1">Last Scan</div>
						<div className="text-sm font-medium">
							{data?.status?.last_scan_date
								? new Date(data.status.last_scan_date).toLocaleString()
								: "Never"}
						</div>
					</div>
				</div>
			</div>

			{/* Strategy Description */}
			{data?.structure?.strategy_description && (
				<div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
					<h2 className="text-lg font-semibold text-blue-900 mb-2">
						Organizational Strategy
					</h2>
					<p className="text-blue-800">{data.structure.strategy_description}</p>
					{data.structure.model_used && (
						<p className="text-xs text-blue-600 mt-2">
							Generated by: {data.structure.model_used}
						</p>
					)}
				</div>
			)}

			{/* Domain Context */}
			{data?.domainContext && (
				<div className="bg-white rounded-lg border border-neutral-200 p-6 mb-6">
					<h2 className="text-xl font-semibold mb-4">Detected Domain</h2>
					<div className="flex items-center gap-4 mb-4">
						<span className="px-3 py-1.5 bg-purple-100 text-purple-800 rounded-lg font-medium capitalize">
							{data.domainContext.detected_domain.replace("_", " ")}
						</span>
						<span
							className={`px-2 py-1 rounded text-sm ${
								CONFIDENCE_COLORS[
									getConfidenceLevel(data.domainContext.confidence)
								]
							}`}
						>
							{(data.domainContext.confidence * 100).toFixed(0)}% confidence
						</span>
						{data.domainContext.model_used &&
							data.domainContext.model_used !== "keyword_fallback" && (
								<span className="text-xs text-neutral-500">
									Model: {data.domainContext.model_used}
								</span>
							)}
						{data.domainContext.model_used === "keyword_fallback" && (
							<span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs">
								keyword fallback
							</span>
						)}
					</div>
					{data.domainContext.evidence.length > 0 && (
						<div>
							<h3 className="text-sm font-medium text-neutral-700 mb-2">
								Evidence
							</h3>
							<ul className="list-disc list-inside text-sm text-neutral-600 space-y-1">
								{data.domainContext.evidence.map((item, idx) => (
									<li key={idx}>{item}</li>
								))}
							</ul>
						</div>
					)}
				</div>
			)}

			{/* Folder Structure Tree */}
			<div className="bg-white rounded-lg border border-neutral-200 p-6 mb-6">
				<div className="flex items-center justify-between mb-4">
					<div>
						<h2 className="text-xl font-semibold">Learned Structure</h2>
						{data?.structure && (
							<p className="text-sm text-neutral-500">
								{data.structure.total_folders} folders,{" "}
								{data.structure.total_files} files,{" "}
								{formatBytes(data.structure.total_size_bytes)}
							</p>
						)}
					</div>
				</div>
				<div className="max-h-96 overflow-y-auto">
					<FolderTree folders={data?.structure?.folders || []} maxDepth={3} />
				</div>
			</div>

			{/* Routing Rules */}
			<div className="bg-white rounded-lg border border-neutral-200 p-6">
				<div className="flex items-center justify-between mb-4">
					<h2 className="text-xl font-semibold">Routing Rules</h2>
					<div className="flex items-center gap-2">
						<select
							value={rulesFilter}
							onChange={(e) =>
								setRulesFilter(e.target.value as "all" | "enabled" | "disabled")
							}
							className="px-3 py-1.5 border border-neutral-300 rounded text-sm"
						>
							<option value="all">All Rules</option>
							<option value="enabled">Enabled Only</option>
							<option value="disabled">Disabled Only</option>
						</select>
					</div>
				</div>

				{filteredRules.length === 0 ? (
					<div className="text-neutral-500 text-sm p-4 bg-neutral-50 rounded">
						{data?.rules?.length === 0
							? "No routing rules learned yet. Run a structure scan to generate rules."
							: "No rules match the current filter."}
					</div>
				) : (
					<div className="space-y-2">
						{filteredRules.map((rule) => (
							<div
								key={rule.pattern}
								className={`bg-neutral-50 rounded-lg border p-4 ${
									rule.enabled
										? "border-neutral-200"
										: "border-neutral-300 opacity-60"
								}`}
							>
								<div className="flex items-center justify-between mb-2">
									<div className="flex items-center gap-2">
										<code className="px-2 py-1 bg-neutral-200 rounded text-sm font-mono">
											{rule.pattern}
										</code>
										<span className="px-2 py-0.5 bg-neutral-200 text-neutral-700 rounded text-xs">
											{rule.pattern_type}
										</span>
										<span
											className={`px-2 py-0.5 rounded text-xs ${
												CONFIDENCE_COLORS[getConfidenceLevel(rule.confidence)]
											}`}
										>
											{(rule.confidence * 100).toFixed(0)}%
										</span>
										{rule.hit_count > 0 && (
											<span className="text-xs text-neutral-500">
												{rule.hit_count} hits
											</span>
										)}
									</div>
									<button
										onClick={() => handleToggleRule(rule.pattern)}
										disabled={
											actionInProgress === `toggle:${rule.pattern}` ||
											actionInProgress === "rescan"
										}
										className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
											rule.enabled
												? "bg-neutral-200 text-neutral-700 hover:bg-neutral-300"
												: "bg-green-100 text-green-700 hover:bg-green-200"
										}`}
									>
										{actionInProgress === `toggle:${rule.pattern}`
											? "..."
											: rule.enabled
												? "Disable"
												: "Enable"}
									</button>
								</div>
								<div className="text-sm text-neutral-600 mb-1">
									<span className="text-neutral-500">Destination:</span>{" "}
									<span className="font-mono">{rule.destination}</span>
								</div>
								{rule.reasoning && (
									<div className="text-sm text-neutral-600">
										<span className="text-neutral-500">Reasoning:</span>{" "}
										{rule.reasoning}
									</div>
								)}
								{rule.source_folder && (
									<div className="text-xs text-neutral-500 mt-1">
										Source: {rule.source_folder}
									</div>
								)}
							</div>
						))}
					</div>
				)}
			</div>
		</main>
	);
}
