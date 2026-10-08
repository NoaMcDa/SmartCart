import { ApiError } from "@/api/client";
import { trackEvent } from "@/features/seo/track";
import { ImageFileError } from "./imageFile";

/** Why a photo did not become rows. Each kind has its own message and way forward in the sheet. */
export type PhotoErrorKind =
  | "not-image"
  | "too-big"
  | "unreadable"
  | "consent"
  | "too-large"
  | "type"
  | "quota"
  | "unavailable"
  | "network"
  | "generic";

export function classifyPhotoError(err: unknown): PhotoErrorKind {
  if (err instanceof ImageFileError) return err.reason;
  if (err instanceof ApiError) {
    switch (err.status) {
      case 403:
        return "consent";
      case 413:
        return "too-large";
      case 415:
        return "type";
      case 429:
        return "quota";
      // 501 is the API's "not implemented yet"; 503 is "no OCR provider configured".
      case 501:
      case 503:
        return "unavailable";
      default:
        return "generic";
    }
  }
  // fetch rejects with a TypeError when the request never reached the server.
  return err instanceof TypeError ? "network" : "generic";
}

/** Errors worth another try with the same photo. Refusals need a different photo or a decision. */
export function isRetryable(kind: PhotoErrorKind): boolean {
  return kind === "network" || kind === "generic" || kind === "unavailable";
}

type ImageParsedOutcome = "parsed" | "empty" | "refused" | "error";

/** A refusal is a decision about this photo or this person (type, size, consent, the cap). */
export function outcomeOfError(kind: PhotoErrorKind): ImageParsedOutcome {
  switch (kind) {
    case "not-image":
    case "too-big":
    case "consent":
    case "too-large":
    case "type":
    case "quota":
      return "refused";
    default:
      return "error";
  }
}

/** Milliseconds on a monotonic clock; a function of its own so handlers can time an upload. */
export const now = (): number => performance.now();

const MAX_ITEMS = 200;
const MAX_DURATION_MS = 600_000;
const clamp = (value: number, max: number) =>
  Math.min(max, Math.max(0, Math.round(Number.isFinite(value) ? value : 0)));

/** `image_parsed`: the kind, the outcome and counts. Never the text, the file name or the image. */
export function reportImageParsed(info: {
  kind: "receipt" | "list";
  outcome: ImageParsedOutcome;
  itemCount?: number;
  durationMs?: number;
}): void {
  trackEvent("image_parsed", {
    kind: info.kind,
    outcome: info.outcome,
    ...(info.itemCount === undefined ? {} : { item_count: clamp(info.itemCount, MAX_ITEMS) }),
    ...(info.durationMs === undefined
      ? {}
      : { duration_ms: clamp(info.durationMs, MAX_DURATION_MS) }),
  });
}
