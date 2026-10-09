/**
 * The price-alert API stores the canonical id and the threshold, not the product's name. The device
 * remembers the name (and what the threshold is per) from the moment the alert was created, so
 * /alerts can say "חלב טרי 3%" instead of a number. Missing entries fall back to "מוצר מס' <id>".
 */
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { alertMessages } from "@/i18n/messages/alerts";
import { readJson, writeJson } from "@/state/storage";

export const ALERT_NAMES_KEY = "sc-alert-names-v1";

export type AlertLabel = { name: string; unitLabel: string };

type Stored = { version: 1; byCanonical: Record<string, AlertLabel> };

function read(): Stored {
  const raw = readJson<Partial<Stored> | null>(ALERT_NAMES_KEY, null);
  if (!raw || raw.version !== 1 || typeof raw.byCanonical !== "object" || !raw.byCanonical) {
    return { version: 1, byCanonical: {} };
  }
  const byCanonical: Record<string, AlertLabel> = {};
  for (const [id, v] of Object.entries(raw.byCanonical)) {
    if (v && typeof v.name === "string" && typeof v.unitLabel === "string") {
      byCanonical[id] = { name: v.name.slice(0, 200), unitLabel: v.unitLabel.slice(0, 40) };
    }
  }
  return { version: 1, byCanonical };
}

export function rememberAlertLabel(canonicalId: number, label: AlertLabel): void {
  const stored = read();
  stored.byCanonical[String(canonicalId)] = label;
  writeJson(ALERT_NAMES_KEY, stored);
}

/** The remembered label; for an alert this device never saw, a numbered fallback in `locale`. */
export function alertLabel(canonicalId: number, locale: Locale = DEFAULT_LOCALE): AlertLabel {
  return (
    read().byCanonical[String(canonicalId)] ?? {
      name: translate(alertMessages, locale, "fallbackName", { id: canonicalId }),
      unitLabel: translate(alertMessages, locale, "fallbackUnit"),
    }
  );
}
