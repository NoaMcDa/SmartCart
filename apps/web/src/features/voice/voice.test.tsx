/**
 * Voice list input (issue #65): the sheet's states against a fake recognizer, the events it sends,
 * and the list builder path (mic hidden without support, a dictated list parsed by /parse-list
 * only after the person confirms it).
 */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ListBuilder } from "@/features/list/ListBuilder";
import { server } from "@/mocks/node";
import { resetListStoreForTests } from "@/state/list";
import {
  FakeRecognizer,
  installFakeSpeech,
  removeFakeSpeech,
} from "../../../tests/unit/fakeSpeech";
import { VoiceSheet } from "./VoiceSheet";

const track = vi.hoisted(() => vi.fn());
vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: track,
}));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  server.events.removeAllListeners();
  removeFakeSpeech();
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
  track.mockClear();
  installFakeSpeech();
});

const events = () => track.mock.calls.map(([name, props]) => [name, props]);

function sheet(onAdd = vi.fn(async (_text: string) => 3 as number | null)) {
  const onClose = vi.fn();
  const user = userEvent.setup();
  render(<VoiceSheet open onClose={onClose} onAdd={onAdd} />);
  return { user, onAdd, onClose };
}

describe("the voice sheet", () => {
  it("explains first and does not touch the microphone until the person taps start", () => {
    sheet();
    expect(screen.getByRole("dialog", { name: "הכתבה קולית" })).toBeInTheDocument();
    expect(screen.getByTestId("voice-privacy")).toHaveTextContent("לא מקליטים ולא שומרים אודיו");
    expect(screen.getByTestId("voice-privacy")).toHaveTextContent("הדפדפן יבקש אישור למיקרופון");
    expect(FakeRecognizer.instances).toHaveLength(0);
    expect(track).not.toHaveBeenCalled();
  });

  it("listens in Hebrew, continuous with interim results, and shows what it hears", async () => {
    const { user } = sheet();
    await user.click(screen.getByTestId("voice-start"));
    const rec = FakeRecognizer.last();
    expect(rec).toMatchObject({
      lang: "he-IL",
      continuous: true,
      interimResults: true,
      started: true,
    });
    expect(screen.getByTestId("voice-status")).toHaveTextContent("ממתינה לאישור המיקרופון");

    act(() => rec.begin());
    expect(screen.getByTestId("voice-status")).toHaveTextContent("מקשיבה");
    act(() => rec.hear({ text: "חלב" }, { text: "שתי עגבניות", final: false }));
    expect(screen.getByTestId("voice-live")).toHaveTextContent("חלב");
    expect(screen.getByTestId("voice-live")).toHaveTextContent("שתי עגבניות");
  });

  it("ends in an editable confirm step, and parses only what the person confirms", async () => {
    const { user, onAdd, onClose } = sheet();
    await user.click(screen.getByTestId("voice-start"));
    const rec = FakeRecognizer.last();
    act(() => {
      rec.begin();
      rec.hear({ text: "חלב" }, { text: "שתי רסק עגבניות" }, { text: "סלמון", final: false });
    });
    await user.click(screen.getByTestId("voice-stop"));
    expect(rec.stopped).toBe(true);

    const draft = screen.getByLabelText(/מה שמענו/);
    expect(draft).toHaveValue("חלב\nשתי רסק עגבניות\nסלמון");
    expect(onAdd).not.toHaveBeenCalled(); // nothing is parsed before the confirm
    await user.clear(draft);
    await user.type(draft, "חלב{Enter}2 רסק עגבניות");
    await user.click(screen.getByTestId("voice-add"));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(onAdd).toHaveBeenCalledWith("חלב\n2 רסק עגבניות");
  });

  it("keeps the text and says so when the list could not be read", async () => {
    const { user, onClose } = sheet(vi.fn(async () => null));
    await user.click(screen.getByTestId("voice-start"));
    const rec = FakeRecognizer.last();
    act(() => {
      rec.begin();
      rec.hear({ text: "חלב" });
      rec.finish();
    });
    await user.click(screen.getByTestId("voice-add"));
    expect(await screen.findByRole("alert")).toHaveTextContent("הטקסט נשמר");
    expect(screen.getByLabelText(/מה שמענו/)).toHaveValue("חלב");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("a denied microphone explains how to allow it and leaves typing as the way forward", async () => {
    const { user, onClose } = sheet();
    await user.click(screen.getByTestId("voice-start"));
    act(() => FakeRecognizer.last().fail("not-allowed"));
    expect(screen.getByTestId("voice-error")).toHaveTextContent("הגישה למיקרופון נחסמה");
    expect(screen.getByTestId("voice-error")).toHaveTextContent("להקליד או להדביק");
    await user.click(screen.getByRole("button", { name: "חזרה להקלדה" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("silence ends in a no-speech message with a retry", async () => {
    const { user } = sheet();
    await user.click(screen.getByTestId("voice-start"));
    act(() => {
      FakeRecognizer.last().begin();
      FakeRecognizer.last().finish();
    });
    expect(screen.getByTestId("voice-error")).toHaveTextContent("לא שמענו כלום");
    await user.click(screen.getByRole("button", { name: "ניסיון נוסף" }));
    expect(FakeRecognizer.instances).toHaveLength(2);
  });

  it("a late error keeps what was already heard for the confirm step", async () => {
    const { user } = sheet();
    await user.click(screen.getByTestId("voice-start"));
    act(() => {
      FakeRecognizer.last().begin();
      FakeRecognizer.last().hear({ text: "ביצים" });
      FakeRecognizer.last().fail("network");
    });
    expect(screen.getByLabelText(/מה שמענו/)).toHaveValue("ביצים");
  });

  it("closing while listening aborts the recognizer", async () => {
    const { user, onClose } = sheet();
    await user.click(screen.getByTestId("voice-start"));
    const rec = FakeRecognizer.last();
    act(() => rec.begin());
    await user.click(screen.getByRole("button", { name: "ביטול" }));
    expect(rec.aborted).toBe(true);
    expect(onClose).toHaveBeenCalled();
  });
});

describe("voice events", () => {
  it("voice_started then voice_completed parsed, with the duration and the item count, never the text", async () => {
    const { user } = sheet(vi.fn(async () => 3));
    await user.click(screen.getByTestId("voice-start"));
    expect(events()).toEqual([["voice_started", { engine: "web_speech" }]]);
    act(() => {
      FakeRecognizer.last().begin();
      FakeRecognizer.last().hear({ text: "חלב" });
    });
    await user.click(screen.getByTestId("voice-stop"));
    await user.click(screen.getByTestId("voice-add"));
    await waitFor(() => expect(track).toHaveBeenCalledTimes(2));
    expect(events()[1]).toEqual([
      "voice_completed",
      { outcome: "parsed", duration_ms: expect.any(Number), item_count: 3 },
    ]);
    expect(JSON.stringify(track.mock.calls)).not.toContain("חלב");
  });

  it.each([
    ["not-allowed", "error"],
    ["audio-capture", "error"],
    ["network", "error"],
  ])("a %s failure completes as %s", async (code, outcome) => {
    const { user } = sheet();
    await user.click(screen.getByTestId("voice-start"));
    act(() => FakeRecognizer.last().fail(code));
    await waitFor(() => expect(track).toHaveBeenCalledTimes(2));
    expect(track.mock.calls[1]![1]).toMatchObject({ outcome });
  });

  it("silence completes as empty", async () => {
    const { user } = sheet();
    await user.click(screen.getByTestId("voice-start"));
    act(() => FakeRecognizer.last().finish());
    await waitFor(() => expect(track).toHaveBeenCalledTimes(2));
    expect(track.mock.calls[1]![1]).toMatchObject({ outcome: "empty" });
  });

  it("closing mid-attempt completes once as cancelled; a re-record cancels the first attempt", async () => {
    const { user } = sheet();
    await user.click(screen.getByTestId("voice-start"));
    act(() => {
      FakeRecognizer.last().begin();
      FakeRecognizer.last().hear({ text: "חלב" });
      FakeRecognizer.last().finish();
    });
    await user.click(screen.getByRole("button", { name: "הקלטה מחדש" }));
    // started, cancelled (the first attempt), started (the second)
    expect(
      track.mock.calls.map(([n, p]) => [n, (p as { outcome?: string } | undefined)?.outcome]),
    ).toEqual([
      ["voice_started", undefined],
      ["voice_completed", "cancelled"],
      ["voice_started", undefined],
    ]);
    await user.click(screen.getByRole("button", { name: "ביטול" }));
    expect(track.mock.calls.filter(([n]) => n === "voice_completed")).toHaveLength(2);
  });
});

describe("the list builder", () => {
  it("hides the microphone and shows a hint when the browser cannot recognize speech", async () => {
    removeFakeSpeech();
    render(<ListBuilder />);
    expect(await screen.findByTestId("voice-unsupported")).toHaveTextContent(
      "הכתבה קולית לא זמינה",
    );
    expect(screen.queryByRole("button", { name: "הכתבה קולית" })).not.toBeInTheDocument();
    // Typing still works.
    expect(screen.getByLabelText("הוסיפי פריטים לרשימה")).toBeEnabled();
  });

  it("shows the microphone and no hint when it can", async () => {
    render(<ListBuilder />);
    expect(await screen.findByRole("button", { name: "הכתבה קולית" })).toBeEnabled();
    expect(screen.queryByTestId("voice-unsupported")).not.toBeInTheDocument();
  });

  it("a dictated list goes through /parse-list like a pasted one, after the confirm step", async () => {
    const bodies: unknown[] = [];
    server.events.on("request:start", async ({ request }) => {
      if (request.url.endsWith("/parse-list")) bodies.push(await request.clone().json());
    });
    const user = userEvent.setup();
    render(<ListBuilder />);
    await user.click(await screen.findByRole("button", { name: "הכתבה קולית" }));
    await user.click(screen.getByTestId("voice-start"));
    const rec = FakeRecognizer.last();
    act(() => {
      rec.begin();
      rec.hear({ text: "חלב" }, { text: "2 רסק עגבניות" }, { text: "סלמון" });
    });
    await user.click(screen.getByTestId("voice-stop"));
    expect(bodies).toHaveLength(0); // heard, not parsed
    await user.click(screen.getByTestId("voice-add"));

    await waitFor(() => expect(screen.getAllByTestId("list-row")).toHaveLength(3));
    expect(bodies).toEqual([{ text: "חלב\n2 רסק עגבניות\nסלמון", flex_defaults: {} }]);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText(/נוספו 3 פריטים מההכתבה/)).toBeInTheDocument();
    // The quantity from the speech survived the parser, as for a pasted list.
    const paste = screen.getAllByTestId("list-row").find((r) => r.textContent?.includes("רסק"))!;
    expect(within(paste).getByRole("group")).toHaveTextContent("2");
    // A dictated list is not a paste.
    expect(track.mock.calls.some(([n]) => n === "list_pasted")).toBe(false);
  });
});
