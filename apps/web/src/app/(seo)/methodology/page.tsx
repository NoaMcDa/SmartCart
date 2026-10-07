import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "איך אנחנו משווים מחירים" };

export default function Page() {
  return (
    <PlaceholderPage
      title="איך אנחנו משווים מחירים"
      description="מקורות המחירים, איך מתאימים מוצרים ומה המשמעות של כל תווית."
      owner="W6"
    />
  );
}
