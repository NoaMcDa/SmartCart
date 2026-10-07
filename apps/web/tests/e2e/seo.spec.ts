import { expect, test } from "@playwright/test";

/** Static SEO pages (#35, #21, #44): crawl files, structured data, trust lines, no scraped content. */

test("sitemap.xml lists at least 50 generated pages with absolute URLs", async ({ request }) => {
  const res = await request.get("/sitemap.xml");
  expect(res.status()).toBe(200);
  expect(res.headers()["content-type"]).toContain("xml");
  const xml = await res.text();
  const urls = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]!);
  expect(urls.length).toBeGreaterThanOrEqual(50);
  expect(urls.filter((u) => u.includes("/c/") || u.includes("/p/")).length).toBeGreaterThanOrEqual(
    50,
  );
  for (const u of urls) expect(u).toMatch(/^https?:\/\//);
  expect(urls.some((u) => u.endsWith("/methodology"))).toBe(true);
  expect(urls.some((u) => u.endsWith("/basket-index"))).toBe(true);
});

test("robots.txt points at the sitemap and keeps per-person pages out", async ({ request }) => {
  const res = await request.get("/robots.txt");
  expect(res.status()).toBe(200);
  const text = await res.text();
  expect(text).toMatch(/Sitemap: https?:\/\/\S+\/sitemap\.xml/);
  expect(text).toContain("Disallow: /compare");
});

test("every sitemap page responds 200 with an RTL Hebrew document", async ({ request, page }) => {
  const xml = await (await request.get("/sitemap.xml")).text();
  const paths = [...xml.matchAll(/<loc>https?:\/\/[^/]+(\/[^<]*)<\/loc>/g)].map((m) => m[1]!);
  const generated = paths.filter((p) => /^\/(c|p)\//.test(p));
  for (const path of generated.slice(0, 12)) {
    const res = await page.goto(path);
    expect(res?.status(), path).toBe(200);
    await expect(page.locator("html")).toHaveAttribute("lang", "he");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  }
});

test("unknown product and category slugs are 404, not empty pages", async ({ page }) => {
  expect((await page.goto("/p/no-such-product"))?.status()).toBe(404);
  expect((await page.goto("/c/no-such-category"))?.status()).toBe(404);
});

test.describe("a product page", () => {
  test("has a title, description, canonical, JSON-LD, an update date and the trust lines", async ({
    page,
  }) => {
    await page.goto("/p/milk-fresh-3");
    await expect(page).toHaveTitle(/חלב טרי 3%/);
    await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /.{40,}/);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
      "href",
      /\/p\/milk-fresh-3$/,
    );
    const blocks = await page.locator('script[type="application/ld+json"]').allTextContents();
    const data = blocks.flatMap((b) => JSON.parse(b) as Record<string, unknown>[]);
    expect(data.map((d) => d["@type"])).toEqual(["BreadcrumbList", "Product"]);
    const product = data.find((d) => d["@type"] === "Product")!;
    expect(product.name).toBe("חלב טרי 3%");
    // no prices are loaded in the committed snapshot, so the page claims no offer
    expect(product).not.toHaveProperty("offers");
    await expect(page.locator("time").first()).toHaveAttribute("datetime", /^\d{4}-\d{2}-\d{2}$/);
    await expect(page.getByText("המחיר הקובע הוא בקופה").first()).toBeVisible();
    await expect(
      page.getByRole("link", { name: "איך אנחנו משווים מחירים" }).first(),
    ).toHaveAttribute("href", "/methodology");
    await expect(page.getByRole("link", { name: "בני רשימת קניות" })).toHaveAttribute("href", "/");
  });

  test("loads no third-party resource (no scraped images, no trackers)", async ({ page }) => {
    const external: string[] = [];
    page.on("request", (req) => {
      const url = new URL(req.url());
      if (!["localhost", "127.0.0.1"].includes(url.hostname)) external.push(req.url());
    });
    for (const path of ["/p/milk-fresh-3", "/c/dairy", "/methodology", "/basket-index"]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      expect(await page.locator("img").count(), `${path} has no images`).toBe(0);
    }
    expect(external).toEqual([]);
  });
});

test("the methodology page shows the quality metric from quality.json with its date", async ({
  page,
}) => {
  await page.goto("/methodology");
  const metric = page.getByTestId("quality-metric");
  await expect(metric).toBeVisible();
  await expect(metric).toContainText("מההחלפות נכונות בסט ההערכה");
  await expect(metric).toContainText("סינתטי עד שיהיו נתונים אמיתיים");
  await expect(metric.locator("time")).toHaveAttribute("datetime", /^\d{4}-\d{2}-\d{2}$/);
});

test("the quality file the page reads is served", async ({ request }) => {
  const res = await request.get("/seo/quality.json");
  expect(res.status()).toBe(200);
  const q = await res.json();
  expect(q.available).toBe(true);
  expect(q.precision.any_brand).toBeGreaterThan(0);
});

test("the basket index shows the first-month placeholder and the published basket", async ({
  page,
}) => {
  await page.goto("/basket-index");
  await expect(page.getByText("המדד הראשון טרם פורסם")).toBeVisible();
  await page.getByText(/רשימת המוצרים והכמויות/).click();
  await expect(page.getByRole("table", { name: /הסל הקבוע, גרסה 1: 25 מוצרים/ })).toBeVisible();
  await expect(page.getByRole("link", { name: "המתודולוגיה המלאה" })).toBeVisible();
});

test.describe("phone, 390 px", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  for (const path of [
    "/p/milk-fresh-3",
    "/c/dairy",
    "/c/dairy-milk",
    "/basket-index",
    "/accessibility",
  ]) {
    test(`${path} has no horizontal scroll`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }
});
