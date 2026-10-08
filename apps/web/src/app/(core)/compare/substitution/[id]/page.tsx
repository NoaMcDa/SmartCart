import type { Metadata } from "next";
import { BackLink, DocumentTitle, PageHeading } from "@/components/shell/PageChrome";
import { DEFAULT_LOCALE } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { appMessages } from "@/i18n/messages/app";
import { SubstitutionView } from "@/features/substitution/SubstitutionView";
import styles from "../../../core.module.css";

export const metadata: Metadata = {
  title: translate(appMessages, DEFAULT_LOCALE, "substitutionDetails"),
};

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
      <DocumentTitle id="substitutionDetails" />
      <BackLink href="/compare" id="backToResults" className={styles.back} />
      <PageHeading id="substitutionDetails" className={styles.title} />
      <SubstitutionView itemId={Number.parseInt(id, 10)} plan={kind} />
    </div>
  );
}
