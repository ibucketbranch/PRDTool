import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// Mock Next.js navigation
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

// Mock the fetch function globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Import after mocking
import EmptyFoldersPage from "@/app/empty-folders/page";

// Mock data
const mockEmptyFoldersResponse = {
  emptyFolders: [
    {
      folderPath: "/Users/test/Documents/OldFolder",
      originalFileCount: 3,
      movedFiles: [
        {
          documentId: "doc-1",
          fileName: "test-file.pdf",
          originalPath: "/Users/test/Documents/OldFolder/test-file.pdf",
          currentPath: "/Users/test/Documents/NewFolder/test-file.pdf",
          movedAt: "2024-01-15T10:00:00Z",
        },
      ],
      isEmpty: true,
      lastMoveDate: "2024-01-15T10:00:00Z",
    },
    {
      folderPath: "/Users/test/Documents/AnotherFolder",
      originalFileCount: 5,
      movedFiles: [],
      isEmpty: false,
      lastMoveDate: "2024-01-10T10:00:00Z",
    },
  ],
  totalEmptyFolders: 2,
  verifiedEmpty: 1,
  notEmpty: 1,
  notFound: 0,
};

const mockAssessmentResponse = {
  assessment: {
    folderPath: "/Users/test/Documents/OldFolder",
    folderName: "OldFolder",
    isCorrectLocation: true,
    isDuplicate: false,
    assessment: "correct",
    confidence: 0.85,
    reasoning: ["Folder name matches AI category"],
    suggestedAction: "restore",
    movedFilesCategories: ["employment"],
    dominantCategory: "employment",
    categoryMatch: true,
    folderHierarchyMatch: true,
    canonicalMatch: false,
    similarCanonicalFolder: null,
  },
  movedFiles: [],
};

describe("EmptyFoldersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock window.alert
    vi.spyOn(window, "alert").mockImplementation(() => {});
    vi.spyOn(window, "confirm").mockImplementation(() => true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders page title and description", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockEmptyFoldersResponse,
    });

    render(<EmptyFoldersPage />);

    expect(screen.getByText("Empty Folders")).toBeInTheDocument();
    expect(
      screen.getByText(/Manage folders that became empty after file consolidation/)
    ).toBeInTheDocument();
  });

  it("shows loading state initially", () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves

    const { container } = render(<EmptyFoldersPage />);

    // Now we show skeleton loaders instead of text
    // Check that skeleton elements are present (animate-pulse class)
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("fetches and displays empty folders", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockEmptyFoldersResponse,
    });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      expect(screen.getByText("OldFolder")).toBeInTheDocument();
      expect(screen.getByText("AnotherFolder")).toBeInTheDocument();
    });
  });

  it("displays summary stats", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockEmptyFoldersResponse,
    });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      expect(screen.getByText("Total Folders")).toBeInTheDocument();
      expect(screen.getByText("Verified Empty")).toBeInTheDocument();
      // "Not Empty" appears in both stats and badges - look for the stat label specifically
      const notEmptyElements = screen.getAllByText("Not Empty");
      // At least one should be in the stats section (text-sm text-neutral-600)
      expect(notEmptyElements.length).toBeGreaterThan(0);
      expect(screen.getByText("Assessed")).toBeInTheDocument();
    });
  });

  it("displays filter buttons", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockEmptyFoldersResponse,
    });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      // Filter buttons have rounded-full class - find them specifically
      const filterButtons = screen.getAllByRole("button").filter(
        (btn) => btn.className.includes("rounded-full")
      );
      expect(filterButtons.length).toBeGreaterThanOrEqual(3);
      expect(filterButtons.some(btn => btn.textContent?.includes("All ("))).toBeTruthy();
      expect(filterButtons.some(btn => btn.textContent?.includes("Empty ("))).toBeTruthy();
      expect(filterButtons.some(btn => btn.textContent?.includes("Not Empty ("))).toBeTruthy();
    });
  });

  it("shows error message on fetch failure", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: "Database connection failed" }),
    });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      expect(screen.getByText(/Error:/)).toBeInTheDocument();
      expect(screen.getByText("Try again")).toBeInTheDocument();
    });
  });

  it("retries fetch when Try again is clicked", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: "Failed" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockEmptyFoldersResponse,
      });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      expect(screen.getByText("Try again")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Try again"));

    await waitFor(() => {
      expect(screen.getByText("OldFolder")).toBeInTheDocument();
    });
  });

  it("filters folders when filter button clicked", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockEmptyFoldersResponse,
    });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      expect(screen.getByText("OldFolder")).toBeInTheDocument();
    });

    // Click "Empty" filter - filter buttons have rounded-full class
    const filterButtons = screen.getAllByRole("button");
    const emptyFilterButton = filterButtons.find(
      (btn) => btn.className.includes("rounded-full") && btn.textContent?.includes("Empty (1)")
    );
    expect(emptyFilterButton).toBeDefined();
    fireEvent.click(emptyFilterButton!);

    // Should only show the empty folder
    expect(screen.getByText("OldFolder")).toBeInTheDocument();
    expect(screen.queryByText("AnotherFolder")).not.toBeInTheDocument();
  });

  it("assesses folder when Assess button clicked", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockEmptyFoldersResponse,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockAssessmentResponse,
      });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      expect(screen.getByText("OldFolder")).toBeInTheDocument();
    });

    // Click first "Assess" button
    const assessButtons = screen.getAllByRole("button", { name: "Assess" });
    fireEvent.click(assessButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("Correct Location")).toBeInTheDocument();
    });
  });

  it("shows bulk actions bar when folders selected", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockEmptyFoldersResponse,
    });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      expect(screen.getByText("OldFolder")).toBeInTheDocument();
    });

    // Select a folder
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]); // First folder checkbox (skip select all)

    // Text is split across span and text node
    expect(screen.getByText((content, element) => {
      return element?.textContent === "1 folder selected";
    })).toBeInTheDocument();
    expect(screen.getByText("Assess All")).toBeInTheDocument();
    expect(screen.getByText("Restore All")).toBeInTheDocument();
    expect(screen.getByText("Remove All")).toBeInTheDocument();
  });

  it("clears selection when Clear selection clicked", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockEmptyFoldersResponse,
    });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      expect(screen.getByText("OldFolder")).toBeInTheDocument();
    });

    // Select a folder
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]);

    // Text is split across span and text node
    expect(screen.getByText((content, element) => {
      return element?.textContent === "1 folder selected";
    })).toBeInTheDocument();

    // Clear selection
    fireEvent.click(screen.getByText("Clear selection"));

    expect(screen.queryByText((content, element) => {
      return element?.textContent?.includes("folder selected") || false;
    })).not.toBeInTheDocument();
  });

  it("shows alert when Restore Files clicked (not implemented)", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockEmptyFoldersResponse,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockAssessmentResponse,
      });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      expect(screen.getByText("OldFolder")).toBeInTheDocument();
    });

    // First assess the folder
    const assessButtons = screen.getAllByRole("button", { name: "Assess" });
    fireEvent.click(assessButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("Restore Files")).toBeInTheDocument();
    });

    // Click Restore Files
    fireEvent.click(screen.getByText("Restore Files"));

    expect(window.alert).toHaveBeenCalledWith(
      expect.stringContaining("Restore functionality")
    );
  });

  it("shows confirm dialog when Remove Folder clicked", async () => {
    const confirmMock = vi.spyOn(window, "confirm").mockReturnValue(true);

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockEmptyFoldersResponse,
          emptyFolders: [
            {
              ...mockEmptyFoldersResponse.emptyFolders[0],
            },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAssessmentResponse,
          assessment: {
            ...mockAssessmentResponse.assessment,
            suggestedAction: "remove",
            assessment: "duplicate",
          },
        }),
      });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      expect(screen.getByText("OldFolder")).toBeInTheDocument();
    });

    // Assess the folder
    fireEvent.click(screen.getByRole("button", { name: "Assess" }));

    await waitFor(() => {
      expect(screen.getByText("Remove Folder")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Remove Folder"));

    expect(confirmMock).toHaveBeenCalled();
  });

  it("shows Back to Dashboard link", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockEmptyFoldersResponse,
    });

    render(<EmptyFoldersPage />);

    expect(screen.getByText("← Back to Dashboard")).toBeInTheDocument();
  });

  it("shows results count", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockEmptyFoldersResponse,
    });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      // Text is split across span and text node - target specific div
      const resultsDiv = screen.getByText((content, element) => {
        // Match the specific div with class mb-4 that contains the results text
        return (
          element?.tagName === "DIV" &&
          element?.className?.includes("mb-4") &&
          element?.textContent?.includes("Showing 2 folders") || false
        );
      });
      expect(resultsDiv).toBeInTheDocument();
    });
  });

  it("select all selects all visible folders", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockEmptyFoldersResponse,
    });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      expect(screen.getByText("OldFolder")).toBeInTheDocument();
    });

    // Click select all
    fireEvent.click(screen.getByRole("checkbox", { name: /Select all folders/i }));

    // Text is split across span and text node
    expect(screen.getByText((content, element) => {
      return element?.textContent === "2 folders selected";
    })).toBeInTheDocument();
  });

  it("handles assessment API error gracefully", async () => {
    const alertMock = vi.spyOn(window, "alert").mockImplementation(() => {});

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockEmptyFoldersResponse,
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: "Assessment failed" }),
      });

    render(<EmptyFoldersPage />);

    await waitFor(() => {
      expect(screen.getByText("OldFolder")).toBeInTheDocument();
    });

    // Try to assess
    const assessButtons = screen.getAllByRole("button", { name: "Assess" });
    fireEvent.click(assessButtons[0]);

    await waitFor(() => {
      expect(alertMock).toHaveBeenCalledWith(
        expect.stringContaining("Failed to assess folder")
      );
    });
  });
});
