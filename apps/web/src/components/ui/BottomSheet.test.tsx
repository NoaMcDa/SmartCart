import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { BottomSheet } from "./BottomSheet";
import { Button } from "./Button";

function Harness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>פתיחה</Button>
      <BottomSheet
        open={open}
        onClose={() => setOpen(false)}
        eyebrow="רמת גמישות לפריט"
        title="חלב טרי 3%, 1 ליטר"
        footer={
          <>
            <Button onClick={() => setOpen(false)}>שמרי</Button>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              ביטול
            </Button>
          </>
        }
      >
        <p>תוכן</p>
      </BottomSheet>
    </>
  );
}

describe("BottomSheet", () => {
  it("closes on Escape pressed right after opening, before focus has moved into the dialog", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "פתיחה" });
    await user.click(opener);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    // Focus moves in on the next animation frame; until then it is still on the opener.
    expect(opener).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(opener).toHaveFocus());
  });

  it("is a labelled modal dialog that takes focus", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "פתיחה" }));
    const dialog = screen.getByRole("dialog", { name: "חלב טרי 3%, 1 ליטר" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    await waitFor(() => expect(screen.getByRole("button", { name: "סגירה" })).toHaveFocus());
  });

  it("traps Tab inside the sheet in both directions", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "פתיחה" }));
    const close = screen.getByRole("button", { name: "סגירה" });
    const cancel = screen.getByRole("button", { name: "ביטול" });
    await waitFor(() => expect(close).toHaveFocus());
    await user.tab({ shift: true });
    expect(cancel).toHaveFocus();
    await user.tab();
    expect(close).toHaveFocus();
  });

  it("closes on Escape and returns focus to the opener", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "פתיחה" });
    await user.click(opener);
    await waitFor(() => expect(screen.getByRole("button", { name: "סגירה" })).toHaveFocus());
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("closes when the scrim is clicked and locks page scroll while open", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "פתיחה" }));
    expect(document.body.style.overflow).toBe("hidden");
    await user.click(screen.getByTestId("sheet-scrim"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("");
  });
});

describe("BottomSheet initial focus", () => {
  it("keeps focus that is already inside the sheet when its first frame runs", () => {
    const frames: FrameRequestCallback[] = [];
    const raf = vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      frames.push(cb);
      return frames.length;
    });
    render(
      <BottomSheet open onClose={() => {}} title="בדיקה">
        <button type="button">ראשון</button>
        <textarea aria-label="שדה" />
      </BottomSheet>,
    );
    const field = screen.getByLabelText("שדה");
    field.focus();
    frames.forEach((cb) => cb(0));
    expect(document.activeElement).toBe(field);
    raf.mockRestore();
  });
});
