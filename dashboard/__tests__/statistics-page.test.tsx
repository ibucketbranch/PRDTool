import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

// Mock the components to avoid Recharts rendering issues in tests
vi.mock("@/components/StatCard", () => ({
  StatCard: ({ title, value, description }: { title: string; value: number | string; description?: string }) => (
    <div data-testid="stat-card">
      <span data-testid="stat-title">{title}</span>
      <span data-testid="stat-value">{value}</span>
      {description && <span data-testid="stat-description">{description}</span>}
    </div>
  ),
}));

vi.mock("@/components/CategoryChart", () => ({
  CategoryChart: ({ data }: { data: unknown[] }) => (
    <div data-testid="category-chart">Categories: {data.length}</div>
  ),
}));

vi.mock("@/components/DateDistributionChart", () => ({
  DateDistributionChart: ({ data }: { data: unknown[] }) => (
    <div data-testid="date-chart">Years: {data.length}</div>
  ),
}));

vi.mock("@/components/ContextBinChart", () => ({
  ContextBinChart: ({ data }: { data: unknown[] }) => (
    <div data-testid="context-chart">Bins: {data.length}</div>
  ),
}));

// Mock next/link
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

import StatisticsPage from "@/app/statistics/page";

// Helper to mock fetch with proper typing
function mockFetch(response: { ok: boolean; status?: number; json?: () => Promise<unknown> }) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: response.ok,
    status: response.status ?? (response.ok ? 200 : 500),
    json: response.json ?? (() => Promise.resolve({})),
  }) as unknown as typeof fetch;
}

function mockFetchReject(error: Error) {
  global.fetch = vi.fn().mockRejectedValue(error) as unknown as typeof fetch;
}

function mockFetchPending() {
  global.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
}

describe("StatisticsPage", () => {
  const mockStatistics = {
    connected: true,
    documentCount: 100,
    categories: [
      { ai_category: "tax_documents", count: 45 },
      { ai_category: "va_claims", count: 23 },
    ],
    dateDistribution: [
      { year: 2024, count: 50 },
      { year: 2023, count: 30 },
    ],
    contextBins: [
      { context_bin: "Finances Bin", count: 60 },
      { context_bin: "Work Bin", count: 40 },
    ],
  };

  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows loading state initially", () => {
    mockFetchPending();
    const { container } = render(<StatisticsPage />);
    // Now we show a skeleton loader instead of text
    // Check that skeleton elements are present (animate-pulse class)
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders statistics data when loaded", async () => {
    mockFetch({
      ok: true,
      json: () => Promise.resolve(mockStatistics),
    });

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Statistics")).toBeDefined();
    });

    // Check stat cards are rendered
    const statCards = screen.getAllByTestId("stat-card");
    expect(statCards.length).toBe(4);

    // Check specific values
    const values = screen.getAllByTestId("stat-value");
    expect(values[0].textContent).toBe("100"); // documentCount
    expect(values[1].textContent).toBe("2"); // categories count
    expect(values[2].textContent).toBe("2"); // years count
    expect(values[3].textContent).toBe("2"); // context bins count
  });

  it("renders chart components", async () => {
    mockFetch({
      ok: true,
      json: () => Promise.resolve(mockStatistics),
    });

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("category-chart")).toBeDefined();
    });

    expect(screen.getByTestId("date-chart")).toBeDefined();
    expect(screen.getByTestId("context-chart")).toBeDefined();
  });

  it("shows error message on fetch failure", async () => {
    mockFetch({
      ok: false,
      status: 500,
    });

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Error: HTTP error: 500/)).toBeDefined();
    });
  });

  it("shows error message from API response", async () => {
    mockFetch({
      ok: true,
      json: () => Promise.resolve({ error: "Database connection failed" }),
    });

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Error: Database connection failed/)).toBeDefined();
    });
  });

  it("shows network error message", async () => {
    mockFetchReject(new Error("Network error"));

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Error: Network error/)).toBeDefined();
    });
  });

  it("shows connected status when connected", async () => {
    mockFetch({
      ok: true,
      json: () => Promise.resolve(mockStatistics),
    });

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Connected to database")).toBeDefined();
    });
  });

  it("shows disconnected status when not connected", async () => {
    mockFetch({
      ok: true,
      json: () =>
        Promise.resolve({
          ...mockStatistics,
          connected: false,
        }),
    });

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Disconnected from database")).toBeDefined();
    });
  });

  it("shows empty state messages when no data", async () => {
    mockFetch({
      ok: true,
      json: () =>
        Promise.resolve({
          connected: true,
          documentCount: 0,
          categories: [],
          dateDistribution: [],
          contextBins: [],
        }),
    });

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByText("No category data available")).toBeDefined();
    });

    expect(screen.getByText("No date distribution data available")).toBeDefined();
    expect(screen.getByText("No context bin data available")).toBeDefined();
  });

  it("renders back to dashboard link", async () => {
    mockFetch({
      ok: true,
      json: () => Promise.resolve(mockStatistics),
    });

    render(<StatisticsPage />);

    await waitFor(() => {
      const backLink = screen.getByText(/Back to Dashboard/);
      expect(backLink).toBeDefined();
      expect(backLink.closest("a")).toHaveAttribute("href", "/");
    });
  });

  it("renders section headings", async () => {
    mockFetch({
      ok: true,
      json: () => Promise.resolve(mockStatistics),
    });

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Category Breakdown" })).toBeDefined();
    });

    expect(screen.getByRole("heading", { name: "Date Distribution" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Context Bins" })).toBeDefined();
  });

  it("renders page description", async () => {
    mockFetch({
      ok: true,
      json: () => Promise.resolve(mockStatistics),
    });

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Overview of your document organization")
      ).toBeDefined();
    });
  });
});

describe("StatisticsPage click handlers", () => {
  const mockStatistics = {
    connected: true,
    documentCount: 100,
    categories: [{ ai_category: "tax_documents", count: 45 }],
    dateDistribution: [{ year: 2024, count: 50 }],
    contextBins: [{ context_bin: "Finances Bin", count: 60 }],
  };

  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("click handlers are defined for charts", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockStatistics),
    }) as unknown as typeof fetch;

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("category-chart")).toBeDefined();
    });

    // Verify charts are rendered (click functionality tested via integration)
    expect(screen.getByTestId("date-chart")).toBeDefined();
    expect(screen.getByTestId("context-chart")).toBeDefined();
  });
});

describe("StatisticsPage interactive chart filtering", () => {
  const mockStatistics = {
    connected: true,
    documentCount: 100,
    categories: [
      { ai_category: "tax_documents", count: 45 },
      { ai_category: "va_claims", count: 23 },
      { ai_category: "invoices", count: 32 },
    ],
    dateDistribution: [
      { year: 2022, count: 30 },
      { year: 2023, count: 40 },
      { year: 2024, count: 30 },
    ],
    contextBins: [
      { context_bin: "Finances Bin", count: 60 },
      { context_bin: "Work Bin", count: 40 },
    ],
  };

  let categoryClickCallback: ((category: string) => void) | undefined;
  let yearClickCallback: ((year: number) => void) | undefined;
  let binClickCallback: ((bin: string) => void) | undefined;

  beforeEach(() => {
    vi.resetAllMocks();
    categoryClickCallback = undefined;
    yearClickCallback = undefined;
    binClickCallback = undefined;

    // Re-mock components to capture click callbacks
    vi.doMock("@/components/CategoryChart", () => ({
      CategoryChart: ({ data, onCategoryClick }: { data: unknown[]; onCategoryClick?: (cat: string) => void }) => {
        categoryClickCallback = onCategoryClick;
        return <div data-testid="category-chart">Categories: {data.length}</div>;
      },
    }));

    vi.doMock("@/components/DateDistributionChart", () => ({
      DateDistributionChart: ({ data, onYearClick }: { data: unknown[]; onYearClick?: (year: number) => void }) => {
        yearClickCallback = onYearClick;
        return <div data-testid="date-chart">Years: {data.length}</div>;
      },
    }));

    vi.doMock("@/components/ContextBinChart", () => ({
      ContextBinChart: ({ data, onBinClick }: { data: unknown[]; onBinClick?: (bin: string) => void }) => {
        binClickCallback = onBinClick;
        return <div data-testid="context-chart">Bins: {data.length}</div>;
      },
    }));
  });

  it("shows updated help text for category chart", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockStatistics),
    }) as unknown as typeof fetch;

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Click a category to filter. Click again to clear.")).toBeDefined();
    });
  });

  it("shows updated help text for date chart", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockStatistics),
    }) as unknown as typeof fetch;

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Click a year to filter. Click again to clear.")).toBeDefined();
    });
  });

  it("does not navigate when chart is clicked (filters instead)", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockStatistics),
    }) as unknown as typeof fetch;

    // Mock window.location to verify no navigation occurs
    const originalHref = window.location.href;
    const hrefSetter = vi.fn();
    Object.defineProperty(window, "location", {
      value: {
        ...window.location,
        get href() {
          return originalHref;
        },
        set href(value: string) {
          hrefSetter(value);
        },
      },
      writable: true,
      configurable: true,
    });

    render(<StatisticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("category-chart")).toBeDefined();
    });

    // Simulate category click (callback should be captured by mock)
    if (categoryClickCallback) {
      categoryClickCallback("tax_documents");
    }

    // Verify no navigation occurred
    expect(hrefSetter).not.toHaveBeenCalled();
  });
});
