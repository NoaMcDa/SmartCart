import type { Metadata } from "next";
import Link from "next/link";
import { IconChevronBack } from "@/components/ui/icons";
import { ResultsView } from "@/features/compare/ResultsView";
import styles from "../core.module.css";

export const metadata: Metadata = { title: "איפה הכי זול השבוע?" };

export default function Page() {
  return (
    <div className={styles.screen}>
      <Link href="/" className={styles.back}>
        <IconChevronBack size={18} />
        חזרה לרשימה
      </Link>
      <h1 className={styles.title}>איפה הכי זול השבוע?</h1>
      <ResultsView />
    </div>
  );
}
