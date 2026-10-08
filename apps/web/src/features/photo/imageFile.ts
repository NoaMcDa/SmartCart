/**
 * Client-side checks and downscaling for the photo upload (issues #61 and #68).
 *
 * The server accepts JPEG, PNG and WebP up to 8 MB (`Body_parse_image_parse_image_post`). A phone
 * photo is often 12 megapixels, far more than OCR needs, so anything longer than 2400 px on its
 * longest side is redrawn smaller as a JPEG before the upload; that keeps requests small on mobile
 * data. A format the server does not take (HEIC from an iPhone, GIF) goes through the same redraw
 * when the browser can decode it.
 *
 * The browser parts (decode, draw, encode) sit behind `ImageIO`, so the size logic is tested
 * without a canvas.
 */

/** The server's limit, checked before reading or resizing anything. */
export const MAX_UPLOAD_BYTES = 8 * 1024 * 1024;
/** Longest side after downscaling. */
export const MAX_EDGE_PX = 2400;
const JPEG_QUALITY = 0.85;
const SERVER_TYPES: ReadonlySet<string> = new Set(["image/jpeg", "image/png", "image/webp"]);
const IMAGE_NAME = /\.(jpe?g|png|webp|gif|bmp|heic|heif)$/iu;

export type ImageProblem = "not-image" | "too-big" | "unreadable";

export class ImageFileError extends Error {
  constructor(readonly reason: ImageProblem) {
    super(`image file: ${reason}`);
    this.name = "ImageFileError";
  }
}

type FileLike = { type: string; size: number; name?: string };

/** `null` when the file may go on; otherwise why not. An empty type falls back to the extension. */
export function checkImageFile(file: FileLike): ImageProblem | null {
  const isImage = file.type ? file.type.startsWith("image/") : IMAGE_NAME.test(file.name ?? "");
  if (!isImage) return "not-image";
  if (file.size > MAX_UPLOAD_BYTES) return "too-big";
  return null;
}

/** The size after fitting the longest side into `maxEdge`; never enlarges. */
export function fitWithin(
  width: number,
  height: number,
  maxEdge: number = MAX_EDGE_PX,
): { width: number; height: number; scaled: boolean } {
  const longest = Math.max(width, height);
  if (!(longest > maxEdge) || !(width > 0) || !(height > 0)) {
    return { width, height, scaled: false };
  }
  const ratio = maxEdge / longest;
  return {
    width: Math.max(1, Math.round(width * ratio)),
    height: Math.max(1, Math.round(height * ratio)),
    scaled: true,
  };
}

export type DecodedImage = { width: number; height: number; source: unknown };

export type ImageIO = {
  /** `null` when the browser cannot decode the file. */
  decode(file: Blob): Promise<DecodedImage | null>;
  /** Redraws on a white canvas of the given size and encodes a JPEG; `null` on failure. */
  encode(image: DecodedImage, width: number, height: number): Promise<Blob | null>;
};

function jpegName(name: string): string {
  const base = name.replace(/\.[^./\\]+$/u, "") || "photo";
  return `${base}.jpg`;
}

/**
 * Validates the file, then returns what to upload: the file itself when it is already small and in
 * a format the server takes, otherwise a downscaled JPEG. Throws `ImageFileError`.
 */
export async function prepareImage(file: File, io: ImageIO = browserImageIO): Promise<File> {
  const problem = checkImageFile(file);
  if (problem) throw new ImageFileError(problem);
  const takenAsIs = SERVER_TYPES.has(file.type);
  const decoded = await io.decode(file).catch(() => null);
  if (!decoded) {
    // The server can still read a JPEG, PNG or WebP the browser failed to decode.
    if (takenAsIs) return file;
    throw new ImageFileError("unreadable");
  }
  const fit = fitWithin(decoded.width, decoded.height);
  if (!fit.scaled && takenAsIs) return file;
  const blob = await io.encode(decoded, fit.width, fit.height).catch(() => null);
  if (!blob) {
    if (takenAsIs) return file;
    throw new ImageFileError("unreadable");
  }
  if (blob.size > MAX_UPLOAD_BYTES) throw new ImageFileError("too-big");
  return new File([blob], jpegName(file.name), { type: "image/jpeg" });
}

// --- the browser implementation -------------------------------------------------------------

type BrowserSource = ImageBitmap | HTMLImageElement;

async function decodeInBrowser(file: Blob): Promise<DecodedImage | null> {
  if (typeof createImageBitmap === "function") {
    try {
      const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
      return { width: bitmap.width, height: bitmap.height, source: bitmap };
    } catch {
      // Fall through to an <img>, which some browsers decode when createImageBitmap refuses.
    }
  }
  if (typeof document === "undefined" || typeof URL.createObjectURL !== "function") return null;
  const href = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = href;
    await img.decode();
    return { width: img.naturalWidth, height: img.naturalHeight, source: img };
  } catch {
    return null;
  } finally {
    URL.revokeObjectURL(href);
  }
}

async function encodeInBrowser(
  image: DecodedImage,
  width: number,
  height: number,
): Promise<Blob | null> {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.fillStyle = "#ffffff"; // a transparent PNG would turn black as a JPEG
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(image.source as BrowserSource, 0, 0, width, height);
  const source = image.source as { close?: () => void };
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
  );
  source.close?.();
  return blob;
}

export const browserImageIO: ImageIO = { decode: decodeInBrowser, encode: encodeInBrowser };
