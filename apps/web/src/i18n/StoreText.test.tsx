import { render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { LocaleProvider } from "./LocaleProvider";
import { LOCALE_KEY } from "./locales";
import { StoreText } from "./StoreText";

afterEach(() => {
  window.localStorage.clear();
  document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
});

function renderIn(locale: "he" | "ar", ui: React.ReactElement) {
  document.cookie = `${LOCALE_KEY}=${locale}; path=/`;
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

describe("StoreText", () => {
  it("is the plain Hebrew text in Hebrew", () => {
    const { container } = renderIn("he", <StoreText name="רמי לוי · מודיעין" />);
    expect(container.innerHTML).toBe("רמי לוי · מודיעין");
  });

  it("writes known chains in Latin and known cities in Arabic, with no Hebrew mark", () => {
    const { container } = renderIn("ar", <StoreText name="רמי לוי · מודיעין" />);
    expect(container.textContent).toMatch(/Rami Levy/);
    expect(container.textContent).not.toMatch(/[֐-׿]/);
    expect(container.querySelector('[lang="he"]')).toBeNull();
  });

  it("marks only the part it cannot translate as Hebrew", () => {
    const { container } = renderIn("ar", <StoreText name="רמי לוי · עיר לא ידועה" />);
    const marked = container.querySelectorAll('[lang="he"]');
    expect(marked).toHaveLength(1);
    expect(marked[0]?.textContent).toBe("עיר לא ידועה");
    expect(container.textContent).toContain("Rami Levy");
  });

  it("a chain name goes through chainLabel", () => {
    const { container } = renderIn("ar", <StoreText kind="chain" name="שופרסל דיל" />);
    expect(container.textContent).toBe("Shufersal Deal");
  });
});
