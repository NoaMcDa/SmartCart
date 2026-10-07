import type { HTMLAttributes } from "react";
import { formatPrice, type FractionDigits } from "@/lib/format";
import styles from "./Price.module.css";

export type PriceProps = Omit<HTMLAttributes<HTMLSpanElement>, "children" | "dir"> & {
  /** Shekels, as a number or the API's decimal string ("389.00"). */
  amount: number | string;
  fractionDigits?: FractionDigits;
  size?: "inherit" | "sm" | "md" | "lg" | "xl" | "hero";
  /** Savings only (green). Color rule: green is reserved for savings. */
  tone?: "default" | "good" | "muted";
};

/**
 * A price inside Hebrew text. Always an LTR island (`<span dir="ltr">`) so the shekel sign and the
 * digits never reorder, and surrounding punctuation stays outside the span.
 */
export function Price({
  amount,
  fractionDigits = "auto",
  size = "inherit",
  tone = "default",
  className,
  ...rest
}: PriceProps) {
  const cls = [styles.price, styles[`size-${size}`], styles[`tone-${tone}`], className]
    .filter(Boolean)
    .join(" ");
  return (
    <span dir="ltr" className={cls} {...rest}>
      {formatPrice(amount, fractionDigits)}
    </span>
  );
}

export type PriceRangeProps = Omit<PriceProps, "amount"> & {
  from: number | string;
  to: number | string;
};

/** "₪ 412–₪ 468" as a single LTR island (list builder basket estimate). */
export function PriceRange({
  from,
  to,
  fractionDigits = "auto",
  size = "inherit",
  tone = "default",
  className,
  ...rest
}: PriceRangeProps) {
  const cls = [styles.price, styles[`size-${size}`], styles[`tone-${tone}`], className]
    .filter(Boolean)
    .join(" ");
  return (
    <span dir="ltr" className={cls} {...rest}>
      {formatPrice(from, fractionDigits)}–{formatPrice(to, fractionDigits)}
    </span>
  );
}
