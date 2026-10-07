import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "סריקת ברקוד" };

export default function Page() {
  return (
    <PlaceholderPage
      title="סריקת ברקוד"
      description="סריקה בחנות והשוואה מיידית יגיעו בשלב הבא."
      owner="W4a (phase 2)"
    />
  );
}
