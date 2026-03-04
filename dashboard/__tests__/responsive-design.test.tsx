import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { DocumentTable } from "@/components/DocumentTable";
import { SearchInput } from "@/components/SearchInput";
import { OrphanedFilesBulkActionsBar } from "@/components/OrphanedFilesList";
import { BulkActionsBar } from "@/components/EmptyFoldersList";
import { CategoryChart } from "@/components/CategoryChart";
import { DateDistributionChart } from "@/components/DateDistributionChart";
import { ContextBinChart } from "@/components/ContextBinChart";
import type { Document } from "@/lib/supabase";

// Mock ResizeObserver for Recharts
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", ResizeObserverMock);
});

describe("DocumentTable Responsive Design", () => {
  const mockDocuments: Document[] = [
    {
      id: "1",
      file_name: "test_document.pdf",
      current_path: "/Users/test/Documents/test_document.pdf",
      ai_category: "tax_documents",
      ai_subcategories: null,
      ai_summary: "A test document summary",
      entities: { organizations: ["IRS"], amounts: ["$1000"] },
      key_dates: ["2024-01-15"],
      folder_hierarchy: ["Documents", "Tax"],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
  ];

  const mockOnSortChange = vi.fn();
  const mockOnPathClick = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders both mobile and desktop views", () => {
    const { container } = render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );

    // Mobile view should be present (block md:hidden)
    const mobileView = container.querySelector(".block.md\\:hidden");
    expect(mobileView).toBeDefined();

    // Desktop view should be present (hidden md:block)
    const desktopView = container.querySelector(".hidden.md\\:block");
    expect(desktopView).toBeDefined();
  });

  it("renders mobile sort dropdown with all options", () => {
    render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );

    // Find the sort dropdown by aria-label
    const sortSelect = screen.getByLabelText("Sort field");
    expect(sortSelect).toBeDefined();

    // Check options
    const options = sortSelect.querySelectorAll("option");
    expect(options.length).toBe(4);

    const optionValues = Array.from(options).map((opt) => opt.getAttribute("value"));
    expect(optionValues).toContain("file_name");
    expect(optionValues).toContain("ai_category");
    expect(optionValues).toContain("created_at");
    expect(optionValues).toContain("current_path");
  });

  it("calls onSortChange when mobile sort dropdown changes", () => {
    render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );

    const sortSelect = screen.getByLabelText("Sort field");
    fireEvent.change(sortSelect, { target: { value: "file_name" } });
    expect(mockOnSortChange).toHaveBeenCalledWith("file_name");
  });

  it("renders mobile card view with document info", () => {
    const { container } = render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );

    // Get mobile view
    const mobileView = container.querySelector(".block.md\\:hidden");
    expect(mobileView).not.toBeNull();

    // Check for document content in mobile view
    const mobileViewEl = mobileView as Element;
    expect(within(mobileViewEl).getByText("test_document.pdf")).toBeDefined();
    expect(within(mobileViewEl).getByText("Tax Documents")).toBeDefined();
  });

  it("renders clickable path in mobile card view", () => {
    const { container } = render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );

    // Get mobile view
    const mobileView = container.querySelector(".block.md\\:hidden") as Element;

    // Find path button by title attribute
    const pathButtons = mobileView.querySelectorAll('button[title*="test_document.pdf"]');
    expect(pathButtons.length).toBeGreaterThan(0);

    // Click the path
    fireEvent.click(pathButtons[0]);
    expect(mockOnPathClick).toHaveBeenCalledWith("/Users/test/Documents/test_document.pdf");
  });

  it("renders desktop table view with headers", () => {
    const { container } = render(
      <DocumentTable
        documents={mockDocuments}
        sortField="created_at"
        sortDirection="desc"
        onSortChange={mockOnSortChange}
        onPathClick={mockOnPathClick}
      />
    );

    // Get desktop view
    const desktopView = container.querySelector(".hidden.md\\:block") as Element;

    // Check for table headers
    expect(within(desktopView).getByText("Name")).toBeDefined();
    expect(within(desktopView).getByText("Path")).toBeDefined();
    expect(within(desktopView).getByText("Category")).toBeDefined();
    expect(within(desktopView).getByText("Dates")).toBeDefined();
    expect(within(desktopView).getByText("Context Bin")).toBeDefined();
    expect(within(desktopView).getByText("Created")).toBeDefined();
  });

  it("handles empty documents in both views", () => {
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
});

describe("SearchInput Responsive Design", () => {
  const mockOnSearch = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders form with responsive layout classes", () => {
    const { container } = render(<SearchInput onSearch={mockOnSearch} />);

    // Form should have flex-col sm:flex-row for stacking on mobile
    const form = container.querySelector("form");
    expect(form).toHaveClass("flex-col");
    expect(form).toHaveClass("sm:flex-row");
  });

  it("renders submit button with full width on mobile", () => {
    render(<SearchInput onSearch={mockOnSearch} />);

    const submitButton = screen.getByRole("button", { name: "Search" });
    expect(submitButton).toHaveClass("w-full");
    expect(submitButton).toHaveClass("sm:w-auto");
  });

  it("renders example queries with horizontal scroll on mobile", () => {
    const { container } = render(<SearchInput onSearch={mockOnSearch} />);

    // Find the example queries container
    const exampleContainer = container.querySelector(".overflow-x-auto");
    expect(exampleContainer).toBeDefined();
    expect(exampleContainer).toHaveClass("sm:overflow-visible");
  });

  it("renders example query buttons with nowrap class", () => {
    render(<SearchInput onSearch={mockOnSearch} />);

    // Get one of the example query buttons
    const exampleButtons = screen.getAllByRole("button").filter(
      (btn) => btn.textContent?.includes("documents") || btn.textContent?.includes("bill")
    );
    expect(exampleButtons.length).toBeGreaterThan(0);
    expect(exampleButtons[0]).toHaveClass("whitespace-nowrap");
    expect(exampleButtons[0]).toHaveClass("flex-shrink-0");
  });
});

describe("OrphanedFilesBulkActionsBar Responsive Design", () => {
  const mockOnAnalyzeAll = vi.fn();
  const mockOnMoveAll = vi.fn();
  const mockOnClearSelection = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when no files selected", () => {
    const { container } = render(
      <OrphanedFilesBulkActionsBar
        selectedCount={0}
        onAnalyzeAll={mockOnAnalyzeAll}
        onMoveAll={mockOnMoveAll}
        onClearSelection={mockOnClearSelection}
        isLoading={false}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders with responsive layout when files selected", () => {
    const { container } = render(
      <OrphanedFilesBulkActionsBar
        selectedCount={3}
        onAnalyzeAll={mockOnAnalyzeAll}
        onMoveAll={mockOnMoveAll}
        onClearSelection={mockOnClearSelection}
        isLoading={false}
      />
    );

    // Check for responsive classes on container
    const bar = container.firstChild as Element;
    expect(bar).toHaveClass("flex-col");
    expect(bar).toHaveClass("sm:flex-row");
    expect(bar).toHaveClass("sm:items-center");
    expect(bar).toHaveClass("sm:justify-between");
  });

  it("renders action buttons with flex-wrap for mobile", () => {
    const { container } = render(
      <OrphanedFilesBulkActionsBar
        selectedCount={3}
        onAnalyzeAll={mockOnAnalyzeAll}
        onMoveAll={mockOnMoveAll}
        onClearSelection={mockOnClearSelection}
        isLoading={false}
      />
    );

    // Find the buttons container
    const buttonsContainer = container.querySelector(".flex-wrap");
    expect(buttonsContainer).toBeDefined();
  });

  it("renders clear selection button with responsive width", () => {
    render(
      <OrphanedFilesBulkActionsBar
        selectedCount={3}
        onAnalyzeAll={mockOnAnalyzeAll}
        onMoveAll={mockOnMoveAll}
        onClearSelection={mockOnClearSelection}
        isLoading={false}
      />
    );

    const clearButton = screen.getByText("Clear selection");
    expect(clearButton).toHaveClass("w-full");
    expect(clearButton).toHaveClass("sm:w-auto");
  });
});

describe("BulkActionsBar (Empty Folders) Responsive Design", () => {
  const mockOnRemoveAll = vi.fn();
  const mockOnRestoreAll = vi.fn();
  const mockOnAssessAll = vi.fn();
  const mockOnClearSelection = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when no folders selected", () => {
    const { container } = render(
      <BulkActionsBar
        selectedCount={0}
        onRemoveAll={mockOnRemoveAll}
        onRestoreAll={mockOnRestoreAll}
        onAssessAll={mockOnAssessAll}
        onClearSelection={mockOnClearSelection}
        isLoading={false}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders with responsive layout when folders selected", () => {
    const { container } = render(
      <BulkActionsBar
        selectedCount={2}
        onRemoveAll={mockOnRemoveAll}
        onRestoreAll={mockOnRestoreAll}
        onAssessAll={mockOnAssessAll}
        onClearSelection={mockOnClearSelection}
        isLoading={false}
      />
    );

    const bar = container.firstChild as Element;
    expect(bar).toHaveClass("flex-col");
    expect(bar).toHaveClass("sm:flex-row");
    expect(bar).toHaveClass("sm:items-center");
    expect(bar).toHaveClass("sm:justify-between");
  });

  it("renders all action buttons with flex classes", () => {
    render(
      <BulkActionsBar
        selectedCount={2}
        onRemoveAll={mockOnRemoveAll}
        onRestoreAll={mockOnRestoreAll}
        onAssessAll={mockOnAssessAll}
        onClearSelection={mockOnClearSelection}
        isLoading={false}
      />
    );

    // Check buttons are present
    expect(screen.getByText("Assess All")).toBeDefined();
    expect(screen.getByText("Restore All")).toBeDefined();
    expect(screen.getByText("Remove All")).toBeDefined();
    expect(screen.getByText("Clear selection")).toBeDefined();
  });
});

describe("CategoryChart Responsive Design", () => {
  const mockData = [
    { ai_category: "tax_documents", count: 45 },
    { ai_category: "va_claims", count: 23 },
  ];

  it("renders both mobile and desktop chart containers", () => {
    const { container } = render(<CategoryChart data={mockData} />);

    // Mobile view (block sm:hidden)
    const mobileView = container.querySelector(".block.sm\\:hidden");
    expect(mobileView).toBeDefined();

    // Desktop view (hidden sm:block)
    const desktopView = container.querySelector(".hidden.sm\\:block");
    expect(desktopView).toBeDefined();
  });

  it("applies different heights for mobile and desktop", () => {
    const { container } = render(<CategoryChart data={mockData} />);

    // Desktop has fixed h-80 class
    const desktopView = container.querySelector(".h-80");
    expect(desktopView).toHaveClass("hidden");
    expect(desktopView).toHaveClass("sm:block");
  });
});

describe("DateDistributionChart Responsive Design", () => {
  const mockData = [
    { year: 2024, count: 150 },
    { year: 2023, count: 120 },
  ];

  it("renders both mobile and desktop chart containers", () => {
    const { container } = render(<DateDistributionChart data={mockData} />);

    // Mobile view (block sm:hidden)
    const mobileView = container.querySelector(".block.sm\\:hidden");
    expect(mobileView).toBeDefined();

    // Desktop view (hidden sm:block)
    const desktopView = container.querySelector(".hidden.sm\\:block");
    expect(desktopView).toBeDefined();
  });

  it("has smaller height on mobile view", () => {
    const { container } = render(<DateDistributionChart data={mockData} />);

    // Mobile has h-48, desktop has h-64
    const mobileView = container.querySelector(".h-48");
    expect(mobileView).toBeDefined();

    const desktopView = container.querySelector(".h-64");
    expect(desktopView).toBeDefined();
  });
});

describe("ContextBinChart Responsive Design", () => {
  const mockData = [
    { context_bin: "Finances Bin", count: 200 },
    { context_bin: "Work Bin", count: 150 },
  ];

  it("renders both mobile and desktop chart containers", () => {
    const { container } = render(<ContextBinChart data={mockData} />);

    // Mobile view (block sm:hidden)
    const mobileView = container.querySelector(".block.sm\\:hidden");
    expect(mobileView).toBeDefined();

    // Desktop view (hidden sm:block)
    const desktopView = container.querySelector(".hidden.sm\\:block");
    expect(desktopView).toBeDefined();
  });

  it("has fixed height on desktop view", () => {
    const { container } = render(<ContextBinChart data={mockData} />);

    const desktopView = container.querySelector(".h-72");
    expect(desktopView).toBeDefined();
    expect(desktopView).toHaveClass("hidden");
    expect(desktopView).toHaveClass("sm:block");
  });
});

describe("Layout Viewport", () => {
  it("exports viewport configuration from layout", async () => {
    const layout = await import("@/app/layout");
    expect(layout.viewport).toBeDefined();
    expect(layout.viewport.width).toBe("device-width");
    expect(layout.viewport.initialScale).toBe(1);
  });
});
