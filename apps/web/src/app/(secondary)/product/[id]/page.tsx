import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "פרטי מוצר" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <PlaceholderPage
      title="פרטי מוצר"
      description="וריאנטים לפי מחיר ליחידה, היסטוריית מחירים ומחיר בכל סניף."
      owner="W5"
    >
      <p dir="ltr" lang="en" data-testid="route-param">
        id: {id}
      </p>
    </PlaceholderPage>
  );
}
