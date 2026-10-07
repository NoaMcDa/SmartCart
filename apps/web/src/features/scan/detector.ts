/**
 * Barcode detection on a live video stream (issue #39). The native `BarcodeDetector` is used when
 * the browser has it for EAN-13 and EAN-8 (Android Chrome); otherwise `@zxing/browser` is loaded on
 * demand, so the decoder is not part of any other screen's JavaScript. iOS Safari has no native
 * detector, so installed iOS PWAs take the zxing path.
 *
 * Every candidate must pass the EAN check digit before it is reported.
 */
import { isValidEan } from "./barcode";

export type DetectorEngine = "native" | "zxing";

export type ScanSession = { engine: DetectorEngine; stop: () => void };

type NativeDetector = {
  detect(source: CanvasImageSource): Promise<Array<{ rawValue: string }>>;
};
type NativeDetectorCtor = {
  new (options: { formats: string[] }): NativeDetector;
  getSupportedFormats?: () => Promise<string[]>;
};

const POLL_MS = 220;

function nativeCtor(): NativeDetectorCtor | null {
  if (typeof window === "undefined") return null;
  const ctor = (window as unknown as { BarcodeDetector?: NativeDetectorCtor }).BarcodeDetector;
  return typeof ctor === "function" ? ctor : null;
}

/** True when the native detector exists and reads EAN-13 (a stubbed detector may omit the list). */
async function nativeUsable(ctor: NativeDetectorCtor): Promise<boolean> {
  if (typeof ctor.getSupportedFormats !== "function") return true;
  try {
    const formats = await ctor.getSupportedFormats();
    return formats.includes("ean_13");
  } catch {
    return false;
  }
}

async function attach(video: HTMLVideoElement, stream: MediaStream): Promise<void> {
  video.srcObject = stream;
  video.muted = true;
  video.setAttribute("playsinline", "true");
  try {
    await video.play();
  } catch {
    // Autoplay can be refused until the element is visible; the detector keeps polling.
  }
}

/**
 * Starts reading `stream` into `video` and calls `onCode` once with the first valid EAN. The
 * returned session's `stop` ends the loop; the caller stops the stream.
 */
export async function startDetector(
  video: HTMLVideoElement,
  stream: MediaStream,
  onCode: (code: string) => void,
): Promise<ScanSession> {
  const Native = nativeCtor();
  if (Native && (await nativeUsable(Native))) {
    await attach(video, stream);
    const detector = new Native({ formats: ["ean_13", "ean_8"] });
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      if (stopped) return;
      try {
        const found = await detector.detect(video);
        const hit = found.map((f) => f.rawValue).find(isValidEan);
        if (hit && !stopped) {
          stopped = true;
          onCode(hit);
          return;
        }
      } catch {
        // A frame that cannot be read yet is not an error worth showing.
      }
      timer = setTimeout(tick, POLL_MS);
    };
    timer = setTimeout(tick, POLL_MS);
    return {
      engine: "native",
      stop: () => {
        stopped = true;
        if (timer) clearTimeout(timer);
      },
    };
  }

  const [{ BrowserMultiFormatReader }, { BarcodeFormat, DecodeHintType }] = await Promise.all([
    import("@zxing/browser"),
    import("@zxing/library"),
  ]);
  const hints = new Map();
  hints.set(DecodeHintType.POSSIBLE_FORMATS, [BarcodeFormat.EAN_13, BarcodeFormat.EAN_8]);
  const reader = new BrowserMultiFormatReader(hints, {
    delayBetweenScanAttempts: POLL_MS,
  });
  let done = false;
  const controls = await reader.decodeFromStream(stream, video, (result) => {
    if (!result || done) return;
    const text = result.getText();
    if (!isValidEan(text)) return;
    done = true;
    onCode(text);
  });
  return {
    engine: "zxing",
    stop: () => {
      done = true;
      controls.stop();
    },
  };
}
