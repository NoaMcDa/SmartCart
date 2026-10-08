"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useT } from "@/i18n/LocaleProvider";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { uiMessages } from "@/i18n/messages/ui";
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

const FLEX_LABEL_KEYS = {
  exact: "flexExact",
  any_brand: "flexAnyBrand",
  close: "flexClose",
} as const satisfies Record<FlexLevel, keyof (typeof uiMessages)["he"]>;

/** The chip text of a level in `locale` (Hebrew by default). Screens call it with `useLocale()`. */
export function flexLevelLabel(level: FlexLevel, locale: Locale = DEFAULT_LOCALE): string {
  return translate(uiMessages, locale, FLEX_LABEL_KEYS[level]);
}

/** `label` is the Hebrew text; use `flexLevelLabel(level, locale)` where the locale can be Arabic. */
export const FLEX_LEVELS: Record<
  FlexLevel,
  { label: string; tone: ChipTone; Icon: typeof IconLock }
> = {
  exact: { label: flexLevelLabel("exact"), tone: "exact", Icon: IconLock },
  any_brand: { label: flexLevelLabel("any_brand"), tone: "brand", Icon: IconTag },
  close: { label: flexLevelLabel("close"), tone: "warn", Icon: IconRefresh },
};

export type FlexChipProps = Omit<ChipProps, "tone" | "icon" | "children"> & {
  level: FlexLevel;
};

/**
 * Flexibility chip: three levels that differ in hue and lightness and always carry an icon
 * (lock / tag / refresh) so they read without color.
 */
export function FlexChip({ level, ...rest }: FlexChipProps) {
  const t = useT(uiMessages);
  const { tone, Icon } = FLEX_LEVELS[level];
  const label = t(FLEX_LABEL_KEYS[level]);
  return (
    <Chip
      tone={tone}
      icon={<Icon size={13} />}
      aria-label={rest.onClick ? t("flexLevelAria", { label }) : undefined}
      data-flex-level={level}
      {...rest}
    >
      {label}
    </Chip>
  );
}
