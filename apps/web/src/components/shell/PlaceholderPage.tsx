"use client";

import type { ReactNode } from "react";
import { useT } from "@/i18n/LocaleProvider";
import { shellMessages } from "@/i18n/messages/shell";
import { Card } from "@/components/ui/Card";
import styles from "./PlaceholderPage.module.css";

export type PlaceholderPageProps = {
  /** Page title, already in the user's language (use `useT` in the caller), rendered as the h1. */
  title: string;
  /** One line about what the screen will do. */
  description?: string;
  /** Workstream that owns the real screen (shown to developers only, not translated). */
  owner: string;
  children?: ReactNode;
};

/**
 * Server component used by every placeholder route until its workstream builds the screen.
 * Replace the whole page; do not extend this component.
 */
export function PlaceholderPage({ title, description, owner, children }: PlaceholderPageProps) {
  const t = useT(shellMessages);
  return (
    <div className={styles.page}>
      <h1 className={styles.title}>{title}</h1>
      {description ? <p className={styles.description}>{description}</p> : null}
      <Card>
        <p className={styles.note}>{t("underConstruction")}</p>
        <p className={styles.owner} lang="en" dir="ltr">
          placeholder · {owner}
        </p>
      </Card>
      {children}
    </div>
  );
}
