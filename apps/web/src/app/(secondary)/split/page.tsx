import type { Metadata } from "next";
import { SplitView } from "@/features/split/SplitView";

export const metadata: Metadata = { title: "פיצול סל" };

export default function Page() {
  return <SplitView />;
}
