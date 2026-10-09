import { expect, type Page } from "@playwright/test";

/**
 * Wait until the page has settled before measuring it: no CSS animation still running (a bottom
 * sheet fades in over 200 ms, and axe would measure contrast through its partial opacity) and no
 * web font still loading (layout measured with a fallback font can be wider). On a fast machine
 * both are already done; on a slow CI runner they are not.
 */
export async function settle(page: Page): Promise<void> {
  await page.waitForFunction(
    () =>
      document
        .getAnimations()
        .every((a) => a.playState !== "running" || a.effect?.getTiming().iterations === Infinity),
    undefined,
    { timeout: 10_000 },
  );
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  await expect
    .poll(
      () => page.evaluate(() => [...document.fonts].filter((f) => f.status === "loading").length),
      { timeout: 10_000 },
    )
    .toBe(0);
}

/** Make the browser fetch the Arabic face now, then wait for it (it is not preloaded). */
export async function loadArabicFont(page: Page): Promise<string[]> {
  return page.evaluate(async () => {
    const family = getComputedStyle(document.body).fontFamily;
    // load() rejects if any face in the stack fails; the Arabic face is what matters here.
    await document.fonts.load(`16px ${family}`, "ابت").catch(() => undefined);
    await document.fonts.ready;
    return [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family);
  });
}
