import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "מחירי קטגוריה" };

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return (
    <PlaceholderPage
      title="מחירי קטגוריה"
      description="השוואת מחירים לקטגוריה בכל הרשתות."
      owner="W6"
    >
      <p dir="ltr" lang="en" data-testid="route-param">
        slug: {slug}
      </p>
    </PlaceholderPage>
  );
}
