/**
 * Tests for enrichment search utilities
 */

import {
  matchEnrichment,
  FileEnrichment,
} from "../lib/enrichment-search";

describe("enrichment-search", () => {
  // Sample enrichment data for testing
  const sampleEnrichment: FileEnrichment = {
    document_type: "utility_bill",
    date_references: ["March 2024", "2024-03-15"],
    people: ["John Smith"],
    organizations: ["Verizon", "AT&T"],
    key_topics: ["telecommunications", "billing", "service"],
    summary: "Verizon wireless bill for March 2024 showing charges for mobile service.",
    suggested_tags: ["utility", "phone", "monthly"],
    confidence: 0.85,
    model_used: "qwen2.5-coder:14b",
    used_keyword_fallback: false,
    enriched_at: "2024-03-20T10:00:00Z",
    duration_ms: 1500,
  };

  const taxEnrichment: FileEnrichment = {
    document_type: "tax_return",
    date_references: ["2023", "April 2024"],
    people: ["Jane Doe", "John Doe"],
    organizations: ["IRS", "TurboTax"],
    key_topics: ["taxes", "federal", "income"],
    summary: "Federal tax return for 2023 filed with the IRS.",
    suggested_tags: ["tax", "federal", "2023"],
    confidence: 0.92,
    model_used: "qwen2.5-coder:14b",
    used_keyword_fallback: false,
    enriched_at: "2024-04-15T10:00:00Z",
    duration_ms: 2000,
  };

  describe("matchEnrichment", () => {
    describe("organization matching", () => {
      it("should match by organization name", () => {
        const result = matchEnrichment(sampleEnrichment, "verizon bill", {
          years: [],
          organizations: ["Verizon"],
          searchTerms: ["bill"],
          category: null,
        });

        expect(result.matches).toBe(true);
        expect(result.reasons).toContain("organization: Verizon");
        expect(result.score).toBeGreaterThan(0);
      });

      it("should match case-insensitively", () => {
        const result = matchEnrichment(sampleEnrichment, "VERIZON", {
          years: [],
          organizations: ["VERIZON"],
          searchTerms: [],
          category: null,
        });

        expect(result.matches).toBe(true);
        expect(result.reasons).toContain("organization: VERIZON");
      });

      it("should not match non-existent organization", () => {
        const result = matchEnrichment(sampleEnrichment, "comcast bill", {
          years: [],
          organizations: ["Comcast"],
          searchTerms: ["bill"],
          category: null,
        });

        // Should not match by organization
        expect(result.reasons).not.toContain("organization: Comcast");
      });
    });

    describe("year matching", () => {
      it("should match by year in date_references", () => {
        const result = matchEnrichment(sampleEnrichment, "2024", {
          years: [2024],
          organizations: [],
          searchTerms: [],
          category: null,
        });

        expect(result.matches).toBe(true);
        expect(result.reasons).toContain("date: 2024");
        expect(result.score).toBeGreaterThan(0);
      });

      it("should match multiple years", () => {
        const result = matchEnrichment(taxEnrichment, "2023 2024", {
          years: [2023, 2024],
          organizations: [],
          searchTerms: [],
          category: null,
        });

        expect(result.matches).toBe(true);
        expect(result.reasons).toContain("date: 2023");
        // 2024 is in "April 2024"
        expect(result.score).toBeGreaterThan(0);
      });

      it("should not match year not in document", () => {
        const result = matchEnrichment(sampleEnrichment, "2022", {
          years: [2022],
          organizations: [],
          searchTerms: [],
          category: null,
        });

        expect(result.reasons).not.toContain("date: 2022");
      });
    });

    describe("category/document_type matching", () => {
      it("should match document type against category", () => {
        const result = matchEnrichment(sampleEnrichment, "utility bill", {
          years: [],
          organizations: [],
          searchTerms: [],
          category: "utility_bill",
        });

        expect(result.matches).toBe(true);
        expect(result.reasons.some((r) => r.includes("document_type"))).toBe(true);
      });

      it("should match tax document", () => {
        const result = matchEnrichment(taxEnrichment, "tax", {
          years: [],
          organizations: [],
          searchTerms: [],
          category: "tax_document",
        });

        expect(result.matches).toBe(true);
      });
    });

    describe("summary matching", () => {
      it("should match terms in summary", () => {
        const result = matchEnrichment(sampleEnrichment, "wireless mobile charges", {
          years: [],
          organizations: [],
          searchTerms: ["wireless", "mobile", "charges"],
          category: null,
        });

        expect(result.matches).toBe(true);
        expect(result.reasons).toContain("summary match");
      });
    });

    describe("topic matching", () => {
      it("should match key topics", () => {
        const result = matchEnrichment(sampleEnrichment, "billing", {
          years: [],
          organizations: [],
          searchTerms: ["billing"],
          category: null,
        });

        expect(result.matches).toBe(true);
        expect(result.reasons).toContain("topic: billing");
      });

      it("should match tax topics", () => {
        const result = matchEnrichment(taxEnrichment, "income", {
          years: [],
          organizations: [],
          searchTerms: ["income"],
          category: null,
        });

        expect(result.matches).toBe(true);
        expect(result.reasons).toContain("topic: income");
      });
    });

    describe("people matching", () => {
      it("should match person names", () => {
        const result = matchEnrichment(sampleEnrichment, "john smith document", {
          years: [],
          organizations: [],
          searchTerms: ["john", "smith", "document"],
          category: null,
        });

        expect(result.matches).toBe(true);
        // Should match on person
        expect(result.reasons.some((r) => r.includes("person"))).toBe(true);
      });
    });

    describe("tag matching", () => {
      it("should match suggested tags", () => {
        const result = matchEnrichment(sampleEnrichment, "monthly", {
          years: [],
          organizations: [],
          searchTerms: [],
          category: null,
        });

        expect(result.matches).toBe(true);
        expect(result.reasons).toContain("tag match");
      });
    });

    describe("direct text search", () => {
      it("should fall back to direct text search", () => {
        const result = matchEnrichment(sampleEnrichment, "telecommunications", {
          years: [],
          organizations: [],
          searchTerms: [],
          category: null,
        });

        expect(result.matches).toBe(true);
        // Either through topics or direct text
        expect(result.reasons.length).toBeGreaterThan(0);
      });
    });

    describe("complex queries", () => {
      it("should handle PRD example: 'verizon bill from march 2024'", () => {
        const result = matchEnrichment(sampleEnrichment, "verizon bill from march 2024", {
          years: [2024],
          organizations: ["Verizon"],
          searchTerms: ["bill"],
          category: "utility_bill",
        });

        expect(result.matches).toBe(true);
        // Should have high score due to multiple matches
        expect(result.score).toBeGreaterThan(15);
        // Should match org, date, and document type
        expect(result.reasons).toContain("organization: Verizon");
        expect(result.reasons).toContain("date: 2024");
      });

      it("should handle 'tax documents from 2023'", () => {
        const result = matchEnrichment(taxEnrichment, "tax documents from 2023", {
          years: [2023],
          organizations: [],
          searchTerms: ["tax", "documents"],
          category: "tax_document",
        });

        expect(result.matches).toBe(true);
        expect(result.reasons).toContain("date: 2023");
      });

      it("should handle 'IRS federal return'", () => {
        const result = matchEnrichment(taxEnrichment, "IRS federal return", {
          years: [],
          organizations: ["IRS"],
          searchTerms: ["federal", "return"],
          category: null,
        });

        expect(result.matches).toBe(true);
        expect(result.reasons).toContain("organization: IRS");
        expect(result.reasons).toContain("topic: federal");
      });
    });

    describe("no match scenarios", () => {
      it("should not match unrelated query", () => {
        const result = matchEnrichment(sampleEnrichment, "medical records 2022", {
          years: [2022],
          organizations: [],
          searchTerms: ["medical", "records"],
          category: "medical_record",
        });

        // Should have few or no matches
        expect(result.score).toBeLessThan(5);
      });

      it("should handle empty query gracefully", () => {
        const result = matchEnrichment(sampleEnrichment, "", {
          years: [],
          organizations: [],
          searchTerms: [],
          category: null,
        });

        // Empty query should not match
        expect(result.matches).toBe(false);
        expect(result.reasons).toHaveLength(0);
      });
    });

    describe("score ranking", () => {
      it("should give higher score to more relevant matches", () => {
        // Perfect match
        const perfectMatch = matchEnrichment(sampleEnrichment, "verizon bill march 2024", {
          years: [2024],
          organizations: ["Verizon"],
          searchTerms: ["bill"],
          category: "utility_bill",
        });

        // Partial match
        const partialMatch = matchEnrichment(sampleEnrichment, "bill", {
          years: [],
          organizations: [],
          searchTerms: ["bill"],
          category: null,
        });

        expect(perfectMatch.score).toBeGreaterThan(partialMatch.score);
      });
    });
  });
});
