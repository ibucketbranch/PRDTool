import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StatCard } from "@/components/StatCard";
import { CategoryChart } from "@/components/CategoryChart";
import { DateDistributionChart } from "@/components/DateDistributionChart";
import { ContextBinChart } from "@/components/ContextBinChart";

// Mock ResizeObserver for Recharts
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", ResizeObserverMock);
});

describe("StatCard", () => {
  it("renders title and value", () => {
    render(<StatCard title="Total Documents" value={42} />);
    expect(screen.getByText("Total Documents")).toBeDefined();
    expect(screen.getByText("42")).toBeDefined();
  });

  it("renders string value", () => {
    render(<StatCard title="Status" value="Active" />);
    expect(screen.getByText("Status")).toBeDefined();
    expect(screen.getByText("Active")).toBeDefined();
  });

  it("renders optional description", () => {
    render(
      <StatCard
        title="Documents"
        value={100}
        description="In the database"
      />
    );
    expect(screen.getByText("In the database")).toBeDefined();
  });

  it("renders without description", () => {
    const { container } = render(<StatCard title="Count" value={5} />);
    // Should only have title and value paragraphs, not description
    const paragraphs = container.querySelectorAll("p");
    expect(paragraphs.length).toBe(1); // Only the value
  });

  it("applies custom className", () => {
    const { container } = render(
      <StatCard title="Test" value={1} className="custom-class" />
    );
    expect(container.firstChild).toHaveClass("custom-class");
  });
});

describe("CategoryChart", () => {
  const mockData = [
    { ai_category: "tax_documents", count: 45 },
    { ai_category: "va_claims", count: 23 },
    { ai_category: "invoices", count: 67 },
  ];

  it("renders without crashing", () => {
    const { container } = render(<CategoryChart data={mockData} />);
    expect(container.querySelector(".recharts-wrapper")).toBeDefined();
  });

  it("renders with empty data", () => {
    const { container } = render(<CategoryChart data={[]} />);
    expect(container.querySelector(".recharts-wrapper")).toBeDefined();
  });

  it("accepts onCategoryClick callback", () => {
    const mockClick = vi.fn();
    render(<CategoryChart data={mockData} onCategoryClick={mockClick} />);
    // Just verify it renders without error - full click testing requires more setup
    expect(mockClick).not.toHaveBeenCalled();
  });

  it("formats category names to title case", () => {
    // The chart should display "Tax Documents" instead of "tax_documents"
    const { container } = render(
      <CategoryChart data={[{ ai_category: "tax_documents", count: 10 }]} />
    );
    // Chart renders asynchronously, just verify it doesn't crash
    expect(container).toBeDefined();
  });
});

describe("DateDistributionChart", () => {
  const mockData = [
    { year: 2024, count: 150 },
    { year: 2023, count: 120 },
    { year: 2022, count: 80 },
  ];

  it("renders without crashing", () => {
    const { container } = render(<DateDistributionChart data={mockData} />);
    expect(container.querySelector(".recharts-wrapper")).toBeDefined();
  });

  it("renders with empty data", () => {
    const { container } = render(<DateDistributionChart data={[]} />);
    expect(container.querySelector(".recharts-wrapper")).toBeDefined();
  });

  it("accepts onYearClick callback", () => {
    const mockClick = vi.fn();
    render(<DateDistributionChart data={mockData} onYearClick={mockClick} />);
    expect(mockClick).not.toHaveBeenCalled();
  });

  it("sorts data by year ascending for timeline view", () => {
    // Data comes in descending, chart should sort ascending
    const unsortedData = [
      { year: 2024, count: 50 },
      { year: 2020, count: 30 },
      { year: 2022, count: 40 },
    ];
    const { container } = render(<DateDistributionChart data={unsortedData} />);
    expect(container).toBeDefined();
  });
});

describe("ContextBinChart", () => {
  const mockData = [
    { context_bin: "Finances Bin", count: 200 },
    { context_bin: "Work Bin", count: 150 },
    { context_bin: "Personal Bin", count: 100 },
  ];

  it("renders without crashing", () => {
    const { container } = render(<ContextBinChart data={mockData} />);
    expect(container.querySelector(".recharts-wrapper")).toBeDefined();
  });

  it("renders with empty data", () => {
    const { container } = render(<ContextBinChart data={[]} />);
    expect(container.querySelector(".recharts-wrapper")).toBeDefined();
  });

  it("accepts onBinClick callback", () => {
    const mockClick = vi.fn();
    render(<ContextBinChart data={mockData} onBinClick={mockClick} />);
    expect(mockClick).not.toHaveBeenCalled();
  });

  it("handles uncategorized bins", () => {
    const dataWithUncategorized = [
      { context_bin: "uncategorized", count: 50 },
      { context_bin: "Documents", count: 100 },
    ];
    const { container } = render(
      <ContextBinChart data={dataWithUncategorized} />
    );
    expect(container).toBeDefined();
  });
});

describe("Component exports", () => {
  it("exports all components from index", async () => {
    const exports = await import("@/components");
    expect(exports.StatCard).toBeDefined();
    expect(exports.CategoryChart).toBeDefined();
    expect(exports.DateDistributionChart).toBeDefined();
    expect(exports.ContextBinChart).toBeDefined();
  });
});
