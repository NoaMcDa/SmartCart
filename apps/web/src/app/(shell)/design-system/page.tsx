import type { Metadata } from "next";
import { Showcase } from "./Showcase";

export const metadata: Metadata = { title: "ערכת עיצוב", robots: { index: false, follow: false } };

/**
 * Developer route: every src/components/ui component in the light and the dark theme side by side
 * (stacked below ~760 px). Playwright screenshots it at 390 px and 1280 px. Not linked from the app.
 */
export default function Page() {
  return <Showcase />;
}
