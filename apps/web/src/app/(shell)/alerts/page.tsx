import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "התראות" };

export default function Page() {
  return (
    <PlaceholderPage
      title="התראות"
      description="התראות על מבצעים וירידות מחיר יגיעו בשלב הבא."
      owner="W4a (phase 2)"
    />
  );
}
