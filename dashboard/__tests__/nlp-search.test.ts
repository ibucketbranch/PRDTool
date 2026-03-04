import { describe, it, expect } from "vitest";
import {
  parseNaturalLanguageQuery,
  detectNaturalLanguage,
  extractYears,
  extractOrganizations,
  detectCategory,
  extractSearchTerms,
  buildSearchDescription,
  formatCategoryName,
  CATEGORY_KEYWORDS,
  ORGANIZATION_PATTERNS,
  type ParsedQuery,
} from "@/lib/nlp-search";

describe("Natural Language Search Parser", () => {
  describe("parseNaturalLanguageQuery", () => {
    it("should return empty result for empty query", () => {
      const result = parseNaturalLanguageQuery("");
      expect(result.originalQuery).toBe("");
      expect(result.searchTerms).toEqual([]);
      expect(result.category).toBeNull();
      expect(result.years).toEqual([]);
      expect(result.organizations).toEqual([]);
    });

    it("should parse a complete natural language query", () => {
      const query = "Show me a file that is a verizon bill from 2024";
      const result = parseNaturalLanguageQuery(query);

      expect(result.originalQuery).toBe(query);
      expect(result.isNaturalLanguage).toBe(true);
      expect(result.years).toContain(2024);
      expect(result.organizations).toContain("Verizon");
      expect(result.category).toBe("utility_bill");
    });

    it("should parse tax document query", () => {
      const result = parseNaturalLanguageQuery("Find all tax documents from 2023");

      expect(result.category).toBe("tax_document");
      expect(result.years).toContain(2023);
      expect(result.isNaturalLanguage).toBe(true);
    });

    it("should parse VA claims query", () => {
      const result = parseNaturalLanguageQuery("Show me VA claims documents");

      expect(result.category).toBe("va_claims");
      expect(result.isNaturalLanguage).toBe(true);
    });

    it("should parse invoice query with organization", () => {
      const result = parseNaturalLanguageQuery("Find invoices from Amazon");

      expect(result.category).toBe("invoice");
      expect(result.organizations).toContain("Amazon");
      expect(result.isNaturalLanguage).toBe(true);
    });

    it("should parse simple keyword search", () => {
      const result = parseNaturalLanguageQuery("tax 2024");

      expect(result.category).toBe("tax_document");
      expect(result.years).toContain(2024);
      expect(result.isNaturalLanguage).toBe(false);
    });

    it("should handle multiple years in query", () => {
      const result = parseNaturalLanguageQuery("Show documents from 2023 or 2024");

      expect(result.years).toContain(2023);
      expect(result.years).toContain(2024);
      expect(result.years[0]).toBe(2024); // Most recent first
    });

    it("should handle query with question mark", () => {
      const result = parseNaturalLanguageQuery(
        "Show me a file that is a verizon bill from 2024?"
      );

      expect(result.isNaturalLanguage).toBe(true);
      expect(result.years).toContain(2024);
      expect(result.organizations).toContain("Verizon");
    });

    it("should handle bank statement query", () => {
      const result = parseNaturalLanguageQuery("Find all bank statements");

      expect(result.category).toBe("bank_statement");
    });

    it("should handle contract query", () => {
      const result = parseNaturalLanguageQuery("Show me contracts");

      expect(result.category).toBe("contract");
    });
  });

  describe("detectNaturalLanguage", () => {
    it("should detect 'show me' as natural language", () => {
      expect(detectNaturalLanguage("show me tax documents")).toBe(true);
    });

    it("should detect 'find' as natural language", () => {
      expect(detectNaturalLanguage("find invoices")).toBe(true);
    });

    it("should detect 'looking for' as natural language", () => {
      expect(detectNaturalLanguage("looking for tax forms")).toBe(true);
    });

    it("should detect 'from' keyword as natural language", () => {
      expect(detectNaturalLanguage("documents from 2024")).toBe(true);
    });

    it("should detect question marks as natural language", () => {
      expect(detectNaturalLanguage("where is my tax return?")).toBe(true);
    });

    it("should NOT detect simple keyword as natural language", () => {
      expect(detectNaturalLanguage("tax")).toBe(false);
    });

    it("should NOT detect multiple keywords as natural language", () => {
      expect(detectNaturalLanguage("tax 2024 verizon")).toBe(false);
    });
  });

  describe("extractYears", () => {
    it("should extract single year", () => {
      expect(extractYears("documents from 2024")).toEqual([2024]);
    });

    it("should extract multiple years", () => {
      const years = extractYears("tax returns 2022 2023 2024");
      expect(years).toContain(2022);
      expect(years).toContain(2023);
      expect(years).toContain(2024);
    });

    it("should sort years descending", () => {
      const years = extractYears("2020 2024 2022");
      expect(years).toEqual([2024, 2022, 2020]);
    });

    it("should not extract years outside 1900-2099 range", () => {
      const years = extractYears("year 1899 and 2100");
      expect(years).toEqual([]);
    });

    it("should extract years in 1900s", () => {
      const years = extractYears("document from 1999");
      expect(years).toEqual([1999]);
    });

    it("should not duplicate years", () => {
      const years = extractYears("2024 tax 2024 returns 2024");
      expect(years).toEqual([2024]);
    });

    it("should return empty array for no years", () => {
      expect(extractYears("tax documents")).toEqual([]);
    });
  });

  describe("extractOrganizations", () => {
    it("should extract Verizon", () => {
      const orgs = extractOrganizations("verizon bill");
      expect(orgs).toContain("Verizon");
    });

    it("should extract AT&T in various forms", () => {
      expect(extractOrganizations("att bill")).toContain("AT&T");
      expect(extractOrganizations("at&t statement")).toContain("AT&T");
    });

    it("should extract Amazon", () => {
      const orgs = extractOrganizations("amazon invoice");
      expect(orgs).toContain("Amazon");
    });

    it("should extract IRS", () => {
      const orgs = extractOrganizations("irs document");
      expect(orgs).toContain("IRS");
    });

    it("should extract VA", () => {
      const orgs = extractOrganizations("va claims");
      expect(orgs).toContain("VA");
    });

    it("should extract multiple organizations", () => {
      const orgs = extractOrganizations("verizon and amazon invoices");
      expect(orgs).toContain("Verizon");
      expect(orgs).toContain("Amazon");
    });

    it("should be case insensitive", () => {
      expect(extractOrganizations("VERIZON")).toContain("Verizon");
      expect(extractOrganizations("VeRiZoN")).toContain("Verizon");
    });

    it("should return empty array for no organizations", () => {
      expect(extractOrganizations("tax documents")).toEqual([]);
    });

    it("should not match partial words", () => {
      // "amazon" should match but "amazonish" should not
      const orgs = extractOrganizations("my amazon order");
      expect(orgs).toContain("Amazon");
    });
  });

  describe("detectCategory", () => {
    it("should detect utility_bill category", () => {
      expect(detectCategory("verizon bill")).toBe("utility_bill");
      expect(detectCategory("phone bill")).toBe("utility_bill");
      expect(detectCategory("electric utility")).toBe("utility_bill");
    });

    it("should detect tax_document category", () => {
      expect(detectCategory("tax return")).toBe("tax_document");
      expect(detectCategory("1099 form")).toBe("tax_document");
      expect(detectCategory("w2 document")).toBe("tax_document");
    });

    it("should detect va_claims category", () => {
      expect(detectCategory("va claims")).toBe("va_claims");
      expect(detectCategory("veteran disability")).toBe("va_claims");
      expect(detectCategory("dd-214")).toBe("va_claims");
    });

    it("should detect invoice category", () => {
      expect(detectCategory("amazon invoice")).toBe("invoice");
      expect(detectCategory("purchase receipt")).toBe("invoice");
    });

    it("should detect bank_statement category", () => {
      expect(detectCategory("bank statement")).toBe("bank_statement");
      expect(detectCategory("checking account")).toBe("bank_statement");
    });

    it("should detect contract category", () => {
      expect(detectCategory("rental agreement")).toBe("contract");
      expect(detectCategory("lease contract")).toBe("contract");
    });

    it("should return null for no category match", () => {
      expect(detectCategory("random words")).toBeNull();
    });

    it("should prioritize category with more keyword matches", () => {
      // "tax return" has two keywords from tax_document: "tax" and "return"
      expect(detectCategory("tax return form")).toBe("tax_document");
      // "phone bill" has two keywords from utility_bill: "phone" and "bill"
      expect(detectCategory("phone bill payment")).toBe("utility_bill");
    });
  });

  describe("extractSearchTerms", () => {
    it("should remove stop words", () => {
      const parsed: ParsedQuery = {
        originalQuery: "show me the tax documents",
        searchTerms: [],
        category: "tax_document",
        years: [],
        organizations: [],
        people: [],
        isNaturalLanguage: true,
      };

      const terms = extractSearchTerms("show me the tax documents", parsed);
      expect(terms).not.toContain("show");
      expect(terms).not.toContain("me");
      expect(terms).not.toContain("the");
    });

    it("should remove extracted years", () => {
      const parsed: ParsedQuery = {
        originalQuery: "tax 2024",
        searchTerms: [],
        category: "tax_document",
        years: [2024],
        organizations: [],
        people: [],
        isNaturalLanguage: false,
      };

      const terms = extractSearchTerms("tax 2024", parsed);
      expect(terms).not.toContain("2024");
    });

    it("should remove extracted organizations", () => {
      const parsed: ParsedQuery = {
        originalQuery: "verizon bill",
        searchTerms: [],
        category: "utility_bill",
        years: [],
        organizations: ["Verizon"],
        people: [],
        isNaturalLanguage: false,
      };

      const terms = extractSearchTerms("verizon bill", parsed);
      expect(terms).not.toContain("verizon");
    });

    it("should remove category keywords", () => {
      const parsed: ParsedQuery = {
        originalQuery: "tax document",
        searchTerms: [],
        category: "tax_document",
        years: [],
        organizations: [],
        people: [],
        isNaturalLanguage: false,
      };

      const terms = extractSearchTerms("tax document", parsed);
      expect(terms).not.toContain("tax");
    });

    it("should return unique terms", () => {
      const parsed: ParsedQuery = {
        originalQuery: "test test test",
        searchTerms: [],
        category: null,
        years: [],
        organizations: [],
        people: [],
        isNaturalLanguage: false,
      };

      const terms = extractSearchTerms("test test test", parsed);
      expect(terms.filter((t) => t === "test").length).toBe(1);
    });
  });

  describe("buildSearchDescription", () => {
    it("should build description with category", () => {
      const parsed: ParsedQuery = {
        originalQuery: "tax documents",
        searchTerms: [],
        category: "tax_document",
        years: [],
        organizations: [],
        people: [],
        isNaturalLanguage: false,
      };

      const desc = buildSearchDescription(parsed);
      expect(desc).toContain("category: Tax Document");
    });

    it("should build description with years", () => {
      const parsed: ParsedQuery = {
        originalQuery: "documents 2024",
        searchTerms: [],
        category: null,
        years: [2024],
        organizations: [],
        people: [],
        isNaturalLanguage: false,
      };

      const desc = buildSearchDescription(parsed);
      expect(desc).toContain("year: 2024");
    });

    it("should build description with multiple years", () => {
      const parsed: ParsedQuery = {
        originalQuery: "documents 2023 2024",
        searchTerms: [],
        category: null,
        years: [2024, 2023],
        organizations: [],
        people: [],
        isNaturalLanguage: false,
      };

      const desc = buildSearchDescription(parsed);
      expect(desc).toContain("years: 2024, 2023");
    });

    it("should build description with organization", () => {
      const parsed: ParsedQuery = {
        originalQuery: "verizon",
        searchTerms: [],
        category: null,
        years: [],
        organizations: ["Verizon"],
        people: [],
        isNaturalLanguage: false,
      };

      const desc = buildSearchDescription(parsed);
      expect(desc).toContain("organization: Verizon");
    });

    it("should build description with search terms", () => {
      const parsed: ParsedQuery = {
        originalQuery: "important stuff",
        searchTerms: ["important", "stuff"],
        category: null,
        years: [],
        organizations: [],
        people: [],
        isNaturalLanguage: false,
      };

      const desc = buildSearchDescription(parsed);
      expect(desc).toContain("keywords: important, stuff");
    });

    it("should fall back to original query when no filters", () => {
      const parsed: ParsedQuery = {
        originalQuery: "xyz",
        searchTerms: [],
        category: null,
        years: [],
        organizations: [],
        people: [],
        isNaturalLanguage: false,
      };

      const desc = buildSearchDescription(parsed);
      expect(desc).toContain('Searching for: "xyz"');
    });

    it("should combine multiple filters", () => {
      const parsed: ParsedQuery = {
        originalQuery: "verizon bill 2024",
        searchTerms: [],
        category: "utility_bill",
        years: [2024],
        organizations: ["Verizon"],
        people: [],
        isNaturalLanguage: false,
      };

      const desc = buildSearchDescription(parsed);
      expect(desc).toContain("category: Utility Bill");
      expect(desc).toContain("year: 2024");
      expect(desc).toContain("organization: Verizon");
    });
  });

  describe("formatCategoryName", () => {
    it("should format snake_case to Title Case", () => {
      expect(formatCategoryName("tax_document")).toBe("Tax Document");
      expect(formatCategoryName("utility_bill")).toBe("Utility Bill");
      expect(formatCategoryName("va_claims")).toBe("Va Claims");
    });

    it("should handle single word", () => {
      expect(formatCategoryName("invoice")).toBe("Invoice");
    });

    it("should handle multiple underscores", () => {
      expect(formatCategoryName("some_long_category_name")).toBe(
        "Some Long Category Name"
      );
    });
  });

  describe("CATEGORY_KEYWORDS constant", () => {
    it("should have utility_bill category with expected keywords", () => {
      expect(CATEGORY_KEYWORDS.utility_bill).toContain("bill");
      expect(CATEGORY_KEYWORDS.utility_bill).toContain("verizon");
    });

    it("should have tax_document category with expected keywords", () => {
      expect(CATEGORY_KEYWORDS.tax_document).toContain("tax");
      expect(CATEGORY_KEYWORDS.tax_document).toContain("1099");
      expect(CATEGORY_KEYWORDS.tax_document).toContain("w2");
    });

    it("should have va_claims category with expected keywords", () => {
      expect(CATEGORY_KEYWORDS.va_claims).toContain("va");
      expect(CATEGORY_KEYWORDS.va_claims).toContain("veteran");
      expect(CATEGORY_KEYWORDS.va_claims).toContain("dd-214");
    });
  });

  describe("ORGANIZATION_PATTERNS constant", () => {
    it("should include major organizations", () => {
      expect(ORGANIZATION_PATTERNS).toContain("verizon");
      expect(ORGANIZATION_PATTERNS).toContain("amazon");
      expect(ORGANIZATION_PATTERNS).toContain("chase");
      expect(ORGANIZATION_PATTERNS).toContain("irs");
    });
  });

  describe("PRD example queries", () => {
    it('should parse "Show me a file that is a verizon bill from 2024?"', () => {
      const result = parseNaturalLanguageQuery(
        "Show me a file that is a verizon bill from 2024?"
      );

      expect(result.isNaturalLanguage).toBe(true);
      expect(result.category).toBe("utility_bill");
      expect(result.years).toContain(2024);
      expect(result.organizations).toContain("Verizon");
    });

    it('should parse "Find all tax documents from 2023"', () => {
      const result = parseNaturalLanguageQuery(
        "Find all tax documents from 2023"
      );

      expect(result.category).toBe("tax_document");
      expect(result.years).toContain(2023);
    });

    it('should parse "Show me VA claims documents"', () => {
      const result = parseNaturalLanguageQuery("Show me VA claims documents");

      expect(result.category).toBe("va_claims");
    });

    it('should parse "Find invoices from Amazon"', () => {
      const result = parseNaturalLanguageQuery("Find invoices from Amazon");

      expect(result.category).toBe("invoice");
      expect(result.organizations).toContain("Amazon");
    });

    it('should parse "Show me documents from 2025"', () => {
      const result = parseNaturalLanguageQuery("Show me documents from 2025");

      expect(result.years).toContain(2025);
    });

    it('should parse "Find all bank statements"', () => {
      const result = parseNaturalLanguageQuery("Find all bank statements");

      expect(result.category).toBe("bank_statement");
    });

    it('should parse "Show me contracts"', () => {
      const result = parseNaturalLanguageQuery("Show me contracts");

      expect(result.category).toBe("contract");
    });
  });
});
