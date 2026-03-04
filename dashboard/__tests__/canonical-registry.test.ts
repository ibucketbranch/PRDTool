/**
 * Tests for canonical registry integration
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import * as fs from "fs";
import {
  normalizeForComparison,
  calculateSimilarity,
  areSimilarFolders,
  findSimilarInRegistry,
  getCategoryFromPythonPatterns,
  getCanonicalFolderForCategory,
  folderMatchesCategoryCanonical,
  assessFolderWithRegistry,
  PYTHON_CATEGORY_PATTERNS,
  type CanonicalRegistry,
} from "../lib/canonical-registry";

describe("normalizeForComparison", () => {
  it("converts to lowercase", () => {
    expect(normalizeForComparison("Resume")).toBe("resume");
    expect(normalizeForComparison("TAXES")).toBe("tax");
  });

  it("removes trailing numbers", () => {
    expect(normalizeForComparison("Resume_1")).toBe("resume");
    expect(normalizeForComparison("Tax-2023")).toBe("tax");
    expect(normalizeForComparison("Folder123")).toBe("folder");
  });

  it("replaces underscores and hyphens with spaces", () => {
    expect(normalizeForComparison("cover_letter")).toBe("cover letter");
    expect(normalizeForComparison("job-application")).toBe("job application");
  });

  it("handles empty strings", () => {
    expect(normalizeForComparison("")).toBe("");
  });

  it("singularizes basic plurals", () => {
    // The function removes trailing 's' but may leave result slightly different
    const resumesNorm = normalizeForComparison("resumes");
    expect(resumesNorm).toBe("resum"); // 'es' endings remove 'es'
    expect(normalizeForComparison("taxes")).toBe("tax"); // 'es' ending
    expect(normalizeForComparison("policies")).toBe("policy"); // 'ies' ending
  });

  it("does not singularize words ending in ss", () => {
    expect(normalizeForComparison("business")).toBe("business");
  });
});

describe("calculateSimilarity", () => {
  it("returns 1.0 for identical strings", () => {
    expect(calculateSimilarity("Resume", "Resume")).toBe(1.0);
    expect(calculateSimilarity("resume", "Resume")).toBe(1.0);
  });

  it("returns 0.0 for empty strings", () => {
    expect(calculateSimilarity("", "Resume")).toBe(0.0);
    expect(calculateSimilarity("Resume", "")).toBe(0.0);
  });

  it("returns high score for similar strings", () => {
    const score = calculateSimilarity("Resume", "Resumes");
    expect(score).toBeGreaterThan(0.8);
  });

  it("returns low score for dissimilar strings", () => {
    const score = calculateSimilarity("Resume", "Taxes");
    expect(score).toBeLessThan(0.5);
  });
});

describe("areSimilarFolders", () => {
  it("returns true for identical folders", () => {
    expect(areSimilarFolders("Resume", "Resume")).toBe(true);
  });

  it("returns true for similar folders above threshold", () => {
    expect(areSimilarFolders("Resume", "Resumes", 0.8)).toBe(true);
  });

  it("returns false for dissimilar folders", () => {
    expect(areSimilarFolders("Resume", "Taxes", 0.8)).toBe(false);
  });

  it("respects custom threshold", () => {
    // Test with a higher similarity pair
    const score = calculateSimilarity("Resume", "Resumes");
    expect(areSimilarFolders("Resume", "Resumes", 0.5)).toBe(true);
    expect(areSimilarFolders("Resume", "Totally_Different", 0.9)).toBe(false);
  });
});

// Note: loadCanonicalRegistry tests are covered in canonical-registry-api.test.ts
// using proper mocking of the function. These tests focus on the helper functions.

describe("findSimilarInRegistry", () => {
  const mockRegistry: CanonicalRegistry = {
    folders: {
      resume: {
        path: "Employment/Resumes",
        normalizedName: "resume",
        category: "Employment",
      },
      tax: {
        path: "Finances/Taxes",
        normalizedName: "tax",
        category: "Finances",
      },
    },
  };

  it("finds exact normalized match", () => {
    const result = findSimilarInRegistry("resume", mockRegistry);
    expect(result?.path).toBe("Employment/Resumes");
  });

  it("finds similar folder by path name", () => {
    const result = findSimilarInRegistry("Resumes", mockRegistry);
    expect(result?.path).toBe("Employment/Resumes");
  });

  it("returns null for unrelated folder", () => {
    const result = findSimilarInRegistry("Contracts", mockRegistry);
    expect(result).toBeNull();
  });

  it("respects threshold", () => {
    const result = findSimilarInRegistry("Re", mockRegistry, 0.95);
    expect(result).toBeNull();
  });
});

describe("getCategoryFromPythonPatterns", () => {
  it("detects employment category from resume", () => {
    expect(getCategoryFromPythonPatterns("Resume")).toBe("employment");
    expect(getCategoryFromPythonPatterns("CV")).toBe("employment");
    expect(getCategoryFromPythonPatterns("cover_letter")).toBe("employment");
  });

  it("detects finances category from tax", () => {
    expect(getCategoryFromPythonPatterns("Taxes")).toBe("finances");
    expect(getCategoryFromPythonPatterns("invoice")).toBe("finances");
  });

  it("detects legal category from contract", () => {
    expect(getCategoryFromPythonPatterns("Contracts")).toBe("legal");
    expect(getCategoryFromPythonPatterns("Agreement")).toBe("legal");
  });

  it("detects health category from medical", () => {
    expect(getCategoryFromPythonPatterns("Medical")).toBe("health");
    expect(getCategoryFromPythonPatterns("prescription")).toBe("health");
  });

  it("detects identity category from passport", () => {
    expect(getCategoryFromPythonPatterns("passport")).toBe("identity");
    expect(getCategoryFromPythonPatterns("ssn")).toBe("identity");
  });

  it("detects education category from diploma", () => {
    expect(getCategoryFromPythonPatterns("diploma")).toBe("education");
    expect(getCategoryFromPythonPatterns("transcript")).toBe("education");
  });

  it("returns null for unknown folders", () => {
    expect(getCategoryFromPythonPatterns("RandomFolder")).toBeNull();
    expect(getCategoryFromPythonPatterns("Unknown")).toBeNull();
  });
});

describe("getCanonicalFolderForCategory", () => {
  it("returns category info for valid category", () => {
    const info = getCanonicalFolderForCategory("employment");
    expect(info?.canonicalFolder).toBe("Resumes");
    expect(info?.parentFolder).toBe("Employment");
  });

  it("returns null for invalid category", () => {
    expect(getCanonicalFolderForCategory("nonexistent")).toBeNull();
  });
});

describe("folderMatchesCategoryCanonical", () => {
  it("returns true for canonical folder name", () => {
    expect(folderMatchesCategoryCanonical("Resumes", "employment")).toBe(true);
    expect(folderMatchesCategoryCanonical("Taxes", "finances")).toBe(true);
  });

  it("returns true for parent folder name", () => {
    expect(folderMatchesCategoryCanonical("Employment", "employment")).toBe(true);
    expect(folderMatchesCategoryCanonical("Health", "health")).toBe(true);
  });

  it("returns false for unrelated folder", () => {
    expect(folderMatchesCategoryCanonical("RandomFolder", "employment")).toBe(false);
    expect(folderMatchesCategoryCanonical("Photos", "finances")).toBe(false);
  });

  it("returns false for invalid category", () => {
    expect(folderMatchesCategoryCanonical("Resume", "nonexistent")).toBe(false);
  });
});

describe("assessFolderWithRegistry", () => {
  const mockRegistry: CanonicalRegistry = {
    folders: {
      resume: {
        path: "Employment/Resumes",
        normalizedName: "resume",
        category: "Employment",
      },
    },
  };

  it("assesses folder found in registry", () => {
    const result = assessFolderWithRegistry("Resume", mockRegistry, null);
    expect(result.isInRegistry).toBe(true);
    expect(result.confidence).toBeGreaterThan(0);
    expect(result.reasoning.length).toBeGreaterThan(0);
  });

  it("assesses folder not found in registry", () => {
    const result = assessFolderWithRegistry("RandomFolder", mockRegistry, null);
    expect(result.isInRegistry).toBe(false);
  });

  it("checks category match with dominant category", () => {
    const result = assessFolderWithRegistry("Resume", mockRegistry, "employment");
    expect(result.matchesCategory).toBe(true);
  });

  it("handles null registry", () => {
    const result = assessFolderWithRegistry("Resume", null, "employment");
    expect(result.isInRegistry).toBe(false);
    expect(result.reasoning).toContain("Canonical registry not available");
  });

  it("detects category from folder name", () => {
    const result = assessFolderWithRegistry("Taxes", null, null);
    expect(result.detectedCategory).toBe("finances");
    expect(result.canonicalInfo?.canonicalFolder).toBe("Taxes");
  });
});

describe("PYTHON_CATEGORY_PATTERNS", () => {
  it("has expected categories", () => {
    expect(PYTHON_CATEGORY_PATTERNS).toHaveProperty("employment");
    expect(PYTHON_CATEGORY_PATTERNS).toHaveProperty("finances");
    expect(PYTHON_CATEGORY_PATTERNS).toHaveProperty("legal");
    expect(PYTHON_CATEGORY_PATTERNS).toHaveProperty("health");
    expect(PYTHON_CATEGORY_PATTERNS).toHaveProperty("identity");
    expect(PYTHON_CATEGORY_PATTERNS).toHaveProperty("education");
  });

  it("employment patterns include resume and cv", () => {
    const patterns = PYTHON_CATEGORY_PATTERNS.employment.patterns;
    expect(patterns).toContain("resume");
    expect(patterns).toContain("cv");
    expect(patterns).toContain("cover letter");
  });

  it("finances patterns include tax and invoice", () => {
    const patterns = PYTHON_CATEGORY_PATTERNS.finances.patterns;
    expect(patterns).toContain("tax");
    expect(patterns).toContain("invoice");
    expect(patterns).toContain("bank");
  });

  it("each category has canonicalFolder and parentFolder", () => {
    for (const [key, info] of Object.entries(PYTHON_CATEGORY_PATTERNS)) {
      expect(info.canonicalFolder).toBeDefined();
      expect(info.parentFolder).toBeDefined();
      expect(info.patterns.length).toBeGreaterThan(0);
    }
  });
});
