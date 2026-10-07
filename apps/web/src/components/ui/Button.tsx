import Link from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./Button.module.css";

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost";

type CommonProps = {
  variant?: ButtonVariant;
  /** "bad" is only for negative feedback actions like "not a good substitute". */
  tone?: "default" | "bad";
  /** md = 48 px (artboard primary actions), sm = 44 px (minimum touch target). */
  size?: "md" | "sm";
  block?: boolean;
  iconStart?: ReactNode;
  iconEnd?: ReactNode;
  children?: ReactNode;
  className?: string;
};

export type ButtonProps = CommonProps &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, keyof CommonProps> & { href?: undefined };

export type ButtonLinkProps = CommonProps &
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, keyof CommonProps | "href"> & { href: string };

function classes({
  variant = "primary",
  tone = "default",
  size = "md",
  block,
  className,
}: CommonProps) {
  return [
    styles.button,
    styles[variant],
    styles[`size-${size}`],
    tone === "bad" ? styles.bad : null,
    block ? styles.block : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");
}

/**
 * Primary / secondary / outline / ghost button. Minimum height 44 px. Pass `href` to render a
 * Next.js link styled as a button.
 */
export function Button(props: ButtonProps | ButtonLinkProps) {
  const { variant, tone, size, block, iconStart, iconEnd, children, className, ...rest } = props;
  const cls = classes({ variant, tone, size, block, className });
  const content = (
    <>
      {iconStart}
      {children}
      {iconEnd}
    </>
  );
  if (typeof rest.href === "string") {
    const { href, ...anchor } = rest as Omit<ButtonLinkProps, keyof CommonProps>;
    return (
      <Link href={href} className={cls} {...anchor}>
        {content}
      </Link>
    );
  }
  const { type = "button", ...button } = rest as Omit<ButtonProps, keyof CommonProps>;
  return (
    <button type={type} className={cls} {...button}>
      {content}
    </button>
  );
}
