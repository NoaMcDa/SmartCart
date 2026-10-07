import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "הקנייה השבועית" };

export default function Page() {
  return (
    <PlaceholderPage
      title="הקנייה השבועית"
      description="בניית רשימת קניות: הדבקה, הכתבה, רמת גמישות לכל פריט."
      owner="W4b"
    />
  );
}
