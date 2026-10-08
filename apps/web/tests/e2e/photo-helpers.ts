/**
 * Helpers for the photo specs (receipts #61, handwritten lists #68).
 *
 * `mockApi` (core-helpers.ts) rewrites every request body as JSON, which breaks a multipart
 * upload, so `mockPhotoApi` answers `/parse-image` itself from the same MSW handler with the real
 * headers and body. Register it after `mockApi`: the later route wins for this path. File names
 * pick the case (see `imageRefusal` in src/mocks/handlers.phase3.ts): `x-429.jpg`, `x-413.jpg`,
 * `x-503.jpg`, `empty.jpg` ...
 */
import type { Page } from "@playwright/test";
import { getResponse } from "msw";
import { API_BASE_URL } from "../../src/api/config";
import { handlers } from "../../src/mocks/handlers";

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS",
};

export type PhotoCall = {
  /** `X-Image-Consent`, as sent. */
  consent: string | null;
  authorization: string | null;
  kind: string;
  filename: string;
  size: number;
  contentType: string;
  /** The uploaded file's bytes. */
  bytes: Buffer;
};

export type PhotoApi = {
  calls: PhotoCall[];
  /** Hold every answer until `release()`, so a test can look at the progress state. */
  hold(): void;
  release(): void;
  /** Drop the connection for the next request (a network failure). */
  failNext(): void;
};

export async function mockPhotoApi(page: Page): Promise<PhotoApi> {
  const calls: PhotoCall[] = [];
  let gate: Promise<void> | null = null;
  let open: (() => void) | null = null;
  let dropNext = false;
  const origin = new URL(API_BASE_URL).origin;

  await page.route(
    (url) => url.origin === origin && url.pathname === "/parse-image",
    async (route) => {
      const req = route.request();
      if (req.method() === "OPTIONS") {
        await route.fulfill({ status: 204, headers: CORS });
        return;
      }
      const headers = req.headers();
      const body = req.postDataBuffer() ?? Buffer.alloc(0);
      const init: RequestInit = {
        method: "POST",
        headers: {
          "content-type": headers["content-type"] ?? "",
          ...(headers["x-image-consent"] ? { "x-image-consent": headers["x-image-consent"] } : {}),
        },
        body: new Uint8Array(body),
      };
      const form = await new Request(req.url(), init).formData();
      const image = form.get("image");
      const file = typeof image === "object" && image !== null ? image : null;
      calls.push({
        consent: headers["x-image-consent"] ?? null,
        authorization: headers["authorization"] ?? null,
        kind: String(form.get("kind")),
        filename: file?.name ?? "",
        size: file?.size ?? 0,
        contentType: headers["content-type"] ?? "",
        bytes: file ? Buffer.from(await file.arrayBuffer()) : Buffer.alloc(0),
      });
      if (dropNext) {
        dropNext = false;
        await route.abort("connectionreset");
        return;
      }
      if (gate) await gate;
      const res = await getResponse(handlers, new Request(req.url(), init));
      if (!res) {
        await route.fulfill({ status: 501, headers: CORS, body: "{}" });
        return;
      }
      await route.fulfill({
        status: res.status,
        headers: { ...CORS, "content-type": "application/json" },
        body: await res.text(),
      });
    },
  );

  return {
    calls,
    hold() {
      gate = new Promise<void>((resolve) => {
        open = resolve;
      });
    },
    release() {
      open?.();
      gate = null;
    },
    failNext() {
      dropNext = true;
    },
  };
}

/** A real 1x1 PNG: the browser can decode it, so the upload path is the normal one. */
export const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC",
  "base64",
);

export const imageFile = (name: string, mimeType = "image/png", buffer: Buffer = TINY_PNG) => ({
  name,
  mimeType,
  buffer,
});

/** Width and height of a JPEG from its first start-of-frame marker; null if there is none. */
export function jpegSize(bytes: Buffer): { width: number; height: number } | null {
  let i = 2;
  while (i + 9 < bytes.length) {
    if (bytes[i] !== 0xff) {
      i += 1;
      continue;
    }
    const marker = bytes[i + 1]!;
    if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) {
      return { height: bytes.readUInt16BE(i + 5), width: bytes.readUInt16BE(i + 7) };
    }
    i += 2 + bytes.readUInt16BE(i + 2);
  }
  return null;
}

/** A large flat-colour photo made in the page (so no image library is needed here), as a JPEG. */
export async function bigPhoto(page: Page, width: number, height: number): Promise<Buffer> {
  const base64 = await page.evaluate(
    async ([w, h]) => {
      const canvas = document.createElement("canvas");
      canvas.width = w!;
      canvas.height = h!;
      const ctx = canvas.getContext("2d")!;
      const gradient = ctx.createLinearGradient(0, 0, w!, h!);
      gradient.addColorStop(0, "#fdfdfd");
      gradient.addColorStop(1, "#8899aa");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, w!, h!);
      const blob = await new Promise<Blob>((resolve) =>
        canvas.toBlob((b) => resolve(b!), "image/jpeg", 0.9),
      );
      const bytes = new Uint8Array(await blob.arrayBuffer());
      let binary = "";
      for (const b of bytes) binary += String.fromCharCode(b);
      return btoa(binary);
    },
    [width, height],
  );
  return Buffer.from(base64, "base64");
}
