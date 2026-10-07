import type { ButtonHTMLAttributes, ReactNode } from "react";
import { IconLock, IconRefresh, IconTag } from "./icons";
import styles from "./Chip.module.css";

export type ChipTone = "brand" | "exact" | "warn" | "neutral" | "accent";

export type ChipProps = {
  tone?: ChipTone;
  icon?: ReactNode;
  children: ReactNode;
  /** Renders a button when set. */
  onClick?: ButtonHTMLAttributes<HTMLButtonElement>["onClick"];
  /** Toggle-style chip (filter / "allow" chips in the flexibility sheet). Renders aria-pressed. */
  selected?: boolean;
  size?: "md" | "sm";
  className?: string;
  "aria-label"?: string;
  [dataAttribute: `data-${string}`]: string | undefined;
};

/** Pill chip. Static (span) unless `onClick` is given. */
export function Chip({
  tone = "neutral",
  icon,
  children,
  onClick,
  selected,
  size = "md",
  className,
  ...aria
}: ChipProps) {
  const cls = [
    styles.chip,
    styles[tone],
    styles[`size-${size}`],
    selected ? styles.selected : null,
    onClick ? styles.interactive : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");
  if (onClick) {
    return (
      <button type="button" className={cls} onClick={onClick} aria-pressed={selected} {...aria}>
        {icon}
        {children}
      </button>
    );
  }
  return (
    <span className={cls} {...aria}>
      {icon}
      {children}
    </span>
  );
}

/** API flexibility levels (openapi BasketItem.flex_level). */
export type FlexLevel = "exact" | "any_brand" | "close";

export const FLEX_LEVELS: Record<
  FlexLevel,
  { label: string; tone: ChipTone; Icon: typeof IconLock }
> = {
  exact: { label: "מוצר מדויק", tone: "exact", Icon: IconLock },
  any_brand: { label: "כל מותג", tone: "brand", Icon: IconTag },
  close: { label: "תחליף קרוב", tone: "warn", Icon: IconRefresh },
};

export type FlexChipProps = Omit<ChipProps, "tone" | "icon" | "children"> & {
  level: FlexLevel;
};

/**
 * Flexibility chip: three levels that differ in hue and lightness and always carry an icon
 * (lock / tag / refresh) so they read without color.
 */
export function FlexChip({ level, ...rest }: FlexChipProps) {
  const { label, tone, Icon } = FLEX_LEVELS[level];
  return (
    <Chip
      tone={tone}
      icon={<Icon size={13} />}
      aria-label={rest.onClick ? `רמת גמישות: ${label}` : undefined}
      data-flex-level={level}
      {...rest}
    >
      {label}
    </Chip>
  );
}
