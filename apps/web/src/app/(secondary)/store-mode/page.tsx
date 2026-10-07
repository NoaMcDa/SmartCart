import type { Metadata } from "next";
import { StoreMode } from "@/features/store/StoreMode";

export const metadata: Metadata = { title: "מצב חנות" };

export default function Page() {
  return <StoreMode />;
}
