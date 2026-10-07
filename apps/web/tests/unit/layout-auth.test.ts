// @vitest-environment node
/**
 * Issue #91: AuthProvider is mounted once, in the root layout, so `/feedback/*` and `/events`
 * carry the user on every screen (a second provider in a route group would shadow the first and
 * subscribe to Supabase twice).
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const APP = fileURLToPath(new URL("../../src/app", import.meta.url));

function layouts(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) layouts(full, out);
    else if (/^layout\.tsx$/.test(name)) out.push(full);
  }
  return out;
}

describe("AuthProvider mount", () => {
  it("is rendered by the root layout, around every route group", () => {
    const root = readFileSync(join(APP, "layout.tsx"), "utf8");
    expect(root).toMatch(/import \{ AuthProvider \} from "@\/features\/auth\/AuthProvider"/);
    expect(root).toMatch(/<AuthProvider>\s*\{children\}\s*<\/AuthProvider>/);
  });

  it("is rendered nowhere else", () => {
    const others = layouts(APP)
      .filter((f) => relative(APP, f) !== "layout.tsx")
      .filter((f) => /<AuthProvider\b/.test(readFileSync(f, "utf8")))
      .map((f) => relative(APP, f));
    expect(others).toEqual([]);
  });
});
