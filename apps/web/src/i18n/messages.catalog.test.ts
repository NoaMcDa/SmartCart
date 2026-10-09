// @vitest-environment node
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Guards for every message module under src/i18n/messages (issue #73). `defineMessages` already
 * rejects a missing or extra key at compile time; this test catches what a cast (`as`) or a
 * `// @ts-expect-error` can hide, and lists Arabic values that were never translated.
 *
 * A module that still has untranslated or draft Arabic carries a `// TODO ar` comment; only those
 * files may contain Arabic values identical to the Hebrew ones (they are printed as a warning list).
 */

const DIR = fileURLToPath(new URL("./messages/", import.meta.url));
const HEBREW_LETTER = /[֐-׿]/;
const TODO_AR = /\/\/\s*TODO ar\b/;

/** Plural-form keys (`item_two`, see `i18n/plural.ts`) are the Arabic dual, which carries its own number. */
const DUAL_FORMS = /_two$/;
/** Other keys that are a dual form by meaning ("two days ago"). */
const DUAL_KEYS = new Set(["ui.ts:updatedTwoDaysAgo"]);

const files = readdirSync(DIR)
  .filter((f) => f.endsWith(".ts") && !f.endsWith(".test.ts"))
  .sort();

type Catalog = { he: Record<string, string>; ar: Record<string, string> };

function isCatalog(value: unknown): value is Catalog {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return typeof v.he === "object" && v.he !== null && typeof v.ar === "object" && v.ar !== null;
}

async function catalogsOf(file: string): Promise<Array<[string, Catalog]>> {
  const mod = (await import(/* @vite-ignore */ `./messages/${file}`)) as Record<string, unknown>;
  return Object.entries(mod).filter((e): e is [string, Catalog] => isCatalog(e[1]));
}

describe("message catalogs", () => {
  it("finds the catalog modules", () => {
    expect(files).toContain("nav.ts");
  });

  for (const file of files) {
    describe(file, () => {
      it("exports at least one catalog", async () => {
        expect((await catalogsOf(file)).length).toBeGreaterThan(0);
      });

      it("has identical key sets in he and ar", async () => {
        for (const [name, c] of await catalogsOf(file)) {
          expect(Object.keys(c.ar).sort(), `${file} ${name}`).toEqual(Object.keys(c.he).sort());
        }
      });

      it("has no empty strings", async () => {
        for (const [name, c] of await catalogsOf(file)) {
          for (const lang of ["he", "ar"] as const) {
            for (const [key, value] of Object.entries(c[lang])) {
              expect(value.trim(), `${file} ${name}.${lang}.${key}`).not.toBe("");
            }
          }
        }
      });

      it("keeps the same {placeholders} in he and ar", async () => {
        const holders = (s: string): string[] => (s.match(/\{\w+\}/g) ?? []).sort();
        for (const [name, c] of await catalogsOf(file)) {
          for (const key of Object.keys(c.he)) {
            const ar = holders(c.ar[key] ?? "");
            const he = holders(c.he[key]!);
            if (DUAL_FORMS.test(key) || DUAL_KEYS.has(`${file}:${key}`)) {
              // Arabic has a dual ("يومين", "صنفان") that names the number itself, so it may drop
              // a placeholder. It may not invent one.
              expect(
                ar.filter((h) => !he.includes(h)),
                `${file} ${name}.${key}`,
              ).toEqual([]);
            } else {
              expect(ar, `${file} ${name}.${key}`).toEqual(he);
            }
          }
        }
      });

      it("flags Arabic values identical to the Hebrew source", async () => {
        const source = readFileSync(`${DIR}${file}`, "utf8");
        const marked = TODO_AR.test(source);
        const untranslated: string[] = [];
        for (const [name, c] of await catalogsOf(file)) {
          for (const [key, he] of Object.entries(c.he)) {
            if (HEBREW_LETTER.test(he) && c.ar[key] === he) untranslated.push(`${name}.${key}`);
          }
        }
        if (untranslated.length > 0) {
          console.warn(
            `[i18n] ${file}: ${untranslated.length} untranslated ar value(s)` +
              `${marked ? " (file is marked // TODO ar)" : ""}: ${untranslated.join(", ")}`,
          );
        }
        if (!marked) {
          expect(
            untranslated,
            `${file} has untranslated ar values; translate or add "// TODO ar"`,
          ).toEqual([]);
        }
      });
    });
  }
});
