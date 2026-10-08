/**
 * Voice input in Arabic (#73): the recognizer is asked for ar-IL, falls back to ar when the
 * browser does not know the Israeli variant, and the sheet speaks Arabic. Hebrew is unchanged
 * (voice.test.tsx).
 */
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { LOCALE_KEY } from "@/i18n/locales";
import {
  FakeRecognizer,
  installFakeSpeech,
  removeFakeSpeech,
} from "../../../tests/unit/fakeSpeech";
import { VoiceSheet } from "./VoiceSheet";

beforeEach(() => {
  window.localStorage.setItem(LOCALE_KEY, "ar");
  installFakeSpeech();
});
afterEach(() => {
  window.localStorage.clear();
  document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
  document.documentElement.lang = "he";
  removeFakeSpeech();
});

function sheet() {
  const user = userEvent.setup();
  render(
    <LocaleProvider>
      <VoiceSheet open onClose={vi.fn()} onAdd={vi.fn(async () => 1)} />
    </LocaleProvider>,
  );
  return user;
}

describe("the voice sheet in Arabic", () => {
  it("is in Arabic and listens in ar-IL", async () => {
    const user = sheet();
    expect(await screen.findByRole("dialog", { name: "الإملاء الصوتي" })).toBeInTheDocument();
    await user.click(screen.getByTestId("voice-start"));
    expect(FakeRecognizer.last()).toMatchObject({ lang: "ar-IL", continuous: true });
    expect(screen.getByTestId("voice-status")).toHaveTextContent("بانتظار إذن الميكروفون");
  });

  it("falls back to ar when the browser does not know ar-IL", async () => {
    const user = sheet();
    await user.click(await screen.findByTestId("voice-start"));
    const first = FakeRecognizer.last();
    act(() => first.fail("language-not-supported"));
    expect(FakeRecognizer.instances).toHaveLength(2);
    const second = FakeRecognizer.last();
    expect(second.lang).toBe("ar");
    expect(first.aborted).toBe(true);
    act(() => {
      second.begin();
      second.hear({ text: "حليب" });
      second.finish();
    });
    expect(screen.getByTestId("voice-draft")).toHaveValue("حليب");
  });

  it("says the language is unsupported only after both variants failed", async () => {
    const user = sheet();
    await user.click(await screen.findByTestId("voice-start"));
    act(() => FakeRecognizer.last().fail("language-not-supported"));
    act(() => FakeRecognizer.last().fail("language-not-supported"));
    expect(screen.getByTestId("voice-error")).toHaveTextContent(
      "هذا المتصفح لا يتعرّف على الكلام بالعربية",
    );
  });
});
