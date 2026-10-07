// @vitest-environment node
/**
 * Proves the RTL guard rejects physical left/right in CSS (stylelint) and in inline styles
 * (ESLint no-restricted-syntax), and accepts the logical equivalents.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { ESLint } from "eslint";
import stylelint from "stylelint";
import { describe, expect, it } from "vitest";

const appRoot = fileURLToPath(new URL("../..", import.meta.url));
const stylelintConfig = JSON.parse(readFileSync(`${appRoot}/.stylelintrc.json`, "utf8"));

async function cssProblems(code: string) {
  const res = await stylelint.lint({ code, config: stylelintConfig });
  return res.results[0]?.warnings.map((w) => w.rule) ?? [];
}

describe("stylelint RTL guard", () => {
  it.each([
    ".a { margin-left: 4px; }",
    ".a { padding-right: 4px; }",
    ".a { left: 0; }",
    ".a { right: 0; }",
    ".a { text-align: left; }",
    ".a { text-align: right; }",
    ".a { border-left: 1px solid; }",
    ".a { float: left; }",
  ])("rejects %s", async (code) => {
    expect((await cssProblems(code)).length).toBeGreaterThan(0);
  });

  it.each([
    ".a { margin-inline-start: 4px; padding-inline: 8px; }",
    ".a { inset-inline-start: 0; inset-inline-end: 0; }",
    ".a { text-align: start; border-inline-start: 1px solid; }",
  ])("accepts %s", async (code) => {
    expect(await cssProblems(code)).toEqual([]);
  });
});

describe("ESLint RTL guard for inline styles", () => {
  const eslint = new ESLint({ cwd: appRoot });
  const lint = async (code: string) => {
    const [res] = await eslint.lintText(code, {
      filePath: `${appRoot}/src/__rtl_guard_fixture__.tsx`,
    });
    return (res?.messages ?? []).filter((m) => m.ruleId === "no-restricted-syntax");
  };

  it.each([
    "export const A = () => <div style={{ marginLeft: 4 }} />;",
    "export const A = () => <div style={{ paddingRight: 4 }} />;",
    "export const A = () => <div style={{ left: 0 }} />;",
    'export const A = () => <div style={{ textAlign: "right" }} />;',
    'export const A = () => <div style={{ "margin-left": 4 }} />;',
  ])(
    "rejects %s",
    async (code) => {
      expect((await lint(code)).length).toBeGreaterThan(0);
    },
    30_000,
  );

  it("accepts logical properties", async () => {
    expect(
      await lint(
        'export const A = () => <div style={{ marginInlineStart: 4, insetInlineEnd: 0, textAlign: "start" }} />;',
      ),
    ).toEqual([]);
  }, 30_000);
});
