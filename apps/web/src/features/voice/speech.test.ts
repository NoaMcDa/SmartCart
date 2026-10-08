import { afterEach, describe, expect, it } from "vitest";
import {
  FakeRecognizer,
  installFakeSpeech,
  removeFakeSpeech,
} from "../../../tests/unit/fakeSpeech";
import {
  classifyVoiceError,
  getRecognizerCtor,
  readTranscript,
  transcriptText,
  VOICE_MESSAGES,
  type SpeechResultLike,
} from "./speech";

afterEach(removeFakeSpeech);

const result = (text: string, isFinal: boolean): SpeechResultLike =>
  Object.assign([{ transcript: text }], { isFinal });

describe("getRecognizerCtor", () => {
  it("is null when the browser has no speech recognition", () => {
    expect(getRecognizerCtor()).toBeNull();
  });

  it("finds the unprefixed and the webkit-prefixed constructor", () => {
    installFakeSpeech("SpeechRecognition");
    expect(getRecognizerCtor()).toBe(FakeRecognizer);
    removeFakeSpeech();
    installFakeSpeech("webkitSpeechRecognition");
    expect(getRecognizerCtor()).toBe(FakeRecognizer);
  });
});

describe("classifyVoiceError", () => {
  it("maps the recognizer's codes to a reason, and ignores aborted", () => {
    expect(classifyVoiceError("not-allowed")).toBe("denied");
    expect(classifyVoiceError("service-not-allowed")).toBe("denied");
    expect(classifyVoiceError("no-speech")).toBe("no-speech");
    expect(classifyVoiceError("audio-capture")).toBe("no-mic");
    expect(classifyVoiceError("network")).toBe("network");
    expect(classifyVoiceError("language-not-supported")).toBe("language");
    expect(classifyVoiceError("aborted")).toBeNull();
    expect(classifyVoiceError("something-new")).toBe("failed");
  });

  it("every reason has a Hebrew message that points back to typing", () => {
    for (const message of Object.values(VOICE_MESSAGES)) {
      expect(message).toMatch(/[֐-׿]/u);
      expect(message).toMatch(/להקליד|הקלידי|לנסות|נסי/u);
    }
  });
});

describe("readTranscript", () => {
  it("separates finished phrases from the one still being recognized", () => {
    const t = readTranscript([
      result(" חלב ", true),
      result("שתי עגבניות", true),
      result("סלמ", false),
    ]);
    expect(t).toEqual({ finals: ["חלב", "שתי עגבניות"], interim: "סלמ" });
  });

  it("skips empty results and collapses whitespace", () => {
    const t = readTranscript([result("   ", true), result("2   רסק\nעגבניות", true)]);
    expect(t.finals).toEqual(["2 רסק עגבניות"]);
  });

  it("reads the whole list each time, so a repeated event cannot duplicate a phrase", () => {
    const list = [result("חלב", true)];
    expect(readTranscript(list)).toEqual(readTranscript(list));
  });
});

describe("transcriptText", () => {
  it("is one phrase per line, with the unfinished phrase last", () => {
    expect(transcriptText({ finals: ["חלב", "סלמון"], interim: "ביצ" })).toBe("חלב\nסלמון\nביצ");
    expect(transcriptText({ finals: [], interim: "" })).toBe("");
  });
});
