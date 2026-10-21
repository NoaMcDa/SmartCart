/**
 * Numbers typed by a person. An Arabic keyboard (and the numeric keypad of a phone set to Arabic)
 * types Arabic-Indic digits (U+0660 to U+0669) or Persian ones; the UI shows Latin digits
 * everywhere, but what is typed must be read either way, or a valid price is reported as invalid
 * or silently lost.
 */

const ARABIC_INDIC_ZERO = 0x0660;
const EXTENDED_ARABIC_INDIC_ZERO = 0x06f0;

/**
 * Latin digits and ASCII separators for what was typed: Arabic-Indic and Persian digits become
 * 0-9, the Arabic decimal separator (U+066B) a point, the Arabic thousands and comma marks
 * (U+066C, U+060C) a comma. Bidi marks drop out, no-break spaces become plain ones and the ends
 * are trimmed. Everything else is left as typed.
 */
export function normalizeNumberInput(text: string): string {
  return text
    .replace(/[\u200e\u200f\u061c\u202a-\u202e\u2066-\u2069]/gu, "")
    .replace(/[\u00a0\u202f]/gu, " ")
    .replace(/[\u0660-\u0669]/gu, (d) => String(d.charCodeAt(0) - ARABIC_INDIC_ZERO))
    .replace(/[\u06f0-\u06f9]/gu, (d) => String(d.charCodeAt(0) - EXTENDED_ARABIC_INDIC_ZERO))
    .replace(/\u066b/gu, ".")
    .replace(/[\u066c\u060c]/gu, ",")
    .trim();
}
