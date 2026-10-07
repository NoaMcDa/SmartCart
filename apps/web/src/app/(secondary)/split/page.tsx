import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "פיצול סל" };

export default function Page() {
  return (
    <PlaceholderPage
      title="פיצול סל"
      description="שני סופרים, סכום לכל אחד וחיסכון נטו אחרי נסיעה."
      owner="W5"
    />
  );
}
