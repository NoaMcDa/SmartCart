import type { MetadataRoute } from "next";
import { sitemapEntries } from "@/features/seo/sitemap-entries";

export const dynamic = "force-static";

/** /sitemap.xml: the static SEO pages from the generated catalog data (docs/seo.md). */
export default function sitemap(): MetadataRoute.Sitemap {
  return sitemapEntries();
}
