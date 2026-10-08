import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { BetaJoin } from "@/features/beta/BetaJoin";
import { BetaTitle } from "@/features/beta/BetaTitle";
import styles from "@/features/beta/Beta.module.css";

export const metadata: Metadata = {
  title: "הצטרפות לבטא",
  // An invite link is private: keep it out of search results and referrers.
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

/** `/beta/join/<code>` (issue #40): the page behind an invite link made by `smartcart-catalog beta-invite`. */
export default async function Page({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  if (!/^[A-Za-z0-9-]{6,32}$/.test(code)) notFound();
  return (
    <div className={styles.page}>
      <BetaTitle />
      <BetaJoin code={code} />
    </div>
  );
}
