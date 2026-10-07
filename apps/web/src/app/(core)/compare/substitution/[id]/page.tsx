import type { Metadata } from "next";
import Link from "next/link";
import { IconChevronBack } from "@/components/ui/icons";
import { SubstitutionView } from "@/features/substitution/SubstitutionView";
import styles from "../../../core.module.css";

export const metadata: Metadata = { title: "פרטי החלפה" };

const PLAN_KINDS = new Set(["single", "split", "minimum_effort"]);

export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const { plan } = await searchParams;
  const kind =
    typeof plan === "string" && PLAN_KINDS.has(plan)
      ? (plan as "single" | "split" | "minimum_effort")
      : undefined;
  return (
    <div className={styles.screen}>
      <Link href="/compare" className={styles.back}>
        <IconChevronBack size={18} />
        חזרה לתוצאות
      </Link>
      <h1 className={styles.title}>פרטי החלפה</h1>
      <SubstitutionView itemId={Number.parseInt(id, 10)} plan={kind} />
    </div>
  );
}
