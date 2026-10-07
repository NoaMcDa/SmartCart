import { render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import type { ReactElement } from "react";
import { describe, expect, it } from "vitest";
import AccessibilityPage from "@/app/(seo)/accessibility/page";
import BasketIndexPage from "@/app/(seo)/basket-index/page";
import CategoryPage, {
  generateMetadata as categoryMetadata,
  generateStaticParams as categoryParams,
} from "@/app/(seo)/c/[slug]/page";
import MethodologyPage from "@/app/(seo)/methodology/page";
import ProductPage, {
  generateMetadata as productMetadata,
  generateStaticParams as productParams,
} from "@/app/(seo)/p/[slug]/page";
import { GET as robots } from "@/app/(seo)/robots.txt/route";
import { getQuality } from "./data";
import { percentDown } from "./format";

async function violations(container: Element) {
  const result = await axe.run(container, {
    rules: { "color-contrast": { enabled: false } },
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
  });
  return result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.html).join(" | ")}`);
}

function jsonLd(container: Element): Record<string, unknown>[] {
  return [...container.querySelectorAll('script[type="application/ld+json"]')].flatMap(
    (s) => JSON.parse(s.textContent ?? "null") as Record<string, unknown>[],
  );
}

describe("methodology page (#21)", () => {
  it("covers sourcing, matching, net saving, neutrality, quality, basket index and privacy", () => {
    const { container } = render(<MethodologyPage />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("איך אנחנו משווים מחירים");
    for (const id of [
      "sources",
      "matching",
      "saving",
      "neutrality",
      "quality",
      "basket-index",
      "privacy",
    ]) {
      expect(container.querySelector(`section#${id}`), id).not.toBeNull();
    }
    expect(screen.getAllByText(/המחיר הקובע הוא בקופה/).length).toBeGreaterThan(0);
  });

  it("states the saving is versus the user's own store and never the most expensive chain", () => {
    render(<MethodologyPage />);
    expect(screen.getByText(/לעולם לא לעומת הרשת היקרה ביותר/)).toBeInTheDocument();
    expect(screen.getByText(/חיסכון נטו = חיסכון בסל − עלות הנסיעה/)).toBeInTheDocument();
  });

  it("makes the neutrality commitments", () => {
    render(<MethodologyPage />);
    expect(screen.getByText(/לא מוכרים מידע על משתמשים/)).toBeInTheDocument();
    expect(screen.getByText(/אין דירוג ממומן/)).toBeInTheDocument();
    expect(screen.getByText(/יסומנו בבירור ולא ישפיעו על הדירוג/)).toBeInTheDocument();
  });

  it("shows the quality metric from quality.json, not hand-typed text", () => {
    render(<MethodologyPage />);
    const q = getQuality();
    expect(q.available).toBe(true);
    if (!q.available) return;
    const metric = screen.getByTestId("quality-metric");
    expect(metric.textContent).toContain(percentDown(q.precision.any_brand ?? 0));
    expect(metric.textContent).toContain("מההחלפות נכונות בסט ההערכה");
    if (q.synthetic) expect(metric.textContent).toContain("סינתטי עד שיהיו נתונים אמיתיים");
    expect(within(metric).getByText(/תאריך מדידה/)).toBeInTheDocument();
  });

  it("marks every kind of number, shows the update date and has WebPage data", () => {
    const { container } = render(<MethodologyPage />);
    for (const kind of ["נמדד", "הערכה", "יעד", "לפי החוק"]) {
      expect(screen.getAllByText(kind).length, kind).toBeGreaterThan(0);
    }
    expect(screen.getByText(/עודכן לאחרונה/).querySelector("time")).not.toBeNull();
    const types = jsonLd(container).map((d) => d["@type"]);
    expect(types).toEqual(expect.arrayContaining(["BreadcrumbList", "WebPage"]));
  });

  it("has no structural accessibility violations", async () => {
    const { container } = render(<MethodologyPage />);
    expect(await violations(container)).toEqual([]);
  });
});

describe("category pages (#35)", () => {
  it("are generated for every exported category with a canonical", async () => {
    const params = categoryParams();
    expect(params.length).toBeGreaterThan(50);
    expect(params).toContainEqual({ slug: "dairy" });
    expect(params).toContainEqual({ slug: "dairy-milk" });
  });

  it("render the Hebrew title, products, update date, methodology link and the checkout line", async () => {
    const element = (await CategoryPage({
      params: Promise.resolve({ slug: "dairy-milk" }),
    })) as ReactElement;
    const { container } = render(element);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("חלב ומשקאות חלב");
    expect(screen.getByRole("link", { name: /חלב טרי 3%/ })).toHaveAttribute(
      "href",
      "/p/milk-fresh-3",
    );
    expect(screen.getByText(/נתוני הקטלוג עודכנו בתאריך/).querySelector("time")).not.toBeNull();
    expect(screen.getByRole("link", { name: "איך אנחנו משווים מחירים" })).toHaveAttribute(
      "href",
      "/methodology",
    );
    expect(screen.getByText(/המחיר הקובע הוא בקופה/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "בני רשימת קניות" })).toHaveAttribute("href", "/");
    const ld = jsonLd(container);
    expect(ld.map((d) => d["@type"])).toEqual(["BreadcrumbList", "CollectionPage"]);
    expect(await violations(container)).toEqual([]);
  });

  it("a department links to its categories", async () => {
    render((await CategoryPage({ params: Promise.resolve({ slug: "dairy" }) })) as ReactElement);
    expect(screen.getByRole("link", { name: /חלב ומשקאות חלב/ })).toHaveAttribute(
      "href",
      "/c/dairy-milk",
    );
  });

  it("have a title, description, canonical URL and open graph data", async () => {
    const meta = await categoryMetadata({ params: Promise.resolve({ slug: "dairy-milk" }) });
    expect(meta.title).toBe("מחירי חלב ומשקאות חלב בסופרים");
    expect(String(meta.description)).toContain("המחיר הקובע הוא בקופה");
    expect(String(meta.alternates?.canonical)).toMatch(/^https?:\/\/.+\/c\/dairy-milk$/);
    expect(meta.openGraph?.locale).toBe("he_IL");
  });
});

describe("product pages (#35)", () => {
  it("are generated for the best-ranked canonicals only", () => {
    const params = productParams();
    expect(params).toContainEqual({ slug: "milk-fresh-3" });
    expect(params.length + categoryParams().length).toBeLessThanOrEqual(200);
  });

  it("without prices say so, carry no offers, and keep the trust lines", async () => {
    const element = (await ProductPage({
      params: Promise.resolve({ slug: "milk-fresh-3" }),
    })) as ReactElement;
    const { container } = render(element);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("חלב טרי 3%");
    expect(screen.getByText(/עדיין לא נטענו מחירים למוצר הזה/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    const product = jsonLd(container).find((d) => d["@type"] === "Product")!;
    expect(product).not.toHaveProperty("offers");
    expect(screen.getByText(/נתוני הקטלוג עודכנו בתאריך/).querySelector("time")).not.toBeNull();
    expect(screen.getByRole("link", { name: "איך אנחנו משווים מחירים" })).toHaveAttribute(
      "href",
      "/methodology",
    );
    expect(screen.getByText(/המחיר הקובע הוא בקופה/)).toBeInTheDocument();
    // critical attributes and the three flexibility levels, each level with icon and text
    expect(screen.getByText("אחוז שומן")).toBeInTheDocument();
    expect(screen.getByText("3%")).toBeInTheDocument();
    for (const label of ["מוצר מדויק", "כל מותג", "תחליף קרוב"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(await violations(container)).toEqual([]);
  });

  it("weighed produce is labeled as an estimate", async () => {
    render((await ProductPage({ params: Promise.resolve({ slug: "tomato" }) })) as ReactElement);
    expect(screen.getByText("מחיר מוערך, מוצר במשקל")).toBeInTheDocument();
  });

  it("have title, description, canonical and are indexable by default", async () => {
    const meta = await productMetadata({ params: Promise.resolve({ slug: "milk-fresh-3" }) });
    expect(String(meta.title)).toContain("חלב טרי 3%");
    expect(String(meta.alternates?.canonical)).toMatch(/\/p\/milk-fresh-3$/);
    expect(meta.robots).toBeUndefined();
  });
});

describe("basket index and accessibility statement", () => {
  it("basket index without a published month says so and still publishes the basket", async () => {
    const { container } = render(<BasketIndexPage />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("מדד הסל החודשי");
    expect(screen.getByText("המדד הראשון טרם פורסם")).toBeInTheDocument();
    expect(screen.getByText(/רשימת המוצרים והכמויות \(גרסה 1\)/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "המתודולוגיה המלאה" })).toHaveAttribute(
      "href",
      "/methodology",
    );
    expect(screen.getByText(/עודכן לאחרונה/).querySelector("time")).not.toBeNull();
    expect(await violations(container)).toEqual([]);
  });

  it("accessibility statement names the standard and what is still manual", async () => {
    const { container } = render(<AccessibilityPage />);
    expect(screen.getAllByText(/5568/).length).toBeGreaterThan(0);
    expect(screen.getByText(/VoiceOver/)).toBeInTheDocument();
    expect(await violations(container)).toEqual([]);
  });
});

describe("robots.txt", () => {
  it("allows crawling, hides per-person pages and points at the sitemap", async () => {
    const text = await robots().text();
    expect(text).toContain("User-agent: *");
    expect(text).toContain("Allow: /");
    expect(text).toContain("Disallow: /compare");
    expect(text).toMatch(/Sitemap: https?:\/\/.+\/sitemap\.xml/);
  });
});
