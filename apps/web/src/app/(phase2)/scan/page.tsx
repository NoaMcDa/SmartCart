import type { Metadata } from "next";
import { ScanScreen } from "@/features/scan/ScanScreen";
import pageStyles from "../phase2.module.css";
import { PageTitle } from "../PageTitle";

export const metadata: Metadata = { title: "סריקת ברקוד" };

export default function Page() {
  return (
    <div className={pageStyles.page}>
      <PageTitle id="scan" />
      <ScanScreen />
    </div>
  );
}
