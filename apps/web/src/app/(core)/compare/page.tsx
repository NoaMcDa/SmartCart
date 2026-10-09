import type { Metadata } from "next";
import { BackLink, DocumentTitle, PageHeading } from "@/components/shell/PageChrome";
import { DEFAULT_LOCALE } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { appMessages } from "@/i18n/messages/app";
import { ResultsView } from "@/features/compare/ResultsView";
import styles from "../core.module.css";

export const metadata: Metadata = {
  title: translate(appMessages, DEFAULT_LOCALE, "whereCheapest"),
};

export default function Page() {
  return (
    <div className={styles.screen}>
      <DocumentTitle id="whereCheapest" />
      <BackLink href="/" id="backToList" className={styles.back} />
      <PageHeading id="whereCheapest" className={styles.title} />
      <ResultsView />
    </div>
  );
}
