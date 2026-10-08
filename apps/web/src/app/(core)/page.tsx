import type { Metadata } from "next";
import { DocumentTitle, PageHeading } from "@/components/shell/PageChrome";
import { DEFAULT_LOCALE } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { appMessages } from "@/i18n/messages/app";
import { ListBuilder } from "@/features/list/ListBuilder";
import styles from "./core.module.css";

export const metadata: Metadata = { title: translate(appMessages, DEFAULT_LOCALE, "weeklyShop") };

export default function Page() {
  return (
    <div className={styles.screen}>
      <DocumentTitle id="weeklyShop" />
      <PageHeading id="weeklyShop" className={styles.title} />
      <ListBuilder />
    </div>
  );
}
