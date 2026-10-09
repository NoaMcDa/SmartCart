import { CHAINS, chainName } from "@/features/profile/chains";
import { CITIES, cityName } from "@/features/profile/cities";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";

/**
 * Chain and store names arrive from the API in Hebrew ("שופרסל דיל · מודיעין"). In Arabic the brand
 * is written in Latin letters, like every brand in the app, and a city is its Arabic name. A name
 * the tables do not know is returned as it came (it is data, not UI copy). Hebrew is never touched.
 */

/** Sub-brand words that follow a chain name ("שופרסל דיל"), in Latin letters for Arabic. */
const CHAIN_SUFFIX: Record<string, string> = {
  דיל: "Deal",
  אקסטרה: "Extra",
  שלי: "Sheli",
  אקספרס: "Express",
  אונליין: "Online",
};

function chainPart(part: string): string | null {
  const chain = [...CHAINS]
    .sort((a, b) => b.name.length - a.name.length)
    .find((c) => part === c.name || part.startsWith(`${c.name} `));
  if (!chain) return null;
  const rest = part
    .slice(chain.name.length)
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => CHAIN_SUFFIX[w] ?? w);
  return [chainName(chain, "ar"), ...rest].join(" ");
}

function cityPart(part: string): string | null {
  const city = CITIES.find((c) => c.name === part || c.name.startsWith(`${part}-`));
  if (!city) return null;
  const full = cityName(city, "ar");
  if (city.name === part) return full;
  const segments = part.split("-").length;
  return full.split("-").slice(0, segments).join("-");
}

/** A chain name ("רמי לוי", "שופרסל דיל") in the UI language. */
export function chainLabel(name: string, locale: Locale = DEFAULT_LOCALE): string {
  if (locale === DEFAULT_LOCALE) return name;
  return chainPart(name) ?? name;
}

/** A store name ("רמי לוי · מודיעין", or only "מודיעין") in the UI language. */
export function storeLabel(name: string, locale: Locale = DEFAULT_LOCALE): string {
  if (locale === DEFAULT_LOCALE) return name;
  return name
    .split(" · ")
    .map((part) => chainPart(part) ?? cityPart(part) ?? part)
    .join(" · ");
}
