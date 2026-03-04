import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  DocumentBrowserFilter,
  DEFAULT_DOCUMENT_FILTERS,
} from "@/components/DocumentBrowserFilter";
import { DocumentTable } from "@/components/DocumentTable";
import { Pagination } from "@/components/Pagination";
import type { DocumentFilterOptions, SortField } from "@/components";
import type { Document } from "@/lib/supabase";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

describe("DocumentBrowserFilter", () => {
  const mockCategories = ["tax_documents", "va_claims", "invoices"];
  const mockContextBins = ["Finances Bin", "Work Bin", "Personal Bin"];
  const mockYears = [2024, 2023, 2022];
  const mockFilters: DocumentFilterOptions = DEFAULT_DOCUMENT_FILTERS;
  const mockOnFilterChange = vi.fn();
  const mockOnClearFilters = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders toggle button", () => {
    render(
      <DocumentBrowserFilter
        categories={mockCategories}
        contextBins={mockContextBins}
        years={mockYears}
        filters={mockFilters}
        onFilterChange={mockOnFilterChange}
        onClearFilters={mockOnClearFilters}
      />
    );
    expect(screen.getByRole("button", { name: /filters/i })).toBeDefined();
  });

  it("shows filter panel by default", () => {
    render(
      <DocumentBrowserFilter
        categories={mockCategories}
        contextBins={mockContextBins}
        years={mockYears}
        filters={mockFilters}
        onFilterChange={mockOnFilterChange}
        onClearFilters={mockOnClearFilters}
      />
    );
    expect(screen.getByLabelText("Search")).toBeDefined();
    expect(screen.getByLabelText("Category")).toBeDefined();
    expect(screen.getByLabelText("Context Bin")).toBeDefined();
  });

  it("shows Active badge when filters are applied", () => {
    const activeFilters: DocumentFilterOptions = {
      ...mockFilters,
      category: "tax_documents",
    };
    render(
      <DocumentBrowserFilter
        categories={mockCategories}
        contextBins={mockContextBins}
        years={mockYears}
        filters={activeFilters}
        onFilterChange={mockOnFilterChange}
        onClearFilters={mockOnClearFilters}
      />
    );
    expect(screen.getByText("Active")).toBeDefined();
  });

  it("shows Clear all button when filters are applied", () => {
    const activeFilters: DocumentFilterOptions = {
      ...mockFilters,
      category: "tax_documents",
    };
    render(
      <DocumentBrowserFilter
        categories={mockCategories}
        contextBins={mockContextBins}
        years={mockYears}
        filters={activeFilters}
        onFilterChange={mockOnFilterChange}
        onClearFilters={mockOnClearFilters}
      />
    );
    expect(screen.getByText("Clear all")).toBeDefined();
  });

  it("calls onClearFilters when Clear all is clicked", () => {
    const activeFilters: DocumentFilterOptions = {
      ...mockFilters,
      category: "tax_documents",
    };
    render(
      <DocumentBrowserFilter
        categories={mockCategories}
        contextBins={mockContextBins}
        years={mockYears}
        filters={activeFilters}
        onFilterChange={mockOnFilterChange}
        onClearFilters={mockOnClearFilters}
      />
    );
    fireEvent.click(screen.getByText("Clear all"));
    expect(mockOnClearFilters).toHaveBeenCalled();
  });

  it("calls onFilterChange when category is selected", () => {
    render(
      <DocumentBrowserFilter
        categories={mockCategories}
        contextBins={mockContextBins}
        years={mockYears}
        filters={mockFilters}
        onFilterChange={mockOnFilterChange}
        onClearFilters={mockOnClearFilters}
      />
    );
    fireEvent.change(screen.getByLabelText("Category"), {
      target: { value: "tax_documents" },
    });
    expect(mockOnFilterChange).toHaveBeenCalledWith({
      ...mockFilters,
      category: "tax_documents",
    });
  });

  it("calls onFilterChange when context bin is selected", () => {
    render(
      <DocumentBrowserFilter
        categories={mockCategories}
        contextBins={mockContextBins}
        years={mockYears}
        filters={mockFilters}
        onFilterChange={mockOnFilterChange}
        onClearFilters={mockOnClearFilters}
      />
    );
    fireEvent.change(screen.getByLabelText("Context Bin"), {
      target: { value: "Finances Bin" },
    });
    expect(mockOnFilterChange).toHaveBeenCalledWith({
      ...mockFilters,
      contextBin: "Finances Bin",
    });
  });

  it("calls onFilterChange when search is entered", () => {
    render(
      <DocumentBrowserFilter
        categories={mockCategories}
        contextBins={mockContextBins}
        years={mockYears}
        filters={mockFilters}
        onFilterChange={mockOnFilterChange}
        onClearFilters={mockOnClearFilters}
      />
    );
    fireEvent.change(screen.getByLabelText("Search"), {
      target: { value: "test query" },
    });
    expect(mockOnFilterChange).toHaveBeenCalledWith({
      ...mockFilters,
      search: "test query",
    });
  });

  it("calls onFilterChange when start year is selected", () => {
    render(
      <DocumentBrowserFilter
        categories={mockCategories}
        contextBins={mockContextBins}
        years={mockYears}
        filters={mockFilters}
        onFilterChange={mockOnFilterChange}
        onClearFilters={mockOnClearFilters}
      />
    );
    fireEvent.change(screen.getByLabelText("Start Year"), {
      target: { value: "2023" },
    });
    expect(mockOnFilterChange).toHaveBeenCalledWith({
      ...mockFilters,
      startYear: 2023,
    });
  });

  it("formats category names in dropdown", () => {
    render(
      <DocumentBrowserFilter
        categories={mockCategories}
        contextBins={mockContextBins}
        years={mockYears}
        filters={mockFilters}
        onFilterChange={mockOnFilterChange}
        onClearFilters={mockOnClearFilters}
      />
    );
    const categorySelect = screen.getByLabelText("Category");
    expect(categorySelect).toBeDefined();
    // Should have "Tax Documents" as an option
    const options = categorySelect.querySelectorAll("option");
    expect(options.length).toBe(4); // "All Categories" + 3 categories
  });

  it("sorts years ascending in dropdown", () => {
    const unsortedYears = [2024, 2020, 2022];
    render(
      <DocumentBrowserFilter
        categories={mockCategories}
        contextBins={mockContextBins}
        years={unsortedYears}
        filters={mockFilters}
        onFilterChange={mockOnFilterChange}
        onClearFilters={mockOnClearFilters}
      />
    );
    const startYearSelect = screen.getByLabelText("Start Year");
    const options = Array.from(startYearSelect.querySelectorAll("option")).map(
      (opt) => opt.textContent
    );
    // First option is "Any", then years sorted ascending
    expect(options).toEqual(["Any", "2020", "2022", "2024"]);
  });

  it("toggles filter panel expansion", () => {
    render(
      <DocumentBrowserFilter
        categories={mockCategories}
        contextBins={mockContextBins}
        years={mockYears}
        filters={mockFilters}
        onFilterChange={mockOnFilterChange}
        onClearFilters={mockOnClearFilters}
      />
    );
    const toggleButton = screen.getByRole("button", { name: /filters/i });

    // Panel is expanded by default
    expect(screen.getByLabelText("Search")).toBeDefined();

    // Click to collapse
    fireEvent.click(toggleButton);
    expect(screen.queryByLabelText("Search")).toBeNull();

    // Click to expand again
    fireEvent.click(toggleButton);
    expect(screen.getByLabelText("Search")).toBeDefined();
  });
});

describe("DEFAULT_DOCUMENT_FILTERS", () => {
  it("has null values for all filter fields", () => {
    expect(DEFAULT_DOCUMENT_FILTERS.category).toBeNull();
    expect(DEFAULT_DOCUMENT_FILTERS.contextBin).toBeNull();
    expect(DEFAULT_DOCUMENT_FILTERS.startYear).toBeNull();
    expect(DEFAULT_DOCUMENT_FILTERS.endYear).toBeNull();
    expect(DEFAULT_DOCUMENT_FILTERS.search).toBe("");
  });
});

describe("DocumentTable", () => {
  const mockDocuments: Document[] = [
    {
      id: "1",
      file_name: "test_document.pdf",
      current_path: "/Users/test/Documents/test_document.pdf",
      ai_category: "tax_documents",
      ai_subcategories: null,
      ai_summary: "A test document summary",
      entities: { organizations: ["IRS"], amounts: ["$1000"] },
      key_dates: ["2024-01-15", "2024-02-20"],
      folder_hierarchy: ["Documents", "Tax"],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "2",
      file_name: "another_file.pdf",
      current_path: "/Users/test/Work/another_file.pdf",
      ai_category: "va_claims",
      ai_subcategories: null,
      ai_summary: null,
      entities: null,
      key_dates: null,
      folder_hierarchy: null,
      created_at: "2024-02-01T00:00:00Z",
      updated_at: "2024-02-01T00:00:00Z",
    },
  ];

  const mockOnSortChange = vi.fn();
  const mockOnPathClick = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders table with documents", () => {
    render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );
    // Documents render in both mobile and desktop views, so use getAllByText
    expect(screen.getAllByText("test_document.pdf").length).toBeGreaterThan(0);
    expect(screen.getAllByText("another_file.pdf").length).toBeGreaterThan(0);
  });

  it("renders empty state when no documents", () => {
    render(
      <DocumentTable
        documents={[]}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );
    expect(screen.getByText("No documents found")).toBeDefined();
  });

  it("renders table headers in desktop view", () => {
    const { container } = render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );
    // Check desktop view contains headers
    const desktopView = container.querySelector(".hidden.md\\:block");
    expect(desktopView).not.toBeNull();
    if (desktopView) {
      expect(desktopView.textContent).toContain("Name");
      expect(desktopView.textContent).toContain("Path");
      expect(desktopView.textContent).toContain("Category");
      expect(desktopView.textContent).toContain("Dates");
      expect(desktopView.textContent).toContain("Context Bin");
      expect(desktopView.textContent).toContain("Created");
    }
  });

  it("calls onSortChange when header is clicked in desktop view", () => {
    const { container } = render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );
    // Get the desktop view and click the Name header within it
    const desktopView = container.querySelector(".hidden.md\\:block") as Element;
    const nameHeader = desktopView?.querySelector("th button");
    if (nameHeader) {
      fireEvent.click(nameHeader);
      expect(mockOnSortChange).toHaveBeenCalledWith("file_name");
    }
  });

  it("calls onPathClick when path is clicked", () => {
    render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );
    // Find all path buttons by title attribute (exists in both mobile and desktop views)
    const pathButtons = screen.getAllByTitle("/Users/test/Documents/test_document.pdf");
    expect(pathButtons.length).toBeGreaterThan(0);
    fireEvent.click(pathButtons[0]);
    expect(mockOnPathClick).toHaveBeenCalledWith("/Users/test/Documents/test_document.pdf");
  });

  it("formats category names", () => {
    render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );
    // Categories render in both views
    expect(screen.getAllByText("Tax Documents").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Va Claims").length).toBeGreaterThan(0);
  });

  it("displays dates from key_dates array", () => {
    render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );
    expect(screen.getByText("2024-01-15, 2024-02-20")).toBeDefined();
  });

  it("displays dash for missing dates", () => {
    render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );
    // Second document has no key_dates
    expect(screen.getAllByText("-")).toBeDefined();
  });

  it("displays context bin from folder_hierarchy", () => {
    const { container } = render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );
    // Context bin appears in desktop view table
    const desktopView = container.querySelector(".hidden.md\\:block");
    expect(desktopView?.textContent).toContain("Documents"); // First item in hierarchy
  });

  it("truncates long paths", () => {
    const longPath = "/Users/very/long/path/that/exceeds/the/maximum/length/for/display/test_file.pdf";
    const longPathDoc: Document = {
      ...mockDocuments[0],
      current_path: longPath,
    };
    render(
      <DocumentTable
        documents={[longPathDoc]}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );
    // Path should be truncated (contains "...") - find all by title attribute
    const pathButtons = screen.getAllByTitle(longPath);
    expect(pathButtons.length).toBeGreaterThan(0);
    expect(pathButtons[0].textContent).toContain("...");
  });
});

describe("Pagination", () => {
  const mockOnPageChange = vi.fn();
  const mockOnItemsPerPageChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders page info correctly", () => {
    render(
      <Pagination
        currentPage={1}
        totalPages={5}
        totalItems={100}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    expect(screen.getByText(/Showing 1-20 of 100 documents/)).toBeDefined();
  });

  it("shows correct range on middle page", () => {
    render(
      <Pagination
        currentPage={3}
        totalPages={5}
        totalItems={100}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    expect(screen.getByText(/Showing 41-60 of 100 documents/)).toBeDefined();
  });

  it("shows correct range on last page with partial items", () => {
    render(
      <Pagination
        currentPage={5}
        totalPages={5}
        totalItems={95}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    expect(screen.getByText(/Showing 81-95 of 95 documents/)).toBeDefined();
  });

  it("shows 0-0 when no items", () => {
    render(
      <Pagination
        currentPage={1}
        totalPages={0}
        totalItems={0}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    expect(screen.getByText(/Showing 0-0 of 0 documents/)).toBeDefined();
  });

  it("renders items per page selector", () => {
    render(
      <Pagination
        currentPage={1}
        totalPages={5}
        totalItems={100}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    expect(screen.getByLabelText("Per page:")).toBeDefined();
    const select = screen.getByRole("combobox");
    expect(select).toHaveValue("20");
  });

  it("calls onItemsPerPageChange when selection changes", () => {
    render(
      <Pagination
        currentPage={1}
        totalPages={5}
        totalItems={100}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "50" },
    });
    expect(mockOnItemsPerPageChange).toHaveBeenCalledWith(50);
  });

  it("renders Previous and Next buttons", () => {
    render(
      <Pagination
        currentPage={2}
        totalPages={5}
        totalItems={100}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    expect(screen.getByText("Previous")).toBeDefined();
    expect(screen.getByText("Next")).toBeDefined();
  });

  it("disables Previous on first page", () => {
    render(
      <Pagination
        currentPage={1}
        totalPages={5}
        totalItems={100}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    const prevButton = screen.getByText("Previous");
    expect(prevButton).toBeDisabled();
  });

  it("disables Next on last page", () => {
    render(
      <Pagination
        currentPage={5}
        totalPages={5}
        totalItems={100}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    const nextButton = screen.getByText("Next");
    expect(nextButton).toBeDisabled();
  });

  it("calls onPageChange when Previous is clicked", () => {
    render(
      <Pagination
        currentPage={3}
        totalPages={5}
        totalItems={100}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    fireEvent.click(screen.getByText("Previous"));
    expect(mockOnPageChange).toHaveBeenCalledWith(2);
  });

  it("calls onPageChange when Next is clicked", () => {
    render(
      <Pagination
        currentPage={3}
        totalPages={5}
        totalItems={100}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    fireEvent.click(screen.getByText("Next"));
    expect(mockOnPageChange).toHaveBeenCalledWith(4);
  });

  it("renders page number buttons", () => {
    render(
      <Pagination
        currentPage={3}
        totalPages={5}
        totalItems={100}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    expect(screen.getByRole("button", { name: "Page 1" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Page 3" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Page 5" })).toBeDefined();
  });

  it("calls onPageChange when page number is clicked", () => {
    render(
      <Pagination
        currentPage={1}
        totalPages={5}
        totalItems={100}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Page 3" }));
    expect(mockOnPageChange).toHaveBeenCalledWith(3);
  });

  it("highlights current page", () => {
    render(
      <Pagination
        currentPage={3}
        totalPages={5}
        totalItems={100}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    const currentPageButton = screen.getByRole("button", { name: "Page 3" });
    expect(currentPageButton).toHaveAttribute("aria-current", "page");
  });

  it("shows ellipsis for many pages", () => {
    render(
      <Pagination
        currentPage={5}
        totalPages={10}
        totalItems={200}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    expect(screen.getAllByText("...").length).toBeGreaterThan(0);
  });

  it("does not show navigation when single page", () => {
    render(
      <Pagination
        currentPage={1}
        totalPages={1}
        totalItems={15}
        itemsPerPage={20}
        onPageChange={mockOnPageChange}
        onItemsPerPageChange={mockOnItemsPerPageChange}
      />
    );
    expect(screen.queryByText("Previous")).toBeNull();
    expect(screen.queryByText("Next")).toBeNull();
  });
});

describe("Component exports", () => {
  it("exports document browser components from index", async () => {
    const exports = await import("@/components");
    expect(exports.DocumentBrowserFilter).toBeDefined();
    expect(exports.DEFAULT_DOCUMENT_FILTERS).toBeDefined();
    expect(exports.DocumentTable).toBeDefined();
    expect(exports.Pagination).toBeDefined();
  });
});
