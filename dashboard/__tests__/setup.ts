import { vi } from "vitest";
import "@testing-library/jest-dom/vitest";

// Mock environment variables for tests
vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co");
vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "test-anon-key");
