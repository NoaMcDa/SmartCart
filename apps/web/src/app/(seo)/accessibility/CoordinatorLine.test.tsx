import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CoordinatorLine } from "./CoordinatorLine";

const text = () => screen.getByTestId("a11y-coordinator").textContent ?? "";

describe("accessibility coordinator line", () => {
  it("shows the name, the e-mail and the phone as links", () => {
    render(
      <p>
        <CoordinatorLine name="נועה כהן" email="access@smartcart.example" phone="03-555 0100" />
      </p>,
    );
    expect(text()).toBe(
      "רכזת הנגישות: נועה כהן. אפשר לפנות בדוא״ל access@smartcart.example או בטלפון 03-555 0100.",
    );
    expect(screen.getByRole("link", { name: "access@smartcart.example" })).toHaveAttribute(
      "href",
      "mailto:access@smartcart.example",
    );
    const phone = screen.getByRole("link", { name: "03-555 0100" });
    expect(phone).toHaveAttribute("href", "tel:035550100");
    expect(phone).toHaveAttribute("dir", "ltr");
  });

  it("works with an e-mail only, as before", () => {
    render(
      <p>
        <CoordinatorLine email="access@smartcart.example" />
      </p>,
    );
    expect(text()).toBe("אפשר לפנות בדוא״ל access@smartcart.example.");
  });

  it("works with a name only", () => {
    render(
      <p>
        <CoordinatorLine name="נועה כהן" />
      </p>,
    );
    expect(text()).toBe("רכזת הנגישות: נועה כהן. ");
  });

  it("falls back to the 'published before launch' line when nothing is set", () => {
    render(
      <p data-testid="p">
        <CoordinatorLine />
      </p>,
    );
    expect(screen.queryByTestId("a11y-coordinator")).not.toBeInTheDocument();
    expect(screen.getByTestId("p")).toHaveTextContent("פרטי הקשר יפורסמו כאן לפני ההשקה.");
  });
});
