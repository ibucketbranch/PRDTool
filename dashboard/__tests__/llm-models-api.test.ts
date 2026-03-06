/**
 * Tests for the LLM models API endpoint
 */

import { describe, it, expect, vi, beforeEach, Mock } from "vitest";
import { GET } from "../app/api/llm/models/route";
import fs from "fs/promises";

// Mock fs/promises
vi.mock("fs/promises");
const mockFs = fs as { readFile: Mock };

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("/api/llm/models", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockOllamaModels = {
    models: [
      {
        name: "llama3.1:8b-instruct-q8_0",
        size: 8537329664, // ~8GB
        digest: "abc123",
        modified_at: "2024-03-19T10:00:00Z",
        details: {
          parameter_size: "8B",
          quantization_level: "Q8_0",
          family: "llama",
          format: "gguf",
        },
      },
      {
        name: "qwen2.5-coder:14b",
        size: 9000000000, // ~9GB
        digest: "def456",
        modified_at: "2024-03-18T10:00:00Z",
        details: {
          parameter_size: "14B",
          quantization_level: "Q4_K_M",
          family: "qwen",
          format: "gguf",
        },
      },
      {
        name: "mistral:7b",
        size: 4000000000, // ~4GB
        digest: "ghi789",
        modified_at: "2024-03-17T10:00:00Z",
        details: {
          parameter_size: "7B",
          family: "mistral",
        },
      },
      {
        name: "unknown-model:latest",
        size: 2000000000, // ~2GB
        digest: "xyz999",
        modified_at: "2024-03-16T10:00:00Z",
        details: {},
      },
    ],
  };

  const mockAgentConfig = {
    llm_models: {
      fast: "llama3.1:8b-instruct-q8_0",
      smart: "qwen2.5-coder:14b",
      cloud: null,
      cloud_enabled: false,
    },
  };

  const setupMocks = (options: {
    ollamaAvailable?: boolean;
    ollamaModels?: typeof mockOllamaModels.models;
    agentConfig?: typeof mockAgentConfig | null;
  } = {}) => {
    const {
      ollamaAvailable = true,
      ollamaModels = mockOllamaModels.models,
      agentConfig = mockAgentConfig,
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
      return Promise.reject(new Error("Unknown path"));
    });
  };

  describe("model listing", () => {
    it("should return list of available models", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.ollama_available).toBe(true);
      expect(data.models.length).toBe(4);
    });

    it("should include model details", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      const llamaModel = data.models.find(
        (m: { name: string }) => m.name === "llama3.1:8b-instruct-q8_0"
      );
      expect(llamaModel).toBeDefined();
      expect(llamaModel.size_bytes).toBe(8537329664);
      expect(llamaModel.size_display).toBe("8.0GB");
      expect(llamaModel.parameter_size).toBe("8B");
      expect(llamaModel.quantization).toBe("Q8_0");
      expect(llamaModel.family).toBe("llama");
      expect(llamaModel.is_available).toBe(true);
    });

    it("should return 503 when Ollama is not available", async () => {
      setupMocks({ ollamaAvailable: false });

      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(503);
      expect(data.ollama_available).toBe(false);
      expect(data.models).toEqual([]);
      expect(data.error).toBeDefined();
    });
  });

  describe("tier assignment", () => {
    it("should assign tier from config for configured models", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      const llamaModel = data.models.find(
        (m: { name: string }) => m.name === "llama3.1:8b-instruct-q8_0"
      );
      expect(llamaModel.tier).toBe("fast");
      expect(llamaModel.tier_source).toBe("config");
      expect(llamaModel.is_configured).toBe(true);

      const qwenModel = data.models.find(
        (m: { name: string }) => m.name === "qwen2.5-coder:14b"
      );
      expect(qwenModel.tier).toBe("smart");
      expect(qwenModel.tier_source).toBe("config");
      expect(qwenModel.is_configured).toBe(true);
    });

    it("should assign tier from pattern for non-configured models", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      const mistralModel = data.models.find(
        (m: { name: string }) => m.name === "mistral:7b"
      );
      expect(mistralModel.tier).toBe("fast");
      expect(mistralModel.tier_source).toBe("pattern");
      expect(mistralModel.is_configured).toBe(false);
    });

    it("should assign unknown tier for unrecognized models", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      const unknownModel = data.models.find(
        (m: { name: string }) => m.name === "unknown-model:latest"
      );
      expect(unknownModel.tier).toBe("unknown");
      expect(unknownModel.tier_source).toBe("default");
      expect(unknownModel.is_configured).toBe(false);
    });
  });

  describe("configured models", () => {
    it("should return configured model names", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      expect(data.configured_models.fast).toBe("llama3.1:8b-instruct-q8_0");
      expect(data.configured_models.smart).toBe("qwen2.5-coder:14b");
      expect(data.configured_models.cloud).toBe(null);
    });

    it("should use default config when agent_config.json is missing", async () => {
      setupMocks({ agentConfig: null });

      const response = await GET();
      const data = await response.json();

      expect(data.configured_models.fast).toBe("llama3.1:8b-instruct-q8_0");
      expect(data.configured_models.smart).toBe("qwen2.5-coder:14b");
    });
  });

  describe("sorting", () => {
    it("should sort configured models first", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      // First two should be configured models
      expect(data.models[0].is_configured).toBe(true);
      expect(data.models[1].is_configured).toBe(true);
      // Last two should be non-configured
      expect(data.models[2].is_configured).toBe(false);
      expect(data.models[3].is_configured).toBe(false);
    });

    it("should sort by tier within configured/non-configured groups", async () => {
      setupMocks();

      const response = await GET();
      const data = await response.json();

      // Among configured, fast should come before smart
      const configuredModels = data.models.filter(
        (m: { is_configured: boolean }) => m.is_configured
      );
      const fastIndex = configuredModels.findIndex(
        (m: { tier: string }) => m.tier === "fast"
      );
      const smartIndex = configuredModels.findIndex(
        (m: { tier: string }) => m.tier === "smart"
      );
      expect(fastIndex).toBeLessThan(smartIndex);
    });
  });

  describe("size formatting", () => {
    it("should format size in GB for large models", async () => {
      setupMocks({
        ollamaModels: [
          {
            name: "large-model",
            size: 15000000000,
            digest: "test",
            modified_at: "2024-01-01",
            details: {},
          },
        ],
      });

      const response = await GET();
      const data = await response.json();

      expect(data.models[0].size_display).toBe("14.0GB");
    });

    it("should format size in MB for smaller models", async () => {
      setupMocks({
        ollamaModels: [
          {
            name: "small-model",
            size: 500000000,
            digest: "test",
            modified_at: "2024-01-01",
            details: {},
          },
        ],
      });

      const response = await GET();
      const data = await response.json();

      expect(data.models[0].size_display).toBe("477MB");
    });

    it("should handle missing size gracefully", async () => {
      setupMocks({
        ollamaModels: [
          {
            name: "no-size-model",
            digest: "test",
            modified_at: "2024-01-01",
            details: {},
          },
        ],
      });

      const response = await GET();
      const data = await response.json();

      expect(data.models[0].size_bytes).toBe(null);
      expect(data.models[0].size_display).toBe("unknown");
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
      expect(data.ollama_available).toBe(false);
      expect(data.error).toContain("timed out");
    });
  });
});
