import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "מדד הסל החודשי" };

export default function Page() {
  return (
    <PlaceholderPage
      title="מדד הסל החודשי"
      description="כמה עלה סל קבוע בכל רשת החודש."
      owner="W6"
    />
  );
}
