import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { cn, openInFinder, copyToClipboard } from "@/lib/utils";

describe("cn utility function", () => {
  it("should merge class names", () => {
    const result = cn("foo", "bar");
    expect(result).toBe("foo bar");
  });

  it("should handle conditional classes", () => {
    const result = cn("base", true && "included", false && "excluded");
    expect(result).toBe("base included");
  });

  it("should merge Tailwind classes correctly", () => {
    const result = cn("px-2 py-1", "px-4");
    expect(result).toBe("py-1 px-4");
  });

  it("should handle undefined and null values", () => {
    const result = cn("base", undefined, null, "end");
    expect(result).toBe("base end");
  });

  it("should handle empty string", () => {
    const result = cn("base", "", "end");
    expect(result).toBe("base end");
  });

  it("should handle arrays of classes", () => {
    const result = cn(["foo", "bar"]);
    expect(result).toBe("foo bar");
  });

  it("should handle object syntax", () => {
    const result = cn({ foo: true, bar: false, baz: true });
    expect(result).toBe("foo baz");
  });
});

describe("openInFinder", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("should return success when API succeeds", async () => {
    const mockResponse = {
      success: true,
      message: "File revealed in Finder",
      path: "/Users/test/Documents/file.pdf",
    };

    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const result = await openInFinder("/Users/test/Documents/file.pdf");

    expect(result.success).toBe(true);
    expect(result.message).toBe("File revealed in Finder");
    expect(result.path).toBe("/Users/test/Documents/file.pdf");
  });

  it("should call API with correct path", async () => {
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, message: "OK" }),
    } as Response);

    await openInFinder("/path/to/file.pdf");

    expect(global.fetch).toHaveBeenCalledWith("/api/open-in-finder", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ path: "/path/to/file.pdf" }),
    });
  });

  it("should return error when API returns error status", async () => {
    const mockResponse = {
      success: false,
      message: "File not found",
      error: "The specified file does not exist",
    };

    vi.mocked(global.fetch).mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => mockResponse,
    } as Response);

    const result = await openInFinder("/nonexistent/file.pdf");

    expect(result.success).toBe(false);
    expect(result.message).toBe("File not found");
    expect(result.error).toBe("The specified file does not exist");
  });

  it("should return error when network fails", async () => {
    vi.mocked(global.fetch).mockRejectedValue(new Error("Network error"));

    const result = await openInFinder("/path/to/file.pdf");

    expect(result.success).toBe(false);
    expect(result.message).toBe("Failed to connect to server");
    expect(result.error).toBe("Network error");
    expect(result.path).toBe("/path/to/file.pdf");
  });

  it("should handle non-macOS platform error", async () => {
    const mockResponse = {
      success: false,
      message: "This feature is only available on macOS",
      error: "Unsupported platform: linux",
    };

    vi.mocked(global.fetch).mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => mockResponse,
    } as Response);

    const result = await openInFinder("/path/to/file.pdf");

    expect(result.success).toBe(false);
    expect(result.message).toBe("This feature is only available on macOS");
  });

  it("should handle missing path error", async () => {
    const mockResponse = {
      success: false,
      message: "File path is required",
      error: "Missing or invalid path parameter",
    };

    vi.mocked(global.fetch).mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => mockResponse,
    } as Response);

    const result = await openInFinder("");

    expect(result.success).toBe(false);
    expect(result.message).toBe("File path is required");
  });
});

describe("copyToClipboard", () => {
  const originalNavigator = global.navigator;

  beforeEach(() => {
    Object.defineProperty(global, "navigator", {
      value: {
        clipboard: {
          writeText: vi.fn(),
        },
      },
      writable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(global, "navigator", {
      value: originalNavigator,
      writable: true,
    });
  });

  it("should return true when clipboard write succeeds", async () => {
    vi.mocked(navigator.clipboard.writeText).mockResolvedValue();

    const result = await copyToClipboard("/path/to/file.pdf");

    expect(result).toBe(true);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("/path/to/file.pdf");
  });

  it("should return false when clipboard write fails", async () => {
    vi.mocked(navigator.clipboard.writeText).mockRejectedValue(new Error("Permission denied"));

    const result = await copyToClipboard("/path/to/file.pdf");

    expect(result).toBe(false);
  });
});
