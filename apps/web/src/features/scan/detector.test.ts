import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { startDetector } from "./detector";

function fakeVideo(): HTMLVideoElement {
  const video = document.createElement("video");
  Object.defineProperty(video, "play", { value: () => Promise.resolve(), configurable: true });
  return video;
}

const STREAM = { getTracks: () => [] } as unknown as MediaStream;

type Win = { BarcodeDetector?: unknown };
const win = window as unknown as Win;

describe("native BarcodeDetector", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    delete win.BarcodeDetector;
  });

  it("reports the first read that passes the check digit and ignores misreads", async () => {
    const reads = [[{ rawValue: "5901234123458" }], [], [{ rawValue: "5901234123457" }]];
    const formats: string[][] = [];
    win.BarcodeDetector = class {
      static getSupportedFormats = () => Promise.resolve(["ean_13", "ean_8", "qr_code"]);
      constructor(options: { formats: string[] }) {
        formats.push(options.formats);
      }
      detect = () => Promise.resolve(reads.shift() ?? []);
    };
    const onCode = vi.fn();
    const session = await startDetector(fakeVideo(), STREAM, onCode);
    expect(session.engine).toBe("native");
    expect(formats).toEqual([["ean_13", "ean_8"]]);

    await vi.advanceTimersByTimeAsync(220);
    expect(onCode).not.toHaveBeenCalled(); // wrong check digit
    await vi.advanceTimersByTimeAsync(220 * 3);
    expect(onCode).toHaveBeenCalledTimes(1);
    expect(onCode).toHaveBeenCalledWith("5901234123457");
    await vi.advanceTimersByTimeAsync(1000);
    expect(onCode).toHaveBeenCalledTimes(1); // one result, then it stops
  });

  it("stops polling when stopped", async () => {
    const detect = vi.fn(() => Promise.resolve([]));
    win.BarcodeDetector = class {
      detect = detect;
    };
    const session = await startDetector(fakeVideo(), STREAM, vi.fn());
    await vi.advanceTimersByTimeAsync(220 * 2);
    const calls = detect.mock.calls.length;
    session.stop();
    await vi.advanceTimersByTimeAsync(2000);
    expect(detect.mock.calls.length).toBe(calls);
  });

  it("survives a frame the detector cannot read", async () => {
    let n = 0;
    win.BarcodeDetector = class {
      detect = () => {
        n += 1;
        return n === 1
          ? Promise.reject(new Error("InvalidStateError"))
          : Promise.resolve([{ rawValue: "96385074" }]);
      };
    };
    const onCode = vi.fn();
    await startDetector(fakeVideo(), STREAM, onCode);
    await vi.advanceTimersByTimeAsync(220 * 3);
    expect(onCode).toHaveBeenCalledWith("96385074");
  });
});

describe("zxing fallback", () => {
  afterEach(() => {
    delete win.BarcodeDetector;
    vi.resetModules();
    vi.doUnmock("@zxing/browser");
  });

  it("is used when the browser has no BarcodeDetector for EAN-13", async () => {
    const stop = vi.fn();
    let callback: ((r: { getText: () => string } | undefined) => void) | undefined;
    vi.doMock("@zxing/browser", () => ({
      BrowserMultiFormatReader: class {
        decodeFromStream(
          _stream: unknown,
          _video: unknown,
          cb: (r: { getText: () => string } | undefined) => void,
        ) {
          callback = cb;
          return Promise.resolve({ stop });
        }
      },
    }));
    // The static list says this browser cannot read EAN-13 natively (e.g. only QR codes).
    win.BarcodeDetector = class {
      static getSupportedFormats = () => Promise.resolve(["qr_code"]);
    };
    const { startDetector: start } = await import("./detector");
    const onCode = vi.fn();
    const session = await start(fakeVideo(), STREAM, onCode);
    expect(session.engine).toBe("zxing");

    callback?.({ getText: () => "5901234123450" }); // bad check digit
    expect(onCode).not.toHaveBeenCalled();
    callback?.({ getText: () => "5901234123457" });
    expect(onCode).toHaveBeenCalledWith("5901234123457");
    session.stop();
    expect(stop).toHaveBeenCalled();
  });
});
