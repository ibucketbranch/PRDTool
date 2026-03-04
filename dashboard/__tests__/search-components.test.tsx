import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { SearchInput, EXAMPLE_QUERIES } from "@/components/SearchInput";
import { SearchResultCard } from "@/components/SearchResultCard";
import type { Document } from "@/lib/supabase";

describe("SearchInput", () => {
  const mockOnSearch = vi.fn();

  beforeEach(() => {
    mockOnSearch.mockClear();
  });

  it("renders search input and button", () => {
    render(<SearchInput onSearch={mockOnSearch} />);
    expect(screen.getByRole("textbox")).toBeDefined();
    expect(screen.getByRole("button", { name: "Search" })).toBeDefined();
  });

  it("renders example queries", () => {
    render(<SearchInput onSearch={mockOnSearch} />);
    expect(screen.getByText("Try an example query:")).toBeDefined();
    // Check that example queries are rendered as buttons
    for (const example of EXAMPLE_QUERIES) {
      expect(screen.getByRole("button", { name: example })).toBeDefined();
    }
  });

  it("calls onSearch when form is submitted", () => {
    render(<SearchInput onSearch={mockOnSearch} />);
    const input = screen.getByRole("textbox");
    const button = screen.getByRole("button", { name: "Search" });

    fireEvent.change(input, { target: { value: "test query" } });
    fireEvent.click(button);

    expect(mockOnSearch).toHaveBeenCalledWith("test query");
  });

  it("trims whitespace from query before searching", () => {
    render(<SearchInput onSearch={mockOnSearch} />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "  test query  " } });
    fireEvent.submit(input.closest("form")!);

    expect(mockOnSearch).toHaveBeenCalledWith("test query");
  });

  it("does not call onSearch for empty query", () => {
    render(<SearchInput onSearch={mockOnSearch} />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.submit(input.closest("form")!);

    expect(mockOnSearch).not.toHaveBeenCalled();
  });

  it("calls onSearch when example query is clicked", () => {
    render(<SearchInput onSearch={mockOnSearch} />);
    const exampleButton = screen.getByRole("button", {
      name: EXAMPLE_QUERIES[0],
    });

    fireEvent.click(exampleButton);

    expect(mockOnSearch).toHaveBeenCalledWith(EXAMPLE_QUERIES[0]);
  });

  it("updates input value when example query is clicked", () => {
    render(<SearchInput onSearch={mockOnSearch} />);
    const input = screen.getByRole("textbox") as HTMLInputElement;
    const exampleButton = screen.getByRole("button", {
      name: EXAMPLE_QUERIES[0],
    });

    fireEvent.click(exampleButton);

    expect(input.value).toBe(EXAMPLE_QUERIES[0]);
  });

  it("shows loading state when isLoading is true", () => {
    render(<SearchInput onSearch={mockOnSearch} isLoading={true} />);
    expect(screen.getByRole("button", { name: "Searching..." })).toBeDefined();
    expect(screen.getByRole("textbox")).toBeDisabled();
  });

  it("disables search button when input is empty", () => {
    render(<SearchInput onSearch={mockOnSearch} />);
    const button = screen.getByRole("button", { name: "Search" });
    expect(button).toBeDisabled();
  });

  it("enables search button when input has text", () => {
    render(<SearchInput onSearch={mockOnSearch} />);
    const input = screen.getByRole("textbox");
    const button = screen.getByRole("button", { name: "Search" });

    fireEvent.change(input, { target: { value: "test" } });

    expect(button).not.toBeDisabled();
  });

  it("disables example buttons when loading", () => {
    render(<SearchInput onSearch={mockOnSearch} isLoading={true} />);
    const exampleButton = screen.getByRole("button", {
      name: EXAMPLE_QUERIES[0],
    });
    expect(exampleButton).toBeDisabled();
  });

  it("uses initialQuery to set initial value", () => {
    render(
      <SearchInput onSearch={mockOnSearch} initialQuery="initial query" />
    );
    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.value).toBe("initial query");
  });

  it("applies custom className", () => {
    const { container } = render(
      <SearchInput onSearch={mockOnSearch} className="custom-class" />
    );
    expect(container.firstChild).toHaveClass("custom-class");
  });

  it("has placeholder text with example query", () => {
    render(<SearchInput onSearch={mockOnSearch} />);
    const input = screen.getByRole("textbox") as HTMLInputElement;
    // Placeholder should contain "Try:" prefix and one of the example queries
    expect(input.placeholder).toContain("Try:");
    expect(input.placeholder).toContain(EXAMPLE_QUERIES[0]);
  });

  it("rotates placeholder through example queries", () => {
    vi.useFakeTimers();
    render(<SearchInput onSearch={mockOnSearch} />);
    const input = screen.getByRole("textbox") as HTMLInputElement;

    // Initial placeholder should contain first example
    expect(input.placeholder).toContain(EXAMPLE_QUERIES[0]);

    // Advance timer to rotate to next example
    act(() => {
      vi.advanceTimersByTime(4000);
    });

    expect(input.placeholder).toContain(EXAMPLE_QUERIES[1]);

    // Advance again
    act(() => {
      vi.advanceTimersByTime(4000);
    });

    expect(input.placeholder).toContain(EXAMPLE_QUERIES[2]);

    vi.useRealTimers();
  });

  it("cycles placeholder back to first example after last one", () => {
    vi.useFakeTimers();
    render(<SearchInput onSearch={mockOnSearch} />);
    const input = screen.getByRole("textbox") as HTMLInputElement;

    // Advance through all examples
    for (let i = 0; i < EXAMPLE_QUERIES.length; i++) {
      act(() => {
        vi.advanceTimersByTime(4000);
      });
    }

    // Should cycle back to first example
    expect(input.placeholder).toContain(EXAMPLE_QUERIES[0]);

    vi.useRealTimers();
  });

  it("has aria-label for accessibility", () => {
    render(<SearchInput onSearch={mockOnSearch} />);
    expect(screen.getByLabelText("Search query")).toBeDefined();
  });
});

describe("SearchResultCard", () => {
  const mockDocument: Document = {
    id: "test-id-1",
    file_name: "Verizon_Bill_2024_03.pdf",
    current_path: "/Users/test/Documents/Bills/Verizon_Bill_2024_03.pdf",
    ai_category: "utility_bill",
    ai_subcategories: ["phone", "internet"],
    ai_summary: "Verizon bill for March 2024 totaling $89.99",
    entities: {
      organizations: ["Verizon"],
      amounts: ["$89.99"],
    },
    key_dates: ["2024-03-15", "2024-03-01"],
    folder_hierarchy: ["Documents", "Bills"],
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };

  it("renders document file name", () => {
    render(<SearchResultCard document={mockDocument} />);
    expect(screen.getByText("Verizon_Bill_2024_03.pdf")).toBeDefined();
  });

  it("renders document path as clickable button", () => {
    render(<SearchResultCard document={mockDocument} />);
    const pathButton = screen.getByRole("button", {
      name: mockDocument.current_path,
    });
    expect(pathButton).toBeDefined();
  });

  it("calls onPathClick when path is clicked", () => {
    const mockPathClick = vi.fn();
    render(
      <SearchResultCard document={mockDocument} onPathClick={mockPathClick} />
    );
    const pathButton = screen.getByRole("button", {
      name: mockDocument.current_path,
    });

    fireEvent.click(pathButton);

    expect(mockPathClick).toHaveBeenCalledWith(mockDocument.current_path);
  });

  it("renders formatted category name", () => {
    render(<SearchResultCard document={mockDocument} />);
    expect(screen.getByText("Utility Bill")).toBeDefined();
  });

  it("renders AI summary", () => {
    render(<SearchResultCard document={mockDocument} />);
    expect(
      screen.getByText("Verizon bill for March 2024 totaling $89.99")
    ).toBeDefined();
  });

  it("renders entities", () => {
    render(<SearchResultCard document={mockDocument} />);
    expect(screen.getByText("Organizations:")).toBeDefined();
    expect(screen.getByText("Verizon")).toBeDefined();
    expect(screen.getByText("Amounts:")).toBeDefined();
    expect(screen.getByText("$89.99")).toBeDefined();
  });

  it("renders formatted dates", () => {
    render(<SearchResultCard document={mockDocument} />);
    expect(screen.getByText(/2024-03-15/)).toBeDefined();
  });

  it("handles document without entities", () => {
    const docWithoutEntities: Document = {
      ...mockDocument,
      entities: null,
    };
    render(<SearchResultCard document={docWithoutEntities} />);
    expect(screen.queryByText("Organizations:")).toBeNull();
  });

  it("handles document without summary", () => {
    const docWithoutSummary: Document = {
      ...mockDocument,
      ai_summary: null,
    };
    const { container } = render(
      <SearchResultCard document={docWithoutSummary} />
    );
    expect(container.textContent).not.toContain("Verizon bill for March 2024");
  });

  it("handles document without dates", () => {
    const docWithoutDates: Document = {
      ...mockDocument,
      key_dates: null,
    };
    render(<SearchResultCard document={docWithoutDates} />);
    expect(screen.getByText("No dates")).toBeDefined();
  });

  it("handles document without category", () => {
    const docWithoutCategory: Document = {
      ...mockDocument,
      ai_category: null,
    };
    render(<SearchResultCard document={docWithoutCategory} />);
    expect(screen.getByText("Uncategorized")).toBeDefined();
  });

  it("truncates long entity lists", () => {
    const docWithManyOrgs: Document = {
      ...mockDocument,
      entities: {
        organizations: ["Org1", "Org2", "Org3", "Org4", "Org5"],
      },
    };
    render(<SearchResultCard document={docWithManyOrgs} />);
    // Should show first 3 and a "+2" indicator
    expect(screen.getByText("Org1")).toBeDefined();
    expect(screen.getByText("Org2")).toBeDefined();
    expect(screen.getByText("Org3")).toBeDefined();
    expect(screen.getByText("+2")).toBeDefined();
  });

  it("truncates long date lists", () => {
    const docWithManyDates: Document = {
      ...mockDocument,
      key_dates: ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"],
    };
    render(<SearchResultCard document={docWithManyDates} />);
    // Should show first 3 dates and "(+1 more)"
    expect(screen.getByText(/\+1 more/)).toBeDefined();
  });

  it("applies custom className", () => {
    const { container } = render(
      <SearchResultCard document={mockDocument} className="custom-class" />
    );
    expect(container.firstChild).toHaveClass("custom-class");
  });

  it("renders people entities when present", () => {
    const docWithPeople: Document = {
      ...mockDocument,
      entities: {
        people: ["John Doe", "Jane Smith"],
      },
    };
    render(<SearchResultCard document={docWithPeople} />);
    expect(screen.getByText("People:")).toBeDefined();
    expect(screen.getByText("John Doe")).toBeDefined();
    expect(screen.getByText("Jane Smith")).toBeDefined();
  });
});

describe("EXAMPLE_QUERIES constant", () => {
  it("contains expected example queries from PRD", () => {
    expect(EXAMPLE_QUERIES).toContain(
      "Show me a file that is a verizon bill from 2024?"
    );
    expect(EXAMPLE_QUERIES).toContain("Find all tax documents from 2023");
    expect(EXAMPLE_QUERIES).toContain("Show me VA claims documents");
    expect(EXAMPLE_QUERIES).toContain("Find invoices from Amazon");
  });

  it("has at least 5 example queries", () => {
    expect(EXAMPLE_QUERIES.length).toBeGreaterThanOrEqual(5);
  });
});

describe("Component exports", () => {
  it("exports SearchInput and SearchResultCard from index", async () => {
    const exports = await import("@/components");
    expect(exports.SearchInput).toBeDefined();
    expect(exports.SearchResultCard).toBeDefined();
    expect(exports.EXAMPLE_QUERIES).toBeDefined();
  });
});
