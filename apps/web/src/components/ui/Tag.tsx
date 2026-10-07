import type { ReactNode } from "react";
import { IconCheck, IconClose, IconDiffers, IconInfo, IconWarning } from "./icons";
import styles from "./Tag.module.css";

/**
 * Attribute / status tag. Meaning is never carried by color alone: every variant has an icon
 * and the caller passes the text.
 * - matched: same attribute as the original (green check, Substitution artboard)
 * - unverified: extracted attribute not yet verified (amber)
 * - differs: a neutral difference, e.g. private label instead of brand
 * - missing: item not available (red, only for missing)
 * - estimated: weighed produce, estimated price (amber)
 * Maps to openapi AttributeTag.status for the first three.
 */
export type TagVariant = "matched" | "unverified" | "differs" | "missing" | "estimated";

const ICONS: Record<TagVariant, ReactNode> = {
  matched: <IconCheck size={13} />,
  unverified: <IconInfo size={13} />,
  differs: <IconDiffers size={13} />,
  missing: <IconClose size={13} />,
  estimated: <IconWarning size={13} />,
};

export type TagProps = {
  variant: TagVariant;
  children: ReactNode;
  className?: string;
};

export function Tag({ variant, children, className }: TagProps) {
  return (
    <span
      className={[styles.tag, styles[variant], className].filter(Boolean).join(" ")}
      data-variant={variant}
    >
      {ICONS[variant]}
      <span>{children}</span>
    </span>
  );
}
