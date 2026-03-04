import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  StatisticsFilter,
  applyFiltersToCategories,
  applyFiltersToDateDistribution,
} from "@/components/StatisticsFilter";
import type { FilterOptions } from "@/components/StatisticsFilter";

// Mock ResizeObserver for any charts that might be rendered
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", ResizeObserverMock);
});

describe("StatisticsFilter", () => {
  const defaultFilters: FilterOptions = {
    category: null,
    startYear: null,
    endYear: null,
  };

  const mockCategories = ["tax_documents", "va_claims", "invoices"];
  const mockYears = [2022, 2023, 2024];

  describe("rendering", () => {
    it("renders filter toggle button", () => {
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );
      expect(screen.getByText("Filters")).toBeDefined();
    });

    it("shows 'Active' badge when filters are applied", () => {
      const activeFilters: FilterOptions = {
        category: "tax_documents",
        startYear: null,
        endYear: null,
      };
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={activeFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );
      expect(screen.getByText("Active")).toBeDefined();
    });

    it("does not show 'Active' badge when no filters are applied", () => {
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );
      expect(screen.queryByText("Active")).toBeNull();
    });

    it("shows 'Clear all' button when filters are active", () => {
      const activeFilters: FilterOptions = {
        category: "tax_documents",
        startYear: null,
        endYear: null,
      };
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={activeFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );
      expect(screen.getByText("Clear all")).toBeDefined();
    });

    it("hides 'Clear all' button when no filters are active", () => {
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );
      expect(screen.queryByText("Clear all")).toBeNull();
    });
  });

  describe("expand/collapse behavior", () => {
    it("expands filter panel when toggle is clicked", () => {
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );

      // Filter panel should be collapsed initially
      expect(document.getElementById("category-filter")).toBeNull();

      // Click to expand
      fireEvent.click(screen.getByText("Filters"));

      // Filter controls should now be visible
      expect(document.getElementById("category-filter")).toBeDefined();
      expect(document.getElementById("start-year-filter")).toBeDefined();
      expect(document.getElementById("end-year-filter")).toBeDefined();
    });

    it("collapses filter panel when toggle is clicked again", () => {
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );

      // Expand
      fireEvent.click(screen.getByText("Filters"));
      expect(document.getElementById("category-filter")).toBeDefined();

      // Collapse
      fireEvent.click(screen.getByText("Filters"));
      expect(document.getElementById("category-filter")).toBeNull();
    });
  });

  describe("category filter", () => {
    it("renders all category options", () => {
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );

      // Expand filter panel
      fireEvent.click(screen.getByText("Filters"));

      const categorySelect = document.getElementById("category-filter") as HTMLSelectElement;
      expect(categorySelect.options.length).toBe(4); // "All Categories" + 3 categories
    });

    it("calls onFilterChange when category is selected", () => {
      const onFilterChange = vi.fn();
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={defaultFilters}
          onFilterChange={onFilterChange}
          onClearFilters={vi.fn()}
        />
      );

      fireEvent.click(screen.getByText("Filters"));
      const categorySelect = document.getElementById("category-filter")!;
      fireEvent.change(categorySelect, { target: { value: "tax_documents" } });

      expect(onFilterChange).toHaveBeenCalledWith({
        category: "tax_documents",
        startYear: null,
        endYear: null,
      });
    });

    it("clears category filter when 'All Categories' is selected", () => {
      const onFilterChange = vi.fn();
      const activeFilters: FilterOptions = {
        category: "tax_documents",
        startYear: null,
        endYear: null,
      };
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={activeFilters}
          onFilterChange={onFilterChange}
          onClearFilters={vi.fn()}
        />
      );

      fireEvent.click(screen.getByText("Filters"));
      const categorySelect = document.getElementById("category-filter")!;
      fireEvent.change(categorySelect, { target: { value: "" } });

      expect(onFilterChange).toHaveBeenCalledWith({
        category: null,
        startYear: null,
        endYear: null,
      });
    });

    it("formats category names to title case in dropdown", () => {
      render(
        <StatisticsFilter
          categories={["tax_documents"]}
          years={mockYears}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );

      fireEvent.click(screen.getByText("Filters"));
      const categorySelect = document.getElementById("category-filter")!;
      const options = Array.from((categorySelect as HTMLSelectElement).options);

      const taxDocsOption = options.find(opt => opt.value === "tax_documents");
      expect(taxDocsOption?.text).toBe("Tax Documents");
    });
  });

  describe("year filters", () => {
    it("renders all year options sorted ascending", () => {
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={[2024, 2022, 2023]}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );

      fireEvent.click(screen.getByText("Filters"));
      const startYearSelect = document.getElementById("start-year-filter") as HTMLSelectElement;

      // "Any" + 3 years
      expect(startYearSelect.options.length).toBe(4);

      // Check order (excluding "Any" option at index 0)
      expect(startYearSelect.options[1].value).toBe("2022");
      expect(startYearSelect.options[2].value).toBe("2023");
      expect(startYearSelect.options[3].value).toBe("2024");
    });

    it("calls onFilterChange when start year is selected", () => {
      const onFilterChange = vi.fn();
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={defaultFilters}
          onFilterChange={onFilterChange}
          onClearFilters={vi.fn()}
        />
      );

      fireEvent.click(screen.getByText("Filters"));
      const startYearSelect = document.getElementById("start-year-filter")!;
      fireEvent.change(startYearSelect, { target: { value: "2022" } });

      expect(onFilterChange).toHaveBeenCalledWith({
        category: null,
        startYear: 2022,
        endYear: null,
      });
    });

    it("calls onFilterChange when end year is selected", () => {
      const onFilterChange = vi.fn();
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={defaultFilters}
          onFilterChange={onFilterChange}
          onClearFilters={vi.fn()}
        />
      );

      fireEvent.click(screen.getByText("Filters"));
      const endYearSelect = document.getElementById("end-year-filter")!;
      fireEvent.change(endYearSelect, { target: { value: "2024" } });

      expect(onFilterChange).toHaveBeenCalledWith({
        category: null,
        startYear: null,
        endYear: 2024,
      });
    });

    it("clears year filter when 'Any' is selected", () => {
      const onFilterChange = vi.fn();
      const activeFilters: FilterOptions = {
        category: null,
        startYear: 2022,
        endYear: null,
      };
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={activeFilters}
          onFilterChange={onFilterChange}
          onClearFilters={vi.fn()}
        />
      );

      fireEvent.click(screen.getByText("Filters"));
      const startYearSelect = document.getElementById("start-year-filter")!;
      fireEvent.change(startYearSelect, { target: { value: "" } });

      expect(onFilterChange).toHaveBeenCalledWith({
        category: null,
        startYear: null,
        endYear: null,
      });
    });
  });

  describe("clear filters", () => {
    it("calls onClearFilters when 'Clear all' button is clicked", () => {
      const onClearFilters = vi.fn();
      const activeFilters: FilterOptions = {
        category: "tax_documents",
        startYear: 2022,
        endYear: 2024,
      };
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={activeFilters}
          onFilterChange={vi.fn()}
          onClearFilters={onClearFilters}
        />
      );

      fireEvent.click(screen.getByText("Clear all"));
      expect(onClearFilters).toHaveBeenCalledTimes(1);
    });
  });

  describe("filter tags", () => {
    it("shows filter tags when collapsed and filters are active", () => {
      const activeFilters: FilterOptions = {
        category: "tax_documents",
        startYear: 2022,
        endYear: 2024,
      };
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={activeFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );

      // Panel is collapsed by default
      expect(screen.getByText(/Category: Tax Documents/)).toBeDefined();
      expect(screen.getByText("From: 2022")).toBeDefined();
      expect(screen.getByText("To: 2024")).toBeDefined();
    });

    it("removes category filter when tag remove button is clicked", () => {
      const onFilterChange = vi.fn();
      const activeFilters: FilterOptions = {
        category: "tax_documents",
        startYear: null,
        endYear: null,
      };
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={activeFilters}
          onFilterChange={onFilterChange}
          onClearFilters={vi.fn()}
        />
      );

      const removeButton = screen.getByLabelText(/Remove Category: Tax Documents filter/);
      fireEvent.click(removeButton);

      expect(onFilterChange).toHaveBeenCalledWith({
        category: null,
        startYear: null,
        endYear: null,
      });
    });

    it("removes start year filter when tag remove button is clicked", () => {
      const onFilterChange = vi.fn();
      const activeFilters: FilterOptions = {
        category: null,
        startYear: 2022,
        endYear: null,
      };
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={activeFilters}
          onFilterChange={onFilterChange}
          onClearFilters={vi.fn()}
        />
      );

      const removeButton = screen.getByLabelText("Remove From: 2022 filter");
      fireEvent.click(removeButton);

      expect(onFilterChange).toHaveBeenCalledWith({
        category: null,
        startYear: null,
        endYear: null,
      });
    });

    it("removes end year filter when tag remove button is clicked", () => {
      const onFilterChange = vi.fn();
      const activeFilters: FilterOptions = {
        category: null,
        startYear: null,
        endYear: 2024,
      };
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={activeFilters}
          onFilterChange={onFilterChange}
          onClearFilters={vi.fn()}
        />
      );

      const removeButton = screen.getByLabelText("Remove To: 2024 filter");
      fireEvent.click(removeButton);

      expect(onFilterChange).toHaveBeenCalledWith({
        category: null,
        startYear: null,
        endYear: null,
      });
    });

    it("hides filter tags when panel is expanded", () => {
      const activeFilters: FilterOptions = {
        category: "tax_documents",
        startYear: null,
        endYear: null,
      };
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={mockYears}
          filters={activeFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );

      // Tags visible when collapsed
      expect(screen.getByText(/Category: Tax Documents/)).toBeDefined();

      // Expand panel
      fireEvent.click(screen.getByText("Filters"));

      // Tags should be hidden when expanded (selects are shown instead)
      expect(screen.queryByText(/Category: Tax Documents/)).toBeNull();
    });
  });

  describe("empty states", () => {
    it("renders with empty categories array", () => {
      render(
        <StatisticsFilter
          categories={[]}
          years={mockYears}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );

      fireEvent.click(screen.getByText("Filters"));
      const categorySelect = document.getElementById("category-filter") as HTMLSelectElement;
      expect(categorySelect.options.length).toBe(1); // Only "All Categories"
    });

    it("renders with empty years array", () => {
      render(
        <StatisticsFilter
          categories={mockCategories}
          years={[]}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onClearFilters={vi.fn()}
        />
      );

      fireEvent.click(screen.getByText("Filters"));
      const startYearSelect = document.getElementById("start-year-filter") as HTMLSelectElement;
      expect(startYearSelect.options.length).toBe(1); // Only "Any"
    });
  });
});

describe("applyFiltersToCategories", () => {
  const categories = [
    { ai_category: "tax_documents", count: 45 },
    { ai_category: "va_claims", count: 23 },
    { ai_category: "invoices", count: 67 },
  ];

  it("returns all categories when no filter is applied", () => {
    const filters: FilterOptions = {
      category: null,
      startYear: null,
      endYear: null,
    };
    const result = applyFiltersToCategories(categories, filters);
    expect(result).toEqual(categories);
  });

  it("filters to single category when category filter is applied", () => {
    const filters: FilterOptions = {
      category: "tax_documents",
      startYear: null,
      endYear: null,
    };
    const result = applyFiltersToCategories(categories, filters);
    expect(result).toEqual([{ ai_category: "tax_documents", count: 45 }]);
  });

  it("returns empty array when category filter matches nothing", () => {
    const filters: FilterOptions = {
      category: "nonexistent",
      startYear: null,
      endYear: null,
    };
    const result = applyFiltersToCategories(categories, filters);
    expect(result).toEqual([]);
  });

  it("ignores year filters (categories don't have year data)", () => {
    const filters: FilterOptions = {
      category: null,
      startYear: 2022,
      endYear: 2024,
    };
    const result = applyFiltersToCategories(categories, filters);
    expect(result).toEqual(categories);
  });
});

describe("applyFiltersToDateDistribution", () => {
  const dateDistribution = [
    { year: 2020, count: 30 },
    { year: 2021, count: 40 },
    { year: 2022, count: 50 },
    { year: 2023, count: 60 },
    { year: 2024, count: 70 },
  ];

  it("returns all years when no filter is applied", () => {
    const filters: FilterOptions = {
      category: null,
      startYear: null,
      endYear: null,
    };
    const result = applyFiltersToDateDistribution(dateDistribution, filters);
    expect(result).toEqual(dateDistribution);
  });

  it("filters by start year", () => {
    const filters: FilterOptions = {
      category: null,
      startYear: 2022,
      endYear: null,
    };
    const result = applyFiltersToDateDistribution(dateDistribution, filters);
    expect(result).toEqual([
      { year: 2022, count: 50 },
      { year: 2023, count: 60 },
      { year: 2024, count: 70 },
    ]);
  });

  it("filters by end year", () => {
    const filters: FilterOptions = {
      category: null,
      startYear: null,
      endYear: 2022,
    };
    const result = applyFiltersToDateDistribution(dateDistribution, filters);
    expect(result).toEqual([
      { year: 2020, count: 30 },
      { year: 2021, count: 40 },
      { year: 2022, count: 50 },
    ]);
  });

  it("filters by both start and end year", () => {
    const filters: FilterOptions = {
      category: null,
      startYear: 2021,
      endYear: 2023,
    };
    const result = applyFiltersToDateDistribution(dateDistribution, filters);
    expect(result).toEqual([
      { year: 2021, count: 40 },
      { year: 2022, count: 50 },
      { year: 2023, count: 60 },
    ]);
  });

  it("returns empty array when no years match filter", () => {
    const filters: FilterOptions = {
      category: null,
      startYear: 2025,
      endYear: null,
    };
    const result = applyFiltersToDateDistribution(dateDistribution, filters);
    expect(result).toEqual([]);
  });

  it("includes boundary years (inclusive filtering)", () => {
    const filters: FilterOptions = {
      category: null,
      startYear: 2022,
      endYear: 2022,
    };
    const result = applyFiltersToDateDistribution(dateDistribution, filters);
    expect(result).toEqual([{ year: 2022, count: 50 }]);
  });

  it("ignores category filter (dates don't have category data)", () => {
    const filters: FilterOptions = {
      category: "tax_documents",
      startYear: null,
      endYear: null,
    };
    const result = applyFiltersToDateDistribution(dateDistribution, filters);
    expect(result).toEqual(dateDistribution);
  });
});

describe("Component exports", () => {
  it("exports StatisticsFilter and utility functions from index", async () => {
    const exports = await import("@/components");
    expect(exports.StatisticsFilter).toBeDefined();
    expect(exports.applyFiltersToCategories).toBeDefined();
    expect(exports.applyFiltersToDateDistribution).toBeDefined();
  });
});
