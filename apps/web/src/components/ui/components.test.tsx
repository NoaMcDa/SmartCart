import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";
import { Card } from "./Card";
import { Chip, FlexChip } from "./Chip";
import { SegmentedControl } from "./SegmentedControl";
import { Skeleton } from "./Skeleton";
import { Stepper } from "./Stepper";
import { Switch } from "./Switch";
import { Tag } from "./Tag";

describe("Button", () => {
  it("defaults to type=button and renders a link when given href", () => {
    render(
      <>
        <Button>השווי</Button>
        <Button href="/compare">להשוואה</Button>
      </>,
    );
    expect(screen.getByRole("button", { name: "השווי" })).toHaveAttribute("type", "button");
    expect(screen.getByRole("link", { name: "להשוואה" })).toHaveAttribute("href", "/compare");
  });
});

describe("FlexChip", () => {
  it.each([
    ["exact", "מוצר מדויק", "lock"],
    ["any_brand", "כל מותג", "tag"],
    ["close", "תחליף קרוב", "refresh"],
  ] as const)("%s reads without color: icon %s plus text", (level, label, icon) => {
    const { container } = render(<FlexChip level={level} />);
    expect(container.textContent).toBe(label);
    expect(container.querySelector(`svg[data-icon="${icon}"]`)).not.toBeNull();
  });

  it("is a labelled button when interactive", async () => {
    const onClick = vi.fn();
    render(<FlexChip level="any_brand" onClick={onClick} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "רמת גמישות: כל מותג" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("toggle chips expose aria-pressed", () => {
    render(
      <Chip selected onClick={() => {}}>
        קרטון או שקית
      </Chip>,
    );
    expect(screen.getByRole("button", { name: "קרטון או שקית" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
});

describe("Tag", () => {
  it.each([
    ["matched", "check"],
    ["unverified", "info"],
    ["differs", "differs"],
    ["missing", "close"],
    ["estimated", "warning"],
  ] as const)("%s carries an icon and text", (variant, icon) => {
    const { container } = render(<Tag variant={variant}>טקסט</Tag>);
    expect(container.querySelector(`svg[data-icon="${icon}"]`)).not.toBeNull();
    expect(container.textContent).toBe("טקסט");
  });
});

describe("Stepper", () => {
  function Harness() {
    const [v, setV] = useState(1);
    return <Stepper value={v} onChange={setV} label="חלב" min={1} max={3} />;
  }

  it("has Hebrew labels, clamps to min/max, and shows the value LTR", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    expect(screen.getByRole("group", { name: "כמות: חלב" })).toBeInTheDocument();
    const dec = screen.getByRole("button", { name: "הפחיתי כמות של חלב" });
    const inc = screen.getByRole("button", { name: "הוסיפי כמות של חלב" });
    expect(dec).toBeDisabled();
    await user.click(inc);
    await user.click(inc);
    expect(screen.getByRole("status")).toHaveTextContent("3");
    expect(inc).toBeDisabled();
    expect(screen.getByRole("status").querySelector('[dir="ltr"]')).toHaveTextContent("3");
  });
});

describe("Switch", () => {
  it("is a labelled role=switch", async () => {
    function Harness() {
      const [on, setOn] = useState(false);
      return <Switch checked={on} onChange={setOn} label="זכרי בחירה זו לכל סוגי החלב" />;
    }
    render(<Harness />);
    const sw = screen.getByRole("switch", { name: "זכרי בחירה זו לכל סוגי החלב" });
    expect(sw).toHaveAttribute("aria-checked", "false");
    await userEvent.setup().click(sw);
    expect(sw).toHaveAttribute("aria-checked", "true");
  });
});

describe("SegmentedControl", () => {
  function Harness() {
    const [v, setV] = useState<"list" | "map">("list");
    return (
      <div dir="rtl">
        <SegmentedControl
          label="תצוגה"
          value={v}
          onChange={setV}
          options={[
            { value: "list", label: "רשימה" },
            { value: "map", label: "מפה" },
          ]}
        />
      </div>
    );
  }

  it("is a radiogroup; ArrowLeft moves forward in RTL", () => {
    render(<Harness />);
    const group = screen.getByRole("radiogroup", { name: "תצוגה" });
    const list = screen.getByRole("radio", { name: "רשימה" });
    expect(list).toHaveAttribute("aria-checked", "true");
    expect(list).toHaveAttribute("tabindex", "0");
    // jsdom does not compute direction from the dir attribute; stub it.
    const spy = vi
      .spyOn(window, "getComputedStyle")
      .mockReturnValue({ direction: "rtl" } as CSSStyleDeclaration);
    fireEvent.keyDown(group, { key: "ArrowLeft" });
    spy.mockRestore();
    expect(screen.getByRole("radio", { name: "מפה" })).toHaveAttribute("aria-checked", "true");
  });
});

describe("Card and Skeleton", () => {
  it("renders the recommended variant and a decorative skeleton", () => {
    const { container } = render(
      <Card as="article" variant="recommended">
        <Skeleton />
      </Card>,
    );
    expect(container.querySelector("article")?.className).toContain("recommended");
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });
});
