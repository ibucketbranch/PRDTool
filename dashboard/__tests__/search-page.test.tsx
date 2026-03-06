import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SearchPage from "@/app/search/page";
import type { Document } from "@/lib/supabase";

// Mock document for testing
const mockDocument: Document = {
  id: "test-id-1",
  file_name: "Verizon_Bill_2024_03.pdf",
  current_path: "/Users/test/Documents/Bills/Verizon_Bill_2024_03.pdf",
  ai_category: "utility_bill",
  ai_subcategories: ["phone"],
  ai_summary: "Verizon bill for March 2024 totaling $89.99",
  entities: {
    organizations: ["Verizon"],
    amounts: ["$89.99"],
  },
  key_dates: ["2024-03-15"],
  folder_hierarchy: ["Documents", "Bills"],
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

// Create multiple mock documents for pagination testing
const createMockDocuments = (count: number, startIndex: number = 0): Document[] => {
  return Array.from({ length: count }, (_, i) => ({
    ...mockDocument,
    id: `test-id-${startIndex + i + 1}`,
    file_name: `Document_${startIndex + i + 1}.pdf`,
  }));
};

// Mock fetch globally
const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SearchPage", () => {
  it("renders page title and description", () => {
    render(<SearchPage />);
    expect(screen.getByText("Natural Language Search")).toBeDefined();
    expect(
      screen.getByText(/Search for documents using natural language queries/)
    ).toBeDefined();
  });

  it("renders back to dashboard link", () => {
    render(<SearchPage />);
    const backLink = screen.getByRole("link", { name: /Back to Dashboard/i });
    expect(backLink).toBeDefined();
    expect(backLink.getAttribute("href")).toBe("/");
  });

  it("renders search input", () => {
    render(<SearchPage />);
    expect(screen.getByRole("textbox")).toBeDefined();
    expect(screen.getByRole("button", { name: "Search" })).toBeDefined();
  });

  it("renders initial state message", () => {
    render(<SearchPage />);
    expect(
      screen.getByText("Enter a search query to find documents")
    ).toBeDefined();
  });

  it("performs search when form is submitted", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test query",
        mode: "natural",
        parsed: {
          category: null,
          years: [],
          organizations: [],
          searchTerms: ["test", "query"],
          isNaturalLanguage: true,
        },
        searchDescription: "Searching for: test query",
        documents: [mockDocument],
        count: 1,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");
    const button = screen.getByRole("button", { name: "Search" });

    fireEvent.change(input, { target: { value: "test query" } });
    fireEvent.click(button);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/search?q=test%20query&mode=natural&limit=20&offset=0"
      );
    });

    await waitFor(() => {
      expect(screen.getByText("Verizon_Bill_2024_03.pdf")).toBeDefined();
    });
  });

  it("displays search results count", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "verizon",
        mode: "natural",
        documents: [mockDocument],
        count: 1,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "verizon" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText(/Showing/)).toBeDefined();
      expect(screen.getByText("1")).toBeDefined();
      expect(screen.getByText(/document$/)).toBeDefined();
    });
  });

  it("displays plural for multiple results", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "bills",
        mode: "natural",
        documents: [mockDocument, { ...mockDocument, id: "test-id-2" }],
        count: 2,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "bills" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText(/documents$/)).toBeDefined();
    });
  });

  it("displays search description from API", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "verizon bill from 2024",
        mode: "natural",
        searchDescription: "Filters: category: Utility Bill | years: 2024",
        documents: [mockDocument],
        count: 1,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "verizon bill from 2024" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(
        screen.getByText("Filters: category: Utility Bill | years: 2024")
      ).toBeDefined();
    });
  });

  it("displays parsed query filters as badges", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "verizon bill from 2024",
        mode: "natural",
        parsed: {
          category: "utility_bill",
          years: [2024],
          organizations: ["Verizon"],
          searchTerms: [],
          isNaturalLanguage: true,
        },
        documents: [mockDocument],
        count: 1,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "verizon bill from 2024" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText(/Category: utility_bill/)).toBeDefined();
      expect(screen.getByText(/Years: 2024/)).toBeDefined();
      expect(screen.getByText(/Org: Verizon/)).toBeDefined();
    });
  });

  it("displays no results message when empty", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "nonexistent",
        mode: "natural",
        documents: [],
        count: 0,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "nonexistent" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText("No documents found")).toBeDefined();
    });
  });

  it("displays error message on API error", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({
        error: "Database connection failed",
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText(/Error: Database connection failed/)).toBeDefined();
    });
  });

  it("displays error message on network error", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText(/Error: Network error/)).toBeDefined();
    });
  });

  it("displays error from response body", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test",
        error: "Search failed",
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText(/Error: Search failed/)).toBeDefined();
    });
  });

  it("shows loading state while searching", async () => {
    // Create a promise that we can control
    let resolvePromise: (value: unknown) => void;
    const fetchPromise = new Promise((resolve) => {
      resolvePromise = resolve;
    });

    mockFetch.mockReturnValueOnce(fetchPromise);

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    // Should show loading state
    expect(screen.getByRole("button", { name: "Searching..." })).toBeDefined();

    // Resolve the promise
    resolvePromise!({
      ok: true,
      json: async () => ({
        query: "test",
        documents: [],
        count: 0,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Search" })).toBeDefined();
    });
  });

  it("searches when example query is clicked", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "Find all tax documents from 2023",
        mode: "natural",
        documents: [],
        count: 0,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    render(<SearchPage />);
    const exampleButton = screen.getByRole("button", {
      name: "Find all tax documents from 2023",
    });

    fireEvent.click(exampleButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("Find%20all%20tax%20documents%20from%202023")
      );
    });
  });

  it("clears error when new search is performed", async () => {
    // First search fails
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: "First error" }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test1" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText(/Error: First error/)).toBeDefined();
    });

    // Second search succeeds
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test2",
        documents: [],
        count: 0,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    fireEvent.change(input, { target: { value: "test2" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.queryByText(/Error:/)).toBeNull();
    });
  });

  it("encodes query parameter correctly", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "bills & invoices",
        documents: [],
        count: 0,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "bills & invoices" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/search?q=bills%20%26%20invoices&mode=natural&limit=20&offset=0"
      );
    });
  });
});

describe("SearchPage pagination", () => {
  it("shows Load More button when hasMore is true", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test",
        mode: "natural",
        documents: createMockDocuments(20),
        count: 20,
        limit: 20,
        offset: 0,
        hasMore: true,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Load More" })).toBeDefined();
    });
  });

  it("does not show Load More button when hasMore is false", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test",
        mode: "natural",
        documents: createMockDocuments(5),
        count: 5,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText("Document_1.pdf")).toBeDefined();
    });

    expect(screen.queryByRole("button", { name: "Load More" })).toBeNull();
  });

  it("loads more results when Load More is clicked", async () => {
    // First page
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test",
        mode: "natural",
        documents: createMockDocuments(20, 0),
        count: 20,
        limit: 20,
        offset: 0,
        hasMore: true,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText("Document_1.pdf")).toBeDefined();
      expect(screen.getByText("Document_20.pdf")).toBeDefined();
    });

    // Second page
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test",
        mode: "natural",
        documents: createMockDocuments(20, 20),
        count: 20,
        limit: 20,
        offset: 20,
        hasMore: true,
      }),
    });

    const loadMoreButton = screen.getByRole("button", { name: "Load More" });
    fireEvent.click(loadMoreButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenLastCalledWith(
        "/api/search?q=test&mode=natural&limit=20&offset=20"
      );
    });

    await waitFor(() => {
      // Should have both first and second page results
      expect(screen.getByText("Document_1.pdf")).toBeDefined();
      expect(screen.getByText("Document_21.pdf")).toBeDefined();
      expect(screen.getByText("Document_40.pdf")).toBeDefined();
    });
  });

  it("shows loading state when loading more results", async () => {
    // First page
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test",
        mode: "natural",
        documents: createMockDocuments(20),
        count: 20,
        limit: 20,
        offset: 0,
        hasMore: true,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Load More" })).toBeDefined();
    });

    // Create a promise that we can control for load more
    let resolvePromise: (value: unknown) => void;
    const fetchPromise = new Promise((resolve) => {
      resolvePromise = resolve;
    });

    mockFetch.mockReturnValueOnce(fetchPromise);

    const loadMoreButton = screen.getByRole("button", { name: "Load More" });
    fireEvent.click(loadMoreButton);

    // Should show loading state on button
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Loading..." })).toBeDefined();
    });

    // Resolve the promise
    resolvePromise!({
      ok: true,
      json: async () => ({
        query: "test",
        mode: "natural",
        documents: createMockDocuments(10, 20),
        count: 10,
        limit: 20,
        offset: 20,
        hasMore: false,
      }),
    });

    await waitFor(() => {
      // Load more button should be gone since hasMore is false
      expect(screen.queryByRole("button", { name: "Load More" })).toBeNull();
    });
  });

  it("hides Load More button when last page is reached", async () => {
    // First page
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test",
        mode: "natural",
        documents: createMockDocuments(20),
        count: 20,
        limit: 20,
        offset: 0,
        hasMore: true,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Load More" })).toBeDefined();
    });

    // Last page
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test",
        mode: "natural",
        documents: createMockDocuments(5, 20),
        count: 5,
        limit: 20,
        offset: 20,
        hasMore: false,
      }),
    });

    fireEvent.click(screen.getByRole("button", { name: "Load More" }));

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Load More" })).toBeNull();
    });
  });

  it("shows (more available) text when hasMore is true", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test",
        mode: "natural",
        documents: createMockDocuments(20),
        count: 20,
        limit: 20,
        offset: 0,
        hasMore: true,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText(/\(more available\)/)).toBeDefined();
    });
  });

  it("resets pagination when new search is performed", async () => {
    // First search with pagination
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test1",
        mode: "natural",
        documents: createMockDocuments(20),
        count: 20,
        limit: 20,
        offset: 0,
        hasMore: true,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test1" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText("Document_1.pdf")).toBeDefined();
    });

    // Load more
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test1",
        mode: "natural",
        documents: createMockDocuments(20, 20),
        count: 20,
        limit: 20,
        offset: 20,
        hasMore: false,
      }),
    });

    fireEvent.click(screen.getByRole("button", { name: "Load More" }));

    await waitFor(() => {
      expect(screen.getByText("Document_40.pdf")).toBeDefined();
    });

    // New search should reset
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test2",
        mode: "natural",
        documents: [{ ...mockDocument, file_name: "NewSearch.pdf" }],
        count: 1,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    fireEvent.change(input, { target: { value: "test2" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenLastCalledWith(
        "/api/search?q=test2&mode=natural&limit=20&offset=0"
      );
    });

    await waitFor(() => {
      expect(screen.getByText("NewSearch.pdf")).toBeDefined();
      // Old results should be cleared
      expect(screen.queryByText("Document_1.pdf")).toBeNull();
      expect(screen.queryByText("Document_40.pdf")).toBeNull();
    });
  });

  it("updates displayed count as more results are loaded", async () => {
    // First page
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test",
        mode: "natural",
        documents: createMockDocuments(20),
        count: 20,
        limit: 20,
        offset: 0,
        hasMore: true,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText("20")).toBeDefined();
    });

    // Second page
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test",
        mode: "natural",
        documents: createMockDocuments(15, 20),
        count: 15,
        limit: 20,
        offset: 20,
        hasMore: false,
      }),
    });

    fireEvent.click(screen.getByRole("button", { name: "Load More" }));

    await waitFor(() => {
      expect(screen.getByText("35")).toBeDefined();
    });
  });
});

describe("SearchPage path click handling", () => {
  // Mock clipboard and alert
  const mockClipboard = {
    writeText: vi.fn().mockResolvedValue(undefined),
  };

  beforeEach(() => {
    vi.stubGlobal("navigator", { clipboard: mockClipboard });
    vi.stubGlobal("alert", vi.fn());
    mockClipboard.writeText.mockClear();
  });

  it("copies path to clipboard when path is clicked", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: "test",
        documents: [mockDocument],
        count: 1,
        limit: 20,
        offset: 0,
        hasMore: false,
      }),
    });

    render(<SearchPage />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText("Verizon_Bill_2024_03.pdf")).toBeDefined();
    });

    const pathButton = screen.getByRole("button", {
      name: mockDocument.current_path,
    });
    fireEvent.click(pathButton);

    await waitFor(() => {
      expect(mockClipboard.writeText).toHaveBeenCalledWith(
        mockDocument.current_path
      );
    });
  });
});
