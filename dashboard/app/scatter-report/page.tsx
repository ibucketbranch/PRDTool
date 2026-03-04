"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import type {
	ScatterReportResponse,
	ScatterViolationGroup,
	ScatterViolation,
} from "../api/scatter-report/route";

const BASE_PATH =
	process.env.NEXT_PUBLIC_ORGANIZER_BASE_PATH ||
	"/Users/michaelvalderrama/Websites/PRDTool";

const CONFIDENCE_COLORS: Record<string, string> = {
	high: "bg-green-100 text-green-800",
	medium: "bg-yellow-100 text-yellow-800",
	low: "bg-red-100 text-red-800",
};

function getConfidenceLevel(confidence: number): "high" | "medium" | "low" {
	if (confidence >= 0.95) return "high";
	if (confidence >= 0.75) return "medium";
	return "low";
}

export default function ScatterReportPage() {
	const [report, setReport] = useState<ScatterReportResponse | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [scanning, setScanning] = useState(false);
	const [selectedViolations, setSelectedViolations] = useState<Set<string>>(
		new Set()
	);
	const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

	const loadReport = useCallback(async () => {
		try {
			setError(null);
			const res = await fetch(
				`/api/scatter-report?basePath=${encodeURIComponent(BASE_PATH)}`
			);
			if (!res.ok) {
				throw new Error(`HTTP error: ${res.status}`);
			}
			const data: ScatterReportResponse = await res.json();
			if (data.error) {
				setError(data.error);
			}
			setReport(data);
			// Expand all groups by default
			setExpandedGroups(new Set(data.groups.map((g) => g.rootBin)));
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load report");
		} finally {
			setLoading(false);
		}
	}, []);

	const runScan = async () => {
		setScanning(true);
		setError(null);
		try {
			const res = await fetch(
				`/api/scatter-report?basePath=${encodeURIComponent(BASE_PATH)}&scan=true`
			);
			if (!res.ok) {
				throw new Error(`HTTP error: ${res.status}`);
			}
			const data: ScatterReportResponse = await res.json();
			if (data.error) {
				setError(data.error);
			}
			setReport(data);
			setExpandedGroups(new Set(data.groups.map((g) => g.rootBin)));
		} catch (err) {
			setError(err instanceof Error ? err.message : "Scan failed");
		} finally {
			setScanning(false);
		}
	};

	useEffect(() => {
		loadReport();
	}, [loadReport]);

	const toggleGroup = (rootBin: string) => {
		setExpandedGroups((prev) => {
			const next = new Set(prev);
			if (next.has(rootBin)) {
				next.delete(rootBin);
			} else {
				next.add(rootBin);
			}
			return next;
		});
	};

	const toggleViolation = (filePath: string) => {
		setSelectedViolations((prev) => {
			const next = new Set(prev);
			if (next.has(filePath)) {
				next.delete(filePath);
			} else {
				next.add(filePath);
			}
			return next;
		});
	};

	const toggleAllInGroup = (group: ScatterViolationGroup) => {
		const groupPaths = group.violations.map((v) => v.filePath);
		const allSelected = groupPaths.every((p) => selectedViolations.has(p));

		setSelectedViolations((prev) => {
			const next = new Set(prev);
			if (allSelected) {
				groupPaths.forEach((p) => next.delete(p));
			} else {
				groupPaths.forEach((p) => next.add(p));
			}
			return next;
		});
	};

	const selectHighConfidence = () => {
		if (!report) return;
		const highConfPaths = report.groups
			.flatMap((g) => g.violations)
			.filter((v) => v.confidence >= 0.95)
			.map((v) => v.filePath);
		setSelectedViolations(new Set(highConfPaths));
	};

	if (loading) {
		return (
			<main className="container mx-auto px-4 py-8">
				<h1 className="text-3xl font-bold mb-6">Scatter Report</h1>
				<div className="bg-neutral-50 rounded-lg border border-neutral-200 p-6">
					<p className="text-neutral-500">Loading scatter report...</p>
				</div>
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
				<h1 className="text-3xl font-bold">Scatter Report</h1>
			</div>
			<p className="text-neutral-600 mb-8">
				Files that exist outside their correct taxonomy bin. Review violations
				and approve corrections.
			</p>

			{/* Error Display */}
			{error && (
				<div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
					<p className="text-red-700 text-sm">{error}</p>
					<button
						onClick={loadReport}
						className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
					>
						Try again
					</button>
				</div>
			)}

			{/* Stats Section */}
			{report && (
				<div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
					<div className="bg-white rounded-lg border border-neutral-200 p-4">
						<div className="text-xs text-neutral-500 uppercase tracking-wide">
							Total Violations
						</div>
						<div className="text-2xl font-bold text-red-600">
							{report.totalViolations}
						</div>
					</div>
					<div className="bg-white rounded-lg border border-neutral-200 p-4">
						<div className="text-xs text-neutral-500 uppercase tracking-wide">
							Files Scanned
						</div>
						<div className="text-2xl font-bold">
							{report.filesScanned || "—"}
						</div>
					</div>
					<div className="bg-white rounded-lg border border-neutral-200 p-4">
						<div className="text-xs text-neutral-500 uppercase tracking-wide">
							Files in Correct Bin
						</div>
						<div className="text-2xl font-bold text-green-600">
							{report.filesInCorrectBin || "—"}
						</div>
					</div>
					<div className="bg-white rounded-lg border border-neutral-200 p-4">
						<div className="text-xs text-neutral-500 uppercase tracking-wide">
							Source
						</div>
						<div className="flex items-center gap-2">
							<span className="text-lg font-medium capitalize">
								{report.source}
							</span>
							{report.usedKeywordFallback && (
								<span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs">
									Keyword Fallback
								</span>
							)}
						</div>
					</div>
				</div>
			)}

			{/* Model Info */}
			{report && report.modelUsed && (
				<div className="bg-neutral-50 rounded-lg border border-neutral-200 p-4 mb-6">
					<div className="flex items-center gap-4 text-sm">
						<span className="text-neutral-500">Model Used:</span>
						<span className="font-medium font-mono">{report.modelUsed}</span>
						{report.scannedDirectory && (
							<>
								<span className="text-neutral-300">|</span>
								<span className="text-neutral-500">Directory:</span>
								<span className="font-mono text-xs truncate max-w-md">
									{report.scannedDirectory}
								</span>
							</>
						)}
					</div>
				</div>
			)}

			{/* Controls */}
			<div className="flex flex-wrap items-center gap-3 mb-6">
				<button
					onClick={loadReport}
					disabled={loading}
					className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
						loading
							? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
							: "bg-neutral-800 text-white hover:bg-neutral-900"
					}`}
				>
					{loading ? "Loading..." : "Refresh from Queue"}
				</button>
				<button
					onClick={runScan}
					disabled={scanning}
					className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
						scanning
							? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
							: "bg-blue-600 text-white hover:bg-blue-700"
					}`}
				>
					{scanning ? "Scanning..." : "Run New Scan"}
				</button>
				{report && report.totalViolations > 0 && (
					<>
						<div className="h-6 w-px bg-neutral-200" />
						<button
							onClick={selectHighConfidence}
							className="px-4 py-2 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 transition-colors"
						>
							Select High Confidence (&gt;0.95)
						</button>
						{selectedViolations.size > 0 && (
							<span className="text-sm text-neutral-500">
								{selectedViolations.size} selected
							</span>
						)}
					</>
				)}
			</div>

			{/* Violations List */}
			{report && report.groups.length === 0 ? (
				<div className="bg-neutral-50 rounded-lg border border-neutral-200 p-8 text-center">
					<p className="text-neutral-500 text-lg mb-2">No violations found</p>
					<p className="text-neutral-400 text-sm">
						All files appear to be in their correct taxonomy bins.
					</p>
				</div>
			) : (
				report &&
				report.groups.map((group) => (
					<ViolationGroup
						key={group.rootBin}
						group={group}
						expanded={expandedGroups.has(group.rootBin)}
						selectedViolations={selectedViolations}
						onToggleGroup={() => toggleGroup(group.rootBin)}
						onToggleViolation={toggleViolation}
						onToggleAll={() => toggleAllInGroup(group)}
					/>
				))
			)}
		</main>
	);
}

interface ViolationGroupProps {
	group: ScatterViolationGroup;
	expanded: boolean;
	selectedViolations: Set<string>;
	onToggleGroup: () => void;
	onToggleViolation: (filePath: string) => void;
	onToggleAll: () => void;
}

function ViolationGroup({
	group,
	expanded,
	selectedViolations,
	onToggleGroup,
	onToggleViolation,
	onToggleAll,
}: ViolationGroupProps) {
	const allSelected = group.violations.every((v) =>
		selectedViolations.has(v.filePath)
	);
	const someSelected = group.violations.some((v) =>
		selectedViolations.has(v.filePath)
	);

	return (
		<div className="bg-white rounded-lg border border-neutral-200 mb-4 overflow-hidden">
			{/* Group Header */}
			<div
				className="flex items-center justify-between px-4 py-3 bg-neutral-50 cursor-pointer hover:bg-neutral-100 transition-colors"
				onClick={onToggleGroup}
			>
				<div className="flex items-center gap-3">
					<span className="text-lg">{expanded ? "▼" : "▶"}</span>
					<div>
						<span className="font-semibold">{group.rootBin || "Unknown"}</span>
						<span className="ml-2 px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs font-medium">
							{group.totalViolations} violation
							{group.totalViolations !== 1 ? "s" : ""}
						</span>
					</div>
				</div>
				<button
					onClick={(e) => {
						e.stopPropagation();
						onToggleAll();
					}}
					className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
						allSelected
							? "bg-blue-600 text-white"
							: "bg-neutral-200 text-neutral-700 hover:bg-neutral-300"
					}`}
				>
					{allSelected ? "Deselect All" : someSelected ? "Select All" : "Select All"}
				</button>
			</div>

			{/* Violations List */}
			{expanded && (
				<div className="divide-y divide-neutral-100">
					{group.violations.map((violation) => (
						<ViolationRow
							key={violation.filePath}
							violation={violation}
							selected={selectedViolations.has(violation.filePath)}
							onToggle={() => onToggleViolation(violation.filePath)}
						/>
					))}
				</div>
			)}
		</div>
	);
}

interface ViolationRowProps {
	violation: ScatterViolation;
	selected: boolean;
	onToggle: () => void;
}

function ViolationRow({ violation, selected, onToggle }: ViolationRowProps) {
	const confidenceLevel = getConfidenceLevel(violation.confidence);
	const confidencePercent = Math.round(violation.confidence * 100);

	return (
		<div
			className={`px-4 py-3 ${selected ? "bg-blue-50" : "hover:bg-neutral-50"}`}
		>
			<div className="flex items-start gap-3">
				{/* Checkbox */}
				<input
					type="checkbox"
					checked={selected}
					onChange={onToggle}
					className="mt-1 h-4 w-4 rounded border-neutral-300 text-blue-600 focus:ring-blue-500"
				/>

				{/* Content */}
				<div className="flex-1 min-w-0">
					{/* File name and confidence */}
					<div className="flex items-center gap-2 flex-wrap">
						<span className="font-medium truncate">{violation.fileName}</span>
						<span
							className={`px-2 py-0.5 rounded text-xs font-medium ${CONFIDENCE_COLORS[confidenceLevel]}`}
						>
							{confidencePercent}%
						</span>
						{violation.usedKeywordFallback && (
							<span className="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs">
								Keyword
							</span>
						)}
						{violation.modelUsed && !violation.usedKeywordFallback && (
							<span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs font-mono">
								{violation.modelUsed}
							</span>
						)}
					</div>

					{/* Path info */}
					<div className="mt-1 text-sm text-neutral-500">
						<span className="text-red-600">{violation.currentBin}</span>
						<span className="mx-2">→</span>
						<span className="text-green-600">{violation.expectedBin}</span>
						{violation.suggestedSubpath && (
							<span className="text-neutral-400">
								/{violation.suggestedSubpath}
							</span>
						)}
					</div>

					{/* Full file path */}
					<div className="mt-1 text-xs font-mono text-neutral-400 truncate">
						{violation.filePath}
					</div>

					{/* Reason */}
					{violation.reason && (
						<div className="mt-2 text-sm text-neutral-600 bg-neutral-50 rounded p-2">
							<span className="text-neutral-500">Reason:</span>{" "}
							{violation.reason}
						</div>
					)}
				</div>
			</div>
		</div>
	);
}
