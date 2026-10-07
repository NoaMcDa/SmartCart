import type { ReactNode } from "react";
import { SeoShell } from "@/features/seo/SeoShell";

/**
 * W6 owns this route group: static SEO pages on the same domain (D8). The shell is the app's own
 * top bar and tabs plus a footer with the trust links (methodology, basket index, accessibility).
 */
export default function SeoLayout({ children }: { children: ReactNode }) {
  return <SeoShell>{children}</SeoShell>;
}
