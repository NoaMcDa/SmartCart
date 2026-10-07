import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "מצב חנות" };

export default function Page() {
  return (
    <PlaceholderPage
      title="מצב חנות"
      description="הרשימה ממוינת לפי מחלקות, עם סימון מה כבר בעגלה."
      owner="W5"
    />
  );
}
