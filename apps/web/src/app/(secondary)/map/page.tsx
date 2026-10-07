import type { Metadata } from "next";
import { MapScreen } from "@/features/map/MapScreen";

export const metadata: Metadata = { title: "מפת סניפים" };

export default function Page() {
  return <MapScreen />;
}
