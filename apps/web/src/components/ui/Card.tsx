import type { HTMLAttributes, ReactNode } from "react";
import styles from "./Card.module.css";

export type CardProps = HTMLAttributes<HTMLElement> & {
  /** "recommended" = 2 px accent border (comparison results). */
  variant?: "default" | "recommended" | "flat";
  /** "list" removes padding so rows with dividers can fill it (list builder groups). */
  padding?: "md" | "none";
  as?: "article" | "section" | "div" | "li";
  children?: ReactNode;
};

/** Surface card: 16 px radius, token border, surface background. */
export function Card({
  variant = "default",
  padding = "md",
  as: Tag = "div",
  className,
  children,
  ...rest
}: CardProps) {
  const cls = [styles.card, styles[variant], styles[`pad-${padding}`], className]
    .filter(Boolean)
    .join(" ");
  return (
    <Tag className={cls} {...rest}>
      {children}
    </Tag>
  );
}

/** A row inside a padding="none" card; adds the divider between rows. */
export function CardRow({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={[styles.row, className].filter(Boolean).join(" ")} {...rest}>
      {children}
    </div>
  );
}
