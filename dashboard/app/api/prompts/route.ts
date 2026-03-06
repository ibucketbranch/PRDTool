import { NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";

// Base path for .organizer directory
const ICLOUD_BASE =
  process.env.NEXT_PUBLIC_ICLOUD_BASE_PATH ||
  "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs";
const PROMPTS_DIR = path.join(ICLOUD_BASE, ".organizer", "prompts");

// Ollama API endpoint
const OLLAMA_URL = process.env.OLLAMA_URL || "http://localhost:11434";

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

interface PromptTestRequest {
  promptName: string;
  variables: Record<string, string>;
  model?: string;
  temperature?: number;
  maxTokens?: number;
}

interface PromptTestResponse {
  success: boolean;
  generatedPrompt: string;
  llmResponse?: {
    text: string;
    model: string;
    durationMs: number;
    tokensEval: number;
  };
  error?: string;
}

interface PromptUpdateRequest {
  promptName: string;
  template: string;
  metadata?: {
    version?: string;
    description?: string;
  };
}

interface PromptUpdateResponse {
  success: boolean;
  prompt?: PromptInfo;
  error?: string;
}

/**
 * Parse prompt metadata from file header comments
 */
function parseHeader(content: string): PromptMetadata {
  const metadata: PromptMetadata = {
    name: "",
    version: "1.0.0",
    lastModified: "",
    description: "",
  };

  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("#")) break;

    const headerLine = trimmed.replace(/^#\s*/, "");
    if (headerLine.startsWith("Prompt:")) {
      metadata.name = headerLine.split(":").slice(1).join(":").trim();
    } else if (headerLine.startsWith("Version:")) {
      metadata.version = headerLine.split(":").slice(1).join(":").trim();
    } else if (headerLine.startsWith("Last-Modified:")) {
      metadata.lastModified = headerLine.split(":").slice(1).join(":").trim();
    } else if (headerLine.startsWith("Description:")) {
      metadata.description = headerLine.split(":").slice(1).join(":").trim();
    }
  }

  return metadata;
}

/**
 * Extract the template portion (non-header) from prompt content
 */
function extractTemplate(content: string): string {
  const lines = content.split("\n");
  const templateLines: string[] = [];
  let inHeader = true;

  for (const line of lines) {
    if (inHeader && line.trim().startsWith("#")) {
      continue;
    }
    inHeader = false;
    templateLines.push(line);
  }

  return templateLines.join("\n").trim();
}

/**
 * Extract variable names from a template
 */
function extractVariables(template: string): string[] {
  const matches = template.match(/\{(\w+)\}/g) || [];
  return [...new Set(matches.map((m) => m.slice(1, -1)))];
}

/**
 * Reconstruct full prompt file content from metadata and template
 */
function reconstructContent(
  name: string,
  template: string,
  metadata: { version?: string; description?: string }
): string {
  const now = new Date().toISOString().split("T")[0];
  const version = metadata.version || "1.0.0";
  const description = metadata.description || "";

  const header = [
    `# Prompt: ${name}`,
    `# Version: ${version}`,
    `# Last-Modified: ${now}`,
    `# Description: ${description}`,
    "",
  ].join("\n");

  return header + template;
}

/**
 * GET /api/prompts
 *
 * Returns all available prompts with their metadata, templates, and variables
 */
export async function GET(): Promise<NextResponse<PromptListResponse>> {
  try {
    // Check if prompts directory exists
    try {
      await fs.access(PROMPTS_DIR);
    } catch {
      return NextResponse.json({
        prompts: [],
        promptsDir: PROMPTS_DIR,
        timestamp: new Date().toISOString(),
        error: `Prompts directory not found: ${PROMPTS_DIR}`,
      });
    }

    // Read all .txt files in the prompts directory
    const files = await fs.readdir(PROMPTS_DIR);
    const txtFiles = files.filter((f) => f.endsWith(".txt"));

    const prompts: PromptInfo[] = [];

    for (const file of txtFiles) {
      const filePath = path.join(PROMPTS_DIR, file);
      const name = file.replace(".txt", "");

      try {
        const content = await fs.readFile(filePath, "utf-8");
        const stats = await fs.stat(filePath);
        const metadata = parseHeader(content);
        const template = extractTemplate(content);
        const variables = extractVariables(template);

        // Fill in name from filename if not in header
        if (!metadata.name) {
          metadata.name = name;
        }

        prompts.push({
          name,
          metadata,
          template,
          variables,
          sourcePath: filePath,
          fileModified: stats.mtime.toISOString(),
        });
      } catch (err) {
        console.error(`Failed to read prompt ${file}:`, err);
      }
    }

    // Sort by name
    prompts.sort((a, b) => a.name.localeCompare(b.name));

    return NextResponse.json({
      prompts,
      promptsDir: PROMPTS_DIR,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    return NextResponse.json(
      {
        prompts: [],
        promptsDir: PROMPTS_DIR,
        timestamp: new Date().toISOString(),
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

/**
 * POST /api/prompts
 *
 * Test a prompt against a sample file and see the response
 * Or update a prompt template
 */
export async function POST(
  request: Request
): Promise<NextResponse<PromptTestResponse | PromptUpdateResponse>> {
  try {
    const body = await request.json();

    // Determine if this is a test request or update request
    if ("variables" in body) {
      // Test request
      return handleTestRequest(body as PromptTestRequest);
    } else if ("template" in body) {
      // Update request
      return handleUpdateRequest(body as PromptUpdateRequest);
    }

    return NextResponse.json(
      {
        success: false,
        generatedPrompt: "",
        error: "Invalid request: must include 'variables' (for test) or 'template' (for update)",
      },
      { status: 400 }
    );
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        generatedPrompt: "",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

/**
 * Handle prompt test request
 */
async function handleTestRequest(
  body: PromptTestRequest
): Promise<NextResponse<PromptTestResponse>> {
  const { promptName, variables, model, temperature, maxTokens } = body;

  if (!promptName) {
    return NextResponse.json(
      {
        success: false,
        generatedPrompt: "",
        error: "promptName is required",
      },
      { status: 400 }
    );
  }

  // Load the prompt template
  const filePath = path.join(PROMPTS_DIR, `${promptName}.txt`);
  let content: string;

  try {
    content = await fs.readFile(filePath, "utf-8");
  } catch {
    return NextResponse.json(
      {
        success: false,
        generatedPrompt: "",
        error: `Prompt not found: ${promptName}`,
      },
      { status: 404 }
    );
  }

  const template = extractTemplate(content);

  // Substitute variables
  let generatedPrompt = template;
  const templateVariables = extractVariables(template);

  for (const varName of templateVariables) {
    const value = variables[varName] || `[${varName}]`;
    generatedPrompt = generatedPrompt.replace(
      new RegExp(`\\{${varName}\\}`, "g"),
      value
    );
  }

  // If no model specified, just return the generated prompt without calling LLM
  if (!model) {
    return NextResponse.json({
      success: true,
      generatedPrompt,
    });
  }

  // Call Ollama to test the prompt
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);

    const response = await fetch(`${OLLAMA_URL}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        prompt: generatedPrompt,
        stream: false,
        options: {
          temperature: temperature ?? 0.7,
          num_predict: maxTokens ?? 1024,
        },
      }),
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json({
        success: false,
        generatedPrompt,
        error: `Ollama error: ${response.status} - ${errorText}`,
      });
    }

    const data = await response.json();

    return NextResponse.json({
      success: true,
      generatedPrompt,
      llmResponse: {
        text: data.response || "",
        model: data.model || model,
        durationMs: Math.round((data.total_duration || 0) / 1_000_000),
        tokensEval: data.eval_count || 0,
      },
    });
  } catch (error) {
    const errorMessage =
      error instanceof Error
        ? error.name === "AbortError"
          ? "Request timed out"
          : error.message
        : String(error);

    return NextResponse.json({
      success: false,
      generatedPrompt,
      error: `Failed to call Ollama: ${errorMessage}`,
    });
  }
}

/**
 * Handle prompt update request
 */
async function handleUpdateRequest(
  body: PromptUpdateRequest
): Promise<NextResponse<PromptUpdateResponse>> {
  const { promptName, template, metadata } = body;

  if (!promptName) {
    return NextResponse.json(
      {
        success: false,
        error: "promptName is required",
      },
      { status: 400 }
    );
  }

  if (!template) {
    return NextResponse.json(
      {
        success: false,
        error: "template is required",
      },
      { status: 400 }
    );
  }

  const filePath = path.join(PROMPTS_DIR, `${promptName}.txt`);

  // Load existing metadata if file exists
  let existingMetadata: { version?: string; description?: string } = {};
  try {
    const existingContent = await fs.readFile(filePath, "utf-8");
    const parsed = parseHeader(existingContent);
    existingMetadata = {
      version: parsed.version,
      description: parsed.description,
    };
  } catch {
    // File doesn't exist, will create new
  }

  // Merge with provided metadata
  const finalMetadata = {
    version: metadata?.version || existingMetadata.version || "1.0.0",
    description: metadata?.description || existingMetadata.description || "",
  };

  // Reconstruct file content
  const newContent = reconstructContent(promptName, template, finalMetadata);

  // Write to file
  try {
    await fs.writeFile(filePath, newContent, "utf-8");
  } catch (err) {
    return NextResponse.json(
      {
        success: false,
        error: `Failed to write file: ${err instanceof Error ? err.message : String(err)}`,
      },
      { status: 500 }
    );
  }

  // Read back the file to return updated info
  const stats = await fs.stat(filePath);
  const parsedMetadata = parseHeader(newContent);
  const variables = extractVariables(template);

  if (!parsedMetadata.name) {
    parsedMetadata.name = promptName;
  }

  return NextResponse.json({
    success: true,
    prompt: {
      name: promptName,
      metadata: parsedMetadata,
      template,
      variables,
      sourcePath: filePath,
      fileModified: stats.mtime.toISOString(),
    },
  });
}
