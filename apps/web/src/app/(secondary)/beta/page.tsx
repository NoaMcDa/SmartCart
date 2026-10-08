import type { Metadata } from "next";
import { BetaJoin } from "@/features/beta/BetaJoin";
import { BetaTitle } from "@/features/beta/BetaTitle";
import styles from "@/features/beta/Beta.module.css";

export const metadata: Metadata = {
  title: "הבטא של SmartCart",
  robots: { index: false, follow: false },
};

/** `/beta` (issue #40): what the beta is, and for members the feedback entry and "leave the beta". */
export default function Page() {
  return (
    <div className={styles.page}>
      <BetaTitle />
      <BetaJoin />
    </div>
  );
}
