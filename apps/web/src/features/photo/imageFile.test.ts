import { describe, expect, it, vi } from "vitest";
import {
  checkImageFile,
  fitWithin,
  ImageFileError,
  MAX_EDGE_PX,
  MAX_UPLOAD_BYTES,
  prepareImage,
  type DecodedImage,
  type ImageIO,
} from "./imageFile";

const file = (name: string, type: string, bytes = 1000) =>
  new File([new Uint8Array(bytes)], name, { type });

/** A fake browser: every file "decodes" to the given size and re-encodes to `encodedBytes`. */
function fakeIO(size: { width: number; height: number } | null, encodedBytes = 500_000) {
  const encode = vi.fn(async (_img: DecodedImage, w: number, h: number) => {
    void w;
    void h;
    return new Blob([new Uint8Array(encodedBytes)], { type: "image/jpeg" });
  });
  const io: ImageIO = {
    decode: vi.fn(async () => (size ? { ...size, source: {} } : null)),
    encode,
  };
  return { io, encode };
}

describe("checkImageFile", () => {
  it("accepts images up to 8 MB", () => {
    expect(checkImageFile({ type: "image/jpeg", size: 1 })).toBeNull();
    expect(checkImageFile({ type: "image/heic", size: 5_000_000 })).toBeNull();
    expect(checkImageFile({ type: "image/png", size: MAX_UPLOAD_BYTES })).toBeNull();
  });

  it("rejects anything that is not an image", () => {
    expect(checkImageFile({ type: "application/pdf", size: 10 })).toBe("not-image");
    expect(checkImageFile({ type: "text/plain", size: 10 })).toBe("not-image");
    expect(checkImageFile({ type: "", size: 10, name: "notes.txt" })).toBe("not-image");
  });

  it("falls back to the extension when the browser gives no type (HEIC on some phones)", () => {
    expect(checkImageFile({ type: "", size: 10, name: "IMG_0042.HEIC" })).toBeNull();
  });

  it("rejects an image over 8 MB", () => {
    expect(checkImageFile({ type: "image/jpeg", size: MAX_UPLOAD_BYTES + 1 })).toBe("too-big");
  });

  it("reports the type before the size", () => {
    expect(checkImageFile({ type: "video/mp4", size: MAX_UPLOAD_BYTES + 1 })).toBe("not-image");
  });
});

describe("fitWithin", () => {
  it("never enlarges and leaves a small image alone", () => {
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600, scaled: false });
    expect(fitWithin(MAX_EDGE_PX, 100)).toEqual({ width: MAX_EDGE_PX, height: 100, scaled: false });
  });

  it("fits the longest side into 2400 px and keeps the aspect ratio", () => {
    expect(fitWithin(4800, 3600)).toEqual({ width: 2400, height: 1800, scaled: true });
    expect(fitWithin(3000, 4000)).toEqual({ width: 1800, height: 2400, scaled: true });
    const tall = fitWithin(1000, 12_000);
    expect(tall).toEqual({ width: 200, height: 2400, scaled: true });
  });

  it("keeps at least one pixel on the short side", () => {
    expect(fitWithin(100_000, 3)).toEqual({ width: 2400, height: 1, scaled: true });
  });

  it("ignores a size it cannot use", () => {
    expect(fitWithin(0, 0).scaled).toBe(false);
    expect(fitWithin(Number.NaN, 5).scaled).toBe(false);
  });
});

describe("prepareImage", () => {
  it("returns a small JPEG, PNG or WebP untouched", async () => {
    const { io, encode } = fakeIO({ width: 1600, height: 1200 });
    for (const type of ["image/jpeg", "image/png", "image/webp"]) {
      const original = file("a", type);
      expect(await prepareImage(original, io)).toBe(original);
    }
    expect(encode).not.toHaveBeenCalled();
  });

  it("downscales a large photo to a JPEG no longer than 2400 px", async () => {
    const { io, encode } = fakeIO({ width: 4032, height: 3024 });
    const out = await prepareImage(file("IMG_1.png", "image/png", 6_000_000), io);
    expect(encode).toHaveBeenCalledTimes(1);
    expect(encode.mock.calls[0]!.slice(1)).toEqual([2400, 1800]);
    expect(out.type).toBe("image/jpeg");
    expect(out.name).toBe("IMG_1.jpg");
    expect(out.size).toBe(500_000);
  });

  it("redraws a format the server does not take, even when it is small", async () => {
    const { io, encode } = fakeIO({ width: 1000, height: 800 });
    const out = await prepareImage(file("IMG_2.heic", "image/heic"), io);
    expect(encode.mock.calls[0]!.slice(1)).toEqual([1000, 800]);
    expect(out.type).toBe("image/jpeg");
    expect(out.name).toBe("IMG_2.jpg");
  });

  it("sends a JPEG the browser cannot decode as it is", async () => {
    const { io } = fakeIO(null);
    const original = file("b.jpg", "image/jpeg");
    expect(await prepareImage(original, io)).toBe(original);
  });

  it("fails clearly for a format that cannot be decoded or converted", async () => {
    const { io } = fakeIO(null);
    await expect(prepareImage(file("c.heic", "image/heic"), io)).rejects.toMatchObject({
      reason: "unreadable",
    });
    const broken: ImageIO = {
      decode: async () => ({ width: 10, height: 10, source: {} }),
      encode: async () => null,
    };
    await expect(prepareImage(file("d.gif", "image/gif"), broken)).rejects.toBeInstanceOf(
      ImageFileError,
    );
  });

  it("falls back to the original when only the redraw fails", async () => {
    const io: ImageIO = {
      decode: async () => ({ width: 5000, height: 4000, source: {} }),
      encode: async () => {
        throw new Error("canvas");
      },
    };
    const original = file("e.jpg", "image/jpeg", 7_000_000);
    expect(await prepareImage(original, io)).toBe(original);
  });

  it("rejects before decoding when the file is not an image or is over 8 MB", async () => {
    const { io } = fakeIO({ width: 10, height: 10 });
    await expect(prepareImage(file("f.pdf", "application/pdf"), io)).rejects.toMatchObject({
      reason: "not-image",
    });
    await expect(
      prepareImage(file("g.jpg", "image/jpeg", MAX_UPLOAD_BYTES + 1), io),
    ).rejects.toMatchObject({ reason: "too-big" });
    expect(io.decode).not.toHaveBeenCalled();
  });

  it("refuses a result that is still over the limit", async () => {
    const { io } = fakeIO({ width: 9000, height: 9000 }, MAX_UPLOAD_BYTES + 1);
    await expect(prepareImage(file("h.png", "image/png", 7_000_000), io)).rejects.toMatchObject({
      reason: "too-big",
    });
  });
});
