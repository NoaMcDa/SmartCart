import type { Metadata } from "next";
import { AlertsScreen } from "@/features/alerts/AlertsScreen";
import pageStyles from "../phase2.module.css";

export const metadata: Metadata = { title: "התראות" };

export default function Page() {
  return (
    <div className={pageStyles.page}>
      <h1 className={pageStyles.title}>התראות</h1>
      <AlertsScreen />
    </div>
  );
}
