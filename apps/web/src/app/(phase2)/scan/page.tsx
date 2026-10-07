import type { Metadata } from "next";
import { ScanScreen } from "@/features/scan/ScanScreen";
import pageStyles from "../phase2.module.css";

export const metadata: Metadata = { title: "סריקת ברקוד" };

export default function Page() {
  return (
    <div className={pageStyles.page}>
      <h1 className={pageStyles.title}>סריקת ברקוד</h1>
      <ScanScreen />
    </div>
  );
}
