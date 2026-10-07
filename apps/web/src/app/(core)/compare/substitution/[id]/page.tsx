import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "פרטי החלפה" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <PlaceholderPage
      title="פרטי החלפה"
      description="למה המוצר הוחלף, מה זהה ומה שונה, ואפשרות לבטל."
      owner="W4b"
    >
      <p dir="ltr" lang="en" data-testid="route-param">
        id: {id}
      </p>
    </PlaceholderPage>
  );
}
