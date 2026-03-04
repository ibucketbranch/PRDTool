import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";

// Import the module under test
import { POST } from "@/app/api/open-in-finder/route";

describe("POST /api/open-in-finder", () => {
  const originalPlatform = process.platform;

  beforeEach(() => {
    // Set platform to darwin (macOS) by default
    Object.defineProperty(process, "platform", { value: "darwin" });
  });

  afterEach(() => {
    Object.defineProperty(process, "platform", { value: originalPlatform });
  });

  it("should return error when not on macOS", async () => {
    Object.defineProperty(process, "platform", { value: "linux" });

    const request = new NextRequest("http://localhost/api/open-in-finder", {
      method: "POST",
      body: JSON.stringify({ path: "/path/to/file.pdf" }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.success).toBe(false);
    expect(data.message).toBe("This feature is only available on macOS");
    expect(data.error).toContain("Unsupported platform");
  });

  it("should return error when path is missing", async () => {
    const request = new NextRequest("http://localhost/api/open-in-finder", {
      method: "POST",
      body: JSON.stringify({}),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.success).toBe(false);
    expect(data.message).toBe("File path is required");
  });

  it("should return error when path is not a string", async () => {
    const request = new NextRequest("http://localhost/api/open-in-finder", {
      method: "POST",
      body: JSON.stringify({ path: 123 }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.success).toBe(false);
    expect(data.message).toBe("File path is required");
  });

  it("should return error when path is empty string", async () => {
    const request = new NextRequest("http://localhost/api/open-in-finder", {
      method: "POST",
      body: JSON.stringify({ path: "" }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.success).toBe(false);
    expect(data.message).toBe("File path is required");
  });

  it("should return error for relative paths", async () => {
    const request = new NextRequest("http://localhost/api/open-in-finder", {
      method: "POST",
      body: JSON.stringify({ path: "relative/path/file.pdf" }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.success).toBe(false);
    expect(data.message).toBe("Invalid file path");
    expect(data.error).toBe("Only absolute paths are allowed");
  });

  it("should return error when file does not exist", async () => {
    const request = new NextRequest("http://localhost/api/open-in-finder", {
      method: "POST",
      body: JSON.stringify({ path: "/nonexistent/path/that/does/not/exist/file.pdf" }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(404);
    expect(data.success).toBe(false);
    expect(data.message).toBe("File not found");
    expect(data.error).toBe("The specified file does not exist");
  });

  it("should handle invalid JSON body", async () => {
    const request = new NextRequest("http://localhost/api/open-in-finder", {
      method: "POST",
      body: "invalid json",
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(500);
    expect(data.success).toBe(false);
    expect(data.message).toBe("Failed to open file in Finder");
  });

  it("should reject paths starting with ./", async () => {
    const request = new NextRequest("http://localhost/api/open-in-finder", {
      method: "POST",
      body: JSON.stringify({ path: "./relative/path/file.pdf" }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.success).toBe(false);
    expect(data.message).toBe("Invalid file path");
  });

  it("should reject paths starting with ../", async () => {
    const request = new NextRequest("http://localhost/api/open-in-finder", {
      method: "POST",
      body: JSON.stringify({ path: "../parent/file.pdf" }),
    });

    const response = await POST(request);
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.success).toBe(false);
    expect(data.message).toBe("Invalid file path");
  });

  it("should normalize path and detect nonexistent file", async () => {
    const request = new NextRequest("http://localhost/api/open-in-finder", {
      method: "POST",
      body: JSON.stringify({ path: "/nonexistent/../nonexistent/file.pdf" }),
    });

    const response = await POST(request);
    const data = await response.json();

    // Path gets normalized to /nonexistent/file.pdf which doesn't exist
    expect(response.status).toBe(404);
    expect(data.success).toBe(false);
    expect(data.path).toBe("/nonexistent/file.pdf");
  });
});
