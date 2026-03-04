import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Tooltip, HelpTooltip, HELP_TEXT } from "@/components/Tooltip";

// ============================================================================
// Tooltip Component Tests
// ============================================================================

describe("Tooltip", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders children correctly", () => {
    render(
      <Tooltip content="Test tooltip">
        <button>Hover me</button>
      </Tooltip>
    );

    expect(screen.getByText("Hover me")).toBeInTheDocument();
  });

  it("shows tooltip on mouse enter after delay", async () => {
    render(
      <Tooltip content="Test tooltip content" delay={200}>
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByText("Hover me").parentElement!;

    // Tooltip should not be visible initially
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    // Hover over the trigger
    fireEvent.mouseEnter(trigger);

    // Tooltip should still not be visible before delay
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    // Advance timers past the delay
    act(() => {
      vi.advanceTimersByTime(250);
    });

    // Now tooltip should be visible
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    expect(screen.getByText("Test tooltip content")).toBeInTheDocument();
  });

  it("hides tooltip on mouse leave", async () => {
    render(
      <Tooltip content="Test tooltip content" delay={0}>
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByText("Hover me").parentElement!;

    // Show tooltip
    fireEvent.mouseEnter(trigger);
    act(() => {
      vi.advanceTimersByTime(10);
    });
    expect(screen.getByRole("tooltip")).toBeInTheDocument();

    // Hide tooltip
    fireEvent.mouseLeave(trigger);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("cancels showing tooltip if mouse leaves before delay", () => {
    render(
      <Tooltip content="Test tooltip content" delay={500}>
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByText("Hover me").parentElement!;

    // Start hover
    fireEvent.mouseEnter(trigger);

    // Leave before delay completes
    act(() => {
      vi.advanceTimersByTime(200);
    });
    fireEvent.mouseLeave(trigger);

    // Advance past original delay
    act(() => {
      vi.advanceTimersByTime(400);
    });

    // Tooltip should never have appeared
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("shows tooltip on focus", () => {
    render(
      <Tooltip content="Test tooltip content">
        <button>Focus me</button>
      </Tooltip>
    );

    const trigger = screen.getByText("Focus me").parentElement!;

    fireEvent.focus(trigger);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });

  it("hides tooltip on blur", () => {
    render(
      <Tooltip content="Test tooltip content">
        <button>Focus me</button>
      </Tooltip>
    );

    const trigger = screen.getByText("Focus me").parentElement!;

    fireEvent.focus(trigger);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();

    fireEvent.blur(trigger);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("renders with default top position", () => {
    render(
      <Tooltip content="Test tooltip content" delay={0}>
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByText("Hover me").parentElement!;
    fireEvent.mouseEnter(trigger);
    act(() => {
      vi.advanceTimersByTime(10);
    });

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.className).toContain("bottom-full");
  });

  it("renders with bottom position when specified", () => {
    render(
      <Tooltip content="Test tooltip content" position="bottom" delay={0}>
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByText("Hover me").parentElement!;
    fireEvent.mouseEnter(trigger);
    act(() => {
      vi.advanceTimersByTime(10);
    });

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.className).toContain("top-full");
  });

  it("renders with left position when specified", () => {
    render(
      <Tooltip content="Test tooltip content" position="left" delay={0}>
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByText("Hover me").parentElement!;
    fireEvent.mouseEnter(trigger);
    act(() => {
      vi.advanceTimersByTime(10);
    });

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.className).toContain("right-full");
  });

  it("renders with right position when specified", () => {
    render(
      <Tooltip content="Test tooltip content" position="right" delay={0}>
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByText("Hover me").parentElement!;
    fireEvent.mouseEnter(trigger);
    act(() => {
      vi.advanceTimersByTime(10);
    });

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.className).toContain("left-full");
  });

  it("applies custom maxWidth", () => {
    render(
      <Tooltip content="Test tooltip content" maxWidth={400} delay={0}>
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByText("Hover me").parentElement!;
    fireEvent.mouseEnter(trigger);
    act(() => {
      vi.advanceTimersByTime(10);
    });

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.style.maxWidth).toBe("400px");
  });

  it("applies custom className", () => {
    render(
      <Tooltip content="Test tooltip content" className="custom-class">
        <button>Hover me</button>
      </Tooltip>
    );

    const container = screen.getByText("Hover me").parentElement;
    expect(container?.className).toContain("custom-class");
  });

  it("renders complex content in tooltip", () => {
    render(
      <Tooltip
        content={
          <div>
            <strong>Title</strong>
            <p>Description text</p>
          </div>
        }
        delay={0}
      >
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByText("Hover me").parentElement!;
    fireEvent.mouseEnter(trigger);
    act(() => {
      vi.advanceTimersByTime(10);
    });

    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Description text")).toBeInTheDocument();
  });
});

// ============================================================================
// HelpTooltip Component Tests
// ============================================================================

describe("HelpTooltip", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders info icon button", () => {
    render(<HelpTooltip text="Help text" />);

    const button = screen.getByRole("button", { name: /help/i });
    expect(button).toBeInTheDocument();
  });

  it("shows help text on hover", () => {
    render(<HelpTooltip text="This is help text" />);

    const button = screen.getByRole("button", { name: /help/i });
    const container = button.parentElement!;

    fireEvent.mouseEnter(container);
    act(() => {
      vi.advanceTimersByTime(250);
    });

    expect(screen.getByText("This is help text")).toBeInTheDocument();
  });

  it("renders with custom size", () => {
    render(<HelpTooltip text="Help text" size={24} />);

    const button = screen.getByRole("button", { name: /help/i });
    const svg = button.querySelector("svg");
    expect(svg).toHaveAttribute("width", "24");
    expect(svg).toHaveAttribute("height", "24");
  });

  it("renders with custom position", () => {
    render(<HelpTooltip text="Help text" position="right" />);

    const button = screen.getByRole("button", { name: /help/i });
    const container = button.parentElement!;

    fireEvent.mouseEnter(container);
    act(() => {
      vi.advanceTimersByTime(250);
    });

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.className).toContain("left-full");
  });

  it("applies custom className", () => {
    render(<HelpTooltip text="Help text" className="custom-help-class" />);

    const button = screen.getByRole("button", { name: /help/i });
    const container = button.parentElement;
    expect(container?.className).toContain("custom-help-class");
  });

  it("is accessible via keyboard focus", () => {
    render(<HelpTooltip text="Accessible help text" />);

    const button = screen.getByRole("button", { name: /help/i });
    const container = button.parentElement!;

    fireEvent.focus(container);

    expect(screen.getByText("Accessible help text")).toBeInTheDocument();
  });
});

// ============================================================================
// HELP_TEXT Constants Tests
// ============================================================================

describe("HELP_TEXT", () => {
  it("contains statistics help text", () => {
    expect(HELP_TEXT.totalDocuments).toBeDefined();
    expect(typeof HELP_TEXT.totalDocuments).toBe("string");
    expect(HELP_TEXT.totalDocuments.length).toBeGreaterThan(0);
  });

  it("contains categories help text", () => {
    expect(HELP_TEXT.categories).toBeDefined();
    expect(typeof HELP_TEXT.categories).toBe("string");
  });

  it("contains dateDistribution help text", () => {
    expect(HELP_TEXT.dateDistribution).toBeDefined();
    expect(typeof HELP_TEXT.dateDistribution).toBe("string");
  });

  it("contains contextBins help text", () => {
    expect(HELP_TEXT.contextBins).toBeDefined();
    expect(typeof HELP_TEXT.contextBins).toBe("string");
  });

  it("contains filter help text", () => {
    expect(HELP_TEXT.categoryFilter).toBeDefined();
    expect(HELP_TEXT.yearRangeFilter).toBeDefined();
    expect(HELP_TEXT.contextBinFilter).toBeDefined();
    expect(HELP_TEXT.searchFilter).toBeDefined();
  });

  it("contains search page help text", () => {
    expect(HELP_TEXT.naturalLanguageSearch).toBeDefined();
    expect(HELP_TEXT.searchExamples).toBeDefined();
  });

  it("contains document browser help text", () => {
    expect(HELP_TEXT.sortableColumns).toBeDefined();
    expect(HELP_TEXT.pathClick).toBeDefined();
  });

  it("contains orphaned files help text", () => {
    expect(HELP_TEXT.orphanedFiles).toBeDefined();
    expect(HELP_TEXT.missingFiles).toBeDefined();
    expect(HELP_TEXT.confidenceScore).toBeDefined();
  });

  it("contains match type help text", () => {
    expect(HELP_TEXT.matchType).toBeDefined();
    expect(HELP_TEXT.matchType.database_history).toBeDefined();
    expect(HELP_TEXT.matchType.similar_files).toBeDefined();
    expect(HELP_TEXT.matchType.filename_pattern).toBeDefined();
    expect(HELP_TEXT.matchType.file_type).toBeDefined();
  });

  it("contains empty folders help text", () => {
    expect(HELP_TEXT.emptyFolders).toBeDefined();
    expect(HELP_TEXT.folderAssessment).toBeDefined();
    expect(HELP_TEXT.restoreFiles).toBeDefined();
    expect(HELP_TEXT.removeFolder).toBeDefined();
  });

  it("contains chart interaction help text", () => {
    expect(HELP_TEXT.chartInteraction).toBeDefined();
  });

  it("contains general help text", () => {
    expect(HELP_TEXT.pagination).toBeDefined();
    expect(HELP_TEXT.bulkSelect).toBeDefined();
  });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe("Tooltip Integration", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("works with different content types", () => {
    const { rerender } = render(
      <Tooltip content="String content" delay={0}>
        <span>Trigger</span>
      </Tooltip>
    );

    const trigger = screen.getByText("Trigger").parentElement!;
    fireEvent.mouseEnter(trigger);
    act(() => {
      vi.advanceTimersByTime(10);
    });
    expect(screen.getByText("String content")).toBeInTheDocument();

    fireEvent.mouseLeave(trigger);

    rerender(
      <Tooltip content={<em>Emphasized content</em>} delay={0}>
        <span>Trigger</span>
      </Tooltip>
    );

    fireEvent.mouseEnter(trigger);
    act(() => {
      vi.advanceTimersByTime(10);
    });
    expect(screen.getByText("Emphasized content")).toBeInTheDocument();
  });

  it("tooltip has proper z-index for layering", () => {
    render(
      <Tooltip content="Test content" delay={0}>
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByText("Hover me").parentElement!;
    fireEvent.mouseEnter(trigger);
    act(() => {
      vi.advanceTimersByTime(10);
    });

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.className).toContain("z-50");
  });

  it("multiple tooltips can exist independently", () => {
    render(
      <div>
        <Tooltip content="Tooltip 1" delay={0}>
          <button>Button 1</button>
        </Tooltip>
        <Tooltip content="Tooltip 2" delay={0}>
          <button>Button 2</button>
        </Tooltip>
      </div>
    );

    const trigger1 = screen.getByText("Button 1").parentElement!;
    const trigger2 = screen.getByText("Button 2").parentElement!;

    // Show first tooltip
    fireEvent.mouseEnter(trigger1);
    act(() => {
      vi.advanceTimersByTime(10);
    });
    expect(screen.getByText("Tooltip 1")).toBeInTheDocument();
    expect(screen.queryByText("Tooltip 2")).not.toBeInTheDocument();

    // Hide first, show second
    fireEvent.mouseLeave(trigger1);
    fireEvent.mouseEnter(trigger2);
    act(() => {
      vi.advanceTimersByTime(10);
    });
    expect(screen.queryByText("Tooltip 1")).not.toBeInTheDocument();
    expect(screen.getByText("Tooltip 2")).toBeInTheDocument();
  });
});
