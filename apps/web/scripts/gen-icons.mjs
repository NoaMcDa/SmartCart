// One-time setup: rasterize public/icons/*.svg into the PNG sizes the manifest and iOS need.
// Output is committed. Rerun after changing the SVGs: node scripts/gen-icons.mjs
// Uses Playwright's Chromium (set PW_CHROMIUM_PATH to use a preinstalled browser binary).
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const icons = path.join(root, "public", "icons");

const jobs = [
  { src: "icon.svg", out: "icon-192.png", size: 192 },
  { src: "icon.svg", out: "icon-512.png", size: 512 },
  { src: "icon-maskable.svg", out: "icon-maskable-512.png", size: 512 },
  // iOS ignores transparency and rounds corners itself, so use the full-bleed variant.
  { src: "icon-maskable.svg", out: "apple-touch-icon.png", size: 180 },
];

const browser = await chromium.launch({
  executablePath: process.env.PW_CHROMIUM_PATH || undefined,
});
try {
  for (const job of jobs) {
    const svg = await readFile(path.join(icons, job.src), "utf8");
    const page = await browser.newPage({ viewport: { width: job.size, height: job.size } });
    await page.setContent(
      `<html><body style="margin:0;background:transparent">` +
        svg.replace(
          "<svg ",
          `<svg style="display:block;width:${job.size}px;height:${job.size}px" `,
        ) +
        `</body></html>`,
    );
    await page.screenshot({ path: path.join(icons, job.out), omitBackground: true });
    await page.close();
    console.log(`wrote ${job.out}`);
  }
} finally {
  await browser.close();
}
