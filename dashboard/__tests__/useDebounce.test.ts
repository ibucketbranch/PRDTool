import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebounce } from "@/hooks/useDebounce";

describe("useDebounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns initial value immediately", () => {
    const { result } = renderHook(() => useDebounce("initial", 300));
    expect(result.current).toBe("initial");
  });

  it("does not update value before delay has passed", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: "initial" } }
    );

    // Change the value
    rerender({ value: "updated" });

    // Before delay passes, should still show initial value
    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(result.current).toBe("initial");
  });

  it("updates value after delay has passed", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: "initial" } }
    );

    // Change the value
    rerender({ value: "updated" });

    // After delay passes, should show updated value
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe("updated");
  });

  it("resets timer on rapid value changes", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: "initial" } }
    );

    // Rapid changes
    rerender({ value: "first" });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    rerender({ value: "second" });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    rerender({ value: "third" });
    act(() => {
      vi.advanceTimersByTime(100);
    });

    // Should still be initial value after 300ms total (timer reset each time)
    expect(result.current).toBe("initial");

    // After another 300ms from last change, should show final value
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toBe("third");
  });

  it("uses default delay of 300ms when not specified", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value),
      { initialProps: { value: "initial" } }
    );

    rerender({ value: "updated" });

    // After 299ms, should still be initial
    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(result.current).toBe("initial");

    // After 300ms, should be updated
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe("updated");
  });

  it("works with different types (number)", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 0 } }
    );

    rerender({ value: 42 });

    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe(42);
  });

  it("works with different types (object)", () => {
    const initialObj = { count: 0 };
    const updatedObj = { count: 1 };

    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: initialObj } }
    );

    rerender({ value: updatedObj });

    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toEqual({ count: 1 });
  });

  it("respects custom delay value", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 500),
      { initialProps: { value: "initial" } }
    );

    rerender({ value: "updated" });

    // Should still be initial after 300ms
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe("initial");

    // Should update after 500ms
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toBe("updated");
  });

  it("handles empty string values", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: "search term" } }
    );

    rerender({ value: "" });

    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe("");
  });
});
