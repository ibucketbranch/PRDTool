/**
 * Tests for the LLM status API endpoint
 */

import { describe, it, expect, vi, beforeEach, Mock } from "vitest";
import { GET } from "../app/api/llm/status/route";
import fs from "fs/promises";

// Mock fs/promises
vi.mock("fs/promises");
const mockFs = fs as { readFile: Mock };

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("/api/llm/status", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-03-20T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const mockOllamaModels = {
    models: [
      {
        name: "llama3.1:8b-instruct-q8_0",
        size: 8500000000,
        digest: "abc123",
        modified_at: "2024-03-19T10:00:00Z",
        details: {
          parameter_size: "8B",
          quantization_level: "Q8_0",
          family: "llama",
        },
      },
      {
        name: "qwen2.5-coder:14b",
        size: 14000000000,
        digest: "def456",
        modified_at: "2024-03-18T10:00:00Z",
        details: {
          parameter_size: "14B",
          quantization_level: "Q4_K_M",
          family: "qwen",
        },
      },
    ],
  };

  const mockAgentConfig = {
    llm_models: {
      fast: "llama3.1:8b-instruct-q8_0",
      smart: "qwen2.5-coder:14b",
      cloud: null,
      cloud_enabled: false,
      escalation_threshold: 0.75,
    },
  };

  const mockEnrichmentCache = {
    version: "1.0",
    updated_at: "2024-03-20T10:00:00Z",
    entry_count: 3,
    entries: [
      {
        file_hash: "abc123",
        file_path: "/test/file1.pdf",
        enrichment: {
          model_used: "qwen2.5-coder:14b",
          used_keyword_fallback: false,
          duration_ms: 1500,
          enriched_at: "2024-03-20T10:00:00Z",
        },
      },
      {
        file_hash: "def456",
        file_path: "/test/file2.pdf",
        enrichment: {
          model_used: "qwen2.5-coder:14b",
          used_keyword_fallback: false,
          duration_ms: 2000,
          enriched_at: "2024-03-20T11:00:00Z",
        },
      },
      {
        file_hash: "ghi789",
        file_path: "/test/file3.pdf",
        enrichment: {
          model_used: "",
          used_keyword_fallback: true,
          duration_ms: 50,
          enriched_at: "2024-03-20T11:30:00Z",
        },
      },
    ],
  };

  const setupMocks = (options: {
    ollamaAvailable?: boolean;
    ollamaModels?: typeof mockOllamaModels.models;
    agentConfig?: typeof mockAgentConfig | null;
    enrichmentCache?: typeof mockEnrichmentCache | null;
  } = {}) => {
    const {
      ollamaAvailable = true,
      ollamaModels = mockOllamaModels.models,
      agentConfig = mockAgentConfig,
      enrichmentCache = mockEnrichmentCache,
    } = options;

    if (ollamaAvailable) {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ models: ollamaModels }),
      });
    } else {
      mockFetch.mockRejectedValue(new Error("Connection refused"));
    }

    mockFs.readFile.mockImplementation((path: string) => {
      if (path.includes("agent_config.json")) {
        if (agentConfig === null) {
          return Promise.reject(new Error("ENOENT"));
        }
        return Promise.resolve(JSON.stringify(agentConfig));
      }
      if (path.includes("enrichment_cache.json")) {
        if (enrichmentCache === null) {
          return Promise.reject(new Error("ENOENT"));
        }
        return Promise.resolve(JSON.stringify(enrichmentCache));
      }
      return Promise.reject(new Error("Unknown path"));
    });
  };

  describe("operational status", () => {
    it("should return operational status when Ollama is running with models", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.status).toBe("operational");
      expect(data.ollama_available).toBe(true);
      expect(data.loaded_models).toContain("llama3.1:8b-instruct-q8_0");
      expect(data.loaded_models).toContain("qwen2.5-coder:14b");
    });

    it("should return degraded status when Ollama is up but no models loaded", async () => {
      setupMocks({ ollamaModels: [] });

      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.status).toBe("degraded");
      expect(data.ollama_available).toBe(true);
      expect(data.loaded_models).toEqual([]);
    });

    it("should return offline status when Ollama is not running", async () => {
      setupMocks({ ollamaAvailable: false });

      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(503);
      expect(data.status).toBe("offline");
      expect(data.ollama_available).toBe(false);
      expect(data.error).toBeDefined();
    });
  });

  describe("configuration", () => {
    it("should return configured model names", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      expect(data.config.fast_model).toBe("llama3.1:8b-instruct-q8_0");
      expect(data.config.smart_model).toBe("qwen2.5-coder:14b");
      expect(data.config.cloud_model).toBe(null);
      expect(data.config.cloud_enabled).toBe(false);
      expect(data.config.escalation_threshold).toBe(0.75);
    });

    it("should use default config when agent_config.json is missing", async () => {
      setupMocks({ agentConfig: null });

      const response = await GET();
      const data = await response.json();

      expect(data.config.fast_model).toBe("llama3.1:8b-instruct-q8_0");
      expect(data.config.smart_model).toBe("qwen2.5-coder:14b");
      expect(data.config.escalation_threshold).toBe(0.75);
    });
  });

  describe("model statistics", () => {
    it("should calculate per-model statistics", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      const modelStats = data.model_stats;
      expect(modelStats.length).toBeGreaterThan(0);

      const qwenStats = modelStats.find(
        (s: { model: string }) => s.model === "qwen2.5-coder:14b"
      );
      expect(qwenStats).toBeDefined();
      expect(qwenStats.total_calls).toBe(2);
      expect(qwenStats.avg_duration_ms).toBe(1750); // (1500 + 2000) / 2
      expect(qwenStats.tier).toBe("smart");
    });

    it("should count classifications from today", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      // All 3 entries are from "today" (2024-03-20)
      expect(data.total_classifications_today).toBe(3);
      expect(data.keyword_fallback_count_today).toBe(1);
    });

    it("should handle missing enrichment cache", async () => {
      setupMocks({ enrichmentCache: null });

      const response = await GET();
      const data = await response.json();

      expect(data.total_classifications_today).toBe(0);
      expect(data.model_stats).toEqual([]);
    });
  });

  describe("health check timestamp", () => {
    it("should include health_checked_at timestamp", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      expect(data.health_checked_at).toBeDefined();
      expect(data.health_checked_at).toBe("2024-03-20T12:00:00.000Z");
    });
  });

  describe("error handling", () => {
    it("should handle Ollama timeout gracefully", async () => {
      mockFetch.mockImplementation(() => {
        const error = new Error("timeout");
        error.name = "AbortError";
        return Promise.reject(error);
      });
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockAgentConfig));

      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(503);
      expect(data.status).toBe("offline");
      expect(data.error).toContain("timed out");
    });

    it("should handle Ollama HTTP error gracefully", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
      });
      mockFs.readFile.mockResolvedValue(JSON.stringify(mockAgentConfig));

      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(503);
      expect(data.status).toBe("offline");
      expect(data.error).toContain("500");
    });
  });
});
