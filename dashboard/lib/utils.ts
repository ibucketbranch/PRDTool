import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface OpenInFinderResult {
  success: boolean;
  message: string;
  path?: string;
  error?: string;
}

/**
 * Opens a file in macOS Finder by calling the backend API
 * Falls back to copying the path to clipboard if the API call fails
 * @param filePath - The absolute path to the file to reveal in Finder
 * @returns Result object with success status and message
 */
export async function openInFinder(filePath: string): Promise<OpenInFinderResult> {
  try {
    const response = await fetch("/api/open-in-finder", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ path: filePath }),
    });

    const result = await response.json() as OpenInFinderResult;

    if (!response.ok) {
      return {
        success: false,
        message: result.message || "Failed to open in Finder",
        path: filePath,
        error: result.error,
      };
    }

    return result;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Network error";
    return {
      success: false,
      message: "Failed to connect to server",
      path: filePath,
      error: errorMessage,
    };
  }
}

/**
 * Copies the given path to the clipboard
 * @param path - The path to copy
 * @returns True if successful, false otherwise
 */
export async function copyToClipboard(path: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(path);
    return true;
  } catch {
    return false;
  }
}
