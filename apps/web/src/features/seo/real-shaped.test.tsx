import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProductContent } from "./PageContents";
import { productJsonLd, serializeJsonLd } from "./jsonld";
import type { ChainPrice, Product } from "./types";

/**
 * Product rows shaped like the ones a real day produces (docs/seo.md, "SEO on real prices"):
 * chain names with quotes and brackets, a weighed product from seven chains, a product priced at
 * one store, a product whose prices the export held back. The pages must keep the update date on
 * every price, the checkout line and the estimate label, and say plainly when a price is held back.
 */

const BASE: Product = {
  slug: "chicken-breast-fresh",
  name_he: "חזה עוף טרי",
  taxonomy_id: "meat.poultry",
  path: [
    { id: "meat", name_he: "בשר ועוף", slug: "meat" },
    { id: "meat.poultry", name_he: "עוף", slug: "meat-poultry" },
  ],
  product_type: "chicken_breast",
  base_unit: "kg",
  critical_attrs: { state: "fresh" },
  rank: 12,
  has_page: true,
  no_prices_yet: false,
  prices: null,
  price_valid_from: "2026-10-22T05:10:00Z",
};

function chain(id: string, name: string, median: number, date: string, stores = 5): ChainPrice {
  return {
    chain_id: id,
    chain_name: name,
    min_unit_price: Math.max(0.01, +(median * 0.9).toFixed(2)),
    median_unit_price: median,
    stores,
    is_estimated: true,
    price_valid_from: date,
  };
}

const SEVEN: ChainPrice[] = [
  chain("shufersal", "שופרסל", 39.9, "2026-10-22T05:10:00Z", 40),
  chain("ramilevy", "רמי לוי", 29.9, "2026-10-22T04:00:00Z", 31),
  chain("mega", 'קרפור "מגה" (קרפור ישראל) בע"מ', 34.9, "2026-10-21T21:00:00Z", 12),
  chain("osherad", "אושר עד", 36.9, "2026-10-20T08:00:00Z", 9),
  chain("tivtaam", "טיב טעם", 44.9, "2026-10-22T03:00:00Z", 7),
  chain("yohananof", "יוחננוף", 35.9, "2026-09-02T08:00:00Z", 3),
  chain("king_store", "קינג סטור <b>", 38.9, "2026-10-22T05:10:00Z", 1),
];

const CRUMBS = [
  { name: "בית", path: "/" },
  { name: "עוף", path: "/c/meat-poultry" },
];

function view(product: Product) {
  return render(
    <ProductContent
      product={product}
      crumbs={CRUMBS}
      related={[]}
      updatedAt={product.price_valid_from ?? "2026-10-22T05:10:00Z"}
    />,
  );
}

describe("a weighed product priced at seven chains", () => {
  const product: Product = { ...BASE, prices: SEVEN };

  it("dates every price row, and shows each chain's own date", () => {
    view(product);
    const table = screen.getByRole("table");
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(7);
    for (const row of rows) {
      const time = row.querySelector("time");
      expect(time, row.textContent ?? "").not.toBeNull();
      expect(time?.getAttribute("datetime")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
    // an old chain date is shown as it is, not replaced by the newest date on the page
    expect(within(table).getByText("2 בספטמבר 2026")).toHaveAttribute("datetime", "2026-09-02");
  });

  it("labels the weighed price as an estimate, in the heading area and in every row", () => {
    view(product);
    expect(screen.getAllByText("הערכה, מוצר במשקל")).toHaveLength(7);
    expect(screen.getByText("מחיר מוערך, מוצר במשקל")).toBeInTheDocument();
  });

  it("keeps the checkout line, the methodology link and renders quotes and tags as text", () => {
    const { container } = view(product);
    expect(screen.getAllByText(/המחיר הקובע הוא בקופה/).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "איך אנחנו משווים מחירים" })).toHaveAttribute(
      "href",
      "/methodology",
    );
    expect(screen.getByText('קרפור "מגה" (קרפור ישראל) בע"מ')).toBeInTheDocument();
    expect(screen.getByText("קינג סטור <b>")).toBeInTheDocument();
    expect(container.querySelector("table b")).toBeNull();
  });

  it("makes no claim of withheld prices when none were withheld", () => {
    view(product);
    expect(screen.queryByText(/לא מוצג כאן כי הוא חריג/)).toBeNull();
  });
});

describe("withheld prices are said, not hidden and not shown", () => {
  const held = [
    {
      chain_id: "ramilevy",
      chain_name: "רמי לוי",
      reason: "chain_outlier",
      detail: "170.40 against 14.16 at the other chains",
      rows: 4,
    },
  ];

  it("with other chains priced: a note under the table, the held chain is not listed", () => {
    view({ ...BASE, prices: SEVEN.filter((c) => c.chain_id !== "ramilevy"), withheld: held });
    expect(screen.getByText(/לא מוצג כאן כי הוא חריג מאוד/)).toBeInTheDocument();
    expect(screen.queryByText("רמי לוי")).toBeNull();
    expect(screen.queryByText(/170/)).toBeNull();
  });

  it("with nothing left to show: the page says the prices are being checked, not that none were loaded", () => {
    view({ ...BASE, no_prices_yet: true, prices: null, price_valid_from: null, withheld: held });
    expect(screen.getByText(/המחירים של המוצר הזה לא מוצגים כרגע/)).toBeInTheDocument();
    expect(screen.queryByText(/עדיין לא נטענו מחירים/)).toBeNull();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getAllByText(/המחיר הקובע הוא בקופה/).length).toBeGreaterThan(0);
  });

  it("a product with no prices and nothing held back keeps the original notice", () => {
    view({ ...BASE, no_prices_yet: true, prices: null, price_valid_from: null });
    expect(screen.getByText(/עדיין לא נטענו מחירים למוצר הזה/)).toBeInTheDocument();
  });
});

describe("one store, one chain", () => {
  it("shows the single row with its date and store count", () => {
    const product: Product = {
      ...BASE,
      base_unit: "100g",
      prices: [
        { ...chain("osherad", "אושר עד", 1.17, "2026-10-21T08:00:00Z", 1), is_estimated: false },
      ],
    };
    view(product);
    const row = within(screen.getByRole("table")).getAllByRole("row")[1]!;
    expect(row).toHaveTextContent("אושר עד");
    expect(row.querySelector("time")).toHaveAttribute("datetime", "2026-10-21");
    expect(screen.queryByText("הערכה, מוצר במשקל")).toBeNull();
  });
});

describe("JSON-LD of real-shaped rows", () => {
  it("dates each Offer with validFrom and keeps odd characters in the text, not in the markup", () => {
    const data = productJsonLd({ ...BASE, prices: SEVEN }, "https://preview.invalid/p/x") as {
      offers: { validFrom: string; seller: { name: string } }[];
    };
    // dates are Israel dates: 21:00 UTC on 21 October is already 22 October in Jerusalem (UTC+3)
    expect(data.offers.map((o) => o.validFrom)).toEqual([
      "2026-10-22",
      "2026-10-22",
      "2026-10-22",
      "2026-10-20",
      "2026-10-22",
      "2026-09-02",
      "2026-10-22",
    ]);
    const text = serializeJsonLd(data);
    expect(text).not.toContain("<");
    expect(JSON.parse(text).offers[6].seller.name).toBe("קינג סטור <b>");
  });
});
