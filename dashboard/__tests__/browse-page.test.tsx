import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

// Mock next/navigation
const mockUseSearchParams = vi.fn(() => new URLSearchParams());
vi.mock("next/navigation", () => ({
  useSearchParams: () => mockUseSearchParams(),
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Import after mocks
import BrowsePage from "@/app/browse/page";

describe("BrowsePage", () => {
  const mockDocumentsResponse = {
    documents: [
      {
        id: "1",
        file_name: "test_document.pdf",
        current_path: "/Users/test/Documents/test_document.pdf",
        ai_category: "tax_documents",
        ai_subcategories: null,
        ai_summary: "A test document",
        entities: null,
        key_dates: ["2024-01-15"],
        folder_hierarchy: ["Documents"],
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    ],
    total: 100,
    filteredTotal: 50,
    limit: 20,
    offset: 0,
  };

  const mockStatisticsResponse = {
    categories: [{ ai_category: "tax_documents", count: 50 }],
    dateDistribution: [{ year: 2024, count: 30 }],
    contextBins: [{ context_bin: "Documents", count: 40 }],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();

    // Default mock responses
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/statistics")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockStatisticsResponse),
        });
      }
      if (url.includes("/api/documents")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockDocumentsResponse),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });
  });

  it("renders page title", async () => {
    render(<BrowsePage />);
    expect(screen.getByText("Document Browser")).toBeDefined();
  });

  it("renders back link to dashboard", () => {
    render(<BrowsePage />);
    const backLink = screen.getByText(/Back to Dashboard/);
    expect(backLink).toBeDefined();
    expect(backLink.closest("a")).toHaveAttribute("href", "/");
  });

  it("renders page description", () => {
    render(<BrowsePage />);
    expect(
      screen.getByText(/Browse and filter all documents/)
    ).toBeDefined();
  });

  it("shows loading state initially", () => {
    render(<BrowsePage />);
    // Multiple elements may show loading text - use getAllByText
    const loadingElements = screen.getAllByText("Loading documents...");
    expect(loadingElements.length).toBeGreaterThan(0);
  });

  it("fetches and displays documents", async () => {
    render(<BrowsePage />);

    await waitFor(() => {
      // Documents render in both mobile and desktop views
      expect(screen.getAllByText("test_document.pdf").length).toBeGreaterThan(0);
    });
  });

  it("displays document count after loading", async () => {
    render(<BrowsePage />);

    await waitFor(() => {
      // The count is displayed in a semibold span after "Found"
      const foundText = screen.getByText(/^Found/);
      expect(foundText).toBeDefined();
      // Check that the count (50) is displayed somewhere in the parent paragraph
      expect(foundText.closest("p")?.textContent).toContain("50");
    });
  });

  it("shows filtered from total when different", async () => {
    render(<BrowsePage />);

    await waitFor(() => {
      expect(screen.getByText(/filtered from 100 total/)).toBeDefined();
    });
  });

  it("renders filter component", async () => {
    render(<BrowsePage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /filters/i })).toBeDefined();
    });
  });

  it("renders pagination component", async () => {
    render(<BrowsePage />);

    await waitFor(() => {
      expect(screen.getByText(/Per page:/)).toBeDefined();
    });
  });

  it("displays error message on fetch failure", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/statistics")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockStatisticsResponse),
        });
      }
      if (url.includes("/api/documents")) {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ error: "Server error" }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<BrowsePage />);

    await waitFor(() => {
      expect(screen.getByText(/Error:/)).toBeDefined();
    });
  });

  it("shows retry button on error", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/statistics")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockStatisticsResponse),
        });
      }
      if (url.includes("/api/documents")) {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ error: "Server error" }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<BrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("Try again")).toBeDefined();
    });
  });

  it("fetches documents with filters from URL params", async () => {
    mockUseSearchParams.mockReturnValue(
      new URLSearchParams("category=tax_documents&year=2024")
    );

    render(<BrowsePage />);

    await waitFor(() => {
      const calls = mockFetch.mock.calls.filter((call) =>
        call[0].includes("/api/documents")
      );
      expect(calls.length).toBeGreaterThan(0);
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall).toContain("category=tax_documents");
    });
  });

  it("includes pagination parameters in fetch", async () => {
    render(<BrowsePage />);

    await waitFor(() => {
      const calls = mockFetch.mock.calls.filter((call) =>
        call[0].includes("/api/documents")
      );
      expect(calls.length).toBeGreaterThan(0);
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall).toContain("limit=20");
      expect(lastCall).toContain("offset=0");
    });
  });

  it("includes sort parameters in fetch", async () => {
    render(<BrowsePage />);

    await waitFor(() => {
      const calls = mockFetch.mock.calls.filter((call) =>
        call[0].includes("/api/documents")
      );
      expect(calls.length).toBeGreaterThan(0);
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall).toContain("orderBy=created_at");
      expect(lastCall).toContain("orderDirection=desc");
    });
  });
});

describe("BrowsePage interactions", () => {
  const mockDocumentsResponse = {
    documents: [
      {
        id: "1",
        file_name: "test_document.pdf",
        current_path: "/Users/test/Documents/test_document.pdf",
        ai_category: "tax_documents",
        ai_subcategories: null,
        ai_summary: "A test document",
        entities: null,
        key_dates: ["2024-01-15"],
        folder_hierarchy: ["Documents"],
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    ],
    total: 100,
    filteredTotal: 50,
    limit: 20,
    offset: 0,
  };

  const mockStatisticsResponse = {
    categories: [{ ai_category: "tax_documents", count: 50 }],
    dateDistribution: [{ year: 2024, count: 30 }],
    contextBins: [{ context_bin: "Documents", count: 40 }],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/statistics")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockStatisticsResponse),
        });
      }
      if (url.includes("/api/documents")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockDocumentsResponse),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });
  });

  it("re-fetches when sort header is clicked", async () => {
    const { container } = render(<BrowsePage />);

    await waitFor(() => {
      // Documents render in both mobile and desktop views
      expect(screen.getAllByText("test_document.pdf").length).toBeGreaterThan(0);
    });

    const initialCallCount = mockFetch.mock.calls.filter((call) =>
      call[0].includes("/api/documents")
    ).length;

    // Click on Name header in desktop view to sort
    const desktopView = container.querySelector(".hidden.md\\:block") as Element;
    const nameHeader = desktopView?.querySelector("th button");
    if (nameHeader) {
      fireEvent.click(nameHeader);

      await waitFor(() => {
        const newCallCount = mockFetch.mock.calls.filter((call) =>
          call[0].includes("/api/documents")
        ).length;
        expect(newCallCount).toBeGreaterThan(initialCallCount);
      });
    }
  });

  it("changes sort direction when same header is clicked twice", async () => {
    const { container } = render(<BrowsePage />);

    await waitFor(() => {
      // Documents render in both mobile and desktop views
      expect(screen.getAllByText("test_document.pdf").length).toBeGreaterThan(0);
    });

    // Find and click Created header in desktop view (default sort field)
    const desktopView = container.querySelector(".hidden.md\\:block") as Element;
    // Created is the last sortable header (6th th)
    const headers = desktopView?.querySelectorAll("th button");
    const createdHeader = headers?.[3]; // Created is at index 3 (after Name, Path, Category)
    if (createdHeader) {
      fireEvent.click(createdHeader);

      await waitFor(() => {
        const calls = mockFetch.mock.calls.filter((call) =>
          call[0].includes("/api/documents")
        );
        const lastCall = calls[calls.length - 1][0];
        // Should toggle from desc to asc
        expect(lastCall).toContain("orderDirection=asc");
      });
    }
  });

  it("re-fetches when page is changed", async () => {
    // Mock response with multiple pages
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/statistics")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockStatisticsResponse),
        });
      }
      if (url.includes("/api/documents")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              ...mockDocumentsResponse,
              filteredTotal: 100, // Enough for multiple pages
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<BrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("Next")).toBeDefined();
    });

    const initialCallCount = mockFetch.mock.calls.filter((call) =>
      call[0].includes("/api/documents")
    ).length;

    // Click Next button
    fireEvent.click(screen.getByText("Next"));

    await waitFor(() => {
      const newCallCount = mockFetch.mock.calls.filter((call) =>
        call[0].includes("/api/documents")
      ).length;
      expect(newCallCount).toBeGreaterThan(initialCallCount);
    });
  });
});
