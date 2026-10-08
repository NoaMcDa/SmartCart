import { Fragment, createElement, type ReactNode } from "react";

/**
 * `Intl` date output in Arabic carries invisible direction marks between the numbers
 * ("07", RLM, "/10", RLM, "/2026"). The digits are Latin and the slash stays inside the number run
 * anyway, so the marks only get in the way of copying and testing.
 */
export function stripBidiMarks(text: string): string {
  return text.replace(/[‎‏]/g, "");
}

/**
 * Like `format` in `messages.ts`, but a placeholder can be a React node: a number wrapped in an LTR
 * island, an email, a link. Text between placeholders stays plain strings.
 *
 *   formatRich("שלב {n} מתוך {total}", { n: <span dir="ltr">1</span>, total: <span dir="ltr">3</span> })
 *
 * An unknown placeholder is left as written, like `format`.
 */
export function formatRich(template: string, vars: Record<string, ReactNode>): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\{(\w+)\}/g;
  let last = 0;
  let index = 0;
  for (let m = re.exec(template); m !== null; m = re.exec(template)) {
    if (m.index > last) out.push(template.slice(last, m.index));
    const name = m[1]!;
    out.push(
      name in vars ? createElement(Fragment, { key: `${name}-${index}` }, vars[name]) : m[0],
    );
    index += 1;
    last = m.index + m[0].length;
  }
  if (last < template.length) out.push(template.slice(last));
  return out;
}
