import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { LocaleProvider, useLocale } from "./LocaleProvider";
import { LOCALE_KEY } from "./locales";

function Probe() {
  const { locale } = useLocale();
  return <p data-testid="locale">{locale}</p>;
}

function clearCookie() {
  document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
}

beforeEach(() => {
  window.localStorage.clear();
  clearCookie();
  document.documentElement.lang = "he";
  delete document.documentElement.dataset.locale;
});
afterEach(() => {
  window.localStorage.clear();
  clearCookie();
  document.documentElement.lang = "he";
});

describe("LocaleProvider", () => {
  it("follows a language switched in another tab, including <html lang>", () => {
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("locale")).toHaveTextContent("he");

    // The other tab stores the choice (cookie and localStorage); this tab gets a storage event.
    act(() => {
      document.cookie = `${LOCALE_KEY}=ar; path=/`;
      window.localStorage.setItem(LOCALE_KEY, "ar");
      window.dispatchEvent(new StorageEvent("storage", { key: LOCALE_KEY, newValue: "ar" }));
    });
    expect(screen.getByTestId("locale")).toHaveTextContent("ar");
    expect(document.documentElement.lang).toBe("ar");
    expect(document.documentElement.dataset.locale).toBe("ar");
  });

  it("starts from the stored choice without flashing Hebrew on <html>", () => {
    document.cookie = `${LOCALE_KEY}=ar; path=/`;
    document.documentElement.lang = "ar"; // what LOCALE_INIT_SCRIPT did before first paint
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("locale")).toHaveTextContent("ar");
    expect(document.documentElement.lang).toBe("ar");
  });

  it("survives a cookie or storage value that is not a locale", () => {
    document.cookie = `${LOCALE_KEY}=fr; path=/`;
    window.localStorage.setItem(LOCALE_KEY, "{garbage");
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("locale")).toHaveTextContent("he");
    expect(document.documentElement.lang).toBe("he");
  });
});
