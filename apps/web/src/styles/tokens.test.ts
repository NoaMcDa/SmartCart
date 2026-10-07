/**
 * Token parity and contrast.
 * 1. Every row of the docs/ux-design.md "Design tokens" table exists in tokens.css as --sc-*, with
 *    the light value in the :root block and the dark value in both dark blocks.
 * 2. AA contrast (4.5:1) for every text/background pair the components use, in both themes.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf8");
const css = read("./tokens.css");
const doc = read("../../../../docs/ux-design.md");

const kebab = (name: string) => name.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);

type Row = { token: string; light: string; dark: string };

function parseDocTable(md: string): Row[] {
  const section = md.split("## Design tokens")[1]?.split("\n## ")[0] ?? "";
  const rows: Row[] = [];
  for (const line of section.split("\n")) {
    const cells = line.split("|").map((c) => c.trim());
    // | name | light | dark | use |
    if (cells.length < 5 || !/^#[0-9A-Fa-f]{6}/.test(cells[2] ?? "")) continue;
    const names = cells[1]!
      .replace(/\(.*?\)/g, "")
      .split("/")
      .map((s) => s.trim());
    const lights = cells[2]!.split("/").map((s) => s.trim());
    const darks = cells[3]!.split("/").map((s) => s.trim());
    names.forEach((n, i) =>
      rows.push({ token: `--sc-${kebab(n)}`, light: lights[i]!, dark: darks[i]! }),
    );
  }
  return rows;
}

function block(marker: "LIGHT" | "DARK", index = 0): Record<string, string> {
  const re = new RegExp(`/\\* ${marker}:start \\*/([\\s\\S]*?)/\\* ${marker}:end \\*/`, "g");
  const matches = [...css.matchAll(re)];
  const body = matches[index]?.[1];
  if (!body) throw new Error(`${marker} block ${index} not found`);
  const vars: Record<string, string> = {};
  for (const m of body.matchAll(/(--sc-[a-z-]+):\s*([^;]+);/g)) vars[m[1]!] = m[2]!.trim();
  return vars;
}

const rows = parseDocTable(doc);
const light = block("LIGHT");
const darkMedia = block("DARK", 0);
const darkAttr = block("DARK", 1);

describe("design tokens match docs/ux-design.md", () => {
  it("parses the full doc table (20 color tokens)", () => {
    expect(rows.map((r) => r.token)).toEqual([
      "--sc-bg",
      "--sc-surface",
      "--sc-subtle",
      "--sc-border",
      "--sc-divider",
      "--sc-text",
      "--sc-muted",
      "--sc-faint",
      "--sc-accent",
      "--sc-accent-fg",
      "--sc-accent-soft",
      "--sc-brand-bg",
      "--sc-brand-fg",
      "--sc-exact-bg",
      "--sc-exact-fg",
      "--sc-warn-bg",
      "--sc-warn-fg",
      "--sc-good-bg",
      "--sc-good-fg",
      "--sc-bad-fg",
    ]);
  });

  it.each(rows)("$token light = $light, dark = $dark", ({ token, light: l, dark: d }) => {
    expect(light[token]?.toUpperCase()).toBe(l.toUpperCase());
    expect(darkMedia[token]?.toUpperCase()).toBe(d.toUpperCase());
    expect(darkAttr[token]?.toUpperCase()).toBe(d.toUpperCase());
  });

  it("keeps the prefers-color-scheme and [data-theme=dark] blocks identical", () => {
    expect(darkAttr).toEqual(darkMedia);
    expect(Object.keys(darkMedia).sort()).toEqual(Object.keys(light).sort());
  });

  it("guards the media block so a manual light choice wins over a dark OS", () => {
    expect(css).toMatch(
      /@media \(prefers-color-scheme: dark\)\s*{\s*:root:not\(\[data-theme="light"\]\)/,
    );
    expect(css).toMatch(/:root\[data-theme="dark"\]/);
  });
});

// ---- WCAG contrast ----

function luminance(hex: string) {
  const n = Number.parseInt(hex.slice(1), 16);
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * ch[0]! + 0.7152 * ch[1]! + 0.0722 * ch[2]!;
}

function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

/** [foreground, background] pairs used for text by the components and artboards. */
const TEXT_PAIRS: Array<[string, string]> = [
  ["--sc-text", "--sc-bg"],
  ["--sc-text", "--sc-surface"],
  ["--sc-text", "--sc-subtle"],
  ["--sc-muted", "--sc-surface"],
  ["--sc-muted", "--sc-bg"],
  ["--sc-muted", "--sc-subtle"],
  ["--sc-accent-fg", "--sc-surface"],
  ["--sc-accent-fg", "--sc-accent-soft"],
  ["--sc-on-accent", "--sc-accent"],
  ["--sc-brand-fg", "--sc-brand-bg"],
  ["--sc-exact-fg", "--sc-exact-bg"],
  ["--sc-warn-fg", "--sc-warn-bg"],
  ["--sc-on-warn", "--sc-warn-fg"],
  ["--sc-good-fg", "--sc-good-bg"],
  ["--sc-good-fg", "--sc-surface"],
  ["--sc-bad-fg", "--sc-surface"],
];

describe.each([
  ["light", light],
  ["dark", darkAttr],
] as const)("AA contrast in the %s theme", (_name, vars) => {
  it.each(TEXT_PAIRS)("%s on %s >= 4.5:1", (fg, bg) => {
    const ratio = contrast(vars[fg]!, vars[bg]!);
    expect(
      ratio,
      `${fg} ${vars[fg]} on ${bg} ${vars[bg]} = ${ratio.toFixed(2)}`,
    ).toBeGreaterThanOrEqual(4.5);
  });
});
