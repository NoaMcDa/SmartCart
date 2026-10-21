import type { NextConfig } from "next";
import { assertNoMockInProduction, securityHeaders, type HeaderEnv } from "./security-headers";

assertNoMockInProduction(process.env);

const headerEnv: HeaderEnv = {
  nodeEnv: process.env.NODE_ENV,
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || undefined,
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL || undefined,
};

// Without the mock switch the MSW library and the mock handlers are replaced by empty modules, so
// the production bundle has no invented prices in it (src/mocks/disabled.ts).
const mockEnabled = process.env.NEXT_PUBLIC_API_MOCK === "1";
const withoutMocks = {
  msw: "./src/mocks/disabled.ts",
  "@/mocks/handlers": "./src/mocks/disabled.ts",
};

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  turbopack: { resolveAlias: mockEnabled ? {} : withoutMocks },
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined, // apps/web/Dockerfile
  async headers() {
    return [
      {
        // Every route, the service worker and the static assets included (security-headers.ts).
        source: "/:path*",
        headers: securityHeaders(headerEnv),
      },
      {
        // The service worker must never be served stale, or a broken worker sticks around.
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
    ];
  },
};

export default nextConfig;
