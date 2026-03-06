import { NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";

// Ollama API endpoint
const OLLAMA_URL = process.env.OLLAMA_URL || "http://localhost:11434";

// Base path for .organizer directory
const ICLOUD_BASE =
  process.env.NEXT_PUBLIC_ICLOUD_BASE_PATH ||
  "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs";
const AGENT_CONFIG_PATH = path.join(
  ICLOUD_BASE,
  ".organizer",
  "agent",
  "agent_config.json"
);

// Default tier assignments based on model names
const TIER_PATTERNS: [RegExp, string][] = [
  // T1 Fast - 8B class models
  [/llama3\.1:8b/i, "fast"],
  [/qwen2\.5-coder:7b/i, "fast"],
  [/qwen2\.5-coder:latest/i, "fast"],
  [/mistral:7b/i, "fast"],
  [/phi-?3/i, "fast"],
  // T2 Smart - 14B class models
  [/qwen2\.5-coder:14b/i, "smart"],
  [/qwen2\.5:14b/i, "smart"],
  [/codellama:13b/i, "smart"],
  [/llama3\.1:70b/i, "smart"],
  // T3 Cloud - very large models (opt-in)
  [/qwen3-coder:480b/i, "cloud"],
  [/deepseek-v3/i, "cloud"],
  [/claude/i, "cloud"],
  [/gpt-?4/i, "cloud"],
];

interface OllamaModel {
  name: string;
  model?: string;
  size?: number;
  digest?: string;
  modified_at?: string;
  details?: {
    parameter_size?: string;
    quantization_level?: string;
    format?: string;
    family?: string;
  };
}

interface AgentConfig {
  llm_models?: {
    fast?: string;
    smart?: string;
    cloud?: string | null;
    cloud_enabled?: boolean;
  };
}

interface ModelInfo {
  name: string;
  tier: string;
  tier_source: "config" | "pattern" | "default";
  size_bytes: number | null;
  size_display: string;
  is_available: boolean;
  is_configured: boolean;
  parameter_size: string | null;
  quantization: string | null;
  family: string | null;
  modified_at: string | null;
}

interface ModelsResponse {
  models: ModelInfo[];
  configured_models: {
    fast: string;
    smart: string;
    cloud: string | null;
  };
  ollama_available: boolean;
  error?: string;
}

/**
 * Format bytes to human-readable size
 */
function formatSize(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return "unknown";
  const gb = bytes / (1024 * 1024 * 1024);
  if (gb >= 1) {
    return `${gb.toFixed(1)}GB`;
  }
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(0)}MB`;
}

/**
 * Get tier from pattern matching
 */
function getTierFromPattern(modelName: string): string | null {
  for (const [pattern, tier] of TIER_PATTERNS) {
    if (pattern.test(modelName)) {
      return tier;
    }
  }
  return null;
}

/**
 * Fetch models from Ollama
 */
async function fetchOllamaModels(): Promise<{
  available: boolean;
  models: OllamaModel[];
  error?: string;
}> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(`${OLLAMA_URL}/api/tags`, {
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!response.ok) {
      return {
        available: false,
        models: [],
        error: `Ollama returned status ${response.status}`,
      };
    }

    const data = await response.json();
    return {
      available: true,
      models: data.models || [],
    };
  } catch (error) {
    const errorMessage =
      error instanceof Error
        ? error.name === "AbortError"
          ? "Connection timed out"
          : error.message
        : String(error);
    return {
      available: false,
      models: [],
      error: errorMessage,
    };
  }
}

/**
 * Load agent configuration
 */
async function loadAgentConfig(): Promise<AgentConfig | null> {
  try {
    const data = await fs.readFile(AGENT_CONFIG_PATH, "utf-8");
    return JSON.parse(data) as AgentConfig;
  } catch {
    return null;
  }
}

/**
 * GET /api/llm/models
 *
 * Returns list of available models with:
 * - Size in bytes and human-readable format
 * - Tier assignment (fast, smart, cloud)
 * - Availability status
 * - Configuration status (is it one of the configured models?)
 */
export async function GET(): Promise<NextResponse<ModelsResponse>> {
  // Load configuration
  const agentConfig = await loadAgentConfig();
  const llmConfig = agentConfig?.llm_models || {};
  const configuredModels = {
    fast: llmConfig.fast || "llama3.1:8b-instruct-q8_0",
    smart: llmConfig.smart || "qwen2.5-coder:14b",
    cloud: llmConfig.cloud || null,
  };

  // Fetch models from Ollama
  const ollamaResult = await fetchOllamaModels();

  // Process models
  const modelInfos: ModelInfo[] = ollamaResult.models.map((model) => {
    const name = model.name || model.model || "unknown";

    // Determine tier and source
    let tier: string;
    let tierSource: "config" | "pattern" | "default";

    if (name === configuredModels.fast || name.startsWith(`${configuredModels.fast.split(":")[0]}:`)) {
      tier = "fast";
      tierSource = "config";
    } else if (name === configuredModels.smart || name.startsWith(`${configuredModels.smart.split(":")[0]}:`)) {
      tier = "smart";
      tierSource = "config";
    } else if (configuredModels.cloud && (name === configuredModels.cloud || name.startsWith(`${configuredModels.cloud.split(":")[0]}:`))) {
      tier = "cloud";
      tierSource = "config";
    } else {
      const patternTier = getTierFromPattern(name);
      if (patternTier) {
        tier = patternTier;
        tierSource = "pattern";
      } else {
        tier = "unknown";
        tierSource = "default";
      }
    }

    // Check if this is a configured model
    const isConfigured =
      name === configuredModels.fast ||
      name === configuredModels.smart ||
      name === configuredModels.cloud;

    return {
      name,
      tier,
      tier_source: tierSource,
      size_bytes: model.size || null,
      size_display: formatSize(model.size || null),
      is_available: true,
      is_configured: isConfigured,
      parameter_size: model.details?.parameter_size || null,
      quantization: model.details?.quantization_level || null,
      family: model.details?.family || null,
      modified_at: model.modified_at || null,
    };
  });

  // Sort: configured first, then by tier (fast, smart, cloud, unknown), then by name
  const tierOrder: Record<string, number> = {
    fast: 0,
    smart: 1,
    cloud: 2,
    unknown: 3,
  };
  modelInfos.sort((a, b) => {
    // Configured models first
    if (a.is_configured !== b.is_configured) {
      return a.is_configured ? -1 : 1;
    }
    // Then by tier
    const tierDiff = (tierOrder[a.tier] ?? 3) - (tierOrder[b.tier] ?? 3);
    if (tierDiff !== 0) return tierDiff;
    // Then by name
    return a.name.localeCompare(b.name);
  });

  const response: ModelsResponse = {
    models: modelInfos,
    configured_models: configuredModels,
    ollama_available: ollamaResult.available,
  };

  if (ollamaResult.error) {
    response.error = ollamaResult.error;
  }

  // Return 503 if Ollama is not available
  const statusCode = ollamaResult.available ? 200 : 503;
  return NextResponse.json(response, { status: statusCode });
}
