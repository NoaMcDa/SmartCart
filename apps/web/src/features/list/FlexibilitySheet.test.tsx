import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { parseRow } from "@/mocks/handlers";
import { dispatch, getListState, resetListStoreForTests } from "@/state/list";
import { FlexibilitySheet } from "./FlexibilitySheet";

function setup() {
  window.localStorage.clear();
  resetListStoreForTests();
  dispatch({ type: "add", rows: [parseRow("חלב"), parseRow("2 רסק עגבניות")] });
  const state = getListState();
  const item = state.items[0]!;
  const onClose = () => {};
  return { item, state, onClose };
}

describe("flexibility sheet", () => {
  beforeEach(() => resetListStoreForTests());

  it("names the product and preselects the current level in a radio group", () => {
    const { item, state, onClose } = setup();
    render(<FlexibilitySheet item={item} flexDefaults={state.flexDefaults} onClose={onClose} />);
    const dialog = screen.getByRole("dialog", { name: "חלב טרי 3%, 1 ליטר" });
    const radios = within(dialog).getAllByRole("radio");
    expect(radios).toHaveLength(3);
    expect(within(dialog).getByRole("radio", { name: /כל מותג/ })).toBeChecked();
    expect(within(dialog).getByRole("radio", { name: /מוצר מדויק/ })).toHaveAccessibleDescription(
      /רק הברקוד שבחרת/,
    );
    expect(
      within(dialog).getByRole("switch", { name: "זכרי בחירה זו לכל סוגי החלב" }),
    ).toHaveAttribute("aria-checked", "false");
  });

  it("saves level, allowed attributes and the category default", () => {
    const { item, state } = setup();
    let closed = 0;
    render(
      <FlexibilitySheet item={item} flexDefaults={state.flexDefaults} onClose={() => closed++} />,
    );
    fireEvent.click(screen.getByRole("radio", { name: /תחליף קרוב/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: "אחוז שומן אחר" }));
    fireEvent.click(screen.getByRole("switch", { name: /זכרי בחירה זו/ }));
    fireEvent.click(screen.getByRole("button", { name: "שמרי" }));
    const next = getListState();
    expect(next.items[0]).toMatchObject({ flexLevel: "close", allow: ["fat_pct"] });
    expect(next.flexDefaults).toEqual({ "dairy.milk": "close" });
    expect(next.items[1]?.flexLevel).toBe("any_brand");
    expect(closed).toBe(1);
  });

  it("cancel discards the changes", () => {
    const { item, state } = setup();
    render(<FlexibilitySheet item={item} flexDefaults={state.flexDefaults} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("radio", { name: /מוצר מדויק/ }));
    expect(screen.queryByRole("checkbox")).toBeNull(); // nothing to allow at the exact level
    fireEvent.click(screen.getByRole("button", { name: "ביטול" }));
    expect(getListState().items[0]?.flexLevel).toBe("any_brand");
  });
});
