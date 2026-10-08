import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { privacyMessages } from "@/i18n/messages/privacy";
import Page from "./page";

describe("privacy policy, finish-round sections (#30)", () => {
  it("is marked as a draft awaiting legal review, under the title", () => {
    render(<Page />);
    expect(screen.getByTestId("privacy-draft")).toHaveTextContent("טיוטה, ממתינה לבדיקה משפטית");
  });

  it("covers beta events, photos, voice, spend and the online-store handoff", () => {
    render(<Page />);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(
      expect.arrayContaining([
        "אירועי שימוש בבטא",
        "תמונות של קבלות ורשימות",
        "הכתבה קולית",
        "מעקב הוצאות ותקציב חודשי",
        "מעבר לחנות המקוונת של הרשת",
      ]),
    );
  });

  const section = (id: string) => {
    render(<Page />);
    return within(document.querySelector(`section[aria-labelledby="${id}"]`) as HTMLElement);
  };

  it("beta events: what is sent, consent and opt-out, and what is never sent", () => {
    const s = section("p-beta");
    s.getByText(/מזהה אקראי של הדפדפן/);
    s.getByText(/זה קורה רק אם הסכמת/);
    s.getByText(/אפשר לצאת בכל רגע בפרופיל/);
    s.getByText(/לא נשמרים: תוכן הרשימה/);
  });

  it("photos: processed in memory and deleted, text not kept, consent and withdrawal", () => {
    const s = section("p-photos");
    s.getByText(/מעובדת בזיכרון בלבד ונמחקת/);
    s.getByText(/הטקסט שנקרא מהתמונה לא נשמר/);
    s.getByText(/הסכמה מפורשת/);
    s.getByText(/לבטל את ההסכמה בכל רגע/);
  });

  it("voice: browser recognition, nothing recorded, transcript not stored", () => {
    const s = section("p-voice");
    s.getByText(/זיהוי הדיבור של הדפדפן/);
    s.getByText(/התמליל לא נשמר אצלנו/);
  });

  it("spend: what is stored, export and deletion", () => {
    const s = section("p-spend");
    s.getByText(/תאריך, החנות, הסכום, מספר הפריטים/);
    s.getByText(/ייצוא של כל הרישומים/);
    s.getByText(/מוחק את התקציב ואת כל רישומי ההוצאה/);
  });

  it("handoff: nothing is fetched and the chain's site has its own policy", () => {
    const s = section("p-handoff");
    s.getByText(/לא מביאים דבר מהאתר שלה/);
    s.getByText(/כפוף למדיניות הפרטיות ולתנאי השימוש שלה/);
  });

  it("keeps the no-sale commitment and has no leftover HTML entities in the new copy", () => {
    render(<Page />);
    expect(screen.getByText(/לא מוכרים ולא מעבירים מידע על משתמשים/)).toBeInTheDocument();
    for (const value of Object.values(privacyMessages.he)) expect(value).not.toContain("&quot;");
  });
});
