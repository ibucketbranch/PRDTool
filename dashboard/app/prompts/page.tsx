"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";

interface PromptMetadata {
	name: string;
	version: string;
	lastModified: string;
	description: string;
}

interface PromptInfo {
	name: string;
	metadata: PromptMetadata;
	template: string;
	variables: string[];
	sourcePath: string;
	fileModified: string;
}

interface PromptListResponse {
	prompts: PromptInfo[];
	promptsDir: string;
	timestamp: string;
	error?: string;
}

interface LLMResponse {
	text: string;
	model: string;
	durationMs: number;
	tokensEval: number;
}

interface PromptTestResponse {
	success: boolean;
	generatedPrompt: string;
	llmResponse?: LLMResponse;
	error?: string;
}

interface PromptUpdateResponse {
	success: boolean;
	prompt?: PromptInfo;
	error?: string;
}

interface LLMModel {
	name: string;
	tier: string;
	available: boolean;
}

interface LLMModelsResponse {
	models: LLMModel[];
	error?: string;
}

export default function PromptsPage() {
	const [prompts, setPrompts] = useState<PromptInfo[]>([]);
	const [promptsDir, setPromptsDir] = useState<string>("");
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	// Selected prompt for editing/testing
	const [selectedPrompt, setSelectedPrompt] = useState<PromptInfo | null>(null);
	const [editedTemplate, setEditedTemplate] = useState<string>("");
	const [editedVersion, setEditedVersion] = useState<string>("");
	const [editedDescription, setEditedDescription] = useState<string>("");
	const [hasChanges, setHasChanges] = useState(false);

	// Testing state
	const [testVariables, setTestVariables] = useState<Record<string, string>>({});
	const [selectedModel, setSelectedModel] = useState<string>("");
	const [availableModels, setAvailableModels] = useState<LLMModel[]>([]);
	const [testResult, setTestResult] = useState<PromptTestResponse | null>(null);
	const [testing, setTesting] = useState(false);

	// Saving state
	const [saving, setSaving] = useState(false);
	const [saveResult, setSaveResult] = useState<{ success: boolean; message: string } | null>(null);

	const loadPrompts = useCallback(async () => {
		try {
			setError(null);
			const res = await fetch("/api/prompts");
			const data: PromptListResponse = await res.json();

			if (data.error) {
				setError(data.error);
			}

			setPrompts(data.prompts || []);
			setPromptsDir(data.promptsDir || "");
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load prompts");
		} finally {
			setLoading(false);
		}
	}, []);

	const loadModels = useCallback(async () => {
		try {
			const res = await fetch("/api/llm/models");
			const data: LLMModelsResponse = await res.json();
			if (data.models) {
				setAvailableModels(data.models.filter((m) => m.available));
			}
		} catch (err) {
			console.error("Failed to load models:", err);
		}
	}, []);

	useEffect(() => {
		loadPrompts();
		loadModels();
	}, [loadPrompts, loadModels]);

	// Handle prompt selection
	const handleSelectPrompt = (prompt: PromptInfo) => {
		setSelectedPrompt(prompt);
		setEditedTemplate(prompt.template);
		setEditedVersion(prompt.metadata.version);
		setEditedDescription(prompt.metadata.description);
		setHasChanges(false);
		setTestResult(null);
		setSaveResult(null);

		// Initialize test variables
		const initialVars: Record<string, string> = {};
		for (const v of prompt.variables) {
			initialVars[v] = "";
		}
		setTestVariables(initialVars);
	};

	// Track changes
	useEffect(() => {
		if (!selectedPrompt) return;
		const templateChanged = editedTemplate !== selectedPrompt.template;
		const versionChanged = editedVersion !== selectedPrompt.metadata.version;
		const descriptionChanged = editedDescription !== selectedPrompt.metadata.description;
		setHasChanges(templateChanged || versionChanged || descriptionChanged);
	}, [editedTemplate, editedVersion, editedDescription, selectedPrompt]);

	// Handle test prompt
	const handleTestPrompt = async (runWithLLM: boolean) => {
		if (!selectedPrompt) return;

		setTesting(true);
		setTestResult(null);

		try {
			const res = await fetch("/api/prompts", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					promptName: selectedPrompt.name,
					variables: testVariables,
					model: runWithLLM ? selectedModel : undefined,
					temperature: 0.7,
					maxTokens: 1024,
				}),
			});

			const data: PromptTestResponse = await res.json();
			setTestResult(data);
		} catch (err) {
			setTestResult({
				success: false,
				generatedPrompt: "",
				error: err instanceof Error ? err.message : "Test failed",
			});
		} finally {
			setTesting(false);
		}
	};

	// Handle save prompt
	const handleSavePrompt = async () => {
		if (!selectedPrompt) return;

		setSaving(true);
		setSaveResult(null);

		try {
			const res = await fetch("/api/prompts", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					promptName: selectedPrompt.name,
					template: editedTemplate,
					metadata: {
						version: editedVersion,
						description: editedDescription,
					},
				}),
			});

			const data: PromptUpdateResponse = await res.json();

			if (data.success && data.prompt) {
				setSaveResult({ success: true, message: "Prompt saved successfully" });
				// Update the prompt in the list
				setPrompts((prev) =>
					prev.map((p) => (p.name === data.prompt!.name ? data.prompt! : p))
				);
				setSelectedPrompt(data.prompt);
				setHasChanges(false);
			} else {
				setSaveResult({ success: false, message: data.error || "Failed to save" });
			}
		} catch (err) {
			setSaveResult({
				success: false,
				message: err instanceof Error ? err.message : "Save failed",
			});
		} finally {
			setSaving(false);
		}
	};

	// Handle revert changes
	const handleRevertChanges = () => {
		if (!selectedPrompt) return;
		setEditedTemplate(selectedPrompt.template);
		setEditedVersion(selectedPrompt.metadata.version);
		setEditedDescription(selectedPrompt.metadata.description);
		setHasChanges(false);
		setSaveResult(null);
	};

	if (loading) {
		return (
			<main className="container mx-auto px-4 py-8">
				<h1 className="text-3xl font-bold mb-6">Prompt Management</h1>
				<p className="text-neutral-600">Loading prompts...</p>
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
				<h1 className="text-3xl font-bold">Prompt Management</h1>
			</div>
			<p className="text-neutral-600 mb-4">
				View and edit prompt templates used by the LLM agents. Test prompts against
				sample data and see the responses.
			</p>
			{promptsDir && (
				<p className="text-xs text-neutral-500 mb-6 font-mono">{promptsDir}</p>
			)}

			{error && (
				<div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
					{error}
				</div>
			)}

			<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
				{/* Prompt List */}
				<div className="lg:col-span-1">
					<div className="bg-white rounded-lg border border-neutral-200 p-4">
						<div className="flex items-center justify-between mb-4">
							<h2 className="text-lg font-semibold">Prompts</h2>
							<button
								onClick={loadPrompts}
								className="px-3 py-1.5 rounded text-sm font-medium text-neutral-600 hover:bg-neutral-100 transition-colors"
							>
								Refresh
							</button>
						</div>

						{prompts.length === 0 ? (
							<p className="text-neutral-500 text-sm">No prompts found.</p>
						) : (
							<div className="space-y-2">
								{prompts.map((prompt) => (
									<button
										key={prompt.name}
										onClick={() => handleSelectPrompt(prompt)}
										className={`w-full text-left p-3 rounded-lg border transition-colors ${
											selectedPrompt?.name === prompt.name
												? "border-blue-500 bg-blue-50"
												: "border-neutral-200 hover:bg-neutral-50"
										}`}
									>
										<div className="font-medium text-sm">{prompt.name}</div>
										<div className="text-xs text-neutral-500 mt-1 truncate">
											{prompt.metadata.description || "No description"}
										</div>
										<div className="flex items-center gap-2 mt-2 text-xs text-neutral-400">
											<span>v{prompt.metadata.version}</span>
											<span>|</span>
											<span>{prompt.variables.length} variables</span>
										</div>
									</button>
								))}
							</div>
						)}
					</div>
				</div>

				{/* Prompt Editor and Tester */}
				<div className="lg:col-span-2">
					{!selectedPrompt ? (
						<div className="bg-neutral-50 rounded-lg border border-neutral-200 p-8 text-center">
							<p className="text-neutral-500">
								Select a prompt from the list to view and edit it.
							</p>
						</div>
					) : (
						<div className="space-y-6">
							{/* Metadata Section */}
							<div className="bg-white rounded-lg border border-neutral-200 p-4">
								<h3 className="text-lg font-semibold mb-4">
									{selectedPrompt.name}
								</h3>

								<div className="grid grid-cols-2 gap-4 mb-4">
									<div>
										<label className="block text-sm font-medium text-neutral-700 mb-1">
											Version
										</label>
										<input
											type="text"
											value={editedVersion}
											onChange={(e) => setEditedVersion(e.target.value)}
											className="w-full px-3 py-2 border border-neutral-300 rounded-lg text-sm"
										/>
									</div>
									<div>
										<label className="block text-sm font-medium text-neutral-700 mb-1">
											Last Modified
										</label>
										<input
											type="text"
											value={selectedPrompt.metadata.lastModified}
											disabled
											className="w-full px-3 py-2 border border-neutral-200 rounded-lg text-sm bg-neutral-50 text-neutral-500"
										/>
									</div>
								</div>

								<div className="mb-4">
									<label className="block text-sm font-medium text-neutral-700 mb-1">
										Description
									</label>
									<input
										type="text"
										value={editedDescription}
										onChange={(e) => setEditedDescription(e.target.value)}
										className="w-full px-3 py-2 border border-neutral-300 rounded-lg text-sm"
									/>
								</div>

								<div>
									<label className="block text-sm font-medium text-neutral-700 mb-1">
										Variables
									</label>
									<div className="flex flex-wrap gap-2">
										{selectedPrompt.variables.length === 0 ? (
											<span className="text-neutral-500 text-sm">
												No variables
											</span>
										) : (
											selectedPrompt.variables.map((v) => (
												<span
													key={v}
													className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-mono"
												>
													{`{${v}}`}
												</span>
											))
										)}
									</div>
								</div>
							</div>

							{/* Template Editor */}
							<div className="bg-white rounded-lg border border-neutral-200 p-4">
								<div className="flex items-center justify-between mb-4">
									<h3 className="text-lg font-semibold">Template</h3>
									{hasChanges && (
										<span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs">
											Unsaved changes
										</span>
									)}
								</div>

								<textarea
									value={editedTemplate}
									onChange={(e) => setEditedTemplate(e.target.value)}
									className="w-full h-64 px-3 py-2 border border-neutral-300 rounded-lg text-sm font-mono resize-y"
									placeholder="Enter prompt template..."
								/>

								<div className="flex justify-end gap-3 mt-4">
									{hasChanges && (
										<button
											onClick={handleRevertChanges}
											className="px-4 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-100 rounded-lg transition-colors"
										>
											Revert
										</button>
									)}
									<button
										onClick={handleSavePrompt}
										disabled={!hasChanges || saving}
										className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
											!hasChanges || saving
												? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
												: "bg-blue-600 text-white hover:bg-blue-700"
										}`}
									>
										{saving ? "Saving..." : "Save Changes"}
									</button>
								</div>

								{saveResult && (
									<div
										className={`mt-4 p-3 rounded-lg text-sm ${
											saveResult.success
												? "bg-green-50 text-green-700 border border-green-200"
												: "bg-red-50 text-red-700 border border-red-200"
										}`}
									>
										{saveResult.message}
									</div>
								)}
							</div>

							{/* Test Section */}
							<div className="bg-white rounded-lg border border-neutral-200 p-4">
								<h3 className="text-lg font-semibold mb-4">Test Prompt</h3>

								{/* Variable inputs */}
								{selectedPrompt.variables.length > 0 && (
									<div className="mb-4">
										<label className="block text-sm font-medium text-neutral-700 mb-2">
											Test Variables
										</label>
										<div className="space-y-3">
											{selectedPrompt.variables.map((v) => (
												<div key={v}>
													<label className="block text-xs text-neutral-500 mb-1 font-mono">
														{`{${v}}`}
													</label>
													<textarea
														value={testVariables[v] || ""}
														onChange={(e) =>
															setTestVariables((prev) => ({
																...prev,
																[v]: e.target.value,
															}))
														}
														className="w-full px-3 py-2 border border-neutral-300 rounded-lg text-sm resize-y"
														rows={2}
														placeholder={`Enter value for ${v}...`}
													/>
												</div>
											))}
										</div>
									</div>
								)}

								{/* Model selection */}
								<div className="mb-4">
									<label className="block text-sm font-medium text-neutral-700 mb-1">
										Test with Model (optional)
									</label>
									<select
										value={selectedModel}
										onChange={(e) => setSelectedModel(e.target.value)}
										className="w-full px-3 py-2 border border-neutral-300 rounded-lg text-sm"
									>
										<option value="">Preview only (no LLM call)</option>
										{availableModels.map((m) => (
											<option key={m.name} value={m.name}>
												{m.name} ({m.tier})
											</option>
										))}
									</select>
									<p className="text-xs text-neutral-500 mt-1">
										Select a model to test the prompt with a real LLM response.
									</p>
								</div>

								{/* Test buttons */}
								<div className="flex gap-3">
									<button
										onClick={() => handleTestPrompt(false)}
										disabled={testing}
										className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
											testing
												? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
												: "bg-neutral-800 text-white hover:bg-neutral-900"
										}`}
									>
										Preview Generated Prompt
									</button>
									{selectedModel && (
										<button
											onClick={() => handleTestPrompt(true)}
											disabled={testing}
											className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
												testing
													? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
													: "bg-green-600 text-white hover:bg-green-700"
											}`}
										>
											{testing ? "Testing..." : "Run with LLM"}
										</button>
									)}
								</div>

								{/* Test Results */}
								{testResult && (
									<div className="mt-4 space-y-4">
										{/* Generated Prompt */}
										<div>
											<div className="text-sm font-medium text-neutral-700 mb-2">
												Generated Prompt
											</div>
											<pre className="bg-neutral-50 border border-neutral-200 rounded-lg p-4 text-sm overflow-auto max-h-64 whitespace-pre-wrap">
												{testResult.generatedPrompt}
											</pre>
										</div>

										{/* LLM Response */}
										{testResult.llmResponse && (
											<div>
												<div className="flex items-center justify-between mb-2">
													<span className="text-sm font-medium text-neutral-700">
														LLM Response
													</span>
													<div className="flex items-center gap-3 text-xs text-neutral-500">
														<span>Model: {testResult.llmResponse.model}</span>
														<span>
															Duration: {testResult.llmResponse.durationMs}ms
														</span>
														<span>
															Tokens: {testResult.llmResponse.tokensEval}
														</span>
													</div>
												</div>
												<pre className="bg-green-50 border border-green-200 rounded-lg p-4 text-sm overflow-auto max-h-64 whitespace-pre-wrap">
													{testResult.llmResponse.text}
												</pre>
											</div>
										)}

										{/* Error */}
										{testResult.error && (
											<div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
												{testResult.error}
											</div>
										)}
									</div>
								)}
							</div>
						</div>
					)}
				</div>
			</div>
		</main>
	);
}
