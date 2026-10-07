import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "איפה הכי זול השבוע?" };

export default function Page() {
  return (
    <PlaceholderPage
      title="איפה הכי זול השבוע?"
      description="השוואת הסל בסניפים הקרובים, חיסכון נטו לעומת הסופר שלך."
      owner="W4b"
    />
  );
}
