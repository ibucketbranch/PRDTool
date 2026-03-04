import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom";

import {
  Spinner,
  Skeleton,
  LoadingText,
  PageLoading,
  StatCardSkeleton,
  StatCardSkeletonGrid,
  ChartSkeleton,
  TableRowSkeleton,
  TableSkeleton,
  CardSkeleton,
  CardListSkeleton,
  SearchResultSkeleton,
  SearchResultsSkeleton,
  EmptyFolderCardSkeleton,
  EmptyFolderListSkeleton,
  StatisticsPageSkeleton,
  BrowsePageSkeleton,
  ErrorDisplay,
  InlineError,
  NetworkError,
  NotFoundError,
  EmptyState,
  AlertBanner,
} from "@/components";

// ============================================================================
// Spinner Component Tests
// ============================================================================

describe("Spinner", () => {
  it("renders with default medium size", () => {
    render(<Spinner />);
    const spinner = screen.getByRole("status");
    expect(spinner).toBeInTheDocument();
    expect(spinner).toHaveClass("h-6", "w-6");
  });

  it("renders with small size", () => {
    render(<Spinner size="sm" />);
    const spinner = screen.getByRole("status");
    expect(spinner).toHaveClass("h-4", "w-4");
  });

  it("renders with large size", () => {
    render(<Spinner size="lg" />);
    const spinner = screen.getByRole("status");
    expect(spinner).toHaveClass("h-8", "w-8");
  });

  it("has accessible label", () => {
    render(<Spinner />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    render(<Spinner className="custom-class" />);
    const spinner = screen.getByRole("status");
    expect(spinner).toHaveClass("custom-class");
  });

  it("has animate-spin class", () => {
    render(<Spinner />);
    const spinner = screen.getByRole("status");
    expect(spinner).toHaveClass("animate-spin");
  });
});

// ============================================================================
// Skeleton Component Tests
// ============================================================================

describe("Skeleton", () => {
  it("renders with default rectangular variant", () => {
    render(<Skeleton />);
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toBeInTheDocument();
    expect(skeleton).toHaveClass("rounded-md");
  });

  it("renders text variant with rounded corners", () => {
    render(<Skeleton variant="text" />);
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toHaveClass("rounded");
  });

  it("renders circular variant", () => {
    render(<Skeleton variant="circular" />);
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toHaveClass("rounded-full");
  });

  it("applies custom width as number", () => {
    render(<Skeleton width={100} />);
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toHaveStyle({ width: "100px" });
  });

  it("applies custom width as string", () => {
    render(<Skeleton width="50%" />);
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toHaveStyle({ width: "50%" });
  });

  it("applies custom height", () => {
    render(<Skeleton height={50} />);
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toHaveStyle({ height: "50px" });
  });

  it("has aria-hidden attribute", () => {
    render(<Skeleton />);
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toHaveAttribute("aria-hidden", "true");
  });

  it("applies custom className", () => {
    render(<Skeleton className="custom-skeleton" />);
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toHaveClass("custom-skeleton");
  });
});

// ============================================================================
// LoadingText Component Tests
// ============================================================================

describe("LoadingText", () => {
  it("renders with default text", () => {
    render(<LoadingText />);
    // There are two "Loading..." texts - one in spinner (sr-only) and one visible
    const loadingTexts = screen.getAllByText("Loading...");
    expect(loadingTexts.length).toBe(2);
  });

  it("renders with custom text", () => {
    render(<LoadingText text="Fetching data..." />);
    expect(screen.getByText("Fetching data...")).toBeInTheDocument();
  });

  it("includes a spinner", () => {
    render(<LoadingText />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    const { container } = render(<LoadingText className="custom-class" />);
    expect(container.firstChild).toHaveClass("custom-class");
  });
});

// ============================================================================
// PageLoading Component Tests
// ============================================================================

describe("PageLoading", () => {
  it("renders with default text", () => {
    render(<PageLoading />);
    // There are two "Loading..." texts - one in spinner (sr-only) and one visible
    const loadingTexts = screen.getAllByText("Loading...");
    expect(loadingTexts.length).toBe(2);
  });

  it("renders with custom text", () => {
    render(<PageLoading text="Loading statistics..." />);
    expect(screen.getByText("Loading statistics...")).toBeInTheDocument();
  });

  it("is centered on page", () => {
    const { container } = render(<PageLoading />);
    expect(container.firstChild).toHaveClass("flex", "items-center", "justify-center");
  });
});

// ============================================================================
// Skeleton Grid/List Component Tests
// ============================================================================

describe("StatCardSkeleton", () => {
  it("renders skeleton structure", () => {
    const { container } = render(<StatCardSkeleton />);
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });
});

describe("StatCardSkeletonGrid", () => {
  it("renders default 4 cards", () => {
    render(<StatCardSkeletonGrid />);
    const grid = document.querySelector(".grid");
    expect(grid).toBeInTheDocument();
    expect(grid?.children.length).toBe(4);
  });

  it("renders custom count of cards", () => {
    render(<StatCardSkeletonGrid count={6} />);
    const grid = document.querySelector(".grid");
    expect(grid?.children.length).toBe(6);
  });
});

describe("ChartSkeleton", () => {
  it("renders with default height", () => {
    render(<ChartSkeleton />);
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toHaveStyle({ height: "300px" });
  });

  it("renders with custom height", () => {
    render(<ChartSkeleton height={200} />);
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toHaveStyle({ height: "200px" });
  });
});

describe("TableSkeleton", () => {
  it("renders table structure", () => {
    render(<TableSkeleton />);
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("renders default 5 rows", () => {
    render(<TableSkeleton />);
    const tbody = document.querySelector("tbody");
    expect(tbody?.children.length).toBe(5);
  });

  it("renders custom row count", () => {
    render(<TableSkeleton rows={10} />);
    const tbody = document.querySelector("tbody");
    expect(tbody?.children.length).toBe(10);
  });

  it("renders custom column count", () => {
    render(<TableSkeleton columns={8} />);
    const headerRow = document.querySelector("thead tr");
    expect(headerRow?.children.length).toBe(8);
  });
});

describe("TableRowSkeleton", () => {
  it("renders default 5 columns", () => {
    const { container } = render(
      <table>
        <tbody>
          <TableRowSkeleton />
        </tbody>
      </table>
    );
    const cells = container.querySelectorAll("td");
    expect(cells.length).toBe(5);
  });

  it("renders custom column count", () => {
    const { container } = render(
      <table>
        <tbody>
          <TableRowSkeleton columns={3} />
        </tbody>
      </table>
    );
    const cells = container.querySelectorAll("td");
    expect(cells.length).toBe(3);
  });
});

describe("CardSkeleton", () => {
  it("renders card structure", () => {
    const { container } = render(<CardSkeleton />);
    expect(container.querySelector(".border")).toBeInTheDocument();
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });
});

describe("CardListSkeleton", () => {
  it("renders default 3 cards", () => {
    const { container } = render(<CardListSkeleton />);
    const cards = container.querySelectorAll(".border");
    expect(cards.length).toBe(3);
  });

  it("renders custom card count", () => {
    const { container } = render(<CardListSkeleton count={5} />);
    const cards = container.querySelectorAll(".border");
    expect(cards.length).toBe(5);
  });
});

describe("SearchResultSkeleton", () => {
  it("renders skeleton structure", () => {
    const { container } = render(<SearchResultSkeleton />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });
});

describe("SearchResultsSkeleton", () => {
  it("renders default 3 results", () => {
    const { container } = render(<SearchResultsSkeleton />);
    expect(container.querySelectorAll(".border").length).toBe(3);
  });

  it("renders custom count", () => {
    const { container } = render(<SearchResultsSkeleton count={5} />);
    expect(container.querySelectorAll(".border").length).toBe(5);
  });
});

describe("EmptyFolderCardSkeleton", () => {
  it("renders skeleton structure", () => {
    const { container } = render(<EmptyFolderCardSkeleton />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });
});

describe("EmptyFolderListSkeleton", () => {
  it("renders default 3 folders", () => {
    const { container } = render(<EmptyFolderListSkeleton />);
    expect(container.querySelectorAll(".border").length).toBe(3);
  });

  it("renders custom count", () => {
    const { container } = render(<EmptyFolderListSkeleton count={7} />);
    expect(container.querySelectorAll(".border").length).toBe(7);
  });
});

describe("StatisticsPageSkeleton", () => {
  it("renders full page skeleton", () => {
    const { container } = render(<StatisticsPageSkeleton />);
    // Should have stat cards grid + multiple chart sections
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(5);
  });
});

describe("BrowsePageSkeleton", () => {
  it("renders page skeleton with filters and table", () => {
    const { container } = render(<BrowsePageSkeleton />);
    // Should have filter skeletons and table skeleton
    expect(container.querySelector("table")).toBeInTheDocument();
  });
});

// ============================================================================
// ErrorDisplay Component Tests
// ============================================================================

describe("ErrorDisplay", () => {
  it("renders error message", () => {
    render(<ErrorDisplay message="Something went wrong" />);
    expect(screen.getByText(/Something went wrong/)).toBeInTheDocument();
  });

  it("renders with Error: prefix by default", () => {
    render(<ErrorDisplay message="Test error" severity="error" />);
    expect(screen.getByText(/Error:/)).toBeInTheDocument();
  });

  it("renders title when provided", () => {
    render(<ErrorDisplay message="Test" title="Error Title" />);
    expect(screen.getByText("Error Title")).toBeInTheDocument();
  });

  it("renders retry button when onRetry provided", () => {
    const onRetry = vi.fn();
    render(<ErrorDisplay message="Test" onRetry={onRetry} />);
    const button = screen.getByText("Try again");
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(onRetry).toHaveBeenCalled();
  });

  it("renders custom retry text", () => {
    render(<ErrorDisplay message="Test" onRetry={() => {}} retryText="Reload" />);
    expect(screen.getByText("Reload")).toBeInTheDocument();
  });

  it("shows retrying state", () => {
    render(<ErrorDisplay message="Test" onRetry={() => {}} isRetrying />);
    expect(screen.getByText("Retrying...")).toBeInTheDocument();
  });

  it("disables retry button when retrying", () => {
    render(<ErrorDisplay message="Test" onRetry={() => {}} isRetrying />);
    const button = screen.getByText("Retrying...");
    expect(button).toBeDisabled();
  });

  it("renders link when linkTo provided", () => {
    render(<ErrorDisplay message="Test" linkTo="/" linkText="Go home" />);
    const link = screen.getByText("Go home");
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/");
  });

  it("applies error styling by default", () => {
    const { container } = render(<ErrorDisplay message="Test" />);
    expect(container.querySelector(".bg-red-50")).toBeInTheDocument();
  });

  it("applies warning styling", () => {
    const { container } = render(<ErrorDisplay message="Test" severity="warning" />);
    expect(container.querySelector(".bg-amber-50")).toBeInTheDocument();
  });

  it("applies info styling", () => {
    const { container } = render(<ErrorDisplay message="Test" severity="info" />);
    expect(container.querySelector(".bg-blue-50")).toBeInTheDocument();
  });

  it("renders full page variant", () => {
    render(<ErrorDisplay message="Test" fullPage />);
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    const { container } = render(<ErrorDisplay message="Test" className="custom-error" />);
    expect(container.querySelector(".custom-error")).toBeInTheDocument();
  });
});

// ============================================================================
// InlineError Component Tests
// ============================================================================

describe("InlineError", () => {
  it("renders error message", () => {
    render(<InlineError message="Field is required" />);
    expect(screen.getByText("Field is required")).toBeInTheDocument();
  });

  it("has red text color", () => {
    const { container } = render(<InlineError message="Test" />);
    expect(container.firstChild).toHaveClass("text-red-600");
  });

  it("applies custom className", () => {
    const { container } = render(<InlineError message="Test" className="mt-2" />);
    expect(container.firstChild).toHaveClass("mt-2");
  });
});

// ============================================================================
// NetworkError Component Tests
// ============================================================================

describe("NetworkError", () => {
  it("renders connection error message", () => {
    render(<NetworkError />);
    expect(screen.getByText(/Unable to connect/)).toBeInTheDocument();
  });

  it("renders retry button when onRetry provided", () => {
    const onRetry = vi.fn();
    render(<NetworkError onRetry={onRetry} />);
    fireEvent.click(screen.getByText("Try again"));
    expect(onRetry).toHaveBeenCalled();
  });
});

// ============================================================================
// NotFoundError Component Tests
// ============================================================================

describe("NotFoundError", () => {
  it("renders default not found message", () => {
    render(<NotFoundError />);
    expect(screen.getByText(/Resource could not be found/)).toBeInTheDocument();
  });

  it("renders custom resource name", () => {
    render(<NotFoundError resource="Document" />);
    expect(screen.getByText(/Document could not be found/)).toBeInTheDocument();
  });

  it("renders link to dashboard", () => {
    render(<NotFoundError />);
    expect(screen.getByText("Return to dashboard")).toHaveAttribute("href", "/");
  });

  it("renders custom link", () => {
    render(<NotFoundError linkTo="/search" />);
    expect(screen.getByText("Return to dashboard")).toHaveAttribute("href", "/search");
  });
});

// ============================================================================
// EmptyState Component Tests
// ============================================================================

describe("EmptyState", () => {
  it("renders message", () => {
    render(<EmptyState message="No items found" />);
    expect(screen.getByText("No items found")).toBeInTheDocument();
  });

  it("renders title when provided", () => {
    render(<EmptyState title="Empty" message="No items" />);
    expect(screen.getByText("Empty")).toBeInTheDocument();
  });

  it("renders icon when provided", () => {
    render(<EmptyState message="Test" icon={<span data-testid="icon">Icon</span>} />);
    expect(screen.getByTestId("icon")).toBeInTheDocument();
  });

  it("renders action when provided", () => {
    render(<EmptyState message="Test" action={<button>Add Item</button>} />);
    expect(screen.getByText("Add Item")).toBeInTheDocument();
  });

  it("is centered", () => {
    const { container } = render(<EmptyState message="Test" />);
    expect(container.firstChild).toHaveClass("flex", "flex-col", "items-center", "justify-center");
  });
});

// ============================================================================
// AlertBanner Component Tests
// ============================================================================

describe("AlertBanner", () => {
  it("renders message", () => {
    render(<AlertBanner message="Important notice" />);
    expect(screen.getByText("Important notice")).toBeInTheDocument();
  });

  it("applies info styling by default", () => {
    const { container } = render(<AlertBanner message="Test" />);
    expect(container.querySelector(".bg-blue-50")).toBeInTheDocument();
  });

  it("applies error styling", () => {
    const { container } = render(<AlertBanner message="Test" severity="error" />);
    expect(container.querySelector(".bg-red-50")).toBeInTheDocument();
  });

  it("applies warning styling", () => {
    const { container } = render(<AlertBanner message="Test" severity="warning" />);
    expect(container.querySelector(".bg-amber-50")).toBeInTheDocument();
  });

  it("renders dismiss button when onDismiss provided", () => {
    const onDismiss = vi.fn();
    render(<AlertBanner message="Test" onDismiss={onDismiss} />);
    const button = screen.getByRole("button", { name: "Dismiss" });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(onDismiss).toHaveBeenCalled();
  });

  it("does not render dismiss button when onDismiss not provided", () => {
    render(<AlertBanner message="Test" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

// ============================================================================
// Component Exports Tests
// ============================================================================

describe("Component exports", () => {
  it("exports all loading state components", () => {
    expect(Spinner).toBeDefined();
    expect(Skeleton).toBeDefined();
    expect(LoadingText).toBeDefined();
    expect(PageLoading).toBeDefined();
    expect(StatCardSkeleton).toBeDefined();
    expect(StatCardSkeletonGrid).toBeDefined();
    expect(ChartSkeleton).toBeDefined();
    expect(TableRowSkeleton).toBeDefined();
    expect(TableSkeleton).toBeDefined();
    expect(CardSkeleton).toBeDefined();
    expect(CardListSkeleton).toBeDefined();
    expect(SearchResultSkeleton).toBeDefined();
    expect(SearchResultsSkeleton).toBeDefined();
    expect(EmptyFolderCardSkeleton).toBeDefined();
    expect(EmptyFolderListSkeleton).toBeDefined();
    expect(StatisticsPageSkeleton).toBeDefined();
    expect(BrowsePageSkeleton).toBeDefined();
  });

  it("exports all error display components", () => {
    expect(ErrorDisplay).toBeDefined();
    expect(InlineError).toBeDefined();
    expect(NetworkError).toBeDefined();
    expect(NotFoundError).toBeDefined();
    expect(EmptyState).toBeDefined();
    expect(AlertBanner).toBeDefined();
  });
});
