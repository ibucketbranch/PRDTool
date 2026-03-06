"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";

interface ModelStats {
	model: string;
	tier: string;
	total_calls: number;
	avg_duration_ms: number;
	calls_today: number;
}

interface LLMStatusResponse {
	status: "operational" | "degraded" | "offline";
	ollama_available: boolean;
	loaded_models: string[];
	total_classifications_today: number;
	keyword_fallback_count_today: number;
	model_stats: ModelStats[];
	config: {
		fast_model: string;
		smart_model: string;
		cloud_model: string | null;
		cloud_enabled: boolean;
		escalation_threshold: number;
	};
	health_checked_at: string;
	error?: string;
}

interface ModelInfo {
	name: string;
	tier: string;
	tier_source: string;
	size_display: string;
	is_available: boolean;
	is_configured: boolean;
	parameter_size: string;
	quantization: string;
	family: string;
	modified_at: string;
}

interface LLMModelsResponse {
	models: ModelInfo[];
	configured_models: {
		fast: string;
		smart: string;
		cloud: string | null;
	};
	ollama_available: boolean;
	error?: string;
}

const STATUS_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
	operational: { bg: "bg-green-100", text: "text-green-800", dot: "bg-green-500" },
	degraded: { bg: "bg-yellow-100", text: "text-yellow-800", dot: "bg-yellow-500" },
	offline: { bg: "bg-red-100", text: "text-red-800", dot: "bg-red-500" },
};

const TIER_COLORS: Record<string, string> = {
	fast: "bg-blue-100 text-blue-800",
	smart: "bg-purple-100 text-purple-800",
	cloud: "bg-orange-100 text-orange-800",
	unknown: "bg-neutral-100 text-neutral-600",
};

export default function ModelPerformancePage() {
	const [status, setStatus] = useState<LLMStatusResponse | null>(null);
	const [models, setModels] = useState<LLMModelsResponse | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const loadData = useCallback(async () => {
		try {
			setError(null);
			const [statusRes, modelsRes] = await Promise.all([
				fetch("/api/llm/status"),
				fetch("/api/llm/models"),
			]);

			if (!statusRes.ok && statusRes.status !== 503) {
				throw new Error(`Status API returned ${statusRes.status}`);
			}
			if (!modelsRes.ok) {
				throw new Error(`Models API returned ${modelsRes.status}`);
			}

			const [statusData, modelsData] = await Promise.all([
				statusRes.json(),
				modelsRes.json(),
			]);

			setStatus(statusData);
			setModels(modelsData);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load LLM status");
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		loadData();
		const interval = setInterval(loadData, 30_000);
		return () => clearInterval(interval);
	}, [loadData]);

	// Calculate additional metrics
	const totalCalls = status?.model_stats?.reduce((sum, m) => sum + m.total_calls, 0) || 0;
	const avgResponseTime =
		status?.model_stats && status.model_stats.length > 0
			? Math.round(
					status.model_stats.reduce((sum, m) => sum + m.avg_duration_ms * m.total_calls, 0) /
						totalCalls
				)
			: 0;
	const escalationRate =
		status?.keyword_fallback_count_today && status?.total_classifications_today
			? (
					(status.keyword_fallback_count_today / status.total_classifications_today) *
					100
				).toFixed(1)
			: "0";

	// Group model stats by tier
	const tierSummary: Record<string, { calls: number; avgDuration: number; models: string[] }> = {};
	if (status?.model_stats) {
		for (const stat of status.model_stats) {
			const tier = stat.tier || "unknown";
			if (!tierSummary[tier]) {
				tierSummary[tier] = { calls: 0, avgDuration: 0, models: [] };
			}
			tierSummary[tier].calls += stat.total_calls;
			tierSummary[tier].models.push(stat.model);
		}
		// Calculate weighted average duration per tier
		for (const tier of Object.keys(tierSummary)) {
			const tierStats = status.model_stats.filter((m) => m.tier === tier);
			const totalCalls = tierStats.reduce((sum, m) => sum + m.total_calls, 0);
			if (totalCalls > 0) {
				tierSummary[tier].avgDuration = Math.round(
					tierStats.reduce((sum, m) => sum + m.avg_duration_ms * m.total_calls, 0) / totalCalls
				);
			}
		}
	}

	if (loading) {
		return (
			<main className="container mx-auto px-4 py-8">
				<div className="mb-6">
					<Link
						href="/"
						className="text-sm text-blue-600 hover:text-blue-800 hover:underline mb-2 inline-block"
					>
						&larr; Back to Dashboard
					</Link>
					<h1 className="text-3xl font-bold">Model Performance</h1>
				</div>
				<p className="text-neutral-600">Loading LLM status...</p>
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
				<h1 className="text-3xl font-bold">Model Performance</h1>
			</div>
			<p className="text-neutral-600 mb-8">
				LLM health metrics, model statistics, and routing configuration.
			</p>

			{error && (
				<div className="bg-red-50 border border-red-200 rounded-lg p-6 mb-6">
					<p className="text-red-700">{error}</p>
				</div>
			)}

			{/* Health Status Header */}
			<div className="bg-white rounded-lg border border-neutral-200 p-6 mb-6">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-4">
						<div
							className={`flex items-center gap-2 px-4 py-2 rounded-full ${
								STATUS_COLORS[status?.status || "offline"]?.bg
							} ${STATUS_COLORS[status?.status || "offline"]?.text}`}
						>
							<span
								className={`w-3 h-3 rounded-full ${
									STATUS_COLORS[status?.status || "offline"]?.dot
								}`}
							/>
							<span className="font-medium capitalize">{status?.status || "Unknown"}</span>
						</div>
						{status?.ollama_available ? (
							<span className="text-sm text-green-600 font-medium">Ollama Connected</span>
						) : (
							<span className="text-sm text-red-600 font-medium">Ollama Offline</span>
						)}
					</div>
					<div className="text-sm text-neutral-500">
						Last check:{" "}
						{status?.health_checked_at
							? new Date(status.health_checked_at).toLocaleString()
							: "N/A"}
						<button
							onClick={loadData}
							className="ml-4 px-3 py-1 rounded text-sm font-medium text-neutral-600 hover:bg-neutral-100 transition-colors"
						>
							Refresh
						</button>
					</div>
				</div>
				{status?.error && (
					<div className="mt-3 text-sm text-red-600">
						<strong>Error:</strong> {status.error}
					</div>
				)}
			</div>

			{/* Key Metrics Grid */}
			<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
				<div className="bg-white rounded-lg border border-neutral-200 p-4">
					<div className="text-xs text-neutral-500 uppercase tracking-wide">
						Classifications Today
					</div>
					<div className="text-2xl font-bold mt-1">
						{status?.total_classifications_today ?? 0}
					</div>
				</div>
				<div className="bg-white rounded-lg border border-neutral-200 p-4">
					<div className="text-xs text-neutral-500 uppercase tracking-wide">
						Total LLM Calls
					</div>
					<div className="text-2xl font-bold mt-1">{totalCalls}</div>
				</div>
				<div className="bg-white rounded-lg border border-neutral-200 p-4">
					<div className="text-xs text-neutral-500 uppercase tracking-wide">
						Avg Response Time
					</div>
					<div className="text-2xl font-bold mt-1">
						{avgResponseTime > 0 ? `${(avgResponseTime / 1000).toFixed(1)}s` : "—"}
					</div>
				</div>
				<div className="bg-white rounded-lg border border-neutral-200 p-4">
					<div className="text-xs text-neutral-500 uppercase tracking-wide">
						Keyword Fallbacks
					</div>
					<div className="text-2xl font-bold mt-1">
						{status?.keyword_fallback_count_today ?? 0}
					</div>
				</div>
				<div className="bg-white rounded-lg border border-neutral-200 p-4">
					<div className="text-xs text-neutral-500 uppercase tracking-wide">
						Fallback Rate
					</div>
					<div className="text-2xl font-bold mt-1">{escalationRate}%</div>
				</div>
				<div className="bg-white rounded-lg border border-neutral-200 p-4">
					<div className="text-xs text-neutral-500 uppercase tracking-wide">
						Models Available
					</div>
					<div className="text-2xl font-bold mt-1">
						{status?.loaded_models?.length ?? 0}
					</div>
				</div>
			</div>

			{/* Tier Summary */}
			<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
				{["fast", "smart", "cloud"].map((tier) => {
					const summary = tierSummary[tier];
					const configuredModel =
						tier === "fast"
							? status?.config?.fast_model
							: tier === "smart"
								? status?.config?.smart_model
								: status?.config?.cloud_model;
					const isAvailable =
						tier === "cloud"
							? status?.config?.cloud_enabled
							: status?.loaded_models?.some((m) => m === configuredModel);

					return (
						<div
							key={tier}
							className="bg-white rounded-lg border border-neutral-200 p-6"
						>
							<div className="flex items-center justify-between mb-4">
								<div className="flex items-center gap-2">
									<span
										className={`px-2 py-1 rounded text-xs font-medium uppercase ${TIER_COLORS[tier]}`}
									>
										T{tier === "fast" ? "1" : tier === "smart" ? "2" : "3"} {tier}
									</span>
									<span
										className={`w-2 h-2 rounded-full ${
											isAvailable ? "bg-green-500" : "bg-neutral-300"
										}`}
									/>
								</div>
							</div>
							<div className="space-y-2">
								<div>
									<div className="text-xs text-neutral-500">Configured Model</div>
									<div className="text-sm font-medium truncate">
										{configuredModel || (tier === "cloud" ? "Disabled" : "Not configured")}
									</div>
								</div>
								<div className="grid grid-cols-2 gap-4">
									<div>
										<div className="text-xs text-neutral-500">Total Calls</div>
										<div className="text-lg font-bold">{summary?.calls ?? 0}</div>
									</div>
									<div>
										<div className="text-xs text-neutral-500">Avg Duration</div>
										<div className="text-lg font-bold">
											{summary?.avgDuration
												? `${(summary.avgDuration / 1000).toFixed(1)}s`
												: "—"}
										</div>
									</div>
								</div>
							</div>
						</div>
					);
				})}
			</div>

			{/* Per-Model Breakdown Table */}
			<div className="bg-white rounded-lg border border-neutral-200 p-6 mb-6">
				<h2 className="text-xl font-semibold mb-4">Model Statistics</h2>
				{status?.model_stats && status.model_stats.length > 0 ? (
					<div className="overflow-x-auto">
						<table className="w-full text-sm">
							<thead>
								<tr className="border-b border-neutral-200">
									<th className="text-left py-3 px-4 font-medium text-neutral-600">
										Model
									</th>
									<th className="text-left py-3 px-4 font-medium text-neutral-600">
										Tier
									</th>
									<th className="text-right py-3 px-4 font-medium text-neutral-600">
										Total Calls
									</th>
									<th className="text-right py-3 px-4 font-medium text-neutral-600">
										Calls Today
									</th>
									<th className="text-right py-3 px-4 font-medium text-neutral-600">
										Avg Duration
									</th>
								</tr>
							</thead>
							<tbody>
								{status.model_stats.map((stat) => (
									<tr
										key={stat.model}
										className="border-b border-neutral-100 hover:bg-neutral-50"
									>
										<td className="py-3 px-4 font-mono text-sm">{stat.model}</td>
										<td className="py-3 px-4">
											<span
												className={`px-2 py-0.5 rounded text-xs font-medium ${TIER_COLORS[stat.tier] || TIER_COLORS.unknown}`}
											>
												{stat.tier}
											</span>
										</td>
										<td className="py-3 px-4 text-right font-medium">
											{stat.total_calls.toLocaleString()}
										</td>
										<td className="py-3 px-4 text-right">{stat.calls_today}</td>
										<td className="py-3 px-4 text-right">
											{stat.avg_duration_ms > 0
												? `${(stat.avg_duration_ms / 1000).toFixed(2)}s`
												: "—"}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				) : (
					<div className="bg-neutral-50 rounded-lg p-6 text-center">
						<p className="text-neutral-500">
							No model statistics available. Run some LLM classifications to see data here.
						</p>
					</div>
				)}
			</div>

			{/* Configuration Panel */}
			<div className="bg-white rounded-lg border border-neutral-200 p-6 mb-6">
				<h2 className="text-xl font-semibold mb-4">Configuration</h2>
				<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
					<div className="bg-neutral-50 rounded-lg p-4">
						<div className="text-xs text-neutral-500 uppercase tracking-wide">
							Fast Model (T1)
						</div>
						<div className="text-sm font-mono mt-1 truncate">
							{status?.config?.fast_model || "Not configured"}
						</div>
					</div>
					<div className="bg-neutral-50 rounded-lg p-4">
						<div className="text-xs text-neutral-500 uppercase tracking-wide">
							Smart Model (T2)
						</div>
						<div className="text-sm font-mono mt-1 truncate">
							{status?.config?.smart_model || "Not configured"}
						</div>
					</div>
					<div className="bg-neutral-50 rounded-lg p-4">
						<div className="text-xs text-neutral-500 uppercase tracking-wide">
							Cloud Model (T3)
						</div>
						<div className="text-sm font-mono mt-1 truncate">
							{status?.config?.cloud_enabled
								? status?.config?.cloud_model || "Enabled (no model set)"
								: "Disabled"}
						</div>
					</div>
					<div className="bg-neutral-50 rounded-lg p-4">
						<div className="text-xs text-neutral-500 uppercase tracking-wide">
							Escalation Threshold
						</div>
						<div className="text-sm font-medium mt-1">
							{status?.config?.escalation_threshold
								? `${(status.config.escalation_threshold * 100).toFixed(0)}%`
								: "75%"}
						</div>
					</div>
				</div>
			</div>

			{/* Loaded Models Panel */}
			<div className="bg-white rounded-lg border border-neutral-200 p-6">
				<h2 className="text-xl font-semibold mb-4">Loaded Models (Ollama)</h2>
				{models?.models && models.models.length > 0 ? (
					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
						{models.models.map((model) => (
							<div
								key={model.name}
								className={`rounded-lg border p-4 ${
									model.is_available
										? "border-green-200 bg-green-50"
										: "border-neutral-200 bg-neutral-50"
								}`}
							>
								<div className="flex items-center justify-between mb-2">
									<span className="font-medium truncate">{model.name}</span>
									<span
										className={`w-2 h-2 rounded-full ${
											model.is_available ? "bg-green-500" : "bg-neutral-300"
										}`}
									/>
								</div>
								<div className="space-y-1 text-xs text-neutral-600">
									<div className="flex items-center gap-2">
										<span
											className={`px-2 py-0.5 rounded font-medium ${TIER_COLORS[model.tier] || TIER_COLORS.unknown}`}
										>
											{model.tier}
										</span>
										{model.is_configured && (
											<span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded font-medium">
												configured
											</span>
										)}
									</div>
									<div>Size: {model.size_display}</div>
									{model.parameter_size && <div>Parameters: {model.parameter_size}</div>}
									{model.quantization && <div>Quantization: {model.quantization}</div>}
									{model.family && <div>Family: {model.family}</div>}
								</div>
							</div>
						))}
					</div>
				) : models?.ollama_available === false ? (
					<div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
						<p className="text-red-700">
							Ollama is not available. Start Ollama to see loaded models.
						</p>
					</div>
				) : (
					<div className="bg-neutral-50 rounded-lg p-6 text-center">
						<p className="text-neutral-500">
							No models loaded. Pull a model with{" "}
							<code className="bg-neutral-200 px-1 rounded">ollama pull llama3.1:8b</code>
						</p>
					</div>
				)}
			</div>
		</main>
	);
}
