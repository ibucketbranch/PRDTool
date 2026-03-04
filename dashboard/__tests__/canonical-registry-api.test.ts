/**
 * Tests for canonical registry API endpoint
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "../app/api/canonical-registry/route";

// Mock the canonical-registry module
vi.mock("../lib/canonical-registry", () => ({
  loadCanonicalRegistry: vi.fn(),
  assessFolderWithRegistry: vi.fn(),
  PYTHON_CATEGORY_PATTERNS: {
    employment: {
      patterns: ["resume", "cv"],
      canonicalFolder: "Resumes",
      parentFolder: "Employment",
    },
    finances: {
      patterns: ["tax", "invoice"],
      canonicalFolder: "Taxes",people 
      parentFolder: "Finances Bin",
    },
  },
}));

import {
  loadCanonicalRegistry,
  assessFolderWithRegistry,
} from "../lib/canonical-registry";

describe("GET /api/canonical-registry", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("returns error when basePath is missing", async () => {
    const request = new NextRequest("http://localhost/api/canonical-registry");
    const response = await GET(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.error).toBe("Missing required parameter: basePath");
  });

  it("returns registry and category patterns", async () => {
    vi.mocked(loadCanonicalRegistry).mockReturnValue({
      registry: {
        folders: {
          resume: {
            path: "Employment/Resumes",
            normalizedName: "resume",
            category: "Employment",
          },
        },
      },
    });

    const request = new NextRequest(
      "http://localhost/api/canonical-registry?basePath=/test/path"
    );
    const response = await GET(request);
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.registry).toBeDefined();
    expect(data.categoryPatterns).toBeDefined();
    expect(data.categoryPatterns.employment).toBeDefined();
  });

  it("returns error when registry load fails", async () => {
    vi.mocked(loadCanonicalRegistry).mockReturnValue({
      registry: null,
      error: "File not found",
    });

    const request = new NextRequest(
      "http://localhost/api/canonical-registry?basePath=/test/path"
    );
    const response = await GET(request);
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.registry).toBeNull();
    expect(data.error).toBe("File not found");
  });
});

describe("POST /api/canonical-registry", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("returns error when basePath is missing", async () => {
    const request = new NextRequest("http://localhost/api/canonical-registry", {
      method: "POST",
      body: JSON.stringify({ folderName: "Resume" }),
    });
    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.error).toBe("Missing required parameter: basePath");
  });

  it("returns error when folderName is missing", async () => {
    const request = new NextRequest("http://localhost/api/canonical-registry", {
      method: "POST",
      body: JSON.stringify({ basePath: "/test/path" }),
    });
    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.error).toBe("Missing or invalid parameter: folderName");
  });

  it("returns error for invalid folderName type", async () => {
    const request = new NextRequest("http://localhost/api/canonical-registry", {
      method: "POST",
      body: JSON.stringify({ basePath: "/test/path", folderName: 123 }),
    });
    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.error).toBe("Missing or invalid parameter: folderName");
  });

  it("returns assessment for valid folder", async () => {
    vi.mocked(loadCanonicalRegistry).mockReturnValue({
      registry: { folders: {} },
    });
    vi.mocked(assessFolderWithRegistry).mockReturnValue({
      isInRegistry: false,
      registryEntry: null,
      matchesCategory: true,
      detectedCategory: "employment",
      canonicalInfo: {
        patterns: ["resume"],
        canonicalFolder: "Resumes",
        parentFolder: "Employment",
      },
      reasoning: ["Detected as employment category"],
      confidence: 0.5,
    });

    const request = new NextRequest("http://localhost/api/canonical-registry", {
      method: "POST",
      body: JSON.stringify({
        basePath: "/test/path",
        folderName: "Resume",
        dominantCategory: "employment",
      }),
    });
    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.folderName).toBe("Resume");
    expect(data.assessment).toBeDefined();
    expect(data.assessment.matchesCategory).toBe(true);
    expect(data.registryAvailable).toBe(true);
  });

  it("handles invalid JSON body", async () => {
    const request = new NextRequest("http://localhost/api/canonical-registry", {
      method: "POST",
      body: "invalid json",
    });
    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.error).toBe("Invalid JSON body");
  });

  it("includes registry availability in response", async () => {
    vi.mocked(loadCanonicalRegistry).mockReturnValue({
      registry: null,
      error: "File not found",
    });
    vi.mocked(assessFolderWithRegistry).mockReturnValue({
      isInRegistry: false,
      registryEntry: null,
      matchesCategory: false,
      detectedCategory: null,
      canonicalInfo: null,
      reasoning: ["Registry not available"],
      confidence: 0,
    });

    const request = new NextRequest("http://localhost/api/canonical-registry", {
      method: "POST",
      body: JSON.stringify({
        basePath: "/test/path",
        folderName: "Resume",
      }),
    });
    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.registryAvailable).toBe(false);
    expect(data.registryError).toBe("File not found");
  });
});
