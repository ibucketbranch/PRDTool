/**
 * Canonical registry integration for Dashboard Phase 5
 *
 * Provides functions to read and use the canonical registry from the Python organizer.
 * The canonical registry is stored at .organizer/canonical_folders.json.
 */

import { existsSync, readFileSync } from "fs";
import path from "path";

// ============================================================================
// Types
// ============================================================================

/**
 * A folder entry from the canonical registry
 */
export interface CanonicalFolderEntry {
  path: string;
  normalizedName: string;
  category: string;
}

/**
 * The canonical registry data structure
 */
export interface CanonicalRegistry {
  folders: Record<string, CanonicalFolderEntry>;
}

/**
 * Category information from the Python category_mapper
 * Synchronized with organizer/category_mapper.py CONSOLIDATION_CATEGORIES
 */
export interface CategoryInfo {
  patterns: string[];
  canonicalFolder: string;
  parentFolder: string;
}

/**
 * Result from loading the canonical registry
 */
export interface CanonicalRegistryResult {
  registry: CanonicalRegistry | null;
  error?: string;
}

// ============================================================================
// Category Patterns (synchronized with Python category_mapper.py)
// ============================================================================

/**
 * Category patterns synchronized with organizer/category_mapper.py CONSOLIDATION_CATEGORIES
 * This ensures consistency between the Python organizer and the dashboard.
 */
export const PYTHON_CATEGORY_PATTERNS: Record<string, CategoryInfo> = {
  employment: {
    patterns: [
      "resume",
      "resumes",
      "cv",
      "cover letter",
      "cover_letter",
      "coverletter",
      "job",
      "application",
      "job application",
      "employment",
      "career",
      "interview",
    ],
    canonicalFolder: "Resumes",
    parentFolder: "Employment",
  },
  finances: {
    patterns: [
      "tax",
      "taxes",
      "tax return",
      "tax_return",
      "taxreturn",
      "invoice",
      "invoices",
      "receipt",
      "receipts",
      "budget",
      "financial",
      "finance",
      "bank",
      "banking",
      "statement",
      "expense",
      "expenses",
    ],
    canonicalFolder: "Taxes",
    parentFolder: "Finances Bin",
  },
  legal: {
    patterns: [
      "contract",
      "contracts",
      "agreement",
      "agreements",
      "deed",
      "deeds",
      "legal",
      "lease",
      "nda",
      "terms",
      "policy",
      "policies",
      "license",
      "licenses",
    ],
    canonicalFolder: "Contracts",
    parentFolder: "Contracts",
  },
  health: {
    patterns: [
      "medical",
      "doctor",
      "prescription",
      "prescriptions",
      "health",
      "hospital",
      "insurance",
      "dental",
      "vision",
      "lab",
      "test result",
      "vaccination",
      "immunization",
    ],
    canonicalFolder: "Medical",
    parentFolder: "Health",
  },
  identity: {
    patterns: [
      "passport",
      "id",
      "identification",
      "license",
      "driver",
      "ssn",
      "social security",
      "birth certificate",
      "citizenship",
      "visa",
    ],
    canonicalFolder: "Identity",
    parentFolder: "Personal",
  },
  education: {
    patterns: [
      "diploma",
      "degree",
      "transcript",
      "certificate",
      "certification",
      "school",
      "college",
      "university",
      "academic",
      "graduation",
    ],
    canonicalFolder: "Education",
    parentFolder: "Education",
  },
};

// ============================================================================
// Helper functions
// ============================================================================

/**
 * Normalize a folder name for comparison (matching Python fuzzy_matcher.py)
 * - Convert to lowercase
 * - Remove underscores and numbers
 * - Singularize basic plurals
 */
export function normalizeForComparison(name: string): string {
  if (!name) return "";

  let normalized = name.toLowerCase();

  // Remove trailing numbers (e.g., _1, _2023, -2)
  normalized = normalized.replace(/[_-]?\d+$/, "");

  // Replace underscores and hyphens with spaces
  normalized = normalized.replace(/[_-]/g, " ");

  // Remove extra spaces
  normalized = normalized.replace(/\s+/g, " ").trim();

  // Basic singularization (matching Python _singularize)
  if (normalized.endsWith("ies")) {
    normalized = normalized.slice(0, -3) + "y";
  } else if (normalized.endsWith("es") && !normalized.endsWith("ses")) {
    normalized = normalized.slice(0, -2);
  } else if (normalized.endsWith("s") && !normalized.endsWith("ss")) {
    normalized = normalized.slice(0, -1);
  }

  return normalized;
}

/**
 * Calculate similarity score between two strings using bigram similarity (Dice coefficient)
 * Matching Python fuzzy_matcher.py get_similarity_score
 */
export function calculateSimilarity(str1: string, str2: string): number {
  const s1 = normalizeForComparison(str1);
  const s2 = normalizeForComparison(str2);

  if (s1 === s2) return 1.0;
  if (!s1 || !s2) return 0.0;

  // Bigram similarity (Dice coefficient)
  const bigrams1 = new Set<string>();
  const bigrams2 = new Set<string>();

  for (let i = 0; i < s1.length - 1; i++) {
    bigrams1.add(s1.slice(i, i + 2));
  }
  for (let i = 0; i < s2.length - 1; i++) {
    bigrams2.add(s2.slice(i, i + 2));
  }

  if (bigrams1.size === 0 && bigrams2.size === 0) return 1.0;
  if (bigrams1.size === 0 || bigrams2.size === 0) return 0.0;

  let intersection = 0;
  for (const bigram of bigrams1) {
    if (bigrams2.has(bigram)) {
      intersection++;
    }
  }

  return (2 * intersection) / (bigrams1.size + bigrams2.size);
}

/**
 * Check if two folder names are similar (matching Python fuzzy_matcher.py)
 */
export function areSimilarFolders(
  name1: string,
  name2: string,
  threshold: number = 0.8
): boolean {
  return calculateSimilarity(name1, name2) >= threshold;
}

// ============================================================================
// Main functions
// ============================================================================

/**
 * Load the canonical registry from the .organizer directory
 *
 * @param basePath - Base path where .organizer directory is located
 * @returns The canonical registry or error
 */
export function loadCanonicalRegistry(basePath: string): CanonicalRegistryResult {
  try {
    const registryPath = path.join(basePath, ".organizer", "canonical_folders.json");

    if (!existsSync(registryPath)) {
      return { registry: null, error: "Canonical registry file not found" };
    }

    const content = readFileSync(registryPath, "utf-8");
    const data = JSON.parse(content) as { folders?: Record<string, unknown> };

    if (!data.folders) {
      return { registry: { folders: {} } };
    }

    // Parse folder entries
    const folders: Record<string, CanonicalFolderEntry> = {};
    for (const [key, entry] of Object.entries(data.folders)) {
      const entryData = entry as Record<string, unknown>;
      folders[key] = {
        path: String(entryData.path ?? ""),
        normalizedName: String(entryData.normalized_name ?? ""),
        category: String(entryData.category ?? ""),
      };
    }

    return { registry: { folders } };
  } catch (err) {
    return {
      registry: null,
      error: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

/**
 * Find a similar folder in the canonical registry
 *
 * @param folderName - The folder name to search for
 * @param registry - The canonical registry to search
 * @param threshold - Similarity threshold (default 0.8)
 * @returns The matching entry or null
 */
export function findSimilarInRegistry(
  folderName: string,
  registry: CanonicalRegistry,
  threshold: number = 0.8
): CanonicalFolderEntry | null {
  const normalized = normalizeForComparison(folderName);

  // Check for exact normalized match first
  if (registry.folders[normalized]) {
    return registry.folders[normalized];
  }

  // Check for similar folders
  for (const entry of Object.values(registry.folders)) {
    const entryName = path.basename(entry.path);
    if (areSimilarFolders(folderName, entryName, threshold)) {
      return entry;
    }
  }

  return null;
}

/**
 * Get the category for a folder name using Python-aligned patterns
 *
 * @param folderName - The folder name to categorize
 * @returns The category key or null
 */
export function getCategoryFromPythonPatterns(folderName: string): string | null {
  const normalized = normalizeForComparison(folderName);

  for (const [categoryKey, categoryInfo] of Object.entries(
    PYTHON_CATEGORY_PATTERNS
  )) {
    for (const pattern of categoryInfo.patterns) {
      const patternNormalized = normalizeForComparison(pattern);
      if (normalized === patternNormalized || normalized.includes(patternNormalized)) {
        return categoryKey;
      }
    }
  }

  return null;
}

/**
 * Get the canonical folder info for a category
 *
 * @param categoryKey - The category key
 * @returns Category info or null
 */
export function getCanonicalFolderForCategory(
  categoryKey: string
): CategoryInfo | null {
  return PYTHON_CATEGORY_PATTERNS[categoryKey] || null;
}

/**
 * Check if a folder name matches a category's canonical folder
 *
 * @param folderName - The folder name to check
 * @param categoryKey - The category key to check against
 * @returns True if the folder matches the category's canonical structure
 */
export function folderMatchesCategoryCanonical(
  folderName: string,
  categoryKey: string
): boolean {
  const categoryInfo = PYTHON_CATEGORY_PATTERNS[categoryKey];
  if (!categoryInfo) return false;

  const normalizedFolder = normalizeForComparison(folderName);
  const normalizedCanonical = normalizeForComparison(categoryInfo.canonicalFolder);
  const normalizedParent = normalizeForComparison(categoryInfo.parentFolder);

  // Check if folder name matches canonical folder or parent folder
  return (
    normalizedFolder === normalizedCanonical ||
    normalizedFolder === normalizedParent ||
    areSimilarFolders(folderName, categoryInfo.canonicalFolder, 0.8) ||
    areSimilarFolders(folderName, categoryInfo.parentFolder, 0.8)
  );
}

/**
 * Assess a folder using the canonical registry and Python-aligned patterns
 *
 * @param folderName - The folder name to assess
 * @param registry - The canonical registry
 * @param dominantCategory - The dominant AI category of files in the folder
 * @returns Assessment results
 */
export function assessFolderWithRegistry(
  folderName: string,
  registry: CanonicalRegistry | null,
  dominantCategory: string | null
): {
  isInRegistry: boolean;
  registryEntry: CanonicalFolderEntry | null;
  matchesCategory: boolean;
  detectedCategory: string | null;
  canonicalInfo: CategoryInfo | null;
  reasoning: string[];
  confidence: number;
} {
  const reasoning: string[] = [];
  let confidence = 0;
  let isInRegistry = false;
  let registryEntry: CanonicalFolderEntry | null = null;
  let matchesCategory = false;
  let detectedCategory: string | null = null;
  let canonicalInfo: CategoryInfo | null = null;

  // Step 1: Check canonical registry
  if (registry) {
    registryEntry = findSimilarInRegistry(folderName, registry, 0.8);
    if (registryEntry) {
      isInRegistry = true;
      reasoning.push(
        `Folder "${folderName}" found in canonical registry as "${registryEntry.path}"`
      );
      confidence += 0.3;

      // If registry entry has a category, use it
      if (registryEntry.category) {
        reasoning.push(`Registry category: "${registryEntry.category}"`);
      }
    } else {
      reasoning.push(`Folder "${folderName}" NOT found in canonical registry`);
    }
  } else {
    reasoning.push("Canonical registry not available");
  }

  // Step 2: Detect category from folder name using Python-aligned patterns
  detectedCategory = getCategoryFromPythonPatterns(folderName);
  if (detectedCategory) {
    canonicalInfo = getCanonicalFolderForCategory(detectedCategory);
    reasoning.push(
      `Folder name suggests category "${detectedCategory}" → canonical: "${canonicalInfo?.canonicalFolder}"`
    );
    confidence += 0.2;
  }

  // Step 3: Check if folder matches dominant AI category
  if (dominantCategory) {
    // Normalize the AI category for comparison
    const aiCategoryKey = getCategoryFromPythonPatterns(dominantCategory);
    if (aiCategoryKey) {
      if (detectedCategory === aiCategoryKey) {
        matchesCategory = true;
        reasoning.push(
          `Folder category matches AI category "${dominantCategory}"`
        );
        confidence += 0.3;
      } else if (detectedCategory) {
        reasoning.push(
          `MISMATCH: Folder suggests "${detectedCategory}" but files are "${dominantCategory}"`
        );
      }

      // Check if folder name directly matches canonical structure
      if (folderMatchesCategoryCanonical(folderName, aiCategoryKey)) {
        matchesCategory = true;
        reasoning.push(
          `Folder name matches canonical structure for "${dominantCategory}"`
        );
        confidence += 0.2;
      }
    } else {
      // AI category doesn't map to our patterns, do direct comparison
      const normalizedFolder = normalizeForComparison(folderName);
      const normalizedCategory = normalizeForComparison(dominantCategory);
      if (normalizedFolder.includes(normalizedCategory) ||
          normalizedCategory.includes(normalizedFolder)) {
        matchesCategory = true;
        reasoning.push(`Folder name contains AI category "${dominantCategory}"`);
        confidence += 0.2;
      }
    }
  }

  return {
    isInRegistry,
    registryEntry,
    matchesCategory,
    detectedCategory,
    canonicalInfo,
    reasoning,
    confidence: Math.min(confidence, 1.0),
  };
}
