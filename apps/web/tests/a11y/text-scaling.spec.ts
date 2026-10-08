import { expect, test, type Page } from "@playwright/test";
import { ROUTES } from "../e2e/routes";
import { israelToday } from "../e2e/phase3-helpers";
import { KEYS, seed, seedComparison, stubTiles } from "../e2e/secondary.helpers";

/**
 * Text-only scaling to 200% (issue #26, WCAG 1.4.4 resize text): the text grows, the viewport does
 * not. Two ways of getting there, because a browser's "font size" setting and an Android text
 * scale do not do the same thing:
 *
 *  - "root": `html { font-size: 200% }`, what the default-font-size setting of desktop browsers
 *    changes. It only moves text sized in rem/em/% (the app sizes in px, so it moves little).
 *  - "all": every element's computed font size and line height doubled in place, which is what
 *    Android's font scale does to px-sized text. This is the one that stresses the layout.
 *
 * On every core route at 390 px and 1280 px, in both modes, asserts that the page has no
 * horizontal scroll, that nothing sticks out of the viewport, and that no key element (headings,
 * buttons, tabs, labels, table cells, price cells, chips and tags) has text clipped or spilling
 * out of its own box: `scrollWidth <= clientWidth` and `scrollHeight <= clientHeight` for the
 * elements that clip (`overflow` other than visible/auto/scroll) or have nowhere to wrap.
 */

type Mode = "root" | "all";
const MODES: ReadonlyArray<Mode> = ["root", "all"];
const VIEWPORTS = [
  { width: 390, height: 844 },
  { width: 1280, height: 900 },
] as const;

const KEY_SELECTOR = [
  "h1",
  "h2",
  "h3",
  "button",
  "[role=button]",
  "[role=tab]",
  "[role=switch]",
  "[role=checkbox]",
  "a[class*=button]",
  "label",
  "th",
  "td",
  "[class*=price]",
  "[class*=Price]",
  "[class*=chip]",
  "[class*=tag]",
].join(",");

/** `html { font-size: 200% }` or every computed size doubled in place. */
async function scaleText(page: Page, mode: Mode) {
  if (mode === "root") {
    await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
    return;
  }
  const before = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize));
  await page.evaluate(() => {
    const els = [...document.querySelectorAll<HTMLElement>("body, body *")];
    // Read everything first, then write, so a parent's new size cannot change what a child reads.
    const sizes = els.map((el) => {
      const cs = getComputedStyle(el);
      const lineHeight = parseFloat(cs.lineHeight);
      return {
        size: parseFloat(cs.fontSize),
        lineHeight: Number.isFinite(lineHeight) ? lineHeight : null,
      };
    });
    els.forEach((el, i) => {
      const s = sizes[i]!;
      if (!Number.isFinite(s.size)) return;
      el.style.setProperty("font-size", `${s.size * 2}px`, "important");
      if (s.lineHeight !== null)
        el.style.setProperty("line-height", `${s.lineHeight * 2}px`, "important");
    });
  });
  const after = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize));
  expect(after, "the text really doubled").toBe(before * 2);
  // Let layout settle (images, fonts, effects that react to size).
  await page.evaluate(() => new Promise<void>((r) => requestAnimationFrame(() => r())));
}

type Finding = { selector: string; text: string; why: string };

async function measure(page: Page) {
  return page.evaluate((keySelector) => {
    const vw = document.documentElement.clientWidth;
    const label = (el: Element) =>
      `${el.tagName.toLowerCase()}.${
        String(el.getAttribute("class") ?? "")
          .split(" ")[0]
          ?.slice(0, 40) ?? ""
      }`;
    const visible = (el: Element) => {
      const r = el.getBoundingClientRect();
      return (
        r.width > 0 && r.height > 0 && !el.closest(".sr-only, [hidden], [aria-hidden=true] svg")
      );
    };
    // Tables scroll inside their own wrapper and the map clips its own canvas (WCAG 1.4.10).
    const scroller = (el: Element) =>
      el.closest("[class*='tableWrap'], [class*='maplibregl-map'], .maplibregl-canvas-container");

    const outside: Finding[] = [];
    for (const el of document.querySelectorAll("body *")) {
      if (!visible(el)) continue;
      const wrap = scroller(el);
      if (wrap && wrap !== el) continue;
      const r = el.getBoundingClientRect();
      if (r.right > vw + 0.5 || r.left < -0.5) {
        outside.push({
          selector: label(el),
          text: (el.textContent ?? "").trim().slice(0, 40),
          why: `outside the viewport: ${Math.round(r.left)}..${Math.round(r.right)} of ${vw}`,
        });
      }
    }

    const clipped: Finding[] = [];
    for (const el of document.querySelectorAll<HTMLElement>(keySelector)) {
      if (!visible(el)) continue;
      const wrap = scroller(el);
      if (wrap && wrap !== el) continue;
      const cs = getComputedStyle(el);
      if (cs.display === "inline" || cs.display === "contents") continue;
      // Text is what is checked: a switch track or an icon-only button has none.
      if (!(el.textContent ?? "").trim()) continue;
      const scrolls = (v: string) => v === "auto" || v === "scroll";
      const clipsX = !scrolls(cs.overflowX);
      const clipsY = !scrolls(cs.overflowY);
      const wide = clipsX && el.scrollWidth > el.clientWidth + 1;
      const tall = clipsY && cs.overflowY !== "visible" && el.scrollHeight > el.clientHeight + 1;
      if (wide || tall) {
        clipped.push({
          selector: label(el),
          text: (el.textContent ?? "").trim().slice(0, 40),
          why: wide
            ? `scrollWidth ${el.scrollWidth} > clientWidth ${el.clientWidth}`
            : `scrollHeight ${el.scrollHeight} > clientHeight ${el.clientHeight}`,
        });
      }
    }

    return {
      vw,
      scroll: document.documentElement.scrollWidth,
      bodyScroll: document.body.scrollWidth,
      outside: outside.slice(0, 10),
      clipped: clipped.slice(0, 10),
    };
  }, KEY_SELECTOR);
}

async function assertScaled(page: Page, viewportWidth: number) {
  const m = await measure(page);
  expect(m.vw, "the viewport did not change").toBe(viewportWidth);
  expect(m.outside, "elements outside the viewport").toEqual([]);
  expect(m.scroll, "document scrollWidth").toBeLessThanOrEqual(m.vw);
  expect(m.bodyScroll, "body scrollWidth").toBeLessThanOrEqual(m.vw);
  expect(m.clipped, "key elements with clipped or spilling text").toEqual([]);
}

async function prepare(page: Page) {
  // The core routes with something to show: a comparison for results, split and store mode, and a
  // budget with two recorded shops (one corrected) for Profile.
  await seedComparison(page);
  await stubTiles(page);
  const today = israelToday();
  await seed(page, {
    [KEYS.profile]: {
      version: 1,
      onboardingDone: true,
      consentLocation: true,
      location: {
        lat: 31.897,
        lon: 35.01,
        city: "מודיעין-מכבים-רעות",
        neighborhood: null,
        source: "manual",
      },
      radiusKm: 5,
      homeChainId: "shufersal",
      homeStoreId: 103,
      clubs: [],
      travelMode: "car",
      extraStopValue: 25,
      costPerKm: 1.2,
      diet: { vegan: false, glutenFree: false, kosherLevel: null, allergens: [] },
      flexDefaults: {},
      updatedAt: null,
    },
    "sc-budget-v1": { monthly: 2500 },
    "sc-spend-v1": {
      version: 1,
      entries: [
        {
          id: "t1",
          client_id: "00000000-0000-4000-8000-000000000001",
          date: today,
          store_id: 101,
          store_name: "רמי לוי · מודיעין",
          total: 389,
          item_count: 8,
          plan: "single",
        },
        {
          id: "t2",
          date: today,
          store_id: 102,
          store_name: "יוחננוף · מודיעין",
          total: 1234.5,
          item_count: 12,
          plan: "split",
          corrected: true,
        },
      ],
      pending: [],
    },
  });
}

const PATHS: ReadonlyArray<string> = [
  ...ROUTES.map((r) => r.path),
  "/store-mode?store=101",
  "/profile#budget",
];

for (const mode of MODES) {
  for (const viewport of VIEWPORTS) {
    test.describe(`text at 200% (${mode}), ${viewport.width} px`, () => {
      test.use({ viewport: { width: viewport.width, height: viewport.height } });

      for (const path of PATHS) {
        test(`${path}: no horizontal scroll, no clipped text`, async ({ page }) => {
          await prepare(page);
          await page.goto(path);
          // The map keeps fetching tiles, so "idle" is best effort.
          await page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => undefined);
          await scaleText(page, mode);
          await assertScaled(page, viewport.width);
        });
      }
    });
  }
}

test.describe("text at 200%, states behind a tap", () => {
  for (const viewport of VIEWPORTS) {
    test.describe(`${viewport.width} px`, () => {
      test.use({ viewport: { width: viewport.width, height: viewport.height } });

      test("the budget section while correcting a total", async ({ page }) => {
        await prepare(page);
        await page.goto("/profile#budget");
        await page
          .getByRole("button", { name: /^תיקון הסכום/ })
          .first()
          .click();
        await expect(page.getByTestId("spend-edit-form")).toBeVisible();
        await scaleText(page, "all");
        await assertScaled(page, viewport.width);
      });

      test("the budget section with the delete confirmation", async ({ page }) => {
        await prepare(page);
        await page.goto("/profile#budget");
        await page
          .getByRole("button", { name: /^מחיקת הקנייה/ })
          .first()
          .click();
        await expect(page.getByTestId("spend-delete-confirm")).toBeVisible();
        await scaleText(page, "all");
        await assertScaled(page, viewport.width);
      });

      test("the flexibility sheet on the list builder", async ({ page }) => {
        await prepare(page);
        await page.goto("/");
        await page.getByTestId("list-row").first().waitFor({ timeout: 10_000 });
        await page
          .getByTestId("list-row")
          .first()
          .getByRole("button", { name: /^רמת גמישות/ })
          .click();
        await expect(page.getByRole("dialog")).toBeVisible();
        await scaleText(page, "all");
        await assertScaled(page, viewport.width);
      });
    });
  }
});
