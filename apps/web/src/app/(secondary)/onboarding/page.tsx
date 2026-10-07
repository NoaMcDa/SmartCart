import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "ברוכים הבאים" };

export default function Page() {
  return (
    <PlaceholderPage
      title="ברוכים הבאים"
      description="שלושה צעדים: מיקום, הסופר שלך ומועדונים, איך את קונה."
      owner="W5"
    />
  );
}
