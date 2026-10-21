import { afterEach, beforeEach, expect, it, vi } from "vitest";

beforeEach(() => {
  vi.resetModules();
  vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://project.supabase.test");
  vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.doUnmock("@supabase/supabase-js");
});

it("a failed load of the library is tried again by the next call, not cached for ever", async () => {
  let attempts = 0;
  vi.doMock("@supabase/supabase-js", () => ({
    createClient: () => {
      attempts += 1;
      if (attempts === 1) throw new Error("ChunkLoadError");
      return { marker: "client" };
    },
  }));
  const { loadSupabase, getSupabase } = await import("./supabaseClient");
  await expect(loadSupabase()).rejects.toThrow("ChunkLoadError");
  expect(getSupabase()).toBeNull();
  await expect(loadSupabase()).resolves.toMatchObject({ marker: "client" });
  expect(attempts).toBe(2);
  // Once loaded it stays: no third attempt.
  await loadSupabase();
  expect(attempts).toBe(2);
});
