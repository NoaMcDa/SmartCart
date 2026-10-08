import { describe, expect, it } from "vitest";
import { detectPlatform } from "./platform";

const IPHONE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1";
const ANDROID =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36";
const MAC =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15";
const WINDOWS =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36";
const LINUX = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36";

describe("detectPlatform", () => {
  it("reads iOS, Android and desktop from the user agent", () => {
    expect(detectPlatform({ userAgent: IPHONE })).toBe("ios");
    expect(detectPlatform({ userAgent: ANDROID })).toBe("android");
    expect(detectPlatform({ userAgent: MAC, maxTouchPoints: 0 })).toBe("desktop");
    expect(detectPlatform({ userAgent: WINDOWS })).toBe("desktop");
    expect(detectPlatform({ userAgent: LINUX })).toBe("desktop");
  });

  it("treats a touch Macintosh as an iPad", () => {
    expect(detectPlatform({ userAgent: MAC, maxTouchPoints: 5 })).toBe("ios");
  });

  it("prefers the UA client hint when the browser sends one", () => {
    expect(detectPlatform({ userAgent: LINUX, uaPlatform: "Android" })).toBe("android");
    expect(detectPlatform({ userAgent: "", uaPlatform: "Windows" })).toBe("desktop");
    expect(detectPlatform({ userAgent: "", uaPlatform: "macOS" })).toBe("desktop");
    expect(detectPlatform({ userAgent: "", uaPlatform: "iOS" })).toBe("ios");
  });

  it("answers other for anything it does not recognise", () => {
    expect(detectPlatform({ userAgent: "" })).toBe("other");
    expect(detectPlatform({ userAgent: "SomeSmartTV/1.0" })).toBe("other");
  });

  it("returns one of the four fixed values for the running browser", () => {
    expect(["ios", "android", "desktop", "other"]).toContain(detectPlatform());
  });
});
