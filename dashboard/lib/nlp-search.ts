/**
 * Natural Language Search Parser
 *
 * Parses natural language queries to extract:
 * - Category keywords (e.g., "verizon bill" → category: "utility_bill")
 * - Date keywords (e.g., "from 2024" → years: [2024])
 * - Entity keywords (e.g., "verizon" → organization: "verizon")
 */

// Category keyword mappings - maps common search terms to AI categories
export const CATEGORY_KEYWORDS: Record<string, string[]> = {
  // Utility bills
  utility_bill: [
    "bill",
    "bills",
    "utility",
    "utilities",
    "verizon",
    "att",
    "at&t",
    "comcast",
    "xfinity",
    "spectrum",
    "electric",
    "gas",
    "water",
    "phone",
    "internet",
    "cable",
  ],
  // Tax documents
  tax_document: [
    "tax",
    "taxes",
    "1099",
    "w2",
    "w-2",
    "1040",
    "irs",
    "return",
    "refund",
  ],
  // VA Claims
  va_claims: [
    "va",
    "veteran",
    "veterans",
    "vba",
    "vha",
    "disability",
    "claim",
    "claims",
    "dd-214",
    "dd214",
    "military",
  ],
  // Invoices
  invoice: [
    "invoice",
    "invoices",
    "receipt",
    "receipts",
    "purchase",
    "order",
  ],
  // Bank statements
  bank_statement: [
    "bank",
    "statement",
    "statements",
    "account",
    "checking",
    "savings",
    "deposit",
  ],
  // Contracts
  contract: [
    "contract",
    "contracts",
    "agreement",
    "agreements",
    "lease",
    "rental",
  ],
  // Medical records
  medical_record: [
    "medical",
    "health",
    "doctor",
    "hospital",
    "prescription",
    "lab",
    "test",
    "results",
  ],
  // Employment
  employment: [
    "employment",
    "job",
    "resume",
    "cv",
    "offer",
    "letter",
    "salary",
    "paycheck",
    "paystub",
  ],
  // Insurance
  insurance: [
    "insurance",
    "policy",
    "coverage",
    "premium",
    "claim",
    "auto",
    "home",
    "life",
  ],
  // Legal documents
  legal: [
    "legal",
    "court",
    "lawsuit",
    "attorney",
    "lawyer",
    "case",
    "filing",
  ],
};

// Organization name patterns for entity extraction
export const ORGANIZATION_PATTERNS: string[] = [
  "verizon",
  "att",
  "at&t",
  "comcast",
  "xfinity",
  "amazon",
  "apple",
  "google",
  "microsoft",
  "walmart",
  "target",
  "costco",
  "chase",
  "bank of america",
  "wells fargo",
  "citi",
  "capital one",
  "irs",
  "va",
  "ssa",
  "social security",
];

// Parsed query result interface
export interface ParsedQuery {
  // Original query string
  originalQuery: string;
  // Cleaned query for text search
  searchTerms: string[];
  // Detected AI category (if any)
  category: string | null;
  // Detected years for date filtering
  years: number[];
  // Detected organizations
  organizations: string[];
  // Detected people names (basic extraction)
  people: string[];
  // Whether this appears to be a natural language query
  isNaturalLanguage: boolean;
}

/**
 * Parse a natural language query into structured search parameters
 */
export function parseNaturalLanguageQuery(query: string): ParsedQuery {
  const result: ParsedQuery = {
    originalQuery: query,
    searchTerms: [],
    category: null,
    years: [],
    organizations: [],
    people: [],
    isNaturalLanguage: false,
  };

  if (!query || !query.trim()) {
    return result;
  }

  const normalizedQuery = query.toLowerCase().trim();

  // Detect if this is a natural language query (contains question words or common phrases)
  result.isNaturalLanguage = detectNaturalLanguage(normalizedQuery);

  // Extract years from the query
  result.years = extractYears(normalizedQuery);

  // Extract organizations
  result.organizations = extractOrganizations(normalizedQuery);

  // Detect category from keywords
  result.category = detectCategory(normalizedQuery);

  // Extract remaining search terms (remove common words and extracted items)
  result.searchTerms = extractSearchTerms(normalizedQuery, result);

  return result;
}

/**
 * Detect if query is natural language vs simple keyword search
 */
export function detectNaturalLanguage(query: string): boolean {
  const naturalLanguageIndicators = [
    "show me",
    "find",
    "search for",
    "looking for",
    "where is",
    "where are",
    "what",
    "which",
    "that is",
    "that are",
    "from",
    "in",
    "with",
    "about",
    "?",
  ];

  return naturalLanguageIndicators.some((indicator) =>
    query.includes(indicator)
  );
}

/**
 * Extract years from query
 * Handles formats like: "2024", "from 2024", "in 2023", "2023-2024"
 */
export function extractYears(query: string): number[] {
  const years: number[] = [];

  // Match 4-digit years in the 1900-2099 range
  const yearPattern = /\b(19|20)\d{2}\b/g;
  const matches = query.match(yearPattern);

  if (matches) {
    for (const match of matches) {
      const year = parseInt(match, 10);
      if (!years.includes(year)) {
        years.push(year);
      }
    }
  }

  // Sort years descending (most recent first)
  return years.sort((a, b) => b - a);
}

/**
 * Extract organization names from query
 */
export function extractOrganizations(query: string): string[] {
  const organizations: string[] = [];

  for (const org of ORGANIZATION_PATTERNS) {
    // Use word boundary matching for organizations
    const pattern = new RegExp(`\\b${escapeRegExp(org)}\\b`, "i");
    if (pattern.test(query)) {
      // Capitalize the organization name
      organizations.push(capitalizeOrg(org));
    }
  }

  return organizations;
}

/**
 * Detect AI category from query keywords
 */
export function detectCategory(query: string): string | null {
  const words = query.split(/\s+/);
  const categoryScores: Record<string, number> = {};

  for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
    let score = 0;
    for (const keyword of keywords) {
      // Check if the keyword is in the query
      if (keyword.includes(" ")) {
        // Multi-word keyword - check if phrase exists
        if (query.includes(keyword)) {
          score += 2; // Higher weight for phrase match
        }
      } else {
        // Single word - check word boundaries
        if (words.includes(keyword)) {
          score += 1;
        }
      }
    }
    if (score > 0) {
      categoryScores[category] = score;
    }
  }

  // Return the category with the highest score, or null if no matches
  const entries = Object.entries(categoryScores);
  if (entries.length === 0) {
    return null;
  }

  entries.sort((a, b) => b[1] - a[1]);
  return entries[0][0];
}

/**
 * Extract search terms by removing common words and extracted entities
 */
export function extractSearchTerms(
  query: string,
  parsed: ParsedQuery
): string[] {
  // Common words to filter out
  const stopWords = new Set([
    "show",
    "me",
    "find",
    "search",
    "for",
    "looking",
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "that",
    "which",
    "what",
    "where",
    "when",
    "how",
    "from",
    "in",
    "on",
    "at",
    "to",
    "of",
    "with",
    "by",
    "my",
    "all",
    "any",
    "file",
    "files",
    "document",
    "documents",
    "please",
    "can",
    "you",
    "i",
    "want",
    "need",
  ]);

  // Split query into words
  let words = query.split(/\s+/).filter((word) => word.length > 1);

  // Remove stop words
  words = words.filter((word) => !stopWords.has(word));

  // Remove extracted years
  words = words.filter((word) => !parsed.years.includes(parseInt(word, 10)));

  // Remove extracted organizations (case-insensitive)
  const orgLower = parsed.organizations.map((o) => o.toLowerCase());
  words = words.filter((word) => !orgLower.includes(word.toLowerCase()));

  // Remove category keywords that were detected
  if (parsed.category) {
    const categoryKeywords = CATEGORY_KEYWORDS[parsed.category] || [];
    words = words.filter((word) => !categoryKeywords.includes(word));
  }

  // Remove duplicates
  return [...new Set(words)];
}

/**
 * Escape special regex characters
 */
function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Capitalize organization name properly
 */
function capitalizeOrg(org: string): string {
  // Handle special cases
  const specialCases: Record<string, string> = {
    "at&t": "AT&T",
    att: "AT&T",
    irs: "IRS",
    va: "VA",
    ssa: "SSA",
  };

  if (specialCases[org.toLowerCase()]) {
    return specialCases[org.toLowerCase()];
  }

  // Title case for others
  return org
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

/**
 * Build search description for display
 */
export function buildSearchDescription(parsed: ParsedQuery): string {
  const parts: string[] = [];

  if (parsed.category) {
    parts.push(`category: ${formatCategoryName(parsed.category)}`);
  }

  if (parsed.years.length > 0) {
    parts.push(
      `year${parsed.years.length > 1 ? "s" : ""}: ${parsed.years.join(", ")}`
    );
  }

  if (parsed.organizations.length > 0) {
    parts.push(`organization: ${parsed.organizations.join(", ")}`);
  }

  if (parsed.searchTerms.length > 0) {
    parts.push(`keywords: ${parsed.searchTerms.join(", ")}`);
  }

  if (parts.length === 0) {
    return `Searching for: "${parsed.originalQuery}"`;
  }

  return `Filters: ${parts.join(" | ")}`;
}

/**
 * Format category name for display (snake_case to Title Case)
 */
export function formatCategoryName(category: string): string {
  return category
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
