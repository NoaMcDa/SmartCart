import type { Metadata } from "next";
import { AlertsScreen } from "@/features/alerts/AlertsScreen";
import pageStyles from "../phase2.module.css";
import { PageTitle } from "../PageTitle";

export const metadata: Metadata = { title: "התראות" };

export default function Page() {
  return (
    <div className={pageStyles.page}>
      <PageTitle id="alerts" />
      <AlertsScreen />
    </div>
  );
}
