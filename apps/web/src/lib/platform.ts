/**
 * Coarse platform for the native-app decision (#56): "ios", "android", "desktop" or "other".
 *
 * It is read from the user agent client hint (`navigator.userAgentData.platform`) when the browser
 * has one, else from the `User-Agent` string, and nothing finer is kept: no OS version, no device
 * model, no browser version. The result is one of four fixed values so it can travel as a beta
 * event property (D10, D11) and cannot identify a person.
 */
export type Platform = "ios" | "android" | "desktop" | "other";

export type PlatformInput = {
  userAgent?: string;
  /** `navigator.userAgentData?.platform`, e.g. "Android", "Windows", "macOS". */
  uaPlatform?: string;
  maxTouchPoints?: number;
};

const DESKTOP_HINTS = /^(windows|macos|linux|chrome os|chromeos)$/i;

export function detectPlatform(input?: PlatformInput): Platform {
  const nav =
    typeof navigator === "undefined"
      ? undefined
      : (navigator as Navigator & { userAgentData?: { platform?: string } });
  const ua = input?.userAgent ?? nav?.userAgent ?? "";
  const hint = (input ? input.uaPlatform : nav?.userAgentData?.platform) ?? "";
  const touch = input?.maxTouchPoints ?? nav?.maxTouchPoints ?? 0;

  if (/android/i.test(hint)) return "android";
  if (/^(ios|iphone|ipad)$/i.test(hint)) return "ios";
  if (/iPhone|iPad|iPod/.test(ua)) return "ios";
  // iPadOS 13+ asks for the desktop site and says "Macintosh"; a Mac has no touch screen.
  if (/Macintosh/.test(ua) && touch > 1) return "ios";
  if (/Android/i.test(ua)) return "android";
  if (DESKTOP_HINTS.test(hint)) return "desktop";
  if (/Windows NT|Macintosh|X11|CrOS|Linux/.test(ua)) return "desktop";
  return "other";
}
