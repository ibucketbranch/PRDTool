import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { GlobalSearchBar } from "@/components/GlobalSearchBar";
import { DashboardHeader } from "@/components/DashboardHeader";

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("GlobalSearchBar", () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockFetch.mockClear();
  });

  it("renders search input", () => {
    render(<GlobalSearchBar />);
    expect(screen.getByPlaceholderText("Search documents...")).toBeDefined();
  });

  it("has aria-label for accessibility", () => {
    render(<GlobalSearchBar />);
    expect(screen.getByLabelText("Global search")).toBeDefined();
  });

  it("shows keyboard shortcut hint on desktop", () => {
    render(<GlobalSearchBar />);
    expect(screen.getByText("K")).toBeDefined();
  });

  it("updates input value on change", () => {
    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "test query" } });

    expect(input.value).toBe("test query");
  });

  it("does not fetch results for queries shorter than 2 characters", async () => {
    vi.useFakeTimers();
    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "a" } });

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(mockFetch).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("fetches results after debounce delay for queries >= 2 characters", async () => {
    vi.useFakeTimers();
    mockFetch.mockResolvedValue({
      json: () => Promise.resolve({ documents: [], count: 0 }),
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "te" } });

    // Before debounce
    expect(mockFetch).not.toHaveBeenCalled();

    // After debounce
    await act(async () => {
      vi.advanceTimersByTime(300);
    });

    expect(mockFetch).toHaveBeenCalledTimes(2); // Documents + File DNA
    vi.useRealTimers();
  });

  it("fetches from both documents and file DNA endpoints", async () => {
    vi.useFakeTimers();
    mockFetch.mockResolvedValue({
      json: () => Promise.resolve({ documents: [], results: [], count: 0, total: 0 }),
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "test" } });

    await act(async () => {
      vi.advanceTimersByTime(300);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/search")
    );
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/file-dna")
    );
    vi.useRealTimers();
  });

  it("shows loading state while fetching", async () => {
    vi.useFakeTimers();
    let resolvePromise: (value: unknown) => void;
    const fetchPromise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    mockFetch.mockReturnValue(fetchPromise);

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.focus(input);

    await act(async () => {
      vi.advanceTimersByTime(300);
    });

    expect(screen.getByText("Searching...")).toBeDefined();

    // Cleanup
    await act(async () => {
      resolvePromise!({
        json: () => Promise.resolve({ documents: [], results: [], count: 0, total: 0 }),
      });
    });
    vi.useRealTimers();
  });

  it("shows 'no results' message when search returns empty", async () => {
    mockFetch.mockResolvedValue({
      json: () => Promise.resolve({ documents: [], results: [], count: 0, total: 0 }),
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "xyz" } });
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByText(/No results found for/)).toBeDefined();
    });
  });

  it("displays document results in dropdown", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/search")) {
        return Promise.resolve({
          json: () =>
            Promise.resolve({
              documents: [
                { id: "1", file_name: "TestDoc.pdf", ai_category: "tax_doc" },
              ],
              count: 1,
            }),
        });
      }
      return Promise.resolve({
        json: () => Promise.resolve({ results: [], total: 0 }),
      });
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByText("TestDoc.pdf")).toBeDefined();
      expect(screen.getByText("tax_doc")).toBeDefined();
    });
  });

  it("displays file DNA results in dropdown", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/file-dna")) {
        return Promise.resolve({
          json: () =>
            Promise.resolve({
              results: [
                { filename: "DNAFile.pdf", path: "/path/to/file", tags: ["invoice", "2024"] },
              ],
              total: 1,
            }),
        });
      }
      return Promise.resolve({
        json: () => Promise.resolve({ documents: [], count: 0 }),
      });
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "DNA" } });
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByText("DNAFile.pdf")).toBeDefined();
      expect(screen.getByText(/Tags: invoice, 2024/)).toBeDefined();
    });
  });

  it("shows section headers for Documents and File DNA", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/search")) {
        return Promise.resolve({
          json: () =>
            Promise.resolve({
              documents: [{ id: "1", file_name: "Doc.pdf" }],
              count: 1,
            }),
        });
      }
      return Promise.resolve({
        json: () =>
          Promise.resolve({
            results: [{ filename: "DNA.pdf", path: "/path", tags: [] }],
            total: 1,
          }),
      });
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByText("Documents")).toBeDefined();
      expect(screen.getByText("File DNA")).toBeDefined();
    });
  });

  it("shows '+N more' indicator when more results exist", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/search")) {
        return Promise.resolve({
          json: () =>
            Promise.resolve({
              documents: [
                { id: "1", file_name: "Doc1.pdf" },
                { id: "2", file_name: "Doc2.pdf" },
                { id: "3", file_name: "Doc3.pdf" },
              ],
              count: 10, // Total is more than shown
            }),
        });
      }
      return Promise.resolve({
        json: () => Promise.resolve({ results: [], total: 0 }),
      });
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByText("+7 more")).toBeDefined();
    });
  });

  it("navigates to search page on Enter key", async () => {
    mockFetch.mockResolvedValue({
      json: () => Promise.resolve({ documents: [], results: [], count: 0, total: 0 }),
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "test query" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(mockPush).toHaveBeenCalledWith("/search?q=test%20query");
  });

  it("navigates to search page when 'View all document results' clicked", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/search")) {
        return Promise.resolve({
          json: () =>
            Promise.resolve({
              documents: [{ id: "1", file_name: "Doc.pdf" }],
              count: 1,
            }),
        });
      }
      return Promise.resolve({
        json: () => Promise.resolve({ results: [], total: 0 }),
      });
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByText("View all document results")).toBeDefined();
    });

    fireEvent.click(screen.getByText("View all document results"));

    expect(mockPush).toHaveBeenCalledWith("/search?q=test");
  });

  it("navigates to file intelligence page when 'View all File DNA results' clicked", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/file-dna")) {
        return Promise.resolve({
          json: () =>
            Promise.resolve({
              results: [{ filename: "DNA.pdf", path: "/path", tags: [] }],
              total: 1,
            }),
        });
      }
      return Promise.resolve({
        json: () => Promise.resolve({ documents: [], count: 0 }),
      });
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByText("View all File DNA results")).toBeDefined();
    });

    fireEvent.click(screen.getByText("View all File DNA results"));

    expect(mockPush).toHaveBeenCalledWith("/file-intelligence?search=test");
  });

  it("closes dropdown on Escape key", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/search")) {
        return Promise.resolve({
          json: () =>
            Promise.resolve({
              documents: [{ id: "1", file_name: "Doc.pdf" }],
              count: 1,
            }),
        });
      }
      return Promise.resolve({
        json: () => Promise.resolve({ results: [], total: 0 }),
      });
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByText("Doc.pdf")).toBeDefined();
    });

    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByText("Doc.pdf")).toBeNull();
    });
  });

  it("closes dropdown when clicking outside", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/search")) {
        return Promise.resolve({
          json: () =>
            Promise.resolve({
              documents: [{ id: "1", file_name: "Doc.pdf" }],
              count: 1,
            }),
        });
      }
      return Promise.resolve({
        json: () => Promise.resolve({ results: [], total: 0 }),
      });
    });

    render(
      <div>
        <GlobalSearchBar />
        <div data-testid="outside">Outside</div>
      </div>
    );
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByText("Doc.pdf")).toBeDefined();
    });

    fireEvent.mouseDown(screen.getByTestId("outside"));

    await waitFor(() => {
      expect(screen.queryByText("Doc.pdf")).toBeNull();
    });
  });

  it("applies custom className", () => {
    const { container } = render(<GlobalSearchBar className="custom-class" />);
    expect(container.firstChild).toHaveClass("custom-class");
  });

  it("navigates to document search when clicking document result", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/search")) {
        return Promise.resolve({
          json: () =>
            Promise.resolve({
              documents: [{ id: "1", file_name: "TestDoc.pdf", ai_category: "invoice" }],
              count: 1,
            }),
        });
      }
      return Promise.resolve({
        json: () => Promise.resolve({ results: [], total: 0 }),
      });
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByText("TestDoc.pdf")).toBeDefined();
    });

    fireEvent.click(screen.getByText("TestDoc.pdf"));

    expect(mockPush).toHaveBeenCalledWith("/search?q=TestDoc.pdf");
  });

  it("truncates tag list to 3 items with ellipsis", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/file-dna")) {
        return Promise.resolve({
          json: () =>
            Promise.resolve({
              results: [
                {
                  filename: "File.pdf",
                  path: "/path",
                  tags: ["tag1", "tag2", "tag3", "tag4", "tag5"],
                },
              ],
              total: 1,
            }),
        });
      }
      return Promise.resolve({
        json: () => Promise.resolve({ documents: [], count: 0 }),
      });
    });

    render(<GlobalSearchBar />);
    const input = screen.getByLabelText("Global search");

    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.focus(input);

    await waitFor(() => {
      // Should show first 3 tags + ellipsis
      expect(screen.getByText(/Tags: tag1, tag2, tag3.../)).toBeDefined();
    });
  });
});

describe("DashboardHeader", () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockFetch.mockClear();
    mockFetch.mockResolvedValue({
      json: () => Promise.resolve({ documents: [], results: [], count: 0, total: 0 }),
    });
  });

  it("renders header with title", () => {
    render(<DashboardHeader />);
    expect(screen.getByText("Organizer")).toBeDefined();
  });

  it("renders home link", () => {
    render(<DashboardHeader />);
    const homeLink = screen.getByRole("link", { name: "Organizer" });
    expect(homeLink).toBeDefined();
    expect(homeLink).toHaveAttribute("href", "/");
  });

  it("renders global search bar", () => {
    render(<DashboardHeader />);
    expect(screen.getByLabelText("Global search")).toBeDefined();
  });

  it("renders navigation links", () => {
    render(<DashboardHeader />);
    expect(screen.getByRole("link", { name: "Search" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Browse" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Agents" })).toBeDefined();
  });

  it("navigation links have correct hrefs", () => {
    render(<DashboardHeader />);
    expect(screen.getByRole("link", { name: "Search" })).toHaveAttribute(
      "href",
      "/search"
    );
    expect(screen.getByRole("link", { name: "Browse" })).toHaveAttribute(
      "href",
      "/browse"
    );
    expect(screen.getByRole("link", { name: "Agents" })).toHaveAttribute(
      "href",
      "/agents"
    );
  });

  it("header is sticky", () => {
    render(<DashboardHeader />);
    const header = screen.getByRole("banner");
    expect(header).toHaveClass("sticky");
    expect(header).toHaveClass("top-0");
  });

  it("header has z-index for proper layering", () => {
    render(<DashboardHeader />);
    const header = screen.getByRole("banner");
    expect(header).toHaveClass("z-40");
  });
});

describe("Component exports", () => {
  it("exports GlobalSearchBar and DashboardHeader from index", async () => {
    const exports = await import("@/components");
    expect(exports.GlobalSearchBar).toBeDefined();
    expect(exports.DashboardHeader).toBeDefined();
  });
});
