import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "מחיר מוצר" };

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return (
    <PlaceholderPage
      title="מחיר מוצר"
      description="המחיר של מוצר בכל הרשתות, לפי קבצי השקיפות."
      owner="W6"
    >
      <p dir="ltr" lang="en" data-testid="route-param">
        slug: {slug}
      </p>
    </PlaceholderPage>
  );
}
