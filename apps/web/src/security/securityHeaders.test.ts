import { describe, expect, it } from "vitest";
import {
  assertNoMockInProduction,
  contentSecurityPolicy,
  DEFAULT_API_BASE_URL,
  PERMISSIONS_POLICY,
  securityHeaders,
  TILE_ORIGIN,
} from "../../security-headers";

function directives(csp: string): Record<string, string[]> {
  return Object.fromEntries(
    csp.split("; ").map((d) => {
      const [name, ...values] = d.split(" ");
      return [name as string, values];
    }),
  );
}

describe("content security policy", () => {
  const prod = directives(
    contentSecurityPolicy({
      nodeEnv: "production",
      apiBaseUrl: "https://api.smartcart.example/v1/",
      supabaseUrl: "https://abcd.supabase.co",
    }),
  );

  it("closes everything that has no reason to be open", () => {
    expect(prod["default-src"]).toEqual(["'self'"]);
    expect(prod["object-src"]).toEqual(["'none'"]);
    expect(prod["frame-src"]).toEqual(["'none'"]);
    expect(prod["frame-ancestors"]).toEqual(["'none'"]);
    expect(prod["base-uri"]).toEqual(["'self'"]);
    expect(prod["form-action"]).toEqual(["'self'"]);
    expect(prod["font-src"]).toEqual(["'self'"]);
    expect(prod["manifest-src"]).toEqual(["'self'"]);
  });

  it("allows no wildcard, no eval and no http: source in production", () => {
    const all = Object.values(prod).flat();
    expect(all).not.toContain("*");
    expect(all).not.toContain("'unsafe-eval'");
    expect(all).not.toContain("http:");
    expect(all).not.toContain("https:");
    expect(all.some((v) => v.includes("googleapis") || v.includes("gstatic"))).toBe(false);
  });

  it("scripts: the app and the inline scripts Next and the layout emit, nothing else", () => {
    expect(prod["script-src"]).toEqual(["'self'", "'unsafe-inline'"]);
  });

  it("connects to the API origin (no path), Supabase over https and wss, and the tiles", () => {
    expect(prod["connect-src"]).toEqual([
      "'self'",
      TILE_ORIGIN,
      "https://api.smartcart.example",
      "https://abcd.supabase.co",
      "wss://abcd.supabase.co",
    ]);
    expect(prod["img-src"]).toEqual(["'self'", "data:", "blob:", TILE_ORIGIN]);
    expect(prod["worker-src"]).toEqual(["'self'", "blob:"]);
  });

  it("without configuration it allows the default local API only, and no Supabase", () => {
    const d = directives(contentSecurityPolicy({ nodeEnv: "production" }));
    expect(d["connect-src"]).toEqual(["'self'", TILE_ORIGIN, DEFAULT_API_BASE_URL]);
  });

  it("an unusable URL adds nothing instead of throwing", () => {
    const d = directives(
      contentSecurityPolicy({
        nodeEnv: "production",
        apiBaseUrl: "not a url",
        supabaseUrl: "javascript:alert(1)",
      }),
    );
    expect(d["connect-src"]).toEqual(["'self'", TILE_ORIGIN]);
  });

  it("development adds eval and the hot-reload socket, and only there", () => {
    const dev = directives(contentSecurityPolicy({ nodeEnv: "development" }));
    expect(dev["script-src"]).toContain("'unsafe-eval'");
    expect(dev["connect-src"]).toContain("ws://localhost:*");
    expect(prod["connect-src"]?.some((v) => v.startsWith("ws://"))).toBe(false);
  });
});

describe("the header set", () => {
  const headers = Object.fromEntries(
    securityHeaders({ nodeEnv: "production" }).map((h) => [h.key, h.value]),
  );

  it("has every header the review asks for", () => {
    expect(Object.keys(headers)).toEqual(
      expect.arrayContaining([
        "Content-Security-Policy",
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cross-Origin-Opener-Policy",
      ]),
    );
    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
    expect(headers["X-Frame-Options"]).toBe("DENY");
    expect(headers["Strict-Transport-Security"]).toBe("max-age=31536000; includeSubDomains");
    expect(headers["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
  });

  it("limits camera, microphone and geolocation to this origin and turns the rest off", () => {
    expect(PERMISSIONS_POLICY).toContain("camera=(self)");
    expect(PERMISSIONS_POLICY).toContain("microphone=(self)");
    expect(PERMISSIONS_POLICY).toContain("geolocation=(self)");
    const policies = PERMISSIONS_POLICY.split(", ");
    for (const p of policies) expect(p).toMatch(/^[a-z-]+=(\(self\)|\(\))$/);
    expect(policies).toContain("payment=()");
  });
});

describe("the mock API in a production build", () => {
  it("refuses to build for production with it on", () => {
    expect(() =>
      assertNoMockInProduction({ NEXT_PUBLIC_API_MOCK: "1", SEO_STRICT_SITE_URL: "1" }),
    ).toThrow(/invented prices/);
    expect(() =>
      assertNoMockInProduction({ NEXT_PUBLIC_API_MOCK: "1", VERCEL_ENV: "production" }),
    ).toThrow();
  });

  it("allows it for local, preview and test builds, and production without it", () => {
    expect(() => assertNoMockInProduction({ NEXT_PUBLIC_API_MOCK: "1" })).not.toThrow();
    expect(() =>
      assertNoMockInProduction({ NEXT_PUBLIC_API_MOCK: "1", VERCEL_ENV: "preview" }),
    ).not.toThrow();
    expect(() => assertNoMockInProduction({ SEO_STRICT_SITE_URL: "1" })).not.toThrow();
    expect(() =>
      assertNoMockInProduction({ NEXT_PUBLIC_API_MOCK: "0", VERCEL_ENV: "production" }),
    ).not.toThrow();
  });
});
