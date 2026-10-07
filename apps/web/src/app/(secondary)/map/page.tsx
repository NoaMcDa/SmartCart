import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "מפת סניפים" };

export default function Page() {
  return <PlaceholderPage title="מפת סניפים" description="מחיר הסל על כל סניף במפה." owner="W5" />;
}
