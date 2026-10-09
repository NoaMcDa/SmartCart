import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});

// findBy* and waitFor give up after 1 s by default. Shared CI runners are several times slower than
// a developer machine (the photo sheet downscales an image before it renders), so allow 5 s. A
// passing test still finishes as soon as its element appears.
configure({ asyncUtilTimeout: 5000 });

// jsdom has no matchMedia; tests that care stub it themselves.
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}
