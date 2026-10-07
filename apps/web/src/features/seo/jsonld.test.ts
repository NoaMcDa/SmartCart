import { describe, expect, it } from "vitest";
import { categoryPages, getProduct, productPages, productsIn } from "./data";
import {
  breadcrumbList,
  categoryJsonLd,
  productJsonLd,
  serializeJsonLd,
  webPageJsonLd,
} from "./jsonld";
import type { Product } from "./types";

const priced: Product = {
  ...getProduct("milk-fresh-3")!,
  no_prices_yet: false,
  price_valid_from: "2026-10-07T05:00:00Z",
  prices: [
    {
      chain_id: "a",
      chain_name: "רמי לוי",
      min_unit_price: 0.45,
      median_unit_price: 0.5,
      stores: 12,
      is_estimated: false,
      price_valid_from: "2026-10-07T05:00:00Z",
    },
    {
      chain_id: "b",
      chain_name: "שופרסל",
      min_unit_price: 0.55,
      median_unit_price: 0.62,
      stores: 30,
      is_estimated: false,
      price_valid_from: "2026-10-06T05:00:00Z",
    },
  ],
};

describe("structured data", () => {
  it("BreadcrumbList has ordered positions and absolute URLs", () => {
    const list = breadcrumbList([
      { name: "בית", path: "/" },
      { name: "חלב", path: "/c/dairy-milk" },
    ]) as { itemListElement: { position: number; item: string; name: string }[] };
    expect(list.itemListElement.map((i) => i.position)).toEqual([1, 2]);
    for (const i of list.itemListElement) expect(i.item).toMatch(/^https?:\/\//);
    expect(list.itemListElement[1]?.item).toMatch(/\/c\/dairy-milk$/);
  });

  it("Product has no offers while no prices are loaded", () => {
    const data = productJsonLd(getProduct("milk-fresh-3")!, "https://x.example/p/milk-fresh-3");
    expect(data["@type"]).toBe("Product");
    expect(data.name).toBe("חלב טרי 3%");
    expect(data).not.toHaveProperty("offers");
  });

  it("Product gets one Offer per chain, quoted per base unit, once prices exist", () => {
    const data = productJsonLd(priced, "https://x.example/p/milk-fresh-3") as {
      offers: {
        "@type": string;
        price: number;
        priceCurrency: string;
        seller: { name: string };
        priceSpecification: {
          "@type": string;
          referenceQuantity: { value: number; unitCode: string };
        };
      }[];
    };
    expect(data.offers).toHaveLength(2);
    const [first] = data.offers;
    expect(first).toMatchObject({ "@type": "Offer", price: 0.5, priceCurrency: "ILS" });
    expect(first?.seller.name).toBe("רמי לוי");
    expect(first?.priceSpecification["@type"]).toBe("UnitPriceSpecification");
    expect(first?.priceSpecification.referenceQuantity).toEqual({
      "@type": "QuantitativeValue",
      value: 100,
      unitCode: "MLT",
    });
  });

  it("CollectionPage lists the products as an ItemList", () => {
    const category = categoryPages().find((c) => c.slug === "dairy-milk")!;
    const products = productsIn(category);
    const data = categoryJsonLd(category, products, "https://x.example/c/dairy-milk") as {
      "@type": string;
      mainEntity: { numberOfItems: number; itemListElement: { position: number }[] };
    };
    expect(data["@type"]).toBe("CollectionPage");
    expect(data.mainEntity.numberOfItems).toBe(products.length);
    expect(data.mainEntity.itemListElement.map((i) => i.position)).toEqual(
      products.map((_, i) => i + 1),
    );
  });

  it("WebPage carries the modification date", () => {
    const data = webPageJsonLd({
      name: "n",
      description: "d",
      path: "/methodology",
      dateModified: "2026-10-07",
    });
    expect(data).toMatchObject({
      "@type": "WebPage",
      dateModified: "2026-10-07",
      inLanguage: "he",
    });
  });

  it("serialization cannot close the script tag and round-trips", () => {
    const text = serializeJsonLd({ name: "</script><script>alert(1)</script>" });
    expect(text).not.toContain("<");
    expect(JSON.parse(text)).toEqual({ name: "</script><script>alert(1)</script>" });
  });

  it("every generated product page has a valid Product and BreadcrumbList", () => {
    for (const p of productPages()) {
      const data = productJsonLd(p, `https://x.example/p/${p.slug}`);
      expect(data).toMatchObject({ "@context": "https://schema.org", "@type": "Product" });
      expect(typeof data.name).toBe("string");
      expect(JSON.parse(serializeJsonLd(data))).toBeTruthy();
      expect(data.offers === undefined).toBe(p.no_prices_yet);
    }
  });
});
