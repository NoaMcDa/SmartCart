import type { Metadata } from "next";
import { ListBuilder } from "@/features/list/ListBuilder";
import styles from "./core.module.css";

export const metadata: Metadata = { title: "הקנייה השבועית" };

export default function Page() {
  return (
    <div className={styles.screen}>
      <h1 className={styles.title}>הקנייה השבועית</h1>
      <ListBuilder />
    </div>
  );
}
