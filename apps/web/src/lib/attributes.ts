/**
 * Hebrew labels for what the API sends as codes: attribute tags (`AttributeTag.key` and `value`)
 * and units (`uom`, a pack-size unit inside a tag value). The mock API already sends Hebrew; the
 * real API sends `pack_size`, `unit`, `base`, `100g`, `kg`, so every screen that shows a tag or a
 * unit goes through here. Anything not in a table is passed through unchanged, never guessed.
 */
import type { AttributeTag } from "@/api/client";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { attributeMessages } from "@/i18n/messages/attributes";

type MessageKey = keyof (typeof attributeMessages)["he"];

/** Code -> message key. The Hebrew and Arabic texts live in `messages/attributes.ts`. */
const KEY_LABELS: Record<string, MessageKey> = {
  product_type: "key_product_type",
  pack_size: "key_pack_size",
  unit: "key_unit",
  brand: "key_brand",
  fat_pct: "key_fat_pct",
  base: "key_base",
  kosher: "key_kosher",
  state: "key_state",
  flavor: "key_flavor",
};

/** Plant-milk bases and the like (`base` tag values). */
const BASE_VALUES: Record<string, MessageKey> = {
  soy: "base_soy",
  almond: "base_almond",
  oat: "base_oat",
  rice: "base_rice",
  coconut: "base_coconut",
};

const STATE_VALUES: Record<string, MessageKey> = {
  fresh: "state_fresh",
  frozen: "state_frozen",
  dried: "state_dried",
  canned: "state_canned",
};

/** The unit codes of `uom` and of pack sizes (the abbreviations the shelf uses). */
const UNITS: Record<string, MessageKey> = {
  g: "unit_g",
  ml: "unit_ml",
  unit: "unit_unit",
  kg: "unit_kg",
  l: "unit_l",
};

const UNIT_PATTERN = /(^|\s)(kg|ml|unit|g|l)$/i;

/** A table lookup that ignores inherited object properties ("constructor" is not a code). */
function lookup(table: Record<string, MessageKey>, code: string): MessageKey | undefined {
  return Object.hasOwn(table, code) ? table[code] : undefined;
}

/** "g" -> "ג׳"; a code the table does not know, or text that is already Hebrew, is unchanged. */
export function unitName(unit: string, locale: Locale = DEFAULT_LOCALE): string {
  const key = lookup(UNITS, unit.trim().toLowerCase());
  return key ? translate(attributeMessages, locale, key) : unit;
}

/**
 * A price unit (`uom`): "100g" -> "100 ג׳", "100ml" -> "100 מ״ל", "unit" -> "יח׳", "kg" -> "ק״ג".
 * A uom that is already Hebrew ("100 מ"ל") comes back as it was.
 */
export function uomText(uom: string, locale: Locale = DEFAULT_LOCALE): string {
  const text = locale === DEFAULT_LOCALE ? uom.trim() : hebrewUnitToCode(uom.trim());
  const m = /^(\d+(?:\.\d+)?)\s*(kg|ml|unit|g|l)$/i.exec(text);
  if (m) return `${m[1]} ${unitName(m[2]!, locale)}`;
  return unitName(text, locale);
}

/** Hebrew unit abbreviations that older data and the mocks carry in `uom`, as the unit codes. */
const HEBREW_UNITS: ReadonlyArray<readonly [RegExp, string]> = [
  [/(^|\s)מ["״]ל$/, "ml"],
  [/(^|\s)ק["״]ג$/, "kg"],
  [/(^|\s)ג['׳]$/, "g"],
  [/(^|\s)יח['׳]$/, "unit"],
  [/(^|\s)ל['׳]$/, "l"],
];

/** "100 מ"ל" -> "100ml"; anything else is returned unchanged. Only used for non-Hebrew output. */
function hebrewUnitToCode(uom: string): string {
  for (const [pattern, code] of HEBREW_UNITS) {
    if (pattern.test(uom)) return uom.replace(pattern, (_, space: string) => `${space}${code}`);
  }
  return uom;
}

/** "for 100 g": "ל-100 ג׳", "ליח׳", "לק״ג". */
export function perUnitLabel(uom: string, locale: Locale = DEFAULT_LOCALE): string {
  const text = uomText(uom, locale);
  return translate(attributeMessages, locale, /^\d/.test(text) ? "perUnitNumeric" : "perUnitWord", {
    text,
  });
}

export function attributeLabel(key: string, locale: Locale = DEFAULT_LOCALE): string {
  const messageKey = lookup(KEY_LABELS, key);
  return messageKey ? translate(attributeMessages, locale, messageKey) : key;
}

/** The value of a tag, in Hebrew: a unit code at the end ("1000 g"), a base, a state, a fat percentage. */
export function attributeValue(
  key: string,
  value: string | null | undefined,
  locale: Locale = DEFAULT_LOCALE,
): string | null {
  if (value === null || value === undefined || value === "") return null;
  const v = value.trim();
  if (locale !== DEFAULT_LOCALE) {
    // The mock and older data send these values in Hebrew; Arabic shows the same words in Arabic.
    const known = hebrewValue(v);
    if (known) return translate(attributeMessages, locale, known);
  }
  switch (key) {
    case "base": {
      const k = lookup(BASE_VALUES, v.toLowerCase());
      return k ? translate(attributeMessages, locale, k) : v;
    }
    case "state": {
      const k = lookup(STATE_VALUES, v.toLowerCase());
      return k ? translate(attributeMessages, locale, k) : v;
    }
    case "unit":
      return unitName(v, locale);
    case "pack_size":
      return v.replace(
        UNIT_PATTERN,
        (_all, space: string, unit: string) => `${space}${unitName(unit, locale)}`,
      );
    case "fat_pct":
      return /^\d+(\.\d+)?$/.test(v) ? `${v}%` : v;
    default:
      return v;
  }
}

/** The message key of a tag value written in Hebrew ("סויה", "מותג פרטי"), when it is a known one. */
function hebrewValue(v: string): MessageKey | undefined {
  const keys: MessageKey[] = [
    ...Object.values(BASE_VALUES),
    ...Object.values(STATE_VALUES),
    "value_private_label",
  ];
  return keys.find((k) => translate(attributeMessages, DEFAULT_LOCALE, k) === v);
}

const SEVERITY: Record<AttributeTag["status"], number> = { matched: 0, unverified: 1, differs: 2 };

/**
 * A `unit` tag that comes with a `pack_size` tag is part of the pack size ("1000" and "g" are
 * "1000 ג׳"), not a chip of its own. The folded tag takes the worse of the two statuses: a unit
 * that differs makes the pack size differ. A `unit` tag alone stays a tag.
 */
export function foldTags(tags: ReadonlyArray<AttributeTag>): AttributeTag[] {
  const pack = tags.find((t) => t.key === "pack_size");
  const unit = tags.find((t) => t.key === "unit");
  if (!pack || !unit) return [...tags];
  const packValue = pack.value ?? "";
  const unitValue = unit.value ?? "";
  // A pack size that already ends in its unit ("1000 g") has nothing to add.
  const hasUnit = UNIT_PATTERN.test(packValue.trim());
  const value = [packValue, hasUnit ? "" : unitValue].filter(Boolean).join(" ") || null;
  const status = SEVERITY[unit.status] > SEVERITY[pack.status] ? unit.status : pack.status;
  return tags.filter((t) => t !== unit).map((t) => (t === pack ? { ...pack, value, status } : t));
}

/**
 * The text of one chip: the label and value in Hebrew, with "לא מאומת" on an unverified one.
 * `plainDiffers` is for the substitution card, whose differing tags with a free-text key (the mock
 * and older data: key "מותג", value "יטבתה במקום תנובה") show the value alone; a tag with a known
 * code key is always labeled, because "1000 ג׳" alone says nothing.
 */
export function attributeTagText(
  tag: AttributeTag,
  options: { plainDiffers?: boolean; locale?: Locale } = {},
): string {
  const locale = options.locale ?? DEFAULT_LOCALE;
  const label = attributeLabel(tag.key, locale);
  const value = attributeValue(tag.key, tag.value, locale);
  if (tag.status === "unverified") {
    return translate(attributeMessages, locale, "tagUnverified", {
      text: `${label}${value ? ` ${value}` : ""}`,
    });
  }
  if (tag.status === "differs") {
    if (options.plainDiffers && !Object.hasOwn(KEY_LABELS, tag.key)) return value ?? label;
    return value ? translate(attributeMessages, locale, "tagDiffers", { label, value }) : label;
  }
  return value ? translate(attributeMessages, locale, "tagMatched", { label, value }) : label;
}
