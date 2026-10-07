import type { ReactNode } from "react";
import { Card } from "@/components/ui/Card";
import styles from "./PlaceholderPage.module.css";

export type PlaceholderPageProps = {
  /** Hebrew page title, rendered as the page's h1. */
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
  return (
    <div className={styles.page}>
      <h1 className={styles.title}>{title}</h1>
      {description ? <p className={styles.description}>{description}</p> : null}
      <Card>
        <p className={styles.note}>המסך הזה עדיין בבנייה.</p>
        <p className={styles.owner} lang="en" dir="ltr">
          placeholder · {owner}
        </p>
      </Card>
      {children}
    </div>
  );
}
