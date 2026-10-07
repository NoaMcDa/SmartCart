import { IconClock } from "./icons";
import styles from "./UpdatedAt.module.css";

const TZ = "Asia/Jerusalem";

function dayKey(d: Date): number {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(d);
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value ?? 0);
  return Date.UTC(get("year"), get("month") - 1, get("day")) / 86_400_000;
}

function hhmm(d: Date): string {
  return d.toLocaleTimeString("he-IL", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: TZ,
  });
}

/**
 * Relative Hebrew update time in Israel time: "היום 06:40", "אתמול 18:20", "לפני 3 ימים",
 * then the date ("12.09.2026"). Returns null for a missing or invalid timestamp.
 */
export function formatUpdatedAt(
  iso: string | null | undefined,
  now: Date = new Date(),
): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const days = dayKey(now) - dayKey(d);
  if (days <= 0) return `היום ${hhmm(d)}`;
  if (days === 1) return `אתמול ${hhmm(d)}`;
  if (days < 7) return `לפני ${days} ימים`;
  return d.toLocaleDateString("he-IL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: TZ,
  });
}

export type UpdatedAtProps = {
  /** ISO timestamp of the price (price_valid_from / prices_updated_at). */
  iso: string | null | undefined;
  /** Text before the time. Default "עודכן". */
  prefix?: string;
  withIcon?: boolean;
  className?: string;
  /** Reference "now" (tests). */
  now?: Date;
};

/**
 * Trust signal (D10): when a price was updated. Renders a <time> with the machine-readable
 * timestamp; a missing timestamp is shown as unknown rather than hidden.
 */
export function UpdatedAt({
  iso,
  prefix = "עודכן",
  withIcon = false,
  className,
  now,
}: UpdatedAtProps) {
  const text = formatUpdatedAt(iso, now);
  const cls = [styles.updated, className].filter(Boolean).join(" ");
  if (!text || !iso) {
    return (
      <span className={cls} data-updated-at="unknown">
        מועד העדכון לא ידוע
      </span>
    );
  }
  return (
    <span className={cls}>
      {withIcon ? <IconClock size={13} /> : null}
      <time dateTime={iso} data-updated-at={iso}>
        {prefix ? `${prefix} ` : ""}
        {text}
      </time>
    </span>
  );
}
