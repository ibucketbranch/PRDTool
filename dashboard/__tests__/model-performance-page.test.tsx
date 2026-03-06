import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// Mock fetch function globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Import after mocking
import ModelPerformancePage from "@/app/model-performance/page";

// Mock data
const mockLLMStatusResponse = {
	status: "operational" as const,
	ollama_available: true,
	loaded_models: ["llama3.1:8b-instruct-q8_0", "qwen2.5-coder:14b"],
	total_classifications_today: 25,
	keyword_fallback_count_today: 3,
	model_stats: [
		{
			model: "qwen2.5-coder:14b",
			tier: "smart",
			total_calls: 100,
			avg_duration_ms: 2500,
			calls_today: 15,
		},
		{
			model: "llama3.1:8b-instruct-q8_0",
			tier: "fast",
			total_calls: 200,
			avg_duration_ms: 1200,
			calls_today: 10,
		},
	],
	config: {
		fast_model: "llama3.1:8b-instruct-q8_0",
		smart_model: "qwen2.5-coder:14b",
		cloud_model: null,
		cloud_enabled: false,
		escalation_threshold: 0.75,
	},
	health_checked_at: "2024-03-20T12:00:00.000Z",
};

const mockLLMModelsResponse = {
	models: [
		{
			name: "llama3.1:8b-instruct-q8_0",
			tier: "fast",
			tier_source: "config",
			size_display: "8.5GB",
			is_available: true,
			is_configured: true,
			parameter_size: "8B",
			quantization: "Q8_0",
			family: "llama",
			modified_at: "2024-03-19T10:00:00Z",
		},
		{
			name: "qwen2.5-coder:14b",
			tier: "smart",
			tier_source: "config",
			size_display: "9.0GB",
			is_available: true,
			is_configured: true,
			parameter_size: "14B",
			quantization: "Q4_K_M",
			family: "qwen",
			modified_at: "2024-03-18T10:00:00Z",
		},
	],
	configured_models: {
		fast: "llama3.1:8b-instruct-q8_0",
		smart: "qwen2.5-coder:14b",
		cloud: null,
	},
	ollama_available: true,
};

const mockOfflineStatusResponse = {
	status: "offline" as const,
	ollama_available: false,
	loaded_models: [],
	total_classifications_today: 0,
	keyword_fallback_count_today: 0,
	model_stats: [],
	config: {
		fast_model: "llama3.1:8b-instruct-q8_0",
		smart_model: "qwen2.5-coder:14b",
		cloud_model: null,
		cloud_enabled: false,
		escalation_threshold: 0.75,
	},
	health_checked_at: "2024-03-20T12:00:00.000Z",
	error: "Connection refused",
};

const mockDegradedStatusResponse = {
	...mockLLMStatusResponse,
	status: "degraded" as const,
	loaded_models: [],
};

describe("ModelPerformancePage", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	const setupMocks = (
		statusResponse = mockLLMStatusResponse,
		modelsResponse = mockLLMModelsResponse,
		statusCode = 200
	) => {
		mockFetch.mockImplementation((url: string) => {
			if (url.includes("/api/llm/status")) {
				return Promise.resolve({
					ok: statusCode === 200 || statusCode === 503,
					status: statusCode,
					json: async () => statusResponse,
				});
			}
			if (url.includes("/api/llm/models")) {
				return Promise.resolve({
					ok: true,
					status: 200,
					json: async () => modelsResponse,
				});
			}
			return Promise.reject(new Error("Unknown URL"));
		});
	};

	describe("basic rendering", () => {
		it("renders page title", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			expect(screen.getByText("Model Performance")).toBeInTheDocument();
		});

		it("shows loading state initially", () => {
			mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves
			render(<ModelPerformancePage />);

			expect(screen.getByText("Loading LLM status...")).toBeInTheDocument();
		});

		it("shows back to dashboard link", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("← Back to Dashboard")).toBeInTheDocument();
			});
		});
	});

	describe("health status display", () => {
		it("shows operational status when Ollama is running with models", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				// Page uses capitalize class, so text is "operational" displayed as "Operational"
				expect(screen.getByText(/operational/i)).toBeInTheDocument();
				expect(screen.getByText("Ollama Connected")).toBeInTheDocument();
			});
		});

		it("shows degraded status when Ollama is up but no models", async () => {
			setupMocks(mockDegradedStatusResponse);
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText(/degraded/i)).toBeInTheDocument();
			});
		});

		it("shows offline status when Ollama is not running", async () => {
			setupMocks(mockOfflineStatusResponse, mockLLMModelsResponse, 503);
			render(<ModelPerformancePage />);

			await waitFor(() => {
				// Multiple elements may match "offline", so use getAllByText
				const offlineElements = screen.getAllByText(/offline/i);
				expect(offlineElements.length).toBeGreaterThan(0);
				expect(screen.getByText("Ollama Offline")).toBeInTheDocument();
			});
		});

		it("shows error message when Ollama has error", async () => {
			setupMocks(mockOfflineStatusResponse, mockLLMModelsResponse, 503);
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText(/Connection refused/)).toBeInTheDocument();
			});
		});

		it("shows last check timestamp", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText(/Last check:/)).toBeInTheDocument();
			});
		});
	});

	describe("key metrics display", () => {
		it("displays classifications today", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Classifications Today")).toBeInTheDocument();
				expect(screen.getByText("25")).toBeInTheDocument();
			});
		});

		it("displays total LLM calls", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Total LLM Calls")).toBeInTheDocument();
				expect(screen.getByText("300")).toBeInTheDocument(); // 100 + 200
			});
		});

		it("displays keyword fallbacks count", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Keyword Fallbacks")).toBeInTheDocument();
				expect(screen.getByText("3")).toBeInTheDocument();
			});
		});

		it("displays fallback rate percentage", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Fallback Rate")).toBeInTheDocument();
				expect(screen.getByText("12.0%")).toBeInTheDocument(); // 3/25 * 100
			});
		});

		it("displays models available count", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Models Available")).toBeInTheDocument();
				expect(screen.getByText("2")).toBeInTheDocument();
			});
		});
	});

	describe("tier summary display", () => {
		it("shows fast tier (T1) card", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("T1 fast")).toBeInTheDocument();
			});
		});

		it("shows smart tier (T2) card", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("T2 smart")).toBeInTheDocument();
			});
		});

		it("shows cloud tier (T3) card", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("T3 cloud")).toBeInTheDocument();
			});
		});

		it("shows configured model for each tier", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				// Check that configured models appear in the tier cards
				expect(
					screen.getAllByText("llama3.1:8b-instruct-q8_0").length
				).toBeGreaterThan(0);
				expect(screen.getAllByText("qwen2.5-coder:14b").length).toBeGreaterThan(0);
			});
		});

		it("shows Disabled for unconfigured cloud tier", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				// "Disabled" may appear in both tier summary and configuration panel
				const disabledElements = screen.getAllByText("Disabled");
				expect(disabledElements.length).toBeGreaterThan(0);
			});
		});
	});

	describe("model statistics table", () => {
		it("renders model statistics table", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Model Statistics")).toBeInTheDocument();
			});
		});

		it("shows model names in the table", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				const modelCells = screen.getAllByText("qwen2.5-coder:14b");
				expect(modelCells.length).toBeGreaterThan(0);
			});
		});

		it("shows tier badges in the table", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getAllByText("smart").length).toBeGreaterThan(0);
				expect(screen.getAllByText("fast").length).toBeGreaterThan(0);
			});
		});

		it("shows total calls for each model", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				// "100" appears in multiple places (tier summary + table), so use getAllByText
				const hundredElements = screen.getAllByText("100");
				expect(hundredElements.length).toBeGreaterThan(0);
				const twoHundredElements = screen.getAllByText("200");
				expect(twoHundredElements.length).toBeGreaterThan(0);
			});
		});

		it("shows empty state when no model stats", async () => {
			const emptyResponse = {
				...mockLLMStatusResponse,
				model_stats: [],
			};
			setupMocks(emptyResponse);
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(
					screen.getByText(
						/No model statistics available. Run some LLM classifications/
					)
				).toBeInTheDocument();
			});
		});
	});

	describe("configuration panel", () => {
		it("shows configuration section", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Configuration")).toBeInTheDocument();
			});
		});

		it("shows fast model configuration", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Fast Model (T1)")).toBeInTheDocument();
			});
		});

		it("shows smart model configuration", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Smart Model (T2)")).toBeInTheDocument();
			});
		});

		it("shows cloud model configuration", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Cloud Model (T3)")).toBeInTheDocument();
			});
		});

		it("shows escalation threshold", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Escalation Threshold")).toBeInTheDocument();
				expect(screen.getByText("75%")).toBeInTheDocument();
			});
		});
	});

	describe("loaded models panel", () => {
		it("shows loaded models section", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Loaded Models (Ollama)")).toBeInTheDocument();
			});
		});

		it("shows model cards with details", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Size: 8.5GB")).toBeInTheDocument();
				expect(screen.getByText("Size: 9.0GB")).toBeInTheDocument();
			});
		});

		it("shows parameter size for models", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Parameters: 8B")).toBeInTheDocument();
				expect(screen.getByText("Parameters: 14B")).toBeInTheDocument();
			});
		});

		it("shows quantization for models", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Quantization: Q8_0")).toBeInTheDocument();
				expect(screen.getByText("Quantization: Q4_K_M")).toBeInTheDocument();
			});
		});

		it("shows family for models", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Family: llama")).toBeInTheDocument();
				expect(screen.getByText("Family: qwen")).toBeInTheDocument();
			});
		});

		it("shows configured badge for configured models", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				const configuredBadges = screen.getAllByText("configured");
				expect(configuredBadges.length).toBeGreaterThan(0);
			});
		});

		it("shows Ollama offline message when not available", async () => {
			const offlineModels = {
				...mockLLMModelsResponse,
				ollama_available: false,
				models: [],
			};
			setupMocks(mockOfflineStatusResponse, offlineModels, 503);
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(
					screen.getByText(/Ollama is not available. Start Ollama to see loaded models/)
				).toBeInTheDocument();
			});
		});

		it("shows empty state when no models loaded", async () => {
			const emptyModels = {
				...mockLLMModelsResponse,
				models: [],
			};
			setupMocks(mockLLMStatusResponse, emptyModels);
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(
					screen.getByText(/No models loaded. Pull a model with/)
				).toBeInTheDocument();
			});
		});
	});

	describe("refresh functionality", () => {
		it("has a refresh button", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Refresh")).toBeInTheDocument();
			});
		});

		it("reloads data when refresh is clicked", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText(/operational/i)).toBeInTheDocument();
			});

			// Update mock to return different data
			const updatedResponse = {
				...mockLLMStatusResponse,
				total_classifications_today: 50,
			};
			setupMocks(updatedResponse);

			fireEvent.click(screen.getByText("Refresh"));

			await waitFor(() => {
				expect(screen.getByText("50")).toBeInTheDocument();
			});
		});
	});

	describe("error handling", () => {
		it("shows error message on fetch failure", async () => {
			mockFetch.mockRejectedValue(new Error("Network error"));
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText(/Network error/)).toBeInTheDocument();
			});
		});

		it("shows error for non-200/503 status", async () => {
			mockFetch.mockImplementation((url: string) => {
				if (url.includes("/api/llm/status")) {
					return Promise.resolve({
						ok: false,
						status: 500,
					});
				}
				if (url.includes("/api/llm/models")) {
					return Promise.resolve({
						ok: true,
						status: 200,
						json: async () => mockLLMModelsResponse,
					});
				}
				return Promise.reject(new Error("Unknown URL"));
			});

			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText(/Status API returned 500/)).toBeInTheDocument();
			});
		});
	});

	describe("average response time calculation", () => {
		it("calculates weighted average response time", async () => {
			setupMocks();
			render(<ModelPerformancePage />);

			await waitFor(() => {
				expect(screen.getByText("Avg Response Time")).toBeInTheDocument();
				// Weighted avg: (100*2500 + 200*1200) / 300 = 490000/300 = 1633ms = 1.6s
				expect(screen.getByText("1.6s")).toBeInTheDocument();
			});
		});

		it("shows dash when no calls have been made", async () => {
			const emptyResponse = {
				...mockLLMStatusResponse,
				model_stats: [],
			};
			setupMocks(emptyResponse);
			render(<ModelPerformancePage />);

			await waitFor(() => {
				// Find the Avg Response Time label
				expect(screen.getByText("Avg Response Time")).toBeInTheDocument();
				// There should be a dash "—" somewhere (appears multiple times as default values)
				const dashes = screen.getAllByText("—");
				expect(dashes.length).toBeGreaterThan(0);
			});
		});
	});
});
