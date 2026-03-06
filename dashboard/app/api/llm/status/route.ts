import { NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";

// Ollama API endpoint
const OLLAMA_URL = process.env.OLLAMA_URL || "http://localhost:11434";

// Base path for .organizer directory
const ICLOUD_BASE =
  process.env.NEXT_PUBLIC_ICLOUD_BASE_PATH ||
  "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs";
const ENRICHMENT_CACHE_PATH = path.join(
  ICLOUD_BASE,
  ".organizer",
  "agent",
  "enrichment_cache.json"
);
const AGENT_CONFIG_PATH = path.join(
  ICLOUD_BASE,
  ".organizer",
  "agent",
  "agent_config.json"
);

// Default model tier assignments
const DEFAULT_TIER_MAP: Record<string, string> = {
  "llama3.1:8b-instruct-q8_0": "fast",
  "llama3.1:8b": "fast",
  "qwen2.5-coder:latest": "fast",
  "qwen2.5-coder:7b": "fast",
  "qwen2.5-coder:14b": "smart",
  "qwen2.5:14b": "smart",
};

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

interface EnrichmentEntry {
  enrichment: {
    model_used: string;
    used_keyword_fallback: boolean;
    duration_ms: number;
    enriched_at: string;
  };
}

interface EnrichmentCache {
  entries: EnrichmentEntry[];
  updated_at: string;
}

interface AgentConfig {
  llm_models?: {
    fast?: string;
    smart?: string;
    cloud?: string | null;
    cloud_enabled?: boolean;
    escalation_threshold?: number;
  };
}

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

/**
 * Check if Ollama is running by hitting /api/tags
 */
async function checkOllamaHealth(): Promise<{
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
 * Load enrichment cache for statistics
 */
async function loadEnrichmentCache(): Promise<EnrichmentCache | null> {
  try {
    const data = await fs.readFile(ENRICHMENT_CACHE_PATH, "utf-8");
    return JSON.parse(data) as EnrichmentCache;
  } catch {
    return null;
  }
}

/**
 * Calculate model statistics from enrichment cache
 */
function calculateModelStats(
  cache: EnrichmentCache | null,
  tierMap: Record<string, string>
): {
  modelStats: ModelStats[];
  classificationsToday: number;
  keywordFallbackToday: number;
} {
  if (!cache || !cache.entries) {
    return { modelStats: [], classificationsToday: 0, keywordFallbackToday: 0 };
  }

  const today = new Date().toISOString().split("T")[0]; // YYYY-MM-DD
  const modelData: Record<
    string,
    { total: number; durations: number[]; today: number }
  > = {};
  let classificationsToday = 0;
  let keywordFallbackToday = 0;

  for (const entry of cache.entries) {
    const enrichment = entry.enrichment;
    if (!enrichment) continue;

    const enrichedDate = enrichment.enriched_at?.split("T")[0];
    const isToday = enrichedDate === today;

    if (enrichment.used_keyword_fallback) {
      if (isToday) {
        keywordFallbackToday++;
        classificationsToday++;
      }
      continue;
    }

    const model = enrichment.model_used || "unknown";
    if (!modelData[model]) {
      modelData[model] = { total: 0, durations: [], today: 0 };
    }

    modelData[model].total++;
    modelData[model].durations.push(enrichment.duration_ms || 0);
    if (isToday) {
      modelData[model].today++;
      classificationsToday++;
    }
  }

  const modelStats: ModelStats[] = Object.entries(modelData).map(
    ([model, data]) => {
      const avgDuration =
        data.durations.length > 0
          ? Math.round(
              data.durations.reduce((a, b) => a + b, 0) / data.durations.length
            )
          : 0;

      // Determine tier from map - check exact match first, then partial matches
      let tier = "unknown";
      // First try exact match
      if (tierMap[model]) {
        tier = tierMap[model];
      } else {
        // Then try partial matches
        for (const [pattern, tierValue] of Object.entries(tierMap)) {
          if (model === pattern || model.startsWith(`${pattern.split(":")[0]}:`)) {
            tier = tierValue;
            break;
          }
        }
      }

      return {
        model,
        tier,
        total_calls: data.total,
        avg_duration_ms: avgDuration,
        calls_today: data.today,
      };
    }
  );

  return {
    modelStats: modelStats.sort((a, b) => b.calls_today - a.calls_today),
    classificationsToday,
    keywordFallbackToday,
  };
}

/**
 * GET /api/llm/status
 *
 * Returns LLM health status including:
 * - Ollama availability
 * - Loaded models
 * - Per-model average response time
 * - Total classifications today
 * - Model configuration
 */
export async function GET(): Promise<NextResponse<LLMStatusResponse>> {
  // Check Ollama health
  const ollamaHealth = await checkOllamaHealth();

  // Load configuration
  const agentConfig = await loadAgentConfig();
  const llmConfig = agentConfig?.llm_models || {};

  // Build tier map from config + defaults
  const tierMap = { ...DEFAULT_TIER_MAP };
  if (llmConfig.fast) {
    tierMap[llmConfig.fast] = "fast";
  }
  if (llmConfig.smart) {
    tierMap[llmConfig.smart] = "smart";
  }
  if (llmConfig.cloud) {
    tierMap[llmConfig.cloud] = "cloud";
  }

  // Load enrichment cache for statistics
  const cache = await loadEnrichmentCache();
  const { modelStats, classificationsToday, keywordFallbackToday } =
    calculateModelStats(cache, tierMap);

  // Get loaded model names
  const loadedModels = ollamaHealth.models.map(
    (m) => m.name || m.model || "unknown"
  );

  // Determine overall status
  let status: "operational" | "degraded" | "offline";
  if (!ollamaHealth.available) {
    status = "offline";
  } else if (loadedModels.length === 0) {
    status = "degraded";
  } else {
    status = "operational";
  }

  const response: LLMStatusResponse = {
    status,
    ollama_available: ollamaHealth.available,
    loaded_models: loadedModels,
    total_classifications_today: classificationsToday,
    keyword_fallback_count_today: keywordFallbackToday,
    model_stats: modelStats,
    config: {
      fast_model: llmConfig.fast || "llama3.1:8b-instruct-q8_0",
      smart_model: llmConfig.smart || "qwen2.5-coder:14b",
      cloud_model: llmConfig.cloud || null,
      cloud_enabled: llmConfig.cloud_enabled || false,
      escalation_threshold: llmConfig.escalation_threshold || 0.75,
    },
    health_checked_at: new Date().toISOString(),
  };

  if (ollamaHealth.error) {
    response.error = ollamaHealth.error;
  }

  // Return 503 if offline, 200 otherwise
  const statusCode = status === "offline" ? 503 : 200;
  return NextResponse.json(response, { status: statusCode });
}
