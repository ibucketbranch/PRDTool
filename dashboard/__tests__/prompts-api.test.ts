/**
 * Tests for the prompts API endpoint
 */

import { describe, it, expect, vi, beforeEach, Mock } from "vitest";
import { GET, POST } from "../app/api/prompts/route";
import fs from "fs/promises";

// Mock fs/promises
vi.mock("fs/promises");
const mockFs = fs as {
  access: Mock;
  readdir: Mock;
  readFile: Mock;
  stat: Mock;
  writeFile: Mock;
};

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("/api/prompts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockPromptContent = `# Prompt: classify_file
# Version: 1.0.0
# Last-Modified: 2024-03-01
# Description: Classify a file into a category based on filename and content preview.

Given the filename and content preview below, classify this file into one of the available bins.

Filename: {filename}
Content Preview: {content}

Available Bins:
{bins}

Reply with JSON:
{
    "bin": "selected_bin_name",
    "confidence": 0.0 to 1.0,
    "reason": "brief explanation"
}`;

  const mockValidatePromptContent = `# Prompt: validate_placement
# Version: 1.2.0
# Last-Modified: 2024-03-15
# Description: Validate if a file belongs in its current location.

File '{filename}' is in '{current_path}'.
Based on its name and content preview, does it belong in '{current_bin}'?

Reply with JSON:
{
    "belongs_here": true/false,
    "reason": "brief explanation"
}`;

  const mockStats = {
    mtime: new Date("2024-03-20T10:00:00Z"),
  };

  describe("GET /api/prompts", () => {
    it("should return all prompts with metadata and variables", async () => {
      mockFs.access.mockResolvedValue(undefined);
      mockFs.readdir.mockResolvedValue(["classify_file.txt", "validate_placement.txt"]);
      mockFs.readFile.mockImplementation((path: string) => {
        if (path.includes("classify_file.txt")) {
          return Promise.resolve(mockPromptContent);
        }
        if (path.includes("validate_placement.txt")) {
          return Promise.resolve(mockValidatePromptContent);
        }
        return Promise.reject(new Error("Unknown file"));
      });
      mockFs.stat.mockResolvedValue(mockStats);

      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.prompts).toHaveLength(2);
      expect(data.prompts[0].name).toBe("classify_file");
      expect(data.prompts[0].metadata.version).toBe("1.0.0");
      expect(data.prompts[0].metadata.description).toBe(
        "Classify a file into a category based on filename and content preview."
      );
      expect(data.prompts[0].variables).toContain("filename");
      expect(data.prompts[0].variables).toContain("content");
      expect(data.prompts[0].variables).toContain("bins");
    });

    it("should return empty array when prompts directory does not exist", async () => {
      mockFs.access.mockRejectedValue(new Error("ENOENT"));

      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.prompts).toEqual([]);
      expect(data.error).toContain("not found");
    });

    it("should filter only .txt files", async () => {
      mockFs.access.mockResolvedValue(undefined);
      mockFs.readdir.mockResolvedValue([
        "classify_file.txt",
        "README.md",
        ".gitkeep",
        "validate_placement.txt",
      ]);
      mockFs.readFile.mockImplementation((path: string) => {
        if (path.includes("classify_file.txt")) {
          return Promise.resolve(mockPromptContent);
        }
        if (path.includes("validate_placement.txt")) {
          return Promise.resolve(mockValidatePromptContent);
        }
        return Promise.reject(new Error("Unknown file"));
      });
      mockFs.stat.mockResolvedValue(mockStats);

      const response = await GET();
      const data = await response.json();

      expect(data.prompts).toHaveLength(2);
    });

    it("should sort prompts by name", async () => {
      mockFs.access.mockResolvedValue(undefined);
      mockFs.readdir.mockResolvedValue(["validate_placement.txt", "classify_file.txt"]);
      mockFs.readFile.mockImplementation((path: string) => {
        if (path.includes("classify_file.txt")) {
          return Promise.resolve(mockPromptContent);
        }
        if (path.includes("validate_placement.txt")) {
          return Promise.resolve(mockValidatePromptContent);
        }
        return Promise.reject(new Error("Unknown file"));
      });
      mockFs.stat.mockResolvedValue(mockStats);

      const response = await GET();
      const data = await response.json();

      expect(data.prompts[0].name).toBe("classify_file");
      expect(data.prompts[1].name).toBe("validate_placement");
    });

    it("should handle prompts without header metadata", async () => {
      const noHeaderContent = `This is a prompt without any header.
Just plain text with {variable} placeholders.`;

      mockFs.access.mockResolvedValue(undefined);
      mockFs.readdir.mockResolvedValue(["simple.txt"]);
      mockFs.readFile.mockResolvedValue(noHeaderContent);
      mockFs.stat.mockResolvedValue(mockStats);

      const response = await GET();
      const data = await response.json();

      expect(data.prompts).toHaveLength(1);
      expect(data.prompts[0].name).toBe("simple");
      expect(data.prompts[0].metadata.version).toBe("1.0.0");
      expect(data.prompts[0].variables).toContain("variable");
    });

    it("should include file modification timestamp", async () => {
      mockFs.access.mockResolvedValue(undefined);
      mockFs.readdir.mockResolvedValue(["classify_file.txt"]);
      mockFs.readFile.mockResolvedValue(mockPromptContent);
      mockFs.stat.mockResolvedValue({
        mtime: new Date("2024-03-20T10:00:00Z"),
      });

      const response = await GET();
      const data = await response.json();

      expect(data.prompts[0].fileModified).toBe("2024-03-20T10:00:00.000Z");
    });
  });

  describe("POST /api/prompts - Test Request", () => {
    it("should generate prompt preview without LLM call", async () => {
      mockFs.readFile.mockResolvedValue(mockPromptContent);

      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          promptName: "classify_file",
          variables: {
            filename: "invoice_2024.pdf",
            content: "Invoice from Acme Corp",
            bins: "Finances, Work, Personal",
          },
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.generatedPrompt).toContain("invoice_2024.pdf");
      expect(data.generatedPrompt).toContain("Invoice from Acme Corp");
      expect(data.generatedPrompt).toContain("Finances, Work, Personal");
      expect(data.llmResponse).toBeUndefined();
    });

    it("should return 404 when prompt not found", async () => {
      mockFs.readFile.mockRejectedValue(new Error("ENOENT"));

      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          promptName: "nonexistent_prompt",
          variables: {},
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.success).toBe(false);
      expect(data.error).toContain("not found");
    });

    it("should use placeholder for missing variables", async () => {
      mockFs.readFile.mockResolvedValue(mockPromptContent);

      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          promptName: "classify_file",
          variables: {
            filename: "test.pdf",
            // content and bins are missing
          },
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.generatedPrompt).toContain("test.pdf");
      expect(data.generatedPrompt).toContain("[content]");
      expect(data.generatedPrompt).toContain("[bins]");
    });

    it("should call Ollama when model is specified", async () => {
      mockFs.readFile.mockResolvedValue(mockPromptContent);
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            response: '{"bin": "Finances", "confidence": 0.95, "reason": "Invoice detected"}',
            model: "llama3.1:8b-instruct-q8_0",
            total_duration: 1500000000, // nanoseconds
            eval_count: 50,
          }),
      });

      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          promptName: "classify_file",
          variables: {
            filename: "invoice.pdf",
            content: "Invoice from Acme",
            bins: "Finances, Work",
          },
          model: "llama3.1:8b-instruct-q8_0",
          temperature: 0.7,
          maxTokens: 1024,
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.llmResponse).toBeDefined();
      expect(data.llmResponse.text).toContain("Finances");
      expect(data.llmResponse.model).toBe("llama3.1:8b-instruct-q8_0");
      expect(data.llmResponse.durationMs).toBe(1500);
      expect(data.llmResponse.tokensEval).toBe(50);
    });

    it("should handle Ollama errors gracefully", async () => {
      mockFs.readFile.mockResolvedValue(mockPromptContent);
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        text: () => Promise.resolve("Internal server error"),
      });

      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          promptName: "classify_file",
          variables: {},
          model: "llama3.1:8b",
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(data.success).toBe(false);
      expect(data.error).toContain("Ollama error");
      expect(data.generatedPrompt).toBeDefined();
    });

    it("should return 400 when promptName is missing", async () => {
      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          variables: {},
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain("promptName");
    });
  });

  describe("POST /api/prompts - Update Request", () => {
    it("should update prompt template and metadata", async () => {
      const existingContent = mockPromptContent;
      const newTemplate = `This is the new template with {variable}.`;

      mockFs.readFile.mockResolvedValue(existingContent);
      mockFs.writeFile.mockResolvedValue(undefined);
      mockFs.stat.mockResolvedValue({
        mtime: new Date("2024-03-21T12:00:00Z"),
      });

      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          promptName: "classify_file",
          template: newTemplate,
          metadata: {
            version: "1.1.0",
            description: "Updated description",
          },
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.prompt).toBeDefined();
      expect(data.prompt.template).toBe(newTemplate);
      expect(data.prompt.metadata.version).toBe("1.1.0");
      expect(data.prompt.metadata.description).toBe("Updated description");
      expect(data.prompt.variables).toContain("variable");

      // Verify writeFile was called with correct content
      expect(mockFs.writeFile).toHaveBeenCalled();
      const writtenContent = mockFs.writeFile.mock.calls[0][1] as string;
      expect(writtenContent).toContain("# Prompt: classify_file");
      expect(writtenContent).toContain("# Version: 1.1.0");
      expect(writtenContent).toContain("# Description: Updated description");
      expect(writtenContent).toContain(newTemplate);
    });

    it("should preserve existing metadata when not provided", async () => {
      mockFs.readFile.mockResolvedValue(mockPromptContent);
      mockFs.writeFile.mockResolvedValue(undefined);
      mockFs.stat.mockResolvedValue({
        mtime: new Date("2024-03-21T12:00:00Z"),
      });

      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          promptName: "classify_file",
          template: "New template content",
          // No metadata provided
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(data.success).toBe(true);
      expect(data.prompt.metadata.version).toBe("1.0.0"); // Preserved from original
      expect(data.prompt.metadata.description).toBe(
        "Classify a file into a category based on filename and content preview."
      );
    });

    it("should create new prompt if it does not exist", async () => {
      mockFs.readFile.mockRejectedValue(new Error("ENOENT"));
      mockFs.writeFile.mockResolvedValue(undefined);
      mockFs.stat.mockResolvedValue({
        mtime: new Date("2024-03-21T12:00:00Z"),
      });

      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          promptName: "new_prompt",
          template: "Brand new template with {var}",
          metadata: {
            version: "1.0.0",
            description: "A new prompt",
          },
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.prompt.name).toBe("new_prompt");
      expect(mockFs.writeFile).toHaveBeenCalled();
    });

    it("should return 400 when template is missing for update", async () => {
      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          promptName: "classify_file",
          // template is missing
          metadata: { version: "1.1.0" },
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.success).toBe(false);
    });

    it("should handle write errors", async () => {
      mockFs.readFile.mockResolvedValue(mockPromptContent);
      mockFs.writeFile.mockRejectedValue(new Error("Permission denied"));

      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          promptName: "classify_file",
          template: "New template",
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(500);
      expect(data.success).toBe(false);
      expect(data.error).toContain("Permission denied");
    });
  });

  describe("POST /api/prompts - Invalid Requests", () => {
    it("should return 400 for invalid request body", async () => {
      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          // Neither variables nor template provided
          promptName: "test",
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain("Invalid request");
    });

    it("should handle malformed JSON gracefully", async () => {
      const request = new Request("http://localhost/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "not valid json",
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(500);
      expect(data.success).toBe(false);
    });
  });
});
