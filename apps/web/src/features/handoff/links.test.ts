import { describe, expect, it } from "vitest";
import type { ChainOnline } from "@/api/client";
import { enabledChain, handoffItems, httpsUrl, listText, searchUrl, tidyQuantity } from "./links";

const chain = (over: Partial<ChainOnline> = {}): ChainOnline => ({
  chain_id: "c1",
  chain_name: "רשת",
  online_url: "https://shop.example/",
  search_url_template: "https://shop.example/s?q={q}",
  enabled: true,
  referral: false,
  ...over,
});

describe("handoff links", () => {
  it("encodes the item name into the search template", () => {
    const url = searchUrl("https://shop.example/s?q={q}", "חלב 3% & שוקו, 1 ליטר");
    expect(url).toBe(`https://shop.example/s?q=${encodeURIComponent("חלב 3% & שוקו, 1 ליטר")}`);
    expect(url).not.toContain(" ");
    expect(new URL(url!).searchParams.get("q")).toBe("חלב 3% & שוקו, 1 ליטר");
  });

  it("returns null without a usable template", () => {
    expect(searchUrl(null, "חלב")).toBeNull();
    expect(searchUrl("https://shop.example/s", "חלב")).toBeNull();
    expect(searchUrl("javascript:alert({q})", "חלב")).toBeNull();
    expect(searchUrl("http://shop.example/?q={q}", "חלב")).toBeNull();
  });

  it("only passes https addresses", () => {
    expect(httpsUrl("https://shop.example/")).toBe("https://shop.example/");
    expect(httpsUrl("http://shop.example/")).toBeNull();
    expect(httpsUrl("javascript:alert(1)")).toBeNull();
    expect(httpsUrl("not a url")).toBeNull();
    expect(httpsUrl(null)).toBeNull();
  });

  it("enables a chain only when the flag is on and the address is usable", () => {
    expect(enabledChain([chain()], "c1")).not.toBeNull();
    expect(enabledChain([chain({ enabled: false })], "c1")).toBeNull();
    expect(enabledChain([chain({ online_url: null })], "c1")).toBeNull();
    expect(enabledChain([chain({ online_url: "http://insecure.example/" })], "c1")).toBeNull();
    expect(enabledChain([chain()], "other")).toBeNull();
    expect(enabledChain(null, "c1")).toBeNull();
  });

  it("writes one name × quantity line per item", () => {
    expect(tidyQuantity("2.000")).toBe("2");
    expect(tidyQuantity("0.500")).toBe("0.5");
    const items = handoffItems([
      { display_name_he: "חלב טרי 3%", quantity: "2.000" },
      { display_name_he: "עגבניות", quantity: "0.750" },
    ]);
    expect(listText(items, (i) => `${i.name} × ${i.quantity}`)).toBe(
      "חלב טרי 3% × 2\nעגבניות × 0.75",
    );
  });
});
