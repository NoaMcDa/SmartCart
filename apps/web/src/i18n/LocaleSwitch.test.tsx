import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Price } from "@/components/ui/Price";
import { Bidi } from "./Bidi";
import { LocaleProvider } from "./LocaleProvider";
import { LocaleSwitch } from "./LocaleSwitch";
import { LOCALE_KEY } from "./locales";

const trackEvent = vi.hoisted(() => vi.fn());
vi.mock("@/features/seo/track", () => ({ trackEvent }));

beforeEach(() => {
  trackEvent.mockClear();
});

afterEach(() => {
  window.localStorage.clear();
  document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
  document.documentElement.lang = "he";
});

function mount() {
  return render(
    <LocaleProvider>
      <LocaleSwitch />
    </LocaleProvider>,
  );
}

describe("LocaleSwitch", () => {
  it("is a radio group with each option named in its own language", () => {
    mount();
    const group = screen.getByRole("radiogroup", { name: "שפה" });
    const [he, ar] = within(group).getAllByRole("radio");
    expect(he).toHaveTextContent("עברית");
    expect(ar).toHaveTextContent("العربية");
    expect(he).toHaveAttribute("aria-checked", "true");
    expect(ar).toHaveAttribute("aria-checked", "false");
    expect(within(ar!).getByText("العربية")).toHaveAttribute("lang", "ar");
    expect(within(he!).getByText("עברית")).toHaveAttribute("lang", "he");
  });

  it("switches to Arabic: stores it, sets lang, renames the group and fires locale_changed", async () => {
    mount();
    await userEvent.click(screen.getByRole("radio", { name: "العربية" }));
    expect(document.documentElement.lang).toBe("ar");
    expect(window.localStorage.getItem(LOCALE_KEY)).toBe("ar");
    expect(document.cookie).toContain(`${LOCALE_KEY}=ar`);
    expect(screen.getByRole("radiogroup", { name: "اللغة" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "العربية" })).toHaveAttribute("aria-checked", "true");
    expect(trackEvent).toHaveBeenCalledTimes(1);
    expect(trackEvent).toHaveBeenCalledWith("locale_changed", { locale: "ar" });
  });

  it("does not fire an event when the current language is picked again", async () => {
    mount();
    await userEvent.click(screen.getByRole("radio", { name: "עברית" }));
    expect(trackEvent).not.toHaveBeenCalled();
  });

  it("moves with the arrow keys", async () => {
    mount();
    screen.getByRole("radio", { name: "עברית" }).focus();
    await userEvent.keyboard("{ArrowLeft}"); // RTL: left is "next"
    expect(trackEvent).toHaveBeenCalledWith("locale_changed", { locale: "ar" });
  });
});

describe("Bidi", () => {
  it("isolates a Latin brand name as an LTR run inside Arabic text", () => {
    const { container } = render(
      <p dir="rtl" lang="ar">
        حليب <Bidi>Tnuva</Bidi> طازج
      </p>,
    );
    const run = container.querySelector("span")!;
    expect(run).toHaveAttribute("dir", "ltr");
    expect(run).toHaveAttribute("lang", "en");
    expect(run).toHaveStyle({ unicodeBidi: "isolate" });
  });

  it("keeps a Price an LTR island inside an Arabic sentence", () => {
    const { container } = render(
      <p dir="rtl" lang="ar">
        السلة بـ <Price amount="389.00" />، مع 5 عروض.
      </p>,
    );
    const islands = container.querySelectorAll('span[dir="ltr"]');
    expect(islands).toHaveLength(1);
    expect(islands[0]!.textContent).toBe("₪ 389");
    // The Arabic comma stays outside the island.
    expect(islands[0]!.nextSibling?.textContent?.startsWith("،")).toBe(true);
  });

  it("marks an Arabic run as RTL", () => {
    const { container } = render(<Bidi lang="ar">حليب</Bidi>);
    expect(container.querySelector("span")).toHaveAttribute("dir", "rtl");
  });
});
