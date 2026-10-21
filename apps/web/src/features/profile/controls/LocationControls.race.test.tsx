/**
 * The device-location request outlives the step that asked for it (issue #18, D11): a position that
 * arrives after the person skipped the step, or removed the location, must not be stored.
 */
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it } from "vitest";
import { getProfile, resetProfileCache, setLocation } from "../profileState";
import { LocationControls } from "./LocationControls";

let deliver: (lat: number, lon: number) => void = () => {};

function stubGeolocation() {
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: (ok: PositionCallback) => {
        deliver = (latitude, longitude) =>
          ok({ coords: { latitude, longitude } } as GeolocationPosition);
      },
    },
  });
}

beforeEach(() => {
  window.localStorage.clear();
  resetProfileCache();
  stubGeolocation();
});
afterEach(() => {
  Object.defineProperty(navigator, "geolocation", { value: undefined, configurable: true });
});

it("a position that arrives after the step was left is not stored", async () => {
  const user = userEvent.setup();
  const view = render(<LocationControls />);
  await user.click(screen.getByRole("button", { name: "אישור שימוש במיקום המכשיר" }));
  view.unmount(); // "דלגי" or navigating away while the browser asks
  act(() => deliver(32.0853123, 34.7818456));
  expect(getProfile().location).toBeNull();
  expect(getProfile().consentLocation).toBe(false);
});

it("a position that arrives after the location was removed does not bring it back", async () => {
  setLocation({ lat: 31.898, lon: 35.01, city: "מודיעין-מכבים-רעות", source: "manual" });
  const user = userEvent.setup();
  render(<LocationControls />);
  await user.click(screen.getByRole("button", { name: "אישור שימוש במיקום המכשיר" }));
  await user.click(screen.getByRole("button", { name: "הסרת המיקום" }));
  expect(getProfile().location).toBeNull();
  act(() => deliver(32.0853123, 34.7818456));
  expect(getProfile().location).toBeNull();
  expect(screen.getByRole("button", { name: "אישור שימוש במיקום המכשיר" })).toBeEnabled();
});

it("a position that arrives while the step is open is stored, rounded to the neighborhood", async () => {
  const user = userEvent.setup();
  render(<LocationControls />);
  await user.click(screen.getByRole("button", { name: "אישור שימוש במיקום המכשיר" }));
  act(() => deliver(32.0853123, 34.7818456));
  expect(getProfile().location).toMatchObject({ lat: 32.085, lon: 34.782, source: "device" });
});
