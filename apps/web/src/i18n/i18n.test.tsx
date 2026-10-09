import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { LocaleProvider, useLocale, useT } from "./LocaleProvider";
import { LOCALE_KEY } from "./locales";
import { defineMessages, format, translate } from "./messages";
import { navMessages } from "./messages/nav";

const demo = defineMessages({
  he: { hello: "שלום {name}" },
  ar: { hello: "مرحبا {name}" },
});

function Probe() {
  const t = useT(demo);
  const { locale, intl, setLocale } = useLocale();
  return (
    <div>
      <p data-testid="text">{t("hello", { name: "נועה" })}</p>
      <p data-testid="intl">{`${locale} ${intl}`}</p>
      <button onClick={() => setLocale("ar")}>ar</button>
    </div>
  );
}

afterEach(() => {
  window.localStorage.clear();
  document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
  document.documentElement.lang = "he";
});

describe("i18n", () => {
  it("fills placeholders and leaves unknown ones", () => {
    expect(format("{a} and {b}", { a: 1 })).toBe("1 and {b}");
    expect(translate(demo, "ar", "hello", { name: "x" })).toBe("مرحبا x");
  });

  it("has the same keys in Hebrew and Arabic for the navigation", () => {
    expect(Object.keys(navMessages.ar).sort()).toEqual(Object.keys(navMessages.he).sort());
  });

  it("renders Hebrew first and switches to Arabic, storing the choice", () => {
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("text").textContent).toBe("שלום נועה");
    expect(screen.getByTestId("intl").textContent).toBe("he he-IL");
    act(() => screen.getByText("ar").click());
    expect(screen.getByTestId("text").textContent).toBe("مرحبا נועה");
    expect(screen.getByTestId("intl").textContent).toBe("ar ar-IL-u-nu-latn");
    expect(window.localStorage.getItem(LOCALE_KEY)).toBe("ar");
    expect(document.documentElement.lang).toBe("ar");
  });

  it("applies a stored Arabic choice after mount", async () => {
    window.localStorage.setItem(LOCALE_KEY, "ar");
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(await screen.findByText("مرحبا נועה")).toBeTruthy();
  });
});
