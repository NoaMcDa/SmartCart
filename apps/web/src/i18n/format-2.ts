import { createElement, Fragment, useCallback, type ReactNode } from "react";
import type { AttributeTag } from "@/api/client";
import { attributeTagText, perUnitLabel } from "@/lib/attributes";
import { useLocale } from "./LocaleProvider";
import { format, type MessageSet } from "./messages";
import type { Locale } from "./locales";

/**
 * Rich messages: one translatable string that carries inline markup, so word order is the
 * translator's, not the component's.
 *
 *   he: "הברקוד <ltr>{barcode}</ltr> לא מקושר"
 *   rich(template, { ltr: (c) => <span dir="ltr">{c}</span> }, { barcode })
 *
 * `<name>text</name>` calls the tag with its children; `<name/>` inserts the tag's node (or calls
 * it with `undefined`). A tag name that is not in `tags` stays literal text, so catalog text with
 * angle brackets can never become markup. `{placeholders}` are filled in the text pieces only.
 */
export type RichTag = ReactNode | ((children: ReactNode) => ReactNode);
export type RichTags = Record<string, RichTag>;
type Vars = Record<string, string | number>;

const TOKEN = /<(\/?)([a-zA-Z][\w-]*)(\/?)>/g;

type Frame = { tag: string | null; children: ReactNode[] };

function apply(tag: RichTag, children: ReactNode): ReactNode {
  return typeof tag === "function" ? (tag as (c: ReactNode) => ReactNode)(children) : tag;
}

export function rich(template: string, tags: RichTags, vars?: Vars): ReactNode {
  const root: Frame = { tag: null, children: [] };
  const stack: Frame[] = [root];
  const top = () => stack[stack.length - 1]!;
  let last = 0;

  const text = (to: number) => {
    const piece = template.slice(last, to);
    if (piece) top().children.push(format(piece, vars));
  };

  for (const m of template.matchAll(TOKEN)) {
    const [whole, closing, name, selfClosing] = m as unknown as [string, string, string, string];
    if (!Object.hasOwn(tags, name)) continue;
    const at = m.index ?? 0;
    if (closing && !selfClosing) {
      if (top().tag !== name || stack.length === 1) continue; // unbalanced: literal
      text(at);
      const done = stack.pop()!;
      top().children.push(apply(tags[name] as RichTag, wrap(done.children)));
    } else if (selfClosing && !closing) {
      text(at);
      top().children.push(apply(tags[name] as RichTag, undefined));
    } else if (!closing) {
      text(at);
      stack.push({ tag: name, children: [] });
    } else {
      continue;
    }
    last = at + whole.length;
  }
  text(template.length);
  // An opening tag that never closed: its content still shows, unwrapped.
  while (stack.length > 1) {
    const open = stack.pop()!;
    top().children.push(...open.children);
  }
  return wrap(root.children);
}

function wrap(children: ReactNode[]): ReactNode {
  if (children.length === 1) return children[0];
  return createElement(
    Fragment,
    null,
    ...children.map((c, i) => createElement(Fragment, { key: i }, c)),
  );
}

/** Non-hook form for code that already holds the locale. */
export function richTranslate<K extends string>(
  messages: MessageSet<K>,
  locale: Locale,
  key: K,
  tags: RichTags,
  vars?: Vars,
): ReactNode {
  return rich(messages[locale][key] ?? messages.he[key], tags, vars);
}

/** `const r = useRich(scanMessages); r("notFoundBody", { ltr: (c) => <span dir="ltr">{c}</span> }, { barcode })` */
export function useRich<K extends string>(messages: MessageSet<K>) {
  const { locale } = useLocale();
  return useCallback(
    (key: K, tags: RichTags, vars?: Vars) => richTranslate(messages, locale, key, tags, vars),
    [messages, locale],
  );
}

/* ------------------------------------------------------------------------------------------ *
 * Locale-aware unit and attribute labels. `src/lib/attributes.ts` is Hebrew only; for `he` these
 * hand over to it unchanged (byte-identical output), for `ar` they use the tables below. A code
 * the table does not know is passed through, never guessed (same rule as lib/attributes).
 * ------------------------------------------------------------------------------------------ */

const AR_KEY_LABELS: Record<string, string> = {
  product_type: "نوع المنتج",
  pack_size: "حجم العبوة",
  unit: "الوحدة",
  brand: "العلامة التجارية",
  fat_pct: "نسبة الدسم",
  base: "القاعدة",
  kosher: "الكشروت",
  state: "الحالة",
  flavor: "النكهة",
};
const AR_BASE_VALUES: Record<string, string> = {
  soy: "صويا",
  almond: "لوز",
  oat: "شوفان",
  rice: "أرز",
  coconut: "جوز الهند",
};
const AR_STATE_VALUES: Record<string, string> = {
  fresh: "طازج",
  frozen: "مجمّد",
  dried: "مجفّف",
  canned: "معلّب",
};
const AR_UNITS: Record<string, string> = { g: "غ", ml: "مل", unit: "وحدة", kg: "كغ", l: "لتر" };
const AR_UNIT_PATTERN = /(^|\s)(kg|ml|unit|g|l)$/i;

function arUnitName(unit: string): string {
  return AR_UNITS[unit.trim().toLowerCase()] ?? unit;
}

function arUomText(uom: string): string {
  const m = /^(\d+(?:\.\d+)?)\s*(kg|ml|unit|g|l)$/i.exec(uom.trim());
  if (m) return `${m[1]} ${arUnitName(m[2]!)}`;
  return arUnitName(uom);
}

/** "for 100 g": "ל-100 ג׳" in Hebrew, "لكل 100 غ" in Arabic; "ליח׳" / "للوحدة" for a single unit. */
export function perUnit(uom: string, locale: Locale): string {
  if (locale === "he") return perUnitLabel(uom);
  if (uom.trim().toLowerCase() === "unit") return "للوحدة";
  return `لكل ${arUomText(uom)}`;
}

function arAttributeValue(key: string, value: string | null | undefined): string | null {
  if (value === null || value === undefined || value === "") return null;
  const v = value.trim();
  switch (key) {
    case "base":
      return AR_BASE_VALUES[v.toLowerCase()] ?? v;
    case "state":
      return AR_STATE_VALUES[v.toLowerCase()] ?? v;
    case "unit":
      return arUnitName(v);
    case "pack_size":
      return v.replace(
        AR_UNIT_PATTERN,
        (_all, space: string, unit: string) => `${space}${arUnitName(unit)}`,
      );
    case "fat_pct":
      return /^\d+(\.\d+)?$/.test(v) ? `${v}%` : v;
    default:
      return v;
  }
}

/** The text of one attribute chip; Hebrew is `attributeTagText` from lib/attributes, unchanged. */
export function attributeTag(
  tag: AttributeTag,
  locale: Locale,
  options: { plainDiffers?: boolean } = {},
): string {
  if (locale === "he") return attributeTagText(tag, options);
  const known = tag.key in AR_KEY_LABELS;
  const label = AR_KEY_LABELS[tag.key] ?? tag.key;
  const value = arAttributeValue(tag.key, tag.value);
  if (tag.status === "unverified") return `${label}${value ? ` ${value}` : ""} · غير مؤكَّد`;
  if (tag.status === "differs") {
    if (options.plainDiffers && !known) return value ?? label;
    return value ? `${label}: ${value}` : label;
  }
  return value ? `${label}، ${value}` : label;
}
