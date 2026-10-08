import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearLocalData, LOCAL_DATA_KEYS } from "@/features/profile/storage";
import {
  getImageConsent,
  IMAGE_CONSENT_KEY,
  resetImageConsentForTests,
  setImageConsent,
  subscribeImageConsent,
} from "./imageConsent";

beforeEach(() => {
  window.localStorage.clear();
  resetImageConsentForTests();
});
afterEach(() => vi.restoreAllMocks());

describe("image consent", () => {
  it("is off until the person agrees, under the documented key", () => {
    expect(IMAGE_CONSENT_KEY).toBe("sc-image-consent-v1");
    expect(getImageConsent()).toBe(false);
    setImageConsent(true);
    expect(window.localStorage.getItem("sc-image-consent-v1")).toBe("1");
    expect(getImageConsent()).toBe(true);
  });

  it("withdrawing removes the key and tells listeners", () => {
    const seen = vi.fn();
    const off = subscribeImageConsent(seen);
    setImageConsent(true);
    setImageConsent(false);
    expect(window.localStorage.getItem(IMAGE_CONSENT_KEY)).toBeNull();
    expect(getImageConsent()).toBe(false);
    expect(seen).toHaveBeenCalledTimes(2);
    off();
    setImageConsent(true);
    expect(seen).toHaveBeenCalledTimes(2);
  });

  it("reads anything but 1 as not agreed", () => {
    window.localStorage.setItem(IMAGE_CONSENT_KEY, "true");
    expect(getImageConsent()).toBe(false);
  });

  it("holds the answer in memory when storage throws (a private window)", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(getImageConsent()).toBe(false);
    setImageConsent(true);
    expect(getImageConsent()).toBe(true);
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    setImageConsent(false);
    expect(getImageConsent()).toBe(false);
  });

  it("is part of 'delete my data': the key is listed and clearing removes it and notifies", () => {
    expect(LOCAL_DATA_KEYS).toContain(IMAGE_CONSENT_KEY);
    setImageConsent(true);
    const seen = vi.fn();
    subscribeImageConsent(seen);
    clearLocalData();
    expect(getImageConsent()).toBe(false);
    expect(seen).toHaveBeenCalled();
  });
});
